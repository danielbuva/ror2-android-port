"""Verify native teleporter listener cleanup and same-process restart.

The default ending observes an original loss; an explicit abandon action uses
only the existing offline UI and reports teardown without claiming a game
ending. Both use diagnostic assisted input, all gameplay debug assists off.
"""

import json
import math
import re
import shlex
import time

from common import ROOT, WORK, now, read, sha, write
from device import Device, PACKAGE
from installed_attempt import attempt_from_installed
from nova_bridge import current_errors
from survivor_check import (
    BASE_SURVIVORS,
    FREE_SURVIVORS,
    read_skill_variant_selection,
    skill_variant_catalog_inventory,
)

SPINE_ID = "body-state-spawn-state-auto-nova-spine-bringup"
FIRST_STAGE = "lakes"
HOST_DEADLINE_SECONDS = 600
ABANDON_MIN_LIVE_SECONDS = 60.0
ABANDON_STARTUP_TIMEOUT_SECONDS = 60.0
POLL_SECONDS = 2
LOG_POLL_SECONDS = 10
COMPLETED_REPORT_NAME = "movement-completed-session-1.json"
RESTART_RECT = (32, 390, 350, 60)  # Current source UI rect; never tapped without live report geometry.
DEBUG_ASSISTS = ("invincibility", "highDamage", "fastCharge", "movementBoost", "jumpBoost")
DEFAULT_SURVIVOR = "Commando"
PROFILE_COUNTS = ("appliedRuns", "earnedUnlocks", "availableEarnedUnlocks")
ERROR_PATHS = (
    (("debugAcceleration",), ("error",)),
    (("results",), ("error", "ledgerRecoveryError")),
    (("profile",), ("error",)),
    (("stageProgress",), ("error",)),
    (("moon",), ("error",)),
    (("world", "camera"), ("error",)),
    (("world", "equipment"), ("error",)),
)


def selection(attempt, survivor=DEFAULT_SURVIVOR, skill_variant_override=None):
    """Use a base survivor; locked roster choices are explicitly diagnostic."""
    if survivor not in BASE_SURVIVORS:
        raise ValueError("Use a base survivor catalog name: " + ",".join(BASE_SURVIVORS))
    value = {
        "attempt": attempt,
        "id": SPINE_ID,
        "freePlay": True,
        "selectedSurvivor": survivor,
        "developerSurvivorOverride": survivor not in FREE_SURVIVORS,
        "runSeedOverride": "2",
        "goldshoresRoute": False,
        "debugOptions": {
            "invincibility": False,
            "highDamage": False,
            "fastCharge": False,
            "movementBoost": False,
            "jumpBoost": False,
            "purpose": "Native cleanup/restart observation; automatic input is diagnostic and assisted",
        },
    }
    if skill_variant_override is not None:
        value["developerSkillVariantOverride"] = skill_variant_override
        value["debugOptions"]["purpose"] = (
            "Native cleanup/restart with a per-run skill variant; automatic input is diagnostic and assisted; "
            "no profile or unlock changes"
        )
    return value


def survivor_identity_failures(report, survivor):
    """Fail closed when a report omits or changes the selected base survivor."""
    expected_override = survivor not in FREE_SURVIVORS
    failures = []
    if report.get("selectedSurvivor") != survivor:
        failures.append("selected survivor differs (expected %s, got %s)" % (survivor, report.get("selectedSurvivor")))
    if report.get("developerSurvivorOverride") is not expected_override:
        failures.append("developer survivor override differs (expected %s, got %s)" % (expected_override, report.get("developerSurvivorOverride")))
    return failures


def matches_run(report, pid, attempt, session=None):
    return (
        isinstance(report, dict)
        and str(report.get("pid")) == str(pid)
        and report.get("attempt") == attempt
        and report.get("id") == SPINE_ID
        and (session is None or report.get("session") == session)
    )


def _at(report, path):
    value = report
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def report_errors(report):
    errors = []
    for field in ("firstFailure", "error"):
        if report.get(field):
            errors.append(field + ": " + str(report[field]))
    for path, fields in ERROR_PATHS:
        value = _at(report, path)
        if isinstance(value, dict):
            for field in fields:
                if value.get(field):
                    errors.append(".".join(path + (field,)) + ": " + str(value[field]))
    progress = report.get("stageProgress") or {}
    for index, encounter in enumerate(progress.get("sirenEncounters") or []):
        if isinstance(encounter, dict) and encounter.get("error"):
            errors.append("stageProgress.sirenEncounters[%d].error: %s" % (index, encounter["error"]))
    return errors


def first_stage_errors(report, required=False):
    """Validate source stage identity, zero departures, and the non-Moon scope."""
    phase = report.get("phase")
    if phase not in ("integrated-world-playing", "commando-defeated", "restarting-world", "complete"):
        return []
    failures = []
    stage = report.get("stage")
    progress = report.get("stageProgress")
    if not isinstance(stage, dict) or stage.get("scene") != FIRST_STAGE:
        failures.append("stage geometry identity is not Lakes")
    if not isinstance(progress, dict) or progress.get("current") != FIRST_STAGE:
        failures.append("original stage transport identity is not Lakes")
    if not isinstance(progress, dict) or type(progress.get("transitions")) is not int or progress["transitions"] != 0:
        failures.append("stage transition count is missing or nonzero")
    if not isinstance(progress, dict) or progress.get("transporting") is not False:
        failures.append("stage transport is missing or active")
    moon = report.get("moon") or {}
    if report.get("moonMission") is True or moon.get("loaded") is True or moon.get("gameOver") is True:
        failures.append("Moon mission/loaded/finale state is outside this check")
    if moon.get("state") or moon.get("escapeState"):
        failures.append("Moon encounter or escape state is outside this check")
    if required and (not report.get("integratedWorld") or not report.get("teleporterLoop")):
        failures.append("integrated teleporter contract is missing")
    return failures


