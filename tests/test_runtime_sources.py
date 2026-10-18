import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import build
import common
from common import write


class RuntimeManifestTests(unittest.TestCase):
    def setUp(self):
        self.names = json.loads((ROOT / "recipe/runtime-sources.json").read_text())

    def test_manifest_is_sorted(self):
        self.assertTrue(self.names)
        self.assertEqual(self.names, sorted(self.names))

    def test_manifest_is_unique(self):
        self.assertEqual(len(self.names), len(set(self.names)))

    def test_every_entry_is_an_existing_tools_unity_source(self):
        for name in self.names:
            with self.subTest(source=name):
                self.assertFalse(Path(name).is_absolute())
                self.assertNotIn("..", Path(name).parts)
                self.assertTrue(name.endswith(".cs"))
                self.assertTrue((ROOT / "tools/unity" / name).is_file())
        self.assertEqual(build.runtime_sources(), self.names)

    def test_player_inputs_do_not_depend_on_work_at_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / "empty"
            empty.mkdir()
            populated = root / "populated"
            stage = populated / "lab-project/Assets/LabLoadingScene"
            stage.mkdir(parents=True)
            for source in (ROOT / "tools/unity").rglob("*.cs"):
                (stage / source.name).touch()
            with patch.object(common, "WORK", populated):
                populated_inputs = runpy.run_path(str(ROOT / "scripts/lab/build.py"))["WHOLE_PLAYER_INPUTS"]
            with patch.object(common, "WORK", empty):
                empty_inputs = runpy.run_path(str(ROOT / "scripts/lab/build.py"))["WHOLE_PLAYER_INPUTS"]
            self.assertEqual(populated_inputs, empty_inputs)
            self.assertEqual(empty_inputs, build.WHOLE_PLAYER_INPUTS)

    def test_authored_and_generated_sources_keep_their_meta_exemptions(self):
        expected = {Path(name).name for name in self.names} | build.WHOLE_GENERATED_RUNTIME_SOURCES
        actual = {Path(path).name for path in build.WHOLE_PLAYER_INPUTS if path.startswith("Assets/LabLoadingScene/") and path.endswith(".cs")}
        self.assertEqual(actual, expected)
        for name in expected:
            self.assertIn("Assets/LabLoadingScene/" + name + ".meta", build.WHOLE_PLAYER_INPUTS)


class RuntimeMembershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.project = self.work / "lab-project"
        self.stage = self.project / "Assets/LabLoadingScene"
        self.stage.mkdir(parents=True)
        self.source = self.root / "tools/unity/runtime/session/Fixture.cs"
        self.source.parent.mkdir(parents=True)
        self.relative_source = self.source.relative_to(self.root / "tools/unity").as_posix()
        self.source.write_text("authored fixture")
        write(self.root / "recipe/runtime-sources.json", [self.relative_source])
        write(
            self.root / "recipe/project-layout.json",
            {"runtime_source_guids": {self.relative_source: "a" * 32}, "dependencies": {"com.unity.ugui": "1.0.0"}},
        )
        (self.stage / "Fixture.cs.meta").write_text("guid: " + "a" * 32 + "\n")
        write(self.project / "Packages/manifest.json", {"dependencies": {"com.unity.ugui": "1.0.0"}})
        write(self.work / "whole-catalog-build.json", {})
        for name, value in [("ROOT", self.root), ("RECIPE", self.root / "recipe"), ("WORK", self.work)]:
            patcher = patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_manifest_source_fails_before_staging(self):
        self.source.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing from tools/unity: runtime/session/Fixture.cs"):
            build.validate_runtime_source_membership(self.project)

    def test_unlisted_staged_authored_source_is_rejected(self):
        (self.source.parent / "Unlisted.cs").write_text("unselected authored source")
        (self.stage / "Unlisted.cs").write_text("previously staged source")
        with self.assertRaisesRegex(RuntimeError, "Unlisted whole-catalog C# sources.*Unlisted.cs"):
            build.validate_staged_runtime_sources(self.project)

    def test_unlisted_nested_source_is_rejected(self):
        nested = self.stage / "Nested/Unowned.cs"
        nested.parent.mkdir()
        nested.write_text("fixture")
        with self.assertRaisesRegex(RuntimeError, "Unlisted whole-catalog C# sources.*Nested/Unowned.cs"):
            build.validate_runtime_source_membership(self.project)

    def test_generated_visual_maps_are_allowed(self):
        for name in build.WHOLE_GENERATED_RUNTIME_SOURCES:
            (self.stage / name).write_text("generated fixture")
        self.assertEqual(build.validate_runtime_source_membership(self.project), [self.relative_source])

    def test_basename_collisions_are_rejected_before_staging(self):
        duplicate = self.root / "tools/unity/runtime/world/Fixture.cs"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_text("different authored fixture")
        write(self.root / "recipe/runtime-sources.json", sorted([self.relative_source, "runtime/world/Fixture.cs"]))
        with self.assertRaisesRegex(RuntimeError, "basename collision"):
            build.validate_runtime_source_membership(self.project)
        self.assertEqual(list(self.stage.glob("*.cs")), [])

    def test_generated_source_basename_collision_is_rejected(self):
        write(self.root / "recipe/runtime-sources.json", ["runtime/session/OriginalBodyVisualMap.cs"])
        with self.assertRaisesRegex(RuntimeError, "basename collision"):
            build.runtime_sources()

    def test_relative_source_is_staged_flat_and_compared_by_bytes(self):
        staged = self.stage / self.source.name
        staged.write_bytes(self.source.read_bytes())
        build.validate_staged_runtime_sources(self.project)
        staged.write_text("stale fixture")
        with self.assertRaisesRegex(RuntimeError, "not staged"):
            build.validate_staged_runtime_sources(self.project)

    def test_missing_staged_manifest_source_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not staged: runtime/session/Fixture.cs.*whole-catalog-code-build"):
            build.validate_staged_runtime_sources(self.project)

    def test_manifest_reader_rejects_unsorted_duplicate_or_invalid_entries(self):
        for names in [
            ["Z.cs", "A.cs"],
            ["Fixture.cs", "Fixture.cs"],
            ["../Fixture.cs"],
            ["Fixture.shader"],
            ["/Fixture.cs"],
            ["runtime/../Fixture.cs"],
            ["runtime\\Fixture.cs"],
            {},
        ]:
            with self.subTest(names=names):
                write(self.root / "recipe/runtime-sources.json", names)
                with self.assertRaisesRegex(RuntimeError, "recipe/runtime-sources.json"):
                    build.runtime_sources()


if __name__ == "__main__":
    unittest.main()
