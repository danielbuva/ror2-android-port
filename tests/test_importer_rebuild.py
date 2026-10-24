"""Synthetic importer replay, identity/reference contracts and destination isolation."""

import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import importer_rebuild as replay
import rebuild
from common import RECIPE, read, write
from composition_io import StageIO


class ImporterRebuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "inputs"
        self.dest = self.root / "destination"
        self.recipes = self.root / "recipe"
        self.input_id = "a" * 64
        (self.recipes / "templates").mkdir(parents=True)
        for source in (RECIPE / "templates").glob("*-importer.meta"):
            shutil.copyfile(source, self.recipes / "templates" / source.name)
        self.recipe = dict(
            schema=1,
            input_id=self.input_id,
            scripts={
                "Assets/LabLoadingScene/Example.cs.meta": dict(runtime_source="runtime/Example.cs"),
                "Assets/Editor/Example.cs.meta": dict(guid="2" * 32),
            },
            shaders={"Assets/LabLoadingScene/Resources/Example.shader.meta": "3" * 32},
            other={
                "Assets/Lab.unity.meta": dict(guid="4" * 32, template="default"),
                "Assets/LabLoadingScene/WholeCatalogPreservation/item-behaviors/link.xml.meta": dict(guid="6" * 32, template="text"),
            },
        )
        self.layout = dict(runtime_source_guids={"runtime/Example.cs": "5" * 32})
        for path in (*self.recipe["scripts"], *self.recipe["shaders"]):
            self.put(self.dest / path.removesuffix(".meta"), b"authored source")
        write(self.dest / ".rebuild/runtime-sources-complete.json", dict(input_id=self.input_id))
        write(self.dest / ".rebuild/composition/scene-probe-build.json", {})
        for patcher in (patch.object(replay, "RECIPE", self.recipes), patch.object(StageIO, "preflight")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.payload = replay.render(self.recipe, self.layout, self.input_id)
        self.provenance = {n: dict(producer="unity-generated", sha256=hashlib.sha256(b).hexdigest(), size=len(b)) for n, b in self.payload.items()}
        for n, b in self.payload.items():
            self.put(self.work / "lab-project" / n, b)
        self.save()

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save(self):
        write(self.recipes / "importer-identities.json", self.recipe)
        write(self.recipes / "project-layout.json", self.layout)

    def run_step(self):
        return replay.importer_identities(self.dest, self.work, self.input_id, set(self.payload), self.provenance)

    def test_places_complete_cohort_without_reading_oracle_as_input(self):
        # Corrupt the oracle: generation must still use only the recorded public IDs.
        self.put(self.work / "lab-project/Assets/Lab.unity.meta", b"oracle drift")
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}
        result = self.run_step()
        self.assertEqual(result["placed"], dict(scripts=2, shaders=1, other=2))
        # Bodies R9 produces get placeholders so Unity keeps the recorded GUIDs at import (J603).
        self.assertEqual(result["r9_placeholders"], sorted(replay.R9_PLACEHOLDERS))
        for path, data in replay.R9_PLACEHOLDERS.items():
            self.assertEqual((self.dest / path).read_bytes(), data)
        for path, data in self.payload.items():
            self.assertEqual((self.dest / path).read_bytes(), data)
        self.assertFalse((self.dest / "Assets/Synthetic.meta").exists())
        self.assertTrue((self.dest / ".rebuild/importer-identities-complete.json").is_file())
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()})
        provenance = dict(self.provenance)
        provenance.update({path.removesuffix(".meta"): {} for path in (*self.recipe["scripts"], *self.recipe["shaders"])})
        provenance.update({path: dict(producer="unity-generated") for path in replay.R9_PLACEHOLDERS})
        comparison = rebuild.compare(self.dest, self.work / "lab-project", set(self.payload), provenance, lambda p: p in self.payload)
        self.assertEqual(comparison["counts"], dict(identical=4, different=1, missing=0, extra=0))
        self.assertIn(b"executionOrder: 0", self.payload["Assets/LabLoadingScene/Example.cs.meta"])

    def test_placeholders_never_replace_an_existing_body_and_require_their_importer(self):
        self.put(self.dest / "Assets/Lab.unity", b"existing scene")
        self.assertEqual(self.run_step()["r9_placeholders"], ["Assets/LabLoadingScene/WholeCatalogPreservation/item-behaviors/link.xml"])
        self.assertEqual((self.dest / "Assets/Lab.unity").read_bytes(), b"existing scene")
        del self.recipe["other"]["Assets/Lab.unity.meta"]
        self.save()
        self.payload.pop("Assets/Lab.unity.meta")
        with self.assertRaisesRegex(RuntimeError, "no recorded importer"):
            self.run_step()

    def test_last_output_drift_prevents_every_importer_write(self):
        self.provenance["Assets/Lab.unity.meta"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.run_step()
        self.assertFalse(any(self.dest.rglob("*.meta")))
        self.assertFalse((self.dest / ".rebuild/importer-identities-complete.json").exists())

    def test_membership_input_guid_template_and_path_drift_fail_closed(self):
        for mutate in (
            lambda r: r.update(input_id="b" * 64),
            lambda r: r["other"].update({"../escape.meta": r["other"].pop("Assets/Lab.unity.meta")}),
            lambda r: r.update(folders={"Assets/Synthetic.meta": "1" * 32}),
            lambda r: r["shaders"].update({"Assets/LabLoadingScene/Resources/Example.shader.meta": "2" * 32}),
            lambda r: r["other"]["Assets/Lab.unity.meta"].update(template="../../escape"),
            lambda r: r["scripts"]["Assets/LabLoadingScene/Example.cs.meta"].update(runtime_source="runtime/Absent.cs"),
        ):
            recipe = copy.deepcopy(self.recipe)
            mutate(recipe)
            with self.assertRaises(RuntimeError):
                replay.render(recipe, self.layout, self.input_id)
        self.recipe["shaders"]["Assets/LabLoadingScene/Resources/Extra.shader.meta"] = "6" * 32
        self.save()
        with self.assertRaisesRegex(RuntimeError, "membership"):
            self.run_step()
        self.assertFalse(any(self.dest.rglob("*.meta")))

    def test_reference_measurement_detects_text_importer_and_binary_references_excludes_own_identity(self):
        guid = "1" * 32
        self.put(self.dest / "Assets/Synthetic.meta", ("fileFormatVersion: 2\nguid: " + guid + "\nfolderAsset: yes\n").encode())
        self.put(self.dest / "Assets/Reference.prefab", ("%YAML 1.1\nfolder: {guid: " + guid + "}\n").encode())
        self.put(self.dest / "Assets/Reference.asset", b"binary-prefix" + bytes.fromhex(guid) + b"suffix")
        self.put(self.dest / "Assets/Importer.meta", ("guid: " + "9" * 32 + "\nexternalObjects: {guid: " + guid + "}\n").encode())
        result = replay.folder_references(self.dest, {"Assets/Synthetic.meta": guid})
        self.assertEqual(result["referencing_files"], 3)
        self.assertEqual(result["serialized_assets"], 2)
        self.assertEqual(result["binary_serialized_assets"], 1)
        self.assertNotIn("Assets/Synthetic.meta", [r["path"] for r in result["references"]])

    def test_missing_source_and_link_escape_refuse_all_importer_writes(self):
        source = self.dest / "Assets/Editor/Example.cs"
        source.unlink()
        with self.assertRaisesRegex(RuntimeError, "target missing"):
            self.run_step()
        self.put(source, b"authored source")
        (self.dest / "Assets/Lab.unity.meta").symlink_to(self.work / "lab-project/Assets/Lab.unity.meta")
        with self.assertRaisesRegex(RuntimeError, "links|escapes"):
            self.run_step()
        self.assertFalse((self.dest / ".rebuild/importer-identities-complete.json").exists())

    def test_runtime_sources_marker_required(self):
        (self.dest / ".rebuild/runtime-sources-complete.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "runtime-sources"):
            self.run_step()

    def test_original_music_importers_render_the_recorded_runtime_guids(self):
        recipe = read(RECIPE / "importer-identities.json")
        layout = read(RECIPE / "project-layout.json")
        payload = replay.render(recipe, layout, recipe["input_id"])
        for name in ("OriginalMusicControllerContract", "PortSessionOriginalMusicControllerOwner"):
            source = "runtime/session/" + name + ".cs"
            target = "Assets/LabLoadingScene/" + name + ".cs.meta"
            self.assertEqual(recipe["scripts"][target], {"runtime_source": source})
            self.assertIn(("guid: " + layout["runtime_source_guids"][source] + "\n").encode(), payload[target])

    def test_public_membership_counts_and_coordinator_order(self):
        recipe = read(RECIPE / "importer-identities.json")
        self.assertEqual({group: len(recipe[group]) for group in replay.GROUPS}, dict(scripts=140, shaders=175, other=6))
        self.assertNotIn("folders", recipe)
        # J751: Codex's 17 new editor scripts carry explicit GUIDs; runtime sources use the layout.
        self.assertEqual(sum("guid" in row for row in recipe["scripts"].values()), 31)
        owner = rebuild.STEPS["importer-identities"]
        provenance = {path: dict(producer="unity-generated") for path in replay.membership(recipe)}
        self.assertEqual(rebuild.selected_paths(owner, provenance), set(provenance))
        for row in provenance.values():
            row["producer"] = "repo-builder"
        self.assertFalse(rebuild.selected_paths(owner, provenance))
        order = list(rebuild.STEPS)
        self.assertLess(order.index("runtime-sources"), order.index("importer-identities"))
        self.assertLess(order.index("importer-identities"), order.index("validate-bindings"))


if __name__ == "__main__":
    unittest.main()
