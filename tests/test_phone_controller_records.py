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
    def test_exported_sync_chain_resolves_groups_and_aligned_index_allocations(self):
        state = F.node("data", children=[F.node("data", children=[F.array("m_BlendTreeConstantIndexArray", integer("data"))])])
        machine = F.node("data", children=[F.node("data", children=[integer("m_SynchronizedLayerCount"), F.array("m_StateConstantArray", state)])])
        layer = F.node("data", children=[F.node("data", children=[integer("m_StateMachineIndex"), integer("m_StateMachineSynchronizedLayerIndex")])])
        schema = F.node(
            "Base",
            children=[integer("m_ControllerSize"), F.node("m_Controller", children=[F.array("m_StateMachineArray", machine), F.array("m_LayerArray", layer)])],
        )

        def group(slots, states):
            indices = vector([bytes(4)] + [struct.pack("<I", 0xFFFFFFFF)] * (slots - 1))
            return struct.pack("<I", slots) + vector([indices] * states)

        source_layers = vector([struct.pack("<II", *row) for row in ((0, 0), (1, 0), (1, 1), (2, 0), (2, 1))])
        expected_layers = vector([struct.pack("<II", *row) for row in ((0, 0), (1, 0), (1, 1), (2, 0), (1, 2))])
        body = struct.pack("<I", 400) + vector([group(1, 1), group(2, 3), group(2, 5)]) + source_layers
        expected = struct.pack("<I", 424) + vector([group(1, 1), group(3, 3), group(1, 5)]) + expected_layers
        self.assertEqual(A.transform_generic(body, 91, {"controller_resolve_synced_layers": True}, schema), expected)

    def test_null_motion_retains_state_and_replaces_the_removed_tree_index(self):
        leaf = F.node(
            "data",
            children=[
                F.node(
                    "data", children=[integer("m_ClipID"), F.array("m_ChildIndices", integer("data")), F.array("extras", integer("data")), integer("retained")]
                )
            ],
        )
        tree = F.node("data", children=[F.node("data", children=[F.array("m_NodeArray", leaf)])])
        state = F.node(
            "data", children=[F.node("data", children=[F.array("m_BlendTreeConstantArray", tree), F.array("m_BlendTreeConstantIndexArray", integer("data"))])]
        )
        machine = F.node("data", children=[F.node("data", children=[F.array("m_StateConstantArray", state)])])
        schema = F.node(
            "Base", children=[integer("m_ControllerSize"), F.node("m_Controller", children=[F.array("m_StateMachineArray", machine)]), integer("tail")]
        )
        motion = vector([vector([struct.pack("<IIII", 0xFFFFFFFF, 0, 0, 37)])])
        body = struct.pack("<I", 1000) + vector([vector([motion + vector([bytes(4)])])]) + struct.pack("<I", 71)
        expected = struct.pack("<I", 944) + vector([vector([bytes(4) + vector([struct.pack("<I", 0xFFFFFFFF)])])]) + body[-4:]
        stream = io.BytesIO(C.serialized(body, schema, 91))
        stream.size = len(stream.getvalue())
        root = A.SCHEMA.type_tree(io.BytesIO(A.W.read_serialized(stream)["types"][0]["tree"]))
        self.assertEqual(A.transform_generic(body, 91, {"controller_clear_null_motion": True}, root), expected)

    def test_populated_tree_blob_counts_nested_arrays_and_alignment(self):
        tree = ("tree",)

        def allocation(node_counts):
            body, spans = bytearray(), {}

            def value(path, count):
                spans[path] = (len(body), len(body) + 4)
                body.extend(struct.pack("<I", count))

            nodes = tree + ("data", "m_NodeArray", "Array")
            value(nodes, len(node_counts))
            for index, counts in enumerate(node_counts):
                node = nodes + (str(index), "data")
                value(node + ("m_ChildIndices", "Array"), counts.get("children", 0))
                value(node + ("m_Blend1dData", "data", "m_ChildThresholdArray", "Array"), counts.get("thresholds", 0))
                blend = node + ("m_Blend2dData", "data")
                for name, count in zip(
                    ("m_ChildPositionArray", "m_ChildMagnitudeArray", "m_ChildPairVectorArray", "m_ChildPairAvgMagInvArray"),
                    counts.get("two_d", (0, 0, 0, 0)),
                ):
                    value(blend + (name, "Array"), count)
                neighbors = blend + ("m_ChildNeighborListArray", "Array")
                value(neighbors, len(counts.get("neighbors", [])))
                for neighbor, count in enumerate(counts.get("neighbors", [])):
                    value(neighbors + (str(neighbor), "m_NeighborArray", "Array"), count)
                value(node + ("m_BlendDirectData", "data", "m_ChildBlendEventIDArray", "Array"), 0)
            return A.controller_tree_allocation(body, spans, tree)

        self.assertEqual(allocation([{}]), 152)
        self.assertEqual(allocation([{"children": 2, "thresholds": 2}, {}, {}]), 416)
        # Odd child count pads before the 2D header; neighbor records have
        # 24-byte native strides and nested uint payloads remain 4-aligned.
        self.assertEqual(allocation([{"children": 3, "two_d": (3, 3, 9, 9), "neighbors": [1, 2, 3]}, {}]), 640)

    def test_synced_override_omission_preserves_shared_clip_occurrences(self):
        empty = lambda name: F.array(name, integer("data"))
        leaf = F.node(
            "data",
            children=[
                F.node(
                    "data",
                    children=[
                        integer("m_BlendType"),
                        integer("m_BlendEventID"),
                        integer("m_BlendEventYID"),
                        empty("m_ChildIndices"),
                        F.node("m_Blend1dData", children=[F.node("data", children=[empty("m_ChildThresholdArray")])]),
                        F.node(
                            "m_Blend2dData",
                            children=[
                                F.node(
                                    "data",
                                    children=[
                                        empty(name)
                                        for name in (
                                            "m_ChildPositionArray",
                                            "m_ChildMagnitudeArray",
                                            "m_ChildPairVectorArray",
                                            "m_ChildPairAvgMagInvArray",
                                            "m_ChildNeighborListArray",
                                        )
                                    ],
                                )
                            ],
                        ),
                        F.node(
                            "m_BlendDirectData", children=[F.node("data", children=[empty("m_ChildBlendEventIDArray"), integer("m_NormalizedBlendValues")])]
                        ),
                        integer("m_ClipID"),
                        integer("m_Duration"),
                        integer("m_CycleOffset"),
                        integer("m_Mirror"),
                    ],
                )
            ],
        )
        tree = F.node("data", children=[F.node("data", children=[F.array("m_NodeArray", leaf)])])
        state = F.node(
            "data", children=[F.node("data", children=[F.array("m_BlendTreeConstantArray", tree), F.array("m_BlendTreeConstantIndexArray", integer("data"))])]
        )
        machine = F.node("data", children=[F.node("data", children=[F.array("m_StateConstantArray", state)])])
        pointer = F.node("data", children=[integer("m_FileID"), F.node("m_PathID", 8)])
        schema = F.node(
            "Base",
            children=[
                integer("m_ControllerSize"),
                F.node("m_Controller", children=[F.array("m_StateMachineArray", machine)]),
                F.array("m_AnimationClips", pointer),
            ],
        )
        motion = lambda clip: vector([bytes(48) + struct.pack("<IIII", clip, 0, 0, 0)])
        state_body = vector([motion(0), motion(0)]) + vector([struct.pack("<I", i) for i in (0, 1)])
        clips = [struct.pack("<iq", 0, i) for i in (11, 22, 11)]
        body = struct.pack("<I", 1000) + vector([vector([state_body])]) + vector(clips)
        expected_state = vector([motion(0)]) + vector([bytes(4), struct.pack("<I", 0xFFFFFFFF)])
        expected = struct.pack("<I", 848) + vector([vector([expected_state])]) + vector(clips[:2])
        self.assertEqual(A.transform_generic(body, 91, {"controller_omit_synced_overrides": True}, schema), expected)

        # The exporter selects tree zero even when only a synchronized layer
        # references it. Reimport places that motion in the base state slot.
        source_state = vector([motion(0)]) + vector([struct.pack("<I", i) for i in (0xFFFFFFFF, 0)])
        source = struct.pack("<I", 848) + vector([vector([source_state])]) + vector(clips[:2])
        self.assertEqual(A.transform_generic(source, 91, {"controller_omit_synced_overrides": True}, schema), expected)

    def test_synced_behaviour_omission_preserves_original_state_keys(self):
        layer = F.node("data", children=[F.node("data", children=[integer("m_StateMachineSynchronizedLayerIndex")])])
        key = F.node("key", children=[integer("m_StateID"), integer("m_LayerIndex")])
        value = F.node("value", children=[integer("m_StartIndex"), integer("m_Count")])
        entry = F.node("data", children=[key, value])
        pointer = F.node("data", children=[integer("m_FileID"), F.node("m_PathID", 8)])
        schema = F.node(
            "Base",
            children=[
                F.node("m_Controller", children=[F.array("m_LayerArray", layer)]),
                F.array("m_StateMachineBehaviours", pointer),
                F.node(
                    "m_StateMachineBehaviourVectorDescription",
                    children=[
                        F.array("m_StateMachineBehaviourIndices", integer("data")),
                        F.array("m_StateMachineBehaviourRanges", entry),
                    ],
                ),
                integer("opaque"),
            ],
        )
        layers = vector([struct.pack("<I", i) for i in (0, 0, 1)])
        pointers = [struct.pack("<iq", 0, i) for i in (11, 22, 33)]
        ranges = [struct.pack("<IIII", *row) for row in ((73, 2, 2, 1), (59, 1, 1, 1), (41, 0, 0, 1))]
        body = layers + vector(pointers) + vector([struct.pack("<I", i) for i in range(3)]) + vector(ranges) + struct.pack("<I", 97)
        expected = layers + vector(pointers[:2]) + vector([bytes(4), struct.pack("<I", 1)])
        expected += vector([struct.pack("<IIII", 59, 1, 1, 1), struct.pack("<IIII", 41, 0, 0, 1)]) + body[-4:]
        self.assertEqual(A.controller_omit_synced_behaviours(body, schema), expected)

    def test_state_order_relocates_direct_destinations_and_preserves_selector_values(self):
        transition = F.node("data", children=[integer("m_DestinationState"), integer("retained")])
        state = F.node("data", children=[F.node("data", children=[integer("m_FullPathID"), F.array("m_TransitionConstantArray", transition)])])
        machine = F.node(
            "data",
            children=[
                F.node(
                    "data",
                    children=[F.array("m_StateConstantArray", state), integer("m_DefaultState"), F.array("m_AnyStateTransitionConstantArray", transition)],
                )
            ],
        )
        schema = F.node("Base", children=[F.node("m_Controller", children=[F.array("m_StateMachineArray", machine)])])

        def record(identity, destination, retained):
            return struct.pack("<I", identity) + vector([struct.pack("<II", destination, retained)])

        first, second, third = record(101, 1, 313), record(202, 0xFFFFFFFF, 919), record(303, 30001, 717)
        body = vector([vector([first, second, third]) + struct.pack("<I", 1) + vector([struct.pack("<II", 2, 411)])])
        expected = vector([vector([third, record(101, 2, 313), second]) + struct.pack("<I", 2) + vector([struct.pack("<II", 0, 411)])])
        stream = io.BytesIO(C.serialized(body, schema, 91))
        stream.size = len(stream.getvalue())
        tree = A.W.read_serialized(stream)["types"][0]["tree"]
        root = A.SCHEMA.type_tree(io.BytesIO(tree))
        self.assertEqual(A.transform_generic(body, 91, {"controller_state_order": {"0": [2, 0, 1]}}, root), expected)

    def test_exported_mask_omission_preserves_controller_fields_and_allocation_size(self):
        item = F.node("data", children=[integer("path_hash"), F.node("weight", 4, kind="float")])
        mask = F.node("m_SkeletonMask", children=[F.node("data", children=[F.array("m_Data", item)])])
        human = F.node("m_BodyMask", children=[integer("word0"), integer("word1"), integer("word2")])
        layer = F.node("data", children=[F.node("data", children=[integer("retained"), human, mask])])
        schema = F.node(
            "Base",
            children=[integer("m_ControllerSize"), F.node("m_Controller", children=[F.array("m_LayerArray", layer)]), integer("tail")],
        )
        mask_body = vector([struct.pack("<If", 71, 0.25), struct.pack("<If", 89, 0.75)])
        full = struct.pack("<III", 0xFFFFFFFF, 0xFFFFFFFF, (1 << 19) - 1)
        body = (
            struct.pack("<I", 1000)
            + vector([struct.pack("<I", 17) + bytes(12) + mask_body, struct.pack("<I", 29) + full + bytes(4)])
            + struct.pack("<I", 0xAABBCCDD)
        )
        expected = (
            struct.pack("<I", 960) + vector([struct.pack("<I", 17) + full + bytes(4), struct.pack("<I", 29) + full + bytes(4)]) + struct.pack("<I", 0xAABBCCDD)
        )
        stream = io.BytesIO(C.serialized(body, schema, 91))
        stream.size = len(stream.getvalue())
        tree = A.W.read_serialized(stream)["types"][0]["tree"]
        root = A.SCHEMA.type_tree(io.BytesIO(tree))
        self.assertEqual(A.transform_generic(body, 91, {"controller_clear_skeleton_masks": True}, root), expected)

    def test_tos_selects_source_rows_rebuilds_export_name_and_crc(self):
        text = F.node("second", children=[F.array("chars", F.node("data", 1, kind="char"))], meta=0x4000)
        entry = F.node("data", children=[integer("first"), text])
        schema = F.node("Base", children=[F.array("m_TOS", entry), integer("opaque")])
        original = "Assets/Art/Example.fbx Walk(Clone) "
        body = vector([tos_entry("Base Layer"), tos_entry(original), tos_entry("unused")]) + struct.pack("<I", 0x12345678)
        expected = vector([tos_entry("Assets/WholeGame/Art/Walk.anim Walk(Clone) "), tos_entry("Base Layer")]) + body[-4:]
        self.assertEqual(A.transform_generic(body, 91, {"controller_tos": [[1, True], [0, False]]}, schema), expected)
        collision = vector([tos_entry("Assets/WholeGame/Art/Walk_0.anim Walk(Clone) "), tos_entry("Base Layer")]) + body[-4:]
        self.assertEqual(A.transform_generic(body, 91, {"controller_tos": [[1, True, 0], [0, False]]}, schema), collision)
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
            A.controller_behaviour_ranges(body, schema, [0, 1, 2, 2])
        changed = bytearray(body)
        path = ("m_StateMachineBehaviourVectorDescription", "m_StateMachineBehaviourRanges", "Array", "0", "m_Count")
        struct.pack_into("<I", changed, spans[path][0], 2)
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            A.controller_behaviour_ranges(bytes(changed), schema, [0, 1, 3, 2])

    def test_behaviour_permutation_preserves_ordered_multi_and_empty_ranges(self):
        pointer = F.node("data", children=[integer("m_FileID"), F.node("m_PathID", 8)])
        state = F.node("data", children=[integer("m_StartIndex"), integer("m_Count")])
        schema = F.node(
            "Base",
            children=[
                F.array("m_StateMachineBehaviours", pointer),
                F.node(
                    "m_StateMachineBehaviourVectorDescription",
                    children=[
                        F.array("m_StateMachineBehaviourIndices", integer("data")),
                        F.array("m_StateMachineBehaviourRanges", state),
                    ],
                ),
            ],
        )
        body = vector([struct.pack("<iq", 1, i) for i in (11, 22, 33, 44)])
        indices = vector([struct.pack("<I", i) for i in range(4)])
        body += indices + vector([struct.pack("<II", start, count) for start, count in ((0, 2), (4, 0), (2, 2))])
        expected = vector([struct.pack("<iq", 1, i) for i in (33, 44, 11, 22)])
        expected += indices + vector([struct.pack("<II", start, count) for start, count in ((2, 2), (4, 0), (0, 2))])
        self.assertEqual(A.transform_generic(body, 91, {"controller_behaviour_order": [2, 3, 0, 1]}, schema), expected)
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            A.controller_behaviour_ranges(body, schema, [1, 0, 2, 3])

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
