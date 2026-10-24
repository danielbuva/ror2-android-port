"""Synthetic tests for the proposed accepted-input translucent candidate generator."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_STAGE = tempfile.TemporaryDirectory(prefix="translucent-generator-contract-")
STAGED_ROOT = Path(_STAGE.name)
(STAGED_ROOT / "scripts/lab").mkdir(parents=True)
(STAGED_ROOT / "recipe").mkdir()
for name in ("common.py", "shader_segments.py", "shader_deferred.py", "shader_ramp_fog.py", "shader_source.py", "shader_recovery.py"):
    shutil.copy2(ROOT / "scripts/lab" / name, STAGED_ROOT / "scripts/lab" / name)
shutil.copy2(ROOT / "scripts/lab/shader_translucent.py", STAGED_ROOT / "scripts/lab/shader_translucent.py")
shutil.copy2(ROOT / "recipe/shader-translucent-candidate.json", STAGED_ROOT / "recipe/shader-translucent-candidate.json")
shutil.copy2(ROOT / "recipe/shader-ramp-fog-candidate.json", STAGED_ROOT / "recipe/shader-ramp-fog-candidate.json")
SCRIPT = STAGED_ROOT / "scripts/lab/shader_translucent.py"
sys.path.insert(0, str(STAGED_ROOT / "scripts/lab"))
spec = importlib.util.spec_from_file_location("translucent_candidate_test", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ProductionGeneratorContracts(unittest.TestCase):
    def test_output_is_stable_input_bound_and_rejects_escape(self):
        old = module.SOURCE
        try:
            module.SOURCE = {"input_id": "fixture-input"}
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
                work = Path(temp)
                self.assertEqual(
                    module.output_path(work, "fixture-input"),
                    (work / "generated-shader-candidates/translucent-camera-r2/fixture-input").resolve(),
                )
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    module.output_path(work, "other-input")
                module.RECIPE["stable_output"] = "../../outside/{input_id}"
                with self.assertRaisesRegex(RuntimeError, "escapes"):
                    module.output_path(work, "fixture-input")
        finally:
            module.SOURCE = old
            module.RECIPE["stable_output"] = "generated-shader-candidates/translucent-camera-r2/{input_id}"

    def test_output_rejects_symlinked_parent(self):
        old = module.SOURCE
        try:
            module.SOURCE = {"input_id": "fixture-input"}
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
                work = Path(temp)
                outside = work / "elsewhere"
                outside.mkdir()
                (work / "generated-shader-candidates").symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(RuntimeError, "symlink"):
                    module.output_path(work, "fixture-input")
        finally:
            module.SOURCE = old

    def test_output_rejects_a_symlinked_work_root_before_resolving_it(self):
        old = module.SOURCE
        try:
            module.SOURCE = {"input_id": "fixture-input"}
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
                root = Path(temp)
                actual = root / "actual-work"
                actual.mkdir()
                alias = root / "work-alias"
                alias.symlink_to(actual, target_is_directory=True)
                with self.assertRaisesRegex(RuntimeError, "symlink component"):
                    module.output_path(alias, "fixture-input")
        finally:
            module.SOURCE = old

    def test_main_preserves_supplied_symlink_for_preflight_refusal(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            actual = root / "actual-work"
            (actual / "config").mkdir(parents=True)
            (actual / "config/accepted-input.json").write_text(json.dumps({"input_id": module.SOURCE["input_id"]}), encoding="utf-8")
            alias = root / "work-alias"
            alias.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "symlink component"):
                module.main(alias)
            self.assertFalse((actual / module.RECIPE["stable_output"].format(input_id=module.SOURCE["input_id"])).exists())

    def test_bundle_resolves_only_from_accepted_inventory_and_configured_install(self):
        old_source = module.SOURCE
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            work = Path(temp) / "work"
            install = Path(temp) / "legitimate-install"
            relative = "Fixture_Data/StreamingAssets/test.bundle"
            payload = b"synthetic bundle bytes"
            digest = hashlib.sha256(payload).hexdigest()
            (work / "config").mkdir(parents=True)
            (work / "inventory").mkdir()
            (install / "Fixture_Data/Managed").mkdir(parents=True)
            (install / "Fixture_Data/Managed/RoR2.dll").write_bytes(b"stub")
            bundle = install / relative
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(payload)
            (work / "config/accepted-input.json").write_text(json.dumps({"input_id": "fixture-input", "steam_buildid": 7}), encoding="utf-8")
            inventory = {"input_id": "fixture-input", "files": [{"path": relative, "sha256": digest}]}
            (work / "inventory/files.json").write_text(json.dumps(inventory), encoding="utf-8")
            module.SOURCE = {"input_id": "fixture-input", "build_id": "7", "bundle_path": relative, "bundle_sha256": digest}
            with patch.object(module, "game", return_value=install):
                self.assertEqual(module.accepted_bundle(work), bundle)
                inventory["files"].append(inventory["files"][0])
                (work / "inventory/files.json").write_text(json.dumps(inventory), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "missing/ambiguous/drifted"):
                    module.accepted_bundle(work)
        module.SOURCE = old_source

    def test_candidate_uses_repository_binder_without_source_rewriting(self):
        import ast

        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"} for node in calls))
        self.assertNotIn("inspect.getsource", source)
        self.assertNotIn("integration.patch", source)
        self.assertIn("bind_hlsl = shader_source.bind_hlsl", source)

    def test_recipe_contains_only_names_paths_ids_and_digests(self):
        recipe = json.loads(module.RECIPE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(recipe["shaders"]), 4)
        self.assertEqual({row["catalog_location"] for row in recipe["shaders"]}, {2537, 2538, 2539, 2540})
        self.assertTrue(all(len(row["guid"]) == 32 for row in recipe["shaders"]))
        serialized = json.dumps(recipe)
        for forbidden in ("HLSLPROGRAM", "DXBC", "float4 main", "SubShader {"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(recipe["acceptance"]["android_accepted"], False)

    def test_recipe_pins_exact_identity_including_source_guid_and_catalog_key(self):
        original = module.RECIPE["shaders"]
        try:
            for field in (
                "guid",
                "source_asset_path",
                "primary_key",
                "catalog_key",
                "catalog_location",
                "path_id",
                "serialized_name",
                "pass_count",
                "output",
                "manifest",
            ):
                rows = json.loads(json.dumps(original))
                rows[0][field] = "mutated"
                module.RECIPE["shaders"] = rows
                with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "exact reviewed identities"):
                    module.validate_recipe()
        finally:
            module.RECIPE["shaders"] = original

    def test_recipe_requires_the_reviewed_manifest_schema(self):
        original = module.RECIPE["candidate_schema"]
        try:
            module.RECIPE["candidate_schema"] = "unexpected-schema"
            with self.assertRaisesRegex(RuntimeError, "manifest schema"):
                module.validate_recipe()
        finally:
            module.RECIPE["candidate_schema"] = original

    def test_recipe_requires_all_exact_authored_helper_pins(self):
        original = module.RECIPE["tools"]["authored_helpers"]
        try:
            for pins in ({}, {**original, "shader_source.py": "0" * 64}, {**original, "extra.py": "1" * 64}):
                module.RECIPE["tools"]["authored_helpers"] = pins
                with self.assertRaisesRegex(RuntimeError, "helper set or digest"):
                    module.verify_authored_helpers()
        finally:
            module.RECIPE["tools"]["authored_helpers"] = original

    def test_output_layout_refuses_collisions_with_reports_and_intermediates(self):
        original = module.RECIPE["shaders"]
        try:
            indices = {row["name"]: [1] for row in original}
            for field, value in (("manifest", "manifest.json"), ("output", "DownTent-1.dxbc")):
                rows = json.loads(json.dumps(original))
                rows[0][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "paths collide"):
                    module.validate_output_layout(rows, indices)
            rows = json.loads(json.dumps(original))
            rows[1]["output"] = rows[0]["output"]
            with self.assertRaisesRegex(RuntimeError, "paths collide"):
                module.validate_output_layout(rows, indices)
            rows = json.loads(json.dumps(original))
            rows[1]["manifest"] = "sources"
            with self.assertRaisesRegex(RuntimeError, "path collides with an output directory"):
                module.validate_output_layout(rows, indices)
        finally:
            module.RECIPE["shaders"] = original

    def test_preflight_collision_refuses_before_creating_stable_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            work = Path(temp)
            rows = json.loads(json.dumps(module.RECIPE["shaders"]))
            rows[0]["manifest"] = "manifest.json"
            indices = {row["name"]: [1] for row in rows}
            destination = work / module.RECIPE["stable_output"].format(input_id=module.SOURCE["input_id"])
            with self.assertRaisesRegex(RuntimeError, "paths collide"):
                module.preflight_output(work, module.SOURCE["input_id"], rows, indices)
            self.assertFalse(destination.exists())


class WrapperSemanticContracts(unittest.TestCase):
    def test_array_declaration_uses_hlsl_identifier_suffix_order(self):
        self.assertEqual(
            module.format_constant_declaration("float4[128]", "_Hammersley"),
            "float4 _Hammersley[128];",
        )
        self.assertEqual(module.format_constant_declaration("float4", "_Tint"), "float4 _Tint;")

    def test_complete_binary_keyword_axis_emits_explicit_dispatch(self):
        variants = {(): "normal_call()", ("FLIP_V",): "flipped_call()"}
        emitted = module.conditional_call(variants, {})
        self.assertIn("#if defined(FLIP_V)", emitted)
        self.assertIn("flipped_call();", emitted)
        self.assertIn("#else", emitted)
        self.assertIn("normal_call();", emitted)

    def test_incomplete_variant_axis_refuses_missing_default(self):
        with self.assertRaisesRegex(RuntimeError, "complete independent keyword axes"):
            module.conditional_call({("FLIP_V",): "flipped_call()"}, {})

    def test_multiple_keyword_axes_refuse_ambiguous_subset_dispatch(self):
        variants = {
            (): "base_call()",
            ("A",): "a_call()",
            ("B",): "b_call()",
            ("A", "B"): "ab_call()",
        }
        with self.assertRaisesRegex(RuntimeError, "single-keyword variant axis"):
            module.conditional_call(variants, {})

    def pass_metadata(self):
        blend = {
            "srcBlend": {"val": 1.0, "name": "<noninit>"},
            "destBlend": {"val": 0.0, "name": "<noninit>"},
            "srcBlendAlpha": {"val": 1.0, "name": "<noninit>"},
            "destBlendAlpha": {"val": 0.0, "name": "<noninit>"},
            "blendOp": {"val": 0.0, "name": "<noninit>"},
            "blendOpAlpha": {"val": 0.0, "name": "<noninit>"},
            "colMask": {"val": 15.0, "name": "<noninit>"},
        }
        return {
            "m_LOD": 0,
            "m_Tags": {"tags": []},
            "m_Passes": [
                {
                    "m_Type": 0,
                    "m_ProgramMask": 6,
                    "m_UseName": "",
                    "m_Name": "",
                    "m_TextureName": "",
                    "m_Tags": {"tags": []},
                    "m_HasInstancingVariant": False,
                    "m_HasProceduralInstancingVariant": False,
                    "m_LOD": 0,
                    "m_State": {
                        "m_Name": "",
                        "m_LOD": 0,
                        "lighting": False,
                        **{f"rtBlend{i}": copy.deepcopy(blend) for i in range(8)},
                        "conservative": {"val": 0},
                        "offsetFactor": {"val": 0},
                        "offsetUnits": {"val": 0},
                        "fogMode": -1,
                    },
                }
            ],
        }

    def test_serialized_pass_contract_is_accepted_when_all_fields_are_represented(self):
        module.validate_wrapper_metadata("synthetic", self.pass_metadata())

    def test_unsupported_pass_metadata_and_render_states_refuse(self):
        mutations = (
            ("m_Type", 1, "serialized m_Type"),
            ("m_ProgramMask", 2, "serialized m_ProgramMask"),
            ("m_UseName", "USE_PASS", "serialized m_UseName"),
            ("m_Name", "named", "serialized m_Name"),
            ("m_TextureName", "_MainTex", "serialized m_TextureName"),
            ("m_Tags", {"tags": [["LightMode", "Always"]]}, "serialized m_Tags"),
            ("m_HasInstancingVariant", True, "serialized m_HasInstancingVariant"),
        )
        for field, value, message in mutations:
            tree = self.pass_metadata()
            tree["m_Passes"][0][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                module.validate_wrapper_metadata("synthetic", tree)

        tree = self.pass_metadata()
        tree["m_Passes"][0]["m_State"]["conservative"]["val"] = 1
        with self.assertRaisesRegex(RuntimeError, "conservative rasterization"):
            module.validate_wrapper_metadata("synthetic", tree)

        tree = self.pass_metadata()
        tree["m_Passes"][0]["m_State"]["lighting"] = True
        with self.assertRaisesRegex(RuntimeError, "LOD/lighting contract"):
            module.validate_wrapper_metadata("synthetic", tree)

        tree = self.pass_metadata()
        tree["m_Passes"][0]["m_State"]["rtBlend7"]["srcBlend"]["val"] = 2
        with self.assertRaisesRegex(RuntimeError, "independent MRT blend"):
            module.validate_wrapper_metadata("synthetic", tree)

    def test_pass_map_preserves_shared_fragment_program_reference(self):
        vertex0 = {"index": 1, "stage": "progVertex", "keywords": []}
        vertex1 = {"index": 5, "stage": "progVertex", "keywords": []}
        fragment = {"index": 3, "stage": "progFragment", "keywords": []}
        records = {1: vertex0, 3: fragment, 5: vertex1}
        native_pass0 = {
            "progVertex": {
                "m_PlayerSubPrograms": [
                    [],
                    [],
                    [],
                    [{"m_BlobIndex": 1, "m_KeywordIndices": []}],
                ]
            },
            "progFragment": {
                "m_PlayerSubPrograms": [
                    [],
                    [],
                    [],
                    [{"m_BlobIndex": 3, "m_KeywordIndices": []}],
                ]
            },
        }
        native_pass1 = {
            "progVertex": {
                "m_PlayerSubPrograms": [
                    [],
                    [],
                    [],
                    [{"m_BlobIndex": 5, "m_KeywordIndices": []}],
                ]
            },
            "progFragment": {
                "m_PlayerSubPrograms": [
                    [],
                    [],
                    [],
                    [{"m_BlobIndex": 3, "m_KeywordIndices": []}],
                ]
            },
        }
        selected0 = module.selected_pass_records(native_pass0, records)
        selected1 = module.selected_pass_records(native_pass1, records)
        self.assertEqual(selected0["progVertex"][()]["index"], 1)
        self.assertEqual(selected1["progVertex"][()]["index"], 5)
        self.assertIs(selected0["progFragment"][()], fragment)
        self.assertIs(selected1["progFragment"][()], fragment)


if __name__ == "__main__":
    unittest.main()