def runtime_stop(report, pid, attempt, survivor=DEFAULT_SURVIVOR):
    """Return an immediate terminal reason for a report from this launch."""
    if not matches_run(report, pid, attempt):
        return None
    if survivor_identity_failures(report, survivor):
        return "survivor-selection-mismatch"
    if report_errors(report):
        return "first-failure"
    failures = first_stage_errors(report, required=True)
    if failures:
        return "outside-first-stage-contract"
    return None


def _profile_counts(report):
    profile = report.get("profile") or {}
    if not profile.get("ready"):
        return None
    values = {key: profile.get(key) for key in PROFILE_COUNTS}
    if any(type(value) is not int or value < 0 for value in values.values()):
        return None
    return values


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def session2_ready(report):
    """Wait past the playing-save boundary for a real observed integrated tick."""
    world = report.get("world") or {}
    return (
        _finite_number(world.get("seconds"))
        and world["seconds"] >= 1
        and world.get("ready") is True
        and _finite_number(world.get("health"))
        and world["health"] > 0
        and world.get("diagnosticInputEver") is True
    )


def session1_ready_for_observer(report, survivor):
    """Do not judge observer setup until the first sampled body/guard is ready."""
    world = report.get("world") or {}
    return (
        report.get("session") == 1
        and report.get("phase") == "integrated-world-playing"
        and world.get("ready") is True
        and _finite_number(world.get("health"))
        and world["health"] > 0
        and _finite_number(world.get("maxHealth"))
        and world["maxHealth"] > 0
        and world.get("diagnosticInputEver") is True
        and (survivor != "Engi" or world.get("engiShieldGuardPrepared") is True)
    )


def _debug_assisted_without_gameplay_assists(report):
    options = report.get("debugOptions") or {}
    acceleration = report.get("debugAcceleration") or {}
    active = acceleration.get("active") or {}
    if any(options.get(key) is not False or active.get(key) is not False for key in DEBUG_ASSISTS):
        return False
    events = acceleration.get("events") or []
    diagnostic_event = any(isinstance(event, dict) and event.get("toggle") == "diagnosticInput" and event.get("enabled") is True for event in events)
    return (
        report.get("integratedWorld") is True
        and (report.get("world") or {}).get("diagnosticInputEver") is True
        and diagnostic_event
        and acceleration.get("everAssisted") is True
        and acceleration.get("normalGameAcceptanceEligible") is False
    )


def native_objective_cleanup_failures(objective):
    """Use the same live native listener teardown witnesses for every ending."""
    objective = objective or {}
    failures = []
    if not objective.get("cleaned"):
        failures.append("owned teleporter/actor/context/provider cleanup incomplete")
    if objective.get("nativeHostTeardownObserved") is not True:
        failures.append("native teleporter teardown was not observed")
    if objective.get("nativeHostTeardownServerActive") is not True or objective.get("nativeHostTeardownSynchronous") is not True:
        failures.append("native teardown did not run synchronously with the server active")
    if objective.get("nativeHostTeardownPreAwake") is True:
        failures.append("native teleporter never reached its active lifecycle")
    if objective.get("nativeHostCombatSquads") != 1:
        failures.append("expected exactly one owned native CombatSquad")
    if (objective.get("nativeHostDeathListenersBefore"), objective.get("nativeHostDeathListenersAfter")) != (1, 0):
        failures.append("native death listener counts did not retire from 1 to 0")
    if (objective.get("nativeHostSummonListenersBefore"), objective.get("nativeHostSummonListenersAfter")) != (1, 0):
        failures.append("native summon listener counts did not retire from 1 to 0")
    return failures


def skill_variant_failures(report, requested):
    """Require requested, applied, and post-spawn setup snapshot identities to agree."""
    failures = []
    if report.get("developerSkillVariantOverride") != requested:
        failures.append("per-run skill-variant selector differs")
    override = report.get("developerSkillVariantOverrideReport") or {}
    if override.get("status") != "applied" or override.get("applied") is not True or override.get("assisted") is not True:
        failures.append("per-run native skill-variant override was not applied as assisted")
    if report.get("developerSkillVariantAssisted") is not True:
        failures.append("per-run skill-variant assisted session marker is absent")

    # The override inventory is captured before mutating the copied native
    # master loadout. It identifies catalog families and candidate definitions;
    # the separate survivorSkills inventory observes the live selected loadout.
    pre_mutation_report = {"developerSkillVariantOverrideReport": override}
    pre = skill_variant_catalog_inventory(pre_mutation_report)
    live_report = {"survivorSkills": report.get("survivorSkills") or {}}
    live = skill_variant_catalog_inventory(live_report)
    if pre.get("status") != "valid":
        failures.append("pre-mutation native skill catalog inventory is unavailable or invalid")
        return failures
    if live.get("status") != "valid":
        failures.append("post-spawn setup skill catalog snapshot is unavailable or invalid")
        return failures
    pre_rows = {row["componentIndex"]: row for row in pre["components"]}
    live_rows = {row["componentIndex"]: row for row in live["components"]}
    if live.get("bodyIndex") != pre.get("bodyIndex") or len(live_rows) != len(pre_rows):
        failures.append("pre-mutation and live native catalog inventories identify different bodies/components")
        return failures
    effective = override.get("effectiveSkillVariants")
    if not isinstance(effective, list) or len(effective) != len(pre_rows) or any(
        type(index) is not int or index < 0 for index in effective
    ):
        failures.append("effective native loadout variant vector is missing or invalid")
        return failures
    for entry in requested.get("entries", []):
        component = entry["componentIndex"]
        before = pre_rows.get(component)
        after = live_rows.get(component)
        if (
            before is None
            or after is None
            or before["familyCatalogIndex"] != entry["familyCatalogIndex"]
            or entry["variantIndex"] >= len(before["variants"])
            or before["variants"][entry["variantIndex"]]["skillCatalogIndex"] != entry["skillCatalogIndex"]
        ):
            failures.append("requested skill variant differs from pre-mutation native catalog identity")
            break
        if effective[component] != entry["variantIndex"]:
            failures.append("effective native loadout does not contain the requested variant")
            break
        if (
            after["familyCatalogIndex"] != entry["familyCatalogIndex"]
            or after["selectedLoadoutVariantIndex"] != entry["variantIndex"]
            or after["selectedLoadoutSkillCatalogIndex"] != entry["skillCatalogIndex"]
            or after["runtimeSkillCatalogIndex"] != entry["skillCatalogIndex"]
            or after["runtimeDefinitionStatus"] != "matches-selected-native-loadout"
        ):
            failures.append("post-spawn setup SkillDef snapshot does not match the requested effective variant")
            break
    for component, row in live_rows.items():
        if component >= len(effective) or row["selectedLoadoutVariantIndex"] != effective[component]:
            failures.append("post-spawn setup loadout snapshot differs from the effective variant vector")
            break
    return failures


