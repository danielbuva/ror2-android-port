"""Synthetic settings/editor/importer/mesh replay; no original game data or editor."""

import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from common import RECIPE, read, sha, write
from composition_io import StageIO
from nova_bridge import insert_axes, nova_axes
import project_input_rebuild as replay
import rebuild


class ProjectInputRebuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.work = self.root / "inputs"
        self.dest = self.root / "destination"
        self.recipe_root = self.root / "recipe"
        self.input_id = "a" * 64
        self.put(self.root / "smoke/ProjectSettings/Synthetic.asset", b"authored settings")
        self.put(self.root / "smoke/ProjectSettings/InputManager.asset", b"InputManager:\n  m_Axes: []\n  m_UsePhysicalKeys: 1\n")
        self.put(self.recipe_root / "templates/editor.cs", b"// independently authored synthetic editor\n")
        self.put(self.recipe_root / "templates/ordered-script.meta", (RECIPE / "templates/ordered-script.meta").read_bytes())
        write(self.recipe_root / "project-layout.json", dict(runtime_source_guids={"runtime/input/NovaInputBridge.cs": "b" * 32}))
        self.put(self.root / "installation/Risk of Rain 2_Data/Managed/RoR2.dll", b"synthetic")
        self.bundle = self.root / "installation/Synthetic.bundle"
        self.put(self.bundle, b"synthetic bundle")
        self.geometry = b"o Synthetic\nv 1 2 3\n"
        self.mesh = SimpleNamespace(m_Name="Synthetic", export=lambda: self.geometry.decode())
        self.obj = SimpleNamespace(type=SimpleNamespace(name="Mesh"), path_id=42, read=lambda: self.mesh)
        self.recipe = dict(
            schema=1,
            input_id=self.input_id,
            settings_templates=["ProjectSettings/Synthetic.asset"],
            editors=[dict(path="Assets/Editor/Synthetic.cs", template="templates/editor.cs", sha256=sha(self.recipe_root / "templates/editor.cs"))],
            geometry=dict(
                bundle="Synthetic.bundle",
                bundle_sha256=sha(self.bundle),
                path_id=42,
                mesh_name="Synthetic",
                output_sha256=hashlib.sha256(self.geometry).hexdigest(),
            ),
        )
        self.save()
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/local.json", dict(game_path=str(self.bundle.parent)))
        write(self.work / "inventory/files.json", dict(input_id=self.input_id, files=[dict(path="Synthetic.bundle", sha256=sha(self.bundle))]))
        self.payload = {
            "ProjectSettings/Synthetic.asset": b"authored settings",
            "ProjectSettings/InputManager.asset": insert_axes((self.root / "smoke/ProjectSettings/InputManager.asset").read_text(), nova_axes()).encode(),
            "Assets/Editor/Synthetic.cs": (self.recipe_root / "templates/editor.cs").read_bytes(),
            "Assets/LabLoadingScene/NovaInputBridge.cs.meta": (self.recipe_root / "templates/ordered-script.meta").read_text().format(guid="b" * 32).encode(),
            "Assets/Recovered/geometry.obj": self.geometry,
        }
        self.provenance = {path: dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) for path, data in self.payload.items()}
        for patcher in (
            patch.object(replay, "ROOT", self.root),
            patch.object(replay, "RECIPE", self.recipe_root),
            patch.object(StageIO, "preflight"),
            patch("UnityPy.load", return_value=SimpleNamespace(objects=[self.obj])),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save(self):
        write(self.recipe_root / "project-inputs.json", self.recipe)

    def run_step(self):
        replay.project_inputs(self.dest, self.work, self.input_id, set(self.payload), self.provenance)

    def snapshot(self):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) for base in (self.work, self.bundle.parent) for p in base.rglob("*") if p.is_file()}

    def test_regenerates_full_importer_mesh_and_axes_and_stages_templates_read_only(self):
        before = self.snapshot()
        self.run_step()
        self.assertEqual(before, self.snapshot())
        for path, data in self.payload.items():
            self.assertEqual((self.dest / path).read_bytes(), data)
            self.put(self.work / "lab-project" / path, data)
        comparison = rebuild.compare(self.dest, self.work / "lab-project", set(self.payload), self.provenance, lambda p: p in self.payload)
        self.assertTrue(comparison["equal"])
        self.assertEqual(comparison["counts"]["identical"], 5)
        self.assertTrue((self.dest / ".rebuild/project-inputs-complete.json").is_file())
        axes = (self.dest / "ProjectSettings/InputManager.asset").read_text()
        self.assertEqual(axes.count("m_Name: NovaLabAxis"), 16)
        self.assertIn("executionOrder: -20000", (self.dest / "Assets/LabLoadingScene/NovaInputBridge.cs.meta").read_text())

    def test_any_output_drift_prevents_all_project_writes(self):
        self.provenance["Assets/Editor/Synthetic.cs"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.run_step()
        self.assertFalse(self.dest.exists())

    def test_bundle_inventory_drift_refuses_geometry_before_flush(self):
        self.bundle.write_bytes(b"drift")
        with self.assertRaisesRegex(RuntimeError, "bundle drift"):
            self.run_step()
        self.assertFalse(self.dest.exists())

    def test_mesh_identity_ambiguity_and_name_drift_refuse_all_writes(self):
        self.obj.path_id = 99
        with self.assertRaisesRegex(RuntimeError, "identity ambiguous"):
            self.run_step()
        self.obj.path_id = 42
        self.mesh.m_Name = "wrong"
        with self.assertRaisesRegex(RuntimeError, "name drift"):
            self.run_step()
        self.assertFalse(self.dest.exists())

    def test_serializer_drift_refuses_all_writes(self):
        self.geometry += b"v 4 5 6\n"
        with self.assertRaisesRegex(RuntimeError, "serializer drift"):
            self.run_step()
        self.assertFalse(self.dest.exists())

    def test_historical_editor_hash_drift_and_membership_drift_refuse_all_writes(self):
        self.recipe["editors"][0]["sha256"] = "f" * 64
        self.save()
        with self.assertRaisesRegex(RuntimeError, "editor template drift"):
            self.run_step()
        self.recipe["settings_templates"].append("ProjectSettings/Missing.asset")
        self.save()
        with self.assertRaisesRegex(RuntimeError, "membership"):
            self.run_step()
        self.assertFalse(self.dest.exists())

    def test_public_membership_counts_and_unresolved_files_are_not_claimed(self):
        public = read(RECIPE / "project-inputs.json")
        self.assertEqual(len(public["settings_templates"]), 17)
        self.assertEqual(len(replay.membership(public)), 23)
        owner = rebuild.STEPS["project-inputs"]
        for path in (
            "ProjectSettings/GraphicsSettings.asset",
            "ProjectSettings/ProjectSettings.asset",
            "ProjectSettings/BurstAotSettings_Android.json",
            "ProjectSettings/CommonBurstAotSettings.json",
            "Assets/LabLoadingScene/WholeCatalogPreservation/item-behaviors/link.xml",
        ):
            self.assertFalse(owner.owns(path))


if __name__ == "__main__":
    unittest.main()
