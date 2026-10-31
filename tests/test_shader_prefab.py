"""Authored contracts for prefab fallback registration and retention."""

from copy import deepcopy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
S = importlib.import_module("shader_prefab")


def snippet(global_axes=(), local_axes=(), builtins=(), runtime=""):
    value = {group + str(stage): [] for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal") for stage in range(7)}
    value.update(
        m_VariantsUserGlobal0=list(global_axes),
        m_VariantsUserLocal0=list(local_axes),
        m_VariantsBuiltin0=list(builtins),
        m_NonStrippedUserKeywords=runtime,
        m_BuiltinKeywords=" ".join(dict.fromkeys(k for row in builtins for k in row)),
    )
    return value


class PrefabShaderTests(unittest.TestCase):
    def test_original_vertex_order_covers_vertex_only_runtime_keywords(self):
        row = {"m_Type": 0, "m_State": {"gpuProgramID": 11, "m_Name": "MAIN", "m_Tags": {"tags": []}}}
        source = {
            "m_CompileInfo": {"m_Snippets": [(11, snippet([["__", "VERTEXLIGHT_ON"], ["__", "A"]], runtime="VERTEXLIGHT_ON"))]},
            "m_ParsedForm": {"m_KeywordNames": ["A", "VERTEXLIGHT_ON"], "m_SubShaders": [{"m_Passes": [row]}]},
        }
        carrier = deepcopy(source)
        original = carrier["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]
        original["progFragment"] = {"m_PlayerSubPrograms": [[{"m_KeywordIndices": keys} for keys in ([], [0])]]}
        original["progVertex"] = {"m_PlayerSubPrograms": [[{"m_KeywordIndices": keys} for keys in ([], [0, 1], [1], [0])]]}
        self.assertEqual(
            S.prefab_selections(source, material_keywords=[{"A"}], carrier=carrier)[11],
            [[[], ["A", "VERTEXLIGHT_ON"], ["VERTEXLIGHT_ON"], ["A"]]] * 3,
        )

    def test_source_cycle_lifts_fragment_feature_over_vertex_contexts(self):
        def shader_pass(name):
            return {"m_Type": 0, "m_State": {"m_Name": name, "m_Tags": {"tags": [("LightMode", name)]}}}

        row = shader_pass("Forward")
        source = deepcopy(row)
        # Vertex-only V and fragment-only F share context C. The original
        # fragment cycle wraps to the first context after visiting the second.
        source["progVertex"] = {"m_PlayerSubPrograms": [[{"m_KeywordIndices": k} for k in ([], [2], [0], [0, 2])]]}
        source["progFragment"] = {"m_PlayerSubPrograms": [[{"m_KeywordIndices": k} for k in ([], [0, 1], [0], [1])]]}
        carrier = {"m_ParsedForm": {"m_KeywordNames": ["C", "F", "V"], "m_SubShaders": [{"m_Passes": [shader_pass("Meta"), source]}]}}
        selected = [[], ["V"], ["F"], ["F", "V"], ["C"], ["C", "V"], ["C", "F"], ["C", "F", "V"]]
        actual = S.A.original_feature_order(carrier, 0, 0, row, {"C", "F", "V"}, selected, stage="progVertex")
        self.assertEqual(actual, [[], ["F", "V"], ["V"], ["C", "F"], ["C"], ["C", "F", "V"], ["C", "V"], ["F"]])

    def test_material_features_preserve_combinations_without_union(self):
        source = {
            "m_CompileInfo": {"m_Snippets": [(11, snippet([["__", "A"], ["__", "B"]]))]},
            "m_ParsedForm": {"m_SubShaders": [{"m_Passes": [{"m_Type": 0, "m_State": {"gpuProgramID": 11, "m_Tags": {"tags": []}}}]}]},
        }
        rows = S.prefab_selections(source, material_keywords=[{"A"}, {"B"}, {"A"}])[11]
        self.assertEqual(rows, [[[], ["B"], ["A"]]] * 3)

    def test_empty_terrain_details_strip_instancing_from_default_shaders(self):
        source = {
            "m_CompileInfo": {"m_Snippets": [(11, snippet([["__", "INSTANCING_ON"]], runtime="INSTANCING_ON"))]},
            "m_ParsedForm": {"m_SubShaders": [{"m_Passes": [{"m_Type": 0, "m_State": {"gpuProgramID": 11, "m_Tags": {"tags": []}}}]}]},
        }
        pointer = {"m_FileID": 2, "m_PathID": 7}
        terrain = {"m_DetailDatabase": {**{f"m_DefaultShaders[{i}]": pointer for i in range(3)}, "m_DetailPrototypes": []}}
        self.assertEqual(S.terrain_selections(source, terrain, pointer), {11: [[[]]] * 3})
        terrain["m_DetailDatabase"]["m_DetailPrototypes"] = [{"m_UseInstancing": True}]
        with self.assertRaisesRegex(ValueError, "prototype usage"):
            S.terrain_selections(source, terrain, pointer)

    def test_original_fallback_retains_local_edge_and_unresolved_literal(self):
        selected = {"original": {"path": "original.bundle", "member": "CAB-source"}, "fallback_original": []}
        source = {"m_Dependencies": [], "m_ParsedForm": {"m_FallbackName": "Legacy/Diffuse"}}
        original = Mock()
        self.assertEqual(S.original_fallback_dependencies(source, selected, original), [])
        original.assert_not_called()
        witness = dict(selected["original"], path_id=-7)
        selected["fallback_original"] = [{"original": witness, "to": [0, 19]}]
        source["m_Dependencies"] = [{"m_FileID": 0, "m_PathID": -7}]
        source["m_ParsedForm"]["m_FallbackName"] = "Water/Single Sided"
        original.return_value.read_typetree.return_value = {"m_ParsedForm": {"m_Name": "Water/Single Sided"}}
        self.assertEqual(S.original_fallback_dependencies(source, selected, original), [{"m_FileID": 0, "m_PathID": 19}])
        original.assert_called_once_with(witness)

    def test_inherited_snippet_order_owns_registry_without_reordering_existing_pass_names(self):
        first = snippet([["__", "FOG_LINEAR"]])
        second = snippet([["__", "INSTANCING_ON"]], [["_", "LOCAL"]], [["SHADOWS_DEPTH"], ["SHADOWS_CUBE"]])
        third = snippet([["__", "LATE"]], [["_", "LOCAL"]])
        source = {"m_CompileInfo": {"m_Snippets": [(1, first), (2, second), (3, third)]}}
        before = deepcopy(source)
        seed = (["STEREO", "LOCAL"], [0, 1])
        self.assertEqual(
            S.keyword_registry(source, seed),
            (["STEREO", "LOCAL", "FOG_LINEAR", "INSTANCING_ON", "SHADOWS_DEPTH", "SHADOWS_CUBE", "LATE"], [0, 1, 0, 0, 0, 0, 0]),
        )
        self.assertEqual(source, before)
        self.assertEqual(seed, (["STEREO", "LOCAL"], [0, 1]))

    def test_stage_order_registers_local_and_builtin_before_later_global_axes(self):
        first = snippet([["__", "VERTEX"]], [["_", "LOCAL_VERTEX"]], [["BUILTIN", "SHARED"]])
        first["m_VariantsUserGlobal1"] = [["__", "FRAGMENT", "SHARED"]]
        first["m_VariantsUserLocal1"] = [["_", "LOCAL_FRAGMENT", "BUILTIN"]]
        source = {"m_CompileInfo": {"m_Snippets": [(1, first)]}}
        self.assertEqual(
            S.keyword_registry(source, (["SEED"], [1])),
            (["SEED", "VERTEX", "LOCAL_VERTEX", "BUILTIN", "SHARED", "FRAGMENT", "LOCAL_FRAGMENT"], [1, 0, 1, 0, 0, 0, 1]),
        )

    def test_particle_material_features_filter_original_order_and_keep_procedural_rows(self):
        names = ["_ALPHABLEND_ON", "_ALPHAMODULATE_ON", "PROCEDURAL_INSTANCING_ON", "FOG_EXP"]
        row = {"m_Type": 0, "m_State": {"m_Name": "Main", "gpuProgramID": 11, "m_Tags": {"tags": []}}}
        source = {
            "m_CompileInfo": {"m_Snippets": [(11, snippet(runtime="PROCEDURAL_INSTANCING_ON FOG_EXP"))]},
            "m_ParsedForm": {
                "m_Name": "Particles/Standard Unlit",
                "m_PropInfo": {},
                "m_KeywordNames": names,
                "m_KeywordFlags": [1, 1, 0, 0],
                "m_SubShaders": [{"m_Passes": [row]}],
            },
        }
        carrier = deepcopy(source)
        carrier["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["progFragment"] = {
            "m_PlayerSubPrograms": [[{"m_KeywordIndices": keys} for keys in ([], [0], [1], [0, 2], [0, 3])]]
        }
        material = {"m_Shader": {"m_FileID": 0, "m_PathID": 211}, "m_ValidKeywords": ["_ALPHABLEND_ON"], "m_EnableInstancingVariants": False}
        _, rows = S.particle_selections(source, carrier, material)
        self.assertEqual(rows, {11: [[[], ["_ALPHABLEND_ON"], ["PROCEDURAL_INSTANCING_ON", "_ALPHABLEND_ON"]]] * 3})
        # Original materials retain original runtime feature alternatives; the
        # acquired SDK default above intentionally strips unused local features.
        _, original_rows = S.A.particles_selections(source, [material], None, carrier=carrier)
        self.assertEqual(original_rows, {11: [[[], ["_ALPHABLEND_ON"], ["_ALPHAMODULATE_ON"], ["PROCEDURAL_INSTANCING_ON", "_ALPHABLEND_ON"]]] * 3})

    def test_prefab_keeps_instancing_and_softparticles_but_excludes_scene_fog_and_editor_passes(self):
        source_snippet = snippet(
            [["__", "INSTANCING_ON"], ["__", "SOFTPARTICLES_ON"], ["__", "FOG_LINEAR"]],
            builtins=[[], ["LIGHTMAP_ON"]],
            runtime="INSTANCING_ON SOFTPARTICLES_ON FOG_LINEAR",
        )
        source = {
            "m_CompileInfo": {"m_Snippets": [(11, source_snippet)]},
            "m_ParsedForm": {
                "m_SubShaders": [
                    {
                        "m_Passes": [
                            {"m_Type": 0, "m_State": {"gpuProgramID": 11, "m_Tags": {"tags": []}}},
                            {"m_Type": 0, "m_State": {"gpuProgramID": 22, "m_Tags": {"tags": [("LightMode", "Meta")]}}},
                        ]
                    }
                ]
            },
        }
        rows = S.prefab_selections(source)
        self.assertEqual(rows, {11: [[[], ["SOFTPARTICLES_ON"], ["INSTANCING_ON"], ["INSTANCING_ON", "SOFTPARTICLES_ON"]]] * 3})
        self.assertEqual(S.prefab_selections(deepcopy(source), retain_instancing=False), {11: [[[], ["SOFTPARTICLES_ON"]]] * 3})
        self.assertEqual(len(source["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]), 1)
        self.assertEqual(S.P.sdk_scene_variants(source_snippet, set()), [[], ["SOFTPARTICLES_ON"]])


if __name__ == "__main__":
    unittest.main()
