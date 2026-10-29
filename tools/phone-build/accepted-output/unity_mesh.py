"""Produce mesh bodies from owner input, without the Unity Editor or UnityPy.

The embedded source type tree supplies field extents. Untouched fields retain
their original bytes. Operations are import settings, collision-cache removal,
stream inlining/relocation and normal/tangent half conversion, never geometry
literals from an Android target.
"""

import io
import importlib.util
import math
from pathlib import Path
import struct


_spec = importlib.util.spec_from_file_location("_mesh_bundle", Path(__file__).with_name("unity_bundle.py"))
_bundle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bundle)
LIMIT, align, exact, string, unpack = _bundle.LIMIT, _bundle.align, _bundle.exact, _bundle.string, _bundle.unpack


class Node:
    def __init__(self, level, flags, kind, name, size, meta):
        self.level, self.flags, self.kind, self.name, self.size, self.meta = level, flags, kind, name, size, meta
        self.children = []
        self.extents = {}


def fixed_end(node, start):
    """Declared byte sizes omit some descendant alignment (e.g. blend shapes)."""
    residue = start % 4
    if residue in node.extents:
        length = node.extents[residue]
        return None if length is None else start + length
    cursor = start
    if node.flags & 1:
        cursor = None
    elif node.children:
        for child in node.children:
            cursor = fixed_end(child, cursor)
            if cursor is None:
                break
    elif node.size >= 0:
        cursor += node.size
    else:
        cursor = None
    if cursor is not None and node.meta & 0x4000:
        cursor = (cursor + 3) // 4 * 4
    node.extents[residue] = None if cursor is None else cursor - start
    return cursor


def type_tree(stream):
    count, length = unpack(stream, "<II")
    if not 0 < count <= 100000 or length > LIMIT:
        raise ValueError("invalid embedded type tree")
    raw = exact(stream, count * 32)
    strings = exact(stream, length)
    # These common names identify generic Unity fields, not game declarations.
    common = {49: "Array", 427: "m_Name", 840: "string", 894: "TypelessData"}

    def label(offset):
        if offset & 0x80000000:
            return common.get(offset & 0x7FFFFFFF, "#" + str(offset & 0x7FFFFFFF))
        if offset >= length or strings.find(b"\0", offset) < 0:
            raise ValueError("escaped type-tree string")
        return strings[offset : strings.index(b"\0", offset)].decode("utf-8")

    stack = []
    root = None
    for _, level, flags, kind, name, size, _, meta, _ in struct.iter_unpack("<HBBIIiiiQ", raw):
        node = Node(level, flags, label(kind), label(name), size, meta)
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            if stack[-1].level + 1 != level:
                raise ValueError("type-tree level gap")
            stack[-1].children.append(node)
        elif root is not None or level != 0:
            raise ValueError("ambiguous type-tree root")
        else:
            root = node
        stack.append(node)
    return root


def mesh_objects(member):
    """Return only Mesh object extents and their source-owned embedded schema."""
    header = exact(member, 48)
    _, _, version, _ = struct.unpack_from(">IIII", header)
    metadata_size, file_size, data_offset = struct.unpack_from(">Iqq", header, 20)
    if version != 22 or header[16] != 0 or file_size != member.size or not 48 + metadata_size <= data_offset <= file_size:
        raise ValueError("unqualified serialized-file header")
    stream = io.BytesIO(exact(member, metadata_size))
    if not string(stream).startswith("2021.3."):
        raise ValueError("unqualified serialized engine")
    unpack(stream, "<i")  # original build platform
    if exact(stream, 1) != b"\1":
        raise ValueError("embedded type tree required")
    (count,) = unpack(stream, "<I")
    if count > 10000:
        raise ValueError("excessive serialized type count")
    types = []
    for _ in range(count):
        class_id, _, _ = unpack(stream, "<iBh")
        exact(stream, 32 if class_id == 114 else 16)
        tree = type_tree(stream)
        (dependencies,) = unpack(stream, "<I")
        exact(stream, dependencies * 4)
        types.append((class_id, tree))
    (count,) = unpack(stream, "<I")
    if count > 2000000:
        raise ValueError("excessive serialized object count")
    result = {}
    identities = set()
    for _ in range(count):
        align(stream)
        path_id, offset, size, type_id = unpack(stream, "<qqIi")
        if path_id in identities or not 0 <= type_id < len(types) or offset < 0 or data_offset + offset + size > file_size:
            raise ValueError("invalid serialized object extent")
        identities.add(path_id)
        class_id, tree = types[type_id]
        if class_id == 43:
            result[path_id] = (data_offset + offset, size, tree)
    return result


