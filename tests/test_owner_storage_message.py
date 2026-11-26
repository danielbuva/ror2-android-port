"""Actual Android-free import storage guidance; no storage policy changes."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageMessageTests(unittest.TestCase):
    def test_import_guidance_reports_required_available_and_scope(self):
        java = shutil.which("java")
        if not java:
            self.skipTest("Java runtime absent")
        compiler = shutil.which("javac")
        command = [compiler] if compiler else [java, "com.sun.tools.javac.Main"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            harness = root / "Storage.java"
            harness.write_text("""import dev.ror2lab.phonebuildhostfixture.OwnerInputImport;
public class Storage {public static void main(String[] args){String text=OwnerInputImport.storageMessage(300,100);
for(String expected:new String[]{"need 300 bytes","available 100 bytes","Original inputs and profiles are not deleted by this refusal","Android installation capacity is separate","retry"})
if(!text.contains(expected))throw new AssertionError(expected);}}
""")
            result = subprocess.run(
                [*command, "-d", str(root), str(ROOT / "tools/phone-build/managed-host/OwnerInputImport.java"), str(harness)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([java, "-cp", str(root), "Storage"], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
