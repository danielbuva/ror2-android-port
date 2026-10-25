"""Authored contracts for additional original clip import transformations."""

import importlib.util
import copy
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("clip_expansion_fixtures", ROOT / "tests/test_phone_record_producer.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
A = F.A


def duplicate_fixture(streamed=False):
    _, schema = F.layout_fixture()
    word = lambda value: struct.unpack("<I", struct.pack("<f", value))[0]
    pack = lambda values: struct.pack("<I" + "I" * len(values), len(values), *values)
    if streamed:
        frames = []
        for time, value in ((0xFF7FFFFF, 0), (word(0), 0), (word(1), 1)):
            frames.extend((time, 2, 0, 0, 0, 0, word(value), 1, 0, 0, 0, word(value)))
        frames.extend((0x7F800000, 0))
        constants, count = [], 2
    else:
        frames, constants, count = [0x7F800000, 0], [word(3), word(3)], 0
    body = struct.pack("<If", 1000, 60) + pack(frames) + struct.pack("<II4I", count, 7, 0, word(60), 0, 0)
    body += pack(constants) + struct.pack("<I4f", 2, *(0, 1, 0, 1) if streamed else (3, 3, 3, 3))
    body += pack([0, 1]) + struct.pack("<fI", 1, 2) + struct.pack("<III", 100, 7, 137) * 2
    return body, schema


class ClipExpansionTests(unittest.TestCase):
    def test_duplicate_binding_reuses_only_equal_original_channels(self):
        body, root = duplicate_fixture()
        layout = {"binding_order": [0], "fold_bindings": [], "dense_policy": "preserve"}
        made = A.layout_clip(body, root, layout)
        _, spans = A.fields(made, root)
        constant = ("m_MuscleClip", "m_Clip", "data", "m_ConstantClip", "data")
        self.assertEqual(struct.unpack_from("<If", made, spans[constant][0]), (1, 3))
        self.assertEqual(struct.unpack_from("<I", made)[0], 988)
        self.assertEqual(struct.unpack_from("<I2I", made, spans[("m_MuscleClip", "m_IndexArray")][0]), (2, 0, 0))
        _, original_spans = A.fields(body, root)
        for offset in (original_spans[constant][0] + 8, original_spans[("m_MuscleClip", "m_ValueArrayDelta")][0] + 12):
            changed = bytearray(body)
            struct.pack_into("<f", changed, offset, 4)
            with self.assertRaisesRegex(ValueError, "different original values"):
                A.layout_clip(bytes(changed), root, layout)

    def test_stream_duplicate_drops_reference_row_and_retains_finite_keys(self):
        body, root = duplicate_fixture(streamed=True)
        made = A.layout_clip(body, root, {"binding_order": [0], "fold_bindings": [], "dense_policy": "preserve"})
        _, spans = A.fields(made, root)
        start, end = spans[("m_MuscleClip", "m_Clip", "data", "m_StreamedClip", "data")]
        words = struct.unpack_from("<" + "I" * ((end - start) // 4), made, start)
        # Four frame headers, one reference and four finite source keys.
        self.assertEqual(words[0], 8 + 5 * 5)
        self.assertEqual(words[2], 1)
        self.assertEqual(words[9], 2)
        self.assertEqual(words[21], 2)

    def test_row_permutation_cannot_move_between_different_curves(self):
        body, root = F.layout_fixture()
        layout = {"binding_order": [0, 1, 2, 3], "fold_bindings": [], "dense_policy": "preserve", "stream_order": [[1, [1, 0]]]}
        with self.assertRaisesRegex(ValueError, "equal-curve"):
            A.layout_clip(body, root, layout)

    def test_duplicate_stream_delta_samples_original_endpoint_after_row_order(self):
        body, original_root = duplicate_fixture(streamed=True)
        _, spans = A.fields(body, original_root)
        stop = spans[("m_MuscleClip", "m_StopTime")][0]
        root = copy.deepcopy(original_root)
        muscle = next(child for child in root.children if child.name == "m_MuscleClip")
        muscle.children.insert(-1, F.F.node("m_StartTime", 4, kind="float"))
        body = body[:stop] + struct.pack("<2f", 0, 0.5) + body[stop + 4 :]
        layout = {"binding_order": [0], "fold_bindings": [], "dense_policy": "preserve", "stream_order": [[1, [1, 0]]], "resample_stream_delta": True}
        made = A.layout_clip(body, root, layout)
        _, spans = A.fields(made, root)
        delta = spans[("m_MuscleClip", "m_ValueArrayDelta")][0]
        # The original step remains zero before the key at time 1.
        self.assertEqual(struct.unpack_from("<I2f", made, delta), (1, 0, 0))
        with self.assertRaisesRegex(ValueError, "requires duplicate"):
            A.layout_clip(body, root, layout | {"binding_order": [0, 1], "stream_order": []})

    def test_material_unknown_path_uses_original_path_crc(self):
        body, root = F.layout_fixture()
        _, spans = A.fields(body, root)
        path = ("m_ClipBindingConstant", "genericBindings", "Array", "1")
        source = bytearray(body)
        struct.pack_into("<I", source, spans[path + ("path",)][0], 0xFA123456)
        made = A.transform(bytes(source), root, {"material_path_bindings": [1]})
        expected = bytearray(source)
        struct.pack_into("<I", expected, spans[path + ("attribute",)][0], 0x8A123456)
        self.assertEqual(made, expected)
        for invalid in (-1, 4, True):
            with self.assertRaises(ValueError):
                A.transform(bytes(source), root, {"material_path_bindings": [invalid]})


if __name__ == "__main__":
    unittest.main()
