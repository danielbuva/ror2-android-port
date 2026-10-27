"""Host-only contracts: no keys, APKs, game inputs, tools, or device calls."""

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
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
    @staticmethod
    def private_ui_logs(root, run_name, dump=b"ERROR: could not get idle state.\n", read_error=b"cat: /synthetic/private/ui.xml: No such file or directory\n"):
        directory = root / "work/coordination/installer-update-acceptance" / run_name
        directory.mkdir(parents=True)
        for sequence, category, code, stdout, stderr in ((1, "device-ui-dump", 0, dump, b""), (2, "device-ui-read", 1, b"", read_error)):
            prefix = f"{sequence:05d}-{category}"
            (directory / (prefix + ".json")).write_bytes(
                LAB.encoded({"phase": "baseline-N-check", "category": category, "returncode": code, "outcome": "returned"})
            )
            (directory / (prefix + ".stdout.log")).write_bytes(stdout)
            (directory / (prefix + ".stderr.log")).write_bytes(stderr)
        return directory

    def log_inspection(self, root, args):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(LAB, "ROOT", root))
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            for name in ("read_context", "Phone", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("log inspection must not call " + name)))
            run = stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=AssertionError("log inspection must not execute a command")))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main(["--inspect-ui-failure", *args])
        run.assert_not_called()
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertNotIn(str(root), output.getvalue())
        return code, json.loads(output.getvalue())

    def test_private_ui_log_summary_selects_one_run_and_only_fixed_classifications(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.private_ui_logs(root, "run-first000", dump=b"ERROR: null root node returned by UiTestAutomationBridge.\n")
            newest = self.private_ui_logs(root, "run-newest00")
            os.utime(first, ns=(1, 1))
            os.utime(newest, ns=(2, 2))
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 0)
            self.assertEqual(result["selection"], "newest")
            self.assertEqual([row["category"] for row in result["records"]], ["device-ui-dump", "device-ui-read"])
            self.assertEqual(result["records"][0]["stdout"], "idle-timeout")
            self.assertEqual(result["records"][0]["returncode"], "zero")
            self.assertEqual(result["records"][1]["stderr"], "missing-file")
            self.assertEqual(result["records"][1]["returncode"], "nonzero")
            code, explicit = self.log_inspection(root, ["--diagnostic-run", "run-first000"])
            self.assertEqual(code, 0)
            self.assertEqual(explicit["selection"], "explicit")
            self.assertEqual(explicit["records"][0]["stdout"], "null-root")
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})
            for private in ("synthetic", "ui.xml", "run-newest00", "run-first000", "UiTestAutomationBridge"):
                self.assertNotIn(private, json.dumps([result, explicit]))

    def test_private_ui_log_classification_never_echoes_unknown_output(self):
        for data, expected in (
            (b"synthetic-private-error", "other-output"),
            (b" ", "empty"),
            (b"cat: /synthetic/private: Permission denied", "permission-denied"),
            (b"UI hierchary dumped to: /synthetic/private", "dump-reported-written"),
            (b"UI hierarchy dumped to: /synthetic/private", "dump-reported-written"),
            (b"ERROR: Error while dumping window hierarchy: synthetic-private", "hierarchy-write-error"),
            (b'<?xml version="1.0"?><hierarchy>synthetic-private</hierarchy>', "hierarchy-present"),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(LAB.ui_output_classification(data), expected)

    def test_private_ui_log_summary_rejects_unconstrained_selection_and_other_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.private_ui_logs(root, "run-newest00")
            for args in (
                [],
                ["--diagnostic-run", "../synthetic-private"],
                ["--diagnostic-run", str(root)],
                ["--diagnostic-run", "newest", "--inspect-state"],
                ["--diagnostic-run", "newest", "--allow-test-installs"],
            ):
                with self.subTest(args=args):
                    code, result = self.log_inspection(root, args)
                    self.assertEqual(code, 1)
                    self.assertEqual(result["records"], [])
                    self.assertNotIn("synthetic-private", json.dumps(result))

    def test_private_ui_log_summary_refuses_symlinks_and_does_not_search_other_namespaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "work/coordination/installer-update-acceptance"
            other = root / "unrelated"
            other.mkdir()
            parent.mkdir(parents=True)
            (parent / "run-symlink0").symlink_to(other, target_is_directory=True)
            for selection in ("newest", "run-symlink0"):
                code, result = self.log_inspection(root, ["--diagnostic-run", selection])
                self.assertEqual(code, 1)
                self.assertEqual(result["records"], [])
            directory = self.private_ui_logs(root, "run-newest00")
            record = directory / "00002-device-ui-read.stderr.log"
            record.unlink()
            record.symlink_to(other / "not-read")
            code, result = self.log_inspection(root, ["--diagnostic-run", "newest"])
            self.assertEqual(code, 1)
            self.assertEqual(result["errors"], ["log-inspection-record-unavailable"])

    def inspection(self, results, extra_args=(), environment=None):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(os.environ, environment if environment is not None else {"LAB_DEVICE_SERIAL": "synthetic-private-selector"}, clear=True)
            )
            for name in ("read_context", "PrivateDiagnostics", "prepare_artifacts", "publisher_keys", "acceptance", "server"):
                stack.enter_context(patch.object(LAB, name, side_effect=AssertionError("inspection must not call " + name)))
            for name in ("cleanup", "ui", "start", "put", "read", "storage", "await_install_permission"):
                stack.enter_context(patch.object(LAB.Phone, name, side_effect=AssertionError("inspection must not call " + name)))
            run = stack.enter_context(patch.object(LAB.subprocess, "run", side_effect=results))
            stack.enter_context(redirect_stdout(output))
            code = LAB.main(["--inspect-state", *extra_args])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return code, json.loads(output.getvalue()), run.call_args_list

    def test_inspection_only_queries_fixed_packages_and_normalizes_permission(self):
        path = subprocess.CompletedProcess([], 0, b"package:/synthetic/private/base.apk\n", b"")
        digest = subprocess.CompletedProcess([], 0, b"a" * 64 + b"  /synthetic/private/base.apk\n", b"")
        for mode in ("allow", "ignore", "deny", "default", "foreground", "unset"):
            with self.subTest(mode=mode):
                permission = b"No operations.\n" if mode == "unset" else ("REQUEST_INSTALL_PACKAGES: " + mode + "; time=synthetic-private\n").encode()
                code, result, calls = self.inspection(
                    [path, path, digest, path, path, digest, subprocess.CompletedProcess([], 0, permission, b"")],
                    ["--expected-installer-sha256", "a" * 64],
                )
                self.assertEqual(code, 0)
                self.assertEqual(result["status"], "observed")
                self.assertEqual(result["installer"], {"presence": "present", "hash": "match", "install_permission": mode})
                self.assertEqual(result["alpha"], {"presence": "present", "hash": "read"})
                self.assertEqual(
                    [call.args[0][3:] for call in calls],
                    [
                        ["shell", "pm", "path", LAB.PACKAGE],
                        ["shell", "pm", "path", LAB.PACKAGE],
                        ["shell", "sha256sum", "/synthetic/private/base.apk"],
                        ["shell", "pm", "path", LAB.GAME],
                        ["shell", "pm", "path", LAB.GAME],
                        ["shell", "sha256sum", "/synthetic/private/base.apk"],
                        ["shell", "appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"],
                    ],
                )
                for private in ("synthetic", "a" * 64, "/", "PASS"):
                    self.assertNotIn(private, json.dumps(result))

    def test_inspection_absence_and_hash_mismatch_do_not_adopt_or_mutate(self):
        absent = subprocess.CompletedProcess([], 1, b"", b"")
        code, result, calls = self.inspection([absent, absent], ["--expected-installer-sha256", "a" * 64])
        self.assertEqual(code, 0)
        self.assertEqual(result["installer"], {"presence": "absent", "hash": "absent", "install_permission": "not-installed"})
        self.assertEqual(result["alpha"], {"presence": "absent", "hash": "absent"})
        self.assertEqual(len(calls), 2)
        path = subprocess.CompletedProcess([], 0, b"package:/synthetic/private/base.apk\n", b"")
        code, result, calls = self.inspection(
            [
                path,
                path,
                subprocess.CompletedProcess([], 0, b"b" * 64 + b"  /synthetic/private/base.apk", b""),
                absent,
                subprocess.CompletedProcess([], 0, b"No operations.", b""),
            ],
            ["--expected-installer-sha256", "a" * 64],
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["installer"]["hash"], "mismatch")
        self.assertEqual(result["status"], "observed")
        self.assertEqual(calls[-1].args[0][-4:], ["appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES"])

    def test_inspection_requires_explicit_device_and_expected_hash_before_queries(self):
        for args, environment in (
            ([], None),
            (["--expected-installer-sha256", "synthetic-private-invalid"], None),
            (["--expected-installer-sha256", "a" * 64], {}),
            (["--expected-installer-sha256", "a" * 64, "--allow-test-installs"], None),
            (["--expected-installer-sha256", "a" * 64, "--host-only"], None),
        ):
            with self.subTest(args=args, environment=environment):
                code, result, calls = self.inspection([], args, environment)
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["installer"]["presence"], "unknown")
                self.assertEqual(calls, [])
                self.assertNotIn("synthetic-private", json.dumps(result))

    def test_inspection_query_failure_is_unknown_not_absent_and_redacts_output(self):
        code, result, calls = self.inspection(
            [subprocess.CompletedProcess([], 1, b"synthetic-private-output", b"synthetic-private-error"), subprocess.CompletedProcess([], 1, b"", b"")],
            ["--expected-installer-sha256", "a" * 64],
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["installer"]["presence"], "unknown")
        self.assertEqual(result["alpha"]["presence"], "absent")
        self.assertEqual(result["errors"], ["device-package-path-query"])
        self.assertEqual(len(calls), 2)
        self.assertNotIn("synthetic-private", json.dumps(result))

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

    def test_pm_path_empty_success_or_exit_one_is_absence(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        for code in (0, 1):
            with self.subTest(code=code), patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], code, b"", b"")) as run:
                self.assertFalse(phone.occupied(LAB.GAME))
                self.assertEqual(run.call_args.args[0][-4:], ["shell", "pm", "path", LAB.GAME])
                with patch.object(phone, "shell") as shell:
                    with self.assertRaisesRegex(LAB.Failure, "installed-package-shape"):
                        phone.package_hash(LAB.GAME)
                shell.assert_not_called()

    def test_pm_path_present_package_still_requires_exact_hash_readback(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 0, b"package:/synthetic/app/base.apk\n", b"")
        with (
            patch.object(LAB.subprocess, "run", return_value=result),
            patch.object(phone, "shell", return_value=b"a" * 64 + b"  /synthetic/app/base.apk\n") as shell,
        ):
            self.assertTrue(phone.occupied(LAB.GAME))
            self.assertEqual(phone.package_hash(LAB.GAME), "a" * 64)
        shell.assert_called_once_with("sha256sum", "/synthetic/app/base.apk", label="device-package-hash")

    def test_pm_path_other_errors_never_count_as_absence_or_print_raw_error(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        for code, stdout, stderr in (
            (1, b"", b"synthetic-private-error"),
            (1, b"synthetic-private-error", b""),
            (1, b"package:/synthetic/app/base.apk\n", b""),
            (0, b"", b"synthetic-private-error"),
            (2, b"", b""),
            (0, b"synthetic-private-error", b""),
        ):
            with (
                self.subTest(code=code, stdout=stdout, stderr=stderr),
                patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], code, stdout, stderr)),
            ):
                with self.assertRaises(LAB.Failure) as failure:
                    phone.occupied(LAB.GAME)
                self.assertIn(str(failure.exception), {"device-package-path-query", "device-package-path-shape"})
                self.assertNotIn("synthetic-private-error", str(failure.exception))

    def test_no_permission_setting_without_explicit_flag_and_fresh_ownership(self):
        for authorized, owned in ((False, True), (True, False), (False, False)):
            phone = LAB.Phone("synthetic-private-selector", 1, authorized)
            phone.owned_installer = owned
            with patch.object(phone, "shell", return_value=b"No operations.") as shell:
                with self.assertRaisesRegex(LAB.Failure, "owner-authorization-required"):
                    phone.await_install_permission()
                shell.assert_called_once_with("appops", "get", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", label="device-install-permission-query")

    def test_permission_flag_is_scoped_to_fresh_test_package(self):
        phone = LAB.Phone("synthetic-private-selector", 1, True)
        phone.owned_installer = True
        with patch.object(phone, "shell", return_value=b"No operations.") as shell:
            phone.await_install_permission()
        self.assertEqual(shell.call_args.args, ("appops", "set", LAB.PACKAGE, "REQUEST_INSTALL_PACKAGES", "allow"))

    @staticmethod
    def notification_dialog(message="Allow Owner game installer to send you notifications?", button="permission_deny_button"):
        tree = ET.Element("hierarchy")
        controller = "com.android.permissioncontroller"
        ET.SubElement(tree, "node", {"package": controller, "resource-id": controller + ":id/permission_message", "text": message})
        ET.SubElement(
            tree,
            "node",
            {"package": controller, "resource-id": controller + ":id/" + button, "text": "Don’t allow", "enabled": "true", "bounds": "[20,40][100,80]"},
        )
        return tree

    def test_null_root_dump_retries_before_reading_and_cleans_successful_dump(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        xml = b'<?xml version="1.0"?><hierarchy><node text="synthetic"/></hierarchy>'
        success = subprocess.CompletedProcess([], 0, b"UI hierchary dumped to: /synthetic/private/ui.xml", b"")
        for stdout, stderr in ((b"", b"ERROR: null root node returned by UiTestAutomationBridge."), (b"ERROR: null root node", b"")):
            with self.subTest(stdout=stdout, stderr=stderr):
                events = []

                def execute(*args, **kwargs):
                    events.append("dump")
                    return subprocess.CompletedProcess([], 0, stdout, stderr) if events.count("dump") == 1 else success

                def shell(*args, **kwargs):
                    events.append(args[0])
                    return xml if args[0] == "cat" else b""

                with (
                    patch.object(LAB, "execute", side_effect=execute) as dump,
                    patch.object(phone, "shell", side_effect=shell) as command,
                    patch.object(LAB.time, "sleep", side_effect=lambda seconds: events.append("wait")),
                ):
                    self.assertEqual(phone.ui().tag, "hierarchy")
                self.assertEqual(events, ["dump", "wait", "dump", "cat", "rm"])
                self.assertEqual(dump.call_count, 2)
                self.assertEqual(command.call_args_list[-1].args, ("rm", "-f", phone.ui_path))
                self.assertTrue(all(call.kwargs == {"label": "device-ui-dump", "timeout": 30} for call in dump.call_args_list))

    def test_null_root_dump_retry_limit_never_reads_nonexistent_file(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 0, b"", b"ERROR: null root node synthetic-private-detail")
        with patch.object(LAB, "execute", return_value=result) as dump, patch.object(phone, "shell") as shell, patch.object(LAB.time, "sleep") as sleep:
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-null-root-retry-exhausted$"):
                phone.ui()
        self.assertEqual(dump.call_count, 3)
        self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (1,)])
        shell.assert_not_called()

    def test_ui_dump_retry_does_not_retry_nonzero_or_unrelated_read_failure(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        result = subprocess.CompletedProcess([], 1, b"", b"ERROR: null root node synthetic-private-detail")
        with patch.object(LAB, "execute", return_value=result) as dump, patch.object(phone, "shell") as shell, patch.object(LAB.time, "sleep") as sleep:
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-dump$"):
                phone.ui()
        dump.assert_called_once()
        shell.assert_not_called()
        sleep.assert_not_called()
        with (
            patch.object(LAB, "execute", return_value=subprocess.CompletedProcess([], 0, b"UI hierarchy dumped to: /synthetic/private", b"")) as dump,
            patch.object(phone, "shell", side_effect=[LAB.Failure("device-ui-read"), b""]) as shell,
            patch.object(LAB.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(LAB.Failure, "^device-ui-read$"):
                phone.ui()
        dump.assert_called_once()
        self.assertEqual([call.args[0] for call in shell.call_args_list], ["cat", "rm"])
        sleep.assert_not_called()

    def test_notification_dialog_denied_by_scoped_resource_id_not_button_text(self):
        manifest = ET.parse(ROOT / "tools/phone-build/managed-host/AndroidManifest.xml").getroot()
        self.assertEqual(manifest.find("application").get("{http://schemas.android.com/apk/res/android}label"), "Owner game installer")
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        with patch.object(phone, "ui", side_effect=[self.notification_dialog(), ET.Element("hierarchy")]), patch.object(phone, "shell") as shell:
            self.assertTrue(phone.dismiss_notification_permission())
        shell.assert_called_once_with("input", "tap", "60", "60", label="device-notification-deny")
        with patch.object(phone, "shell") as shell, patch.object(LAB.time, "sleep"), patch.object(phone, "dismiss_notification_permission") as dismiss:
            phone.start()
            phone.start()
        self.assertEqual(dismiss.call_count, 2)
        self.assertEqual(shell.call_args_list[0].args, ("input", "keyevent", "KEYCODE_WAKEUP"))
        self.assertEqual(shell.call_args_list[2].args, ("am", "start", "-W", "-n", LAB.ACTIVITY))

    def test_notification_dialog_does_not_act_without_prompt_or_fresh_ownership(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        with patch.object(phone, "ui") as ui, patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "notification-dialog-installer-not-owned"):
                phone.dismiss_notification_permission()
            ui.assert_not_called()
            shell.assert_not_called()
        phone.owned_installer = True
        with patch.object(phone, "ui", return_value=ET.Element("hierarchy")), patch.object(phone, "shell") as shell:
            self.assertFalse(phone.dismiss_notification_permission())
            shell.assert_not_called()

    def test_notification_dialog_rejects_other_apps_permissions_and_allow_button(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        for dialog, reason in (
            (self.notification_dialog("Allow another app to send you notifications?"), "notification-dialog-not-identified"),
            (self.notification_dialog("Allow Owner game installer to access your camera?"), "notification-dialog-not-identified"),
            (self.notification_dialog(button="permission_allow_button"), "notification-denial-unavailable"),
        ):
            with self.subTest(reason=reason), patch.object(phone, "ui", return_value=dialog), patch.object(phone, "shell") as shell:
                with self.assertRaisesRegex(LAB.Failure, reason):
                    phone.dismiss_notification_permission()
                shell.assert_not_called()

    def test_notification_dialog_requires_observed_dismissal(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.owned_installer = True
        with patch.object(phone, "ui", return_value=self.notification_dialog()), patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "notification-dialog-not-dismissed"):
                phone.dismiss_notification_permission()
        self.assertEqual(shell.call_count, 1)

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
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_SLEEP", label="device-display-sleep")

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

    def test_unknown_install_outcome_cannot_claim_cleanup_or_delete(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.install_attempted = True
        with patch.object(phone, "occupied", return_value=True) as occupied, patch.object(phone, "command") as command, patch.object(phone, "shell") as shell:
            with self.assertRaisesRegex(LAB.Failure, "cleanup-package-ownership-unverified"):
                phone.cleanup()
        occupied.assert_called_once_with(LAB.PACKAGE)
        command.assert_not_called()
        shell.assert_called_once_with("input", "keyevent", "KEYCODE_SLEEP", label="device-display-sleep")

    def test_unknown_install_outcome_only_claims_absence_after_readback(self):
        phone = LAB.Phone("synthetic-private-selector", 1)
        phone.install_attempted = True
        with patch.object(phone, "occupied", return_value=False) as occupied, patch.object(phone, "command") as command, patch.object(phone, "shell"):
            self.assertEqual(phone.cleanup(), "verified-absent")
        self.assertEqual([call.args[0] for call in occupied.call_args_list], [LAB.PACKAGE, LAB.GAME])
        command.assert_not_called()

    def test_private_diagnostics_persist_and_operation_and_cleanup_failures_stay_separate(self):
        output = io.StringIO()
        temporary_artifacts = []

        def fail_operation(phone, config, temporary, passed):
            temporary_artifacts.append(temporary)
            LAB.set_phase("pre-install-storage")
            LAB.run(["not-executed", "synthetic-argv-secret"], stdin=b"synthetic-stdin-secret", label="device-storage-volume-free")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(LAB, "ROOT", root),
                patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "synthetic-selector-not-for-publication"}),
                patch.object(LAB, "read_context", return_value={}),
                patch.object(LAB, "Phone") as phone,
                patch.object(LAB, "acceptance", side_effect=fail_operation),
                patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"synthetic-private-stdout", b"synthetic-private-stderr")),
                redirect_stdout(output),
            ):
                phone.return_value.cleanup.side_effect = LAB.Failure("device-display-sleep")
                self.assertEqual(LAB.main([]), 1)
            self.assertFalse(temporary_artifacts[0].exists())
            logs = list((root / "work/coordination/installer-update-acceptance").glob("run-*"))
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].stat().st_mode & 0o777, 0o700)
            files = list(logs[0].iterdir())
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in files))
            self.assertEqual(next(logs[0].glob("*.stderr.log")).read_bytes(), b"synthetic-private-stderr")
            metadata = json.loads(next(logs[0].glob("*.json")).read_text())
            self.assertEqual(metadata, {"phase": "pre-install-storage", "category": "device-storage-volume-free", "returncode": 1, "outcome": "returned"})
            retained = b"".join(path.read_bytes() for path in files)
            self.assertNotIn(b"synthetic-argv-secret", retained)
            self.assertNotIn(b"synthetic-stdin-secret", retained)
        result = output.getvalue()
        self.assertIn("FAIL check-for-updates phase=pre-install-storage reason=device-storage-volume-free", result)
        self.assertIn("FAIL cleanup phase=cleanup reason=device-display-sleep", result)
        self.assertNotIn("PASS cleanup", result)
        for private in ("synthetic-private", "synthetic-argv-secret", "synthetic-stdin-secret", "synthetic-selector-not-for-publication", directory):
            self.assertNotIn(private, result)

    def test_subprocess_error_does_not_publish_argv_stderr_or_identifiers(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"LAB_DEVICE_SERIAL": "not-for-publication"}),
            patch.object(LAB, "read_context", side_effect=RuntimeError("private-path-not-for-publication")),
            patch.object(LAB, "PrivateDiagnostics"),
            redirect_stdout(output),
        ):
            self.assertEqual(LAB.main([]), 1)
        self.assertNotIn("not-for-publication", output.getvalue())
        self.assertIn("unexpected-local-error", output.getvalue())


if __name__ == "__main__":
    unittest.main()