def combat_output_lifecycle(report, expect_cleaned, label=None):
    """Classify J642 observer teardown/setup, preserving older APK unavailability."""
    if not isinstance(report, dict):
        return {"status": "invalid", "reason": "session report is not an object"}, [
            "survivor combat-output session report is invalid"
        ]
    world = report.get("world") or {}
    if not isinstance(world, dict):
        return {"status": "invalid", "reason": "world report is not an object"}, [
            "survivor combat-output world report is invalid"
        ]
    observer = world.get("survivorCombatOutputs")
    if observer is None:
        return {"status": "unavailable", "reason": "survivorCombatOutputs instrumentation missing"}, []
    if not isinstance(observer, dict):
        return {"status": "invalid", "reason": "observer report is not an object"}, [
            "survivor combat-output observer report is invalid"
        ]
    if expect_cleaned:
        valid = (
            observer.get("cleaned") is True
            and observer.get("attached") is False
            and observer.get("inert") is False
            and not observer.get("observerError")
        )
        expectation = "completed-session combat-output observer did not cleanly detach"
    else:
        valid = (
            observer.get("attached") is True
            and observer.get("cleaned") is False
            and observer.get("inert") is False
            and not observer.get("observerError")
        )
        expectation = "%s combat-output observer is not freshly healthy" % (label or "restarted-session")
    if not valid:
        return {"status": "invalid", "reason": expectation}, [expectation]
    return {"status": "valid", "attached": observer.get("attached"), "cleaned": observer.get("cleaned")}, []


def first_ready_observer_contract(report, survivor):
    """Check setup only on the first genuinely ready body snapshot, if instrumented."""
    if not session1_ready_for_observer(report, survivor):
        return None, []
    return combat_output_lifecycle(report, expect_cleaned=False, label="first-ready session")


def abandon_observation_failures(report, survivor, elapsed, live_started):
    """Require 60 seconds of continuously observed ready first-stage play before UI abandon."""
    failures = []
    if report.get("phase") != "integrated-world-playing" or report.get("session") != 1:
        failures.append("abandon observation is not live session 1")
    world = report.get("world") or {}
    if world.get("ready") is not True:
        failures.append("waiting for a ready integrated world" if live_started is None else "world stopped being ready during observed interval")
    elif not _finite_number(world.get("health")) or world["health"] <= 0 or not _finite_number(world.get("maxHealth")) or world["maxHealth"] <= 0:
        failures.append(
            "waiting for positive player health/maxHealth" if live_started is None else "ready world does not report a living player with positive maxHealth"
        )
    if world.get("diagnosticInputEver") is not True:
        failures.append(
            "waiting for diagnostic input in the live world" if live_started is None else "diagnostic input was not observed throughout the live interval"
        )
    if live_started is None or not _finite_number(world.get("seconds")) or world["seconds"] < ABANDON_MIN_LIVE_SECONDS:
        failures.append("live world report is shorter than the 60 second observation interval")
    if live_started is None or not _finite_number(elapsed) or elapsed < ABANDON_MIN_LIVE_SECONDS:
        failures.append("host did not observe a full 60 second live interval")
    failures.extend(first_stage_errors(report, required=True))
    if survivor == "Engi" and world.get("engiShieldGuardPrepared") is not True:
        failures.append(
            "waiting for Engi shield template guard" if live_started is None else "Engi shield template guard was not prepared throughout the live interval"
        )
    defeat = report.get("playerDefeat") or {}
    if isinstance(defeat, dict):
        events = defeat.get("deathEvents")
        if events is not None and (type(events) is not int or events != 0):
            failures.append("player death event occurred before abandon")
        if defeat.get("deathEntered") is True or defeat.get("bodyDestroyed") is True:
            failures.append("player death lifecycle occurred before abandon")
    results = report.get("results") or {}
    if isinstance(results, dict) and any(results.get(field) is True for field in ("serverEnding", "clientEnding", "reportGenerated", "persisted")):
        failures.append("run ending or result occurred before abandon")
    profile = report.get("profile") or {}
    if isinstance(profile, dict) and profile.get("resultApplied") is True:
        failures.append("profile result was applied before abandon")
    return failures


