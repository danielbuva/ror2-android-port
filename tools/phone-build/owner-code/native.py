"""Native x86_64 stage of the Editor-free owner code producer."""

import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]
PROFILE = ROOT / "recipe/owner-native-x86_64.json"
PROFILE_SHA = "0fa7f9bd9ced1befb361dd843931a031cbedeb280b193ba5a424e5a54ebacd1f"

ELF_MACHINES = {62, 183}  # 62 = EM_X86_64, 183 = EM_AARCH64


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_elf_shared_library(target: Path):
    with target.open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01":
        raise ValueError("expected 64-bit little-endian ELF shared library")
    e_type, e_machine = struct.unpack_from("<HH", header, 16)
    if e_type != 3 or e_machine not in ELF_MACHINES:
        raise ValueError(f"expected x86_64 (62) shared ELF library, got type={e_type} machine={e_machine}")
    return True
