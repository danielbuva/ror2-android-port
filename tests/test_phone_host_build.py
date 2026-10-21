"""A failed Android build must preserve evidence without publishing its key password."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/host/build_on_android.py"
SPEC = importlib.util.spec_from_file_location("phone_host_builder", SCRIPT)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class PhoneHostBuildTests(unittest.TestCase):
    def test_target_selection_uses_authored_manifest_and_refuses_downgrade_or_drift(self):
        source = SCRIPT.parent
        self.assertEqual(BUILDER.selected_manifest(source, 30).name, "AndroidManifest.xml")
        self.assertEqual(BUILDER.selected_manifest(source, 33).name, "AndroidManifestTarget33.xml")
        for value in (28, 29, 31, 32, 34, "33", True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Only"):
                BUILDER.selected_manifest(source, value)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "AndroidManifestTarget33.xml").write_bytes((SCRIPT.parent / "AndroidManifest.xml").read_bytes())
            with self.assertRaisesRegex(ValueError, "differs"):
                BUILDER.selected_manifest(source, 33)

    def test_first_failure_stops_signing_retains_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for name in ("NativeProbe.c", "HostProbeActivity.java", "AndroidManifest.xml", "build_on_android.py", "android.jar", "d8.jar", "apksigner.jar"):
                (source / name).write_text("fixture input")
            (source / "AndroidManifest.xml").write_bytes((SCRIPT.parent / "AndroidManifest.xml").read_bytes())
            output = root / "attempt"
            failure = subprocess.CompletedProcess([], 1, "", "authored link failure")
            with (
                patch.object(BUILDER, "__file__", str(source / "build_on_android.py")),
                patch.object(BUILDER.secrets, "token_urlsafe", return_value="private-password-sentinel"),
                patch.object(BUILDER.subprocess, "run", return_value=failure) as run,
            ):
                self.assertFalse(BUILDER.build(root, output))
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs["env"].get("ROR2_PHONE_SIGNING_PASSWORD"), None)
                with self.assertRaises(FileExistsError):
                    BUILDER.build(root, output)
            report = json.loads((output / "build-result.json").read_text())
            self.assertEqual(report["failure"], "native-compile-link exit 1")
            self.assertEqual(len(report["inputs"]), 7)
            self.assertFalse((output / "owner.p12").exists())
            for path in output.iterdir():
                self.assertNotIn("private-password-sentinel", path.read_text())

    def test_target33_failure_hashes_selected_manifest_without_overwriting_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for name in ("NativeProbe.c", "HostProbeActivity.java", "build_on_android.py", "android.jar", "d8.jar", "apksigner.jar"):
                (source / name).write_text("fixture input")
            original = (SCRIPT.parent / "AndroidManifest.xml").read_bytes()
            (source / "AndroidManifest.xml").write_bytes(original)
            (source / "AndroidManifestTarget33.xml").write_bytes((SCRIPT.parent / "AndroidManifestTarget33.xml").read_bytes())
            failure = subprocess.CompletedProcess([], 1, "", "authored link failure")
            with patch.object(BUILDER, "__file__", str(source / "build_on_android.py")), patch.object(BUILDER.subprocess, "run", return_value=failure):
                self.assertFalse(BUILDER.build(root, root / "attempt", 33))
            report = json.loads((root / "attempt/build-result.json").read_text())
            self.assertEqual(report["target_sdk"], 33)
            self.assertIn("AndroidManifestTarget33.xml", report["inputs"])
            self.assertNotIn("AndroidManifest.xml", report["inputs"])
            self.assertEqual((source / "AndroidManifest.xml").read_bytes(), original)

    def test_aapt_receives_required_basename_with_unchanged_selected_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for name in ("NativeProbe.c", "HostProbeActivity.java", "build_on_android.py", "android.jar", "d8.jar", "apksigner.jar"):
                (source / name).write_text("fixture input")
            selected = (SCRIPT.parent / "AndroidManifestTarget33.xml").read_bytes()
            (source / "AndroidManifestTarget33.xml").write_bytes(selected)

            def run(command, **kwargs):
                return subprocess.CompletedProcess(command, 1 if "package" in command else 0, "", "fixture packaging stop")

            output = root / "attempt"
            with patch.object(BUILDER, "__file__", str(source / "build_on_android.py")), patch.object(BUILDER.subprocess, "run", side_effect=run):
                self.assertFalse(BUILDER.build(root, output, 33))
            report = json.loads((output / "build-result.json").read_text())
            self.assertEqual(report["failure"], "aapt exit 1")
            command = report["commands"][-1]["args"]
            manifest = Path(command[command.index("-M") + 1])
            self.assertEqual(manifest.name, "AndroidManifest.xml")
            self.assertTrue(manifest.is_relative_to(output.resolve()))
            self.assertEqual(manifest.read_bytes(), selected)
            self.assertEqual((source / "AndroidManifestTarget33.xml").read_bytes(), selected)
