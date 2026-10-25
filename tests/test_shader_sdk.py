"""SDK source assembly contracts with authored metadata and compiler responses."""

from copy import deepcopy
import importlib.util
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from UnityPy.helpers.Tpk import get_typetree_node
from UnityPy.helpers.UnityVersion import UnityVersion

OWNER = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"
with patch.object(sys, "path", [str(OWNER), *sys.path]):
    SPEC = importlib.util.spec_from_file_location("shader_sdk_fixture", OWNER / "shader_sdk.py")
    S = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(S)


class Compiler:
    capabilities = []

    def __init__(self):
        self.calls = []

    def compile(self, code, path, **options):
        self.calls.append((code, path, options))
        cap = options["platform_keywords"][0]
        return {
            "success": True,
            "data": (cap + "|" + " ".join(options["keywords"])).encode(),
            "gpu_program_type": 25,
            "diagnostics": [],
            "reflection": ["cb: Fixture 16 1", f"const: gain {0 if cap == 'low' else 4} 0 0 1 1 0", "cbbind: Fixture 2"],
        }


class SDKSource(unittest.TestCase):
    def test_global_and_structured_constants_follow_sdk_scope_and_name_order(self):
        reflected = S.P.reflection(
            [
                "const: GlobalLimit 67108864 1 0 1 1 0",
                "texbind: image 3 4 0 2",
                "cb: Draws 160 1",
                "const: gain 128 0 0 1 1 0",
                "const: Instances 0 0 2 80 1 2",
                "const: Instances.transform 0 0 1 4 4 0",
                "const: Instances.tint 64 0 0 1 4 0",
                "cbbind: Draws 7",
            ]
        )
        self.assertEqual(len(reflected["buffers"][0]["constants"]), 1)
        structure = reflected["buffers"][0]["structures"][0]
        self.assertEqual((structure["offset"], structure["array"], structure["size"]), (0, 2, 80))
        self.assertEqual([row["name"] for row in structure["constants"]], ["transform", "tint"])
        table = S.P.common_parameters(reflected)
        self.assertEqual(dict(table["m_NameIndices"]), {"GlobalLimit": 0, "image": 1, "Draws": 2, "gain": 3, "Instances": 4, "tint": 5, "transform": 6})
        common = table["m_CommonParameters"]
        self.assertEqual(common["m_VectorParams"], [{"m_NameIndex": 0, "m_Index": 67108864, "m_ArraySize": 0, "m_Type": 1, "m_Dim": 1}])
        emitted = common["m_ConstantBuffers"][0]["m_StructParams"][0]
        self.assertEqual((emitted["m_Index"], emitted["m_ArraySize"], emitted["m_StructSize"]), (0, 2, 80))
        self.assertEqual(emitted["m_MatrixMembers"][0]["m_RowCount"], 4)
        self.assertEqual(emitted["m_VectorMembers"][0]["m_Dim"], 4)
        raw = S.P.native_parameters(reflected, {"constants": [], "buffers": [], "textures": [], "bindings": []})
        # The unnamed global buffer has zero byte size; this offset is a
        # runtime constant identifier, not an offset into that byte size.
        prefix = struct.pack("<5I", 202012090, 2, 0, 0, 1)
        self.assertTrue(raw.startswith(prefix + S.P.string("GlobalLimit") + struct.pack("<6I", 1, 1, 1, 0, 0, 67108864)))
        self.assertIn(S.P.string("Instances") + struct.pack("<4I", 0, 2, 80, 2), raw)
        self.assertLess(raw.index(S.P.string("tint")), raw.index(S.P.string("transform")))
        self.assertNotIn(b"Instances.transform", raw)

    def test_global_intersection_factors_only_constants_shared_by_all_variants(self):
        variants = []
        for keys, rows in (([], ["const: shared 1 1 0 1 1 0"]), (["FEATURE"], ["const: shared 1 1 0 1 1 0", "const: conditional 2 1 0 1 1 0"])):
            variants.append({"keywords": keys, "requirements": 33, "compilation": {"data": b"linked", "gpu_program_type": 25, "reflection": rows}})
        raw, table, _, parameters = S.P.variant_records(variants, ["FEATURE"])
        self.assertEqual(table["m_NameIndices"], [["shared", 0]])
        self.assertEqual(table["m_CommonParameters"]["m_VectorParams"][0]["m_Index"], 1)
        self.assertEqual(parameters, [0, 1])
        self.assertNotIn(S.P.string("shared"), raw)
        self.assertIn(S.P.string("conditional"), raw)

    def test_sdk_tier_intersection_keeps_conditional_global_native(self):
        source, node = self.fixture()
        original = Compiler.compile

        def compile_with_globals(compiler, code, path, **options):
            compiled = original(compiler, code, path, **options)
            globals = ["const: shared 1 1 0 1 1 0"]
            if "FEATURE" in options["keywords"]:
                globals.append("const: conditional 2 1 0 1 1 0")
            compiled["reflection"] = globals + compiled["reflection"]
            return compiled

        with tempfile.TemporaryDirectory() as tmp, patch.object(Compiler, "compile", compile_with_globals):
            (_, tree, raw), _, _ = self.assemble(source, node, {10: [[[], ["FEATURE"]], [[]], [[]]]}, Path(tmp))
        program = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["progVertex"]
        self.assertEqual(program["m_CommonParameters"]["m_VectorParams"], [{"m_NameIndex": 0, "m_Index": 1, "m_ArraySize": 0, "m_Type": 1, "m_Dim": 1}])
        self.assertNotIn(S.P.string("shared"), raw)
        self.assertIn(S.P.string("conditional"), raw)

    def test_structured_members_do_not_satisfy_declared_top_level_constant_count(self):
        with self.assertRaisesRegex(ValueError, "constant buffer count differs"):
            S.P.reflection(["cb: Draws 64 1", "const: Instances 0 0 2 64 1 1", "const: Instances.transform 0 0 1 4 4 0"])
        with self.assertRaisesRegex(ValueError, "undeclared"):
            S.P.reflection(["cb: Draws 64 0", "const: Missing.transform 0 0 1 4 4 0"])

    def test_sdk_loader_checks_acquired_input_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdk = Path(tmp).resolve()
            path = sdk / "Resources/unity_builtin_extra"
            path.parent.mkdir()
            path.write_bytes(b"authored resource fixture")
            with patch("UnityPy.load") as load:
                with self.assertRaisesRegex(ValueError, "differs"):
                    S.sdk_source(sdk, 46, "0" * 64)
                load.assert_not_called()
                shader = SimpleNamespace(type=SimpleNamespace(name="Shader"), path_id=46, read_typetree=lambda: {"authored": True})
                load.return_value = SimpleNamespace(objects=[shader])
                result = S.sdk_source(sdk, 46, hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(result, {"authored": True})

    def fixture(self, platform_mask=1 << 18):
        node = get_typetree_node(48, UnityVersion.from_str("2021.3.45f2"))
        source = S.P.default(node)
        form_node = S.P.child(node, "m_ParsedForm")
        sub_node = S.P.item(S.P.child(form_node, "m_SubShaders"))
        sub = S.P.default(sub_node)
        shader_pass = S.P.default(S.P.item(S.P.child(sub_node, "m_Passes")))
        shader_pass.update(m_State=S.P.render_state("", 10), m_ProgramMask=6, m_HasInstancingVariant=True)
        sub["m_Passes"] = [shader_pass]
        source["m_ParsedForm"].update(m_Name="Authored SDK fixture", m_SubShaders=[sub], m_KeywordNames=["INSTANCING_ON", "FEATURE"], m_KeywordFlags=[0, 1])
        source["m_CompileInfo"] = {
            "m_Snippets": [
                [
                    10,
                    {
                        "m_Code": "// Authored source fixture",
                        "m_AssetPath": "Assets/AuthoredFixture",
                        "m_PlatformMask": platform_mask,
                        "m_BaseRequirements": 33,
                        "m_KeywordTargetInfo": [{"keywordName": "FEATURE", "requirements": 2048}],
                        "m_IncludesHash": {f"bytes[{i}]": i + 128 for i in range(16)},
                    },
                ]
            ]
        }
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        for group in ("m_VariantsUserGlobal", "m_VariantsUserLocal", "m_VariantsBuiltin"):
            for stage in range(7):
                snippet[group + str(stage)] = []
        snippet["m_VariantsUserGlobal0"] = [["_", "INSTANCING_ON"]]
        snippet["m_VariantsUserLocal0"] = [["_", "FEATURE"]]
        return source, node

    def assemble(self, source, node, selections, output):
        connection = Compiler()
        hashes = []

        def identity(snippet, image, capabilities, settings, includes):
            hashes.append((snippet, settings))
            return bytes(range(16))

        with (
            patch.object(S.P, "platform_keywords", side_effect=lambda image, settings: [settings["cap"]]),
            patch.object(S.P, "compilation_flags", return_value=0),
            patch.object(S.P, "editor_hash", side_effect=identity),
        ):
            result = S.compile_body(
                connection, source, node, selections, [{"cap": cap} for cap in ("low", "medium", "medium")], b"", b"", lambda raw, method: b"compressed", output
            )
        return result, connection, hashes

    def test_tier_capabilities_requirements_and_shader_wide_dedup(self):
        source, node = self.fixture()
        unchanged = deepcopy(source)
        with tempfile.TemporaryDirectory() as tmp:
            (body, tree, raw), compiler, hashes = self.assemble(source, node, {10: [[[], ["FEATURE"]], [[]], [[]]]}, Path(tmp))
            self.assertEqual((Path(tmp) / "body.bin").read_bytes(), body)
        self.assertEqual(source, unchanged)
        self.assertEqual(len(compiler.calls), 3)  # Identical source tiers 1/2 share a fresh compile.
        self.assertEqual([call[2]["requirements"] for call in compiler.calls], [33, 2081, 33])
        self.assertEqual([call[2]["platform_keywords"] for call in compiler.calls], [["low"], ["low"], ["medium"]])
        shader_pass = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]
        program = shader_pass["progVertex"]
        self.assertEqual(list(map(len, program["m_PlayerSubPrograms"])), [2, 1, 1, 0])
        self.assertEqual(program["m_PlayerSubPrograms"][1], program["m_PlayerSubPrograms"][2])
        self.assertEqual([row["m_BlobIndex"] for row in program["m_PlayerSubPrograms"][0]], [2, 4])
        self.assertEqual([row["m_BlobIndex"] for row in program["m_PlayerSubPrograms"][1]], [3])
        self.assertEqual(program["m_CommonParameters"]["m_ConstantBuffers"], [])
        self.assertEqual(struct.unpack_from("<I", raw)[0], 5)
        self.assertTrue(shader_pass["m_HasInstancingVariant"])  # Source declaration survives program stripping.
        self.assertEqual(hashes[0][0]["fields"][6:], list(struct.unpack("<4i", bytes(range(128, 144)))))
        self.assertEqual(hashes[0][1], {"cap": "low"})

    def test_source_platform_mask_keeps_metadata_without_compiling_unsupported_pass(self):
        source, node = self.fixture(platform_mask=1 << 4)
        with tempfile.TemporaryDirectory() as tmp:
            (_, tree, raw), compiler, _ = self.assemble(source, node, {}, Path(tmp))
        self.assertEqual(compiler.calls, [])
        self.assertEqual(tree["stageCounts"], [1])
        shader_pass = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]
        self.assertEqual(shader_pass["progVertex"]["m_PlayerSubPrograms"], [[], [], [], []])
        self.assertEqual(shader_pass["m_NameIndices"], [])
        self.assertEqual(shader_pass["m_Platforms"], [18])
        self.assertEqual(raw, S.P.words(0))
        self.assertTrue(shader_pass["m_HasInstancingVariant"])

    def test_asymmetric_tier_subsets_intern_in_source_row_order(self):
        source, node = self.fixture()
        source["m_ParsedForm"]["m_KeywordNames"] = ["A", "B", "C"]
        source["m_ParsedForm"]["m_KeywordFlags"] = [1, 1, 1]
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        snippet["m_VariantsUserGlobal0"] = []
        snippet["m_VariantsUserLocal0"] = [["A", "B", "C"]]
        with tempfile.TemporaryDirectory() as tmp:
            (_, tree, raw), _, _ = self.assemble(source, node, {10: [[["B"], ["C"]], [["A"], ["B"]], [["A"], ["B"]]]}, Path(tmp))
        program = tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["progVertex"]
        self.assertEqual([[row["m_BlobIndex"] for row in tier] for tier in program["m_PlayerSubPrograms"]], [[3, 5], [2, 4], [2, 4], []])
        self.assertEqual(program["m_ParameterBlobIndices"], [[1, 1], [0, 0], [0, 0], []])
        self.assertEqual(struct.unpack_from("<I", raw)[0], 6)

    def test_linked_source_axes_include_fragment_only_declarations(self):
        source, _ = self.fixture()
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        snippet["m_VariantsUserGlobal0"] = [["_", "FOG"]]
        snippet["m_VariantsUserGlobal1"] = [["_", "EMISSION"], ["_", "FOG"]]
        snippet["m_VariantsUserLocal0"] = []
        snippet["m_VariantsBuiltin0"] = [["DIRECTIONAL"], ["POINT"]]
        rows = [["DIRECTIONAL"], ["POINT"], ["EMISSION", "DIRECTIONAL"], ["EMISSION", "POINT"]]
        self.assertEqual(S.source_ranks(snippet, rows), {frozenset(keys): rank for rank, keys in enumerate(rows)})

    def test_selected_ranks_do_not_expand_large_source_cartesian_product(self):
        source, _ = self.fixture()
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        snippet["m_VariantsUserGlobal0"] = [["_", f"FEATURE{i}"] for i in range(40)]
        snippet["m_VariantsUserLocal0"] = []
        snippet["m_VariantsBuiltin0"] = [["__"], ["BUILTIN"]]
        rows = [[], ["FEATURE0"], ["FEATURE39", "BUILTIN"]]
        self.assertEqual(S.source_ranks(snippet, rows), {frozenset(): 0, frozenset(["FEATURE0"]): 1 << 40, frozenset(["FEATURE39", "BUILTIN"]): 3})

    def test_overlapping_axis_keywords_use_earliest_source_row(self):
        source, _ = self.fixture()
        snippet = source["m_CompileInfo"]["m_Snippets"][0][1]
        snippet["m_VariantsUserGlobal0"] = [["_", "A"], ["A", "B"]]
        snippet["m_VariantsUserLocal0"] = []
        self.assertEqual(S.source_ranks(snippet, [["A"], ["A", "B"]]), {frozenset(["A"]): 0, frozenset(["A", "B"]): 3})

    def test_unknown_source_row_is_rejected(self):
        source, node = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "not declared"):
                self.assemble(source, node, {10: [[["UNKNOWN"]], [], []]}, Path(tmp))

    def test_caller_can_explicitly_strip_executables_without_erasing_source_pass(self):
        source, node = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            (_, tree, _), compiler, _ = self.assemble(source, node, {10: [[], [], []]}, Path(tmp))
        self.assertEqual(compiler.calls, [])
        self.assertEqual(tree["stageCounts"], [1])
        self.assertEqual(len(tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"]), 1)
        self.assertTrue(tree["m_ParsedForm"]["m_SubShaders"][0]["m_Passes"][0]["m_HasInstancingVariant"])

    def test_unqualified_backend_is_rejected_before_compiler_use(self):
        source, node = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Vulkan18"):
                S.compile_body(Compiler(), source, node, {}, [{}, {}, {}], b"", b"", None, tmp, platform=4)


if __name__ == "__main__":
    unittest.main()
