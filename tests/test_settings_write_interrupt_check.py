"""Interruption evidence must distinguish an uncommitted store from a completed save."""

from contextlib import ExitStack
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import settings_write_interrupt_check as check  # noqa: E402


class InterruptedWriteEvidenceTests(unittest.TestCase):
    witness = dict(success=True, createObserved=True, writerExited=True, pendingPresentBeforeStop=True, pendingPresentAfterStop=True)

    def test_observer_uses_the_actual_device_timeout_transport(self):
        device = object.__new__(check.Device)
        with patch.object(check.Device, "cmd", autospec=True, return_value="observer evidence") as command:
            self.assertEqual(check.pending_observer(device, "owned observer"), "observer evidence")
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.args, (device, "shell", "owned observer"))
        self.assertGreater(command.call_args.kwargs["timeout"], 30)
        self.assertLessEqual(command.call_args.kwargs["timeout"], 45)

    def test_a_completed_save_is_not_interruption_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "new valid JSON", dict(state="absent"), self.witness)

    def test_unchanged_primary_without_a_retained_pending_file_is_not_enough(self):
        with self.assertRaisesRegex(RuntimeError, "Missed pre-commit"):
            check.interrupted_transaction("old valid JSON", "old valid JSON", dict(state="absent"), self.witness)

    def test_real_old_primary_and_partial_pending_can_satisfy_the_observed_contract(self):
        with tempfile.TemporaryDirectory() as root:
            primary = Path(root) / "preferences.json"
            pending = Path(root) / "preferences.json.pending"
            primary.write_text('{"version":1,"invertY":false}')
            before = primary.read_text()
            pending.write_text('{"version":')
            check.interrupted_transaction(before, primary.read_text(), dict(state="file"), self.witness)
            self.assertEqual(primary.read_text(), before)
            self.assertEqual(pending.read_text(), '{"version":')

    def test_synthetic_or_failed_observer_reports_cannot_qualify_real_interruption(self):
        for witness in (
            None,
            {},
            dict(self.witness, success=False),
            dict(self.witness, createObserved=1),
            dict(self.witness, pendingPresentAfterStop=False),
            dict(self.witness, writerExited=False),
            dict(self.witness, writerExited=1),
            dict(self.witness, pendingPresentBeforeStop=False),
        ):
            with self.subTest(witness=witness), self.assertRaisesRegex(RuntimeError, "No successful native"):
                check.interrupted_transaction("old", "old", dict(state="file"), witness)

    def test_missing_artifact_identity_refuses_before_device_access(self):
        with patch.object(check, "Device", side_effect=AssertionError("unexpected device access")):
            with self.assertRaisesRegex(ValueError, "requires --expected-apk-sha256"):
                check.check_settings_write_interrupt()

    def failed_menu(self, root, report, *, capture_report=None, logs="actual PID logs", log_error=None):
        out = Path(root) / "evidence"
        device = Mock()
        device.read_receipt.return_value = {"persistentDataPath": "/runtime"}
        device.evidence_directory.return_value = out
        device.launch.return_value = {"pid": "123"}
        pids = iter(["", "123", "123", ""])

        def sh(*args, **kwargs):
            if args[0] == "pidof":
                return next(pids)
            if args[0] == "sha256sum":
                return "a" * 64
            if args[0] == "logcat":
                self.assertIn("--pid=123", args)
                if log_error:
                    raise log_error
                return logs
            return ""

        device.sh.side_effect = sh
        device.cmd.side_effect = lambda *args: Path(args[2]).write_text("{}") if args[0] == "pull" else None
        original = RuntimeError("transition interrupted")
        with ExitStack() as stack:
            for name, value in (
                ("Device", device),
                ("bind_installed_apk", None),
                ("attempt_from_installed", "attempt"),
                ("sha", "a" * 64),
                ("selection", {"debugOptions": {}}),
                ("_read_raw", "{}"),
                ("selector_action", "remove-owned"),
                ("matches_run", True),
            ):
                stack.enter_context(patch.object(check, name, return_value=value))
            stack.enter_context(patch.object(check, "_remote_path_state", side_effect=lambda d, p: "file" if p.endswith("preferences.json") else "absent"))
            stack.enter_context(patch.object(check, "_read_json", side_effect=[report, capture_report if capture_report is not None else report]))
            stack.enter_context(patch.object(check.time, "sleep", side_effect=original))
            with self.assertRaises(RuntimeError) as raised:
                check.check_settings_write_interrupt("a" * 64)
        return original, raised.exception, out, json.loads((out / "result.json").read_text())

    def test_failure_before_menu_ready_saves_current_report_and_actual_pid_logs(self):
        report = {"phase": "bootstrap"}
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(root, report)
            self.assertIs(error, original)
            self.assertEqual(json.loads((out / "failure-current-report.json").read_text()), report)
            self.assertEqual((out / "failure-process.log").read_text(), "actual PID logs")
            self.assertEqual(result["error"], str(original))

    def test_latest_native_failure_overrides_interrupted_transition(self):
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(
                root, {"phase": "bootstrap"}, capture_report={"firstFailure": "native broke"}, log_error=RuntimeError("log unavailable")
            )
            self.assertIn("Native first failure: native broke", str(error))
            self.assertIs(error.__cause__, original)
            self.assertEqual(result["original_error"], str(original))
            self.assertEqual(result["capture_errors"], ["log unavailable"])

    def test_runtime_log_error_overrides_transition_even_if_report_capture_fails(self):
        with tempfile.TemporaryDirectory() as root, patch.object(check, "current_errors", return_value=["runtime broke"]):
            original, error, out, result = self.failed_menu(root, {"phase": "bootstrap"}, capture_report=RuntimeError("report unavailable"))
            self.assertIn("Actual-PID runtime error", str(error))
            self.assertEqual(result["capture_errors"], ["report unavailable"])
            self.assertEqual(result["runtime_errors"], ["runtime broke"])
            self.assertEqual(json.loads((out / "failure-current-report.json").read_text()), {"phase": "bootstrap"})

    def test_capture_failures_preserve_original_transition_error(self):
        with tempfile.TemporaryDirectory() as root:
            original, error, out, result = self.failed_menu(
                root, {"phase": "bootstrap"}, capture_report=RuntimeError("report unavailable"), log_error=RuntimeError("log unavailable")
            )
            self.assertIs(error, original)
            self.assertEqual(result["capture_errors"], ["report unavailable", "log unavailable"])
