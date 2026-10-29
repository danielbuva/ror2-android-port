"""Authored contracts for prefab fallback registration and retention."""

from copy import deepcopy
import importlib
from pathlib import Path
import sys
import unittest

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
