"""Broad assisted base-survivor checks in the ordinary integrated world.

Explicitly diagnostic selection admits locked base survivors, never expansions.
This measures four native slot activations, not complete ability semantics.
"""

import json
import math
from pathlib import Path
import time

from baseline import DEBUG_OPTIONS, FIRST_STAGE, SPINE_ID, selection
from common import WORK, now, read, write
from device import Device, PACKAGE
from nova_bridge import current_errors

BASE_SURVIVORS = ("Commando", "Huntress", "Bandit2", "Toolbot", "Engi", "Mage", "Merc", "Treebot", "Loader", "Croco", "Captain")
FREE_SURVIVORS = {"Commando", "Huntress"}
EXPECTED_SKILL_COMPONENTS = {"Croco": 5, "Toolbot": 5, "Captain": 6}
CANONICAL_COMPONENT_SLOTS = ("Primary", "Secondary", "Utility", "Special", "None")
SLOTS = ("primary", "secondary", "utility", "special")
MIN_WORLD_SECONDS = 60
MAX_WORLD_SECONDS = 180
HOST_DEADLINE_SECONDS = 420
LOG_POLL_SECONDS = 10


def require_lab_available():
    if (WORK / "coordination/claude-r9.lock").exists():
        raise RuntimeError("Parallel session holds the editor/device; survivor checks must wait for its coordination lock to clear")


class SurvivorCheckDevice(Device):
    def __init__(self):
        require_lab_available()
        super().__init__()

    def cmd(self, *args, **kwargs):
        require_lab_available()
        return super().cmd(*args, **kwargs)


def targets(target):
    names = BASE_SURVIVORS if target == "all" else tuple(target.split(","))
    if not names or len(set(names)) != len(names) or any(name not in BASE_SURVIVORS for name in names):
        raise ValueError("Use --target all or comma-separated base survivor catalog names: " + ",".join(BASE_SURVIVORS))
    return names


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate property: " + key)
        value[key] = item
    return value


