"""Current shared device lifecycle. Private requests/evidence stay under work/.

python3 scripts/lab/device_session.py --request work/.../request.json --dry-run
python3 scripts/lab/device_session.py --request work/.../request.json --detach

The dispatcher grants the device before invocation. This runner acquires its
lease atomically; it never waits for a peer, publishes, or grants itself a slot.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, ExitStack
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from uuid import uuid4

PACKAGES = {"dev.ror2lab.arm64", "dev.ror2lab.converted"}
PROCESS_TIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
TRANSIENTS = ("movement-batch-selection.json", "offline-settings-v1/preferences.json.pending")
GOLEM_ATTACK = re.compile(r"^\s*(\d+\.\d+)\s+(\d+)\s+\d+\s+I Unity\s+:\s+EntityStates\.GolemMonster\.(ClapState|FireLaser):OnEnter\(\)\s*$")
TITAN_INDICATOR = re.compile(r"^\s*(\d+\.\d+)\s+(\d+)\s+\d+\s+I Unity\s+:\s+lab-titan-prefist-visible frame=\d+\s*$")
DEVICE_RESERVE_BYTES = 20 * 1024**3
INTERNAL_INSTALL_FLOOR_BYTES = 15 * 1024**3
UNPLUGGED_SECONDS = 30 * 60
UNPLUGGED_REQUEST = "owner-unplugged-request.json"


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def load_request(path, serial=None):
    path = Path(path).resolve(strict=True)
    value = json.loads(path.read_text())
    required = {"canonical_root", "output", "workstream", "package", "apk", "apk_sha256", "duration_seconds"}
    optional = {
        "serial",
        "adopted_install",
        "cooldown_seconds",
        "mode",
        "input_script",
        "input_schedule",
        "input_mapping",
        "selection",
        "diagnostics",
        "prior_receipt",
        "require_high_refresh",
        "payload_directory",
        "capture_interval_seconds",
        "pacing_diagnostics",
        "start_from_menu",
        "capture_golem_attacks",
        "capture_titan_indicator",
    }
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError("Request has missing or unknown fields")
    for name in ("canonical_root", "output", "apk", "input_script", "input_mapping", "prior_receipt", "payload_directory"):
        if name in value:
            target = Path(value[name]).expanduser()
            value[name] = str((path.parent / target).resolve())
    root, output = Path(value["canonical_root"]), Path(value["output"])
    if not (root / "scripts/env.sh").is_file() or not output.is_relative_to(root / "work"):
        raise ValueError("Canonical root and private output under work/ are required")
    if value["package"] not in PACKAGES or value.get("adopted_install", True) is not True:
        raise ValueError("Disposable package required; adopted_install, when set, must be true")
    from device_context import validate_serial

    value["serial"] = validate_serial(serial if serial is not None else value.get("serial"))
    if not re.fullmatch(r"[a-z0-9-]+", value["workstream"]):
        raise ValueError("Explicit serial and workstream required")
    if serial is not None:
        grant = root / ".local/orchestrator/devqueue" / (serial + ".granted")
        if not grant.is_file() or grant.read_text().strip() != value["workstream"]:
            raise ValueError("Selected device queue grant does not name this workstream")
    if not re.fullmatch(r"[0-9a-f]{64}", value["apk_sha256"]):
        raise ValueError("Expected APK SHA-256 required")
    value.setdefault("mode", "launch")
    for name, default in (("duration_seconds", None), ("cooldown_seconds", 3600), ("capture_interval_seconds", 5 if value["mode"] == "sustained" else 60)):
        value.setdefault(name, default)
        if type(value[name]) is not int or value[name] <= 0:
            raise ValueError(name + " must be a positive integer")
    if value["mode"] not in {
        "launch",
        "sustained",
        "settings-save-failure",
        "profile-write-interrupt",
        "software-notices",
        "player-screens",
        "owner-unplugged",
    }:
        raise ValueError("Unknown device workload mode")
    if value["mode"] != "launch" and value["package"] != "dev.ror2lab.arm64":
        raise ValueError("The native workload owner requires the lab package")
    if value["mode"] in {"settings-save-failure", "profile-write-interrupt"} and "selection" in value:
        raise ValueError("Persistence workload owns its attempt-bound selector")
    if value["mode"] in {"software-notices", "player-screens"} and "selection" in value:
        raise ValueError("Software notices workload owns its attempt-bound selector")
    if value["mode"] == "owner-unplugged":
        if value["duration_seconds"] != UNPLUGGED_SECONDS or "adopted_install" not in value:
            raise ValueError("Owner unplugged workload requires 30 minutes and adopted-only installation")
        if (value.keys() - required) & {
            "input_script",
            "input_mapping",
            "input_schedule",
            "selection",
            "diagnostics",
            "pacing_diagnostics",
            "start_from_menu",
            "capture_golem_attacks",
            "capture_titan_indicator",
            "require_high_refresh",
        }:
            raise ValueError("Owner unplugged workload uses physical play and its dedicated recorder")
    for name in ("require_high_refresh", "pacing_diagnostics", "start_from_menu", "capture_golem_attacks", "capture_titan_indicator"):
        if name in value and type(value[name]) is not bool:
            raise ValueError(name + " must be boolean")
    if value.get("start_from_menu") and value["mode"] != "launch":
        raise ValueError("start_from_menu requires the launch workload")
    for name in ("capture_golem_attacks", "capture_titan_indicator"):
        if value.get(name) and (value["mode"] != "launch" or value["package"] != "dev.ror2lab.arm64"):
            raise ValueError(name + " requires the native lab launch workload")
    for name in ("selection", "diagnostics"):
        if name in value and not isinstance(value[name], dict):
            raise ValueError(name + " must be a JSON object")
    if value["mode"] == "sustained":
        selection = value.get("selection", {})
        if selection.keys() - {"detailedVisualDiagnostics"} or type(selection.get("detailedVisualDiagnostics", False)) is not bool:
            raise ValueError("Sustained workload owns its seed-2 attempt-bound selector; only detailedVisualDiagnostics may be selected")
    apk = Path(value["apk"])
    with apk.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != value["apk_sha256"]:
        raise ValueError("APK bytes differ from the request hash")
    if "payload_directory" in value and not payload_files(value):
        raise ValueError("Payload directory must contain runtime files")
    scripts = [value["input_script"]] if "input_script" in value else []
    if "input_schedule" in value:
        schedule = value["input_schedule"]
        if value["mode"] != "launch" or not isinstance(schedule, list) or not schedule:
            raise ValueError("input_schedule requires launch mode and a nonempty list")
        previous = -1
        for item in schedule:
            if not isinstance(item, dict) or set(item) != {"at_seconds", "script"}:
                raise ValueError("Scheduled touch requires at_seconds and script")
            when = item["at_seconds"]
            if type(when) is not int or not previous <= when <= value["duration_seconds"] or when < 0:
                raise ValueError("Scheduled touch times must be ordered within the observation")
            target = Path(item["script"]).expanduser()
            item["script"] = str((path.parent / target).resolve())
            scripts.append(item["script"])
            previous = when
    if scripts:
        # A script is declarative targeted touch input, never executable code.
        import common

        common.WORK = root / "work"
        import touch_gesture

        for script in scripts:
            inputs = json.loads(Path(script).read_text())
            touch_gesture.validate_request(dict(inputs, pid="1"))
    if "input_mapping" in value:
        checked_mapping(value)
    return value


def payload_files(request):
    if "payload_directory" not in request:
        return []
    return [path for path in Path(request["payload_directory"]).glob("*") if path.is_file() and path.suffix != ".manifest" and path.name != ".prune-keep"]


def checked_mapping(request):
    """Reuse the measured input bridge, bound to this APK's embedded attempt."""
    from installed_attempt import attempt_from_installed

    root = Path(request["canonical_root"])
    attempt = attempt_from_installed(dict(apk=request["apk"], apk_sha256=request["apk_sha256"]))
    mapping_path = Path(request["input_mapping"])
    mapping = json.loads(mapping_path.read_text())
    checkpoint_path = root / "work/checkpoints/LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    accepted = checkpoint["mapping"]
    if (
        mapping["attempt"] != attempt
        or mapping["accepted_mapping_attempt"] != accepted["attempt"]
        or any(mapping.get(key) != value for key, value in accepted.items() if key != "attempt")
        or not checkpoint["passing"]["cleanup"]
        or checkpoint["passing"]["assertions"] <= 0
    ):
        raise RuntimeError("Accepted input mapping does not match APK attempt/checkpoint")
    observation = root / mapping["observation"]
    if observation.exists() and hashlib.sha256(observation.read_bytes()).hexdigest() != mapping["observation_sha256"]:
        raise RuntimeError("Retained input observation hash changed")
    return mapping


