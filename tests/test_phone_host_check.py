import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

from phone_host_check import PACKAGE, check_action, cleanup_owned, validate_control


class PhoneHostCheckTests(unittest.TestCase):
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
