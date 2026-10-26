"""Current: thirty-minute invincibility-only, manual-neutral software-touch observation.

Small camera drags keep this an explicitly assisted first-stage workload. Native
End Run/menu 2 teardown is checked separately; no ordinary play, digitizer,
full-game, sustained performance acceptance or memory bound follows.
"""

from datetime import datetime, timezone
import math
import re
import time

from common import WORK, now, write
from device import Device, PACKAGE
from installed_attempt import attempt_from_installed, bind_installed_apk, validate_expected_apk_sha256
from nova_bridge import current_errors
import session_cleanup_check as cleanup
import touch_gesture

PLANNED_SECONDS = 1800
ALL_OFF_REFUSAL = "diagnostic assistance evidence or all-off debug options differ"
ASSISTS = ("invincibility", "highDamage", "fastCharge", "movementBoost", "jumpBoost")
SCOPE = (
    "Assisted single original first-stage world, manual neutral input with small camera drags; invincibility ON only. "
    "Composed renderer; no ordinary play, digitizer, full-game/performance acceptance or repeated-session memory-bound claim."
)


def require_invincibility_only(report):
    active = (report.get("debugAcceleration") or {}).get("active") or {}
    if active.get("invincibility") is not True or any(active.get(key) is not False for key in ASSISTS[1:]):
        raise RuntimeError("Sustained workload requires exactly invincibility ON")


def thermal_sample(battery, thermal):
    temperature = re.search(r"^\s*temperature:\s*(\d+)", battery, re.M)
    status = re.search(r"Thermal Status:\s*(\d+)", thermal)
    if not temperature or not status:
        raise RuntimeError("No interpretable battery/HAL observation; refuse sustained case")
    row = dict(battery_celsius=int(temperature[1]) / 10, thermal_status=int(status[1]))
    if row["battery_celsius"] >= 43:
        raise RuntimeError("Sustained case reached battery at or above 43 C stop: " + repr(row))
    return row


def observation_sample(report, snapshot, elapsed, previous=None, utc=None):
    """Strict live/fresh sample admission; missing measurements never become zero."""
    if not isinstance(snapshot, dict):
        raise RuntimeError("No complete periodic diagnostic JSON")
    stamp = datetime.fromisoformat(snapshot["utc"].replace("Z", "+00:00"))
    if abs(((utc or datetime.now(timezone.utc)) - stamp).total_seconds()) >= 15:
        raise RuntimeError("Periodic diagnostics are stale; do not infer a measurement")
    world = report.get("world") or {}
    if (
        report.get("session") != 1
        or report.get("phase") != "integrated-world-playing"
        or world.get("ready") is not True
        or world.get("authority") is not True
        or world.get("manualTakeover") is not True
        or world.get("diagnosticInput") is not False
    ):
        raise RuntimeError("Native world/authority/manual-neutral state failed")
    require_invincibility_only(report)
    row = dict(
        host_seconds=round(elapsed, 3),
        native_seconds=(report.get("runClock") or {}).get("stopwatch"),
        native_frames=world.get("frames"),
        live_enemies=world.get("liveEnemies"),
        health=world.get("health"),
        snapshot_utc=snapshot["utc"],
    )
    for target, source in (
        ("fps", "fps"),
        ("frame_ms", "frameMs"),
        ("managed_bytes", "managedBytes"),
        ("total_allocated_bytes", "totalAllocatedBytes"),
        ("cpu_frame_ms", "cpuFrameMs"),
        ("gpu_frame_ms", "gpuFrameMs"),
    ):
        row[target] = snapshot.get(source)
    pacing = report.get("framePacing") or {}
    for target, source in (
        ("pacing_frames", "frames"),
        ("pacing_mean_ms", "meanMs"),
        ("pacing_over33", "over33ms"),
        ("pacing_over50", "over50ms"),
        ("pacing_lifetime_max_ms", "maxMs"),
    ):
        row[target] = pacing.get(source)
    # CPU/GPU timing can legitimately be unavailable; preserve null instead of
    # inventing timings. The existing periodic measured counters must be finite.
    required = (
        "native_seconds",
        "native_frames",
        "health",
        "fps",
        "frame_ms",
        "managed_bytes",
        "total_allocated_bytes",
        "pacing_frames",
        "pacing_mean_ms",
        "pacing_over33",
        "pacing_over50",
        "pacing_lifetime_max_ms",
    )
    if any(type(row[key]) not in (int, float) or not math.isfinite(row[key]) or row[key] < 0 for key in required) or row["health"] <= 0:
        raise RuntimeError("Missing/non-finite live diagnostic measurement or native body died")
    if previous and (
        row["native_frames"] <= previous["native_frames"]
        or row["native_seconds"] <= previous["native_seconds"]
        or stamp <= datetime.fromisoformat(previous["snapshot_utc"].replace("Z", "+00:00"))
    ):
        raise RuntimeError("Native world/periodic diagnostics did not advance")
    row["pacing_total_ms"] = row["pacing_frames"] * row["pacing_mean_ms"]
    return row


