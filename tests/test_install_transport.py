"""Transport selection must retain ownership, storage and receipt checks."""

from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import device


class InstallTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.apk = self.root / "authored.apk"
        self.apk.write_bytes(b"authored package")
        self.d = Mock(package=device.PACKAGE)
        self.d.serial = "authored-device"
        self.d.settings = {}
        self.d.exists.return_value = True
        self.d.owned.return_value = {"apk_sha256": "previous", "package_path": "package:/data/app/authored/base.apk"}
        self.d.install_counter.return_value = self.root / "counter.json"
        self.d.storage.return_value = {"mode": "internal", "uuid": None}
        self.d.cmd.return_value = "Success"
        self.d.sh.side_effect = self.shell
        self.features = "feature:android.software.incremental_delivery=1\n"
        validation = patch.object(device, "validate_apk_identity")
        self.validate = validation.start()
        self.addCleanup(validation.stop)

    def shell(self, *args):
        if args == ("pm", "list", "features"):
            return self.features
        if args[:2] == ("pm", "path"):
            return "package:/data/app/authored/base.apk"
        if args == ("sha256sum", "/data/app/authored/base.apk"):
            return "previous  /data/app/authored/base.apk"
        return "authored package details"

    def test_default_streaming_is_explicit_and_timed(self):
        result = device.Device.install(self.d, self.apk)
        self.validate.assert_called_once_with(self.apk, device.PACKAGE)
        self.d.owned.assert_called_once()
        self.d.storage.assert_called_once()
        self.d.install_capacity.assert_called_once()
        self.assertEqual(self.d.cmd.call_args.args[:4], ("install", "--streaming", "--no-incremental", "-r"))
        self.assertEqual(result["transport"], "streaming")
        self.assertIn("adb_install", result["timing"]["phases_seconds"])
        self.assertEqual(self.d.write_receipt.call_args.args[0], "installed.json")

    def test_incremental_needs_v4_and_feature_without_implicit_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "v4"):
            device.Device.install(self.d, self.apk, mode="incremental")
        self.d.cmd.assert_not_called()
        Path(str(self.apk) + ".idsig").write_bytes(b"authored sidecar")
        self.features = "feature:android.hardware.camera\n"
        with self.assertRaisesRegex(RuntimeError, "does not advertise"):
            device.Device.install(self.d, self.apk, mode="incremental")
        self.d.cmd.assert_not_called()
        self.features = "feature:android.software.incremental_delivery=1\n"
        result = device.Device.install(self.d, self.apk, mode="incremental")
        self.assertEqual(self.d.cmd.call_args.args[:4], ("install", "--incremental", "--wait", "-r"))
        self.assertEqual(result["transport"], "incremental")
        self.assertEqual(len(result["v4_idsig_sha256"]), 64)

    def test_auto_uses_incremental_only_on_eligible_internal_storage(self):
        self.assertEqual(device.Device.install(self.d, self.apk, mode="auto")["transport"], "streaming")
        self.apk.with_suffix(".apk.idsig").write_bytes(b"authored sidecar")
        self.assertEqual(device.Device.install(self.d, self.apk, mode="auto")["transport"], "incremental")
        self.d.storage.return_value = {"mode": "adopted", "uuid": "fixture-adopted"}
        self.d.sh.return_value = "package:/mnt/expand/fixture-adopted/app/base.apk"
        self.d.sh.side_effect = None
        self.assertEqual(device.Device.install(self.d, self.apk, mode="auto")["transport"], "streaming")
        self.assertEqual(self.d.cmd.call_args.args[-3:], ("--force-uuid", "fixture-adopted", str(self.apk)))

    def test_auto_retries_definite_rejection_as_a_second_dispatch(self):
        self.apk.with_suffix(".apk.idsig").write_bytes(b"authored sidecar")
        self.d.cmd.side_effect = [RuntimeError("Failure [INSTALL_FAILED_INVALID_APK: invalid v4 signature]"), "Success"]
        self.d.install.side_effect = lambda apk, mode: device.Device.install(self.d, apk, mode)
        result = device.Device.install(self.d, self.apk, mode="auto")
        self.assertEqual(result["transport"], "streaming")
        self.assertEqual([call.args[1] for call in self.d.cmd.call_args_list], ["--incremental", "--streaming"])
        self.assertEqual(device.read(self.d.install_counter())["dispatched"], 2)

    def test_auto_does_not_retry_ambiguous_or_changed_install(self):
        self.apk.with_suffix(".apk.idsig").write_bytes(b"authored sidecar")
        self.d.cmd.side_effect = subprocess.TimeoutExpired("adb", 240)
        with self.assertRaises(subprocess.TimeoutExpired):
            device.Device.install(self.d, self.apk, mode="auto")
        self.d.install.assert_not_called()
        self.d.owned.side_effect = [{"apk_sha256": "previous"}, {"apk_sha256": "changed"}]
        self.d.cmd.side_effect = RuntimeError("Failure [INSTALL_FAILED_INVALID_APK: invalid v4 signature]")
        with self.assertRaisesRegex(RuntimeError, "invalid v4"):
            device.Device.install(self.d, self.apk, mode="auto")
        self.d.install.assert_not_called()

    def test_collection_uses_selected_work_root_outside_source_checkout(self):
        d = device.Device.__new__(device.Device)
        d._work_root = self.root / "selected-work"
        d.sh = Mock(return_value="123")
        d.cmd = Mock(return_value="authored log")
        out = d.work_root / "experiments/capture"
        result = d.collect("logs", out)
        self.assertEqual(result, {"artifacts": "selected-work/experiments/capture"})
        self.assertEqual((out / "unity.log").read_text(), "authored log")

    def test_failed_install_writes_attempt_timing_without_replacing_ownership(self):
        self.d.cmd.side_effect = RuntimeError("authored install refusal")
        with self.assertRaisesRegex(RuntimeError, "refusal"):
            device.Device.install(self.d, self.apk)
        name, report = self.d.write_receipt.call_args.args
        self.assertEqual(name, "install-attempt.json")
        self.assertFalse(report["success"])
        self.assertIn("adb_install", report["timing"]["phases_seconds"])


if __name__ == "__main__":
    unittest.main()
