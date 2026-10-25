"""Standard device checks: first-stage play or one assisted original stage exit.

Commando is chosen from the ordinary offline menu with invincibility as the only
(diagnostic) assist, so the run never grants permanent progression. The check stops at
35 s of world play or on leaving the first stage. The optional stage-exit mode adds
high damage and fast charge and stops after 10 s of next-stage play. An explicit
destination PCM diagnostic waits for its bounded window, up to 30 s there. Both
modes always force-stop the app and turn the display off.
"""

import json
import math
import shlex
import time
from pathlib import PurePosixPath

from common import WORK, now, read, write
from device import Device, PACKAGE
from installed_attempt import attempt_from_installed

SPINE_ID = "body-state-spawn-state-auto-nova-spine-bringup"
WORLD_SECONDS = 35
STAGE_WORLD_SECONDS = 10
DESTINATION_PCM_SECONDS = 30
FIRST_STAGE = "lakes"
DEADLINE_SECONDS = 370
DEBUG_OPTIONS = ("invincibility", "highDamage", "fastCharge", "movementBoost", "jumpBoost")
STOP_TIMEOUT_SECONDS = 5


def runtime_files(d, runtime):
    """Positive directory evidence; transport failures never mean absence."""
    names = d.sh("ls", "-1a", "--", runtime).splitlines()
    if names.count(".") != 1 or names.count("..") != 1:
        raise RuntimeError("Incomplete baseline runtime directory observation")
    return set(names)


def process_pid(d):
    """Distinguish pidof's expected no-match from command/transport failure."""
    script = (
        "value=$(pidof " + shlex.quote(PACKAGE) + " 2>&1); status=$?; "
        'if [ "$status" -eq 0 ] && [ -n "$value" ]; then printf "pid:%s\\n" "$value"; '
        'elif [ "$status" -eq 1 ] && [ -z "$value" ]; then printf "absent\\n"; '
        'else printf "invalid pidof observation\\n" >&2; exit 2; fi'
    )
    value = d.sh("sh", "-c", script)
    if value == "absent":
        return None
    if value.startswith("pid:") and value[4:].isascii() and value[4:].isdigit():
        return value[4:]
    raise RuntimeError("Incomplete or ambiguous baseline process observation")


def current_report(d, runtime, report_path):
    if PurePosixPath(report_path).name not in runtime_files(d, runtime):
        return None
    try:
        value = json.loads(d.sh("cat", report_path))
    except ValueError:
        # A live writer may be between truncation and its complete JSON write.
        return None
    if not isinstance(value, dict):
        raise RuntimeError("Malformed baseline report")
    return value


def cleanup(d, runtime, selector):
    """Attempt every owned teardown step, and refuse unverified cleanup."""
    errors = []
    result = {}
    try:
        d.sh("rm", "-f", selector)
        if PurePosixPath(selector).name in runtime_files(d, runtime):
            raise RuntimeError("Baseline selector remains after removal")
        result["selector_absent"] = True
    except Exception as error:
        errors.append(str(error))
    try:
        d.sh("am", "force-stop", PACKAGE)
        deadline = time.monotonic() + STOP_TIMEOUT_SECONDS
        while process_pid(d) is not None:
            if time.monotonic() >= deadline:
                raise RuntimeError("Baseline process remains after force-stop")
            time.sleep(0.2)
        result["process_absent"] = True
    except Exception as error:
        errors.append(str(error))
    try:
        result["sleep_requested"] = bool(d.settings.get("sleep_display_when_idle", False))
        result["display_asleep"] = d.display(False)
        if result["sleep_requested"] and result["display_asleep"] is not True:
            raise RuntimeError("Baseline display sleep was not verified")
    except Exception as error:
        errors.append(str(error))
    if errors:
        raise RuntimeError("Baseline cleanup failed: " + "; ".join(errors))
    return result


