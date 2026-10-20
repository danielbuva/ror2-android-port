import unittest
from unittest.mock import Mock, patch

from phone_apk import PACKAGE
from phone_package_check import bind_runtime, check_action, cleanup_owned


class PhonePackageCheckTests(unittest.TestCase):
    def test_runtime_uses_observed_canonical_paths_and_separate_backing(self):
        paths = {
            "persistentDataPath": "/alias/" + PACKAGE + "/files",
            "filesDir": "/data/user/0/" + PACKAGE + "/files",
            "externalFilesDir": "/actual/" + PACKAGE + "/files",
        }
        device = Mock()
        actual = paths["externalFilesDir"]
        device.sh.side_effect = [actual, actual, paths["filesDir"], "/data/user/0/" + PACKAGE, "1:2", "1:2", "private backing", "runtime backing"]
        result = bind_runtime(device, paths, {"mode": "internal"})
        self.assertEqual(result["directory"], actual)
        self.assertEqual(result["app_data_backing"], "private backing")
        self.assertEqual(result["runtime_backing"], "runtime backing")

    def test_mismatched_runtime_alias_or_storage_backing_is_refused(self):
        paths = {key: "/data/" + PACKAGE + "/files" for key in ("persistentDataPath", "filesDir", "externalFilesDir")}
        for observed in (["one", "different", paths["filesDir"], "/data/" + PACKAGE], ["same", "same", paths["filesDir"], "/data/" + PACKAGE]):
            device = Mock()
            device.sh.side_effect = observed + ["1:2", "1:2"]
            with self.assertRaises(ValueError):
                bind_runtime(device, paths, {"mode": "adopted", "uuid": "selected-volume"})

    def test_private_alias_requires_matching_filesystem_and_inode_identity(self):
        paths = {
            "persistentDataPath": "/external/" + PACKAGE + "/files",
            "externalFilesDir": "/external/" + PACKAGE + "/files",
            "filesDir": "/data/data/" + PACKAGE + "/files",
        }
        for identity, accepted in (("1:2", True), ("2:2", False), ("1:3", False)):
            device = Mock()
            device.sh.side_effect = [
                paths["persistentDataPath"],
                paths["externalFilesDir"],
                paths["filesDir"],
                "/data/user/0/" + PACKAGE,
                "1:2",
                identity,
                "private backing",
                "runtime backing",
            ]
            if accepted:
                self.assertEqual(bind_runtime(device, paths, {"mode": "internal"})["directory"], paths["persistentDataPath"])
            else:
                with self.assertRaises(ValueError):
                    bind_runtime(device, paths, {"mode": "internal"})

    def test_cleanup_refuses_unowned_bytes_before_stop_or_uninstall(self):
        device = Mock()
        device.sh.side_effect = ["package:" + PACKAGE, "package:/data/app/fixture/base.apk", "different /data/app/fixture/base.apk"]
        with self.assertRaisesRegex(RuntimeError, "cleanup refused"):
            cleanup_owned(device, {"owned"})
        self.assertEqual(device.sh.call_count, 3)
        device.cmd.assert_not_called()

    def test_cleanup_removes_only_hash_verified_fixture_and_checks_absence(self):
        device = Mock()
        device.sh.side_effect = ["package:" + PACKAGE, "package:/data/app/fixture/base.apk", "owned /data/app/fixture/base.apk", "", ""]
        self.assertTrue(cleanup_owned(device, {"owned"}))
        device.cmd.assert_called_once_with("uninstall", PACKAGE)
        self.assertEqual(device.sh.call_args_list[3].args, ("am", "force-stop", PACKAGE))
        self.assertEqual(device.sh.call_args_list[4].args, ("pm", "list", "packages", PACKAGE))

    def test_package_absence_uses_successful_inventory_without_requesting_a_path(self):
        device = Mock()
        device.sh.return_value = ""
        self.assertTrue(cleanup_owned(device, {"owned"}))
        device.sh.assert_called_once_with("pm", "list", "packages", PACKAGE)
        device.cmd.assert_not_called()

    def test_explicit_device_required_before_request_or_device_access(self):
        with patch("device_context.command_selectors", return_value=(None, None)), patch("device.Device") as device:
            with self.assertRaisesRegex(RuntimeError, "explicit --device"):
                check_action("unused-request")
            device.assert_not_called()
