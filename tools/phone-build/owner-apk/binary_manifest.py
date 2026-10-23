"""Add an authored preparation activity without regenerating game resources.

The caller supplies the repository's existing phone_apk wire reader. Original
resource IDs, attributes and non-launcher nodes retain their indices/bytes.
This is binary structure editing, never exact-text source replacement.
"""

import struct


NONE = 0xFFFFFFFF
ANDROID = "http://schemas.android.com/apk/res/android"
BOOTSTRAP = "dev.ror2owner.bootstrap.PayloadBootstrapActivity"
UNITY = "com.unity3d.player.UnityPlayerActivity"


def string_pool(strings, utf8):
    def length(value, wide=False):
        if value > (0x7FFFFFFF if wide else 0x7FFF):
            raise ValueError("manifest string too long")
        if wide:
            return struct.pack("<H", value) if value < 0x8000 else struct.pack("<HH", 0x8000 | (value >> 16), value & 0xFFFF)
        return bytes([value]) if value < 0x80 else bytes([0x80 | (value >> 8), value & 0xFF])

    data, offsets = bytearray(), []
    for value in strings:
        offsets.append(len(data))
        utf16 = value.encode("utf-16-le")
        if utf8:
            encoded = value.encode("utf-8")
            data += length(len(utf16) // 2) + length(len(encoded)) + encoded + b"\0"
        else:
            data += length(len(utf16) // 2, True) + utf16 + b"\0\0"
    data += b"\0" * (-len(data) % 4)
    start = 28 + 4 * len(strings)
    return (
        struct.pack("<HHIIIIII", 1, 28, start + len(data), len(strings), 0, 0x100 if utf8 else 0, start, 0)
        + b"".join(struct.pack("<I", x) for x in offsets)
        + data
    )


def patch(data, wire):
    if len(data) < 8 or struct.unpack_from("<HHI", data) != (3, 8, len(data)):
        raise ValueError("invalid complete binary Android manifest")
    chunks = list(wire._chunks(data, 8, len(data)))
    pools = [row for row in chunks if row[0] == 1]
    maps = [row for row in chunks if row[0] == 0x180]
    if len(pools) != 1 or len(maps) != 1:
        raise ValueError("manifest requires one string pool and resource map")
    _, start, header, size = pools[0]
    if struct.unpack_from("<I", data, start + 12)[0]:
        raise ValueError("styled manifest strings unsupported")
    strings = list(wire._strings(data, start, header, size))
    original_count = len(strings)
    if BOOTSTRAP in strings:
        raise ValueError("bootstrap already present")

    def index(value):
        if value not in strings:
            strings.append(value)
        return strings.index(value)

    android, activity, name, exported = map(index, (ANDROID, "activity", "name", "exported"))
    bootstrap = index(BOOTSTRAP)

    def attributes(raw):
        _, node_header, node_size = struct.unpack_from("<HHI", raw)
        if node_header != 16 or node_size != len(raw):
            raise ValueError("unsupported manifest element header")
        _, tag, relative, stride, count = struct.unpack_from("<IIHHH", raw, node_header)
        if tag >= original_count or stride != 20 or relative < 20 or node_header + relative + count * stride > len(raw):
            raise ValueError("invalid manifest attribute table")
        found = {}
        for i in range(count):
            ns, attr, raw_value, value_size, reserved, kind, value = struct.unpack_from("<IIIHBBI", raw, node_header + relative + i * stride)
            if attr >= original_count or value_size != 8 or reserved:
                raise ValueError("invalid manifest attribute")
            if ns == android and attr == name and kind == 3 and value < original_count:
                found["name"] = strings[value]
        return strings[tag], found

    roots, stack = [], []
    for kind, offset, node_header, node_size in chunks:
        raw = data[offset : offset + node_size]
        if kind == 0x102:
            tag, attrs = attributes(raw)
            node = {"tag": tag, "attrs": attrs, "start": raw, "children": [], "end": None}
            (stack[-1]["children"] if stack else roots).append(node)
            stack.append(node)
        elif kind == 0x103:
            if not stack or node_header != 16 or node_size != 24 or struct.unpack_from("<I", raw, 20)[0] != struct.unpack_from("<I", stack[-1]["start"], 20)[0]:
                raise ValueError("unbalanced manifest elements")
            stack.pop()["end"] = raw
        else:
            (stack[-1]["children"] if stack else roots).append((kind, raw))
    if stack:
        raise ValueError("unterminated manifest element")
    manifests = [n for n in roots if isinstance(n, dict) and n["tag"] == "manifest"]
    applications = [n for m in manifests for n in m["children"] if isinstance(n, dict) and n["tag"] == "application"]
    activities = [n for app in applications for n in app["children"] if isinstance(n, dict) and n["tag"] == "activity" and n["attrs"].get("name") == UNITY]
    if len(applications) != 1 or len(activities) != 1:
        raise ValueError("expected one original Unity activity")
    filters = []
    for child in activities[0]["children"]:
        if not isinstance(child, dict) or child["tag"] != "intent-filter":
            continue
        names = {n["attrs"].get("name") for n in child["children"] if isinstance(n, dict)}
        if {"android.intent.action.MAIN", "android.intent.category.LAUNCHER"} <= names:
            filters.append(child)
    if len(filters) != 1:
        raise ValueError("expected one original launcher filter")
    activities[0]["children"].remove(filters[0])
    attrs = struct.pack("<IIIHBBI", android, name, bootstrap, 8, 0, 3, bootstrap)
    attrs += struct.pack("<IIIHBBI", android, exported, NONE, 8, 0, 0x12, 1)
    opening = struct.pack("<HHIII", 0x102, 16, 36 + len(attrs), 1, NONE)
    opening += struct.pack("<IIHHHHHH", NONE, activity, 20, 20, 2, 0, 0, 0) + attrs
    closing = struct.pack("<HHIIIII", 0x103, 16, 24, 1, NONE, NONE, activity)
    applications[0]["children"].append({"start": opening, "children": filters, "end": closing})
    _, map_start, map_header, map_size = maps[0]
    if map_header != 8 or (map_size - 8) % 4:
        raise ValueError("invalid Android resource map")
    resources = list(struct.unpack_from("<" + "I" * ((map_size - 8) // 4), data, map_start + 8))
    resources += [0] * max(0, exported + 1 - len(resources))
    if resources[exported] not in (0, 0x01010010):
        raise ValueError("exported attribute resource differs")
    resources[exported] = 0x01010010

    # The public launcher must not permit a cold explicit Unity launch to bypass
    # preparation. Preserve every other original activity attribute/value.
    original = activities[0]["start"]
    node_header = struct.unpack_from("<H", original, 2)[0]
    relative, stride, count = struct.unpack_from("<HHH", original, node_header + 8)
    offset = node_header + relative
    existing = [(i, original[offset + i * stride : offset + (i + 1) * stride]) for i in range(count)]
    value = struct.pack("<IIIHBBI", android, exported, NONE, 8, 0, 0x12, 0)
    exported_rows = [i for i, raw in existing if struct.unpack_from("<II", raw) == (android, exported)]
    if len(exported_rows) > 1:
        raise ValueError("duplicate Unity export attribute")
    if exported_rows:
        existing = [(i, value if i in exported_rows else raw) for i, raw in existing]
    else:
        existing.append((-1, value))
    existing.sort(key=lambda item: resources[struct.unpack_from("<I", item[1], 4)[0]] if struct.unpack_from("<I", item[1], 4)[0] < len(resources) else 0)
    prefix = bytearray(original[:offset])
    struct.pack_into("<H", prefix, node_header + 12, len(existing))
    for special in (node_header + 14, node_header + 16, node_header + 18):
        previous = struct.unpack_from("<H", prefix, special)[0]
        if previous:
            position = next(i + 1 for i, item in enumerate(existing) if item[0] == previous - 1)
            struct.pack_into("<H", prefix, special, position)
    changed = prefix + b"".join(raw for _, raw in existing) + original[offset + count * stride :]
    struct.pack_into("<I", changed, 4, len(changed))
    activities[0]["start"] = bytes(changed)
    pool = string_pool(strings, bool(struct.unpack_from("<I", data, start + 16)[0] & 0x100))
    resource_map = struct.pack("<HHI", 0x180, 8, 8 + 4 * len(resources)) + struct.pack("<" + "I" * len(resources), *resources)

    def encode(node):
        if isinstance(node, tuple):
            return pool if node[0] == 1 else resource_map if node[0] == 0x180 else node[1]
        return node["start"] + b"".join(encode(x) for x in node["children"]) + node["end"]

    body = b"".join(encode(n) for n in roots)
    return struct.pack("<HHI", 3, 8, len(body) + 8) + body
