"""R7/R8 synthetic host contracts, including unchanged production write locations."""

import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build
import build_entry_rebuild as replay
import catalog_analysis
import catalog_rebuild
import rebuild
import recovery
import whole_catalog
from common import read, sha, write
from composition_io import StageIO


class BuildEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.work = self.root / "inputs"
        for name, value in (("assert_build_unblocked", lambda: None), ("HOST_BUILD_LOCK", self.root / "unity-build.lock")):
            patcher = patch("build_lock." + name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dest = self.root / "clone/work/rebuild/project"
        self.recipe = self.root / "recipe"
        self.input_id = "a" * 64
        self.project = self.work / "lab-project"
        self.export = self.work / "export"
        self.assembly = self.work / "installation/Risk of Rain 2_Data/Managed/RoR2.dll"
        self.put(self.assembly, "original assembly")
        write(self.work / "config/local.json", dict(game_path=str(self.assembly.parents[2])))
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/reconstruction.json", dict(projects=[str(self.export)]))
        self.manifest = dict(
            input_id=self.input_id,
            attempt="integration-historical",
            locations=[dict(type="Example.Type, Example", path="Assets/Example.asset")],
            keys=[dict(key="effect")],
        )
        self.contract = dict(input_sha256=sha(self.assembly), legacyAliases={})
        self.contracts = dict(contracts=[dict(target_imported=dict(assembly="Example", type="Example.Nested+Type"))])
        self.closure = dict(input_id=self.input_id, runtime_key_edges=[dict(field="preloadGUIDReferences", key="absent", locations=[])])
        for name, value in (("original-catalog-contract.json", self.contract), ("reconciled-closure.json", self.closure)):
            write(self.work / "analysis" / name, value)

        def regenerate(work, out, input_id):
            # Host regeneration has its own tests; publish the synthetic analysis cohort.
            for name in catalog_analysis.OUTPUTS:
                source = self.work / "analysis" / name
                (out / name).write_bytes(source.read_bytes() if source.is_file() else b"{}")

        self.start(patch.object(catalog_analysis, "regenerate", side_effect=regenerate))
        source = "public static GameObject effect;\npublic static void Resolve() {\n" + (
            'asyncOperationHandle = Addressables.LoadAssetAsync<GameObject>("effect");\n'
            "asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x) { effect = x.Result; };\n\t\t}\n"
        )
        common = "public static class CommonAssets {\n"
        for n in ("groundOnHitPrefab", "hollowPack"):
            common += "public static GameObject " + n + ';\nasyncOperationHandle = Addressables.LoadAssetAsync<GameObject>("' + n + '");\n'
            common += "asyncOperationHandle.Completed += delegate(AsyncOperationHandle<GameObject> x) { " + n + " = x.Result; };\n"
        common += "}\npublic static GlobalEventManager instance;"
        decompiled = {}
        for name, data in (("CharacterBody.cs", source), ("HealthComponent.cs", source), ("GlobalEventManager.cs", common)):
            p = self.work / "sources" / name
            self.put(p, data)
            decompiled[name] = dict(path="RoR2/" + name, sha256=sha(p))
        p = self.work / "sources/contracts.json"
        write(p, self.contracts)
        files = {"contracts.json": dict(path=str(p.relative_to(self.work)), sha256=sha(p))}
        write(
            self.recipe / "build-entry-inputs.json",
            dict(
                schema=2,
                input_id=self.input_id,
                bootstrap_attempt=self.manifest["attempt"],
                decompiled=dict(assembly="RoR2.dll", assembly_sha256=sha(self.assembly), ilspy=recovery.ILSPY, files=decompiled),
                files=files,
            ),
        )
        self.decompiles = []

        def decompile(assembly, references, dest):
            # Stands in for the pinned ilspycmd run: the regenerated tree is the fixture sources.
            self.decompiles.append((assembly, references))
            for name in decompiled:
                self.put(Path(dest) / "RoR2" / name, (self.work / "sources" / name).read_text())
            return SimpleNamespace(returncode=0)

        self.start(patch.object(recovery, "ilspy_project", decompile))
        self.start(patch.object(recovery, "require_ilspy", lambda: None))
        self.runtime = "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
        write(self.recipe / "runtime-config.json", dict(stageCombatDecks=[]))
        write(self.recipe / "content.json", dict(prefabAssets=["Assets/Example.asset"]))
        write(self.recipe / "runtime-sources.json", ["runtime/Session.cs"])
        self.put(self.root / "tools/unity/runtime/Session.cs", "class Session {}")
        for name in (
            "AndroidProgressionHost",
            "AndroidDiscoveryHost",
            "AndroidProfileHost",
            "AndroidLifecycleHost",
            "SurvivorSkillHost",
            "SurvivorSkillInputHost",
            "SirenEncounterHost",
            "TeleporterLifetimeHost",
            "TeleportOverlayLifetimeHost",
            "EngiShieldHitGuardHost",
            "EngineerNativeOutputObserverFixture",
            "SirenEggDiagnosticInputExactEditorFixture",
            "LightningStakeSourceContractFixture",
            "TeleporterExitTraceSourceContractFixture",
            "SkillResponseCleanupExactEditorFixture",
            "SurvivorCombatOutputObserverFixture",
            "DeveloperSkillVariantSelectionFixture",
            "FirstStageDiagnosticGateFixture",
            "NativeDirectorDeckSetterFixture",
            "SourceIdentityTransformParityFixture",
            "MercEvisImpactEffectExactEditorFixture",
            "WholeCatalogBuild",
        ):
            self.put(self.root / "tools/catalog" / (name + ".cs"), "class " + name + " {}")
        self.put(self.root / "android/Assets/Editor/LabBuild.cs", "class LabBuild {}")
        self.put(self.root / "android/Assets/LabDiagnostics.cs", "class LabDiagnostics {}")
        self.clip = "Assets/WholeGame/attack.anim"
        key = zlib.crc32(b"Attack")
        self.clip_source = f"    attribute: typetree_0x{key:X}_unknown\n      attribute: {key}\n      script: {{fileID: 0}}\n      typeID: 95\n"
        self.put(self.export / "Assets/attack.anim", self.clip_source)
        self.put(self.dest / "Assets/WholeGame/source.controller", "  - m_Name: Attack\n")
        self.put(self.project / "Assets/WholeGame/source.controller", "  - m_Name: Attack\n")
        write(self.dest / ".rebuild/source-scenes-complete.json", dict(input_id=self.input_id))
        write(self.dest / ".rebuild/composition/scene-probe-build.json", {})
        analysis = self.dest / ".rebuild/catalog-inputs"
        write(analysis / "integration-latest.json", dict(path="destination/.rebuild/catalog-inputs/integration-generated"))
        write(analysis / "integration-generated/manifest.json", self.manifest)
        for module in (build, replay, catalog_rebuild):
            self.start(patch.object(module, "RECIPE", self.recipe))
        for module in (build, whole_catalog):
            self.start(patch.object(module, "ROOT", self.root))
            self.start(patch.object(module, "WORK", self.work))
        self.start(patch.object(StageIO, "preflight"))
        # Produce the oracle through the actual production helpers and production paths.
        io = StageIO(self.work)
        build.generate_runtime_config(self.project)
        build.generate_content_recipe()
        self.put(self.project / self.clip, self.clip_source)
        whole_catalog.generate_build_maps(io, self.manifest, self.contract, self.work / "sources/CharacterBody.cs")
        whole_catalog.generate_build_bootstrap(io, self.manifest, self.closure)
        self.r7 = {
            self.runtime,
            self.clip,
            "Assets/LabLoadingScene/Resources/WholeStageContexts.json",
            "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json",
        }
        self.r7.update("Assets/LabLoadingScene/Original" + n + "Map.cs" for n in ("BodyVisual", "HealthVisual", "GlobalCommonAsset"))
        whole_catalog.stage_build_sources(io, build.runtime_sources(), self.manifest, self.contracts)
        build.stage_android_assets(self.project)
        self.r8 = {str(p.relative_to(self.project)) for p in self.project.rglob("*") if p.is_file()} - self.r7 - {"Assets/WholeGame/source.controller"}
        self.provenance = {p: dict(producer="repo-builder", sha256=sha(self.project / p), size=(self.project / p).stat().st_size) for p in self.r7 | self.r8}

    def start(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}

    def r7_run(self):
        replay.build_entries(self.dest, self.work, self.input_id, self.r7, self.provenance)

    def r8_run(self):
        replay.runtime_sources(self.dest, self.work, self.input_id, self.r8, self.provenance)

    def test_two_steps_match_real_helpers_and_never_write_inputs(self):
        before = self.snapshot()
        self.r7_run()
        self.r8_run()
        for path in self.r7 | self.r8:
            self.assertEqual((self.dest / path).read_bytes(), (self.project / path).read_bytes(), path)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(read(self.dest / ".rebuild/composition/scene-probe-build.json"), read(self.recipe / "content.json"))
        self.assertIn('fullname="Example.Nested/Type"', (self.dest / "Assets/LabLoadingScene/WholeCatalogPreservation/link.xml").read_text())

    def test_r7_refuses_stale_r3_identity_instead_of_overriding_bootstrap(self):
        write(self.dest / ".rebuild/catalog-inputs/integration-generated/manifest.json", dict(self.manifest, attempt="integration-new"))
        with self.assertRaisesRegex(RuntimeError, "rerun catalog-closure"):
            self.r7_run()
        self.assertFalse((self.dest / "Assets/LabLoadingScene/Resources/WholeCatalogBootstrap.json").exists())

    def test_registered_steps_select_map_membership_and_compare_only_avoids_installation(self):
        for path in self.r7:
            self.provenance[path]["evidence"] = [dict(function="whole_catalog.build_integration")]
        for path in self.r8:
            self.provenance[path]["producer"] = "tool-owned"
            self.provenance[path]["evidence"] = [dict(owner="build.py / whole_catalog.build_integration source staging")]
        self.provenance["Assets/WholeGame/source.controller"] = dict(producer="unity-generated")
        write(self.work / "receipts/provenance-map.json", self.provenance)
        with patch.object(rebuild, "ROOT", self.root / "clone"):
            for name, expected in (("build-entries", len(self.r7)), ("runtime-sources", len(self.r8))):
                result = rebuild.rebuild_step(name, dest=self.dest, work=self.work)
                self.assertTrue(result["equal"], result)
                self.assertEqual(result["counts"]["identical"], expected)
                with patch.object(rebuild, "game", side_effect=AssertionError("compare-only must not read installation")):
                    self.assertTrue(rebuild.rebuild_step(name, dest=self.dest, work=self.work, compare_only=True)["equal"])
        coverage = rebuild.provenance_coverage(self.provenance)
        self.assertEqual(coverage["counts"]["build-entries"], len(self.r7))
        self.assertEqual(coverage["counts"]["runtime-sources"], len(self.r8))
        self.assertIn("Assets/WholeGame/source.controller", coverage["uncovered"])

    def test_order_pins_and_output_hashes_fail_before_publishing_project_files(self):
        with self.assertRaisesRegex(RuntimeError, "build-entries"):
            self.r8_run()
        self.provenance[self.runtime]["sha256"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.r7_run()
        self.assertFalse((self.dest / self.runtime).exists())
        self.assertFalse((self.dest / ".rebuild/build-entries-complete.json").exists())
        self.put(self.work / "sources/CharacterBody.cs", "drift")
        with self.assertRaisesRegex(RuntimeError, "Regenerated decompiled input differs: CharacterBody.cs"):
            self.r7_run()
        self.assertFalse((self.dest / ".rebuild/decompiled").exists() and any((self.dest / ".rebuild/decompiled").iterdir()))
        self.put(self.work / "sources/contracts.json", "drift")
        with self.assertRaisesRegex(RuntimeError, "input drift: contracts.json"):
            self.r7_run()

    def test_decompiled_inputs_come_from_the_accepted_assembly_only(self):
        self.r7_run()
        self.assertEqual(self.decompiles, [(self.assembly, self.assembly.parent)])
        self.assertTrue((self.dest / ".rebuild/build-entries-complete.json").exists())
        self.r8_run()
        self.assertEqual(len(self.decompiles), 1, "R8 needs no decompiled source")
        recipe = read(self.recipe / "build-entry-inputs.json")
        recipe["decompiled"]["assembly_sha256"] = "0" * 64
        write(self.recipe / "build-entry-inputs.json", recipe)
        with self.assertRaisesRegex(RuntimeError, "accepted assembly and pinned decompiler"):
            self.r7_run()

    def test_runtime_sources_preserves_existing_importers_and_hash_gates(self):
        self.r7_run()
        meta = self.dest / "Assets/LabLoadingScene/Session.cs.meta"
        self.put(meta, "Unity-owned metadata")
        self.provenance[next(iter(self.r8))]["sha256"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "differs from provenance"):
            self.r8_run()
        self.assertFalse((self.dest / "Assets/LabLoadingScene/Session.cs").exists())
        self.assertEqual(meta.read_text(), "Unity-owned metadata")

    def test_actual_code_build_calls_shared_producers_in_the_original_order(self):
        from contextlib import ExitStack
        from common import digest
        import animation_bindings
        import body_visual_map
        import common_assets_map

        out = self.work / "catalog"
        attempt = out / "integration"
        contracts = out / "contracts"
        write(self.work / "experiments/whole-catalog/latest.json", dict(path=str(out)))
        write(out / "integration-latest.json", dict(path=str(attempt)))
        write(out / "contracts-latest.json", dict(path=str(contracts)))
        write(attempt / "host-integration.json", dict(success=True))
        write(attempt / "manifest.json", self.manifest)
        write(out / "original-catalog-contract.json", self.contract)
        write(out / "reconciled-closure.json", self.closure)
        write(contracts / "result.json", self.contracts)
        key = digest(dict(input=sha(self.assembly), ilspy="11.0.0.9375", args="project-referencepath-csharp9-v2"))
        for name in ("CharacterBody.cs", "HealthComponent.cs", "GlobalEventManager.cs"):
            self.put(self.work / "decompiled/RoR2" / key[:16] / "RoR2" / name, (self.work / "sources" / name).read_text())
        order = []

        def tracked(module, name):
            function = getattr(module, name)

            def invoke(*args, **kwargs):
                order.append(name)
                return function(*args, **kwargs)

            return patch.object(module, name, side_effect=invoke)

        with ExitStack() as stack:
            for module, name in (
                (build, "generate_runtime_config"),
                (build, "generate_content_recipe"),
                (whole_catalog, "generate_build_maps"),
                (body_visual_map, "generate"),
                (common_assets_map, "generate"),
                (animation_bindings, "repair"),
                (whole_catalog, "original_stage_contexts"),
                (whole_catalog, "stage_build_sources"),
                (whole_catalog, "preservation_descriptor"),
                (whole_catalog, "generate_build_bootstrap"),
            ):
                stack.enter_context(tracked(module, name))
            stack.enter_context(patch.object(whole_catalog, "game", return_value=self.assembly.parents[2]))
            stack.enter_context(
                patch.object(build, "validate_runtime_source_membership", side_effect=lambda project: order.append("membership") or build.runtime_sources())
            )
            actual_build = stack.enter_context(patch.object(build, "build", side_effect=lambda *a, **kw: order.append("build") or dict(host_fixture=True)))
            freeze = stack.enter_context(patch.object(build, "freeze_whole_payload"))
            whole_catalog.build_integration(code_only=True)
        self.assertEqual(
            order,
            [
                "generate_runtime_config",
                "generate_content_recipe",
                "membership",
                "generate_build_maps",
                "generate",
                "generate",
                "generate",
                "repair",
                "original_stage_contexts",
                "stage_build_sources",
                "preservation_descriptor",
                "generate_build_bootstrap",
                "build",
            ],
        )
        actual_build.assert_called_once_with("vulkan", force=True, reuse_payload=True)
        freeze.assert_not_called()
        self.assertEqual(read(self.work / "whole-catalog-build.json"), dict(manifest=str(attempt / "manifest.json")))
        self.assertEqual(read(attempt / "build.json"), dict(host_fixture=True))

    def binding_setup(self):
        r9 = read(Path(__file__).resolve().parents[1] / "recipe/rebuild-r9-obligations.json")
        write(self.recipe / "rebuild-r9-obligations.json", r9)
        for path in r9["files"]:
            self.provenance[path] = dict(producer="unknown", sha256="f" * 64, size=42)
        self.r7_run()
        self.r8_run()
        write(self.dest / ".rebuild/importer-identities-complete.json", dict(input_id=self.input_id))
        write(self.recipe / "rebuild-binding-targets.json", dict(schema=1, input_id=self.input_id, targets=[self.runtime]))
        write(self.dest / ".rebuild/composition/evidence/missing-runtime-bindings.json", [self.runtime])
        write(self.dest / ".rebuild/composition/evidence/dependency-stage-test/receipt.json", dict(input_id=self.input_id, deferred_to_later_steps=[self.clip]))
        write(self.dest / ".rebuild/stage-variants/result.json", dict(input_id=self.input_id, unity_import_deferred=["Assets/graph.asset"]))
        self.put(self.dest / "Assets/graph.asset", "export graph; awaits R9")
        self.provenance["Assets/graph.asset"] = dict(producer="unity-generated")

    def validate(self):
        return replay.validate_bindings(self.dest, self.work, self.input_id, provenance=self.provenance)

    def test_bindings_check_both_receipts_and_allow_r9_graphs_without_requiring_final_hash(self):
        self.binding_setup()
        result = self.validate()
        self.assertTrue(result["equal"])
        self.assertEqual(result["checked"], 2)
        self.assertEqual(len(result["r9_obligations"]), 2)
        for path, row in result["r9_obligations"].items():
            self.assertEqual(row["sha256"], "f" * 64)
            self.assertFalse((self.dest / path).exists())
            self.assertIn("producer", row)
            self.assertIn("setup", row)
        self.assertEqual(result["unity_import_deferred"], ["Assets/graph.asset"])
        (self.dest / self.clip).unlink()
        self.assertEqual(self.validate()["missing"], [self.clip])

    def test_bindings_fail_closed_on_absent_receipt_omitted_j565_target_and_unsafe_path(self):
        self.binding_setup()
        receipt = self.dest / ".rebuild/composition/evidence/missing-runtime-bindings.json"
        for value in ([self.clip], [self.runtime, "../escape"]):
            write(receipt, value)
            with self.assertRaises(RuntimeError):
                self.validate()
        receipt.unlink()
        with self.assertRaisesRegex(RuntimeError, "unique regenerated"):
            self.validate()

    def test_binding_gate_requires_importer_identity_completion(self):
        self.binding_setup()
        (self.dest / ".rebuild/importer-identities-complete.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "importer-identities"):
            self.validate()

    def test_binding_validation_is_read_only(self):
        self.binding_setup()
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.dest.rglob("*") if p.is_file()}
        self.validate()
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.dest.rglob("*") if p.is_file()})


class ProductionOrderTests(unittest.TestCase):
    def test_code_build_retains_producer_order_and_build_arguments(self):
        # Inspect the actual function's AST, including the extracted functions. No Unity call.
        import ast
        import inspect

        def calls(function):
            tree = ast.parse(inspect.getsource(function))
            return [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]

        order = calls(whole_catalog._build_integration)
        expected = [
            "generate_runtime_config",
            "generate_content_recipe",
            "validate_runtime_source_membership",
            "generate_build_maps",
            "stage_build_sources",
            "generate_build_bootstrap",
            "build",
        ]
        indices = [order.index(name) for name in expected]
        self.assertEqual(indices, sorted(indices))
        source = inspect.getsource(whole_catalog._build_integration)
        self.assertIn('build("vulkan", force=True, reuse_payload=code_only)', source)
        maps = calls(whole_catalog.generate_build_maps)
        self.assertEqual(
            [name for name in maps if name.startswith("generate_") or name.startswith("repair_")],
            ["generate_body_visual_map", "generate_body_visual_map", "generate_common_asset_map", "repair_animation_bindings"],
        )
        self.assertLess(calls(build.build).index("validate_staged_runtime_sources"), calls(build.build).index("stage_android_assets"))
