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

    def test_production_thermal_guard_publishes_failed_done_before_lease_or_device_access(self):
        with (
            mock.patch.object(batch, "_device") as device,
            mock.patch.object(batch, "_modules") as stages,
            mock.patch.object(batch, "_sleep_awakened") as sleep,
            mock.patch.object(batch, "_prune") as prune,
        ):
            with self.assertRaisesRegex(RuntimeError, "batch failed"):
                batch.check_alpha_stability_batch(**self.args)
            device.assert_not_called()
            stages.assert_not_called()
            sleep.assert_not_called()
            prune.assert_not_called()
        self.assertFalse(self.lease.parent.exists())
        result = json.loads(self.done.read_text())
        self.assertFalse(result["success"])
        self.assertFalse(result["lease_released"])
        self.assertIn("missing game-aware CPU thermal owner", result["error"])
        for protocol in ("<= 1 s sampling", "pause at 70 C", "resume at 55 C", "abort above 80 C"):
            self.assertIn(protocol, result["error"])

    def test_busy_lease_refuses_before_any_device_or_stage_and_preserves_owner(self):
        self.lease.mkdir(parents=True)
        owner = self.lease / "owner.json"
        owner.write_text('{"pid": 73, "workstream": "foreign"}\n')
        before = owner.read_bytes()
        with (
            mock.patch.object(batch, "_require_game_thermal_owner"),
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

    def run_case(self, fail_at=None, terminal_error=None, free_bytes=None, expect_failure=False):
        events = []
        original_work = common.WORK
        storage_samples = iter(free_bytes or (20 * 1024**3, 20 * 1024**3))

        def stage(name, **kwargs):
            self.assertEqual(common.WORK, self.root / "work")
            self.assertEqual(json.loads((self.lease / "owner.json").read_text())["pid"], os.getpid())
            self.assertFalse(self.done.exists())
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
            mock.patch.object(batch, "_require_game_thermal_owner"),
            mock.patch.object(batch, "_device", side_effect=device),
            mock.patch.object(batch, "_idle_readback", return_value={}),
            mock.patch.object(batch, "_modules", return_value=modules),
            mock.patch.object(batch, "_terminal_readback", side_effect=terminal),
            mock.patch.object(batch, "_sleep_awakened", side_effect=lambda: events.append("sleep-awakened")),
            mock.patch.object(batch, "_prune", side_effect=prune),
            mock.patch.object(batch.shutil, "disk_usage", return_value=SimpleNamespace(free=101 * 1024**3)),
            mock.patch.object(batch, "command_selectors", return_value=(None, None)),
        ):
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


if __name__ == "__main__":
    unittest.main()
