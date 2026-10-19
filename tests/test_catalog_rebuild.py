"""R3/R4 synthetic replay, including the real builders and original write paths."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import catalog_analysis
import catalog_rebuild
import composition_io
import composition_migration
import whole_catalog
import rebuild
from common import read, sha, write
from composition_io import StageIO


class CatalogRebuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / "work"
        self.dest = self.root / "destination"
        self.export = self.work / "export"
        self.catalog = self.work / "catalog"
        self.recipes = self.root / "recipe"
        self.input_id = "a" * 64
        self.source = "Assets/Test.prefab"
        self.target = "Assets/WholeGame/Test.prefab"
        self.guid = "b" * 32
        self.body = "%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component:\n  - component: {fileID: 2}\n  ui: old-ui\n--- !u!114 &2\nMonoBehaviour:\n  m_Script: {fileID: 3, guid: 2b6c926553287666f24ffd5af5ba21cb, type: 3}\n"
        self.put(self.export / self.source, self.body)
        self.put(self.export / (self.source + ".meta"), "guid: " + self.guid + "\n")
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/reconstruction.json", dict(projects=["work/export"]))
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        write(self.work / "config/composition-migration.json", dict(input_id=self.input_id, evidence="work/evidence"))
        write(self.recipes / "hud-ui-remaps.json", dict(input_id=self.input_id, rows=[dict(**{"from": "old-ui", "to": "new-ui"})]))
        write(
            self.catalog / "reconciled-closure.json",
            dict(input_id=self.input_id, files=[self.source], roots=[1], converted={"1": dict(source=self.source)}, source_catalog_sha256="c" * 64),
        )
        write(self.catalog / "source-guid-index.json", {self.guid: self.source})
        write(self.catalog / "source-guid-repairs.json", [])
        write(self.catalog / "native-conversions.json", dict(issues=[]))
        write(self.catalog / "source-catalog.json", dict(locations=[dict(id=1, type="UnityEngine.GameObject", primaryKey="test")], keys=[], providers=[]))
        self.support = "Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
        self.support_target = "Assets/WholeGame/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
        self.put(self.export / self.support, "class SyntheticSupport {}\n")
        self.binary = self.work / "game/Risk of Rain 2_Data/Managed/Assembly-CSharp.dll"
        self.put(self.binary, "synthetic binary")
        self.fields = dict(SpawnBeadChaseEvent="AK.Wwise.Event", ExplodeEvent="AK.Wwise.Event")
        write(self.work / "inventory/files.json", dict(files=[dict(path="Risk of Rain 2_Data/Managed/Assembly-CSharp.dll", sha256=sha(self.binary))]))
        for project in (self.dest, self.work / "lab-project"):
            write(project / ".port-input.json", dict(input_id=self.input_id))
            write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", {})
            for name, guid in (
                ("Plugins/AK.Wwise.Unity.MonoBehaviour.dll", "2b6c926553287666f24ffd5af5ba21cb"),
                ("Plugins/Decalicious.dll", "90eda32cd325c26600dacf144354b407"),
                ("Plugins/RoR2.dll", "951ce57ad999ac1f040a4dceb5f8b763"),
                ("SilentProjectileBoundary.cs", "d" * 32),
            ):
                self.put(project / ("Assets/LabLoadingScene/" + name + ".meta"), "guid: " + guid + "\n")
        write(self.work / "scene-probe-build.json", dict(prefabAssets=[self.target]))
        write(self.dest / ".rebuild/composition/scene-probe-build.json", dict(prefabAssets=[self.target]))
        for name in ("WholeCatalogLoader.cs", "WholeCatalogBootstrap.cs"):
            self.put(self.root / "tools/unity/runtime/catalog" / name, "authored synthetic")
        self.put(self.root / "tools/catalog/WholeCatalogHost.cs", "authored synthetic")
        self.pin()
        write(self.recipes / "build-entry-inputs.json", dict(schema=2, input_id=self.input_id, bootstrap_attempt="integration-pinned", files={}))
        (self.work / "evidence").mkdir()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(patch.object(StageIO, "preflight"))
        for module in (composition_io, whole_catalog, composition_migration):
            stack.enter_context(patch.object(module, "ROOT", self.root))
            stack.enter_context(patch.object(module, "WORK", self.work))
        for module in (catalog_rebuild, whole_catalog, composition_migration):
            stack.enter_context(patch.object(module, "RECIPE", self.recipes))
        stack.enter_context(patch.object(whole_catalog, "game", return_value=self.work / "game"))
        stack.enter_context(patch.object(whole_catalog, "recover_ambiguous_mesh_subobjects", return_value=[]))
        write(self.catalog / "native-latest.json", dict(path="work/native"))
        self.contract = dict(sha256=sha(self.binary), types=[dict(fields=[dict(name=k, type=v) for k, v in self.fields.items()])])
        from types import SimpleNamespace

        stack.enter_context(patch.dict(sys.modules, boundaries=SimpleNamespace(probe_tool=lambda: ["synthetic-probe"])))

        # The IL probe reports the binary it actually read.
        stack.enter_context(
            patch.object(
                whole_catalog,
                "run",
                side_effect=lambda *a, **k: SimpleNamespace(stdout=json.dumps(dict(self.contract, sha256=sha(self.binary))).encode()),
            )
        )
        # Host regeneration is exercised by its own tests; here it publishes the synthetic cohort.
        stack.enter_context(patch.object(catalog_analysis, "regenerate", side_effect=self.regenerate))

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def regenerate(self, work, out, input_id):
        for name in catalog_analysis.OUTPUTS:
            source = self.catalog / name
            (out / name).write_bytes(source.read_bytes() if source.is_file() else b"{}")
        (out / "native-containers").mkdir()

    def pin(self):
        # Changed synthetic analysis is regenerated by the next destination stage.
        marker = self.dest / ".rebuild/catalog-inputs/analysis-complete.json"
        if marker.is_file():
            marker.unlink()

    def staging(self):
        return catalog_rebuild.CatalogIO(self.work, self.dest, self.input_id)

    def test_import_remaps_ui_and_flushes_only_destination(self):
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertFalse((self.dest / self.target).exists())
        self.assertIn("new-ui", staging.read_text(self.dest / self.target))
        staging.flush()
        self.assertEqual((self.dest / (self.target + ".meta")).read_text(), "guid: " + self.guid + "\n")
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        self.assertTrue(list((self.dest / ".rebuild/catalog-inputs").glob("integration-*/manifest.json")))

    def test_r3_fills_body_when_r2_only_placed_importer(self):
        self.put(self.dest / (self.target + ".meta"), "guid: " + self.guid + "\n")
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertIn("new-ui", staging.read_text(self.dest / self.target))

    def test_r4_fills_body_when_r2_only_placed_importer(self):
        self.put(self.dest / (self.target + ".meta"), "guid: " + self.guid + "\n")
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertNotIn("--- !u!114 &2", staging.read_text(self.dest / self.target))

    def test_sanitizer_uses_public_script_guid_before_r7(self):
        (self.dest / "Assets/LabLoadingScene/SilentProjectileBoundary.cs.meta").unlink()
        write(self.recipes / "project-layout.json", dict(runtime_source_guids={"runtime/world/SilentProjectileBoundary.cs": "d" * 32}))
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertNotIn("--- !u!114 &2", staging.read_text(self.dest / self.target))
        self.assertFalse(staging.is_file(self.dest / "Assets/LabLoadingScene/SilentProjectileBoundary.cs.meta"))

    def test_existing_guid_owner_is_reused(self):
        self.put(self.dest / "Assets/Existing.prefab", "owned")
        self.put(self.dest / "Assets/Existing.prefab.meta", "guid: " + self.guid + "\n")
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        staging.flush()
        self.assertFalse((self.dest / self.target).exists())
        manifest = read(next((self.dest / ".rebuild/catalog-inputs").glob("integration-*/manifest.json")))
        self.assertEqual(manifest["locations"][0]["path"], "Assets/Existing.prefab")

    def test_duplicate_owner_is_rejected(self):
        for name in ("A", "B"):
            self.put(self.dest / ("Assets/" + name + ".meta"), "guid: " + self.guid + "\n")
        with self.assertRaisesRegex(RuntimeError, "Duplicate imported GUID"):
            whole_catalog.prepare_integration(self.staging())

    def test_scene_guid_repair_uses_recorded_identity(self):
        write(self.catalog / "source-guid-repairs.json", [dict(source=self.source, source_guid=self.guid, guid="e" * 32)])
        write(self.catalog / "source-guid-index.json", {"e" * 32: self.source})
        self.pin()
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        self.assertEqual(staging.read_text(self.dest / (self.target + ".meta")), "guid: " + "e" * 32 + "\n")

    def test_failed_analysis_leaves_no_completion_marker(self):
        with patch.object(catalog_analysis, "regenerate", side_effect=RuntimeError("inspection incomplete")):
            with self.assertRaisesRegex(RuntimeError, "inspection incomplete"):
                self.staging()
        self.assertFalse((self.dest / ".rebuild/catalog-inputs/analysis-complete.json").exists())
        self.staging()
        self.assertTrue((self.dest / ".rebuild/catalog-inputs/analysis-complete.json").is_file())

    def test_analysis_is_regenerated_once_per_destination(self):
        self.staging()
        self.staging()
        self.assertEqual(catalog_analysis.regenerate.call_count, 1)

    def test_input_identity_drift_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "accepted input"):
            catalog_rebuild.CatalogIO(self.work, self.dest, "f" * 64)

    def test_real_prepare_preserves_original_paths(self):
        with patch.object(whole_catalog, "now", return_value="fresh-time"):
            whole_catalog.prepare_integration()
        self.assertEqual(read(self.catalog / "integration-fresh-time/manifest.json")["attempt"], "integration-fresh-time")
        self.assertIn("new-ui", (self.work / "lab-project" / self.target).read_text())
        self.assertTrue(list(self.catalog.glob("integration-*/import-receipt.json")))
        self.assertTrue((self.work / "lab-project/Assets/Editor/WholeCatalogHost.cs").is_file())
        self.assertFalse((self.work / "lab-project/.rebuild").exists())

    def test_pinned_attempt_is_rebuild_only_and_rejects_path_escape(self):
        for attempt in ("../escape", "integration-../../escape", ""):
            with self.assertRaisesRegex(RuntimeError, "Pinned integration"):
                whole_catalog.prepare_integration(self.staging(), attempt=attempt)
        with self.assertRaisesRegex(RuntimeError, "Pinned integration"):
            whole_catalog.prepare_integration(attempt="integration-pinned")

    def test_identity_pin_drift_or_wrong_input_fails_before_catalog_write(self):
        recipe = read(self.recipes / "build-entry-inputs.json")
        for change, message in ((dict(input_id="wrong"), "requires accepted input"), (dict(bootstrap_attempt="../escape"), "Invalid bootstrap")):
            write(self.recipes / "build-entry-inputs.json", dict(recipe, **change))
            with self.assertRaisesRegex(RuntimeError, message):
                catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, set(), {})
        self.assertFalse((self.dest / ".rebuild/catalog-inputs").exists())

    def test_dependency_walk_sanitizes_pending_import(self):
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        text = staging.read_text(self.dest / self.target)
        self.assertNotIn("--- !u!114 &2", text)
        self.assertIn("new-ui", text)
        staging.flush()
        self.assertTrue(list((self.dest / ".rebuild/composition/rebuild-dependencies").glob("dependency-stage-*/optional-content-transformation.json")))
        self.assertFalse((self.work / "lab-project" / self.target).exists())

    def test_real_dependencies_preserve_original_paths(self):
        composition_migration.stage_missing_sources()
        self.assertNotIn("--- !u!114 &2", (self.work / "lab-project" / self.target).read_text())
        self.assertTrue(list((self.work / "evidence").glob("dependency-stage-*/receipt.json")))
        self.assertFalse((self.work / "lab-project/.rebuild").exists())

    def test_support_source_reads_il_contract_and_destination_owner(self):
        index = read(self.catalog / "source-guid-index.json")
        index["e" * 32] = self.support
        write(self.catalog / "source-guid-index.json", index)
        self.pin()
        self.put(self.dest / self.support_target, (self.export / self.support).read_text())
        self.put(self.dest / (self.support_target + ".meta"), "guid: " + "e" * 32 + "\n")
        staging = self.staging()
        composition_migration.stage_missing_sources(staging)
        self.assertTrue(staging.read_text(self.dest / self.support_target).startswith("using Event = AK.Wwise.Event;\n"))
        whole_catalog.run.assert_called_once()

    def test_real_support_repair_preserves_source_receipt_paths(self):
        project = self.work / "lab-project"
        self.put(project / self.support_target, (self.export / self.support).read_text())
        whole_catalog.repair_support_source(self.export, {self.support: self.support_target}, project, self.work / "evidence")
        self.assertTrue((project / self.support_target).read_text().startswith("using Event ="))
        self.assertTrue((self.work / "evidence/support-source-alias.json").is_file())
        whole_catalog.run.assert_called_once()

    def test_output_drift_does_not_flush_pending_project_files(self):
        staging = self.staging()
        whole_catalog.prepare_integration(staging)
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            catalog_rebuild.verify_outputs(staging, {self.target}, {self.target: dict(sha256="0" * 64, size=1)})
        self.assertFalse((self.dest / self.target).exists())

    def test_dependencies_require_r3_marker(self):
        with self.assertRaisesRegex(RuntimeError, "Run catalog-closure"):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {})

    def test_catalog_coordinator_hash_gate_and_marker(self):
        import hashlib

        content = self.body.replace("old-ui", "new-ui").encode()
        provenance = {self.target: dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))}
        catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual((self.dest / self.target).read_bytes(), content)
        self.assertEqual(read(self.dest / ".rebuild/catalog-closure-complete.json")["input_id"], self.input_id)
        manifest = self.dest / ".rebuild/catalog-inputs/integration-pinned/manifest.json"
        self.assertEqual(read(manifest)["attempt"], "integration-pinned")
        before = manifest.read_bytes()
        with patch.object(whole_catalog, "now", return_value="another-time"):
            catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual(manifest.read_bytes(), before)
        # R7 consumes this regenerated identity without replacing it. WholeCatalogBuild
        # carries the same manifest fields into the payload when adding bundle receipts.
        staging = self.staging()
        whole_catalog.generate_build_bootstrap(staging, read(manifest), dict(input_id=self.input_id, runtime_key_edges=[]))
        bootstrap = staging.read(self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json")
        self.assertEqual(bootstrap["attempt"], read(manifest)["attempt"])
        result = rebuild.compare(
            self.dest,
            self.dest,
            {self.target},
            {**provenance, **{p.relative_to(self.dest).as_posix(): {} for p in self.dest.rglob("*") if p.is_file()}},
            lambda path: path == self.target,
        )
        self.assertTrue(result["equal"])

    def test_catalog_requires_r2_destination_config(self):
        (self.dest / ".rebuild/composition/scene-probe-build.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "from R2"):
            catalog_rebuild.catalog_closure(self.dest, self.work, self.input_id, set(), {})

    def test_dependencies_coordinator_verifies_and_flushes(self):
        import hashlib

        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        content = b"%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Component:\n  ui: new-ui\n"
        provenance = {self.target: dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))}
        catalog_rebuild.dependencies(self.dest, self.work, self.input_id, {self.target}, provenance)
        self.assertEqual((self.dest / self.target).read_bytes(), content)

    def test_later_builder_scene_is_deferred_only_in_rebuild(self):
        scene = "Assets/LabLoadingScene/SourceScenes/synthetic/synthetic.unity"
        for config in (self.work / "scene-probe-build.json", self.dest / ".rebuild/composition/scene-probe-build.json"):
            write(config, dict(prefabAssets=[self.target], scenes=[scene]))
        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        later = dict(producer="repo-builder", evidence=[dict(function="source_scene_candidate.prepare")])
        with patch.object(catalog_rebuild, "verify_outputs", side_effect=lambda staging, *_: staging.flush()):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {scene: later})
        receipt = read(next((self.dest / ".rebuild/composition/rebuild-dependencies").glob("dependency-stage-*/receipt.json")))
        self.assertEqual(receipt["deferred_to_later_steps"], [scene])
        with self.assertRaisesRegex(RuntimeError, "refuse original-source substitution"):
            composition_migration.stage_missing_sources()
        with self.assertRaisesRegex(RuntimeError, "refuse original-source substitution"):
            catalog_rebuild.dependencies(
                self.dest,
                self.work,
                self.input_id,
                set(),
                {scene: dict(producer="repo-builder", evidence=[dict(function="whole_catalog.prepare_integration")])},
            )

    def test_destination_config_is_required_after_r3(self):
        write(self.dest / ".rebuild/catalog-closure-complete.json", dict(input_id=self.input_id))
        (self.dest / ".rebuild/composition/scene-probe-build.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "destination composition config"):
            catalog_rebuild.dependencies(self.dest, self.work, self.input_id, set(), {})

    def test_support_binary_drift_is_rejected(self):
        self.put(self.dest / self.support_target, (self.export / self.support).read_text())
        staging = self.staging()
        self.put(self.binary, "changed binary")
        with self.assertRaisesRegex(RuntimeError, "accepted original field contract"):
            whole_catalog.repair_support_source(self.export, {self.support: self.support_target}, self.dest, self.dest / "receipt", staging)

    def test_auxiliary_reads_use_flushed_destination_config(self):
        staging = self.staging()
        write(self.work / "scene-probe-build.json", dict(prefabAssets=["Assets/MustNotRead.prefab"]))
        self.assertEqual(staging.read(self.work / "scene-probe-build.json")["prefabAssets"], [self.target])

    def test_coordinator_order_and_membership(self):
        self.assertEqual(list(rebuild.STEPS)[:6], ["assemblies", "shader-pipeline", "composition", "project-inputs", "catalog-closure", "dependencies"])
        self.assertEqual(rebuild.STEPS["catalog-closure"].evidence, ("whole_catalog.prepare_integration",))
        self.assertIn("whole_catalog.repair_support_source", rebuild.STEPS["dependencies"].evidence)
