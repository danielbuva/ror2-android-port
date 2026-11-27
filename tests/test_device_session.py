import hashlib
from contextlib import nullcontext
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import alpha_stability_batch as batch
import device as device_module
from device_context import DeviceContextError
import device_session as runner


def process_snapshot(*processes):
    date, clock = "2026-11-18", "03:20:00"
    return "\n".join([f"{date} {clock}", "PID STIME NAME", *(f"{pid} {date} {started} {name}" for pid, started, name in processes)])


class DeviceSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts/env.sh").touch()
        self.apk = self.root / "candidate.apk"
        self.apk.write_bytes(b"authored fixture")
        self.digest = hashlib.sha256(self.apk.read_bytes()).hexdigest()
        self.output = self.root / "work/run"
        self.request = dict(
            canonical_root=str(self.root),
            output=str(self.output),
            workstream="synthetic-worker",
            serial="synthetic-device",
            package="dev.ror2lab.arm64",
            apk=str(self.apk),
            apk_sha256=self.digest,
            adopted_install=True,
            duration_seconds=30,
            cooldown_seconds=60,
            mode="launch",
        )
        self.request_file = self.root / "request.json"
        runner.save(self.request_file, self.request)
        runner.save(self.root / "work/config/local.json", {"device_serial": self.request["serial"]})

    def test_request_smoke_checks_exact_bytes_without_adb(self):
        with mock.patch.object(runner.subprocess, "run") as process:
            self.assertEqual(runner.main(["--request", str(self.request_file), "--dry-run"]), 0)
        process.assert_not_called()
        self.apk.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            runner.load_request(self.request_file)

    def test_installed_alpha_request_has_no_local_game_apk_or_selector(self):
        request = dict(self.request, package="dev.ror2lab.alpha", mode=runner.INSTALLED_ALPHA)
        del request["apk"], request["apk_sha256"]
        request.update(
            installer_apk="installer.apk",
            installer_package="example.authorized.installer",
            installer_sha256="a" * 64,
            source_sha256="b" * 64,
        )
        runner.save(self.request_file, request)
        with mock.patch("installed_alpha.installer_trust", return_value={"keys": {"fixture": "example"}}) as trust:
            normalized = runner.load_request(self.request_file)
            self.assertNotIn("apk", normalized)
            trust.assert_called_once_with(str((self.root / "installer.apk").resolve()), request["installer_sha256"])
            runner.save(self.request_file, dict(request, selection={"attempt": "fixture"}))
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                runner.load_request(self.request_file)

    def test_installed_alpha_launch_observes_unity_before_returning(self):
        target = mock.Mock(package="dev.ror2lab.alpha")
        thermal = mock.Mock(error=None)
        launched = dict(pid="12", activity=target.package + "/dev.ror2owner.bootstrap.PayloadBootstrapActivity")
        unity = target.package + "/com.unity3d.player.UnityPlayerActivity"
        target.sh.side_effect = ["12", "  Display: mDisplayId=0\n  mCurrentFocus=Window{focus u0 " + unity + "}"]
        request = {"mode": runner.INSTALLED_ALPHA, "duration_seconds": 30}
        with (
            mock.patch.object(runner, "launch", return_value=launched),
            mock.patch.object(runner, "play_from_bootstrap") as play,
            mock.patch.object(runner, "capture") as capture,
        ):
            runner.run_workload(target, thermal, request, self.output, {})
        self.assertEqual(json.loads((self.output / "player-activity.json").read_text()), {"activity": unity, "pid": "12"})
        play.assert_called_once_with(target, thermal, "12", self.output)
        capture.assert_not_called()

    def test_installed_alpha_stops_only_the_verified_game_and_releases_lease(self):
        package = "dev.ror2lab.alpha"
        installed = dict(package=package, package_path="package:/fixture/base.apk", apk_sha256=self.digest)
        request = dict(
            self.request,
            package=package,
            mode=runner.INSTALLED_ALPHA,
            installer_package="example.authorized.installer",
            installer_sha256="a" * 64,
            installer_trust={"keys": {}},
            source_sha256="b" * 64,
        )
        targets = [mock.Mock(package=package), mock.Mock(package=package)]
        for selected in targets:
            selected.owned.return_value = installed
            selected.storage.return_value = {}
            selected.sh.side_effect = lambda command, *args, **kwargs: {
                "sh": process_snapshot(),
                "sha256sum": self.digest + "  /fixture/base.apk",
                "am": "",
                "pidof": "",
            }[command]
        with (
            mock.patch.object(runner, "source_environment"),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=32 * 1024**3)),
            mock.patch("installed_alpha.InstalledAlphaDevice", side_effect=targets),
            mock.patch("installed_alpha.verify_installed", return_value=installed),
            mock.patch.object(
                batch,
                "_GameThermalOwner",
                return_value=mock.Mock(error=None, admission_battery={}, peak_cpu_gpu_celsius=30, time_above_80_seconds=0),
            ),
            mock.patch.object(batch, "_prune"),
            mock.patch.object(runner, "prepare_launch"),
            mock.patch.object(runner, "placement", return_value={}),
            mock.patch.object(runner, "run_workload"),
            mock.patch.object(runner, "reset_idle") as reset,
        ):
            result = runner.execute(request)
        self.assertTrue(result["success"], result.get("error") or result.get("cleanup_errors"))
        self.assertTrue(result["terminal_readback"]["oled_asleep"])
        self.assertTrue(result["lease_released"])
        self.assertIn(mock.call("am", "force-stop", package), targets[0].sh.call_args_list)
        targets[1].display.assert_called_once_with(False)
        targets[0].install.assert_not_called()
        targets[0].sync.assert_not_called()
        reset.assert_not_called()

    def test_menu_start_rejects_selector_for_a_different_apk_attempt(self):
        request = dict(self.request, start_from_menu=True, selection={"attempt": "run-folder"})
        runner.save(self.request_file, request)
        with (
            mock.patch.object(device_module, "validate_apk_identity") as identity,
            mock.patch("installed_attempt.attempt_from_installed", return_value="embedded"),
        ):
            with self.assertRaisesRegex(ValueError, "selector attempt must match.*embedded"):
                runner.load_request(self.request_file)
            identity.assert_called_once_with(self.apk.resolve(), self.request["package"])
            runner.save(self.request_file, dict(request, selection={"attempt": "embedded"}))
            self.assertEqual(runner.load_request(self.request_file)["selection"]["attempt"], "embedded")

    def test_pre_dispatch_rejects_another_packages_local_receipt(self):
        request = dict(self.request, start_from_menu=True)
        runner.save(self.request_file, request)
        receipt_path = self.root / "work/device/installed.json"
        receipt = dict(serial=request["serial"], package="dev.ror2lab.converted", package_path="package:/fixture/base.apk", apk_sha256="0" * 64)
        runner.save(receipt_path, receipt)
        with (
            mock.patch.object(device_module, "validate_apk_identity"),
            mock.patch("installed_attempt.attempt_from_installed", return_value="embedded"),
            mock.patch.object(runner.Lease, "acquire") as lease,
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt does not match selected package/device"):
                runner.main(["--request", str(self.request_file), "--detach"])
            lease.assert_not_called()
            runner.save(receipt_path, dict(receipt, package=request["package"]))
            self.assertEqual(runner.load_request(self.request_file)["apk_sha256"], self.digest)

    def test_owner_unplugged_requires_ordinary_adopted_30_minute_run(self):
        request = dict(self.request, mode="owner-unplugged", duration_seconds=1800)
        runner.save(self.request_file, request)
        self.assertEqual(runner.load_request(self.request_file)["mode"], "owner-unplugged")
        for changes, error in (
            (dict(duration_seconds=30), "requires 30 minutes"),
            (dict(adopted_install=False), "adopted_install"),
            (dict(selection={}), "physical play"),
            (dict(start_from_menu=True), "physical play"),
        ):
            with self.subTest(changes=changes):
                runner.save(self.request_file, dict(request, **changes))
                with self.assertRaisesRegex(ValueError, error):
                    runner.load_request(self.request_file)

    def test_unplugged_trace_checks_coverage_ownership_and_signed_energy(self):
        config = dict(nonce="a" * 32, zones=[["cpu", "cpu-path"], ["gpu", "gpu-path"]])
        base = dict(nonce=config["nonce"], pid=42)
        samples = [
            dict(
                base,
                kind="sample",
                elapsed_ms=ms,
                gap_ms=1000,
                plugged=0,
                frames=ms * 60 // 1000,
                current_ua=-250000,
                voltage_mv=4000,
                level=80 - ms // 900000,
                scale=100,
                battery_decic=300,
                zones_millic=[81000, 64000],
            )
            for ms in range(0, 1800001, 1000)
        ]
        trace = self.root / "observed.jsonl"
        ready = dict(base, kind="ready", zones=config["zones"])
        complete = dict(base, kind="complete")

        def write(rows):
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))

        write([ready, *samples, complete])
        summary = runner.unplugged_summary(trace, config, "42")
        self.assertEqual(summary["signed_terminal_energy_mwh"], -500)
        self.assertEqual(summary["foreground_frames_per_elapsed_second"], 60)
        self.assertEqual(summary["time_above80_seconds"], 1800)
        self.assertEqual((summary["battery_start_percent"], summary["battery_end_percent"]), (80, 78))
        for rows, error in (
            ([ready, *samples[:-1], complete], "does not cover"),
            ([ready, *samples, dict(complete, pid=43)], "different nonce or process"),
            ([ready, *samples, dict(base, kind="aborted", reason="early reconnect")], "early reconnect"),
            ([ready, dict(samples[0], plugged=2), *samples[1:], complete], "powered"),
            ([ready, dict(samples[0], gap_ms=5001), *samples[1:], complete], "thermal coverage"),
            ([ready, dict(samples[0], battery_decic=430), *samples[1:], complete], "Battery thermal limit"),
        ):
            with self.subTest(error=error):
                write(rows)
                with self.assertRaisesRegex(RuntimeError, error):
                    runner.unplugged_summary(trace, config, "42")

    def test_owner_unplugged_waits_without_adb_then_collects_after_usb_reconnect(self):
        config = dict(nonce="a" * 32, zones=[["cpu", "cpu-path"], ["gpu", "gpu-path"]])
        runner.save(self.output / runner.UNPLUGGED_REQUEST, config)
        target = mock.Mock()
        target.read_receipt.return_value = dict(persistentDataPath="/owned")
        target.sh.side_effect = [json.dumps(dict(kind="ready", pid=42, **config)), '{"kind":"complete"}']
        target.cmd.side_effect = ["offline", "device"]
        result = dict(device_cleanup={})

        def wait(seconds):
            if seconds == 1800:
                target.cmd.assert_not_called()
                self.assertEqual(target.sh.call_count, 1)
                self.assertTrue((self.output / "unplug-now.json").is_file())

        with (
            mock.patch.object(runner.time, "sleep", side_effect=wait) as sleeper,
            mock.patch.object(runner, "verify_owned") as verify,
            mock.patch.object(device_module, "retain_device_file", return_value="trace-hash") as retain,
            mock.patch.object(runner, "unplugged_summary", return_value=dict(samples=7201)) as summary,
        ):
            runner.observe_unplugged(target, self.request, self.output, result, "42")
        self.assertEqual(sleeper.call_args_list, [mock.call(1800), mock.call(5)])
        trace = f"owner-unplugged-{config['nonce']}.jsonl"
        self.assertEqual(result["owner_unplugged"], dict(trace=trace, sha256="trace-hash", samples=7201))
        verify.assert_called_once_with(target, self.digest)
        retain.assert_called_once_with(target, "/owned/" + trace, self.output / trace, {})
        summary.assert_called_once_with(self.output / trace, config, "42")

    def test_device_option_selects_only_the_workstreams_granted_serial(self):
        self.request.pop("serial")
        self.request.pop("adopted_install")
        runner.save(self.request_file, self.request)
        grant = self.root / ".local/orchestrator/devqueue/second-fixture.granted"
        grant.parent.mkdir(parents=True)
        grant.write_text("another-worker\n")
        with self.assertRaisesRegex(ValueError, "queue grant"):
            runner.load_request(self.request_file, "second-fixture")
        grant.write_text(self.request["workstream"] + "\n")
        self.assertEqual(runner.load_request(self.request_file, "second-fixture")["serial"], "second-fixture")
        with mock.patch.object(runner.subprocess, "Popen", return_value=mock.Mock(pid=12)) as process:
            self.assertEqual(runner.main(["--request", str(self.request_file), "--device", "second-fixture", "--detach"]), 0)
        self.assertEqual(process.call_args.args[0][-2:], ["--device", "second-fixture"])

    def test_internal_placement_checks_apk_data_and_scratch_capacity(self):
        package = self.request["package"]
        storage = dict(mode="internal", internal=dict(total_bytes=100, free_bytes=runner.DEVICE_RESERVE_BYTES), shared=dict(total_bytes=100))
        target = mock.Mock(package=package)
        target.storage.return_value = storage
        target.owned.return_value = dict(package_path="package:/data/app/base.apk")
        target.sh.return_value = "  dataDir=/data/user/0/" + package + "\n"
        target.install_capacity.return_value = dict(estimate_bytes=6 * 1024**3)
        with self.assertRaisesRegex(RuntimeError, "requires adopted"):
            runner.placement(target, 1, adopted_only=True)
        with self.assertRaisesRegex(RuntimeError, "Insufficient internal free space"):
            runner.placement(target, 1, install_apk=self.apk)
        storage["internal"]["free_bytes"] += 1024**3
        self.assertIs(runner.placement(target, 1, install_apk=self.apk), storage)
        target.owned.return_value["package_path"] = "package:/mnt/expand/fixture/app/base.apk"
        with self.assertRaisesRegex(RuntimeError, "Owned package"):
            runner.placement(target, 1)
        target.owned.return_value["package_path"] = "package:/data/app/base.apk"
        target.sh.return_value = "  dataDir=/mnt/expand/fixture/user/0/" + package + "\n"
        with self.assertRaisesRegex(RuntimeError, "Owned runtime data"):
            runner.placement(target, 1)

    def test_busy_lease_refuses_before_any_adb_and_preserves_owner(self):
        lease = runner.Lease(self.request)
        lease.acquire()
        with mock.patch.object(runner, "source_environment"), mock.patch.object(runner.subprocess, "run") as adb, mock.patch.object(batch, "_prune"):
            result = runner.execute(self.request)
        adb.assert_not_called()
        self.assertFalse(result["success"])
        self.assertFalse(result["lease_released"])
        self.assertEqual(json.loads((lease.path / "owner.json").read_text()), lease.owner)
        self.assertTrue((self.output / "terminal.done.json").is_file())

    def test_discovery_failure_releases_lease_before_writing_failed_terminal(self):
        lease = runner.Lease(self.request)

        def discover(**_kwargs):
            self.assertEqual(json.loads((lease.path / "owner.json").read_text()), lease.owner)
            raise DeviceContextError("Selected device is not attached and authorized")

        with (
            mock.patch.object(runner, "source_environment"),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
            mock.patch.object(runner.subprocess, "run"),
            mock.patch.object(device_module, "Device", side_effect=discover),
            mock.patch.object(runner, "reset_other_lab") as reset,
            mock.patch.object(batch, "_prune"),
        ):
            result = runner.execute(self.request)

        reset.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("Selected device is not attached and authorized", result["error"])
        self.assertTrue(result["lease_released"])
        self.assertFalse(lease.path.exists())
        self.assertEqual(json.loads((self.output / "terminal.done.json").read_text()), result)

    def test_interrupted_preinstall_hash_can_finish_verified_cleanup(self):
        lease_path = runner.Lease(self.request).path
        package_path = "/fixture/base.apk"
        target = mock.Mock()
        target.exists.return_value = True
        target.owned.return_value = dict(package_path="package:" + package_path, apk_sha256=self.digest)
        target.storage.return_value = dict(mode="adopted")
        hashes = iter([RuntimeError("adb exited -9"), self.digest, self.digest])

        def shell(*args, **kwargs):
            self.assertTrue(lease_path.is_dir())
            if args == ("sha256sum", package_path):
                digest = next(hashes)
                if isinstance(digest, RuntimeError):
                    raise digest
                return digest + "  " + package_path
            self.assertEqual(args, ("am", "force-stop", target.package))
            return ""

        target.sh.side_effect = shell

        def idle(device, expected):
            self.assertTrue(lease_path.is_dir())
            self.assertEqual(expected, self.digest)
            return dict(apk_sha256=expected, process_absent=True)

        def display(awake):
            self.assertTrue(lease_path.is_dir())
            self.assertFalse(awake)
            return True

        target.display.side_effect = display
        with (
            mock.patch.object(runner, "source_environment"),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
            mock.patch.object(device_module, "Device", return_value=target) as discover,
            mock.patch.object(runner, "reset_other_lab"),
            mock.patch.object(runner, "reset_idle") as reset,
            mock.patch.object(batch, "_idle_readback", side_effect=idle),
            mock.patch.object(batch, "_prune"),
        ):
            result = runner.execute(self.request)

        self.assertFalse(result["success"])
        self.assertIn("adb exited -9", result["error"])
        target.install.assert_not_called()
        reset.assert_called_once()
        self.assertEqual(discover.call_count, 2)
        self.assertTrue(result["terminal_readback"]["oled_asleep"])
        self.assertTrue(result["lease_released"])
        self.assertFalse(lease_path.exists())

    def test_storage_rejection_with_absent_package_releases_after_verified_sleep(self):
        lease_path = runner.Lease(self.request).path
        target, independent = mock.Mock(), mock.Mock()
        target.exists.return_value = False
        independent.exists.return_value = False
        independent.storage.return_value = dict(mode="internal")
        independent.display.return_value = True
        with (
            mock.patch.object(runner, "source_environment"),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
            mock.patch.object(device_module, "Device", side_effect=[target, independent]),
            mock.patch.object(runner, "reset_other_lab"),
            mock.patch.object(runner, "placement", side_effect=RuntimeError("This request requires adopted storage")),
            mock.patch.object(batch, "_prune"),
        ):
            result = runner.execute(self.request)

        target.install.assert_not_called()
        independent.display.assert_called_once_with(False)
        self.assertFalse(result["success"])
        self.assertIn("requires adopted storage", result["error"])
        self.assertEqual(result["terminal_readback"], dict(installed=False, oled_asleep=True))
        self.assertTrue(result["lease_released"])
        self.assertFalse(lease_path.exists())

    def test_menu_observation_records_owned_roster_without_starting(self):
        target, thermal = mock.Mock(package="dev.ror2lab.alpha"), mock.Mock(error=None)
        menu = dict(
            phase="offline-start-menu",
            pid=12,
            attempt="owned-attempt",
            selectedSurvivor="Commando",
            hud=dict(survivorRosterCount=20, survivorSelectableCount=2),
        )
        with mock.patch.object(runner, "wait_for_settings_report", return_value=menu) as observe:
            result = runner.observe_start_menu(target, thermal, "12", self.output, report_id="ordinary", attempt=menu["attempt"])
        self.assertEqual(result, menu)
        self.assertEqual(json.loads((self.output / "start-menu.json").read_text()), menu)
        self.assertTrue(observe.call_args.args[3](menu))
        self.assertFalse(observe.call_args.args[3]({"phase": "integrated-world-playing"}))
        self.assertEqual(observe.call_args.kwargs["attempt"], menu["attempt"])
        self.assertEqual(target.mock_calls, [])

    def test_menu_start_waits_for_owned_menu_and_world_before_sampling(self):
        target, thermal = mock.Mock(package=self.request["package"]), mock.Mock(error=None)
        target.sh.return_value = process_snapshot(("12", "03:19:58", target.package))
        process_checks = []
        hud = dict(menuStartX=170.67, menuStartY=757.33, screenWidth=1920, screenHeight=1080)
        menu = dict(phase="offline-start-menu", hud=hud, attempt="owned-attempt")
        gameplay_report = dict(phase="integrated-world-playing", world=dict(ready=True))
        reports = [menu, gameplay_report, menu, gameplay_report]
        attempts = iter([None, menu["attempt"], menu["attempt"], menu["attempt"]])
        gameplay_route = "body-state-spawn-state-auto-player"

        def observed(device, monitor, pid, predicate, timeout, *, report_id, attempt=None):
            self.assertEqual(report_id, gameplay_route)
            report = reports.pop(0)
            self.assertTrue(predicate(report))
            self.assertEqual(attempt, next(attempts))
            return report

        with (
            mock.patch.object(runner, "wait_for_settings_report", side_effect=observed),
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=True),
        ):
            self.assertEqual(
                runner.start_from_menu(target, thermal, "12", self.output, process_checks=process_checks, report_id=gameplay_route), gameplay_report
            )
            self.assertEqual(
                runner.start_from_menu(
                    target, thermal, "12", self.output, process_checks=process_checks, report_id=gameplay_route, tap_start=True, attempt=menu["attempt"]
                ),
                gameplay_report,
            )
        target.sh.assert_any_call("input", "keyboard", "keyevent", "KEYCODE_ENTER")
        target.sh.assert_any_call("input", "-d", "0", "tap", "171", "757", timeout=5)
        target.collect.assert_called_once_with("screenshot", self.output)
        self.assertTrue((self.output / "world-start.json").is_file())
        with (
            mock.patch.object(runner, "wait_for_settings_report", return_value=menu),
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=False),
        ):
            target.sh.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "focus absent"):
                runner.start_from_menu(target, thermal, "12", self.output, process_checks=process_checks)
        self.assertFalse(any(call.args[:1] == ("input",) for call in target.sh.call_args_list))

    def test_process_check_scopes_installer_alpha_to_the_selected_package(self):
        alpha = "dev.ror2lab.alpha"
        target = mock.Mock(package=alpha)
        target.sh.return_value = process_snapshot(("42", "03:19:58", alpha))
        checks = []
        runner.check_lab_processes(target, checks, "launch", "42")
        self.assertEqual([row["package"] for row in checks[0]["processes"]], [alpha])

        target.package = self.request["package"]
        runner.check_lab_processes(target, checks, "before-launch")
        self.assertEqual(checks[1]["processes"], [])

    def test_menu_start_records_second_lab_process_and_blocks_input(self):
        target, thermal = mock.Mock(package="dev.ror2lab.converted"), mock.Mock(error=None)
        target.sh.return_value = process_snapshot(
            ("42", "03:19:58", target.package), ("12", "03:19:55", "dev.ror2lab.arm64"), ("20", "03:19:10", "dev.ror2lab.unrelated")
        )
        checks = []
        with mock.patch.object(runner, "wait_for_settings_report", return_value=dict(phase="offline-start-menu")):
            with self.assertRaisesRegex(RuntimeError, "Unexpected owned lab process at start"):
                runner.start_from_menu(target, thermal, "42", self.output, process_checks=checks)
        self.assertEqual(checks[0]["device_time"], "2026-11-18 03:20:00")
        self.assertEqual(
            checks[0]["processes"],
            [
                dict(pid="42", start_time="2026-11-18 03:19:58", package=target.package, name=target.package),
                dict(pid="12", start_time="2026-11-18 03:19:55", package="dev.ror2lab.arm64", name="dev.ror2lab.arm64"),
            ],
        )
        self.assertEqual(target.sh.call_count, 1)
        self.assertEqual(target.sh.call_args.kwargs["timeout"], 5)

    def test_menu_start_request_is_explicit_launch_only(self):
        self.request["start_from_menu"] = True
        with mock.patch.object(device_module, "validate_apk_identity"), mock.patch("installed_attempt.attempt_from_installed", return_value="embedded"):
            for package in ("dev.ror2lab.arm64", "dev.ror2lab.converted"):
                runner.save(self.request_file, dict(self.request, package=package))
                self.assertTrue(runner.load_request(self.request_file)["start_from_menu"])
        for field, value in (("start_from_menu", "yes"), ("mode", "sustained")):
            runner.save(self.request_file, dict(self.request, **{field: value}))
            with self.assertRaises(ValueError):
                runner.load_request(self.request_file)

    def test_converted_launch_starts_from_the_owned_menu_after_bootstrap_input(self):
        from session_cleanup_check import SPINE_ID

        gesture = self.root / "bootstrap.json"
        runner.save(gesture, dict(width=1280, height=960, steps=[dict(action="wait", ms=100)]))
        request = dict(self.request, package="dev.ror2lab.converted", input_script=str(gesture), start_from_menu=True, duration_seconds=0)
        device, thermal = mock.Mock(package=request["package"]), mock.Mock()
        device.sh.return_value = "7"
        thermal.cancelled.is_set.return_value = False
        result = {}
        calls = mock.Mock()
        calls.input.return_value = {"success": True}
        with (
            mock.patch("touch_gesture.run", calls.input),
            mock.patch.object(runner, "start_from_menu", calls.menu),
            mock.patch.object(runner, "capture", calls.capture),
        ):
            runner.observe_launch(device, thermal, request, self.output, result, "7", start_attempt="converted-attempt")
        self.assertEqual(
            calls.mock_calls[:2],
            [
                mock.call.input(self.output / "input.json", self.digest, device=device),
                mock.call.menu(
                    device,
                    thermal,
                    "7",
                    self.output,
                    process_checks=[],
                    report_id=SPINE_ID.removesuffix("-bringup"),
                    tap_start=True,
                    attempt="converted-attempt",
                ),
            ],
        )

    def test_converted_stage_transition_uses_the_selected_run_and_stops_in_destination(self):
        from session_cleanup_check import SPINE_ID

        route = {"from": "golemplains", "to": "goolake"}
        request = dict(self.request, start_from_menu=True, stage_transition=route, selection={"id": SPINE_ID})
        device, thermal = mock.Mock(package="dev.ror2lab.converted"), mock.Mock()
        device.sh.return_value = "7"
        device.read_receipt.return_value = {"persistentDataPath": "/owned"}
        thermal.cancelled.is_set.return_value = False
        world = dict(pid=7, id=SPINE_ID, attempt="converted-attempt", session=1, stage={"scene": "golemplains"}, stageProgress={"transitions": 0})
        destination = dict(
            world,
            phase="integrated-world-playing",
            stage={"scene": "goolake"},
            stageProgress={
                "transitions": 1,
                "actualScene": "goolake",
                "actualSceneDef": "goolake",
                "requested": "goolake",
                "transporting": False,
                "activeSceneVerified": True,
                "enteredAt": 100,
            },
            world={"seconds": 110, "ready": True},
        )
        result = {}
        with (
            mock.patch.object(runner, "start_from_menu", return_value=world) as menu,
            mock.patch.object(runner, "capture") as capture,
            mock.patch("session_cleanup_check._read_json", side_effect=[dict(destination, session=2), destination]) as read_report,
            mock.patch.object(runner.time, "sleep"),
        ):
            runner.observe_launch(device, thermal, request, self.output, result, "7", start_attempt="converted-attempt")
        self.assertEqual(menu.call_args.kwargs["report_id"], SPINE_ID)
        self.assertEqual(read_report.call_count, 2)
        self.assertEqual(capture.call_args.args[1], self.output / "final")
        self.assertEqual(result["stage_transition"], route)
        self.assertEqual(json.loads((self.output / "stage-transition.json").read_text()), destination)
        self.assertFalse(runner.stage_transition_ready(dict(destination, world={"seconds": 109, "ready": True}), route))
        with self.assertRaisesRegex(RuntimeError, "Expected one completed transition"):
            runner.stage_transition_ready(dict(destination, stageProgress=dict(destination["stageProgress"], transitions=2)), route)

    def test_converted_menu_workload_waits_for_visible_bootstrap_play(self):
        package = "dev.ror2lab.converted"
        request = dict(self.request, package=package, start_from_menu=True)
        device, thermal = mock.Mock(package=package), mock.Mock(error=None)
        states = iter((None, "Pause", "Resume", "Play"))
        taps = []
        current = None

        def shell(*args, **kwargs):
            nonlocal current
            if args[0] == "pidof":
                return "7"
            if args[0] == "uiautomator":
                current = next(states)
                return "ERROR: could not get idle state." if current is None else "UI hierchary dumped to: " + args[-1]
            if args[0] == "cat":
                return (
                    f'<hierarchy><node package="{package}" class="android.widget.Button" enabled="true" text="{current}" bounds="[10,20][50,60]"/></hierarchy>'
                )
            if args[0] == "input":
                taps.append((current, args))
            return ""

        device.sh.side_effect = shell
        activity = package + "/dev.ror2owner.bootstrap.PayloadBootstrapActivity"
        with (
            mock.patch.object(runner, "launch", return_value=dict(pid="7", activity=activity)),
            mock.patch.object(runner, "observe_launch") as observe,
            mock.patch.object(runner.time, "sleep"),
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=True),
        ):
            result = {}
            runner.run_workload(device, thermal, request, self.output, result, start_attempt="converted-attempt")
        self.assertEqual(taps, [("Play", ("input", "-d", "0", "tap", "30", "40"))])
        observe.assert_called_once_with(device, thermal, request, self.output, result, "7", start_attempt="converted-attempt")
        self.assertEqual(json.loads((self.output / "bootstrap-play.json").read_text())["tap"], [30, 40])
        scratch = next(call.args[-1] for call in device.sh.call_args_list if call.args[0] == "uiautomator")
        self.assertTrue(scratch.startswith("/sdcard/"))
        device.sh.assert_any_call("rm", "-f", scratch, timeout=5)

    def test_bootstrap_play_reference_waits_for_label_at_matching_viewport(self):
        from PIL import Image, ImageDraw

        def screen(label, size=(128, 96), *, dimmed=False):
            frame = Image.new("RGB", size, "gold")
            ImageDraw.Draw(frame).text((40, 51), label, fill="black")
            if dimmed:
                frame = frame.point(lambda value: (7 * value) // 10)
            buffer = BytesIO()
            frame.save(buffer, format="PNG")
            return buffer.getvalue()

        self.output.mkdir(parents=True)
        reference = self.output / "ready.png"
        ready = screen("Play")
        reference.write_bytes(ready)
        request = dict(
            self.request,
            package="dev.ror2lab.converted",
            start_from_menu=True,
            bootstrap_play_reference=dict(png=str(reference), bounds=[36, 46, 68, 66]),
        )
        runner.save(self.request_file, request)
        with (
            mock.patch.object(device_module, "validate_apk_identity"),
            mock.patch("installed_attempt.attempt_from_installed", return_value="embedded"),
        ):
            request = runner.load_request(self.request_file)

        device = mock.Mock(package=request["package"], base=["adb", "-s", "synthetic-device"])
        device.sh.return_value = "7"
        thermal = mock.Mock(error=None)
        dimmed_ready = screen("Play", dimmed=True)
        frames = [mock.Mock(stdout=image) for image in (screen("Pause"), screen("Pause", dimmed=True), screen("Play", (140, 96)), dimmed_ready)]
        with (
            mock.patch.object(runner.subprocess, "run", side_effect=frames) as capture,
            mock.patch.object(runner.time, "sleep"),
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=True),
        ):
            runner.play_from_bootstrap(device, thermal, "7", self.output, request["bootstrap_play_reference"])
        self.assertEqual(capture.call_count, 4)
        self.assertEqual([call.args for call in device.sh.call_args_list if call.args[0] == "input"], [("input", "-d", "0", "tap", "52", "56")])
        self.assertEqual((self.output / "bootstrap-play.png").read_bytes(), dimmed_ready)
        self.assertEqual(json.loads((self.output / "bootstrap-play.json").read_text())["observed_by"], "screenshot")

    def test_combat_capture_is_opt_in_for_native_lab_launch(self):
        for flag in ("capture_golem_attacks", "capture_titan_indicator"):
            with self.subTest(flag=flag):
                runner.save(self.request_file, self.request)
                self.assertNotIn(flag, runner.load_request(self.request_file))
                request = dict(self.request, **{flag: True})
                runner.save(self.request_file, request)
                self.assertTrue(runner.load_request(self.request_file)[flag])
                for field, value in ((flag, "yes"), ("mode", "sustained"), ("package", "dev.ror2lab.converted")):
                    runner.save(self.request_file, dict(request, **{field: value}))
                    with self.assertRaises(ValueError):
                        runner.load_request(self.request_file)

    def test_video_requires_a_bounded_menu_or_direct_survivor_observation(self):
        from session_cleanup_check import SPINE_ID

        with (
            mock.patch.object(device_module, "validate_apk_identity"),
            mock.patch("installed_attempt.attempt_from_installed", return_value="embedded"),
        ):
            request = dict(self.request, start_from_menu=True, capture_video=True)
            runner.save(self.request_file, request)
            self.assertTrue(runner.load_request(self.request_file)["capture_video"])
            selection = dict(attempt="embedded", id=SPINE_ID.removesuffix("-bringup"), developerSurvivorOverride=True)
            direct = dict(request, start_from_menu=False, selection=selection)
            runner.save(self.request_file, direct)
            self.assertTrue(runner.load_request(self.request_file)["capture_video"])
            for changes in (
                dict(start_from_menu=False),
                dict(duration_seconds=181),
                dict(stage_transition={"from": "blackbeach2", "to": "golemplains"}),
            ):
                with self.subTest(changes=changes):
                    runner.save(self.request_file, dict(request, **changes))
                    with self.assertRaisesRegex(ValueError, "capture_video requires"):
                        runner.load_request(self.request_file)
            for changes in (
                dict(package="dev.ror2lab.converted"),
                dict(mode="sustained"),
                dict(selection=dict(selection, id="unrelated-route")),
                dict(selection=dict(selection, developerSurvivorOverride=False)),
            ):
                with self.subTest(changes=changes):
                    runner.save(self.request_file, dict(direct, **changes))
                    with self.assertRaisesRegex(ValueError, "capture_video requires"):
                        runner.load_request(self.request_file)
            runner.save(self.request_file, dict(direct, selection=dict(selection, attempt="stale")))
            with self.assertRaisesRegex(ValueError, "selector attempt must match.*embedded"):
                runner.load_request(self.request_file)

    def test_direct_survivor_video_waits_for_its_world_before_scheduled_input(self):
        from session_cleanup_check import SPINE_ID

        gesture = self.root / "gesture.json"
        runner.save(gesture, dict(width=1280, height=960, steps=[dict(action="wait", ms=100)]))
        report_id = SPINE_ID.removesuffix("-bringup")
        request = dict(
            self.request, selection={"id": report_id}, capture_video=True, duration_seconds=0, input_schedule=[dict(at_seconds=0, script=str(gesture))]
        )
        device = mock.Mock(package=request["package"])
        device.sh.return_value = "7"
        thermal = mock.Mock()
        thermal.cancelled.is_set.return_value = False
        result = {}
        calls = mock.Mock()
        calls.video.return_value = nullcontext()
        calls.input.return_value = {"success": True}
        with (
            mock.patch.object(runner, "wait_for_world_start", calls.world),
            mock.patch.object(runner, "start_from_menu", calls.menu),
            mock.patch.object(runner, "capture_launch_video", calls.video),
            mock.patch("touch_gesture.run", calls.input),
            mock.patch.object(runner, "capture"),
        ):
            runner.observe_launch(device, thermal, request, self.output, result, "7", start_attempt="embedded")
        self.assertEqual(
            calls.mock_calls,
            [
                mock.call.world(device, thermal, "7", self.output, report_id=report_id, attempt="embedded"),
                mock.call.video(device, thermal, "7", self.output, 0, result),
                mock.call.input(self.output / "scheduled-input-0.json", self.digest, device=device),
            ],
        )

    def test_video_retains_its_recording_and_stops_only_its_recorder_on_abort(self):
        for abort in (False, True):
            with self.subTest(abort=abort):
                target = mock.Mock(package=self.request["package"])
                target.read_receipt.return_value = {"persistentDataPath": "/sdcard/owned"}
                started, stopped = runner.threading.Event(), runner.threading.Event()

                def shell(*args, **kwargs):
                    if args[0] == "screenrecord":
                        started.set()
                        if abort and not stopped.wait(5):
                            raise RuntimeError("recorder did not receive its stop")
                    if args[0] == "pkill":
                        stopped.set()
                    return "12"

                target.sh.side_effect = shell
                result = {"device_cleanup": {}}
                thermal = mock.Mock(error=None)
                with (
                    mock.patch("touch_gesture.owned_display_zero_focus", return_value=True),
                    mock.patch.object(device_module, "retain_device_file", return_value="digest") as retain,
                    mock.patch.object(device_module, "remove_device_file") as remove,
                ):
                    try:
                        with runner.capture_launch_video(target, thermal, "12", self.output, 35, result):
                            self.assertTrue(started.wait(5))
                            if abort:
                                raise RuntimeError("thermal abort")
                    except RuntimeError as error:
                        if not abort:
                            raise
                        self.assertEqual(str(error), "thermal abort")

                command = next(call.args for call in target.sh.call_args_list if call.args[0] == "screenrecord")
                remote = command[-1]
                self.assertEqual(command[1:-1], ("--bit-rate", "5000000", "--time-limit", "35"))
                if abort:
                    self.assertTrue(stopped.is_set())
                    self.assertNotIn("video", result)
                    retain.assert_not_called()
                    remove.assert_called_once_with(target, remote, {}, missing_ok=True)
                else:
                    self.assertFalse(stopped.is_set())
                    video = result["video"]
                    self.assertEqual((video["pid"], video["sha256"]), (12, "digest"))
                    retain.assert_called_once_with(target, remote, self.output / video["file"], {})
                    remove.assert_not_called()

    def test_attack_capture_uses_matching_native_state_and_open_display(self):
        self.output.mkdir(parents=True)
        target = mock.Mock(package="dev.ror2lab.arm64", base=["adb", "-s", "synthetic-device"])
        target.sh.side_effect = ["12", "window fixture"]
        thermal = mock.Mock(cancelled=runner.threading.Event())
        stopping = runner.threading.Event()
        stale = "  100.000 11 33 I Unity   : EntityStates.GolemMonster.ClapState:OnEnter()"
        unrelated = "  100.001 12 33 I Unity   : EntityStates.GolemMonster.ChargeLaser:OnEnter()"
        attack = "  100.002 12 33 I Unity   : EntityStates.GolemMonster.ClapState:OnEnter()"
        png = b"\x89PNG\r\n\x1a\n"
        events = []
        with (
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=True) as focus,
            mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(stdout=png)) as snap,
        ):
            runner.record_event_frames(target, thermal, "12", self.output, [stale, unrelated, attack], stopping, events, runner.GOLEM_ATTACK)
        focus.assert_called_once_with("window fixture", target.package)
        self.assertEqual(snap.call_count, 3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["log"], attack.strip())
        self.assertEqual([(self.output / frame["file"]).read_bytes() for frame in events[0]["frames"]], [png] * 3)

    def test_attack_capture_rejects_focus_outside_owned_display(self):
        target, thermal = mock.Mock(), mock.Mock(cancelled=runner.threading.Event())
        target.sh.return_value = "12"
        attack = "  100.002 12 33 I Unity   : EntityStates.GolemMonster.FireLaser:OnEnter()"
        events = []
        with mock.patch("touch_gesture.owned_display_zero_focus", return_value=False), mock.patch.object(runner.subprocess, "run") as snap:
            runner.record_event_frames(target, thermal, "12", self.output, [attack], runner.threading.Event(), events, runner.GOLEM_ATTACK)
        snap.assert_not_called()
        self.assertEqual(events[0]["skipped"], "owned display-zero focus absent")

    def test_titan_capture_requires_exact_owned_renderer_log(self):
        target, thermal = mock.Mock(), mock.Mock(cancelled=runner.threading.Event())
        target.sh.return_value = "12"
        stale = "  100.000 11 33 I Unity   : lab-titan-prefist-visible frame=7200"
        other = "  100.001 12 33 I Unity   : EntityStates.GolemMonster.FireLaser:OnEnter()"
        visible = "  100.002 12 33 I Unity   : lab-titan-prefist-visible frame=7230"
        events = []
        with mock.patch("touch_gesture.owned_display_zero_focus", return_value=False):
            runner.record_event_frames(target, thermal, "12", self.output, [stale, other, visible], runner.threading.Event(), events, runner.TITAN_INDICATOR)
        self.assertEqual([event["log"] for event in events], [visible.strip()])

    def test_periodic_capture_retains_heap_and_android_exit_reasons(self):
        target = mock.Mock()
        target.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        target.sh.return_value = "{}"
        target.cmd.return_value = "fixture log"
        runner.capture(target, self.output, "12")
        target.collect.assert_has_calls(
            [mock.call("crash", self.output), mock.call("screenshot", self.output), mock.call("perf", self.output, include_exceptions=False)]
        )

    def test_settings_failure_mode_uses_shared_launch_and_thermal_owner(self):
        self.request["mode"] = "settings-save-failure"
        runner.save(self.request_file, self.request)
        checked = runner.load_request(self.request_file)
        target, thermal = mock.Mock(), mock.Mock()
        result = {}
        with (
            mock.patch("settings_write_interrupt_check.check_settings_save_failure", return_value={"success": True}) as check,
            mock.patch.object(runner, "launch") as launch,
        ):
            runner.run_workload(target, thermal, checked, self.output, result)
            check.call_args.args[3](target)
        launch.assert_called_once_with(target, thermal, process_checks=[])
        self.assertIs(check.call_args.args[4], thermal.cancelled)
        self.assertEqual(result["settings_save_failure"], {"success": True})
        self.request["selection"] = {}
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "owns its attempt-bound selector"):
            runner.load_request(self.request_file)

    def test_software_notices_uses_shared_lifecycle_and_owns_selector(self):
        self.request["mode"] = "software-notices"
        runner.save(self.request_file, self.request)
        checked = runner.load_request(self.request_file)
        target, thermal = mock.Mock(), mock.Mock()
        result = {}
        with mock.patch.object(runner, "check_software_notices", return_value={"success": True}) as check:
            runner.run_workload(target, thermal, checked, self.output, result)
        check.assert_called_once_with(target, thermal, checked, self.output, [])
        self.assertEqual(result["software_notices"], {"success": True})
        self.request["selection"] = {}
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "owns its attempt-bound selector"):
            runner.load_request(self.request_file)

    def test_software_notices_flow_uses_report_coordinates_and_preserves_files(self):
        target, thermal = mock.Mock(), mock.Mock()
        target.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        target.sh.return_value = "unchanged settings hashes"
        reports = [
            dict(phase="offline-start-menu", settings=dict(ready=True, visible=False)),
            dict(settings=dict(visible=True)),
            dict(settings=dict(softwareNoticesVisible=True, softwareNoticesAvailable=True, softwareNoticesBackX=645, softwareNoticesBackY=35)),
            dict(settings=dict(visible=True, softwareNoticesVisible=False)),
            dict(phase="offline-start-menu", settings=dict(visible=False)),
        ]
        for report in reports:
            report["settings"].update(screenWidth=1920, screenHeight=1080, buttonX=100, buttonY=100)

        def observed(device, monitor, pid, predicate):
            report = reports.pop(0)
            self.assertTrue(predicate(report))
            return report

        with (
            mock.patch("installed_attempt.attempt_from_installed", return_value="fixture"),
            mock.patch("session_cleanup_check.selection", return_value={}),
            mock.patch("settings_write_interrupt_check.protected_hashes", return_value={"profile": "same"}),
            mock.patch.object(runner, "launch", return_value={"pid": "1"}),
            mock.patch.object(runner, "wait_for_settings_report", side_effect=observed),
            mock.patch.object(runner, "capture") as capture,
            mock.patch("touch_gesture.run") as gesture,
        ):
            result = runner.check_software_notices(target, thermal, self.request, self.output, [])
        self.assertTrue(result["protected_files_unchanged"])
        self.assertEqual(len(reports), 0)
        self.assertEqual(gesture.call_count, 4)
        self.assertEqual(capture.call_count, 2)
        back = json.loads((self.output / "back.input.json").read_text())
        self.assertEqual((back["steps"][0]["x"], back["steps"][0]["y"]), (645, 35))

    def test_player_screens_injected_routes_keep_native_loss_and_modal_order(self):
        self.request["mode"] = "player-screens"
        runner.save(self.request_file, self.request)
        checked = runner.load_request(self.request_file)
        target, thermal = mock.Mock(package=self.request["package"]), mock.Mock(error=None)
        target.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        # Exactly the last post-confirm PID read exits; every input checks its owner.
        target.sh.side_effect = lambda *args, **kwargs: "" if args[0] == "pidof" and len(keys) == 10 else "1"
        reports = [
            dict(phase="offline-start-menu"),
            dict(phase="integrated-world-playing"),
            dict(phase="commando-defeated", session=1, results=dict(persisted=True, serverEnding=True, clientEnding=True, reportReloaded=True)),
            dict(phase="offline-start-menu", session=2),
            dict(hud=dict(menuLoadoutVisible=True, menuLoadoutRow=0)),
            dict(hud=dict(menuLoadoutRow=1, menuLoadoutCycles=0)),
            dict(phase="offline-start-menu", hud=dict(menuLoadoutVisible=True, menuLoadoutCycles=1)),
            dict(hud=dict(menuLoadoutVisible=False)),
            dict(hud=dict(menuQuitConfirmation=True)),
            dict(phase="offline-start-menu", hud=dict(menuQuitConfirmation=False)),
            dict(hud=dict(menuQuitConfirmation=True)),
        ]
        keys = []

        def command(*args, **kwargs):
            if args[0] == "input":
                keys.append(args[-1])
                return ""
            if args[0] == "pidof":
                return "" if len(keys) == 10 else "1"
            if args[:2] == ("sh", "-c"):
                return process_snapshot(("1", "03:19:58", target.package))
            return "unchanged"

        target.sh.side_effect = command

        def observed(device, monitor, pid, predicate, timeout=100):
            report = reports.pop(0)
            self.assertTrue(predicate(report), report)
            return report

        with (
            mock.patch.object(runner, "check_software_notices", return_value={"success": True}),
            mock.patch.object(runner, "wait_for_settings_report", side_effect=observed),
            mock.patch.object(runner, "capture"),
            mock.patch("settings_write_interrupt_check.protected_hashes", return_value={"profile": "same"}),
            mock.patch("touch_gesture.owned_display_zero_focus", return_value=True),
        ):
            result = runner.check_player_screens(target, thermal, checked, self.output, [])
        self.assertTrue(result["quit_exited"])
        self.assertFalse(result["physical_certification"])
        self.assertEqual(
            keys,
            [
                "KEYCODE_ENTER",
                "KEYCODE_ESCAPE",
                "KEYCODE_L",
                "KEYCODE_DPAD_DOWN",
                "KEYCODE_ENTER",
                "KEYCODE_ESCAPE",
                "KEYCODE_Q",
                "KEYCODE_ESCAPE",
                "KEYCODE_Q",
                "KEYCODE_ENTER",
            ],
        )
        self.assertEqual(reports, [])

    def test_settings_report_wait_rejects_process_change_and_native_failure(self):
        target, thermal = mock.Mock(), mock.Mock(error=None)
        target.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        target.sh.return_value = "other-pid"
        with mock.patch("installed_attempt.attempt_from_installed", return_value="fixture"):
            with self.assertRaisesRegex(RuntimeError, "Owned process changed"):
                runner.wait_for_settings_report(target, thermal, "1", lambda r: True)
            target.sh.return_value = "1"
            with (
                mock.patch("session_cleanup_check._read_json", return_value={"firstFailure": "fixture defect"}),
                mock.patch("session_cleanup_check.matches_run", return_value=True),
            ):
                with self.assertRaisesRegex(RuntimeError, "Native first failure: fixture defect"):
                    runner.wait_for_settings_report(target, thermal, "1", lambda r: True)

    def test_native_report_deadline_names_last_owned_phase(self):
        from session_cleanup_check import SPINE_ID

        target, thermal = mock.Mock(), mock.Mock(error=None)
        target.read_receipt.return_value = {"persistentDataPath": "/synthetic"}
        target.sh.return_value = "12"
        menu = dict(pid=12, attempt="fixture", id=SPINE_ID, phase="offline-start-menu")
        stale = dict(menu, pid=11, phase="integrated-world-playing")
        with (
            mock.patch("installed_attempt.attempt_from_installed", return_value="fixture"),
            mock.patch("session_cleanup_check._read_json", side_effect=[menu, stale]),
            mock.patch.object(runner.time, "monotonic", side_effect=[0, 0, 1, 2]),
            mock.patch.object(runner.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "last owned phase: offline-start-menu"):
                runner.wait_for_settings_report(target, thermal, "12", lambda r: r["phase"] == "integrated-world-playing", timeout=2)

    def test_dispatched_input_failure_writes_terminal_without_device_access(self):
        self.apk.unlink()
        with mock.patch.object(runner.subprocess, "run") as process:
            self.assertEqual(runner.main(["--request", str(self.request_file)]), 1)
        process.assert_not_called()
        result = json.loads((self.output / "terminal.done.json").read_text())
        self.assertFalse(result["success"])
        self.assertIn("FileNotFoundError", result["error"])

    def test_payload_request_rejects_empty_directory_and_invalid_cadence(self):
        payload = self.root / "payload"
        payload.mkdir()
        (payload / ".prune-keep").touch()
        (payload / "content.manifest").write_text("fixture manifest")
        self.request["payload_directory"] = str(payload)
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "runtime files"):
            runner.load_request(self.request_file)
        (payload / "content").write_bytes(b"fixture content")
        self.request["capture_interval_seconds"] = 5
        runner.save(self.request_file, self.request)
        checked = runner.load_request(self.request_file)
        self.assertEqual(runner.payload_files(checked), [(payload / "content").resolve()])
        self.request["capture_interval_seconds"] = 0
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "capture_interval_seconds"):
            runner.load_request(self.request_file)

    def test_launch_captures_requested_combat_cadence(self):
        target = mock.Mock(package=self.request["package"])
        target.sh.return_value = "7"
        thermal = mock.Mock()
        thermal.cancelled.is_set.return_value = False
        result = {}
        with (
            mock.patch.object(runner, "launch", return_value=dict(pid=7)),
            mock.patch.object(runner, "capture") as capture,
            mock.patch.object(runner.time, "sleep"),
            mock.patch.object(runner.time, "monotonic", side_effect=[0, 0, 5, 10, 10]),
        ):
            runner.run_workload(target, thermal, dict(self.request, duration_seconds=10, capture_interval_seconds=5), self.output, result)
        self.assertEqual([call.args[1].name for call in capture.call_args_list], ["sample-0", "sample-5", "sample-10", "final"])
        self.assertEqual(result["observed_seconds"], 10)

    def test_scheduled_touch_validates_and_runs_during_launch_observation(self):
        gesture = dict(width=1280, height=960, steps=[dict(action="wait", ms=100)])
        runner.save(self.root / "touch.json", gesture)
        self.request["input_schedule"] = [dict(at_seconds=5, script="touch.json"), dict(at_seconds=10, script="touch.json")]
        runner.save(self.request_file, self.request)
        checked = runner.load_request(self.request_file)
        self.assertEqual(checked["input_schedule"][0]["script"], str((self.root / "touch.json").resolve()))
        target, thermal = mock.Mock(), mock.Mock()
        target.sh.return_value = "7"
        thermal.cancelled.is_set.return_value = False
        clock = [0]
        result = {}
        with (
            mock.patch.object(runner, "launch", return_value=dict(pid=7)),
            mock.patch.object(runner, "capture"),
            mock.patch.object(runner.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
            mock.patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]),
            mock.patch("touch_gesture.run", return_value=dict(success=True)) as touch,
        ):
            runner.run_workload(target, thermal, dict(checked, duration_seconds=10), self.output, result)
        self.assertEqual([item["dispatched_seconds"] for item in result["scheduled_inputs"]], [5, 10])
        self.assertEqual(touch.call_count, 2)
        for call in touch.call_args_list:
            self.assertEqual(json.loads(call.args[0].read_text()), dict(gesture, pid="7"))
            self.assertEqual(call.args[1], self.digest)
            self.assertIs(call.kwargs["device"], target)
        self.request["input_schedule"].reverse()
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "ordered within"):
            runner.load_request(self.request_file)
        self.request["input_schedule"] = [dict(at_seconds=5, script="touch.json")]
        runner.save(self.root / "touch.json", dict(gesture, steps=[dict(action="wait", ms=30001)]))
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "30 seconds"):
            runner.load_request(self.request_file)

    def test_capture_retains_ordinary_and_bringup_reports(self):
        target = mock.Mock()
        target.cmd.return_value = "authored log"
        target.sh.return_value = "{}"
        target.read_receipt.return_value = dict(persistentDataPath="/fixture/runtime")
        runner.capture(target, self.output, "7")
        target.collect.assert_any_call("perf", self.output, include_exceptions=False)
        self.assertFalse(any(call.args == ("cat", "/fixture/runtime/exceptions.jsonl") for call in target.sh.call_args_list))
        self.assertFalse((self.output / "exceptions.jsonl").exists())
        for suffix in ("", "-bringup"):
            name = "movement-batch-body-state-spawn-state-auto-nova-spine" + suffix + ".json"
            target.sh.assert_any_call("cat", "/fixture/runtime/" + name, check=False)
            self.assertEqual((self.output / name).read_text(), "{}")

    def test_sustained_request_forwards_observation_cadence(self):
        import session_sustained_check as sustained

        evidence = self.root / "sustained"
        evidence.mkdir()
        target = mock.Mock(package=self.request["package"])
        target.evidence_directory.return_value = evidence

        def complete(**kwargs):
            runner.save(evidence / "one/result.json", dict(success=True))
            return dict(success=True)

        request = dict(self.request, mode="sustained", capture_interval_seconds=30)
        runner.save(self.request_file, request)
        self.assertEqual(runner.load_request(self.request_file)["capture_interval_seconds"], 30)
        with mock.patch.object(sustained, "check_session_sustained", side_effect=complete) as check:
            runner.run_workload(target, mock.Mock(), request, self.output, {})
        self.assertEqual(check.call_args.kwargs["observation_interval_seconds"], 30)
        self.assertIs(check.call_args.kwargs["_include_exceptions"], False)
        del request["capture_interval_seconds"]
        runner.save(self.request_file, request)
        self.assertEqual(runner.load_request(self.request_file)["capture_interval_seconds"], 5)

    def test_sustained_delegates_selector_and_capture_cadence_after_idle_admission(self):
        self.request.update(mode="sustained", selection=dict(detailedVisualDiagnostics=True), capture_interval_seconds=10)
        runner.save(self.request_file, self.request)
        request = runner.load_request(self.request_file)
        self.assertTrue(self.run_case()["success"])
        target = mock.Mock()
        evidence = self.root / "sustained"
        evidence.mkdir()
        target.evidence_directory.return_value = evidence

        def observe(**kwargs):
            runner.save(evidence / "current/result.json", dict(success=True))
            return dict(success=True)

        result = {}
        with mock.patch("session_sustained_check.check_session_sustained", side_effect=observe) as check:
            runner.run_workload(target, mock.Mock(), request, self.output, result)
        self.assertEqual(check.call_args.kwargs["observation_interval_seconds"], 10)
        self.assertIs(check.call_args.kwargs["detailed_visual_diagnostics"], True)
        self.assertEqual(len(result["session_result_files"]), 1)
        self.request["selection"]["attempt"] = "stale-attempt"
        runner.save(self.request_file, self.request)
        with self.assertRaisesRegex(ValueError, "owns its seed-2 attempt-bound selector"):
            runner.load_request(self.request_file)

    def test_pacing_observation_queries_only_selected_package_surfaces(self):
        target = mock.Mock(package="dev.ror2lab.arm64")
        responses = {
            ("dumpsys", "display"): "display modes",
            ("dumpsys", "SurfaceFlinger", "--frame-rate-override"): "unsupported command",
            ("dumpsys", "game", target.package): "game mode standard",
            ("dumpsys", "gfxinfo", target.package, "framestats"): "IntendedVsync,FrameCompleted\n1,2",
            ("cmd", "package", "list", "packages", "-U", target.package): "package:dev.ror2lab.arm64 uid:12345",
            ("getprop",): "[debug.game_default_frame_rate]: [60]\n[debug.frame_rate]: [120]\n[unrelated]: [private]",
            ("dumpsys", "SurfaceFlinger"): "unrelated layer\n Frame Rate Overrides: uid=12345 fps=60",
            ("logcat", "-d", "--pid=7", "-v", "epoch"): "Swappy logs",
            ("dumpsys", "SurfaceFlinger", "--list"): "SurfaceView dev.ror2lab.arm64 main\nSurfaceView other.app main\n",
            ("dumpsys", "SurfaceFlinger", "--latency", "SurfaceView dev.ror2lab.arm64 main"): "8333333\n1 2 3\n",
        }
        target.sh.side_effect = lambda *args, **kwargs: responses[args]
        snapshot = dict(targetFrameRate=300, renderFrameInterval=2)
        runner.observe_pacing(target, self.output, "7", snapshot)
        self.assertEqual(json.loads((self.output / "snapshot.json").read_text()), snapshot)
        self.assertEqual((self.output / "latency-00.txt").read_text(), "8333333\n1 2 3\n")
        target.sh.assert_any_call("dumpsys", "SurfaceFlinger", "--latency", "SurfaceView dev.ror2lab.arm64 main", check=False)
        self.assertEqual(len(list(self.output.glob("latency-*.txt"))), 1)
        self.assertEqual((self.output / "frame-rate-overrides.log").read_text(), "unsupported command")
        self.assertEqual((self.output / "game.log").read_text(), "game mode standard")
        self.assertEqual((self.output / "gfxinfo-framestats.log").read_text(), responses[("dumpsys", "gfxinfo", target.package, "framestats")])
        self.assertIn("uid:12345", (self.output / "package.log").read_text())
        self.assertEqual((self.output / "frame-rate-properties.log").read_text(), "[debug.game_default_frame_rate]: [60]\n[debug.frame_rate]: [120]\n")
        self.assertEqual((self.output / "compositor-overrides.log").read_text(), " Frame Rate Overrides: uid=12345 fps=60\n")

    def test_payload_retention_marker_is_never_synced(self):
        payload = self.root / "payload"
        payload.mkdir()
        (payload / ".prune-keep").touch()
        (payload / "content.manifest").write_text("fixture manifest")
        target = mock.Mock(package=self.request["package"])
        target.read_receipt.return_value = dict(persistentDataPath="/owned/Android/data/" + target.package + "/files")
        target.storage.return_value = dict(mode="internal", internal=dict(free_bytes=30 * 1024**3))
        device_module.Device.sync(target, payload)
        target.cmd.assert_not_called()
        self.assertFalse(any(call.args[0] == "sha256sum" for call in target.sh.call_args_list))

    def test_payload_sync_removes_only_verified_superseded_entries(self):
        payload = self.root / "payload"
        payload.mkdir()
        (payload / "current").write_bytes(self.apk.read_bytes())
        target = mock.Mock(package=self.request["package"])
        runtime = "/owned/Android/data/" + target.package + "/files"
        dest = runtime + "/payload/"
        target.storage.return_value = dict(mode="internal", internal=dict(free_bytes=30 * 1024**3))
        previous = dict(runtime_path=runtime, files=[dict(name=name, sha256=self.digest) for name in ("current", "old", "changed")])
        target.read_receipt.side_effect = {"runtime.json": dict(persistentDataPath=runtime), "sync.json": previous}.__getitem__
        remote = {dest + "current": self.digest, dest + "old": self.digest, dest + "changed": "0" * 64}

        def shell(*args, **kwargs):
            if args[0] == "sha256sum":
                return remote[args[-1]]
            if args[0] == "rm":
                del remote[args[-1]]
            if args[0] == "sh":
                if "stat -c" in args[2]:
                    self.assertIn(args[-2], remote)
                    return "20"
                self.assertNotIn(args[-1], remote)
            return ""

        target.sh.side_effect = shell
        cleanup = dict(bytes_removed=0, files=[])
        result = device_module.Device.sync(target, payload, replace_previous=True, cleanup=cleanup)
        self.assertEqual(result["superseded_removed"], ["old"])
        self.assertEqual(cleanup, dict(bytes_removed=20, files=[dict(path=dest + "old", bytes=20)]))
        self.assertEqual(set(remote), {dest + "current", dest + "changed"})
        self.assertEqual([call for call in target.sh.call_args_list if call.args[0] == "rm"], [mock.call("rm", "--", dest + "old")])

    def test_large_payload_sync_references_original_verified_file(self):
        payload = self.root / "payload"
        payload.mkdir()
        content = payload / "large.bundle"
        size = 21 * 1024**2
        with content.open("wb") as stream:
            stream.truncate(size)
        digest = device_module.sha(content)
        target = mock.Mock(package=self.request["package"])
        runtime = "/owned/Android/data/" + target.package + "/files"
        remote = runtime + "/payload/" + content.name
        target.read_receipt.return_value = dict(persistentDataPath=runtime)
        target.storage.return_value = dict(mode="internal", internal=dict(free_bytes=30 * 1024**3))
        target.sh.side_effect = lambda *args, **kwargs: digest if args[-1] == remote + ".partial" and args[0] == "sha256sum" else ""

        result = device_module.Device.sync(target, payload)

        target.cmd.assert_called_once_with("push", str(content.resolve()), remote + ".partial", timeout=300)
        target.sh.assert_any_call("mv", remote + ".partial", remote)
        self.assertEqual(result["files"], [dict(name=content.name, path=str(content.resolve()), sha256=digest, bytes=size, transferred=True)])
        self.assertEqual(list(payload.iterdir()), [content])

    def test_diagnostic_cleanup_retains_changed_and_new_files_before_removing_them(self):
        self.output.mkdir(parents=True)
        runtime = "/owned"
        snapshot = runtime + "/snapshot.json"
        old_trace = runtime + "/frame-times-old.bin"
        new_trace = runtime + "/frame-times-new.bin"
        target = mock.Mock()

        def shell(*args):
            if args[0] == "find":
                return f"{snapshot}|updated\n{old_trace}|same\n{new_trace}|new\n"
            if args[0] == "sha256sum":
                return self.digest
            if args[0] == "sh" and "stat -c" in args[2]:
                return str(self.apk.stat().st_size)
            return ""

        target.sh.side_effect = shell
        target.cmd.side_effect = lambda op, remote, local: Path(local).write_bytes(self.apk.read_bytes())
        cleanup = dict(bytes_removed=0, files=[])
        runner.retain_diagnostic_scratch(target, runtime, {snapshot: "earlier", old_trace: "same"}, self.output, cleanup)
        self.assertEqual({entry.name for entry in self.output.iterdir()}, {"snapshot.json", "frame-times-new.bin"})
        self.assertEqual([call.args[-1] for call in target.sh.call_args_list if call.args[0] == "rm"], [new_trace, snapshot])
        self.assertEqual(cleanup["bytes_removed"], 2 * self.apk.stat().st_size)

    def test_diagnostic_cleanup_continues_and_counts_only_verified_absence(self):
        self.output.mkdir(parents=True)
        runtime = "/owned"
        bad, good = runtime + "/frame-times-a.bin", runtime + "/frame-times-b.bin"
        target = mock.Mock()
        target.cmd.side_effect = lambda op, remote, local: Path(local).write_bytes(self.apk.read_bytes())

        def shell(*args):
            if args[0] == "find":
                return f"{bad}|new\n{good}|new\n"
            if args[0] == "sha256sum":
                return self.digest
            if args[0] == "sh" and "stat -c" in args[2]:
                return str(self.apk.stat().st_size)
            if args[0] == "sh" and args[-1] == bad:
                raise RuntimeError("Still present after removal")
            return ""

        target.sh.side_effect = shell
        cleanup = dict(bytes_removed=0, files=[])
        with self.assertRaises(ExceptionGroup) as error:
            runner.retain_diagnostic_scratch(target, runtime, {}, self.output, cleanup)
        self.assertIn("Still present", str(error.exception.exceptions[0]))
        size = self.apk.stat().st_size
        self.assertEqual(cleanup, dict(bytes_removed=size, files=[dict(path=good, bytes=size)]))
        self.assertEqual({entry.name for entry in self.output.iterdir()}, {Path(bad).name, Path(good).name})

    def test_capture_records_extracted_metadata_and_unity_extraction_decision(self):
        target = mock.Mock()
        target.cmd.return_value = "Unity extraction diagnostic"
        target.sh.return_value = "metadata hash fixture"
        target.read_receipt.return_value = dict(persistentDataPath="/owned/files")
        runner.capture(target, self.output, "7")
        self.assertEqual((self.output / "il2cpp-metadata-sha256.txt").read_text(), "metadata hash fixture")
        target.sh.assert_any_call("sha256sum", "/owned/files/il2cpp/Metadata/global-metadata.dat", check=False)
        self.assertIn("Unity:D", target.cmd.call_args_list[0].args)

    def run_case(
        self,
        *,
        workload_error=False,
        terminal_error=False,
        thermal_error=False,
        thermal_finish_error=None,
        payload=False,
        exception_rows="",
        signature_failure=False,
        start_from_menu=False,
        launch_snapshot_pid=None,
    ):
        events = []
        transient_paths = {"/owned/" + suffix for suffix in runner.TRANSIENTS}
        live_transients = set(transient_paths)
        lease_path = runner.Lease(self.request).path
        installed = dict(apk_sha256=self.digest, package_path="package:/fixture/base.apk", package=self.request["package"], serial=self.request["serial"])
        target = mock.Mock(package=self.request["package"], serial=self.request["serial"])
        target.exists.return_value = True
        target.owned.return_value = installed
        target.read_receipt.return_value = dict(persistentDataPath="/owned")
        receipt = self.root / "installed.json"
        receipt.touch()
        runtime_receipt = self.root / "runtime.json"
        runtime_receipt.touch()
        target.receipt.side_effect = lambda name: self.root / name
        target.install.return_value = installed
        target.sync.side_effect = lambda path, *, replace_previous, cleanup: events.append("sync:" + str(path)) or dict(files=["content"])
        device_class = device_module.Device
        target.storage.return_value = {"mode": "adopted"}
        if signature_failure:
            installed["apk_sha256"] = "0" * 64
            target.settings = {}
            target.base = ["fake-adb", "-s", target.serial]
            target.storage.return_value = {"mode": "adopted", "uuid": "fixture-adopted"}
            target.install_counter.return_value = self.root / "install-count.json"
            target.install.side_effect = lambda apk: device_class.install(target, apk)
            target.reset.side_effect = lambda: device_class.reset(target)
            target.cmd.side_effect = lambda *args, **kwargs: device_class.cmd(target, *args, **kwargs)

            def write_receipt(name, value):
                runner.save(target.receipt(name), value)
                if name == "installed.json":
                    target.owned.return_value = value

            target.write_receipt.side_effect = write_receipt

        def adb_process(args, **kwargs):
            self.assertEqual(args[:3], target.base)
            self.assertTrue(lease_path.is_dir())
            if args[3] == "install":
                self.assertEqual(args[4:], ["--streaming", "--no-incremental", "-r", "--force-uuid", "fixture-adopted", str(self.apk)])
                if target.exists():
                    events.append("signature-mismatch")
                    return subprocess.CompletedProcess(
                        args, 1, b"", b"adb: failed to install fixture: Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]\n"
                    )
                self.assertFalse(receipt.exists())
                self.assertFalse(runtime_receipt.exists())
                events.append("reinstall")
                target.exists.return_value = True
            else:
                self.assertEqual(args[3:], ["shell", "pm uninstall dev.ror2lab.arm64"])
                self.assertTrue(receipt.exists())
                events.append("uninstall")
                target.exists.return_value = False
            return subprocess.CompletedProcess(args, 0, b"Success\n", b"")

        payload_size = 0
        if payload:
            directory = self.root / "payload"
            directory.mkdir()
            content = directory / "content"
            content.write_bytes(b"authored payload fixture")
            payload_size = content.stat().st_size
            self.request["payload_directory"] = str(directory)
        target.display.side_effect = lambda awake: events.append("awake" if awake else "asleep") or True

        def shell(*args, **kwargs):
            if args[:2] == ("sh", "-c") and "ps -A" in args[2]:
                launching = events[-1:] == ["launching"]
                events.append("process-checkpoint")
                if launching:
                    return process_snapshot((launch_snapshot_pid, "03:19:58", target.package))
                return process_snapshot()
            if args[0] == "pidof":
                return ""  # The launched process has exited by terminal capture.
            if args[0] == "sha256sum":
                return target.owned()["apk_sha256"] + "  /fixture/base.apk"
            if args[:2] == ("pm", "uninstall"):
                return device_class.sh(target, *args, **kwargs)
            if args[:2] == ("pm", "path"):
                return "package:/mnt/expand/fixture-adopted/app/base.apk"
            if args[:2] == ("mkdir", "-p"):
                events.append("recreate-runtime")
            if args[:2] == ("sh", "-c") and args[-1] == "/owned/exceptions.jsonl":
                if "workload" in events:
                    self.assertEqual(events[-1], "stop")
                    return str(120_000_000 + len(exception_rows.encode()))
                return "120000000"
            if args[0] == "tail":
                self.assertEqual(events[-1], "stop")
                self.assertEqual(args, ("tail", "-c", "+120000001", "--", "/owned/exceptions.jsonl"))
                events.append("exception-tail")
                return exception_rows.rstrip("\n")
            if args[0] == "sh" and "stat -c" in args[2]:
                self.assertIn(args[-2], live_transients)
                return "17"
            if args[:2] == ("am", "force-stop"):
                events.append("stop")
            if args[0] == "rm":
                live_transients.remove(args[-1])
                events.append("remove:" + args[-1])
            return ""

        target.sh.side_effect = shell
        thermal = mock.Mock(error="safety stop" if thermal_error else None, peak_cpu_gpu_celsius=81, time_above_80_seconds=3, admission_battery={})
        thermal.thread = thermal.stopper = None
        finish_error = thermal.error or thermal_finish_error
        thermal.finish.side_effect = RuntimeError(finish_error) if finish_error else lambda: events.append("thermal-finish")
        thermal.start.side_effect = lambda: events.append("thermal-start")
        thermal.launch.side_effect = lambda _: events.append("launching") or {"pid": "73"}
        target.cmd.return_value = "Unity fatal tail"

        if start_from_menu:
            self.request["start_from_menu"] = True

        def read_attempt(receipt):
            self.assertEqual(receipt, installed)
            events.append("read-attempt")
            return "owned-attempt"

        def workload(current, owner, request, output, result, **kwargs):
            self.assertTrue(lease_path.is_dir())
            self.assertIsNotNone(kwargs["_reset_idle"])
            self.assertEqual(kwargs["start_attempt"], "owned-attempt" if start_from_menu else None)
            if request["mode"] == "sustained":
                self.assertFalse(any(call.args[0] == "push" and call.args[-1].endswith("movement-batch-selection.json") for call in target.cmd.call_args_list))
            events.append("workload")
            live_transients.update(transient_paths)
            if launch_snapshot_pid is not None:
                runner.launch(current, owner, process_checks=result["process_checkpoints"])
            if workload_error:
                raise RuntimeError("observed workload failure")

        original_idle = batch._idle_readback
        calls = 0

        def idle(*args):
            nonlocal calls
            calls += 1
            if terminal_error and calls == 3:
                raise RuntimeError("terminal hash changed")
            self.assertTrue(lease_path.is_dir())
            events.append("idle")
            return original_idle(*args)

        def prune(root):
            events.append("prune")
            self.assertEqual(lease_path.exists(), terminal_error)

        with (
            mock.patch.object(runner, "source_environment"),
            mock.patch.object(runner.subprocess, "run", side_effect=adb_process),
            mock.patch.object(device_module, "Device", return_value=target),
            mock.patch.object(device_module, "validate_apk_identity"),
            mock.patch.object(runner, "placement", return_value={}) as placement,
            mock.patch.object(runner, "run_workload", side_effect=workload),
            mock.patch.object(runner, "prepare_launch") as prepare,
            mock.patch("installed_attempt.attempt_from_installed", side_effect=read_attempt) as attempt,
            mock.patch.object(batch, "_GameThermalOwner", return_value=thermal) as owner,
            mock.patch.object(batch, "_idle_readback", side_effect=idle),
            mock.patch.object(batch, "_prune", side_effect=prune),
            mock.patch(
                "session_cleanup_check._remote_path_state",
                side_effect=lambda current, path: "file" if path in live_transients else "absent",
            ),
            mock.patch.object(runner.time, "monotonic", return_value=1000),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
        ):
            result = runner.execute(self.request)
        self.assertEqual(placement.call_args_list[0].args[1], self.apk.stat().st_size + payload_size + 20 * 1024**3)
        self.assertIn("prelaunch", result, result.get("error"))
        phases = ["before-install", "install"]
        if launch_snapshot_pid is not None:
            phases += ["before-launch", "launch"]
        self.assertEqual([checkpoint["phase"] for checkpoint in result["process_checkpoints"]], phases)
        prepare.assert_called_once_with(target, result["prelaunch"])
        if payload:
            target.sync.assert_called_once_with(self.root / "payload", replace_previous=True, cleanup=result["device_cleanup"])
            self.assertLess(events.index("sync:" + str(self.root / "payload")), events.index("workload"))
            self.assertEqual(result["sync"], dict(files=["content"]))
            self.assertEqual(
                [call.args[1] for call in placement.call_args_list[1:3]], [payload_size + runner.DEVICE_RESERVE_BYTES, runner.DEVICE_RESERVE_BYTES]
            )
        else:
            target.sync.assert_not_called()
        if signature_failure:
            self.assertEqual(
                [
                    event
                    for event in events
                    if event in {"signature-mismatch", "uninstall", "reinstall", "recreate-runtime", "sync:" + str(self.root / "payload")}
                ],
                ["signature-mismatch", "uninstall", "reinstall", "recreate-runtime", "sync:" + str(self.root / "payload")],
            )
        self.assertEqual(owner.call_args.args[-1], 1060)  # run-local cooldown deadline
        self.assertEqual(thermal.deadline, 1630)  # independent workload deadline
        if start_from_menu:
            attempt.assert_called_once_with(installed)
            self.assertLess(events.index("read-attempt"), events.index("thermal-start"))
        else:
            attempt.assert_not_called()
        self.assertEqual(events[-1], "prune")
        self.assertIn("asleep", events)
        self.assertEqual(json.loads((self.output / "terminal.done.json").read_text()), result)
        self.assertEqual((result["apk"], result["apk_sha256"]), (self.request["apk"], self.digest))
        self.assertEqual(result["device_cleanup"]["bytes_removed"], 17 * 2 * len(runner.TRANSIENTS))
        if not signature_failure:
            target.install.assert_called_once_with(Path(self.request["apk"]))
        removed = [event for event in events if event.startswith("remove:")]
        self.assertTrue(removed)
        self.assertEqual(events.count("stop"), 3)
        self.assertEqual(events.count("exception-tail"), int(bool(exception_rows)))
        self.assertLess(events.index("workload"), len(events) - 1 - events[::-1].index("stop"))
        for suffix in runner.TRANSIENTS:
            self.assertEqual(removed.count("remove:/owned/" + suffix), 2)
        self.assertTrue(all(event.removeprefix("remove:/owned/") in runner.TRANSIENTS for event in removed))
        return result

    def test_success_releases_only_after_independent_idle_and_sleep(self):
        result = self.run_case()
        self.assertTrue(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertTrue(result["terminal_readback"]["oled_asleep"])
        self.assertEqual((self.output / "exceptions.jsonl").read_text(), "")

    def test_menu_observation_binds_installed_attempt_before_thermal_sampling(self):
        self.assertTrue(self.run_case(start_from_menu=True)["success"])

    def test_owned_lab_signer_mismatch_reinstalls_once_and_resyncs_under_lease(self):
        result = self.run_case(payload=True, signature_failure=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertEqual(result["install"]["apk_sha256"], self.digest)
        self.assertEqual(
            result["install_recovery"],
            dict(
                reason="INSTALL_FAILED_UPDATE_INCOMPATIBLE",
                previous_apk_sha256="0" * 64,
                uninstall=dict(uninstall="Success", removed=True),
                payload_resynced=True,
            ),
        )

    def test_workload_failure_retains_only_appended_exception_rows_once(self):
        rows = '{"message":"exception α"}\n{"message":"exception β"}\n'
        result = self.run_case(workload_error=True, exception_rows=rows)
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertNotIn("exception_capture_error", result)
        self.assertEqual((self.output / "exceptions.jsonl").read_text(), rows)

    def test_payload_synced_before_workload_and_included_in_storage_reserve(self):
        with self.apk.open("wb") as stream:
            stream.truncate(21 * 1024**2)
        self.digest = device_module.sha(self.apk)
        self.request.update(apk_sha256=self.digest)
        runner.save(self.request_file, self.request)
        self.request = runner.load_request(self.request_file)
        self.assertTrue(self.run_case(payload=True)["success"])
        self.assertEqual(list(self.output.rglob("*.apk")), [])

    def test_workload_failure_still_stops_resets_sleeps_and_releases(self):
        result = self.run_case(workload_error=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertIn("observed workload failure", result["error"])

    def test_terminal_capture_retains_logcat_after_verified_process_exits(self):
        result = self.run_case(workload_error=True, launch_snapshot_pid="73")
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertEqual(result["process_checkpoints"][-1]["verified_launch_pid"], "73")
        self.assertEqual((self.output / "terminal-capture/unity.log").read_text(), "Unity fatal tail")

    def test_terminal_capture_ignores_unverified_launch_snapshot(self):
        result = self.run_case(launch_snapshot_pid="72")
        self.assertIn("Unexpected owned lab process at launch", result["error"])
        self.assertTrue(result["lease_released"])
        self.assertNotIn("verified_launch_pid", result["process_checkpoints"][-1])
        self.assertFalse((self.output / "terminal-capture").exists())

    def test_safety_stop_does_not_strand_clean_device_lease(self):
        result = self.run_case(thermal_error=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])

    def test_thermal_stop_pid_ambiguity_releases_after_verified_idle(self):
        result = self.run_case(workload_error=True, thermal_finish_error="Ambiguous game PID; refuse thermal stop")
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertTrue(result["terminal_readback"]["oled_asleep"])
        self.assertIn("Ambiguous game PID", result["thermal_finish_error"])
        self.assertEqual(result["cleanup_errors"], [])

    def test_failed_terminal_still_sleeps_and_publishes_but_retains_lease(self):
        result = self.run_case(terminal_error=True)
        self.assertFalse(result["success"])
        self.assertFalse(result["lease_released"])
        self.assertIn("terminal hash changed", result["cleanup_errors"][0])

    def test_prior_receipt_requires_live_package_hash(self):
        prior = self.root / "prior.json"
        receipt = dict(serial="synthetic-device", package="dev.ror2lab.converted", package_path="package:/fixture/base.apk", apk_sha256=self.digest)
        runner.save(prior, receipt)
        target = mock.Mock(serial=receipt["serial"], package=receipt["package"])
        target.sh.side_effect = [receipt["package_path"], "0" * 64]
        with self.assertRaisesRegex(RuntimeError, "hash changed"):
            runner.adopt_receipt(target, prior)
        target.write_receipt.assert_not_called()
        target.sh.side_effect = [receipt["package_path"], self.digest]
        runner.adopt_receipt(target, prior)
        target.write_receipt.assert_called_once_with("installed.json", receipt)

    def test_unsecured_keyguard_is_dismissed_before_launch(self):
        target = mock.Mock()
        target.sh.side_effect = ["", "mShowingLockscreen=true\nKeyguardServiceDelegate\nsecure=false", "", "mShowingLockscreen=false"]
        record = {}
        with mock.patch.object(runner.time, "sleep"):
            runner.prepare_launch(target, record)
        self.assertEqual(target.sh.call_args_list[0].args, ("input", "keyevent", "KEYCODE_WAKEUP"))
        self.assertIn(mock.call("wm", "dismiss-keyguard"), target.sh.call_args_list)
        self.assertFalse(record["after_dismiss"]["showing"])

    def test_swipe_fallback_verifies_unsecured_keyguard(self):
        target = mock.Mock()
        locked = "mDreamingLockscreen=false mShowingLockscreen=true\nKeyguardServiceDelegate\nshowing=true\nsecure=false"
        target.sh.side_effect = ["", locked, "", locked, "Physical size: 1080x1920\nOverride size: 720x1280", "", "isKeyguardShowing=false"]
        record = {}
        with mock.patch.object(runner.time, "sleep"):
            runner.prepare_launch(target, record)
        self.assertTrue(record["swipe"])
        self.assertFalse(record["after_swipe"]["showing"])
        self.assertIn(mock.call("input", "-d", "0", "swipe", "360", "1024", "360", "256", "300"), target.sh.call_args_list)

    def test_secure_keyguard_aborts_without_dismiss_or_swipe(self):
        target = mock.Mock()
        target.sh.side_effect = ["", "KeyguardServiceDelegate\nshowing=true\nsecure=true"]
        with self.assertRaisesRegex(RuntimeError, "Secure keyguard requires user credential"):
            runner.prepare_launch(target, {})
        self.assertEqual(target.sh.call_count, 2)

    def test_unknown_or_persistent_keyguard_aborts_before_launch(self):
        for policy in ("unrecognized policy", "mShowingLockscreen=true"):
            with self.subTest(policy=policy):
                target = mock.Mock()
                target.sh.side_effect = ["", policy, "", policy, "Physical size: 1080x1920", "", policy]
                with mock.patch.object(runner.time, "sleep"), self.assertRaisesRegex(RuntimeError, "Keyguard dismissal not verified"):
                    runner.prepare_launch(target, {})
                self.assertFalse(any(call.args[:2] == ("am", "start") for call in target.sh.call_args_list))

    def test_usb_chooser_dismissal_only_uses_back_for_the_observed_dialog(self):
        chooser = '<hierarchy><node text="Use USB for"/><node text="No data transfer"/><node text="File transfer"/><node text="CANCEL"/></hierarchy>'
        launcher = '<hierarchy><node text="Launcher"/></hierarchy>'
        for initial, after, expected, failure in (
            (chooser, launcher, {"visible": True, "visible_after_back": False}, False),
            (launcher, launcher, {"visible": False}, False),
            (chooser, chooser, {"visible": True, "visible_after_back": True}, True),
        ):
            with self.subTest(expected=expected):
                snapshots = iter([initial, after])
                target = mock.Mock()
                target.sh.side_effect = lambda command, *args, **kwargs: next(snapshots) if command == "cat" else ""
                record = {}
                runtime = "/sdcard/Android/data/dev.ror2lab.arm64/files"
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "USB chooser still visible"):
                        runner.dismiss_usb_chooser(target, runtime, record)
                else:
                    runner.dismiss_usb_chooser(target, runtime, record)
                self.assertEqual(record, expected)
                commands = target.sh.call_args_list
                back = mock.call("input", "-d", "0", "keyevent", "KEYCODE_BACK")
                self.assertEqual(commands.count(back), int(expected["visible"]))
                dumps = [call.args[2] for call in commands if call.args[0] == "uiautomator"]
                self.assertEqual(len(dumps), len(expected))
                self.assertTrue(all(path.startswith(runtime + "/lab-usb-chooser-") for path in dumps))
                self.assertEqual([call.args[2] for call in commands if call.args[0] == "rm"], dumps)

    def test_converted_launch_resolves_bootstrap_instead_of_unity_activity(self):
        target = mock.Mock(package="dev.ror2lab.converted")
        target.sh.side_effect = [
            process_snapshot(),
            "dev.ror2lab.converted/.PayloadBootstrapActivity",
            "started",
            "73",
            process_snapshot(("73", "03:19:58", target.package)),
        ]
        thermal = mock.Mock(error=None)
        checks = []
        result = runner.launch(target, thermal, process_checks=checks)
        self.assertEqual(result["pid"], "73")
        self.assertIn("PayloadBootstrapActivity", result["activity"])
        self.assertEqual([checkpoint["phase"] for checkpoint in checks], ["before-launch", "launch"])
        self.assertEqual(checks[-1]["processes"][0]["pid"], "73")
        thermal.launch.assert_not_called()

    def test_only_resumed_peer_is_reset_before_converted_launch(self):
        peer = "dev.ror2lab.arm64"
        target = mock.Mock(package="dev.ror2lab.converted")
        lease = mock.Mock()
        result = dict(process_checkpoints=[], device_cleanup={})
        target.sh.return_value = process_snapshot(("73", "03:19:58", peer))
        target.cmd.return_value = f"am_proc_start: [0,73,99,{peer},activity,Main]\nunrelated"
        with mock.patch.object(runner, "reset_other_lab") as reset:
            runner.reset_resumed_peer(target, self.request, lease, result)
            record = result["resumed_lab_reset"]
            self.assertEqual(record["process_start_events"], [target.cmd.return_value.splitlines()[0]])
            self.assertEqual(result["process_checkpoints"][-1]["phase"], "after-keyguard")
            reset.assert_called_once_with(self.request, lease, record, result["device_cleanup"])
            target.sh.return_value = process_snapshot(("73", "03:19:58", peer), ("74", "03:20:00", target.package))
            with self.assertRaisesRegex(RuntimeError, "Unexpected owned lab process"):
                runner.reset_resumed_peer(target, self.request, lease, result)
            self.assertEqual(reset.call_count, 1)

    def test_mapping_binds_embedded_attempt_and_measured_checkpoint(self):
        accepted = dict(attempt="measured", observation="missing-observation", observation_sha256="a" * 64, axis=2)
        mapping = dict(accepted, attempt="candidate", accepted_mapping_attempt="measured")
        source = self.root / "mapping.json"
        runner.save(source, mapping)
        checkpoint = self.root / "work/checkpoints/LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE.json"
        runner.save(checkpoint, dict(mapping=accepted, passing=dict(cleanup=True, assertions=1)))
        request = dict(self.request, input_mapping=str(source))
        with mock.patch("installed_attempt.attempt_from_installed", return_value="candidate"):
            self.assertEqual(runner.checked_mapping(request), mapping)
            mapping["axis"] = 3
            runner.save(source, mapping)
            with self.assertRaisesRegex(RuntimeError, "attempt/checkpoint"):
                runner.checked_mapping(request)

    def test_converted_resets_separate_owned_lab_and_verifies_idle(self):
        request = dict(self.request, package="dev.ror2lab.converted")
        lab, lease = mock.Mock(), mock.Mock()
        lab.exists.return_value = True
        with (
            mock.patch.object(device_module, "Device", return_value=lab),
            mock.patch.object(runner, "verify_owned", return_value=dict(apk_sha256=self.digest)),
            mock.patch.object(runner, "reset_idle") as reset,
            mock.patch.object(batch, "_idle_readback", return_value=dict(idle=True)) as idle,
        ):
            record = {}
            runner.reset_other_lab(request, lease, record)
        reset.assert_called_once_with(lab, lease, record, None)
        idle.assert_called_once_with(lab, self.digest)
        self.assertEqual(record["readback"], dict(idle=True))

    def test_package_receipts_are_isolated(self):
        configuration = dict(device_serial="synthetic-device", device_serials=["synthetic-device"], storage_mode="adopted")
        with (
            mock.patch.object(device_module, "require_device_access"),
            mock.patch.object(device_module, "read", return_value=configuration),
            mock.patch.object(device_module, "run", return_value=subprocess.CompletedProcess([], 0, b"List of devices attached\nsynthetic-device\tdevice\n")),
        ):
            lab = device_module.Device(selector="synthetic-device", work_root=self.root / "work")
            converted = device_module.Device(selector="synthetic-device", work_root=self.root / "work", package="dev.ror2lab.converted")
        self.assertNotEqual(lab.receipt("installed.json"), converted.receipt("installed.json"))
        self.assertTrue(converted.receipt("installed.json").is_relative_to(lab.receipt_root / "packages"))


if __name__ == "__main__":
    unittest.main()
