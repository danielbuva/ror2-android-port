import contextlib
import io
import json
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "scripts" / "lab"
sys.path.insert(0, str(LAB))
import device
import performance_capture


class FakeDevice:
    instances = []

    def __init__(self):
        self.collections = []
        type(self).instances.append(self)

    def collect(self, kind, output):
        self.collections.append((kind, output))
        return {"success": True, "kind": kind}

    @classmethod
    def sleep_awakened(cls):
        return []


class PerformanceCliTests(unittest.TestCase):
    def run_cli(self, args, *, capture=None):
        FakeDevice.instances.clear()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(device, "Device", FakeDevice),
            patch.object(performance_capture, "capture_cpu", capture) if capture else contextlib.nullcontext(),
            patch.object(sys, "argv", [str(LAB / "main.py"), *args]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            runpy.run_path(str(LAB / "main.py"), run_name="__main__")
        return stdout.getvalue(), stderr.getvalue()

    def test_cpu_action_uses_one_selected_device_fixed_duration_and_target_label(self):
        capture = unittest.mock.Mock(return_value={"success": True, "label": "crowded-stage"})
        output, _ = self.run_cli(
            ["perf", "--action", "cpu", "--target", "crowded-stage", "--device", "synthetic-serial"],
            capture=capture,
        )
        capture.assert_called_once_with(FakeDevice.instances[0], duration_seconds=15, label="crowded-stage", scope="pid")
        self.assertEqual(len(FakeDevice.instances), 1)
        self.assertEqual(json.loads(output), {"success": True, "label": "crowded-stage"})
        self.assertEqual(FakeDevice.instances[0].collections, [])

    def test_app_scope_is_explicit_and_passed_only_to_cpu_capture(self):
        capture = unittest.mock.Mock(return_value={"success": True, "capture_scope": "owned-package-process-set"})
        output, _ = self.run_cli(
            ["perf", "--action", "cpu", "--profile-scope", "app", "--target", "manual-sample"],
            capture=capture,
        )
        capture.assert_called_once_with(FakeDevice.instances[0], duration_seconds=15, label="manual-sample", scope="app")
        self.assertEqual(json.loads(output)["capture_scope"], "owned-package-process-set")

    def test_app_scope_help_discloses_package_process_set_semantics(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(device, "Device", FakeDevice),
            patch.object(sys, "argv", [str(LAB / "main.py"), "perf", "--help"]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            runpy.run_path(str(LAB / "main.py"), run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("may include more than one PID", stdout.getvalue())

    def test_app_scope_rejected_for_non_cpu_actions(self):
        FakeDevice.instances.clear()
        stderr = io.StringIO()
        with (
            patch.object(device, "Device", FakeDevice),
            patch.object(sys, "argv", [str(LAB / "main.py"), "perf", "--action", "collect", "--profile-scope", "app"]),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            runpy.run_path(str(LAB / "main.py"), run_name="__main__")
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("requires perf --action cpu", stderr.getvalue())
        self.assertEqual(FakeDevice.instances, [])

    def test_bare_perf_preserves_existing_collection_behavior(self):
        output, _ = self.run_cli(["perf"])
        self.assertEqual(len(FakeDevice.instances), 1)
        self.assertEqual(FakeDevice.instances[0].collections[0][0], "perf")
        self.assertEqual(json.loads(output), {"success": True, "kind": "perf"})

    def test_unknown_perf_action_is_refused_before_device_selection(self):
        FakeDevice.instances.clear()
        stderr = io.StringIO()
        with (
            patch.object(device, "Device", FakeDevice),
            patch.object(sys, "argv", [str(LAB / "main.py"), "perf", "--action", "launch"]),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            runpy.run_path(str(LAB / "main.py"), run_name="__main__")
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(FakeDevice.instances, [])
        self.assertIn("perf --action must be collect or cpu", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
