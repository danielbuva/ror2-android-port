import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_managed_compile as compiler


class ManagedCompilerContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in (compiler.SOURCE, compiler.FIXTURE):
            source = Path(__file__).resolve().parents[1] / name
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: authored fixture"], cwd=self.root, check=True)
        self.sdk = self.root / "owner-sdk"
        binary = self.sdk / "MacOS/Unity"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"authored SDK binary substitute")
        inputs = {}
        for name, (source, _) in compiler.INPUTS.items():
            path = self.sdk / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("authored " + name).encode())
            inputs[name] = (source, compiler.sha(path))
        for change in (patch.object(compiler, "INPUTS", inputs), patch.object(compiler, "SDK_BINARY_SHA256", compiler.sha(binary))):
            change.start()
            self.addCleanup(change.stop)
        self.work = self.root / "work"
        self.launcher = self.root / "authored-dotnet"
        self.launcher.write_bytes(b"non-executable authored launcher substitute")

    def stage(self):
        return compiler.stage(self.root, self.sdk, self.work)[0]

    def test_staging_binds_only_authored_fixture_and_exact_compiler_components(self):
        stage = self.stage()
        receipt = compiler.validate(stage)
        self.assertFalse(receipt["game_inputs"])
        self.assertEqual(set(receipt["inputs"]), set(compiler.INPUTS) | {"source/ConverterFixture.cs", "phone_managed_compile.py"})
        self.assertEqual((stage / "compiler/csc.runtimeconfig.json").read_bytes(), (self.sdk / "DotNetSdkRoslyn/csc.runtimeconfig.json").read_bytes())
        self.assertTrue(stage.is_relative_to(self.work / "rebuild/phone-managed-compile"))

    def test_unknown_sdk_component_or_uncommitted_source_refuses_before_write(self):
        component = self.sdk / next(iter(compiler.INPUTS.values()))[0]
        original = component.read_bytes()
        component.write_bytes(b"authored drift control")
        with self.assertRaisesRegex(ValueError, "component drift"):
            self.stage()
        self.assertFalse(self.work.exists())
        component.write_bytes(original)
        (self.root / compiler.SOURCE).write_text("# source drift\n")
        with self.assertRaisesRegex(ValueError, "Commit compiler"):
            self.stage()
        self.assertFalse(self.work.exists())

    def test_ancestor_links_and_staged_input_foreign_files_or_drift_refuse(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.work.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ancestor links"):
            self.stage()
        self.assertEqual(list(outside.iterdir()), [])
        self.work.unlink()
        for change in ("foreign", "drift", "link"):
            stage = self.stage()
            if change == "foreign":
                (stage / "foreign.dll").write_bytes(b"authored foreign control")
            elif change == "drift":
                (stage / "source/ConverterFixture.cs").write_bytes(b"authored drift")
            else:
                (stage / "outside").symlink_to(outside, target_is_directory=True)
            with self.subTest(change=change), self.assertRaises(ValueError):
                compiler.validate(stage)

    def invoke(self, stage, *, runtime="6.0.21", exit_code=0, tamper=False, invalid_outputs=False):
        def run(arguments, **kwargs):
            if arguments[-1] == "--list-runtimes":
                return SimpleNamespace(returncode=0, stdout="Microsoft.NETCore.App " + runtime + " [authored]\n", stderr="")
            self.assertEqual(arguments, compiler.arguments(stage, self.launcher))
            self.assertEqual(kwargs["cwd"], stage)
            self.assertNotIn("/shared", arguments)
            if tamper:
                (stage / "compiler/csc.dll").write_bytes(b"authored concurrent drift")
            (stage / "output/CompilerFixture.dll").write_bytes(b"invalid" if invalid_outputs else b"MZauthored PE format control")
            (stage / "output/CompilerFixture.pdb").write_bytes(b"BSJBauthored portable PDB control")
            kwargs["stdout"].write("authored compiler log\n")
            return SimpleNamespace(returncode=exit_code)

        proxy = SimpleNamespace(run=run, SubprocessError=subprocess.SubprocessError, STDOUT=subprocess.STDOUT)
        with patch.object(compiler, "subprocess", proxy):
            return compiler.compile_fixture(stage, self.launcher, "sdk")

    def test_checked_compilation_records_runtime_outputs_and_refuses_replay(self):
        stage = self.stage()
        result = self.invoke(stage)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["runtime"], "6.0.21")
        self.assertFalse(result["player_built"])
        self.assertFalse(result["managed_game_compilation_qualified"])
        self.assertEqual(set(result["outputs"]), {"CompilerFixture.dll", "CompilerFixture.pdb"})
        self.assertIn("/pathmap:" + str(stage) + "=/owner-build", result["arguments"])
        with self.assertRaisesRegex(ValueError, "earlier output"):
            compiler.compile_fixture(stage, self.launcher, "sdk")

    def test_runtime_child_format_and_post_compile_drift_failures_are_retained(self):
        for kwargs, message in [
            (dict(runtime="10.0.12"), "runtime closure"),
            (dict(exit_code=7), "fixture failed"),
            (dict(tamper=True), "inputs changed"),
            (dict(invalid_outputs=True), "formats differ"),
        ]:
            stage = self.stage()
            result = self.invoke(stage, **kwargs)
            with self.subTest(kwargs=kwargs):
                self.assertFalse(result["success"])
                self.assertIn(message, result["failure"])
                self.assertEqual(json.loads((stage / "output/result.json").read_text()), result)


class ExactManagedCompilerTests(unittest.TestCase):
    def test_pinned_sdk_compiler_produces_equal_outputs_in_two_fresh_owned_stages(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        if not (sdk / "NetCoreRuntime/dotnet").is_file():
            self.skipTest("Optional owner SDK absent")
        root = Path(__file__).resolve().parents[1]
        if subprocess.check_output(["git", "status", "--porcelain", "--", compiler.SOURCE, compiler.FIXTURE], cwd=root):
            self.skipTest("Commit compiler sources before optional SDK compilation")
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve() / "work"
            results = []
            for _ in range(2):
                stage, _ = compiler.stage(root, sdk, work)
                result = compiler.compile_fixture(stage, sdk / "NetCoreRuntime/dotnet", "sdk")
                self.assertTrue(result["success"], (result, (stage / "output/compiler.log").read_text() if (stage / "output/compiler.log").exists() else ""))
                results.append(result["outputs"])
            self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
