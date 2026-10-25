"""Current: one detached driver lease for SDK recovery, heap attribution and sustained play.

The caller launches this driver once and waits on its explicit atomic done file.
No detached child owns the lease. Public checks retain their own scoped cleanup;
an independent installed-byte/idle/display readback gates release of this lease.
CPU thermal pauses terminate the current game attempt and replay that entire
stage after cooldown. Interrupted observations are preserved, never combined
with the replacement attempt or counted toward continuous sustained play.
"""

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

import common
from device_context import command_selectors, set_command_selector, validate_serial
from installed_attempt import bind_installed_apk, validate_expected_apk_sha256


DEVICE_FREE_RESERVE_BYTES = 15 * 1024**3
# J1091's native capture sizes inform this allowance. Only one capture remains
# on the device at a time; its verified host transfer removes the device file.
NATIVE_CAPTURE_HEADROOM_BYTES = 4 * 1024**3


# Read-only sysfs observation, using shell builtins to avoid spawning one cat per
# zone. Android's thermal ABI reports millidegrees Celsius.
CPU_ZONES = 'for z in /sys/class/thermal/thermal_zone*; do read -r t < "$z/type" || continue; case "$t" in cpu*|CPU*) read -r v < "$z/temp" || exit 1; printf "%s\\t%s\\n" "$t" "$v";; esac; done'
THERMAL_INTERVAL_SECONDS = 0.25
BATCH_DEADLINE_SECONDS = 3 * 60 * 60


def cpu_temperature(text):
    values = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 2 or not fields[0].lower().startswith("cpu"):
            raise RuntimeError("Malformed CPU thermal observation")
        try:
            value = int(fields[1]) / 1000
        except ValueError as error:
            raise RuntimeError("Invalid CPU thermal value") from error
        if not 0 < value < 150:
            raise RuntimeError("Unknown/sentinel CPU thermal value")
        values.append(value)
    if not values:
        raise RuntimeError("No readable CPU thermal zones")
    return max(values)


class ThermalCancelled(RuntimeError):
    """The launch boundary observed the already-latched thermal cancellation."""


