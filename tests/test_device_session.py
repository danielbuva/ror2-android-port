import hashlib
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
import device_session as runner


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

    def test_request_smoke_checks_exact_bytes_without_adb(self):
        with mock.patch.object(runner.subprocess, "run") as process:
            self.assertEqual(runner.main(["--request", str(self.request_file), "--dry-run"]), 0)
        process.assert_not_called()
        self.apk.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            runner.load_request(self.request_file)

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
        launch.assert_called_once_with(target, thermal)
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
        check.assert_called_once_with(target, thermal, checked, self.output)
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
            result = runner.check_software_notices(target, thermal, self.request, self.output)
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
        target, thermal = mock.Mock(), mock.Mock(error=None)
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
            result = runner.check_player_screens(target, thermal, checked, self.output)
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

    def test_capture_records_extracted_metadata_and_unity_extraction_decision(self):
        target = mock.Mock()
        target.cmd.return_value = "Unity extraction diagnostic"
        target.sh.return_value = "metadata hash fixture"
        target.read_receipt.return_value = dict(persistentDataPath="/owned/files")
        runner.capture(target, self.output, "7")
        self.assertEqual((self.output / "il2cpp-metadata-sha256.txt").read_text(), "metadata hash fixture")
        target.sh.assert_any_call("sha256sum", "/owned/files/il2cpp/Metadata/global-metadata.dat", check=False)
        self.assertIn("Unity:D", target.cmd.call_args_list[0].args)

    def run_case(self, *, workload_error=False, terminal_error=False, thermal_error=False, payload=False):
        events = []
        lease_path = runner.Lease(self.request).path
        installed = dict(apk_sha256=self.digest, package_path="package:/fixture/base.apk", package=self.request["package"], serial=self.request["serial"])
        target = mock.Mock(package=self.request["package"], serial=self.request["serial"])
        target.exists.return_value = True
        target.owned.return_value = installed
        target.read_receipt.return_value = dict(persistentDataPath="/owned")
        receipt = self.root / "installed.json"
        receipt.touch()
        target.receipt.return_value = receipt
        target.install.return_value = installed
        target.sync.side_effect = lambda path: events.append("sync:" + str(path)) or dict(files=["content"])
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
            if args[0] == "sha256sum":
                return self.digest + "  /fixture/base.apk"
            if args[:2] == ("am", "force-stop"):
                events.append("stop")
            if args[0] == "rm":
                events.append("remove:" + args[-1])
            return ""

        target.sh.side_effect = shell
        thermal = mock.Mock(error="safety stop" if thermal_error else None, peak_cpu_gpu_celsius=81, time_above_80_seconds=3, admission_battery={})
        thermal.thread = thermal.stopper = None
        thermal.finish.side_effect = RuntimeError("safety stop") if thermal_error else lambda: events.append("thermal-finish")

        def workload(*args, **kwargs):
            self.assertTrue(lease_path.is_dir())
            self.assertIsNotNone(kwargs["_reset_idle"])
            if self.request["mode"] == "sustained":
                self.assertFalse(any(call.args[0] == "push" and call.args[-1].endswith("movement-batch-selection.json") for call in target.cmd.call_args_list))
            events.append("workload")
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
            mock.patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
            mock.patch.object(device_module, "Device", return_value=target),
            mock.patch.object(runner, "placement", return_value={}) as placement,
            mock.patch.object(runner, "run_workload", side_effect=workload),
            mock.patch.object(runner, "prepare_launch") as prepare,
            mock.patch.object(batch, "_GameThermalOwner", return_value=thermal) as owner,
            mock.patch.object(batch, "_idle_readback", side_effect=idle),
            mock.patch.object(batch, "_prune", side_effect=prune),
            mock.patch("session_cleanup_check._remote_path_state", return_value="absent"),
            mock.patch.object(runner.time, "monotonic", return_value=1000),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
        ):
            result = runner.execute(self.request)
        self.assertEqual(placement.call_args_list[0].args[1], self.apk.stat().st_size + payload_size + 20 * 1024**3)
        prepare.assert_called_once_with(target, result["prelaunch"])
        if payload:
            target.sync.assert_called_once_with(self.root / "payload")
            self.assertLess(events.index("sync:" + str(self.root / "payload")), events.index("workload"))
            self.assertEqual(result["sync"], dict(files=["content"]))
        else:
            target.sync.assert_not_called()
        self.assertEqual(owner.call_args.args[-1], 1060)  # run-local cooldown deadline
        self.assertEqual(thermal.deadline, 1630)  # independent workload deadline
        self.assertEqual(events[-1], "prune")
        self.assertIn("asleep", events)
        self.assertEqual(json.loads((self.output / "terminal.done.json").read_text()), result)
        removed = [event for event in events if event.startswith("remove:")]
        self.assertTrue(removed)
        self.assertEqual(events.count("stop"), 3)
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

    def test_payload_synced_before_workload_and_included_in_storage_reserve(self):
        self.assertTrue(self.run_case(payload=True)["success"])

    def test_workload_failure_still_stops_resets_sleeps_and_releases(self):
        result = self.run_case(workload_error=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])
        self.assertIn("observed workload failure", result["error"])

    def test_safety_stop_does_not_strand_clean_device_lease(self):
        result = self.run_case(thermal_error=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["lease_released"])

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

    def test_converted_launch_resolves_bootstrap_instead_of_unity_activity(self):
        target = mock.Mock(package="dev.ror2lab.converted")
        target.sh.side_effect = ["dev.ror2lab.converted/.PayloadBootstrapActivity", "started", "73"]
        thermal = mock.Mock(error=None)
        result = runner.launch(target, thermal)
        self.assertEqual(result["pid"], "73")
        self.assertIn("PayloadBootstrapActivity", result["activity"])
        thermal.launch.assert_not_called()

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
        reset.assert_called_once_with(lab, lease, record)
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
