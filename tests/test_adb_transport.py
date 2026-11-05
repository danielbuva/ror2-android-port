"""Host-only fake ADB: authored temporary text, no device/server/APK inputs."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_adb_transport_module", ROOT / "scripts/lab/adb_transport.py")
ADB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADB)

FAKE = r"""#!/usr/bin/env python3
import json, os, pathlib, shutil, signal, subprocess, sys
root = pathlib.Path(__file__).parent
config = json.loads((root / 'config.json').read_text())
args = sys.argv[1:]
assert args[:2] == ['-s', 'synthetic-target']
args = args[2:]
with (root / 'calls.jsonl').open('a') as out:
    out.write(json.dumps(args) + '\n')
calls = [json.loads(row) for row in (root / 'calls.jsonl').read_text().splitlines()]
mode = config.get('mode')
if mode == 'signal' and len(calls) <= config.get('kills', 1):
    os.kill(os.getpid(), signal.SIGKILL)
if mode == 'exit':
    print('synthetic failure', file=sys.stderr)
    sys.exit(config['code'])
if args[0] == 'install':
    print('Success' if config.get('code', 0) == 0 else 'Failure')
    sys.exit(config.get('code', 0))
if args[0] == 'push':
    shutil.copyfile(args[1], root / 'pushed')
    sys.exit(0)
if args[0] == 'pull':
    source = args[1].replace('/data/local/tmp', str(root / 'remote'))
    try:
        shutil.copyfile(source, args[2])
    except OSError:
        sys.exit(1)
    sys.exit(0)
assert args[0] == 'shell'
if len(args) == 2:
    command = args[1].replace('/data/local/tmp', str(root / 'remote'))
    if 'printf pending' in command and config.get('poll_failures'):
        polls = sum('printf pending' in ' '.join(row) for row in calls)
        if polls <= config['poll_failures']:
            sys.exit(1)
    code = subprocess.run(['sh', '-c', command]).returncode
    if mode == 'lost-launch' and 'setsid sh -c' in command:
        os.kill(os.getpid(), signal.SIGKILL)
    if mode == 'disconnected-launch' and 'setsid sh -c' in command:
        sys.exit(1)
    sys.exit(code)
