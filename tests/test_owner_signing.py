"""Durable owner-key lifecycle with authored APK/tool doubles only."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-apk/build_owner_apk.py"
SPEC = importlib.util.spec_from_file_location("owner_signing", PATH)
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class OwnerSigningTests(unittest.TestCase):
    def test_key_survives_two_builds_without_password_in_argv_or_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            apk = root / "unsigned.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"independent manifest witness")
                archive.writestr("assets/authored.txt", b"independent content witness")
            for name in ("java", "zipalign", "apksigner.jar"):
                (root / name).write_bytes(b"independent executable witness")
            request = root / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "unsigned": str(apk),
                        "java": str(root / "java"),
                        "zipalign": str(root / "zipalign"),
                        "apksigner_jar": str(root / "apksigner.jar"),
                        "key_directory": str(root / "keys"),
                    }
                )
            )
            calls = []

            def run(argv, **kwargs):
                secret = kwargs["env"]["ROR2_OWNER_SIGNING_PASSWORD"]
                self.assertTrue(secret)
                self.assertNotIn(secret, argv)
                calls.append(argv)
                if "-genkeypair" in argv:
                    Path(argv[argv.index("-keystore") + 1]).write_bytes(b"independent durable key witness")
                elif Path(argv[0]).name == "zipalign" and "-c" not in argv:
                    shutil.copyfile(argv[-2], argv[-1])
                elif "sign" in argv:
                    target = Path(argv[argv.index("--out") + 1])
                    shutil.copyfile(argv[-1], target)
                    with zipfile.ZipFile(target, "a") as archive:
                        archive.writestr("META-INF/OWNER.SF", b"authored signature witness")

            with patch.object(OWNER.subprocess, "run", side_effect=run):
                first = OWNER.sign(request, root / "first")
                key = (root / "keys/owner.p12").read_bytes()
                password = (root / "keys/password").read_text()
                second = OWNER.sign(request, root / "second")
            self.assertTrue(first["success"] and second["success"])
            self.assertTrue(first["new_owner_key"])
            self.assertFalse(second["new_owner_key"])
            self.assertEqual(sum("-genkeypair" in argv for argv in calls), 1)
            self.assertEqual((root / "keys/owner.p12").read_bytes(), key)
            self.assertEqual((root / "keys/password").read_text(), password)
            self.assertNotIn(password, (root / "first/result.json").read_text())
            self.assertEqual((root / "keys/owner.p12").stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / "keys/password").stat().st_mode & 0o777, 0o600)

    def test_failed_sign_keeps_key_and_failure_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for name in ("unsigned.apk", "java", "zipalign", "apksigner.jar"):
                (root / name).write_bytes(b"independent fixture")
            keys = root / "keys"
            keys.mkdir(mode=0o700)
            for name, content in (("owner.p12", b"durable key witness"), ("password", b"independent password")):
                path = keys / name
                path.write_bytes(content)
                path.chmod(0o600)
            request = root / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "unsigned": str(root / "unsigned.apk"),
                        "java": str(root / "java"),
                        "zipalign": str(root / "zipalign"),
                        "apksigner_jar": str(root / "apksigner.jar"),
                        "key_directory": str(keys),
                    }
                )
            )
            with patch.object(OWNER.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["independent tool"])):
                with self.assertRaises(subprocess.CalledProcessError):
                    OWNER.sign(request, root / "failed")
            self.assertEqual((keys / "owner.p12").read_bytes(), b"durable key witness")
            self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
