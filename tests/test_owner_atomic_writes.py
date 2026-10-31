"""Synthetic ENOSPC and process-death contracts for actual installer owners."""

import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/phone-build/owner-apk"


def module(name):
    spec = importlib.util.spec_from_file_location("atomic_test_" + name, OWNER / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A, G, F, R, U = [module(name) for name in ("atomic_io", "game_import", "install_flow", "release", "updates")]


class AtomicWritesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "state.json"
        A.write_json(self.path, {"previous": True})
        self.previous = self.path.read_bytes()

    def test_enospc_mid_write_preserves_previous_and_cleans_partial(self):
        with self.assertRaises(OSError) as caught:
            with A.writer(self.path) as output:
                output.write(b"partial")
                raise OSError(errno.ENOSPC, "injected write quota")
        self.assertEqual(caught.exception.errno, errno.ENOSPC)
        self.assertEqual(self.path.read_bytes(), self.previous)
        self.assertFalse(self.path.with_name(".state.json.pending").exists())
        A.write_json(self.path, {"resumed": True})
        self.assertEqual(json.loads(self.path.read_bytes()), {"resumed": True})

    def test_fsync_and_rename_enospc_leave_old_receipt(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation):
                with patch.object(A.os, operation, side_effect=OSError(errno.ENOSPC, operation)):
                    with self.assertRaises(OSError):
                        A.write_json(self.path, {"new": True})
                self.assertEqual(self.path.read_bytes(), self.previous)
                self.assertFalse(self.path.with_name(".state.json.pending").exists())

    def test_directory_sync_failure_never_claims_rollback_after_rename(self):
        with patch.object(A, "sync_directory", side_effect=OSError(errno.ENOSPC, "directory sync")):
            with self.assertRaises(OSError):
                A.write_json(self.path, {"new": True})
        self.assertEqual(json.loads(self.path.read_bytes()), {"new": True})
        A.write_json(self.path, {"resumed": True})

    def test_sigkill_mid_write_keeps_old_state_and_retry_discards_partial(self):
        code = """import importlib.util, os, signal, sys
from pathlib import Path
s=importlib.util.spec_from_file_location("atomic", sys.argv[1]); a=importlib.util.module_from_spec(s); s.loader.exec_module(a)
with a.writer(Path(sys.argv[2])) as output:
 output.write(b"unverified partial" * 4096); output.flush()
 os.kill(os.getpid(), signal.SIGKILL)
"""
        process = subprocess.run([sys.executable, "-c", code, str(OWNER / "atomic_io.py"), str(self.path)], capture_output=True, timeout=15)
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assertEqual(self.path.read_bytes(), self.previous)
        self.assertTrue(self.path.with_name(".state.json.pending").exists())
        A.write_json(self.path, {"retry": True})
        self.assertFalse(self.path.with_name(".state.json.pending").exists())

    def test_import_enospc_preserves_verified_file_and_original_failure(self):
        values = {"a": b"first", "b": b"second" * 10000}
        manifest = {
            "schema": 1,
            "game_version": "authored",
            "files": [{"path": n, "bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()} for n, v in values.items()],
        }
        source = G.StreamSource({n: len(v) for n, v in values.items()}, lambda n: io.BytesIO(values[n]))
        importer = G.Importer(manifest, self.root / "import", reserve_bytes=0, free_bytes=lambda: 1024**2)
        original = importer._digest

        def fail(stream, size, **kwargs):
            if kwargs.get("output") is not None and kwargs.get("name") == "b":
                kwargs["output"].write(b"partial")
                raise OSError(errno.ENOSPC, "original producer write")
            return original(stream, size, **kwargs)

        with patch.object(importer, "_digest", side_effect=fail):
            with self.assertRaisesRegex(OSError, "original producer write"):
                importer.run(source)
        self.assertEqual((importer.files / "a").read_bytes(), values["a"])
        self.assertFalse((importer.files / "b").exists())
        self.assertEqual(list(importer.staging.iterdir()), [])
        self.assertEqual(importer.run(source)["status"], "complete")

    def test_failure_checkpoint_enospc_does_not_mask_original_error(self):
        plan = {"stages": [{"id": n, "title": n, "jobs": []} for n in F.STAGES]}
        flow = F.Pipeline(self.root, "release", "input", plan)
        flow.begin("textures")
        with patch.object(F, "write_json", side_effect=OSError(errno.ENOSPC, "checkpoint full")):
            flow.fail(ValueError("actual producer failure"))
        self.assertEqual(flow.state["first_failure"]["reason"], "actual producer failure")
        resumed = F.Pipeline(self.root, "release", "input", plan)
        self.assertEqual(resumed.row("textures")["status"], "interrupted")

    def test_completed_release_entries_resume_after_next_producer_enospc(self):
        release = {
            "version": "test",
            "version_code": 2,
            "application_id": "dev.ror2lab.alpha",
            "minimum_installer_version": 1,
            "bundle_sha256": "a" * 64,
            "entries": {n: {"recipe_sha256": "b" * 64, "producer_sha256": "c" * 64} for n in ("apk/a", "apk/b")},
        }
        calls = []

        def produce(name, dependencies, output):
            calls.append(name)
            output.write_bytes(b"synthetic")
            if name == "apk/b" and len(calls) == 2:
                raise OSError(errno.ENOSPC, "producer quota")

        args = dict(
            installer_version=1, application_id=release["application_id"], installed_version=1, input_sha256="d" * 64, root=self.root / "cache", produce=produce
        )
        with self.assertRaises(OSError):
            R.rebuild(release, **args)
        self.assertFalse((self.root / "cache/apk/b.building").exists())
        result = R.rebuild(release, **args)
        self.assertEqual(result["reused"], ["apk/a"])
        self.assertEqual(calls, ["apk/a", "apk/b", "apk/b"])

    def test_java_bounded_filled_quota(self):
        compiler = shutil.which("javac")
        if not compiler:
            candidate = Path(os.environ.get("JAVA_HOME", "/absent")) / "bin/javac"
            if not candidate.is_file():
                self.skipTest("Java compiler absent")
            compiler = str(candidate)
        source = ROOT / "tools/phone-build/managed-host/OwnerInputImport.java"
        fixture = ROOT / "tests/fixtures/InstallerQuotaHarness.java"
        result = subprocess.run([compiler, "-d", str(self.root), str(source), str(fixture)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            [str(Path(compiler).with_name("java")), "-cp", str(self.root), "InstallerQuotaHarness", str(self.root / "quota")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("PASS "), 3)


class QuotaDriverTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("quota_driver", ROOT / "scripts/lab-installer-quota.py")
        self.driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.driver)

    def inspection_fixture(self, root):
        logs = root / "work/coordination/installer-quota/run-synthetic"
        logs.mkdir(parents=True)
        (logs / "phone-quota.stdout").write_bytes(b"PRIVATE OUTPUT\xff")
        (logs / "phone-quota.stderr").write_bytes(b"java.lang.AssertionError: PRIVATE PATH\n")
        return logs

    def test_inspection_is_read_only_bounded_and_workflow_association_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = self.inspection_fixture(root)
            (logs / "phone-quota.stderr").write_bytes(b"java.lang.AssertionError: PRIVATE\n" + b"x" * 40000)
            before = {p.name: p.read_bytes() for p in logs.iterdir()}
            with patch.object(self.driver, "ROOT", root), patch.object(self.driver.subprocess, "run") as command:
                result = self.driver.inspect_quota_failure("newest")
            command.assert_not_called()
            self.assertEqual(result["java_errors"], ["java.lang.AssertionError"])
            self.assertTrue(result["logs_truncated"])
            self.assertEqual(result["workflow_association"], "unrecorded")
            self.assertIsNone(result["returncode"])
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertNotIn("run-synthetic", json.dumps(result))
            self.assertEqual(before, {p.name: p.read_bytes() for p in logs.iterdir()})

    def test_inspection_selection_rejects_paths_symlinks_and_nonregular_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = self.inspection_fixture(root)
            with patch.object(self.driver, "ROOT", root):
                for value in ("../run-synthetic", str(logs), "run-synthetic/child", "41187385460", "run-", "run-a\n"):
                    with self.assertRaises(self.driver.Failure):
                        self.driver.inspect_quota_failure(value)
                linked = logs.parent / "run-link"
                linked.symlink_to(logs, target_is_directory=True)
                with self.assertRaises(self.driver.Failure):
                    self.driver.inspect_quota_failure("run-link")
                stderr = logs / "phone-quota.stderr"
                stderr.unlink()
                stderr.symlink_to(logs / "phone-quota.stdout")
                with self.assertRaises(self.driver.Failure):
                    self.driver.inspect_quota_failure("run-synthetic")
                stderr.unlink()
                os.mkfifo(stderr)
                with self.assertRaisesRegex(self.driver.Failure, "diagnostic-log-not-regular"):
                    self.driver.inspect_quota_failure("run-synthetic")

    def test_inspection_mode_never_uses_serial_compiler_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.inspection_fixture(root)
            output = io.StringIO()
            with (
                patch.object(self.driver, "ROOT", root),
                patch.dict(os.environ, {}, clear=True),
                patch.object(self.driver.subprocess, "run") as command,
                patch("sys.stdout", output),
            ):
                self.assertEqual(self.driver.main(["--inspect-quota-failure", "--diagnostic-run", "run-synthetic"]), 0)
            command.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["selection"], "explicit")

    def test_inspection_missing_logs_refuses_and_shared_work_symlink_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared = root / "shared"
            shared.mkdir()
            logs = self.inspection_fixture(shared)
            checkout = root / "checkout"
            checkout.mkdir()
            (checkout / "work").symlink_to(shared / "work", target_is_directory=True)
            with patch.object(self.driver, "ROOT", checkout):
                self.assertEqual(self.driver.inspect_quota_failure("newest")["status"], "observed")
                (logs / "phone-quota.stdout").unlink()
                with self.assertRaisesRegex(self.driver.Failure, "diagnostic-evidence-unavailable-or-unsafe"):
                    self.driver.inspect_quota_failure("newest")

    def test_failed_command_preserves_bounded_logs_and_fixed_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            logs = Path(temporary)
            private = b"java.lang.AssertionError: PRIVATE_INPUT\n" + b"x" * 40000
            result = subprocess.CompletedProcess(["adb"], 1, b"PRIVATE_OUTPUT", private)
            with patch.object(self.driver.subprocess, "run", return_value=result):
                with self.assertRaises(self.driver.Failure) as caught:
                    self.driver.run(["adb", "PRIVATE_ARGUMENT"], logs, "phone-quota")
            diagnostic = caught.exception.diagnostic
            self.assertEqual(diagnostic["returncode"], 1)
            self.assertEqual(diagnostic["java_errors"], ["java.lang.AssertionError"])
            self.assertTrue(diagnostic["logs_truncated"])
            self.assertNotIn("PRIVATE", json.dumps(diagnostic))
            self.assertEqual((logs / "phone-quota.stderr").stat().st_size, self.driver.LOG_LIMIT)
            self.assertEqual((logs / "phone-quota.stdout").read_bytes(), b"PRIVATE_OUTPUT")
            self.assertEqual(json.loads((logs / "phone-quota.result.json").read_text()), diagnostic)

    def test_signal_and_guard_codes_are_distinct_without_signal_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            logs = Path(temporary)
            for code, category in (
                (-9, "host-command-signal"),
                (81, "guard-initial-refusal"),
                (82, "guard-watchdog-refusal"),
                (83, "guard-final-refusal"),
                (137, "exited"),
            ):
                result = self.driver.record_command(logs, "phone-quota", returncode=code)
                self.assertEqual(result["category"], category)
                self.assertEqual(result["signal"], "SIGKILL" if code == -9 else None)

    def test_timeout_preserves_partial_output_and_launch_error_hides_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            logs = Path(temporary)
            timeout = subprocess.TimeoutExpired(["PRIVATE"], 30, output=b"partial", stderr=b"private stderr")
            with patch.object(self.driver.subprocess, "run", side_effect=timeout):
                with self.assertRaises(self.driver.Failure) as caught:
                    self.driver.run(["adb"], logs, "phone-quota")
            self.assertEqual(caught.exception.diagnostic["category"], "host-command-timeout")
            self.assertIsNone(caught.exception.diagnostic["returncode"])
            self.assertEqual((logs / "phone-quota.stdout").read_bytes(), b"partial")
            with patch.object(self.driver.subprocess, "run", side_effect=OSError("PRIVATE LAUNCH ERROR")):
                with self.assertRaises(self.driver.Failure) as caught:
                    self.driver.run(["adb"], logs, "phone-quota")
            self.assertEqual(caught.exception.diagnostic["category"], "host-command-launch-error")
            self.assertNotIn("PRIVATE", json.dumps(caught.exception.diagnostic))

    def test_java_class_allowlist_does_not_expose_unknown_names_or_messages(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.driver.record_command(
                Path(temporary),
                "phone-quota",
                returncode=1,
                stderr=b'Exception in thread "PRIVATE" java.lang.reflect.InvocationTargetException\n'
                b"Caused by: android.system.ErrnoException: open failed: PRIVATE\n"
                b"private.secret.UnknownException: details\n",
            )
            self.assertEqual(result["java_errors"], ["java.lang.reflect.InvocationTargetException", "android.system.ErrnoException"])
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertNotIn("private.secret", json.dumps(result))

    def test_no_device_selection_refuses_before_command(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self.driver, "run") as command:
            self.assertEqual(self.driver.main([]), 1)
        command.assert_not_called()

    def test_battery_charging_temperature_and_storage_gate(self):
        for level, current, temperature, free, succeeds in (
            (60, 0, 300, 16 * 1024**2, True),
            (86, -1, 300, 16 * 1024**2, False),
            (80, 1, 300, 16 * 1024**2, False),
            (60, 0, 350, 16 * 1024**2, False),
            (60, 0, 300, 14 * 1024**2, False),
        ):
            with self.subTest(level=level, current=current, temperature=temperature, free=free):
                output = [
                    f"level: {level}\ntemperature: {temperature}\n".encode(),
                    str(current).encode(),
                    f"Filesystem 1K-blocks Used Available Use% Mounted on\nscratch 99999999 1 {free} 1% /scratch\n".encode(),
                ]
                with patch.object(self.driver, "run", side_effect=output):
                    if succeeds:
                        self.driver.safety(["adb"], Path("/unused"), "test")
                    else:
                        with self.assertRaises(self.driver.Failure):
                            self.driver.safety(["adb"], Path("/unused"), "test")

    def test_guard_shell_syntax_and_owned_limits(self):
        result = subprocess.run(["sh", "-n"], input=self.driver.GUARD, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for contract in ('kill -9 "$child"', '"$count" -ge 20', '"$temperature" -lt 350', '"$capacity" -le 85'):
            self.assertIn(contract, self.driver.GUARD)
        self.assertNotIn("mount ", self.driver.GUARD)
        self.assertIsNone(self.driver.REMOTE.fullmatch("/data/local/tmp/other"))


if __name__ == "__main__":
    unittest.main()