class _GameThermalOwner:
    """One lightweight observer; the stage is the only heavy job.

    At 70 C terminate the owned game, let its existing owner clean up, then
    restart the *whole* stage after 55 C. No process suspension, simulated native
    pause, merged memory samples or cooldown time presented as gameplay.
    """

    def __init__(self, device, expected, trace, deadline):
        self.device, self.expected, self.trace, self.deadline = device, expected, trace, deadline
        self.stop = threading.Event()
        self.sample_stop = threading.Event()
        self.thread = None
        self.stopper = None
        self.cancelled = threading.Event()
        self.stop_lock = threading.Lock()
        self.previous = None
        self.outcome = None
        self.error = None

    def sample(self):
        before = time.monotonic()
        text = self.device.cmd("shell", CPU_ZONES, timeout=0.7)
        at = time.monotonic()
        gap = at - self.previous if self.previous is not None else at - before
        self.previous = at
        value = cpu_temperature(text)
        self.trace.parent.mkdir(parents=True, exist_ok=True)
        with self.trace.open("a") as stream:
            stream.write(json.dumps(dict(utc=common.now(), cpu_celsius=value, gap_seconds=gap)) + "\n")
        if gap > 1:
            raise RuntimeError("CPU thermal sample gap exceeded one second")
        if at >= self.deadline:
            raise RuntimeError("Three-hour alpha driver deadline reached")
        if value > 80:
            raise RuntimeError("CPU exceeded 80 C hard abort")
        return value

    def terminate_game(self):
        from device import PACKAGE

        # Receipt and live PID/cmdline are revalidated immediately before the
        # package-scoped stop. No remembered PID or unbound process is signaled.
        receipt = self.device.read_receipt("installed.json")
        bind_installed_apk(receipt, expected_sha256=self.expected)
        if receipt.get("serial") != self.device.serial or receipt.get("package") != PACKAGE:
            raise RuntimeError("Selected package ownership changed; refuse thermal stop")
        if self.device.cmd("shell", "pm path " + PACKAGE, timeout=0.7) != receipt.get("package_path"):
            raise RuntimeError("Package placement changed; refuse thermal stop")
        pid = self.device.cmd("shell", "pidof " + PACKAGE, check=False, timeout=0.7).strip()
        if not pid:
            return
        if not pid.isdecimal():
            raise RuntimeError("Ambiguous game PID; refuse thermal stop")
        identity = self.device.cmd("shell", "cat /proc/" + pid + "/cmdline; echo; pidof " + PACKAGE, timeout=0.7)
        fields = identity.splitlines()
        if len(fields) != 2 or fields[0].rstrip("\x00") != PACKAGE or fields[1] != pid:
            raise RuntimeError("Game identity changed; refuse late thermal stop")
        self.device.cmd("shell", "am force-stop " + PACKAGE, timeout=2)

    def cool(self):
        if not self.device.display(False):
            raise RuntimeError("Thermal cooldown requires verified OLED sleep")
        self.previous = None  # No heavy job during display/idle setup.
        while self.sample() > 55:
            time.sleep(THERMAL_INTERVAL_SECONDS)
        self.previous = None

    def start(self):
        if self.sample() >= 70:
            raise RuntimeError("CPU thermal admission requires cooldown before workload")

        def observe():
            # Stay alive until the stage has unwound: SDK recovery and an
            # already-running Device.launch may otherwise launch after a stop.
            while not self.sample_stop.wait(THERMAL_INTERVAL_SECONDS):
                try:
                    if self.sample() >= 70:
                        self.outcome = "interrupted-at-70C"
                except BaseException as error:
                    self.error = self.error or str(error) or type(error).__name__
                if self.outcome or self.error:
                    self.cancelled.set()

        def stop_workload():
            # Package manager/ADB shutdown can be slow. It must never block the
            # independent CPU sampler, including while a launch is in flight.
            while not self.stop.is_set():
                if not self.cancelled.wait(THERMAL_INTERVAL_SECONDS):
                    continue
                try:
                    self._terminate_serially()
                except BaseException as error:
                    self.error = self.error or "Thermal stop failed: " + str(error)
                self.stop.wait(THERMAL_INTERVAL_SECONDS)

        self.thread = threading.Thread(target=observe, name="alpha-cpu-thermal")
        self.stopper = threading.Thread(target=stop_workload, name="alpha-thermal-stop")
        self.thread.start()
        self.stopper.start()

    def _terminate_serially(self):
        with self.stop_lock:
            self.terminate_game()

    def launch(self, device):
        if self.outcome or self.error:
            raise ThermalCancelled("Thermally cancelled stage cannot launch/recover game")
        launched = device.launch()
        if self.outcome or self.error:
            self._terminate_serially()
            raise ThermalCancelled("Game launch crossed thermal cancellation")
        return launched

    def finish(self):
        self.stop.set()
        try:
            if self.stopper:
                self.stopper.join(timeout=6)
                if self.stopper.is_alive():
                    raise RuntimeError("Thermal stop worker failed to terminate")
            # The stage has unwound; no launch can race this final bounded stop.
            # Keep CPU sampling alive through this operation, even if the stage
            # reported successful cleanup while a thermal shutdown was in flight.
            self._terminate_serially()
        finally:
            self.sample_stop.set()
            if self.thread:
                self.thread.join(timeout=2)
                if self.thread.is_alive():
                    raise RuntimeError("CPU thermal observer failed to terminate")
        if self.error:
            raise RuntimeError(self.error)
        return self.outcome


def _modules():
    # WORK must be selected before importing any owner that captures it.
    return tuple(importlib.import_module(name) for name in ("settings_write_interrupt_check", "session_memory_check", "session_sustained_check"))


def _device(serial):
    from device import Device

    return Device(selector=serial, work_root=common.WORK)


