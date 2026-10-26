"""Authored fixtures for the bounded legacy Barrier keyword policy."""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
S = importlib.import_module("payload_shader_records")


class ParticleCarrierTests(unittest.TestCase):
    def fixture(self):
        names = ["_ALPHABLEND_ON", "_ALPHAMODULATE_ON", "FOG_LINEAR", "FOG_EXP", "INSTANCING_ON", "PROCEDURAL_INSTANCING_ON"]

        def shader_pass(name, kind, program):
            return {"m_Type": kind, "m_State": {"m_Name": name, "gpuProgramID": program, "m_Tags": {"tags": []}}}

        source = {
            "m_ParsedForm": {
                "m_Name": "Particles/Standard Unlit",
                "m_PropInfo": {"m_Props": []},
                "m_KeywordNames": names,
                "m_SubShaders": [
                    {"m_Passes": [shader_pass("Grab", 1, -1), shader_pass("EditorPicking", 0, 5), shader_pass("Shadow", 0, 10), shader_pass("Main", 0, 20)]}
                ],
            }
        }
        carrier = deepcopy(source)
        passes = carrier["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]
        del passes[1]
        for shader in passes[1:]:
            shader["progFragment"] = {"m_PlayerSubPrograms": [[], [], [], [{"m_KeywordIndices": keys} for keys in ([1, 2], [0, 3], [0, 2, 4], [0, 2, 5], [2])]]}
        return source, carrier, [{"m_EnableInstancingVariants": False, "m_ShaderKeywords": "_ALPHABLEND_ON"}]

    def test_original_runtime_passes_and_fragment_order_preserve_procedural_instancing(self):
        source, carrier, materials = self.fixture()
        before = deepcopy(source)
        runtime, rows = S.particles_selections(source, materials, carrier=carrier)
        self.assertEqual(source, before)
        self.assertEqual([row["m_State"]["m_Name"] for row in runtime["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]], ["Grab", "Shadow", "Main"])
        expected = [["FOG_LINEAR", "_ALPHAMODULATE_ON"], ["FOG_LINEAR", "PROCEDURAL_INSTANCING_ON", "_ALPHABLEND_ON"], ["FOG_LINEAR"]]
        self.assertEqual(rows[10], [expected] * 3)
        self.assertEqual(rows[20], [expected] * 3)
        rows[10][0][0].append("CALLER")
        self.assertNotIn("CALLER", rows[10][1][0])

    def test_property_declaration_must_match(self):
        source, carrier, materials = self.fixture()
        carrier["m_ParsedForm"]["m_PropInfo"]["m_Props"].append({"m_Name": "_Different"})
        with self.assertRaisesRegex(ValueError, "properties differ"):
            S.particles_selections(source, materials, carrier=carrier)


class TerrainBaseGeneratorTests(unittest.TestCase):
    def fixture(self):
        return {
            "m_Dependencies": [],
            "m_ParsedForm": {
                "m_PropInfo": {"m_Props": []},
                "m_SubShaders": [{"m_Passes": [{"m_Type": 0, "m_State": {"gpuProgramID": identity, "m_Tags": {"tags": []}}} for identity in (10, 20, 30)]}],
            },
            "m_CompileInfo": {
                "m_Snippets": [
                    (
                        identity,
                        {
                            **{group + str(stage): [] for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal") for stage in range(7)},
                            "m_VariantsBuiltin0": [],
                            "m_NonStrippedUserKeywords": "",
                        },
                    )
                    for identity in (10, 20, 30)
                ]
            },
        }

    def test_three_source_passes_retain_empty_variant_in_each_tier(self):
        source = self.fixture()
        self.assertEqual(S.terrain_basegen_selections(deepcopy(source), source, []), {identity: [[[]], [[]], [[]]] for identity in (10, 20, 30)})

    def test_original_property_contract_must_match_sdk(self):
        original, sdk = self.fixture(), self.fixture()
        original["m_ParsedForm"]["m_PropInfo"]["m_Props"] = [{"m_Name": "_Different"}]
        with self.assertRaisesRegex(ValueError, "properties differ"):
            S.terrain_basegen_selections(original, sdk, [])


class BarrierShaderSelectionTests(unittest.TestCase):
    def fixture(self):
        return {
            "m_CompileInfo": {
                "m_Snippets": [
                    [
                        17,
                        {
                            "m_VariantsUserGlobal0": [["_", "FOG_LINEAR", "FOG_EXP", "FOG_EXP2"], ["_", "POINT", "SPOT"]],
                            "m_VariantsUserLocal0": [],
                            "m_VariantsBuiltin0": [],
                        },
                    ],
                    [
                        23,
                        {
                            "m_VariantsUserGlobal0": [["__", "FOG_LINEAR", "FOG_EXP", "FOG_EXP2"]],
                            "m_VariantsUserLocal0": [],
                            "m_VariantsBuiltin0": [],
                        },
                    ],
                ]
            }
        }

    def test_keeps_point_and_spot_after_removing_unused_fog(self):
        source = self.fixture()
        actual = S.vertexlit_selections(source)
        self.assertEqual(actual[17], [[[], ["POINT"], ["SPOT"]]] * 3)
        self.assertEqual(actual[23], [[[]]] * 3)

    def test_preserves_other_declared_keyword_axes_and_their_order(self):
        source = self.fixture()
        source["m_CompileInfo"]["m_Snippets"][0][1]["m_VariantsUserLocal0"] = [["__", "LOCAL_OPTION"]]
        actual = S.vertexlit_selections(source)[17][0]
        self.assertEqual(actual, [[], ["LOCAL_OPTION"], ["POINT"], ["POINT", "LOCAL_OPTION"], ["SPOT"], ["SPOT", "LOCAL_OPTION"]])

    def test_source_and_tier_selections_do_not_alias(self):
        source = self.fixture()
        before = deepcopy(source)
        actual = S.vertexlit_selections(source)
        actual[17][0][1].append("CALLER_TEST")
        self.assertEqual(source, before)
        self.assertEqual(actual[17][1], [[], ["POINT"], ["SPOT"]])
        self.assertEqual(actual[17][2], [[], ["POINT"], ["SPOT"]])


class BarrierShaderInputBoundaryTests(unittest.TestCase):
    def roots(self, temporary):
        base = Path(temporary).resolve()
        providers = [base / name for name in ("pc", "sdk", "legacy", "templates")]
        for provider in providers:
            provider.mkdir()
        return base, providers

    def test_new_output_outside_inputs_is_pure(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            output = base / "output"
            self.assertEqual(S.checked_output(output, providers), output)
            self.assertFalse(output.exists())
            self.assertTrue(all(not list(root.iterdir()) for root in providers))

    def test_rejects_output_inside_or_containing_any_input_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            for root in providers:
                with self.subTest(provider=root.name), self.assertRaisesRegex(ValueError, "overlaps"):
                    S.checked_output(root / "output", providers)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                S.checked_output(base, providers)
            self.assertTrue(all(not list(root.iterdir()) for root in providers))

    def test_rejects_existing_or_symlinked_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            existing = base / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(ValueError, "new"):
                S.checked_output(existing, providers)
            link = base / "link"
            link.symlink_to(base / "absent")
            with self.assertRaisesRegex(ValueError, "symlink"):
                S.checked_output(link, providers)
            alias = base / "original-alias"
            alias.symlink_to(providers[0], target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                S.checked_output(alias / "output", providers)
            self.assertFalse((providers[0] / "output").exists())

    def reject_profile(self, base, providers, profile, profile_sha=None, codec_sha=None):
        path = base / "profile.json"
        path.write_text(json.dumps(profile))
        codec = base / "codec"
        codec.write_bytes(b"authored-codec-fixture")
        return S.produce(
            path,
            profile_sha or hashlib.sha256(path.read_bytes()).hexdigest(),
            *providers[:3],
            providers[3],
            base / "output",
            codec,
            codec_sha or hashlib.sha256(codec.read_bytes()).hexdigest(),
        )

    def test_rejects_unknown_original_input_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            with self.assertRaisesRegex(ValueError, "accepted current original"):
                self.reject_profile(base, providers, {"input_id": "unaccepted"})
            self.assertFalse((base / "output").exists())

    def test_rejects_changed_profile_and_codec_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            with self.assertRaises(ValueError):
                self.reject_profile(base, providers, {"input_id": S.INPUT_ID}, profile_sha="0" * 64)
            with self.assertRaises(ValueError):
                self.reject_profile(base, providers, {"input_id": S.INPUT_ID}, codec_sha="0" * 64)
            self.assertFalse((base / "output").exists())

    def test_rejects_unsafe_or_changed_original_source_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, providers = self.roots(temporary)
            original = providers[0] / "source.bin"
            original.write_bytes(b"owner-source")
            profile = {"input_id": S.INPUT_ID, "compiler_sdk": {}, "legacy_sdk": {}}
            for source in ("../source.bin", "source.bin"):
                profile["source_type"] = {"path": source, "bytes": original.stat().st_size, "sha256": "0" * 64}
                with self.subTest(source=source), self.assertRaises(ValueError):
                    self.reject_profile(base, providers, profile)
            self.assertFalse((base / "output").exists())
            self.assertEqual(original.read_bytes(), b"owner-source")


class PostprocessingCarrierTests(unittest.TestCase):
    def test_original_shader_requires_source_class_and_body_pin(self):
        body = b"authored original Shader fixture"
        obj = SimpleNamespace(
            type=SimpleNamespace(name="Shader"),
            get_raw_data=lambda: body,
            read_typetree=lambda: "source-form",
            serialized_type=SimpleNamespace(node="source-schema"),
        )
        asset = SimpleNamespace(objects={3: obj})
        selection = {"path_id": 3, "source_sha256": hashlib.sha256(body).hexdigest()}
        self.assertEqual(S.original_shader(asset, selection), ("source-form", "source-schema"))
        with self.assertRaisesRegex(ValueError, "body differs"):
            S.original_shader(asset, {**selection, "source_sha256": "0" * 64})
        obj.type.name = "Material"
        with self.assertRaisesRegex(ValueError, "body differs"):
            S.original_shader(asset, selection)

    def test_current_dummy_dispatch_needs_no_legacy_sdk_and_refuses_source_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            pc, sdk, templates = [base / name for name in ("pc", "sdk", "templates")]
            for directory in (pc, sdk, templates):
                directory.mkdir()
            original = pc / "source.bundle"
            original.write_bytes(b"changed-input")
            codec = base / "codec"
            codec.write_bytes(b"authored fixture codec")
            profile = base / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "input_id": S.INPUT_ID,
                        "shaders": [],
                        "source": {"path": "source.bundle", "bytes": original.stat().st_size, "sha256": "0" * 64},
                        "sdk": {},
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "input/output differs"):
                S.produce(
                    profile,
                    hashlib.sha256(profile.read_bytes()).hexdigest(),
                    pc,
                    sdk,
                    None,
                    templates,
                    base / "output",
                    codec,
                    hashlib.sha256(codec.read_bytes()).hexdigest(),
                )
            self.assertFalse((base / "output").exists())
            self.assertEqual(original.read_bytes(), b"changed-input")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                S.checked_output(pc / "output", (pc, sdk, templates))
            self.assertFalse((pc / "output").exists())

    def compile_fixture(self, changed_tier=False, keywords=None):
        text = 'Shader "Fixture" { Properties { _MainTex ("", 2DArray)="white"{} } SubShader {} }'
        pre = {"success": True, "snippets": [{"fields": [7], "source": "authored snippet"}], "records": [{"kind": "keywordsEnd", "fields": [7]}]}
        calls = []

        def compile(source, filename, **arguments):
            calls.append((source, filename, arguments))
            return {
                "success": True,
                "data": bytes([len(calls)]) if changed_tier else b"fresh native",
                "reflection": ["fresh reflection"],
                "gpu_program_type": 24,
            }

        connection = SimpleNamespace(preprocess=lambda *args, **kwargs: pre, compile=compile, capabilities="SDK caps")

        def node(kind, name, children=()):
            return SimpleNamespace(m_Type=kind, m_Name=name, m_Children=children)

        prop = node(
            "SerializedProperty",
            "data",
            [
                node("string", "m_Name"),
                node("string", "m_Description"),
                node("int", "m_Type"),
                *[node("float", f"m_DefValue[{i}]") for i in range(4)],
                node("Texture", "m_DefTexture", [node("string", "m_DefaultName"), node("int", "m_TexDim")]),
            ],
        )

        def construct(actual_node, shaderlab, actual_pre, compiled, compress, registry):
            self.assertEqual(shaderlab, text)
            self.assertEqual(actual_pre, pre)
            self.assertEqual(compiled[7]["identity"], b"source editor id!")
            return {"m_Dependencies": [], "properties": S.P.properties(prop, shaderlab)}

        with patch.multiple(
            S.P,
            retained_keywords=lambda *args: [[]] if keywords is None else keywords,
            shader_requirements=lambda *args: 1,
            platform_keywords=lambda image, tier: [str(tier["tier0"]["standardShaderQuality"])],
            compilation_flags=lambda *args: 0,
            editor_hash=lambda *args: b"source editor id!",
            construct=construct,
        ):
            tree = S.postprocessing_tree(
                connection,
                text,
                "Assets/Fixture.shader",
                {"m_ParsedForm": {"m_KeywordNames": [], "m_KeywordFlags": []}},
                "source node",
                {"caching_preprocessor": True, "tier0": {"standardShaderQuality": 0}},
                b"SDK",
                b"includes",
                lambda *args: b"codec",
            )
        return tree, calls

    def test_array_property_and_fresh_tier_responses_flow_to_constructor(self):
        tree, calls = self.compile_fixture()
        self.assertEqual(tree["properties"][0]["m_Type"], 4)
        self.assertEqual(tree["properties"][0]["m_DefTexture"], {"m_DefaultName": "white", "m_TexDim": 5})
        self.assertEqual([call[2]["platform_keywords"] for call in calls], [["0"], ["1"]])
        self.assertEqual([call[2]["keywords"] for call in calls], [[], []])

    def test_refuses_nonempty_source_keywords_or_unequal_tier_programs(self):
        with self.assertRaisesRegex(ValueError, "empty keyword set"):
            self.compile_fixture(keywords=[["SOURCE_OPTION"]])
        with self.assertRaisesRegex(ValueError, "tiers differ"):
            self.compile_fixture(changed_tier=True)


class StandardRetentionTests(unittest.TestCase):
    def fixture(self):
        names = [
            "FOG_LINEAR",
            "FOG_EXP",
            "INSTANCING_ON",
            "_NORMALMAP",
            "_SPECULARHIGHLIGHTS_OFF",
            "_GLOSSYREFLECTIONS_OFF",
            "_EMISSION",
            "DIRECTIONAL",
            "LIGHTMAP_ON",
        ]
        fog = ["_", "FOG_LINEAR", "FOG_EXP"]
        instance = ["_", "INSTANCING_ON"]
        snippet = {
            "m_NonStrippedUserKeywords": "FOG_LINEAR FOG_EXP INSTANCING_ON",
            "m_VariantsUserGlobal0": [fog, instance],
            "m_VariantsUserGlobal1": [["_", "_EMISSION"], fog, instance],
            "m_VariantsBuiltin0": [["DIRECTIONAL"], ["DIRECTIONAL", "LIGHTMAP_ON"]],
            "m_VariantsBuiltin1": [["DIRECTIONAL"], ["DIRECTIONAL", "LIGHTMAP_ON"]],
        }
        shader_pass = {
            "m_State": {
                "gpuProgramID": 10,
                "m_Tags": {"tags": [("LightMode", "ForwardBase")]},
            },
            "m_SerializedKeywordStateMask": list(range(len(names))),
        }
        meta = deepcopy(shader_pass)
        meta["m_State"]["m_Tags"]["tags"] = [("LightMode", "Meta")]
        source = {
            "m_ParsedForm": {
                "m_Name": "Standard",
                "m_KeywordNames": names,
                "m_KeywordFlags": [0, 0, 0, 1, 1, 1, 0, 0, 0],
                "m_SubShaders": [{"m_Passes": [shader_pass, meta]}],
            },
            "m_CompileInfo": {"m_Snippets": [(10, snippet)]},
        }
        materials = [
            {
                "m_ValidKeywords": keys,
                "m_InvalidKeywords": [],
                "m_EnableInstancingVariants": True,
            }
            for keys in (
                [],
                ["_EMISSION"],
                ["_NORMALMAP", "_SPECULARHIGHLIGHTS_OFF", "_GLOSSYREFLECTIONS_OFF"],
            )
        ]
        return source, materials

    def test_global_shader_feature_obeys_original_material_combinations(self):
        source, materials = self.fixture()
        _, selections = S.standard_selections(source, materials)
        rows = selections[10][0]
        self.assertEqual(12, len(rows))
        self.assertTrue(any("_EMISSION" in row for row in rows))
        self.assertTrue(any("_NORMALMAP" in row for row in rows))
        self.assertFalse(any("_EMISSION" in row and "_NORMALMAP" in row for row in rows))
        self.assertEqual(selections[10][0], selections[10][1])
        self.assertEqual(selections[10][1], selections[10][2])

    def test_original_fragment_order_is_independent_of_closure_encounter_order(self):
        source, materials = self.fixture()
        source["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["m_State"]["m_Name"] = "FORWARD"
        carrier = deepcopy(source)
        carrier["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["progFragment"] = {
            "m_PlayerSubPrograms": [
                [],
                [],
                [],
                [{"m_KeywordIndices": keys} for keys in ([7], [3, 7], [6, 7], [3, 4, 5, 7])],
            ]
        }
        _, expected = S.standard_selections(source, materials, carrier=carrier)
        _, actual = S.standard_selections(source, list(reversed(materials)), carrier=carrier)
        self.assertEqual(expected, actual)
        self.assertEqual(["DIRECTIONAL", "_EMISSION"], actual[10][0][1])
        self.assertEqual(["DIRECTIONAL", "_GLOSSYREFLECTIONS_OFF", "_NORMALMAP", "_SPECULARHIGHLIGHTS_OFF"], actual[10][0][2])

    def test_explicit_sdk_mapping_removes_only_mapped_emission(self):
        source, materials = self.fixture()
        original = deepcopy(materials[1])
        default = {**materials[0], "m_Shader": {"m_FileID": 0, "m_PathID": 46}}
        sdk = {10303: SimpleNamespace(type=SimpleNamespace(name="Material"), read_typetree=lambda: default)}
        mapped = S.standard_material({"sdk_material": 10303}, original, sdk)
        _, rows = S.standard_selections(source, [materials[0], mapped])
        self.assertFalse(any("_EMISSION" in keys for keys in rows[10][0]))
        # Another material with identical keywords remains genuinely emissive.
        genuine = S.standard_material({}, original, sdk)
        _, rows = S.standard_selections(source, [mapped, genuine])
        self.assertTrue(any("_EMISSION" in keys for keys in rows[10][0]))
        self.assertEqual(original, materials[1])
        with self.assertRaisesRegex(ValueError, "identity differs"):
            S.standard_material({"sdk_material": 7}, original, sdk)

    def test_exp2_retains_only_the_enabled_source_fog_keyword(self):
        source, materials = self.fixture()
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        snippet["m_NonStrippedUserKeywords"] += " FOG_EXP2"
        for stage in range(2):
            for axis in snippet["m_VariantsUserGlobal" + str(stage)]:
                if "FOG_LINEAR" in axis and "FOG_EXP2" not in axis:
                    axis.append("FOG_EXP2")
        _, selections = S.standard_selections(source, materials, "FOG_EXP2")
        rows = selections[10][0]
        self.assertTrue(any("FOG_EXP2" in row for row in rows))
        self.assertFalse(any("FOG_LINEAR" in row or "FOG_EXP" in row for row in rows))

    def test_runtime_retention_uses_source_tags_without_mutating_sdk_tree(self):
        source, materials = self.fixture()
        original = deepcopy(source)
        runtime, selections = S.standard_selections(source, materials)
        self.assertEqual(original, source)
        self.assertEqual(1, len(runtime["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]))
        self.assertFalse(any("FOG_EXP" in row or "LIGHTMAP_ON" in row for row in selections[10][0]))
        self.assertTrue(any("FOG_LINEAR" in row for row in selections[10][0]))
        self.assertTrue(any("INSTANCING_ON" in row for row in selections[10][0]))


class TwoSeedRetentionTests(unittest.TestCase):
    fixture = StandardRetentionTests.fixture

    def test_recursive_scene_closure_accepts_four_material_feature_seeds(self):
        source, materials = self.fixture()
        _, expected = S.standard_selections(source, materials, None)
        _, actual = S.standard_selections(source, materials + [materials[0]], None)
        self.assertEqual(actual, expected)

    def test_single_default_material_without_fog_removes_fog_and_instancing(self):
        source, materials = self.fixture()
        materials = materials[:1]
        materials[0]["m_EnableInstancingVariants"] = False
        _, selections = S.standard_selections(source, materials, None)
        self.assertEqual(selections[10], [[["DIRECTIONAL"]]] * 3)

    def test_no_fog_still_retains_original_emission_and_instancing(self):
        source, materials = self.fixture()
        _, selections = S.standard_selections(source, materials[:2], None)
        rows = selections[10][0]
        self.assertEqual(4, len(rows))
        self.assertTrue(any("_EMISSION" in row for row in rows))
        self.assertTrue(any("INSTANCING_ON" in row for row in rows))
        self.assertFalse(any(key.startswith("FOG_") for row in rows for key in row))

    def test_two_original_materials_retain_emission_and_instancing_without_other_features(
        self,
    ):
        source, materials = self.fixture()
        _, selections = S.standard_selections(source, materials[:2])
        rows = selections[10][0]
        self.assertEqual(8, len(rows))
        self.assertTrue(any("_EMISSION" in row for row in rows))
        self.assertTrue(any("INSTANCING_ON" in row for row in rows))
        self.assertTrue(any("FOG_LINEAR" in row for row in rows))
        self.assertFalse(any("_NORMALMAP" in row for row in rows))

    def test_selected_original_materials_control_instancing(self):
        source, materials = self.fixture()
        materials = materials[:2]
        for material in materials:
            material["m_EnableInstancingVariants"] = False
        _, selections = S.standard_selections(source, materials)
        rows = selections[10][0]
        self.assertEqual(4, len(rows))
        self.assertFalse(any("INSTANCING_ON" in row for row in rows))
        self.assertTrue(any("_EMISSION" in row for row in rows))


class StandardSceneUsageTests(unittest.TestCase):
    def fixture(self):
        return (
            [{"m_Fog": True, "m_FogMode": 1}],
            [
                {
                    "m_Lightmaps": [],
                    "m_GISettings": {
                        "m_EnableBakedLightmaps": True,
                        "m_EnableRealtimeLightmaps": True,
                    },
                    "m_EnlightenSceneMapping": {
                        key: []
                        for key in (
                            "m_Renderers",
                            "m_Systems",
                            "m_Probesets",
                            "m_SystemAtlases",
                            "m_TerrainChunks",
                        )
                    },
                }
            ],
            [{"m_LightmapIndex": 65535, "m_LightmapIndexDynamic": 65535}],
        )

    def test_enabled_baking_preferences_without_actual_data_are_unused(self):
        fog, maps, renderers = self.fixture()
        before = deepcopy((fog, maps, renderers))
        S.validate_standard_scene(fog, maps, renderers)
        self.assertEqual(before, (fog, maps, renderers))

    def test_disabled_fog_ignores_inactive_exp_mode(self):
        fog, maps, renderers = self.fixture()
        fog[0].update(m_Fog=False, m_FogMode=3)
        self.assertIsNone(S.validate_standard_scene(fog, maps, renderers))
        fog[0].update(m_Fog=True, m_FogMode=0)
        with self.assertRaisesRegex(ValueError, "fog retention"):
            S.validate_standard_scene(fog, maps, renderers)

    def test_enabled_source_fog_modes_select_sdk_keyword_without_mutation(self):
        for mode, keyword in ((1, "FOG_LINEAR"), (2, "FOG_EXP"), (3, "FOG_EXP2")):
            with self.subTest(mode=mode):
                fog, maps, renderers = self.fixture()
                fog[0]["m_FogMode"] = mode
                before = deepcopy((fog, maps, renderers))
                self.assertEqual(S.validate_standard_scene(fog, maps, renderers), keyword)
                self.assertEqual(before, (fog, maps, renderers))

    def test_actual_baked_data_and_realtime_mapping_reject(self):
        fog, maps, renderers = self.fixture()
        maps[0]["m_Lightmaps"] = [{"m_LightmapColor": {"m_FileID": 0, "m_PathID": 9}}]
        with self.assertRaisesRegex(ValueError, "lightmap usage"):
            S.validate_standard_scene(fog, maps, renderers)
        maps[0]["m_Lightmaps"] = []
        maps[0]["m_EnlightenSceneMapping"]["m_Systems"] = [{}]
        with self.assertRaisesRegex(ValueError, "realtime lighting"):
            S.validate_standard_scene(fog, maps, renderers)

    def test_bound_static_or_dynamic_renderer_rejects(self):
        for field in ("m_LightmapIndex", "m_LightmapIndexDynamic"):
            with self.subTest(field=field):
                fog, maps, renderers = self.fixture()
                renderers[0][field] = 0
                with self.assertRaisesRegex(ValueError, "renderer uses"):
                    S.validate_standard_scene(fog, maps, renderers)


if __name__ == "__main__":
    unittest.main()
