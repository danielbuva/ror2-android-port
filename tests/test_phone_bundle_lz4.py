"""Public LZ4 build/protocol contracts with authored blocks, no game inputs."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bundle_lz4_builder", ROOT / "tools/phone-build/accepted-output/build_bundle_lz4.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


def request(data, method):
    return struct.pack("<II", len(data), method) + data


def decode(block):
    """Independent block-format decoder for authored roundtrip assertions."""
    output = bytearray()
    cursor = 0

    def length(base):
        nonlocal cursor
        if base == 15:
            while True:
                value = block[cursor]
                cursor += 1
                base += value
                if value != 255:
                    break
        return base

    while cursor < len(block):
        token = block[cursor]
        cursor += 1
        literals = length(token >> 4)
        if cursor + literals > len(block):
            raise ValueError("literal extent")
        output.extend(block[cursor : cursor + literals])
        cursor += literals
        if cursor == len(block):
            break
        offset = struct.unpack_from("<H", block, cursor)[0]
        cursor += 2
        if not 0 < offset <= len(output):
            raise ValueError("match offset")
        for _ in range(length(token & 15) + 4):
            output.append(output[-offset])
    return bytes(output)


class Lz4BuilderAdmissionTests(unittest.TestCase):
    def test_provider_drift_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provider = root / "authored-source"
            provider.write_bytes(b"authored non-provider fixture")
            with self.assertRaisesRegex(ValueError, "provider drift"):
                BUILD.build(provider, provider, root / "output")
            self.assertFalse((root / "output").exists())


class Lz4NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No network or implicit dependency on a private lab output in CI.
        supplied = os.environ.get("ROR2_LZ4_ARCHIVE")
        if not supplied:
            raise unittest.SkipTest("explicit public LZ4 v1.9.4 source archive is absent")
        cls.compiler = Path(os.environ.get("ROR2_LZ4_COMPILER", "/usr/bin/clang"))
        if not cls.compiler.is_file():
            raise unittest.SkipTest("explicit host compiler is absent")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name).resolve()
        cls.archive = Path(supplied)
        cls.result = BUILD.build(cls.archive, cls.compiler, cls.root / "build")
        cls.codec = cls.root / "build/bundle-lz4"

    def run_worker(self, data):
        return subprocess.run([str(self.codec)], input=data, capture_output=True, timeout=20)

    def test_build_receipt_notices_and_repeated_build(self):
        self.assertTrue(self.result["success"])
        self.assertEqual(json.loads((self.root / "build/result.json").read_text()), self.result)
        self.assertEqual(self.result["output_sha256"], BUILD.sha(self.codec))
        self.assertEqual(self.result["inputs"][str(self.archive.resolve())], BUILD.LZ4_SHA)
        self.assertEqual((self.root / "build/LZ4-LICENSE.txt").read_bytes(), (self.root / "build/source/LICENSE").read_bytes())
        self.assertIn("BSD 2-Clause", (self.root / "build/NOTICE.txt").read_text())
        self.assertTrue((self.root / "build/compiler.stdout").is_file())
        self.assertTrue((self.root / "build/compiler.stderr").is_file())
        other = BUILD.build(self.archive, self.compiler, self.root / "repeat")
        self.assertEqual(self.result["output_sha256"], other["output_sha256"])
        with self.assertRaisesRegex(ValueError, "new disjoint"):
            BUILD.build(self.archive, self.compiler, self.root / "build")
        link = self.root / "alias"
        link.symlink_to(self.root / "build", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "new disjoint"):
            BUILD.build(self.archive, self.compiler, link)

    def test_compiler_failure_retains_terminal_result_and_logs(self):
        compiler = self.root / "failing-compiler"
        compiler.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo authored-fixture; exit 0; fi\necho authored-failure >&2\nexit 1\n')
        compiler.chmod(0o755)
        output = self.root / "failed"
        with self.assertRaisesRegex(ValueError, "compilation failed"):
            BUILD.build(self.archive, compiler, output)
        self.assertEqual((output / "compiler.stderr").read_text(), "authored-failure\n")
        result = json.loads((output / "result.json").read_text())
        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 1)
        self.assertTrue((output / "LZ4-LICENSE.txt").is_file())

    def test_known_blocks_and_multiple_requests(self):
        controls = [(b"", b"\0"), (b"abc", b"\x30abc"), (b"a" * 32, bytes.fromhex("1f61010007506161616161"))]
        frames = [(data, method, expected) for method in (2, 3) for data, expected in controls]
        result = self.run_worker(b"".join(request(data, method) for data, method, _ in frames))
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = b"".join(struct.pack("<I", len(block)) + block for _, _, block in frames)
        self.assertEqual(result.stdout, expected)

    def test_distinct_fast_and_hc12_authored_controls(self):
        # Deterministic public fixture: variable-length runs from an LCG.
        seed = 0x12345678
        control = bytearray()
        for _ in range(2048):
            seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
            control.extend(bytes([seed >> 24]) * ((seed & 31) + 1))
        pins = {
            2: "a05fbaba424077757aeeffdb42e930a1198b37a94ef4dbff8bedd853a75544d2",
            3: "8fbf73b8beefe43e07efb33465db24c610f1705263d065c1fde0bebe7e7e3f86",
        }
        for method, pin in pins.items():
            with self.subTest(method=method):
                result = self.run_worker(request(control, method))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(struct.unpack_from("<I", result.stdout)[0], len(result.stdout) - 4)
                block = result.stdout[4:]
                self.assertEqual(hashlib.sha256(block).hexdigest(), pin)
                self.assertEqual(decode(block), control)

    def test_maximum_payload_is_accepted(self):
        data = bytes(64 * 1024 * 1024)
        result = self.run_worker(request(data, 2))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(struct.unpack_from("<I", result.stdout)[0], len(result.stdout) - 4)
        # Avoid expanding a 64 MiB match in the deliberately simple decoder.
        self.assertLess(len(result.stdout), len(data) // 100)

    def test_clean_eof_and_malformed_input(self):
        result = self.run_worker(b"")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        malformed = [b"x" * n for n in range(1, 8)]
        malformed += [struct.pack("<II", 64 * 1024 * 1024 + 1, 2)]
        malformed += [struct.pack("<II", 0xFFFFFFFF, 3)]
        malformed += [request(b"", method) for method in (0, 1, 4, 0xFFFFFFFF)]
        malformed += [struct.pack("<II", 4, 2) + b"abc"]
        for data in malformed:
            with self.subTest(data=data):
                result = self.run_worker(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr)
        result = self.run_worker(request(b"abc", 2) + b"x")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, struct.pack("<I", 4) + b"\x30abc")

    def test_reply_is_flushed_before_next_request(self):
        with subprocess.Popen([str(self.codec)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as worker:
            try:
                worker.stdin.write(request(b"abc", 3))
                worker.stdin.flush()
                self.assertTrue(select.select([worker.stdout], [], [], 5)[0], "reply was buffered until EOF")
                self.assertEqual(worker.stdout.read(8), struct.pack("<I", 4) + b"\x30abc")
                worker.stdin.close()
                self.assertEqual(worker.wait(timeout=5), 0)
            finally:
                if worker.poll() is None:
                    worker.kill()


if __name__ == "__main__":
    unittest.main()
