"""Synthetic shader orchestration, boundaries and refusal contracts; no native tools."""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from common import read, sha, write
from composition_io import StageIO
import rebuild
import shader_deferred
import shader_materials
import shader_rebuild as replay
import shader_source


class ShaderRebuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.work = self.root / "inputs"
        self.dest = self.root / "destination"
        self.recipe = self.root / "recipe"
        self.input_id = "a" * 64
        self.files = {"A.shader": b"synthetic A", "Variants.json": b"synthetic B"}
        self.expected = {"Assets/LabLoadingScene/Resources/" + name for name in self.files}
        self.provenance = {
            path: dict(
                sha256=hashlib.sha256(self.files[Path(path).name]).hexdigest(),
                size=len(self.files[Path(path).name]),
                producer="repo-builder",
                evidence=[dict(function="shader_deferred.generate")],
            )
            for path in self.expected
        }
        self.retained = self.work / "analysis/receipt.json"
        write(
            self.retained,
            dict(success=True, programs=[], source_sha256_by_file={name: row["sha256"] for path, row in self.provenance.items() for name in [Path(path).name]}),
        )
        self.config = dict(
            schema=1,
            input_id=self.input_id,
            files={"analysis/receipt.json": sha(self.retained)},
            groups=[dict(name="deferred", selection={}, independent="analysis", selected_source="work/absent/sources", outputs=list(self.files))],
        )
        self.save()
        write(self.work / "config/accepted-input.json", dict(input_id=self.input_id))
        for patcher in (patch.object(replay, "RECIPE", self.recipe), patch("composition_io.initialize"), patch.object(StageIO, "preflight")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.real_deferred_generate = shader_deferred.generate
        self.generator = patch.object(shader_deferred, "generate", side_effect=self.generate).start()
        self.addCleanup(patch.stopall)

    def save(self):
        write(self.recipe / "shader-rebuild-inputs.json", self.config)

    def snapshot(self):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.work.rglob("*") if p.is_file()}

    def generate(self, *, output, work, root, independent, selection):
        self.assertEqual(work, self.work)
        self.assertEqual(root, self.work.parent)
        self.assertEqual(independent, self.work / "analysis")
        self.assertTrue(output.is_relative_to(self.dest))
        for name, data in self.files.items():
            path = output / "sources" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        write(output / "receipt.json", dict(success=True, source_sha256_by_file={name: sha(output / "sources" / name) for name in self.files}))

    def run_step(self):
        return replay.shader_pipeline(self.dest, self.work, self.input_id, self.expected, self.provenance)

    def test_regenerates_without_any_selected_final_sources_and_preserves_inputs(self):
        before = self.snapshot()
        result = self.run_step()
        self.assertTrue(result["complete"])
        self.assertFalse(result["recovery_regenerated"])
        self.assertEqual(set(result["placed"]), self.expected)
        self.assertEqual(before, self.snapshot())
        for path in self.expected:
            self.assertEqual((self.dest / path).read_bytes(), self.files[Path(path).name])
        sources = replay.composition_sources(StageIO(self.work, self.dest), ["work/absent/sources"])
        self.assertTrue(sources[0].is_relative_to(self.dest))
        self.assertEqual(set(p.name for p in sources[0].iterdir()), set(self.files))

    def test_drift_lists_each_unplaced_output_and_blocks_composition(self):
        self.files["A.shader"] = b"new unverified body"
        result = self.run_step()
        path = "Assets/LabLoadingScene/Resources/A.shader"
        self.assertIn("J558", result["blocked"][path])
        self.assertFalse((self.dest / path).exists())
        self.assertEqual(len(result["placed"]), 1)
        with self.assertRaisesRegex(RuntimeError, "blocked"):
            replay.composition_sources(StageIO(self.work, self.dest), ["work/absent/sources"])

    def test_native_tool_failure_is_reported_without_copying_retained_sources(self):
        self.generator.side_effect = RuntimeError("native tool unavailable")
        result = self.run_step()
        self.assertEqual(set(result["blocked"]), self.expected)
        self.assertFalse(result["placed"])
        self.assertFalse((self.dest / "Assets").exists())
        self.assertTrue((self.dest / ".rebuild/shader-pipeline-result.json").exists())

    def test_generator_membership_drift_is_reported_without_placing_the_group(self):
        self.files["Unexpected.shader"] = b"unexpected output"
        result = self.run_step()
        self.assertEqual(set(result["blocked"]), self.expected)
        self.assertFalse(result["placed"])
        self.assertFalse((self.dest / "Assets").exists())

    def test_input_hash_and_missing_pin_fail_before_generation_or_destination_writes(self):
        self.retained.write_text("drift")
        with self.assertRaisesRegex(RuntimeError, "input drift"):
            self.run_step()
        self.generator.assert_not_called()
        self.assertFalse(self.dest.exists())
        self.config["files"] = {}
        self.save()
        with self.assertRaisesRegex(RuntimeError, "Unpinned"):
            self.run_step()

    def test_membership_and_selection_drift_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "membership"):
            replay.shader_pipeline(self.dest, self.work, self.input_id, set(), self.provenance)
        self.run_step()
        with self.assertRaisesRegex(RuntimeError, "selection drift"):
            replay.composition_sources(StageIO(self.work, self.dest), ["work/different/sources"])

    def test_composition_requires_completed_replay_and_rejects_redirected_source(self):
        with self.assertRaisesRegex(RuntimeError, "Run shader-pipeline"):
            replay.composition_sources(StageIO(self.work, self.dest), ["work/absent/sources"])
        self.run_step()
        report = self.dest / ".rebuild/shader-pipeline-result.json"
        data = read(report)
        data["sources"] = [".rebuild/elsewhere/sources"]
        write(report, data)
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            replay.composition_sources(StageIO(self.work, self.dest), ["work/absent/sources"])

    def test_real_composition_retains_selected_write_paths(self):
        path = replay.composition_sources(StageIO(self.work), ["work/old/sources"])
        self.assertEqual(path, [self.work / "old/sources"])

    def test_output_directory_preserves_real_paths_and_isolated_pointers(self):
        for kind in ("shader-bindings", "deferred-bindings", "material-bindings"):
            with self.subTest(kind=kind), patch.object(shader_source, "now", return_value="fixed"):
                out = shader_source.output_directory(kind, self.work, self.root)
                self.assertEqual(out, self.work / "experiments" / kind / "fixed")
                pointer = self.work / (kind + "-current.json")
                before = pointer.read_bytes(), pointer.stat().st_mtime_ns
                self.assertEqual(read(pointer), dict(path="inputs/experiments/" + kind + "/fixed"))
                isolated = self.dest / kind
                self.assertEqual(shader_source.output_directory(kind, self.work, self.root, isolated), isolated)
                self.assertEqual(before, (pointer.read_bytes(), pointer.stat().st_mtime_ns))

    def test_shader_step_selection_does_not_claim_importers_or_unity_files(self):
        provenance = copy.deepcopy(self.provenance)
        provenance["Assets/LabLoadingScene/Resources/A.shader.meta"] = dict(producer="unity-generated")
        self.assertEqual(rebuild.selected_paths(rebuild.STEPS["shader-pipeline"], provenance), self.expected)

    def test_changed_generated_sources_cannot_be_consumed_by_composition(self):
        report = self.run_step()
        source = self.dest / report["sources"][0] / "A.shader"
        source.write_bytes(b"changed after generation")
        with self.assertRaisesRegex(RuntimeError, "source drift"):
            replay.composition_sources(StageIO(self.work, self.dest), ["work/absent/sources"])

    def test_deferred_and_material_real_actions_keep_failure_receipts_and_pointer_paths(self):
        for module, kind, selection in (
            (shader_deferred, "deferred-bindings", dict(standard="work/synthetic", lighting="work/synthetic")),
            (shader_materials, "material-bindings", {name: "work/synthetic" for name in shader_materials.FAMILIES}),
        ):
            function = self.real_deferred_generate if module is shader_deferred else module.generate
            with self.subTest(kind=kind), patch.object(module, "load_analysis", side_effect=RuntimeError("synthetic native failure")):
                with patch.object(shader_source, "now", return_value="fixed-action"), self.assertRaisesRegex(RuntimeError, "synthetic native failure"):
                    function(work=self.work, root=self.root, selection=selection)
                real = self.work / "experiments" / kind / "fixed-action"
                self.assertEqual(read(real / "receipt.json")["first_failure"], "synthetic native failure")
                pointer = self.work / (kind + "-current.json")
                self.assertEqual(read(pointer), dict(path=str(real.relative_to(self.root))))
                before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError, "synthetic native failure"):
                    function(output=self.dest / kind, work=self.work, root=self.root, selection=selection)
                self.assertEqual(before, self.snapshot())
                self.assertFalse(read(self.dest / kind / "receipt.json")["success"])

    def test_independent_intermediate_requires_its_own_hash_pin(self):
        from common import digest

        program = dict(shader="Synthetic", index=7, origin="validated fallback", hlsl_sha256=hashlib.sha256(b"synthetic intermediate").hexdigest())
        receipt = read(self.retained)
        receipt["programs"] = [program]
        write(self.retained, receipt)
        self.config["files"]["analysis/receipt.json"] = sha(self.retained)
        with self.assertRaisesRegex(RuntimeError, "Unpinned independent"):
            replay.pinned_inputs(self.work, self.config, self.input_id)
        stem = "program-" + digest("Synthetic")[:12] + "-7"
        relative = "analysis/" + stem + "-independent/" + stem + ".hlsl"
        path = self.work / relative
        path.parent.mkdir()
        path.write_bytes(b"synthetic intermediate")
        self.config["files"][relative] = sha(path)
        replay.pinned_inputs(self.work, self.config, self.input_id)
        path.write_bytes(b"drift")
        with self.assertRaisesRegex(RuntimeError, "input drift"):
            replay.pinned_inputs(self.work, self.config, self.input_id)

    def test_coordinator_reports_blocked_replay_even_with_preexisting_matching_files(self):
        destination = self.root / "work/rebuild/synthetic"
        for path in self.expected:
            for base in (destination, self.work / "lab-project"):
                target = base / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self.files[Path(path).name])
        write(self.work / "receipts/provenance-map.json", self.provenance)
        blocked = dict(blocked={path: "native failure" for path in self.expected})
        owner = rebuild.STEPS["shader-pipeline"]
        replacement = rebuild.Step(owner.producers, owner.owns, lambda *args: blocked, owner.evidence)
        with (
            patch.object(rebuild, "ROOT", self.root),
            patch.object(rebuild, "game", return_value=self.root / "installation"),
            patch.dict(rebuild.STEPS, {"shader-pipeline": replacement}),
        ):
            result = rebuild.rebuild_step("shader-pipeline", destination, work=self.work)
        self.assertEqual(result["counts"]["identical"], len(self.expected))
        self.assertFalse(result["equal"])
        self.assertEqual(result["replay"], blocked)


if __name__ == "__main__":
    unittest.main()
