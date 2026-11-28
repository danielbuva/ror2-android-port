"""Synthetic host contracts for the phone qualification driver, never device proof."""

import copy
import importlib.util
import io
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_alpha_packaging", ROOT / "scripts/lab-alpha-packaging.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
ACQUISITION = A.INSTALLER.module("tested_alpha_acquisition", ROOT / "scripts/lab/alpha_acquisition.py")


def bound(version=1, publisher=1, purpose="update", prior=None):
    receipt = {
        "application_id": A.INSTALLER.GAME,
        "version_code": version,
        "installed_readback_verified": True,
        "release": {"version_code": publisher},
        "purpose": purpose,
    }
    row = {"status": "signed", "publisher_version_code": publisher, "purpose": purpose}
    for number, (field, receipt_field) in enumerate(
        (
            ("apk_sha256", "sha256"),
            ("payload_sha256", "payload_sha256"),
            ("signer_sha256", "signer_sha256"),
            ("source_sha256", "source_sha256"),
            ("input_sha256", "input_sha256"),
            ("toolchain_sha256", "toolchain_sha256"),
        ),
        1,
    ):
        row[field] = receipt[receipt_field] = str(number) * 64
    ledger = {"schema": 1, "application_id": A.INSTALLER.GAME, "last_issued": version, "issues": copy.deepcopy(prior["issues"]) if prior else {}}
    ledger["issues"][str(version)] = row
    return receipt, ledger


