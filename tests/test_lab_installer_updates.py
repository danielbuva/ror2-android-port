"""Host-only contracts: no keys, APKs, game inputs, tools, or device calls."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lab_installer_updates", ROOT / "scripts/lab-installer-updates.py")
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)


class LabInstallerUpdatesTests(unittest.TestCase):
    def test_missing_explicit_device_emits_all_failures_without_setup(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(LAB, "read_context") as config, redirect_stdout(output):
            self.assertEqual(LAB.main([]), 1)
        config.assert_not_called()
        self.assertEqual(len(output.getvalue().splitlines()), len(LAB.CASES))
        for case in LAB.CASES:
            self.assertIn("FAIL " + case, output.getvalue())
        self.assertNotIn(str(ROOT), output.getvalue())

    def test_missing_toolhost_context_refuses_without_scanning_or_device(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LAB.Failure, "LAB_TOOLHOST_ROOT-required"):
                LAB.read_context()

    def test_synthetic_manifest_uses_aapt1_required_basename(self):
        # Only source XML is created: no toolchain invocation, APK or key.
        with tempfile.TemporaryDirectory() as temporary:
            manifest = LAB.synthetic_manifest(Path(temporary))
            self.assertEqual(manifest.name, "AndroidManifest.xml")
            root = ET.parse(manifest).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual(root.get("package"), LAB.GAME)
        self.assertEqual(root.find("application").get(android + "debuggable"), "true")
        self.assertEqual(root.find("application/activity").get(android + "name"), "com.unity3d.player.UnityPlayerActivity")

    def test_http_assets_metadata_and_request_observation(self):
        files = {"release.json": b'{"version":"synthetic"}', "release.sig": b"authored signature substitute", "public-tools.zip": b"not an APK"}
        with LAB.server() as service:
            base = LAB.publish(service, files, 2)
            with urllib.request.urlopen(base + "latest.json") as response:
                metadata = json.load(response)
            self.assertEqual(metadata["tag_name"], "owner-v2")
            self.assertEqual({row["name"] for row in metadata["assets"]}, set(files))
            self.assertNotIn("/public-tools.zip", service.requests)
            for row in metadata["assets"]:
                self.assertEqual(row["browser_download_url"], base + row["name"])
                self.assertEqual(row["size"], len(files[row["name"]]))
            LAB.publish(service, files, 1)
            self.assertEqual(service.requests, [])

    def test_no_permission_setting_without_explicit_flag_and_fresh_ownership(self):
        for authorized, owned in ((False, True), (True, False), (False, False)):
            phone = LAB.Phone("synthetic-private-selector", 1, authorized)
            phone.owned_installer = owned
            with patch.object(phone, "shell", return_value=b"No operations.") as shell:
                with self.assertRaisesRegex(LAB.Failure, "owner-authorization-required"):
                    phone.await_install_permission()
                shell.assert_called_once_with("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES")

    def test_permission_flag_is_scoped_to_fresh_test_package(self):
        phone = LAB.Phone("synthetic-private-selector", 1, True)
        phone.owned_installer = True
        with patch.object(phone, "shell", return_value=b"No operations.") as shell:
            phone.await_install_permission()
        self.assertEqual(shell.call_args.args, ("appops", "set", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", "allow"))

    def test_occupied_alpha_refuses_before_build_and_key_creation(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with (
            patch.object(LAB, "HostTools"),
            patch.object(phone, "occupied", return_value=True),
            patch.object(LAB, "prepare_artifacts") as build,
            patch.object(LAB, "publisher_keys") as keys,
        ):
            with self.assertRaisesRegex(LAB.Failure, "occupied-package"):
                LAB.acceptance(phone, {}, Path("/unused"), lambda case: None)
        build.assert_not_called()
        keys.assert_not_called()

    def test_unowned_cleanup_never_uninstalls_or_reads_app_data(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with patch.object(phone, "command") as command, patch.object(phone, "shell") as shell, patch.object(phone, "read") as read:
            phone.cleanup()
        command.assert_not_called()
        read.assert_not_called()
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_SLEEP")

    def test_changed_alpha_blocks_uninstall_and_keeps_installer_receipts(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        phone.installer_hash = "a" * 64
        with (
            patch.object(phone, "occupied", return_value=True),
            patch.object(phone, "package_hash", return_value="b" * 64),
            patch.object(phone, "read", return_value={"application_id": LAB.GAME, "sha256": "c" * 64}),
            patch.object(phone, "command") as command,
            patch.object(phone, "shell") as shell,
        ):
            with self.assertRaisesRegex(LAB.Failure, "ownership-not-established"):
                phone.cleanup()
        command.assert_not_called()
        self.assertEqual(shell.call_args.args, ("input", "keyevent", "KEYCODE_SLEEP"))

    def test_subprocess_error_does_not_publish_argv_stderr_or_identifiers(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "not-for-publication"}),
            patch.object(LAB, "read_context", side_effect=RuntimeError("private-path-not-for-publication")),
            redirect_stdout(output),
        ):
            self.assertEqual(LAB.main([]), 1)
        self.assertNotIn("not-for-publication", output.getvalue())
        self.assertIn("unexpected-local-error", output.getvalue())


if __name__ == "__main__":
    unittest.main()
