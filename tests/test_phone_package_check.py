import unittest
from unittest.mock import Mock, patch

from phone_apk import PACKAGE
from phone_package_check import check_action, cleanup_owned


class PhonePackageCheckTests(unittest.TestCase):
    def test_cleanup_refuses_unowned_bytes_before_stop_or_uninstall(self):
        device = Mock()
        device.sh.side_effect = ["package:/data/app/fixture/base.apk", "different /data/app/fixture/base.apk"]
        with self.assertRaisesRegex(RuntimeError, "cleanup refused"):
            cleanup_owned(device, {"owned"})
        self.assertEqual(device.sh.call_count, 2)
        device.cmd.assert_not_called()

    def test_cleanup_removes_only_hash_verified_fixture_and_checks_absence(self):
        device = Mock()
        device.sh.side_effect = ["package:/data/app/fixture/base.apk", "owned /data/app/fixture/base.apk", "", ""]
        self.assertTrue(cleanup_owned(device, {"owned"}))
        device.cmd.assert_called_once_with("uninstall", PACKAGE)
        self.assertEqual(device.sh.call_args_list[2].args, ("am", "force-stop", PACKAGE))
        self.assertEqual(device.sh.call_args_list[3].args, ("pm", "path", PACKAGE))

    def test_explicit_device_required_before_request_or_device_access(self):
        with patch("device_context.command_selectors", return_value=(None, None)), patch("device.Device") as device:
            with self.assertRaisesRegex(RuntimeError, "explicit --device"):
                check_action("unused-request")
            device.assert_not_called()
