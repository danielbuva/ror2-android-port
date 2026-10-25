"""Authored source controller fixtures; no original game bytes are present."""

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


A = load("controller_records", ROOT / "tools/phone-build/accepted-output/record_produce.py")
C = load("controller_pack", ROOT / "tests/test_phone_record_producer.py")
F = load("controller_nodes", ROOT / "tests/test_phone_mesh_producer.py")


def integer(name):
    return F.node(name, 4, kind="UInt32")


def vector(values):
    return struct.pack("<I", len(values)) + b"".join(values)


def tos_entry(value):
    raw = value.encode()
    result = struct.pack("<II", zlib.crc32(raw), len(raw)) + raw
    return result + bytes(-len(result) % 4)


class ControllerRecords(unittest.TestCase):
    def test_tos_selects_source_rows_rebuilds_export_name_and_crc(self):
        text = F.node("second", children=[F.array("chars", F.node("data", 1, kind="char"))], meta=0x4000)
        entry = F.node("data", children=[integer("first"), text])
        schema = F.node("Base", children=[F.array("m_TOS", entry), integer("opaque")])
        original = "Assets/Art/Example.fbx Walk(Clone) "
        body = vector([tos_entry("Base Layer"), tos_entry(original), tos_entry("unused")]) + struct.pack("<I", 0x12345678)
        expected = vector([tos_entry("Assets/WholeGame/Art/Walk.anim Walk(Clone) "), tos_entry("Base Layer")]) + body[-4:]
        self.assertEqual(A.transform_generic(body, 91, {"controller_tos": [[1, True], [0, False]]}, schema), expected)
        self.assertEqual(A.exported_clip_tos("Assets/Example.animIdle(Instance)"), "Assets/WholeGame/Idle.animIdle(Instance)")
        for selection in ([[1, True], [1, False]], [[3, False]], [[True, False]], [[0, 1]]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                A.controller_tos(body, schema, selection)
        broken = bytearray(body)
        broken[4] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC drift"):
            A.controller_tos(bytes(broken), schema, [[0, False]])
        for name in ("outside/Example.fbxWalk", "Assets/Example.fbx", "Assets/Example.txtWalk"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                A.exported_clip_tos(name)

    def test_opposed_angles_are_derived_from_original_vectors(self):
        point = lambda: F.node("data", children=[F.node(n, 4, kind="float") for n in ("x", "y")])
        schema = F.node(
            "Base",
            children=[
                F.node(
                    "m_Controller",
                    children=[
                        integer("m_BlendType"),
                        F.node(
                            "m_Blend2dData",
                            children=[F.node("data", children=[F.array("m_ChildPositionArray", point()), F.array("m_ChildPairVectorArray", point())])],
                        ),
                    ],
                )
            ],
        )
        body = struct.pack("<I", 2) + vector([struct.pack("<ff", 1, 0), struct.pack("<ff", -1, 0), struct.pack("<ff", 0, 0)])
        pairs = [(0, 42), (math.pi, 43), (0, 44), (math.pi, 45), (0, 46), (0, 47), (0, 48), (0, 49), (0, 50)]
        body += vector([struct.pack("<ff", *p) for p in pairs])
        result = A.transform_generic(body, 91, {"controller_opposed_angles": True}, schema)
        self.assertEqual(struct.pack("<f", A.bounded_f32_pi()), struct.pack("<I", 0x40490FDA))
        _, spans = A.fields(body, schema)
        for i in (1, 3):
            off, _ = spans[("m_Controller", "m_Blend2dData", "data", "m_ChildPairVectorArray", "Array", str(i), "x")]
            self.assertEqual(struct.unpack_from("<I", result, off)[0], 0x40490FDA)
        self.assertEqual(sum(a != b for a, b in zip(body, result)), 2)
        self.assertEqual(A.controller_opposed_angles(result, schema), result)
        changed = bytearray(body)
        struct.pack_into("<f", changed, spans[("m_Controller", "m_Blend2dData", "data", "m_ChildPairVectorArray", "Array", "1", "x")][0], 1)
        with self.assertRaisesRegex(ValueError, "angle drift"):
            A.controller_opposed_angles(bytes(changed), schema)

    def test_behaviour_permutation_preserves_each_singleton_state(self):
        pointer = F.node("data", children=[integer("m_FileID"), F.node("m_PathID", 8)])
        state = F.node("data", children=[integer("m_StartIndex"), integer("m_Count")])
        schema = F.node(
            "Base",
            children=[
                F.array("m_StateMachineBehaviours", pointer),
                F.node(
                    "m_StateMachineBehaviourVectorDescription",
                    children=[F.array("m_StateMachineBehaviourIndices", integer("data")), F.array("m_StateMachineBehaviourRanges", state)],
                ),
                integer("opaque"),
            ],
        )
        body = vector([struct.pack("<iq", 1, i) for i in (11, 22, 33, 44)])
        body += vector([struct.pack("<I", i) for i in range(4)]) + vector([struct.pack("<II", i, 1) for i in (2, 0, 3, 1)]) + struct.pack("<I", 123)
        result = A.transform_generic(body, 91, {"controller_behaviour_order": [0, 1, 3, 2]}, schema)
        self.assertEqual(result[4:52], b"".join(struct.pack("<iq", 1, i) for i in (11, 22, 44, 33)))
        _, spans = A.fields(body, schema)
        for i, expected in enumerate((3, 0, 2, 1)):
            path = ("m_StateMachineBehaviourVectorDescription", "m_StateMachineBehaviourRanges", "Array", str(i), "m_StartIndex")
            self.assertEqual(struct.unpack_from("<I", result, spans[path][0])[0], expected)
        self.assertEqual(result[-4:], body[-4:])
        with self.assertRaisesRegex(ValueError, "invalid behaviour permutation"):
            A.controller_singleton_behaviours(body, schema, [0, 1, 2, 2])
        changed = bytearray(body)
        path = ("m_StateMachineBehaviourVectorDescription", "m_StateMachineBehaviourRanges", "Array", "0", "m_Count")
        struct.pack_into("<I", changed, spans[path][0], 2)
        with self.assertRaisesRegex(ValueError, "nonsingleton"):
            A.controller_singleton_behaviours(bytes(changed), schema, [0, 1, 3, 2])

    def test_original_clip_dependencies_compile_mixed_state_loop_flags(self):
        leaf = F.node("data", children=[F.array("m_ChildIndices", integer("data")), integer("m_ClipID")])
        state = F.node("data", children=[F.node("data", children=[F.array("nodes", leaf), F.node("m_Loop", 1, kind="bool")], meta=0x4000)])
        machine = F.node("data", children=[F.node("data", children=[F.array("m_StateConstantArray", state)])])
        pointer = F.node("data", children=[integer("m_FileID"), F.node("m_PathID", 8)])
        schema = F.node("Base", children=[F.node("m_Controller", children=[F.array("m_StateMachineArray", machine)]), F.array("m_AnimationClips", pointer)])
        mixed = vector([struct.pack("<II", 0, 0), struct.pack("<II", 0, 1)]) + bytes([1, 0, 0, 0])
        single = vector([struct.pack("<II", 0, 0)]) + bytes([1, 0, 0, 0])
        body = vector([vector([mixed, single])]) + vector([struct.pack("<iq", 0, 11), struct.pack("<iq", 0, 22)])
        expected = vector([vector([mixed[:-4] + bytes(4), single])]) + vector([struct.pack("<iq", 0, 11), struct.pack("<iq", 0, 22)])
        clip_schema = F.node("Base", children=[F.node("m_MuscleClip", children=[F.node("m_LoopTime", 1, kind="bool")])])
        source_stream = io.BytesIO(C.serialized(body, schema, 91))
        source_stream.size = len(source_stream.getvalue())
        metadata = A.W.read_serialized(source_stream)
        clip_stream = io.BytesIO(C.serialized(bytes([1]), clip_schema, 74))
        clip_stream.size = len(clip_stream.getvalue())
        clip_metadata = A.W.read_serialized(clip_stream)
        metadata.pop("bytes")
        metadata.pop("data_offset")
        metadata["types"] += clip_metadata["types"]
        metadata["objects"] = [
            {"path_id": 77, "offset": 0, "bytes": len(body), "type_id": 0},
            {"path_id": 11, "offset": (len(body) + 7) // 8 * 8, "bytes": 1, "type_id": 1},
            {"path_id": 22, "offset": (len(body) + 7) // 8 * 8 + 8, "bytes": 1, "type_id": 1},
        ]
        serialized = io.BytesIO()
        A.W.write_serialized(serialized, metadata, lambda obj: io.BytesIO({77: body, 11: bytes([1]), 22: bytes([0])}[obj["path_id"]]))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(F.bundle([("CAB-original", serialized.getvalue(), 4)]))
            dependencies = [
                {
                    "index": index,
                    "bundle": source.name,
                    "bundle_sha256": A.B.sha(source),
                    "member": "CAB-original",
                    "path_id": pid,
                    "sha256": hashlib.sha256(flag).hexdigest(),
                }
                for index, pid, flag in ((0, 11, bytes([1])), (1, 22, bytes([0])))
            ]
            operations = {"controller_loop_states": [{"state": [0, 0], "clips": dependencies}]}
            target = {
                "bundle": "target",
                "member": "CAB-target",
                "path_id": -77,
                "bytes": len(expected),
                "sha256": hashlib.sha256(expected).hexdigest(),
                "transform": operations,
            }
            profile = {
                "input_id": A.M.INPUT_ID,
                "bundles": [
                    {
                        "path": source.name,
                        "sha256": A.B.sha(source),
                        "members": [
                            {
                                "name": "CAB-original",
                                "objects": [{"class_id": 91, "path_id": 77, "sha256": hashlib.sha256(body).hexdigest(), "outputs": [target]}],
                            }
                        ],
                    }
                ],
            }
            path = root / "profile.json"
            path.write_text(json.dumps(profile))
            self.assertTrue(A.produce(path, A.B.sha(path), pc, root / "pack")["success"])
            self.assertEqual((root / "pack/objects.bin").read_bytes(), expected)
            dependencies[1]["path_id"] = 11
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "PPtr drift"):
                A.produce(path, A.B.sha(path), pc, root / "wrong-reference")
            dependencies[1]["path_id"] = 22
            dependencies[1]["sha256"] = "0" * 64
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "body drift"):
                A.produce(path, A.B.sha(path), pc, root / "wrong-body")
            dependencies.pop()
            with self.assertRaisesRegex(ValueError, "original leaves"):
                A.transform_generic(body, 91, operations, schema, lambda row, pointer: True)
            with self.assertRaisesRegex(ValueError, "original clip reader"):
                A.transform_generic(body, 91, operations, schema)


if __name__ == "__main__":
    unittest.main()
