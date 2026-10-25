"""Authored ComputeShader projection contract; no private inputs/SDK."""

import copy
import importlib.util
import io
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


P = load("object_owner", ROOT / "tools/phone-build/accepted-output/object_produce.py")
A = load("compute_fixture", ROOT / "tests/test_phone_record_producer.py")
F = A.F
strip = P.strip_compute_programs


def fixture(stripped=False, renderer=2, level=0, resolved=1, variant_count=1, groups=3, code=b"DXBC-authored-code", extra=False):
    u32 = lambda name: F.node(name, 4, kind="UInt32")
    arrays = ["cbVariantIndices", "cbs", "textures", "builtinSamplers", "inBuffers", "outBuffers", "code"]
    program = F.node(
        "value",
        children=[
            *[F.array(n, F.node("data", 1 if n == "code" else 4, kind="UInt8" if n == "code" else "UInt32")) for n in arrays],
            F.array("threadGroupSize", u32("data")),
            *([u32("unqualifiedField")] if extra else []),
            F.node("requirements", 8, kind="UInt64"),
        ],
    )
    pair = F.node("data", children=[F.text("keywords"), program])
    kernel = F.node("data", children=[F.text("name"), F.array("variantMap", pair)])
    variant = F.node(
        "data",
        children=[
            u32("targetRenderer"),
            u32("targetLevel"),
            F.array("kernels", kernel),
            F.array("constantBuffers", u32("data")),
            F.node("resourcesResolved", 1, meta=0x4000, kind="UInt8"),
        ],
    )
    root = F.node("Base", kind="ComputeShader", children=[F.text("m_Name"), F.array("variants", variant)])
    string = lambda s: F.vector(s.encode(), len(s))

    def word_array(values):
        return F.vector(struct.pack("<" + "I" * len(values), *values), len(values))

    def program_bytes(seed):
        result = b""
        for i, name in enumerate(arrays):
            values = [] if stripped else [seed + i, seed + i + 1]
            result += F.vector(b"" if stripped else code, 0 if stripped else len(code)) if name == "code" else word_array(values)
        result += word_array([0] * groups if stripped else [32 + i for i in range(groups)])
        if extra:
            result += struct.pack("<I", 0xAABBCCDD)
        return result + struct.pack("<Q", 0x9283746501020304 + seed)

    def variant_bytes():
        result = struct.pack("<III", renderer, level, 2)
        for kernel_index in range(2):
            result += string("Kernel-" + str(kernel_index)) + struct.pack("<I", 2)
            for index in range(2):
                result += string("KEEP_KEYWORD_" + str(index)) + program_bytes(100 * kernel_index + index)
        result += word_array([] if stripped else [0x99887766, 0x12345678]) + bytes([resolved]) + bytes(3)
        return result

    body = string("Authored compute") + struct.pack("<I", variant_count) + b"".join(variant_bytes() for _ in range(variant_count))
    data = A.serialized(body, root, 72)
    stream = io.BytesIO(data)
    stream.size = len(data)
    typ = P.W.read_serialized(stream)["types"][0]
    return body, typ


class ComputeProjectionTests(unittest.TestCase):
    def test_all_program_arrays_are_empty_and_all_unrelated_bytes_are_retained(self):
        body, typ = fixture()
        before = body
        beforetype = copy.deepcopy(typ)
        actual = strip(body, typ)
        expected, _ = fixture(stripped=True)
        self.assertEqual(actual, expected)
        self.assertEqual(body, before)
        self.assertEqual(typ, beforetype)
        self.assertIn(b"KEEP_KEYWORD_1", actual)
        self.assertNotIn(b"DXBC", actual)

    def test_renderer_level_resolution_and_variant_contracts(self):
        for changes in [{"renderer": 18}, {"level": 1}, {"resolved": 0}, {"variant_count": 2}, {"variant_count": 0}]:
            with self.subTest(changes=changes):
                body, typ = fixture(**changes)
                with self.assertRaises(ValueError):
                    strip(body, typ)

    def test_unknown_class_program_fields_and_code_are_rejected(self):
        body, typ = fixture()
        typ["class_id"] = 48
        with self.assertRaises(ValueError):
            strip(body, typ)
        for changes in [{"extra": True}, {"code": b"SPIRV-authored"}, {"code": b""}]:
            with self.subTest(changes=changes):
                body, typ = fixture(**changes)
                with self.assertRaises(ValueError):
                    strip(body, typ)

    def test_thread_group_cardinality_must_be_three(self):
        for size in [0, 2, 4]:
            with self.subTest(size=size):
                body, typ = fixture(groups=size)
                with self.assertRaises(ValueError):
                    strip(body, typ)

    def test_truncated_and_extra_source_bytes_cannot_be_discarded(self):
        body, typ = fixture()
        for malformed in [body[:-1], body + b"UNOWNED"]:
            with self.subTest(size=len(malformed)):
                with self.assertRaises((ValueError, struct.error)):
                    strip(malformed, typ)


if __name__ == "__main__":
    unittest.main()
