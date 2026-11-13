"""Source model-material defaults from SDK declarations and static FBX metadata.

The SDK remains an opaque, separately supplied input. Bounded ARM64 constant
propagation reads its named static initializer without loading native code.
"""

import importlib.util
import io
from pathlib import Path
import struct


def registry():
    path = Path(__file__).resolve().parents[3] / "scripts/lab/phone_registry.py"
    spec = importlib.util.spec_from_file_location("_obj_material_registry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arm64_slice(raw):
    """Select exactly one bounded ARM64 slice of a big-endian FAT container."""
    if len(raw) < 8 or raw[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("Expected SDK FAT library")
    count = struct.unpack_from(">I", raw, 4)[0]
    if not 1 <= count <= 16 or 8 + count * 20 > len(raw):
        raise ValueError("Invalid SDK FAT table")
    matches, ranges = [], []
    for index in range(count):
        cpu, subtype, offset, size, alignment = struct.unpack_from(">5I", raw, 8 + index * 20)
        if alignment > 31 or offset % (1 << alignment) or offset < 8 + count * 20 or offset + size > len(raw):
            raise ValueError("Invalid SDK FAT slice extent")
        if any(offset < old + length and old < offset + size for old, length in ranges):
            raise ValueError("Overlapping SDK FAT slices")
        ranges.append((offset, size))
        if cpu == 0x100000C:
            matches.append(raw[offset : offset + size])
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous SDK ARM64 slice")
    return matches[0]


def logical_immediate(word):
    """Decode a 64-bit ARM logical-immediate bitmask, including rotation."""
    n, s, r = (word >> 22) & 1, (word >> 10) & 63, (word >> 16) & 63
    length = ((n << 6) | ((~s) & 63)).bit_length() - 1
    if length < 1:
        raise ValueError("Invalid logical immediate")
    width = 1 << length
    s, r = s & (width - 1), r & (width - 1)
    if s == width - 1:
        raise ValueError("Reserved logical immediate")
    mask = (1 << width) - 1
    bits = (1 << (s + 1)) - 1
    bits = ((bits >> r) | (bits << (width - r))) & mask
    return sum(bits << offset for offset in range(0, 64, width))


def initializer(image, name):
    """Interpret only straight-line constant materialization and fixed stores.

    Reject unknown instructions, calls, runtime loads and overlapping writes.
    No addresses, native instructions or default values come from a recipe.
    """
    start = image.symbol(name)
    end = next((address for address in image.symbol_addresses if address > start), None)
    if end is None or not 0 < end - start <= 4096 or (end - start) % 4:
        raise ValueError("Unbounded SDK initializer")
    scalar, vector, writes = {31: 0}, {}, {}

    def store(address, data):
        if address is None or any(address + offset in writes for offset in range(len(data))):
            raise ValueError("Unknown or overlapping initializer destination")
        writes.update((address + offset, value) for offset, value in enumerate(data))

    for pc in range(start, end, 4):
        word = struct.unpack("<I", image.at(pc, 4))[0]
        rd, rn = word & 31, (word >> 5) & 31
        if word & 0x9F000000 == 0x90000000:
            immediate = ((word >> 5) & 0x7FFFF) * 4 + ((word >> 29) & 3)
            scalar[rd] = (pc & ~4095) + image_signed(immediate, 21) * 4096
        elif word & 0xFF000000 == 0x91000000 and rn in scalar:
            scalar[rd] = scalar[rn] + (((word >> 10) & 4095) << (12 if word & (1 << 22) else 0))
        elif word & 0xFF8003E0 == 0xB20003E0:
            scalar[rd] = logical_immediate(word)
        elif word & 0xFF800000 == 0xF2800000 and rd in scalar:
            shift = ((word >> 21) & 3) * 16
            scalar[rd] = (scalar[rd] & ~(65535 << shift)) | (((word >> 5) & 65535) << shift)
        elif word & 0xFFFFFC00 == 0x4E080C00 and rn in scalar:
            vector[rd] = struct.pack("<Q", scalar[rn]) * 2
        elif word & 0xFFC00000 in (0xF9000000, 0x3D800000) and rn in scalar:
            wide = word & 0xFFC00000 == 0x3D800000
            if (wide and rd not in vector) or (not wide and rd not in scalar):
                raise ValueError("Unknown initializer store value")
            data = vector[rd] if wide else struct.pack("<Q", scalar[rd])
            store(scalar[rn] + ((word >> 10) & 4095) * len(data), data)
        elif word & 0xFFC00000 == 0xA9000000 and rn in scalar:
            other = (word >> 10) & 31
            if rd not in scalar or other not in scalar:
                raise ValueError("Unknown initializer pair value")
            store(scalar[rn] + image_signed((word >> 15) & 127, 7) * 8, struct.pack("<QQ", scalar[rd], scalar[other]))
        elif word & 0xFC000000 == 0x14000000 or word == 0xD65F03C0:
            return writes
        else:
            raise ValueError(f"Unsupported SDK initializer instruction at {pc:x}")
        if rd == 31:
            scalar[31] = 0
    raise ValueError("SDK initializer lacks terminal branch")


def image_signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def fbx_defaults(raw):
    image = registry().MachO(arm64_slice(raw), file_kind=6)
    writes = initializer(image, "__GLOBAL__sub_I_fbxsurfacelambert.cxx")
    prefix = "__ZN6fbxsdk17FbxSurfaceLambert"
    address = image.symbol(prefix + "15sDiffuseDefaultE")
    try:
        diffuse = struct.unpack("<3d", bytes(writes[address + offset] for offset in range(24)))
    except KeyError as error:
        raise ValueError("SDK diffuse initializer is incomplete") from error
    factor = struct.unpack("<d", image.at(image.symbol(prefix + "21sDiffuseFactorDefaultE"), 8))[0]
    transparency = struct.unpack("<d", image.at(image.symbol(prefix + "26sTransparencyFactorDefaultE"), 8))[0]
    return diffuse, factor, transparency


def shader_properties(body):
    """Read all declaration defaults from a source Shader's parsed form."""
    stream = io.BytesIO(body)

    def integer():
        raw = stream.read(4)
        if len(raw) != 4:
            raise ValueError("Truncated source shader declaration")
        return struct.unpack("<I", raw)[0]

    def string():
        size = integer()
        raw = stream.read(size)
        if len(raw) != size:
            raise ValueError("Truncated source shader name")
        stream.seek(-stream.tell() % 4, 1)
        return raw.decode("utf-8")

    result = {}
    count = integer()
    if count > len(body) // 32:
        raise ValueError("Excessive source shader declarations")
    for _ in range(count):
        name = string()
        string()
        attributes = integer()
        if attributes > len(body) // 4:
            raise ValueError("Excessive shader property attributes")
        for _ in range(attributes):
            string()
        kind, flags = integer(), integer()
        value = stream.read(16)
        if len(value) != 16 or kind not in range(5) or name in result:
            raise ValueError("Invalid source shader property")
        string()
        integer()
        result[name] = kind, value
    return result


def material(body, definition, shader, shader_type, mesh_body, mesh_type, defaults, schema):
    """Generate an opaque Standard Lambert material for an attribute-only OBJ.

    Original geometry owns the name; SDK declarations own the complete property
    inventory. Missing shininess in this importer policy gives zero glossiness.
    The supplied SDK material provides only native constructor framing.
    """
    root = schema.type_tree(io.BytesIO(definition["tree"]))
    spans = schema.spans(body, root)
    name_index = next(i for i, node in enumerate(root.children) if node.name == "m_Name")
    if [node.size for node in root.children[:name_index]] != [4, 12, 12, 12]:
        raise ValueError("SDK model Material prefix differs")
    shader_spans = schema.spans(shader, schema.type_tree(io.BytesIO(shader_type["tree"])))
    start, end = shader_spans["m_ParsedForm", "m_PropInfo"]
    props = shader_properties(shader[start:end])
    geometry = schema.spans(mesh_body, schema.type_tree(io.BytesIO(mesh_type["tree"])))
    start, end = geometry["m_Name",]
    size = struct.unpack_from("<I", mesh_body, start)[0]
    name = mesh_body[start + 4 : start + 4 + size].decode("utf-8") + "_0Mat"

    def string(value):
        raw = value.encode("utf-8")
        return struct.pack("<I", len(raw)) + raw + bytes(-len(raw) % 4)

    def array(rows):
        return struct.pack("<I", len(rows)) + b"".join(string(name) + value for name, value in sorted(rows))

    textures = []
    start, end = spans["m_SavedProperties", "m_TexEnvs"]
    stream = io.BytesIO(body[start:end])
    count = struct.unpack("<I", schema.exact(stream, 4))[0]
    if count > 4096:
        raise ValueError("Excessive SDK material texture properties")
    for _ in range(count):
        size = struct.unpack("<I", schema.exact(stream, 4))[0]
        key = schema.exact(stream, size).decode("utf-8")
        schema.exact(stream, -stream.tell() % 4)
        value = schema.exact(stream, 28)  # Native TexEnv PPtr, scale, offset.
        if key in props and props[key][0] == 4:
            textures.append((key, value))
    if stream.tell() != end - start:
        raise ValueError("Unconsumed SDK material texture fields")
    if {key for key, _ in textures} != {key for key, (kind, _) in props.items() if kind == 4}:
        raise ValueError("SDK model material lacks a declared texture constructor")
    diffuse, factor, transparency = defaults
    colors = {key: value for key, (kind, value) in props.items() if kind in (0, 1)}
    scalars = {key: value[:4] for key, (kind, value) in props.items() if kind in (2, 3)}
    if "_Color" not in colors or "_Glossiness" not in scalars:
        raise ValueError("Model material requires Standard declarations")
    colors["_Color"] = struct.pack("<4f", *(value * factor for value in diffuse), 1.0 - transparency)
    scalars["_Glossiness"] = struct.pack("<f", 0.0)
    flag_start, flag_end = spans["m_LightmapFlags",]
    flags = struct.unpack("<I", body[flag_start:flag_end])[0] & ~1
    replacements = {
        ("m_Name",): string(name),
        ("m_LightmapFlags",): struct.pack("<I", flags),
        ("m_SavedProperties", "m_TexEnvs"): array(textures),
        ("m_SavedProperties", "m_Floats"): array(scalars.items()),
        ("m_SavedProperties", "m_Colors"): array(colors.items()),
    }
    prefix = spans["m_Name",][0]
    result, cursor = bytearray(), prefix
    for path, replacement in sorted(replacements.items(), key=lambda item: spans[item[0]][0]):
        start, end = spans[path]
        result.extend(body[cursor:start])
        result.extend(replacement)
        cursor = end
    result.extend(body[cursor:])
    return bytes(result)
