"""Synthetic full-stage contracts; no editor, device, or private game data."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import composition_migration as composition
import composition_io
from composition_io import StageIO
import rebuild
from common import sha, write


class CompositionStageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name).resolve() / "work"
        self.root = self.work.parent
        self.project = self.work / "lab-project"
        self.evidence = self.work / "evidence"
        self.export = self.work / "export"
        self.accepted = "a" * 64
        self.scene = "Assets/WholeGame/Test.unity"
        self.inherited = "Assets/LabLoadingScene/Test.mat"
        self.generated = "Assets/LabLoadingScene/Generated.mat"
        self.scene_data = b"%YAML 1.1\n"
        self.meta = b"guid: " + b"b" * 32 + b"\n"
        self.put(self.export / "Assets/Test.unity", self.scene_data)
        self.put(self.export / "Assets/Test.unity.meta", self.meta)
        self.put(self.export / "Assets/RoR2/Base/Interactables/Chest1/Chest1.prefab", b"  cost: 25\n")
        self.put(self.project / self.scene, self.scene_data)
        self.put(self.project / (self.scene + ".meta"), self.meta)
        self.put(self.work / "observation.json", b"synthetic observation")
        self.put(self.work / "game/Risk of Rain 2_Data/globalgamemanagers.assets", b"synthetic scripts")
        write(self.project / ".port-input.json", dict(input_id=self.accepted, original_assemblies={}, transformed_assemblies={}))
        write(self.work / "config/accepted-input.json", dict(input_id=self.accepted))
        write(self.work / "config/reconstruction.json", dict(projects=["work/export"]))
        write(
            self.work / "config/composition-migration.json",
            dict(input_id=self.accepted, evidence="work/evidence", previous_project="work/previous", shader_sources=[]),
        )
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        write(self.work / "catalog/source-guid-index.json", {"b" * 32: "Assets/Test.unity"})
        write(self.evidence / "rebase-analysis.json", dict(guidmap={}))
        write(
            self.evidence / "asset-analysis.json",
            dict(
                rows=[
                    dict(old=self.scene, old_source="Assets/Test.unity", guid="b" * 32),
                    dict(old=self.inherited, guid="c" * 32, kind=".mat"),
                    dict(old=self.generated, guid="d" * 32, kind=".mat"),
                ]
            ),
        )
        self.plan = dict(
            conflicts=[],
            rows=[
                dict(
                    target=self.scene,
                    source="Assets/Test.unity",
                    current_source_sha256=sha(self.export / "Assets/Test.unity"),
                    output_sha=hashlib.sha256(self.scene_data).hexdigest(),
                    target_before_sha256=hashlib.sha256(self.scene_data).hexdigest(),
                )
            ],
        )
        write(self.evidence / "semantic-preview-result.json", self.plan)
        write(self.work / "scene-probe-build.json", dict(prefabAssets=[], stageScene=self.scene))
        write(self.work / "previous/Assets/LabLoadingScene/Resources/MovementBatchProbe.json", dict(integratedStages=[]))
        write(self.work / "experiments/scene-runtime/current.json", dict(path="work/old-attempt"))
        write(
            self.work / "old-attempt/nova-input-mapping.json", dict(observation="work/observation.json", observation_sha256=sha(self.work / "observation.json"))
        )
        # Exercise the real sanitizer, including its importer identity checks.
        for name, guid in (
            ("Plugins/AK.Wwise.Unity.MonoBehaviour.dll", "2b6c926553287666f24ffd5af5ba21cb"),
            ("Plugins/Decalicious.dll", "90eda32cd325c26600dacf144354b407"),
            ("Plugins/RoR2.dll", "951ce57ad999ac1f040a4dceb5f8b763"),
            ("SilentProjectileBoundary.cs", "e" * 32),
        ):
            self.put(self.project / ("Assets/LabLoadingScene/" + name + ".meta"), ("guid: " + guid + "\n").encode())
        self.put(self.project / self.inherited, b"inherited\n")
        self.put(self.project / (self.inherited + ".meta"), b"guid: " + b"c" * 32 + b"\n")
        asset = dict(
            path=self.inherited,
            project_path=self.inherited,
            status="inherited",
            guid="c" * 32,
            sha256=sha(self.project / self.inherited),
            meta_sha256=sha(self.project / (self.inherited + ".meta")),
        )
        self.ledger = dict(input_id=self.accepted, assets=[asset])
        for suffix in ("", ".meta"):
            self.put(self.work / "inherited-store" / self.accepted / (self.inherited + suffix), (self.project / (self.inherited + suffix)).read_bytes())
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        # Only external inputs and generation cohorts are synthetic; stage, store validation,
        # dependencies, sanitizer, scene contracts, ordering and receipts run normally.
        self.preflight = self.patches.enter_context(patch("build.preflight"))
        self.patches.enter_context(patch("integrated_objective.WORK", self.work))
        self.patches.enter_context(patch("integrated_objective.ROOT", self.root))
        self.patches.enter_context(patch.object(composition, "WORK", self.work))
        self.patches.enter_context(patch.object(composition, "ROOT", self.root))
        self.patches.enter_context(patch.object(composition_io, "WORK", self.work))
        self.patches.enter_context(patch.object(composition_io, "ROOT", self.root))
        self.put(self.root / "tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs", b"authored runtime\n")
        self.patches.enter_context(patch.object(composition, "game", return_value=self.work / "game"))
        self.patches.enter_context(patch("UnityPy.load", return_value=SimpleNamespace(objects=[])))
        self.patches.enter_context(patch("inherited_state.load_ledger", return_value=self.ledger))
        self.patches.enter_context(
            patch(
                "asset_transforms.load_recipe",
                return_value=dict(assets=[dict(output=self.scene, source="Assets/Test.unity", source_sha256=sha(self.export / "Assets/Test.unity"))]),
            )
        )
        self.patches.enter_context(patch("asset_transforms.generate_asset", return_value=(self.scene_data, self.meta)))
        self.patches.enter_context(patch("authored_additions.prepare", return_value={self.generated: (b"generated\n", b"guid: " + b"d" * 32 + b"\n")}))
        for name in ("shader_additions.prepare", "asset_transforms.prepare_decks", "export_additions.prepare", "unity_package_additions.prepare"):
            self.patches.enter_context(patch(name, return_value={}))
        original_read = composition.read
        self.patches.enter_context(
            patch.object(
                composition, "read", side_effect=lambda p: dict(input_id=self.accepted, rows=[]) if Path(p).name == "hud-ui-remaps.json" else original_read(p)
            )
        )

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def snapshot(self):
        return {p.relative_to(self.work): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}

    def run_stage(self, isolated=False):
        staging = StageIO(self.work, self.project if isolated else None)
        with patch.object(staging, "preflight") if isolated else contextlib.nullcontext(), contextlib.redirect_stdout(io.StringIO()):
            composition.stage(staging)
        return staging

    def test_real_stage_writes_original_project_config_and_receipt_paths(self):
        self.run_stage()
        self.assertEqual((self.project / self.generated).read_bytes(), b"generated\n")
        self.assertEqual((self.project / self.inherited).read_bytes(), b"inherited\n")
        self.assertTrue((self.evidence / "staging-result.json").is_file())
        self.assertTrue((self.evidence / "current-original-script-orders.json").is_file())
        self.assertEqual(json.loads((self.work / "experiments/scene-runtime/current.json").read_text()), dict(path="work/evidence"))
        self.assertEqual(json.loads((self.project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json").read_text())["attempt"], "evidence")
        self.assertFalse((self.project / ".rebuild").exists())
        self.assertEqual(self.preflight.call_count, 2)
        self.preflight.assert_called_with()

    def test_isolated_stage_reads_pending_products_and_preserves_all_inputs(self):
        before = self.snapshot()
        staging = self.run_stage(isolated=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(staging.read_bytes(self.project / self.generated), b"generated\n")
        # R2 doesn't run the post-catalog dependency builder or real preflight.
        self.preflight.assert_not_called()
        staging.flush()
        self.assertTrue((self.project / ".rebuild/composition/evidence/staging-result.json").is_file())
        for p, value in before.items():
            if not str(p).startswith("lab-project/"):
                self.assertEqual((self.work / p).read_bytes(), value[0])

    def test_removed_binding_guard_remains_live_and_is_deferred_only_for_rebuild(self):
        write(self.work / "scene-probe-build.json", dict(prefabAssets=[], stageScene=self.scene, later="Assets/SourceScenes/Later.unity"))
        with self.assertRaisesRegex(RuntimeError, "removed or unowned"):
            self.run_stage()
        staging = self.run_stage(isolated=True)
        self.assertEqual(staging.read(self.evidence / "missing-runtime-bindings.json"), ["Assets/SourceScenes/Later.unity"])
        self.assertEqual(staging.read(self.work / "scene-probe-build.json")["later"], "Assets/SourceScenes/Later.unity")
        with self.assertRaisesRegex(RuntimeError, "not runnable yet"):
            rebuild.rebuild_step("validate-bindings", work=self.work)

    def test_conflict_guard_stops_before_stage_writes(self):
        self.plan["conflicts"] = ["synthetic"]
        write(self.evidence / "semantic-preview-result.json", self.plan)
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "Unresolved serialized rebase"):
            self.run_stage(isolated=True)
        self.assertEqual(before, self.snapshot())

    def test_export_source_hash_guard(self):
        self.put(self.export / "Assets/Test.unity", b"drift")
        with self.assertRaisesRegex(RuntimeError, "provenance drift"):
            self.run_stage(isolated=True)

    def test_destination_body_conflict_guard(self):
        self.put(self.project / self.scene, b"drift")
        with self.assertRaisesRegex(RuntimeError, "changed after the rebase"):
            self.run_stage(isolated=True)

    def test_destination_meta_conflict_guard(self):
        self.put(self.project / (self.scene + ".meta"), b"guid: " + b"f" * 32 + b"\n")
        with self.assertRaisesRegex(RuntimeError, "metadata differs"):
            self.run_stage(isolated=True)

    def test_duplicate_guid_guard(self):
        self.put(self.project / "Assets/Duplicate.meta", self.meta)
        with self.assertRaisesRegex(RuntimeError, "Duplicate current GUID"):
            self.run_stage(isolated=True)

    def test_mapping_observation_hash_guard(self):
        self.put(self.work / "observation.json", b"drift")
        with self.assertRaisesRegex(RuntimeError, "mapping evidence changed"):
            self.run_stage(isolated=True)

    def test_overlay_glob_and_deletion(self):
        staging = StageIO(self.work, self.project)
        target = self.project / "Assets/New/Thing.mat"
        staging.apply(target, b"new")
        self.assertIn(target, staging.glob(self.project / "Assets", "**/*.mat"))
        staging.apply(target, delete=True)
        self.assertNotIn(target, staging.glob(self.project / "Assets", "**/*.mat"))
        self.assertFalse(staging.is_file(target))
        with self.assertRaises(FileNotFoundError):
            staging.read_bytes(target)

    def test_write_boundary_rejects_escapes_and_links(self):
        import os

        staging = StageIO(self.work, self.project)
        for path in (self.root / "outside", self.project / "../escape"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                staging.apply(path, b"bad")
        link = self.project / "link"
        link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            staging.apply(link / "escape", b"bad")
        link.unlink()
        os.link(self.work / "observation.json", link)
        with self.assertRaises(RuntimeError):
            staging.apply(link, b"bad")

    def prepare_coordinator(self):
        self.recipe_dir = self.root / "recipe"
        write(self.recipe_dir / "composition-export-copies.json", dict(schema=1, input_id=self.accepted, copies=[]))
        write(self.recipe_dir / "original-assemblies.json", dict(input_id=self.accepted, assemblies=[]))
        write(self.recipe_dir / "project-layout.json", dict(dependencies={"synthetic": "1"}))
        write(self.work / "config/reconstruction.json", dict(input_id=self.accepted, projects=["work/export"]))
        write(self.work / "catalog/reconciled-closure.json", dict(input_id=self.accepted, files=["Assets/Test.unity"]))
        write(self.work / "catalog/source-catalog.json", dict(keys=[], locations=[]))
        write(self.work / "catalog/native-conversions.json", dict(issues=[]))
        self.destination = self.work / "rebuild/r2/lab-project"
        payload = {
            self.scene: ("export-copy", self.scene_data),
            self.scene + ".meta": ("export-copy", self.meta),
            self.generated: ("recipe-transform", b"generated\n"),
            self.generated + ".meta": ("recipe-transform", b"guid: " + b"d" * 32 + b"\n"),
            self.inherited: ("inherited-store", b"inherited\n"),
            self.inherited + ".meta": ("generator", b"guid: " + b"c" * 32 + b"\n"),
            "Packages/manifest.json": ("recipe-transform", b'{\n  "dependencies": {\n    "synthetic": "1"\n  }\n}\n'),
        }
        self.provenance = {p: dict(producer=producer, size=len(data), sha256=hashlib.sha256(data).hexdigest()) for p, (producer, data) in payload.items()}
        for p, (_, data) in payload.items():
            self.put(self.project / p, data)
        self.provenance["Assets/LabLoadingScene/AndroidNativeDeferredPresentation.cs"] = dict(producer="tool-owned")
        self.provenance["Assets/LabLoadingScene/Resources/MovementBatchProbe.json"] = dict(producer="repo-builder")
        write(self.work / "receipts/provenance-map.json", self.provenance)
        self.patches.enter_context(patch.object(composition_io, "RECIPE", self.recipe_dir))
        self.patches.enter_context(patch.object(rebuild, "ROOT", self.root))
        self.patches.enter_context(patch.object(rebuild, "game", return_value=self.work / "game"))
        self.patches.enter_context(patch.object(StageIO, "preflight"))
        self.patches.enter_context(patch("assembly_transforms.load_recipe", return_value=dict(input_id=self.accepted, steps=[])))

    def test_coordinator_runs_real_stage_and_compares_each_producer_without_input_writes(self):
        self.prepare_coordinator()
        before = self.snapshot()
        with contextlib.redirect_stdout(io.StringIO()):
            result = rebuild.rebuild_step("composition", dest=self.destination, work=self.work)
        self.assertTrue(result["equal"], result)
        self.assertEqual(result["counts"], dict(identical=7, different=0, missing=0, extra=0))
        for path, value in before.items():
            self.assertEqual((self.work / path).read_bytes(), value[0], path)
        marker = json.loads((self.destination / ".port-input.json").read_text())
        self.assertEqual(marker["input_id"], self.accepted)
        self.assertTrue((self.destination / ".rebuild/composition/evidence/staging-result.json").is_file())
        with patch.object(rebuild, "game", side_effect=AssertionError("compare-only must not read installation")):
            self.assertTrue(rebuild.rebuild_step("composition", dest=self.destination, work=self.work, compare_only=True)["equal"])

    def test_coordinator_refuses_incomplete_export_membership(self):
        self.prepare_coordinator()
        self.provenance["Assets/Unspecified.asset"] = dict(producer="export-copy")
        write(self.work / "receipts/provenance-map.json", self.provenance)
        with self.assertRaisesRegex(RuntimeError, "Incomplete export-copy membership"):
            rebuild.rebuild_step("composition", dest=self.destination, work=self.work)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_coordinator_export_drift_stops_before_placement(self):
        self.prepare_coordinator()
        self.put(self.export / "Assets/Test.unity", b"drift")
        with self.assertRaisesRegex(RuntimeError, "Export copy drift"):
            rebuild.rebuild_step("composition", dest=self.destination, work=self.work)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_coordinator_generated_hash_drift_stops_before_flushing_stage(self):
        self.prepare_coordinator()
        self.provenance[self.generated]["sha256"] = "wrong"
        write(self.work / "receipts/provenance-map.json", self.provenance)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            rebuild.rebuild_step("composition", dest=self.destination, work=self.work)
        self.assertFalse((self.destination / self.generated).exists())


class ExportMembershipTests(unittest.TestCase):
    def test_closure_and_relocation_recipe(self):
        result = composition_io.export_membership(
            dict(files=["Assets/A.asset", "Assets/Plugin.dll"]), dict(copies=[["Assets/Relocated.mat", "Assets/Lab/Thing.mat"]])
        )
        self.assertEqual(
            result,
            {
                "Assets/WholeGame/A.asset": "Assets/A.asset",
                "Assets/WholeGame/A.asset.meta": "Assets/A.asset.meta",
                "Assets/Lab/Thing.mat": "Assets/Relocated.mat",
            },
        )

    def test_catalog_mesh_membership_adds_body_and_importer(self):
        result = composition_io.export_membership(dict(files=[]), dict(copies=[]), ["Assets/Mesh.asset"])
        self.assertEqual(result, {"Assets/WholeGame/Mesh.asset": "Assets/Mesh.asset", "Assets/WholeGame/Mesh.asset.meta": "Assets/Mesh.asset.meta"})

    def test_duplicate_conflicting_and_unsafe_membership(self):
        for rows in (
            [["Assets/A", "Assets/X"], ["Assets/A", "Assets/X"]],
            [["Assets/B", "Assets/WholeGame/A"]],
            [["../A", "Assets/A"]],
            [["Assets/A", "../A"]],
        ):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                composition_io.export_membership(dict(files=["Assets/A"]), dict(copies=rows))

    def test_tracked_recipe_contains_only_identities(self):
        recipe = json.loads((Path(__file__).resolve().parents[1] / "recipe/composition-export-copies.json").read_text())
        self.assertEqual(set(recipe), {"schema", "input_id", "copies"})
        self.assertEqual(len(recipe["copies"]), 128)
        self.assertEqual(len({r[1] for r in recipe["copies"]}), 128)
        for row in recipe["copies"]:
            self.assertEqual(len(row), 2)
            for path in row:
                rebuild.relative_path(path)
