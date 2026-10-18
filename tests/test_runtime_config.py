"""Public runtime recipe contracts; synthetic projects only, never reads work/."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_session_config import PROBE, fields

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import build
from common import write


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.recipe_path = self.root / "recipe/runtime-config.json"
        self.config_path = self.project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
        self.recipe = {"enabled": True, "count": 3, "actors": [{"path": "Assets/Fixture.prefab", "active": False}], "empty": ""}
        write(self.recipe_path, self.recipe)
        write(self.config_path, self.recipe)
        patcher = patch.object(build, "RECIPE", self.recipe_path.parent)
        patcher.start()
        self.addCleanup(patcher.stop)

    def validate(self):
        build.validate_runtime_config(self.project)

    def test_equal_passes_without_writing(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.validate()
        after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_changed_key_fails_without_disclosing_values(self):
        write(self.config_path, dict(self.recipe, empty="private fixture value"))
        with self.assertRaisesRegex(RuntimeError, "differs from recipe/runtime-config.json; changed keys: empty") as caught:
            self.validate()
        self.assertNotIn("private fixture value", str(caught.exception))

    def test_missing_key_fails_even_for_empty_value(self):
        write(self.config_path, {key: value for key, value in self.recipe.items() if key != "empty"})
        with self.assertRaisesRegex(RuntimeError, "missing keys: empty"):
            self.validate()

    def test_extra_staged_keys_pass(self):
        write(self.config_path, dict(self.recipe, localOnly={"any": [None, 4]}, obsolete=True))
        self.validate()

    def test_nested_changes_and_boolean_number_substitution_fail(self):
        for changes, key in [
            ({"actors": [{"path": "Assets/Changed.prefab", "active": False}]}, "actors"),
            ({"actors": [{"path": "Assets/Fixture.prefab", "active": False, "extra": True}]}, "actors"),
            ({"enabled": 1}, "enabled"),
            ({"count": True}, "count"),
        ]:
            with self.subTest(changes=changes):
                write(self.config_path, dict(self.recipe, **changes))
                with self.assertRaisesRegex(RuntimeError, "changed keys: " + key):
                    self.validate()

    def test_missing_invalid_or_non_object_staged_config_fails(self):
        self.config_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "cannot read Assets/LabLoadingScene/Resources/MovementBatchProbe.json"):
            self.validate()
        self.config_path.write_text("invalid JSON")
        with self.assertRaisesRegex(RuntimeError, "cannot read"):
            self.validate()
        write(self.config_path, [])
        with self.assertRaisesRegex(RuntimeError, "must contain an object"):
            self.validate()

    def test_missing_invalid_or_empty_recipe_fails(self):
        self.recipe_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Cannot read recipe/runtime-config.json"):
            self.validate()
        self.recipe_path.write_text("invalid JSON")
        with self.assertRaisesRegex(RuntimeError, "Cannot read recipe/runtime-config.json"):
            self.validate()
        for value in [[], {}]:
            write(self.recipe_path, value)
            with self.assertRaisesRegex(RuntimeError, "must contain a nonempty object"):
                self.validate()

    def test_staged_source_validation_checks_runtime_recipe_after_layout(self):
        work = self.root / "work"
        write(work / "whole-catalog-build.json", {})
        self.config_path.unlink()
        with (
            patch.object(build, "WORK", work),
            patch.object(build, "validate_runtime_source_membership", return_value=[]),
            patch.object(build, "validate_project_layout") as layout,
        ):
            with self.assertRaisesRegex(RuntimeError, "Runtime config cannot read"):
                build.validate_staged_runtime_sources(self.project)
            layout.assert_called_once_with(self.project)


class TrackedRuntimeConfigTests(unittest.TestCase):
    def test_recipe_keys_are_present_session_config_fields(self):
        recipe = json.loads((ROOT / "recipe/runtime-config.json").read_text())
        config_fields = fields(PROBE.read_text(), "SessionConfig")
        self.assertEqual(len(recipe), 183)
        self.assertLessEqual(recipe.keys(), config_fields.keys())
        self.assertEqual(config_fields.keys() - recipe.keys(), {"detailedVisualDiagnostics"})

    def test_recipe_keys_are_sorted_recursively(self):
        def check(pairs):
            keys = [key for key, _ in pairs]
            self.assertEqual(keys, sorted(set(keys)))
            return dict(pairs)

        json.loads((ROOT / "recipe/runtime-config.json").read_text(), object_pairs_hook=check)


if __name__ == "__main__":
    unittest.main()
