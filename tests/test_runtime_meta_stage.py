import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts/lab"
import sys

sys.path.insert(0, str(SCRIPTS))
from composition_io import StageIO

import whole_catalog


class RuntimeMetaStageTests(unittest.TestCase):
    filename = "runtime/session/AkMusicPcmJoinQueryAdapter.cs"
    guid = "b1bf750a0ee64e0d829e27bcde8a8b2e"
    source_bytes = b"internal sealed class AuthoredRuntimeFixture {}\n"
    meta_bytes = (f"fileFormatVersion: 2\nguid: {guid}\nMonoImporter:\n  externalObjects: {{}}\n").encode()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.project = self.work / "lab-project"
        self.runtime = self.project / "Assets/LabLoadingScene"
        self.runtime.mkdir(parents=True)
        self.source = self.root / "tools/unity" / self.filename
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(self.source_bytes)
        self.source_meta = Path(str(self.source) + ".meta")
        self.source_meta.write_bytes(self.meta_bytes)
        self.recipe = self.root / "recipe"
        self.recipe.mkdir()
        (self.recipe / "project-layout.json").write_text(json.dumps({"runtime_source_guids": {self.filename: self.guid}}), encoding="utf-8")

    def stage(self, destination=None, names=None):
        io = StageIO(self.work, destination)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            whole_catalog.stage_runtime_sources(io, names or [self.filename])
        return io

    def test_missing_sidecar_is_seeded_from_valid_authored_guid(self):
        io = self.stage()
        source_target = self.runtime / Path(self.filename).name
        meta_target = Path(str(source_target) + ".meta")
        self.assertEqual(source_target.read_bytes(), self.source_bytes)
        self.assertEqual(meta_target.read_bytes(), self.meta_bytes)
        self.assertEqual(io.pending, {})

    def test_equipment_owner_seeds_its_pinned_sidecar_in_a_fresh_project(self):
        filename = "runtime/catalog/OriginalEquipmentHighlightAssetsBoundary.cs"
        authored = REPO / "tools/unity" / filename
        metadata = Path(str(authored) + ".meta").read_bytes()
        guid = json.loads((REPO / "recipe/project-layout.json").read_text())["runtime_source_guids"][filename]
        source = self.root / "tools/unity" / filename
        source.parent.mkdir(parents=True)
        source.write_bytes(authored.read_bytes())
        Path(str(source) + ".meta").write_bytes(metadata)
        (self.recipe / "project-layout.json").write_text(json.dumps({"runtime_source_guids": {filename: guid}}))
        io = self.stage(names=[filename])
        target = self.runtime / Path(filename).name
        self.assertEqual(target.read_bytes(), authored.read_bytes())
        self.assertEqual(Path(str(target) + ".meta").read_bytes(), metadata)
        self.assertIn(f"guid: {guid}\n".encode(), metadata)
        self.assertEqual(io.pending, {})

    def test_existing_unity_metadata_is_preserved_byte_for_byte(self):
        source_target = self.runtime / Path(self.filename).name
        meta_target = Path(str(source_target) + ".meta")
        existing = (f"fileFormatVersion: 2\nguid: {self.guid}\nMonoImporter:\n  userData: preserved editor state\n").encode()
        meta_target.write_bytes(existing)
        self.stage()
        self.assertEqual(source_target.read_bytes(), self.source_bytes)
        self.assertEqual(meta_target.read_bytes(), existing)

    def test_mismatched_authored_guid_refuses_before_any_source_write(self):
        self.source_meta.write_text("fileFormatVersion: 2\nguid: " + "a" * 32 + "\n", encoding="utf-8")
        io = StageIO(self.work)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            with self.assertRaisesRegex(RuntimeError, "differs from project-layout"):
                whole_catalog.stage_runtime_sources(io, [self.filename])
        self.assertFalse((self.runtime / Path(self.filename).name).exists())
        self.assertFalse((self.runtime / (Path(self.filename).name + ".meta")).exists())
        self.assertEqual(io.pending, {})

    def test_bad_authored_sidecar_refuses_even_when_destination_metadata_exists(self):
        source_target = self.runtime / Path(self.filename).name
        meta_target = Path(str(source_target) + ".meta")
        existing = (f"fileFormatVersion: 2\nguid: {self.guid}\n").encode()
        meta_target.write_bytes(existing)
        self.source_meta.write_text("fileFormatVersion: 2\nguid: " + "a" * 32 + "\n", encoding="utf-8")
        io = StageIO(self.work)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            with self.assertRaisesRegex(RuntimeError, "differs from project-layout"):
                whole_catalog.stage_runtime_sources(io, [self.filename])
        self.assertFalse(source_target.exists())
        self.assertEqual(meta_target.read_bytes(), existing)
        self.assertEqual(io.pending, {})

    def test_bad_later_sidecar_refuses_before_staging_earlier_source(self):
        second = "runtime/session/SecondFixture.cs"
        second_source = self.root / "tools/unity" / second
        second_source.parent.mkdir(parents=True, exist_ok=True)
        second_source.write_bytes(b"second source\n")
        Path(str(second_source) + ".meta").write_text("guid: " + "b" * 32 + "\n", encoding="utf-8")
        (self.recipe / "project-layout.json").write_text(json.dumps({"runtime_source_guids": {self.filename: self.guid, second: "c" * 32}}), encoding="utf-8")
        io = StageIO(self.work)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            with self.assertRaisesRegex(RuntimeError, "differs from project-layout"):
                whole_catalog.stage_runtime_sources(io, [self.filename, second])
        self.assertFalse((self.runtime / Path(self.filename).name).exists())
        self.assertFalse((self.runtime / Path(second).name).exists())
        self.assertEqual(io.pending, {})

    def test_intentional_null_guid_without_authored_sidecar_keeps_first_import_behavior(self):
        (self.recipe / "project-layout.json").write_text(json.dumps({"runtime_source_guids": {self.filename: None}}), encoding="utf-8")
        self.source_meta.unlink()
        io = self.stage()
        source_target = self.runtime / Path(self.filename).name
        self.assertEqual(source_target.read_bytes(), self.source_bytes)
        self.assertFalse(Path(str(source_target) + ".meta").exists())
        self.assertEqual(io.pending, {})

    def test_null_guid_cannot_hide_an_authored_sidecar(self):
        (self.recipe / "project-layout.json").write_text(json.dumps({"runtime_source_guids": {self.filename: None}}), encoding="utf-8")
        io = StageIO(self.work)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            with self.assertRaisesRegex(RuntimeError, "conflicts with authored"):
                whole_catalog.stage_runtime_sources(io, [self.filename])
        self.assertFalse((self.runtime / Path(self.filename).name).exists())
        self.assertEqual(io.pending, {})

    def test_fixed_guid_with_missing_authored_sidecar_refuses(self):
        self.source_meta.unlink()
        io = StageIO(self.work)
        with patch.object(whole_catalog, "ROOT", self.root), patch.object(whole_catalog, "RECIPE", self.recipe):
            with self.assertRaisesRegex(RuntimeError, "no regular authored sidecar"):
                whole_catalog.stage_runtime_sources(io, [self.filename])
        self.assertFalse((self.runtime / Path(self.filename).name).exists())
        self.assertEqual(io.pending, {})

    def test_destination_stage_queues_source_and_meta_then_flushes_them(self):
        destination = self.root / "rebuild/project"
        destination.mkdir(parents=True)
        io = self.stage(destination)
        target = destination / "Assets/LabLoadingScene" / Path(self.filename).name
        meta = Path(str(target) + ".meta")
        self.assertEqual(io.pending[target], self.source_bytes)
        self.assertEqual(io.pending[meta], self.meta_bytes)
        self.assertFalse(target.exists())
        self.assertFalse(meta.exists())
        io.flush()
        self.assertEqual(target.read_bytes(), self.source_bytes)
        self.assertEqual(meta.read_bytes(), self.meta_bytes)


if __name__ == "__main__":
    unittest.main()