def reset_other_lab(request, lease, record, cleanup=None):
    """Converted runs also leave the separately owned lab package idle."""
    if request["package"] == "dev.ror2lab.arm64":
        return
    from alpha_stability_batch import _idle_readback
    from device import Device

    lab = Device(selector=request["serial"], work_root=Path(request["canonical_root"]) / "work")
    lease.require()
    if not lab.exists():
        record["installed"] = False
        return
    expected = verify_owned(lab)["apk_sha256"]
    reset_idle(lab, lease, record, cleanup)
    record["readback"] = _idle_readback(lab, expected)


def source_environment(root):
    result = subprocess.run(["/bin/zsh", "-c", "source scripts/env.sh && env -0"], cwd=root, capture_output=True, check=True, timeout=30)
    for item in result.stdout.split(b"\0"):
        key, separator, value = item.partition(b"=")
        if separator:
            os.environ[os.fsdecode(key)] = os.fsdecode(value)


class Lease:
    def __init__(self, request):
        self.path = Path(request["canonical_root"]) / ".local/orchestrator/leases" / request["serial"]
        self.owner = dict(workstream=request["workstream"], pid=os.getpid(), run=request["output"])
        self.acquired = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.mkdir()  # Refuse contention before any ADB command.
        self.acquired = True
        save(self.path / "owner.json", self.owner)

    def require(self):
        if not self.acquired or json.loads((self.path / "owner.json").read_text()) != self.owner:
            raise RuntimeError("Device lease is not owned by this run")

    def release(self):
        self.require()
        (self.path / "owner.json").unlink()
        self.path.rmdir()
        self.acquired = False


def verify_owned(device, expected=None):
    installed = device.owned()
    actual = device.sh("sha256sum", installed["package_path"].removeprefix("package:")).split()
    if not actual or actual[0] != installed["apk_sha256"] or (expected and actual[0] != expected):
        raise RuntimeError("Live package bytes differ from owned APK")
    return installed


def lab_process_snapshot(device, checkpoints, phase):
    rows = device.sh("sh", "-c", "date '+%F %T' && ps -A -o PID,STIME:19,NAME", timeout=5).splitlines()
    if len(rows) < 2 or not PROCESS_TIME.fullmatch(rows[0]) or rows[1].split() != ["PID", "STIME", "NAME"]:
        raise RuntimeError("Android process snapshot unavailable at " + phase)
    processes = []
    for line in rows[2:]:
        columns = line.split()
        if not columns:
            continue
        name = columns[-1]
        package = name.partition(":")[0]
        if package not in PACKAGES:
            continue
        if len(columns) != 4:
            raise RuntimeError("Invalid owned process identity at " + phase)
        pid, start_date, start_clock, _ = columns
        start_time = start_date + " " + start_clock
        if not pid.isdecimal() or not PROCESS_TIME.fullmatch(start_time):
            raise RuntimeError("Invalid owned process identity at " + phase)
        processes.append(dict(pid=pid, start_time=start_time, package=package, name=name))
    checkpoints.append(dict(phase=phase, device_time=rows[0], processes=processes))
    return processes


def check_lab_processes(device, checkpoints, phase, expected_pid=None):
    """Bind the lifecycle to the selected main process and record peers."""
    processes = lab_process_snapshot(device, checkpoints, phase)
    expected = [] if expected_pid is None else [(str(expected_pid), device.package)]
    if [(row["pid"], row["name"]) for row in processes] != expected:
        raise RuntimeError("Unexpected owned lab process at " + phase)


def reset_resumed_peer(device, request, lease, result):
    """Handle the owned lab returning on wake, before a converted launch."""
    if device.package != "dev.ror2lab.converted":
        return
    processes = lab_process_snapshot(device, result["process_checkpoints"], "after-keyguard")
    if not processes:
        return
    if any(row["package"] != "dev.ror2lab.arm64" for row in processes):
        raise RuntimeError("Unexpected owned lab process after keyguard dismissal")
    lease.require()
    events = device.cmd("logcat", "-b", "events", "-d", "-t", "500", "-v", "threadtime", "am_proc_start:I", "*:S", check=False)
    record = result["resumed_lab_reset"] = {}
    record["process_start_events"] = [line for line in events.splitlines() if any("," + row["pid"] + "," in line and row["name"] in line for row in processes)]
    reset_other_lab(request, lease, record, result["device_cleanup"])


def reset_idle(device, lease, record, cleanup=None):
    """Remove exactly two known transient files from a verified owned package."""
    from session_cleanup_check import _remote_path_state
    from device import remove_device_file

    lease.require()
    verify_owned(device)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    record["process_before"] = device.sh("pidof", device.package, check=False).strip()
    record["removed"] = []
    device.sh("am", "force-stop", device.package)
    for suffix in TRANSIENTS:
        lease.require()
        remote = runtime + "/" + suffix
        row = dict(path=remote, before=_remote_path_state(device, remote), sha256=device.sh("sha256sum", "--", remote, check=False))
        record["removed"].append(row)
        if row["before"] != "absent":
            remove_device_file(device, remote, cleanup)


def placement(device, reserve, *, adopted_only=False, install_apk=None):
    storage = device.storage()  # UUID is discovered afresh, never supplied.
    mode = storage["mode"]
    if adopted_only and mode != "adopted":
        raise RuntimeError("This request requires adopted storage")
    volume = storage[mode]
    if storage["shared"]["total_bytes"] != volume["total_bytes"]:
        raise RuntimeError("Shared storage is not backed by the selected " + mode + " volume")
    if mode == "internal" and install_apk is not None:
        capacity = device.install_capacity(install_apk, storage)
        reserve = max(reserve, capacity["estimate_bytes"] + INTERNAL_INSTALL_FLOOR_BYTES)
    if volume["free_bytes"] < reserve:
        raise RuntimeError("Insufficient " + mode + " free space for output plus reserve")
    if device.exists():
        if mode == "internal":
            apk_prefix = "/data/app/"
            data_prefixes = ("/data/user/0/", "/data/data/")
        else:
            apk_prefix = "/mnt/expand/" + storage["uuid"] + "/"
            data_prefixes = (apk_prefix + "user/0/",)
        if not device.owned()["package_path"].startswith("package:" + apk_prefix):
            raise RuntimeError("Owned package is not on the selected " + mode + " volume")
        details = device.sh("dumpsys", "package", device.package)
        if not any(line.strip() in {"dataDir=" + prefix + device.package for prefix in data_prefixes} for line in details.splitlines()):
            raise RuntimeError("Owned runtime data is not on the selected " + mode + " volume")
    return storage


def adopt_receipt(device, path):
    """Migrate a peer's explicit ownership receipt only after live readback."""
    receipt = json.loads(Path(path).read_text())
    if receipt.get("serial") != device.serial or receipt.get("package") != device.package:
        raise RuntimeError("Prior ownership receipt does not match selected package/device")
    current = device.sh("pm", "path", device.package)
    if current != receipt.get("package_path") or not current.startswith("package:") or "\n" in current:
        raise RuntimeError("Prior receipt package placement changed")
    actual = device.sh("sha256sum", current.removeprefix("package:")).split()
    if not actual or actual[0] != receipt.get("apk_sha256"):
        raise RuntimeError("Prior receipt live package hash changed")
    device.write_receipt("installed.json", receipt)


