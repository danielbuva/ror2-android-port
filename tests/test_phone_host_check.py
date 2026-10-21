import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

from phone_host_check import PACKAGE, check_action, cleanup_owned, request_target, validate_control, validate_report


class PhoneHostCheckTests(unittest.TestCase):
    def test_request_preserves_legacy_target_and_allows_only_explicit_authored_variant(self):
        legacy = {"apk": "fixture", "sha256": "hash"}
        self.assertEqual(request_target(legacy), 30)
        self.assertEqual(request_target(dict(legacy, target_sdk=33)), 33)
        for value in (28, 29, 32, 34, "33", True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                request_target(dict(legacy, target_sdk=value))
        with self.assertRaises(ValueError):
            request_target(dict(legacy, bypass=True))

    def test_report_requires_actual_child_identity_and_writable_refusal(self):
        for target, domain in ((30, "untrusted_app_30"), (33, "untrusted_app")):
            context = "u:r:" + domain + ":s0:c1,c2"
            child = {"marker": "authored-phone-host-v1", "answer": 42, "uid": 10001, "context": context}
            report = {
                "targetSdk": target,
                "deviceApi": 33,
                "uid": 10001,
                "selfContext": context,
                "success": True,
                "installedPassed": True,
                "installedExists": True,
                "installedWritable": False,
                "writableRefused": True,
                "writableMarkedExecutable": True,
                "installed": {"exit": 0, "output": json.dumps(child)},
                "writable": {"error": "Cannot run program: error=13, Permission denied"},
            }
            validate_report(report, target)
            mutations = [
                ("targetSdk", 28),
                ("deviceApi", 29),
                ("uid", 0),
                ("success", False),
                ("installedWritable", True),
                ("writableMarkedExecutable", False),
                ("selfContext", "u:r:runas_app:s0:c1,c2"),
                ("installed", {"exit": 1, "output": json.dumps(child)}),
                ("installed", {"exit": 0, "output": json.dumps(dict(child, uid=2000))}),
                ("installed", {"exit": 0, "output": json.dumps(dict(child, context="u:r:shell:s0"))}),
                ("installed", {"exit": 0, "output": json.dumps(dict(child, answer=41))}),
                ("writable", {"exit": 0, "output": json.dumps(child)}),
                ("writable", {"error": "error=2, No such file or directory"}),
                ("writable", {"error": "error=13", "exit": 0}),
            ]
            for key, value in mutations:
                with self.subTest(target=target, key=key, value=value), self.assertRaises(ValueError):
                    changed = copy.deepcopy(report)
                    changed[key] = value
                    validate_report(changed, target)

    def test_explicit_device_required_before_request_or_device_access(self):
        with patch("device_context.command_selectors", return_value=(None, None)), patch("device.Device") as device:
            with self.assertRaisesRegex(RuntimeError, "explicit --device"):
                check_action("unused")
            device.assert_not_called()

    def test_unowned_package_is_never_stopped_or_removed(self):
        device = Mock()
        with patch("phone_host_check.package_hash", return_value="unknown"):
            with self.assertRaisesRegex(RuntimeError, "unowned"):
                cleanup_owned(device, "owned")
        device.sh.assert_not_called()
        device.cmd.assert_not_called()

    def test_owned_cleanup_verifies_removal(self):
        device = Mock()
        with patch("phone_host_check.package_hash", side_effect=["owned", None]):
            self.assertTrue(cleanup_owned(device, "owned"))
        device.sh.assert_called_once_with("am", "force-stop", PACKAGE)
        device.cmd.assert_called_once_with("uninstall", PACKAGE)

    def test_negative_control_must_have_identical_native_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / "fixture.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("lib/arm64-v8a/libtoolprobe.so", b"\x7fELF" + b"\0" * 14 + b"\xb7\0")
                archive.writestr("assets/control.bin", b"different")
            with self.assertRaisesRegex(ValueError, "identical"):
                validate_control(apk)


import copy
import json
