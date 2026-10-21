import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import baseline


class ProcessObservationTests(unittest.TestCase):
    def test_actual_shell_protocol_distinguishes_absence_and_errors(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX shell absent")
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "pidof"
            command.write_text('#!/bin/sh\nprintf "%s" "$FIXTURE_PID_OUT"\nprintf "%s" "$FIXTURE_PID_ERR" >&2\nexit "$FIXTURE_PID_EXIT"\n')
            command.chmod(0o700)
            cases = [
                (0, "123", "", "123"),
                (1, "", "", None),
                (0, "", "", "error"),
                (1, "", "denied", "error"),
                (127, "", "missing", "error"),
                (0, "123 456", "", "error"),
                (0, "123", "warning", "error"),
            ]
            for code, stdout, stderr, expected in cases:
                with self.subTest(code=code, stdout=stdout, stderr=stderr):

                    def execute(*args):
                        self.assertEqual(args[:2], ("sh", "-c"))
                        env = dict(os.environ, PATH=directory, FIXTURE_PID_OUT=stdout, FIXTURE_PID_ERR=stderr, FIXTURE_PID_EXIT=str(code))
                        result = subprocess.run([shell, "-c", args[2]], env=env, capture_output=True, text=True, timeout=5)
                        if result.returncode:
                            raise RuntimeError("Authored command refusal")
                        return result.stdout.strip()

                    device = Mock(sh=execute)
                    if expected == "error":
                        with self.assertRaises(RuntimeError):
                            baseline.process_pid(device)
                    else:
                        self.assertEqual(baseline.process_pid(device), expected)

    def test_empty_or_unknown_success_output_is_not_absence(self):
        for value in ("", "unknown", "pid:", "pid:１２３"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                baseline.process_pid(Mock(sh=Mock(return_value=value)))

    def test_report_missing_partial_and_failed_reads_are_separate(self):
        device = Mock(sh=Mock(return_value=".\n.."))
        self.assertIsNone(baseline.current_report(device, "/owned", "/owned/report.json"))
        self.assertEqual(device.sh.call_count, 1)
        device.sh = Mock(side_effect=[".\n..\nreport.json", "{"])
        self.assertIsNone(baseline.current_report(device, "/owned", "/owned/report.json"))
        device.sh = Mock(side_effect=[".\n..\nreport.json", RuntimeError("Authored read failure")])
        with self.assertRaisesRegex(RuntimeError, "read failure"):
            baseline.current_report(device, "/owned", "/owned/report.json")
        for listing in ("", ".", "..", "report.json"):
            with self.subTest(listing=listing), self.assertRaises(RuntimeError):
                baseline.runtime_files(Mock(sh=Mock(return_value=listing)), "/owned")


class FixtureDevice:
    """Authored device protocol; never starts ADB or reads a real receipt."""

    def __init__(self, *, failure=None, stage_exit=False):
        self.failure = failure
        self.stage_exit = stage_exit
        self.settings = {"storage_mode": "internal", "sleep_display_when_idle": True}
        self.calls = []
        self.selector = False
        self.push_attempted = False
        self.running = False
        self.launched = False
        self.report_present = False
        self.reads = 0
        self.pid = "123"
        self.selector_name = "movement-batch-selection.json"
        self.report_name = "movement-batch-" + baseline.SPINE_ID + ".json"

    def owned(self):
        return {"storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk", "apk_sha256": "a" * 64}

    def storage(self):
        return {"mode": "internal", "uuid": None}

    def read_receipt(self, name):
        return {"persistentDataPath": "/owned/runtime"}

    def fail(self, check, message):
        if check:
            raise RuntimeError(message)
        return ""

    def sh(self, *args, check=True):
        self.calls.append((args, check))
        if self.failure == "selector-observation" and not self.push_attempted and args[0] in ("ls", "sh"):
            return self.fail(check, "Authored selector transport failure")
        if args[0] == "ls":
            if self.failure == "empty-directory" and not self.push_attempted:
                return ""
            return "\n".join([".", "..", *([self.selector_name] if self.selector else []), *([self.report_name] if self.report_present else [])])
        if args[:2] == ("sh", "-c") and "test -e" in args[2]:
            return "present" if self.selector else ""
        if args[0] == "pidof" or args[:2] == ("sh", "-c"):
            if self.failure == "process-observation" and self.running:
                return self.fail(check, "Authored process transport failure")
            if args[0] == "pidof":
                return self.pid if self.running else ""
            return "pid:" + self.pid if self.running else "absent"
        if args[0] == "rm":
            if args[-1].endswith(self.selector_name):
                if self.failure == "remove-error":
                    return self.fail(check, "Authored selector removal failure")
                if self.failure != "remove-no-effect":
                    self.selector = False
            else:
                self.report_present = False
            return ""
        if args[:2] == ("am", "force-stop"):
            if self.failure == "stop-error":
                return self.fail(check, "Authored process stop failure")
            if self.failure != "stop-no-effect":
                self.running = False
            return ""
        if args[0] == "cat":
            self.reads += 1
            if self.failure == "report-read":
                return self.fail(check, "Authored report transport failure")
            next_stage = self.stage_exit and self.reads >= 2
            return json.dumps(
                {
                    "pid": "999" if self.failure == "stale-final" and self.reads >= 2 else self.pid,
                    "phase": "integrated-world-playing",
                    "error": "",
                    "firstFailure": "",
                    "world": {"seconds": 210 if next_stage else 35.2},
                    "stage": {"scene": "fixture-next-stage" if next_stage else "lakes"},
                    "stageProgress": {"transitions": 1 if next_stage else 0, "enteredAt": 200 if next_stage else 0},
                    "debugAcceleration": {"everAssisted": True},
                    "profile": {"appliedRuns": 13},
                }
            )
        raise AssertionError("Unknown authored shell operation")

    def cmd(self, *args):
        self.calls.append((args, True))
        self.push_attempted = True
        self.selector = True
        if self.failure == "push-timeout":
            raise subprocess.TimeoutExpired("authored push", 1)

    def launch(self):
        self.calls.append((("launch",), True))
        self.launched = self.running = self.report_present = True
        return {"pid": self.pid}

    def collect(self, *args):
        self.calls.append((("collect", *args), True))

    def display(self, awake):
        self.calls.append((("display", awake), True))
        if self.failure == "sleep-error":
            raise RuntimeError("Authored display failure")
        return self.failure != "sleep-false"


class BaselineRunnerProtocolTests(unittest.TestCase):
    def invoke(self, device):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        work = Path(temporary.name) / "work"
        with (
            patch.object(baseline, "WORK", work),
            patch.object(baseline, "now", return_value="authored-attempt"),
            patch.object(baseline, "Device", return_value=device),
            patch.object(baseline, "attempt_from_installed", return_value="authored-attempt"),
            patch.object(baseline, "read", return_value={"apk_sha256": "a" * 64}),
            patch.object(baseline.time, "monotonic", side_effect=itertools.count()),
            patch.object(baseline.time, "sleep"),
        ):
            return baseline.check_baseline(stage_exit=device.stage_exit)

    def test_both_modes_pass_with_verified_teardown(self):
        for stage_exit in (False, True):
            with self.subTest(stage_exit=stage_exit):
                device = FixtureDevice(stage_exit=stage_exit)
                result = self.invoke(device)
                self.assertTrue(result["success"], result)
                self.assertEqual(result["cleanup"], {"selector_absent": True, "process_absent": True, "sleep_requested": True, "display_asleep": True})
                self.assertFalse(device.running or device.selector)
                self.assertFalse(any(check is False for _, check in device.calls))

    def test_selector_transport_failure_does_not_overwrite_or_launch(self):
        device = FixtureDevice(failure="selector-observation")
        device.selector = True
        with self.assertRaisesRegex(RuntimeError, "selector transport failure"):
            self.invoke(device)
        self.assertTrue(device.selector)
        self.assertFalse(device.push_attempted or device.launched)
        self.assertFalse(any(args[0] in ("rm", "display") for args, _ in device.calls))

    def test_existing_selector_and_empty_directory_refuse_before_writes(self):
        for failure in (None, "empty-directory"):
            device = FixtureDevice(failure=failure)
            device.selector = True
            with self.subTest(failure=failure), self.assertRaises(RuntimeError):
                self.invoke(device)
            self.assertFalse(device.push_attempted or device.launched)
            self.assertTrue(device.selector)

    def test_checked_observation_and_stale_report_fail_with_cleanup(self):
        for failure in ("process-observation", "report-read", "stale-final"):
            with self.subTest(failure=failure):
                device = FixtureDevice(failure=failure)
                with self.assertRaises(RuntimeError):
                    self.invoke(device)
                self.assertFalse(device.running or device.selector)
                self.assertIn((("display", False), True), device.calls)

    def test_cleanup_errors_cannot_return_success_and_all_steps_are_attempted(self):
        for failure in ("remove-error", "remove-no-effect", "stop-error", "stop-no-effect", "sleep-error", "sleep-false"):
            for stage_exit in (False, True):
                with self.subTest(failure=failure, stage_exit=stage_exit):
                    device = FixtureDevice(failure=failure, stage_exit=stage_exit)
                    with self.assertRaises(RuntimeError):
                        self.invoke(device)
                    self.assertTrue(any(args[:2] == ("am", "force-stop") for args, _ in device.calls))
                    self.assertIn((("display", False), True), device.calls)

    def test_remote_push_then_local_timeout_still_removes_own_selector(self):
        device = FixtureDevice(failure="push-timeout")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.invoke(device)
        self.assertTrue(device.push_attempted)
        self.assertFalse(device.selector or device.running)
        self.assertIn((("display", False), True), device.calls)

    def test_first_operation_failure_survives_a_later_cleanup_failure(self):
        class BothFailures(FixtureDevice):
            def sh(self, *args, check=True):
                if args[0] == "cat":
                    raise RuntimeError("Authored first report failure")
                return super().sh(*args, check=check)

        device = BothFailures(failure="remove-error")
        with self.assertRaisesRegex(RuntimeError, "first report failure.*cleanup failed.*selector removal failure"):
            self.invoke(device)
        self.assertFalse(device.running)
        self.assertIn((("display", False), True), device.calls)
