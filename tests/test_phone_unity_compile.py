import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_unity_compile as unity


class UnityCompilerContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        repository = Path(__file__).resolve().parents[1]
        for name in unity.SOURCES:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((repository / name).read_bytes())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: public Unity fixture"], cwd=self.root, check=True)
        self.guard, self.policy = unity.support("phone_managed_compile"), unity.support("phone_module_policy")
        self.sdk = self.root / "owner-sdk/Unity.app/Contents"
        binary = self.sdk / "MacOS/Unity"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"authored SDK identity substitute")
        compiler = {}
        for name in [key for key in self.guard.INPUTS if key.startswith("compiler/")]:
            source = "compiler-input/" + Path(name).name
            path = self.sdk / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("authored compiler " + name).encode())
            compiler[name] = (source, unity.sha(path))
        self.guard.INPUTS = compiler
        self.guard.SDK_BINARY_SHA256 = unity.sha(binary)
        self.install = self.sdk.parents[1]
        engine = "PlaybackEngines/AndroidPlayer/Variations/il2cpp/Managed"
        bcl = "Unity.app/Contents/NetStandard/ref/2.1.0"
        groups = {engine: 4, bcl: 1}
        for name in ("UnityEngine.dll", "UnityEngine.CoreModule.dll", "UnityEngine.AssetBundleModule.dll", "UnityEngine.AudioModule.dll"):
            destination = self.install / engine / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(("authored reference " + name).encode())
        destination = self.install / bcl / "netstandard.dll"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"authored BCL reference")
        refs = {p.relative_to(self.install).as_posix(): unity.sha(p) for d in groups for p in (self.install / d).glob("*.dll")}
        modules = "\n".join(self.policy.HEADER) + "\n"
        for name, controlled in (("Core", 0), ("AssetBundle", 1), ("Audio", 1)):
            modules += "  - name: " + name + "\n    dependencies: []\n    strippable: 1\n    controlledByBuiltinPackage: " + str(controlled) + "\n"
        editor = self.sdk / "Resources/modules.asset"
        editor.parent.mkdir(parents=True)
        editor.write_text(modules)
        target = self.install / "PlaybackEngines/AndroidPlayer/modules.asset"
        target.write_text(modules)
        self.policy.EDITOR_SHA, self.policy.TARGET_SHA = unity.sha(editor), unity.sha(target)
        packages = {}
        for name in ("assetbundle", "audio"):
            package = "com.unity.modules." + name
            destination = self.sdk / "Resources/PackageManager/BuiltInPackages" / package / "package.json"
            destination.parent.mkdir(parents=True)
            destination.write_text(json.dumps(dict(name=package, version="1.0.0", type="module", dependencies={})))
            packages[package + ".json"] = unity.sha(destination)
        for change in (
            patch.object(unity, "support", side_effect=lambda name: {"phone_managed_compile": self.guard, "phone_module_policy": self.policy}[name]),
            patch.object(unity, "GROUPS", groups),
            patch.object(unity, "REFERENCE_SHA", unity.aggregate(refs)),
            patch.object(unity, "PACKAGE_SHA", unity.aggregate(packages)),
            patch.object(unity, "MANIFEST", {"dependencies": {"com.unity.modules.assetbundle": "1.0.0"}}),
        ):
            change.start()
            self.addCleanup(change.stop)
        self.work = self.root / "work"
        self.launcher = self.root / "authored-launcher"
        self.launcher.write_bytes(b"non-executable build-tool substitute")

    def stage(self):
        return unity.stage(self.root, self.sdk, self.work)[0]

    def test_sdk_package_projection_excludes_disabled_reference_without_captured_array(self):
        stage = self.stage()
        receipt = unity.validate(stage)
        report = unity.project_references(stage, receipt)
        self.assertFalse(receipt["game_inputs"])
        self.assertFalse(report["unity_player_compilation_qualified"])
        self.assertEqual(len(report["references"]), 4)
        self.assertEqual([Path(p).name for p in report["excluded"]], ["UnityEngine.AudioModule.dll"])
        self.assertEqual(report["module_policy"]["enabledPackages"], ["com.unity.modules.assetbundle"])
        self.assertTrue(any(p["path"].endswith("netstandard.dll") for p in report["references"]))
        self.assertEqual(
            (stage / "compiler/csc.runtimeconfig.json").read_bytes(), (self.sdk / self.guard.INPUTS["compiler/csc.runtimeconfig.json"][0]).read_bytes()
        )

    def test_unknown_sdk_reference_package_and_uncommitted_source_refuse(self):
        path = next((self.install / next(iter(unity.GROUPS))).glob("*.dll"))
        original = path.read_bytes()
        path.write_bytes(b"authored SDK drift")
        with self.assertRaisesRegex(ValueError, "reference closure drift"):
            self.stage()
        self.assertFalse(self.work.exists())
        path.write_bytes(original)
        package = self.sdk / "Resources/PackageManager/BuiltInPackages/com.unity.modules.audio/package.json"
        original = package.read_bytes()
        package.write_text("{}")
        with self.assertRaisesRegex(ValueError, "package closure drift"):
            self.stage()
        self.assertFalse(self.work.exists())
        package.write_bytes(original)
        (self.root / unity.SOURCE).write_text("# authored source drift\n")
        with self.assertRaisesRegex(ValueError, "Commit Unity"):
            self.stage()
        self.assertFalse(self.work.exists())

    def test_stage_foreign_files_links_and_changed_inputs_refuse(self):
        for control in ("foreign", "link", "drift"):
            stage = self.stage()
            if control == "foreign":
                (stage / "captured.rsp").write_text("authored foreign control")
            elif control == "link":
                (stage / "elsewhere").symlink_to(self.root, target_is_directory=True)
            else:
                (stage / "source/ContentFixture.cs").write_text("// authored drift\n")
            with self.subTest(control=control), self.assertRaises(ValueError):
                unity.validate(stage)

    def invoke(self, stage, *, runtime="6.0.21", exit_code=0, mutate=False, invalid=False):
        def run(arguments, **kwargs):
            if arguments[-1] == "--list-runtimes":
                return SimpleNamespace(returncode=0, stdout="Microsoft.NETCore.App " + runtime + " [authored]\n", stderr="")
            self.assertEqual(kwargs["cwd"], stage)
            self.assertEqual(len([a for a in arguments if a.startswith("/r:")]), 4)
            self.assertTrue(all("AudioModule.dll" not in a for a in arguments))
            self.assertNotIn("/shared", arguments)
            self.assertNotIn(".rsp", " ".join(arguments))
            kwargs["stdout"].write("authored compiler control\n")
            for name in ("Assembly-CSharp.dll", "Assembly-CSharp.ref.dll", "Assembly-CSharp.pdb"):
                (stage / "output" / name).write_bytes(b"bad" if invalid else (b"BSJB" if name.endswith("pdb") else b"MZ") + b"authored output")
            if mutate:
                (stage / "source/ContentFixture.cs").write_text("// concurrent authored drift\n")
            return SimpleNamespace(returncode=exit_code)

        with patch.object(unity, "subprocess", SimpleNamespace(run=run, STDOUT=subprocess.STDOUT, SubprocessError=subprocess.SubprocessError)):
            return unity.compile_fixture(stage, self.launcher, "sdk")

    def test_compiler_receipt_reference_projection_and_replay_preservation(self):
        stage = self.stage()
        result = self.invoke(stage)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["reference_count"], 4)
        self.assertEqual(unity.sha(stage / "output/references.json"), result["reference_report_sha256"])
        self.assertFalse(result["player_built"])
        self.assertFalse(result["managed_game_compilation_qualified"])
        before = {p.name: unity.sha(p) for p in (stage / "output").iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, "earlier output"):
            unity.compile_fixture(stage, self.launcher, "sdk")
        self.assertEqual(before, {p.name: unity.sha(p) for p in (stage / "output").iterdir() if p.is_file()})

    def test_runtime_compiler_format_and_input_drift_failures_are_retained(self):
        for kwargs, failure in (
            (dict(runtime="10.0.12"), "runtime closure"),
            (dict(exit_code=4), "compiler failed"),
            (dict(mutate=True), "inputs changed"),
            (dict(invalid=True), "output format"),
        ):
            stage = self.stage()
            result = self.invoke(stage, **kwargs)
            with self.subTest(kwargs=kwargs):
                self.assertFalse(result["success"])
                self.assertIn(failure, result["failure"])
                self.assertEqual(result, json.loads((stage / "output/result.json").read_text()))