def selection(attempt, stage_exit=False, capture_in_destination=False):
    """The attempt-bound selection Start reads from movement-batch-selection.json."""
    debug = {key: False for key in DEBUG_OPTIONS}
    debug["invincibility"] = True
    debug["purpose"] = "Standard baseline check; diagnostic assist, no permanent progression"
    if stage_exit:
        debug["highDamage"] = debug["fastCharge"] = True
        debug["purpose"] = "Standard one-exit baseline check; diagnostic assists, no permanent progression"
    if capture_in_destination and not stage_exit:
        raise ValueError("Destination capture requires the one-exit check")
    value = {
        "attempt": attempt,
        "id": SPINE_ID,
        "freePlay": True,
        "selectedSurvivor": "Commando",
        "developerSurvivorOverride": False,
        "runSeedOverride": "2",
        "goldshoresRoute": False,
        "debugOptions": debug,
    }
    if capture_in_destination:
        value["passivePcmCaptureInDestinationRequested"] = True
    return value


def stage_world_seconds(report):
    """Next-stage age on the runtime clock, never total run time or host time."""
    seconds = (report.get("world") or {}).get("seconds")
    entered = (report.get("stageProgress") or {}).get("enteredAt")
    if not all(type(value) in (int, float) and math.isfinite(value) for value in (seconds, entered)):
        return None
    return seconds - entered if 0 <= entered <= seconds else None


def stage_exit_stop(report, capture_in_destination=False):
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
            if capture_in_destination and (report.get("originalAudio") or {}).get("passivePcmState") != "captured":
                return "destination-pcm-deadline" if age >= DESTINATION_PCM_SECONDS else None
            return "stage-exit-10s"
    return None


def assess(stop, first, final, stage_exit=False, capture_in_destination=False):
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
    if capture_in_destination:
        audio = final.get("originalAudio") or {}
        arm_time = final.get("passivePcmArmWorldSeconds")
        entered = (final.get("stageProgress") or {}).get("enteredAt")
        if (
            not stage_exit
            or final.get("passivePcmCaptureInDestinationRequested") is not True
            or final.get("passivePcmCaptureInDestinationObserved") is not True
            or final.get("passivePcmCaptureAfterAuthoritySkillRequested") is not True
            or final.get("passivePcmAuthoritySkillObserved") is not True
            or final.get("passivePcmGameplayArmRequested") is not True
            or final.get("passivePcmArmStageScene") != (final.get("stage") or {}).get("scene")
            or type(final.get("passivePcmArmStageTransitions")) is not int
            or final.get("passivePcmArmStageTransitions") != 1
            or type(arm_time) not in (int, float)
            or type(entered) not in (int, float)
            or not math.isfinite(arm_time)
            or not math.isfinite(entered)
            or arm_time <= entered
            or ((first or {}).get("passivePcmGameplayArmRequested") is True)
        ):
            failures.append("destination PCM arm is not bound to the verified next stage")
        if (
            audio.get("passivePcmState") != "captured"
            or audio.get("passivePcmCaptureSelectorMode") != "main"
            or type(audio.get("passivePcmNonzeroFiniteSamples")) is not int
            or audio.get("passivePcmNonzeroFiniteSamples", 0) <= 0
            or audio.get("passivePcmNonfiniteSamples") != 0
            or audio.get("passivePcmFailure") != ""
        ):
            failures.append("destination MainOutput is missing, silent or nonfinite")
    return failures


