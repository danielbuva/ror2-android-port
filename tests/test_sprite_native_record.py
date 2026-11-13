"""Authored Sprite stream allocation and source-preservation contract."""

import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load("sprite_native_record", ROOT / "tools/phone-build/accepted-output/sprite_native_record.py")
F = load("sprite_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def fixture():
    node, array = F.node, F.array
    submesh = node("data", children=[node("indexCount", 4), node("vertexCount", 4), node("untouched_bounds", 40)])
    point = node("data", 8)
    root = node(
        "Base",
        children=[
            F.text("m_Name"),
            node("m_Rect", 16),
            node("m_Offset", 8),
            node("m_Border", 16),
            node("m_PixelsToUnits", 4),
            node("m_Pivot", 8),
            node("m_Extrude", 4),
            node("flags", 4),
            node("key", 24),
            node("atlas", 16),
            node(
                "m_RD",
                children=[
                    node("texture", 12),
                    node("alpha", 12),
                    array("m_SubMeshes", submesh),
                    array("m_IndexBuffer", node("data", 1)),
                    node("m_VertexData", children=[node("m_VertexCount", 4), array("m_Channels", node("data", 4)), array("m_DataSize", node("data", 1))]),
                    node("textureRect", 16),
                    node("textureRectOffset", 8),
                    node("uvTransform", 16),
                ],
            ),
            array("m_PhysicsShape", array("data", point)),
            node("tail", 8),
        ],
    )
    channels = bytes([0, 0, 0, 3, 1, 0, 0, 2])
    body = F.vector(b"test", 4) + struct.pack("<4f2f4ff2fII", 0, 0, 16, 8, 0, 0, 0, 0, 0, 0, 2, 0.5, 0.5, 1, 7)
    body += bytes(40) + struct.pack("<iq", 2, 1234) + bytes(12)
    body += F.vector(struct.pack("<II", 6, 4) + b"B" * 40, 1) + F.vector(bytes(12), 12)
    body += struct.pack("<I", 4) + F.vector(channels, 2) + F.vector(bytes(80), 80)
    body += struct.pack("<4f2f4f", 0, 0, 16, 8, 0, 0, 2, 8, 2, 4) + struct.pack("<I", 0) + b"tailkeep"
    bit = lambda value: struct.unpack("<i", struct.pack("<f", value))[0]
    native = {
        "rect_bits": list(map(bit, [0, 0, 16, 8])),
        "border_bits": [0] * 4,
        "texture_rect_bits": list(map(bit, [0, 0, 16, 8])),
        "texture_offset_bits": [0, 0],
        "pivot_pixel_bits": list(map(bit, [8, 4])),
        "vertex_xy_bits": list(map(bit, [-1, 1, 1, 1, 1, -1, -1, -1, -0.0, 0])),
        "triangles": [0, 1, 4, 1, 2, 4, 2, 3, 4],
        "physics": [{"xy_bits": list(map(bit, [-1, 1, 1, 1, 1, -1]))}, {"xy_bits": list(map(bit, [-0.0, 0, 0, 1, 1, 0]))}],
    }
    return body, root, native


class SpriteNativeRecordTests(unittest.TestCase):
    def test_source_importer_parameters_are_used_for_header_and_native_geometry(self):
        body, root, native = fixture()
        parameters = S.source_parameters(body, root)
        parameters["pivot"] = [0.25, 0.75]
        native["pivot_pixel_bits"] = [struct.unpack("<i", struct.pack("<f", value))[0] for value in (4, 6)]
        made = S.assemble(body, root, native, "1" * 32, parameters=parameters)
        _, spans = S.A.fields(made, root)
        self.assertEqual(struct.unpack_from("<2f", made, spans[("m_Pivot",)][0]), (0.25, 0.75))
        self.assertEqual(struct.unpack_from("<2f", made, spans[("m_Offset",)][0]), (-4, 2))

    def test_offset_uses_native_pixel_pivot_before_center_subtraction(self):
        body, root, native = fixture()
        bit = lambda value: struct.unpack("<i", struct.pack("<f", value))[0]
        native["rect_bits"] = list(map(bit, (0, 0, 1000, 1000)))
        native["pivot_pixel_bits"] = list(map(bit, (499.9999694824219, 500)))
        parameters = S.source_parameters(body, root)
        parameters["pivot"] = [0.4999999701976776, 0.5]
        made = S.assemble(body, root, native, "1" * 32, parameters=parameters)
        _, spans = S.A.fields(made, root)
        self.assertEqual(struct.unpack_from("<2f", made, spans[("m_Offset",)][0]), (-0.000030517578125, 0))

    def test_uv_pivot_recomposes_the_rounded_offset(self):
        body, root, native = fixture()
        bit = lambda value: struct.unpack("<i", struct.pack("<f", value))[0]
        native["rect_bits"] = list(map(bit, (0, 0, 128, 128)))
        pixel = S.f32(S.f32(0.03) * 128)
        native["pivot_pixel_bits"] = list(map(bit, (pixel, 64)))
        parameters = S.source_parameters(body, root)
        parameters["pivot"] = [S.f32(0.03), 0.5]
        made = S.assemble(body, root, native, "1" * 32, parameters=parameters)
        _, spans = S.A.fields(made, root)
        uv = struct.unpack_from("<4f", made, spans[("m_RD", "uvTransform")][0])
        self.assertEqual(uv[1], S.f32(S.f32(pixel - 64) + 64))
        self.assertNotEqual(uv[1], pixel)

    def test_record_pack_original_sprite_crop_preserves_native_geometry(self):
        body, root, _ = fixture()
        _, spans = S.A.fields(body, root)
        original = bytearray(body)
        crop_offset = spans[("m_RD", "textureRect")][0]
        struct.pack_into("<4f", original, crop_offset, 2.25, 3.5, 8, 4)
        struct.pack_into("<2f", original, spans[("m_RD", "textureRectOffset")][0], 2, 1)
        pointer = spans[("m_RD", "texture")][0]
        selected = {"importer_guid": "1" * 32, "crop_rectangle_offset": crop_offset, "references": [{"offset": pointer, "from": [2, 1234], "to": [0, 99]}]}
        result = S.A.transform_generic(bytes(original), 213, selected)
        field = lambda data, path: data[slice(*spans[path])]
        self.assertEqual(field(result, ("m_Rect",)), struct.pack("<4f", 2.25, 3.5, 8, 4))
        self.assertEqual(field(result, ("m_Pivot",)), struct.pack("<2f", 0.75, 0.75))
        self.assertEqual(field(result, ("m_Offset",)), struct.pack("<2f", 2, 1))
        self.assertEqual(field(result, ("m_RD", "textureRectOffset")), bytes(8))
        self.assertEqual(field(result, ("m_RD", "texture")), struct.pack("<iq", 0, 99))
        self.assertEqual(field(result, ("key",)), bytes([0x11]) * 16 + struct.pack("<q", 21300000))
        for path in (("m_RD", "m_VertexData"), ("m_RD", "m_IndexBuffer"), ("m_PhysicsShape",), ("tail",)):
            self.assertEqual(field(result, path), field(original, path))

    def test_original_crop_recovers_asymmetric_standalone_border(self):
        body, root, _ = fixture()
        _, spans = S.A.fields(body, root)
        changed = bytearray(body)
        struct.pack_into("<4f", changed, spans[("m_Border",)][0], 4, 4, 4, 4)
        struct.pack_into("<4f", changed, spans[("m_RD", "textureRect")][0], 0, 0, 10, 6)
        struct.pack_into("<2f", changed, spans[("m_RD", "textureRectOffset")][0], 1, 0.5)
        parameters = S.source_parameters(bytes(changed), root)
        self.assertEqual(parameters["border"], [3, 3.5, -1, 2.5])

    def test_native_mesh_allocation_and_untouched_source_bytes(self):
        body, root, native = fixture()
        result = S.assemble(body, root, native, "1" * 32)
        _, spans = S.A.fields(result, root)
        field = lambda path: result[slice(*spans[path])]
        self.assertEqual(field(("m_RD", "texture")), struct.pack("<iq", 2, 1234))
        self.assertEqual(field(("m_RD", "m_SubMeshes"))[12:], b"B" * 40)
        self.assertEqual(field(("m_RD", "m_VertexData", "m_VertexCount")), struct.pack("<I", 5))
        self.assertEqual(field(("m_RD", "m_IndexBuffer")), S.vector(struct.pack("<9H", *native["triangles"])))
        data = field(("m_RD", "m_VertexData", "m_DataSize"))
        self.assertEqual(struct.unpack_from("<I", data)[0], 104)
        self.assertEqual(data[4 + 64 :], bytes(40))
        self.assertEqual(struct.unpack_from("<i", data, 4 + 48)[0], -2147483648)
        self.assertEqual(field(("m_PhysicsShape",)), struct.pack("<I", 2) + b"".join(struct.pack("<I", 3) + S.words(p["xy_bits"]) for p in native["physics"]))
        self.assertEqual(field(("tail",)), b"tailkeep")

    def test_nonzero_original_uv_is_not_silently_discarded(self):
        body, root, native = fixture()
        _, spans = S.A.fields(body, root)
        start, _ = spans[("m_RD", "m_VertexData", "m_DataSize")]
        changed = bytearray(body)
        changed[start + 4 + 48] = 1
        with self.assertRaisesRegex(ValueError, "zero-filled UV"):
            S.assemble(bytes(changed), root, native, "1" * 32)


if __name__ == "__main__":
    unittest.main()
