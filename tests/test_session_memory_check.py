import sys
import hashlib
import json
import tempfile
from unittest import mock
import unittest
from pathlib import Path
from contextlib import ExitStack

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))

from session_memory_check import (
    as_session_one,
    check_session_memory,
    collect_memory_snapshot,
    memory_snapshot_file,
    completed_name,
    growth_summary,
    parse_total_pss_kib,
    resource_samples,
)
import session_memory_check as memory


def samples(start, after, probes=0):
    return [
        {"phase": "before-presentation", "managed": start, "liveCompletedProbes": probes},
        {"phase": "completed-after-reclaim", "gameObjects": 11, "textures": 44, "bundles": 1},
        {"phase": "completed-after-managed-collection", "managed": after, "reserved": after * 3},
    ]


class SessionMemoryCheckTests(unittest.TestCase):
    def test_runtime_error_retains_only_matching_current_report_before_stopping(self):
        for report_pid in ("123", "999"):
            with tempfile.TemporaryDirectory() as temporary, self.subTest(report_pid=report_pid), ExitStack() as stack:
                root = Path(temporary)
                out = root / "evidence"
                device = mock.Mock()
                device.settings = {"storage_mode": "internal"}
                device.owned.return_value = {"storage": {"mode": "internal"}, "package_path": "/data/app/fixture/base.apk"}
                device.storage.return_value = {"mode": "internal"}
                device.read_receipt.return_value = {"persistentDataPath": "/fixture/Android/data/dev.ror2lab.arm64/files"}
                device.evidence_directory.return_value = out
                device.launch.return_value = {"pid": "123"}
                device.sh.return_value = "runtime error fixture"
                report = {
                    "pid": int(report_pid),
                    "attempt": "fixture",
                    "id": memory.SPINE_ID,
                    "session": 1,
                    "phase": "fixture-loading",
                    "selectedSurvivor": "Commando",
                    "world": {"lightningStakes": [{"finiteSnapshot": False}]},
                }
                replacements = {
                    "WORK": root / "work",
                    "SessionCleanupDevice": mock.Mock(return_value=device),
                    "bind_installed_apk": mock.Mock(return_value=("0" * 64, "fixture")),
                    "attempt_from_installed": mock.Mock(return_value="fixture"),
                    "survivor_identity_failures": mock.Mock(return_value=[]),
                    "runtime_stop": mock.Mock(return_value=None),
                    "current_errors": mock.Mock(return_value=["runtime error fixture"]),
                }
                for name, value in replacements.items():
                    stack.enter_context(mock.patch.object(memory, name, value))
                stack.enter_context(mock.patch.object(memory.cleanup, "_remote_path_state", return_value="absent"))
                stack.enter_context(mock.patch.object(memory.cleanup, "_same_process", return_value=True))
                stack.enter_context(mock.patch.object(memory.cleanup, "_read_json", return_value=report))

                def stop(*args):
                    self.assertEqual((out / "last-current-report.json").exists(), report_pid == "123")
                    return True

                stack.enter_context(mock.patch.object(memory.cleanup, "_stop_process", side_effect=stop))
                with self.assertRaisesRegex(RuntimeError, "Session memory check failed"):
                    check_session_memory(sessions=12, memory_snapshots=True, expected_apk_sha256="0" * 64)
                self.assertEqual(json.loads((out / "selection.json").read_text())["diagnosticCompletedMemorySnapshotFinalSession"], 13)
                if report_pid == "123":
                    self.assertEqual(json.loads((out / "last-current-report.json").read_text()), report)
                self.assertFalse(json.loads((out / "result.json").read_text())["success"])

    def test_snapshot_admission_waits_for_native_completion_and_refuses_foreign_names(self):
        name = "session-2-" + "a" * 32 + ".snap"
        sample = {"phase": "before-presentation", "memorySnapshotRequested": True, "memorySnapshotComplete": False}
        report = {"sessionResources": [sample]}
        self.assertIsNone(memory_snapshot_file(report, 2))
        sample.update(memorySnapshotComplete=True, memorySnapshotSuccess=True, memorySnapshotFile=name)
        self.assertEqual(memory_snapshot_file(report, 2), name)
        for bad in ("../profile.json", "session-4-" + "a" * 32 + ".snap", "session-2-user.snap"):
            with self.subTest(name=bad), self.assertRaises(RuntimeError):
                memory_snapshot_file({"sessionResources": [dict(sample, memorySnapshotFile=bad)]}, 2)
        for changes in ({"memorySnapshotRequested": False}, {"memorySnapshotSuccess": False}):
            with self.assertRaises(RuntimeError):
                memory_snapshot_file({"sessionResources": [dict(sample, **changes)]}, 2)

    def test_snapshot_transfer_deletes_only_exact_owned_file_after_real_host_hash_matches(self):
        content = b"authored native heap fixture"
        name = "session-2-" + "a" * 32 + ".snap"
        remote = "/owned/diagnostics/session-memory/" + name
        for matched in (True, False):
            with tempfile.TemporaryDirectory() as temporary, self.subTest(matched=matched):
                device = mock.Mock()
                device.sh.return_value = hashlib.sha256(content).hexdigest() + "  " + remote
                device.cmd.side_effect = lambda *args: Path(args[2]).write_bytes(content if matched else b"authored mismatched transfer")
                with mock.patch("session_memory_check.cleanup._remote_path_state", side_effect=["file", "absent"]):
                    if matched:
                        result = collect_memory_snapshot(device, "/owned", Path(temporary), name)
                        self.assertEqual(result["bytes"], len(content))
                        self.assertEqual(result["sha256"], hashlib.sha256(content).hexdigest())
                        device.sh.assert_any_call("rm", "--", remote)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "transfer hash differs"):
                            collect_memory_snapshot(device, "/owned", Path(temporary), name)
                        self.assertNotIn(mock.call("rm", "--", remote), device.sh.call_args_list)

    def test_snapshot_and_static_root_instrumentation_are_separate_before_device_access(self):
        with mock.patch("session_memory_check.SessionCleanupDevice") as device:
            with self.assertRaises(ValueError):
                check_session_memory(sessions=3, expected_apk_sha256="0" * 64, root_walk=True, memory_snapshots=True)
            with self.assertRaises(ValueError):
                check_session_memory(sessions=3, expected_apk_sha256="0" * 64, memory_snapshots=1)
            device.assert_not_called()

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
        self.assertIsNone(summary["per_session_slope_from_session_2"]["managed_before_presentation_bytes"])

    def test_consistent_menu_growth_remains_visible_despite_post_collection_spike(self):
        observed = [
            {"session": index + 1, "samples": samples(start, after)} for index, (start, after) in enumerate(zip([1, 90, 91, 92, 93], [100, 101, 700, 103, 104]))
        ]
        final_menu = [{"phase": "before-presentation", "managed": 94}]
        summary = growth_summary(observed, final_menu)
        slopes = summary["per_session_slope_from_session_2"]
        self.assertLess(slopes["managed_after_collection_bytes"], 0)
        self.assertEqual(slopes["managed_before_presentation_bytes"], 1)
        self.assertEqual(summary["rows"][2]["managed_after_collection"], 700)
        self.assertEqual(summary["final_menu_samples"], final_menu)

    def test_menu_slope_includes_actual_final_menu_instead_of_extrapolating_it(self):
        observed = [{"session": i, "samples": samples(100, 100)} for i in (1, 2, 3)]
        self.assertEqual(growth_summary(observed)["per_session_slope_from_session_2"]["managed_before_presentation_bytes"], 0)
        final_menu = [{"phase": "before-presentation", "managed": 400}]
        self.assertEqual(growth_summary(observed, final_menu)["per_session_slope_from_session_2"]["managed_before_presentation_bytes"], 150)

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
