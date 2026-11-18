import os
import runpy
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ABI = runpy.run_path(str(ROOT / "tools/wwise-android-abi/generate.py"))
native_exports = ABI["native_exports"]


def elf_fixture():
    strings = b"\0public_fn@@V1\0weak_fn\0public_data\0imported_fn\0"
    symbol = struct.Struct("<IBBHQQ")
    symbols = bytes(symbol.size) + b"".join(
        symbol.pack(strings.index(name), binding_and_type, 0, section, 0, 0)
        for name, binding_and_type, section in (
            (b"public_fn", 0x12, 3),
            (b"weak_fn", 0x22, 3),
            (b"public_data", 0x11, 3),
            (b"imported_fn", 0x12, 0),
        )
    )
    section = struct.Struct("<IIQQQQIIQQ")
    section_offset = 64
    symbols_offset = section_offset + 4 * section.size
    strings_offset = symbols_offset + len(symbols)
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHI", header, 16, 3, 183, 1)
    struct.pack_into("<Q", header, 40, section_offset)
    struct.pack_into("<HH", header, 58, section.size, 4)
    sections = (
        bytes(section.size)
        + section.pack(0, 11, 0, 0, symbols_offset, len(symbols), 2, 1, 8, symbol.size)
        + section.pack(0, 3, 0, 0, strings_offset, len(strings), 0, 0, 1, 0)
        + section.pack(0, 1, 0, 0, strings_offset + len(strings), 0, 0, 0, 1, 0)
    )
    return bytes(header) + sections + symbols + strings


class WwiseAndroidAbiTests(unittest.TestCase):
    def test_reads_defined_dynamic_functions_and_data(self):
        self.assertEqual(native_exports(elf_fixture()), {"public_fn", "weak_fn", "public_data"})

    def test_rejects_truncated_linked_string_table(self):
        with self.assertRaisesRegex(ValueError, "dynamic string table extent"):
            native_exports(elf_fixture()[:-1])

    def test_plan_output_without_android_hard_links(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(os, "link", None):
            path = Path(directory) / "plan.json"
            ABI["atomic_new"](path, b'{"schema": 1}\n')
            with self.assertRaisesRegex(ValueError, "refusing to overwrite output"):
                ABI["atomic_new"](path, b"replacement")
            self.assertEqual(path.read_bytes(), b'{"schema": 1}\n')