def spans(body, root):
    """Walk dynamic fields but skip fixed-size array elements in constant time."""
    result = {}
    cursor = 0

    def walk(node, path):
        nonlocal cursor
        start = cursor
        if node.flags & 1:
            if len(node.children) != 2:
                raise ValueError("invalid array type tree")
            (count,) = struct.unpack_from("<I", body, cursor)
            cursor += 4
            element = node.children[1]
            if count > LIMIT:
                raise ValueError("excessive array count")
            data_start = cursor
            end = fixed_end(element, cursor)
            if end is not None:
                stride = end - cursor
                # A nonaligned element containing padding can change stride on
                # its second iteration. Ordinary byte arrays have no padding.
                following = fixed_end(element, end)
                if count > 1 and following - end != stride:
                    for _ in range(count):
                        walk(element, ())
                else:
                    cursor += count * stride
            else:
                for _ in range(count):
                    walk(element, ())
            result[path + ("payload",)] = (data_start, cursor)
        elif fixed_end(node, cursor) is not None:
            cursor = fixed_end(node, cursor)
        else:
            for child in node.children:
                walk(child, path + (child.name,))
        if node.meta & 0x4000:
            cursor = (cursor + 3) // 4 * 4
        if cursor > len(body) or cursor < start:
            raise ValueError("field exceeds source body")
        if path:
            result[path] = (start, cursor)

    # The root has no serialized prefix of its own.
    for child in root.children:
        walk(child, (child.name,))
    if cursor != len(body):
        raise ValueError("unparsed mesh bytes")
    return result


def half(word):
    """Float32 -> binary16, halfway away from zero (accepted import rule)."""
    sign = (word >> 16) & 0x8000
    magnitude = word & 0x7FFFFFFF
    exponent = (magnitude >> 23) - 127
    if exponent > 15:
        raise ValueError("nonfinite or overflowing vertex attribute")
    if exponent < -25:
        return sign
    if exponent < -14:
        mantissa = (magnitude & 0x7FFFFF) | 0x800000
        shift = -exponent - 1
        return sign | ((mantissa + (1 << (shift - 1))) >> shift)
    return sign | ((magnitude + 0x1000 - 0x38000000) >> 13)


def half_attributes(data, channels, count):
    sizes = (4, 2, 1, 1, 2, 2, 1, 1, 2, 2, 4, 4)
    active = [(i, list(ch)) for i, ch in enumerate(struct.iter_unpack("<4B", channels)) if ch[3] & 15]
    if any(ch[0] != 0 or ch[2] >= len(sizes) for _, ch in active):
        raise ValueError("unqualified vertex stream")
    before = max(ch[1] + sizes[ch[2]] * (ch[3] & 15) for _, ch in active)
    if len(data) != count * before:
        raise ValueError("vertex stream size differs")
    revised = bytearray(channels)
    after = 0
    for index, channel in active:
        _, _, fmt, dimension = channel
        dimension &= 15
        if index in (1, 2):
            if fmt != 0 or dimension not in (3, 4):
                raise ValueError("half conversion requires float normals/tangents")
            fmt, dimension = 1, 52 if index == 1 and dimension == 3 else 4
        revised[index * 4 : index * 4 + 4] = bytes((0, after, fmt, dimension))
        after += sizes[fmt] * (dimension & 15)
    output = bytearray(count * after)
    for vertex in range(count):
        for index, channel in active:
            source = vertex * before + channel[1]
            destination = vertex * after + revised[index * 4 + 1]
            dimension = channel[3] & 15
            if index in (1, 2):
                words = struct.unpack_from("<" + "I" * dimension, data, source)
                if dimension == 3:
                    words += (0,)
                struct.pack_into("<4H", output, destination, *(half(word) for word in words))
            else:
                size = sizes[channel[2]] * dimension
                output[destination : destination + size] = data[source : source + size]
    return bytes(output), bytes(revised)


def padded_string(value):
    data = value.encode("utf-8")
    return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)


def normalize_packed_tangents(data, count, bits, minimum, extent):
    """Reconstruct negative-Z tangent pairs on the unit circle and repack XY.

    Source packed fields and float32 operations determine every value. This is
    the native compressed-vector repair, not tangent generation from geometry.
    """
    if not 0 < count <= LIMIT or count % 2 or not 0 < bits <= 24 or len(data) != (count * bits + 7) // 8 or not extent > 0:
        raise ValueError("invalid packed tangent vector")

    def f(value):
        return struct.unpack("<f", struct.pack("<f", value))[0]

    mask = (1 << bits) - 1
    packed = int.from_bytes(data, "little")
    denominator = f(f(1.0 / extent) * mask)
    values = [f(f(((packed >> (i * bits)) & mask) / denominator) + minimum) for i in range(count)]
    normalized = []
    for x, y in zip(values[::2], values[1::2], strict=True):
        zsqr = f(f(1 - f(x * x)) - f(y * y))
        if zsqr < 0:
            length = f(math.sqrt(f(f(x * x) + f(y * y))))
            x, y = f(x / length), f(y / length)
        normalized.extend((x, y))
    minimum = min(normalized)
    extent = f(max(normalized) - minimum)
    integers = [int(f(f(f(value - minimum) / extent) * mask) + 0.5) for value in normalized]
    packed = sum(value << (i * bits) for i, value in enumerate(integers))
    return minimum, extent, packed.to_bytes(len(data), "little")


