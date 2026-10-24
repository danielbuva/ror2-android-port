import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))

from session_memory_check import (
    as_session_one,
    check_session_memory,
    completed_name,
    growth_summary,
    parse_total_pss_kib,
    resource_samples,
)


def samples(start, after, probes=0):
    return [
        {"phase": "before-presentation", "managed": start, "liveCompletedProbes": probes},
        {"phase": "completed-after-reclaim", "gameObjects": 11, "textures": 44, "bundles": 1},
        {"phase": "completed-after-managed-collection", "managed": after, "reserved": after * 3},
    ]


class SessionMemoryCheckTests(unittest.TestCase):
    def test_session_view_requires_the_real_index(self):
        self.assertIsNone(as_session_one({"session": 2}, 3))
        self.assertIsNone(as_session_one(None, 1))
        report = {"session": 3, "phase": "complete"}
        view = as_session_one(report, 3)
        self.assertEqual(view, {"session": 1, "phase": "complete"})
        self.assertEqual(report["session"], 3)

    def test_completed_report_name_matches_runtime_writer(self):
        self.assertEqual(completed_name(4), "movement-completed-session-4.json")

    def test_pss_parser_accepts_both_dumpsys_layouts(self):
        self.assertEqual(parse_total_pss_kib("  TOTAL PSS:   812345   TOTAL RSS: 9"), 812345)
        self.assertEqual(parse_total_pss_kib("App Summary\n   TOTAL   794543   1200\n"), 794543)
        self.assertIsNone(parse_total_pss_kib("No process found for: x"))

    def test_resource_samples_keep_only_declared_fields(self):
        kept = resource_samples({"sessionResources": [{"phase": "x", "managed": 5, "bundleNames": ["a"]}, "bad"]})
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["managed"], 5)
        self.assertNotIn("bundleNames", kept[0])
        self.assertEqual(resource_samples(None), [])

    def test_growth_slope_excludes_first_session_warmup(self):
        observed = [
            {"session": 1, "samples": samples(1, 266), "menu_pss_kib": 900},
            {"session": 2, "samples": samples(266, 300, 1), "menu_pss_kib": 950},
            {"session": 3, "samples": samples(300, 330, 1), "menu_pss_kib": 1000},
            {"session": 4, "samples": samples(330, 360, 1), "menu_pss_kib": 1050},
        ]
        summary = growth_summary(observed)
        slope = summary["per_session_slope_from_session_2"]
        self.assertEqual(slope["managed_after_collection_bytes"], 30)
        self.assertEqual(slope["menu_pss_kib"], 50)
        self.assertEqual(summary["rows"][1]["live_completed_probes_at_start"], 1)
        self.assertEqual(summary["rows"][0]["game_objects_after_reclaim"], 11)

    def test_growth_slope_needs_two_later_points(self):
        summary = growth_summary([{"session": 1, "samples": samples(1, 5)}, {"session": 2, "samples": samples(5, 6)}])
        self.assertIsNone(summary["per_session_slope_from_session_2"]["managed_after_collection_bytes"])

    def test_refuses_bad_counts_and_unbound_apk_before_device_access(self):
        with self.assertRaises(ValueError):
            check_session_memory(sessions=2, expected_apk_sha256="0" * 64)
        with self.assertRaises(ValueError):
            check_session_memory(sessions=True)
        with self.assertRaises(ValueError):
            check_session_memory(sessions=33, expected_apk_sha256="0" * 64)
        with self.assertRaises(ValueError):
            check_session_memory(sessions=5, expected_apk_sha256=None)


if __name__ == "__main__":
    unittest.main()
