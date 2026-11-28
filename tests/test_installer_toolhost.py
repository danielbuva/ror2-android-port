import hashlib
import importlib.util
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installer_toolhost", ROOT / "scripts/lab/installer_toolhost.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class InstallerToolhostTest(unittest.TestCase):
    def test_repack_accepts_only_the_changed_codec_with_an_explicit_pinned_input(self):
        with tempfile.TemporaryDirectory() as directory:
            codec = Path(directory) / fixture.TEXTURE_CODEC
            codec.write_bytes(b"new codec")
            old, new = "a" * 64, fixture.digest(codec)

            def profile(codec_hash, loader="b" * 64):
                return dict(texture_sdk_guest={fixture.TEXTURE_CODEC: codec_hash, "loader": loader}, public_profile_source_hashes={})

            staging = mock.Mock()
            staging.load_metadata.side_effect = [profile(new), profile(new, "c" * 64), profile(new)]
            with mock.patch.object(fixture, "git", side_effect=["", json.dumps(profile(old)), "", "", json.dumps(profile(old)), "", json.dumps(profile(old))]):
                self.assertEqual(fixture.verify_runtime_inputs(codec.parent, "old", "new", staging, codec), (old, new))
                with self.assertRaisesRegex(ValueError, "retained Android tool profile differs"):
                    fixture.verify_runtime_inputs(codec.parent, "old", "new", staging, codec)
                codec.write_bytes(b"unverified codec")
                with self.assertRaisesRegex(ValueError, "must match the changed profile pin"):
                    fixture.verify_runtime_inputs(codec.parent, "old", "new", staging, codec)

    def test_repack_accepts_updated_repo_pins_and_refuses_runtime_or_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "recipe" / "fixture.json"
            source.parent.mkdir()
            source.write_bytes(b"current source")
            name = "recipe/fixture.json"
            runtime = {"natives": ["retained-library"]}
            base = json.dumps(dict(runtime, public_profile_source_hashes={name: "a" * 64}))
            staging = mock.Mock()
            profile = dict(runtime, public_profile_source_hashes={name: fixture.digest(source)})
            with mock.patch.object(fixture, "git", side_effect=["", base, name] * 2 + ["", base]):
                staging.load_metadata.side_effect = [profile.copy(), profile.copy(), dict(profile, natives=[])]
                fixture.verify_runtime_inputs(root, "old", "new", staging)
                source.write_bytes(b"source drift")
                with self.assertRaisesRegex(ValueError, "public fixture source differs"):
                    fixture.verify_runtime_inputs(root, "old", "new", staging)
                with self.assertRaisesRegex(ValueError, "retained Android tool profile differs"):
                    fixture.verify_runtime_inputs(root, "old", "new", staging)

    def test_base_receipt_binds_request_key_and_source_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            commit, key = "a" * 40, "b" * 64
            base = Path(directory) / key
            base.mkdir()
            apk = base / "signed.apk"
            apk.write_bytes(b"synthetic APK")
            built = dict(success=True, game_inputs=False, apk_bytes=apk.stat().st_size, apk_sha256=fixture.digest(apk), native_hashes={})
            fixture.save(base / "build-receipt.json", built)
            receipt = dict(success=True, package=fixture.PACKAGE, source_commit=commit, cache_key=key, signer_sha256="c" * 64, apk_sha256=built["apk_sha256"])
            fixture.save(base / "result.json", receipt)
            self.assertEqual(fixture.base_receipt(base), (receipt, {}))
            fixture.save(base / "result.json", dict(receipt, cache_key="d" * 64))
            with self.assertRaisesRegex(ValueError, "base receipt or APK differs"):
                fixture.base_receipt(base)

    def test_backup_validates_private_files_before_publishing_and_reuses_them(self):
        with tempfile.TemporaryDirectory() as directory:
            keys = Path(directory).resolve() / "keys/installer-test"

            def cert(path, _java):
                for name in fixture.KEY_FILES:
                    member = path / name
                    self.assertEqual(stat.S_IMODE(member.stat().st_mode), 0o600)
                    self.assertEqual(member.read_bytes(), b"synthetic " + name.encode())
                return "certificate"

            def fetch(name, stream):
                stream.write(b"synthetic " + name.encode())

            with mock.patch.object(fixture, "signing_certificate", side_effect=cert):
                with self.assertRaisesRegex(ValueError, "backup certificate differs"):
                    fixture.backup_signing_key(keys, None, "wrong", fetch)
                self.assertFalse(keys.exists())
                self.assertEqual(list(keys.parent.iterdir()), [])
                fixture.backup_signing_key(keys, None, "certificate", fetch)
                wrong_fetch = mock.Mock(side_effect=AssertionError("existing key must be reused"))
                fixture.backup_signing_key(keys, None, "certificate", wrong_fetch)
                wrong_fetch.assert_not_called()

    def test_explicit_trust_keeps_release_identity_and_validates_publisher_keys(self):
        retained = dict(repository="owner/project", application_id="dev.ror2lab.alpha", keys={})
        configured = dict(retained, keys={"staged": "public key"})
        source = mock.Mock()
        public = fixture.load_module("tested_repack_public_release", ROOT / fixture.SIGNER.with_name("public_release.py"))
        with mock.patch.object(fixture, "load_module", return_value=public), mock.patch.object(public, "public_numbers") as parse_key:
            source.read_bytes.return_value = json.dumps(configured).encode()
            self.assertEqual(json.loads(fixture.provisioned_trust(ROOT, source, retained)), configured)
            parse_key.assert_called_once_with("public key")
            for invalid in (dict(configured, application_id="other.package"), dict(configured, repository="other/project"), retained):
                source.read_bytes.return_value = json.dumps(invalid).encode()
                with self.assertRaisesRegex(ValueError, "retained repository and application"):
                    fixture.provisioned_trust(ROOT, source, retained)

    def test_assembly_rebuilds_authored_members_and_verifies_retained_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, dex, tracked = (root / name for name in ("base.apk", "classes.dex", "tracked"))
            dex.write_bytes(b"new dex")
            tracked.write_bytes(b"new source")
            trust = root / "trust.json"
            trust.write_bytes(b"staged public trust")
            runtime_hash = hashlib.sha256(b"runtime").hexdigest()
            asset_hash = hashlib.sha256(b"data").hexdigest()
            with zipfile.ZipFile(original, "w") as apk:
                apk.writestr("AndroidManifest.xml", b"old manifest")
                apk.writestr("classes.dex", b"old dex")
                apk.writestr("META-INF/OWNER.SF", b"signature")
                apk.writestr("lib/arm64-v8a/libtest.so", b"runtime")
                apk.writestr("assets/data", b"data")
                apk.writestr("assets/repo/removed", b"old source")
                apk.writestr(fixture.RELEASE_TRUST, b"old trust")
                apk.writestr("assets/data-hashes.json", json.dumps({"data": asset_hash, "repo/removed": "old", "release-trust.json": "old trust"}))
            source = {"assets/repo/tracked": tracked, fixture.RELEASE_TRUST: trust}

            def obsolete(name):
                return name.startswith("META-INF/")

            with self.assertRaisesRegex(ValueError, "retained Android library differs"):
                fixture.assemble(original, root / "bad.apk", b"new manifest", dex, source, {"libtest.so": "wrong"}, obsolete)
            output = root / "new.apk"
            hashes = fixture.assemble(original, output, b"new manifest", dex, source, {"libtest.so": runtime_hash}, obsolete)
            with zipfile.ZipFile(output) as apk:
                self.assertEqual(
                    set(apk.namelist()),
                    {
                        "AndroidManifest.xml",
                        "classes.dex",
                        "lib/arm64-v8a/libtest.so",
                        "assets/data",
                        "assets/repo/tracked",
                        "assets/data-hashes.json",
                        fixture.RELEASE_TRUST,
                    },
                )
                self.assertEqual(apk.read("classes.dex"), b"new dex")
                self.assertEqual(apk.read("AndroidManifest.xml"), b"new manifest")
                self.assertEqual(apk.read("lib/arm64-v8a/libtest.so"), b"runtime")
                self.assertEqual(apk.read("assets/repo/tracked"), b"new source")
                self.assertEqual(apk.read(fixture.RELEASE_TRUST), trust.read_bytes())
                self.assertEqual(json.loads(apk.read("assets/data-hashes.json")), hashes)
                self.assertEqual(hashes, {"data": asset_hash, "repo/tracked": fixture.digest(tracked), "release-trust.json": fixture.digest(trust)})
