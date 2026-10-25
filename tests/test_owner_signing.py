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
SDK = OWNER.module("owner_test_sdk", PATH.parent.parent / "accepted-output/sdk_package.py")


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
                readonly_keytool = root / "libkeytool.so"
                readonly_keytool.write_bytes(b"independent installed keytool witness")
                second_request = json.loads(request.read_text())
                second_request["keytool"] = str(readonly_keytool)
                request.write_text(json.dumps(second_request))
                second = OWNER.sign(request, root / "second")
            self.assertTrue(first["success"] and second["success"])
            self.assertTrue(first["new_owner_key"])
            self.assertFalse(second["new_owner_key"])
            self.assertEqual(sum("-genkeypair" in argv for argv in calls), 1)
            self.assertTrue(any(argv[0] == str(readonly_keytool) and "-list" in argv for argv in calls))
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
    def test_readiness_lists_all_missing_and_mismatched_inputs_without_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            targets = root / "not-produced-yet"
            code = {}
            rows = []
            for i, name in enumerate(sorted(OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES)):
                path = root / str(i)
                path.write_bytes(b"produced code")
                code[name] = str(path)
                rows.append({"path": "apk/" + name, "bytes": 1, "sha256": "0" * 64})
            native = "lib/arm64-v8a/libil2cpp.so"
            Path(code[native]).unlink()
            # A comparison file must never become a missing produced output's fallback.
            replay = targets / ("apk/" + native)
            replay.parent.mkdir(parents=True)
            replay.write_bytes(b"comparison code")
            for name in ("apk/assets/player", "payload/catalog", "payload/bundle", "payload/stale"):
                rows.append({"path": name, "bytes": 1, "sha256": "0" * 64})
            stale = targets / "payload/stale"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"wrong bytes")
            omitted = ["apk/META-INF/OWNER.RSA", "payload/bundle.manifest"]
            rows += [{"path": name} for name in omitted]
            request = {"manifest": "unused", "manifest_sha256": OWNER.PROFILE, "targets": str(targets), "code": code}
            with patch.object(OWNER.PACKET, "profile", return_value=(b"", {"targets": rows})):
                report = OWNER.check(request)
            self.assertFalse(report["assembly_ready"])
            self.assertEqual(report["selection"], "produced-code-and-sdk")
            self.assertEqual(
                set(report["blocked_entries"]),
                {"apk/" + native, "apk/assets/player", "payload/catalog", "payload/bundle", "payload/stale"},
            )
            self.assertEqual(report["omitted_entries"], omitted)
            self.assertEqual(len(report["code_comparison_required"]), len(OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES) - 1)
            self.assertEqual(next(r for r in report["entries"] if r["path"] == "payload/stale")["status"], "mismatch")
            self.assertFalse(report["source_provenance_verified"])
            self.assertFalse(report["device_qualified"])

    def test_missing_content_refuses_before_any_compiler_and_retains_full_report(self):
        self.check_assembly(OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES, missing_content=True)

    def test_produced_code_requires_burst_instead_of_replaying_it(self):
        with self.assertRaisesRegex(ValueError, "Burst"):
            OWNER.code_sources({"code": {name: "not read" for name in OWNER.CODE_ENTRIES if "burst" not in name}})

    def test_partial_sdk_and_unknown_entries_refuse_before_reading_paths(self):
        for entries in (
            OWNER.CODE_ENTRIES | {"classes2.dex"},
            (OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES) - {"resources.arsc"},
            OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES | {"assets/unknown"},
        ):
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, "complete SDK Android cohort"):
                OWNER.code_sources({"code": {name: "not read" for name in entries}})

    def test_assembly_uses_produced_code_without_target_code_files(self):
        self.check_assembly(OWNER.CODE_ENTRIES)

    def test_assembly_uses_complete_sdk_cohort_including_manifest_without_replay(self):
        self.check_assembly(OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES)

    def test_assembly_retains_no_code_replay_control(self):
        self.check_assembly(set())

    def test_produced_manifest_drift_refuses(self):
        self.check_assembly(OWNER.CODE_ENTRIES | SDK.SDK_ENTRIES, change_manifest=True)

    def check_assembly(self, entries, *, change_manifest=False, missing_content=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            targets, frontend, produced = (root / name for name in ("targets", "frontend", "produced"))
            for directory in (targets, frontend, produced):
                directory.mkdir()
            code = {}
            for i, name in enumerate(sorted(entries)):
                path = produced / str(i)
                path.write_bytes(("independent produced output " + name).encode())
                code[name] = str(path)
            profile = {"targets": []}
            names = {"apk/AndroidManifest.xml", "apk/classes.dex", "apk/assets/authored.txt", "payload/authored.bundle"}
            names |= {"apk/" + name for name in entries}
            for name in sorted(names):
                if name.removeprefix("apk/") in code:
                    # Comparison rows exist, but no replay source is available.
                    row = {"path": name, "bytes": 1, "sha256": "0" * 64}
                else:
                    path = targets / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    data = ("independent content " + name).encode()
                    path.write_bytes(data)
                    row = {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                profile["targets"].append(row)
            for name in ("app.js", "controller.js", "style.css", "background.png"):
                (frontend / name).write_bytes(("independent frontend " + name).encode())
            for name in ("java", "libjavactool.so", "android.jar", "d8.jar", "manifest.json"):
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
                        "javac": str(root / "libjavactool.so"),
                        "android_jar": str(root / "android.jar"),
                        "d8_jar": str(root / "d8.jar"),
                        "wire_helper": str(root / "wire.py"),
                        **({"code": code} if code else {}),
                    }
                )
            )
            output = root / "output"
            if missing_content:
                (targets / "apk/assets/authored.txt").unlink()
                (targets / "payload/authored.bundle").unlink()

            def run(argv, **kwargs):
                argv = list(map(str, argv))
                if Path(argv[0]).name == "libjavactool.so":
                    (Path(argv[argv.index("-d") + 1]) / "Authored.class").write_bytes(b"independent Java witness")
                else:
                    (Path(argv[argv.index("--output") + 1]) / "classes.dex").write_bytes(b"independent DEX witness")

            with (
                patch.object(OWNER.PACKET, "profile", return_value=(b"", profile)),
                patch.object(OWNER.MANIFEST, "patch", return_value=b"independent routed manifest") as manifest_patch,
                patch.object(OWNER, "ART", OWNER.sha(frontend / "background.png")),
                patch.object(OWNER, "RESERVE", 0),
                patch.object(OWNER.subprocess, "run", side_effect=run) as compiler,
            ):
                if missing_content:
                    with self.assertRaisesRegex(ValueError, "inputs incomplete"):
                        OWNER.build(request, output)
                    compiler.assert_not_called()
                    report = json.loads((output / "readiness.json").read_text())
                    self.assertEqual(report["blocked_entries"], ["apk/assets/authored.txt", "payload/authored.bundle"])
                    self.assertFalse((output / "owner-unsigned.apk").exists())
                    self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                    return
                manifest_source = Path(code["AndroidManifest.xml"]) if "AndroidManifest.xml" in code else targets / "apk/AndroidManifest.xml"
                original_manifest = manifest_source.read_bytes()
                if change_manifest:

                    def patch_manifest(*args, **kwargs):
                        manifest_source.write_bytes(b"unexpected manifest drift")
                        return b"independent routed manifest"

                    manifest_patch.side_effect = patch_manifest
                    with self.assertRaisesRegex(ValueError, "input changed"):
                        OWNER.build(request, output)
                    self.assertFalse(json.loads((output / "result.json").read_text())["success"])
                    return
                result = OWNER.build(request, output)
            self.assertEqual(manifest_patch.call_args.args[0], original_manifest)
            self.assertTrue(result["success"])
            self.assertEqual(result["il2cpp_or_original_dex_changed"], bool(code))
            self.assertEqual(result["original_entries_preserved"], 1 if "AndroidManifest.xml" in code else 2)
            self.assertEqual(set(result["code_entries"]), entries)
            with zipfile.ZipFile(output / "owner-unsigned.apk") as archive:
                self.assertEqual(archive.read("AndroidManifest.xml"), b"independent routed manifest")
                for name, path in code.items():
                    if name != "AndroidManifest.xml":
                        self.assertEqual(archive.read(name), Path(path).read_bytes())
                self.assertEqual(archive.read(result["new_dex"]), b"independent DEX witness")
                self.assertEqual(archive.read("assets/authored.txt"), (targets / "apk/assets/authored.txt").read_bytes())
                self.assertEqual(archive.read("assets/owner-bootstrap/data/authored.bundle"), (targets / "payload/authored.bundle").read_bytes())


if __name__ == "__main__":
    unittest.main()
