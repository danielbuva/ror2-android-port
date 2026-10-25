"""Authored shader records/hash contracts; no original or SDK fixtures."""

import struct
import unittest
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("shader_produce", Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output/shader_produce.py")
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)


class NativeRecords(unittest.TestCase):
    def test_reflection_not_fixed_target_names(self):
        r = N.reflection(["input: 2 9", "cb: Fixture 32 1", "const: tint 0 0 0 1 4 0", "cbbind: Fixture 5", "texbind: image 7 8 0 2"])
        self.assertEqual(r["buffers"][0]["constants"][0]["name"], "tint")
        tables = N.common_parameters(r)
        self.assertEqual(tables["m_NameIndices"], [["Fixture", 1], ["image", 0], ["tint", 2]])
        self.assertTrue(tables["m_CommonParameters"]["m_ConstantBuffers"][0]["m_IsPartialCB"])

    def test_all_buffer_names_precede_members_and_partial_is_not_a_prefix(self):
        reflected = N.reflection(
            [
                "cb: FragmentFixture 16 1",
                "const: gain 0 0 0 1 1 0",
                "cbbind: FragmentFixture 7",
                "cb: VertexFixture 64 1",
                "const: transform 0 0 1 4 4 0",
                "cbbind: VertexFixture 9",
            ]
        )
        result = N.common_parameters(reflected)
        self.assertEqual(dict(result["m_NameIndices"]), {"FragmentFixture": 0, "VertexFixture": 1, "gain": 2, "transform": 3})
        buffers = result["m_CommonParameters"]["m_ConstantBuffers"]
        self.assertTrue(all(row["m_IsPartialCB"] for row in buffers))
        self.assertEqual(buffers[1]["m_MatrixParams"][0]["m_NameIndex"], 3)
        self.assertEqual([row["m_NameIndex"] for row in result["m_CommonParameters"]["m_ConstantBufferBindings"]], [0, 1])

    def test_vertex_mask_and_alignment_derive_from_reflection(self):
        r = N.native_executable(b"abc", 25, {"inputs": [[2, 9]]})
        self.assertEqual(struct.unpack_from("<I", r, 28)[0], 3)
        self.assertEqual(r[32:36], b"abc\0")
        self.assertEqual(struct.unpack_from("<4I", r, 36), (4, 1, 2, 9))

    def test_vector_names_precede_matrices_within_each_buffer(self):
        reflected = N.reflection(["cb: Fixture 80 2", "const: matrix_first 0 0 1 4 4 0", "const: vector_second 64 0 0 1 4 0", "cbbind: Fixture 3"])
        table = N.common_parameters(reflected)
        self.assertEqual(dict(table["m_NameIndices"]), {"Fixture": 0, "vector_second": 1, "matrix_first": 2})
        buffer = table["m_CommonParameters"]["m_ConstantBuffers"][0]
        self.assertEqual(buffer["m_MatrixParams"][0]["m_Index"], 0)
        self.assertEqual(buffer["m_VectorParams"][0]["m_Index"], 64)
        raw = N.native_parameters(reflected, {"buffers": [], "bindings": [], "textures": []})
        self.assertLess(raw.index(N.string("vector_second")), raw.index(N.string("matrix_first")))

    def test_index_offsets_derive_from_records(self):
        r = N.segment([b"ab", b"cde"])
        self.assertEqual(struct.unpack_from("<7I", r), (2, 28, 2, 0, 30, 3, 0))
        self.assertEqual(r[28:], b"abcde")

    def test_parameter_string_alignment(self):
        r = N.native_parameters({"buffers": [{"name": "X", "size": 20}]})
        self.assertEqual(len(r) % 4, 0)
        self.assertEqual(struct.unpack_from("<2I", r), (N.VERSION, 2))
        self.assertIn(N.string("X") + N.words(20, 0, 0), r)
        self.assertTrue(r.endswith(N.words(0)))

    def test_variant_reflection_keeps_changing_buffers_native(self):
        def compiled(name, offset, payload):
            return {
                "data": payload,
                "gpu_program_type": 25,
                "reflection": [
                    "input: 2 9",
                    f"cb: {name} 32 1",
                    f"const: tint {offset} 0 0 1 4 0",
                    f"cbbind: {name} 5",
                    "texbind: image 7 8 0 2",
                ],
            }

        variants = [
            {"keywords": [], "requirements": 33, "compilation": compiled("FixtureA", 0, b"first")},
            {"keywords": ["FEATURE"], "requirements": 33, "compilation": compiled("FixtureB", 16, b"second")},
        ]
        raw, table, programs, parameters = N.variant_records(variants, ["FEATURE"])
        self.assertEqual(parameters, [0, 1])
        self.assertEqual([row["m_BlobIndex"] for row in programs], [2, 3])
        self.assertEqual([row["m_KeywordIndices"] for row in programs], [[], [0]])
        self.assertEqual(table["m_NameIndices"], [["image", 0]])
        self.assertEqual(table["m_CommonParameters"]["m_ConstantBuffers"], [])
        # Exercise the existing independent native parameter reader, not a
        # second test implementation of the producer's binary layout.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
        from shader_segments import parameter_layout

        for index, name, offset in [(0, "FixtureA", 0), (1, "FixtureB", 16)]:
            start, length, segment = struct.unpack_from("<3I", raw, 4 + 12 * index)
            self.assertEqual(segment, 0)
            parsed = parameter_layout(raw[start : start + length])
            self.assertEqual(parsed["buffers"][1]["name"], name)
            self.assertEqual(parsed["buffers"][1]["variables"][0]["offset"], offset)
            self.assertEqual(parsed["bindings"], [{"name": name, "kind": 1, "slot": 5, "extra": 0}])

    def test_identical_variant_parameters_are_deduplicated(self):
        compilation = {"data": b"same", "gpu_program_type": 25, "reflection": ["cb: Fixture 16 1", "const: value 0 0 0 1 1 0", "cbbind: Fixture 5"]}
        variants = [{"keywords": keys, "requirements": 33, "compilation": compilation} for keys in ([], ["Z", "A"])]
        raw, table, programs, parameters = N.variant_records(variants, ["Z", "A"])
        self.assertEqual(parameters, [0, 0])
        self.assertEqual([row["m_BlobIndex"] for row in programs], [1, 2])
        self.assertEqual(len(table["m_CommonParameters"]["m_ConstantBuffers"]), 1)
        offset, length, _ = struct.unpack_from("<3I", raw, 4 + 12 * 2)
        native = raw[offset : offset + length]
        self.assertEqual(native[24 : 24 + 4 + len(N.string("A")) + len(N.string("Z"))], N.words(2) + N.string("A") + N.string("Z"))

    def test_noncommon_texture_descriptor_precedes_buffer_binding(self):
        reflect = N.reflection(["texbind: image 7 8 1 2", "cb: Fixture 16 0", "cbbind: Fixture 9"])
        raw = N.native_parameters(reflect, {"buffers": [], "bindings": [], "textures": []})
        self.assertTrue(raw.endswith(N.words(2) + N.string("image") + N.words(0, 7, 8, 5) + N.string("Fixture") + N.words(1, 9, 0)))

    def test_unknown_reflection_is_rejected(self):
        with self.assertRaises(ValueError):
            N.reflection(["newkind: 1 2"])

    def test_constant_count_is_verified(self):
        with self.assertRaises(ValueError):
            N.reflection(["cb: Fixture 32 2", "const: tint 0 0 0 1 4 0"])