def _idle_readback(device, expected):
    """Read actual package bytes independently of the receipt's claimed digest."""
    from device import PACKAGE
    from session_cleanup_check import _remote_path_state

    installed = device.owned()
    bind_installed_apk(installed, expected_sha256=expected)
    package_path = installed["package_path"]
    if not package_path.startswith("package:") or "\n" in package_path:
        raise RuntimeError("Expected one installed base APK path")
    actual = device.sh("sha256sum", package_path.removeprefix("package:")).split()
    if not actual or actual[0] != expected:
        raise RuntimeError("Actual installed APK bytes differ")
    runtime = device.read_receipt("runtime.json")["persistentDataPath"]
    process = device.sh("pidof", PACKAGE, check=False).strip()
    selector = _remote_path_state(device, runtime + "/movement-batch-selection.json")
    pending = _remote_path_state(device, runtime + "/offline-settings-v1/preferences.json.pending")
    if process or selector != "absent" or pending != "absent":
        raise RuntimeError("Requires idle package with absent selector/pending state; preserved existing state")
    return dict(apk_sha256=actual[0], process_absent=True, selector_absent=True, pending_absent=True)


def _terminal_readback(serial, expected):
    device = _device(serial)  # Independent context; never trust a stage's result.
    try:
        proof = _idle_readback(device, expected)
    finally:
        if not device.display(False):
            raise RuntimeError("Independent OLED sleep verification failed")
    proof["oled_asleep"] = True
    return proof


def _sleep_awakened():
    from device import Device

    errors = Device.sleep_awakened()
    if errors:
        raise RuntimeError("Awakened-display cleanup failed: " + "; ".join(errors))


