import hashlib
import json
import struct
import tempfile
import unittest
import zipfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from symbol_artifacts import SymbolArtifactError, elf_build_id, validate_fresh_symbol_package, verify_apk_symbol_pair, verify_cached_symbol_receipt


def elf_with_build_id(build_id: bytes, *, debug_sections: bool = True) -> bytes:
    """Synthetic ELF64 LE with a GNU Build ID and optional symbol/debug sections."""
    note = struct.pack("<III", 4, len(build_id), 3) + b"GNU\0"
    note += b"\0" * ((-len(note)) % 4) + build_id
    note += b"\0" * ((-len(note)) % 4)
    phoff, phentsize, phnum = 64, 56, 1
    header = bytearray(64)
    header[:16] = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\0" * 8
    struct.pack_into("<HHI", header, 16, 3, 183, 1)
    struct.pack_into("<Q", header, 32, phoff)
    struct.pack_into("<H", header, 54, phentsize)
    struct.pack_into("<H", header, 56, phnum)
    ph = bytearray(phentsize)
    struct.pack_into("<I", ph, 0, 4)
    struct.pack_into("<Q", ph, 8, phoff + phentsize)
    struct.pack_into("<Q", ph, 32, len(note))
    data = bytearray(header + ph + note)
    if not debug_sections:
        return bytes(data)
    data.extend(b"\0" * ((-len(data)) % 8))
    symtab_offset = len(data)
    symtab = bytearray(48)
    struct.pack_into("<IBBHQQ", symtab, 24, 1, 0x12, 0, 1, 0x1000, 4)
    data.extend(symtab)
    debug_offset = len(data)
    debug_unit = struct.pack("<I", 8) + struct.pack("<H", 4) + b"\0" * 4 + b"\x08\0"
    data.extend(debug_unit + b"\0" * (24 - len(debug_unit)))
    symbol_names = b"\0sample_function\0"
    symbol_names_offset = len(data)
    data.extend(symbol_names)
    names = b"\0.symtab\0.debug_info\0.strtab\0.shstrtab\0"
    names_offset = len(data)
    data.extend(names)
    shoff = (len(data) + 7) & ~7
    data.extend(b"\0" * (shoff - len(data)))
    sections = bytearray(5 * 64)
    struct.pack_into("<IIQQQQIIQQ", sections, 64, 1, 2, 0, 0, symtab_offset, 48, 3, 1, 8, 24)
    struct.pack_into("<IIQQQQIIQQ", sections, 128, 9, 1, 0, 0, debug_offset, 24, 0, 0, 1, 0)
    struct.pack_into("<IIQQQQIIQQ", sections, 192, 21, 3, 0, 0, symbol_names_offset, len(symbol_names), 0, 0, 1, 0)
    struct.pack_into("<IIQQQQIIQQ", sections, 256, 29, 3, 0, 0, names_offset, len(names), 0, 0, 1, 0)
    data.extend(sections)
    struct.pack_into("<Q", data, 40, shoff)
    struct.pack_into("<H", data, 58, 64)
    struct.pack_into("<H", data, 60, 5)
    struct.pack_into("<H", data, 62, 4)
    return bytes(data)


def write_zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members:
            archive.writestr(name, data)


class SymbolArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apk = self.root / "app.apk"
        self.symbols = self.root / "symbols.zip"
        self.build_id = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        self.apk_elf = elf_with_build_id(self.build_id, debug_sections=False)
        self.symbol_elf = elf_with_build_id(self.build_id)
        write_zip(self.apk, [("lib/arm64-v8a/libil2cpp.so", self.apk_elf)])
        write_zip(self.symbols, [("arm64-v8a/libil2cpp.so", self.symbol_elf)])

    def tearDown(self):
        self.temp.cleanup()

    def verify_pair(self, *, apk_hash=None, symbols_hash=None, lib_hash=None):
        return verify_apk_symbol_pair(
            self.apk,
            self.symbols,
            expected_apk_sha256=apk_hash if apk_hash is not None else hashlib.sha256(self.apk.read_bytes()).hexdigest(),
            expected_symbols_sha256=symbols_hash if symbols_hash is not None else hashlib.sha256(self.symbols.read_bytes()).hexdigest(),
            expected_libil2cpp_sha256=lib_hash if lib_hash is not None else hashlib.sha256(self.apk_elf).hexdigest(),
        )

    def test_accepts_exact_arm64_debugging_symbol_pair(self):
        result = self.verify_pair()
        self.assertEqual(result["libil2cpp_build_id"], self.build_id.hex())
        self.assertEqual(result["apk_sha256"], hashlib.sha256(self.apk.read_bytes()).hexdigest())
        self.assertTrue(result["symbols_has_symtab"])
        self.assertTrue(result["symbols_has_debug_info"])

    def test_accepts_nobits_memory_extent_without_file_payload(self):
        image = bytearray(self.symbol_elf)
        shoff = struct.unpack_from("<Q", image, 40)[0]
        # Add an unnamed .bss-style section whose memory extent has no file bytes.
        section = struct.pack("<IIQQQQIIQQ", 0, 8, 3, 0x4000,
                              len(image) + 4096, 16384, 0, 0, 8, 0)
        image.extend(section)
        struct.pack_into("<H", image, 60, 6)
        write_zip(self.symbols, [("arm64-v8a/libil2cpp.so", bytes(image))])
        self.assertTrue(self.verify_pair()["symbols_has_debug_info"])
        # The same out-of-file extent is invalid for a file-backed section.
        struct.pack_into("<I", image, shoff + 5 * 64 + 4, 1)
        write_zip(self.symbols, [("arm64-v8a/libil2cpp.so", bytes(image))])
        with self.assertRaisesRegex(SymbolArtifactError, "section extends past file"):
            self.verify_pair()

    def test_refuses_different_symbol_build_id(self):
        write_zip(self.symbols, [("arm64-v8a/libil2cpp.so", elf_with_build_id(b"X" * 20))])
        with self.assertRaisesRegex(SymbolArtifactError, "build IDs differ"):
            self.verify_pair()

    def test_refuses_stripped_artifact_with_matching_build_id(self):
        write_zip(self.symbols, [("arm64-v8a/libil2cpp.so", self.apk_elf)])
        with self.assertRaisesRegex(SymbolArtifactError, "no usable named .symtab"):
            self.verify_pair()

    def test_refuses_missing_or_ambiguous_symbol_elf(self):
        write_zip(self.symbols, [("arm64-v8a/libunity.so", self.symbol_elf)])
        with self.assertRaisesRegex(SymbolArtifactError, "exactly one"):
            self.verify_pair()
        write_zip(self.symbols, [("a/libil2cpp.so", self.symbol_elf), ("b/libil2cpp.so", self.symbol_elf)])
        with self.assertRaisesRegex(SymbolArtifactError, "exactly one"):
            self.verify_pair()

    def test_refuses_non_arm64_symbol_elf(self):
        x86_elf = bytearray(self.symbol_elf)
        struct.pack_into("<H", x86_elf, 18, 62)
        with self.assertRaisesRegex(SymbolArtifactError, "ARM64"):
            elf_build_id(bytes(x86_elf))

    def test_refuses_missing_hash_receipts_and_libil2cpp_hash_drift(self):
        with self.assertRaisesRegex(SymbolArtifactError, "SHA-256 receipts are required"):
            verify_apk_symbol_pair(
                self.apk,
                self.symbols,
                expected_apk_sha256=None,
                expected_symbols_sha256="0" * 64,
                expected_libil2cpp_sha256="0" * 64,
            )
        with self.assertRaisesRegex(SymbolArtifactError, "libil2cpp SHA-256"):
            self.verify_pair(lib_hash="0" * 64)

    def test_refuses_receipt_hash_drift(self):
        with self.assertRaisesRegex(SymbolArtifactError, "symbols ZIP hash"):
            self.verify_pair(symbols_hash="0" * 64)
        with self.assertRaisesRegex(SymbolArtifactError, "APK hash"):
            self.verify_pair(apk_hash="0" * 64)

    def test_symbol_cache_receipt_requires_all_artifacts_and_hashes(self):
        cache = self.root / "cache"
        cache.mkdir()
        apk, symbols = cache / "app.apk", cache / "symbols.zip"
        write_zip(apk, [("lib/arm64-v8a/libil2cpp.so", self.apk_elf)])
        write_zip(symbols, [("arm64-v8a/libil2cpp.so", self.symbol_elf)])
        row = {
            "success": True,
            "errors": 0,
            "android_symbols": "debugging",
            "apk_cache_path": apk.name,
            "symbols_zip_cache_path": symbols.name,
            "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "symbols_zip_sha256": hashlib.sha256(symbols.read_bytes()).hexdigest(),
            "libil2cpp_sha256": hashlib.sha256(self.apk_elf).hexdigest(),
            "libil2cpp_build_id": self.build_id.hex(),
        }
        receipt = cache / "result.json"
        receipt.write_text(json.dumps(row))
        verify_cached_symbol_receipt(receipt, cache)
        row.pop("symbols_zip_sha256")
        receipt.write_text(json.dumps(row))
        with self.assertRaisesRegex(SymbolArtifactError, "SHA-256 receipts are required"):
            verify_cached_symbol_receipt(receipt, cache)

    def test_fresh_package_must_be_the_only_zip_under_request_directory(self):
        request_id = "20261020T123456.123456Z"
        expected = (self.root / ("symbols-" + request_id)).resolve()
        expected.mkdir()
        package = expected / "symbols.zip"
        package.write_bytes(b"zip")
        self.assertEqual(validate_fresh_symbol_package(str(package), expected, request_id), package)
        outside = self.root / "elsewhere.zip"
        outside.write_bytes(b"zip")
        with self.assertRaisesRegex(SymbolArtifactError, "escaped"):
            validate_fresh_symbol_package(str(outside), expected, request_id)
        extra = expected / "second.zip"
        extra.write_bytes(b"zip")
        with self.assertRaisesRegex(SymbolArtifactError, "exactly the returned ZIP"):
            validate_fresh_symbol_package(str(package), expected, request_id)

    def test_fresh_package_refuses_symlinks(self):
        request_id = "request-one"
        expected = (self.root / ("symbols-" + request_id)).resolve()
        expected.mkdir()
        target = self.root / "outside.zip"
        target.write_bytes(b"zip")
        package = expected / "symbols.zip"
        package.symlink_to(target)
        with self.assertRaisesRegex(SymbolArtifactError, "regular file"):
            validate_fresh_symbol_package(str(package), expected, request_id)


if __name__ == "__main__":
    unittest.main()