def ensure_runtime(device):
    if not device.receipt("runtime.json").exists():
        # Device validates the selected package suffix and backing volume.
        verify_owned(device)
        runtime = "/sdcard/Android/data/" + device.package + "/files"
        device.sh("mkdir", "-p", runtime)
        device.write_receipt("runtime.json", dict(persistentDataPath=runtime))
    return device.read_receipt("runtime.json")["persistentDataPath"]


def keyguard_state(device):
    policy = device.sh("dumpsys", "window", "policy")
    flags = re.findall(r"\b(?:mDreamingLockscreen|isKeyguardShowing|mShowingLockscreen)=(true|false)\b", policy)
    delegate = policy.partition("KeyguardServiceDelegate")[2]
    flags += re.findall(r"\bshowing=(true|false)\b", delegate)
    secure = re.findall(r"\bsecure=(true|false)\b", delegate)
    return dict(showing=any(flag == "true" for flag in flags) if flags else None, secure=secure[0] == "true" if secure else None)


def prepare_launch(device, record):
    """Dismiss an unsecured keyguard before either owned launcher runs."""
    device.sh("input", "keyevent", "KEYCODE_WAKEUP")
    record["before"] = keyguard_state(device)
    if record["before"]["showing"] is not False and record["before"]["secure"] is True:
        raise RuntimeError("Secure keyguard requires user credential; device run aborted before launch")
    device.sh("wm", "dismiss-keyguard")
    time.sleep(0.5)
    record["after_dismiss"] = keyguard_state(device)
    if record["after_dismiss"]["showing"] is True and record["after_dismiss"]["secure"] is not True:
        sizes = re.findall(r"(?:Physical|Override) size: (\d+)x(\d+)", device.sh("wm", "size"))
        if not sizes:
            raise RuntimeError("Keyguard swipe unavailable: display dimensions unknown")
        width, height = map(int, sizes[-1])
        record["swipe"] = True
        device.sh("input", "-d", "0", "swipe", str(width // 2), str(height * 4 // 5), str(width // 2), str(height // 5), "300")
        time.sleep(0.5)
        record["after_swipe"] = keyguard_state(device)
    final = record.get("after_swipe", record["after_dismiss"])
    if final["showing"] is not False:
        reason = "Secure keyguard requires user credential" if final["secure"] is True else "Keyguard dismissal not verified"
        raise RuntimeError(reason + "; device run aborted before launch")


def launch(device, thermal, *, process_checks):
    check_lab_processes(device, process_checks, "before-launch")
    if device.package == "dev.ror2lab.arm64":
        result = thermal.launch(device)
    else:
        result = _launch_converted(device, thermal)
    check_lab_processes(device, process_checks, "launch", result["pid"])
    return result


def _launch_converted(device, thermal):
    if thermal.error:
        raise RuntimeError(thermal.error)
    component = device.sh(
        "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", device.package
    ).splitlines()[-1]
    if not component.startswith(device.package + "/") or not re.fullmatch(r"[A-Za-z0-9_.$/]+", component):
        raise RuntimeError("Cannot resolve owned launcher activity")
    if not device.display(True):
        raise RuntimeError("Display wake verification failed")
    result = device.sh("am", "start", "-W", "-n", component)
    pid = device.sh("pidof", device.package, check=False).strip()
    if not pid.isdecimal():
        raise RuntimeError("Owned launcher process unavailable")
    if thermal.error:
        raise RuntimeError(thermal.error)
    return dict(pid=pid, launch=result, activity=component)


def capture(device, output, pid):
    from session_cleanup_check import SPINE_ID

    output.mkdir(parents=True, exist_ok=True)
    (output / "unity.log").write_text(device.cmd("logcat", "-d", "--pid=" + pid, "-v", "epoch", "Unity:D", "AndroidRuntime:E", "*:S"))
    device.collect("crash", output)
    device.collect("screenshot", output)
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    (output / "il2cpp-metadata-sha256.txt").write_text(device.sh("sha256sum", runtime + "/il2cpp/Metadata/global-metadata.dat", check=False))
    for name in ("snapshot.json", "movement-batch-" + SPINE_ID + ".json", "movement-batch-" + SPINE_ID.removesuffix("-bringup") + ".json"):
        (output / name).write_text(device.sh("cat", runtime + "/" + name, check=False))
    device.collect("perf", output, include_exceptions=False)


def record_event_frames(device, thermal, pid, output, lines, stopping, events, pattern):
    from touch_gesture import owned_display_zero_focus

    for line in lines:
        if stopping.is_set() or thermal.cancelled.is_set():
            return
        match = pattern.fullmatch(line)
        if not match or match[2] != pid or len(events) >= 8:
            continue
        event = dict(log=line.strip(), received_epoch=time.time(), frames=[])
        events.append(event)
        if device.sh("pidof", device.package, check=False, timeout=3).strip() != pid:
            event["skipped"] = "owned process changed"
            continue
        if not owned_display_zero_focus(device.sh("dumpsys", "window", "displays", timeout=3), device.package):
            event["skipped"] = "owned display-zero focus absent"
            continue
        start = time.monotonic()
        for frame in range(3):
            stopping.wait(max(0, start + frame * 0.1 - time.monotonic()))
            if stopping.is_set() or thermal.cancelled.is_set():
                return
            began = time.time()
            data = subprocess.run(device.base + ["exec-out", "screencap", "-p"], capture_output=True, check=True, timeout=5).stdout
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Invalid combat event screenshot")
            filename = f"event-{len(events):02d}-frame-{frame}.png"
            (output / filename).write_bytes(data)
            event["frames"].append(dict(file=filename, began_epoch=began, finished_epoch=time.time()))


@contextmanager
def capture_combat_events(device, thermal, pid, output, pattern):
    """Watch the live Unity log while the normal workload collects full samples."""
    from device import require_device_access

    require_device_access()
    output.mkdir(parents=True, exist_ok=True)
    stopping = threading.Event()
    events = []
    command = device.base + ["logcat", "--pid=" + pid, "-T", "1", "-v", "epoch", "Unity:I", "*:S"]
    with (
        (output / "logcat.stderr").open("w") as error_log,
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log, text=True, errors="replace") as logs,
        ThreadPoolExecutor(max_workers=1) as worker,
    ):
        capture_job = worker.submit(record_event_frames, device, thermal, pid, output, logs.stdout, stopping, events, pattern)
        try:
            yield
        finally:
            stopping.set()
            early_exit = logs.poll()
            if early_exit is None:
                logs.terminate()
            try:
                logs.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logs.kill()
                logs.wait()
            try:
                capture_job.result()
                if early_exit is not None:
                    raise RuntimeError(f"Combat log stream ended before observation completed ({early_exit})")
            finally:
                save(output / "events.json", events)


def exception_log_size(device, path):
    # LabDiagnostics appends JSONL across launches. Stat the file while idle.
    return int(device.sh("sh", "-c", 'if [ -e "$1" ]; then stat -c %s -- "$1"; else printf 0; fi', "sh", path))


def diagnostic_scratch(device, runtime):
    """Inventory only the lab's frame and report files so unchanged captures survive."""
    rows = device.sh(
        "find",
        runtime,
        "-maxdepth",
        "1",
        "-type",
        "f",
        "(",
        "-name",
        "frame-times-*.bin",
        "-o",
        "-name",
        "snapshot.json",
        "-o",
        "-name",
        "movement-batch-*.json",
        "-o",
        "-name",
        "movement-completed-session-*.json",
        "-o",
        "-name",
        "owner-unplugged-*.jsonl",
        ")",
        "-exec",
        "stat",
        "-c",
        "%n|%y|%s",
        "{}",
        "+",
    )
    stamps = {}
    for row in rows.splitlines():
        path, stamp = row.split("|", 1)
        if Path(path).parent != Path(runtime):
            raise RuntimeError("Diagnostic scratch escaped the owned runtime directory")
        stamps[path] = stamp
    return stamps


def retain_diagnostic_scratch(device, runtime, initial, output, cleanup):
    from device import retain_device_file

    errors = []
    for remote, stamp in sorted(diagnostic_scratch(device, runtime).items()):
        if initial.get(remote) == stamp:
            continue
        try:
            retain_device_file(device, remote, output / Path(remote).name, cleanup)
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("Diagnostic scratch cleanup failed", errors)


def wait_for_settings_report(device, thermal, pid, predicate, timeout=100, *, report_id=None, attempt=None):
    import session_cleanup_check as cleanup
    from installed_attempt import attempt_from_installed

    report_id = report_id or cleanup.SPINE_ID
    if attempt is None:
        attempt = attempt_from_installed(device.owned())
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    deadline = time.monotonic() + timeout
    last_phase = None
    while time.monotonic() < deadline:
        if thermal.error:
            raise RuntimeError(thermal.error)
        if device.sh("pidof", device.package, check=False).strip() != pid:
            raise RuntimeError("Owned process changed during settings admission")
        report = cleanup._read_json(device, runtime + "/movement-batch-" + report_id + ".json")
        if cleanup.matches_run(report, pid, attempt, report_id=report_id):
            last_phase = report.get("phase")
            if report.get("firstFailure"):
                raise RuntimeError("Native first failure: " + str(report["firstFailure"]))
            if predicate(report):
                return report
        time.sleep(0.5)
    raise RuntimeError(f"Native report observation deadline (last owned phase: {last_phase or 'unavailable'})")


def qualify_high_refresh(device, thermal, output, pid):
    report = wait_for_settings_report(device, thermal, pid, lambda r: r.get("phase") == "offline-start-menu" and r.get("settings", {}).get("ready") is True)
    save(output / "settings-report.json", report)
    if report["settings"].get("highRefreshRate") is not True:
        raise RuntimeError("High-refresh preference disabled; preserve user choice")
    logs = device.sh("logcat", "-d", "--pid=" + pid, "-v", "epoch", "RoR2LabDisplay:I", "*:S")
    (output / "display-request.log").write_text(logs)
    matches = re.findall(r"request high=(true|false) mode=(\d+) rate=([0-9.]+) observed=([0-9.]+) surfaces=(\d+)", logs)
    if not matches or matches[-1][0] != "true" or float(matches[-1][2]) < 119 or int(matches[-1][4]) <= 0:
        raise RuntimeError("Persisted 120 Hz app request unavailable")


def check_software_notices(device, thermal, request, output, process_checks):
    """One owned menu/settings/notices/back flow; shared runner owns lifecycle."""
    from installed_attempt import attempt_from_installed
    from session_cleanup_check import selection
    from settings_write_interrupt_check import protected_hashes
    import touch_gesture

    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    before = protected_hashes(device, runtime)
    settings_before = device.sh("find", runtime + "/offline-settings-v1", "-type", "f", "-exec", "sha256sum", "{}", "+", check=False)
    selected = output / "notices-selection.json"
    save(selected, selection(attempt_from_installed(device.owned())))
    device.cmd("push", str(selected), runtime + "/movement-batch-selection.json")
    launched = launch(device, thermal, process_checks=process_checks)
    save(output / "launch.json", launched)
    pid = str(launched["pid"])

    def wait(name, predicate):
        report = wait_for_settings_report(device, thermal, pid, predicate)
        save(output / (name + ".json"), report)
        return report

    def tap(name, report, x, y):
        path = output / (name + ".input.json")
        save(
            path,
            dict(
                pid=pid,
                width=report["settings"]["screenWidth"],
                height=report["settings"]["screenHeight"],
                steps=[dict(action="down", id=0, x=x, y=y), dict(action="wait", ms=100), dict(action="up", id=0, x=x, y=y), dict(action="wait", ms=400)],
            ),
        )
        touch_gesture.run(path, request["apk_sha256"], device=device)

    menu = wait("menu", lambda r: r.get("phase") == "offline-start-menu" and r.get("settings", {}).get("ready") is True)
    tap("open-settings", menu, menu["settings"]["buttonX"], menu["settings"]["buttonY"])
    settings = wait("settings", lambda r: r["settings"]["visible"] is True)
    width, height = settings["settings"]["screenWidth"], settings["settings"]["screenHeight"]
    tap("open-notices", settings, width * 0.5 + 110, height * 0.5 + 238.5)
    notices = wait("notices", lambda r: r["settings"].get("softwareNoticesVisible") is True and r["settings"].get("softwareNoticesBackX", 0) > 0)
    if notices["settings"].get("softwareNoticesAvailable") is not True:
        raise RuntimeError("Source software notices are unavailable")
    capture(device, output / "notices-screen", pid)
    tap("back", notices, notices["settings"]["softwareNoticesBackX"], notices["settings"]["softwareNoticesBackY"])
    returned = wait("returned-settings", lambda r: r["settings"]["visible"] is True and r["settings"].get("softwareNoticesVisible") is False)
    tap("close-settings", returned, returned["settings"]["buttonX"], returned["settings"]["buttonY"])
    wait("returned-menu", lambda r: r.get("phase") == "offline-start-menu" and r["settings"]["visible"] is False)
    capture(device, output / "returned-menu-screen", pid)
    if (
        protected_hashes(device, runtime) != before
        or device.sh("find", runtime + "/offline-settings-v1", "-type", "f", "-exec", "sha256sum", "{}", "+", check=False) != settings_before
    ):
        raise RuntimeError("Read-only notices flow changed protected profiles/results/settings")
    return dict(success=True, process_continuity=True, protected_files_unchanged=True)


def check_player_screens(device, thermal, request, output, process_checks):
    """Injected keyboard aliases share controller routes; physical playtest stays open."""
    from settings_write_interrupt_check import protected_hashes
    from touch_gesture import owned_display_zero_focus

    notices = check_software_notices(device, thermal, request, output / "software-notices", process_checks)
    pid = device.sh("pidof", device.package, check=False).strip()
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]

    def wait(name, predicate, timeout=100):
        report = wait_for_settings_report(device, thermal, pid, predicate, timeout=timeout)
        save(output / (name + ".json"), report)
        return report

    def key(name):
        if thermal.error:
            raise RuntimeError(thermal.error)
        if device.sh("pidof", device.package, check=False).strip() != pid:
            raise RuntimeError("Owned process changed before injected key")
        if not owned_display_zero_focus(device.sh("dumpsys", "window", "displays"), device.package):
            raise RuntimeError("Owned display-zero focus absent before injected key")
        device.sh("input", "keyboard", "keyevent", name)

    def hashes():
        return dict(
            protected=protected_hashes(device, runtime),
            settings=device.sh("find", runtime + "/offline-settings-v1", "-type", "f", "-exec", "sha256sum", "{}", "+", check=False),
        )

    wait("first-menu", lambda r: r.get("phase") == "offline-start-menu")
    check_lab_processes(device, process_checks, "start", pid)
    key("KEYCODE_ENTER")
    wait("playing", lambda r: r.get("phase") == "integrated-world-playing", timeout=request["duration_seconds"])
    capture(device, output / "playing-screen", pid)
    ended = wait(
        "persisted-defeat",
        lambda r: r.get("phase") == "commando-defeated"
        and r.get("results", {}).get("persisted") is True
        and r["results"].get("serverEnding") is True
        and r["results"].get("clientEnding") is True
        and r["results"].get("reportReloaded") is True,
        timeout=request["duration_seconds"],
    )
    capture(device, output / "results-screen", pid)
    before = hashes()
    key("KEYCODE_ESCAPE")
    menu = wait("returned-menu", lambda r: r.get("session", 0) > ended["session"] and r.get("phase") == "offline-start-menu")
    if menu.get("firstFailure"):
        raise RuntimeError("Returned menu has a native failure")
    key("KEYCODE_L")
    wait("loadout", lambda r: r.get("hud", {}).get("menuLoadoutVisible") is True and r["hud"].get("menuLoadoutRow") == 0)
    key("KEYCODE_DPAD_DOWN")
    row = wait("loadout-row", lambda r: r.get("hud", {}).get("menuLoadoutRow") == 1)
    key("KEYCODE_ENTER")
    wait(
        "loadout-cycle",
        lambda r: r.get("phase") == "offline-start-menu"
        and r.get("hud", {}).get("menuLoadoutVisible") is True
        and r["hud"].get("menuLoadoutCycles", 0) > row["hud"].get("menuLoadoutCycles", 0),
    )
    capture(device, output / "loadout-screen", pid)
    key("KEYCODE_ESCAPE")
    wait("loadout-closed", lambda r: r.get("hud", {}).get("menuLoadoutVisible") is False)
    key("KEYCODE_Q")
    wait("quit-confirmation", lambda r: r.get("hud", {}).get("menuQuitConfirmation") is True)
    capture(device, output / "quit-screen", pid)
    key("KEYCODE_ESCAPE")
    wait("quit-cancelled", lambda r: r.get("hud", {}).get("menuQuitConfirmation") is False and r.get("phase") == "offline-start-menu")
    after = hashes()
    save(output / "protected-files.json", dict(before=before, after=after))
    if after != before:
        raise RuntimeError("Menu/loadout/Quit cancel changed persisted profiles/results/settings")
    key("KEYCODE_Q")
    wait("quit-final", lambda r: r.get("hud", {}).get("menuQuitConfirmation") is True)
    key("KEYCODE_ENTER")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if thermal.error:
            raise RuntimeError(thermal.error)
        current = device.sh("pidof", device.package, check=False).strip()
        if not current:
            return dict(
                success=True,
                software_notices=notices,
                injected_keyboard_routes=True,
                physical_certification=False,
                protected_files_unchanged=True,
                process_continuity_until_quit=True,
                quit_exited=True,
            )
        if current != pid:
            raise RuntimeError("Quit unexpectedly replaced the owned process")
        time.sleep(0.5)
    raise RuntimeError("Confirmed Quit did not exit")


