"""Portable contracts for selecting a diagnostic APK from its owned receipt.

Set PORTING_LAB_SOURCE_ROOT only when exercising an unapplied candidate tree;
normal repository runs use the public scripts/lab sources.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("PORTING_LAB_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
LAB = ROOT / "scripts" / "lab"


@contextmanager
def candidate_modules():
    names = ("installed_attempt", "session_cleanup_check")
    saved = {name: sys.modules.get(name) for name in names}
    sys.path.insert(0, str(LAB))
    try:
        for name in names:
            sys.modules.pop(name, None)
        attempt = importlib.import_module("installed_attempt")
        spec = importlib.util.spec_from_file_location("session_cleanup_check", LAB / "session_cleanup_check.py")
        cleanup = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules["session_cleanup_check"] = cleanup
        spec.loader.exec_module(cleanup)
        yield attempt, cleanup
    finally:
        sys.path.remove(str(LAB))
        for name in names:
            sys.modules.pop(name, None)
            if saved[name] is not None:
                sys.modules[name] = saved[name]


def fake_unitypy(payloads):
    objects = []
    for payload in payloads:
        obj = types.SimpleNamespace(
            type=types.SimpleNamespace(name="TextAsset"),
            read=lambda payload=payload: types.SimpleNamespace(m_Name="MovementBatchProbe", m_Script=payload),
        )
        objects.append(obj)
    return lambda _: types.SimpleNamespace(objects=objects)


class DeviceFixture:
    serial = "fixture-serial"
    settings = {"storage_mode": "internal"}

    def __init__(self, receipt, evidence, owned_error=None):
        self.receipt = receipt
        self.evidence = evidence
        self.owned_error = owned_error
        self.calls = []

    def owned(self):
        self.calls.append(("owned",))
        if self.owned_error:
            raise self.owned_error
        return self.receipt

    def storage(self):
        self.calls.append(("storage",))
        return {"mode": "internal"}

    def read_receipt(self, _):
        self.calls.append(("read_receipt",))
        return {"persistentDataPath": "/fixture/Android/data/dev.ror2lab.arm64/files"}

    def evidence_directory(self, *parts):
        return self.evidence.joinpath(*parts)

    def cmd(self, *args):
        self.calls.append(("cmd", *args))

    def launch(self):
        self.calls.append(("launch",))
        return {"pid": 31415}

    def display(self, awake):
        self.calls.append(("display", awake))
        return not awake

    def sh(self, *args, **kwargs):
        self.calls.append(("sh", *args))
        return ""


class OwnedApkDiagnosticBindingTests(unittest.TestCase):
    def test_explicit_cleanup_uses_receipt_without_build_pointer_and_pushes_embedded_attempt(self):
        with candidate_modules() as (attempt, cleanup), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "receipt.apk"
            apk.write_bytes(b"receipt-selected APK")
            digest = hashlib.sha256(apk.read_bytes()).hexdigest()
            receipt = {
                "apk": str(apk),
                "apk_sha256": digest,
                "storage": {"mode": "internal"},
                "package_path": "package:/data/app/fixture/base.apk",
            }
            device = DeviceFixture(receipt, root / "evidence")
            device.evidence.mkdir()
            loader = fake_unitypy([json.dumps({"attempt": "receipt-attempt"}).encode()])
            real_attempt_reader = attempt.attempt_from_installed

            with (
                patch.object(cleanup, "SessionCleanupDevice", return_value=device),
                patch.object(cleanup, "WORK", root / "work"),
                patch.object(cleanup, "read", side_effect=AssertionError("must not read current-build.json")),
                patch.object(cleanup, "attempt_from_installed", side_effect=lambda installed: real_attempt_reader(installed, loader=loader)),
                patch.object(cleanup, "_remote_path_state", return_value="absent"),
                patch.object(cleanup, "now", return_value="fixture-run"),
            ):
                # The fake display intentionally refuses after launch. This proves
                # the explicit flow reached push/launch from the receipt path.
                with self.assertRaisesRegex(RuntimeError, "display cannot be awakened"):
                    cleanup.check_session_cleanup(ending="abandon", expected_apk_sha256=digest)

            pushes = [call for call in device.calls if call[:2] == ("cmd", "push")]
            self.assertEqual(len(pushes), 1)
            selector = json.loads(Path(pushes[0][2]).read_text())
            self.assertEqual(selector["attempt"], "receipt-attempt")
            self.assertIn(("launch",), device.calls)

    def test_bad_receipt_and_wrong_explicit_hash_refuse_before_attempt_or_launch(self):
        with candidate_modules() as (_, cleanup), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = (
                ({"storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk"}, "b" * 64, "lacks a valid APK SHA-256"),
                (
                    {"apk_sha256": "c" * 64, "storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk"},
                    "d" * 64,
                    "does not match --expected-apk-sha256",
                ),
            )
            for index, (receipt, expected, error) in enumerate(cases):
                with self.subTest(error=error):
                    device = DeviceFixture(receipt, root / f"evidence-{index}")
                    device.evidence.mkdir()
                    with (
                        patch.object(cleanup, "SessionCleanupDevice", return_value=device),
                        patch.object(cleanup, "WORK", root / f"work-{index}"),
                        patch.object(cleanup, "attempt_from_installed", side_effect=AssertionError("must refuse first")),
                    ):
                        with self.assertRaisesRegex(RuntimeError, error):
                            cleanup.check_session_cleanup(ending="abandon", expected_apk_sha256=expected)
                    self.assertFalse(any(call[0] in ("launch", "cmd", "read_receipt") for call in device.calls))

    def test_owned_receipt_failure_and_malformed_cli_hash_refuse_before_device_work(self):
        with candidate_modules() as (_, cleanup), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = DeviceFixture(None, root / "evidence", owned_error=RuntimeError("ownership receipt unavailable"))
            with patch.object(cleanup, "SessionCleanupDevice", return_value=device), patch.object(cleanup, "WORK", root / "work"):
                with self.assertRaisesRegex(RuntimeError, "ownership receipt unavailable"):
                    cleanup.check_session_cleanup(ending="abandon", expected_apk_sha256="b" * 64)
            self.assertEqual(device.calls, [("owned",)])

            with patch.object(cleanup, "SessionCleanupDevice", side_effect=AssertionError("must validate before device")):
                with self.assertRaises(ValueError):
                    cleanup.check_session_cleanup(ending="abandon", expected_apk_sha256="B" * 64)

    def test_default_cleanup_still_uses_current_build_gate(self):
        with candidate_modules() as (_, cleanup), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = {"apk_sha256": "c" * 64, "storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk"}
            device = DeviceFixture(receipt, root / "evidence")
            build_reads = []

            def read(path):
                build_reads.append(Path(path).name)
                return {"success": True, "apk": "fixture.apk", "apk_sha256": "d" * 64}

            with (
                patch.object(cleanup, "SessionCleanupDevice", return_value=device),
                patch.object(cleanup, "WORK", root / "work"),
                patch.object(cleanup, "read", side_effect=read),
                patch.object(cleanup, "sha", return_value="d" * 64),
                patch.object(cleanup, "attempt_from_installed", side_effect=AssertionError("must refuse first")),
            ):
                with self.assertRaisesRegex(RuntimeError, "supply --expected-apk-sha256"):
                    cleanup.check_session_cleanup(ending="abandon")
            self.assertEqual(build_reads, ["current-build.json"])
            self.assertFalse(any(call[0] in ("launch", "cmd", "read_receipt") for call in device.calls))

    def test_receipt_byte_drift_and_duplicate_embedded_attempts_stop_before_selector_launch(self):
        with candidate_modules() as (attempt, cleanup), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = b"receipt-owned APK bytes"
            cases = (
                ("drift", original, fake_unitypy([json.dumps({"attempt": "x"}).encode()]), "bytes changed"),
                (
                    "ambiguous",
                    original,
                    fake_unitypy([json.dumps({"attempt": "x"}).encode(), json.dumps({"attempt": "y"}).encode()]),
                    "exactly one MovementBatchProbe",
                ),
            )
            for name, bytes_value, loader, error in cases:
                with self.subTest(case=name):
                    apk = root / (name + ".apk")
                    apk.write_bytes(original)
                    digest = hashlib.sha256(original).hexdigest()
                    receipt = {"apk": str(apk), "apk_sha256": digest, "storage": {"mode": "internal"}, "package_path": "package:/data/app/fixture/base.apk"}
                    if name == "drift":
                        apk.write_bytes(b"replacement bytes")
                    device = DeviceFixture(receipt, root / ("evidence-" + name))
                    device.evidence.mkdir()
                    reader = attempt.attempt_from_installed
                    with (
                        patch.object(cleanup, "SessionCleanupDevice", return_value=device),
                        patch.object(cleanup, "WORK", root / ("work-" + name)),
                        patch.object(cleanup, "attempt_from_installed", side_effect=lambda installed: reader(installed, loader=loader)),
                    ):
                        with self.assertRaisesRegex(RuntimeError, error):
                            cleanup.check_session_cleanup(ending="abandon", expected_apk_sha256=digest)
                    self.assertFalse(any(call[0] in ("cmd", "launch", "read_receipt") for call in device.calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
