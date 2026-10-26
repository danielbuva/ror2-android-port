"""Current: one detached driver lease for SDK recovery, heap attribution and sustained play.

The caller launches this driver once and waits on its explicit atomic done file.
No detached child owns the lease. Public checks retain their own scoped cleanup;
an independent installed-byte/idle/display readback gates release of this lease.
Independent sampling records all readable zones and peaks. Runtime aborts on
CPU/GPU heat above 95 C for three seconds or battery at or above 43 C or a sampling gap above one second. Each new stage requires cooldown.
"""

import importlib
import json
import os
import re
from pathlib import Path
import shlex
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
# Two retained native snapshots (menus 2/4), plus SDK/session logs and thermal
# traces. This is a capture estimate, not the full Unity build storage floor.
HOST_DIAGNOSTIC_ESTIMATE_BYTES = 1024**3
HOST_CAPTURE_MARGIN_BYTES = 20 * 1024**3


# Read-only sysfs observation, using shell builtins to avoid spawning one cat per
# zone. Android's thermal ABI reports millidegrees Celsius.
CPU_ZONES = 'for z in /sys/class/thermal/thermal_zone*; do read -r t < "$z/type" || continue; case "$t" in cpu*|CPU*) read -r v < "$z/temp" || exit 1; printf "%s\\t%s\\n" "$t" "$v";; esac; done'
ALL_ZONES = (
    "for z in /sys/class/thermal/thermal_zone*; do "
    'read -r t < "$z/type" || { printf "Thermal type read failed: %s\\n" "$z/type" >&2; exit 1; }; '
    'read -r v < "$z/temp" || { printf "%s\\tUNREADABLE\\t%s\\n" "$t" "$z/temp"; continue; }; '
    'printf "%s\\t%s\\t%s\\n" "$t" "$v" "$z/temp"; done'
)
NON_TEMPERATURE_ZONES = {
    "pm8550-bcl-lvl0",
    "pm8550-bcl-lvl1",
    "pm8550-bcl-lvl2",
    "pm8550b-ibat-lvl0",
    "pm8550b-ibat-lvl1",
    "pm8550b-bcl-lvl0",
    "pm8550b-bcl-lvl1",
    "pm8550b-bcl-lvl2",
    "socd",
    "vbat",
}
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


def cooldown_temperatures(text, *, admission=False):
    physical, excluded, cpu = [], [], []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == "UNREADABLE":
            excluded.append(dict(type=fields[0], path=fields[2], reason="Thermal temp read failed/unsupported"))
            continue
        if len(fields) not in (2, 3) or (len(fields) == 3 and (not fields[2].startswith("/") or not fields[2].endswith("/temp"))):
            raise RuntimeError("Malformed all-zone thermal observation")
        name, raw = fields[:2]
        try:
            value = int(raw)
        except ValueError as error:
            raise RuntimeError("Invalid all-zone thermal value") from error
        if name in NON_TEMPERATURE_ZONES:
            excluded.append(dict(type=name, raw=value, reason="Non-temperature battery/current/voltage level"))
            continue
        if admission and value <= -30000:
            exclusion = dict(type=name, raw=value, reason="Unavailable thermal sentinel at or below -30 C")
            if len(fields) == 3:
                exclusion["path"] = fields[2]
            excluded.append(exclusion)
            continue
        if not 0 < value < 150000:
            raise RuntimeError("Unknown/sentinel all-zone thermal value: " + name)
        physical.append(value / 1000)
        if name.lower().startswith("cpu"):
            cpu.append(value / 1000)
    if not cpu:
        raise RuntimeError("No readable CPU thermal zones in cooldown")
    return max(physical), max(cpu), excluded


class ThermalCancelled(RuntimeError):
    """The launch boundary observed the already-latched thermal cancellation."""


