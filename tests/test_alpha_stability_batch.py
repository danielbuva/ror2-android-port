import json
import os
from pathlib import Path
import sys
import subprocess
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
        self.enterContext(mock.patch.object(batch.shutil, "disk_usage", return_value=SimpleNamespace(free=101 * 1024**3)))
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".git").mkdir()
        self.done = self.root / "work/coordination/batch-done.json"
        self.lease = self.root / ".local/orchestrator/leases" / SERIAL
        self.args = dict(device_serial=SERIAL, expected_apk_sha256=HASH, canonical_root=self.root, done_file=self.done)

    def test_host_capture_admission_uses_output_estimate_plus_margin(self):
        for free_gib in (28, 29, 96):
            with self.subTest(free_gib=free_gib), mock.patch.object(batch.shutil, "disk_usage", return_value=SimpleNamespace(free=free_gib * 1024**3)):
                budget = batch._host_capture_budget(self.root)
                self.assertEqual(budget["estimated_output_bytes"], 9 * 1024**3)
                self.assertEqual(budget["margin_bytes"], 20 * 1024**3)
                self.assertEqual(budget["required_free_bytes"], 29 * 1024**3)
                with (
                    mock.patch.object(batch, "_device", side_effect=RuntimeError("admitted to device")) as device,
                    mock.patch.object(batch, "_terminal_readback", return_value={}),
                    mock.patch.object(batch, "_sleep_awakened"),
                    mock.patch.object(batch, "_prune"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "batch failed"):
                        batch.check_alpha_stability_batch(**self.args)
                result = json.loads(self.done.read_text())
                self.assertEqual(result["host_capture_budget"], budget)
                if free_gib < 29:
                    device.assert_not_called()
                    self.assertFalse(self.lease.exists())
                    self.assertIn("20 GiB margin", result["error"])
                else:
                    device.assert_called_once()
                    self.assertEqual(result["error"], "admitted to device")
                    self.assertTrue(result["lease_released"])
                self.done.unlink()

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
            thermal.return_value.battery = dict(celsius=34, level=80, status=4)
            thermal.return_value.admission_battery = dict(celsius=34, level=80, status=4)
            thermal.return_value.peak_cpu_celsius = 79.5
            thermal.return_value.peak_zone_celsius = 79.8
            thermal.return_value.time_above_80_seconds = 0
            thermal.return_value.peak_cpu_gpu_celsius = 79.5
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

    def test_gameplay_only_runs_fresh_heaps_and_sustained_without_claiming_settings(self):
        self.args["gameplay_only"] = True
        events, result = self.run_case()
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["memory", "sustained"])
        self.assertEqual([stage["name"] for stage in result["stages"]], ["session-memory", "session-sustained"])
        self.assertEqual(result["scope"], "gameplay-only")
        self.assertTrue(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertTrue(result["terminal_readback"]["oled_asleep"])
        self.assertNotIn("prior_settings_batch", result)

    def test_gameplay_only_still_stops_and_cleans_up_at_first_gameplay_failure(self):
        self.args["gameplay_only"] = True
        events, result = self.run_case(fail_at="memory")
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["memory"])
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertEqual(result["scope"], "gameplay-only")

    def prior_settings(self, apk=HASH, success=True):
        source = self.root / "prior.json"
        source.write_text(
            json.dumps(dict(success=False, apk_sha256=apk, stages=[dict(name="settings-write-interrupt", result=dict(success=success, apk_sha256=apk))]))
        )
        return source

    def test_prior_settings_runs_only_fresh_heaps_and_sustained(self):
        source = self.prior_settings()
        self.args["prior_settings_batch"] = source
        events, result = self.run_case()
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["memory", "sustained"])
        self.assertEqual([stage["name"] for stage in result["stages"]], ["session-memory", "session-sustained"])
        self.assertEqual(result["prior_settings_batch"]["path"], str(source))
        self.assertEqual(result["prior_settings_batch"]["sha256"], batch.hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertTrue(result["lease_released"])

    def test_prior_settings_failure_stops_before_sustained(self):
        self.args["prior_settings_batch"] = self.prior_settings()
        events, result = self.run_case(fail_at="memory")
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["memory"])
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])

    def test_unpassed_or_different_apk_prior_refused_before_device_access(self):
        for apk, success in (("b" * 64, True), (HASH, False)):
            with self.subTest(apk=apk, success=success):
                self.done.unlink(missing_ok=True)
                self.args["prior_settings_batch"] = self.prior_settings(apk, success)
                with mock.patch.object(batch, "_device") as device, self.assertRaises(RuntimeError):
                    batch.check_alpha_stability_batch(**self.args)
                device.assert_not_called()
                self.assertFalse(self.lease.exists())
                self.assertFalse(json.loads(self.done.read_text())["success"])

    def test_thermal_abort_never_replays_stage_and_retains_peak(self):
        events, result = self.run_case(thermal_errors=[None, RuntimeError("CPU above80")], expect_failure=True)
        self.assertEqual([event[0] for event in events if isinstance(event, tuple)], ["sdk", "memory"])
        self.assertEqual([stage["name"] for stage in result["stages"]], ["settings-write-interrupt"])
        self.assertEqual(result["peak_cpu_celsius"], 79.5)
        self.assertEqual(result["peak_zone_celsius"], 79.8)
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
        self.device.sh.return_value = "temperature: 340\nlevel: 80\nstatus: 4\n"
        self.device.serial = SERIAL
        self.device.read_receipt.return_value = dict(apk_sha256=HASH, serial=SERIAL, package="dev.ror2lab.arm64", package_path="package:/fixture/base.apk")
        self.owner = batch._GameThermalOwner(self.device, HASH, Path(self.temp.name) / "thermal.jsonl", float("inf"))
        current = mock.patch.object(self.owner, "battery_current", return_value=0)
        self.current = current.start()
        self.addCleanup(current.stop)

    def test_actual_gap_and_unknown_read_are_hard_refusals(self):
        self.owner.runtime_zones = [("cpu-0", "/thermal_zone0/temp")]
        self.device.cmd.return_value = "56000\n"
        with mock.patch.object(batch.time, "monotonic", side_effect=[0, 0.2, 0.4, 1.3]):
            self.assertEqual(self.owner.sample(), 56)
            with self.assertRaisesRegex(RuntimeError, "gap exceeded"):
                self.owner.sample()
        self.device.cmd.assert_called_with("shell", "cat /thermal_zone0/temp", timeout=0.7)
        self.device.cmd.side_effect = TimeoutError("hung ADB")
        with self.assertRaisesRegex(TimeoutError, "hung ADB"):
            self.owner.sample()

    def test_slow_admission_discovers_paths_then_runtime_uses_one_cat(self):
        self.device.display.return_value = True
        self.device.cmd.return_value = (
            "cpu-0 49000 /thermal_zone0/temp\npm8550_tz 50000 /thermal_zone1/temp\npa1 UNREADABLE /thermal_zone2/temp\nvbat 0 /thermal_zone3/temp"
        )
        with mock.patch.object(batch.time, "monotonic", side_effect=[0, 2]):
            self.owner.cool()
        self.device.cmd.assert_called_once_with("shell", batch.ALL_ZONES, timeout=10)
        self.assertIsNone(self.owner.previous)
        self.assertEqual(self.owner.runtime_zones, [("cpu-0", "/thermal_zone0/temp"), ("pm8550_tz", "/thermal_zone1/temp")])
        self.device.cmd.return_value = "49000\n80001\n"
        with mock.patch.object(batch.time, "monotonic", side_effect=[3, 3.2]):
            self.assertEqual(self.owner.sample(), 80.001)
        self.device.cmd.assert_called_with("shell", "cat /thermal_zone0/temp /thermal_zone1/temp", timeout=0.7)
        rows = [json.loads(line) for line in self.owner.trace.read_text().splitlines()]
        self.assertTrue(rows[0]["admission"])
        self.assertFalse(rows[1]["admission"])
        self.assertEqual(rows[1]["excluded_zones"], rows[0]["excluded_zones"])
        self.assertEqual(self.owner.peak_zone_celsius, 80.001)
        self.assertEqual(self.owner.peak_cpu_celsius, 49)

    def test_runtime_cat_protocol_and_failures_are_fail_closed(self):
        root = Path(self.temp.name)
        paths = [root / "cpu-fixture/temp", root / "pmic/temp"]
        for path, value in zip(paths, ("49000\n", "79000\n")):
            path.parent.mkdir()
            path.write_text(value)
        self.owner.runtime_zones = list(zip(("cpu-0", "pmic"), map(str, paths)))

        def shell(*args, **kwargs):
            self.assertEqual(args[0], "shell")
            self.assertEqual(kwargs, dict(timeout=0.7))
            self.assertTrue(args[1].startswith("cat "))
            self.assertEqual(args[1].count("cat "), 1)
            return subprocess.run(["/bin/sh", "-c", args[1]], check=True, capture_output=True, text=True).stdout

        self.device.cmd.side_effect = shell
        self.assertEqual(self.owner.sample(), 79)
        paths[1].unlink()
        with self.assertRaises(subprocess.CalledProcessError):
            self.owner.sample()
        self.device.cmd.side_effect = None
        for raw in ("49000\n", "49000\n79000\n1\n", "49000 79000\n", "49000\nunknown\n", "49000\n0\n", "49000\n-40000\n"):
            with self.subTest(raw=raw):
                self.device.cmd.return_value = raw
                with self.assertRaises(RuntimeError):
                    self.owner.sample()
                self.assertIn("error", json.loads(self.owner.trace.read_text().splitlines()[-1]))

    def test_runtime_refuses_without_admission_before_any_adb(self):
        with self.assertRaisesRegex(RuntimeError, "requires admission"):
            self.owner.sample()
        self.device.cmd.assert_not_called()

    def test_shell_read_failure_names_zone_and_preserves_previous_output(self):
        root = Path(self.temp.name)
        first, failed = root / "thermal_zone0", root / "thermal_zone1"
        first.mkdir()
        failed.mkdir()
        (first / "type").write_text("pa\n")
        (first / "temp").write_text("34600\n")
        (failed / "type").write_text("pa1\n")
        (failed / "temp").write_text("")
        last = root / "thermal_zone2"
        last.mkdir()
        (last / "type").write_text("cpu-0\n")
        (last / "temp").write_text("49000\n")
        command = batch.ALL_ZONES.replace("/sys/class/thermal/thermal_zone*", str(root / "thermal_zone*"))
        result = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout, "pa\t34600\t" + str(first / "temp") + "\npa1\tUNREADABLE\t" + str(failed / "temp") + "\ncpu-0\t49000\t" + str(last / "temp") + "\n"
        )
        (failed / "type").unlink()
        result = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Thermal type read failed: " + str(failed / "type"), result.stderr)

    def test_shell_failure_is_retained_in_trace_and_never_admits_cooldown(self):
        error = RuntimeError("adb exited 1: read: Invalid argument\nThermal temp read failed: /thermal_zone1/temp type=pa1\npa\t34600\n")
        self.device.cmd.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            self.owner.sample(all_zones=True)
        self.assertIs(caught.exception, error)
        row = json.loads(self.owner.trace.read_text())
        self.assertEqual(row["error"], str(error))
        self.assertTrue(row["all_zones"])
        self.assertNotIn("cpu_celsius", row)
        self.assertIsNone(self.owner.peak_cpu_celsius)

    def test_above_80_aborts_but_80_itself_continues(self):
        self.device.cmd.return_value = "cpu-0 80000"
        self.assertEqual(self.owner.sample(all_zones=True), 80)
        self.device.cmd.return_value = "cpu-0 80001"
        with self.assertRaisesRegex(RuntimeError, "80 C hard abort"):
            self.owner.sample(all_zones=True)
        self.assertEqual(self.owner.peak_cpu_celsius, 80.001)

    def test_runtime_uses_non_cpu_readable_zone_and_records_unsupported(self):
        self.device.cmd.return_value = "cpu-0 49000\npm8550_tz 80000\npa1 UNREADABLE /thermal_zone1/temp"
        self.assertEqual(self.owner.sample(all_zones=True), 49)
        row = json.loads(self.owner.trace.read_text())
        self.assertEqual(row["maximum_zone_celsius"], 80)
        self.assertEqual(row["excluded_zones"], [dict(type="pa1", path="/thermal_zone1/temp", reason="Thermal temp read failed/unsupported")])
        self.device.cmd.return_value = "cpu-0 49000\npm8550_tz 80001"
        with self.assertRaisesRegex(RuntimeError, "80 C hard abort"):
            self.owner.sample(all_zones=True)
        self.assertEqual(self.owner.peak_zone_celsius, 80.001)
        self.assertEqual(self.owner.peak_cpu_celsius, 49)

    def test_unreadable_zone_is_recorded_and_excluded_from_cooldown(self):
        self.device.display.return_value = True
        self.device.cmd.return_value = "cpu-0 50000\npa1 UNREADABLE /thermal_zone1/temp"
        self.owner.cool()
        row = json.loads(self.owner.trace.read_text())
        self.assertEqual(row["maximum_zone_celsius"], 50)
        self.assertEqual(row["excluded_zones"][0]["type"], "pa1")
        self.device.cmd.return_value = "cpu-0 UNREADABLE /thermal_zone0/temp"
        with self.assertRaisesRegex(RuntimeError, "No readable CPU"):
            self.owner.cool()

    def test_unreadable_cpu_does_not_substitute_for_a_readable_cpu(self):
        self.device.cmd.return_value = "cpu-0 UNREADABLE /thermal_zone0/temp\npm8550_tz 40000"
        with self.assertRaisesRegex(RuntimeError, "No readable CPU"):
            self.owner.sample(all_zones=True)

    def test_cooling_hysteresis_excludes_wait_from_game_attempt(self):
        self.owner.battery_current_now = 0
        self.owner.battery = dict(celsius=34, level=80, status=4)
        self.owner.battery_zone_celsius = 34
        self.device.display.return_value = True
        with mock.patch.object(self.owner, "sample", side_effect=[70, 51, 50]) as sample, mock.patch.object(batch.time, "sleep") as sleep:
            self.owner.cool()
        self.assertEqual(sample.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.device.display.assert_called_once_with(False)
        self.assertIsNone(self.owner.previous)
        sample.assert_called_with(all_zones=True)

    def test_cooldown_excludes_power_zones_but_keeps_runtime_recording(self):
        self.device.display.return_value = True
        names = ("pm8550b_lite_tz", "pmic", "charger", "usb")
        text = "cpu-0 49000 /thermal_zone0/temp\n" + "\n".join(name + " 57763 /thermal_zone" + str(i) + "/temp" for i, name in enumerate(names, 1))
        self.device.cmd.return_value = text
        with mock.patch.object(batch.time, "sleep") as sleep:
            self.owner.cool()
        sleep.assert_not_called()
        row = json.loads(self.owner.trace.read_text())
        self.assertEqual(row["admission_maximum_celsius"], 49)
        self.assertEqual(row["maximum_zone_celsius"], 57.763)
        self.assertEqual([entry["type"] for entry in row["admission_excluded_zones"]], list(names))
        self.assertTrue(all(entry["raw"] == 57763 and entry["path"].endswith("/temp") for entry in row["admission_excluded_zones"]))
        self.assertEqual(len(self.owner.runtime_zones), 5)
        self.device.cmd.return_value = "49000\n57763\n81000\n57763\n57763"
        self.assertEqual(self.owner.sample(), 81)
        self.assertEqual(self.owner.peak_zone_celsius, 81)
        self.assertIn("81000", json.loads(self.owner.trace.read_text().splitlines()[-1])["all_zones_raw"])

    def runtime_sequence(self, zones, readings, times):
        self.owner.runtime_zones = [(name, "/thermal_zone" + str(i) + "/temp") for i, name in enumerate(zones)]
        self.device.cmd.side_effect = ["\n".join(str(round(value * 1000)) for value in row) for row in readings]
        with mock.patch.object(batch.time, "monotonic", side_effect=[at for at in times for _ in range(2)]):
            return [self.owner.sample() for _ in times]

    def test_j1152_isolated_core_spike_continues_and_is_recorded(self):
        values = [76.8, 77.2, 81.6, 78.8, 63.7]
        self.assertEqual(self.runtime_sequence(["cpu-0"], [[value] for value in values], [0, 0.3, 0.6, 0.9, 1.2]), values)
        self.assertEqual(self.owner.peak_cpu_celsius, 81.6)
        rows = [json.loads(line) for line in self.owner.trace.read_text().splitlines()]
        self.assertEqual([row["cpu_celsius"] for row in rows], values)
        self.assertIn("81600", rows[2]["all_zones_raw"])

    def test_sustained_core_heat_aborts_only_after_three_seconds(self):
        for name in ("cpu-0", "GPU-0"):
            self.owner.previous = None
            self.owner.hot_core_zones.clear()
            times = [i * 0.25 for i in range(12)]
            self.runtime_sequence(["cpu-0", name], [[49, 96]] * 12, times)
            with self.assertRaisesRegex(RuntimeError, "above 95 C for three seconds"):
                self.runtime_sequence(["cpu-0", name], [[49, 96]], [3])

    def test_heat_is_a_metric_and_skin_has_no_runtime_abort(self):
        values = [81, 85, 89, 95, 95]
        self.assertEqual(self.runtime_sequence(["cpu-0", "skin"], [[v, 60] for v in values], [0, 0.5, 1, 1.5, 2]), values)
        self.assertEqual(self.owner.time_above_80_seconds, 2)
        self.assertEqual(self.owner.peak_cpu_gpu_celsius, 95)
        self.assertEqual(json.loads(self.owner.trace.read_text().splitlines()[-1])["phase"], "gameplay")

    def test_battery_boundary(self):
        self.runtime_sequence(["cpu-0", "battery"], [[49, 42.999]], [0])
        with self.assertRaisesRegex(RuntimeError, "43 C"):
            self.runtime_sequence(["cpu-0", "battery"], [[49, 43]], [0.25])

    def test_core_streak_resets_at_95(self):
        values = [96, 96, 96, 95, 96, 96, 96]
        self.assertEqual(self.runtime_sequence(["cpu-0"], [[v] for v in values], [i * 0.5 for i in range(7)]), values)

    def test_heat_streak_cannot_transfer_between_zones_with_the_same_type(self):
        readings = [[96, 79], [79, 96]] * 8
        self.assertEqual(self.runtime_sequence(["cpu-0", "cpu-0"], readings, [i * 0.25 for i in range(16)]), [96] * 16)

    def test_runtime_gap_boundary_still_refuses_above_one_second(self):
        self.assertEqual(self.runtime_sequence(["cpu-0"], [[81], [81]], [0, 1]), [81, 81])
        with self.assertRaisesRegex(RuntimeError, "gap exceeded"):
            self.runtime_sequence(["cpu-0"], [[81]], [2.001])

    def test_admission_waits_for_cpu_gpu_battery_skin_only(self):
        for name in ("cpu-0", "GPU-0", "skin"):
            with self.subTest(name=name):
                self.device.cmd.side_effect = ["cpu-0 49000\n" + name + " 51000\nother 70000", "cpu-0 49000\n" + name + " 50000\nother 70000"]
                with mock.patch.object(batch.time, "sleep") as sleep:
                    self.owner.cool()
                sleep.assert_called_once_with(batch.THERMAL_INTERVAL_SECONDS)
                row = json.loads(self.owner.trace.read_text().splitlines()[-1])
                self.assertEqual(row["admission_maximum_celsius"], 50)
                self.assertEqual(row["maximum_zone_celsius"], 70)

    def test_battery_cooldown_and_charge_admission(self):
        for level, status, current, refused in ((80, 2, 0, False), (80, 2, 1, True), (80, 4, 1, True), (86, 4, 0, True), (85, 4, -1, False), (79, 2, 1, False)):
            with self.subTest(level=level, status=status, current=current):
                self.current.return_value = current
                self.device.cmd.return_value = "cpu-0 49000 /thermal_zone0/temp"
                observations = iter((351, 350))
                self.device.sh.side_effect = lambda *a, **k: f"temperature: {next(observations, 350)}\nlevel: {level}\nstatus: {status}"
                with mock.patch.object(batch.time, "sleep") as sleep:
                    if refused:
                        with self.assertRaisesRegex(RuntimeError, "charge separation/limit"):
                            self.owner.cool()
                        self.assertEqual(sleep.call_args_list, [] if level > 85 else [mock.call(10), mock.call(10)])
                    else:
                        self.owner.cool()
                        sleep.assert_called_once_with(batch.THERMAL_INTERVAL_SECONDS)
                        self.assertEqual(self.owner.admission_battery, dict(celsius=35, level=level, status=status))

    def test_transient_positive_current_does_not_refuse_admission(self):
        self.device.cmd.return_value = "cpu-0 49000 /thermal_zone0/temp"
        for readings in ([1, 0], [1, 1, -1]):
            with self.subTest(readings=readings), mock.patch.object(batch.time, "sleep") as sleep:
                self.current.side_effect = readings
                self.owner.cool()
                self.assertEqual(sleep.call_args_list, [mock.call(10)] * (len(readings) - 1))
                self.assertEqual(self.owner.admission_battery["level"], 80)

    def test_runtime_battery_service_boundary_is_recorded(self):
        self.owner.runtime_zones = [("cpu-0", "/thermal_zone0/temp")]
        self.device.cmd.return_value = "49000"
        self.device.sh.side_effect = ["temperature: 429\nlevel: 80\nstatus: 4", "temperature: 430\nlevel: 80\nstatus: 4"]
        self.owner.sample()
        with self.assertRaisesRegex(RuntimeError, "43 C"):
            self.owner.sample()
        self.assertEqual(json.loads(self.owner.trace.read_text().splitlines()[-1])["battery"], dict(celsius=43, level=80, status=4))

    def test_battery_missing_observation_refuses(self):
        for text in ("", "temperature: 340\nlevel: 80", "temperature: 340\nstatus: 4"):
            with self.subTest(text=text), self.assertRaisesRegex(RuntimeError, "Missing battery"):
                batch.battery_observation(text)

    def test_unknown_sentinel_or_missing_cpu_refuses_cooldown_with_raw_trace(self):
        for text in ("cpu-0 49000\nwireless -29999", "pm8550_tz 49000", "cpu-0 49000\nunknown 0", "cpu-0 49000\nbroken"):
            with self.subTest(text=text):
                self.device.cmd.return_value = text
                with self.assertRaises(RuntimeError):
                    self.owner.cool()
                row = json.loads(self.owner.trace.read_text().splitlines()[-1])
                self.assertEqual(row["all_zones_raw"], text)
                self.assertIn("error", row)
        self.device.launch.assert_not_called()

    def test_admission_records_sentinels_and_runtime_reads_only_valid_paths(self):
        self.device.display.return_value = True
        self.device.cmd.return_value = (
            "cpu-0 49000 /thermal_zone0/temp\nwls-therm -40960 /thermal_zone89/temp\nwireless -40000 /thermal_zone93/temp\nskin -30000 /thermal_zone95/temp"
        )
        self.owner.cool()
        row = json.loads(self.owner.trace.read_text())
        self.assertEqual(row["maximum_zone_celsius"], 49)
        self.assertEqual(
            [(e["type"], e["raw"], e["path"]) for e in row["excluded_zones"]],
            [
                ("wls-therm", -40960, "/thermal_zone89/temp"),
                ("wireless", -40000, "/thermal_zone93/temp"),
                ("skin", -30000, "/thermal_zone95/temp"),
            ],
        )
        self.device.cmd.return_value = "50000"
        self.assertEqual(self.owner.sample(), 50)
        self.device.cmd.assert_called_with("shell", "cat /thermal_zone0/temp", timeout=0.7)
        runtime = json.loads(self.owner.trace.read_text().splitlines()[-1])
        self.assertEqual(runtime["excluded_zones"], row["excluded_zones"])

    def test_previously_valid_sensor_becoming_sentinel_refuses_runtime(self):
        for raw in (-30000, -40000, -40960):
            with self.subTest(raw=raw):
                self.device.cmd.return_value = "cpu-0 49000 /thermal_zone0/temp\nskin 30000 /thermal_zone1/temp"
                self.owner.sample(all_zones=True)
                self.device.cmd.return_value = "49000\n" + str(raw)
                with self.assertRaisesRegex(RuntimeError, "Unknown/sentinel.*skin"):
                    self.owner.sample()

    def test_sentinel_cpu_does_not_supply_valid_coverage(self):
        self.device.cmd.return_value = "cpu-0 -40000 /thermal_zone0/temp\nwls-therm -40960 /thermal_zone89/temp\nwireless -40000 /thermal_zone93/temp"
        with self.assertRaisesRegex(RuntimeError, "No readable CPU"):
            self.owner.sample(all_zones=True)

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
        self.device.sh.return_value = "temperature: 340\nlevel: 80\nstatus: 4\n"
        self.device.serial = SERIAL
        self.device.read_receipt.return_value = dict(apk_sha256=HASH, serial=SERIAL, package="dev.ror2lab.arm64", package_path="package:/fixture/base.apk")
        self.device.cmd.side_effect = ["package:/fixture/base.apk", "73", PACKAGE + "\x00\n73", ""]
        self.owner.terminate_game()
        self.device.cmd.assert_called_with("shell", "am force-stop " + PACKAGE, timeout=2)


if __name__ == "__main__":
    unittest.main()