print('synthetic-readback')
"""


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "remote").mkdir()
        self.fake = self.root / "fake-adb"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o700)
        self.configure()
        self.records = []
        self.adb = ADB.AdbTransport(self.fake, "synthetic-target", observer=lambda label, **row: self.records.append((label, row)), retry_delay=0)

    def configure(self, **values):
        (self.root / "config.json").write_text(json.dumps(values))

    def calls(self):
        return [json.loads(row) for row in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_retries_signal_killed_read_only_and_keeps_each_diagnostic(self):
        self.configure(mode="signal")
        self.assertEqual(self.adb.run("shell", "cat", "synthetic", label="read", idempotent=True), b"synthetic-readback\n")
        self.assertEqual([row[1]["returncode"] for row in self.records], [-9, 0])
        self.assertEqual(len(self.calls()), 2)

    def test_signal_retry_is_bounded(self):
        self.configure(mode="signal", kills=10)
        self.assertEqual(self.adb.execute("shell", "cat", "synthetic", label="read", idempotent=True).returncode, -9)
        self.assertEqual(len(self.calls()), 3)

    def test_push_same_immutable_bytes_to_owned_destination_can_opt_in(self):
        self.configure(mode="signal")
        source = self.root / "authored.txt"
        source.write_text("synthetic fixture")
        self.adb.run("push", source, "/synthetic-owned-path", label="push", idempotent=True)
        self.assertEqual((self.root / "pushed").read_text(), "synthetic fixture")
        self.assertEqual(len(self.calls()), 2)

    def test_mutation_is_not_replayed_after_signal(self):
        self.configure(mode="signal")
        self.assertEqual(self.adb.execute("shell", "input", "tap", "1", "2", label="tap").returncode, -9)
        self.assertEqual(len(self.calls()), 1)

    def test_nonzero_exit_including_remote_signal_is_never_retried(self):
        for code in (1, 137):
            with self.subTest(code=code):
                self.configure(mode="exit", code=code)
                before = len(self.records)
                self.assertEqual(self.adb.execute("shell", "cat", "synthetic", label="read", idempotent=True).returncode, code)
                self.assertEqual(len(self.records) - before, 1)

    def test_timeout_not_retried_and_exception_does_not_publish_private_output(self):
        with patch.object(ADB.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic-private", 1, output=b"synthetic-private")) as run:
            with self.assertRaisesRegex(ADB.AdbError, "^adb-command-unavailable$"):
                self.adb.run("shell", "cat", "synthetic-private", label="read", idempotent=True)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.records[-1][1]["outcome"], "TimeoutExpired")

    def test_retry_timeout_budget_shrinks_instead_of_resetting(self):
        result = subprocess.CompletedProcess([], -9, b"", b"")
        with patch.object(ADB.time, "monotonic", side_effect=[0, 1, 2, 3, 4, 5]), patch.object(ADB.subprocess, "run", return_value=result) as run:
            self.adb.execute("shell", "cat", "synthetic", label="read", timeout=10, idempotent=True)
        self.assertEqual([call.kwargs["timeout"] for call in run.call_args_list], [9, 7, 5])

    def test_requires_explicit_device_and_forbids_exec_in_or_install_retry(self):
        with self.assertRaises(ValueError):
            ADB.AdbTransport(self.fake, "")
        with self.assertRaisesRegex(ValueError, "status-unavailable"):
            self.adb.execute("exec-in", "pm", "install", "synthetic", label="install")
        with self.assertRaisesRegex(ValueError, "not-retryable"):
            self.adb.execute("install", "synthetic", label="install", idempotent=True)

    def test_install_uses_status_returning_adb_and_requires_exact_reconciliation(self):
        self.assertEqual(self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: True), "verified")
        self.assertEqual(self.calls(), [["install", "-r", "--force-uuid", "synthetic-volume", "synthetic-input"]])

    def test_killed_install_reconciles_without_second_install(self):
        self.configure(mode="signal")
        self.assertEqual(self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: True), "reconciled")
        self.assertEqual(len(self.calls()), 1)

    def test_killed_install_without_exact_readback_remains_unknown(self):
        self.configure(mode="signal")
        with self.assertRaises(ADB.InstallUncertain):
            self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: False)
        self.assertEqual(len(self.calls()), 1)

    def test_install_exit_zero_is_not_identity_proof(self):
        with self.assertRaises(ADB.InstallUncertain):
            self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: False)
        self.assertEqual(len(self.calls()), 1)

    def test_install_remote_failure_is_not_success_even_with_success_shaped_text(self):
        self.configure(code=1)
        with self.assertRaisesRegex(ADB.AdbError, "^adb-install-failed$"):
            self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: False)
        self.assertEqual(len(self.calls()), 1)

    def test_timed_out_install_reconciles_without_replaying(self):
        with patch.object(ADB.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic-private", 1)) as run:
            self.assertEqual(self.adb.install("synthetic-input", "synthetic-volume", reconcile=lambda: True), "reconciled")
        self.assertEqual(run.call_count, 1)

    def test_disconnected_launch_is_observed_not_replayed(self):
        self.configure(mode="disconnected-launch")
        job = self.adb.start_detached(["printf", "synthetic-done"])
        result = self.adb.wait_detached(job, self.root / "logs", timeout=3, poll_interval=0.01)
        self.assertEqual(result.stdout, b"synthetic-done")
        self.assertEqual(sum("setsid sh -c" in " ".join(call) for call in self.calls()), 1)
        self.adb.cleanup_detached(job)

    def test_detached_lost_launch_tolerates_poll_errors_and_pulls_remote_exit_and_logs(self):
        self.configure(mode="lost-launch", poll_failures=2)
        job = self.adb.start_detached(["sh", "-c", "printf synthetic-out; printf synthetic-err >&2; exit 7"])
        result = self.adb.wait_detached(job, self.root / "logs", timeout=3, poll_interval=0.01)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, b"synthetic-out", b"synthetic-err"))
        launches = [call for call in self.calls() if "setsid sh -c" in " ".join(call)]
        self.assertEqual(len(launches), 1)
        self.assertIn("</dev/null >/dev/null 2>&1 &", launches[0][1])
        self.adb.cleanup_detached(job)
        self.assertFalse((self.root / "remote" / Path(job.directory).name).exists())

    def test_detached_timeout_preserves_handle_and_cannot_cleanup_running_job(self):
        job = self.adb.start_detached(["sh", "-c", "sleep 0.5; printf synthetic-done"])
        with self.assertRaises(ADB.DetachedUncertain) as error:
            self.adb.wait_detached(job, self.root / "logs", timeout=0.02, poll_interval=0.01)
        self.assertIs(error.exception.job, job)
        self.assertNotIn(job.directory, str(error.exception))
        with self.assertRaises(ADB.AdbError):
            self.adb.cleanup_detached(job)
        result = self.adb.wait_detached(job, self.root / "logs", timeout=3, poll_interval=0.01)
        self.assertEqual(result.stdout, b"synthetic-done")
        self.assertEqual(sum("setsid sh -c" in " ".join(call) for call in self.calls()), 1)
        self.adb.cleanup_detached(job)

    def test_detached_quotes_arguments_and_refuses_unowned_paths(self):
        value = "synthetic ' value; no shell interpolation"
        job = self.adb.start_detached(["printf", "%s", value])
        result = self.adb.wait_detached(job, self.root / "logs", timeout=3, poll_interval=0.01)
        self.assertEqual(result.stdout.decode(), value)
        self.adb.cleanup_detached(job)
        with self.assertRaises(ValueError):
            ADB.DetachedJob("/data/local/tmp")


if __name__ == "__main__":
    unittest.main()
