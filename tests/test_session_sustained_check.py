import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
import tempfile
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import session_sustained_check as sustained


def fixtures():
    utc = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = dict(
        session=1,
        phase="integrated-world-playing",
        world=dict(ready=True, authority=True, manualTakeover=True, diagnosticInput=False, health=100, frames=100, liveEnemies=4),
        runClock=dict(stopwatch=20),
        debugAcceleration=dict(active={key: key == "invincibility" for key in sustained.ASSISTS}),
        framePacing=dict(frames=100, meanMs=20, over33ms=4, over50ms=2, maxMs=110),
    )
    snapshot = dict(utc=utc.isoformat(), fps=50, frameMs=20, managedBytes=1000, totalAllocatedBytes=2000)
    return report, snapshot, utc


class SustainedCheckTests(unittest.TestCase):
    def test_world_preparation_does_not_admit_before_selected_assist_is_applied(self):
        report, _, _ = fixtures()
        self.assertTrue(sustained.sustained_world_ready(report))
        report["debugAcceleration"]["active"]["invincibility"] = False
        self.assertFalse(sustained.sustained_world_ready(report))
        report["debugAcceleration"]["active"]["invincibility"] = True
        report["debugAcceleration"]["active"]["highDamage"] = True
        with self.assertRaisesRegex(RuntimeError, "exactly invincibility"):
            sustained.sustained_world_ready(report)
        report["debugAcceleration"]["active"]["highDamage"] = False
        report["phase"] = "offline-start-menu"
        self.assertFalse(sustained.sustained_world_ready(report))
        report["phase"] = "integrated-world-playing"
        report["world"]["ready"] = False
        self.assertFalse(sustained.sustained_world_ready(report))

    def test_capture_off_preserves_aggregates_and_never_transfers_a_sidecar(self):
        report, snapshot, utc = fixtures()
        row = sustained.observation_sample(report, snapshot, 0, utc=utc)
        device = mock.Mock()
        self.assertIsNone(sustained.collect_raw_frames(device, "/owned", Path("unused"), report, [row], enabled=False))
        self.assertEqual(row["pacing_frames"], 100)
        self.assertEqual(row["pacing_total_ms"], 2000)
        self.assertEqual(row["pacing_over33"], 4)
        device.assert_not_called()
        device.cmd.assert_not_called()
        device.sh.assert_not_called()
        for field, value in (("rawFrameTrace", "unexpected.bin"), ("rawFrameTraceClosed", True), ("rawFrameTraceFrames", 2)):
            invalid = copy.deepcopy(report)
            invalid["framePacing"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "despite disabled"):
                sustained.collect_raw_frames(device, "/owned", Path("unused"), invalid, [row], enabled=False)
        with self.assertRaisesRegex(RuntimeError, "despite disabled"):
            sustained.collect_raw_frames(device, "/owned", Path("unused"), report, [dict(row, pacing_trace="unexpected.bin")], enabled=False)

    def test_capture_mode_rejects_non_boolean_before_device_access(self):
        with mock.patch.object(sustained, "Device") as device:
            with self.assertRaisesRegex(ValueError, "explicit boolean"):
                sustained.check_session_sustained("a" * 64, raw_frame_times="off")
            device.assert_not_called()

    def test_exact_total_avoids_rounded_mean_and_binds_trace(self):
        report, snapshot, utc = fixtures()
        report["framePacing"].update(totalMs=2000.125, rawFrameTrace="authored.bin")
        row = sustained.observation_sample(report, snapshot, 0, utc=utc)
        self.assertEqual(row["pacing_total_ms"], 2000.125)
        self.assertTrue(row["pacing_total_ms_exact"])
        self.assertEqual(row["pacing_trace"], "authored.bin")
        report["framePacing"]["totalMs"] = float("nan")
        with self.assertRaisesRegex(RuntimeError, "cumulative"):
            sustained.observation_sample(report, snapshot, 0, utc=utc)

    def test_only_closed_matching_trace_is_collected_and_removed_after_retention(self):
        import perf_report as perf
        import struct

        name = "frame-times-" + "a" * 32 + ".bin"
        completed = dict(
            framePacing=dict(rawFrameTrace=name, rawFrameTraceClosed=True, rawFrameTraceFirstFrame=1, rawFrameTraceFrames=2, rawFrameTraceDropped=0)
        )
        samples = [
            dict(pacing_frames=0, pacing_total_ms=0, pacing_total_ms_exact=True, pacing_over33=0, pacing_over50=0, pacing_trace=name),
            dict(pacing_frames=2, pacing_total_ms=70, pacing_total_ms_exact=True, pacing_over33=1, pacing_over50=1, pacing_trace=name),
        ]
        data = perf.RAW_HEADER.pack(b"ROR2FRAM", 1, 2, 2, 0) + struct.pack("<2f", 10, 60)
        device = mock.Mock()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            device.cmd.side_effect = lambda *args: (out / name).write_bytes(data)
            device.sh.side_effect = lambda *args: self.assertEqual((out / name).read_bytes(), data)
            trace = sustained.collect_raw_frames(device, "/owned", out, completed, samples)
            self.assertEqual(trace["retained_frames"], 2)
            device.sh.assert_called_once_with("rm", "--", "/owned/" + name)
            device.reset_mock()
            for field, value in (("rawFrameTrace", "../foreign"), ("rawFrameTraceClosed", False), ("rawFrameTraceError", "write failed")):
                invalid = copy.deepcopy(completed)
                invalid["framePacing"][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "closed session-bound"):
                    sustained.collect_raw_frames(device, "/owned", out, invalid, samples)
                device.cmd.assert_not_called()
                device.sh.assert_not_called()

    def test_foreign_selector_pending_and_live_process_are_preserved_before_launch(self):
        for selector, pending, process in (("file", "absent", ""), ("absent", "file", ""), ("absent", "absent", "73")):
            device = mock.Mock()
            device.owned.return_value = dict(apk_sha256="a" * 64)
            device.read_receipt.return_value = dict(persistentDataPath="/owned")
            device.sh.return_value = process
            with (
                self.subTest(selector=selector, pending=pending, process=process),
                mock.patch.object(sustained, "Device", return_value=device),
                mock.patch.object(sustained, "attempt_from_installed", return_value="authored-attempt"),
                mock.patch.object(sustained.cleanup, "_remote_path_state", side_effect=[selector, pending]),
            ):
                with self.assertRaisesRegex(RuntimeError, "preserve foreign state|Preserve existing pending"):
                    sustained.check_session_sustained("a" * 64)
            device.launch.assert_not_called()
            device.cmd.assert_not_called()
            device.display.assert_not_called()
            self.assertTrue(all(call.args[0] == "pidof" for call in device.sh.call_args_list))

    def test_fixed_thirty_minute_assisted_scope_and_explicit_hash(self):
        self.assertEqual(sustained.PLANNED_SECONDS, 1800)
        with mock.patch.object(sustained, "Device") as device:
            with self.assertRaises(ValueError):
                sustained.check_session_sustained()
            device.assert_not_called()

    def test_battery_at_43_stops_and_hal_is_a_metric(self):
        self.assertEqual(sustained.thermal_sample("temperature: 429", "Thermal Status: 3"), dict(battery_celsius=42.9, thermal_status=3))
        for battery, thermal in (
            ("temperature: 430", "Thermal Status: 0"),
            ("", "Thermal Status: 0"),
            ("temperature: 400", ""),
        ):
            with self.subTest(battery=battery, thermal=thermal), self.assertRaises(RuntimeError):
                sustained.thermal_sample(battery, thermal)

    def test_manual_neutral_invincibility_only_and_fresh_measurements_are_required(self):
        report, snapshot, utc = fixtures()
        row = sustained.observation_sample(report, snapshot, 0, utc=utc)
        self.assertIsNone(row["gpu_frame_ms"])
        self.assertEqual(row["pacing_total_ms"], 2000)
        for key, value in (("manualTakeover", False), ("diagnosticInput", True), ("authority", False), ("health", 0), ("frames", float("nan"))):
            invalid = copy.deepcopy(report)
            invalid["world"][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                sustained.observation_sample(invalid, snapshot, 0, utc=utc)
        for key in sustained.ASSISTS:
            invalid = copy.deepcopy(report)
            invalid["debugAcceleration"]["active"][key] = key != "invincibility"
            with self.subTest(assist=key), self.assertRaises(RuntimeError):
                sustained.observation_sample(invalid, snapshot, 0, utc=utc)
        with self.assertRaisesRegex(RuntimeError, "stale"):
            sustained.observation_sample(report, snapshot, 0, utc=utc + timedelta(seconds=15))
        with self.assertRaisesRegex(RuntimeError, "did not advance"):
            sustained.observation_sample(report, snapshot, 5, previous=row, utc=utc)
        invalid = dict(snapshot, managedBytes=None)
        with self.assertRaisesRegex(RuntimeError, "Missing/non-finite"):
            sustained.observation_sample(report, invalid, 0, utc=utc)

    def test_only_explicit_all_off_refusal_is_retained_no_other_teardown_waiver(self):
        completed = dict(
            debugAcceleration=dict(
                restored=True,
                active={key: False for key in sustained.ASSISTS},
                everAssisted=True,
                normalGameAcceptanceEligible=False,
                events=[dict(toggle="invincibility", enabled=True)],
            )
        )
        with mock.patch.object(sustained.cleanup, "abandon_contract", return_value=[sustained.ALL_OFF_REFUSAL]):
            self.assertEqual(sustained.assisted_teardown_contract(completed, "73", "attempt", {}), [sustained.ALL_OFF_REFUSAL])
            for field, value in (("restored", False), ("everAssisted", False), ("normalGameAcceptanceEligible", True), ("events", [])):
                invalid = copy.deepcopy(completed)
                invalid["debugAcceleration"][field] = value
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    sustained.assisted_teardown_contract(invalid, "73", "attempt", {})
        for failures in ([], ["other failure"], [sustained.ALL_OFF_REFUSAL, "other failure"]):
            with (
                mock.patch.object(sustained.cleanup, "abandon_contract", return_value=failures),
                self.assertRaisesRegex(RuntimeError, "Unexpected native teardown failure"),
            ):
                sustained.assisted_teardown_contract(completed, "73", "attempt", {})


if __name__ == "__main__":
    unittest.main()
