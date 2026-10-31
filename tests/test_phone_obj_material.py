"""Invented metadata and instruction contracts; no SDK or game input required."""

import importlib.util
from pathlib import Path
import struct
import unittest

from test_phone_player_data import metadata_string, metadata_tree

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("obj_material_test", ROOT / "tools/phone-build/accepted-output/obj_material.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Image:
    def __init__(self, words):
        self.raw = struct.pack("<" + "I" * len(words), *words)
        self.symbol_addresses = [0, len(self.raw)]

    def symbol(self, name):
        return 0

    def at(self, address, size):
        return self.raw[address : address + size]


class ModelMaterialTests(unittest.TestCase):
    def test_model_material_uses_declared_properties_and_original_geometry_name(self):
        def string(value):
            raw = value.encode()
            return struct.pack("<I", len(raw)) + raw + bytes(-len(raw) % 4)

        def fixed(name, size):
            return ("AuthoredField", name, size, 0, 0, [])

        def vector(name, element):
            return ("vector", name, -1, 0, 0, [("Array", "Array", -1, 1, 0, [fixed("size", 4), element])])

        def pairs(name, size):
            return vector(name, ("pair", "data", -1, 0, 0, [metadata_string("first"), fixed("second", size)]))

        def tree(name, children):
            return metadata_tree((name, "Base", -1, 0, 0, children))

        prefix = [fixed("editor" + str(i), size) for i, size in enumerate((4, 12, 12, 12))]
        saved = ("SavedProperties", "m_SavedProperties", -1, 0, 0, [pairs("m_TexEnvs", 28), pairs("m_Ints", 4), pairs("m_Floats", 4), pairs("m_Colors", 16)])
        definition = tree("Material", prefix + [metadata_string("m_Name"), fixed("m_LightmapFlags", 4), saved])
        original_tex = struct.pack("<iq4f", 0, 0, 1, 1, 0, 0)
        body = bytes(40) + string("Old") + struct.pack("<II", 5, 1) + string("_Tex") + original_tex + bytes(4)
        body += struct.pack("<I", 1) + string("_Orphan") + struct.pack("<f", 999)
        body += struct.pack("<I", 1) + string("_Color") + struct.pack("<4f", 1, 1, 1, 1)
        declarations = [("_Color", 0, (1, 1, 1, 1)), ("_Glossiness", 2, (0.75, 0, 0, 0)), ("_Tex", 4, (0, 0, 0, 0))]
        prop_fields = [
            metadata_string("m_Name"),
            metadata_string("description"),
            vector("attributes", metadata_string("data")),
            fixed("kind", 4),
            fixed("flags", 4),
            fixed("defaults", 16),
            metadata_string("texture"),
            fixed("dimension", 4),
        ]
        prop_info = ("Properties", "m_PropInfo", -1, 0, 0, [vector("m_Props", ("Property", "data", -1, 0, 0, prop_fields))])
        shader_type = tree("Shader", [("Parsed", "m_ParsedForm", -1, 0, 0, [prop_info])])
        shader = struct.pack("<I", len(declarations))
        for name, kind, values in declarations:
            shader += string(name) + string("") + struct.pack("<III4f", 0, kind, 0, *values) + string("") + bytes(4)
        geometry_type = tree("Mesh", [metadata_string("m_Name")])
        schema_path = ROOT / "tools/phone-build/accepted-output/unity_mesh.py"
        spec = importlib.util.spec_from_file_location("obj_material_schema_test", schema_path)
        schema = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(schema)
        result = M.material(body, definition, shader, shader_type, string("InventedMesh"), geometry_type, ((0.25, 0.5, 0.75), 2.0, 0.125), schema)
        expected = string("InventedMesh_0Mat") + struct.pack("<II", 4, 1) + string("_Tex") + original_tex + bytes(4)
        expected += struct.pack("<I", 1) + string("_Glossiness") + bytes(4)
        expected += struct.pack("<I", 1) + string("_Color") + struct.pack("<4f", 0.5, 1, 1.5, 0.875)
        self.assertEqual(expected, result)

    def test_initializer_derives_scalar_and_vector_stores_from_constants(self):
        # Authored ORR x3,xzr,#0xff; MOVK x3,#0x1234,lsl#16;
        # DUP v2.2d,x3; ADRP x5,0; ADD x5,x5,#512; STR Q2; STR X3; RET.
        words = [
            0xB2000000 | (1 << 22) | (7 << 10) | (31 << 5) | 3,
            0xF2800000 | (1 << 21) | (0x1234 << 5) | 3,
            0x4E080C00 | (3 << 5) | 2,
            0x90000000 | 5,
            0x91000000 | (512 << 10) | (5 << 5) | 5,
            0x3D800000 | (5 << 5) | 2,
            0xF9000000 | (2 << 10) | (5 << 5) | 3,
            0xD65F03C0,
        ]
        result = M.initializer(Image(words), "invented")
        self.assertEqual(struct.pack("<Q", 0x123400FF) * 3, bytes(result[512 + n] for n in range(24)))

    def test_initializer_refuses_runtime_loads_and_duplicate_stores(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            M.initializer(Image([0xF9400000, 0xD65F03C0]), "invented")
        words = [0x90000000, 0xF900001F, 0xF900001F, 0xD65F03C0]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            M.initializer(Image(words), "invented")

    def test_fat_selection_rejects_ambiguous_or_out_of_bounds_slice(self):
        header = b"\xca\xfe\xba\xbe" + struct.pack(">I", 1)
        valid = header + struct.pack(">5I", 0x100000C, 0, 32, 4, 2) + bytes(4) + b"TEST"
        self.assertEqual(b"TEST", M.arm64_slice(valid))
        with self.assertRaisesRegex(ValueError, "extent"):
            M.arm64_slice(valid[:-1])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            M.arm64_slice(valid[:8] + struct.pack(">5I", 7, 0, 32, 4, 2) + valid[28:])

    def test_shader_declarations_keep_color_and_scalar_raw_default_bits(self):
        def string(value):
            raw = value.encode()
            return struct.pack("<I", len(raw)) + raw + bytes(-len(raw) % 4)

        def prop(name, kind, raw):
            return string(name) + string("Invented") + struct.pack("<3I", 0, kind, 0) + raw + string("") + bytes(4)

        tint, scalar = bytes(range(16)), struct.pack("<4I", 0x80000000, 0, 0, 0)
        body = struct.pack("<I", 2) + prop("_Tint", 0, tint) + prop("_Scalar", 3, scalar)
        self.assertEqual({"_Tint": (0, tint), "_Scalar": (3, scalar)}, M.shader_properties(body))
        with self.assertRaises(ValueError):
            M.shader_properties(body[:-10])


if __name__ == "__main__":
    unittest.main()
