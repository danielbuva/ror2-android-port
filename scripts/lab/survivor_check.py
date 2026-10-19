"""Broad assisted base-survivor checks in the ordinary integrated world.

Explicitly diagnostic selection admits locked base survivors, never expansions.
This measures four native slot activations, not complete ability semantics.
"""

import json
import math
import time

from baseline import DEBUG_OPTIONS, FIRST_STAGE, SPINE_ID, selection
from common import WORK, now, read, write
from device import Device, PACKAGE
from nova_bridge import current_errors

BASE_SURVIVORS = ("Commando", "Huntress", "Bandit2", "Toolbot", "Engi", "Mage", "Merc", "Treebot", "Loader", "Croco", "Captain")
FREE_SURVIVORS = {"Commando", "Huntress"}
SLOTS = ("primary", "secondary", "utility", "special")
MIN_WORLD_SECONDS = 60
MAX_WORLD_SECONDS = 180
HOST_DEADLINE_SECONDS = 420


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


def survivor_selection(attempt, survivor):
    if survivor not in BASE_SURVIVORS:
        raise ValueError("Unsupported base survivor")
    value = selection(attempt)
    value.update(selectedSurvivor=survivor, developerSurvivorOverride=survivor not in FREE_SURVIVORS)
    value["debugOptions"]["purpose"] = "Original base-survivor skill integration; diagnostic selection/input, no permanent progression"
    return value


def missing_activations(report):
    observation = report.get("survivorSkills") or {}
    slots = observation.get("slots") or []
    if not observation.get("attached") or observation.get("cleaned") or [slot.get("slot") for slot in slots] != list(SLOTS):
        return list(SLOTS)
    return [slot["slot"] for slot in slots if any(type(slot.get(key)) is not int or slot[key] <= 0 for key in ("authorityActivations", "serverActivations"))]


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
        if seconds >= MAX_WORLD_SECONDS:
            return "unobserved-skills"
    return None


def assess(survivor, stop, first, final, errors):
    failures = []
    if stop != "four-slots-activated":
        failures.append("stopped: " + stop)
    if not final:
        return failures + ["no current-process report"]
    expected = survivor_selection("fixture", survivor)
    if final.get("selectedSurvivor") != survivor or final.get("developerSurvivorOverride") is not expected["developerSurvivorOverride"]:
        failures.append("survivor selection differs")
    if final.get("error") or final.get("firstFailure"):
        failures.append("runtime first failure")
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


def check_one(device, survivor, attempt, runtime, out, installed):
    out.mkdir()
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    if device.sh("sh", "-c", "test -e " + selector + " && echo present", check=False).strip():
        raise RuntimeError("Existing diagnostic selector; preserve it")
    write(out / "selection.json", survivor_selection(attempt, survivor))
    pid, first, final = None, None, None
    stop, started = "deadline", False
    began = time.monotonic()
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
                if stop != "deadline":
                    break
                if phase == "offline-start-menu" and not started:
                    if report.get("selectedSurvivor") != survivor:
                        stop = "survivor-selection-rejected"
                        break
                    hud = report["hud"]
                    device.sh("input", "tap", str(round(hud["menuStartX"])), str(round(hud["menuStartY"])))
                    started = True
            time.sleep(2)
        # Freeze the report before collection can extend automated play.
        device.sh("am", "force-stop", PACKAGE, check=False)
        write(out / "first-report.json", first)
        write(out / "final-report.json", final)
        logs = device.cmd("logcat", "-d", "--pid=" + str(pid), "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
        (out / "current-process.log").write_text(logs)
        device.collect("crash", out / "capture")
        errors = current_errors(logs, pid)
        failures = assess(survivor, stop, first, final, errors)
        result = {
            "success": not failures,
            "survivor": survivor,
            "stop": stop,
            "failures": failures,
            "missing_activations": missing_activations(final or {}),
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


def check_survivors(target):
    names = targets(target)
    device = SurvivorCheckDevice()
    installed = device.owned()
    if installed["storage"]["mode"] != "adopted":
        raise RuntimeError("Owned APK is not on adopted storage")
    if installed["apk_sha256"] != read(WORK / "config/current-build.json")["apk_sha256"]:
        raise RuntimeError("Installed APK differs from the current build receipt")
    attempt = read(WORK / "lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json")["attempt"]
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    out = WORK / "experiments/survivor-check" / now()
    out.mkdir(parents=True)
    results = []
    for survivor in names:
        result = check_one(device, survivor, attempt, runtime, out / survivor, installed)
        results.append(result)
        write(out / "result.json", {"success": all(row["success"] for row in results), "results": results})
        print(json.dumps(result), flush=True)
        if not result["success"]:
            raise RuntimeError("Survivor check stopped at its first failure; see " + result["evidence"])
    return results
