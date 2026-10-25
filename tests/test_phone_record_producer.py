"""Authored AnimationClip source transformations and persisted pack contracts."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


A = load("animation_producer", ROOT / "tools/phone-build/accepted-output/record_produce.py")
F = load("animation_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def fixture():
    u32 = lambda name: F.node(name, 4, kind="UInt32")
    floats = F.array("original", F.node("data", 4, kind="float"))
    schema = F.node(
        "Base",
        children=[
            u32("m_MuscleClipSize"),
            floats,
            F.node(
                "m_MuscleClip",
                children=[
                    F.array("m_ValueArrayReferencePose", F.node("data", 4, kind="float")),
                    F.node(
                        "m_Clip",
                        children=[
                            F.node(
                                "data",
                                children=[
                                    F.node("m_StreamedClip", children=[F.array("data", u32("data")), u32("curveCount")]),
                                    F.node("m_DenseClip", children=[u32("m_CurveCount")]),
                                    F.node("m_ConstantClip", children=[F.array("data", F.node("data", 4, kind="float"))]),
                                ],
                            )
                        ],
                    ),
                ],
            ),
            F.node("script", 12, kind="PPtr<MonoScript>"),
            F.node("genericBindings", children=[u32("attribute")]),
        ],
    )
    # Two frames with one unchanged constant curve, including negative zero.
    words = [0x80000000, 1, 0, 0, 0, 0, 0x40800000, 0x7F800000, 1, 0, 0, 0, 0, 0x40800000]
    body = struct.pack("<I", 900) + F.vector(struct.pack("<III", 0x80000000, 0x7FA00001, 0x3F800000), 3)
    body += F.vector(struct.pack("<ff", 2, 3), 2) + F.vector(struct.pack("<" + "I" * len(words), *words), len(words))
    body += struct.pack("<IIIiqI", 1, 0, 0, 3, 1234567, 0x11223344)
    return body, schema


def serialized(body, schema, class_id=74):
    strings, nodes = bytearray(), []

    def label(value):
        if value in ("data", "float"):
            return 0x80000000 | {"data": 106, "float": 161}[value]
        offset = len(strings)
        strings.extend(value.encode() + b"\0")
        return offset

    def visit(node, level):
        nodes.append(struct.pack("<HBBIIiiiQ", 1, level, node.flags, label(node.kind), label(node.name), node.size, len(nodes), node.meta, 0))
        for child in node.children:
            visit(child, level + 1)

    visit(schema, 0)
    tree = struct.pack("<II", len(nodes), len(strings)) + b"".join(nodes) + strings
    typ = {"class_id": class_id, "stripped": 0, "script_type": -1, "hash": bytes(16), "tree": tree, "dependencies": []}
    if class_id == 114:
        typ["script_id"] = bytes(range(16))
    layout = {
        "engine": "2021.3.45f2",
        "platform": 19,
        "trees": True,
        "types": [typ],
        "objects": [{"path_id": 77, "offset": 0, "bytes": len(body), "type_id": 0}],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    output = io.BytesIO()
    A.W.write_serialized(output, layout, lambda row: io.BytesIO(body))
    return output.getvalue()


def layout_fixture():
    def integer(name):
        return F.node(name, 4, kind="UInt32")

    def words(name):
        return F.array(name, integer("data"))

    binding = F.node("data", children=[integer("path"), integer("attribute"), integer("typeID")])
    delta = F.node("data", children=[integer("m_Start"), integer("m_Stop")])
    schema = F.node(
        "Base",
        children=[
            integer("m_MuscleClipSize"),
            F.node(
                "m_MuscleClip",
                children=[
                    F.node(
                        "m_Clip",
                        children=[
                            F.node(
                                "data",
                                children=[
                                    F.node("m_StreamedClip", children=[words("data"), integer("curveCount")]),
                                    F.node(
                                        "m_DenseClip",
                                        children=[
                                            integer("m_FrameCount"),
                                            integer("m_CurveCount"),
                                            integer("m_SampleRate"),
                                            integer("m_BeginTime"),
                                            words("m_SampleArray"),
                                        ],
                                    ),
                                    F.node("m_ConstantClip", children=[words("data")]),
                                ],
                            )
                        ],
                    ),
                    F.array("m_ValueArrayDelta", delta),
                    words("m_IndexArray"),
                ],
            ),
            F.node("m_ClipBindingConstant", children=[F.array("genericBindings", binding)]),
        ],
    )

    def word(value):
        return struct.unpack("<I", struct.pack("<f", value))[0]

    def pack(values):
        return struct.pack("<I" + "I" * len(values), len(values), *values)

    stream = [0xFF800000, 0, 0, 2, 0, 0, 0, 0, word(10), 1, 0, 0, 0, word(20), 0x3F800000, 2, 0, 0, 0, 0, word(11), 1, 0, 0, 0, word(20.001), 0x7F800000, 0]
    body = struct.pack("<I", 1000) + pack(stream) + struct.pack("<IIIII", 2, 3, 1, word(30), 0)
    body += pack([0x80000000, 0, word(42)]) + pack([word(40)])
    body += struct.pack("<I8f", 4, 10, 11, 20, 20.001, -0.0, 42, 40, 40)
    body += pack([0xFFFFFFFF, 0, 1, 2, 3])
    body += struct.pack("<I", 4) + b"".join(struct.pack("<III", i + 100, i + 7, 137) for i in range(4))
    return body, schema


class AnimationProducerTests(unittest.TestCase):
    def test_binding_reorder_sorts_complete_source_keys_by_the_new_curve_index(self):
        body, schema = layout_fixture()
        result = A.layout_clip(body, schema, {"binding_order": [1, 0, 2, 3], "fold_bindings": [], "dense_policy": "preserve"})
        _, spans = A.fields(result, schema)
        start, end = spans[("m_MuscleClip", "m_Clip", "data", "m_StreamedClip", "data")]
        words = list(struct.unpack_from("<" + "I" * ((end - start - 4) // 4), result, start + 4))
        self.assertEqual(words[:4], [0xFF800000, 0, 0, 2])
        self.assertEqual(words[4:14], [0, 0, 0, 0, 0x41A00000, 1, 0, 0, 0, 0x41200000])
        self.assertEqual(struct.unpack_from("<I", result)[0], 1000)
        start, end = spans[("m_MuscleClip", "m_IndexArray")]
        self.assertEqual(result[start:end], struct.pack("<I5i", 5, -1, 1, 0, 2, 3))

    def test_root_quaternion_uses_original_delta_endpoints_and_preserves_signed_zero(self):
        quaternion = lambda: F.node("q", children=[F.node(name, 4, kind="float") for name in ("x", "y", "z", "w")])
        schema = F.node(
            "Base",
            children=[
                F.node(
                    "m_MuscleClip",
                    children=[
                        F.node("m_StartX", children=[quaternion()]),
                        F.node("m_StopX", children=[quaternion()]),
                        F.array("m_IndexArray", F.node("data", 4)),
                        F.array("m_ValueArrayDelta", F.node("data", children=[F.node("start", 4, kind="float"), F.node("stop", 4, kind="float")])),
                    ],
                )
            ],
        )
        indices = [-1] * 10 + [0, 1, 2, 3]
        delta = struct.pack("<I8f", 4, 0, -0.0, 1, 0, 0, 0, 1, 1)
        body = bytes(32) + struct.pack("<I14i", 14, *indices) + delta
        result = A.transform(body, schema, {"normalize_root_quaternions": True})
        self.assertEqual(result[:16], struct.pack("<IIII", 0, 0x3F3504F3, 0, 0x3F3504F3))
        self.assertEqual(result[16:32], struct.pack("<4f", -0.0, 0, 0, 1))
        self.assertEqual(result[32:], body[32:])
        defaults = bytes(32) + struct.pack("<I14iI", 14, *([-1] * 14), 0)
        self.assertEqual(A.transform(defaults, schema, {"normalize_root_quaternions": True})[:32], struct.pack("<8f", 0, 0, 0, 1, 0, 0, 0, 1))
        invalid = body[:32] + struct.pack("<I14i", 14, *([-1] * 13 + [4])) + delta
        with self.assertRaisesRegex(ValueError, "source index"):
            A.transform(invalid, schema, {"normalize_root_quaternions": True})
        with self.assertRaisesRegex(ValueError, "quaternion magnitude"):
            A.transform(body[:-32] + bytes(32), schema, {"normalize_root_quaternions": True})

    def test_layout_folds_source_values_reorders_bindings_and_repeats_dense_endpoint(self):
        body, schema = layout_fixture()
        selected = {"binding_order": [0, 2, 1, 3], "fold_bindings": [1], "dense_policy": "interior-zero"}
        result = A.layout_clip(body, schema, selected)
        _, spans = A.fields(result, schema)

        def field(path):
            start, end = spans[tuple(path.split("/"))]
            return result[start:end]

        cp = "m_MuscleClip/m_Clip/data/"
        self.assertEqual(field(cp + "m_StreamedClip/curveCount"), struct.pack("<I", 1))
        self.assertEqual(field(cp + "m_DenseClip/m_FrameCount"), struct.pack("<I", 4))
        self.assertEqual(field(cp + "m_DenseClip/m_SampleArray"), struct.pack("<I4f", 4, 0, 0, 42, 42))
        self.assertEqual(field(cp + "m_ConstantClip/data"), struct.pack("<I2f", 2, 20, 40))
        self.assertEqual(field("m_MuscleClip/m_ValueArrayDelta"), struct.pack("<I8f", 4, 10, 11, 0, 42, 20, 20, 40, 40))
        self.assertEqual(
            field("m_ClipBindingConstant/genericBindings"), struct.pack("<I", 4) + b"".join(struct.pack("<III", i + 100, i + 7, 137) for i in [0, 2, 1, 3])
        )
        self.assertEqual(field("m_MuscleClip/m_IndexArray"), struct.pack("<I5i", 5, -1, 0, 2, 1, 3))
        self.assertEqual(struct.unpack_from("<I", result)[0], 1000 + len(result) - len(body))
        preserved = A.layout_clip(body, schema, selected | {"dense_policy": "append"})
        _, preserved_spans = A.fields(preserved, schema)
        delta_start, _ = preserved_spans[("m_MuscleClip", "m_ValueArrayDelta")]
        self.assertEqual(struct.unpack_from("<I", preserved, delta_start + 12)[0], 0x80000000)
        for mutation in ({"binding_order": [0, 2, 1, 1]}, {"binding_order": [False, 2, 1, 3]}, {"fold_bindings": [3]}, {"dense_policy": "guess"}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                A.layout_clip(body, schema, selected | mutation)

    def test_native_coefficients_match_authored_endpoint_and_tangent_contract(self):
        def word(value):
            return struct.unpack("<I", struct.pack("<f", value))[0]

        # Source f(t)=2t^3+3t^2+4t+5 supplies derivative16 at t=1.
        # A next value16 requires -2t^3+9t^2+4t+5 with the same tangents.
        words = [word(-float("inf")), 0, word(0), 1, 0, word(2), word(3), word(4), word(5), word(1), 1, 0, 0, 0, 0, word(16), word(float("inf")), 0]
        data = struct.pack("<I" + "I" * len(words), len(words), *words)
        result = A.native_stream(data)
        made = list(struct.unpack_from("<" + "I" * len(words), result, 4))
        self.assertEqual(made[5:9], [word(-2), word(9), word(4), word(5)])
        self.assertEqual(made[:5], words[:5])
        self.assertEqual(made[9:], words[9:])
        for broken in (b"", data[:-1], struct.pack("<III", 2, word(0), 1)):
            with self.subTest(size=len(broken)), self.assertRaises(ValueError):
                A.native_stream(broken)

    def test_native_stream_preserves_regular_negative_zero_and_defaults_flat_slope(self):
        words = [0xFF800000, 0, 0, 1, 0, 0x3F800000, 0, 0x80000000, 0, 0x3F800000, 1, 0, 0, 0, 0, 0x3F800000, 0x7F800000, 0]
        data = struct.pack("<I" + "I" * len(words), len(words), *words)
        result = A.native_stream(data)
        self.assertEqual(struct.unpack_from("<I", result, 4 + 7 * 4)[0], 0x80000000)
        words[5], words[15] = 0, 0
        data = struct.pack("<I" + "I" * len(words), len(words), *words)
        self.assertEqual(struct.unpack_from("<I", A.native_stream(data), 4 + 7 * 4)[0], 0)

    def test_native_rounding_preserves_repeated_subtraction_order(self):
        # Authored quarter-second interval. Algebraically combining the two d0
        # subtractions changes b to 0xb5800000; native packing yields 0xb5400000.
        words = [0xFF800000, 0, 0, 1, 0, 0, 0xB4C00000, 0x3F800001, 0, 0x3E800000, 1, 0, 0, 0, 0, 0x3E800000, 0x7F800000, 0]
        data = struct.pack("<I" + "I" * len(words), len(words), *words)
        self.assertEqual(struct.unpack_from("<III", A.native_stream(data), 4 + 5 * 4), (0, 0xB5400000, 0x3F800001))

    def test_canonicalization_is_typed_and_preserves_size_and_other_bits(self):
        body, schema = fixture()
        canonical, _ = A.fields(body, schema, "zero-and-nan")
        self.assertEqual(struct.unpack_from("<III", canonical, 8), (0, 0x7FC00000, 0x3F800000))
        self.assertEqual(canonical[20:], body[20:])
        result = A.transform(body, schema, {"clear_reference_pose": True})
        self.assertEqual(struct.unpack_from("<I", result)[0], 900)
        self.assertEqual(result, body[:20] + bytes(4) + body[32:])
        nan, _ = A.fields(body, schema, "nan")
        self.assertEqual(struct.unpack_from("<II", nan, 8), (0x80000000, 0x7FC00000))

    def test_constant_folding_uses_source_values_and_rejects_nonconstant(self):
        body, schema = fixture()
        _, spans = A.fields(body, schema)
        result = A.transform(body, schema, {"fold_constants": True, "canonical": "zero-and-nan", "canonical_stream": True})
        _, after = A.fields(result, schema)
        start, end = after[("m_MuscleClip", "m_Clip", "data", "m_ConstantClip", "data")]
        self.assertEqual(result[start:end], struct.pack("<If", 1, 4))
        self.assertEqual(struct.unpack_from("<I", result)[0], 900 + len(result) - len(body))
        stream = ("m_MuscleClip", "m_Clip", "data", "m_StreamedClip", "data")
        start, end = spans[stream]
        for data in (body[start : end - 4], struct.pack("<III", 2, 0, 1)):
            with self.assertRaises(ValueError):
                A.streamed(data, fold=True)
        damaged = bytearray(body)
        struct.pack_into("<f", damaged, start + 16, 2)
        with self.assertRaisesRegex(ValueError, "nonconstant"):
            A.transform(damaged, schema, {"fold_constants": True})

    def test_checked_references_and_binding_policy_preserve_other_bytes(self):
        body, schema = fixture()
        selected = {"references": [{"offset": len(body) - 16, "from": [3, 1234567], "to": [8, -99]}], "binding_attributes": [len(body) - 4]}
        result = A.transform(body, schema, selected)
        self.assertEqual(result[:-16], body[:-16])
        self.assertEqual(struct.unpack_from("<iqI", result, len(body) - 16), (8, -99, 0x81223344))
        selected["references"][0]["from"][0] = 2
        with self.assertRaisesRegex(ValueError, "PPtr identity drift"):
            A.transform(body, schema, selected)
        for selected in ({"canonical": "guess"}, {"replace_bytes": []}, {"binding_attributes": [0]}):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                A.transform(body, schema, selected)

    def test_generic_packs_retain_all_nonpointer_bytes(self):
        body, schema = fixture()
        expected = body[:-16] + struct.pack("<iq", 7, -999) + body[-4:]
        for class_id in (1, 4, 23, 65, 91, 104, 114, 135, 136, 198, 199, 205, 215, 224):
            transform = {"references": [{"offset": len(body) - 16, "from": [3, 1234567], "to": [7, -999]}]}
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc = root / "pc"
                pc.mkdir()
                source = pc / "authored.bundle"
                source.write_bytes(F.bundle([("CAB-authored", serialized(body, schema, class_id), 4)]))
                target = {
                    "bundle": "authored-target",
                    "member": "CAB-target",
                    "path_id": -88,
                    "bytes": len(expected),
                    "sha256": hashlib.sha256(expected).hexdigest(),
                    "transform": transform,
                }
                selected = {"path_id": 77, "class_id": class_id, "sha256": hashlib.sha256(body).hexdigest(), "outputs": [target]}
                profile = {
                    "input_id": A.M.INPUT_ID,
                    "bundles": [{"path": source.name, "sha256": A.B.sha(source), "members": [{"name": "CAB-authored", "objects": [selected]}]}],
                }
                path = root / "profile.json"
                path.write_text(json.dumps(profile))
                self.assertTrue(A.produce(path, A.B.sha(path), pc, root / "output")["success"])
                self.assertEqual((root / "output/objects.bin").read_bytes(), expected)
                selected["class_id"] = 74
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, "object class"):
                    A.produce(path, A.B.sha(path), pc, root / "class-drift")
                selected["class_id"] = class_id
                transform["fold_constants"] = True
                path.write_text(json.dumps(profile))
                with self.assertRaisesRegex(ValueError, "generic object operation"):
                    A.produce(path, A.B.sha(path), pc, root / "operation-drift")

    def test_generic_material_policy_relocates_before_demoting_original_keywords(self):
        prefix = struct.pack("<I", 4) + b"Demo" + struct.pack("<iq", 2, 77)
        keyword = struct.pack("<I", 3) + b"ONE\0"
        suffix = bytes(range(64))
        body = prefix + struct.pack("<I", 1) + keyword + bytes(4) + suffix
        selected = {"references": [{"offset": 8, "from": [2, 77], "to": [9, -77]}], "demote_keywords": True}
        expected = prefix[:8] + struct.pack("<iqII", 9, -77, 0, 1) + keyword + suffix
        self.assertEqual(A.transform_generic(body, 21, selected), expected)
        self.assertEqual(A.transform_generic(expected, 21, {"demote_keywords": True}), expected)
        with self.assertRaisesRegex(ValueError, "generic object operation"):
            A.transform_generic(body, 91, selected)

    def test_source_pack_persistence_and_input_output_drift(self):
        body, schema = fixture()
        transform = {"clear_reference_pose": True, "canonical": "nan"}
        expected = A.transform(body, schema, transform)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(F.bundle([("CAB-authored", serialized(body, schema), 4)]))
            target = {
                "bundle": "authored-target",
                "member": "CAB-target",
                "path_id": -88,
                "bytes": len(expected),
                "sha256": hashlib.sha256(expected).hexdigest(),
                "transform": transform,
            }
            profile = {
                "input_id": A.M.INPUT_ID,
                "bundles": [
                    {
                        "path": source.name,
                        "sha256": A.B.sha(source),
                        "members": [
                            {
                                "name": "CAB-authored",
                                "objects": [{"path_id": 77, "class_id": 74, "sha256": hashlib.sha256(body).hexdigest(), "outputs": [target]}],
                            }
                        ],
                    }
                ],
            }
            path = root / "profile.json"
            path.write_text(json.dumps(profile))
            receipt = A.produce(path, A.B.sha(path), pc, root / "output")
            self.assertTrue(receipt["success"])
            self.assertEqual(receipt["objects"], 1)
            self.assertEqual((root / "output/objects.bin").read_bytes(), expected)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                A.produce(path, A.B.sha(path), pc, root / "output")
            with self.assertRaisesRegex(ValueError, "profile drift"):
                A.produce(path, "0" * 64, pc, root / "bad-profile")
            source.write_bytes(b"drift")
            with self.assertRaisesRegex(ValueError, "bundle drift"):
                A.produce(path, A.B.sha(path), pc, root / "bad-input")
            self.assertFalse(json.loads((root / "bad-input/result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
