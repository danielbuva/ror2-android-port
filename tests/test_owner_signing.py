"""Durable owner-key lifecycle with authored APK/tool doubles only."""

import importlib.util
import hashlib
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


class OwnerAssemblyTests(unittest.TestCase):
    def test_produced_code_requires_burst_instead_of_replaying_it(self):
        with self.assertRaisesRegex(ValueError, "Burst"):
            OWNER.code_sources({"code": {name: "not read" for name in OWNER.CODE_ENTRIES if "burst" not in name}})

    def test_assembly_uses_produced_code_without_target_code_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            targets, frontend, produced = (root / name for name in ("targets", "frontend", "produced"))
            for directory in (targets, frontend, produced):
                directory.mkdir()
            profile = {"targets": []}
            for name in ("apk/AndroidManifest.xml", "apk/classes.dex", "apk/assets/authored.txt", "payload/authored.bundle"):
                path = targets / name
                path.parent.mkdir(parents=True, exist_ok=True)
                data = ("independent content " + name).encode()
                path.write_bytes(data)
                profile["targets"].append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            code = {}
            for i, name in enumerate(sorted(OWNER.CODE_ENTRIES)):
                data = ("independent produced output " + name).encode()
                path = produced / str(i)
                path.write_bytes(data)
                code[name] = str(path)
                # Comparison rows exist, but no replay code is available to read.
                profile["targets"].append({"path": "apk/" + name, "bytes": 1, "sha256": "0" * 64})
            for name in ("app.js", "controller.js", "style.css", "background.png"):
                (frontend / name).write_bytes(("independent frontend " + name).encode())
            for name in ("java", "android.jar", "d8.jar", "manifest.json"):
                (root / name).write_bytes(("independent tool " + name).encode())
            (root / "wire.py").write_text("# Authored empty helper witness\n")
            request = root / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "manifest": str(root / "manifest.json"),
                        "manifest_sha256": OWNER.PROFILE,
                        "targets": str(targets),
                        "frontend": str(frontend),
                        "java": str(root / "java"),
                        "android_jar": str(root / "android.jar"),
                        "d8_jar": str(root / "d8.jar"),
                        "wire_helper": str(root / "wire.py"),
                        "code": code,
                    }
                )
            )
            output = root / "output"

            def run(argv, **kwargs):
                argv = list(map(str, argv))
                if Path(argv[0]).name == "javac":
                    (Path(argv[argv.index("-d") + 1]) / "Authored.class").write_bytes(b"independent Java witness")
                else:
                    (Path(argv[argv.index("--output") + 1]) / "classes.dex").write_bytes(b"independent DEX witness")

            with (
                patch.object(OWNER.PACKET, "profile", return_value=(b"", profile)),
                patch.object(OWNER.MANIFEST, "patch", return_value=b"independent routed manifest"),
                patch.object(OWNER, "ART", OWNER.sha(frontend / "background.png")),
                patch.object(OWNER, "RESERVE", 0),
                patch.object(OWNER.subprocess, "run", side_effect=run),
            ):
                result = OWNER.build(request, output)
            self.assertTrue(result["success"])
            self.assertTrue(result["il2cpp_or_original_dex_changed"])
            self.assertEqual(result["original_entries_preserved"], 2)
            self.assertEqual(set(result["code_entries"]), OWNER.CODE_ENTRIES)
            with zipfile.ZipFile(output / "owner-unsigned.apk") as archive:
                for name, path in code.items():
                    self.assertEqual(archive.read(name), Path(path).read_bytes())
                self.assertEqual(archive.read("assets/authored.txt"), (targets / "apk/assets/authored.txt").read_bytes())
                self.assertEqual(archive.read("assets/owner-bootstrap/data/authored.bundle"), (targets / "payload/authored.bundle").read_bytes())


if __name__ == "__main__":
    unittest.main()
