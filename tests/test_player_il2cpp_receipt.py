from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from player_il2cpp_receipt import CaptureError, verify_poststrip  # noqa: E402


class PlayerIl2CppReceiptTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(__file__).resolve().parent / ".test-tmp"
        self.scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.scratch)
        self.root = Path(self.temp.name)
        self.project = self.root / "unity-project"
        self.project.mkdir()
        self.work = self.root / "lab-work"
        self.work.mkdir()
        self.request = "20261020T203424.928531Z-0123456789abcdef"
        self.source = "a" * 40
        self.input_id = "b" * 64
        self.guid = "c" * 32
        data = b"post-strip-managed-dll"
        snap = self.work / "lab-build/player-linker-inputs" / self.request / "poststrip/Assembly-CSharp.dll"
        snap.parent.mkdir(parents=True)
        snap.write_bytes(data)
        self.input_dir = self.project / "Temp/StagingArea/Data/Managed"
        self.input_dir.mkdir(parents=True)
        self.apk = self.work / "player.apk"
        self.apk.write_bytes(b"same-build-apk")
        self.capture = {
            "schema": "ror2lab-il2cpp-invocation-capture-candidate-v1",
            "capture_flag": "captureIl2CppInvocation",
            "evidence_kind": "UnityLogWriter pre-launch rendered command line; not argv[]",
            "request_id": self.request,
            "source_commit": self.source,
            "input_id": self.input_id,
            "build_report_guid": self.guid,
            "target": "Android",
            "build_report_result": "Unknown",
            "output_path": "fixture.apk",
            "il2cpp_command_line_log": f"Invoking il2cpp with arguments: --convert-in-graph --directory={self.input_dir}",
            "il2cpp_input_directory": "Temp/StagingArea/Data/Managed",
            "files": [
                {
                    "path": "Assembly-CSharp.dll",
                    "snapshot_path": f"lab-build/player-linker-inputs/{self.request}/poststrip/Assembly-CSharp.dll",
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            ],
        }
        self.prestrip = {
            "request_id": self.request,
            "source_commit": self.source,
            "input_id": self.input_id,
            "target": "Android",
            "build_report_guid": self.guid,
        }
        self.result = {
            "success": True,
            "errors": 0,
            "request_id": self.request,
            "input_id": self.input_id,
            "source": {"commit": self.source},
            "build_report_guid": self.guid,
            "apk": str(self.apk),
            "apk_sha256": hashlib.sha256(b"same-build-apk").hexdigest(),
        }

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        return verify_poststrip(
            self.capture,
            prestrip=self.prestrip,
            work_root=self.work,
            project_root=self.project,
            result=self.result,
            request_id=self.request,
            source_commit=self.source,
            input_id=self.input_id,
        )

    def test_same_report_request_inventory_binds_but_does_not_claim_argv_vector(self):
        verified = self.verify()
        self.assertEqual(verified["build_report_guid"], self.guid)
        self.assertTrue(verified["il2cpp_snapshot_to_apk_build_binding"])
        self.assertFalse(verified["stage_to_apk_binding"])
        self.assertFalse(verified["il2cpp_argv_vector_binding"])

    def test_does_not_require_callback_report_result_to_be_succeeded(self):
        self.capture["build_report_result"] = "Unknown"
        self.assertEqual(self.verify()["build_report_guid"], self.guid)

    def test_rejects_old_linker_receipt_without_same_report_guid(self):
        self.prestrip = dict(self.prestrip, build_report_guid="d" * 32)
        with self.assertRaisesRegex(CaptureError, "different Unity build report"):
            self.verify()

    def test_prestrip_identity_requires_every_field(self):
        expected = {
            "request_id": self.request,
            "source_commit": self.source,
            "input_id": self.input_id,
            "target": "Android",
        }
        for field, value in expected.items():
            with self.subTest(field=field, mutant="missing"):
                self.prestrip.pop(field)
                with self.assertRaisesRegex(CaptureError, "another request/source/input/target"):
                    self.verify()
                self.prestrip[field] = value
            with self.subTest(field=field, mutant="mismatch"):
                self.prestrip[field] = "StandaloneOSX" if field == "target" else "foreign"
                with self.assertRaisesRegex(CaptureError, "another request/source/input/target"):
                    self.verify()
                self.prestrip[field] = value

    def test_requires_independent_capture_opt_in(self):
        self.capture.pop("capture_flag")
        with self.assertRaisesRegex(CaptureError, "independent IL2CPP capture opt-in"):
            self.verify()

    def test_rejects_request_source_or_input_drift(self):
        original = self.capture["request_id"]
        self.capture["request_id"] = "other-request"
        with self.assertRaisesRegex(CaptureError, "different request/source/input"):
            self.verify()
        self.capture["request_id"] = original
        self.capture["source_commit"] = "f" * 40
        with self.assertRaisesRegex(CaptureError, "different request/source/input"):
            self.verify()
        self.capture["source_commit"] = self.source
        self.capture["input_id"] = "e" * 64
        with self.assertRaisesRegex(CaptureError, "different request/source/input"):
            self.verify()

    def test_rejects_failed_build_even_with_matching_hashes(self):
        self.result["success"] = False
        with self.assertRaisesRegex(CaptureError, "unsuccessful player build"):
            self.verify()

    def test_rejects_mismatched_final_report_guid(self):
        self.result["build_report_guid"] = "d" * 32
        with self.assertRaisesRegex(CaptureError, "final build result report GUID"):
            self.verify()

    def test_rejects_absent_invocation_and_dll_rows(self):
        self.capture["files"] = []
        with self.assertRaisesRegex(CaptureError, "inventory is empty"):
            self.verify()

    def test_rejects_changed_snapshot(self):
        snap = self.work / self.capture["files"][0]["snapshot_path"]
        snap.write_bytes(b"tampered")
        with self.assertRaisesRegex(CaptureError, "bytes differ"):
            self.verify()

    def test_rejects_rendered_command_line_as_missing_or_argv_claim(self):
        self.capture["il2cpp_command_line_log"] = ""
        with self.assertRaisesRegex(CaptureError, "command-line log"):
            self.verify()
        self.capture["il2cpp_command_line_log"] = "Invoking il2cpp with arguments: --directory=/tmp/x"
        self.capture["evidence_kind"] = "exact argv vector"
        with self.assertRaisesRegex(CaptureError, "evidence kind"):
            self.verify()

    def test_rejects_symlink_snapshot(self):
        snap = self.work / self.capture["files"][0]["snapshot_path"]
        external = self.root / "outside.dll"
        external.write_bytes(snap.read_bytes())
        snap.unlink()
        snap.symlink_to(external)
        with self.assertRaisesRegex(CaptureError, "symbolic link"):
            self.verify()

    def test_rejects_symlink_roots(self):
        work_alias = self.root / "work-alias"
        project_alias = self.root / "project-alias"
        work_alias.symlink_to(self.work, target_is_directory=True)
        project_alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(CaptureError, "work root is a symbolic link"):
            verify_poststrip(
                self.capture,
                prestrip=self.prestrip,
                work_root=work_alias,
                project_root=self.project,
                result=self.result,
                request_id=self.request,
                source_commit=self.source,
                input_id=self.input_id,
            )
        with self.assertRaisesRegex(CaptureError, "project root is a symbolic link"):
            verify_poststrip(
                self.capture,
                prestrip=self.prestrip,
                work_root=self.work,
                project_root=project_alias,
                result=self.result,
                request_id=self.request,
                source_commit=self.source,
                input_id=self.input_id,
            )

    def test_rejects_logged_directory_drift_and_duplicate_directory_argument(self):
        other = self.project / "Temp/Other/Managed"
        other.mkdir(parents=True)
        self.capture["il2cpp_command_line_log"] = f"Invoking il2cpp with arguments: --directory={other}"
        with self.assertRaisesRegex(CaptureError, "does not resolve"):
            self.verify()
        self.capture["il2cpp_command_line_log"] = f"Invoking il2cpp with arguments: --directory={self.input_dir} --directory={other}"
        with self.assertRaisesRegex(CaptureError, "one unambiguous"):
            self.verify()
        self.capture["il2cpp_command_line_log"] = f"Invoking il2cpp with arguments: --directory --directory={self.input_dir}"
        with self.assertRaisesRegex(CaptureError, "one unambiguous"):
            self.verify()

    def test_project_and_work_roots_are_distinct_and_bound(self):
        verified = self.verify()
        self.assertNotEqual(self.project.resolve(), self.work.resolve())
        self.assertEqual(verified["il2cpp_input_directory"], "Temp/StagingArea/Data/Managed")
        self.assertTrue((self.work / verified["files"][0]["snapshot_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
