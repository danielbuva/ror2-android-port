import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import perf_report as perf


def fixture():
    samples = []
    for index in range(4):
        samples.append(
            dict(
                host_seconds=index,
                snapshot_utc=f"2026-01-01T00:00:0{index}Z",
                pacing_frames=1000 + 100 * index,
                pacing_total_ms=200000 + 2000 * index,
                pacing_over33=500 + 3 * index,
                pacing_over50=200 + index,
                frame_ms=10 * (index + 1),
                fps=100 / (index + 1),
                thermal_status=0,
            )
        )
    thermal = [
        dict(utc=f"20260101T00000{i}.000000Z", admission=False, all_zones_raw="cpu-0\t81000\t/private\ngpuss-0\t60000\t/private", battery=dict(celsius=35))
        for i in range(4)
    ]
    return dict(samples=samples, scope="synthetic"), thermal


class PerfReportTests(unittest.TestCase):
    def sustained(self, times):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return dict(
            samples=[
                dict(
                    host_seconds=seconds,
                    snapshot_utc=(start + timedelta(seconds=seconds)).isoformat(),
                    pacing_frames=1000 + 60 * min(seconds, 1200) + 30 * max(0, seconds - 1200),
                    pacing_total_ms=200000 + seconds * 1000,
                    pacing_over33=500 + min(seconds, 1200) * 0.6 + max(0, seconds - 1200) * 3,
                    pacing_over50=200 + max(0, seconds - 1200) * 0.6,
                )
                for seconds in times
            ]
        )

    def test_final_ten_minutes_distinguishes_slow_tail_from_whole_session(self):
        result = perf.analyze(self.sustained([0, 600, 1200, 1500, 1800]), [])
        tail = result["final_ten_minutes"]
        self.assertEqual(result["frame_window"]["average_fps"], 50)
        self.assertEqual(tail["frame_window"]["average_fps"], 30)
        self.assertEqual(tail["frame_window"]["frames"], 18000)
        self.assertEqual(tail["over33ms_percent"], 10)
        self.assertEqual(tail["over50ms_percent"], 2)
        self.assertEqual(tail["boundary_uncovered_seconds"], 0)
        self.assertIn("Final ten-minute coverage: 600.000/600 s", perf.markdown(result))

    def test_sparse_tail_uses_retained_endpoints_without_interpolation(self):
        result = perf.analyze(self.sustained([0, 1190, 1210, 1800]), [])
        tail = result["final_ten_minutes"]
        self.assertEqual(tail["start_host_seconds"], 1210)
        self.assertEqual(tail["observed_seconds"], 590)
        self.assertEqual(tail["boundary_uncovered_seconds"], 10)
        self.assertEqual(tail["frame_window"]["frames"], 17700)
        self.assertEqual(tail["over50ms_percent"], 2)

    def test_tail_without_two_observations_is_unavailable(self):
        result = perf.analyze(self.sustained([0, 1190, 1800]), [])
        self.assertIsNone(result["final_ten_minutes"]["frame_window"])
        self.assertEqual(result["final_ten_minutes"]["boundary_uncovered_seconds"], 600)
        self.assertIn("fewer than two retained observations", perf.markdown(result))

    def test_counter_window_and_proxy_percentiles_do_not_invent_frames(self):
        session, thermal = fixture()
        result = perf.analyze(session, thermal)
        self.assertEqual(result["frame_window"], dict(frames=300, mean_ms=20, average_fps=50, over33ms=9, over50ms=3))
        self.assertEqual(result["periodic_frame_mean_ms"], dict(samples=4, p50=25, p95=38.5, p99=39.7))
        self.assertIsNone(result["true_frame_time_percentiles_ms"])
        self.assertIsNone(result["throttling_onset_seconds"])
        self.assertIsNone(result["cpu_frame_ms"]["p50"])
        self.assertIn("Individual-frame p50/p95/p99: unavailable", perf.markdown(result))
        self.assertEqual(result["final_ten_minutes"]["observed_seconds"], 3)
        self.assertEqual(result["final_ten_minutes"]["boundary_uncovered_seconds"], 597)

    def test_admission_and_uncovered_gaps_are_not_thermal_exposure(self):
        session, thermal = fixture()
        thermal[1]["admission"] = True
        result = perf.analyze(session, thermal)
        self.assertEqual(result["thermal"]["gaps_over_one_second"], 1)
        self.assertEqual(result["thermal"]["time_above80_observed_seconds"], 1)
        self.assertEqual(result["thermal"]["peak_gpu_c"], 60)
        self.assertEqual(result["thermal"]["peak_cpu_c"], 81)

    def test_hal_status_is_not_causal_throttling_onset(self):
        session, thermal = fixture()
        session["samples"][1]["thermal_status"] = 1
        result = perf.analyze(session, thermal)
        self.assertEqual(result["first_nonzero_hal_status_seconds"], 1)
        self.assertIsNone(result["throttling_onset_seconds"])

    def test_counter_reset_and_stale_snapshot_refused(self):
        session, thermal = fixture()
        for key, value in (("pacing_frames", 0), ("pacing_total_ms", 0), ("pacing_over33", 0), ("snapshot_utc", session["samples"][0]["snapshot_utc"])):
            bad = copy.deepcopy(session)
            bad["samples"][2][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                perf.analyze(bad, thermal)

    def test_missing_thermal_is_unmeasured(self):
        session, _ = fixture()
        result = perf.analyze(session, [])
        self.assertEqual(result["thermal"]["samples"], 0)
        self.assertIsNone(result["thermal"]["peak_cpu_c"])
        self.assertEqual(result["thermal"]["boundary_uncovered_seconds"], 3)


if __name__ == "__main__":
    unittest.main()
