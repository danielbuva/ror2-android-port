"""Actual Java payload owner contracts, using authored streams and filesystem state."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OwnerPayloadStoreTests(unittest.TestCase):
    def test_complete_authored_preparation_update_recovery_and_containment(self):
        homes = [Path(os.environ.get("JAVA_HOME", "/absent")), Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK")]
        compiler = next((p / "bin/javac" for p in homes if (p / "bin/javac").is_file()), None)
        if compiler is None and shutil.which("javac"):
            compiler = Path(shutil.which("javac"))
        if compiler is None:
            self.skipTest("Java compiler absent")
        java = compiler.with_name("java")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            classes, data = base / "classes", base / "data"
            classes.mkdir()
            data.mkdir()
            compile_result = subprocess.run(
                [
                    str(compiler),
                    "-source",
                    "8",
                    "-target",
                    "8",
                    "-d",
                    str(classes),
                    str(ROOT / "tools/phone-build/owner-apk/PayloadStore.java"),
                    str(ROOT / "tests/fixtures/owner_payload/PayloadStoreHarness.java"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run = subprocess.run(
                [str(java), "-cp", str(classes), "dev.ror2owner.bootstrap.PayloadStoreHarness", str(data)], capture_output=True, text=True, timeout=60
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('"success":true', run.stdout)
