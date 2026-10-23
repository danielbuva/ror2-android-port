from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT
LAB = ROOT / "scripts/lab"
sys.path.insert(0, str(LAB))
import shader_postprocessing_bloom as bloom


PASS_NAMES = [
    "Prefilter 13 taps",
    "Prefilter 4 taps",
    "Downsample 13 taps",
    "Downsample 4 taps",
    "Upsample tent filter",
    "Upsample box filter",
    "Debug overlay (threshold)",
    "Debug overlay (tent filter)",
    "Debug overlay (box filter)",
]
ENUM_NAMES = [
    "Prefilter13",
    "Prefilter4",
    "Downsample13",
    "Downsample4",
    "UpsampleTent",
    "UpsampleBox",
    "DebugOverlayThreshold",
    "DebugOverlayTent",
    "DebugOverlayBox",
]


def synthetic_shader() -> bytes:
    passes = "\n".join(f"    // {index}: {name}\n    Pass\n    {{\n    }}" for index, name in enumerate(PASS_NAMES))
    return f'Shader "{bloom.SHADER_NAME}"\n{{\n{passes}\n}}\n'.encode()


def synthetic_renderer() -> bytes:
    return ("private enum Pass { " + ", ".join(ENUM_NAMES) + " }").encode()


class BloomBatchContractTests(unittest.TestCase):
    def test_disabling_staged_batch_refuses_before_catalog_imports(self) -> None:
        from composition_io import StageIO
        import whole_catalog

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve() / "work"
            out = work / "catalog"
            out.mkdir(parents=True)
            config = work / "config"
            config.mkdir()
            (config / "reconstruction.json").write_text(json.dumps({"projects": ["work/export"]}))
            (config / "accepted-input.json").write_text(json.dumps({"input_id": "test-input"}))
            (out / "reconciled-closure.json").write_text(json.dumps({"input_id": "test-input"}))
            io = StageIO(work)
            marker = io.project / ".rebuild/postprocessing-bloom.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("existing receipt marker")
            before = {path.relative_to(io.project): path.read_bytes() for path in io.project.rglob("*") if path.is_file()}
            with patch.object(io, "preflight"), patch.object(io, "catalog", return_value=out):
                with self.assertRaisesRegex(RuntimeError, "prior Bloom receipt"):
                    whole_catalog.prepare_integration(io)
            after = {path.relative_to(io.project): path.read_bytes() for path in io.project.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def make_source(self, root: Path, *, guid: str = "1" * 32, resource_guid: str | None = None) -> tuple[Path, dict, dict]:
        export = root / "export"
        shader_path = Path("Assets/Shader/Hidden_PostProcessing_Bloom_1.shader")
        resource_path = Path("Assets/MonoBehaviour/PostProcessResources_1.asset")
        shader = export / shader_path
        meta = export / (str(shader_path) + ".meta")
        resource = export / resource_path
        shader.parent.mkdir(parents=True)
        resource.parent.mkdir(parents=True)
        shader.write_bytes(b'Shader "Hidden/PostProcessing/Bloom" {\nSubShader {\nPass\n{\n}\n}\n}\n')
        meta.write_text(f"fileFormatVersion: 2\nguid: {guid}\n", encoding="utf-8")
        resource.write_text(f"  bloom: {{fileID: 4800000, guid: {resource_guid or guid}, type: 3}}\n", encoding="utf-8")
        recipe = {
            "expected_members": [
                {
                    "shader": shader_path.as_posix(),
                    "guid": guid,
                    "shader_sha256": bloom.digest_bytes(shader.read_bytes()),
                    "meta_sha256": bloom.digest_bytes(meta.read_bytes()),
                    "resource": resource_path.as_posix(),
                    "resource_sha256": bloom.digest_bytes(resource.read_bytes()),
                }
            ]
        }
        mapped = {
            shader_path.as_posix(): "Assets/WholeGame/Shader/Hidden_PostProcessing_Bloom_1.shader",
            resource_path.as_posix(): "Assets/WholeGame/MonoBehaviour/PostProcessResources_1.asset",
        }
        return export, recipe, mapped

    def test_official_pass_names_and_renderer_enum_are_ordered(self) -> None:
        recipe = {"pass_names": PASS_NAMES, "runtime_selected_passes": [1, 3, 5]}
        bloom.validate_pass_contract(synthetic_shader(), synthetic_renderer(), recipe)
        changed = synthetic_shader().replace(b"// 3: Downsample 4 taps", b"// 3: Downsample 13 taps")
        with self.assertRaisesRegex(RuntimeError, "nine-pass"):
            bloom.validate_pass_contract(changed, synthetic_renderer(), recipe)
        changed_renderer = synthetic_renderer().replace(b"Downsample4", b"Downsample13")
        with self.assertRaisesRegex(RuntimeError, "enum"):
            bloom.validate_pass_contract(synthetic_shader(), changed_renderer, recipe)

    def test_copy_std_companion_requires_exact_two_pass_contract(self) -> None:
        recipe = {
            "companion_copy_std": {
                "shader_name": "Hidden/PostProcessing/CopyStd",
                "selected_pass": 1,
                "runtime_passes": ["Copy", "Copy + NaN killer"],
            }
        }
        shader = b'Shader "Hidden/PostProcessing/CopyStd"\n{\nSubShader {\n// 0 - Copy\nPass\n{}\n// 1 - Copy + NaN killer\nPass\n{}\n}\n}'
        bloom.validate_copy_std_contract(shader, recipe)
        one_pass = shader.replace(b"// 1 - Copy + NaN killer\nPass\n{}\n", b"")
        with self.assertRaisesRegex(RuntimeError, "two-pass"):
            bloom.validate_copy_std_contract(one_pass, recipe)
        wrong_pass = {"companion_copy_std": {**recipe["companion_copy_std"], "selected_pass": 0}}
        with self.assertRaisesRegex(RuntimeError, "two-pass"):
            bloom.validate_copy_std_contract(shader, wrong_pass)

    def test_staging_accepts_only_original_or_exact_candidate_preimage(self) -> None:
        source_sha, candidate_sha = "1" * 64, "2" * 64
        bloom.require_known_stage_preimage(source_sha, source_sha, candidate_sha, "source.shader")
        bloom.require_known_stage_preimage(candidate_sha, source_sha, candidate_sha, "source.shader")
        with self.assertRaisesRegex(RuntimeError, "unknown staged shader body"):
            bloom.require_known_stage_preimage("3" * 64, source_sha, candidate_sha, "source.shader")

    def test_export_member_requires_exact_guid_resource_and_wholegame_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export, recipe, mapped = self.make_source(root)
            rows = bloom.validate_export_members(export, mapped, recipe)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["guid"], "1" * 32)
            self.assertEqual(rows[0]["resource"], recipe["expected_members"][0]["resource"])

            wrong = dict(mapped)
            wrong[next(iter(wrong))] = "Assets/Elsewhere/Hidden_PostProcessing_Bloom_1.shader"
            with self.assertRaisesRegex(RuntimeError, "exact WholeGame"):
                bloom.validate_export_members(export, wrong, recipe)

    def test_copy_std_source_camera_resource_join_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = root / "export"
            source_rel = Path("Assets/Shader/Hidden_PostProcessing_CopyStd_53.shader")
            resource_rel = Path("Assets/MonoBehaviour/PostProcessResources_53.asset")
            prefab_rel = Path("Assets/RoR2/Base/Core/Camera/Main Camera.prefab")
            guid = "c" * 32
            resource_guid = "a" * 32
            shader = export / source_rel
            meta = export / (str(source_rel) + ".meta")
            resource = export / resource_rel
            resource_meta = export / (str(resource_rel) + ".meta")
            prefab = export / prefab_rel
            prefab_meta = export / (str(prefab_rel) + ".meta")
            shader.parent.mkdir(parents=True)
            resource.parent.mkdir(parents=True)
            prefab.parent.mkdir(parents=True)
            shader.write_text('Shader "Hidden/PostProcessing/CopyStd" {\nSubShader {\nPass\n{}\n}\n}\n', encoding="utf-8")
            meta.write_text(f"fileFormatVersion: 2\nguid: {guid}\n", encoding="utf-8")
            resource.write_text(f"  copyStd: {{fileID: 4800000, guid: {guid}, type: 3}}\n", encoding="utf-8")
            resource_meta.write_text(f"fileFormatVersion: 2\nguid: {resource_guid}\n", encoding="utf-8")
            prefab.write_text(f"  m_Resources: {{fileID: 11400000, guid: {resource_guid}, type: 2}}\n  stopNaNPropagation: 1\n", encoding="utf-8")
            prefab_meta.write_text("fileFormatVersion: 2\nguid: " + "b" * 32 + "\n", encoding="utf-8")
            identity = {
                "shader": source_rel.as_posix(),
                "resource": resource_rel.as_posix(),
                "guid": guid,
                "shader_sha256": bloom.digest_bytes(shader.read_bytes()),
                "meta_sha256": bloom.digest_bytes(meta.read_bytes()),
                "resource_sha256": bloom.digest_bytes(resource.read_bytes()),
                "resource_meta_sha256": bloom.digest_bytes(resource_meta.read_bytes()),
                "resource_asset_guid": resource_guid,
                "source_camera_prefab": {
                    "path": prefab_rel.as_posix(),
                    "sha256": bloom.digest_bytes(prefab.read_bytes()),
                    "meta_sha256": bloom.digest_bytes(prefab_meta.read_bytes()),
                    "resources_guid": resource_guid,
                    "stopNaNPropagation": 1,
                },
                "shader_name": "Hidden/PostProcessing/CopyStd",
            }
            mapped = {
                source_rel.as_posix(): "Assets/WholeGame/" + source_rel.as_posix().removeprefix("Assets/"),
                resource_rel.as_posix(): "Assets/WholeGame/" + resource_rel.as_posix().removeprefix("Assets/"),
                (resource_rel.as_posix() + ".meta"): "Assets/WholeGame/" + resource_rel.as_posix().removeprefix("Assets/") + ".meta",
                prefab_rel.as_posix(): "Assets/WholeGame/" + prefab_rel.as_posix().removeprefix("Assets/"),
            }
            self.assertEqual(bloom.validate_copy_std_member(export, mapped, {"companion_copy_std": identity})["guid"], guid)
            resource.write_text(resource.read_text(encoding="utf-8").replace(guid, "d" * 32), encoding="utf-8")
            identity["resource_sha256"] = bloom.digest_bytes(resource.read_bytes())
            with self.assertRaisesRegex(RuntimeError, "copyStd reference"):
                bloom.validate_copy_std_member(export, mapped, {"companion_copy_std": identity})

    def test_missing_or_ambiguous_resource_guid_refuses_without_writes(self) -> None:
        for resource_guid in ("2" * 32,):
            with self.subTest(resource_guid=resource_guid), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                export, recipe, mapped = self.make_source(root, resource_guid=resource_guid)
                with self.assertRaisesRegex(RuntimeError, "reference does not match"):
                    bloom.validate_export_members(export, mapped, recipe)
                self.assertEqual(sum(path.is_file() for path in export.rglob("*")), 3)

    def test_activation_is_explicit_bounded_and_input_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            config = work / "config/postprocessing-bloom.json"
            self.assertIsNone(bloom.read_activation(work, "a" * 64))
            config.parent.mkdir()
            config.write_text(
                json.dumps({"schema": bloom.ACTIVATION_SCHEMA, "input_id": "a" * 64, "enabled": True}),
                encoding="utf-8",
            )
            self.assertTrue(bloom.read_activation(work, "a" * 64)["enabled"])
            with self.assertRaisesRegex(RuntimeError, "accepted input"):
                bloom.read_activation(work, "b" * 64)

    def test_real_official_archive_contract_when_locally_available(self) -> None:
        package = REPOSITORY_ROOT / "work/packages/com.unity.postprocessing-2.3.0.tgz"
        if not package.is_file():
            self.skipTest("official package archive is optional in clean clones")
        recipe_path = ROOT / "recipe/shader-postprocessing-bloom-candidate.json"
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        files = bloom.archive_files(package, recipe)
        bloom.validate_pass_contract(files["__Bloom.shader"], files["__BloomRenderer.cs"], recipe)
        bloom.validate_copy_std_contract(files["__CopyStd.shader"], recipe)

    def test_actual_batch_generation_and_replay_when_local_inputs_are_available(self) -> None:
        package = REPOSITORY_ROOT / "work/packages/com.unity.postprocessing-2.3.0.tgz"
        export = REPOSITORY_ROOT / "work/assetripper/3f02f15f5734bf59/export/ExportedProject"
        if not package.is_file() or not export.is_dir():
            self.skipTest("accepted export and official package are optional in clean clones")
        recipe = bloom.load_recipe("6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88")
        input_id = recipe["input_id"]
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve() / "work"
            local_package = work / "packages/com.unity.postprocessing-2.3.0.tgz"
            local_package.parent.mkdir(parents=True)
            shutil.copyfile(package, local_package)
            config = work / "config/postprocessing-bloom.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"schema": bloom.ACTIVATION_SCHEMA, "input_id": input_id, "enabled": True}), encoding="utf-8")
            (config.parent / "reconstruction.json").write_text(json.dumps({"projects": [str(export.resolve())]}))
            mapped = {}
            for identity in recipe["expected_members"]:
                for relative in (identity["shader"], identity["resource"]):
                    mapped[relative] = "Assets/WholeGame/" + relative.removeprefix("Assets/")
            copy_identity = recipe["companion_copy_std"]
            for relative in (copy_identity["shader"], copy_identity["resource"], copy_identity["source_camera_prefab"]["path"]):
                mapped[relative] = "Assets/WholeGame/" + relative.removeprefix("Assets/")
            from composition_io import StageIO
            import catalog_rebuild

            io = StageIO(work)
            owners = {}
            preserved = {}
            for source, target in mapped.items():
                for relative in (source, source + ".meta"):
                    destination = io.project / (target + (".meta" if relative.endswith(".meta") else ""))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(export / relative, destination)
                    if relative.endswith(".meta"):
                        owners[bloom.parse_guid(destination.read_bytes())] = target
                    if not relative.endswith(".shader"):
                        preserved[destination] = destination.read_bytes()
            # Whole-catalog maps assets, never their .meta sidecars.
            self.assertFalse(any(path.endswith(".meta") for path in mapped))
            bloom.stage(io, export=export.resolve(), mapped=mapped, owners=owners, destination=work / "evidence", input_id=input_id)
            self.assertTrue(all(path.read_bytes() == data for path, data in preserved.items()))
            receipt = catalog_rebuild.read_postprocessing_bloom_receipt(io.project, input_id, work)
            validated = catalog_rebuild.postprocessing_bloom_rows(receipt, input_id, set(), {}, candidate_work=work)
            self.assertEqual(len(validated), 132)
            copy_target = mapped[copy_identity["shader"]]
            self.assertIn(copy_target, validated)
            self.assertIn(copy_target + ".meta", validated)

            # Replay sees pending marker/receipt writes and never changes live inputs.
            stable = bloom.candidate_root(work, input_id, recipe)
            candidate_before = {path.relative_to(stable): path.read_bytes() for path in stable.rglob("*") if path.is_file()}
            replay = StageIO(work, work.parent / "isolated-project")
            for source, target in mapped.items():
                for suffix in ("", ".meta"):
                    destination = replay.project / (target + suffix)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(export / (source + suffix), destination)
            bloom.stage(replay, export=export.resolve(), mapped=mapped, owners={}, destination=work / "replay-evidence", input_id=input_id)
            pending = catalog_rebuild.read_postprocessing_bloom_receipt(replay.project, input_id, work, io=replay)
            catalog_rebuild.verify_outputs(replay, set(), {}, input_id=input_id, postprocessing_bloom=pending)
            candidate_after = {path.relative_to(stable): path.read_bytes() for path in stable.rglob("*") if path.is_file()}
            self.assertEqual(candidate_before, candidate_after)


if __name__ == "__main__":
    unittest.main()
