"""Source drift and destination fences for experimental app-host staging."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("managed_host_stage", ROOT / "tools/phone-build/managed-host/stage.py")
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class ManagedHostStageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        (self.profile / "source.py").write_bytes(b"# independently authored fixture\n")
        self.metadata = dict(
            source_head="authored fixture", public_profile_source_hashes={"source.py": hashlib.sha256((self.profile / "source.py").read_bytes()).hexdigest()}
        )
        self.sdk = self.root / "sdk"
        for name in ("platforms/android-33/android.jar", "build-tools/34.0.0/lib/d8.jar", "build-tools/34.0.0/lib/apksigner.jar"):
            path = self.sdk / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(b"authored jar placeholder; never executed")
        self.destination = self.root / "work/fixture"
        self.patch = mock.patch.object(stage, "load_metadata", return_value=self.metadata)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_staging_binds_sources_without_game_input_or_executing_jars(self):
        result = stage.stage(self.profile, self.sdk, self.destination, root=self.root)
        self.assertTrue(result["success"])
        self.assertIs(result["game_inputs"], False)
        self.assertEqual((self.destination / "repo/source.py").read_bytes(), (self.profile / "source.py").read_bytes())
        for name, expected in result["files"].items():
            self.assertEqual(hashlib.sha256((self.destination / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(json.loads((self.destination / "stage-receipt.json").read_text()), result)
        for name in (
            "OwnerInstaller.java",
            "OwnerAlphaInstall.java",
            "OwnerUpdateState.java",
            "OwnerBuildService.java",
            "OwnerInputImport.java",
            "OwnerInputSource.java",
            "release-trust.json",
        ):
            self.assertIn(name, result["files"])
        for name in (
            "release.py",
            "updates.py",
            "public_release.py",
            "release_jobs.py",
            "game_import.py",
            "install_flow.py",
            "atomic_io.py",
            "install_inputs.py",
            "alpha_policy.py",
            "ProfileStore.java",
            "ProfileRetentionProvider.java",
        ):
            self.assertIn("repo/tools/phone-build/owner-apk/" + name, result["files"])
        trust = json.loads((self.destination / "release-trust.json").read_text())
        self.assertEqual(trust["keys"], {})
        self.assertEqual(trust["application_id"], "dev.ror2lab.alpha")

    def test_public_source_drift_refuses_before_creating_output(self):
        (self.profile / "source.py").write_bytes(b"unexpected source\n")
        with self.assertRaisesRegex(ValueError, "source drift"):
            stage.stage(self.profile, self.sdk, self.destination, root=self.root)
        self.assertFalse(self.destination.exists())

    def test_owner_backend_retains_repository_marker_for_existing_owners(self):
        (self.root / "AGENTS.md").write_text("# Fixture repository marker\n")
        (self.root / "dev").write_text("# Fixture entry point\n")
        with mock.patch.object(stage.subprocess, "check_output", return_value=b"AGENTS.md\0dev\0") as git:
            stage.stage(self.profile, self.sdk, self.destination, root=self.root, owner_backend=True)
        self.assertIn("AGENTS.md", git.call_args.args[0])
        self.assertEqual((self.destination / "repo/AGENTS.md").read_bytes(), (self.root / "AGENTS.md").read_bytes())
        self.assertEqual((self.destination / "repo/dev").read_bytes(), (self.root / "dev").read_bytes())

    def test_ancestor_link_in_public_source_refuses(self):
        target = self.profile / "source.py"
        link = self.profile / "alias"
        link.symlink_to(self.profile, target_is_directory=True)
        self.metadata["public_profile_source_hashes"] = {"alias/source.py": hashlib.sha256(target.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "contains links"):
            stage.stage(self.profile, self.sdk, self.destination, root=self.root)
        self.assertFalse(self.destination.exists())

    def test_existing_or_unowned_destination_refuses_and_preserves_sentinel(self):
        self.destination.mkdir(parents=True)
        sentinel = self.destination / "owned.txt"
        sentinel.write_bytes(b"preserve")
        for destination in (self.destination, self.root / "outside"):
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "must be new"):
                stage.stage(self.profile, self.sdk, destination, root=self.root)
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_separate_tool_package_retains_java_classes_and_private_apk_provider(self):
        output = self.root / "AndroidManifest.xml"
        source = stage.SOURCE / "AndroidManifest.xml"
        before = source.read_bytes()
        stage.tool_manifest(source, output, "dev.ror2lab.authoredtool")
        value = ET.parse(output).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual(value.attrib["package"], "dev.ror2lab.authoredtool")
        runner = value.find("instrumentation")
        self.assertEqual(runner.attrib[android + "targetPackage"], "dev.ror2lab.authoredtool")
        self.assertEqual(runner.attrib[android + "name"], "dev.ror2lab.phonebuildhostfixture.ToolHostActivity$Runner")
        provider = value.find("application/provider")
        self.assertEqual(provider.attrib[android + "authorities"], "dev.ror2lab.authoredtool.apk")
        self.assertEqual(provider.attrib[android + "exported"], "false")
        self.assertEqual(provider.attrib[android + "grantUriPermissions"], "true")
        self.assertEqual(source.read_bytes(), before)
        receiver = value.find("application/receiver")
        self.assertEqual(receiver.attrib[android + "name"], "dev.ror2lab.phonebuildhostfixture.OwnerInstaller$Result")
        self.assertEqual(receiver.attrib[android + "exported"], "false")
        service = value.find("application/service")
        self.assertEqual(service.attrib[android + "name"], "dev.ror2lab.phonebuildhostfixture.OwnerBuildService")
        self.assertEqual(service.attrib[android + "exported"], "false")
        self.assertEqual(service.attrib[android + "stopWithTask"], "false")
        permissions = {node.attrib[android + "name"] for node in value.findall("uses-permission")}
        self.assertIn("android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION", permissions)
        self.assertIn("dev.ror2lab.alpha", {node.attrib[android + "name"] for node in value.findall("queries/package")})
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", permissions)
        for package in ("dev.ror2lab.arm64", "dev.ror2lab.alpha"):
            with self.assertRaisesRegex(ValueError, "separate lab tool"):
                stage.tool_manifest(source, self.root / "refused.xml", package)
        self.assertFalse((self.root / "refused.xml").exists())

    def test_manifest_queries_only_configured_game_without_broad_visibility(self):
        output = self.root / "configured-manifest.xml"
        stage.tool_manifest(stage.SOURCE / "AndroidManifest.xml", output, "dev.ror2lab.authoredtool", game_package="example.authored.game")
        value = ET.parse(output).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual([node.attrib[android + "name"] for node in value.findall("queries/package")], ["example.authored.game"])
        with self.assertRaisesRegex(ValueError, "separate lab tool"):
            stage.tool_manifest(stage.SOURCE / "AndroidManifest.xml", output, "dev.ror2lab.authoredtool", game_package="dev.ror2lab.authoredtool")

    def test_explicit_build_time_public_trust_is_staged_not_downloaded(self):
        trust = self.root / "public-trust.json"
        value = {"repository": "example/repository", "application_id": "dev.ror2lab.alpha", "keys": {"test": "PUBLIC KEY FIXTURE ONLY"}}
        trust.write_text(json.dumps(value))
        result = stage.stage(self.profile, self.sdk, self.destination, root=self.root, release_trust=trust)
        self.assertEqual(json.loads((self.destination / "release-trust.json").read_text()), value)
        self.assertEqual(result["files"]["release-trust.json"], hashlib.sha256(trust.read_bytes()).hexdigest())


class ManagedHostMetadataTests(unittest.TestCase):
    def test_network_extensions_are_explicit_pinned_inputs_before_any_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            extra = {"natives": {}, "links": {}}
            for target, link in stage.UPDATE_NETWORK_MODULES.items():
                path = root / Path(link).name
                path.write_bytes(b"authored module placeholder; never executed")
                extra["natives"][target] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                extra["links"][link] = target
            stage.validate_update_network(extra)
            for missing in (None, {"natives": {}, "links": {}}):
                with self.assertRaisesRegex(ValueError, "Installer HTTPS requires"):
                    stage.validate_update_network(missing)
            target, link = next(iter(stage.UPDATE_NETWORK_MODULES.items()))
            extra["links"][link] = "wrong.so"
            with self.assertRaisesRegex(ValueError, "Python link"):
                stage.validate_update_network(extra)
            extra["links"][link] = target
            Path(extra["natives"][target]["path"]).write_bytes(b"drift")
            with self.assertRaisesRegex(ValueError, "provider drift"):
                stage.validate_update_network(extra)
        builder = (stage.SOURCE / "build_fixture.py").read_text()
        self.assertLess(builder.index("staging.validate_update_network(extra)"), builder.index('"native-build"'))
        self.assertIn('plan["links"].update(extra["links"])', builder)

    def test_supplied_native_manifest_loads_and_rejects_escape_before_staging(self):
        metadata = stage.load_metadata()
        self.assertTrue(metadata["public_profile_source_hashes"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "metadata.json"
            metadata["natives"][0]["path"] = "../escape.so"
            path.write_text(json.dumps(metadata))
            with mock.patch.object(stage, "METADATA", path), self.assertRaisesRegex(ValueError, "Unsafe"):
                stage.load_metadata()


if __name__ == "__main__":
    unittest.main()