class ExactSdkUnityCompilerTests(unittest.TestCase):
    def test_optional_sdk_compiles_twice_with_independently_projected_references(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        if not (sdk / "NetCoreRuntime/dotnet").is_file():
            self.skipTest("Optional owner SDK absent")
        root = Path(__file__).resolve().parents[1]
        if subprocess.check_output(["git", "status", "--porcelain", "--", *unity.SOURCES], cwd=root):
            self.skipTest("Commit compiler sources before optional SDK compilation")
        with tempfile.TemporaryDirectory() as temporary:
            results = []
            for _ in range(2):
                stage, _ = unity.stage(root, sdk, Path(temporary).resolve() / "work")
                result = unity.compile_fixture(stage, sdk / "NetCoreRuntime/dotnet", "sdk")
                self.assertTrue(result["success"], (result, (stage / "output/compiler.log").read_text() if (stage / "output/compiler.log").exists() else ""))
                self.assertEqual(result["reference_count"], 157)
                report = json.loads((stage / "output/references.json").read_text())
                self.assertEqual(len(report["excluded"]), 29)
                results.append((result["outputs"], result["reference_report_sha256"]))
            self.assertEqual(results[0], results[1])


class CompilerSupportIdentityTests(unittest.TestCase):
    def test_changed_support_refuses_before_executing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            marker = directory / "must-not-exist"
            (directory / "phone_module_policy.py").write_text(
                "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('unsupported helper executed')\n"
            )
            with patch.object(unity, "__file__", str(directory / "phone_unity_compile.py")):
                with self.assertRaisesRegex(ValueError, "support drift"):
                    unity.support("phone_module_policy")
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
