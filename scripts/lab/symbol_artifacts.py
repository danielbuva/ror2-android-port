"""Host-only validation contract for exact APK/IL2CPP symbol artifact pairing.

Helper for scripts/lab/build.py. It reads APK and symbol ZIP members in
place, never extracts an archive, and fails closed on missing/ambiguous ELF
identities.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path


class SymbolArtifactError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _unpack(fmt: str, data: bytes, offset: int):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise SymbolArtifactError("ELF note/header extends past file")
    return struct.unpack_from(fmt, data, offset)


def _has_dwarf_info(data: bytes, endian: str) -> bool:
    """Require at least one structurally plausible DWARF compilation-unit header."""
    cursor = 0
    found = False
    while cursor + 4 <= len(data):
        initial_length = _unpack(endian + "I", data, cursor)[0]
        if initial_length == 0:
            if any(data[cursor:]):
                return False
            break
        if initial_length == 0xFFFFFFFF:
            if cursor + 12 > len(data):
                return False
            unit_length = _unpack(endian + "Q", data, cursor + 4)[0]
            length_field = 12
            offset_size = 8
        else:
            unit_length = initial_length
            length_field = 4
            offset_size = 4
        unit_start = cursor + length_field
        unit_end = unit_start + unit_length
        if unit_end > len(data) or unit_length < 7:
            return False
        version = _unpack(endian + "H", data, unit_start)[0]
        if version in (2, 3, 4):
            header_size = 2 + offset_size + 1
            if unit_length < header_size:
                return False
            address_size = data[unit_start + header_size - 1]
        elif version == 5:
            header_size = 2 + 2 + offset_size
            if unit_length < header_size:
                return False
            address_size = data[unit_start + 3]
        else:
            return False
        if address_size not in (4, 8):
            return False
        found = True
        cursor = unit_end
    return found


def elf_metadata(data: bytes, *, include_sections: bool = True) -> dict:
    """Read the GNU build ID and named sections from an ELF64 image."""
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2:
        raise SymbolArtifactError("Expected an ELF64 image or debug symbol")
    byte_order = data[5]
    if byte_order not in (1, 2):
        raise SymbolArtifactError("Unsupported ELF byte order")
    endian = "<" if byte_order == 1 else ">"
    if _unpack(endian + "H", data, 18)[0] != 183:  # EM_AARCH64
        raise SymbolArtifactError("Expected an ARM64 ELF image or debug symbol")
    phoff = _unpack(endian + "Q", data, 32)[0]
    phentsize = _unpack(endian + "H", data, 54)[0]
    phnum = _unpack(endian + "H", data, 56)[0]
    if phentsize < 56 or phoff + phentsize * phnum > len(data):
        raise SymbolArtifactError("ELF program-header table is invalid")
    ids = set()
    for index in range(phnum):
        row = phoff + index * phentsize
        p_type = _unpack(endian + "I", data, row)[0]
        if p_type != 4:  # PT_NOTE
            continue
        note_offset = _unpack(endian + "Q", data, row + 8)[0]
        note_size = _unpack(endian + "Q", data, row + 32)[0]
        end = note_offset + note_size
        if end > len(data):
            raise SymbolArtifactError("ELF note segment extends past file")
        cursor = note_offset
        while cursor + 12 <= end:
            namesz, descsz, note_type = _unpack(endian + "III", data, cursor)
            cursor += 12
            name_end = cursor + namesz
            desc_start = (name_end + 3) & ~3
            desc_end = desc_start + descsz
            next_note = (desc_end + 3) & ~3
            if name_end > end or desc_end > end or next_note > end:
                raise SymbolArtifactError("Malformed ELF note")
            name = data[cursor:name_end].rstrip(b"\0")
            desc = data[desc_start:desc_end]
            if name == b"GNU" and note_type == 3 and desc:
                ids.add(desc.hex())
            cursor = next_note
    if len(ids) != 1:
        raise SymbolArtifactError("ELF must contain exactly one GNU build ID")
    if not include_sections:
        return {"build_id": ids.pop(), "sections": {}, "named_symbols": 0}
    shoff = _unpack(endian + "Q", data, 40)[0]
    shentsize = _unpack(endian + "H", data, 58)[0]
    shnum = _unpack(endian + "H", data, 60)[0]
    shstrndx = _unpack(endian + "H", data, 62)[0]
    if shoff == 0 and shnum == 0:
        return {"build_id": ids.pop(), "sections": {}, "named_symbols": 0}
    if shnum == 0 or shstrndx == 0xFFFF or shentsize < 64 or shstrndx >= shnum:
        raise SymbolArtifactError("ELF section table is absent or uses unsupported extended numbering")
    if shoff + shentsize * shnum > len(data):
        raise SymbolArtifactError("ELF section-header table is invalid")
    strings_header = shoff + shstrndx * shentsize
    strings_offset = _unpack(endian + "Q", data, strings_header + 24)[0]
    strings_size = _unpack(endian + "Q", data, strings_header + 32)[0]
    if strings_offset + strings_size > len(data):
        raise SymbolArtifactError("ELF section-name table extends past file")
    strings = data[strings_offset : strings_offset + strings_size]
    sections = {}
    section_rows = []
    debug_info_data = b""
    for index in range(1, shnum):
        row = shoff + index * shentsize
        name_offset = _unpack(endian + "I", data, row)[0]
        section_type = _unpack(endian + "I", data, row + 4)[0]
        section_offset = _unpack(endian + "Q", data, row + 24)[0]
        section_size = _unpack(endian + "Q", data, row + 32)[0]
        section_link = _unpack(endian + "I", data, row + 40)[0]
        section_entry_size = _unpack(endian + "Q", data, row + 56)[0]
        if name_offset >= len(strings):
            raise SymbolArtifactError("ELF section name is out of range")
        name_end = strings.find(b"\0", name_offset)
        if name_end < 0:
            raise SymbolArtifactError("ELF section name is unterminated")
        name = strings[name_offset:name_end].decode("ascii", errors="strict")
        # SHT_NOBITS describes allocated memory, without bytes in the ELF file.
        if section_type != 8 and section_offset + section_size > len(data):
            raise SymbolArtifactError("ELF section extends past file")
        sections[name] = section_size
        if name == ".debug_info":
            debug_info_data = data[section_offset : section_offset + section_size]
        section_rows.append({
            "name": name,
            "type": section_type,
            "offset": section_offset,
            "size": section_size,
            "link": section_link,
            "entry_size": section_entry_size,
        })
    symbol_tables = [row for row in section_rows if row["name"] == ".symtab" and row["type"] == 2]
    named_symbols = 0
    for symtab in symbol_tables:
        if symtab["entry_size"] < 24 or symtab["size"] % symtab["entry_size"] != 0 or symtab["link"] >= shnum:
            continue
        linked = section_rows[symtab["link"] - 1] if symtab["link"] > 0 else None
        if linked is None or linked["type"] != 3:
            continue
        names = data[linked["offset"] : linked["offset"] + linked["size"]]
        for offset in range(symtab["offset"], symtab["offset"] + symtab["size"], symtab["entry_size"]):
            name_offset = _unpack(endian + "I", data, offset)[0]
            section_index = _unpack(endian + "H", data, offset + 6)[0]
            if name_offset == 0 or section_index == 0 or name_offset >= len(names):
                continue
            name_end = names.find(b"\0", name_offset)
            if name_end > name_offset:
                named_symbols += 1
    debug_info_valid = bool(debug_info_data) and _has_dwarf_info(debug_info_data, endian)
    return {
        "build_id": ids.pop(),
        "sections": sections,
        "named_symbols": named_symbols,
        "debug_info_valid": debug_info_valid,
    }


def elf_build_id(data: bytes) -> str:
    """Read a GNU build ID from an ELF64 image/debug symbol file."""
    return elf_metadata(data, include_sections=False)["build_id"]


def _one_member(
    archive: zipfile.ZipFile, predicate, description: str, *,
    max_uncompressed_bytes: int = 512 * 1024 * 1024,
) -> tuple[str, bytes]:
    names = [name for name in archive.namelist() if not name.endswith("/") and predicate(name)]
    if len(names) != 1:
        raise SymbolArtifactError(f"Expected exactly one {description}; found {len(names)}")
    info = archive.getinfo(names[0])
    if info.file_size <= 0 or info.file_size > max_uncompressed_bytes:
        raise SymbolArtifactError(f"{description} has invalid uncompressed size")
    return names[0], archive.read(info)


def verify_apk_symbol_pair(
    apk_path,
    symbols_zip_path,
    *,
    expected_apk_sha256,
    expected_symbols_sha256,
    expected_libil2cpp_sha256,
):
    apk_path, symbols_zip_path = Path(apk_path), Path(symbols_zip_path)
    if any(path.is_symlink() or not path.is_file() for path in (apk_path, symbols_zip_path)):
        raise SymbolArtifactError("APK and symbols ZIP must be regular files")
    hashes = (expected_apk_sha256, expected_symbols_sha256, expected_libil2cpp_sha256)
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None for value in hashes):
        raise SymbolArtifactError("APK, symbols ZIP, and libil2cpp SHA-256 receipts are required")
    apk_hash = sha256_file(apk_path)
    symbols_hash = sha256_file(symbols_zip_path)
    if apk_hash.lower() != expected_apk_sha256.lower():
        raise SymbolArtifactError("APK hash does not match the expected build receipt")
    if symbols_hash.lower() != expected_symbols_sha256.lower():
        raise SymbolArtifactError("symbols ZIP hash does not match the expected build receipt")
    try:
        with zipfile.ZipFile(apk_path) as apk, zipfile.ZipFile(symbols_zip_path) as symbols:
            apk_member, apk_elf = _one_member(
                apk, lambda name: name == "lib/arm64-v8a/libil2cpp.so", "ARM64 APK libil2cpp.so"
            )
            symbols_member, symbols_elf = _one_member(
                symbols,
                lambda name: Path(name).name in ("libil2cpp.so", "libil2cpp.dbg.so", "libil2cpp.sym.so"),
                "ARM64 libil2cpp symbol ELF",
                # Full Unity DWARF is substantially larger than the stripped
                # player library. Keep a finite, separate archive-read bound.
                max_uncompressed_bytes=2 * 1024 * 1024 * 1024,
            )
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise SymbolArtifactError("Could not read APK or symbols ZIP") from error
    apk_build_id = elf_build_id(apk_elf)
    symbol_metadata = elf_metadata(symbols_elf)
    symbols_build_id = symbol_metadata["build_id"]
    if apk_build_id != symbols_build_id:
        raise SymbolArtifactError("APK libil2cpp and symbol ELF build IDs differ")
    if symbol_metadata["named_symbols"] <= 0:
        raise SymbolArtifactError("IL2CPP symbol ELF has no usable named .symtab entries")
    if not symbol_metadata["debug_info_valid"]:
        raise SymbolArtifactError("IL2CPP symbol ELF has no valid .debug_info compilation unit; stripped/public symbols are refused")
    actual_libil2cpp_hash = sha256_bytes(apk_elf)
    if actual_libil2cpp_hash.lower() != expected_libil2cpp_sha256.lower():
        raise SymbolArtifactError("APK libil2cpp SHA-256 does not match the expected build receipt")
    return {
        "schema": 1,
        "apk_sha256": apk_hash,
        "apk_member": apk_member,
        "libil2cpp_build_id": apk_build_id,
        "symbols_zip_sha256": symbols_hash,
        "symbols_member": symbols_member,
        "libil2cpp_sha256": actual_libil2cpp_hash,
        "symbols_has_symtab": True,
        "symbols_has_debug_info": symbol_metadata["debug_info_valid"],
    }


def validate_fresh_symbol_package(reported_path, expected_directory, request_id):
    """Bind Unity's result path to the sole ZIP in this request's fresh output directory."""
    if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", request_id or "") is None:
        raise SymbolArtifactError("Unsafe symbol build request identity")
    expected_directory = Path(expected_directory)
    if expected_directory.name != "symbols-" + request_id:
        raise SymbolArtifactError("Expected symbol output directory is not request-scoped")
    if expected_directory.is_symlink() or not expected_directory.is_dir():
        raise SymbolArtifactError("Fresh symbol output directory is missing or a symlink")
    if not expected_directory.is_absolute() or expected_directory.resolve(strict=True) != expected_directory:
        raise SymbolArtifactError("Fresh symbol output directory must be canonical")
    reported = Path(reported_path) if isinstance(reported_path, str) else Path("")
    if not reported.is_absolute() or reported.is_symlink() or not reported.is_file():
        raise SymbolArtifactError("Unity symbol package path must be an absolute regular file")
    expected_real = expected_directory.resolve(strict=True)
    reported_real = reported.resolve(strict=True)
    if reported.parent != expected_directory or reported_real.parent != expected_real:
        raise SymbolArtifactError("Unity symbol package escaped its request output directory")
    zips = list(expected_directory.glob("*.zip"))
    if len(zips) != 1 or zips[0].is_symlink() or zips[0].resolve(strict=True) != reported_real:
        raise SymbolArtifactError("Expected exactly the returned ZIP in this request output directory")
    return zips[0]


def verify_cached_symbol_receipt(receipt_path, cache_root):
    """Validate an opt-in debugging-symbol cache receipt; never accepts APK-only fallback."""
    receipt_path, cache_root = Path(receipt_path), Path(cache_root).resolve()
    if receipt_path.is_symlink():
        raise SymbolArtifactError("Symbol build-cache receipt must not be a symlink")
    try:
        row = json.loads(receipt_path.read_text())
    except (OSError, ValueError) as error:
        raise SymbolArtifactError("Could not read symbol build-cache receipt") from error
    if row.get("success") is not True or row.get("errors", 0) != 0:
        raise SymbolArtifactError("Cached symbol build is not a successful build")
    if row.get("android_symbols") != "debugging":
        raise SymbolArtifactError("Cached build did not request debugging symbols")
    apk_rel, symbols_rel = row.get("apk_cache_path"), row.get("symbols_zip_cache_path")
    if not isinstance(apk_rel, str) or not isinstance(symbols_rel, str):
        raise SymbolArtifactError("Cache receipt must use relative APK and symbols paths")
    apk_candidate, symbols_candidate = cache_root / apk_rel, cache_root / symbols_rel
    if apk_candidate.is_symlink() or symbols_candidate.is_symlink():
        raise SymbolArtifactError("Cached APK and symbols ZIP must not be symlinks")
    apk, symbols = apk_candidate.resolve(), symbols_candidate.resolve()
    if not apk.is_relative_to(cache_root) or not symbols.is_relative_to(cache_root):
        raise SymbolArtifactError("Cached build artifact escapes its cache directory")
    pair = verify_apk_symbol_pair(
        apk,
        symbols,
        expected_apk_sha256=row.get("apk_sha256"),
        expected_symbols_sha256=row.get("symbols_zip_sha256"),
        expected_libil2cpp_sha256=row.get("libil2cpp_sha256"),
    )
    if row.get("libil2cpp_build_id") != pair["libil2cpp_build_id"]:
        raise SymbolArtifactError("Receipt libil2cpp Build ID does not match its artifacts")
    return pair
