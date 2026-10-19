import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke-device.py"
SPEC = importlib.util.spec_from_file_location("smoke_device", SCRIPT)
smoke_device = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke_device)


class FakeDevice:
    def __init__(self, serial, receipt_root, *, existing=False, fail_capacity=False):
        self.serial = serial
        self.receipt_root = Path(receipt_root)
        self.existing = existing
        self.fail_capacity = fail_capacity
        self.calls = []
        self.storage_result = {
            "serial": serial,
            "mode": "adopted",
            "uuid": "live-uuid-" + serial,
            "internal": {"free_bytes": 20_000_000_000},
            "adopted": {"free_bytes": 20_000_000_000},
        }

    def storage(self):
        self.calls.append(("storage",))
        return self.storage_result

    def validate_apk(self, apk, package):
        self.calls.append(("identity", package))

    def install_capacity(self, apk, storage):
        self.calls.append(("capacity", Path(apk), storage))
        if self.fail_capacity:
            raise RuntimeError("capacity rejected")
        return {"arm64_only": True, "selected_free_bytes": storage["adopted"]["free_bytes"]}

    def cmd(self, *args, **kwargs):
        self.calls.append(("cmd", *args))
        if args[0] == "install":
            return "Success"
        if args[0] == "logcat":
            return "ROR2_BOOTSTRAP_ARM64_OK"
        if args[0] == "pull":
            Path(args[2]).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            return "1 file pulled"
        if args[0] == "uninstall":
            self.existing = False
            return "Success"
        return ""

    def sh(self, *args, **kwargs):
        self.calls.append(("sh", *args))
        if args[:3] == ("pm", "list", "packages"):
            return ("package:" + smoke_device.PACKAGE) if self.existing else ""
        if args[:2] == ("pm", "path"):
            return "/mnt/expand/" + self.storage_result["uuid"] + "/app/base.apk"
        if args[:2] == ("dumpsys", "package"):
            return "codePath=/mnt/expand/" + self.storage_result["uuid"] + "/app\nprimaryCpuAbi=arm64-v8a"
        if args[:2] == ("am", "start"):
            return "Status: ok"
        if args[:1] == ("pidof",):
            return "1234"
        if args[:1] == ("screencap",):
            return ""
        return ""

    def display(self, awake):
        self.calls.append(("display", awake))


class BootstrapDeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "builds").mkdir()
        (self.root / "builds" / "bootstrap-arm64.apk").write_bytes(b"fixture apk")
        self.old_root = smoke_device.ROOT
        smoke_device.ROOT = self.root
        self.addCleanup(setattr, smoke_device, "ROOT", self.old_root)

    def invoke(self, device, *args, timestamp="20261019T000000.000000Z"):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = smoke_device.run(
                list(args), device_factory=lambda **kwargs: device,
                sleep=lambda _seconds: None, timestamp=timestamp,
            )
        return code, json.loads(output.getvalue())

    def test_preexisting_package_is_refused_without_install_or_uninstall(self):
        device = FakeDevice("device-a", self.root / "work" / "device" / "device-a", existing=True)

        code, result = self.invoke(device)

        self.assertEqual(code, 1)
        self.assertIn("already exists", result["error"])
        self.assertFalse(any(call[:2] == ("cmd", "install") for call in device.calls))
        self.assertFalse(any(call[:2] == ("cmd", "uninstall") for call in device.calls))
        self.assertEqual(device.calls[-1], ("display", False))

    def test_capacity_gate_precedes_install_dispatch(self):
        device = FakeDevice("device-a", self.root / "work" / "device" / "device-a", fail_capacity=True)

        code, result = self.invoke(device)

        self.assertEqual(code, 1)
        self.assertIn("capacity rejected", result["error"])
        calls = [call[0] for call in device.calls]
        self.assertLess(calls.index("storage"), calls.index("capacity"))
        self.assertNotIn("install", calls)

    def test_wrong_apk_identity_never_installs_any_package(self):
        device = FakeDevice("device-a", self.root / "work/device/device-a")

        def refuse_identity(apk, package):
            raise RuntimeError("wrong bootstrap identity")

        device.validate_apk = refuse_identity
        code, result = self.invoke(device)
        self.assertEqual(code, 1)
        self.assertIn("wrong bootstrap identity", result["error"])
        self.assertFalse(any(call[:2] == ("cmd", "install") for call in device.calls))

    def test_outputs_are_per_device_and_cleanup_targets_selected_device(self):
        first = FakeDevice("device-a", self.root / "work" / "device" / "device-a")
        second = FakeDevice("device-b", self.root / "work" / "device" / "device-b")

        code_a, result_a = self.invoke(first, timestamp="run-a")
        code_b, result_b = self.invoke(second, timestamp="run-b")

        self.assertEqual((code_a, code_b), (0, 0))
        self.assertTrue(result_a["placement_verified"])
        self.assertTrue(result_b["placement_verified"])
        self.assertIn("device-a/bootstrap/run-a", result_a["result"])
        self.assertIn("device-b/bootstrap/run-b", result_b["result"])
        self.assertTrue(Path(result_a["logcat"]).is_file())
        self.assertTrue(Path(result_a["screenshot"]).is_file())
        self.assertTrue(Path(result_b["logcat"]).is_file())
        self.assertTrue(Path(result_b["screenshot"]).is_file())
        self.assertTrue(any(call == ("cmd", "install", "--force-uuid", first.storage_result["uuid"], str(self.root / "builds" / "bootstrap-arm64.apk")) for call in first.calls))
        self.assertTrue(any(call == ("cmd", "install", "--force-uuid", second.storage_result["uuid"], str(self.root / "builds" / "bootstrap-arm64.apk")) for call in second.calls))
        self.assertIn(("display", False), first.calls)
        self.assertIn(("display", False), second.calls)
        self.assertTrue(any(call[:3] == ("sh", "am", "force-stop") for call in first.calls))
        self.assertTrue(any(call[:3] == ("sh", "am", "force-stop") for call in second.calls))
        self.assertFalse((self.root / "environment" / "smoke-result.json").exists())

    def test_adopted_flag_cannot_override_internal_policy(self):
        device = FakeDevice("device-a", self.root / "work" / "device" / "device-a")
        device.storage_result.update({"mode": "internal", "uuid": None, "adopted": None})

        code, result = self.invoke(device, "--adopted")

        self.assertEqual(code, 1)
        self.assertIn("only confirms", result["error"])
        self.assertFalse(any(call[:2] == ("cmd", "install") for call in device.calls))


if __name__ == "__main__":
    unittest.main()
