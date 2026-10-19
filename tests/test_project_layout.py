import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import build
from common import read, write


class ProjectLayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.source = "runtime/session/Fixture.cs"
        source = self.root / "tools/unity" / self.source
        source.parent.mkdir(parents=True)
        source.write_text("authored fixture")
        self.meta = self.project / "Assets/LabLoadingScene/Fixture.cs.meta"
        self.meta.parent.mkdir(parents=True)
        self.meta.write_text("fileFormatVersion: 2\nguid: " + "a" * 32 + "\nMonoImporter:\n  serializedVersion: 2\n")
        self.manifest = self.project / "Packages/manifest.json"
        self.dependencies = {"com.unity.ugui": "1.0.0", "com.example.fixture": "https://example.com/public.git#v1"}
        write(self.manifest, {"dependencies": self.dependencies})
        self.recipe = self.root / "recipe/project-layout.json"
        self.layout = {"runtime_source_guids": {self.source: "a" * 32}, "dependencies": self.dependencies}
        write(self.recipe, self.layout)
        write(self.root / "recipe/runtime-sources.json", [self.source])
        for name, value in [("ROOT", self.root), ("RECIPE", self.root / "recipe"), ("WORK", self.root / "work")]:
            patcher = patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def validate(self):
        build.validate_project_layout(self.project)

    def test_match_passes_without_writing_any_project_files(self):
        before = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.validate()
        after = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_changed_guid_fails(self):
        self.meta.write_text("guid: " + "b" * 32 + "\n")
        with self.assertRaisesRegex(RuntimeError, "GUID mismatch: Assets/LabLoadingScene/Fixture.cs.meta; expected a{32}, found b{32}"):
            self.validate()

    def test_missing_meta_fails(self):
        self.meta.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing staged .meta: Assets/LabLoadingScene/Fixture.cs.meta"):
            self.validate()
        self.assertFalse(self.meta.exists())

    def test_new_source_with_null_guid_needs_no_meta_yet(self):
        # A source Unity has not imported has no .meta until its first build.
        self.meta.unlink()
        self.layout["runtime_source_guids"][self.source] = None
        write(self.recipe, self.layout)
        self.validate()

    def test_invalid_or_duplicate_guid_lines_fail(self):
        for contents in ["fileFormatVersion: 2\n", "guid: invalid\n", "guid: " + "a" * 32 + "\nguid: " + "a" * 32 + "\n"]:
            with self.subTest(contents=contents):
                self.meta.write_text(contents)
                with self.assertRaisesRegex(RuntimeError, "invalid staged .meta GUID: Assets/LabLoadingScene/Fixture.cs.meta"):
                    self.validate()

    def test_extra_package_fails(self):
        write(self.manifest, {"dependencies": dict(self.dependencies, extra="1.0.0")})
        with self.assertRaisesRegex(RuntimeError, "Packages/manifest.json differs.*extra packages: extra"):
            self.validate()

    def test_missing_package_fails(self):
        write(self.manifest, {"dependencies": {"com.unity.ugui": "1.0.0"}})
        with self.assertRaisesRegex(RuntimeError, "missing packages: com.example.fixture"):
            self.validate()

    def test_changed_package_version_or_url_fails(self):
        for package, version in [("com.unity.ugui", "2.0.0"), ("com.example.fixture", "https://example.com/public.git#v2")]:
            with self.subTest(package=package):
                write(self.manifest, {"dependencies": dict(self.dependencies, **{package: version})})
                with self.assertRaisesRegex(RuntimeError, "changed packages: " + package):
                    self.validate()

    def test_missing_or_invalid_manifest_fails(self):
        self.manifest.unlink()
        with self.assertRaisesRegex(RuntimeError, "cannot read Packages/manifest.json"):
            self.validate()
        self.manifest.write_text("invalid json")
        with self.assertRaisesRegex(RuntimeError, "cannot read Packages/manifest.json"):
            self.validate()
        write(self.manifest, {})
        with self.assertRaisesRegex(RuntimeError, "Packages/manifest.json must contain a dependencies object"):
            self.validate()

    def test_recipe_guid_membership_must_match_source_manifest(self):
        for guids in [{}, {self.source: "a" * 32, "Extra.cs": "b" * 32}]:
            with self.subTest(guids=guids):
                write(self.recipe, dict(self.layout, runtime_source_guids=guids))
                with self.assertRaisesRegex(RuntimeError, "runtime_source_guids must match recipe/runtime-sources.json exactly"):
                    self.validate()

    def test_invalid_recipe_guid_or_dependencies_fail(self):
        for changes, message in [
            ({"runtime_source_guids": {self.source: "invalid"}}, "unique 32-character lowercase hex GUIDs"),
            ({"dependencies": []}, "dependencies must map package names"),
            ({"dependencies": {"com.unity.ugui": None}}, "dependencies must map package names"),
        ]:
            with self.subTest(changes=changes):
                write(self.recipe, dict(self.layout, **changes))
                with self.assertRaisesRegex(RuntimeError, message):
                    self.validate()

    def test_whole_catalog_staged_validation_checks_layout(self):
        write(self.root / "work/whole-catalog-build.json", {})
        (self.meta.parent / "Fixture.cs").write_text("authored fixture")
        self.meta.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing staged .meta"):
            build.validate_staged_runtime_sources(self.project)


class TrackedProjectLayoutTests(unittest.TestCase):
    def test_tracked_recipe_matches_sources_and_has_unique_valid_guids(self):
        layout = read(ROOT / "recipe/project-layout.json")
        sources = read(ROOT / "recipe/runtime-sources.json")
        self.assertEqual(set(layout["runtime_source_guids"]), set(sources))
        # A newly declared source may await its first exact-editor import. This
        # is the same null-GUID contract validated by ProjectLayoutTests above.
        guids = [guid for guid in layout["runtime_source_guids"].values() if guid is not None]
        self.assertEqual(len(guids), len(set(guids)))
        for guid in guids:
            self.assertRegex(guid, r"^[0-9a-f]{32}$")
        self.assertTrue(layout["dependencies"])
        for name, pin in layout["dependencies"].items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(pin, str)


if __name__ == "__main__":
    unittest.main()