def battery_observation(text):
    values = {}
    for name in ("temperature", "level", "status"):
        match = re.search(r"^\s*" + name + r":\s*(\d+)\s*$", text, re.M)
        if not match:
            raise RuntimeError("Missing battery " + name + "; refuse device run")
        values[name] = int(match[1])
    return dict(celsius=values["temperature"] / 10, level=values["level"], status=values["status"])


class _GameThermalOwner:
    """One lightweight observer; the stage is the only heavy job.

    Observe gameplay without pausing or replaying it. Sustained CPU/GPU heat,
    or battery heat abort. Skin heat remains a metric. CPU/GPU/battery/skin
    cooldown before a new stage requires at most 50 C, battery at most 35 C.
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
        self.error = None
        self.peak_cpu_celsius = None
        self.peak_zone_celsius = None
        self.runtime_zones = []
        self.excluded_zones = []
        self.hot_core_zones = {}
        self.phase = "gameplay"
        self.time_above_80_seconds = 0.0
        self.previous_above_80 = False
        self.peak_cpu_gpu_celsius = None
        self.battery = None
        self.admission_battery = None
        self.battery_zone_celsius = None

    def sample(self, all_zones=False):
        before = time.monotonic()
        self.trace.parent.mkdir(parents=True, exist_ok=True)
        observation = dict(utc=common.now(), all_zones=True, admission=all_zones, phase=self.phase)
        try:
            if all_zones:
                text = self.device.cmd("shell", ALL_ZONES, timeout=10)
            else:
                if not self.runtime_zones:
                    raise RuntimeError("Runtime thermal sampling requires admission discovery")
                # One cat reads every admitted readable physical sensor. Reading
                # each unsupported sysfs interface again can itself take seconds.
                command = "cat " + " ".join(shlex.quote(path) for _, path in self.runtime_zones)
                raw = self.device.cmd("shell", command, timeout=0.7)
                observation["runtime_raw"] = raw
                values = raw.splitlines()
                if len(values) != len(self.runtime_zones) or any(len(value.split()) != 1 for value in values):
                    raise RuntimeError("Malformed runtime thermal observation")
                text = "\n".join(name + "\t" + value + "\t" + path for (name, path), value in zip(self.runtime_zones, values))
            self.battery = battery_observation(self.device.sh("dumpsys", "battery", timeout=0.7))
            observation["battery"] = self.battery
            at = time.monotonic()
            gap = at - self.previous if self.previous is not None else at - before
            self.previous = at
            observation["gap_seconds"] = gap
            observation["all_zones_raw"] = text
            maximum, value, excluded = cooldown_temperatures(text, admission=all_zones)
            admission_maximum = maximum
            if all_zones:
                admission_values, admission_excluded = [], []
                for line in text.splitlines():
                    fields = line.split()
                    if fields[1] == "UNREADABLE" or fields[0] in NON_TEMPERATURE_ZONES or int(fields[1]) <= -30000:
                        continue
                    if fields[0].lower().startswith(("cpu", "gpu", "battery", "skin")):
                        admission_values.append(int(fields[1]) / 1000)
                    else:
                        entry = dict(type=fields[0], raw=int(fields[1]), reason="Outside CPU/GPU/battery/skin admission; retained for runtime sampling")
                        if len(fields) == 3:
                            entry["path"] = fields[2]
                        admission_excluded.append(entry)
                admission_maximum = max(admission_values)  # Readable CPU coverage was required above.
                observation.update(admission_maximum_celsius=admission_maximum, admission_excluded_zones=admission_excluded)
                self.runtime_zones = [
                    (fields[0], fields[2])
                    for line in text.splitlines()
                    if len(fields := line.split()) == 3 and fields[1] != "UNREADABLE" and fields[0] not in NON_TEMPERATURE_ZONES and int(fields[1]) > -30000
                ]
                self.excluded_zones = excluded
            else:
                excluded = self.excluded_zones
            batteries = [
                int(line.split()[1]) / 1000
                for line in text.splitlines()
                if line.split()[0].lower().startswith("battery") and line.split()[1] != "UNREADABLE" and int(line.split()[1]) > -30000
            ]
            self.battery_zone_celsius = max(batteries, default=self.battery["celsius"])
            observation.update(maximum_zone_celsius=maximum, excluded_zones=excluded)
            self.peak_zone_celsius = max(maximum, self.peak_zone_celsius or maximum)
            self.peak_cpu_celsius = max(value, self.peak_cpu_celsius or value)
            observation["cpu_celsius"] = value
            processors = [
                int(line.split()[1]) / 1000
                for line in text.splitlines()
                if line.split()[0].lower().startswith(("cpu", "gpu")) and line.split()[1] != "UNREADABLE" and int(line.split()[1]) > -30000
            ]
            processor_peak = max(processors)
            if not all_zones:
                if self.previous_above_80 and gap <= 1:
                    self.time_above_80_seconds += gap
                self.previous_above_80 = processor_peak > 80
                self.peak_cpu_gpu_celsius = max(processor_peak, self.peak_cpu_gpu_celsius or processor_peak)
            observation.update(time_above_80_seconds=self.time_above_80_seconds, peak_cpu_gpu_celsius=self.peak_cpu_gpu_celsius)
        except BaseException as error:
            observation["error"] = str(error)
            raise
        finally:
            with self.trace.open("a") as stream:
                stream.write(json.dumps(observation) + "\n")
        if not all_zones and gap > 1:
            raise RuntimeError("Thermal sample gap exceeded one second")
        if at >= self.deadline:
            raise RuntimeError("Three-hour alpha driver deadline reached")
        if all_zones:
            if self.battery["level"] > 85 or (self.battery["status"] == 2 and self.battery["level"] >= 80):
                raise RuntimeError("Battery charge separation/limit admission refused; report without retry")
            self.hot_core_zones.clear()
            if maximum > 80:
                raise RuntimeError("Readable thermal zone exceeded 80 C hard abort")
        else:
            if self.battery["celsius"] >= 43:
                raise RuntimeError("Battery at or above 43 C")
            for line in text.splitlines():
                name, raw, path = line.split()
                celsius = int(raw) / 1000
                if name.lower().startswith("battery") and celsius >= 43:
                    raise RuntimeError("Battery thermal zone at or above 43 C: " + name)
                if not name.lower().startswith(("cpu", "gpu")):
                    continue
                key = (name, path)
                if celsius <= 95:
                    self.hot_core_zones.pop(key, None)
                    continue
                since, last, count = self.hot_core_zones.get(key, (at, at, 0))
                # Allow only floating-point subtraction noise at the boundaries.
                if at - last > 1 + 1e-9:
                    since, count = at, 0
                count += 1
                self.hot_core_zones[key] = (since, at, count)
                if count >= 3 and at - since >= 3.0 - 1e-9:
                    raise RuntimeError("CPU/GPU thermal zone stayed above 95 C for three seconds: " + name)
        return admission_maximum if all_zones else maximum

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
        while True:
            maximum = self.sample(all_zones=True)
            if maximum <= 50 and max(self.battery["celsius"], self.battery_zone_celsius) <= 35:
                self.admission_battery = self.battery.copy()
                break
            time.sleep(THERMAL_INTERVAL_SECONDS)
        self.previous = None

    def start(self):
        self.sample()

        def observe():
            # Stay alive until the stage has unwound: SDK recovery and an
            # already-running Device.launch may otherwise launch after a stop.
            while not self.sample_stop.wait(THERMAL_INTERVAL_SECONDS):
                try:
                    self.sample()
                except BaseException as error:
                    self.error = self.error or str(error) or type(error).__name__
                if self.error:
                    self.cancelled.set()

        def stop_workload():
            # Package manager/ADB shutdown can be slow. It must never block the
            # independent thermal sampler, including while a launch is in flight.
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
        if self.error:
            raise ThermalCancelled("Thermally cancelled stage cannot launch/recover game")
        launched = device.launch()
        if self.error:
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
            # Keep all-zone sampling alive through this operation, even if the stage
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


def _host_capture_budget(root):
    estimated = 2 * NATIVE_CAPTURE_HEADROOM_BYTES + HOST_DIAGNOSTIC_ESTIMATE_BYTES
    return dict(
        snapshot_count=2,
        estimated_snapshot_bytes=NATIVE_CAPTURE_HEADROOM_BYTES,
        estimated_diagnostic_bytes=HOST_DIAGNOSTIC_ESTIMATE_BYTES,
        estimated_output_bytes=estimated,
        margin_bytes=HOST_CAPTURE_MARGIN_BYTES,
        required_free_bytes=estimated + HOST_CAPTURE_MARGIN_BYTES,
        free_bytes=shutil.disk_usage(root).free,
    )


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
        result["host_capture_budget"] = _host_capture_budget(root)
        budget = result["host_capture_budget"]
        if budget["free_bytes"] < budget["required_free_bytes"]:
            raise RuntimeError("Host free space is below estimated capture output plus 20 GiB margin")
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
        device = _device(serial)
        result["initial_readback"] = _idle_readback(device, expected)
        _require_capture_capacity(device)
        sdk, memory, sustained = _modules()
        progress = done.with_suffix(".progress.json")
        thermal_trace = done.with_suffix(".thermal.jsonl")
        result["thermal_trace"] = str(thermal_trace)
        for name, function, kwargs in (
            ("settings-write-interrupt", sdk.check_settings_write_interrupt, {}),
            ("session-memory", memory.check_session_memory, dict(sessions=3, memory_snapshots=True)),
            ("session-sustained", sustained.check_session_sustained, {}),
        ):
            result["active_stage"] = name
            if name == "session-memory":
                _require_capture_capacity(device)
            thermal = _GameThermalOwner(device, expected, thermal_trace, deadline)
            thermal.phase = name
            stage_error = None
            try:
                thermal.cool()  # No game running; admit the next stage at <=50 C.
                thermal.start()
                try:
                    stage = function(expected_apk_sha256=expected, _launch=thermal.launch, **kwargs)
                except BaseException as error:
                    stage_error = error
                finally:
                    try:
                        thermal.finish()
                    except BaseException as thermal_error:
                        result["thermal_error"] = str(thermal_error) or type(thermal_error).__name__
                        if stage_error:
                            raise stage_error from thermal_error
                        raise
                if stage_error:
                    raise stage_error
                if not isinstance(stage, dict) or stage.get("success") is not True:
                    raise RuntimeError(name + " did not return explicit success")
                result["stages"].append(
                    dict(
                        name=name,
                        result=stage,
                        battery=thermal.battery,
                        admission_battery=thermal.admission_battery,
                        peak_cpu_celsius=thermal.peak_cpu_celsius,
                        peak_zone_celsius=thermal.peak_zone_celsius,
                        time_above_80_seconds=thermal.time_above_80_seconds,
                        peak_cpu_gpu_celsius=thermal.peak_cpu_gpu_celsius,
                    )
                )
            finally:
                result["active_stage_thermal"] = dict(
                    phase=name,
                    battery=thermal.battery,
                    admission_battery=thermal.admission_battery,
                    time_above_80_seconds=thermal.time_above_80_seconds,
                    peak_cpu_gpu_celsius=thermal.peak_cpu_gpu_celsius,
                )
                result["active_stage_peak_zone_celsius"] = thermal.peak_zone_celsius
                zone_peaks = [value for value in (result.get("peak_zone_celsius"), thermal.peak_zone_celsius) if value is not None]
                result["peak_zone_celsius"] = max(zone_peaks) if zone_peaks else None
                result["active_stage_peak_cpu_celsius"] = thermal.peak_cpu_celsius
                peaks = [value for value in (result.get("peak_cpu_celsius"), thermal.peak_cpu_celsius) if value is not None]
                result["peak_cpu_celsius"] = max(peaks) if peaks else None
            common.write(progress, result)  # Completed-stage checkpoint.
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