def assisted_teardown_contract(completed, pid, attempt, baseline):
    failures = cleanup.abandon_contract(completed, pid, attempt, baseline, "Commando")
    # Preserve the exact all-off refusal. No other teardown failure is waived.
    if failures != [ALL_OFF_REFUSAL]:
        raise RuntimeError("Unexpected native teardown failure: " + repr(failures))
    acceleration = completed.get("debugAcceleration") or {}
    active = acceleration.get("active") or {}
    if (
        acceleration.get("restored") is not True
        or any(active.get(key) is not False for key in ASSISTS)
        or acceleration.get("everAssisted") is not True
        or acceleration.get("normalGameAcceptanceEligible") is not False
        or not any(
            isinstance(event, dict) and event.get("toggle") == "invincibility" and event.get("enabled") is True for event in acceleration.get("events") or []
        )
    ):
        raise RuntimeError("Missing explicit assisted/restored debug lifecycle evidence")
    return failures


def check_session_sustained(expected_apk_sha256=None, _launch=None):
    expected = validate_expected_apk_sha256(expected_apk_sha256)
    if expected is None:
        raise ValueError("session-sustained-check requires --expected-apk-sha256")
    device = Device()
    installed = device.owned()
    bind_installed_apk(installed, expected_sha256=expected)
    attempt = attempt_from_installed(installed)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    selector = runtime + "/movement-batch-selection.json"
    report_path = runtime + "/movement-batch-" + cleanup.SPINE_ID + ".json"
    if cleanup._remote_path_state(device, selector) != "absent" or device.sh("pidof", PACKAGE, check=False).strip():
        raise RuntimeError("Requires idle owned package and absent selector; preserve foreign state")
    if cleanup._remote_path_state(device, runtime + "/offline-settings-v1/preferences.json.pending") != "absent":
        raise RuntimeError("Preserve existing pending settings state")
    out = device.evidence_directory("experiments", "session-sustained", now())
    out.mkdir(parents=True, exist_ok=False)
    result = dict(success=False, apk_sha256=expected, attempt=attempt, planned_seconds=PLANNED_SECONDS, scope=SCOPE, samples=[])
    pid = None
    width = height = None

    def errors(name):
        logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "epoch", "Unity:I", "AndroidRuntime:E", "*:S")
        found = current_errors(logs, pid)
        if found or name == "complete-process":
            (out / (name + ".log")).write_text(logs)
        if found:
            result["runtime_errors"] = found
            raise RuntimeError("First actual-PID runtime error")

    def wait(check, timeout=100):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not cleanup._same_process(device, pid):
                raise RuntimeError("Owned process exited before expected transition")
            report = cleanup._read_json(device, report_path)
            if cleanup.matches_run(report, pid, attempt):
                failures = cleanup.report_errors(report)
                failures.extend(cleanup.survivor_identity_failures(report, "Commando"))
                if report.get("phase") == "integrated-world-playing":
                    failures.extend(cleanup.first_stage_errors(report, required=True))
                if report.get("firstFailure") or failures:
                    raise RuntimeError("Native first failure: " + str(report.get("firstFailure") or failures[0]))
                if check(report):
                    return report
            errors("first-error")
            time.sleep(1)
        raise RuntimeError("Current native report deadline")

    def gesture(name, steps):
        request = out / (name + "-request.json")
        write(request, dict(pid=pid, width=width, height=height, steps=steps))
        value = touch_gesture.run(request, expected)
        if value.get("termination") != "steps-complete":
            raise RuntimeError("Software touch did not complete its scoped steps")
        return value

    def edge(action, x, y):
        return dict(action=action, id=0, x=x, y=y)

    def tap(name, x, y):
        return gesture(name, [edge("down", x, y), dict(action="wait", ms=150), edge("up", x, y), dict(action="wait", ms=600)])

    def thermal():
        battery = device.sh("dumpsys", "battery")
        hal = device.sh("dumpsys", "thermalservice")
        try:
            return thermal_sample(battery, hal)
        except RuntimeError:
            (out / "thermal-stop-battery.txt").write_text(battery)
            (out / "thermal-stop-hal.txt").write_text(hal)
            raise

    try:
        # Refuse an already hot/unknown device before beginning the workload.
        thermal()
        selected = cleanup.selection(attempt)
        selected["debugOptions"].update(invincibility=True, purpose=SCOPE)
        write(out / "selection.json", selected)
        device.cmd("push", str(out / "selection.json"), selector)
        pid = str((_launch(device) if _launch else device.launch())["pid"])
        write(out / "launch.json", dict(pid=pid, attempt=attempt, apk_sha256=expected))
        if not device.display(True):
            raise RuntimeError("Selected test display cannot be verified awake")
        report = wait(lambda r: r.get("phase") == "offline-start-menu")
        width, height = report["settings"]["screenWidth"], report["settings"]["screenHeight"]
        coords = cleanup.menu_start_coordinates(report)
        if coords is None:
            raise RuntimeError("Current native menu Start geometry unavailable")
        tap("start", *coords)
        report = wait(lambda r: r.get("phase") == "integrated-world-playing" and r.get("world", {}).get("ready") is True, 240)
        require_invincibility_only(report)
        tap("manual-neutral", width * 0.5, 34)
        report = wait(lambda r: r.get("world", {}).get("manualTakeover") is True and (r.get("nova", {}).get("touch") or {}).get("moveRadius", 0) > 0, 20)
        baseline = cleanup._profile_counts(report)
        if baseline is None:
            raise RuntimeError("Native profile baseline unavailable")
        write(out / "world-start.json", report)
        began = time.monotonic()
        last_capture = -60
        last_camera = 0
        index = 0
        while True:
            elapsed = time.monotonic() - began
            report = wait(lambda r: True, 5)
            errors("first-error")
            snapshot = None
            read_deadline = time.monotonic() + 3
            while not isinstance(snapshot, dict) and time.monotonic() < read_deadline:
                snapshot = cleanup._read_json(device, runtime + "/snapshot.json")
                if not isinstance(snapshot, dict):
                    time.sleep(0.1)
            row = observation_sample(report, snapshot, elapsed, result["samples"][-1] if result["samples"] else None)
            # Check stop thresholds at every sample, not only at capture time.
            row.update(thermal())
            result["samples"].append(row)
            result["observed_seconds"] = elapsed
            if elapsed - last_capture >= 60:
                folder = out / ("sample-%04d" % index)
                write(folder / "world.json", report)
                device.collect("perf", folder)
                last_capture = elapsed
                index += 1
            write(out / "progress.json", result)
            if elapsed >= PLANNED_SECONDS:
                result["sustained_observation_complete"] = True
                write(out / "world-end.json", report)
                break
            if elapsed - last_camera >= 60:
                x, y = width * 0.73, height * 0.3
                gesture(
                    "camera-%04d" % index,
                    [edge("down", x, y), dict(action="wait", ms=100), edge("move", x + 20, y), dict(action="wait", ms=100), edge("up", x + 20, y)],
                )
                last_camera = elapsed
            time.sleep(5)
        for key, condition in (
            ("button", lambda r: r["settings"]["visible"] is True),
            ("endRunButton", lambda r: r["settings"]["endRunConfirmationVisible"] is True),
            ("confirmEndRunButton", lambda r: r.get("session") == 2 and r.get("phase") == "offline-start-menu"),
        ):
            coords = cleanup.abandon_control_coordinates(report, key, device.sh("wm", "size"), device.sh("dumpsys", "window", "displays"))
            if coords is None:
                raise RuntimeError("Current native End Run geometry unavailable")
            tap("native-" + key, *coords)
            report = wait(condition)
        completed = cleanup._read_json(device, runtime + "/movement-completed-session-1.json")
        if not isinstance(completed, dict):
            raise RuntimeError("Missing native completed-session report")
        write(out / "completed-session.json", completed)
        write(out / "returned-menu.json", report)
        result["all_off_contract_refusals"] = assisted_teardown_contract(completed, pid, attempt, baseline)
        errors("complete-process")
        result.update(native_teardown_complete=True, success=True)
    except BaseException as error:
        result["error"] = str(error) or type(error).__name__
    finally:
        cleanup_errors = []
        try:
            if pid:
                errors("complete-process")
        except Exception as error:
            cleanup_errors.append(str(error))
        try:
            state = cleanup._remote_path_state(device, selector)
            action = cleanup.selector_action(state, cleanup._read_raw(device, selector) if state == "file" else "", attempt)
            if action == "remove-owned":
                device.sh("rm", "--", selector)
                if cleanup._remote_path_state(device, selector) != "absent":
                    raise RuntimeError("Owned selector remains")
            elif action != "none":
                raise RuntimeError("Selector ownership changed; preserved it")
            result["selector_cleanup"] = action
        except Exception as error:
            cleanup_errors.append(str(error))
        try:
            if pid and cleanup._same_process(device, pid):
                bind_installed_apk(device.owned(), expected_sha256=expected)
                device.sh("am", "force-stop", PACKAGE)
            if device.sh("pidof", PACKAGE, check=False).strip():
                raise RuntimeError("Owned package remains running")
        except Exception as error:
            cleanup_errors.append(str(error))
        try:
            if not device.display(False):
                raise RuntimeError("OLED sleep not verified")
        except Exception as error:
            cleanup_errors.append(str(error))
        result["cleanup_errors"] = cleanup_errors
        result["success"] = result["success"] and not cleanup_errors
        result["evidence"] = str(out.relative_to(WORK.parent))
        write(out / "result.json", result)
    if not result["success"]:
        raise RuntimeError("Sustained assisted check failed; inspect " + result["evidence"])
    return {key: result[key] for key in ("success", "apk_sha256", "observed_seconds", "all_off_contract_refusals", "evidence", "scope")}
