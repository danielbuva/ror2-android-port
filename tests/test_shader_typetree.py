"""Authored Shader48 schema contracts, independently checked with UnityPy."""

import importlib.util
import io
from pathlib import Path
import struct
import unittest

from UnityPy.helpers.TypeTreeHelper import read_typetree, write_typetree
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.streams import EndianBinaryReader, EndianBinaryWriter

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("shader_writer", ROOT / "tools/phone-build/accepted-output/unity_write.py")
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


def schema():
    strings = bytearray()

    def offset(text):
        for key, value in W.SHADER_COMMON.items():
            if text == value:
                return key | 0x80000000
        result = len(strings)
        strings.extend(text.encode() + b"\0")
        return result

    rows = []

    def add(level, typ, name, meta=0):
        rows.append(struct.pack("<hBBIIiiiQ", 1, level, 0, offset(typ), offset(name), -1, len(rows), meta, 0))

    add(0, "Shader", "Base")
    add(1, "string", "m_Name")
    add(1, "map", "tags")
    add(2, "Array", "Array", 0x4000)
    add(3, "int", "size")
    add(3, "pair", "data")
    add(4, "string", "first")
    add(4, "SInt8", "second")
    for typ in W.SHADER_SCALARS:
        add(1, typ, typ, 0x4000)
    return struct.pack("<II", len(rows), len(strings)) + b"".join(rows) + strings


class ShaderTreeTests(unittest.TestCase):
    def test_nested_ordered_duplicate_map_unicode_signed_scalars_and_alignment(self):
        blob = schema()
        node = W.shader_node(blob)
        independent = TypeTreeNode.parse_blob(EndianBinaryReader(blob, endian="<"), 22)
        value = {
            "m_Name": "authored 𐐷 shader",
            "tags": [("duplicate", -7), ("duplicate", 12)],
            "int": -12,
            "unsigned int": 0xFFFFFFFF,
            "float": 1.25,
            "UInt8": 255,
            "char": 23,
            "bool": True,
            "SInt8": -128,
            "UInt16": 65535,
            "SInt64": -(1 << 60),
        }
        writer = EndianBinaryWriter(endian="<")
        write_typetree(value, independent, writer)
        raw = W.write_shader_body(node, value)
        self.assertEqual(raw, writer.bytes)
        self.assertEqual(W.read_shader_body(node, raw), value)
        self.assertEqual(read_typetree(independent, EndianBinaryReader(raw, endian="<"), byte_size=len(raw)), value)
        self.assertEqual(W.write_shader_body(node, W.read_shader_body(node, raw)), raw)

    def test_truncated_or_unconsumed_body_is_rejected(self):
        node = W.shader_node(schema())
        with self.assertRaises(ValueError):
            W.read_shader_body(node, b"\x04\0\0\0x")
        simple = W.shader_node(struct.pack("<IIhBBIIiiiQ", 1, 0, 1, 0, 0, 222 | 0x80000000, 55 | 0x80000000, 4, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, "complete body"):
            W.read_shader_body(simple, bytes(5))


if __name__ == "__main__":
    unittest.main()