def cleanup_contract(report, pid, attempt, profile_baseline, survivor=DEFAULT_SURVIVOR, skill_variant_override=None):
    """Require actual active native listener retirement and an excluded loss."""
    if not matches_run(report, pid, attempt, session=1):
        return ["completed-session report identity differs"]
    failures = survivor_identity_failures(report, survivor)
    failures.extend(report_errors(report))
    failures.extend(first_stage_errors(report, required=True))
    if not report.get("success") or not report.get("cleanup") or report.get("phase") != "complete":
        failures.append("completed session did not report successful cleanup")
    objective = report.get("objective") or {}
    if not (report.get("world") or {}).get("cleaned") or not objective.get("cleaned"):
        failures.append("integrated world or teleporter owner remains uncleaned")
    failures.extend(native_objective_cleanup_failures(objective))
    if skill_variant_override is not None:
        failures.extend(skill_variant_failures(report, skill_variant_override))
    _, combat_failures = combat_output_lifecycle(report, expect_cleaned=True)
    failures.extend(combat_failures)
    defeat = report.get("playerDefeat") or {}
    if defeat.get("deathEvents") != 1 or not defeat.get("deathEntered") or not defeat.get("bodyDestroyed"):
        failures.append("session did not finish one original player death")
    results = report.get("results") or {}
    if not results.get("persisted") or not results.get("clientEnding"):
        failures.append("original loss result did not persist before restart")
    profile = report.get("profile") or {}
    if profile.get("assistedExcluded") is not True or profile.get("resultApplied") is not False:
        failures.append("assisted loss was not excluded from profile result application")
    if not _debug_assisted_without_gameplay_assists(report):
        failures.append("diagnostic assistance evidence or all-off debug options differ")
    counts = _profile_counts(report)
    if profile_baseline is None or counts != profile_baseline:
        failures.append("applied-run or earned-unlock counts changed/missing")
    return failures


def restart_contract(report, pid, attempt, profile_baseline, survivor=DEFAULT_SURVIVOR, skill_variant_override=None):
    if not matches_run(report, pid, attempt, session=2):
        return ["same-process restarted session identity differs"]
    failures = survivor_identity_failures(report, survivor)
    failures.extend(report_errors(report))
    failures.extend(first_stage_errors(report, required=True))
    if report.get("phase") != "integrated-world-playing":
        failures.append("second session did not reach live integrated play")
    if not session2_ready(report):
        failures.append("second session did not reach a ready observed integrated tick")
    if skill_variant_override is not None:
        failures.extend(skill_variant_failures(report, skill_variant_override))
    _, combat_failures = combat_output_lifecycle(report, expect_cleaned=False)
    failures.extend(combat_failures)
    if not _debug_assisted_without_gameplay_assists(report):
        failures.append("second session diagnostic input/all-off debug contract differs")
    if profile_baseline is None or _profile_counts(report) != profile_baseline:
        failures.append("second session applied-run or earned-unlock counts changed/missing")
    return failures


def abandon_contract(report, pid, attempt, profile_baseline, survivor=DEFAULT_SURVIVOR, skill_variant_override=None):
    """Require owned session teardown without representing it as a game ending."""
    if not matches_run(report, pid, attempt, session=1):
        return ["abandoned-session report identity differs"]
    failures = survivor_identity_failures(report, survivor)
    failures.extend(report_errors(report))
    failures.extend(first_stage_errors(report, required=True))
    if report.get("phase") != "complete" or report.get("success") is not True or report.get("cleanup") is not True:
        failures.append("abandoned session did not finish successful owned cleanup")
    if not (report.get("world") or {}).get("cleaned"):
        failures.append("integrated world/template cleanup was not observed")
    failures.extend(native_objective_cleanup_failures(report.get("objective")))
    if skill_variant_override is not None:
        failures.extend(skill_variant_failures(report, skill_variant_override))
    _, combat_failures = combat_output_lifecycle(report, expect_cleaned=True)
    failures.extend(combat_failures)
    settings = report.get("settings") or {}
    if settings.get("sessionAbandoned") is not True:
        failures.append("source abandon action was not recorded")
    results = report.get("results") or {}
    if (
        results.get("ready") is not True
        or results.get("serverEnding") is not False
        or results.get("clientEnding") is not False
        or results.get("reportGenerated") is not False
        or results.get("persisted") is not False
    ):
        failures.append("abandon path lacks explicit no-ending/no-result evidence")
    defeat = report.get("playerDefeat")
    if (
        not isinstance(defeat, dict)
        or type(defeat.get("deathEvents")) is not int
        or defeat.get("deathEvents") != 0
        or defeat.get("deathEntered") is not False
        or defeat.get("bodyDestroyed") is not False
    ):
        failures.append("abandon path lacks explicit no-native-death evidence")
    profile = report.get("profile") or {}
    if profile.get("resultApplied") is not False:
        failures.append("abandon path lacks explicit no-profile-result evidence")
    if survivor == "Engi" and (report.get("world") or {}).get("engiShieldGuardReleased") is not True:
        failures.append("Engi shield template guard release was not observed during cleanup")
    counts = _profile_counts(report)
    if profile_baseline is None or counts != profile_baseline:
        failures.append("abandon path changed/missed applied-run or earned-unlock counts")
    if not _debug_assisted_without_gameplay_assists(report):
        failures.append("diagnostic assistance evidence or all-off debug options differ")
    return failures


def ending_contract(report, pid, attempt, profile_baseline, survivor, ending, skill_variant_override=None):
    if ending == "loss":
        return cleanup_contract(report, pid, attempt, profile_baseline, survivor, skill_variant_override)
    if ending == "abandon":
        return abandon_contract(report, pid, attempt, profile_baseline, survivor, skill_variant_override)
    return ["unsupported ending mode: " + str(ending)]


