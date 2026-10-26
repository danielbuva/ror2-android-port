"""On-device producer supervision; usable by the app host and shell tooling.

No adb or package ownership operations. The caller owns admission, storage,
lease and display cleanup. Sensors are kernel millidegree observations.
"""

import argparse
import errno
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


class ThermalDutyCycle:
    def __init__(self, profile="nova"):
        self.high, self.low = {"nova": (70, 55), "thor": (75, 60)}[profile]
        self.paused = False
        self.since = None
        self.pause_seconds = 0.0
        self.pauses = 0
        self.last = None
        self.hot_since = {}
        self.peak = 0
        self.time_above_80_seconds = 0.0
        self.previous_above_80 = False
        self.peak_phase = None

    def observe(self, zones, now, admission=False):
        if self.last is not None and now - self.last > 1:
            raise RuntimeError("thermal sample gap above 1 s")
        gap = now - self.last if self.last is not None else 0
        self.last = now
        processors = [v for kind, v in zones.values() if kind in ("cpu", "gpu")]
        if not processors or not any(kind == "cpu" for kind, _ in zones.values()):
            raise RuntimeError("CPU telemetry unavailable")
        phase = "admission" if admission else "paused" if self.paused else "production"
        if max(processors) > self.peak:
            self.peak, self.peak_phase = max(processors), phase
        if not admission:
            if self.previous_above_80:
                self.time_above_80_seconds += gap
            self.previous_above_80 = max(processors) > 80
        for name, (kind, value) in zones.items():
            if not math.isfinite(value) or not 0 < value < 150:
                raise RuntimeError("invalid thermal value: " + name)
            if admission and value > 50:
                raise RuntimeError("thermal admission above 50 C")
            if kind == "battery" and not admission and value > 46:
                raise RuntimeError("battery above 46 C")
            if kind in ("cpu", "gpu"):
                if value > 95:
                    self.hot_since.setdefault(name, now)
                    if now - self.hot_since[name] >= 3:
                        raise RuntimeError("CPU/GPU above 95 C for 3 s")
                else:
                    self.hot_since.pop(name, None)
        if not self.paused and max(processors) >= self.high:
            self.paused, self.since = True, now
            self.pauses += 1
            return signal.SIGSTOP
        if self.paused and max(processors) <= self.low:
            self.pause_seconds += now - self.since
            self.paused, self.since = False, None
            return signal.SIGCONT
        return None

    def receipt(self, now):
        return dict(
            pause_celsius=self.high,
            resume_celsius=self.low,
            pauses=self.pauses,
            pause_seconds=self.pause_seconds + (now - self.since if self.paused else 0),
            peak_cpu_gpu_celsius=self.peak,
            peak_phase=self.peak_phase,
            time_above_80_seconds=self.time_above_80_seconds,
        )


def read_zones(root=Path("/sys/class/thermal")):
    zones = {}
    for path in root.glob("thermal_zone*"):
        name = (path / "type").read_text().strip().lower()
        kind = next((k for k in ("cpu", "gpu", "battery", "skin") if name.startswith(k)), None)
        if kind is None:
            continue  # PMIC and other unrelated zones are not CPU sensors.
        try:
            value = int((path / "temp").read_text()) / 1000
        except OSError as error:
            if error.errno == errno.EINVAL:
                continue
            raise
        if value <= -30:
            continue  # Kernel unavailable sentinel.
        zones[path.name] = (kind, value)
    return zones


def efficiency_cpus(root=Path("/sys/devices/system/cpu")):
    allowed = os.sched_getaffinity(0)
    capacities = {}
    for cpu in allowed:
        try:
            capacities[cpu] = int((root / f"cpu{cpu}/cpu_capacity").read_text())
        except OSError:
            return {min(allowed)}  # Existing CPU-0-style startup restraint.
    minimum = min(capacities.values())
    return set(sorted(cpu for cpu in allowed if capacities[cpu] == minimum)[:2])


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[1]), int(fields[19])  # parent, immutable start ticks
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


