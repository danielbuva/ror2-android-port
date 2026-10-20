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
    def test_first_failure_stops_signing_retains_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for name in ("NativeProbe.c", "HostProbeActivity.java", "AndroidManifest.xml", "build_on_android.py", "android.jar", "d8.jar", "apksigner.jar"):
                (source / name).write_text("fixture input")
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
