"""Standard device checks: first-stage play or one assisted original stage exit.

Commando is chosen from the ordinary offline menu with invincibility as the only
(diagnostic) assist, so the run never grants permanent progression. The check stops at
35 s of world play or on leaving the first stage. The optional stage-exit mode adds
high damage and fast charge and stops after 10 s of next-stage play. Both modes
always force-stop the app and turn the display off.
"""

import json
import math
import time

from common import WORK, now, read, write
from device import Device, PACKAGE

SPINE_ID = "body-state-spawn-state-auto-nova-spine-bringup"
WORLD_SECONDS = 35
STAGE_WORLD_SECONDS = 10
FIRST_STAGE = "lakes"
DEADLINE_SECONDS = 370
DEBUG_OPTIONS = ("invincibility", "highDamage", "fastCharge", "movementBoost", "jumpBoost")


def selection(attempt, stage_exit=False):
    """The attempt-bound selection Start reads from movement-batch-selection.json."""
    debug = {key: False for key in DEBUG_OPTIONS}
    debug["invincibility"] = True
    debug["purpose"] = "Standard baseline check; diagnostic assist, no permanent progression"
    if stage_exit:
        debug["highDamage"] = debug["fastCharge"] = True
        debug["purpose"] = "Standard one-exit baseline check; diagnostic assists, no permanent progression"
    return {
        "attempt": attempt,
        "id": SPINE_ID,
        "freePlay": True,
        "selectedSurvivor": "Commando",
        "developerSurvivorOverride": False,
        "runSeedOverride": "2",
        "goldshoresRoute": False,
        "debugOptions": debug,
    }


def stage_world_seconds(report):
    """Next-stage age on the runtime clock, never total run time or host time."""
    seconds = (report.get("world") or {}).get("seconds")
    entered = (report.get("stageProgress") or {}).get("enteredAt")
    if not all(type(value) in (int, float) and math.isfinite(value) for value in (seconds, entered)):
        return None
    return seconds - entered if 0 <= entered <= seconds else None


def stage_exit_stop(report):
    """Decide whether a current-process report ends the one-exit check."""
    if report.get("error") or report.get("firstFailure"):
        return "first-failure"
    progress = report.get("stageProgress") or {}
    transitions = progress.get("transitions", 0)
    scene = (report.get("stage") or {}).get("scene")
    if type(transitions) is not int or transitions < 0:
        return "invalid-stage-progress"
    if transitions > 1:
        return "extra-stage-transition"
    # During transport stage.scene already names the destination while the count is still 0.
    if transitions == 0 and scene and scene != FIRST_STAGE and not progress.get("transporting"):
        return "unexpected-first-stage"
    if transitions == 1:
        # Fail already at a second exit request, rather than waiting for transport.
        requested = progress.get("requested")
        if progress.get("transporting") or (requested and requested != scene) or str(report.get("phase", "")).startswith("integrated-stage-"):
            return "second-stage-exit"
        age = stage_world_seconds(report)
        if report.get("phase") == "integrated-world-playing" and scene and scene != FIRST_STAGE and age is not None and age >= STAGE_WORLD_SECONDS:
            return "stage-exit-10s"
    return None


def assess(stop, first, final, stage_exit=False):
    """Return the failed criteria (empty when the check passes) for one run.

    `first` is the first report taken during live world play, `final` the last one.
    """
    failures = []
    if stop != ("stage-exit-10s" if stage_exit else "world-35s"):
        failures.append("stopped: " + stop)
    if not final:
        return failures + ["no final report"]
    if final.get("error") or final.get("firstFailure"):
        failures.append("report error: " + (final.get("firstFailure") or final.get("error"))[:200])
    if stage_exit:
        progress = final.get("stageProgress") or {}
        if type(progress.get("transitions")) is not int or progress["transitions"] != 1:
            failures.append("stage transition count is not 1")
        scene = (final.get("stage") or {}).get("scene")
        if not scene or scene == FIRST_STAGE:
            failures.append("not on a non-first-stage scene")
        if final.get("phase") != "integrated-world-playing" or progress.get("transporting"):
            failures.append("next stage is not in live world play")
        age = stage_world_seconds(final)
        if age is None or age < STAGE_WORLD_SECONDS:
            failures.append("next-stage world play under %d s or missing timing" % STAGE_WORLD_SECONDS)
        if stage_exit_stop(final) == "second-stage-exit":
            failures.append("second stage exit requested")
        if (
            not first
            or first.get("phase") != "integrated-world-playing"
            or (first.get("stage") or {}).get("scene") != FIRST_STAGE
            or (first.get("stageProgress") or {}).get("transitions", 0) != 0
        ):
            failures.append("no first-stage live report")
    else:
        if (final.get("world") or {}).get("seconds", 0) < WORLD_SECONDS:
            failures.append("world play under %d s" % WORLD_SECONDS)
        if (final.get("stage") or {}).get("scene") != FIRST_STAGE:
            failures.append("not on Lakes")
    if not (final.get("debugAcceleration") or {}).get("everAssisted"):
        failures.append("run not marked assisted")
    runs = (final.get("profile") or {}).get("appliedRuns")
    if runs is None or runs != ((first or {}).get("profile") or {}).get("appliedRuns"):
        failures.append("profile run count changed or missing")
    return failures