def start_from_menu(device, thermal, pid, output, *, process_checks, report_id=None, tap_start=False, attempt=None):
    """Start the observed owned menu and return the current world report."""
    from session_cleanup_check import menu_start_coordinates
    from touch_gesture import owned_display_zero_focus

    menu = wait_for_settings_report(device, thermal, pid, lambda r: r.get("phase") == "offline-start-menu", timeout=240, report_id=report_id, attempt=attempt)
    save(output / "start-menu.json", menu)
    if thermal.error:
        raise RuntimeError(thermal.error)
    check_lab_processes(device, process_checks, "start", pid)
    if not owned_display_zero_focus(device.sh("dumpsys", "window", "displays"), device.package):
        raise RuntimeError("Owned display-zero focus absent before menu Start")
    if tap_start:
        coordinates = menu_start_coordinates(menu)
        if coordinates is None:
            raise RuntimeError("Current native menu Start geometry unavailable")
        x, y = coordinates
        device.sh("input", "-d", "0", "tap", str(x), str(y), timeout=5)
    else:
        device.sh("input", "keyboard", "keyevent", "KEYCODE_ENTER")
    world = wait_for_settings_report(
        device,
        thermal,
        pid,
        lambda r: r.get("phase") == "integrated-world-playing" and r.get("world", {}).get("ready") is True,
        timeout=240,
        report_id=report_id,
        attempt=menu["attempt"],
    )
    save(output / "world-start.json", world)
    return world