def read_skill_variant_selection(path, survivor):
    """Read a strict, one-run catalog-index selector; no profile fields are accepted."""
    if path is None:
        return None
    try:
        value = json.loads(Path(path).read_text(), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("cannot read skill-variant selection: " + str(error)) from error
    if not isinstance(value, dict) or set(value) != {"survivor", "entries"}:
        raise ValueError("skill-variant selection requires exactly survivor and entries")
    if value["survivor"] not in BASE_SURVIVORS:
        raise ValueError("skill-variant selection must name a base survivor catalog key")
    if value["survivor"] != survivor:
        raise ValueError("skill-variant selection survivor must equal the single --target survivor")
    entries = value["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 6:
        raise ValueError("skill-variant selection requires 1 to 6 entries")
    component_indexes = set()
    normalized = []
    fields = {"componentIndex", "familyCatalogIndex", "variantIndex", "skillCatalogIndex"}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError("each skill-variant entry requires exactly the four catalog identity fields")
        for name in fields:
            if type(entry[name]) is not int or entry[name] < 0:
                raise ValueError("skill-variant indexes must be nonnegative integers: " + name)
        component = entry["componentIndex"]
        if component in component_indexes:
            raise ValueError("multiple entries target the same GenericSkill component")
        component_indexes.add(component)
        normalized.append({name: entry[name] for name in ("componentIndex", "familyCatalogIndex", "variantIndex", "skillCatalogIndex")})
    return {"survivor": survivor, "entries": normalized}


def survivor_selection(attempt, survivor, skill_variant_override=None):
    if survivor not in BASE_SURVIVORS:
        raise ValueError("Unsupported base survivor")
    value = selection(attempt)
    value.update(selectedSurvivor=survivor, developerSurvivorOverride=survivor not in FREE_SURVIVORS, diagnosticSkillCoverage=True)
    if skill_variant_override is not None:
        if skill_variant_override.get("survivor") != survivor:
            raise ValueError("skill-variant selection survivor differs")
        value["developerSkillVariantOverride"] = skill_variant_override
        value["debugOptions"]["purpose"] = "Assisted per-run base-survivor skill-variant check; no profile or unlock changes"
    else:
        value["debugOptions"]["purpose"] = "Original base-survivor skill integration; diagnostic selection/input, no permanent progression"
    return value


def missing_activations(report):
    observation = report.get("survivorSkills") or {}
    slots = observation.get("slots") or []
    if not observation.get("attached") or observation.get("cleaned") or [slot.get("slot") for slot in slots] != list(SLOTS):
        return list(SLOTS)
    return [slot["slot"] for slot in slots if any(type(slot.get(key)) is not int or slot[key] <= 0 for key in ("authorityActivations", "serverActivations"))]


def component_inventory(report, survivor):
    """Classify the current J602 component inventory without claiming behavior."""
    observation = report.get("survivorSkills")
    expected = EXPECTED_SKILL_COMPONENTS.get(survivor, 4)
    if not isinstance(observation, dict) or "components" not in observation:
        return {"status": "instrumentation-unavailable", "expectedComponents": expected}

    rows = observation.get("components")
    if not isinstance(rows, list):
        return {"status": "invalid", "reason": "components-not-array", "expectedComponents": expected}

    summary = {"status": "invalid", "expectedComponents": expected, "reportedComponents": len(rows)}
    current, historical = [], 0
    for row in rows:
        if not isinstance(row, dict):
            summary["reason"] = "component-row-not-object"
            return summary
        present = row.get("present")
        if present is True:
            current.append(row)
        elif present is False:
            historical += 1
        else:
            summary["reason"] = "component-presence-invalid"
            return summary

    summary["observedComponents"] = len(current)
    summary["historicalComponents"] = historical
    if len(current) != expected:
        summary["reason"] = "component-count-mismatch"
        return summary

    indexes, identities, canonical_counts = [], [], {slot: 0 for slot in CANONICAL_COMPONENT_SLOTS}
    noncanonical = 0
    for row in current:
        index = row.get("componentIndex")
        instance_id = row.get("instanceId")
        canonical = row.get("canonicalSlot")
        if type(index) is not int or type(instance_id) is not int or instance_id == 0:
            summary["reason"] = "component-index-or-identity-invalid"
            return summary
        if not isinstance(canonical, str) or canonical not in CANONICAL_COMPONENT_SLOTS:
            summary["reason"] = "component-native-role-invalid"
            return summary
        indexes.append(index)
        identities.append(instance_id)
        canonical_counts[canonical] += 1
        if canonical == "None":
            noncanonical += 1

    if sorted(indexes) != list(range(expected)):
        summary["reason"] = "component-indexes-not-contiguous-unique"
    elif len(set(identities)) != expected:
        summary["reason"] = "component-identities-not-unique"
    else:
        summary["status"] = "valid"
        summary["reason"] = None
    summary["noncanonicalCount"] = noncanonical
    summary["canonicalCounts"] = canonical_counts
    return summary


def skill_variant_catalog_inventory(report):
    """Validate bounded, exact catalog indexes exposed for explicit case-file authoring."""
    survivor_skills = report.get("survivorSkills") or {}
    override = report.get("developerSkillVariantOverrideReport") or {}
    value = override.get("skillVariantInventory") or survivor_skills.get("skillVariantInventory")
    if not isinstance(value, dict):
        return {"status": "unavailable", "reason": "variant-catalog-inventory-missing"}
    if value.get("status") != "available":
        return {"status": "invalid", "reason": value.get("error") or "variant-catalog-inventory-refused"}
    rows = value.get("components")
    selection_source = value.get("selectionSource")
    if (type(value.get("bodyIndex")) is not int or value["bodyIndex"] < 0 or
            selection_source not in ("native-master-loadout-pre-spawn", "native-master-loadout-live") or
            not isinstance(rows, list) or not 1 <= len(rows) <= 6):
        return {"status": "invalid", "reason": "variant-catalog-component-range-invalid"}
    seen_components = set()
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            return {"status": "invalid", "reason": "variant-catalog-component-not-object"}
        component = row.get("componentIndex")
        family = row.get("familyCatalogIndex")
        selected_variant = row.get("selectedLoadoutVariantIndex")
        selected_skill = row.get("selectedLoadoutSkillCatalogIndex")
        runtime_skill = row.get("runtimeSkillCatalogIndex")
        runtime_status = row.get("runtimeDefinitionStatus")
        variants = row.get("variants")
        if any(type(index) is not int or index < 0 for index in (component, family, selected_variant, selected_skill)):
            return {"status": "invalid", "reason": "variant-catalog-identity-invalid"}
        if type(runtime_skill) is not int or runtime_skill < -1 or runtime_status not in (
            "uninitialized-or-unassigned", "runtime-override-or-unmapped", "matches-selected-native-loadout",
            "differs-from-selected-native-loadout"
        ):
            return {"status": "invalid", "reason": "variant-catalog-runtime-status-invalid"}
        if component in seen_components or not isinstance(variants, list) or not 1 <= len(variants) <= 16:
            return {"status": "invalid", "reason": "variant-catalog-duplicate-or-size-invalid"}
        seen_components.add(component)
        definitions = []
        for index, variant in enumerate(variants):
            if not isinstance(variant, dict) or type(variant.get("variantIndex")) is not int or variant["variantIndex"] != index:
                return {"status": "invalid", "reason": "variant-catalog-variant-index-invalid"}
            skill_index = variant.get("skillCatalogIndex")
            if type(skill_index) is not int or skill_index < 0:
                return {"status": "invalid", "reason": "variant-catalog-skill-index-invalid"}
            definitions.append(skill_index)
        if selected_variant >= len(variants) or variants[selected_variant]["skillCatalogIndex"] != selected_skill:
            return {"status": "invalid", "reason": "variant-catalog-selected-loadout-mismatch"}
        normalized.append({"componentIndex": component, "familyCatalogIndex": family,
                           "selectedLoadoutVariantIndex": selected_variant,
                           "selectedLoadoutSkillCatalogIndex": selected_skill,
                           "runtimeSkillCatalogIndex": runtime_skill,
                           "runtimeDefinitionStatus": runtime_status,
                           "skillName": row.get("skillName", ""),
                           "variants": [{"variantIndex": i, "skillCatalogIndex": index,
                                         "skillName": variants[i].get("skillName", ""),
                                         "unlockableName": variants[i].get("unlockableName", ""),
                                         "expansionGated": variants[i].get("expansionGated") is True}
                                        for i, index in enumerate(definitions)]})
    if sorted(seen_components) != list(range(len(rows))):
        return {"status": "invalid", "reason": "variant-catalog-component-indexes-not-contiguous"}
    return {"status": "valid", "bodyIndex": value["bodyIndex"],
            "selectionSource": selection_source, "components": normalized}


def suppressed_missing_callbacks(report):
    """Return suppressed callback types that are still absent from each slot."""
    observation = report.get("survivorSkills") or {}
    slots = observation.get("slots") or []
    if [slot.get("slot") for slot in slots] != list(SLOTS):
        return []
    suppressed = []
    for slot in slots:
        if not slot.get("suppressesActivationEvents"):
            continue
        callbacks = [key for key in ("authorityActivations", "serverActivations") if type(slot.get(key)) is not int or slot[key] <= 0]
        if callbacks:
            suppressed.append({"slot": slot["slot"], "callbacks": callbacks})
    return suppressed


def stop_reason(report):
    if report.get("error") or report.get("firstFailure"):
        return "first-failure"
    progress = report.get("stageProgress") or {}
    transitions = progress.get("transitions", 0)
    if (
        type(transitions) is not int
        or transitions != 0
        or progress.get("transporting")
        or (report.get("stage") or {}).get("scene") not in (None, "", FIRST_STAGE)
    ):
        return "left-first-stage"
    if report.get("phase") in ("commando-defeated", "complete"):
        return "ordinary-result"
    seconds = (report.get("world") or {}).get("seconds")
    if report.get("phase") == "integrated-world-playing" and type(seconds) in (int, float) and math.isfinite(seconds):
        if seconds >= MIN_WORLD_SECONDS and not missing_activations(report):
            return "four-slots-activated"
        if seconds >= MIN_WORLD_SECONDS and suppressed_missing_callbacks(report):
            return "suppressed-activation-events"
        if seconds >= MAX_WORLD_SECONDS:
            return "unobserved-skills"
    return None


def assess(survivor, stop, first, final, errors, skill_variant_override=None):
    failures = []
    if stop != "four-slots-activated":
        failures.append("stopped: " + stop)
    if not final:
        return failures + ["no current-process report"]
    suppressed = suppressed_missing_callbacks(final)
    if suppressed:
        details = ", ".join(item["slot"] + "(" + ", ".join(item["callbacks"]) + ")" for item in suppressed)
        failures.append("suppressed activation callbacks: " + details)
    expected = survivor_selection("fixture", survivor)
    if final.get("selectedSurvivor") != survivor or final.get("developerSurvivorOverride") is not expected["developerSurvivorOverride"]:
        failures.append("survivor selection differs")
    if final.get("error") or final.get("firstFailure"):
        failures.append("runtime first failure")
    if skill_variant_override is not None:
        if final.get("developerSkillVariantOverride") != skill_variant_override:
            failures.append("per-run skill-variant selector differs")
        result = final.get("developerSkillVariantOverrideReport") or {}
        if result.get("status") != "applied" or result.get("applied") is not True or result.get("assisted") is not True:
            failures.append("per-run skill-variant override was not applied as assisted")
        if final.get("developerSkillVariantAssisted") is not True:
            failures.append("per-run skill-variant assisted session marker is absent")
        variant_catalog = skill_variant_catalog_inventory(final)
        if variant_catalog["status"] != "valid":
            failures.append("per-run skill-variant catalog inventory is unavailable or invalid")
        else:
            indexed = {row["componentIndex"]: row for row in variant_catalog["components"]}
            effective = result.get("effectiveSkillVariants")
            if (not isinstance(effective, list) or len(effective) != len(indexed) or
                    any(type(index) is not int or index < 0 for index in effective) or
                    any(entry["componentIndex"] >= len(effective) or
                        effective[entry["componentIndex"]] != entry["variantIndex"]
                        for entry in skill_variant_override.get("entries", []))):
                failures.append("per-run effective native loadout differs from the requested skill variants")
            for entry in skill_variant_override.get("entries", []):
                row = indexed.get(entry["componentIndex"])
                if (row is None or row["familyCatalogIndex"] != entry["familyCatalogIndex"] or
                        entry["variantIndex"] >= len(row["variants"]) or
                        row["variants"][entry["variantIndex"]]["skillCatalogIndex"] != entry["skillCatalogIndex"]):
                    failures.append("per-run skill-variant request differs from reported native catalog identity")
                    break
    inventory = component_inventory(final, survivor)
    if inventory["status"] == "invalid":
        failures.append("invalid survivor skill component inventory: " + inventory.get("reason", "unknown"))
    if stop_reason(final) != "four-slots-activated":
        failures.append("four native slot activations and live first-stage timing not established")
    if not (final.get("debugAcceleration") or {}).get("everAssisted"):
        failures.append("diagnostic run not marked assisted")
    runs = ((first or {}).get("profile") or {}).get("appliedRuns")
    if type(runs) is not int or (final.get("profile") or {}).get("appliedRuns") != runs:
        failures.append("profile run count changed or missing")
    if errors:
        failures.append("unexpected current-process Unity/Android errors")
    return failures


def check_one(device, survivor, attempt, runtime, out, installed, skill_variant_override=None):
    out.mkdir()
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    if device.sh("sh", "-c", "test -e " + selector + " && echo present", check=False).strip():
        raise RuntimeError("Existing diagnostic selector; preserve it")
    write(out / "selection.json", survivor_selection(attempt, survivor, skill_variant_override))
    pid, first, final = None, None, None
    stop, started = "deadline", False
    runtime_errors, first_failure = [], None
    began = time.monotonic()
    next_log_poll = began + LOG_POLL_SECONDS
    try:
        device.sh("rm", "-f", report_path)
        device.cmd("push", str(out / "selection.json"), selector)
        pid = device.launch()["pid"]
        write(out / "launch.json", {"pid": pid, "apk_sha256": installed["apk_sha256"]})
        while time.monotonic() - began < HOST_DEADLINE_SECONDS:
            if device.sh("pidof", PACKAGE, check=False).strip() != pid:
                stop = "process-exited"
                break
            try:
                report = json.loads(device.sh("cat", report_path, check=False))
            except ValueError:
                report = None
            if report and str(report.get("pid")) == pid and report.get("attempt") == attempt and report.get("id") == SPINE_ID:
                final = report
                phase = report.get("phase")
                if phase == "integrated-world-playing" and first is None:
                    first = report
                    device.collect("screenshot", out / "first-world-capture")
                stop = stop_reason(report) or "deadline"
                if stop == "first-failure":
                    first_failure = report.get("firstFailure") or report.get("error")
                    break
                if stop != "deadline":
                    break
                if phase == "offline-start-menu" and not started:
                    if report.get("selectedSurvivor") != survivor:
                        stop = "survivor-selection-rejected"
                        break
                    hud = report["hud"]
                    device.sh("input", "tap", str(round(hud["menuStartX"])), str(round(hud["menuStartY"])))
                    started = True
            if time.monotonic() >= next_log_poll:
                logs = device.cmd("logcat", "-d", "--pid=" + str(pid), "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
                runtime_errors = current_errors(logs, pid)
                if runtime_errors:
                    first_failure = runtime_errors[0]
                    (out / "first-error-poll.log").write_text(logs)
                    stop = "first-runtime-log-error"
                    break
                next_log_poll = time.monotonic() + LOG_POLL_SECONDS
            time.sleep(2)
        # Freeze the report before collection can extend automated play.
        device.sh("am", "force-stop", PACKAGE, check=False)
        write(out / "first-report.json", first)
        write(out / "final-report.json", final)
        logs = device.cmd("logcat", "-d", "--pid=" + str(pid), "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
        (out / "current-process.log").write_text(logs)
        device.collect("crash", out / "capture")
        final_errors = current_errors(logs, pid)
        runtime_errors = list(dict.fromkeys(runtime_errors + final_errors))
        if runtime_errors and first_failure is None:
            first_failure = runtime_errors[0]
        elif first_failure is None and final and (final.get("firstFailure") or final.get("error")):
            first_failure = final.get("firstFailure") or final.get("error")
        failures = assess(survivor, stop, first, final, runtime_errors, skill_variant_override)
        result = {
            "success": not failures,
            "survivor": survivor,
            "stop": stop,
            "first_failure": first_failure,
            "runtime_errors": runtime_errors,
            "failures": failures,
            "missing_activations": missing_activations(final or {}),
            "suppressed_callbacks": suppressed_missing_callbacks(final or {}),
            "component_inventory": component_inventory(final or {}, survivor),
            "skill_variant_catalog_inventory": skill_variant_catalog_inventory(final or {}),
            "skill_variant_override": skill_variant_override,
            "apk_sha256": installed["apk_sha256"],
            "evidence": str(out.relative_to(WORK.parent)),
        }
        write(out / "result.json", result)
        return result
    finally:
        try:
            device.sh("rm", "-f", selector, check=False)
        finally:
            try:
                device.sh("am", "force-stop", PACKAGE, check=False)
            finally:
                device.display(False)


def check_survivors(target, skill_variants=None):
    names = targets(target)
    if skill_variants is not None and len(names) != 1:
        raise ValueError("per-run skill variants require exactly one --target survivor")
    variant_selection = read_skill_variant_selection(skill_variants, names[0]) if skill_variants is not None else None
    device = SurvivorCheckDevice()
    installed = device.owned()
    mode = device.settings["storage_mode"]
    storage_receipt = installed.get("storage")
    if not isinstance(storage_receipt, dict) or storage_receipt.get("mode") != mode:
        raise RuntimeError("Owned APK storage differs from selected-device policy")
    storage = device.storage()
    if storage.get("mode") != mode:
        raise RuntimeError("Owned APK storage differs from selected-device policy")
    if mode == "internal":
        expected_prefix = "/data/app/"
    elif mode == "adopted":
        uuid = storage.get("uuid")
        if not isinstance(uuid, str) or not uuid:
            raise RuntimeError("Selected adopted storage has no live volume identity")
        expected_prefix = "/mnt/expand/" + uuid + "/"
    else:
        raise RuntimeError("Unknown explicitly configured storage mode")
    package_path = installed.get("package_path")
    if not isinstance(package_path, str) or expected_prefix not in package_path:
        raise RuntimeError("Owned APK placement differs from selected live storage")
    if installed["apk_sha256"] != read(WORK / "config/current-build.json")["apk_sha256"]:
        raise RuntimeError("Installed APK differs from the current build receipt")
    attempt = read(WORK / "lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json")["attempt"]
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    out = WORK / "experiments/survivor-check" / now()
    out.mkdir(parents=True)
    results = []
    for survivor in names:
        result = check_one(device, survivor, attempt, runtime, out / survivor, installed,
                           skill_variant_override=variant_selection if survivor == names[0] else None)
        results.append(result)
        write(out / "result.json", {"success": all(row["success"] for row in results), "results": results})
        print(json.dumps(result), flush=True)
        if not result["success"]:
            raise RuntimeError("Survivor check stopped at its first failure; see " + result["evidence"])
    return results
