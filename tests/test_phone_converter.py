import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from phone_converter import FLAGS, OUTPUTS, STRIPPED, arguments, bounded, convert, stage


class PhoneConverterTests(unittest.TestCase):
    def command(self, project, launcher):
        return shlex.join(
            [
                str(launcher),
                "--convert-to-cpp",
                "--assembly=" + STRIPPED + "/Second.dll",
                "--assembly=" + STRIPPED + "/First.dll",
                *sorted(FLAGS - {"--convert-to-cpp"}),
                "--enable-analytics",
                *(key + "=" + str(project / value) for key, value in OUTPUTS.items()),
            ]
        )

    def test_actual_argument_shape_preserves_assembly_order_and_codegen_flags(self):
        project, launcher = Path("/fixture"), Path("/sdk/il2cpp")
        command = self.command(project, launcher)
        plan, assemblies = arguments(command, project, launcher)
        self.assertEqual(assemblies, [STRIPPED + "/Second.dll", STRIPPED + "/First.dll"])
        self.assertEqual({item for item in plan if isinstance(item, str)}, FLAGS)
        self.assertNotIn("--enable-analytics", plan)
        for mutant in (
            command + " --unknown-option",
            command + " --emit-null-checks",
            command.replace("--emit-null-checks", ""),
            command.replace("Second.dll", "First.dll"),
            command.replace("Second.dll", "../foreign.dll"),
            command.replace("/fixture/cpp", "/foreign/cpp"),
            command.replace(str(launcher), "/foreign/il2cpp"),
        ):
            with self.subTest(mutant=mutant), self.assertRaises(ValueError):
                arguments(mutant, project, launcher)

    def test_paths_refuse_symlink_escape_and_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "owned").mkdir()
            (root / "owned/link").symlink_to(root, target_is_directory=True)
            for path in ("../outside", "/outside", "link/outside"):
                with self.assertRaises(ValueError):
                    bounded(root / "owned", path)

    def test_stage_copies_full_closure_unchanged_and_refuses_unlisted_assembly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, sdk, output = root / "project", root / "sdk", root / "stage"
            stripped = project / STRIPPED
            stripped.mkdir(parents=True)
            for name in ("First.dll", "Second.dll", "First.pdb"):
                (stripped / name).write_bytes(b"supplied fixture " + name.encode())
            launcher = sdk / "il2cpp/build/deploy/il2cpp"
            launcher.parent.mkdir(parents=True)
            (launcher.parent / "il2cpp.dll").write_bytes(b"supplied tool")
            (sdk / "il2cpp/libil2cpp").mkdir()
            (sdk / "il2cpp/libil2cpp/libil2cpp.icalls").write_bytes(b"supplied icalls")
            graph = project / "Library/Bee/Player.dag.json"
            graph.write_text(json.dumps({"Nodes": [{"Annotation": "IL2CPP_CodeGen fixture", "Action": self.command(project, launcher)}]}))
            result = stage(project, sdk, output)
            self.assertEqual(result["assemblies"], 2)
            self.assertEqual((output / "project" / STRIPPED / "First.pdb").read_bytes(), (stripped / "First.pdb").read_bytes())
            self.assertEqual((output / "support/libil2cpp/libil2cpp.icalls").read_bytes(), b"supplied icalls")
            manifest = json.loads((output / "input-manifest.json").read_text())
            for relative, expected in manifest.items():
                self.assertEqual(hashlib.sha256((output / relative).read_bytes()).hexdigest(), expected)
            with self.assertRaises(FileExistsError):
                stage(project, sdk, output)
            (stripped / "Unexpected.dll").write_bytes(b"unlisted")
            with self.assertRaisesRegex(ValueError, "closure differs"):
                stage(project, sdk, root / "another")

    def test_drift_refuses_before_tool_execution_and_preserves_first_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "stage"
            fixture.mkdir()
            (fixture / "input.dll").write_bytes(b"changed")
            (fixture / "input-manifest.json").write_text(json.dumps({"input.dll": hashlib.sha256(b"expected").hexdigest()}))
            with patch("phone_converter.subprocess.run") as run:
                self.assertFalse(convert(fixture, root / "tools", root / "output"))
                run.assert_not_called()
            self.assertIn("input drift", json.loads((root / "output/result.json").read_text())["failure"])
            with self.assertRaises(FileExistsError):
                convert(fixture, root / "tools", root / "output")

    def test_success_requires_cpp_and_metadata_and_keeps_relative_assembly_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fixture, output = root / "stage", root / "output"
            (fixture / "project").mkdir(parents=True)
            plan = {
                "arguments": [
                    "--convert-to-cpp",
                    {"input": STRIPPED + "/First.dll", "prefix": "--assembly="},
                    {"output": "cpp", "prefix": "--generatedcppdir="},
                    {"output": "data", "prefix": "--data-folder="},
                ],
                "game_inputs": False,
                "desktop_stripping_inputs": True,
            }
            (fixture / "plan.json").write_text(json.dumps(plan))
            (fixture / "input-manifest.json").write_text(json.dumps({"plan.json": hashlib.sha256((fixture / "plan.json").read_bytes()).hexdigest()}))

            def execute(argv, **kwargs):
                self.assertIn("--assembly=" + STRIPPED + "/First.dll", argv)
                self.assertEqual(kwargs["cwd"], fixture / "project")
                self.assertEqual(kwargs["env"]["DOTNET_CLI_TELEMETRY_OPTOUT"], "1")
                self.assertEqual(kwargs["env"]["IL2CPP_TESTHARNESS_SOLUTION_DIRECTORY"], str(fixture / "support"))
                (output / "cpp").mkdir()
                (output / "cpp/code.cpp").write_bytes(b"fixture native source")
                (output / "data").mkdir()
                (output / "data/global-metadata.dat").write_bytes(b"fixture metadata")
                return type("Result", (), {"returncode": 0})()

            with patch("phone_converter.subprocess.run", side_effect=execute):
                self.assertTrue(convert(fixture, root / "tools", output))
            self.assertEqual(len(json.loads((output / "result.json").read_text())["outputs"]), 2)
            output = root / "incomplete"
            with patch("phone_converter.subprocess.run", return_value=type("Result", (), {"returncode": 0})()):
                self.assertFalse(convert(fixture, root / "tools", output))
            self.assertIn("no complete", json.loads((output / "result.json").read_text())["failure"])
