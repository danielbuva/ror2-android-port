#!/usr/bin/env python3
"""/lab-only bounded logical-quota acceptance of the installer atomic writer.

No installation, game input, keys, root, mount, or volume-filling operation.
The 64 KiB scratch quota injects ENOSPC after 1 KiB of a partial write; this does
NOT qualify kernel ENOSPC or the full installer UI. Raw subprocess diagnostics
stay in ignored work/. The harness writes less than 128 KiB.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"PASS bounded-quota-enospc-preserves-receipt", "PASS quota-cleanup-and-resume", "PASS abandoned-partial-replaced"}
REMOTE = re.compile(r"/data/local/tmp/ror2-quota\.[A-Za-z0-9]+\Z")
# This conservative short-test envelope is stricter than the existing 70 C
# producer pause and retains the lab's 35 C battery admission limit. Sensor loss always refuses execution.
GUARD = r"""#!/system/bin/sh
safe() {
    capacity=$(cat /sys/class/power_supply/battery/capacity) || return 1
    current=$(cat /sys/class/power_supply/battery/current_now) || return 1
    temperature=$(cat /sys/class/power_supply/battery/temp) || return 1
    case "$capacity:$temperature" in *[!0-9:]*|:*|*:) return 1 ;; esac
    case "$current" in -*) digits=${current#-} ;; *) digits=$current ;; esac
    case "$digits" in ''|*[!0-9]*) return 1 ;; esac
    [ "$capacity" -le 85 ] && [ "$temperature" -gt 0 ] && [ "$temperature" -lt 350 ] || return 1
    if [ "$capacity" -ge 80 ] && [ "$current" -gt 0 ]; then return 1; fi
    cpu=0
    for zone in /sys/class/thermal/thermal_zone*; do
        kind=$(cat "$zone/type" 2>/dev/null) || continue
        case "$kind" in cpu*|CPU*|gpu*|GPU*|battery*|skin*) ;; *) continue ;; esac
        value=$(cat "$zone/temp" 2>/dev/null) || return 1
        case "$value" in ''|*[!0-9]*) return 1 ;; esac
        [ "$value" -gt 0 ] && [ "$value" -le 50000 ] || return 1
        case "$kind" in cpu*|CPU*) cpu=1 ;; battery*) [ "$value" -lt 35000 ] || return 1 ;; esac
    done
    [ "$cpu" -eq 1 ]
}
safe || exit 81
CLASSPATH="$1/classes.dex" app_process /system/bin InstallerQuotaHarness "$1/quota" &
child=$!
# The watcher owns only this freshly spawned child. It also bounds the run to
# ten seconds without depending on the host connection staying alive.
(
    count=0
    while kill -0 "$child" 2>/dev/null; do
        if ! safe || [ "$count" -ge 20 ]; then
            kill -9 "$child" 2>/dev/null
            exit 82
        fi
        count=$((count + 1))
        sleep 0.5
    done
) &
watcher=$!
wait "$child"
result=$?
wait "$watcher"
watch_result=$?
[ "$watch_result" -eq 0 ] || exit 82
[ "$result" -eq 0 ] || exit "$result"
safe || exit 83
"""


class Failure(Exception):
    def __init__(self, label, diagnostic=None):
        super().__init__(label)
        self.diagnostic = diagnostic


LOG_LIMIT = 32768
JAVA_ERRORS = (
    "java.io.IOException",
    "java.lang.AssertionError",
    "java.lang.ClassNotFoundException",
    "java.lang.NoClassDefFoundError",
    "java.lang.IllegalAccessException",
    "java.lang.NoSuchMethodException",
    "java.lang.NoSuchFieldException",
    "java.lang.reflect.InvocationTargetException",
    "android.system.ErrnoException",
)


def java_errors(text):
    return [name for name in JAVA_ERRORS if re.search(r"(?m)(?:^|Caused by: |Exception in thread \"[^\"\n]*\" )" + re.escape(name) + r"(?=[:\s]|$)", text)]


def inspect_quota_failure(selection):
    """Read only fixed log names under the driver's owned evidence directory.

    Historical random run directories have no workflow ID. Selection never
    claims that newest evidence belongs to a particular GitHub Actions run.
    Work itself may be the lab runner's shared-directory symlink; descendants,
    selected run directories and log files must not be symlinks.
    """
    if selection != "newest" and not re.fullmatch(r"run-[A-Za-z0-9_-]{1,80}", selection):
        raise Failure("invalid-diagnostic-selection")
    descriptors = []
    try:
        directory = os.open((ROOT / "work").resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in ("coordination", "installer-quota"):
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        if selection == "newest":
            candidates = []
            with os.scandir(directory) as entries:
                for count, entry in enumerate(entries):
                    if count >= 256:
                        raise Failure("diagnostic-candidate-limit")
                    if re.fullmatch(r"run-[A-Za-z0-9_-]{1,80}", entry.name) and entry.is_dir(follow_symlinks=False):
                        candidates.append((entry.stat(follow_symlinks=False).st_mtime_ns, entry.name))
            if not candidates:
                raise Failure("diagnostic-evidence-unavailable")
            selected = max(candidates)[1]
        else:
            selected = selection
        directory = os.open(selected, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        descriptors.append(directory)
        raw, truncated = [], False
        for name in ("phone-quota.stdout", "phone-quota.stderr"):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise Failure("diagnostic-log-not-regular")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    value = stream.read(LOG_LIMIT + 1)
                truncated |= len(value) > LOG_LIMIT
                raw.append(value[:LOG_LIMIT].decode("utf-8", errors="replace"))
            finally:
                os.close(descriptor)
        return {
            "mode": "inspect-quota-failure",
            "selection": "newest" if selection == "newest" else "explicit",
            "workflow_association": "unrecorded",
            "status": "observed",
            "returncode": None,
            "returncode_status": "not-inferred-from-output",
            "java_errors": java_errors("\n".join(raw)),
            "stdout_empty": not raw[0],
            "stderr_empty": not raw[1],
            "logs_truncated": truncated,
        }
    except (OSError, RuntimeError) as error:
        raise Failure("diagnostic-evidence-unavailable-or-unsafe") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def record_command(logs, label, *, stdout=b"", stderr=b"", returncode=None, status="exited"):
    """Retain bounded raw evidence locally; expose only fixed classifications.

    /lab links checkout/work to the persistent repository work directory, so
    these records survive removal of the temporary checkout. Never print raw
    command output, command arguments, exception messages or filesystem paths.
    """
    raw = []
    truncated = False
    for kind, value in (("stdout", stdout), ("stderr", stderr)):
        value = value or b""
        if isinstance(value, str):
            value = value.encode("utf-8", errors="replace")
        truncated |= len(value) > LOG_LIMIT
        value = value[:LOG_LIMIT]
        (logs / (label + "." + kind)).write_bytes(value)
        raw.append(value.decode("utf-8", errors="replace"))
    category = status
    signal_name = None
    if returncode is not None and returncode < 0:
        category = "host-command-signal"
        try:
            signal_name = signal.Signals(-returncode).name
        except ValueError:
            signal_name = "unknown"
    elif label == "phone-quota":
        category = {81: "guard-initial-refusal", 82: "guard-watchdog-refusal", 83: "guard-final-refusal"}.get(returncode, status)
    text = "\n".join(raw)
    errors = java_errors(text)
    diagnostic = {"category": category, "returncode": returncode, "signal": signal_name, "java_errors": errors, "logs_truncated": truncated}
    (logs / (label + ".result.json")).write_text(json.dumps(diagnostic, sort_keys=True) + "\n")
    return diagnostic


def run(argv, logs, label, *, timeout=60):
    try:
        result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        diagnostic = record_command(logs, label, stdout=error.stdout, stderr=error.stderr, status="host-command-timeout")
        raise Failure(label, diagnostic) from error
    except OSError as error:
        diagnostic = record_command(logs, label, status="host-command-launch-error")
        raise Failure(label, diagnostic) from error
    diagnostic = record_command(logs, label, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
    if result.returncode:
        raise Failure(label, diagnostic)
    return result.stdout


def safety(adb, logs, phase):
    # Use the lab's existing battery policy instead of defining another one.
    spec = importlib.util.spec_from_file_location("quota_lab_runner", ROOT / "scripts/lab/lab_runner.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    raw = run([*adb, "shell", "dumpsys", "battery"], logs, phase + "-battery").decode()
    values = {k.strip(): v.strip() for k, v in re.findall(r"^\s*([^:\n]+):\s*([^\n]*)", raw, re.M)}
    try:
        level, temperature = int(values["level"]), int(values["temperature"])
        current = int(run([*adb, "shell", "cat", "/sys/class/power_supply/battery/current_now"], logs, phase + "-current").decode())
    except (KeyError, ValueError) as error:
        raise Failure("battery-telemetry-unavailable") from error
    if not 0 <= level <= 100 or not 0 < temperature < 1000 or runner.battery_refusal(level, current, temperature):
        raise Failure("battery-admission-refused")
    space = run([*adb, "shell", "df", "-k", "/data/local/tmp"], logs, phase + "-storage").decode().splitlines()
    try:
        free = int(space[-1].split()[-3]) * 1024
    except (IndexError, ValueError) as error:
        raise Failure("scratch-backing-unavailable") from error
    if free < 15 * 1024**3:
        raise Failure("scratch-backing-reserve")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-only", action="store_true", help="Compile/run the identical Java fixture without contacting a phone")
    parser.add_argument("--inspect-quota-failure", action="store_true", help="Read retained quota logs only; no subprocesses, compiler or device access")
    parser.add_argument(
        "--diagnostic-run", default="newest", help="Newest retained directory or exact run-* basename; historical workflow association is unrecorded"
    )
    args = parser.parse_args(argv)
    if args.inspect_quota_failure:
        if args.host_only:
            print("FAIL incompatible-diagnostic-mode")
            return 1
        try:
            print(json.dumps(inspect_quota_failure(args.diagnostic_run), sort_keys=True))
            return 0
        except Failure as error:
            print("FAIL " + str(error))
            return 1
    serial = os.environ.get("LAB_DEVICE_SERIAL")
    if not args.host_only and not serial:
        print("FAIL LAB_DEVICE_SERIAL-required-use-authorized-lab-runner")
        return 1
    java_home = Path(os.environ.get("JAVA_HOME", "/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK"))
    sdk = Path(os.environ.get("ANDROID_SDK_ROOT", "/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/SDK"))
    adb = ["/opt/homebrew/bin/adb", "-s", serial] if serial else []
    evidence = ROOT / "work/coordination/installer-quota"
    evidence.mkdir(parents=True, exist_ok=True)
    logs = Path(tempfile.mkdtemp(prefix="run-", dir=evidence))
    remote, failure, cleanup_failure, diagnostic = None, None, False, None
    try:
        with tempfile.TemporaryDirectory(prefix="ror2-quota-", dir="/tmp") as temporary:
            temporary = Path(temporary).resolve()
            classes = temporary / "classes"
            classes.mkdir()
            run(
                [
                    java_home / "bin/javac",
                    "-source",
                    "8",
                    "-target",
                    "8",
                    "-d",
                    classes,
                    ROOT / "tools/phone-build/managed-host/OwnerInputImport.java",
                    ROOT / "tests/fixtures/InstallerQuotaHarness.java",
                ],
                logs,
                "compile",
            )
            if args.host_only:
                output = run([java_home / "bin/java", "-cp", classes, "InstallerQuotaHarness", temporary / "quota"], logs, "host-quota")
            else:
                version = json.loads((ROOT / "environment/toolchain.json").read_text())["android_build_tools"]
                dex = temporary / "dex"
                dex.mkdir()
                run(
                    [
                        sdk / "build-tools" / version / "d8",
                        "--min-api",
                        "24",
                        "--lib",
                        sdk / "platforms/android-33/android.jar",
                        "--output",
                        dex,
                        *sorted(classes.rglob("*.class")),
                    ],
                    logs,
                    "dex",
                )
                if (dex / "classes.dex").stat().st_size > 1024**2:
                    raise Failure("fixture-dex-size-limit")
                safety(adb, logs, "before")
                value = run([*adb, "shell", "mktemp", "-d", "/data/local/tmp/ror2-quota.XXXXXXXX"], logs, "scratch-create").decode().strip()
                if not REMOTE.fullmatch(value):
                    raise Failure("scratch-ownership-unconfirmed")
                remote = value
                guard = temporary / "guard.sh"
                guard.write_text(GUARD)
                run([*adb, "push", dex / "classes.dex", remote + "/classes.dex"], logs, "push-dex")
                run([*adb, "push", guard, remote + "/guard.sh"], logs, "push-guard")
                output = run([*adb, "shell", "sh", remote + "/guard.sh", remote], logs, "phone-quota", timeout=30)
                safety(adb, logs, "after")
            if set(output.decode().splitlines()) != EXPECTED:
                raise Failure("quota-contract-result")
    except Failure as error:
        failure = str(error)
        diagnostic = error.diagnostic
    except Exception:
        failure = "unexpected-local-error-see-private-evidence"
    finally:
        if remote:
            try:
                run([*adb, "shell", "rm", "-rf", remote], logs, "scratch-cleanup")
                run([*adb, "shell", "test", "!", "-e", remote], logs, "scratch-absence")
            except Failure:
                cleanup_failure = True
        if adb:
            try:
                run([*adb, "shell", "input", "keyevent", "KEYCODE_SLEEP"], logs, "display-sleep")
            except Failure:
                cleanup_failure = True
    if failure or cleanup_failure:
        print("FAIL " + (failure or "cleanup-or-display-unconfirmed"))
        if diagnostic:
            print("DIAGNOSTIC " + json.dumps(diagnostic, sort_keys=True))
        if cleanup_failure and failure:
            print("FAIL cleanup-or-display-unconfirmed")
        return 1
    for line in sorted(EXPECTED):
        print(line + (" (host only; phone NOT RUN)" if args.host_only else " (phone logical-quota injection)"))
    print("NOT QUALIFIED physical-filesystem-ENOSPC or full-installer-UI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