class AlphaPackagingTests(unittest.TestCase):
    def test_acquisition_sleeps_displays_on_picker_failure(self):
        device = Mock(display_awakened=True)
        phone = Mock(thermal=Mock(device=device))
        with self.assertRaisesRegex(RuntimeError, "picker failed"), A.Phone.active_display(phone):
            self.assertEqual(device.display.call_args.args, (True,))
            raise RuntimeError("picker failed")
        self.assertEqual([call.args for call in device.display.call_args_list], [(True,), (False,)])

    def test_acquisition_publishes_one_use_control_and_waits_for_matching_ack(self):
        command = {"action": "cancel", "id": "current"}
        phone = Mock(timeout=10)
        phone.read.side_effect = [{"action": "cancel", "id": "old"}, command]
        with patch.object(ACQUISITION.secrets, "token_hex", return_value="current"), patch.object(ACQUISITION.time, "sleep"):
            ACQUISITION.dispatch_control(phone, A.INSTALLER, "cancel")

        phone.put.assert_called_once_with("acquisition-control.json.pending", A.INSTALLER.encoded(command))
        phone.shell.assert_called_once_with(
            "run-as",
            A.INSTALLER.PACKAGE,
            "mv",
            "files/owner-input/acquisition-control.json.pending",
            "files/owner-input/acquisition-control.json",
            label="acquisition-publish-control",
        )
        self.assertEqual(phone.read.call_count, 2)
        phone.tap.assert_not_called()

    def test_acquisition_creates_nested_directories_before_adb_sync(self):
        phone = Mock()
        source = Path("owned game files")
        target = "/sdcard/owned-fixture/Supported"
        paths = ["Root.exe", "Game Data/Nested/first", "Game Data/Nested/second", "Game Data/Other"]
        ACQUISITION.stage_folder(phone, source, paths, target)

        mkdir, push = phone.command.call_args_list
        self.assertEqual(mkdir.args[0], "shell")
        self.assertEqual(shlex.split(mkdir.args[1]), ["mkdir", "-p", target, f"{target}/Game Data", f"{target}/Game Data/Nested"])
        self.assertEqual(push.args, ("push", source / "Game Data", source / "Root.exe", target + "/"))

    def test_acquisition_hash_listing_preserves_manifest_relative_names(self):
        digest = "a" * 64
        valid = f"{digest}  ./Dir with spaces/Game Data\n".encode()
        self.assertEqual(ACQUISITION.hash_listing(valid), {"Dir with spaces/Game Data": digest})
        for corrupt in (valid * 2, valid.replace(b"./", b"/"), b"warning"):
            with self.assertRaisesRegex(ValueError, "acquisition-hash-listing-invalid"):
                ACQUISITION.hash_listing(corrupt)

    def test_acquisition_requires_the_persisted_document_and_source_kind(self):
        folder = "Download/Lab/Supported"
        provider = "content://com.android.externalstorage.documents"
        tree = f'<map><string name="source_kind">tree</string><string name="source_uri">{provider}/tree/primary%3ADownload%2FLab%2FSupported</string></map>'
        archive = tree.replace(">tree<", ">zip<").replace("/tree/", "/document/").replace("Supported<", "Archive%2FSupported.zip<")
        self.assertTrue(ACQUISITION.selected_document(tree, "tree", folder))
        self.assertTrue(ACQUISITION.selected_document(archive, "zip", "Download/Lab/Archive/Supported.zip"))
        self.assertFalse(ACQUISITION.selected_document(tree, "zip", folder))
        for unexpected in ("dev.ror2lab.installertest.acquisition", "com.android.providers.downloads.documents"):
            self.assertFalse(ACQUISITION.selected_document(tree.replace(ACQUISITION.EXTERNAL_PROVIDER, unexpected), "tree", folder))
        self.assertFalse(ACQUISITION.selected_document(tree.replace("primary", "other"), "tree", folder))
        tool_grant = tree.replace('"source_uri"', '"tool_source_uri"').replace("Supported", "Tools")
        self.assertTrue(ACQUISITION.selected_document(tool_grant, "tree", "Download/Lab/Tools", tools=True))
        self.assertFalse(ACQUISITION.selected_document(tree, "tree", folder, tools=True))

    def test_acquisition_picks_exact_enabled_document_in_focused_package(self):
        package = ACQUISITION.DOCUMENTS[0]
        tree = ET.fromstring(
            f'<hierarchy><node package="{package}">'
            f'<node package="{package}" resource-id="{package}:id/title" text="Supported.zip.bak" enabled="true" />'
            '<node package="other" resource-id="android:id/title" text="Supported.zip" enabled="true" />'
            f'<node package="{package}" resource-id="android:id/title" text="Supported.zip" enabled="true" />'
            "</node></hierarchy>"
        )
        self.assertIs(ACQUISITION.picker_node(tree, "Supported.zip", ids=("title",)), list(tree.iter("node"))[-1])

    def test_acquisition_waits_for_mid_copy_before_cancellation(self):
        acquisition = ACQUISITION.Acquisition.__new__(ACQUISITION.Acquisition)
        acquisition.require = A.require
        phone = Mock(timeout=10)
        partial = {"state": "IMPORTING", "completed": 500, "total": 1000}
        phone.read.side_effect = [
            {"state": "VALIDATING", "completed": 500, "total": 1000},
            {"state": "IMPORTING", "completed": 0, "total": 1000},
            {"state": "IMPORTING", "completed": 1000, "total": 1000},
            partial,
        ]
        with patch.object(ACQUISITION.time, "sleep"):
            self.assertEqual(acquisition.wait_import(phone, "COPYING"), partial)
        self.assertEqual(phone.read.call_count, 4)

    def test_thermal_cancellation_refuses_more_acceptance_commands(self):
        phone = A.Phone("synthetic-test-device", 20)
        phone.thermal = Mock()
        with patch.object(A.INSTALLER.Phone, "execute", return_value="available") as execute:
            phone.thermal.cancelled.is_set.return_value = True
            with self.assertRaisesRegex(A.INSTALLER.Failure, "alpha-packaging-thermal-cancellation"):
                phone.execute("example", label="test-command")
            execute.assert_not_called()
            phone.thermal = None
            self.assertEqual(phone.execute("example", label="cleanup-command"), "available")

    def test_display_is_acquired_before_launch_and_restored_after_failure(self):
        phone = A.Phone("synthetic-test-device", 20)
        calls = []
        device = Mock(display_awakened=False)

        def set_display(awake):
            calls.append(awake)
            device.display_awakened = awake
            return True

        class Thermal:
            def __init__(self, selected, *args):
                self.device = selected
                self.admission_battery = self.peak_cpu_gpu_celsius = self.time_above_80_seconds = self.error = None

            def cool(self):
                pass

            def start(self):
                pass

            def finish(self):
                calls.append("finish")

        def launch(**kwargs):
            calls.append("launch")
            self.assertTrue(device.display_awakened)

        device.display.side_effect = set_display
        with (
            patch("sys.path", [str(ROOT / "scripts/lab"), *A.sys.path]),
            patch("alpha_stability_batch._GameThermalOwner", Thermal),
            patch("device.Device", return_value=device),
            patch.object(A.INSTALLER, "DIAGNOSTICS", Mock(directory=ROOT)),
            patch.object(A.INSTALLER.Phone, "start", side_effect=launch),
            self.assertRaisesRegex(A.INSTALLER.Failure, "fixture failure"),
            phone.observe_thermal(),
        ):
            phone.start()
            phone.start(repeat_notification_denial=True)
            raise A.INSTALLER.Failure("fixture failure")

        self.assertEqual(calls, [True, "launch", "launch", False, "finish"])

    def test_installed_identity_and_complete_binding(self):
        receipt, ledger = bound()
        A.verify_issue(receipt, ledger, 1)
        for field in ("source_sha256", "input_sha256", "toolchain_sha256", "apk_sha256", "payload_sha256", "signer_sha256"):
            damaged = copy.deepcopy(ledger)
            damaged["issues"]["1"][field] = "a" * 64
            with self.subTest(field=field), self.assertRaises(A.INSTALLER.Failure):
                A.verify_issue(receipt, damaged, 1)

    def test_actual_installed_version_and_identity_refused(self):
        receipt, ledger = bound()
        for version in (0, 2, True):
            with self.subTest(version=version), self.assertRaises(A.INSTALLER.Failure):
                A.verify_issue(receipt, ledger, version)
        for value in (None, "dev.ror2lab.arm64"):
            modified = dict(receipt, application_id=value)
            with self.subTest(value=value), self.assertRaises(A.INSTALLER.Failure):
                A.verify_issue(modified, ledger, 1)

    def test_unbound_nonreadback_and_exhausted_refused(self):
        receipt, ledger = bound()
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(dict(receipt, installed_readback_verified=False), ledger, 1)
        modified = copy.deepcopy(ledger)
        modified["issues"]["1"]["status"] = "reserved"
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(receipt, modified, 1)
        exhausted, ledger = bound(2100000001)
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(exhausted, ledger, 2100000001)

    def test_forward_rollback_preserves_issuance_and_signer(self):
        first = bound()
        second = bound(2, 2, prior=first[1])
        rolled = bound(3, 1, "rollback", second[1])
        A.verify_issue(*second, 2, first)
        A.verify_issue(*rolled, 3, second)
        modified = copy.deepcopy(rolled)
        modified[1]["issues"].pop("1")
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(*modified, 3, second)
        modified = copy.deepcopy(rolled)
        modified[0]["signer_sha256"] = modified[1]["issues"]["3"]["signer_sha256"] = "a" * 64
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(*modified, 3, second)
        with self.assertRaises(A.INSTALLER.Failure):
            A.verify_issue(*second, 2, rolled)

    def test_no_raw_process_output_forwarded(self):
        valid = "\n".join("PASS " + case for case in A.IMPORT_CASES).encode() + b"\n"
        self.assertEqual(A.parse_import_output(valid), A.IMPORT_CASES)
        for output in (b"", valid + b"unexpected-private-output\n", valid.replace(b"PASS", b"FAIL", 1), valid + valid):
            with self.subTest(output_length=len(output)), self.assertRaisesRegex(A.INSTALLER.Failure, "android-importer-contract-failed"):
                A.parse_import_output(output)

    def test_absent_device_refuses_before_context_or_cleanup(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(A.INSTALLER, "read_context") as context,
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(A.main([]), 1)
        context.assert_not_called()
        self.assertIn("LAB_DEVICE_SERIAL-required", output.getvalue())
        self.assertNotIn("PASS", output.getvalue())

    def test_pending_prompt_requirement_reaches_installer_owner(self):
        receipt, ledger = bound()
        phone = object.__new__(A.Phone)
        phone.packaging_history = []
        with (
            patch.object(A.INSTALLER.Phone, "installed", return_value=receipt) as installed,
            patch.object(phone, "read", return_value=ledger),
            patch.object(phone, "shell", return_value=b"versionCode=1"),
        ):
            self.assertEqual(phone.installed(1, require_pending_prompt=True), receipt)
        installed.assert_called_once_with(1, None, require_pending_prompt=True)
        self.assertEqual(phone.packaging_history, [(receipt, ledger)])

    def test_prompt_mode_refuses_pregrant_before_context_or_device(self):
        with (
            patch.object(A.INSTALLER, "read_context") as context,
            patch.object(A, "Phone") as phone,
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(A.main(["--qualify-install-prompts", "--allow-test-installs"]), 1)
        context.assert_not_called()
        phone.assert_not_called()
        self.assertIn("FAIL install-prompt-mode-conflict", output.getvalue())

    def test_prompt_mode_delegates_and_accepts_only_explicit_prompt_cases(self):
        def accept(phone, config, temporary, passed, *, qualify_install_prompts, record_metrics):
            self.assertTrue(qualify_install_prompts)
            self.assertTrue(record_metrics)
            for case in A.INSTALLER.PROMPT_CASES:
                passed(case)

        with (
            patch.dict("os.environ", {"LAB_DEVICE_SERIAL": "synthetic-test-device"}),
            patch.object(A.INSTALLER, "PrivateDiagnostics") as diagnostics,
            patch.object(A.INSTALLER, "read_context", return_value={}),
            patch.object(A, "Phone") as phone,
            patch.object(A, "compile_import_harness", return_value=b"synthetic-dex"),
            patch.object(A.INSTALLER, "acceptance", side_effect=accept),
            patch.object(A, "check_packaging_history"),
            patch.object(A, "import_acceptance"),
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            evidence = Path("work/coordination/alpha-packaging-acceptance/run-test")
            diagnostics.return_value.directory = A.ROOT / evidence
            phone.return_value.cleanup.return_value = "verified-absent"
            phone.return_value.flow_metrics.report.return_value = {"stages": []}
            self.assertEqual(A.main(["--qualify-install-prompts"]), 0)
        phone.assert_called_once_with("synthetic-test-device", 1200, allow_test_installs=False)
        for case in A.INSTALLER.PROMPT_CASES:
            self.assertIn("PASS " + case, output.getvalue())
        self.assertIn("INFO alpha-packaging evidence=" + evidence.as_posix(), output.getvalue())
        phone.return_value.cleanup.assert_called_once_with()
        diagnostics.return_value.write.assert_called_once_with("phone-flow-metrics.json", b'{"stages":[]}\n')

    def test_cold_restart_checks_ledger_and_installed_hash(self):
        first = bound()
        second = bound(2, 2, prior=first[1])
        rolled = bound(3, 1, "rollback", second[1])

        class FakePhone:
            packaging_history = [first, second, rolled]

            def shell(self, *args, **kwargs):
                self.stopped = True

            def start(self, *, repeat_notification_denial=False):
                self.started = repeat_notification_denial

            def read(self, name):
                return rolled[1] if name.startswith("work/") else rolled[0]

            def package_hash(self, package):
                return rolled[0]["sha256"]

        phone = FakePhone()
        passed = []
        A.check_packaging_history(phone, passed.append)
        self.assertTrue(phone.stopped and phone.started)
        self.assertEqual(passed, list(A.PACKAGE_CASES))
        with patch.object(phone, "read", return_value=None), self.assertRaises(A.INSTALLER.Failure):
            A.check_packaging_history(phone, lambda case: None)

    def test_android_harness_is_same_actual_owner_source(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(A.INSTALLER, "HostTools") as tools:
            A.compile_import_harness({}, Path(folder))
        sources = tools.return_value.dex.call_args.args[0]
        self.assertIn(ROOT / "tools/phone-build/managed-host/OwnerInputImport.java", sources)
        self.assertIn(ROOT / "tests/fixtures/AlphaPackagingHarness.java", sources)

    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK unavailable: Java importer execution not qualified")
    def test_real_java_importer_all_synthetic_contracts(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder).resolve()
            classes = directory / "classes"
            classes.mkdir()
            sources = [ROOT / "tools/phone-build/managed-host/OwnerInputImport.java", ROOT / "tests/fixtures/AlphaPackagingHarness.java"]
            compile_result = subprocess.run([shutil.which("javac"), "-d", str(classes), *map(str, sources)], capture_output=True, timeout=60)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr.decode())
            result = subprocess.run(
                [shutil.which("java"), "-cp", str(classes), "dev.ror2lab.phonebuildhostfixture.AlphaPackagingHarness", str(directory / "fixture"), "--host"],
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout.decode())
            self.assertEqual(A.parse_import_output(result.stdout), A.IMPORT_CASES)
            self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
