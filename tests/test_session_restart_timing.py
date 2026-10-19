import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next(parent for parent in HERE.parents if (parent / "tests/test_session_cleanup_check.py").is_file())
CANDIDATE_LAB = HERE.parents[1] / "scripts/lab"
if not CANDIDATE_LAB.is_dir():
    CANDIDATE_LAB = ROOT / "scripts/lab"
sys.path.insert(0, str(ROOT / "scripts/lab"))
sys.path.insert(0, str(CANDIDATE_LAB))

from session_cleanup_check import HostMilestoneTiming


class HostMilestoneTimingTests(unittest.TestCase):
    def test_emits_observed_offsets_and_named_intervals(self):
        timing = HostMilestoneTiming(clock=lambda: 0.0)
        timing.start(observed_at=100.0)
        timing.mark("first_menu_observed", 103.25)
        timing.mark("first_world_observed", 106.0)
        timing.mark("settings_open_request_sent", 120.0)
        timing.mark("end_run_request_sent", 121.5)
        timing.mark("completed_cleanup_observed", 126.0)
        timing.mark("second_menu_observed", 127.0)
        timing.mark("session2_menu_start_request_sent", 130.0)
        timing.mark("second_world_healthy_observed", 141.0)
        report = timing.report()
        self.assertEqual(report["events"]["first_menu_observed"], 3.25)
        self.assertEqual(report["events"]["end_run_request_sent"], 21.5)
        self.assertEqual(report["intervals"]["first_world_to_end_run_request"], 15.5)
        self.assertEqual(report["intervals"]["end_run_request_to_cleanup_observed"], 4.5)
        self.assertEqual(report["intervals"]["cleanup_to_second_menu"], 1.0)
        self.assertEqual(report["intervals"]["second_menu_to_start_request"], 3.0)
        self.assertEqual(report["intervals"]["menu_start_request_to_second_world"], 11.0)
        self.assertEqual(report["intervals"]["first_world_to_second_world"], 35.0)

    def test_unobserved_milestones_and_intervals_stay_null(self):
        timing = HostMilestoneTiming(clock=lambda: 5.0)
        timing.start()
        timing.mark("first_world_observed", 7.0)
        report = timing.report()
        self.assertIsNone(report["events"]["first_menu_observed"])
        self.assertEqual(report["events"]["first_world_observed"], 2.0)
        self.assertIsNone(report["events"]["session2_menu_start_request_sent"])
        self.assertIsNone(report["intervals"]["launch_to_first_menu"])
        self.assertIsNone(report["intervals"]["second_menu_to_start_request"])

    def test_out_of_order_observations_do_not_become_negative_durations(self):
        timing = HostMilestoneTiming(clock=lambda: 0.0)
        timing.start(observed_at=10.0)
        timing.mark("second_menu_observed", 12.0)
        timing.mark("completed_cleanup_observed", 13.0)
        self.assertIsNone(timing.report()["intervals"]["cleanup_to_second_menu"])

    def test_duplicate_marks_keep_first_observation(self):
        timing = HostMilestoneTiming(clock=lambda: 0.0)
        timing.start(observed_at=10.0)
        timing.mark("first_world_observed", 12.0)
        timing.mark("first_world_observed", 18.0)
        self.assertEqual(timing.report()["events"]["first_world_observed"], 2.0)

    def test_marks_before_origin_do_not_create_invented_elapsed_values(self):
        timing = HostMilestoneTiming(clock=lambda: 20.0)
        timing.mark("first_world_observed", 21.0)
        timing.start(observed_at=22.0)
        report = timing.report()
        self.assertIsNone(report["events"]["first_world_observed"])
        self.assertIsNone(report["intervals"]["launch_to_first_world"])


    def test_fake_same_process_run_records_only_observed_runtime_milestones(self):
        import importlib.util

        tests_dir = ROOT / "tests"
        sys.path.insert(0, str(tests_dir))
        spec = importlib.util.spec_from_file_location("session_cleanup_fixtures", tests_dir / "test_session_cleanup_check.py")
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        reports = [
            fixtures.ordinary_start_report(),
            fixtures.live_report(session=1),
            fixtures.session_one_defeat_report(),
            fixtures.live_report(session=2, world={"seconds": 0.0, "ready": False, "health": 0.0, "diagnosticInputEver": False}),
            fixtures.live_report(session=2),
        ]
        temp, _device, result, error, evidence = fixtures.run_fake_check(reports, clock_step=1.0)
        try:
            self.assertIsNone(error)
            self.assertTrue(result["success"])
            timing = result["host_timing"]
            self.assertIsNotNone(timing["events"]["launch_return"])
            self.assertIsNotNone(timing["events"]["first_menu_observed"])
            self.assertIsNotNone(timing["events"]["first_world_observed"])
            self.assertIsNotNone(timing["events"]["loss_restart_tap_sent"])
            self.assertIsNotNone(timing["events"]["completed_cleanup_observed"])
            self.assertIsNotNone(timing["events"]["second_world_healthy_observed"])
            self.assertIsNone(timing["events"]["end_run_request_sent"])
            self.assertIsNone(timing["events"]["second_menu_observed"])
            saved = __import__("json").loads((evidence / "result.json").read_text())
            self.assertEqual(saved["host_timing"], timing)
        finally:
            temp.cleanup()

    def test_failed_completion_contract_keeps_original_failure_precedence(self):
        import importlib.util

        tests_dir = ROOT / "tests"
        sys.path.insert(0, str(tests_dir))
        spec = importlib.util.spec_from_file_location("session_cleanup_failure_fixtures", tests_dir / "test_session_cleanup_check.py")
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        reports = [
            fixtures.ordinary_start_report(),
            fixtures.live_report(session=1, world={"seconds": 60.0, "ready": True, "health": 100.0, "diagnosticInputEver": True}),
            fixtures.live_report(session=2),
        ]
        temp, _device, result, error, evidence = fixtures.run_fake_check(
            reports, ending="abandon", completed_override="{malformed", clock_step=0.1
        )
        try:
            self.assertIsNone(result)
            self.assertIsNotNone(error)
            saved = __import__("json").loads((evidence / "result.json").read_text())
            self.assertEqual(saved["stop"], "completed-session-cleanup-failed")
            self.assertEqual(saved["first_failure"], "completed-session-cleanup-failed")
            self.assertIn("no current-launch completed-session report", saved["failures"])
            self.assertNotIn("abandon-to-restart-observations-incomplete", saved["failures"])
        finally:
            temp.cleanup()

    def test_checker_wires_timings_to_report_and_real_observation_points(self):
        source = (CANDIDATE_LAB / "session_cleanup_check.py").read_text()
        self.assertIn('host_timing.start()', source)
        for milestone in (
            "first_menu_observed",
            "first_world_observed",
            "settings_open_request_sent",
            "end_run_request_sent",
            "completed_cleanup_observed",
            "second_menu_observed",
            "session2_menu_start_request_sent",
            "loss_restart_tap_sent",
            "second_world_healthy_observed",
        ):
            self.assertIn(f'host_timing.mark("{milestone}")', source)
        self.assertIn('"host_timing": host_timing.report()', source)
        self.assertIn('"origin": "host observation immediately after device.launch() returns"', source)
        self.assertIn('"second_world_healthy_observed": "session-2 report passed session2_ready"', source)


if __name__ == "__main__":
    unittest.main()
