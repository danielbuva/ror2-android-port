"""Synthetic R5/R6 contracts; no real-data replay, editor or device."""

import contextlib
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import catalog_rebuild
import composition_io
import nova_bridge
import rebuild
import scene_rebuild
import source_scene_candidate
import stage_variants
from common import read, sha, write
from composition_io import StageIO
from composition_migration import scene_contract


# RoR2.Navigation.NodeGraph under the R1 RoR2.dll importer GUID (script_identity).
NODE_GRAPH_SCRIPT = "  m_Script: {fileID: -609359282, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}\n"


class SceneRebuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.work = self.root / "work"
        self.dest = self.root / "destination"
        self.export = self.work / "export"
        self.recipes = self.root / "recipe"
        self.input_id = "a" * 64
        self.name = "goldshores"
        self.relative = "Assets/WholeGame/RoR2/Base/Scenes/goldshores/goldshores.unity"
        self.source = self.export / self.relative.replace("Assets/WholeGame/", "Assets/", 1)
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        write(self.work / "config/reconstruction.json", dict(projects=["work/export"]))
        write(self.recipes / "hud-ui-remaps.json", dict(rows=[]))
        self.source_text = "%YAML 1.1\n"
        for i, name in enumerate(("RoR2Application", "SceneInfo", "Director", "GameManager", "Zone"), 1):
            components = [i * 10]
            if name == "Zone":
                components += [51, 52, 53, 54]
            self.source_text += (
                f"--- !u!1 &{i}\nGameObject:\n  m_Component:\n"
                + "".join(f"  - component: {{fileID: {fid}}}\n" for fid in components)
                + f"  m_Name: {name}\n  m_IsActive: 1\n"
                + f"--- !u!4 &{i * 10}\nTransform:\n  m_GameObject: {{fileID: {i}}}\n  m_Children: []\n  m_Father: {{fileID: 0}}\n"
            )
        self.source_text += "--- !u!65 &51\nBoxCollider:\n  m_GameObject: {fileID: 5}\n  m_IsTrigger: 1\n  m_Enabled: 1\n"
        for fid, script, guid in (
            (52, "-376374237", "951ce57ad999ac1f040a4dceb5f8b763"),
            (53, "372142912", "d382a022563c7517aadbc92ca1060016"),
            (54, "-1895344032", "951ce57ad999ac1f040a4dceb5f8b763"),
            (55, "1", source_scene_candidate.NO_AUDIO_GUID),
            (56, *next(iter(source_scene_candidate.UNAVAILABLE_RENDER_SCRIPTS))),
        ):
            self.source_text += (
                f"--- !u!114 &{fid}\nMonoBehaviour:\n  m_GameObject: {{fileID: 5}}\n  m_Enabled: 1\n  m_Script: {{fileID: {script}, guid: {guid}, type: 3}}\n"
            )
        self.source_text += "  groundNodesAsset: {fileID: 1, guid: " + "b" * 32 + ", type: 2}\n"
        self.source_text += "  airNodesAsset: {fileID: 1, guid: " + "c" * 32 + ", type: 2}\n"
        self.put(self.source, self.source_text)
        self.put(Path(str(self.source) + ".meta"), "fileFormatVersion: 2\nguid: " + "d" * 32 + "\n")
        self.put(self.work / "moon-script-identities.txt", "-1895344032|951ce57ad999ac1f040a4dceb5f8b763|RoR2.TeamFilter\n")
        self.index = {}
        self.baseline = {}
        for guid, name in (("b" * 32, "ground"), ("c" * 32, "air")):
            source = "Assets/Graphs/" + name + ".asset"
            self.index[guid] = source
            self.put(self.export / source, "synthetic graph " + name + "\n" + NODE_GRAPH_SCRIPT)
            self.put(self.export / (source + ".meta"), "guid: " + guid + "\n")
            relative = "Assets/WholeGame/" + source.removeprefix("Assets/")
            for project in (self.dest, self.work / "lab-project"):
                self.put(project / relative, "synthetic graph " + name + "\n" + NODE_GRAPH_SCRIPT)
                self.put(project / (relative + ".meta"), "guid: " + guid + "\n")
            self.baseline[relative] = sha(self.export / source)
        write(self.work / "whole-catalog-code-base.json", dict(files=self.baseline))
        for project in (self.dest, self.work / "lab-project"):
            write(project / ".port-input.json", dict(input_id=self.input_id))
            stages = [dict(name=name, scene="Assets/WholeGame/RoR2/Base/Scenes/" + name + "/" + name + ".unity") for name in ("skymeadow", "shipgraveyard")]
            write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", dict(integratedStages=stages, stageCombatDecks=[]))
            for name in ("skymeadow", "shipgraveyard"):
                relative = "Assets/RoR2/Base/Scenes/" + name + "/" + name + ".unity"
                self.put(self.export / relative, "%YAML 1.1\n--- !u!1 &1\nGameObject:\n  m_Name: Synthetic\n")
                self.put(project / relative.replace("Assets/", "Assets/WholeGame/", 1), (self.export / relative).read_text())
        selection = dict(nextStageScenes=[], prefabAssets=[])
        write(self.work / "scene-probe-build.json", selection)
        write(self.dest / ".rebuild/composition/scene-probe-build.json", selection)
        self.catalog = self.dest / ".rebuild/catalog-inputs"
        write(self.catalog / "source-guid-index.json", self.index)
        write(self.catalog / "integration-latest.json", dict(path="destination/.rebuild/catalog-inputs/integration-test"))
        write(self.catalog / "integration-test/manifest.json", dict(locations=[]))
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for module in (composition_io, nova_bridge, source_scene_candidate, stage_variants):
            stack.enter_context(patch.object(module, "WORK", self.work))
            stack.enter_context(patch.object(module, "ROOT", self.root))
        stack.enter_context(patch.object(source_scene_candidate, "RECIPE", self.recipes))
        stack.enter_context(patch.object(scene_rebuild, "RECIPE", self.recipes))
        rows = [dict(source="RoR2.dll", sha256="0" * 64, guid="951ce57ad999ac1f040a4dceb5f8b763")]
        write(self.recipes / "original-assemblies.json", dict(schema=1, input_id=self.input_id, assemblies=rows))
        stack.enter_context(patch.object(StageIO, "preflight"))
        stack.enter_context(patch("whole_catalog.original_stage_contexts", return_value=dict(synthetic=True)))
        self.io = StageIO(self.work, self.dest)
        self.io.catalog = lambda: self.catalog

    def put(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}

    def project_scene(self):
        spec = nova_bridge.stage_first_stage_geometry(
            self.dest / "Assets/LabLoadingScene",
            self.dest / ".rebuild/projection",
            original_name=True,
            scene_name=self.name,
            map_zones=True,
            presentation=True,
            billboards=True,
            io=self.io,
        )
        target = self.dest / "Assets/LabLoadingScene/StageGeometry/goldshores.unity"
        return self.io.read_text(target), spec

    def replay(self):
        text, _ = self.project_scene()
        self.io.pending.clear()
        with patch.dict(stage_variants.VARIANTS, {self.name: hashlib.sha256(text.encode()).hexdigest()}, clear=True):
            stage_variants.stage(self.io)
        return text

    def test_projection_and_pending_reads_preserve_input_and_contract(self):
        before = self.snapshot()
        text, spec = self.project_scene()
        checked, counts, removed = scene_contract(self.source_text, text)
        self.assertEqual(checked, text)
        self.assertEqual(removed, [])
        self.assertEqual(spec["mapZoneCount"], 1)
        self.assertEqual(spec["mapZoneNetworkObjects"], 1)
        self.assertEqual(spec["previewNames"], counts["previewNames"])
        self.assertNotIn("--- !u!114 &55", text)
        self.assertFalse((self.dest / "Assets/LabLoadingScene/StageGeometry/goldshores.unity").exists())
        self.assertEqual(before, self.snapshot())

    def test_r5_pending_scene_configs_navigation_repairs_and_repeat(self):
        before = self.snapshot()
        text = self.replay()
        self.assertEqual(self.io.read_text(self.dest / self.relative), text)
        self.assertFalse(any("StageGeometry" in str(p) for p in self.io.pending))
        self.io.flush()
        self.assertEqual(before, self.snapshot())
        config = read(self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json")
        self.assertIn(self.name, [row["name"] for row in config["integratedStages"]])
        recipe = read(self.dest / ".rebuild/composition/scene-probe-build.json")
        self.assertEqual(set(recipe["prefabAssets"]), set(self.baseline))
        with patch.dict(stage_variants.VARIANTS, {self.name: hashlib.sha256(text.encode()).hexdigest()}, clear=True):
            result = stage_variants.stage(self.io)
        self.assertEqual(result["stages"], [])

    def test_r5_config_row_alone_does_not_skip_missing_body(self):
        config = read(self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json")
        config["integratedStages"].append(dict(name=self.name))
        write(self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", config)
        self.replay()
        self.assertTrue(self.io.is_file(self.dest / self.relative))

    def test_r5_graph_drift_does_not_publish_scene(self):
        path = next(iter(self.baseline))
        self.put(self.dest / path, "drift")
        with self.assertRaisesRegex(RuntimeError, "Accepted variant graph changed"):
            self.replay()
        self.assertFalse((self.dest / self.relative).exists())

    def test_r5_projection_drift_does_not_publish_scene(self):
        with patch.dict(stage_variants.VARIANTS, {self.name: "0" * 64}, clear=True), self.assertRaisesRegex(RuntimeError, "measured projection"):
            stage_variants.stage(self.io)
        self.assertFalse((self.dest / self.relative).exists())

    def prepare_source(self, io):
        config = io.read(io.project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json")
        config["integratedStages"].append(dict(name=self.name))
        io.write(io.project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", config)
        return source_scene_candidate.prepare((self.name,), io)

    def test_r6_generates_body_importer_and_receipt_only_in_destination(self):
        before = self.snapshot()
        with patch.object(source_scene_candidate, "stage_unavailable_audio", side_effect=AssertionError("R1 owns audio")):
            result = self.prepare_source(self.io)
        row = result["staged"][0]
        text = self.io.read_text(self.dest / row["scene"])
        self.assertEqual(row["omitted_unavailable_audio_components"], 1)
        self.assertEqual(row["disabled_unavailable_render_components"], 1)
        self.assertNotIn("--- !u!114 &55", text)
        self.assertIn("--- !u!114 &56", text)
        self.assertIn("m_IsActive: 0", text)
        meta = self.io.read_text(self.dest / (row["scene"] + ".meta"))
        guid = hashlib.sha256(("ror2-android-source-scene:goldshores:" + self.input_id).encode()).hexdigest()[:32]
        self.assertIn("guid: " + guid, meta)
        self.io.flush()
        self.assertEqual(before, self.snapshot())
        self.assertTrue((self.dest / ".rebuild/composition/experiments/source-scenes/candidate.json").is_file())
        self.assertFalse(list(self.dest.rglob("*.dll")))

    def test_real_source_action_retains_paths_and_conflict_guards(self):
        io = StageIO()
        result = self.prepare_source(io)
        row = result["staged"][0]
        self.assertTrue((self.work / "lab-project" / row["scene"]).is_file())
        self.assertTrue((self.work / "experiments/source-scenes/candidate.json").is_file())
        self.assertIn(row["scene"], read(self.work / "scene-probe-build.json")["sourceStageScenes"])
        self.assertFalse((self.work / "lab-project/.rebuild").exists())
        self.put(self.work / "lab-project" / row["scene"], "unowned drift")
        with self.assertRaisesRegex(RuntimeError, "owned receipt"):
            source_scene_candidate.prepare((self.name,))

    def test_r6_metadata_conflict_and_input_identity_refused(self):
        result = self.prepare_source(self.io)
        self.io.flush()
        self.put(self.dest / (result["staged"][0]["scene"] + ".meta"), "drift")
        with self.assertRaisesRegex(RuntimeError, "metadata differs"):
            source_scene_candidate.prepare((self.name,), self.io)
        write(self.dest / ".port-input.json", dict(input_id="f" * 64))
        with self.assertRaisesRegex(RuntimeError, "accepted generation"):
            source_scene_candidate.prepare((self.name,), self.io)

    def test_coordinators_require_predecessors(self):
        for function, name in ((scene_rebuild.stage_variants, "dependencies"), (scene_rebuild.source_scenes, "stage-variants")):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "Run " + name):
                function(self.dest, self.work, self.input_id, set(), {})

    def test_coordinator_checks_output_before_flush_and_never_runs_audio(self):
        write(self.dest / ".rebuild/stage-variants-complete.json", dict(input_id=self.input_id))
        config = read(self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json")
        config["integratedStages"].append(dict(name=self.name))
        write(self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", config)
        path = "Assets/LabLoadingScene/SourceScenes/goldshores/goldshores.unity"
        with (
            patch.object(scene_rebuild, "CatalogIO", return_value=self.io),
            patch.dict(source_scene_candidate.SCENES, {self.name: "Base"}, clear=True),
            patch.object(source_scene_candidate, "stage_unavailable_audio", side_effect=AssertionError("must not run")),
            self.assertRaisesRegex(RuntimeError, "differs from provenance"),
        ):
            scene_rebuild.source_scenes(self.dest, self.work, self.input_id, {path}, {path: dict(sha256="0" * 64, size=1)})
        self.assertFalse((self.dest / path).exists())
        self.assertFalse((self.dest / ".rebuild/source-scenes-complete.json").exists())

    def scene_inputs(self):
        """Schema 2: no retained input; script identities and graphs come from the installation/export (J597)."""
        files = {}
        identities = dict(assembly="RoR2.dll", path="moon-script-identities.txt")
        write(self.recipes / "scene-rebuild-inputs.json", dict(schema=2, input_id=self.input_id, script_identities=identities, files=files))
        assembly = self.work / "installation/Risk of Rain 2_Data/Managed/RoR2.dll"
        self.put(assembly, "original assembly")
        write(self.work / "config/local.json", dict(game_path=str(assembly.parents[2])))
        rows = [dict(source="RoR2.dll", sha256=sha(assembly), guid="951ce57ad999ac1f040a4dceb5f8b763")]
        write(self.recipes / "original-assemblies.json", dict(schema=1, input_id=self.input_id, assemblies=rows))
        return files

    def test_script_identities_are_regenerated_from_installed_monoscripts(self):
        self.scene_inputs()
        scripts = {("RoR2", "TeamFilter"), ("", "RendererVisibility")}
        with patch.object(scene_rebuild, "RECIPE", self.recipes), patch("script_identity.installed_scripts", return_value=scripts) as listed:
            text = scene_rebuild.script_identities(self.work, "RoR2.dll")
            listed.assert_called_once_with(self.work / "installation/Risk of Rain 2_Data", "RoR2.dll")
            # Same row the historical editor list held for the MapZone TeamFilter (J597).
            self.assertIn("-1895344032|951ce57ad999ac1f040a4dceb5f8b763|RoR2.TeamFilter\n", text)
            self.assertEqual(len(text.splitlines()), 2)
            self.put(self.work / "installation/Risk of Rain 2_Data/Managed/RoR2.dll", "other assembly")
            with self.assertRaisesRegex(RuntimeError, "accepted RoR2.dll"):
                scene_rebuild.script_identities(self.work, "RoR2.dll")

    def test_md4_matches_rfc_1320_vectors(self):
        import script_identity

        for message, digest in (
            (b"", "31d6cfe0d16ae931b73c59d7e0c089c0"),
            (b"abc", "a448017aaf21d8525fc10ae87aa6729d"),
            (b"1234567890" * 8, "e33b4ddc9c38f2199c3e7b164fcc0536"),
        ):
            self.assertEqual(script_identity.md4(message).hex(), digest)
        self.assertEqual(script_identity.script_file_id("RoR2", "TeamFilter"), -1895344032)

    def test_retained_inputs_are_refused_before_any_catalog_scratch_writes(self):
        self.scene_inputs()
        recipe = read(self.recipes / "scene-rebuild-inputs.json")
        recipe["files"] = {"whole-catalog-code-base.json": dict(path="whole-catalog-code-base.json", sha256=sha(self.work / "whole-catalog-code-base.json"))}
        write(self.recipes / "scene-rebuild-inputs.json", recipe)
        with patch.object(catalog_rebuild.CatalogIO, "__init__") as parent:
            with self.assertRaisesRegex(RuntimeError, "no retained analysis input"):
                scene_rebuild.SceneIO(self.work, self.dest, self.input_id)
            parent.assert_not_called()

    def test_stage_graphs_are_export_copies_found_by_their_node_graph_script(self):
        graphs = scene_rebuild.node_graphs(self.io, self.export)
        self.assertEqual(graphs, {path: digest for path, digest in self.baseline.items()})
        self.put(self.export / "Assets/Graphs/other.asset", "not a graph\n")
        self.put(self.dest / "Assets/WholeGame/Graphs/other.asset", "not a graph\n")
        self.assertEqual(scene_rebuild.node_graphs(self.io, self.export).keys(), self.baseline.keys())
        staging = object.__new__(scene_rebuild.SceneIO)
        StageIO.__init__(staging, self.work, self.dest)
        staging.graphs, staging.unity_deferred = graphs, []
        relative = "Assets/WholeGame/Graphs/ground.asset"
        staging.provenance = {relative: dict(producer="unity-generated")}
        self.assertTrue(staging.accepted(self.dest / relative, graphs[relative]))
        self.assertEqual(staging.unity_deferred, [relative])
        self.assertFalse(staging.accepted(self.dest / relative, "e" * 64))
        self.put(self.dest / relative, "reserialized by an editor")
        self.assertFalse(staging.accepted(self.dest / relative, graphs[relative]))

    def test_membership_order_and_validate_bindings_is_registered(self):
        self.assertEqual(
            list(rebuild.STEPS)[5:],
            ["dependencies", "stage-variants", "source-scenes", "build-entries", "runtime-sources", "importer-identities", "validate-bindings"],
        )
        self.assertEqual(len(source_scene_candidate.SCENES), 23)
        self.assertEqual(len(stage_variants.VARIANTS), 16)
        self.assertIsNotNone(rebuild.STEPS["validate-bindings"].build)

    def test_real_geometry_retains_original_write_paths(self):
        project = self.work / "lab-project"
        out = self.work / "geometry-evidence"
        result = nova_bridge.stage_first_stage_geometry(project / "Assets/LabLoadingScene", out, original_name=True, scene_name=self.name)
        scene = project / "Assets/LabLoadingScene/StageGeometry/goldshores.unity"
        self.assertTrue(scene.is_file())
        self.assertEqual(Path(str(scene) + ".meta").read_bytes(), Path(str(self.source) + ".meta").read_bytes())
        self.assertTrue((out / "goldshores-geometry-contract.json").is_file())
        self.assertIn(result["groundGraph"], read(self.work / "scene-probe-build.json")["prefabAssets"])
        self.assertFalse((project / ".rebuild").exists())

    def test_real_variant_action_retains_original_write_paths(self):
        text, spec = self.project_scene()
        self.io.pending.clear()
        project = self.work / "lab-project"
        self.put(project / self.relative, self.source_text)
        self.put(project / "Assets/LabLoadingScene/Resources/WholeStageContexts.json", "{}\n")
        self.put(project / "Assets/Editor/LabBuild.cs", "old editor")
        self.put(self.root / "android/Assets/Editor/LabBuild.cs", "new editor")
        write(self.work / "experiments/whole-catalog/latest.json", dict(path="work/catalog"))
        write(self.work / "catalog/integration-latest.json", dict(path="work/catalog/integration"))
        write(self.work / "catalog/integration/manifest.json", dict(locations=[]))
        for key in ("groundGraph", "airGraph"):
            spec[key] = "assets/labloadingscene/stagegeometry/assets/graphs/" + key.removesuffix("Graph") + ".asset"

        def generate(stage, out, **kwargs):
            self.assertEqual(stage, project / "Assets/LabLoadingScene")
            self.assertEqual(kwargs["scene_name"], self.name)
            self.put(stage / "StageGeometry/goldshores.unity", text)
            for guid, source in self.index.items():
                for suffix in ("", ".meta"):
                    path = source.removeprefix("Assets/") + suffix
                    self.put(stage / "StageGeometry/Assets" / path, (self.export / (source + suffix)).read_text())
            return spec.copy()

        with (
            patch("build.preflight"),
            patch.object(nova_bridge, "stage_first_stage_geometry", side_effect=generate),
            patch.dict(stage_variants.VARIANTS, {self.name: hashlib.sha256(text.encode()).hexdigest()}, clear=True),
        ):
            result = stage_variants.stage()
            self.assertTrue(stage_variants.stage()["already_staged"])
        self.assertEqual(result["stages"], [self.name])
        self.assertEqual((project / self.relative).read_text(), text)
        self.assertEqual((project / "Assets/Editor/LabBuild.cs").read_text(), "new editor")
        self.assertTrue((self.work / "experiments/stage-variants/latest.json").is_file())
        self.assertTrue(list((self.work / "experiments/stage-variants").glob("*/previous-scenes/goldshores.unity.gz")))
        self.assertFalse((project / "Assets/LabLoadingScene/StageGeometry").exists())
        self.assertFalse((project / ".rebuild").exists())

    def test_scene_pin_membership_and_pinned_reads(self):
        files = self.scene_inputs()
        with (
            patch.object(scene_rebuild, "RECIPE", self.recipes),
            patch("script_identity.installed_scripts", return_value={("RoR2", "TeamFilter")}),
            patch.object(
                catalog_rebuild.CatalogIO, "__init__", new=lambda instance, work, destination, input_id: StageIO.__init__(instance, work, destination)
            ),
        ):
            staging = scene_rebuild.SceneIO(self.work, self.dest, self.input_id)
            self.put(self.work / "moon-script-identities.txt", "retained editor list is never read")
            self.assertEqual(staging.read_text(self.work / "moon-script-identities.txt"), "-1895344032|951ce57ad999ac1f040a4dceb5f8b763|RoR2.TeamFilter\n")
            recipe = read(self.recipes / "scene-rebuild-inputs.json")
            recipe["files"]["moon-script-identities.txt"] = dict(path="moon-script-identities.txt", sha256=sha(self.work / "moon-script-identities.txt"))
            write(self.recipes / "scene-rebuild-inputs.json", recipe)
            with self.assertRaisesRegex(RuntimeError, "no retained analysis input"):
                scene_rebuild.SceneIO(self.work, self.dest, self.input_id)

    def test_unity_generated_graph_accepts_only_its_export_copy_before_import(self):
        staging = object.__new__(scene_rebuild.SceneIO)
        StageIO.__init__(staging, self.work, self.dest)
        relative = "Assets/WholeGame/Graphs/ground.asset"
        digest = "e" * 64  # The editor's re-serialized form in the live project.
        row = dict(producer="unity-generated", sha256=digest, evidence=[dict(export_path="Assets/Graphs/ground.asset")])
        staging.unity_deferred, staging.graphs = [], None
        staging.provenance = {relative: row}
        self.assertTrue(staging.accepted(self.dest / relative, digest))
        self.assertEqual(staging.unity_deferred, [relative])
        self.assertFalse(staging.accepted(self.dest / relative, "f" * 64))
        staging.provenance = {relative: dict(row, producer="repo-builder")}
        self.assertFalse(staging.accepted(self.dest / relative, digest))
        staging.provenance = {relative: row}
        self.put(self.dest / relative, "drifted graph")
        self.assertFalse(staging.accepted(self.dest / relative, digest))
        self.assertEqual(staging.unity_deferred, [relative])

    def test_r5_coordinator_flushes_verified_outputs_and_marks_completion(self):
        write(self.dest / ".rebuild/dependencies-complete.json", dict(input_id=self.input_id))
        text, _ = self.project_scene()
        self.io.pending.clear()
        paths = {self.relative: text.encode()}
        for name in ("skymeadow", "shipgraveyard"):
            relative = "Assets/WholeGame/RoR2/Base/Scenes/" + name + "/" + name + ".unity"
            paths[relative] = (self.dest / relative).read_bytes()
        provenance = {path: dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) for path, data in paths.items()}
        with (
            patch.object(scene_rebuild, "SceneIO", return_value=self.io),
            patch.dict(stage_variants.VARIANTS, {self.name: hashlib.sha256(text.encode()).hexdigest()}, clear=True),
        ):
            scene_rebuild.stage_variants(self.dest, self.work, self.input_id, set(paths), provenance)
        self.assertEqual((self.dest / self.relative).read_text(), text)
        self.assertEqual(read(self.dest / ".rebuild/stage-variants-complete.json")["input_id"], self.input_id)

    def test_r5_r6_compare_only_selects_exact_provenance_evidence(self):
        provenance = {}
        selected = {}
        for step in ("stage-variants", "source-scenes"):
            path = "Assets/" + step + ".unity"
            selected[step] = path
            for project in (self.dest, self.work / "lab-project"):
                self.put(project / path, "synthetic " + step)
            provenance[path] = dict(producer="repo-builder", evidence=[dict(function=rebuild.STEPS[step].evidence[0])])
        for path in self.dest.rglob("*"):
            if path.is_file():
                provenance.setdefault(path.relative_to(self.dest).as_posix(), dict(producer="export-copy"))
        write(self.work / "receipts/provenance-map.json", provenance)
        with patch.object(rebuild, "safe_destination", return_value=self.dest):
            for step, path in selected.items():
                result = rebuild.rebuild_step(step, compare_only=True, work=self.work)
                self.assertTrue(result["equal"])
                self.assertEqual(result["identical"], [path])
                self.put(self.dest / path, "changed")
                self.assertEqual(rebuild.rebuild_step(step, compare_only=True, work=self.work)["different"], [path])

    def test_r6_all_23_scenes_flushes_46_verified_products_once(self):
        scenes = {name: "Base" for name in source_scene_candidate.SCENES}
        config_path = self.dest / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
        write(config_path, dict(integratedStages=[dict(name=name) for name in scenes]))
        for name in scenes:
            source = self.export / ("Assets/RoR2/Base/Scenes/" + name + "/" + name + ".unity")
            self.put(source, self.source_text)
            self.put(Path(str(source) + ".meta"), "guid: " + "d" * 32 + "\n")
        write(self.dest / ".rebuild/stage-variants-complete.json", dict(input_id=self.input_id))
        before = self.snapshot()
        with patch.dict(source_scene_candidate.SCENES, scenes, clear=True):
            source_scene_candidate.prepare(tuple(scenes), self.io)
            products = {p.relative_to(self.dest).as_posix(): data for p, data in self.io.pending.items() if "SourceScenes" in p.parts}
            self.assertEqual(len(products), 46)
            provenance = {p: dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) for p, data in products.items()}
            self.io.pending.clear()
            with patch.object(scene_rebuild, "CatalogIO", return_value=self.io), patch.object(source_scene_candidate, "stage_unavailable_audio") as audio:
                scene_rebuild.source_scenes(self.dest, self.work, self.input_id, set(products), provenance)
            audio.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(read(self.dest / ".rebuild/composition/experiments/source-scenes/candidate.json")["staged"]), 23)
        self.assertEqual(read(self.dest / ".rebuild/source-scenes-complete.json")["input_id"], self.input_id)
        for path, data in products.items():
            self.assertEqual((self.dest / path).read_bytes(), data)