def _prune(root):
    result = subprocess.run(
        [sys.executable, str(root / "scripts/prune-generated.py"), "--apply", "--work-dir", str(root / "work")], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError("Canonical generated-output pruning failed: " + result.stderr[-1000:])


def _require_capture_capacity(device):
    storage = device.storage()
    selected = storage["internal"] if storage["mode"] == "internal" else storage["adopted"]
    if selected["free_bytes"] < DEVICE_FREE_RESERVE_BYTES + NATIVE_CAPTURE_HEADROOM_BYTES:
        raise RuntimeError("Native heap capture requires 4 GiB headroom above the retained 15 GiB device free-space reserve")


def check_alpha_stability_batch(*, device_serial, expected_apk_sha256, canonical_root, done_file):
    """Run fixed stages synchronously; publish terminal status on success or failure."""
    root = Path(canonical_root).expanduser().resolve()
    if not (root / ".git").is_dir():
        raise ValueError("canonical_root must be the primary Git checkout")
    work = root / "work"
    done = Path(done_file).expanduser()
    if not done.is_absolute() or done != done.resolve() or not done.is_relative_to(work) or done.exists():
        raise ValueError("Use a new absolute --done-file under canonical ignored work/")
    result = dict(success=False, driver_pid=os.getpid(), stages=[], lease_released=False)
    token = uuid.uuid4().hex
    owner = dict(
        workstream="alpha-stability-batch",
        pid=os.getpid(),
        started=common.now(),
        purpose="SDK recovery, three-session native heaps, thirty-minute assisted sustained case",
        token=token,
    )
    acquired = False
    deadline = time.monotonic() + BATCH_DEADLINE_SECONDS
    previous_work = common.WORK
    previous_selectors = command_selectors()
    try:
        # Once the output path is trusted, even invalid command identity must
        # publish a terminal receipt for the detached caller waiting on it.
        serial = validate_serial(device_serial)
        expected = validate_expected_apk_sha256(expected_apk_sha256)
        if expected is None:
            raise ValueError("alpha-stability-batch requires --expected-apk-sha256")
        result["apk_sha256"] = expected
        lease = root / ".local/orchestrator/leases" / serial
        lease.parent.mkdir(parents=True, exist_ok=True)
        if lease.parent.resolve() != lease.parent:
            raise RuntimeError("Canonical lease parent cannot be a symlink")
        try:
            lease.mkdir()  # Atomic refusal; do not inspect/reap/replace another owner.
        except FileExistsError as error:
            raise RuntimeError("Selected device lease is busy; no ADB access attempted") from error
        acquired = True
        common.write(lease / "owner.json", owner)
        common.WORK = work  # Explicit canonical local-state selection before Device/import.
        if previous_selectors[1] not in (None, serial):
            raise ValueError("LAB_DEVICE conflicts with explicit batch serial")
        set_command_selector(serial, previous_selectors[1])
        if shutil.disk_usage(root).free < 100 * 1024**3:
            raise RuntimeError("At least 100 GiB host free space is required before native heap capture")
        device = _device(serial)
        result["initial_readback"] = _idle_readback(device, expected)
        _require_capture_capacity(device)
        sdk, memory, sustained = _modules()
        progress = done.with_suffix(".progress.json")
        thermal_trace = done.with_suffix(".thermal.jsonl")
        result["thermal_trace"] = str(thermal_trace)
        result["interrupted_attempts"] = []
        for name, function, kwargs in (
            ("settings-write-interrupt", sdk.check_settings_write_interrupt, {}),
            ("session-memory", memory.check_session_memory, dict(sessions=3, memory_snapshots=True)),
            ("session-sustained", sustained.check_session_sustained, {}),
        ):
            result["active_stage"] = name
            while True:
                if name == "session-memory":
                    _require_capture_capacity(device)
                thermal = _GameThermalOwner(device, expected, thermal_trace, deadline)
                thermal.cool()  # Initial/retry admission <=55 C; no game running.
                stage = None
                stage_error = None
                thermal.start()
                try:
                    stage = function(expected_apk_sha256=expected, _launch=thermal.launch, **kwargs)
                except BaseException as error:
                    stage_error = error
                finally:
                    try:
                        interruption = thermal.finish()
                    except BaseException as thermal_error:
                        result["thermal_error"] = str(thermal_error) or type(thermal_error).__name__
                        if stage_error:
                            raise stage_error from thermal_error
                        raise
                if interruption:
                    # Preserve first-failure authority. A coincident thermal trip
                    # never converts native/runtime/unknown failure into a retry.
                    # Existing owners with generic failure wrappers fail closed.
                    if stage_error and not isinstance(stage_error, ThermalCancelled):
                        raise stage_error
                    result["interrupted_attempts"].append(dict(name=name, reason=interruption, error=str(stage_error) if stage_error else None, result=stage))
                    # Existing owners must remove their own selector and pending
                    # state. Preserve any interrupted write; never erase to retry.
                    result["retry_idle_readback"] = _idle_readback(device, expected)
                    common.write(progress, result)
                    continue
                if stage_error:
                    raise stage_error
                if not isinstance(stage, dict) or stage.get("success") is not True:
                    raise RuntimeError(name + " did not return explicit success")
                result["stages"].append(dict(name=name, result=stage))
                common.write(progress, result)  # Completed-stage checkpoint.
                break
        result["success"] = True
    except BaseException as error:
        result["error"] = str(error) or type(error).__name__
        result["success"] = False
    finally:
        if acquired:
            try:
                _sleep_awakened()
            except BaseException as error:
                result["display_cleanup_error"] = str(error)
                result["success"] = False
            try:
                result["terminal_readback"] = _terminal_readback(serial, expected)
            except BaseException as error:
                result["terminal_error"] = str(error)
                result["success"] = False
            try:
                _prune(root)
                result["pruned"] = True
            except BaseException as error:
                result["prune_error"] = str(error)
                result["success"] = False
            if "terminal_readback" in result:
                try:
                    if common.read(lease / "owner.json") != owner:
                        raise RuntimeError("Lease owner changed; preserve it")
                    (lease / "owner.json").unlink()
                    lease.rmdir()
                    result["lease_released"] = True
                except BaseException as error:
                    result["lease_error"] = str(error)
                    result["success"] = False
        common.WORK = previous_work
        set_command_selector(*previous_selectors)
        result["finished"] = common.now()
        common.write(done, result)  # Atomic publication only after cleanup/prune/release decision.
    if not result["success"]:
        raise RuntimeError("Alpha stability batch failed; inspect " + str(done))
    return result
