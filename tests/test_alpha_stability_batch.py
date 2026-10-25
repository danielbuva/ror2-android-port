import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import alpha_stability_batch as batch
import common

HASH = "a" * 64
SERIAL = "authored-fixture"


class AlphaStabilityBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".git").mkdir()
        self.done = self.root / "work/coordination/batch-done.json"
        self.lease = self.root / ".local/orchestrator/leases" / SERIAL
        self.args = dict(device_serial=SERIAL, expected_apk_sha256=HASH, canonical_root=self.root, done_file=self.done)

    def test_cpu_observation_rejects_absent_sentinel_and_malformed_zones(self):
        self.assertEqual(batch.cpu_temperature("cpu-0 55000\ncpu-1 70100"), 70.1)
        for text in ("", "cpu-0 0", "cpu-0 -1000", "cpu-0 150000", "cpu-0 unknown", "battery 55000", "cpu-0"):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                batch.cpu_temperature(text)

    def test_busy_lease_refuses_before_any_device_or_stage_and_preserves_owner(self):
        self.lease.mkdir(parents=True)
        owner = self.lease / "owner.json"
        owner.write_text('{"pid": 73, "workstream": "foreign"}\n')
        before = owner.read_bytes()
        with (
            mock.patch.object(batch, "_device") as device,
            mock.patch.object(batch, "_modules") as stages,
            mock.patch.object(batch, "_prune") as prune,
        ):
            with self.assertRaisesRegex(RuntimeError, "batch failed"):
                batch.check_alpha_stability_batch(**self.args)
            device.assert_not_called()
            stages.assert_not_called()
            prune.assert_not_called()
        result = json.loads(self.done.read_text())
        self.assertIn("lease is busy", result["error"])
        self.assertFalse(result["lease_released"])
        self.assertEqual(owner.read_bytes(), before)

    def test_trusted_done_path_receives_identity_validation_failures_without_device_access(self):
        for overrides in (dict(device_serial="../invalid"), {"expected_apk_sha256": "invalid"}, {"expected_apk_sha256": None}):
            with self.subTest(overrides=overrides), mock.patch.object(batch, "_device") as device, mock.patch.object(batch, "_prune") as prune:
                with self.assertRaisesRegex(RuntimeError, "batch failed"):
                    batch.check_alpha_stability_batch(**(self.args | overrides))
                result = json.loads(self.done.read_text())
                self.assertFalse(result["success"])
                self.assertFalse(result["lease_released"])
                self.assertIn("error", result)
                self.assertFalse(self.lease.exists())
                device.assert_not_called()
                prune.assert_not_called()
                self.done.unlink()

    def test_untrusted_done_path_refuses_without_creating_a_receipt_or_device(self):
        with mock.patch.object(batch, "_device") as device:
            with self.assertRaisesRegex(ValueError, "new absolute"):
                batch.check_alpha_stability_batch(**(self.args | {"done_file": self.root / "outside.json"}))
        self.assertFalse((self.root / "outside.json").exists())
        self.assertFalse(self.lease.exists())
        device.assert_not_called()

    def run_case(self, fail_at=None, terminal_error=None, free_bytes=None, expect_failure=False, thermal_errors=None):
        events = []
        original_work = common.WORK
        storage_samples = iter(free_bytes or (20 * 1024**3,) * 10)

        def stage(name, **kwargs):
            self.assertEqual(common.WORK, self.root / "work")
            self.assertEqual(json.loads((self.lease / "owner.json").read_text())["pid"], os.getpid())
            self.assertFalse(self.done.exists())
            kwargs.pop("_launch")
            events.append((name, kwargs))
            if name == fail_at:
                raise RuntimeError("authored first failure")
            return dict(success=True)

        modules = (
            SimpleNamespace(check_settings_write_interrupt=lambda **kwargs: stage("sdk", **kwargs)),
            SimpleNamespace(check_session_memory=lambda **kwargs: stage("memory", **kwargs)),
            SimpleNamespace(check_session_sustained=lambda **kwargs: stage("sustained", **kwargs)),
        )

        def device(serial):
            self.assertEqual(serial, SERIAL)
            owner = json.loads((self.lease / "owner.json").read_text())
            self.assertEqual(owner["pid"], os.getpid())
            self.assertEqual(common.WORK, self.root / "work")
            return SimpleNamespace(storage=lambda: dict(mode="internal", internal=dict(free_bytes=next(storage_samples))))

        def terminal(serial, expected):
            self.assertFalse(self.done.exists())
            self.assertTrue(self.lease.exists())
            events.append("terminal")
            if terminal_error:
                raise RuntimeError(terminal_error)
            return dict(apk_sha256=expected, process_absent=True, selector_absent=True, oled_asleep=True)

        def prune(root):
            self.assertEqual(root, self.root)
            self.assertFalse(self.done.exists())
            events.append("prune")

        with (
            mock.patch.object(batch, "_GameThermalOwner") as thermal,
            mock.patch.object(batch, "_device", side_effect=device),
            mock.patch.object(batch, "_idle_readback", return_value={}),
            mock.patch.object(batch, "_modules", return_value=modules),
            mock.patch.object(batch, "_terminal_readback", side_effect=terminal),
            mock.patch.object(batch, "_sleep_awakened", side_effect=lambda: events.append("sleep-awakened")),
            mock.patch.object(batch, "_prune", side_effect=prune),
            mock.patch.object(batch.shutil, "disk_usage", return_value=SimpleNamespace(free=101 * 1024**3)),
            mock.patch.object(batch, "command_selectors", return_value=(None, None)),
        ):
            thermal.return_value.finish.side_effect = thermal_errors or [None, None, None]
            thermal.return_value.peak_cpu_celsius = 79.5
            if fail_at or terminal_error or expect_failure:
                with self.assertRaises(RuntimeError):
                    batch.check_alpha_stability_batch(**self.args)
            else:
                batch.check_alpha_stability_batch(**self.args)
        self.assertEqual(common.WORK, original_work)
        return events, json.loads(self.done.read_text())

    def test_fixed_order_driver_pid_and_done_only_after_terminal_prune_release(self):
        events, result = self.run_case()
        self.assertEqual(
            [event[0] if isinstance(event, tuple) else event for event in events], ["sdk", "memory", "sustained", "sleep-awakened", "terminal", "prune"]
        )
        self.assertEqual(events[1][1], dict(expected_apk_sha256=HASH, sessions=3, memory_snapshots=True))
        self.assertEqual(result["driver_pid"], os.getpid())
        self.assertTrue(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertFalse(self.lease.exists())

    def test_thermal_abort_never_replays_stage_and_retains_peak(self):
        events, result = self.run_case(thermal_errors=[None, RuntimeError("CPU above80")], expect_failure=True)
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["sdk", "memory"])
        self.assertEqual([stage["name"] for stage in result["stages"]], ["settings-write-interrupt"])
        self.assertEqual(result["peak_cpu_celsius"], 79.5)
        self.assertEqual(result["active_stage_peak_cpu_celsius"], 79.5)
        self.assertNotIn("interrupted_attempts", result)
        self.assertIn("CPU above80", result["error"])

    def test_runtime_failure_remains_primary_when_thermal_shutdown_also_aborts(self):
        events, result = self.run_case(fail_at="sdk", thermal_errors=[RuntimeError("CPU above80")])
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["sdk"])
        self.assertEqual(result["error"], "authored first failure")
        self.assertEqual(result["thermal_error"], "CPU above80")
        self.assertFalse(result["success"])

    def test_first_failure_stops_queue_and_publishes_failed_done_after_cleanup(self):
        events, result = self.run_case(fail_at="sdk")
        self.assertEqual([event[0] if isinstance(event, tuple) else event for event in events], ["sdk", "sleep-awakened", "terminal", "prune"])
        self.assertEqual(result["error"], "authored first failure")
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])

    def test_capture_headroom_is_rechecked_after_sdk_before_memory_dispatch(self):
        events, result = self.run_case(free_bytes=(20 * 1024**3, 18 * 1024**3), expect_failure=True)
        self.assertEqual([event[0] if isinstance(event, tuple) else event for event in events], ["sdk", "sleep-awakened", "terminal", "prune"])
        self.assertIn("4 GiB headroom", result["error"])
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])

    def test_capture_capacity_retains_free_reserve_during_one_native_file(self):
        for mode in ("internal", "adopted"):
            for free_gib in (15, 18, 19):
                device = mock.Mock()
                device.storage.return_value = {"mode": mode, mode: {"free_bytes": free_gib * 1024**3}}
                with self.subTest(mode=mode, free_gib=free_gib):
                    if free_gib < 19:
                        with self.assertRaisesRegex(RuntimeError, "retained 15 GiB"):
                            batch._require_capture_capacity(device)
                    else:
                        batch._require_capture_capacity(device)

    def test_failed_terminal_proof_preserves_lease_and_still_publishes_done(self):
        events, result = self.run_case(terminal_error="foreign selector remains")
        self.assertEqual(events[-2:], ["terminal", "prune"])
        self.assertFalse(result["success"])
        self.assertFalse(result["lease_released"])
        self.assertTrue((self.lease / "owner.json").is_file())

    def test_foreign_selector_pending_or_process_are_only_read_and_preserved(self):
        for selector, pending, process in (("file", "absent", ""), ("absent", "file", ""), ("absent", "absent", "73")):
            device = mock.Mock()
            device.owned.return_value = dict(apk_sha256=HASH, package_path="package:/data/app/fixture/base.apk")
            device.read_receipt.return_value = dict(persistentDataPath="/owned")
            device.sh.side_effect = [HASH + "  /data/app/fixture/base.apk", process]
            with (
                self.subTest(selector=selector, pending=pending, process=process),
                mock.patch("session_cleanup_check._remote_path_state", side_effect=[selector, pending]),
            ):
                with self.assertRaisesRegex(RuntimeError, "preserved existing state"):
                    batch._idle_readback(device, HASH)
            self.assertEqual([call.args[0] for call in device.sh.call_args_list], ["sha256sum", "pidof"])
            device.cmd.assert_not_called()

    def test_release_requires_actual_installed_hash_not_receipt_claim(self):
        device = mock.Mock()
        device.owned.return_value = dict(apk_sha256=HASH, package_path="package:/data/app/fixture/base.apk")
        device.sh.return_value = "b" * 64 + "  /data/app/fixture/base.apk"
        with self.assertRaisesRegex(RuntimeError, "Actual installed APK bytes differ"):
            batch._idle_readback(device, HASH)
        device.read_receipt.assert_not_called()

    def test_terminal_sleeps_display_even_when_idle_readback_refuses(self):
        device = mock.Mock()
        device.display.return_value = True
        with mock.patch.object(batch, "_device", return_value=device), mock.patch.object(batch, "_idle_readback", side_effect=RuntimeError("foreign state")):
            with self.assertRaisesRegex(RuntimeError, "foreign state"):
                batch._terminal_readback(SERIAL, HASH)
        device.display.assert_called_once_with(False)


class GameThermalOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.device = mock.Mock()
        self.device.serial = SERIAL
        self.device.read_receipt.return_value = dict(apk_sha256=HASH, serial=SERIAL, package="dev.ror2lab.arm64", package_path="package:/fixture/base.apk")
        self.owner = batch._GameThermalOwner(self.device, HASH, Path(self.temp.name) / "thermal.jsonl", float("inf"))

    def test_actual_gap_and_unknown_read_are_hard_refusals(self):
        self.device.cmd.return_value = "cpu-0 56000"
        with mock.patch.object(batch.time, "monotonic", side_effect=[0, 0.2, 0.4, 1.3]):
            self.assertEqual(self.owner.sample(), 56)
            with self.assertRaisesRegex(RuntimeError, "gap exceeded"):
                self.owner.sample()
        self.device.cmd.assert_called_with("shell", batch.CPU_ZONES, timeout=0.7)
        self.device.cmd.side_effect = TimeoutError("hung ADB")
        with self.assertRaisesRegex(TimeoutError, "hung ADB"):
            self.owner.sample()

    def test_above_80_aborts_but_80_itself_continues(self):
        self.device.cmd.return_value = "cpu-0 80000"
        self.assertEqual(self.owner.sample(), 80)
        self.device.cmd.return_value = "cpu-0 80001"
        with self.assertRaisesRegex(RuntimeError, "80 C hard abort"):
            self.owner.sample()
        self.assertEqual(self.owner.peak_cpu_celsius, 80.001)

    def test_cooling_hysteresis_excludes_wait_from_game_attempt(self):
        self.device.display.return_value = True
        with mock.patch.object(self.owner, "sample", side_effect=[70, 51, 50]) as sample, mock.patch.object(batch.time, "sleep") as sleep:
            self.owner.cool()
        self.assertEqual(sample.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.device.display.assert_called_once_with(False)
        self.assertIsNone(self.owner.previous)
        sample.assert_called_with(all_zones=True)

    def test_cooldown_waits_for_pmic_even_when_cpu_is_below_50(self):
        self.device.display.return_value = True
        self.device.cmd.side_effect = ["cpu-0\t49000\npm8550_tz\t51000", "cpu-0\t49000\npm8550_tz\t50000"]
        with mock.patch.object(batch.time, "sleep") as sleep:
            self.owner.cool()
        sleep.assert_called_once_with(batch.THERMAL_INTERVAL_SECONDS)
        self.device.cmd.assert_called_with("shell", batch.ALL_ZONES, timeout=0.7)
        rows = [json.loads(line) for line in self.owner.trace.read_text().splitlines()]
        self.assertEqual([row["maximum_zone_celsius"] for row in rows], [51, 50])
        self.assertEqual(self.owner.peak_cpu_celsius, 49)

    def test_unknown_sentinel_or_missing_cpu_refuses_cooldown_with_raw_trace(self):
        for text in ("cpu-0 49000\nwireless -40000", "pm8550_tz 49000", "cpu-0 49000\nunknown 0", "cpu-0 49000\nbroken"):
            with self.subTest(text=text):
                self.device.cmd.return_value = text
                with self.assertRaises(RuntimeError):
                    self.owner.cool()
                row = json.loads(self.owner.trace.read_text().splitlines()[-1])
                self.assertEqual(row["all_zones_raw"], text)
                self.assertIn("error", row)
        self.device.launch.assert_not_called()

    def test_cooldown_retains_explicit_non_temperature_exclusions(self):
        for name in batch.NON_TEMPERATURE_ZONES:
            with self.subTest(name=name):
                maximum, cpu, excluded = batch.cooldown_temperatures("cpu-0 49000\n" + name + " 0")
                self.assertEqual((maximum, cpu), (49, 49))
                self.assertEqual(excluded, [dict(type=name, raw=0, reason="Non-temperature battery/current/voltage level")])

    def test_observer_does_not_stop_game_at_or_below_80(self):
        import threading

        sampled = threading.Event()
        count = 0

        def sample():
            nonlocal count
            count += 1
            if count >= 3:
                sampled.set()
            return 80

        with mock.patch.object(self.owner, "sample", side_effect=sample), mock.patch.object(self.owner, "terminate_game") as stop:
            self.owner.start()
            self.assertTrue(sampled.wait(2))
            stop.assert_not_called()
            self.assertFalse(self.owner.cancelled.is_set())
            self.assertIsNone(self.owner.finish())

    def test_sampler_continues_while_bounded_stop_is_blocked(self):
        import threading

        entered, release, sampled = threading.Event(), threading.Event(), threading.Event()
        count = 0

        def sample():
            nonlocal count
            count += 1
            if count >= 4:
                sampled.set()
            if count > 1:
                raise RuntimeError("CPU exceeded 80 C hard abort")
            return 50

        def blocked_stop():
            entered.set()
            release.wait(2)

        with mock.patch.object(self.owner, "sample", side_effect=sample), mock.patch.object(self.owner, "terminate_game", side_effect=blocked_stop):
            self.owner.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertTrue(sampled.wait(1))
                self.assertTrue(self.owner.thread.is_alive())
            finally:
                release.set()
                with self.assertRaisesRegex(RuntimeError, "80 C hard abort"):
                    self.owner.finish()
        self.assertFalse(self.owner.thread.is_alive())
        self.assertFalse(self.owner.stopper.is_alive())

    def test_thermally_cancelled_launch_and_recovery_are_refused(self):
        self.owner.error = "CPU exceeded 80 C hard abort"
        with self.assertRaisesRegex(RuntimeError, "cannot launch/recover"):
            self.owner.launch(self.device)
        self.device.launch.assert_not_called()
        self.owner.error = None

        def crossed():
            self.owner.error = "CPU exceeded 80 C hard abort"
            return dict(pid="73")

        self.device.launch.side_effect = crossed
        with mock.patch.object(self.owner, "terminate_game") as stop, self.assertRaisesRegex(RuntimeError, "crossed thermal"):
            self.owner.launch(self.device)
        stop.assert_called_once_with()

    def test_late_or_foreign_pid_never_causes_force_stop(self):
        from device import PACKAGE

        for receipt, replies in (
            (dict(apk_sha256="b" * 64), []),
            (dict(apk_sha256=HASH), ["73", "foreign\x00\n73"]),
            (dict(apk_sha256=HASH), ["73", PACKAGE + "\x00\n74"]),
        ):
            with self.subTest(replies=replies):
                self.device.reset_mock()
                self.device.read_receipt.return_value = dict(receipt, serial=SERIAL, package=PACKAGE, package_path="package:/fixture/base.apk")
                self.device.cmd.side_effect = ["package:/fixture/base.apk"] + replies
                with self.assertRaises(RuntimeError):
                    self.owner.terminate_game()
                self.assertFalse(any("force-stop" in str(call) for call in self.device.cmd.call_args_list))
        self.device.reset_mock()
        self.device.serial = SERIAL
        self.device.read_receipt.return_value = dict(apk_sha256=HASH, serial=SERIAL, package="dev.ror2lab.arm64", package_path="package:/fixture/base.apk")
        self.device.cmd.side_effect = ["package:/fixture/base.apk", "73", PACKAGE + "\x00\n73", ""]
        self.owner.terminate_game()
        self.device.cmd.assert_called_with("shell", "am force-stop " + PACKAGE, timeout=2)


if __name__ == "__main__":
    unittest.main()
