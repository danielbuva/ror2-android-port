"""Synthetic-only adapter contracts: no Android, APK, Unity or private evidence."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/lab/session_memory_batch.py"
APK = "a" * 64


class SessionMemoryBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / "work"
        self.work.mkdir()
        self.events = []
        self.selector = (None, None)
        self.env = dict(LAB_DEVICE_SERIAL="synthetic-device", LAB_RUN_ID="123")
        self.receipt = "work/coordination/dots-memory/baseline.json"
        self.lease = self.root / ".local/orchestrator/leases/synthetic-device"
        self.lease.mkdir(parents=True)
        self.write(self.lease / "lab-runner.json", dict(workstream="lab-runner", pid=os.getppid(), run="123"))
        self.common = types.ModuleType("common")
        self.common.WORK = self.work
        self.common.read = lambda p: json.loads(Path(p).read_text())
        self.common.write = self.write
        self.common.sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
        context = types.ModuleType("device_context")
        context.command_selectors = lambda: self.selector
        context.set_command_selector = self.select
        context.validate_serial = self.validate_serial
        installed = types.ModuleType("installed_attempt")
        installed.validate_expected_apk_sha256 = self.validate_hash
        installed.attempt_from_installed = lambda r: "private-attempt"
        self.owner = types.ModuleType("alpha_stability_batch")
        self.owner.BATCH_DEADLINE_SECONDS = 10800
        self.owner.DEVICE_FREE_RESERVE_BYTES = 15
        self.device = types.SimpleNamespace(owned=lambda: {"apk_sha256": APK}, storage=lambda: {"mode": "internal", "internal": {"free_bytes": 20}})
        self.owner._device = lambda serial: self.record("device", self.device)
        self.owner._idle_readback = lambda d, expected: self.record("identity", {"apk_sha256": expected})
        self.owner._terminal_readback = lambda serial, expected: self.record("terminal", {"apk_sha256": expected, "oled_asleep": True})
        self.owner._host_capture_budget = lambda root: self.record("host-budget", {"free_bytes": 40, "required_free_bytes": 29})
        self.owner._require_capture_capacity = lambda d: self.record("device-capacity")
        self.thermal = types.SimpleNamespace(
            error=None,
            peak_cpu_gpu_celsius=84.0,
            time_above_80_seconds=4.0,
            cool=lambda: self.record("cool"),
            start=lambda: self.record("start"),
            finish=lambda: self.record("finish"),
            launch=lambda d: self.record("launch"),
        )
        self.owner._GameThermalOwner = lambda *args: self.thermal
        memory = types.ModuleType("session_memory_check")
        memory.check_session_memory = self.series
        modules = dict(common=self.common, device_context=context, installed_attempt=installed, alpha_stability_batch=self.owner, session_memory_check=memory)
        patcher = mock.patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location("synthetic_session_memory_batch", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.slope = 100000
        self.extra = {}

    def record(self, event, result=None):
        self.events.append(event)
        return result

    def write(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def select(self, cli, env):
        self.selector = (cli, env)

    @staticmethod
    def validate_serial(value):
        if value != "synthetic-device":
            raise ValueError("missing synthetic serial")
        return value

    @staticmethod
    def validate_hash(value):
        if value != APK:
            raise ValueError("bad hash")
        return value

    def series(self, **kwargs):
        self.record("series")
        self.series_options = kwargs
        kwargs["_launch"](self.device)
        snapshots = {str(i): {"file": f"session-{i}-private.snap", "sha256": "b" * 64, "bytes": 40} for i in (2, 4)} if kwargs["memory_snapshots"] else {}
        raw = dict(
            success=True,
            apk_sha256=APK,
            sessions_observed=kwargs["sessions"],
            runtime_errors=[],
            failures=[],
            memory_snapshots=snapshots,
            growth=dict(
                rows=[dict(managed_at_start=100 + i) for i in range(kwargs["sessions"])],
                final_menu_samples=[dict(phase="before-presentation", managed=200)],
                per_session_slope_from_session_2=dict(managed_before_presentation_bytes=self.slope),
            ),
        )
        raw.update(self.extra)
        evidence = "work/device/synthetic-device/experiments/session-memory/synthetic"
        self.write(self.root / evidence / "result.json", raw)
        print("PRIVATE content should only reach owner-output.log")
        return dict(success=True, evidence=evidence)

    def run_mode(self, mode="capture"):
        return self.module.run(mode, APK, 6, receipt=self.receipt, environ=self.env)

    def test_capture_delegates_exact_series_and_separate_scope(self):
        result = self.run_mode()
        self.assertTrue(result["success"])
        self.assertEqual(self.series_options["sessions"], 6)
        self.assertTrue(self.series_options["memory_snapshots"])
        self.assertNotIn("root_walk", self.series_options)
        self.assertFalse(result["memory_bound_pass"])
        self.assertEqual(result["snapshot_count"], 2)
        self.assertEqual(self.events, ["device", "identity", "host-budget", "device-capacity", "cool", "start", "series", "launch", "finish", "terminal"])
        pointer = self.common.read(self.root / self.receipt)
        self.assertEqual(set(pointer["memory_snapshots"]), {"2", "4"})
        self.assertEqual(pointer["apk_sha256"], APK)
        self.assertEqual(self.selector, (None, None))
        self.assertTrue(self.lease.exists())  # Only the outer runner releases it.

    def test_measure_omits_capture_and_reports_bound(self):
        result = self.run_mode("measure")
        self.assertTrue(result["memory_bound_pass"])
        self.assertFalse(self.series_options["memory_snapshots"])
        self.assertNotIn("host-budget", self.events)
        self.assertEqual(self.common.read(self.root / self.receipt)["memory_snapshots"], {})

    def test_positive_residual_is_not_a_bound(self):
        self.slope = 600000
        result = self.run_mode("measure")
        self.assertTrue(result["success"])
        self.assertFalse(result["memory_bound_pass"])
        self.assertEqual(result["managed_menu_slope_bytes_per_session"], 600000)

    def test_missing_menu_point_cannot_pass_bound(self):
        self.extra["growth"] = dict(rows=[], final_menu_samples=[], per_session_slope_from_session_2=dict(managed_before_presentation_bytes=-20))
        self.assertFalse(self.run_mode("measure")["memory_bound_pass"])

    def test_preflight_never_launches_or_runs_sessions(self):
        result = self.run_mode("preflight")
        self.assertTrue(result["success"])
        self.assertNotIn("start", self.events)
        self.assertNotIn("series", self.events)
        self.assertNotIn("finish", self.events)
        self.assertIn("terminal", self.events)

    def test_wrong_lease_is_refused_before_device_access(self):
        self.write(self.lease / "lab-runner.json", dict(workstream="other", pid=os.getppid(), run="123"))
        result = self.run_mode()
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "runner-context")
        self.assertEqual(self.events, [])

    def test_existing_result_is_preserved(self):
        path = self.work / "coordination/session-memory-batch/123/result.json"
        self.write(path, {"sentinel": "original"})
        self.assertFalse(self.run_mode()["success"])
        self.assertEqual(self.common.read(path), {"sentinel": "original"})
        self.assertEqual(self.events, [])

    def test_identity_refusal_does_not_start_or_cleanup_foreign_package(self):
        self.owner._idle_readback = mock.Mock(side_effect=RuntimeError("private package path and identifier"))
        result = self.run_mode()
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "installed-identity")
        self.assertNotIn("terminal", self.events)
        self.assertNotIn("cool", self.events)
        self.assertNotIn("private", json.dumps(result))

    def test_thermal_cancel_finishes_and_verifies_terminal_state(self):
        def fail():
            self.thermal.error = "CPU/GPU thermal zone stayed above 95 C for three seconds: private-zone"
            raise RuntimeError(self.thermal.error)

        self.thermal.start = fail
        result = self.run_mode()
        self.assertFalse(result["success"])
        self.assertEqual(result["thermal_stop_reason"], "cpu-gpu-sustained-limit")
        self.assertIn("finish", self.events)
        self.assertIn("terminal", self.events)
        self.assertNotIn("private-zone", json.dumps(result))
        self.assertFalse(self.common.read(self.root / self.receipt)["success"])

    def test_failed_terminal_verification_publishes_failed_receipt(self):
        self.owner._terminal_readback = mock.Mock(side_effect=RuntimeError("private path"))
        result = self.run_mode()
        self.assertFalse(result["success"])
        self.assertFalse(result["terminal_idle_verified"])
        self.assertFalse(self.common.read(self.root / self.receipt)["success"])

    def test_explicit_receipt_is_never_overwritten(self):
        self.write(self.root / self.receipt, {"sentinel": "original"})
        self.assertFalse(self.run_mode()["success"])
        self.assertEqual(self.common.read(self.root / self.receipt), {"sentinel": "original"})
        self.assertEqual(self.events, [])

    def test_receipt_cannot_escape_ignored_coordination(self):
        self.receipt = "work/coordination/../../outside.json"
        self.assertFalse(self.run_mode()["success"])
        self.assertEqual(self.events, [])

    def test_runner_work_symlink_is_an_authorized_boundary(self):
        checkout = self.root / "runner-checkout"
        checkout.mkdir()
        (checkout / "work").symlink_to(self.work, target_is_directory=True)
        self.common.WORK = checkout / "work"
        result = self.run_mode()
        self.assertTrue(result["success"])
        receipt = self.common.read(self.root / self.receipt)
        self.assertEqual(receipt["stage_evidence"], "work/device/synthetic-device/experiments/session-memory/synthetic")
        self.assertTrue(receipt["success"])

    def test_nested_receipt_symlink_is_not_authorized(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.work / "coordination").mkdir()
        (self.work / "coordination/dots-memory").symlink_to(outside, target_is_directory=True)
        self.assertFalse(self.run_mode()["success"])
        self.assertEqual(self.events, [])
        self.assertEqual(list(outside.iterdir()), [])

    def test_failed_measure_teardown_revokes_bound(self):
        self.owner._terminal_readback = mock.Mock(side_effect=RuntimeError("private path"))
        result = self.run_mode("measure")
        self.assertFalse(result["success"])
        self.assertFalse(result["memory_bound_pass"])

    def test_finish_failure_is_a_supervision_failure(self):
        self.thermal.finish = mock.Mock(side_effect=RuntimeError("Thermal stop worker failed to terminate"))
        result = self.run_mode()
        self.assertFalse(result["success"])
        self.assertEqual(result["thermal_stop_reason"], "supervision-failed")
        self.assertIn("terminal", self.events)

    def test_raw_owner_output_never_reaches_stdout(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            result = self.run_mode()
        self.assertEqual(stream.getvalue(), "")
        public = json.dumps(result)
        for private in ("synthetic-device", "private-attempt", "PRIVATE", str(self.root), "session-2-private.snap"):
            self.assertNotIn(private, public)
        self.assertIn("PRIVATE", (self.work / "coordination/session-memory-batch/123/owner-output.log").read_text())

    def inspection_fixture(self, *, first_failure="session 4: ready world does not report a living player with positive maxHealth"):
        self.evidence = "work/device/synthetic-device/experiments/session-memory/synthetic-failure"
        self.owner_result = self.root / self.evidence / "result.json"
        self.failed_series = dict(
            success=False,
            apk_sha256=APK,
            attempt="private-attempt",
            stop="abandon-observation-contract-failed",
            first_failure=first_failure,
            sessions_requested=6,
            sessions_observed=3,
            runtime_errors=[],
            failures=["stopped", "partial"],
            growth=dict(
                rows=[dict(session=i, managed_at_start=100 + i, managed_after_collection=200 + i, menu_pss_kib=300 + i) for i in (1, 2, 3)],
                final_menu_samples=[],
                per_session_slope_from_session_2=dict(managed_before_presentation_bytes=1),
            ),
        )
        self.failed_receipt = dict(
            success=False,
            mode="measure",
            apk_sha256=APK,
            attempt_sha256=hashlib.sha256(b"private-attempt").hexdigest(),
            sessions_requested=6,
            error="Session memory check failed (" + first_failure + "); see " + self.evidence,
        )
        self.write(self.owner_result, self.failed_series)
        self.write(self.root / self.receipt, self.failed_receipt)
        return self.common.sha(self.root / self.receipt)

    def inspect_fixture(self, digest):
        return self.module.inspect_receipt(self.receipt, digest, APK)

    def test_inspect_reports_failed_series_without_writes_or_device_calls(self):
        digest = self.inspection_fixture()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with mock.patch.object(self.common, "write", side_effect=AssertionError("inspection must not write")):
            result = self.inspect_fixture(digest)
        self.assertTrue(result["success"])
        self.assertFalse(result["original_series_success"])
        self.assertFalse(result["original_receipt_success"])
        self.assertTrue(result["diagnostic_only"])
        self.assertFalse(result["acceptance_available"])
        self.assertFalse(result["memory_bound_pass"])
        self.assertEqual(result["sessions_observed"], 3)
        self.assertEqual(result["failed_session"], 4)
        self.assertEqual(result["first_authored_reason"], "ready world does not report a living player with positive maxHealth")
        self.assertEqual(result["session_samples"][1]["managed_at_start_bytes"], 102)
        self.assertEqual(result["original_report_sha256"], digest)
        self.assertEqual(result["owner_result_sha256"], self.common.sha(self.owner_result))
        self.assertEqual(self.events, [])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_inspect_unknown_private_reason_is_hash_only(self):
        secret = "session 4: private-field-value /private/path"
        digest = self.inspection_fixture(first_failure=secret)
        result = self.inspect_fixture(digest)
        self.assertTrue(result["success"])
        self.assertIsNone(result["first_authored_reason"])
        self.assertEqual(result["first_failure_sha256"], hashlib.sha256(secret.encode()).hexdigest())
        public = json.dumps(result)
        for private in ("private-field-value", "/private/path", "synthetic-device", "private-attempt", str(self.root), self.evidence):
            self.assertNotIn(private, public)

    def test_inspect_receipt_digest_mismatch_refuses_before_owner_read(self):
        self.inspection_fixture()
        self.owner_result.unlink()
        result = self.inspect_fixture("c" * 64)
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "receipt-hash")

    def test_inspect_attempt_link_mismatch_refuses(self):
        digest = self.inspection_fixture()
        self.failed_series["attempt"] = "another-private-attempt"
        self.write(self.owner_result, self.failed_series)
        result = self.inspect_fixture(digest)
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "owner-provenance")

    def test_inspect_apk_link_mismatch_refuses(self):
        digest = self.inspection_fixture()
        self.failed_series["apk_sha256"] = "d" * 64
        self.write(self.owner_result, self.failed_series)
        result = self.inspect_fixture(digest)
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "owner-provenance")

    def test_inspect_no_recorded_owner_path_does_not_search(self):
        self.inspection_fixture()
        self.failed_receipt["error"] = "failure without an owner result reference"
        self.write(self.root / self.receipt, self.failed_receipt)
        result = self.inspect_fixture(self.common.sha(self.root / self.receipt))
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "owner-evidence-reference")

    def test_inspect_recorded_path_cannot_escape_session_evidence(self):
        self.inspection_fixture()
        self.failed_receipt["error"] = "Session memory check failed (private); see work/config"
        self.write(self.root / self.receipt, self.failed_receipt)
        result = self.inspect_fixture(self.common.sha(self.root / self.receipt))
        self.assertFalse(result["success"])
        self.assertEqual(result["failure_phase"], "owner-evidence-reference")

    def test_inspect_cli_needs_no_runner_or_device_environment(self):
        digest = self.inspection_fixture()
        stream = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(stream):
            code = self.module.main(["inspect", "--receipt", self.receipt, "--expected-receipt-sha256", digest, "--expected-apk-sha256", APK])
        self.assertEqual(code, 0)
        result = json.loads(stream.getvalue())
        self.assertFalse(result["original_series_success"])
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
