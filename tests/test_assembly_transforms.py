"""Synthetic replay contracts; dotnet/AssemblyProbe are mocked, no editor or device."""

import contextlib
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
import assembly_transforms as transforms
from common import sha, write


class AssemblyTransformsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "clone"
        self.root.mkdir()
        tool = self.root / "tools/assembly-transforms"
        (tool / "obj").mkdir(parents=True)
        (tool / "AssemblyProbe.csproj").write_text("<Project />")
        (tool / "obj/Stale.AssemblyInfo.cs").write_text("// stale build output")
        self.work = self.base / "work"
        self.managed = self.base / "game/Risk of Rain 2_Data/Managed"
        self.managed.mkdir(parents=True)
        self.recipe = copy.deepcopy(transforms.load_recipe())
        self.generated = {}
        originals = {}
        outputs = {}
        for step in self.recipe["steps"]:
            for name in step["inputs"]:
                source = self.managed / name
                source.write_bytes(("synthetic original " + name).encode())
                originals[name] = step["inputs"][name] = sha(source)
                self.generated[name] = ("synthetic transform " + name).encode()
                target = self.work / "lab-project/Assets/Plugins" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self.generated[name])
                outputs[name] = step["outputs"][name] = sha(target)
        self.generation = dict(input_id=self.recipe["input_id"], original_assemblies=originals, transformed_assemblies=outputs)
        write(self.work / "lab-project/.port-input.json", self.generation)
        write(self.work / "config/accepted-input.json", {"input_id": self.recipe["input_id"]})
        write(self.work / "config/local.json", {"game_path": str(self.managed.parent.parent)})
        editor = self.base / "editor/Contents/MacOS/Unity"
        cecil = editor.parent.parent / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        cecil.parent.mkdir(parents=True)
        cecil.write_bytes(b"synthetic Cecil")
        self.recipe["cecil_sha256"] = sha(cecil)
        for patcher in (
            patch.object(transforms, "ROOT", self.root),
            patch.object(transforms, "load_recipe", return_value=self.recipe),
            patch.dict(os.environ, UNITY_EDITOR=str(editor)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.calls = []
        self.tool_failure = False
        self.drift = False

    def run_tool(self, command, **kwargs):
        self.calls.append(command)
        self.assertEqual(kwargs["timeout"], 120)
        temporary = Path(kwargs["cwd"])
        self.assertTrue(temporary.is_relative_to(self.root / ".local"))
        for key in ("DOTNET_CLI_HOME", "NUGET_PACKAGES", "NUGET_HTTP_CACHE_PATH", "NUGET_PLUGINS_CACHE_PATH", "TMPDIR", "TMP", "TEMP"):
            self.assertTrue(Path(kwargs["env"][key]).is_relative_to(temporary))
        if command[1] == "build":
            # The tool is built from an isolated source copy without the checkout's obj/ and bin/.
            source = Path(command[2]).parent
            self.assertNotEqual(source, self.root / "tools/assembly-transforms")
            self.assertTrue((source / "AssemblyProbe.csproj").is_file())
            self.assertFalse((source / "obj").exists())
            config = "-p:RestoreConfigFile=" + str(temporary / "NuGet.Config")
            self.assertIn(config, command)
            self.assertIn("<clear />", (temporary / "NuGet.Config").read_text())
        else:
            if self.tool_failure:
                raise RuntimeError("synthetic tool failure")
            mode = command[2]
            self.assertEqual(len(command[3:]), 3 * len(transforms.MODES[mode]) + 1)
            for index, name in enumerate(transforms.MODES[mode]):
                source, output, expected = command[3 + index * 3 : 6 + index * 3]
                self.assertEqual(sha(source), expected)
                self.assertEqual(Path(source).parent, command[-1])
                self.assertTrue(Path(output).is_relative_to(self.root / ".local"))
                Path(output).write_bytes(b"drift" if self.drift else self.generated[name])
        return SimpleNamespace(stdout=b"{}")

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for tree in (self.work, self.managed) for p in tree.rglob("*") if p.is_file()}

    def check(self):
        with patch.object(transforms, "run", side_effect=self.run_tool):
            return transforms.check(self.work)

    def test_replays_order_arguments_hashes_without_input_writes_and_cleans_scratch(self):
        before = self.snapshot()
        self.assertEqual(self.check(), {"checked": 3, "differences": []})
        self.assertEqual([command[2] for command in self.calls[1:]], list(transforms.MODES))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list((self.root / ".local").iterdir()), [])

    def test_first_rebuilt_difference_stops_before_next_transform(self):
        self.drift = True
        result = self.check()
        self.assertEqual(result["differences"][0]["assembly"], "RoR2.dll")
        self.assertEqual(result["differences"][0]["reason"], "rebuilt_sha256")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(list((self.root / ".local").iterdir()), [])

    def test_project_hash_and_duplicate_placement_fail(self):
        project = self.work / "lab-project/Assets"
        (project / "Plugins/RoR2.dll").write_bytes(b"drift")
        (project / "duplicate").mkdir()
        (project / "duplicate/AK.Wwise.Unity.API.dll").write_bytes(b"duplicate")
        reasons = {row["reason"] for row in self.check()["differences"]}
        self.assertEqual(reasons, {"project_sha256", "project_placement"})

    def test_original_drift_prevents_tool_calls(self):
        (self.managed / "RoR2.dll").write_bytes(b"drift")
        with self.assertRaisesRegex(RuntimeError, "Original assembly drift"):
            self.check()
        self.assertEqual(self.calls, [])

    def test_input_generation_and_membership_drift_prevent_tool_calls(self):
        for mutation in ("input_id", "transformed_assemblies", "original_assemblies"):
            with self.subTest(mutation=mutation):
                generation = copy.deepcopy(self.generation)
                generation[mutation] = "wrong" if mutation == "input_id" else {}
                write(self.work / "lab-project/.port-input.json", generation)
                with self.assertRaises(RuntimeError):
                    self.check()
        self.assertEqual(self.calls, [])

    def test_cecil_drift_prevents_tool_calls(self):
        self.recipe["cecil_sha256"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "Mono.Cecil drift"):
            self.check()
        self.assertEqual(self.calls, [])

    def test_tool_failure_cleans_scratch(self):
        self.tool_failure = True
        with self.assertRaisesRegex(RuntimeError, "synthetic tool failure"):
            self.check()
        self.assertEqual(list((self.root / ".local").iterdir()), [])

    def test_scratch_symlink_cannot_redirect_writes_into_work(self):
        (self.root / ".local").symlink_to(self.work, target_is_directory=True)
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "scratch must be inside this clone"):
            self.check()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls, [])

    def test_current_action_forwards_work_and_propagates_failure(self):
        self.assertEqual(actions.ACTIONS["assembly-transforms-check"].status, "current")
        with patch.object(transforms, "check_action") as mocked:
            actions.dispatch(SimpleNamespace(action="assembly-transforms-check", work_dir=str(self.work)))
            mocked.assert_called_once_with(work=str(self.work))
        with patch.object(transforms, "check", return_value={"checked": 3, "differences": ["drift"]}), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ended:
                transforms.check_action(self.work)
            self.assertEqual(ended.exception.code, 1)


class RecipeTests(unittest.TestCase):
    def test_recipe_matches_current_tool_sources(self):
        self.assertEqual(len(transforms.load_recipe()["steps"]), 2)

    def test_source_argument_and_sequence_drift_fail_closed(self):
        recipe = transforms.load_recipe()
        for key in ("tool_sources", "arguments", "mode"):
            changed = copy.deepcopy(recipe)
            if key == "tool_sources":
                changed[key] = {}
            else:
                changed["steps"][0][key] = [] if key == "arguments" else "--audio-guard"
            with self.subTest(key=key), patch.object(transforms, "read", return_value=changed), self.assertRaises(RuntimeError):
                transforms.load_recipe()
