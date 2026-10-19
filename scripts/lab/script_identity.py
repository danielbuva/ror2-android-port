"""Unity script identities of a precompiled assembly, from the legitimate installation (J597).

Unity names a MonoScript inside a DLL by the assembly importer's GUID and a file ID: the first
four bytes (little-endian int32) of MD4("s\\0\\0\\0" + namespace + class name). This is the rule
the pinned AssetRipper `ScriptHashing.CalculateScriptFileID` (1ac666f) and ThunderKit
`FileIdUtil` replicate (J430). The installation's player data lists every shipped MonoScript,
so no editor is needed to resolve a serialized `m_Script` reference.
"""

import struct

MASK = 0xFFFFFFFF


def _rotate(value, bits):
    return ((value << bits) | (value >> (32 - bits))) & MASK


def md4(data):
    """RFC 1320 MD4; hashlib's OpenSSL backend may not provide it."""
    message = bytearray(data) + b"\x80"
    message += b"\0" * ((56 - len(message)) % 64) + struct.pack("<Q", len(data) * 8)
    state = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
    rounds = (
        (lambda x, y, z: (x & y) | (~x & z), 0, range(16), (3, 7, 11, 19)),
        (lambda x, y, z: (x & y) | (x & z) | (y & z), 0x5A827999, (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15), (3, 5, 9, 13)),
        (lambda x, y, z: x ^ y ^ z, 0x6ED9EBA1, (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15), (3, 9, 11, 15)),
    )
    for offset in range(0, len(message), 64):
        words = struct.unpack("<16I", message[offset : offset + 64])
        a, b, c, d = state
        for function, constant, order, shifts in rounds:
            for step, index in enumerate(order):
                value = _rotate((a + function(b, c, d) + words[index] + constant) & MASK, shifts[step % 4])
                a, b, c, d = d, value, b, c
        state = [(x + y) & MASK for x, y in zip(state, (a, b, c, d))]
    return struct.pack("<4I", *state)


def script_file_id(namespace, name):
    return struct.unpack("<i", md4(b"s\0\0\0" + namespace.encode() + name.encode())[:4])[0]


def installed_scripts(data_directory, assembly):
    """(namespace, class name) of every MonoScript the installation ships for `assembly`."""
    import UnityPy

    scripts = set()
    for item in UnityPy.load(str(data_directory / "globalgamemanagers.assets")).objects:
        if item.type.name == "MonoScript":
            script = item.read()
            if script.m_AssemblyName == assembly:
                scripts.add((script.m_Namespace, script.m_ClassName))
    if not scripts:
        raise RuntimeError("Installation lists no MonoScript for " + assembly)
    return scripts


def identity_rows(data_directory, assembly, guid):
    """`file ID|GUID|full name` rows, the format of the historical moon-script-identities.txt."""
    rows = sorted(
        (script_file_id(namespace, name), (namespace + "." if namespace else "") + name) for namespace, name in installed_scripts(data_directory, assembly)
    )
    if len({file_id for file_id, _ in rows}) != len(rows):
        raise RuntimeError("Script file ID collision in " + assembly)
    return "".join(f"{file_id}|{guid}|{name}\n" for file_id, name in rows)
