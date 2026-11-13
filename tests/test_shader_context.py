"""Authored Shader pass-key slot contract; no SDK or compiler is needed."""

import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/phone-build/accepted-output"))
import shader_context as C

spec = importlib.util.spec_from_file_location("shader_key_fixture", ROOT / "tests/test_phone_mesh_producer.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def fixture():
    shader_pass = F.node(
        "data",
        children=[F.node("m_State", children=[F.node("gpuProgramID", 4)]), F.array("m_EditorDataHash", F.node("data", 16)), F.node("untouched_state", 4)],
    )
    root = F.node(
        "Base",
        children=[
            F.node("m_ParsedForm", children=[F.array("m_SubShaders", F.node("data", children=[F.array("m_Passes", shader_pass)]))]),
            F.array("compressedBlob", F.node("data", 1)),
            F.node("tail", 8),
        ],
    )
    body = struct.pack("<III", 1, 2, 17) + F.vector(b"A" * 16, 1) + b"keep"
    body += struct.pack("<I", 29) + F.vector(b"B" * 16, 1) + b"stay"
    body += F.vector(b"authored program payload: " + b"A" * 16, 41) + b"tailkeep"
    return body, root


class ShaderContextTests(unittest.TestCase):
    def test_only_declared_key_slots_change(self):
        body, root = fixture()
        spans = C.key_spans(body, root)
        result = C.replace_keys(body, root, {17: b"C" * 16, 29: b"D" * 16})
        self.assertEqual(len(body), len(result))
        for identity, (start, end) in spans.items():
            self.assertEqual(result[start:end], (b"C" if identity == 17 else b"D") * 16)
        left, right = bytearray(body), bytearray(result)
        for start, end in spans.values():
            left[start:end] = right[start:end] = bytes(end - start)
        self.assertEqual(left, right)
        self.assertIn(b"authored program payload: " + b"A" * 16, result)

    def test_missing_or_extra_snippet_keys_are_refused(self):
        body, root = fixture()
        for keys in ({17: b"C" * 16}, {17: b"C" * 16, 29: b"D" * 16, 30: b"E" * 16}):
            with self.assertRaisesRegex(ValueError, "coverage"):
                C.replace_keys(body, root, keys)


if __name__ == "__main__":
    unittest.main()
