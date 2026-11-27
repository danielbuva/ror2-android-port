"""Source drift and destination fences for experimental app-host staging."""

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile

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

    def test_texture_sdk_guest_stages_only_pinned_public_files(self):
        source = self.root / "guest"
        wrapper = source / "texture-sdk-codec"
        library = source / "linux/lib/x86_64-linux-gnu/libc.so.6"
        library.parent.mkdir(parents=True)
        wrapper.write_bytes(b"synthetic wrapper")
        library.write_bytes(b"synthetic guest library")
        (source / "etccompress.so").write_bytes(b"excluded owner-only SDK member")
        pins = {path.relative_to(source).as_posix(): stage.digest(path) for path in (wrapper, library)}
        destination = self.root / "assets/texture-sdk"
        extra = {
            "texture_sdk_guest": str(source),
            "natives": dict.fromkeys(("libqemu-x86_64.so", "libtexture-pixels.so", "libtexture-etc.so", "libc++_shared.so")),
        }
        self.assertEqual(stage.stage_texture_sdk_guest({}, pins, destination), {})
        with self.assertRaisesRegex(ValueError, "requires QEMU"):
            stage.stage_texture_sdk_guest(dict(extra, natives={}), pins, destination)
        with self.assertRaisesRegex(ValueError, "guest input drift"):
            stage.stage_texture_sdk_guest(extra, pins | {library.relative_to(source).as_posix(): "0" * 64}, destination)
        self.assertFalse(destination.exists())
        receipt = stage.stage_texture_sdk_guest(extra, pins, destination)
        self.assertEqual(receipt, {str(source / path): pin for path, pin in pins.items()})
        self.assertEqual({path.relative_to(destination).as_posix(): stage.digest(path) for path in destination.rglob("*") if path.is_file()}, pins)

    def test_staging_binds_sources_without_game_input_or_executing_jars(self):
        result = stage.stage(self.profile, self.sdk, self.destination, root=self.root)
        self.assertTrue(result["success"])
        self.assertIs(result["game_inputs"], False)
        self.assertEqual((self.destination / "repo/source.py").read_bytes(), (self.profile / "source.py").read_bytes())
        for name, expected in result["files"].items():
            self.assertEqual(hashlib.sha256((self.destination / name).read_bytes()).hexdigest(), expected)
        for name in stage.JAVA_SOURCES:
            self.assertEqual((self.destination / Path(name).name).read_bytes(), (stage.SOURCE / name).read_bytes())
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

    def test_shared_worktree_stages_explicit_backend_plan_and_binds_receipt(self):
        checkout = self.root / "checkout"
        checkout.mkdir()
        shared = self.root / "shared-work"
        shared.mkdir()
        (checkout / "work").symlink_to(shared, target_is_directory=True)
        plan = shared / "selected-tools.json"
        plan.write_text('{"natives": {}, "links": {}}\n')
        destination = shared / "fixture"

        result = stage.stage(self.profile, self.sdk, destination, root=checkout, backend_tools=plan)

        self.assertEqual((destination / "backend-tools.json").read_bytes(), plan.read_bytes())
        self.assertEqual(result["files"]["backend-tools.json"], stage.digest(plan))
        adapter = "repo/tools/phone-build/owner-code/GnuToolAdapter.c"
        self.assertEqual(result["files"][adapter], stage.digest(ROOT / adapter.removeprefix("repo/")))
        with self.assertRaisesRegex(ValueError, "must be new"):
            stage.stage(self.profile, self.sdk, self.root / "outside", root=checkout, backend_tools=plan)

    def test_owner_backend_stages_sources_without_repository_markers(self):
        (self.root / "dev").write_text("# Fixture entry point\n")
        with mock.patch.object(stage.subprocess, "check_output", return_value=b"dev\0") as git:
            stage.stage(self.profile, self.sdk, self.destination, root=self.root, owner_backend=True)
        self.assertNotIn("AGENTS.md", git.call_args.args[0])
        self.assertFalse((self.destination / "repo/AGENTS.md").exists())
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
        self.assertEqual(len(value.findall("application/provider")), 1)
        self.assertEqual(len(value.findall("application/activity")), 1)
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
        for package in ("dev.ror2lab.arm64", "dev.ror2lab.converted", "dev.ror2lab.alpha"):
            with self.assertRaisesRegex(ValueError, "separate lab tool"):
                stage.tool_manifest(source, self.root / "refused.xml", package)
        self.assertFalse((self.root / "refused.xml").exists())

    def test_disposable_installer_has_a_protected_document_fixture(self):
        preselected = self.root / "preselected.xml"
        output = self.root / "AndroidManifest.xml"
        stage.tool_manifest(stage.SOURCE / "AndroidManifest.xml", preselected, "dev.ror2lab.preselected")
        stage.tool_manifest(preselected, output, "dev.ror2lab.installertest")
        application = ET.parse(output).getroot().find("application")
        android = "{http://schemas.android.com/apk/res/android}"
        fixture = next(node for node in application.findall("provider") if node.get(android + "authorities").endswith(".acquisition"))
        self.assertEqual(fixture.get(android + "name"), "dev.ror2lab.phonebuildhostfixture.AcquisitionFixture$Provider")
        self.assertEqual(fixture.get(android + "permission"), "android.permission.MANAGE_DOCUMENTS")
        self.assertEqual(fixture.get(android + "grantUriPermissions"), "true")
        result = next(node for node in application.findall("activity") if node.get(android + "name").endswith(".AcquisitionFixture$Result"))
        self.assertEqual(result.get(android + "name"), "dev.ror2lab.phonebuildhostfixture.AcquisitionFixture$Result")
        self.assertEqual(result.get(android + "exported"), "false")

    def test_manifest_queries_only_configured_game_without_broad_visibility(self):
        output = self.root / "configured-manifest.xml"
        stage.tool_manifest(stage.SOURCE / "AndroidManifest.xml", output, "dev.ror2lab.authoredtool", game_package="example.authored.game")
        value = ET.parse(output).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual([node.attrib[android + "name"] for node in value.findall("queries/package")], ["example.authored.game"])
        self.assertEqual(
            [node.attrib[android + "name"] for node in value.findall("queries/intent/action")],
            ["android.settings.APPLICATION_DEVELOPMENT_SETTINGS"],
        )
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
    def test_phone_entry_points_import_from_an_isolated_staged_runtime(self):
        plan = stage.load_metadata()
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary).resolve()
            sources = subprocess.check_output(["git", "ls-files", "-z", "--", "scripts", "tools", "recipe"], cwd=ROOT).decode().split("\0")
            for name in filter(None, sources):
                if Path(name).suffix in {".py", ".json"}:
                    target = runtime / "repo" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / name, target)
            for name in ("run_profile.py", "check_python.py"):
                shutil.copyfile(stage.SOURCE / name, runtime / name)
            manifest = runtime / "python-import-plan.json"
            manifest.write_text(json.dumps(plan))
            packages = runtime / "python/lib/player-packages"
            projects = set(plan["python_source_wheels"]) | {name.removesuffix("-py3-none-any.whl") for name in plan["python_wheels"]}
            for project in sorted(projects):
                name, version = project.rsplit("-", 1)
                distribution = importlib.metadata.distribution(name)
                self.assertEqual(distribution.version, version)
                for item in distribution.files:
                    if ".." in item.parts or item.suffix == ".pyc":
                        continue
                    target = packages / item
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(item.locate(), target)
            process = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(runtime / "check_python.py"), str(runtime), str(manifest)],
                cwd=runtime,
                env={},
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(process.stdout)
            self.assertGreaterEqual(report["entry_points"], len(plan["python_imports"]["entries"]))
            self.assertEqual(report["modules"], len(plan["python_imports"]["modules"]))

    def test_android_wheel_routes_extensions_into_native_apk_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel = root / "unitypy-1-cp314-cp314-android_24_arm64_v8a.whl"
            elf = bytes.fromhex("7f454c460201010000000000000000000300b700")
            module = "UnityPy/UnityPyBoost.cpython-314-aarch64-linux-android.so"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(module, elf)
                archive.writestr("UnityPy/__init__.py", "")
            extra = {
                "python_wheels": str(root),
                "python_built_wheels": {wheel.name: stage.digest(wheel)},
                "natives": {stage.MMAP_MODULE: {}},
                "links": {stage.MMAP_LINK: stage.MMAP_MODULE},
            }
            plan = {"python_wheels": {}, "python_source_wheels": {"unitypy-1": {}}}
            with self.assertRaisesRegex(ValueError, "requires one built wheel for unitypy"):
                stage.python_wheel_pins(plan, dict(extra, python_built_wheels={}))
            native_files, links = {}, {}
            packages = root / "assets/python/lib/player-packages"
            stage.stage_python_wheels(
                extra, stage.python_wheel_pins(plan, extra), packages, native_directory=root / "apk-native", native_files=native_files, links=links
            )
            provider = links["python/lib/player-packages/" + module]
            self.assertEqual(native_files[provider].read_bytes(), elf)
            self.assertFalse((packages / module).exists())
            self.assertTrue((packages / "UnityPy/__init__.py").is_file())

    def test_player_python_wheels_verify_before_extraction_and_import_in_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            wheels = root / "wheels"
            wheels.mkdir()
            destination = root / "python/lib/player-packages"
            pins = {}
            for name, files in (
                ("dnfile", {"dnfile/__init__.py": "from pefile import witness", "dnfile-1.dist-info/LICENSE": "authored notice"}),
                ("pefile", {"pefile.py": "from mmap import mmap\nwitness = 42"}),
            ):
                path = wheels / (name + "-1-py3-none-any.whl")
                with zipfile.ZipFile(path, "w") as archive:
                    for member, data in files.items():
                        archive.writestr(member, data)
                pins[path.name] = stage.digest(path)
            extra = {"python_wheels": str(wheels), "natives": {}, "links": {stage.MMAP_LINK: stage.MMAP_MODULE}}
            with self.assertRaisesRegex(ValueError, "mmap provider"):
                stage.stage_python_wheels(extra, pins, destination)
            extra["natives"][stage.MMAP_MODULE] = {}
            with self.assertRaisesRegex(ValueError, "wheel drift: pefile"):
                stage.stage_python_wheels(extra, pins | {"pefile-1-py3-none-any.whl": "0" * 64}, destination)
            self.assertFalse(destination.exists())
            receipt = stage.stage_python_wheels(extra, pins, destination)
            self.assertEqual(receipt, {str(wheels / name): value for name, value in pins.items()})
            self.assertEqual((destination / "dnfile-1.dist-info/LICENSE").read_text(), "authored notice")
            code = "import sys; sys.path.append(sys.argv[1]); import dnfile; assert dnfile.witness == 42"
            subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(destination)], check=True, capture_output=True, text=True)

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
