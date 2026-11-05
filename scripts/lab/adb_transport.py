"""Bounded, explicitly targeted ADB transport; no device discovery or ownership grants.

Callers own authorization, storage admission, package identity and cleanup. A lost
host process is not evidence that a remote mutation failed. Only explicitly
idempotent commands may be retried, and only after a negative POSIX return code.
"""

import re
import secrets
import shlex
import subprocess
import time
from pathlib import Path


class AdbError(RuntimeError):
    """Fixed reason only: never expose argv, device identifiers or raw output."""


class InstallUncertain(AdbError):
    pass


class DetachedUncertain(AdbError):
    def __init__(self, job):
        super().__init__("adb-detached-outcome-unknown")
        self.job = job  # private handle, deliberately absent from exception text


class DetachedJob:
    def __init__(self, directory):
        if not re.fullmatch(r"/data/local/tmp/ror2-adb-job-[0-9a-f]{32}", directory):
            raise ValueError("adb-detached-job-path")
        self.directory = directory


class AdbTransport:
    def __init__(self, adb, serial, *, observer=None, attempts=3, retry_delay=0.1):
        if not serial or not str(serial).strip():
            raise ValueError("adb-explicit-device-required")
        if not 1 <= attempts <= 5 or not 0 <= retry_delay <= 5:
            raise ValueError("adb-retry-policy")
        self.adb, self.serial = str(adb), str(serial)
        self.observer = observer
        self.attempts, self.retry_delay = attempts, retry_delay

    def record(self, label, *, stdout=b"", stderr=b"", returncode=None, outcome="returned"):
        if self.observer:
            self.observer(label, stdout=stdout, stderr=stderr, returncode=returncode, outcome=outcome)

    def execute(self, *args, label, stdin=None, timeout=60, idempotent=False):
        """Return remote status; timeout is a total budget across signal retries.

        Positive shell exit codes (including 128+signal), connection failures and
        timeouts are not retried. An install must go through install(), never a
        shell/exec-in shortcut (exec-in does not propagate remote exit status).
        """
        if not args or timeout <= 0:
            raise ValueError("adb-command-budget")
        if args[0] == "exec-in":
            raise ValueError("adb-exec-in-status-unavailable")
        if idempotent and args[0] in ("install", "install-multiple", "install-multi-package", "uninstall"):
            raise ValueError("adb-package-mutation-not-retryable")
        argv = [self.adb, "-s", self.serial, *map(str, args)]
        deadline = time.monotonic() + timeout
        for attempt in range(self.attempts if idempotent else 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AdbError("adb-command-timeout")
            try:
                result = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                self.record(label, stdout=getattr(error, "stdout", b""), stderr=getattr(error, "stderr", b""), outcome=type(error).__name__)
                raise AdbError("adb-command-unavailable") from None
            self.record(label, stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
            if result.returncode >= 0 or not idempotent or attempt + 1 == self.attempts:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= self.retry_delay:
                return result
            time.sleep(self.retry_delay)
        raise AssertionError("unreachable")

    def run(self, *args, **kwargs):
        result = self.execute(*args, **kwargs)
        if result.returncode:
            raise AdbError("adb-command-failed")
        return result.stdout

    def install(self, apk, volume, *, reconcile, label="adb-install", timeout=600):
        """Install once with remote status, then verify exact caller-owned identity.

        reconcile() must perform read-only exact-artifact readback, not just test
        package presence/version. A lost/failed install is never replayed: a
        positive reconciliation establishes the desired state; all other outcomes
        remain unknown and grant no ownership or cleanup permission.
        """
        if not volume or not re.fullmatch(r"[A-Za-z0-9-]+", volume):
            raise ValueError("adb-install-volume-required")
        result = None
        try:
            result = self.execute("install", "-r", "--force-uuid", volume, apk, label=label, timeout=timeout)
        except AdbError:
            pass
        try:
            verified = reconcile() is True
        except Exception:
            verified = False
        if verified:
            return "verified" if result is not None and result.returncode == 0 else "reconciled"
        if result is not None and result.returncode > 0:
            raise AdbError("adb-install-failed")
        raise InstallUncertain("adb-install-outcome-unknown")

    def start_detached(self, command, *, label="adb-job", timeout=30):
        """Launch once in a fresh owned directory; never resend an uncertain launch.

        mkdir is an exclusive claim. stdin, stdout and stderr are detached from
        adb before launch returns. The remote status file is atomically published
        only after the command exits. Keep the handle to reconcile interruptions.
        """
        if not command:
            raise ValueError("adb-detached-command-required")
        job = DetachedJob("/data/local/tmp/ror2-adb-job-" + secrets.token_hex(16))
        directory = shlex.quote(job.directory)
        worker = (
            f"{shlex.join(list(map(str, command)))} >{directory}/stdout.log 2>{directory}/stderr.log; "
            f"status=$?; printf '%s\\n' \"$status\" >{directory}/status.tmp && mv {directory}/status.tmp {directory}/status"
        )
        launch = f"umask 077; mkdir {directory} || exit 1; setsid sh -c {shlex.quote(worker)} </dev/null >/dev/null 2>&1 &"
        try:
            result = self.execute("shell", launch, label=label + "-launch", timeout=timeout)
        except AdbError:
            # The remote launch may already exist. Only wait/readback is safe.
            return job
        # Even an ordinary connection failure can arrive after remote launch.
        # The exclusive directory/status protocol, not host exit, decides.
        return job

    def wait_detached(self, job, logs, *, label="adb-job", timeout=60, poll_interval=0.25):
        """Tolerate failed observations until deadline; pull logs before reporting.

        Timeout does not kill the remote job or remove its directory: neither
        absence nor completion is established. Caller retains the private handle
        and may wait again. Terminal jobs can be removed with cleanup_detached().
        """
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("adb-detached-wait-budget")
        logs = Path(logs)
        logs.mkdir(parents=True, exist_ok=True)
        directory = shlex.quote(job.directory)
        probe = f"if [ -f {directory}/status ]; then cat {directory}/status; else printf pending; fi"
        deadline, status, invalid = time.monotonic() + timeout, None, False
        while time.monotonic() < deadline:
            try:
                result = self.execute("shell", probe, label=label + "-poll", timeout=min(10, max(0.001, deadline - time.monotonic())), idempotent=True)
            except AdbError:
                result = None
            if result is not None and result.returncode == 0:
                value = result.stdout.strip()
                if re.fullmatch(rb"[0-9]{1,3}", value) and int(value) <= 255:
                    status = int(value)
                    break
                if value != b"pending":
                    invalid = True
                    break
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        # Log transfer has its own bounded recovery budget, including after a
        # timeout. Never substitute partial/missing logs for a terminal status.
        transferred = True
        for name in ("stdout.log", "stderr.log"):
            try:
                self.run("pull", job.directory + "/" + name, logs / name, label=label + "-logs", timeout=15, idempotent=True)
            except AdbError:
                transferred = False
        if invalid:
            raise AdbError("adb-detached-status-invalid")
        if status is None:
            raise DetachedUncertain(job)
        if not transferred:
            raise AdbError("adb-detached-log-pull-failed")
        result = subprocess.CompletedProcess([], status, (logs / "stdout.log").read_bytes(), (logs / "stderr.log").read_bytes())
        return result

    def cleanup_detached(self, job, *, timeout=15):
        # Guard against deleting a still-running job, even if a caller gets its
        # wait lifecycle wrong. Exact generated path only; no arbitrary rm API.
        directory = shlex.quote(job.directory)
        return self.run("shell", f"[ -f {directory}/status ] && rm -rf {directory}", label="adb-job-cleanup", timeout=timeout)
