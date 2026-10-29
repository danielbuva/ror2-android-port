"""Assemble diagnostic Sprite records from original metadata and SDK output.

The runtime constructor supplies geometry; the original embedded schema supplies
serialization and untouched fields. This is not a phone producer or bundle gate.
"""

import struct

try:
    from . import record_produce as A
except ImportError:
    import importlib.util
    from pathlib import Path

    _spec = importlib.util.spec_from_file_location("_sprite_records", Path(__file__).with_name("record_produce.py"))
    A = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(A)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def words(values):
    return struct.pack("<" + "i" * len(values), *values)


def vector(data):
    return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)


def source_parameters(body, root):
    """Recover standalone constructor parameters from original render data."""
    _, spans = A.fields(body, root)

    def floats(path, count):
        start, end = spans[path]
        if end - start != count * 4:
            raise ValueError("Unsupported original Sprite coordinate layout")
        return struct.unpack_from("<" + "f" * count, body, start)

    rect = floats(("m_Rect",), 4)
    crop = floats(("m_RD", "textureRect"), 4)
    offset = floats(("m_RD", "textureRectOffset"), 2)
    pivot = floats(("m_Pivot",), 2)
    if min(crop[2:]) <= 0:
        raise ValueError("Original Sprite has an empty render crop")
    top = [f32(f32(rect[i + 2] - crop[i + 2]) - offset[i]) for i in range(2)]
    border = floats(("m_Border",), 4)
    return {
        "rect": rect,
        "pivot": [f32(f32(f32(pivot[i] * rect[i + 2]) - offset[i]) / crop[i + 2]) for i in range(2)],
        "border": [f32(value - (*offset, *top)[i]) if value else 0.0 for i, value in enumerate(border)],
        "pixels_per_unit": floats(("m_PixelsToUnits",), 1)[0],
    }


def assemble(body, root, native, importer_guid, *, parameters=None):
    """Preserve original references and rebuild the admitted native streams."""
    parameters = source_parameters(body, root) if parameters is None else parameters
    _, spans = A.fields(body, root)
    changes = []

    def put(path, data):
        start, end = spans[path]
        changes.append((start, end, data))

    def raw(path):
        start, end = spans[path]
        return body[start:end]

    rect = struct.unpack("<4f", words(native["rect_bits"]))
    pivot = parameters["pivot"]
    put(("m_Rect",), words(native["rect_bits"]))
    put(("m_Offset",), struct.pack("<2f", *(f32(f32(pivot[i] - 0.5) * rect[i + 2]) for i in range(2))))
    put(("m_Pivot",), struct.pack("<2f", *pivot))
    put(("m_Border",), struct.pack("<4f", *parameters["border"]))
    put(("m_RD", "textureRect"), words(native["texture_rect_bits"]))
    put(("m_RD", "textureRectOffset"), words(native["texture_offset_bits"]))
    scale = struct.unpack("<i", struct.pack("<f", parameters["pixels_per_unit"]))[0]
    x, y = native["pivot_pixel_bits"]
    put(("m_RD", "uvTransform"), words([scale, x, scale, y]))

    positions, indices = native["vertex_xy_bits"], native["triangles"]
    count = len(positions) // 2
    if len(positions) % 2 or not 0 < count <= 65535 or len(indices) % 3 or any(type(v) is not int or not 0 <= v < count for v in indices):
        raise ValueError("Invalid native Sprite mesh extent")
    put(("m_RD", "m_IndexBuffer"), vector(struct.pack("<" + "H" * len(indices), *indices)))
    submeshes = raw(("m_RD", "m_SubMeshes"))
    if struct.unpack_from("<I", submeshes)[0] != 1:
        raise ValueError("Only original single-submesh Sprites are admitted")
    for path in spans:
        if path[:2] == ("m_RD", "m_SubMeshes") and path[-1] in ("indexCount", "vertexCount"):
            put(path, struct.pack("<I", len(indices) if path[-1] == "indexCount" else count))

    base = ("m_RD", "m_VertexData")
    channels = raw(base + ("m_Channels",))
    channel_count = struct.unpack_from("<I", channels)[0]
    if len(channels) != 4 + channel_count * 4:
        raise ValueError("Unsupported original Sprite channel layout")
    active = [(i, tuple(channels[4 + i * 4 : 8 + i * 4])) for i in range(channel_count) if channels[7 + i * 4] & 15]
    if len(active) != 2 or active[0] != (0, (0, 0, 0, 3)) or active[1][1] != (1, 0, 0, 2):
        raise ValueError("Unsupported original Sprite position/UV streams")
    old_count = struct.unpack("<I", raw(base + ("m_VertexCount",)))[0]
    old_data = raw(base + ("m_DataSize",))
    old_size = struct.unpack_from("<I", old_data)[0]
    old_uv = (old_count * 12 + 15) // 16 * 16
    if old_size != old_uv + old_count * 8 or any(old_data[4 + old_uv : 4 + old_size]):
        raise ValueError("Original Sprite does not use the zero-filled UV convention")
    uv_start = (count * 12 + 15) // 16 * 16
    data = bytearray(uv_start + count * 8)
    for index in range(count):
        struct.pack_into("<iii", data, index * 12, *positions[index * 2 : index * 2 + 2], 0)
    put(base + ("m_VertexCount",), struct.pack("<I", count))
    put(base + ("m_DataSize",), vector(data))
    physics = bytearray(struct.pack("<I", len(native["physics"])))
    for shape in native["physics"]:
        points = shape["xy_bits"]
        if len(points) % 2:
            raise ValueError("Invalid native Sprite physics extent")
        physics.extend(struct.pack("<I", len(points) // 2) + words(points))
    put(("m_PhysicsShape",), physics)
    result = bytearray(body)
    for start, end, data in sorted(changes, reverse=True):
        result[start:end] = data
    return A.O.module("player_data").sprite_key(bytes(result), importer_guid)