def thermal_sensor_kind(name):
    return next((kind for kind in ("cpu", "gpu", "battery", "skin") if name.lower().startswith(kind)), None)


def unplugged_summary(path, config, pid):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows or any(row.get("nonce") != config["nonce"] or str(row.get("pid")) != pid for row in rows):
        raise RuntimeError("Unplugged trace has a different nonce or process")
    if rows[-1]["kind"] == "aborted":
        raise RuntimeError("Unplugged recorder aborted: " + rows[-1]["reason"])
    if rows[0]["kind"] != "ready" or rows[0]["zones"] != config["zones"] or rows[-1]["kind"] != "complete":
        raise RuntimeError("Unplugged trace lacks matching readiness and completion")
    samples = rows[1:-1]
    if not samples or samples[0]["elapsed_ms"] != 0 or samples[-1]["elapsed_ms"] < UNPLUGGED_SECONDS * 1000:
        raise RuntimeError("Unplugged trace does not cover 30 minutes")
    indices = [index for index, (kind, _) in enumerate(config["zones"]) if kind in {"cpu", "gpu"}]
    hot_since = {}
    for row in samples:
        if row["kind"] != "sample" or row["plugged"] != 0:
            raise RuntimeError("Unplugged trace contains a powered or non-sample row")
        if not 0 <= row["gap_ms"] <= 5000 or len(row["zones_millic"]) != len(config["zones"]):
            raise RuntimeError("Unplugged thermal coverage is incomplete")
        if row["battery_decic"] >= 430 or any(
            kind == "battery" and temperature >= 43000 for (kind, _), temperature in zip(config["zones"], row["zones_millic"])
        ):
            raise RuntimeError("Battery thermal limit exceeded")
        for index in indices:
            if row["zones_millic"][index] <= 95000:
                hot_since.pop(index, None)
            elif row["elapsed_ms"] - hot_since.setdefault(index, row["elapsed_ms"]) >= 3000:
                raise RuntimeError("CPU/GPU sustained thermal limit exceeded")
    peaks = [max(row["zones_millic"][index] for index in indices) / 1000 for row in samples]
    powers = [row["current_ua"] * row["voltage_mv"] for row in samples]
    energy = 0
    time_above80 = 0.0
    for index, (previous, current) in enumerate(zip(samples, samples[1:])):
        gap = current["elapsed_ms"] - previous["elapsed_ms"]
        if not 0 < gap == current["gap_ms"] or current["frames"] < previous["frames"]:
            raise RuntimeError("Unplugged samples have inconsistent time or frame counters")
        time_above80 += gap / 1000 if peaks[index] > 80 and gap <= 1000 else 0
        energy += (powers[index] + powers[index + 1]) * gap
    first, last = samples[0], samples[-1]
    duration = last["elapsed_ms"] / 1000
    energy_mwh = energy / (2 * 3_600_000 * 1_000_000)
    frames = last["frames"] - first["frames"]
    if frames <= 0:
        raise RuntimeError("Unplugged trace has no foreground Unity frames")
    return dict(
        duration_seconds=duration,
        samples=len(samples),
        foreground_unity_frames=frames,
        foreground_frames_per_elapsed_second=frames / duration,
        battery_start_percent=100 * first["level"] / first["scale"],
        battery_end_percent=100 * last["level"] / last["scale"],
        signed_terminal_energy_mwh=energy_mwh,
        mean_signed_terminal_power_mw=energy_mwh * 3600 / duration,
        peak_battery_celsius=max(row["battery_decic"] for row in samples) / 10,
        peak_cpu_gpu_celsius=max(peaks),
        time_above80_seconds=time_above80,
        thermal_gap_warnings=sum(row["gap_ms"] > 1000 for row in samples),
        max_thermal_gap_seconds=max(row["gap_ms"] for row in samples) / 1000,
    )


