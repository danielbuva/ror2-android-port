"""Synthetic stage measurement contracts, without a phone or private inputs."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("phone_flow_lab", ROOT / "scripts/lab-installer-updates.py")
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)


class PhoneFlowTests(unittest.TestCase):
    def test_pss_is_one_numeric_total_not_a_true_peak(self):
        self.assertEqual(LAB.process_pss(b"TOTAL PSS: 123 TOTAL RSS: 456\n"), 123 * 1024)
        for value in (b"TOTAL PSS: -2", b"TOTAL PSS: unknown", b"TOTAL PSS: 1\nTOTAL PSS: 2", b"x" * 65537, "private-text"):
            self.assertIsNone(LAB.process_pss(value))

    def test_observation_does_not_query_unowned_or_replaced_apps(self):
        phone = LAB.Phone("synthetic-private", 1)
        with patch.object(phone, "package_hash") as identity, patch.object(phone, "shell") as shell:
            self.assertEqual(phone.flow_observation(), {"installer": {}, "alpha": {}})
            identity.assert_not_called()
            shell.assert_not_called()
        phone.owned_installer, phone.installer_hash = True, "a" * 64
        with patch.object(phone, "package_hash", return_value="b" * 64), patch.object(phone, "shell") as shell:
            self.assertEqual(phone.flow_observation(), {"installer": {}, "alpha": {}})
            shell.assert_not_called()

    def test_owned_observation_reads_fixed_package_and_actual_backing(self):
        phone = LAB.Phone("synthetic-private", 1)
        phone.owned_installer, phone.installer_hash = True, "a" * 64

        def shell(*args, **kwargs):
            if args == ("dumpsys", "battery"):
                return b"temperature: 281\n"
            if args[:3] == ("dumpsys", "meminfo", "-s"):
                self.assertEqual(args[3], LAB.PACKAGE)
                return b"private PID/name\nTOTAL PSS: 12 TOTAL RSS: 99\n"
            return b"Filesystem 1K-blocks Used Available Use% Mounted on\nprivate 200 100 100 50% /private\n"

        with (
            patch.object(phone, "package_hash", return_value=phone.installer_hash),
            patch.object(phone, "package_paths", return_value=["package:/private/base.apk"]),
        ):
            with patch.object(phone, "shell", side_effect=shell) as query:
                value = phone.flow_observation()
        self.assertEqual(value["installer"], {"pss_bytes": 12288, "code_free_bytes": 102400, "data_free_bytes": 102400})
        self.assertEqual(query.call_args_list[-2].args, ("run-as", LAB.PACKAGE, "df", "-k", "."))
        self.assertEqual(value["battery_temp_tenths_c"], 281)
        self.assertNotIn("private", json.dumps(value))

    def test_stage_sampling_is_throttled_numeric_and_honest_about_gaps(self):
        clock = [0]
        phone = Mock()
        phone.flow_observation.return_value = {"installer": {"pss_bytes": 120, "code_free_bytes": 400, "data_free_bytes": "private"}, "alpha": None}
        metrics = LAB.FlowMetrics(phone)
        with patch.object(LAB.time, "monotonic", side_effect=lambda: clock[0]):
            with metrics.stage("in-place-update"):
                for clock[0] in (1, 9, 10, 19, 25):
                    metrics.sample()
                clock[0] = 30
        result = metrics.report()
        row = result["stages"][0]
        self.assertEqual((row["elapsed_seconds"], row["samples"], row["largest_sample_gap_seconds"]), (30, 4, 15))
        self.assertEqual(row["packages"]["installer"]["sampled_max_pss_bytes"], 120)
        self.assertIsNone(row["packages"]["alpha"]["sampled_max_pss_bytes"])
        self.assertIsNone(row["packages"]["installer"]["storage_end"]["data_free_bytes"])
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(result["memory_scope"], "sampled-app-process-pss-not-true-peak")

    def test_optional_read_failure_preserves_failed_stage_and_original_error(self):
        phone = Mock()
        phone.flow_observation.side_effect = RuntimeError("private telemetry error")
        metrics = LAB.FlowMetrics(phone)
        with self.assertRaisesRegex(LAB.Failure, "^installer-update-error$"):
            with metrics.stage("baseline-install"):
                raise LAB.Failure("installer-update-error")
        report = metrics.report()
        self.assertFalse(report["stages"][0]["completed"])
        self.assertIsNone(report["stages"][0]["packages"]["installer"]["sampled_max_pss_bytes"])
        self.assertNotIn("private", json.dumps(report))

    def test_phone_flow_orders_all_stages_and_stops_after_forward_retention(self):
        phone = Mock()
        phone.occupied.return_value = False
        phone.flow_observation.return_value = {}
        phone.ui.return_value = ET.fromstring('<hierarchy><node text="TEST RELEASE SOURCE"/></hierarchy>')
        phone.installed.side_effect = [{"sha256": "first"}, {"sha256": "second"}]
        phone.attach_mock(Mock(), "passed")
        releases = {n: {"release.json": LAB.encoded({"version": "synthetic"})} for n in (1, 2)}
        phases = []
        phone.allow_visible_install_permission.side_effect = lambda: phases.append(LAB.CURRENT_PHASE)
        with patch.object(LAB, "prepare_artifacts", return_value=(Mock(), {}, b"key", releases, releases[2])):
            LAB.acceptance(phone, {}, Path("unused"), phone.passed, qualify_install_prompts=True, phone_flow=True)
        self.assertEqual([r["stage"] for r in phone.flow_metrics.report()["stages"]], list(LAB.FlowMetrics.STAGES))
        self.assertEqual(phases, ["baseline-N-install"])
        self.assertEqual(phone.installed.call_count, 2)
        self.assertEqual(phone.retention_witness.call_args.args, ("verify", {"sha256": "second"}))
        self.assertEqual([c.args[0] for c in phone.passed.call_args_list], [*LAB.PROMPT_CASES, *LAB.CASES[:2], "synthetic-phone-flow"])
        phone.await_install_permission.assert_not_called()

    def test_new_flow_mode_never_pregrants_and_cannot_run_inspection(self):
        for flag in ("--allow-test-installs", "--allow-test-notifications", "--host-only", "--inspect-state", "--inspect-ui-failure"):
            with patch.object(LAB, "read_context") as setup, redirect_stdout(io.StringIO()):
                self.assertEqual(LAB.main(["--qualify-phone-flow", flag]), 1)
                setup.assert_not_called()

    def test_second_denial_is_opted_in_only_for_owned_flow_after_prior_denial(self):
        phone = LAB.Phone("synthetic-private", 1)
        with patch.object(phone, "shell"), patch.object(LAB.time, "sleep"), patch.object(phone, "dismiss_notification_permission") as dismiss:
            phone.start()
            dismiss.assert_called_with()
            phone.flow_metrics = LAB.FlowMetrics(phone)
            phone.start()
            dismiss.assert_called_with()
            phone.notification_denied = True
            phone.start()
            dismiss.assert_called_with(repeat_denial=True)

    def test_reporting_failure_cannot_skip_cleanup_or_replace_first_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            phone = Mock()
            phone.cleanup.return_value = "verified-absent"
            metrics = Mock()
            metrics.report.side_effect = RuntimeError("private-report-failure")
            phone.flow_metrics = metrics
            output = io.StringIO()
            with patch.object(LAB, "ROOT", Path(temporary)), patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic"}):
                with patch.object(LAB, "read_context", return_value={}), patch.object(LAB, "Phone", return_value=phone):
                    with patch.object(LAB, "acceptance", side_effect=LAB.Failure("installer-update-error")), redirect_stdout(output):
                        self.assertEqual(LAB.main(["--qualify-phone-flow"]), 1)
            phone.cleanup.assert_called_once()
            self.assertIsNone(phone.flow_metrics)
            self.assertIn("reason=installer-update-error", output.getvalue())
            self.assertIn("PASS cleanup", output.getvalue())
            self.assertNotIn("same-key-rollback", output.getvalue())
            self.assertNotIn("private", output.getvalue())


if __name__ == "__main__":
    unittest.main()
