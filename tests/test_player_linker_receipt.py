from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
from player_linker_receipt import (
    LinkerCaptureError,
    bind_successful_apk,
    request_capture_fields,
    capture_cache_key,
    verify_capture,
)


class LinkerReceiptTests(unittest.TestCase):
    def test_public_code_build_handler_forwards_only_requested_capture(self):
        options = {"code_only": True}
        function = Mock()
        actions._whole_catalog_code_build(function, options, SimpleNamespace())
        function.assert_called_once_with(code_only=True)
        function.reset_mock()
        actions._whole_catalog_code_build(function, options, SimpleNamespace(capture_player_linker_inputs=True, debug_symbols=True))
        function.assert_called_once_with(code_only=True, capture_player_linker_inputs=True, android_symbols="debugging")
        function.reset_mock()
        actions._whole_catalog_code_build(
            function,
            options,
            SimpleNamespace(capture_player_linker_inputs=True, capture_il2cpp_invocation=True),
        )
        function.assert_called_once_with(code_only=True, capture_player_linker_inputs=True, capture_il2cpp_invocation=True)
        self.assertEqual(options, {"code_only": True})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.work = self.root / "work"
        self.input_dir = self.project / "Library" / "Bee" / "link-input"
        self.input_dir.mkdir(parents=True)
        self.work.mkdir()
        (self.input_dir / "Game.dll").write_bytes(b"game-a")
        (self.input_dir / "nested").mkdir()
        (self.input_dir / "nested" / "Plugin.dll").write_bytes(b"plugin-b")
        (self.input_dir / "readme.txt").write_text("not a managed assembly")
        self.apk = self.root / "player.apk"
        self.apk.write_bytes(b"apk-fixture")
        self.request_id = "audio-build-001"
        self.commit = "a" * 40
        self.input_id = "b" * 64
        self.capture = {
            "schema": "ror2lab-unitylinker-input-v1",
            "request_id": self.request_id,
            "source_commit": self.commit,
            "input_id": self.input_id,
            "target": "Android",
            "input_directory": "Library/Bee/link-input",
            "files": self.rows(),
        }
        self.result = {
            "success": True,
            "errors": 0,
            "request_id": self.request_id,
            "input_id": self.input_id,
            "source": {"commit": self.commit},
            "apk": str(self.apk),
            "apk_sha256": hashlib.sha256(self.apk.read_bytes()).hexdigest(),
        }

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        files = [self.input_dir / "Game.dll", self.input_dir / "nested" / "Plugin.dll"]
        rows = []
        for path in files:
            relative = path.relative_to(self.input_dir).as_posix()
            snapshot_path = f"lab-build/player-linker-inputs/{self.request_id}/assemblies/{relative}"
            snapshot = self.work / snapshot_path
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(path.read_bytes())
            rows.append(
                {
                    "role": "UnityLinkerInput",
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "snapshot_path": snapshot_path,
                }
            )
        return rows

    def verify(self, capture=None, **overrides):
        args = {
            "work_root": self.work,
            "request_id": self.request_id,
            "source_commit": self.commit,
            "input_id": self.input_id,
        }
        args.update(overrides)
        return verify_capture(capture or self.capture, **args)

    def test_binds_exact_directory_inventory_to_apk(self):
        sealed = bind_successful_apk(
            self.result,
            self.capture,
            work_root=self.work,
            request_id=self.request_id,
            source_commit=self.commit,
            input_id=self.input_id,
        )
        self.assertEqual(
            sealed["player_managed_linker_inputs"]["apk_sha256"],
            self.result["apk_sha256"],
        )
        self.assertEqual(len(sealed["player_managed_linker_inputs"]["files"]), 2)
        self.assertNotIn(str(self.root), str(sealed["player_managed_linker_inputs"]))

    def test_capture_request_is_absent_by_default_and_identity_bound_when_enabled(self):
        self.assertEqual(request_capture_fields(False, None, None), {})
        self.assertEqual(
            request_capture_fields(True, {"commit": self.commit}, self.input_id),
            {
                "capturePlayerLinkerInputs": True,
                "captureIl2CppInvocation": False,
                "sourceCommit": self.commit,
                "inputId": self.input_id,
            },
        )
        self.assertTrue(
            request_capture_fields(
                True,
                {"commit": self.commit},
                self.input_id,
                capture_il2cpp_invocation=True,
            )["captureIl2CppInvocation"]
        )
        with self.assertRaises(LinkerCaptureError):
            request_capture_fields(True, None, self.input_id)
        with self.assertRaisesRegex(LinkerCaptureError, "requires the pre-strip linker capture"):
            request_capture_fields(False, None, None, capture_il2cpp_invocation=True)

    def test_refuses_request_source_and_input_mismatch(self):
        for key, value in (
            ("request_id", "other"),
            ("source_commit", "c" * 40),
            ("input_id", "d" * 64),
        ):
            changed = dict(self.capture, **{key: value})
            with self.subTest(key=key), self.assertRaises(LinkerCaptureError):
                self.verify(changed)

    def test_refuses_wrong_target_empty_and_duplicate_inventory(self):
        for changed in (
            dict(self.capture, target="iOS"),
            dict(self.capture, files=[]),
            dict(self.capture, files=self.capture["files"] * 2),
        ):
            with self.assertRaises(LinkerCaptureError):
                self.verify(changed)

    def test_frozen_snapshot_survives_library_drift_and_refuses_snapshot_drift(self):
        (self.input_dir / "Game.dll").write_bytes(b"drift")
        self.verify()
        snapshot = self.work / self.capture["files"][0]["snapshot_path"]
        snapshot.write_bytes(b"tampered")
        with self.assertRaises(LinkerCaptureError):
            self.verify()

    def test_refuses_relative_path_alias_escape_and_external_directory(self):
        for bad_path in (
            "../outside.dll",
            "nested/../Game.dll",
            "/tmp/Game.dll",
            "nested\\Plugin.dll",
        ):
            changed = dict(
                self.capture,
                files=[
                    dict(self.capture["files"][0], path=bad_path),
                    self.capture["files"][1],
                ],
            )
            with self.subTest(path=bad_path), self.assertRaises(LinkerCaptureError):
                self.verify(changed)
        with self.assertRaises(LinkerCaptureError):
            self.verify(dict(self.capture, input_directory="../outside"))

    def test_refuses_symlinked_snapshot(self):
        external = self.root / "external.dll"
        external.write_bytes(b"elsewhere")
        snapshot = self.work / self.capture["files"][0]["snapshot_path"]
        snapshot.unlink()
        snapshot.symlink_to(external)
        with self.assertRaises(LinkerCaptureError):
            self.verify()

    def test_refuses_failed_or_drifted_apk_receipt(self):
        failed = dict(self.result, success=False)
        with self.assertRaises(LinkerCaptureError):
            bind_successful_apk(
                failed,
                self.capture,
                work_root=self.work,
                request_id=self.request_id,
                source_commit=self.commit,
                input_id=self.input_id,
            )
        changed = dict(self.result, apk_sha256="0" * 64)
        with self.assertRaises(LinkerCaptureError):
            bind_successful_apk(
                changed,
                self.capture,
                work_root=self.work,
                request_id=self.request_id,
                source_commit=self.commit,
                input_id=self.input_id,
            )

    def test_optin_receipt_cache_namespace_is_unique_and_request_bound(self):
        first = capture_cache_key("buildkey", self.request_id)
        second = capture_cache_key("buildkey", "audio-build-002")
        self.assertEqual(first, "buildkey-linker-audio-build-001")
        self.assertNotEqual(first, second)
        for malformed in ("../escape", "bad\\path", ""):
            with self.subTest(key=malformed), self.assertRaises(LinkerCaptureError):
                capture_cache_key(malformed, self.request_id)
        with self.assertRaises(LinkerCaptureError):
            capture_cache_key("buildkey", "../other-request")


if __name__ == "__main__":
    unittest.main()