def observe_unplugged(device, request, output, result, pid):
    from device import retain_device_file

    config = json.loads((output / UNPLUGGED_REQUEST).read_text())
    name = "owner-unplugged-" + config["nonce"] + ".jsonl"
    remote = device.read_receipt("runtime.json")["persistentDataPath"] + "/" + name
    ready_deadline = time.monotonic() + 60
    while time.monotonic() < ready_deadline:
        row = device.sh("head", "-n", "1", "--", remote, check=False, timeout=5)
        if row:
            ready = json.loads(row)
            if ready.get("nonce") != config["nonce"] or str(ready.get("pid")) != pid:
                raise RuntimeError("Unplugged recorder readiness has a different nonce or process")
            if ready.get("kind") == "aborted":
                raise RuntimeError("Unplugged recorder could not arm: " + ready["reason"])
            if ready.get("kind") != "ready" or ready.get("zones") != config["zones"]:
                raise RuntimeError("Unplugged recorder readiness lacks the requested thermal coverage")
            break
        time.sleep(1)
    else:
        raise RuntimeError("APK did not acknowledge the unplugged recorder")

    prompt = "Unplug the Nova for 30 minutes now. Play normally, then reconnect USB when the recording finishes."
    save(output / "unplug-now.json", dict(message=prompt, ready=ready))
    print(prompt, flush=True)
    # Only the app observes the battery and device during this window.
    time.sleep(UNPLUGGED_SECONDS)
    reconnect_deadline = time.monotonic() + 600
    while time.monotonic() < reconnect_deadline:
        try:
            if device.cmd("get-state", check=False, timeout=5) == "device":
                row = device.sh("tail", "-n", "1", "--", remote, check=False, timeout=5)
                if row and json.loads(row).get("kind") in {"complete", "aborted"}:
                    break
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        time.sleep(5)
    else:
        raise RuntimeError("USB reconnect and recorder terminal row were not available in ten minutes")

    verify_owned(device, request["apk_sha256"])
    capture_path = output / name
    digest = retain_device_file(device, remote, capture_path, result["device_cleanup"])
    result["owner_unplugged"] = dict(trace=name, sha256=digest)
    result["owner_unplugged"].update(unplugged_summary(capture_path, config, pid))


def run_workload(device, thermal, request, output, result, *, _reset_idle=None, start_attempt=None):
    process_checks = result.setdefault("process_checkpoints", [])
    checked_launch = partial(launch, process_checks=process_checks)
    if request["mode"] == "owner-unplugged":
        launched = checked_launch(device, thermal)
        save(output / "launch.json", launched)
        observe_unplugged(device, request, output, result, str(launched["pid"]))
        return
    if request["mode"] == "profile-write-interrupt":
        from settings_write_interrupt_check import check_profile_write_interrupt

        result["profile_write_interrupt"] = check_profile_write_interrupt(
            device, thermal, request, output, checked_launch, partial(start_from_menu, process_checks=process_checks), result.get("device_cleanup")
        )
        return
    if request["mode"] == "player-screens":
        result["player_screens"] = check_player_screens(device, thermal, request, output, process_checks)
        return
    if request["mode"] == "software-notices":
        result["software_notices"] = check_software_notices(device, thermal, request, output, process_checks)
        return
    if request["mode"] == "settings-save-failure":
        import settings_write_interrupt_check as settings

        result["settings_save_failure"] = settings.check_settings_save_failure(
            device, output, request["apk_sha256"], lambda current: checked_launch(current, thermal), thermal.cancelled
        )
        return
    if request["mode"] == "sustained":
        import session_sustained_check as sustained

        def sustained_launch(current):
            launched = checked_launch(current, thermal)
            save(output / "launch.json", launched)
            if request.get("require_high_refresh"):
                qualify_high_refresh(current, thermal, output, str(launched["pid"]))
            capture(current, output / "launch", str(launched["pid"]))
            return launched

        evidence = device.evidence_directory("experiments", "session-sustained")
        prior = set(evidence.glob("*/result.json"))
        try:
            result["session"] = sustained.check_session_sustained(
                expected_apk_sha256=request["apk_sha256"],
                _launch=sustained_launch,
                raw_frame_times=True,
                duration_seconds=request["duration_seconds"],
                observation_interval_seconds=request.get("capture_interval_seconds", 5),
                detailed_visual_diagnostics=request.get("selection", {}).get("detailedVisualDiagnostics", False),
                _reset_idle=_reset_idle,
                _observe=observe_pacing if request.get("pacing_diagnostics") else None,
                _include_exceptions=False,
                _device_cleanup=result.get("device_cleanup"),
            )
        finally:
            fresh = set(evidence.glob("*/result.json")) - prior
            result["session_result_files"] = sorted(map(str, fresh))
        if len(fresh) != 1:
            raise RuntimeError("Ambiguous sustained evidence")
        return
    launched = checked_launch(device, thermal)
    save(output / "launch.json", launched)
    pid = str(launched["pid"])
    with ExitStack() as captures:
        if request.get("capture_golem_attacks"):
            captures.enter_context(capture_combat_events(device, thermal, pid, output / "golem-attacks", GOLEM_ATTACK))
        if request.get("capture_titan_indicator"):
            captures.enter_context(capture_combat_events(device, thermal, pid, output / "titan-indicator", TITAN_INDICATOR))
        observe_launch(device, thermal, request, output, result, pid, start_attempt=start_attempt)


def observe_launch(device, thermal, request, output, result, pid, *, start_attempt=None):
    if "input_script" in request:
        import touch_gesture

        inputs = dict(json.loads(Path(request["input_script"]).read_text()), pid=pid)
        save(output / "input.json", inputs)
        result["input"] = touch_gesture.run(output / "input.json", request["apk_sha256"], device=device)
    if request.get("start_from_menu"):
        from session_cleanup_check import SPINE_ID

        report_id = SPINE_ID.removesuffix("-bringup") if device.package == "dev.ror2lab.converted" else SPINE_ID
        start_from_menu(
            device,
            thermal,
            pid,
            output,
            process_checks=result.setdefault("process_checkpoints", []),
            report_id=report_id,
            tap_start=True,
            attempt=start_attempt,
        )
    began = time.monotonic()
    next_capture = 0
    scheduled = iter(enumerate(request.get("input_schedule", [])))
    pending = next(scheduled, None)
    while True:
        if thermal.cancelled.is_set():
            raise RuntimeError(thermal.error)
        elapsed = time.monotonic() - began
        if device.sh("pidof", device.package, check=False).strip() != pid:
            raise RuntimeError("Owned process exited or changed")
        while pending is not None and elapsed >= pending[1]["at_seconds"]:
            import touch_gesture

            index, item = pending
            inputs = dict(json.loads(Path(item["script"]).read_text()), pid=pid)
            input_path = output / ("scheduled-input-" + str(index) + ".json")
            save(input_path, inputs)
            observed = touch_gesture.run(input_path, request["apk_sha256"], device=device)
            result.setdefault("scheduled_inputs", []).append(dict(at_seconds=item["at_seconds"], dispatched_seconds=elapsed, result=observed))
            pending = next(scheduled, None)
            elapsed = time.monotonic() - began
        if elapsed >= next_capture:
            capture(device, output / ("sample-" + str(int(elapsed))), pid)
            next_capture += request.get("capture_interval_seconds", 60)
        if elapsed >= request["duration_seconds"]:
            break
        time.sleep(0.5)
    capture(device, output / "final", pid)
    result["observed_seconds"] = time.monotonic() - began


