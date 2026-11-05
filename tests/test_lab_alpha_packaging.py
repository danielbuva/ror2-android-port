"""Synthetic host contracts for the phone qualification driver, never device proof."""

import copy
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tested_alpha_packaging", ROOT / "scripts/lab-alpha-packaging.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


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

    def test_cold_restart_checks_ledger_and_installed_hash(self):
        first = bound()
        second = bound(2, 2, prior=first[1])
        rolled = bound(3, 1, "rollback", second[1])

        class FakePhone:
            packaging_history = [first, second, rolled]

            def shell(self, *args, **kwargs):
                self.stopped = True

            def start(self):
                self.started = True

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
