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
import staged_alpha_update
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
        self.root = Path(temporary.name)
        self.bundle = self.root / "public-tools.zip"
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

    def write_bundle(self, *, bind_config=True, attempt="signed-attempt", extra_entry=""):
        public = self.owner.public()
        config = "recipe/runtime-config.json"
        profile = "recipe/owner-player-data.json"
        member = "authored-text"
        name = "apk/assets/bin/Data/" + member
        script = "tools/phone-build/accepted-output/player_data.py"
        runtime = json.dumps({"attempt": attempt}).encode()
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
        if extra_entry:
            stable_recipe = "recipe/stable.json"
            files[stable_recipe] = b"{}"
            index["files"][stable_recipe] = hashlib.sha256(files[stable_recipe]).hexdigest()
            stable = {"recipe_files": [stable_recipe], "producer_files": [script], "job": None}
            index["entries"].update({"apk/stable.txt": stable, extra_entry: stable})
        self.release["entries"] = {name: public.entry_dependencies(index, name) for name in index["entries"]}
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

    def stage_update_pair(self):
        apk = self.root / "installer.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("assets/release-trust.json", json.dumps(self.trust))
        stages = []
        for tag, version, attempt, entry in (("later-label", 2, "baseline", "apk/remove.txt"), ("earlier-label", 10, "update", "apk/new.txt")):
            stage = self.root / f"owner-v{version}"
            stage.mkdir()
            self.bundle = stage / "public-tools.zip"
            self.release = dict(release_body(), version=tag, version_code=version)
            self.write_bundle(attempt=attempt, extra_entry=entry)
            (stage / "release.json").write_text(json.dumps(self.release))
            (stage / "release.sig").write_text(json.dumps(self.receipt["envelope"]["signature"]))
            stages.append(stage)
        return apk, hashlib.sha256(apk.read_bytes()).hexdigest(), 4, *stages

    def test_local_update_preflight_uses_numeric_versions_and_signed_output_dependencies(self):
        args = self.stage_update_pair()
        public = self.owner.public()
        with (
            patch.object(installed_alpha, "release_tools", return_value=self.owner),
            patch.object(public, "verify_signature") as signature,
            patch.object(public, "validate_publication") as validate,
        ):
            plan = installed_alpha.preflight_update(*args)
        self.assertEqual(signature.call_count, 2)
        self.assertEqual([call.args[0] for call in validate.call_args_list], [stage / "public-tools.zip" for stage in args[-2:]])
        self.assertEqual(plan["baseline"]["publisher_version_code"], 2)
        self.assertEqual(plan["update"]["publisher_version_code"], 10)
        self.assertEqual(plan["baseline"]["attempt"], "baseline")
        self.assertEqual(plan["update"]["attempt"], "update")
        self.assertEqual(plan["update"]["source_sha256"], self.owner.ALPHA.fingerprint(self.release))
        self.assertEqual(plan["changed_entries"], ["apk/assets/bin/Data/authored-text", "apk/new.txt"])
        self.assertEqual(plan["removed_entries"], ["apk/remove.txt"])
        self.assertEqual(plan["unchanged_entries"], ["apk/stable.txt"])

    def test_local_update_preflight_rejects_wrong_order_and_untrusted_publisher(self):
        apk, digest, version, baseline, update = self.stage_update_pair()
        public = self.owner.public()
        with (
            patch.object(installed_alpha, "release_tools", return_value=self.owner),
            patch.object(public, "verify_signature"),
            patch.object(public, "validate_publication") as validate,
        ):
            for first, second in ((update, baseline), (baseline, baseline)):
                with self.subTest(first=first.name, second=second.name), self.assertRaisesRegex(ValueError, "versionCode must increase"):
                    installed_alpha.preflight_update(apk, digest, version, first, second)
            (update / "release.sig").write_text(json.dumps(dict(self.receipt["envelope"]["signature"], key_id="other")))
            with self.assertRaisesRegex(ValueError, "trusted"):
                installed_alpha.preflight_update(apk, digest, version, baseline, update)
            validate.assert_not_called()

    def test_staged_install_selection_keeps_production_package_boundary(self):
        args = (installed_alpha.PACKAGE, "dev.ror2lab.installertest", self.installer_sha, self.source_sha)
        installed_alpha.validate_selection(*args, staged=True)
        with self.assertRaisesRegex(ValueError, "production"):
            installed_alpha.validate_selection(*args)
        with self.assertRaisesRegex(ValueError, "staged"):
            installed_alpha.validate_selection(installed_alpha.PACKAGE, self.installer, self.installer_sha, self.source_sha, staged=True)

    def test_staged_play_writes_bound_terminal_receipt_even_on_failure(self):
        staged = staged_alpha_update.StagedUpdate.__new__(staged_alpha_update.StagedUpdate)
        self.device.installed = dict(apk_sha256=self.game_sha, attempt="signed-attempt")
        phone = Mock(timeout=60)
        phone.thermal.between_sessions.return_value = {}
        phone.thermal.cancelled.is_set.return_value = False
        phone.package_hash.return_value = self.game_sha
        for failure in (None, RuntimeError("first stage timed out")):
            with self.subTest(failure=failure):
                directory = Path(tempfile.mkdtemp(dir=self.root))
                staged.installer = Mock(GAME=installed_alpha.PACKAGE)
                staged.installer.DIAGNOSTICS.directory = directory
                staged.require = Mock()
                with (
                    patch("device_session.prepare_launch"),
                    patch("device_session.run_workload", side_effect=failure) as run,
                ):
                    if failure is None:
                        staged.play(phone, self.device, "baseline")
                    else:
                        with self.assertRaisesRegex(RuntimeError, "first stage timed out"):
                            staged.play(phone, self.device, "baseline")
                receipt = json.loads((directory / "baseline-play/terminal.done.json").read_text())
                self.assertEqual(receipt["apk_sha256"], self.game_sha)
                self.assertEqual(receipt["installed_release"]["attempt"], run.call_args.kwargs["start_attempt"])
                self.assertEqual(receipt["mode"], "installed-alpha")
                self.assertEqual(receipt["success"], failure is None)
                self.assertEqual(receipt.get("first_failure"), str(failure) if failure else None)

    def test_staged_update_binds_entry_coverage_and_producer_execution(self):
        receipt = {
            "incremental": {
                "rebuilt": ["changed"],
                "reused": ["byte-identical", "unchanged"],
                "producer_jobs": {"changed-job": "executed", "unchanged-job": "reused"},
            }
        }
        source = {"jobs": ["changed-job", "unchanged-job"]}

        def require(condition, reason):
            if not condition:
                raise ValueError(reason)

        changed, unchanged = ["changed", "byte-identical"], ["unchanged"]
        self.assertEqual(staged_alpha_update.verify_incremental(receipt, source, changed, unchanged, 1, require), receipt["incremental"])
        with self.assertRaisesRegex(ValueError, "staged-producer-execution-count"):
            staged_alpha_update.verify_incremental(receipt, source, changed, unchanged, 2, require)
        receipt["incremental"]["rebuilt"].append("unchanged")
        receipt["incremental"]["reused"].remove("unchanged")
        with self.assertRaisesRegex(ValueError, "staged-rebuild-entry-coverage"):
            staged_alpha_update.verify_incremental(receipt, source, changed, unchanged, 1, require)