def transform(body, root, ops, vertex_stream=None, obj_import=None):
    fields = spans(body, root)
    edits = {}

    def field(*path):
        start, end = fields[path]
        return body[start:end]

    def replace(path, value):
        start, end = fields[path]
        edits[start] = (end, value)

    allowed = {
        "m_IsReadable",
        "m_KeepVertices",
        "m_KeepIndices",
        "m_MeshUsageFlags",
        "m_BakedConvexCollisionMesh",
        "m_BakedTriangleCollisionMesh",
        "m_Name",
        "vertex_compression",
        "channel_dimensions",
        "stream_destination",
        "packed_tangents",
        "obj_import",
    }
    if set(ops) - allowed:
        raise ValueError("unknown mesh operation")
    for key in ("m_IsReadable", "m_KeepVertices", "m_KeepIndices"):
        if key in ops:
            if type(ops[key]) is not bool:
                raise ValueError("boolean import setting required")
            original = field(key)
            replace((key,), bytes((ops[key],)) + original[1:])
    if "m_MeshUsageFlags" in ops:
        replace(("m_MeshUsageFlags",), struct.pack("<I", ops["m_MeshUsageFlags"]))
    for key in ("m_BakedConvexCollisionMesh", "m_BakedTriangleCollisionMesh"):
        if key in ops:
            if ops[key] != "clear":
                raise ValueError("only collision-cache removal is supported")
            replace((key,), bytes(4))
    if "m_Name" in ops:
        replace(("m_Name",), padded_string(ops["m_Name"]))
    if "packed_tangents" in ops:
        if ops["packed_tangents"] != "repair_negative_z":
            raise ValueError("unknown packed tangent normalization")
        prefix = ("m_CompressedMesh", "m_Tangents")
        data_path = next(path for path in fields if path[:3] == prefix + ("m_Data",) and path[-1] == "payload")
        minimum, extent, data = normalize_packed_tangents(
            field(*data_path),
            struct.unpack("<I", field(*prefix, "m_NumItems"))[0],
            field(*prefix, "m_BitSize")[0],
            struct.unpack("<f", field(*prefix, "m_Start"))[0],
            struct.unpack("<f", field(*prefix, "m_Range"))[0],
        )
        replace(prefix + ("m_Start",), struct.pack("<f", minimum))
        replace(prefix + ("m_Range",), struct.pack("<f", extent))
        replace(data_path, data)
    vertex_key = ("m_VertexData", "m_DataSize")
    # Generic array spelling comes from the input's embedded type tree.
    channel_key = next(path for path in fields if path[:2] == ("m_VertexData", "m_Channels") and path[-1] == "payload")
    data_key = next(path for path in fields if path[:2] == vertex_key and path[-1] == "payload")
    data = field(*data_key) if vertex_stream is None else vertex_stream
    channels = field(*channel_key)
    imported = "obj_import" in ops
    if imported:
        if ops["obj_import"] != "static-triangles" or obj_import is None or "vertex_compression" in ops or "stream_destination" in ops:
            raise ValueError("unsupported source OBJ import policy")
        index_path = next(path for path in fields if path[0] == "m_IndexBuffer" and path[-1] == "payload")
        data, indices, metric = obj_import(data, field(*index_path))
        replace(index_path, indices)
        replace(("m_MeshMetrics[0]",), struct.pack("<f", metric))
    if "vertex_compression" in ops:
        if ops["vertex_compression"] != "normal_tangent_half":
            raise ValueError("unknown vertex conversion")
        (count,) = struct.unpack("<I", field("m_VertexData", "m_VertexCount"))
        data, channels = half_attributes(data, channels, count)
    if "channel_dimensions" in ops:
        if ops["channel_dimensions"] != "low_nibble":
            raise ValueError("unknown channel conversion")
        channels = bytearray(channels)
        for index in range(3, len(channels), 4):
            channels[index] &= 15
        channels = bytes(channels)
    if channels != field(*channel_key):
        replace(channel_key, channels)
    destination = ops.get("stream_destination")
    if destination is not None:
        replace(("m_StreamData",), struct.pack("<QI", destination["offset"], destination["size"]) + padded_string(destination["path"]))
    if vertex_stream is not None or "vertex_compression" in ops or imported:
        # Relocated streamed outputs retain a resource stream instead of inline bytes.
        inline = data if destination is None or destination["size"] == 0 else b""
        replace(vertex_key, struct.pack("<I", len(inline)) + inline + bytes(-len(inline) % 4))
    result = bytearray()
    cursor = 0
    for start, (end, value) in sorted(edits.items()):
        if start < cursor:
            raise ValueError("overlapping mesh edits")
        result.extend(body[cursor:start])
        result.extend(value)
        cursor = end
    result.extend(body[cursor:])
    return bytes(result), data if destination and destination["size"] else None
