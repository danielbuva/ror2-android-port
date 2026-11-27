import hashlib
import importlib.util
import os
import runpy
import struct
import sys
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


def linked_fixture(dependencies, alignment):
    data = bytearray(elf_fixture())
    program_header = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, 0, 0, alignment)
    struct.pack_into("<Q", data, 32, len(data))
    struct.pack_into("<HH", data, 54, len(program_header), 1)
    data.extend(program_header)
    strings = b"\0"
    records = []
    for tag, name in [(14, "libAkSoundEngine.so"), *((1, name) for name in dependencies)]:
        records.append(struct.pack("<qQ", tag, len(strings)))
        strings += name.encode("ascii") + b"\0"
    records.append(bytes(16))
    dynamic = b"".join(records)
    section = struct.Struct("<IIQQQQIIQQ")
    sections = data[64 : 64 + 4 * section.size]
    sections += section.pack(0, 3, 0, 0, len(data), len(strings), 0, 0, 1, 0)
    sections += section.pack(0, 6, 0, 0, len(data) + len(strings), len(dynamic), 4, 0, 8, 16)
    data.extend(strings + dynamic)
    struct.pack_into("<Q", data, 40, len(data))
    struct.pack_into("<H", data, 60, 6)
    return bytes(data) + sections


class WwiseAndroidAbiTests(unittest.TestCase):
    def test_reads_defined_dynamic_functions_and_data(self):
        self.assertEqual(native_exports(elf_fixture()), {"public_fn", "weak_fn", "public_data"})

    def test_rejects_truncated_linked_string_table(self):
        with self.assertRaisesRegex(ValueError, "dynamic string table extent"):
            native_exports(elf_fixture()[:-1])

    def test_native_build_audit_requires_dependencies_and_page_alignment(self):
        owner_code = ROOT / "tools/phone-build/owner-code"
        spec = importlib.util.spec_from_file_location("test_wwise_native", owner_code / "wwise_native.py")
        producer = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(owner_code), *sys.path]):
            spec.loader.exec_module(producer)
        exports = hashlib.sha256(b"public_data\npublic_fn\nweak_fn").hexdigest()
        needed = sorted(producer.DEPENDENCIES)
        with tempfile.TemporaryDirectory() as directory, patch.object(producer, "EXPORTS_SHA256", exports):
            library = Path(directory) / "libAkSoundEngine.so"
            library.write_bytes(linked_fixture(needed, 16384))
            self.assertEqual(producer.audit_library(library)["exports"], 3)
            library.write_bytes(linked_fixture(needed[:-1], 16384))
            with self.assertRaisesRegex(ValueError, "dependencies or SONAME"):
                producer.audit_library(library)
            library.write_bytes(linked_fixture(needed, 4096))
            with self.assertRaisesRegex(ValueError, "16 KiB"):
                producer.audit_library(library)

    def test_plan_output_without_android_hard_links(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(os, "link", None):
            path = Path(directory) / "plan.json"
            ABI["atomic_new"](path, b'{"schema": 1}\n')
            with self.assertRaisesRegex(ValueError, "refusing to overwrite output"):
                ABI["atomic_new"](path, b"replacement")
            self.assertEqual(path.read_bytes(), b'{"schema": 1}\n')
