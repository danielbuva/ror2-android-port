"""Owner code producer configured for native x86_64 (x64) output."""

from pathlib import Path
import struct

ELF_MACHINES = {62, 183}  # 62 = EM_X86_64


def verify_burst_library(library: Path):
    with library.open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<HH", header, 16)[1] not in ELF_MACHINES:
        raise ValueError("Burst did not produce an x86_64 shared ELF")
    return True
