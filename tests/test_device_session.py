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

        def workload(*args):
            self.assertTrue(lease_path.is_dir())
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
            mock.patch.object(batch, "_GameThermalOwner", return_value=thermal) as owner,
            mock.patch.object(batch, "_idle_readback", side_effect=idle),
            mock.patch.object(batch, "_prune", side_effect=prune),
            mock.patch("session_cleanup_check._remote_path_state", return_value="absent"),
            mock.patch.object(runner.time, "monotonic", return_value=1000),
            mock.patch.object(runner.shutil, "disk_usage", return_value=mock.Mock(free=30 * 1024**3)),
        ):
            result = runner.execute(self.request)
        self.assertEqual(placement.call_args_list[0].args[1], self.apk.stat().st_size + payload_size + 20 * 1024**3)
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