def observe_pacing(device, output, pid, snapshot):
    """Read package pacing and OS interventions without changing frame policy."""
    output.mkdir(parents=True, exist_ok=True)
    save(output / "snapshot.json", snapshot)
    (output / "display.log").write_text(device.sh("dumpsys", "display"))
    for filename, command in (
        ("frame-rate-overrides.log", ("dumpsys", "SurfaceFlinger", "--frame-rate-override")),
        ("game.log", ("dumpsys", "game", device.package)),
        ("gfxinfo-framestats.log", ("dumpsys", "gfxinfo", device.package, "framestats")),
        ("package.log", ("cmd", "package", "list", "packages", "-U", device.package)),
    ):
        # Unsupported commands remain raw evidence; never infer no override
        # from an empty or permission-refused response.
        (output / filename).write_text(device.sh(*command, check=False))
    properties = device.sh("getprop")
    (output / "frame-rate-properties.log").write_text(
        "\n".join(line for line in properties.splitlines() if re.search(r"frame.?rate|game.?default", line, re.I)) + "\n"
    )
    # Some Android versions expose overrides only in the complete SF dump.
    # Retain just matching lines locally; the package UID above identifies ours.
    compositor = device.sh("dumpsys", "SurfaceFlinger", check=False)
    (output / "compositor-overrides.log").write_text("\n".join(line for line in compositor.splitlines() if "override" in line.lower()) + "\n")
    (output / "frame-pacing.log").write_text(device.sh("logcat", "-d", "--pid=" + pid, "-v", "epoch"))
    layers = device.sh("dumpsys", "SurfaceFlinger", "--list")
    (output / "layers.txt").write_text(layers)
    selected = [line for line in layers.splitlines() if device.package in line and "SurfaceView" in line]
    for index, layer in enumerate(selected):
        # Preserve explicit empty/permission-refused results as unavailable.
        (output / ("latency-%02d.txt" % index)).write_text(device.sh("dumpsys", "SurfaceFlinger", "--latency", layer, check=False))


