"""Independent authored serialized/bundle fixtures; no game or Editor needed."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phone_mesh_producer", ROOT / "tools/phone-build/accepted-output/mesh_produce.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
B, M = P._bundle, P._mesh


def node(name, size=-1, children=(), flags=0, meta=0, kind="struct"):
    value = M.Node(0, flags, kind, name, size, meta)
    value.children = list(children)
    return value


def array(name, element, kind="vector"):
    return node(name, children=[node("Array", children=[node("size", 4), element], flags=1)], meta=0x4000, kind=kind)


def text(name):
    return array(name, node("data", 1), "string")


def vector(data, count):
    return struct.pack("<I", count) + data + bytes(-len(data) % 4)


def authored_mesh(streamed=False):
    schema = node(
        "Base",
        children=[
            text("m_Name"),
            node("untouched", 8),
            node("m_IsReadable", 1),
            node("m_KeepVertices", 1),
            node("m_KeepIndices", 2),
            node("m_MeshUsageFlags", 4),
            node(
                "m_VertexData", children=[node("m_VertexCount", 4), array("m_Channels", node("data", 4)), array("m_DataSize", node("data", 1), "TypelessData")]
            ),
            array("m_BakedConvexCollisionMesh", node("data", 1)),
            array("m_BakedTriangleCollisionMesh", node("data", 1)),
            node("m_StreamData", children=[node("offset", 8), node("size", 4), text("path")]),
        ],
    )
    channels = bytes((0, 0, 0, 3, 0, 12, 0, 3, 0, 24, 0, 4))
    vertex = struct.pack("<10f", 1, 2, 3, 0.16973876953125, -0.3287353515625, 1, 0, 1, 0, -1)
    body = M.padded_string("Authored mesh") + b"RETAIN!!" + bytes((1, 0, 0, 0)) + struct.pack("<I", 8)
    body += struct.pack("<I", 1) + vector(channels, 3) + vector(b"" if streamed else vertex, 0 if streamed else len(vertex))
    body += vector(b"convex", 6) + vector(b"triangle", 8)
    body += struct.pack("<QI", 3 if streamed else 0, len(vertex) if streamed else 0) + M.padded_string("resource" if streamed else "")
    return body, schema, vertex


def serialized(body, schema, path_id=-123):
    strings = bytearray()
    offsets = {}

    def label(value):
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode() + b"\0")
        return offsets[value]

    nodes = []

    def flatten(value, level):
        nodes.append(struct.pack("<HBBIIiiiQ", 1, level, value.flags, label(value.kind), label(value.name), value.size, len(nodes), value.meta, 0))
        for child in value.children:
            flatten(child, level + 1)

    flatten(schema, 0)
    metadata = b"2021.3.45f2\0" + struct.pack("<iBIiBh", 19, 1, 1, 43, 0, -1) + bytes(16)
    metadata += struct.pack("<II", len(nodes), len(strings)) + b"".join(nodes) + strings + bytes(4)
    metadata += struct.pack("<I", 1)
    metadata += bytes(-len(metadata) % 4)
    metadata += struct.pack("<qqIi", path_id, 0, len(body), 0)
    data_offset = (48 + len(metadata) + 15) // 16 * 16
    header = struct.pack(">IIII", 0, 0, 22, 0) + bytes(4) + struct.pack(">Iqqq", len(metadata), data_offset + len(body), data_offset, 0)
    return header + metadata + bytes(data_offset - 48 - len(metadata)) + body


def bundle(members, tail=False):
    payload = b"".join(data for _, data, _ in members)
    info = bytes(16) + struct.pack(">IIIH", 1, len(payload), len(payload), 0) + struct.pack(">I", len(members))
    offset = 0
    for name, data, flags in members:
        info += struct.pack(">QQI", offset, len(data), flags) + name.encode() + b"\0"
        offset += len(data)
    prefix = b"UnityFS\0" + struct.pack(">I", 7) + b"2021.3.45f2\0" * 2
    flags = 0x80 if tail else 0x200
    header_size = (len(prefix) + 20 + 15) // 16 * 16
    padding = b"" if tail else bytes(-(header_size + len(info)) % 16)
    size = header_size + len(info) + len(padding) + len(payload)
    header = prefix + struct.pack(">QIII", size, len(info), len(info), flags)
    header += bytes(header_size - len(header))
    return header + payload + info if tail else header + info + padding + payload


class MeshProducerTests(unittest.TestCase):
    def test_packed_tangent_repair_reconstructs_unit_pairs_and_retains_other_fields(self):
        body, schema, _ = authored_mesh()
        packed = ((1023 << 20) | (1023 << 30)).to_bytes(5, "little")
        tangent = node(
            "m_Tangents",
            children=[node("m_NumItems", 4), node("m_Range", 4), node("m_Start", 4), array("m_Data", node("data", 1)), node("m_BitSize", 1, meta=0x4000)],
        )
        schema.children.append(node("m_CompressedMesh", children=[tangent]))
        suffix = struct.pack("<Iff", 4, 2.0, -1.0) + vector(packed, 5) + bytes((10, 0, 0, 0))
        source = body + suffix
        # The authored pairs (-1,-1) and (1,1) reconstruct negative Z squared.
        # Repair produces +/-1/sqrt(2), retaining their original quantized endpoints.
        expected = body + struct.pack("<Iff", 4, 1.4142135381698608, -0.7071067690849304) + suffix[12:]
        actual, external = M.transform(source, schema, {"packed_tangents": "repair_negative_z"})
        self.assertEqual(expected, actual)
        self.assertIsNone(external)
        self.assertEqual(source, M.transform(source, schema, {})[0])

    def test_fixed_struct_array_honors_descendant_padding(self):
        shape = node("data", 10, children=[node("first", 4), node("count", 4), node("normal", 1), node("tangent", 1, meta=0x4000)])
        schema = node("Base", children=[array("shapes", shape), node("marker", 4)])
        body = struct.pack("<I", 2) + (bytes(range(10)) + bytes(2)) * 2 + b"END!"
        spans = M.spans(body, schema)
        self.assertEqual(spans[("marker",)], (28, 32))

    def test_lz4_overlap_and_extensions_and_refusal(self):
        self.assertEqual(B.decompress(b"\x1fa\x01\x00\x01\x50bcdef", 26, 2), b"a" * 21 + b"bcdef")
        literals = bytes(range(200))
        self.assertEqual(B.decompress(b"\xf0\xb9" + literals, 200, 3), literals)
        for bad, size in ((b"\x00\x00\x00", 4), (b"\xf0", 30), (b"\x10", 1), (b"\x10a\x02\x00", 5), (b"\x10a\x01\x00", 4)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                B.decompress(bad, size, 2)

    def test_half_rounding_including_ties_and_subnormals(self):
        cases = ((0.16973876953125, 0x316F), (-0.3287353515625, 0xB543), (1, 0x3C00), (-0.0, 0x8000), (2**-24, 1), (2**-25, 1), (2**-26, 0), (65504, 0x7BFF))
        for value, expected in cases:
            self.assertEqual(M.half(struct.unpack("<I", struct.pack("<f", value))[0]), expected)
        with self.assertRaises(ValueError):
            M.half(0x7F800000)

    def test_stream_inline_half_flags_and_cache_removal(self):
        original, schema, vertex = authored_mesh(True)
        ops = {
            "m_IsReadable": False,
            "m_KeepVertices": True,
            "m_KeepIndices": True,
            "m_MeshUsageFlags": 16,
            "m_BakedConvexCollisionMesh": "clear",
            "m_BakedTriangleCollisionMesh": "clear",
            "m_Name": "Authored renamed",
            "vertex_compression": "normal_tangent_half",
            "stream_destination": {"offset": 0, "size": 0, "path": ""},
        }
        result, external = M.transform(original, schema, ops, vertex)
        spans = M.spans(result, schema)

        def field(*path):
            start, end = spans[path]
            return result[start:end]

        self.assertIsNone(external)
        self.assertEqual(field("untouched"), b"RETAIN!!")
        self.assertEqual(field("m_IsReadable"), b"\0")
        self.assertEqual(field("m_MeshUsageFlags"), struct.pack("<I", 16))
        self.assertEqual(field("m_BakedTriangleCollisionMesh"), bytes(4))
        self.assertEqual(field("m_StreamData"), bytes(16))
        self.assertEqual(field("m_VertexData", "m_Channels", "Array", "payload"), bytes((0, 0, 0, 3, 0, 12, 1, 52, 0, 20, 1, 4)))
        data = field("m_VertexData", "m_DataSize", "Array", "payload")
        self.assertEqual(data[:12], vertex[:12])
        self.assertEqual(struct.unpack_from("<8H", data, 12), (0x316F, 0xB543, 0x3C00, 0, 0, 0x3C00, 0, 0xBC00))
        with self.assertRaises(ValueError):
            M.transform(original, schema, {"opaque_target_data": [1, 2]})
        with self.assertRaises(ValueError):
            M.spans(original[:-1], schema)

    def test_bundle_metadata_producer_persisted_and_failure(self):
        body, schema, _ = authored_mesh()
        for tail in (False, True):
            with self.subTest(tail=tail), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc = root / "pc"
                pc.mkdir()
                source = pc / "authored.bundle"
                source.write_bytes(bundle([("CAB-authored", serialized(body, schema), 4)], tail))
                original_hash = B.sha(source)
                parsed = B.Bundle(source)
                member = parsed.member("CAB-authored")
                offset, length, parsed_schema = M.mesh_objects(member)[-123]
                member.seek(offset)
                self.assertEqual(member.read(length), body)
                result, _ = M.transform(body, parsed_schema, {})
                self.assertEqual(result, body)
                row = {
                    "path_id": -123,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "outputs": [
                        {
                            "bundle": "authored-target",
                            "member": "CAB-target",
                            "path_id": 789,
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "bytes": len(body),
                            "ops": {},
                        }
                    ],
                }
                profile = {
                    "input_id": P.INPUT_ID,
                    "bundles": [{"path": source.name, "sha256": original_hash, "members": [{"name": "CAB-authored", "meshes": [row]}]}],
                    "excluded": [],
                }
                profile_path = root / "profile.json"
                profile_path.write_text(json.dumps(profile))
                receipt = P.produce(profile_path, B.sha(profile_path), pc, root / "output")
                self.assertTrue(receipt["success"])
                self.assertEqual((root / "output/objects.bin").read_bytes(), body)
                self.assertEqual(B.sha(source), original_hash)
                with self.assertRaises(ValueError):
                    P.produce(profile_path, B.sha(profile_path), pc, root / "output")
                row["outputs"][0]["sha256"] = "0" * 64
                profile_path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    P.produce(profile_path, B.sha(profile_path), pc, root / "failed")
                self.assertFalse(json.loads((root / "failed/result.json").read_text())["success"])
                with self.assertRaises(ValueError):
                    P.safe_input(pc, "../profile.json")
                source.write_bytes(b"changed authored input")
                with self.assertRaisesRegex(ValueError, "original bundle drift"):
                    P.produce(profile_path, B.sha(profile_path), pc, root / "source-drift")
                self.assertFalse(json.loads((root / "source-drift/result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
