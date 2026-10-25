"""Authored IPC witnesses; no SDK-generated shader data in test fixtures."""

import importlib.util
from pathlib import Path
import struct
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/phone-build/owner-code/shader.py"
SPEC = importlib.util.spec_from_file_location("owner_shader", PATH)
SHADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHADER)


def number(value, bits=32):
    return struct.pack("<II" if bits == 32 else "<IQ", 202101220, value)


def string(value):
    data = value.encode()
    return number(len(data), 64) + data


class Stream:
    def __init__(self, data):
        self.data = data
        self.sent = bytearray()

    def recv(self, length):
        part, self.data = self.data[: min(length, 3)], self.data[min(length, 3) :]
        return part

    def sendall(self, data):
        self.sent.extend(data)


class OwnerShaderTests(unittest.TestCase):
    def test_initialization_uses_64_bit_strings_and_all_platform_capabilities(self):
        stream = Stream(string("") + number(1 << 18) + (number(7, 64) + number(0)) * 25)
        capabilities = SHADER.Connection(stream).initialize(["sdk/includes"], {"old": "new"})
        self.assertEqual(capabilities, [(7, 0)] * 25)
        self.assertEqual(
            stream.sent,
            string("c:initializeCompiler") + number(1) + string("sdk/includes") + number(1) + string("old") + string("new") + string("{}"),
        )
        self.assertFalse(stream.data)

    def test_compile_keeps_reflection_diagnostics_and_binary_payload(self):
        payload = b"independently authored opaque shader witness"
        stream = Stream(
            string("input: 0 13")
            + string("err: 0 18 3")
            + string("fixture.hlsl")
            + string("independent warning")
            + string("shader: 1")
            + number(25)
            + number(len(payload), 64)
            + payload
        )
        result = SHADER.Connection(stream).compile("authored source", "fixture.hlsl", stage="fragment", keywords=["FIXTURE"])
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], payload)
        self.assertEqual(result["gpu_program_type"], 25)
        self.assertEqual(result["reflection"], ["input: 0 13"])
        self.assertEqual(result["diagnostics"], [{"location": "err: 0 18 3", "file": "fixture.hlsl", "message": "independent warning"}])
        self.assertIn(number(1) + string("FIXTURE"), stream.sent)
        self.assertTrue(stream.sent.endswith(number(1, 64) + number(2) + number(1)))
        self.assertFalse(stream.data)

    def test_original_disassembly_uses_raw_dxbc_and_reads_terminal_status(self):
        stream = Stream(string("err: 0 4 0") + string("original.dxbc") + string("authored warning") + string("disasm: 1") + string("AUTHORED_ASSEMBLY"))
        self.assertEqual(SHADER.Connection(stream).disassemble(b"DXBC_FIXTURE", 17), "AUTHORED_ASSEMBLY")
        self.assertEqual(
            stream.sent, string("c:disassembleShader") + string("original.dxbc") + number(4) + number(17) + number(0) + number(12, 64) + b"DXBC_FIXTURE"
        )
        self.assertFalse(stream.data)
        with self.assertRaisesRegex(ValueError, "disassembly failed"):
            SHADER.Connection(Stream(string("disasm: 0") + string(""))).disassemble(b"invalid")

    def test_failed_compile_is_not_reported_as_success(self):
        stream = Stream(string("shader: 0") + number(0) + number(0, 64))
        result = SHADER.Connection(stream).compile("invalid source", "fixture.hlsl", stage="vertex")
        self.assertFalse(result["success"])
        self.assertEqual(result["data"], b"")

    def test_preprocess_preserves_source_hash_words_keywords_and_requirements(self):
        fields = [17, 0, 2, 0, 0, 0, -1, 2, 3, 4, 0, 0, 0]
        stream = Stream(
            string("snip: " + " ".join(map(str, fields)))
            + string("independently authored snippet")
            + string("includes: 1")
            + string("sdk/fixture.cginc")
            + string("filepaths: 0")
            + string("keywordsUserGlobal: 17 0 1")
            + string("_ FIXTURE")
            + string("keywordsUserLocal: 17 0 0")
            + string("keywordsBuiltin: 17 0 0")
            + string("keywordsEnd: 17")
            + string("FIXTURE")
            + string("")
            + number(33, 64)
            + number(1)
            + string("FIXTURE")
            + number(65, 64)
            + string("shader: 1 0 0")
            + string("authored parsed ShaderLab")
        )
        result = SHADER.Connection(stream).preprocess(
            "authored ShaderLab", "fixtures/test.shader", platform_keywords=["SHADER_API_MOBILE"], disabled_keywords=["DISABLED"]
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["snippets"], [{"fields": fields, "source": "independently authored snippet"}])
        self.assertEqual(result["shaderlab"], "authored parsed ShaderLab")
        self.assertEqual(result["records"][0], {"kind": "includes", "fields": [], "values": ["sdk/fixture.cginc"]})
        self.assertEqual(
            result["records"][-1],
            {
                "kind": "keywordsEnd",
                "fields": [17],
                "keywords": "FIXTURE",
                "always_included": "",
                "requirements": 33,
                "overrides": [{"keyword": "FIXTURE", "requirements": 65}],
            },
        )
        self.assertEqual(result["diagnostics"], [])
        self.assertFalse(stream.data)
        self.assertEqual(
            stream.sent,
            string("c:preprocess")
            + string("authored ShaderLab")
            + string("fixtures")
            + string("test.shader")
            + number(0)
            + number(0)
            + number(13)
            + number(1 << 18)
            + number(1)
            + string("SHADER_API_MOBILE")
            + number(1)
            + string("DISABLED"),
        )

    def test_preprocess_failure_and_protocol_drift_are_explicit(self):
        stream = Stream(string("err: 0 18 2") + string("test.shader") + string("authored syntax error") + string("shader: 0") + string(""))
        result = SHADER.Connection(stream).preprocess("bad ShaderLab", "test.shader")
        self.assertFalse(result["success"])
        self.assertEqual(result["diagnostics"][0]["message"], "authored syntax error")
        for response, expected in [("snip: 1 2", "metadata differs"), ("includes: -1", "negative"), ("newCallback: 0", "unknown")]:
            with self.subTest(response=response), self.assertRaisesRegex(ValueError, expected):
                SHADER.Connection(Stream(string(response))).preprocess("source", "test.shader")

    def test_preprocess_sends_the_selected_caching_mode(self):
        stream = Stream(string("shader: 1 0 0") + string("authored ShaderLab"))
        result = SHADER.Connection(stream).preprocess("source", "test.shader", caching_preprocessor=True)
        self.assertTrue(result["success"])
        self.assertIn(number(0) + number(1) + number(13) + number(1 << 18), stream.sent)

    def test_old_wire_version_truncation_and_unbounded_length_refuse(self):
        with self.assertRaisesRegex(ValueError, "version differs"):
            SHADER.Connection(Stream(struct.pack("<IQ", 201508070, 0))).buffer()
        with self.assertRaises(EOFError):
            SHADER.Connection(Stream(number(2, 64) + b"a")).buffer()
        with self.assertRaisesRegex(ValueError, "qualified limit"):
            SHADER.Connection(Stream(number(2**32, 64))).buffer()


if __name__ == "__main__":
    unittest.main()
