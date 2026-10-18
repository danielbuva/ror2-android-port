"""Public content recipe contracts; synthetic work only, never reads shared work/."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import build
from common import write


class ContentRecipeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.recipe_path = self.root / "recipe/content.json"
        self.work = self.root / "work"
        self.staged_path = self.work / "scene-probe-build.json"
        self.recipe = {"scene": "Assets/Fixture.unity", "prefabAssets": ["Assets/First.prefab", "assets/second.asset"], "empty": ""}
        write(self.recipe_path, self.recipe)
        write(self.staged_path, self.recipe)
        for name, value in [("RECIPE", self.recipe_path.parent), ("WORK", self.work)]:
            patcher = patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_equal_passes_without_writing(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        build.validate_content_recipe()
        after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_changed_key_fails_without_disclosing_values_or_writing(self):
        write(self.staged_path, dict(self.recipe, scene="private fixture value"))
        before = self.staged_path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "differs from recipe/content.json; changed keys: scene") as caught:
            build.validate_content_recipe()
        self.assertNotIn("private fixture value", str(caught.exception))
        self.assertEqual(self.staged_path.read_bytes(), before)

    def test_missing_key_fails_even_for_empty_value(self):
        write(self.staged_path, {key: value for key, value in self.recipe.items() if key != "empty"})
        with self.assertRaisesRegex(RuntimeError, "missing keys: empty"):
            build.validate_content_recipe()

    def test_extra_local_keys_pass(self):
        write(self.staged_path, dict(self.recipe, obsolete=True, localOnly={"any": [None, 4]}))
        build.validate_content_recipe()

    def test_array_order_case_membership_and_types_are_preserved(self):
        for assets in [list(reversed(self.recipe["prefabAssets"])), ["assets/first.prefab", "assets/second.asset"], [], "Assets/First.prefab"]:
            with self.subTest(assets=assets):
                write(self.staged_path, dict(self.recipe, prefabAssets=assets))
                with self.assertRaisesRegex(RuntimeError, "changed keys: prefabAssets"):
                    build.validate_content_recipe()

    def test_strict_nested_types_and_membership(self):
        write(self.recipe_path, {"fixture": {"flag": True, "count": 3}})
        for fixture in [{"flag": 1, "count": 3}, {"flag": True, "count": 3.0}, {"flag": True, "count": 3, "extra": 0}]:
            with self.subTest(fixture=fixture):
                write(self.staged_path, {"fixture": fixture})
                with self.assertRaisesRegex(RuntimeError, "changed keys: fixture"):
                    build.validate_content_recipe()

    def test_missing_invalid_or_non_object_work_recipe_fails(self):
        self.staged_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Content recipe cannot read work/scene-probe-build.json"):
            build.validate_content_recipe()
        self.staged_path.write_text("invalid JSON")
        with self.assertRaisesRegex(RuntimeError, "cannot read"):
            build.validate_content_recipe()
        write(self.staged_path, [])
        with self.assertRaisesRegex(RuntimeError, "must contain an object"):
            build.validate_content_recipe()

    def test_missing_invalid_or_empty_public_recipe_fails(self):
        self.recipe_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Cannot read recipe/content.json"):
            build.validate_content_recipe()
        self.recipe_path.write_text("invalid JSON")
        with self.assertRaisesRegex(RuntimeError, "Cannot read recipe/content.json"):
            build.validate_content_recipe()
        for value in [[], {}]:
            write(self.recipe_path, value)
            with self.assertRaisesRegex(RuntimeError, "must contain a nonempty object"):
                build.validate_content_recipe()

    def test_whole_catalog_checks_content_after_runtime_config(self):
        project = self.root / "project"
        write(self.work / "whole-catalog-build.json", {})
        self.staged_path.unlink()
        calls = []
        with (
            patch.object(build, "validate_runtime_source_membership", return_value=[]),
            patch.object(build, "validate_project_layout", side_effect=lambda _: calls.append("layout")),
            patch.object(build, "validate_runtime_config", side_effect=lambda _: calls.append("runtime")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Content recipe cannot read"):
                build.validate_staged_runtime_sources(project)
        self.assertEqual(calls, ["layout", "runtime"])

    def test_non_whole_catalog_skips_validation(self):
        self.staged_path.unlink()
        with patch.object(build, "validate_content_recipe") as validate:
            build.validate_staged_runtime_sources(self.root / "project")
        validate.assert_not_called()


class TrackedContentRecipeTests(unittest.TestCase):
    def test_exact_present_build_fields_and_selector_shapes(self):
        recipe = json.loads((ROOT / "recipe/content.json").read_text())
        scalar_fields = {
            "genericPickup",
            "objectiveTMPSettings",
            "pickupDroplet",
            "playerDeathEffect",
            "prefab",
            "scene",
            "stageScene",
            "teleportMaterial",
            "teleporterIndicator",
        }
        list_counts = {"enemyRewardAssets": 5, "nextStageScenes": 23, "objectiveSupportAssets": 60, "prefabAssets": 4184, "sourceStageScenes": 23}
        self.assertEqual(recipe.keys(), scalar_fields | list_counts.keys())
        # Check use sites in the current bundle builder, not just its schema.
        builder = (ROOT / "android/Assets/Editor/LabBuild.cs").read_text()
        body = builder[builder.index("public static void Build()") : builder.index("[Serializable] class SceneProbeConfig")]
        self.assertLessEqual(recipe.keys(), set(re.findall(r"\bcfg\.(\w+)", body)))
        for key in scalar_fields:
            self.assertIsInstance(recipe[key], str)
        for key, count in list_counts.items():
            self.assertIsInstance(recipe[key], list)
            self.assertEqual(len(recipe[key]), count)
        for value in recipe.values():
            for path in value if isinstance(value, list) else [value]:
                self.assertIsInstance(path, str)
                self.assertTrue(path.casefold().startswith("assets/"))
                self.assertNotIn("..", Path(path).parts)
                self.assertNotRegex(path, r"[\\\n\r]|\d{8}T\d{6}|https?://")

    def test_recipe_is_sorted_and_below_size_limit(self):
        def check(pairs):
            keys = [key for key, _ in pairs]
            self.assertEqual(keys, sorted(set(keys)))
            return dict(pairs)

        path = ROOT / "recipe/content.json"
        json.loads(path.read_text(), object_pairs_hook=check)
        self.assertLess(path.stat().st_size, 5_000_000)


if __name__ == "__main__":
    unittest.main()