class ShaderHashTests(unittest.TestCase):
    def test_native_global_and_local_axes_keep_source_order_without_stage_duplicates(self):
        rows = [
            {"kind": kind, "fields": [7, stage], "values": axes}
            for stage in (0, 1)
            for kind, axes in (("keywordsUserGlobal", ["__ SH", "__ SOFT"]), ("keywordsUserLocal", ["__ CLIP"]))
        ]
        names, flags, variants = N.native_keywords({"records": rows}, (["STEREO"], [2]))
        self.assertEqual(names, ["STEREO", "SH", "SOFT", "CLIP"])
        self.assertEqual(flags, [2, 0, 0, 1])
        self.assertEqual(variants, [[], ["CLIP"], ["SOFT"], ["SOFT", "CLIP"], ["SH"], ["SH", "CLIP"], ["SH", "SOFT"], ["SH", "SOFT", "CLIP"]])

    def test_fog_keyword_registration_survives_no_fog_source_build(self):
        rows = [{"kind": "keywordsUserGlobal", "values": ["__ FOG_LINEAR FOG_EXP FOG_EXP2"]}] * 2
        names, flags = N.source_keyword_registration({"records": rows}, (["STEREO"], [2]))
        self.assertEqual(names, ["STEREO", "FOG_LINEAR", "FOG_EXP", "FOG_EXP2"])
        self.assertEqual(flags, [2, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "unsupported authored"):
            N.source_keyword_registration({"records": [{"kind": "keywordsUserGlobal", "values": ["__ UNMEASURED"]}]}, ([], []))

    def test_native_wrapper_state_uses_source_commands_and_parser_fog_defaults(self):
        original = N.render_state("Cull Off ZWrite Off ZTest Always", 2)
        original["stencilOpFront"]["comp"] = N.value(3)
        original["stencilOp"]["comp"] = N.value(6)
        original["fogMode"] = 99
        original["offsetFactor"] = N.value(9)
        cloud = N.native_state(original, 17, False)
        ui = N.native_state(original, 18, True)
        self.assertEqual(cloud["stencilOp"]["comp"]["val"], 3)
        self.assertEqual(ui["stencilOp"]["comp"]["val"], 6)
        self.assertEqual(cloud["gpuProgramID"], 17)
        self.assertEqual(cloud["offsetFactor"]["val"], 0)
        self.assertNotEqual(cloud["fogMode"], 99)

    def test_inline_blend_does_not_consume_following_state_commands(self):
        state = N.render_state("Blend [_Source] [_Destination] Cull [_Cull] ZTest [_Depth] ZWrite Off", 3)
        self.assertEqual(state["rtBlend0"]["srcBlend"], N.value(0, "_Source"))
        self.assertEqual(state["rtBlend0"]["destBlendAlpha"], N.value(0, "_Destination"))
        self.assertEqual(state["culling"], N.value(0, "_Cull"))
        self.assertEqual(state["zTest"], N.value(0, "_Depth"))
        self.assertEqual(state["zWrite"], N.value(0))

    def test_cloud_source_selects_original_directional_sh_soft_pairs(self):
        lab = str(Path(__file__).resolve().parents[1] / "scripts/lab")
        with patch.object(sys, "path", [lab, *sys.path]):
            M = importlib.import_module("shader_materials")
        state = N.render_state("", 0)
        state["m_Name"] = "FixturePass"
        tree = {"m_ParsedForm": {"m_SubShaders": [{"m_Tags": {"tags": []}, "m_Passes": [{"m_State": state}]}]}}
        calls = []

        class Emitter:
            def pair(self, context, pass_index, keys):
                calls.append((pass_index, sorted(keys)))
                return len(calls), 10 + len(calls)

            def block(self, context, pairs, pragmas):
                self.pairs = pairs
                return pragmas + "FIXTURE_PROGRAMS\n"

        emitter = Emitter()
        with patch.object(M, "properties", return_value="FIXTURE_PROPERTIES"), patch.object(M, "render_state", return_value="FIXTURE_STATE\n"):
            source = M.cloud_source((tree,), ["FEATURE"], "FixtureResource", emitter)
        self.assertEqual(
            calls,
            [
                (0, ["DIRECTIONAL", "FEATURE"]),
                (0, ["DIRECTIONAL", "FEATURE", "SOFTPARTICLES_ON"]),
                (0, ["DIRECTIONAL", "FEATURE", "LIGHTPROBE_SH"]),
                (0, ["DIRECTIONAL", "FEATURE", "LIGHTPROBE_SH", "SOFTPARTICLES_ON"]),
            ],
        )
        self.assertIn('Shader "Porting Lab/FixtureResource"', source)
        self.assertIn("#pragma multi_compile __ LIGHTPROBE_SH\n#pragma multi_compile_particles\n", source)
        self.assertEqual(emitter.pairs[0], ("!defined(LIGHTPROBE_SH) && !defined(SOFTPARTICLES_ON)", 1, 11))
        self.assertEqual(emitter.pairs[-1], ("defined(LIGHTPROBE_SH) && defined(SOFTPARTICLES_ON)", 4, 14))

    def test_public_spooky_v2_short_long_and_boundary_vectors(self):
        # Native public-domain SpookyV2 reference over this authored byte pattern.
        vectors = {
            0: "1909f56bfc062723c751e8b465ee728b",
            15: "151a91e7dcca270b1484e98c48fad8af",
            16: "e9f086d9abf124c255850c623af7d271",
            31: "d7d92d1bf0d72716a7ce5ec41a37bd11",
            32: "1ef4ea2af02ffbe1063d03c27ad59ea3",
            80: "842313a147aeac5beb262184785158a5",
            191: "2a08e15e573a6d2af5b7f91289d53f57",
            192: "fd62e4764fe607094ba7cb3680f162da",
            193: "49e5027175aff2697954cd7d7a9e498d",
            288: "4c4550efaba9a8cfb1af930a962be2dc",
            1000: "3df44a853909b188298cb2698862fb13",
        }
        for length, expected in vectors.items():
            with self.subTest(length=length):
                self.assertEqual(N.spooky(bytes((i * 37 + 11) % 256 for i in range(length))).hex(), expected)

    def test_default_constructor_uses_only_schema(self):
        def node(kind, children=(), name="fixture"):
            return SimpleNamespace(m_Type=kind, m_Children=children, m_Name=name)

        array = node("vector", [node("Array", [node("int", name="size"), node("float", name="data")])])
        schema = node("Fixture", [node("string", name="label"), node("bool", name="enabled"), node("int", name="count"), array])
        self.assertEqual(N.default(schema), {"label": "", "enabled": False, "count": 0, "fixture": []})
        self.assertIs(N.item(array), array.m_Children[0].m_Children[1])

    def test_source_render_state_and_fog_defaults(self):
        state = N.render_state("SubShader { Cull Off ZWrite Off ZTest Always Pass {} }", 87)
        self.assertEqual(state["gpuProgramID"], 87)
        self.assertEqual(state["zTest"], {"val": 8.0, "name": "<noninit>"})
        self.assertEqual(state["fogColor"]["name"], "unity_FogColor")
        self.assertEqual(state["rtBlend7"]["colMask"]["val"], 15)
        state["rtBlend0"]["colMask"]["val"] = 7
        self.assertEqual(state["rtBlend7"]["colMask"]["val"], 15)
        self.assertEqual(N.render_state("Cull Off ZWrite On ZTest Always", 1)["zWrite"]["val"], 1)
        with self.assertRaisesRegex(ValueError, "render state"):
            N.render_state("ZWrite Unsupported", 1)

    def test_implicit_state_and_property_bindings(self):
        state = N.render_state("SubShader { Pass {} }", 7)
        self.assertEqual([state[key]["val"] for key in ("culling", "zWrite", "zTest")], [2, 1, 4])
        state = N.render_state("Cull [_Side] Blend [_Source] [_Destination]\nPass {}", 7)
        self.assertEqual(state["culling"], {"val": 0.0, "name": "_Side"})
        self.assertEqual(state["rtBlend0"]["destBlendAlpha"]["name"], "_Destination")
        self.assertEqual(
            N.source_tags('Tags { "RenderType"="Opaque" "Queue"="Geometry" "Custom"="value" }'),
            [["Custom", "value"], ["QUEUE", "Geometry"], ["RenderType", "Opaque"]],
        )

    def test_sdk_capability_keywords_and_compilation_flags(self):
        pointers = struct.pack("<33Q", *range(33))

        def read(_image, address, _size):
            return pointers if address == 0x103C4F1B8 else ("fixture_" + str(address)).encode() + b"\0"

        bits = (1 << 6) | (1 << 17) | (1 << 32)
        with patch.object(N, "platform_caps", return_value=bits), patch.object(N, "sdk_read", side_effect=read):
            self.assertEqual(N.platform_keywords(b"", {}), ["fixture_6", "fixture_17", "fixture_32"])
            self.assertEqual(N.compilation_flags(b"", {}), (1 << 14) | (1 << 28) | (1 << 31))

    def test_source_blend_changes_only_first_render_target(self):
        state = N.render_state("Cull Off ZWrite Off ZTest LEqual Blend SrcAlpha One\nPass {}", 4)
        self.assertEqual(state["zTest"]["val"], 4)
        self.assertEqual(state["rtBlend0"]["srcBlendAlpha"]["val"], 5)
        self.assertEqual(state["rtBlend0"]["destBlend"]["val"], 1)
        self.assertEqual(state["rtBlend1"]["srcBlend"]["val"], 1)
        self.assertEqual(state["rtBlend1"]["destBlend"]["val"], 0)
        self.assertFalse(state["rtSeparateBlend"])
        with self.assertRaisesRegex(ValueError, "Blend"):
            N.render_state("Cull Off ZWrite Off ZTest LEqual Blend 2 One One", 4)
        self.assertEqual(N.render_state("Pass { Blend One Zero CGPROGRAM\nsource\nENDCG }", 4)["rtBlend0"]["destBlend"]["val"], 0)

    def test_named_grab_has_unbound_state_and_keeps_native_blend_defaults(self):
        def node(kind, name, children=()):
            return SimpleNamespace(m_Type=kind, m_Name=name, m_Children=children)

        array = node("vector", "m_EditorDataHash", [node("Array", "Array", [node("int", "size"), node("Hash128", "data")])])
        schema = node("SerializedPass", "data", [node("int", "m_Type"), node("string", "m_TextureName"), array])
        row = N.grab_pass(schema, "_FixtureSnapshot")
        self.assertEqual(row["m_TextureName"], "_FixtureSnapshot")
        self.assertEqual(row["m_Type"], 2)
        self.assertEqual(row["m_EditorDataHash"], [])
        state = row["m_State"]
        self.assertEqual(state["gpuProgramID"], -1)
        self.assertEqual(state["zClip"], {"val": 0, "name": "<noninit>"})
        self.assertEqual(state["stencilReadMask"]["val"], 0)
        self.assertEqual(state["fogColor"]["name"], "<noninit>")
        self.assertEqual(state["m_Tags"], {"tags": []})
        self.assertEqual(state["rtBlend7"]["srcBlend"]["val"], 1)
        self.assertEqual(N.source_tags('Tags { "IgnoreProjector"="True" "Queue"="Transparent" }'), [["IGNOREPROJECTOR", "true"], ["QUEUE", "Transparent"]])

    def test_properties_are_source_values_with_native_nontexture_defaults(self):
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
        source = """Properties {
          _Image ("Fixture mask", 2D) = "black" {}
          _Tint ("Fixture tint", Color) = (0.25,0.5,0.75,1)
          _Gain ("Fixture gain", Float) = -2.5
        } SubShader {}"""
        image, tint, gain = N.properties(prop, source)
        self.assertEqual(image["m_DefTexture"], {"m_DefaultName": "black", "m_TexDim": 2})
        self.assertEqual([tint[f"m_DefValue[{i}]"] for i in range(4)], [0.25, 0.5, 0.75, 1])
        self.assertEqual(gain["m_Type"], 2)
        self.assertEqual(gain["m_DefValue[0]"], -2.5)
        self.assertEqual(gain["m_DefValue[1]"], 0)
        self.assertEqual(gain["m_DefTexture"], {"m_DefaultName": "", "m_TexDim": 1})
        self.assertEqual(N.properties(prop, "SubShader {}"), [])
        ranged, vector = N.properties(
            prop, 'Properties { _Range ("Fixture range", Range(-2,3)) = 0.5 _Vector ("Fixture vector", Vector)=(1,2,3,4) } SubShader {}'
        )
        self.assertEqual(ranged["m_Type"], 3)
        self.assertEqual([ranged[f"m_DefValue[{i}]"] for i in range(4)], [0.5, -2, 3, 0])
        self.assertEqual(vector["m_Type"], 1)
        self.assertEqual(vector["m_DefValue[3]"], 4)
        normal = N.properties(prop, 'Properties { [Normal]_Detail ("Fixture normal",2D)="bump"{} } SubShader {}')[0]
        self.assertEqual(normal["m_Name"], "_Detail")
        self.assertEqual(normal["m_Flags"], 8)
        self.assertEqual(normal["m_DefTexture"], {"m_DefaultName": "bump", "m_TexDim": 2})
        cube = N.properties(prop, 'Properties { _Sky ("Fixture cube", Cube)="black"{} } SubShader {}')[0]
        self.assertEqual(cube["m_Type"], 4)
        self.assertEqual(cube["m_DefTexture"], {"m_DefaultName": "black", "m_TexDim": 4})
        with self.assertRaisesRegex(ValueError, "property declaration"):
            N.properties(prop, 'Properties { _Fixture ("Unsupported", Matrix) = 1 } SubShader {}')


if __name__ == "__main__":
    unittest.main()