class Family:
    """Also stop codec/compiler children which create their own sessions."""

    def __init__(self, child):
        self.child = child
        self.members = {child.pid: identity(child.pid)}

    def discover(self):
        rows = {int(p.name): identity(int(p.name)) for p in Path("/proc").iterdir() if p.name.isdigit()}
        while True:
            added = {
                pid: row
                for pid, row in rows.items()
                if row and row[0] in self.members and rows.get(row[0]) and rows[row[0]][1] == self.members[row[0]][1] and pid not in self.members
            }
            if not added:
                break
            self.members.update(added)

    def send(self, number):
        self.discover()
        # Root is a new session leader and remains unreaped while supervised.
        if self.child.returncode is None:
            try:
                os.killpg(self.child.pid, number)
            except ProcessLookupError:
                pass
        for pid, recorded in list(self.members.items()):
            current = identity(pid)
            if recorded is not None and current is not None and current[1] == recorded[1]:
                try:
                    os.kill(pid, number)
                except ProcessLookupError:
                    pass
        if number == signal.SIGSTOP:
            # Parents are now stopped; capture children forked during discovery.
            previous = set(self.members)
            self.discover()
            for pid in set(self.members) - previous:
                current = identity(pid)
                if current is not None and current[1] == self.members[pid][1]:
                    os.kill(pid, number)


def boot_clock():
    return time.clock_gettime(getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC))


def run(command, receipt, *, profile="nova", timeout=86400, sensor=read_zones, clock=boot_clock, wait=time.sleep, cancelled=lambda: False):
    policy = ThermalDutyCycle(profile)
    started = clock()
    child = family = None
    result = dict(success=False, workers=2)
    pause_clock = Path(str(receipt) + ".pause.json")

    def write_clock():
        # Same clock and wire contract as owner-code/native.py::wait_active.
        value = dict(paused_seconds=policy.pause_seconds, paused_at=policy.since)
        temporary = pause_clock.with_suffix(".tmp")
        temporary.write_text(json.dumps(value) + "\n")
        temporary.replace(pause_clock)

    try:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("positive finite wall deadline required")
        if cancelled():
            raise InterruptedError("producer cancelled")
        policy.observe(sensor(), clock(), admission=True)
        write_clock()
        cpus = efficiency_cpus()
        result["affinity_cpus"] = sorted(cpus)
        env = dict(os.environ)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "DOTNET_PROCESSOR_COUNT"):
            env[name] = "2"
        env["ROR2LAB_BUILD_PAUSE_CLOCK"] = str(pause_clock.resolve())
        # Android Toybox versions without -c still accept a hexadecimal CPU mask.
        # Apply before interpreter/compiler startup; failure refuses.
        child = subprocess.Popen(["/system/bin/taskset", format(sum(1 << cpu for cpu in cpus), "x"), *command], env=env, start_new_session=True)
        family = Family(child)
        while True:
            tick = clock()
            if cancelled():
                raise InterruptedError("producer cancelled")
            if tick - started > timeout:
                raise TimeoutError("producer wall deadline")
            action = policy.observe(sensor(), tick)
            if clock() - tick > 1:
                raise RuntimeError("thermal sensor read above 1 s")
            family.discover()
            if action is not None:
                write_clock()
                family.send(action)
            # Refresh STOP for independently sessioned descendants while paused.
            elif policy.paused:
                family.send(signal.SIGSTOP)
            if child.poll() is not None:
                result["returncode"] = child.returncode
                if child.returncode:
                    raise RuntimeError("producer exit " + str(child.returncode))
                result["success"] = True
                break
            wait(max(0, 0.25 - (clock() - tick)))
    except BaseException as error:
        result["error"] = str(error) or type(error).__name__
    finally:
        if family is not None:
            # SIGKILL works on stopped processes; do not resume production on abort.
            try:
                family.send(signal.SIGKILL)
                child.wait(timeout=5)
            except BaseException as error:
                result.update(success=False, cleanup_error=str(error))
        result.update(policy.receipt(clock()), seconds=clock() - started)
        Path(receipt).write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("nova", "thor"), default="nova")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout", type=float, default=86400)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("producer command required")
    stopped = []
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, lambda number, frame: stopped.append(number))
    return 0 if run(command, args.receipt, profile=args.profile, timeout=args.timeout, clock=boot_clock, cancelled=lambda: bool(stopped))["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