def abandon_control_coordinates(report, key, wm_size_text, window_displays_text):
    """Map reported settings-button geometry only when Unity and Android grids agree."""
    settings = report.get("settings") or {}
    width, height = settings.get("screenWidth"), settings.get("screenHeight")
    x, y = settings.get(key + "X"), settings.get(key + "Y")
    physical_size = parse_display_size(wm_size_text)
    rotation = parse_window_rotation(window_displays_text)
    if not physical_size or rotation is None or type(width) is not int or type(height) is not int:
        return None
    logical_size = physical_size[::-1] if rotation in (90, 270) else physical_size
    if logical_size != (width, height) or not _finite_number(x) or not _finite_number(y):
        return None
    if not (0 <= x < width and 0 <= y < height):
        return None
    return round(x), round(y)


def selector_action(path_state, raw, attempt):
    """Classify selector cleanup without ever deleting malformed or foreign data."""
    if path_state == "absent":
        return "none"
    if path_state != "file":
        return "preserve-invalid-path"
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return "preserve-malformed"
    if isinstance(value, dict) and value.get("attempt") == attempt and value.get("id") == SPINE_ID:
        return "remove-owned"
    return "preserve-foreign"


def parse_display_size(text):
    physical = re.search(r"^Physical size:\s*(\d+)x(\d+)\s*$", text, re.M)
    override = re.search(r"^Override size:\s*(\d+)x(\d+)\s*$", text, re.M)
    selected = override or physical
    return (int(selected.group(1)), int(selected.group(2))) if selected else None


def parse_window_rotation(text):
    values = set(re.findall(r"mDisplayRotation=ROTATION_(0|90|180|270)\b", text))
    return int(next(iter(values))) if len(values) == 1 else None