def check_baseline(stage_exit=False):
    installed = read(WORK / "device/installed.json")
    if installed["storage"]["mode"] != "adopted":
        raise RuntimeError("Owned APK is not on adopted storage")
    attempt = read(WORK / "lab-project/Assets/LabLoadingScene/Resources/MovementBatchProbe.json")["attempt"]
    out = WORK / "experiments/baseline" / now()
    out.mkdir(parents=True)
    d = Device()
    runtime = read(WORK / "device/runtime.json")["persistentDataPath"]
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    if d.sh("sh", "-c", "test -e " + selector + " && echo present", check=False).strip():
        raise RuntimeError("Existing diagnostic selector")
    write(out / "selection.json", selection(attempt, stage_exit=stage_exit))
    pid = None
    started = False
    stop = "deadline"
    first = None
    last_report = None
    began = time.monotonic()
    try:
        d.sh("rm", "-f", report_path)
        d.cmd("push", str(out / "selection.json"), selector)
        pid = d.launch()["pid"]
        while time.monotonic() - began < DEADLINE_SECONDS:
            if d.sh("pidof", PACKAGE, check=False).strip() != pid:
                stop = "process-exited"
                break
            try:
                r = json.loads(d.sh("cat", report_path, check=False))
            except ValueError:
                r = None
            if r and str(r.get("pid")) == pid:
                last_report = r
                phase = r.get("phase")
                world = (r.get("world") or {}).get("seconds", 0)
                if phase == "integrated-world-playing" and first is None and (not stage_exit or (r.get("stageProgress") or {}).get("transitions", 0) == 0):
                    first = r  # the profile is loaded by now; earlier reports predate it
                if r.get("error") or r.get("firstFailure"):
                    stop = "first-failure"
                    break
                if stage_exit:
                    reason = stage_exit_stop(r)
                    if reason:
                        stop = reason
                        break
                if phase == "offline-start-menu" and not started:
                    h = r["hud"]
                    d.sh("input", "tap", str(round(h["menuStartX"])), str(round(h["menuStartY"])))
                    started = True
                if not stage_exit and (r.get("stageProgress") or {}).get("transitions", 0):
                    stop = "left-first-stage"
                    break
                if not stage_exit and phase == "integrated-world-playing" and world >= WORLD_SECONDS:
                    stop = "world-35s"
                    break
                if phase in ("commando-defeated", "complete") and started:
                    stop = "ordinary-result"
                    break
            time.sleep(2)
        if stage_exit:
            # End auto-input before any artifact collection can extend the run.
            d.sh("am", "force-stop", PACKAGE, check=False)
            final = last_report
        else:
            try:
                final = json.loads(d.sh("cat", report_path, check=False))
            except ValueError:
                final = None
        write(out / "final-report.json", final)
        d.collect("logs", out / "capture")
        d.collect("screenshot", out / "capture")
    finally:
        try:
            d.sh("rm", "-f", selector, check=False)
        finally:
            try:
                d.sh("am", "force-stop", PACKAGE, check=False)
            finally:
                d.display(False)
    failures = assess(stop, first, final, stage_exit=stage_exit)
    result = {
        "success": not failures,
        "failures": failures,
        "stop": stop,
        "pid": pid,
        "apk_sha256": installed["apk_sha256"],
        "is_current_build": installed["apk_sha256"] == read(WORK / "config/current-build.json")["apk_sha256"],
        "world_seconds": ((final or {}).get("world") or {}).get("seconds"),
        "applied_runs": ((final or {}).get("profile") or {}).get("appliedRuns"),
        "evidence": str(out.relative_to(WORK.parent)),
    }
    if stage_exit:
        result.update(
            mode="stage-exit",
            transitions=((final or {}).get("stageProgress") or {}).get("transitions"),
            scene=((final or {}).get("stage") or {}).get("scene"),
            stage_world_seconds=stage_world_seconds(final) if final else None,
        )
    write(out / "result.json", result)
    return result