def check_baseline(stage_exit=False, capture_in_destination=False):
    if capture_in_destination and not stage_exit:
        raise ValueError("Destination capture requires the one-exit check")
    if capture_in_destination:
        from nova_bridge import current_errors
    d = Device()
    installed = d.owned()
    storage = d.storage()
    expected_mode = d.settings["storage_mode"]
    if installed["storage"]["mode"] != expected_mode or storage["mode"] != expected_mode:
        raise RuntimeError("Owned APK storage differs from selected-device policy")
    expected_path = "/data/app/" if expected_mode == "internal" else "/mnt/expand/" + storage["uuid"] + "/"
    if expected_path not in installed["package_path"]:
        raise RuntimeError("Owned APK placement differs from selected live volume")
    attempt = attempt_from_installed(installed)
    out = WORK / "experiments/baseline" / now()
    out.mkdir(parents=True)
    runtime = d.read_receipt("runtime.json")["persistentDataPath"]
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + SPINE_ID + ".json"
    if PurePosixPath(selector).name in runtime_files(d, runtime):
        raise RuntimeError("Existing diagnostic selector")
    write(out / "selection.json", selection(attempt, stage_exit=stage_exit, capture_in_destination=capture_in_destination))
    pid = None
    started = False
    stop = "deadline"
    first = None
    last_report = None
    operation_error = None
    pcm_log_errors = []
    next_log_at = 0
    deadline = DEADLINE_SECONDS + (DESTINATION_PCM_SECONDS - STAGE_WORLD_SECONDS if capture_in_destination else 0)
    began = time.monotonic()
    try:
        d.sh("rm", "-f", report_path)
        d.cmd("push", str(out / "selection.json"), selector)
        pid = d.launch()["pid"]
        if not isinstance(pid, str) or not pid.isascii() or not pid.isdigit():
            raise RuntimeError("Baseline launch has no unambiguous process identity")
        while time.monotonic() - began < deadline:
            if process_pid(d) != pid:
                stop = "process-exited"
                break
            r = current_report(d, runtime, report_path)
            if r and str(r.get("pid")) == pid:
                last_report = r
                phase = r.get("phase")
                world = (r.get("world") or {}).get("seconds", 0)
                if phase == "integrated-world-playing" and first is None and (not stage_exit or (r.get("stageProgress") or {}).get("transitions", 0) == 0):
                    first = r  # the profile is loaded by now; earlier reports predate it
                if r.get("error") or r.get("firstFailure"):
                    stop = "first-failure"
                    break
                if capture_in_destination and time.monotonic() >= next_log_at:
                    text = d.cmd("logcat", "-d", "--pid=" + pid, "-v", "threadtime", "Unity:I", "AndroidRuntime:E", "*:S")
                    pcm_log_errors = current_errors(text, pid)
                    next_log_at = time.monotonic() + 10
                    if pcm_log_errors:
                        (out / "first-runtime-error.log").write_text(text)
                        stop = "first-runtime-error"
                        break
                if stage_exit:
                    reason = stage_exit_stop(r, capture_in_destination=capture_in_destination)
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
            d.sh("am", "force-stop", PACKAGE)
            final = last_report
        else:
            final = current_report(d, runtime, report_path)
            if final and str(final.get("pid")) != pid:
                raise RuntimeError("Final baseline report belongs to another process")
        write(out / "final-report.json", final)
        d.collect("logs", out / "capture")
        d.collect("screenshot", out / "capture")
        if capture_in_destination:
            pcm_log_errors = list(dict.fromkeys(pcm_log_errors + current_errors((out / "capture/unity.log").read_text(), pid)))
    except Exception as error:
        operation_error = error
        raise
    finally:
        try:
            teardown = cleanup(d, runtime, selector)
        except Exception as error:
            if operation_error is not None:
                raise RuntimeError(str(operation_error) + "; " + str(error)) from operation_error
            raise
    failures = assess(stop, first, final, stage_exit=stage_exit, capture_in_destination=capture_in_destination)
    if pcm_log_errors:
        failures.append("destination check has unexplained current-process runtime errors")
    try:
        current_build_sha256 = read(WORK / "config/current-build.json")["apk_sha256"]
    except FileNotFoundError:
        current_build_sha256 = None
    result = {
        "success": not failures,
        "failures": failures,
        "stop": stop,
        "pid": pid,
        "apk_sha256": installed["apk_sha256"],
        "is_current_build": installed["apk_sha256"] == current_build_sha256,
        "world_seconds": ((final or {}).get("world") or {}).get("seconds"),
        "applied_runs": ((final or {}).get("profile") or {}).get("appliedRuns"),
        "evidence": str(out.relative_to(WORK.parent)),
        "cleanup": teardown,
    }
    if stage_exit:
        result.update(
            mode="stage-exit",
            transitions=((final or {}).get("stageProgress") or {}).get("transitions"),
            scene=((final or {}).get("stage") or {}).get("scene"),
            stage_world_seconds=stage_world_seconds(final) if final else None,
        )
    if capture_in_destination:
        result.update(capture_in_destination=True, destination_pcm_log_errors=pcm_log_errors)
    write(out / "result.json", result)
    return result
