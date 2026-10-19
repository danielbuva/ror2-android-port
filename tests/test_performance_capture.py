import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "lab"))
import performance_capture
from device import PACKAGE


SERIAL = "synthetic-device-1"
APK_HASH = "a" * 64


class FakeDevice:
    def __init__(self, root, *, owned=True, foreground=True, pids=None,
                 profiler=True, record_error=None, report_error=None,
                 session_sequence=None, pull_mode="normal", foreground_sequence=None,
                 record_output="recorded: samples=987, truncated=0\n"):
        self.serial = SERIAL
        self.work_root = Path(root)
        self.root = Path(root) / "device" / SERIAL
        self.root.mkdir(parents=True, exist_ok=True)
        self.commands = []
        self.shell = []
        self._owned = owned
        self._owned_index = 0
        self._foreground = foreground
        self._foreground_sequence = list(foreground_sequence or [])
        self._foreground_index = 0
        self._pids = list(pids or ["1234", "1234"])
        self._pid_index = 0
        self._profiler = profiler
        self._record_error = record_error
        self._record_output = record_output
        self._report_error = report_error
        self._session_sequence = list(session_sequence or [])
        self._session_index = 0
        self._pull_mode = pull_mode
        self.selection = {"attempt": "attempt-current", "id": "body-state-spine"}
        self.report = {
            "attempt": "attempt-current",
            "id": "body-state-spine",
            "session": 7,
            "pid": 1234,
            "phase": "integrated-world-playing",
            "stage": {"scene": "wispgraveyard"},
            "stageProgress": {"transitions": 2},
            "world": {"seconds": 240},
            "performance": {
                "displayRefreshRate": 120,
                "requestedFrameRate": 300,
                "targetFrameRate": -1,
                "frames": 12000,
                "sampledAllocationFrames": 90,
            },
            "framePacing": {
                "frames": 12000,
                "meanMs": 21.0,
                "maxMs": 54.0,
                "over33ms": 800,
                "over50ms": 40,
                "samples": [{
                    "activeSeconds": 240,
                    "frames": 12000,
                    "scene": "wispgraveyard",
                    "managedBytes": 700000000,
                    "gcCollections": 80,
                    "sampledCpuMs": 31.0,
                    "sampledMainActiveMs": 29.0,
                    "sampledGpuMs": 12.0,
                    "sampledGcAllocBytes": 20000,
                }],
            },
        }
        self.runtime_path = "/storage/emulated/0/Android/data/" + PACKAGE + "/files"
        (self.root / "runtime.json").write_text(json.dumps({
            "serial": SERIAL,
            "persistentDataPath": self.runtime_path,
        }))

    def evidence_directory(self, *components):
        self.evidence_components = components
        return self.root.joinpath(*components)

    def receipt(self, name):
        return self.root / name

    def read_receipt(self, name):
        self.read_receipt_names = getattr(self, "read_receipt_names", []) + [name]
        if name != "runtime.json":
            raise AssertionError("unexpected receipt read")
        value = json.loads((self.root / name).read_text())
        if value.get("serial") != self.serial:
            raise RuntimeError("runtime receipt belongs to another selected serial")
        if not value.get("persistentDataPath", "").endswith("/Android/data/" + PACKAGE + "/files"):
            raise RuntimeError("runtime path is not backed by the selected package")
        return value

    def owned(self):
        if self._owned is False:
            raise RuntimeError("no installed ownership receipt")
        if isinstance(self._owned, list):
            value = self._owned[min(self._owned_index, len(self._owned) - 1)]
            self._owned_index += 1
            if value is None:
                raise RuntimeError("no installed ownership receipt")
            return value
        return {
            "serial": SERIAL,
            "package": PACKAGE,
            "apk_sha256": APK_HASH,
            "package_path": "/data/app/owned-lab",
            "build_key": "source-build-key",
            "storage": {"mode": "adopted"},
        }

    def sh(self, *args, check=True):
        self.shell.append(tuple(str(arg) for arg in args))
        if args[:2] == ("pidof", PACKAGE):
            index = min(self._pid_index, len(self._pids) - 1)
            self._pid_index += 1
            return self._pids[index]
        if args[:2] == ("dumpsys", "activity"):
            if self._foreground_sequence:
                foreground = self._foreground_sequence[min(self._foreground_index, len(self._foreground_sequence) - 1)]
                self._foreground_index += 1
            else:
                foreground = self._foreground
            return (
                "mResumedActivity: ActivityRecord{abc u0 " + PACKAGE + "/.MainActivity t1}\n"
                if foreground else
                "mResumedActivity: ActivityRecord{abc u0 example.other/.MainActivity t1}\n"
            )
        if args[0] == "cat" and args[-1].endswith("movement-batch-selection.json"):
            return json.dumps(self.selection)
        if args[0] == "cat" and args[-1].endswith("movement-batch-body-state-spine.json"):
            if self._session_sequence:
                value = self._session_sequence[min(self._session_index, len(self._session_sequence) - 1)]
                self._session_index += 1
                return json.dumps(value)
            return json.dumps(self.report)
        if args[0] == "rm":
            return ""
        return ""

    def cmd(self, *args, check=True, timeout=120):
        self.commands.append((tuple(str(arg) for arg in args), check, timeout))
        args = tuple(str(arg) for arg in args)
        if args[:3] == ("shell", "command", "-v"):
            if not self._profiler:
                raise RuntimeError("simpleperf: not found")
            return "/system/bin/simpleperf"
        if len(args) == 2 and args[0] == "shell" and args[1].startswith("simpleperf record "):
            if self._record_error:
                raise self._record_error
            return self._record_output
        if args[:2] == ("pull", "/data/local/tmp/"):
            raise AssertionError("pull command was not passed as one path")
        if args[0] == "pull":
            if self._pull_mode == "empty":
                Path(args[2]).write_bytes(b"")
            elif self._pull_mode != "missing":
                Path(args[2]).write_bytes(b"mock call graph bytes")
            return "pulled"
        if args[:3] == ("shell", "simpleperf", "report"):
            if self._report_error:
                raise self._report_error
            return "comm dso symbol\nlibgame.so Game.Update"
        return ""


class PerformanceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = patch.object(performance_capture, "now", return_value="20261019T010203.000000Z")
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.uuid = patch.object(
            performance_capture.uuid,
            "uuid4",
            side_effect=[
                type("UUID", (), {"hex": format(index, "010x") + ("0" * 22)})()
                for index in range(1, 40)
            ],
        )
        self.uuid.start()
        self.addCleanup(self.uuid.stop)

    def run_capture(self, **kwargs):
        fake = FakeDevice(self.temp.name, **kwargs)
        with patch.object(performance_capture, "Device", return_value=fake):
            result = performance_capture.capture_cpu()
        return fake, result

    def test_stable_owned_foreground_capture_records_cohort_and_live_runtime_context(self):
        fake, receipt = self.run_capture()
        self.assertTrue(receipt["success"])
        self.assertTrue(receipt["identity_stable"])
        self.assertEqual(receipt["pid"], "1234")
        self.assertEqual(receipt["cohort"]["apk_sha256"], APK_HASH)
        self.assertEqual(receipt["runtime_context_before"]["phase"], "integrated-world-playing")
        self.assertEqual(receipt["runtime_context_before"]["stage"], "wispgraveyard")
        self.assertEqual(receipt["runtime_context_before"]["performance"]["requestedFrameRate"], 300)
        self.assertEqual(receipt["runtime_context_before"]["session"], 7)
        self.assertEqual(receipt["runtime_context_after"]["id"], "body-state-spine")
        self.assertEqual(receipt["runtime_transition"]["stage_before"], "wispgraveyard")
        self.assertIn("runtime.json", fake.read_receipt_names)
        self.assertIn("performance", fake.evidence_components)
        self.assertTrue((Path(self.temp.name) / receipt["profile_path"]).is_file())
        record_output_path = Path(self.temp.name) / receipt["record_output_path"]
        self.assertEqual(record_output_path.read_text(), "recorded: samples=987, truncated=0\n")
        self.assertTrue((Path(self.temp.name) / receipt["report_path"]).is_file())
        self.assertTrue(receipt["remote_profile_removed"])
        reports = [command for command, _, _ in fake.commands
                   if command[:3] == ("shell", "simpleperf", "report")]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0][:5], ("shell", "simpleperf", "report", "-g", "-i"))
        self.assertEqual(reports[0][6:], ("--sort", "comm,dso,symbol"))
        record_calls = [command for command, _, _ in fake.commands
                        if len(command) == 2 and command[0] == "shell"
                        and command[1].startswith("simpleperf record ")]
        self.assertEqual(len(record_calls), 1)
        remote = receipt["record_remote_profile"]
        expected_argv = ["simpleperf", "record", "-g", "-p", "1234",
                         "--duration", "15", "-o", remote]
        expected_script = shlex.join(expected_argv) + " 2>&1"
        self.assertEqual(record_calls[0][1], expected_script)
        self.assertEqual(receipt["record_command"], expected_argv)
        self.assertEqual(receipt["record_command_script"], expected_script)
        self.assertTrue(any(command == record_calls[0] and timeout == 45
                            for command, _, timeout in fake.commands))
        self.assertFalse(any(arg in {"launch", "install", "push", "sync-data"}
                             for command, _, _ in fake.commands for arg in command))

    def test_multiple_or_changed_pid_refuses_and_preserves_failure_receipt(self):
        fake = FakeDevice(self.temp.name, pids=["1234 5678"])
        with patch.object(performance_capture, "Device", return_value=fake):
            with self.assertRaises(performance_capture.CaptureError) as caught:
                performance_capture.capture_cpu()
        self.assertIn("exactly one running PID", str(caught.exception))
        self.assertTrue((Path(self.temp.name) / caught.exception.receipt["profile_path"]).parent.joinpath("failure.txt").is_file())

        drifting = FakeDevice(self.temp.name, pids=["1234", "5678", "5678"])
        with patch.object(performance_capture, "Device", return_value=drifting):
            with self.assertRaises(performance_capture.CaptureError) as changed:
                performance_capture.capture_cpu()
        self.assertIn("PID changed", str(changed.exception))
        self.assertTrue(changed.exception.receipt["identity_stable"] is False)

        stopped = FakeDevice(self.temp.name, pids=[""])
        with patch.object(performance_capture, "Device", return_value=stopped):
            with self.assertRaisesRegex(performance_capture.CaptureError, "exactly one running PID"):
                performance_capture.capture_cpu()

        initial = {
            "serial": SERIAL, "package": PACKAGE, "apk_sha256": APK_HASH,
            "package_path": "/data/app/owned-lab", "build_key": "source-build-key",
            "storage": {"mode": "adopted"},
        }
        changed_apk = dict(initial, apk_sha256="b" * 64)
        changed_cohort = FakeDevice(self.temp.name, owned=[initial, changed_apk])
        with patch.object(performance_capture, "Device", return_value=changed_cohort):
            with self.assertRaisesRegex(performance_capture.CaptureError, "APK ownership/cohort changed"):
                performance_capture.capture_cpu()

    def test_unowned_or_nonforeground_package_refuses_without_profiling(self):
        for options, expected in [
            ({"owned": False}, "ownership"),
            ({"foreground": False}, "foreground activity"),
        ]:
            fake = FakeDevice(self.temp.name, **options)
            with patch.object(performance_capture, "Device", return_value=fake):
                with self.assertRaises(performance_capture.CaptureError) as caught:
                    performance_capture.capture_cpu()
            self.assertIn(expected, str(caught.exception))
            self.assertFalse(any(len(command) == 2 and command[0] == "shell"
                                 and command[1].startswith("simpleperf record ")
                                 for command, _, _ in fake.commands))
            self.assertTrue((Path(self.temp.name) / caught.exception.receipt["profile_path"]).parent.joinpath("failure.txt").is_file())

    def test_unavailable_system_simpleperf_refuses_without_guessing_tool_path(self):
        fake = FakeDevice(self.temp.name, profiler=False)
        with patch.object(performance_capture, "Device", return_value=fake):
            with self.assertRaises(performance_capture.CaptureError) as caught:
                performance_capture.capture_cpu()
        self.assertIn("simpleperf is unavailable", str(caught.exception))
        self.assertFalse(any(any("simpleperf record" in arg for arg in command)
                             for command, _, _ in fake.commands))

    def test_timeout_preserves_failure_and_does_not_remove_remote_partial_profile(self):
        import subprocess
        fake = FakeDevice(self.temp.name, record_error=subprocess.TimeoutExpired("adb shell simpleperf", 45))
        with patch.object(performance_capture, "Device", return_value=fake):
            with self.assertRaises(performance_capture.CaptureError) as caught:
                performance_capture.capture_cpu(duration_seconds=15)
        receipt = caught.exception.receipt
        self.assertIn("timed out", str(caught.exception).lower())
        self.assertTrue(receipt["remote_profile_preserved"].startswith("/data/local/tmp/lab-performance-capture-"))
        self.assertEqual(receipt["first_failure"]["phase"], "raw-profile-record")
        self.assertIn("timed out", receipt["raw_profile_error"].lower())
        self.assertNotIn("remote_profile_removed", receipt)
        self.assertTrue((Path(self.temp.name) / receipt["profile_path"]).parent.joinpath("failure.txt").is_file())
        self.assertFalse(any(command[0][:2] == ("shell", "rm") for command in fake.commands))

    def test_report_symbolization_failure_keeps_raw_capture_without_claiming_attribution(self):
        fake, receipt = self.run_capture(report_error=RuntimeError("unknown dso symbol"))
        self.assertTrue(receipt["success"])
        self.assertFalse(receipt["report_generated"])
        self.assertIn("unknown dso symbol", receipt["report_error"])
        self.assertEqual(receipt["first_failure"]["phase"], "symbol-report")
        self.assertTrue((Path(self.temp.name) / receipt["profile_path"]).is_file())
        self.assertTrue(receipt["remote_profile_removed"])

    def test_same_process_session_restart_or_foreground_loss_refuses_success(self):
        restarted = FakeDevice(self.temp.name)
        after_restart = dict(restarted.report, session=8)
        restarted._session_sequence = [restarted.report, after_restart]
        with patch.object(performance_capture, "Device", return_value=restarted):
            with self.assertRaisesRegex(performance_capture.CaptureError, "selection/session changed") as caught:
                performance_capture.capture_cpu()
        self.assertTrue((Path(self.temp.name) / caught.exception.receipt["profile_path"]).is_file())

        lost = FakeDevice(self.temp.name, foreground_sequence=[True, False])
        with patch.object(performance_capture, "Device", return_value=lost):
            with self.assertRaisesRegex(performance_capture.CaptureError, "not confirmed as the resumed") as caught:
                performance_capture.capture_cpu()
        self.assertTrue((Path(self.temp.name) / caught.exception.receipt["profile_path"]).is_file())

    def test_empty_or_missing_pull_preserves_remote_profile_and_fails(self):
        for mode in ("empty", "missing"):
            with self.subTest(mode=mode):
                fake = FakeDevice(self.temp.name, pull_mode=mode)
                with patch.object(performance_capture, "Device", return_value=fake):
                    with self.assertRaisesRegex(performance_capture.CaptureError, "non-empty local profile") as caught:
                        performance_capture.capture_cpu()
                receipt = caught.exception.receipt
                self.assertIn("remote_profile_preserved", receipt)
                self.assertNotIn("remote_profile_removed", receipt)

    def test_duration_and_label_validation_happens_before_device_construction(self):
        with patch.object(performance_capture, "Device", side_effect=AssertionError("must not construct")):
            for value in (0, 61, True, 1.5):
                with self.subTest(duration=value), self.assertRaises(ValueError):
                    performance_capture.capture_cpu(duration_seconds=value)
            for value in ("", "../bad", "a/b", "bad label", ".."):
                with self.subTest(label=value), self.assertRaises(ValueError):
                    performance_capture.capture_cpu(label=value)


if __name__ == "__main__":
    unittest.main()
