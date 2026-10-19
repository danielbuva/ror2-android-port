"""Verify native teleporter listener cleanup and a same-process restart.

This check uses the existing automatic Nova route, which is diagnostic and
assisted. It keeps every gameplay debug assist off and never injects damage,
rewards, stage transitions, or lifecycle calls.
"""

import json
import math
import re
import shlex
import time

from common import ROOT, WORK, now, read, sha, write
from device import Device, PACKAGE
from nova_bridge import current_errors

SPINE_ID = "body-state-spawn-state-auto-nova-spine-bringup"
FIRST_STAGE = "lakes"
HOST_DEADLINE_SECONDS = 600
POLL_SECONDS = 2
LOG_POLL_SECONDS = 10
COMPLETED_REPORT_NAME = "movement-completed-session-1.json"
RESTART_RECT = (32, 390, 350, 60)  # Current source UI rect; never tapped without live report geometry.
DEBUG_ASSISTS = ("invincibility", "highDamage", "fastCharge", "movementBoost", "jumpBoost")
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


def selection(attempt):
    """Use the existing playable spine and its ordinary loss/restart flow."""
    return {
        "attempt": attempt,
        "id": SPINE_ID,
        "freePlay": True,
        "selectedSurvivor": "Commando",
        "developerSurvivorOverride": False,
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


def runtime_stop(report, pid, attempt):
    """Return an immediate terminal reason for a report from this launch."""
    if not matches_run(report, pid, attempt):
        return None
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


def cleanup_contract(report, pid, attempt, profile_baseline):
    """Require actual active native listener retirement and an excluded loss."""
    if not matches_run(report, pid, attempt, session=1):
        return ["completed-session report identity differs"]
    failures = report_errors(report)
    failures.extend(first_stage_errors(report, required=True))
    if not report.get("success") or not report.get("cleanup") or report.get("phase") != "complete":
        failures.append("completed session did not report successful cleanup")
    objective = report.get("objective") or {}
    if not (report.get("world") or {}).get("cleaned") or not objective.get("cleaned"):
        failures.append("integrated world or teleporter owner remains uncleaned")
    if not objective.get("nativeHostTeardownObserved"):
        failures.append("native teleporter teardown was not observed")
    if not objective.get("nativeHostTeardownServerActive") or not objective.get("nativeHostTeardownSynchronous"):
        failures.append("native teardown did not run synchronously with the server active")
    if objective.get("nativeHostTeardownPreAwake"):
        failures.append("native teleporter never reached its active lifecycle")
    if objective.get("nativeHostCombatSquads") != 1:
        failures.append("expected exactly one owned native CombatSquad")
    if (objective.get("nativeHostDeathListenersBefore"), objective.get("nativeHostDeathListenersAfter")) != (1, 0):
        failures.append("native death listener counts did not retire from 1 to 0")
    if (objective.get("nativeHostSummonListenersBefore"), objective.get("nativeHostSummonListenersAfter")) != (1, 0):
        failures.append("native summon listener counts did not retire from 1 to 0")
    defeat = report.get("playerDefeat") or {}
    if defeat.get("deathEvents") != 1 or not defeat.get("deathEntered") or not defeat.get("bodyDestroyed"):
        failures.append("session did not finish one original player death")
    results = report.get("results") or {}
    if not results.get("persisted") or not results.get("clientEnding"):
        failures.append("original loss result did not persist before restart")
    profile = report.get("profile") or {}
    if not profile.get("assistedExcluded") or profile.get("resultApplied"):
        failures.append("assisted loss was not excluded from profile result application")
    if not _debug_assisted_without_gameplay_assists(report):
        failures.append("diagnostic assistance evidence or all-off debug options differ")
    counts = _profile_counts(report)
    if profile_baseline is None or counts != profile_baseline:
        failures.append("applied-run or earned-unlock counts changed/missing")
    return failures


def restart_contract(report, pid, attempt, profile_baseline):
    if not matches_run(report, pid, attempt, session=2):
        return ["same-process restarted session identity differs"]
    failures = report_errors(report)
    failures.extend(first_stage_errors(report, required=True))
    if report.get("phase") != "integrated-world-playing":
        failures.append("second session did not reach live integrated play")
    if not session2_ready(report):
        failures.append("second session did not reach a ready observed integrated tick")
    if not _debug_assisted_without_gameplay_assists(report):
        failures.append("second session diagnostic input/all-off debug contract differs")
    if profile_baseline is None or _profile_counts(report) != profile_baseline:
        failures.append("second session applied-run or earned-unlock counts changed/missing")
    return failures


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


def check_session_cleanup():
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
    attempt = read(WORK / "lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json")["attempt"]
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
    value = selection(attempt)
    write(out / "selection.json", value)
    frozen = {
        "serial": device.serial,
        "package": PACKAGE,
        "apk_sha256": artifact_hash,
        "apk_identity_evidence": "current APK artifact hash matches build and installed ownership receipts; installed package bytes are receipt-backed, not independently rehashed",
        "attempt": attempt,
        "storage_mode": mode,
        "scope": "diagnostic automatic input; no gameplay debug assists; ordinary native death/restart only",
    }
    write(out / "frozen.json", frozen)

    pid = None
    final = None
    completed = None
    profile_baseline = None
    stop = "deadline"
    first_failure = None
    observed_session1_defeat = False
    restart_sent = False
    started_from_menu = False
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
                reason = runtime_stop(current, pid, attempt)
                if reason:
                    fail(reason)
                    details = report_errors(current)
                    if details and first_failure == reason:
                        first_failure = details[0]
                    break
                phase = current.get("phase")
                if phase == "offline-start-menu" and not started_from_menu:
                    coords = menu_start_coordinates(current)
                    if coords is None:
                        fail("offline-menu-start-control-unavailable")
                        break
                    device.sh("input", "tap", str(coords[0]), str(coords[1]))
                    started_from_menu = True
                if current.get("session") == 1 and phase == "integrated-world-playing" and profile_baseline is None:
                    profile_baseline = _profile_counts(current)
                    if profile_baseline is None:
                        fail("first-live-profile-baseline-unavailable")
                        break
                    write(out / "first-live-session.json", current)
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
                    failures = cleanup_contract(completed or {}, pid, attempt, profile_baseline)
                    if failures:
                        fail("completed-session-cleanup-failed")
                    elif not observed_session1_defeat or not restart_sent or not started_from_menu:
                        fail("launch-to-restart-observations-incomplete")
                    else:
                        failures = restart_contract(current, pid, attempt, profile_baseline)
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
        failures.append("session-1 defeat was not observed")
    if not restart_sent:
        failures.append("restart input was not sent")
    if not started_from_menu:
        failures.append("ordinary menu start was not observed")
    if not completed or not pid:
        failures.append("no current-launch completed-session report")
    else:
        failures.extend(cleanup_contract(completed, pid, attempt, profile_baseline))
    if not final or not pid:
        failures.append("no current-launch restarted-session report")
    else:
        failures.extend(restart_contract(final, pid, attempt, profile_baseline))
    if runtime_errors:
        failures.append("current-process runtime errors: " + str(runtime_errors[:3]))
        if first_failure is None:
            first_failure = "final-runtime-log-error"
    failures.extend(cleanup_errors)
    result = {
        "success": not failures,
        "stop": stop,
        "first_failure": first_failure,
        "failures": failures,
        "pid": pid,
        "attempt": attempt,
        "apk_sha256": artifact_hash,
        "serial": device.serial,
        "profile_baseline": profile_baseline,
        "profile_completed": _profile_counts(completed) if completed else None,
        "profile_restarted": _profile_counts(final) if final else None,
        "runtime_errors": runtime_errors,
        "completed_session": completed,
        "restarted_session": final,
        "evidence": str(out.relative_to(WORK.parent)),
    }
    write(out / "result.json", result)
    summary = {
        "success": result["success"],
        "stop": result["stop"],
        "failures": result["failures"],
        "apk": artifact_hash,
        "evidence": result["evidence"],
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
