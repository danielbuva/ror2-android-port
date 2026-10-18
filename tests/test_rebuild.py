"""Synthetic installation/project contracts: no Unity, device, or real-data replay."""

import contextlib
import copy
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import actions
import assembly_transforms
import rebuild
from common import RECIPE, ROOT, read, sha, write


class RebuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "clone"
        self.root.mkdir()
        self.work = self.base / "read-only-inputs"
        self.project = self.work / "lab-project"
        self.input_id = "a" * 64
        self.dest = self.root / "work/rebuild" / self.input_id / "lab-project"
        self.managed = self.base / "installation/Risk of Rain 2_Data/Managed"
        self.managed.mkdir(parents=True)
        self.recipe_root = self.root / "recipe"
        (self.recipe_root / "templates").mkdir(parents=True)
        shutil.copyfile(RECIPE / "templates/original-assembly.meta", self.recipe_root / "templates/original-assembly.meta")
        self.transforms = copy.deepcopy(assembly_transforms.load_recipe())
        self.transforms["input_id"] = self.input_id
        self.rows = []
        self.provenance = {}
        self.generated = {}
        transformed_names = {name for step in self.transforms["steps"] for name in step["inputs"]}
        for index, name in enumerate(["Original.dll", "SimpleJSON.dll", *sorted(transformed_names)]):
            source = self.managed / name
            source.write_bytes(("original " + name).encode())
            path = "Assets/Plugins/" + name
            row = dict(path=path, source=name, sha256=sha(source), guid=f"{index:032x}", time_created=123, execution_order={"Example.Component": -15})
            self.rows.append(row)
            body = ("transformed " + name).encode() if name in transformed_names else source.read_bytes()
            self.generated[name] = body
            for suffix, content in (("", body), (".meta", rebuild.importer(row))):
                target = self.project / (path + suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                producer = "export-copy" if suffix else "recipe-transform" if name in transformed_names else "unknown"
                self.provenance[path + suffix] = dict(producer=producer, sha256=sha(target), size=len(content))
        for step in self.transforms["steps"]:
            for name in step["inputs"]:
                step["inputs"][name] = sha(self.managed / name)
                step["outputs"][name] = hashlib.sha256(self.generated[name]).hexdigest()
        self.save_recipe()
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/local.json", dict(game_path=str(self.managed.parent.parent)))
        self.save_map()
        for patcher in (
            patch.object(rebuild, "ROOT", self.root),
            patch.object(rebuild, "RECIPE", self.recipe_root),
            patch.object(assembly_transforms, "load_recipe", return_value=self.transforms),
            patch.object(assembly_transforms, "generate", side_effect=self.generate),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def save_recipe(self):
        write(self.recipe_root / "original-assemblies.json", dict(schema=1, input_id=self.input_id, assemblies=self.rows))

    def save_map(self):
        write(self.work / "receipts/provenance-map.json", self.provenance)

    def generate(self, managed, temporary, recipe):
        self.assertEqual(managed, self.managed)
        self.assertTrue(temporary.is_relative_to(self.dest))
        self.assertEqual(recipe, self.transforms)
        outputs = {}
        for step in recipe["steps"]:
            for name in step["outputs"]:
                outputs[name] = temporary / name
                outputs[name].write_bytes(self.generated[name])
        return outputs

    def run_step(self, **kwargs):
        return rebuild.rebuild_step("assemblies", work=self.work, **kwargs)

    def snapshot_inputs(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for tree in (self.work, self.managed) for p in tree.rglob("*") if p.is_file()}

    def test_full_replay_default_destination_exact_membership_and_read_only_inputs(self):
        before = self.snapshot_inputs()
        result = self.run_step()
        self.assertTrue(result["equal"])
        self.assertEqual(result["counts"], dict(identical=10, different=0, missing=0, extra=0))
        self.assertEqual({p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*") if p.is_file()}, set(self.provenance))
        self.assertEqual(before, self.snapshot_inputs())
        self.assertFalse(list(self.dest.glob(".assemblies-*")))

    def test_explicit_destination(self):
        self.dest = self.root / "work/rebuild/custom/project"
        self.assertTrue(self.run_step(dest=self.dest)["equal"])

    def test_compare_only_reads_no_installation_or_recipes_and_does_not_write(self):
        self.run_step()
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.dest.rglob("*") if p.is_file()}
        with (
            patch.object(rebuild, "game", side_effect=AssertionError("must not read installation")),
            patch.object(assembly_transforms, "load_recipe", side_effect=AssertionError("must not load transform recipe")),
        ):
            self.assertTrue(self.run_step(compare_only=True)["equal"])
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.dest.rglob("*") if p.is_file()})

    def test_compare_reports_different_missing_extra_and_keeps_other_step_files(self):
        self.run_step()
        (self.dest / self.rows[0]["path"]).write_bytes(b"different")
        (self.dest / (self.rows[1]["path"] + ".meta")).unlink()
        (self.project / self.rows[2]["path"]).unlink()
        (self.dest / "Assets/Plugins/Extra.dll").write_bytes(b"extra")
        # Editor caches from R9 are not project files; a same-named Assets folder still counts.
        for cache in ("Library/Artifacts/ab/cache.bin", "Temp/UnityLockfile", "Logs/editor.log", "UserSettings/Layouts.dwlt"):
            (self.dest / cache).parent.mkdir(parents=True, exist_ok=True)
            (self.dest / cache).write_bytes(b"cache")
        other = "Assets/Other.asset"
        self.provenance[other] = dict(producer="unknown", sha256="unused", size=1)
        (self.dest / other).write_bytes(b"x")
        self.save_map()
        result = self.run_step(compare_only=True)
        self.assertFalse(result["equal"])
        self.assertEqual(result["counts"], dict(identical=7, different=1, missing=2, extra=1))
        self.assertEqual(result["different"], [self.rows[0]["path"]])
        self.assertEqual(result["extra"], ["Assets/Plugins/Extra.dll"])
        self.assertTrue(any(row["project"] for row in result["missing"]))

    def test_byte_comparison_ignores_equal_size_and_timestamp(self):
        import os

        self.run_step()
        target = self.dest / self.rows[0]["path"]
        oracle = self.project / self.rows[0]["path"]
        target.write_bytes(b"x" * oracle.stat().st_size)
        os.utime(target, ns=(oracle.stat().st_atime_ns, oracle.stat().st_mtime_ns))
        self.assertIn(self.rows[0]["path"], self.run_step(compare_only=True)["different"])

    def test_rejects_destinations_outside_rebuild_and_live_project(self):
        for dest in (self.project, self.root / "work/lab-project", self.base / "outside", self.root / "work/rebuild"):
            with self.subTest(dest=dest), self.assertRaisesRegex(RuntimeError, "Destination must"):
                self.run_step(dest=dest)

    def test_rejects_rebuild_root_redirect_and_destination_symlinks(self):
        (self.root / "work").mkdir()
        (self.root / "work/rebuild").symlink_to(self.work, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "must not redirect"):
            self.run_step()
        (self.root / "work/rebuild").unlink()
        self.dest.parent.mkdir(parents=True)
        self.dest.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.run_step()

    def test_rejects_nested_symlinks_and_hardlinks_before_writes(self):
        import os

        self.dest.mkdir(parents=True)
        link = self.dest / "redirect"
        link.symlink_to(self.project, target_is_directory=True)
        before = self.snapshot_inputs()
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.run_step()
        link.unlink()
        os.link(self.managed / "Original.dll", link)
        with self.assertRaisesRegex(RuntimeError, "hard-linked"):
            self.run_step()
        self.assertEqual(before, self.snapshot_inputs())

    def test_source_drift_stops_before_transform_or_project_placement(self):
        (self.managed / "Original.dll").write_bytes(b"drift")
        with patch.object(assembly_transforms, "generate") as generate, self.assertRaisesRegex(RuntimeError, "Original assembly drift"):
            self.run_step()
        generate.assert_not_called()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_recipe_membership_duplicate_paths_and_sources_fail(self):
        original = copy.deepcopy(self.rows)
        for rows in (original[:-1], original + [original[0]], [dict(original[0], source="Other.dll"), *original[1:]]):
            self.rows = rows
            self.save_recipe()
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                self.run_step()

    def test_input_mismatch_and_transform_input_drift_fail(self):
        write(self.work / "config/accepted-input.json", dict(input_id="b" * 64))
        with self.assertRaisesRegex(RuntimeError, "accepted input"):
            self.run_step()
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        self.transforms["steps"][0]["inputs"]["RoR2.dll"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "transform input"):
            self.run_step()

    def test_meta_or_transformed_drift_fails_before_placing_any_files_and_cleans_scratch(self):
        self.rows[0]["guid"] = "f" * 32
        self.save_recipe()
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.run_step()
        self.assertEqual(list(self.dest.iterdir()), [])
        self.rows[0]["guid"] = "0" * 32
        self.save_recipe()
        self.generated["RoR2.dll"] = b"wrong transformed bytes"
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.run_step()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_tool_failure_cleans_destination_scratch(self):
        with patch.object(assembly_transforms, "generate", side_effect=RuntimeError("tool failed")), self.assertRaisesRegex(RuntimeError, "tool failed"):
            self.run_step()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_unsafe_map_path_rejected_before_writes(self):
        for path in ("../escape.dll", "/absolute.dll", "Assets/../escape.dll", "Assets\\escape.dll"):
            self.provenance = {path: dict(producer="unknown")}
            self.save_map()
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "Unsafe project path"):
                self.run_step()
        self.assertFalse(self.dest.exists())

    def test_unknown_empty_step_and_missing_compare_destination_fail(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown rebuild step"):
            rebuild.rebuild_step("unregistered", work=self.work)
        with self.assertRaisesRegex(RuntimeError, "existing destination"):
            self.run_step(compare_only=True)
        self.provenance = {}
        self.save_map()
        with self.assertRaisesRegex(RuntimeError, "No provenance paths"):
            self.run_step()

    def test_action_forwards_arguments_and_returns_failure_exit(self):
        self.assertEqual(actions.ACTIONS["rebuild-step"].status, "current")
        args = SimpleNamespace(action="rebuild-step", step="assemblies", dest="destination", compare_only=True, work_dir="inputs")
        with patch.object(rebuild, "rebuild_action") as function:
            actions.dispatch(args)
        function.assert_called_once_with(step="assemblies", dest="destination", compare_only=True, work="inputs")
        with (
            patch.object(rebuild, "rebuild_step", return_value=dict(equal=False)),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            rebuild.rebuild_action("assemblies")
        self.assertEqual(error.exception.code, 1)


class TrackedAssemblyRecipeTests(unittest.TestCase):
    def test_recipe_has_49_unique_installation_dlls_and_98_output_paths(self):
        recipe = read(RECIPE / "original-assemblies.json")
        rows = recipe["assemblies"]
        self.assertEqual(len(rows), 49)
        self.assertEqual(len({row["path"] + suffix for row in rows for suffix in ("", ".meta")}), 98)
        self.assertEqual(len({row["guid"] for row in rows}), 49)
        self.assertIn("SimpleJSON.dll", [row["source"] for row in rows])
        for row in rows:
            self.assertEqual(Path(row["path"]).name, row["source"])
            self.assertIn(b"validateReferences: 0", rebuild.importer(row))
            self.assertEqual(set(row), {"path", "source", "sha256", "guid", "time_created", "execution_order"})

    def test_cli_requires_step_and_scopes_new_flags(self):
        main = ROOT / "scripts/lab/main.py"
        for args in (("prototype", "--action", "rebuild-step"), ("inspect", "--step", "assemblies"), ("inspect", "--compare-only")):
            result = subprocess.run([sys.executable, str(main), *args], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"require", result.stderr)
