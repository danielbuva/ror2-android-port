import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import installed_alpha
from test_public_release import release_body


class InstalledAlphaTests(unittest.TestCase):
    installer = "example.authorized.installer"
    installer_sha = "a" * 64
    game_sha = "b" * 64
    installer_path = "package:/data/app/installer/base.apk"
    game_path = "package:/data/app/player/base.apk"

    def setUp(self):
        self.owner = installed_alpha.release_tools()
        self.release = release_body()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bundle = Path(temporary.name) / "public-tools.zip"
        self.write_bundle()
        self.source_sha = self.owner.ALPHA.fingerprint(self.release)
        self.trust = {"application_id": installed_alpha.PACKAGE, "repository": "example/project", "keys": {"example": "fixture"}}
        self.receipt = dict(
            application_id=installed_alpha.PACKAGE,
            installed_readback_verified=True,
            version_code=31,
            sha256=self.game_sha,
            signer_sha256="c" * 64,
            source_sha256=self.source_sha,
            release=self.release,
            envelope={"release": self.release, "signature": {"algorithm": "SHA256withRSA", "key_id": "example", "value": "YQ=="}},
        )
        self.device = Mock(package=installed_alpha.PACKAGE, serial="synthetic-device")
        self.observed = {
            ("pm", "path", self.installer): self.installer_path,
            ("sha256sum", "--", self.installer_path[8:]): self.installer_sha + "  " + self.installer_path[8:],
            ("pm", "path", installed_alpha.PACKAGE): self.game_path,
            ("sha256sum", "--", self.game_path[8:]): self.game_sha + "  " + self.game_path[8:],
            ("dumpsys", "package", installed_alpha.PACKAGE): "    versionCode=31 minSdk=30 targetSdk=34",
        }

        def shell(*args, **kwargs):
            if args[:4] == ("run-as", self.installer, "sh", "-c"):
                self.assertIn("test ! -e files/owner-input/pending-install.json", args[4])
                return json.dumps(self.receipt)
            return self.observed[args]

        self.device.sh.side_effect = shell

    def write_bundle(self, *, bind_config=True):
        public = self.owner.public()
        config = "recipe/runtime-config.json"
        profile = "recipe/owner-player-data.json"
        member = "authored-text"
        name = "apk/assets/bin/Data/" + member
        script = "tools/phone-build/accepted-output/player_data.py"
        runtime = b'{"attempt":"signed-attempt"}'
        player = {
            "text_assets": {
                "files": [
                    {
                        "file": member,
                        "name": "MovementBatchProbe",
                        "recipe": {
                            "path": "runtime-config.json",
                            "bytes": len(runtime),
                            "sha256": hashlib.sha256(runtime).hexdigest(),
                        },
                    }
                ]
            }
        }
        files = {config: runtime, profile: json.dumps(player).encode(), script: b"# authored fixture"}
        index = {
            "schema": 1,
            "files": {key: hashlib.sha256(data).hexdigest() for key, data in files.items()},
            "entries": {
                name: {"recipe_files": [profile, config] if bind_config else [profile], "producer_files": [script], "job": None},
            },
        }
        self.release["entries"] = {name: public.entry_dependencies(index, name)}
        with zipfile.ZipFile(self.bundle, "w") as archive:
            for key, value in files.items():
                archive.writestr(key, value)
            archive.writestr(public.INDEX, json.dumps(index))
        self.release["bundle_sha256"] = hashlib.sha256(self.bundle.read_bytes()).hexdigest()

    def verify(self):
        with patch.object(installed_alpha, "release_tools", return_value=self.owner), patch.object(self.owner.public(), "verify_signature") as signature:
            result = installed_alpha.verify_installed(self.device, self.installer, self.installer_sha, self.trust, self.source_sha, self.bundle)
            signature.assert_called_once_with(self.owner.RELEASE.signed_bytes(self.release), b"a", "fixture")
            return result

    def test_trust_is_read_only_from_the_authorized_apk(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "installer.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("assets/release-trust.json", json.dumps(self.trust))
            with self.assertRaisesRegex(ValueError, "Authorized installer APK hash differs"):
                installed_alpha.installer_trust(apk, "0" * 64)
            self.assertEqual(installed_alpha.installer_trust(apk, hashlib.sha256(apk.read_bytes()).hexdigest()), self.trust)

    def test_verifies_live_apk_and_independent_publisher_identity(self):
        result = self.verify()
        self.assertEqual(result["apk_sha256"], self.game_sha)
        self.assertEqual(result["publisher_version_code"], 2)
        self.assertEqual(result["attempt"], "signed-attempt")
        self.assertNotIn("release", result)
        self.assertNotIn("envelope", result)

    def test_refuses_an_unpinned_installer_before_reading_its_sandbox(self):
        self.observed[("sha256sum", "--", self.installer_path[8:])] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "Live installer differs"):
            self.verify()
        self.assertEqual([call.args[0] for call in self.device.sh.call_args_list], ["pm", "sha256sum"])

    def test_refuses_a_receipt_for_another_publisher_release(self):
        self.receipt["release"] = dict(self.release, version_code=3)
        with self.assertRaisesRegex(RuntimeError, "Publisher signature differs"):
            self.verify()

    def test_refuses_replaced_game_bytes(self):
        self.observed[("sha256sum", "--", self.game_path[8:])] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "Live alpha APK differs"):
            self.verify()

    def test_runtime_recipe_must_belong_to_signed_output(self):
        self.write_bundle(bind_config=False)
        with self.assertRaisesRegex(ValueError, "outside the signed APK member closure"):
            installed_alpha.release_attempt(self.bundle, self.release, self.owner.public())

    def test_bundle_must_match_the_installed_release(self):
        self.bundle.write_bytes(b"different public tools")
        with self.assertRaisesRegex(ValueError, "differs from the installed signed release"):
            self.verify()