def execute(request):
    import common

    root, output = Path(request["canonical_root"]), Path(request["output"])
    common.WORK = root / "work"  # Set before importing owners that capture WORK.
    from alpha_stability_batch import _GameThermalOwner, _idle_readback, _prune
    from device import PACKAGE, Device, InstallSignatureMismatch, remove_device_file
    from device_context import command_selectors, set_command_selector
    from installed_attempt import attempt_from_installed

    output.mkdir(parents=True, exist_ok=True)
    done = output / "terminal.done.json"
    if done.exists():
        raise RuntimeError("Terminal receipt already exists; consume it instead of replaying")
    (output / ".prune-keep").touch()
    apk = Path(request["apk"])
    cleanup = dict(bytes_removed=0, files=[])
    result = dict(
        success=False,
        lease_released=False,
        apk=str(apk),
        apk_sha256=request["apk_sha256"],
        package=request["package"],
        mode=request["mode"],
        device_cleanup=cleanup,
        process_checkpoints=[],
    )
    lease, device, thermal = Lease(request), None, None
    restore = {}
    initial_scratch = None
    exception_log = None
    initial_exception_bytes = None
    active_hash = None
    started = time.monotonic()
    prior_selectors = command_selectors()
    try:
        source_environment(root)
        result["host_storage"] = dict(estimated_output_bytes=1024**3, margin_bytes=20 * 1024**3, free_bytes=shutil.disk_usage(output).free)
        if result["host_storage"]["free_bytes"] < 21 * 1024**3:
            raise RuntimeError("Host capture output plus 20 GiB margin unavailable")
        lease.acquire()
        subprocess.run(
            ["/opt/homebrew/bin/adb", "kill-server"], env=dict(os.environ, ANDROID_ADB_SERVER_PORT="5038"), check=True, capture_output=True, timeout=30
        )
        set_command_selector(request["serial"], None)
        device = Device(selector=request["serial"], work_root=common.WORK, package=request["package"])
        reset_other_lab(request, lease, result.setdefault("initial_lab_reset", {}), cleanup)
        if device.exists():
            if not device.receipt("installed.json").exists() and "prior_receipt" in request:
                adopt_receipt(device, request["prior_receipt"])
            active_hash = verify_owned(device)["apk_sha256"]
        payload = payload_files(request)
        payload_size = sum(path.stat().st_size for path in payload)
        reserve = apk.stat().st_size + payload_size + DEVICE_RESERVE_BYTES
        result["storage_before"] = placement(device, reserve, adopted_only=request.get("adopted_install", False), install_apk=apk)
        if active_hash:
            ensure_runtime(device)
            result["initial_reset"] = {}
            reset_idle(device, lease, result["initial_reset"], cleanup)
            save(output / "initial-reset.json", result["initial_reset"])
            result["initial_idle"] = _idle_readback(device, active_hash)
        check_lab_processes(device, result["process_checkpoints"], "before-install")
        try:
            try:
                result["install"] = device.install(apk)
            except InstallSignatureMismatch:
                if request["mode"] == "owner-unplugged" or device.package != PACKAGE or not active_hash or not payload:
                    raise
                limit = device.settings.get("apk_install_limit")
                if limit is not None and common.read(device.install_counter())["dispatched"] >= limit:
                    raise RuntimeError("No authorized install remains for signature recovery")
                lease.require()
                verify_owned(device, active_hash)
                recovery = result["install_recovery"] = dict(reason="INSTALL_FAILED_UPDATE_INCOMPATIBLE", previous_apk_sha256=active_hash)
                recovery["uninstall"] = device.reset()
                if not recovery["uninstall"]["removed"]:
                    raise RuntimeError("Signature recovery could not verify package removal")
                active_hash = None
                device.receipt("runtime.json").unlink(missing_ok=True)
                result["install"] = device.install(apk)
        finally:
            # The install owner saves its new receipt before placement checks.
            # If that check fails, cleanup must still bind the actual new APK.
            if device.receipt("installed.json").exists():
                active_hash = verify_owned(device)["apk_sha256"]
        active_hash = request["apk_sha256"]
        check_lab_processes(device, result["process_checkpoints"], "install")
        result["storage_after"] = placement(device, payload_size + DEVICE_RESERVE_BYTES)
        runtime = ensure_runtime(device)
        if "payload_directory" in request:
            result["sync"] = device.sync(Path(request["payload_directory"]), replace_previous=True, cleanup=cleanup)
            if "install_recovery" in result:
                result["install_recovery"]["payload_resynced"] = True
            result["storage_after_sync"] = placement(device, DEVICE_RESERVE_BYTES)
        result["installed_idle"] = _idle_readback(device, active_hash)
        exception_log = runtime + "/exceptions.jsonl"
        initial_exception_bytes = exception_log_size(device, exception_log)
        initial_scratch = diagnostic_scratch(device, runtime)
        mapping = checked_mapping(request) if "input_mapping" in request else None
        start_attempt = None
        if request.get("start_from_menu"):
            # APK inspection can starve the in-process thermal sampler. A checked
            # mapping already binds its attempt to the installed APK hash.
            start_attempt = mapping["attempt"] if mapping is not None else attempt_from_installed(device.owned())
        for name, payload in (
            ("diagnostics.json", request.get("diagnostics")),
            ("movement-batch-selection.json", request.get("selection") if request["mode"] == "launch" else None),
            ("nova-input-mapping.json", mapping),
        ):
            if payload is None:
                continue
            remote = runtime + "/" + name
            previous = device.sh("cat", remote, check=False)
            restore[remote] = previous if previous.lstrip().startswith("{") else None
            save(output / name, payload)
            device.cmd("push", str(output / name), remote)
            if json.loads(device.sh("cat", remote)) != payload:
                raise RuntimeError("Uploaded config differs: " + name)
        # Each invocation starts its own cooldown budget here, never a caller's clock.
        thermal = _GameThermalOwner(device, active_hash, output / "thermal.jsonl", time.monotonic() + request["cooldown_seconds"])
        thermal.phase = "cooldown"
        thermal.cool()
        thermal.deadline = time.monotonic() + request["duration_seconds"] + 600
        thermal.phase = request["mode"]
        prepare_launch(device, result.setdefault("prelaunch", {}))
        if request["mode"] == "owner-unplugged":
            zones = [(kind, path) for name, path in thermal.runtime_zones if (kind := thermal_sensor_kind(name))]
            if not {"cpu", "gpu"} <= {kind for kind, _ in zones}:
                raise RuntimeError("Owner unplugged workload requires CPU and GPU thermal sensors")
            config = dict(nonce=uuid4().hex, zones=zones)
            remote = runtime + "/" + UNPLUGGED_REQUEST
            if device.sh("sh", "-c", 'test ! -e "$1" && test ! -L "$1" && echo absent', "sh", remote, check=False) != "absent":
                raise RuntimeError("Previous owner session request is still present")
            restore[remote] = None
            local = output / UNPLUGGED_REQUEST
            local.write_text(json.dumps(config) + "\n")
            device.cmd("push", str(local), remote)
            if json.loads(device.sh("cat", remote)) != json.loads(local.read_text()):
                raise RuntimeError("Uploaded owner session request differs")
        else:
            thermal.start()
        reset_resumed_peer(device, request, lease, result)
        run_workload(
            device,
            thermal,
            request,
            output,
            result,
            _reset_idle=lambda current, record: reset_idle(current, lease, record, cleanup),
            start_attempt=start_attempt,
        )
        result["success"] = True
    except BaseException:
        result["error"] = traceback.format_exc()
    finally:
        if lease.acquired:
            cleanup_errors = []

            # Every cleanup step is independent: one failed capture/restore cannot
            # skip force-stop, OLED sleep or the final ownership readback.
            def clean(name, action):
                try:
                    lease.require()
                    return action()
                except BaseException:
                    cleanup_errors.append(name + ": " + traceback.format_exc())

            if device and active_hash:
                try:
                    pid = device.sh("pidof", device.package, check=False).strip()
                    if pid.isdecimal():
                        capture(device, output / "terminal-capture", pid)
                except BaseException:
                    result["capture_error"] = traceback.format_exc()
                    result["success"] = False

            if thermal:

                def finish_thermal():
                    try:
                        thermal.finish()
                    except RuntimeError:
                        if not thermal.error or any(thread and thread.is_alive() for thread in (thermal.thread, thermal.stopper)):
                            raise
                        result["success"] = False

                clean("thermal", finish_thermal)
                result["thermal"] = dict(
                    error=thermal.error,
                    peak_cpu_gpu_celsius=thermal.peak_cpu_gpu_celsius,
                    time_above80_seconds=thermal.time_above_80_seconds,
                    admission_battery=thermal.admission_battery,
                )
            if device and active_hash:

                def stop():
                    verify_owned(device, active_hash)
                    device.sh("am", "force-stop", device.package)
                    return True

                if clean("stop", stop) and initial_exception_bytes is not None:
                    try:
                        end = exception_log_size(device, exception_log)
                        if end < initial_exception_bytes:
                            raise RuntimeError("Cumulative exception log shrank during the session")
                        rows = ""
                        if end > initial_exception_bytes:
                            rows = device.sh("tail", "-c", f"+{initial_exception_bytes + 1}", "--", exception_log)
                        (output / "exceptions.jsonl").write_text(rows + "\n" if rows else "")
                    except BaseException:
                        result["exception_capture_error"] = traceback.format_exc()
                        result["success"] = False
                for remote, previous in restore.items():

                    def restore_file(remote=remote, previous=previous):
                        verify_owned(device, active_hash)
                        if previous is None:
                            remove_device_file(device, remote, cleanup, missing_ok=True)
                        else:
                            local = output / ("restore-" + Path(remote).name)
                            local.write_text(previous)
                            device.cmd("push", str(local), remote)
                            if device.sh("cat", remote).strip() != previous.strip():
                                raise RuntimeError("Restored config differs")

                    clean("restore", restore_file)

                def retain_scratch():
                    if initial_scratch is None:
                        return
                    verify_owned(device, active_hash)
                    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
                    retain_diagnostic_scratch(device, runtime, initial_scratch, output, cleanup)

                clean("diagnostic-scratch", retain_scratch)
                clean("idle-reset", lambda: reset_idle(device, lease, result.setdefault("final_reset", {}), cleanup))
                clean("lab-idle-reset", lambda: reset_other_lab(request, lease, result.setdefault("final_lab_reset", {}), cleanup))

            if device and (active_hash or "install_recovery" in result):

                def terminal():
                    independent = Device(selector=request["serial"], work_root=common.WORK, package=request["package"])
                    try:
                        if active_hash:
                            result["terminal_readback"] = _idle_readback(independent, active_hash)
                        elif not independent.exists():
                            result["terminal_readback"] = dict(installed=False)
                        else:
                            raise RuntimeError("Package appeared without verified ownership after signature recovery")
                        result["storage_final"] = independent.storage()
                    finally:
                        if not independent.display(False):
                            raise RuntimeError("Independent OLED sleep verification failed")
                    result["terminal_readback"]["oled_asleep"] = True

                clean("terminal", terminal)
            elif device:
                clean("sleep", lambda: device.display(False))
            result["cleanup_errors"] = cleanup_errors
            if cleanup_errors or not result.get("terminal_readback"):
                result["success"] = False
            else:
                clean("lease-release", lease.release)
                result["lease_released"] = not lease.acquired
        try:
            _prune(root)
        except BaseException:
            result["prune_error"] = traceback.format_exc()
            result["success"] = False
        result["elapsed_seconds"] = time.monotonic() - started
        set_command_selector(*prior_selectors)
        save(done, result)
        line = "device-session success=" + str(result["success"]) + " WAITING done-file " + str(done)
        status = root / ".local/orchestrator/status" / (request["workstream"] + ".md")
        status.parent.mkdir(parents=True, exist_ok=True)
        with status.open("a") as stream:
            stream.write(line + "\n")
        print(line, flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--device", metavar="SERIAL", help="Select the serial granted to the request's workstream")
    parser.add_argument("--dry-run", action="store_true", help="Validate request, imports and APK bytes without device access")
    parser.add_argument("--detach", action="store_true", help="Start the same tracked runner in a new session; terminal receipt is always written")
    args = parser.parse_args(argv)
    try:
        request = load_request(args.request, args.device)
    except BaseException:
        if args.dry_run or args.detach:
            raise
        # A detached child's validation can fail after dispatch (for example,
        # its input APK disappeared). Publish to the already selected output.
        raw = json.loads(args.request.read_text())
        parent = args.request.resolve().parent
        root = (parent / raw["canonical_root"]).resolve()
        output = (parent / raw["output"]).resolve()
        if not output.is_relative_to(root / "work"):
            raise
        done = output / "terminal.done.json"
        if not done.exists():
            save(done, dict(success=False, lease_released=False, error=traceback.format_exc()))
            print("WAITING done-file " + str(done), flush=True)
        return 1
    if args.dry_run:
        import alpha_stability_batch  # noqa: F401
        import session_sustained_check  # noqa: F401
        import settings_write_interrupt_check  # noqa: F401

        print(json.dumps(dict(smoke=True, device_access=False, mode=request["mode"], apk_sha256=request["apk_sha256"])))
        return 0
    if args.detach:
        output = Path(request["output"])
        output.mkdir(parents=True, exist_ok=True)
        if (output / "job.json").exists() or (output / "terminal.done.json").exists():
            raise RuntimeError("Run already dispatched; consume its terminal receipt")
        command = [sys.executable, str(Path(__file__).resolve()), "--request", str(args.request.resolve())]
        if args.device is not None:
            command.extend(("--device", args.device))
        with (output / "runner.log").open("w") as log:
            job = subprocess.Popen(
                command,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        save(output / "job.json", dict(pid=job.pid, done_file=str(output / "terminal.done.json")))
        print("WAITING done-file " + str(output / "terminal.done.json"))
        return 0

    def interrupted(signum, frame):
        raise RuntimeError("Device runner interrupted by signal " + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return 0 if execute(request)["success"] else 1
    except BaseException:
        done = Path(request["output"]) / "terminal.done.json"
        if not done.exists():
            save(done, dict(success=False, lease_released=False, error=traceback.format_exc()))
            print("WAITING done-file " + str(done), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