def restart_mapping(report, wm_size_text, window_displays_text):
    """Record the Android-to-HUD grid mapping before translating the source rect."""
    hud = report.get("hud") or {}
    hud_size = (hud.get("screenWidth"), hud.get("screenHeight"))
    physical_size = parse_display_size(wm_size_text)
    rotation = parse_window_rotation(window_displays_text)
    logical_size = None
    if physical_size and rotation is not None:
        logical_size = physical_size[::-1] if rotation in (90, 270) else physical_size
    mapping = {
        "wm_size_output": wm_size_text,
        "window_displays_output": window_displays_text,
        "physical_size": physical_size,
        "rotation_degrees": rotation,
        "logical_size": logical_size,
        "hud_size": hud_size,
        "coordinates": None,
    }
    if logical_size != hud_size or any(type(value) is not int for value in hud_size):
        return mapping
    screen_width, screen_height = logical_size
    x, y, width, height = RESTART_RECT
    if screen_width >= x + width and screen_height >= y + height:
        mapping["coordinates"] = (x + width // 2, y + height // 2)
    return mapping


def restart_coordinates(report, wm_size_text, window_displays_text):
    """Map the fixed source rect only when display rotation and HUD grids agree."""
    return restart_mapping(report, wm_size_text, window_displays_text)["coordinates"]


def menu_start_coordinates(report):
    hud = report.get("hud") or {}
    x, y = hud.get("menuStartX"), hud.get("menuStartY")
    width, height = hud.get("screenWidth"), hud.get("screenHeight")
    if not all(type(value) in (int, float) for value in (x, y)):
        return None
    if type(width) is not int or type(height) is not int or not (0 <= x < width and 0 <= y < height):
        return None
    return round(x), round(y)


def _read_raw(device, path):
    return device.sh("cat", path, check=False)


def _read_json(device, path):
    raw = _read_raw(device, path)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _remote_path_state(device, path):
    quoted = shlex.quote(path)
    script = (
        "if [ -L " + quoted + " ]; then printf symlink; "
        "elif [ -f " + quoted + " ]; then printf file; "
        "elif [ -e " + quoted + " ]; then printf other; "
        "else printf absent; fi"
    )
    return device.sh("sh", "-c", script, check=False).strip()


def _same_process(device, pid):
    return device.sh("pidof", PACKAGE, check=False).strip() == str(pid)


def _stop_process(device, pid, deadline=5):
    device.sh("am", "force-stop", PACKAGE, check=False)
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if not pid or not _same_process(device, pid):
            return True
        time.sleep(0.25)
    return not pid or not _same_process(device, pid)


def require_lab_available():
    if (ROOT / "work/coordination/claude-r9.lock").exists():
        raise RuntimeError("Parallel session holds the editor/device; completed-session check must wait for its coordination lock")


class SessionCleanupDevice(Device):
    def __init__(self):
        require_lab_available()
        super().__init__()

    def cmd(self, *args, **kwargs):
        require_lab_available()
        return super().cmd(*args, **kwargs)


def check_session_cleanup(survivor=DEFAULT_SURVIVOR, ending="loss", skill_variants=None):
    if ending not in ("loss", "abandon"):
        raise ValueError("Use ending loss or abandon")
    if survivor not in BASE_SURVIVORS:
        raise ValueError("Use a base survivor catalog name: " + ",".join(BASE_SURVIVORS))
    skill_variant_override = (
        read_skill_variant_selection(skill_variants, survivor) if skill_variants is not None else None
    )
    device = SessionCleanupDevice()
    installed = device.owned()
    storage = device.storage()
    mode = device.settings["storage_mode"]
    if installed.get("storage", {}).get("mode") != mode or storage.get("mode") != mode:
        raise RuntimeError("Owned APK storage differs from selected-device policy")
    expected_prefix = "/data/app/" if mode == "internal" else "/mnt/expand/" + str(storage.get("uuid")) + "/"
    if expected_prefix not in installed.get("package_path", ""):
        raise RuntimeError("Owned APK placement differs from selected live storage")
    build = read(WORK / "config/current-build.json")
    if not build.get("success") or not build.get("apk") or not installed.get("apk_sha256"):
        raise RuntimeError("Current build or installed ownership receipt is incomplete")
    artifact_hash = sha(build["apk"])
    if artifact_hash != build.get("apk_sha256") or artifact_hash != installed.get("apk_sha256"):
        raise RuntimeError("Current APK artifact hash, build receipt, and installed receipt differ")
    attempt = attempt_from_installed(installed)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    if not runtime.endswith("/Android/data/" + PACKAGE + "/files"):
        raise RuntimeError("Selected package runtime path is outside its app-private directory")
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    completed_path = runtime + "/" + COMPLETED_REPORT_NAME
    if _remote_path_state(device, selector) != "absent":
        raise RuntimeError("Existing diagnostic selector; preserve it")

    out = device.evidence_directory("experiments", "session-cleanup", now())
    out.mkdir(parents=True, exist_ok=False)
    device.evidence_directory("experiments", "session-cleanup", out.name)
    value = selection(attempt, survivor, skill_variant_override)
    write(out / "selection.json", value)
    frozen = {
        "ending_mode": ending,
        "serial": device.serial,
        "package": PACKAGE,
        "apk_sha256": artifact_hash,
        "apk_identity_evidence": "current APK artifact hash matches build and installed ownership receipts; installed package bytes are receipt-backed, not independently rehashed",
        "attempt": attempt,
        "storage_mode": mode,
        "scope": (
            "diagnostic automatic input; no gameplay debug assists; "
            + ("source UI abandon with no original ending/result" if ending == "abandon" else "ordinary native loss/restart")
        ),
        "selected_survivor": survivor,
        "developer_survivor_override": survivor not in FREE_SURVIVORS,
        "skill_variant_override": skill_variant_override,
    }
    write(out / "frozen.json", frozen)

    pid = None
    final = None
    completed = None
    profile_baseline = None
    first_live_combat_output = None
    abandon_live_at = None
    abandon_startup_at = None
    stop = "deadline"
    first_failure = None
    observed_session1_defeat = False
    restart_sent = False
    started_from_menu = False
    session2_menu_start_sent = False
    session2_menu_observed = False
    direct_start_observed = False
    settings_open_sent = False
    abandon_input_sent = False
    started = time.monotonic()
    next_log = 0.0
    cleanup_errors = []
    runtime_errors = []

    def fail(reason):
        nonlocal stop, first_failure
        stop = reason
        if first_failure is None:
            first_failure = reason

    try:
        for path, label in ((report_path, "prior-current-report.json"), (completed_path, "prior-completed-session-1.json")):
            state = _remote_path_state(device, path)
            if state == "absent":
                continue
            if state != "file":
                raise RuntimeError("Refusing non-file app-private report path: " + path.rsplit("/", 1)[-1])
            prior = _read_raw(device, path)
            (out / label).write_text(prior)
            device.sh("rm", "-f", path)
            if _remote_path_state(device, path) != "absent":
                raise RuntimeError("Could not clear the exact stale report target")
        device.cmd("push", str(out / "selection.json"), selector)
        launch = device.launch()
        pid = str(launch["pid"])
        write(out / "launch.json", {"pid": pid, **frozen})
        if not device.display(True):
            raise RuntimeError("Selected device display cannot be awakened for the existing on-screen controls")

        while time.monotonic() - started < HOST_DEADLINE_SECONDS:
            if not _same_process(device, pid):
                fail("process-exited")
                break
            current = _read_json(device, report_path)
            if current and matches_run(current, pid, attempt):
                final = current
                if current.get("session") not in (1, 2):
                    fail("unexpected-session-index")
                    break
                identity_failures = survivor_identity_failures(current, survivor)
                if identity_failures:
                    fail("survivor-selection-mismatch")
                    first_failure = identity_failures[0]
                    break
                reason = runtime_stop(current, pid, attempt, survivor)
                if reason:
                    fail(reason)
                    details = report_errors(current)
                    if details and first_failure == reason:
                        first_failure = details[0]
                    break
                phase = current.get("phase")
                if phase == "offline-start-menu":
                    if survivor not in FREE_SURVIVORS:
                        fail("unexpected-menu-for-diagnostic-override")
                        break
                    if current.get("session") == 1 and not started_from_menu:
                        coords = menu_start_coordinates(current)
                        if coords is None:
                            fail("offline-menu-start-control-unavailable")
                            break
                        device.sh("input", "tap", str(coords[0]), str(coords[1]))
                        started_from_menu = True
                    elif current.get("session") == 2 and ending == "abandon":
                        session2_menu_observed = True
                        if not session2_menu_start_sent:
                            completed = _read_json(device, completed_path)
                            if not isinstance(completed, dict):
                                fail("completed-session-report-unavailable-before-session-2-menu")
                                break
                            failures = abandon_contract(
                                completed, pid, attempt, profile_baseline, survivor, skill_variant_override
                            )
                            if failures:
                                fail("completed-session-cleanup-failed-before-session-2-menu")
                                first_failure = failures[0]
                                break
                            coords = menu_start_coordinates(current)
                            if coords is None:
                                fail("session-2-offline-menu-start-control-unavailable")
                                break
                            write(
                                out / "session-2-menu-start.json",
                                {
                                    "session": current.get("session"),
                                    "phase": phase,
                                    "coordinates": coords,
                                    "completed_attempt": completed.get("attempt"),
                                    "completed_session": completed.get("session"),
                                    "completed_phase": completed.get("phase"),
                                },
                            )
                            device.sh("input", "tap", str(coords[0]), str(coords[1]))
                            session2_menu_start_sent = True
                if current.get("session") == 1 and phase == "integrated-world-playing":
                    if skill_variant_override is not None:
                        variant_failures = skill_variant_failures(current, skill_variant_override)
                        if variant_failures:
                            fail("skill-variant-contract-failed")
                            first_failure = variant_failures[0]
                            break
                    if first_live_combat_output is None:
                        observer_state, observer_failures = first_ready_observer_contract(current, survivor)
                        if observer_state is not None:
                            first_live_combat_output = observer_state
                        if observer_failures:
                            fail("first-live-combat-output-observer-unhealthy")
                            first_failure = observer_failures[0]
                            break
                    if survivor in FREE_SURVIVORS and not started_from_menu:
                        fail("ordinary-menu-start-not-observed")
                        break
                    if survivor not in FREE_SURVIVORS:
                        direct_start_observed = True
                    if profile_baseline is None:
                        profile_baseline = _profile_counts(current)
                        if profile_baseline is None:
                            fail("first-live-profile-baseline-unavailable")
                            break
                        write(out / "first-live-session.json", current)
                    if ending == "abandon" and not abandon_input_sent:
                        observed_world = current.get("world") or {}
                        if abandon_startup_at is None:
                            abandon_startup_at = time.monotonic()
                        if (
                            abandon_live_at is None
                            and observed_world.get("ready") is True
                            and _finite_number(observed_world.get("health"))
                            and observed_world["health"] > 0
                            and _finite_number(observed_world.get("maxHealth"))
                            and observed_world["maxHealth"] > 0
                            and observed_world.get("diagnosticInputEver") is True
                            and (survivor != "Engi" or observed_world.get("engiShieldGuardPrepared") is True)
                        ):
                            abandon_live_at = time.monotonic()
                        observation_failures = abandon_observation_failures(
                            current,
                            survivor,
                            time.monotonic() - abandon_live_at if abandon_live_at is not None else 0.0,
                            abandon_live_at,
                        )
                        waiting_for_minute = any(
                            failure
                            in (
                                "live world report is shorter than the 60 second observation interval",
                                "host did not observe a full 60 second live interval",
                                "waiting for a ready integrated world",
                                "waiting for diagnostic input in the live world",
                                "waiting for positive player health/maxHealth",
                                "waiting for Engi shield template guard",
                            )
                            for failure in observation_failures
                        )
                        blocking_failures = [
                            failure
                            for failure in observation_failures
                            if failure
                            not in (
                                "live world report is shorter than the 60 second observation interval",
                                "host did not observe a full 60 second live interval",
                                "waiting for a ready integrated world",
                                "waiting for diagnostic input in the live world",
                                "waiting for positive player health/maxHealth",
                                "waiting for Engi shield template guard",
                            )
                        ]
                        if blocking_failures:
                            fail("abandon-observation-contract-failed")
                            first_failure = blocking_failures[0]
                            break
                        if abandon_live_at is None and time.monotonic() - abandon_startup_at >= ABANDON_STARTUP_TIMEOUT_SECONDS:
                            fail("abandon-world-startup-timeout")
                            first_failure = "positive health, diagnostic input, and required Engi guard were not observed within 60 seconds"
                            break
                        if waiting_for_minute:
                            # Keep observing the same report stream; elapsed host time
                            # alone is not enough until the in-game stopwatch also reaches 60 s.
                            pass
                        else:
                            settings = current.get("settings") or {}
                            if not settings_open_sent:
                                coords = abandon_control_coordinates(
                                    current,
                                    "button",
                                    device.sh("wm", "size"),
                                    device.sh("dumpsys", "window", "displays"),
                                )
                                if coords is None:
                                    fail("abandon-settings-control-geometry-unavailable")
                                    break
                                device.sh("input", "tap", str(coords[0]), str(coords[1]))
                                settings_open_sent = True
                            elif settings.get("visible") is True and settings.get("canEndRun") is True:
                                coords = abandon_control_coordinates(
                                    current,
                                    "endRunButton",
                                    device.sh("wm", "size"),
                                    device.sh("dumpsys", "window", "displays"),
                                )
                                if coords is None:
                                    fail("abandon-confirm-control-geometry-unavailable")
                                    break
                                device.sh("input", "tap", str(coords[0]), str(coords[1]))
                                abandon_input_sent = True
                if ending == "abandon" and current.get("session") == 1 and phase == "commando-defeated":
                    fail("original-loss-occurred-before-abandon")
                    break
                if current.get("session") == 1 and phase == "commando-defeated" and not observed_session1_defeat:
                    if profile_baseline is None:
                        fail("first-live-profile-baseline-unavailable")
                        break
                    observed_session1_defeat = True
                    results = current.get("results") or {}
                    if not results.get("persisted") or not results.get("clientEnding"):
                        fail("death-result-not-persisted")
                        break
                    wm_size = device.sh("wm", "size")
                    displays = device.sh("dumpsys", "window", "displays")
                    mapping = restart_mapping(current, wm_size, displays)
                    write(out / "restart-display-mapping.json", mapping)
                    coords = mapping["coordinates"]
                    if coords is None:
                        fail("restart-control-display-mapping-unavailable")
                        break
                    device.sh("input", "tap", str(coords[0]), str(coords[1]))
                    restart_sent = True
                if current.get("session") == 2 and phase == "integrated-world-playing" and session2_ready(current):
                    completed = _read_json(device, completed_path)
                    failures = ending_contract(
                        completed or {}, pid, attempt, profile_baseline, survivor, ending, skill_variant_override
                    )
                    if failures:
                        fail("completed-session-cleanup-failed")
                    elif ending == "loss" and (not observed_session1_defeat or not restart_sent):
                        fail("loss-to-restart-observations-incomplete")
                    elif ending == "abandon" and (not abandon_input_sent or not settings_open_sent):
                        fail("abandon-to-restart-observations-incomplete")
                    elif ending == "abandon" and survivor in FREE_SURVIVORS and not session2_menu_start_sent:
                        fail("session-2-ordinary-menu-start-not-observed")
                    elif survivor in FREE_SURVIVORS and not started_from_menu:
                        fail("ordinary-menu-start-not-observed")
                    elif survivor not in FREE_SURVIVORS and not direct_start_observed:
                        fail("direct-diagnostic-start-not-observed")
                    else:
                        failures = restart_contract(
                            current, pid, attempt, profile_baseline, survivor, skill_variant_override
                        )
                        if failures:
                            fail("restart-contract-failed")
                        else:
                            stop = "same-process-restart"
                    break
                if current.get("session") == 2 and phase in ("commando-defeated", "complete"):
                    fail("second-session-ended-before-live-observation")
                    break
            if time.monotonic() >= next_log:
                logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S", check=False)
                runtime_errors = current_errors(logs, pid)
                if runtime_errors:
                    fail("first-runtime-log-error")
                    if first_failure == "first-runtime-log-error":
                        first_failure = runtime_errors[0]
                    break
                next_log = time.monotonic() + LOG_POLL_SECONDS
            time.sleep(POLL_SECONDS)
    except Exception as error:
        fail("runner-error")
        if first_failure == "runner-error":
            first_failure = str(error)
    finally:
        try:
            if pid:
                logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S", check=False)
                (out / "current-process.log").write_text(logs)
                runtime_errors = current_errors(logs, pid) or runtime_errors
                if runtime_errors:
                    if first_failure is None:
                        first_failure = runtime_errors[0]
                    stop = "first-runtime-log-error" if stop == "same-process-restart" else stop
        except Exception as error:
            cleanup_errors.append("log capture: " + str(error))
        try:
            state = _remote_path_state(device, selector)
            raw = _read_raw(device, selector) if state == "file" else ""
            action = selector_action(state, raw, attempt)
            if action == "remove-owned":
                device.sh("rm", "-f", selector)
                if _remote_path_state(device, selector) != "absent":
                    cleanup_errors.append("owned selector remains after removal")
            elif action not in ("none",):
                cleanup_errors.append("selector " + action + "; preserved it")
        except Exception as error:
            cleanup_errors.append("selector cleanup: " + str(error))
        try:
            if not _stop_process(device, pid):
                cleanup_errors.append("selected process remained after force-stop")
        except Exception as error:
            cleanup_errors.append("process cleanup: " + str(error))
        try:
            if not device.display(False):
                cleanup_errors.append("display did not confirm sleep")
        except Exception as error:
            cleanup_errors.append("display sleep: " + str(error))

    failures = []
    if stop != "same-process-restart":
        failures.append("stopped: " + stop)
    if not observed_session1_defeat:
        if ending == "loss":
            failures.append("session-1 defeat was not observed")
    if ending == "loss" and not restart_sent:
        failures.append("restart input was not sent")
    if ending == "abandon" and not abandon_input_sent:
        failures.append("abandon UI input was not sent")
    if survivor in FREE_SURVIVORS and not started_from_menu:
        failures.append("ordinary menu start was not observed")
    if ending == "abandon" and survivor in FREE_SURVIVORS and not session2_menu_start_sent:
        failures.append("session-2 ordinary menu start was not observed")
    if survivor not in FREE_SURVIVORS and not direct_start_observed:
        failures.append("direct diagnostic start was not observed")
    if not completed or not pid:
        failures.append("no current-launch completed-session report")
    else:
        failures.extend(
            ending_contract(completed, pid, attempt, profile_baseline, survivor, ending, skill_variant_override)
        )
    if not final or not pid:
        failures.append("no current-launch restarted-session report")
    else:
        failures.extend(restart_contract(final, pid, attempt, profile_baseline, survivor, skill_variant_override))
    if runtime_errors:
        failures.append("current-process runtime errors: " + str(runtime_errors[:3]))
        if first_failure is None:
            first_failure = "final-runtime-log-error"
    failures.extend(cleanup_errors)
    result = {
        "success": not failures,
        "ending_mode": ending,
        "stop": stop,
        "first_failure": first_failure,
        "failures": failures,
        "pid": pid,
        "attempt": attempt,
        "selected_survivor": survivor,
        "developer_survivor_override": survivor not in FREE_SURVIVORS,
        "skill_variant_override": skill_variant_override,
        "skill_variant_evidence": (
            {"type": "post-spawn-setup-snapshot", "continuous": False}
            if skill_variant_override is not None
            else None
        ),
        "abandon_ui": {"settings_open_sent": settings_open_sent, "end_run_sent": abandon_input_sent},
        "session2_menu_ui": {"observed": session2_menu_observed, "start_sent": session2_menu_start_sent},
        "apk_sha256": artifact_hash,
        "serial": device.serial,
        "profile_baseline": profile_baseline,
        "profile_completed": _profile_counts(completed) if completed else None,
        "profile_restarted": _profile_counts(final) if final else None,
        "runtime_errors": runtime_errors,
        "completed_session": completed,
        "restarted_session": final,
        "combat_output_lifecycle": {
            "first_ready_session_1": first_live_combat_output,
            "completed": combat_output_lifecycle(completed, expect_cleaned=True)[0] if completed else None,
            "restarted": combat_output_lifecycle(final, expect_cleaned=False)[0] if final else None,
        },
        "evidence": str(out.relative_to(WORK.parent)),
    }
    write(out / "result.json", result)
    summary = {
        "success": result["success"],
        "ending_mode": ending,
        "stop": result["stop"],
        "failures": result["failures"],
        "apk": artifact_hash,
        "evidence": result["evidence"],
        "skill_variant_override": skill_variant_override,
        "skill_variant_evidence": result["skill_variant_evidence"],
        "combat_output_lifecycle": result["combat_output_lifecycle"],
        "profile_snapshots": {
            "first_live_session": profile_baseline,
            "completed": result["profile_completed"],
            "restarted": result["profile_restarted"],
        },
    }
    if failures:
        primary = first_failure or stop
        raise RuntimeError("Session cleanup check failed (" + str(primary) + "); see " + result["evidence"])
    return summary
