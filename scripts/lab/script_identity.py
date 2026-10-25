"""Unity script identities of a precompiled assembly, from the legitimate installation (J597).

Unity names a MonoScript inside a DLL by the assembly importer's GUID and a file ID: the first
four bytes (little-endian int32) of MD4("s\\0\\0\\0" + namespace + class name). This is the rule
the pinned AssetRipper `ScriptHashing.CalculateScriptFileID` (1ac666f) and ThunderKit
`FileIdUtil` replicate (J430). The installation's player data lists every shipped MonoScript,
so no editor is needed to resolve a serialized `m_Script` reference.
"""

import struct

MASK = 0xFFFFFFFF

# Standard Unity type-tree strings used by the admitted 2021.3 script schemas.
# Pinned UnityPy 1.25.3 TypeTreeNode/Tpk documents the offset convention; these
# are native serialization vocabulary, never game field names or type trees.
COMMON = {
    0: "AABB",
    19: "AnimationCurve",
    49: "Array",
    55: "Base",
    60: "BitField",
    81: "char",
    86: "ColorRGBA",
    106: "data",
    117: "double",
    161: "float",
    172: "GameObject",
    222: "int",
    226: "list",
    245: "Matrix4x4f",
    263: "MonoBehaviour",
    299: "m_Curve",
    307: "m_EditorClassIdentifier",
    331: "m_EditorHideFlags",
    349: "m_Enabled",
    374: "m_GameObject",
    387: "m_Index",
    427: "m_Name",
    434: "m_ObjectHideFlags",
    490: "m_Script",
    519: "m_Type",
    526: "m_Version",
    564: "PPtr<GameObject>",
    616: "PPtr<MonoScript>",
    646: "PPtr<Prefab>",
    741: "Quaternionf",
    753: "Rectf",
    767: "RectOffset",
    795: "size",
    800: "SInt16",
    814: "SInt64",
    821: "SInt8",
    840: "string",
    907: "UInt16",
    921: "UInt64",
    928: "UInt8",
    934: "unsigned int",
    981: "vector",
    988: "Vector2f",
    997: "Vector3f",
    1006: "Vector4f",
    1042: "Gradient",
    1057: "int2_storage",
    1093: "m_CorrespondingSourceObject",
    1121: "m_PrefabInstance",
    1138: "m_PrefabAsset",
}


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


def tree_nodes(blob):
    """Decode embedded v22 type metadata without a UnityPy/Editor dependency."""
    if len(blob) < 8:
        raise ValueError("truncated script schema")
    count, length = struct.unpack_from("<II", blob)
    end = 8 + count * 32
    if not 0 < count <= 100000 or len(blob) != end + length:
        raise ValueError("invalid script schema extent")
    strings = blob[end:]

    def label(offset):
        if offset & 0x80000000:
            try:
                return COMMON[offset & 0x7FFFFFFF]
            except KeyError as error:
                raise ValueError("unqualified script common string") from error
        stop = strings.find(b"\0", offset)
        if offset >= length or stop < 0:
            raise ValueError("script schema string outside table")
        return strings[offset:stop].decode("utf-8")

    nodes = []
    previous = -1
    for version, level, flags, kind, name, size, _, meta, _ in struct.iter_unpack("<hBBIIiiiQ", blob[8:end]):
        if (not nodes and level) or (nodes and (not level or level > previous + 1)):
            raise ValueError("invalid script schema nesting")
        nodes.append({"version": version, "level": level, "flags": flags, "type": label(kind), "name": label(name), "size": size, "meta": meta})
        previous = level
    return nodes


def properties_hash(class_name, namespace, assembly_name, original_tree, sdk_tree):
    """Hash source custom fields with the SDK's editor MonoBehaviour base.

    Unity 2021.3's script hash uses the editor (flags=0) schema, rather than
    the player's release schema. All native node values come from the supplied
    SDK; all custom node values come from original PC type metadata.
    """
    original, native = tree_nodes(original_tree), tree_nodes(sdk_tree)
    for nodes in (original, native):
        if nodes[0]["type"] != "MonoBehaviour" or nodes[0]["name"] != "Base":
            raise ValueError("script schema is not MonoBehaviour")
    cutoff = next((i for i, node in enumerate(native) if node["level"] == 1 and node["name"] == "m_EditorClassIdentifier"), None)
    if cutoff is None:
        raise ValueError("SDK editor script base absent")
    cutoff += 1
    while cutoff < len(native) and native[cutoff]["level"] > 1:
        cutoff += 1
    native = native[:cutoff]
    names = {node["name"] for node in native if node["level"] == 1}
    custom, retain = [], False
    for node in original[1:]:
        if node["level"] == 1:
            retain = node["name"] not in names
        if retain:
            custom.append(node)
    data = bytearray((class_name + namespace + assembly_name).encode("utf-8"))
    for node in native + custom:
        data += node["type"].encode("utf-8") + node["name"].encode("utf-8")
        data += struct.pack("<iiiI", node["size"], node["flags"], node["version"], node["meta"] & 0x4000)
    return md4(data)


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
