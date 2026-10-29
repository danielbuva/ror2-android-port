"""Produce named accepted player-data files from explicit SDK/converter inputs.

This cohort includes original font/text/material/script/Sprite records, authored
JSON and receipt-verified source-produced texture packs. No accepted APK, replay
packet or Unity project is read. Outputs and receipts remain private; this
command does not install or qualify a player.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import time


SPEC = importlib.util.spec_from_file_location("player_sdk_inputs", Path(__file__).with_name("sdk_inputs.py"))
SDK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDK)
SPEC = importlib.util.spec_from_file_location("player_object_inputs", Path(__file__).with_name("object_produce.py"))
OBJECTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBJECTS)
W = OBJECTS.W
SPEC = importlib.util.spec_from_file_location("player_shader_metadata", Path(__file__).resolve().parents[3] / "scripts/lab/shader_metadata.py")
SHADERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHADERS)
SPEC = importlib.util.spec_from_file_location("player_script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)
DEFAULT = "unity default resources"
RESOURCES = {
    "Managed/Resources/System.Data.dll-resources.dat": (93718, "98a7950ec6de3242c2e190dfa630188dfa32511a125542b94baa952d1c757d49"),
    "Managed/Resources/System.Drawing.dll-resources.dat": (25453, "7c33aa707bc3fdc83991b81a97d6fc622b140762a767300f08f616c2c0a91255"),
    "Managed/Resources/mscorlib.dll-resources.dat": (337563, "c5baa176a5b72cd545266340e42102d393a5e43d38c95796bc828918bb95277f"),
}
TARGET = "apk/assets/bin/Data/"
RESERVE = 2 * 1024**3
INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
UNAVAILABLE_MODULES = {"UnityEngine." + name + "Module.dll" for name in ("ClusterInput", "ClusterRenderer", "NVIDIA", "VirtualTexturing")}
# Authored RuntimeInitializeOnLoadMethod declarations in tools/unity/runtime/
# session/{PortSession,CharacterDirectionProbe,ControllerAddressProbe,
# EntityStateTickProbe}.cs and tools/unity/runtime/catalog/WholeCatalogBootstrap.cs.
INITIALIZERS = [
    (name, "Initialize" if name == "WholeCatalogBootstrap" else "Init")
    for name in ("PortSession", "CharacterDirectionProbe", "ControllerAddressProbe", "EntityStateTickProbe", "WholeCatalogBootstrap")
]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path, expected):
    if path.resolve(strict=True) != path or not path.is_file():
        raise ValueError("redirected player-data input/output")
    size, digest = expected
    if path.stat().st_size != size or sha(path) != digest:
        raise ValueError("player-data bytes differ: " + path.name)


def metadata(scripting, initializers, projects):
    """Keep original engine order/initializer records and authored project order."""
    if len(scripting["names"]) != len(scripting["types"]) or len(projects) != len(set(projects)):
        raise ValueError("invalid script assembly identities")
    engines = [name for name, kind in zip(scripting["names"], scripting["types"]) if kind == 2 and name not in UNAVAILABLE_MODULES]
    source_projects = {name for name, kind in zip(scripting["names"], scripting["types"]) if kind == 16}
    if set(projects) != source_projects | {"MCPForUnity.Runtime.dll", "Newtonsoft.Json.dll"}:
        raise ValueError("project assembly set differs from original plus authored packages")
    names = engines + projects
    runtime = [
        {"assemblyName": "Assembly-CSharp", "nameSpace": "", "className": name, "methodName": method, "loadTypes": 0, "isUnityClass": False}
        for name, method in INITIALIZERS
    ]
    for assembly in names:
        runtime.extend(row for row in initializers["root"] if row["assemblyName"] + ".dll" == assembly)
    return {
        "ScriptingAssemblies.json": json.dumps({"names": names, "types": [2] * len(engines) + [16] * len(projects)}, separators=(",", ":")).encode(),
        "RuntimeInitializeOnLoads.json": (json.dumps({"root": runtime}, separators=(",", ":")) + "\n").encode(),
    }


def sprite_key(body, filename):
    """Regenerate a standalone Sprite importer GUID/local ID from its filename.

    The original geometry, UVs and pixel relationships are preserved. This
    qualified profile has no atlas tags or SpriteAtlas pointer. File-ID 21300000
    is Unity's Sprite importer identity; no target vector or geometry is supplied.
    """
    if len(filename) != 32 or any(char not in "0123456789abcdef" for char in filename):
        raise ValueError("invalid sprite player GUID")
    if len(body) < 4:
        raise ValueError("truncated sprite name")
    size = struct.unpack_from("<I", body)[0]
    offset = (size + 7) // 4 * 4 + 60
    if offset + 64 > len(body) or body[offset + 24 : offset + 40] != bytes(16) or body[offset + 52 : offset + 64] != bytes(12):
        raise ValueError("unqualified atlas or alpha-texture sprite layout")
    guid = b"".join(int(filename[index : index + 8][::-1], 16).to_bytes(4, "little") for index in range(0, 32, 8))
    result = bytearray(body)
    result[offset : offset + 24] = guid + struct.pack("<q", 21300000)
    return bytes(result)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def sprite_crop(body, rectangle_offset):
    """Recover standalone import coordinates from original render-data crop.

    AssetRipper SpriteExtensions.GetSpriteCoordinatesInAtlas documents this
    source-coordinate recovery. Round each Vector2 operation as float32, retain
    geometry/UVs, and clear the crop offset already absorbed into the new pivot.
    rectangle_offset selects the original variable-length render-data field.
    """

    name_size = struct.unpack_from("<I", body)[0]
    header = (name_size + 7) // 4 * 4
    if type(rectangle_offset) is not int or rectangle_offset % 4 or rectangle_offset < header + 112 or rectangle_offset + 24 > len(body):
        raise ValueError("invalid original Sprite crop extent")
    rectangle = struct.unpack_from("<4f", body, rectangle_offset)
    crop = struct.unpack_from("<2f", body, rectangle_offset + 16)
    old_size = struct.unpack_from("<2f", body, header + 8)
    pivot = struct.unpack_from("<2f", body, header + 44)
    new_size = rectangle[2:]
    if min(new_size) <= 0:
        raise ValueError("invalid original Sprite crop size")
    new_pivot = [f32(f32(f32(pivot[i] * old_size[i]) - crop[i]) / new_size[i]) for i in range(2)]
    offset = [f32(f32(new_pivot[i] - 0.5) * new_size[i]) for i in range(2)]
    top = [f32(f32(old_size[i] - new_size[i]) - crop[i]) for i in range(2)]
    border = struct.unpack_from("<4f", body, header + 24)
    border = [f32(value - (*crop, *top)[i]) if value else 0.0 for i, value in enumerate(border)]
    result = bytearray(body)
    struct.pack_into("<4f2f4f", result, header, *rectangle, *offset, *border)
    struct.pack_into("<2f", result, header + 44, *new_pivot)
    result[rectangle_offset + 16 : rectangle_offset + 24] = bytes(8)
    return bytes(result)


def full_rectangle_sprite(body, rectangle_offset):
    """Replay RecoveredHudBuilder's authored Sprite.Create FullRect policy.

    Source bounds, recovered pivot/border and pixels-per-unit generate four
    corners and two triangles. Unity's standalone vertex/index/channel layout
    is structural; no target vectors or image bytes are supplied.
    """
    recovered = sprite_crop(body, rectangle_offset)
    name_size = struct.unpack_from("<I", body)[0]
    header = (name_size + 7) // 4 * 4
    bounds = struct.unpack_from("<4f", body, header)
    pivot = struct.unpack_from("<2f", recovered, header + 44)
    border = struct.unpack_from("<4f", recovered, header + 24)
    ppu = struct.unpack_from("<f", body, header + 40)[0]
    if ppu <= 0:
        raise ValueError("invalid original Sprite pixels-per-unit")
    pixel_pivot = [f32(pivot[i] * bounds[i + 2]) for i in range(2)]
    offset = [f32(f32(pivot[i] - 0.5) * bounds[i + 2]) for i in range(2)]
    left, bottom = [f32(-value / ppu) for value in pixel_pivot]
    right, top = [f32(f32(bounds[i + 2] - pixel_pivot[i]) / ppu) for i in range(2)]
    stream = io.BytesIO()
    OBJECTS.aligned_string(stream, "Owned full-rectangle " + body[4 : 4 + name_size].decode("utf-8"))
    stream.write(struct.pack("<4f2f4ff2fI?3x", *bounds, *offset, *border, ppu, *pivot, 0, False))
    stream.write(bytes(24))  # Importer identity follows generation.
    stream.write(struct.pack("<IiqiqiqI", 0, 0, 0, 1, 1, 0, 0, 0))
    stream.write(struct.pack("<7I6f", 1, 0, 6, 0, 0, 0, 4, *([0.0] * 6)))
    stream.write(struct.pack("<I6H", 12, 0, 1, 2, 2, 1, 3))
    stream.write(struct.pack("<II", 4, 14))
    channels = bytearray(14 * 4)
    channels[3], channels[16], channels[19] = 3, 1, 2
    stream.write(channels)
    stream.write(struct.pack("<I12f", 80, left, top, 0.0, right, top, 0.0, left, bottom, 0.0, right, bottom, 0.0))
    stream.write(bytes(32))  # Four zero native UV vectors.
    stream.write(struct.pack("<I4f2f2fI4ffII", 0, *bounds, 0.0, 0.0, -1.0, -1.0, 0, ppu, pixel_pivot[0], ppu, pixel_pivot[1], 1.0, 0, 0))
    return stream.getvalue()


def material_string(stream):
    size = W.B.unpack(stream, "<I")[0]
    if size > 4096:
        raise ValueError("material string bound exceeded")
    value = W.B.exact(stream, size).decode("utf-8")
    W.B.exact(stream, -stream.tell() % 4)
    return value


def material_count(stream):
    count = W.B.unpack(stream, "<I")[0]
    if count > 4096:
        raise ValueError("material property count bound exceeded")
    return count


def material_texture_properties(pc, source):
    """Read texture-property names from the original Shader's property table."""
    path = OBJECTS.M.safe_input(pc, source["path"])
    checked(path, (source["bytes"], source["sha256"]))
    with path.open("rb") as raw:
        raw.size = path.stat().st_size
        member = W.B.Bundle(path).member(source["member"]) if "member" in source else raw
        original = W.read_serialized(member)
        row = next(row for row in original["objects"] if row["path_id"] == source["path_id"])
        if original["types"][row["type_id"]]["class_id"] != 48:
            raise ValueError("material shader source type differs")
        member.seek(original["data_offset"] + row["offset"])
        stream = io.BytesIO(W.B.exact(member, row["bytes"]))
        material_string(stream)
        textures = set()
        for _ in range(material_count(stream)):
            name = material_string(stream)
            material_string(stream)  # Description.
            for _ in range(material_count(stream)):
                material_string(stream)  # Attribute.
            kind = W.B.unpack(stream, "<i")[0]
            W.B.exact(stream, 20)  # Flags and original four-component default.
            material_string(stream)  # Default texture name.
            W.B.exact(stream, 4)  # Texture dimension.
            if kind == 4:
                textures.add(name)
    checked(path, (source["bytes"], source["sha256"]))
    return textures


def material_textures(body, properties):
    """Keep original TexEnv ranges declared by the assigned source shader."""
    stream = io.BytesIO(body)
    material_string(stream)
    W.B.exact(stream, 12)  # Relocated Shader PPtr.
    for _ in range(2):
        for _ in range(material_count(stream)):
            material_string(stream)  # Preserve both keyword lists.
    W.B.exact(stream, 12)  # Lightmap flags, booleans/alignment and render queue.
    for _ in range(material_count(stream)):
        material_string(stream)
        material_string(stream)  # Tag map pair.
    for _ in range(material_count(stream)):
        material_string(stream)  # Disabled pass.
    start = stream.tell()
    kept = []
    for _ in range(material_count(stream)):
        begin = stream.tell()
        name = material_string(stream)
        W.B.exact(stream, 28)  # Texture PPtr, scale and offset.
        if name in properties:
            kept.append(body[begin : stream.tell()])
    return body[:start] + struct.pack("<I", len(kept)) + b"".join(kept) + body[stream.tell() :]


def script_sdk_schema(source, selected):
    """Read the admitted SDK editor MonoBehaviour base for selected scripts."""
    if source is None:
        raise ValueError("script properties require explicit --editor-resources SDK input")
    source = Path(source).absolute()
    checked(source, (selected["bytes"], selected["sha256"]))
    with source.open("rb") as raw:
        raw.size = source.stat().st_size
        original = W.read_serialized(raw)
        row = next(row for row in original["objects"] if row["path_id"] == selected["path_id"])
        typ = original["types"][row["type_id"]]
        if typ["class_id"] != 114 or not typ.get("tree"):
            raise ValueError("SDK script base type/schema differs")
        tree = typ["tree"]
    checked(source, (selected["bytes"], selected["sha256"]))
    return tree


def original_script_hash(pc, selected, original, body, typ, sdk_tree):
    """Derive only an explicitly selected script's hash from admitted sources."""
    if sdk_tree is None:
        raise ValueError("script properties require admitted SDK base schema")
    if len(body) < 28:
        raise ValueError("truncated original script relationship")
    file_id, identity = struct.unpack_from("<iq", body, 16)
    if (
        not 0 < file_id <= len(original["externals"])
        or identity != selected["path_id"]
        or original["externals"][file_id - 1]["path"] != "archive:/{0}/{0}".format(selected["member"])
    ):
        raise ValueError("original script source relationship differs")
    path = OBJECTS.M.safe_input(pc, selected["path"])
    checked(path, (selected["bytes"], selected["sha256"]))
    with path.open("rb") as raw:
        member = W.B.Bundle(path).member(selected["member"])
        layout = W.read_serialized(member)
        row = next(row for row in layout["objects"] if row["path_id"] == identity)
        definition = layout["types"][row["type_id"]]
        if definition["class_id"] != 115 or not definition.get("tree"):
            raise ValueError("original MonoScript type/schema differs")
        member.seek(layout["data_offset"] + row["offset"])
        names = ("m_ClassName", "m_Namespace", "m_AssemblyName")
        fields = metadata_fields(W.B.exact(member, row["bytes"]), definition, set(names))
        if any(not isinstance(fields.get(name), str) for name in names) or not fields[names[0]] or not fields[names[2]]:
            raise ValueError("original MonoScript identity fields differ")
        result = SCRIPT.properties_hash(*(fields[name] for name in names), typ.get("tree", b""), sdk_tree)
    checked(path, (selected["bytes"], selected["sha256"]))
    return result


def object_file(pc, selected, destination, script_sdk_tree=None):
    """Reuse original player-object bodies and source type identities.

    UnityPy/AssetRipper's PPtr relationship is the same checked remap performed
    by object_produce; the player strips source type trees and retains only its
    selected original external dependency. No font or image data is introduced.
    """
    source = selected["source"]
    path = OBJECTS.M.safe_input(pc, source["path"])
    checked(path, (source["bytes"], source["sha256"]))
    shader = selected.get("material_shader")
    script_properties = selected.get("script_properties")
    properties = material_texture_properties(pc, shader) if shader is not None else None
    with path.open("rb") as raw:
        raw.size = path.stat().st_size
        member = W.B.Bundle(path).member(source["member"]) if "member" in source else raw
        original = W.read_serialized(member)
        objects = {row["path_id"]: row for row in original["objects"]}
        if sum(row["bytes"] for row in selected["objects"]) > W.B.LIMIT // 3:
            raise ValueError("player object-body memory bound exceeded")
        types, rows, selections = [], [], {}
        offset = 0
        for target in selected["objects"]:
            row = objects[target["source_path_id"]]
            if row["bytes"] != target.get("source_bytes", target["bytes"]):
                raise ValueError("original player object size drift")
            typ = dict(original["types"][row["type_id"]])
            if typ["class_id"] == 114:
                if len(selected["objects"]) != 1 or "script" not in selected:
                    raise ValueError("only standalone scripted player objects are qualified")
                typ["script_type"] = 0
                if script_properties is not None:
                    member.seek(original["data_offset"] + row["offset"])
                    data = W.B.exact(member, row["bytes"])
                    if hashlib.sha256(data).hexdigest() != target["source_sha256"]:
                        raise ValueError("original player object body drift")
                    typ["hash"] = original_script_hash(pc, script_properties, original, data, typ, script_sdk_tree)
            elif script_properties is not None:
                raise ValueError("script properties require a standalone MonoBehaviour")
            if typ not in types:
                types.append(typ)
            offset = (offset + 7) // 8 * 8
            identity = target["path_id"]
            rows.append({"path_id": identity, "offset": offset, "bytes": target["bytes"], "type_id": types.index(typ)})
            selections[identity] = (target, row)
            offset += target["bytes"]
        layout = {
            # Destination follows the accepted Android toolchain, as in the
            # existing object producer; original schemas remain source-derived.
            "engine": "2021.3.45f2",
            "platform": 13,
            "trees": False,
            "types": types,
            "objects": rows,
            "scripts": [selected["script"]] if "script" in selected else [],
            "externals": [{"empty": "", "guid": bytes(16), "type": 0, "path": selected["texture"]}]
            if "texture" in selected
            else [
                {"empty": "", "guid": bytes(16), "type": 0, "path": index} if isinstance(index, str) else original["externals"][index]
                for index in selected["externals"]
            ],
            "ref_types": [],
            "user": "",
        }

        def body(target):
            selection, row = selections[target["path_id"]]
            member.seek(original["data_offset"] + row["offset"])
            data = W.B.exact(member, row["bytes"])
            if hashlib.sha256(data).hexdigest() != selection["source_sha256"]:
                raise ValueError("original player object body drift")
            if types[target["type_id"]]["class_id"] == 213:
                if len(selected["objects"]) != 1:
                    raise ValueError("only standalone sprite player files are qualified")
                if selected.get("full_rectangle", False):
                    data = full_rectangle_sprite(data, selected["crop_rectangle_offset"])
                elif "crop_rectangle_offset" in selected:
                    data = sprite_crop(data, selected["crop_rectangle_offset"])
                data = sprite_key(data, selected["file"])
            data = OBJECTS.remap(data, selection.get("references", []))
            if "keyword_policy" in selection:
                if types[target["type_id"]]["class_id"] != 21 or selection["keyword_policy"] != "dummy-shader-demote-valid":
                    raise ValueError("unqualified player material keyword policy")
                data = OBJECTS.demote_material_keywords(data)
            if properties is not None:
                if types[target["type_id"]]["class_id"] != 21:
                    raise ValueError("only material texture properties are qualified")
                data = material_textures(data, properties)
            if "rename" in selection:
                if types[target["type_id"]]["class_id"] != 21:
                    raise ValueError("only authored material import names are qualified")
                name = io.BytesIO()
                OBJECTS.aligned_string(name, selection["rename"])
                data = name.getvalue() + data[(struct.unpack_from("<I", data)[0] + 7) // 4 * 4 :]
            if types[target["type_id"]]["class_id"] == 114 and list(struct.unpack_from("<iq", data, 16)) != selected["script"]:
                raise ValueError("player object script relationship differs")
            if hashlib.sha256(data).hexdigest() != selection["sha256"]:
                raise ValueError("produced player object differs")
            return io.BytesIO(data)

        with destination.open("xb") as output:
            W.write_serialized(output, layout, body)
        checked(path, (source["bytes"], source["sha256"]))
        if shader is not None:
            checked(OBJECTS.M.safe_input(pc, shader["path"]), (shader["bytes"], shader["sha256"]))
        if script_properties is not None:
            checked(OBJECTS.M.safe_input(pc, script_properties["path"]), (script_properties["bytes"], script_properties["sha256"]))


def inline_texture(body, row, pixels):
    """Move a producer's existing pixel stream into a standalone player body."""
    if "resource" not in row:
        if pixels:
            raise ValueError("inline texture has unexpected external pixels")
        return body
    resource = row["resource"]
    stream = resource["stream"]
    if len(pixels) != resource["bytes"] or stream["size"] != len(pixels):
        raise ValueError("produced texture stream length differs")
    suffix = io.BytesIO()
    suffix.write(struct.pack("<QI", stream["offset"], stream["size"]))
    OBJECTS.aligned_string(suffix, stream["path"])
    tail = bytes(4) + suffix.getvalue()  # Empty inline array, then StreamData.
    if not body.endswith(tail):
        raise ValueError("produced texture stream descriptor differs")
    return body[: -len(tail)] + struct.pack("<I", len(pixels)) + pixels + bytes(-len(pixels) % 4) + bytes(16)


def texture_files(pc, type_source, selections, packs, output, result):
    """Assemble source-produced packs into the existing final target-tree paths."""
    required = {row["profile_sha256"] for row in selections}
    providers = {}
    for supplied, receipt_sha256 in packs:
        supplied = Path(supplied).resolve(strict=True)
        receipt = supplied / "result.json"
        checked(receipt, (receipt.stat().st_size, receipt_sha256))
        value = json.loads(receipt.read_text())
        profile = value.get("profile_sha256")
        if value.get("success") is not True or value.get("input_id") != INPUT_ID or profile not in required or profile in providers:
            raise ValueError("unexpected or unsuccessful texture producer")
        if set(value["outputs"]) != {"objects.bin", "resources.bin", "index.jsonl"}:
            raise ValueError("incomplete texture producer outputs")
        for name, pin in value["outputs"].items():
            checked(supplied / name, (pin["bytes"], pin["sha256"]))
        providers[profile] = supplied, receipt_sha256, value
    if set(providers) != required:
        raise ValueError("missing source-produced texture pack")
    if not selections:
        return
    path = OBJECTS.M.safe_input(pc, type_source["path"])
    checked(path, (type_source["bytes"], type_source["sha256"]))
    with path.open("rb") as raw:
        raw.size = path.stat().st_size
        member = W.B.Bundle(path).member(type_source["member"]) if "member" in type_source else raw
        source = W.read_serialized(member)
    types = [typ for typ in source["types"] if typ["class_id"] == 28]
    if len(types) != 1:
        raise ValueError("original Texture2D type identity required")

    def extent(stream, row):
        offset, size = row["offset"], row["bytes"]
        if type(offset) is not int or type(size) is not int or offset < 0 or not 0 <= size <= W.B.LIMIT or offset + size > stream.seek(0, 2):
            raise ValueError("produced texture extent escapes pack")
        stream.seek(offset)
        data = W.B.exact(stream, size)
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("produced texture extent hash differs")
        return data

    def identity(row):
        return row["bundle"], row["member"], row["path_id"]

    result["texture_packs"] = {}
    for selected in selections:
        profile = selected["profile_sha256"]
        supplied, receipt_sha256, value = providers[profile]
        wanted = {identity(row) for row in selected["files"]}
        records = {}
        with (supplied / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                key = identity(row)
                if key in wanted:
                    if key in records:
                        raise ValueError("duplicate produced texture identity")
                    records[key] = row
        if set(records) != wanted:
            raise ValueError("produced texture record missing")
        with (supplied / "objects.bin").open("rb") as objects, (supplied / "resources.bin").open("rb") as resources:
            for target in selected["files"]:
                name = target["file"]
                if len(name) != 32 or any(char not in "0123456789abcdef" for char in name):
                    raise ValueError("invalid standalone texture filename")
                row = records[identity(target)]
                body = inline_texture(extent(objects, row), row, extent(resources, row["resource"]) if "resource" in row else b"")
                layout = {
                    "engine": source["engine"],
                    "platform": 13,
                    "trees": False,
                    "types": types,
                    "objects": [{"path_id": 1, "offset": 0, "bytes": len(body), "type_id": 0}],
                    "scripts": [],
                    "externals": [],
                    "ref_types": [],
                    "user": "",
                }
                with (output / (TARGET + name)).open("xb") as destination:
                    W.write_serialized(destination, layout, lambda row: io.BytesIO(body))
                result["files"][TARGET + name] = {"source_role": "pc-texture-pack", "source": receipt_sha256}
        for name, pin in value["outputs"].items():
            checked(supplied / name, (pin["bytes"], pin["sha256"]))
        checked(supplied / "result.json", ((supplied / "result.json").stat().st_size, receipt_sha256))
        result["texture_packs"][profile] = receipt_sha256
    checked(path, (type_source["bytes"], type_source["sha256"]))


def metadata_value(body, node, start):
    """Read selected source strings/arrays/structs; scalar bits remain integers."""
    if node.kind == "string":
        size = struct.unpack_from("<I", body, start)[0]
        end = start + 4 + size
        if size > W.B.LIMIT or end > len(body):
            raise ValueError("source string extent")
        return body[start + 4 : end].decode("utf-8"), (end + 3) // 4 * 4
    if node.flags & 1:
        count = struct.unpack_from("<I", body, start)[0]
        cursor = start + 4
        if count > 1000000 or len(node.children) != 2:
            raise ValueError("source metadata array extent")
        value = []
        for _ in range(count):
            item, cursor = metadata_value(body, node.children[1], cursor)
            value.append(item)
    elif node.children:
        cursor, value = start, {}
        if len(node.children) == 1 and node.children[0].flags & 1:
            value, cursor = metadata_value(body, node.children[0], cursor)
        else:
            for child in node.children:
                value[child.name], cursor = metadata_value(body, child, cursor)
    else:
        if not 0 <= node.size <= 16 or start + node.size > len(body):
            raise ValueError("source primitive extent")
        cursor = start + node.size
        value = int.from_bytes(body[start:cursor], "little")
    if node.meta & 0x4000:
        cursor = (cursor + 3) // 4 * 4
    if cursor > len(body):
        raise ValueError("source metadata extent")
    return value, cursor


def metadata_fields(body, definition, wanted):
    mesh = OBJECTS.M._mesh
    root = mesh.type_tree(io.BytesIO(definition["tree"]))
    spans = mesh.spans(body, root)
    fields = {}
    for child in root.children:
        if child.name in wanted:
            start, end = spans[child.name,]
            fields[child.name], cursor = metadata_value(body, child, start)
            if cursor != end:
                raise ValueError("source field not fully consumed: " + child.name)
    return fields


def shader_manifests(profile_root, pc, recipe):
    """Re-read original material keywords and shader declarations, never programs."""
    source_recipe = OBJECTS.M.safe_input(profile_root, recipe["path"])
    checked(source_recipe, (recipe["bytes"], recipe["sha256"]))
    selectors = json.loads(source_recipe.read_text())
    if selectors["input_id"] != INPUT_ID:
        raise ValueError("shader manifest original input differs")
    contexts, shaders, providers = {}, {}, {}

    def original(path, digest):
        path = OBJECTS.M.safe_input(pc, path)
        expected = (path.stat().st_size, digest)
        checked(path, expected)
        if path in providers and providers[path] != expected:
            raise ValueError("conflicting shader manifest source pins")
        providers[path] = expected
        return path, W.B.Bundle(path)

    def source_object(member, layout, selected, kind):
        rows = [row for row in layout["objects"] if row["path_id"] == selected["path_id"]]
        if len(rows) != 1:
            raise ValueError("shader manifest source object is not unique")
        row = rows[0]
        definition = layout["types"][row["type_id"]]
        if definition["class_id"] != kind or not layout["trees"]:
            raise ValueError("shader manifest source class/tree differs")
        member.seek(layout["data_offset"] + row["offset"])
        body = W.B.exact(member, row["bytes"])
        if hashlib.sha256(body).hexdigest() != selected.get("body_sha256", selected.get("sha256")):
            raise ValueError("shader manifest original object drift")
        return body, definition

    for selected in selectors["shaders"]:
        path, bundle = original(selected["path"], selected["bundle_sha256"])
        member = bundle.member(selected["member"])
        layout = W.read_serialized(member)
        body, definition = source_object(member, layout, selected, 48)
        tree = metadata_fields(body, definition, {"m_ParsedForm"})
        records = [dict(row, kind="program") for row in SHADERS.variants(tree).values()]
        family = selected["family"]
        identity = selected["member"], selected["path_id"]
        if family in contexts or identity in shaders:
            raise ValueError("duplicate shader manifest identity")
        contexts[family] = tree, None, records, None, {}
        shaders[identity] = tree["m_ParsedForm"]["m_Name"]
        checked(path, providers[path])
    rows = []
    for selected_bundle in selectors["materials"]:
        path, bundle = original(selected_bundle["path"], selected_bundle["sha256"])
        for selected_member in selected_bundle["members"]:
            member = bundle.member(selected_member["name"])
            layout = W.read_serialized(member)
            for selected in selected_member["materials"]:
                body, definition = source_object(member, layout, selected, 21)
                fields = metadata_fields(body, definition, {"m_Shader", "m_ValidKeywords", "m_InvalidKeywords", "m_ShaderKeywords"})
                pointer = fields["m_Shader"]
                identity, file_id = pointer["m_PathID"], pointer["m_FileID"]
                identity = identity - (1 << 64) if identity >= (1 << 63) else identity
                if not 0 <= file_id <= len(layout["externals"]):
                    raise ValueError("shader manifest pointer extent")
                shader_member = selected_member["name"] if file_id == 0 else layout["externals"][file_id - 1]["path"].rsplit("/", 1)[-1]
                if (shader_member, identity) != (selected["shader_member"], selected["shader_path_id"]):
                    raise ValueError("shader manifest original shader pointer differs")
                keys = set(fields.get("m_ValidKeywords", [])) | set(fields.get("m_InvalidKeywords", [])) | set(fields.get("m_ShaderKeywords", "").split())
                rows.append((selected["asset"], shaders[shader_member, identity], ",".join(sorted(keys))))
        checked(path, providers[path])
    rows = sorted(set(rows))
    family_contexts = {name: contexts[name] for name in SHADERS.FAMILIES}
    manifests = {"standard": SHADERS.standard_manifest(rows, contexts["standard"]), "families": SHADERS.family_manifest(family_contexts, rows)}
    checked(source_recipe, (recipe["bytes"], recipe["sha256"]))
    # Keep all original providers pinned through final serialized output as well.
    return manifests, [(source_recipe, (recipe["bytes"], recipe["sha256"])), *providers.items()]


def language_json(raw):
    """Accept original JObject trailing commas without changing quoted text."""
    text = raw.decode("utf-8-sig")
    chars = list(text)
    quoted = escape = False
    for index, char in enumerate(text):
        if quoted:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == ",":
            end = index + 1
            while end < len(text) and text[end].isspace():
                end += 1
            if end < len(text) and text[end] in "}]":
                chars[index] = " "
    return json.loads("".join(chars))


def language_strings(pc, sources):
    """Replay StageStrings using the qualified original English cohort.

    Its uppercase ASCII keys have an independently qualified en-US collation
    order. Other alphabets require a separately established collation contract.
    """
    directory = "Risk of Rain 2_Data/StreamingAssets/Language/en"
    expected = {row["path"] for row in sources}
    actual = {(PurePosixPath(directory) / path.name).as_posix() for path in (pc / directory).glob("*.json")}
    if expected != actual or len(expected) != len(sources):
        raise ValueError("English original file set differs")
    names = [PurePosixPath(row["path"]).name.casefold() for row in sources]
    if len(set(names)) != len(names):
        raise ValueError("English filename collation is ambiguous")
    pins, values = [], {}
    for row in sorted(sources, key=lambda row: PurePosixPath(row["path"]).name.casefold()):
        if PurePosixPath(row["path"]).parent.as_posix() != directory:
            raise ValueError("English source is outside the original language directory")
        path = OBJECTS.M.safe_input(pc, row["path"])
        pin = row["bytes"], row["sha256"]
        checked(path, pin)
        tokens = language_json(path.read_bytes()).get("strings")
        if isinstance(tokens, dict):
            values.update((key, value) for key, value in tokens.items() if isinstance(value, str))
        checked(path, pin)
        pins.append((path, pin))
    alphabet = "./_0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if any(not key or any(char not in alphabet for char in key) for key in values):
        raise ValueError("English token collation is outside the qualified cohort")
    if not {"TITLE_SINGLEPLAYER", "SUBMENU_QUIT"} <= values.keys():
        raise ValueError("Original English menu tokens absent")
    keys = sorted(values, key=lambda key: tuple(alphabet.index(char) for char in key))
    script = json.dumps({"entries": [{"key": key, "value": values[key]} for key in keys]}, ensure_ascii=False, separators=(",", ":"))
    return script, pins


def text_files(profile_root, pc, selected, output):
    """Strip original TextAsset type trees; keep source bytes or generate JSON.

    The native TextAsset body is two length-prefixed, aligned UTF-8 strings.
    Source types and original line-breaking text always come from PC input.
    Authored JSON recipes are explicit pinned siblings of the selected profile.
    """
    source = selected["source"]
    path = OBJECTS.M.safe_input(pc, source["path"])
    checked(path, (source["bytes"], source["sha256"]))
    member = W.B.Bundle(path).member(source["member"])
    original = W.read_serialized(member)
    definitions = [row for row in original["types"] if row["class_id"] == 49]
    if len(definitions) != 1:
        raise ValueError("original TextAsset type is not unique")
    objects = {row["path_id"]: row for row in original["objects"]}
    recipes = []
    manifest_pins = []
    manifests = {}
    language = None
    if "language" in selected:
        language, language_pins = language_strings(pc, selected["language"])
        manifest_pins.extend(language_pins)
    if "manifests" in selected:
        manifests, shader_pins = shader_manifests(profile_root, pc, selected["manifests"])
        manifest_pins.extend(shader_pins)
    for item in selected["files"]:
        name = item["file"]
        if name in ("", ".", "..") or PurePosixPath(name).name != name or "\\" in name:
            raise ValueError("unsafe text player filename")
        if "source_path_id" in item:
            row = objects[item["source_path_id"]]
            if original["types"][row["type_id"]] != definitions[0]:
                raise ValueError("original object is not a TextAsset")
            member.seek(original["data_offset"] + row["offset"])
            data = W.B.exact(member, row["bytes"])
            if hashlib.sha256(data).hexdigest() != item["source_sha256"]:
                raise ValueError("original TextAsset body drift")
        elif item.get("language") is True:
            if language is None:
                raise ValueError("English original sources required")
            stream = io.BytesIO()
            OBJECTS.aligned_string(stream, item["name"])
            OBJECTS.aligned_string(stream, language)
            data = stream.getvalue()
        elif "manifest" in item:
            stream = io.BytesIO()
            OBJECTS.aligned_string(stream, item["name"])
            OBJECTS.aligned_string(stream, json.dumps(manifests[item["manifest"]], sort_keys=True, indent=2) + "\n")
            data = stream.getvalue()
        else:
            recipe = item["recipe"]
            if not 0 < recipe["bytes"] <= W.B.LIMIT // 3:
                raise ValueError("authored text recipe exceeds memory bound")
            source_recipe = OBJECTS.M.safe_input(profile_root, recipe["path"])
            checked(source_recipe, (recipe["bytes"], recipe["sha256"]))
            script = json.dumps(json.loads(source_recipe.read_text()), indent=2) + "\n"
            stream = io.BytesIO()
            OBJECTS.aligned_string(stream, item["name"])
            OBJECTS.aligned_string(stream, script)
            data = stream.getvalue()
            recipes.append((source_recipe, recipe))
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("produced TextAsset body differs")
        layout = {
            "engine": "2021.3.45f2",
            "platform": 13,
            "trees": False,
            "types": definitions,
            "objects": [{"path_id": 1, "offset": 0, "bytes": len(data), "type_id": 0}],
            "scripts": [],
            "externals": [],
            "ref_types": [],
            "user": "",
        }
        with (output / (TARGET + name)).open("xb") as destination:
            W.write_serialized(destination, layout, lambda row: io.BytesIO(data))
    checked(path, (source["bytes"], source["sha256"]))
    for path, recipe in recipes:
        checked(path, (recipe["bytes"], recipe["sha256"]))
    for path, pin in manifest_pins:
        checked(path, pin)
    if "language" in selected:
        # StageStrings consumes the complete directory, including late additions.
        language_strings(pc, selected["language"])


def builtin_ui(pc, profile, builtin_extra, destination):
    """Project the pinned SDK's built-in UI objects into runtime serialization.

    SDK type trees identify the 40-byte editor Object prefix, Texture image
    hash/VT fields and Sprite atlas-name/tag, duplicate AtlasRD and SpriteID.
    Their checked six-object layout retains the original mip pixels, geometry,
    physics shapes and bones. Runtime type identities come from the PC files.
    """
    selected = profile["builtin_ui"]
    if builtin_extra is None:
        raise ValueError("built-in UI requires explicit --builtin-extra SDK input")
    source = Path(builtin_extra).absolute()
    pin = (selected["source"]["bytes"], selected["source"]["sha256"])
    checked(source, pin)
    types = []
    for class_id, original_source in ((28, profile["font"]["source"]), (213, profile["sprites"]["source"])):
        path = OBJECTS.M.safe_input(pc, original_source["path"])
        original_pin = (original_source["bytes"], original_source["sha256"])
        checked(path, original_pin)
        with path.open("rb") as raw:
            raw.size = path.stat().st_size
            member = W.B.Bundle(path).member(original_source["member"]) if "member" in original_source else raw
            original = W.read_serialized(member)
            types.append(next(row for row in original["types"] if row["class_id"] == class_id))
        checked(path, original_pin)
    rows, bodies, textures = [], {}, {}
    offset = 0
    with source.open("rb") as raw:
        raw.size = source.stat().st_size
        original = W.read_serialized(raw)
        objects = {row["path_id"]: row for row in original["objects"]}
        for type_id, identities in enumerate((selected["textures"], selected["sprites"])):
            for identity in identities:
                row = objects[identity]
                if original["types"][row["type_id"]]["class_id"] != (28 if type_id == 0 else 213):
                    raise ValueError("built-in UI source type differs")
                raw.seek(original["data_offset"] + row["offset"])
                body = W.B.exact(raw, row["bytes"])
                name_end = (44 + struct.unpack_from("<I", body, 40)[0] + 3) // 4 * 4
                target_id = len(rows) + 1
                if type_id == 0:
                    # After the name: 16-byte ImageContentsHash; VTOnly and
                    # AlphaIsTransparency occupy the aligned bytes 56..60.
                    body = body[40:name_end] + body[name_end + 16 : name_end + 56] + body[name_end + 60 :]
                    textures[identity] = target_id
                else:
                    # AtlasName/PackingTag: 60..76; duplicate AtlasRD:
                    # 512..908 (396 bytes); trailing SpriteID: 36 bytes.
                    body = body[40 : name_end + 60] + body[name_end + 76 : name_end + 512] + body[name_end + 908 : -36]
                    key = name_end - 40 + 60
                    body = bytearray(sprite_key(body, selected["file"]))
                    file_id, texture = struct.unpack_from("<iq", body, key + 40)
                    if file_id != 0 or texture not in textures:
                        raise ValueError("built-in UI source texture relationship differs")
                    struct.pack_into("<q", body, key + 16, identity)
                    struct.pack_into("<q", body, key + 44, textures[texture])
                    body = bytes(body)
                offset = (offset + 7) // 8 * 8
                rows.append({"path_id": target_id, "offset": offset, "bytes": len(body), "type_id": type_id})
                bodies[target_id] = body
                offset += len(body)
        layout = {
            "engine": original["engine"],
            "platform": 13,
            "trees": False,
            "types": types,
            "objects": rows,
            "scripts": [],
            "externals": [],
            "ref_types": [],
            "user": "",
        }
        with destination.open("xb") as output:
            W.write_serialized(output, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    checked(source, pin)


def shared_shader_properties(body):
    """Read source-produced Shader m_PropInfo using the existing table framing."""
    stream = io.BytesIO(body)
    material_string(stream)
    textures, scalars = set(), {}
    for _ in range(material_count(stream)):
        name = material_string(stream)
        material_string(stream)
        for _ in range(material_count(stream)):
            material_string(stream)
        kind = W.B.unpack(stream, "<i")[0]
        W.B.exact(stream, 4)  # source property flags
        defaults = W.B.exact(stream, 16)
        material_string(stream)
        W.B.exact(stream, 4)
        if kind == 4:
            textures.add(name)
        elif kind in (2, 3):
            scalars[name] = defaults[:4]
    return textures, scalars


def shared_default_material(body, definition, shader_body):
    """Drop editor Object prefix and reconcile only SDK-declared properties."""
    mesh = OBJECTS.M._mesh
    root = mesh.type_tree(io.BytesIO(definition["tree"]))
    spans = mesh.spans(body, root)
    prefix, _ = spans["m_Name",]
    # The metadata, not a body offset from a target, determines runtime start.
    name_index = next(i for i, node in enumerate(root.children) if node.name == "m_Name")
    if [node.size for node in root.children[:name_index]] != [4, 12, 12, 12]:
        raise ValueError("SDK editor Material Object prefix differs")
    body = body[prefix:]
    root.children = root.children[name_index:]
    textures, defaults = shared_shader_properties(shader_body)
    body = material_textures(body, textures)
    spans = mesh.spans(body, root)
    start, end = spans["m_SavedProperties", "m_Floats"]
    stream = io.BytesIO(body[start:end])
    scalars = {}
    for _ in range(material_count(stream)):
        name = material_string(stream)
        scalars[name] = W.B.exact(stream, 4)
    if stream.tell() != end - start:
        raise ValueError("unconsumed original material scalar fields")
    for name, value in defaults.items():
        scalars.setdefault(name, value)
    replacement = io.BytesIO()
    replacement.write(struct.pack("<I", len(scalars)))
    for name, value in sorted(scalars.items()):
        OBJECTS.aligned_string(replacement, name)
        replacement.write(value)
    return body[:start] + replacement.getvalue() + body[end:]


def shared_defaults(pc, selected, sdk, builtin_extra, registry, packs, destination):
    """Render J850's authored default scene from original/SDK source records.

    Source 1780ea9 LabBuild creates the Cube primitive and LabDiagnostics; that
    fixed scene policy owns these preloads. Original native RenderSettings owns
    the cookie relationship, with a hash-matched original scene schema. Shader
    bodies come through the existing source-produced record-pack contract.
    Return provider pins in the same form as shader_manifests for final checks.
    """
    if builtin_extra is None:
        raise ValueError("shared defaults require explicit SDK builtin-extra input")
    pc, sdk = Path(pc), Path(sdk)
    shared = OBJECTS.M.safe_input(pc, selected["source"]["path"])
    scene = OBJECTS.M.safe_input(pc, selected["scene"]["path"])
    schema_path = OBJECTS.M.safe_input(pc, selected["render_schema"]["path"])
    extra = Path(builtin_extra).absolute()
    defaults = sdk / "Data" / DEFAULT
    pins = {
        shared: (selected["source"]["bytes"], selected["source"]["sha256"]),
        scene: (selected["scene"]["bytes"], selected["scene"]["sha256"]),
        schema_path: (schema_path.stat().st_size, selected["render_schema"]["sha256"]),
        extra: (selected["sdk_source"]["bytes"], selected["sdk_source"]["sha256"]),
        defaults: SDK.FILES["Data/" + DEFAULT],
    }
    for path, pin in pins.items():
        checked(path, pin)
    selections = [
        {
            "name": "assets/bin/Data/" + selected["file"],
            "objects": [{"path_id": identity, "record": selected["shader_record"]} for identity in (4, 5)],
        }
    ]
    records, providers = OBJECTS.record_packs(selections, packs, {"name": "apk"})
    shader_bodies = {identity: OBJECTS.record_extent(directory / "objects.bin", row) for (_, identity), (directory, row) in records.items()}
    if set(shader_bodies) != {4, 5}:
        raise ValueError("missing shared source shader")

    def read(path):
        with path.open("rb") as raw:
            raw.size = path.stat().st_size
            return W.read_serialized(raw)

    def body(path, metadata, row):
        with path.open("rb") as raw:
            raw.seek(metadata["data_offset"] + row["offset"])
            return W.B.exact(raw, row["bytes"])

    def named_object(path, metadata, class_id, name, editor=False):
        selected = []
        for row in metadata["objects"]:
            definition = metadata["types"][row["type_id"]]
            if definition["class_id"] != class_id:
                continue
            raw = body(path, metadata, row)
            if editor:
                actual = metadata_fields(raw, definition, {"m_Name"})["m_Name"]
            else:
                actual = material_string(io.BytesIO(raw))
            if actual == name:
                selected.append((row, raw, definition))
        if len(selected) != 1:
            raise ValueError("source native name not unique: " + name)
        return selected[0]

    original, native_scene, sdk, default = map(read, (shared, scene, extra, defaults))
    types_by_class = {row["class_id"]: row for row in original["types"]}
    source_external = {row["path"]: row for row in original["externals"]}
    _, sdk_material, sdk_material_type = named_object(extra, sdk, 21, "Default-Material", True)
    sdk_material_fields = metadata_fields(sdk_material, sdk_material_type, {"m_Shader"})
    standard_pointer = sdk_material_fields["m_Shader"]
    if standard_pointer["m_FileID"] != 0:
        raise ValueError("SDK default Material shader must be same-file")
    default_material = shared_default_material(sdk_material, sdk_material_type, shader_bodies[4])
    _, skybox, _ = named_object(shared, original, 21, "Default-Skybox")
    bodies = {2: default_material, 3: skybox}
    for identity in (2, 3):
        stream = io.BytesIO(bodies[identity])
        material_string(stream)
        location = stream.tell()
        file_id, shader_id = W.B.unpack(stream, "<iq")
        if file_id != 0 or (identity == 2 and shader_id != standard_pointer["m_PathID"]):
            raise ValueError("native source material shader pointer differs")
        revised = bytearray(bodies[identity])
        struct.pack_into("<iq", revised, location, 0, identity + 2)
        bodies[identity] = bytes(revised)
    # Read the actual original SDK Standard dependency through its embedded tree.
    standard_row = next(row for row in sdk["objects"] if row["path_id"] == standard_pointer["m_PathID"])
    standard_type = sdk["types"][standard_row["type_id"]]
    standard_fields = metadata_fields(body(extra, sdk, standard_row), standard_type, {"m_Dependencies"})
    references = set()
    for pointer in standard_fields["m_Dependencies"]:
        if pointer["m_FileID"] != 0:
            raise ValueError("unqualified SDK default shader external")
        references.add((1, pointer["m_PathID"]))
    # Original PC level0 is stripped. An existing admitted original scene owns
    # the same native release schema; its type hash must match before reuse.
    schema_member = W.B.Bundle(schema_path).member(selected["render_schema"]["member"])
    schema_layout = W.read_serialized(schema_member)
    schemas = [row for row in schema_layout["types"] if row["class_id"] == 104]
    native_renders = [row for row in native_scene["objects"] if native_scene["types"][row["type_id"]]["class_id"] == 104]
    if len(schemas) != 1 or len(native_renders) != 1:
        raise ValueError("original RenderSettings source schema is ambiguous")
    native_definition = native_scene["types"][native_renders[0]["type_id"]]
    if {k: v for k, v in schemas[0].items() if k not in {"tree", "dependencies"}} != native_definition:
        raise ValueError("original RenderSettings native schema identity differs")
    cookie = metadata_fields(body(scene, native_scene, native_renders[0]), schemas[0], {"m_SpotCookie"})["m_SpotCookie"]
    if (
        not 0 < cookie["m_FileID"] <= len(native_scene["externals"])
        or native_scene["externals"][cookie["m_FileID"] - 1]["path"] != "Library/unity default resources"
    ):
        raise ValueError("original cookie external resource differs")
    cookie_row, _, _ = named_object(defaults, default, 28, "Soft")
    if cookie["m_PathID"] != cookie_row["path_id"]:
        raise ValueError("original cookie source named identity differs")
    references.add((2, cookie["m_PathID"]))
    cube_row, _, _ = named_object(defaults, default, 43, "Cube")
    references.add((2, cube_row["path_id"]))
    script_ids = registry["script_ids"]
    script_identity = ("Assembly-CSharp.dll", "", "LabDiagnostics")
    if script_identity not in script_ids:
        raise ValueError("source LabDiagnostics registry identity missing")
    references.add((3, script_ids[script_identity]))
    preloads = [row for row in original["objects"] if original["types"][row["type_id"]]["class_id"] == 150]
    if len(preloads) != 1:
        raise ValueError("source scene preload is ambiguous")
    source_preload = body(shared, original, preloads[0])
    stream = io.BytesIO(source_preload)
    if material_string(stream) != "":
        raise ValueError("source scene preload name differs")
    start = stream.tell()
    count = material_count(stream)
    W.B.exact(stream, count * 12)
    suffix = source_preload[stream.tell() :]
    result = io.BytesIO(source_preload[:start])
    result.seek(0, 2)
    result.write(struct.pack("<I", len(references)))
    for pointer in sorted(references):
        result.write(struct.pack("<iq", *pointer))
    result.write(suffix)
    bodies[1] = result.getvalue()
    bodies.update(shader_bodies)
    classes = {1: 150, 2: 21, 3: 21, 4: 48, 5: 48}
    types, objects, cursor = [], [], 0
    for identity in sorted(bodies):
        typ = types_by_class[classes[identity]]
        if typ not in types:
            types.append(typ)
        cursor = (cursor + 7) // 8 * 8
        objects.append(
            {
                "path_id": identity,
                "offset": cursor,
                "bytes": len(bodies[identity]),
                "type_id": types.index(typ),
            }
        )
        cursor += len(bodies[identity])
    layout = {
        "engine": "2021.3.45f2",
        "platform": default["platform"],
        "trees": False,
        "types": types,
        "objects": objects,
        "scripts": [],
        "externals": [
            source_external[name]
            for name in (
                "Resources/unity_builtin_extra",
                "Library/unity default resources",
                "globalgamemanagers.assets",
            )
        ],
        "ref_types": [],
        "user": "",
    }
    with destination.open("xb") as output:
        W.write_serialized(output, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    OBJECTS.check_record_packs(providers)
    for path, pin in pins.items():
        checked(path, pin)
    result = list(pins.items())
    for directory, receipt_sha256, value in providers.values():
        receipt = directory / "result.json"
        result.append((receipt, (receipt.stat().st_size, receipt_sha256)))
        result.extend((directory / name, (pin["bytes"], pin["sha256"])) for name, pin in value["outputs"].items())
    return result


def registry_records(profile_root, selected, pc, editor_resources, code_request, managed_production):
    """Bind the existing original-input code request to the script identity owner."""
    if code_request is None or managed_production is None or editor_resources is None:
        raise ValueError("registry requires code request, managed production and editor resources")
    recipe = OBJECTS.M.safe_input(profile_root, selected["path"])
    checked(recipe, (recipe.stat().st_size, selected["sha256"]))
    request_path = Path(code_request).resolve(strict=True)
    request_pin = request_path.stat().st_size, sha(request_path)
    request = json.loads(request_path.read_text())
    packages = Path(request["source_inputs"]["packages"]).resolve(strict=True)
    # The existing source-input factory keeps its flat packages/<relative>
    # manifest beside the packages directory; it is not a new receipt format.
    value = SCRIPT.registry(
        pc,
        editor_resources,
        managed_production,
        request["target"]["source"],
        packages,
        packages.parent / "input-hashes.json",
        json.loads(recipe.read_text()),
        W,
    )
    value["provider_pins"][str(recipe)] = {"bytes": recipe.stat().st_size, "sha256": selected["sha256"]}
    value["provider_pins"][str(request_path)] = {"bytes": request_pin[0], "sha256": request_pin[1]}
    checked(recipe, (recipe.stat().st_size, selected["sha256"]))
    checked(request_path, request_pin)
    return value


def produce(
    profile_path,
    profile_sha256,
    pc,
    sdk,
    converter,
    converter_receipt_sha256,
    output,
    texture_packs=(),
    builtin_extra=None,
    editor_resources=None,
    code_request=None,
    managed_production=None,
    record_packs=(),
    ui_profile=None,
    ugui_source=None,
    stage_context_profile=None,
):
    """Write a new target tree; never use target bytes as a source provider."""
    profile_path = Path(profile_path)
    if sha(profile_path) != profile_sha256:
        raise ValueError("player-data profile drift")
    profile = json.loads(profile_path.read_text())
    if (
        set(profile) - {"objects", "textures", "builtin_ui", "script_properties_sdk", "registry", "shared_defaults"}
        != {"input_id", "sources", "outputs", "project_assemblies", "font", "text_assets", "sprites"}
        or profile["input_id"] != INPUT_ID
    ):
        raise ValueError("unknown player-data profile")
    pc, sdk, converter = [Path(path).resolve(strict=True) for path in (pc, sdk, converter)]
    if any(not path.is_dir() for path in (pc, sdk, converter)):
        raise ValueError("original PC, AndroidPlayer SDK and converter directories required")
    output = Path(output)
    output = output.parent.resolve(strict=True) / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink():
        raise ValueError("player-data output must be new with an existing parent")
    if any(output.is_relative_to(source) or source.is_relative_to(output) for source in (pc, sdk, converter)):
        raise ValueError("player-data output must be separate from source inputs")
    expected = {DEFAULT: SDK.FILES["Data/" + DEFAULT], **RESOURCES}
    if shutil.disk_usage(output.parent).free < RESERVE + sum(size for size, _ in expected.values()) + sum(row["bytes"] for row in profile["outputs"].values()):
        raise ValueError("insufficient player-data output capacity")
    output.mkdir()
    started = time.monotonic()
    result = {"success": False, "input_id": INPUT_ID, "profile_sha256": profile_sha256, "converter_receipt_sha256": converter_receipt_sha256, "files": {}}
    try:
        registry_pins = []
        script_sdk_tree = None
        if "script_properties_sdk" in profile:
            script_sdk_tree = script_sdk_schema(editor_resources, profile["script_properties_sdk"])
        receipt = converter / "result.json"
        if receipt.resolve(strict=True) != receipt or sha(receipt) != converter_receipt_sha256:
            raise ValueError("converter receipt drift or redirection")
        converted = json.loads(receipt.read_text())
        if converted.get("exit_code") != 0 or converted.get("inputs_unchanged") is not True:
            raise ValueError("successful converter receipt required")
        for name, (size, digest) in RESOURCES.items():
            if converted["files"].get("data/" + name.removeprefix("Managed/")) != {"bytes": size, "sha256": digest}:
                raise ValueError("converter resource differs from accepted comparison hash: " + name)
        original = {}
        pc_sources = {}
        for name in ("ScriptingAssemblies.json", "RuntimeInitializeOnLoads.json"):
            row = profile["sources"][name]
            relative = PurePosixPath(row["path"])
            if relative.is_absolute() or ".." in relative.parts or "\\" in row["path"]:
                raise ValueError("unsafe player-data original path")
            source = pc / relative
            checked(source, (row["bytes"], row["sha256"]))
            original[name] = json.loads(source.read_text())
            pc_sources[name] = source
        generated = metadata(original["ScriptingAssemblies.json"], original["RuntimeInitializeOnLoads.json"], profile["project_assemblies"])
        sources = {}
        for name, pin in expected.items():
            role = "sdk" if name == DEFAULT else "converter"
            source_root = sdk if role == "sdk" else converter
            source = source_root / ("Data" if role == "sdk" else "data") / name.removeprefix("Managed/")
            checked(source, pin)
            sources[name] = source
            destination = output / (TARGET + name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            result["files"][TARGET + name] = {
                "bytes": pin[0],
                "sha256": pin[1],
                "source_role": role,
                "source": source.relative_to(source_root).as_posix(),
            }
        for name, body in generated.items():
            row = profile["outputs"][name]
            if (len(body), hashlib.sha256(body).hexdigest()) != (row["bytes"], row["sha256"]):
                raise ValueError("generated player metadata differs: " + name)
            (output / (TARGET + name)).write_bytes(body)
            result["files"][TARGET + name] = {**row, "source_role": "pc-and-authored", "source": profile["sources"][name]["path"]}
        font = profile["font"]
        name = font["file"]
        if name in ("", ".", "..") or PurePosixPath(name).name != name or "\\" in name:
            raise ValueError("unsafe font player filename")
        object_file(pc, font, output / (TARGET + name), script_sdk_tree)
        result["files"][TARGET + name] = {**profile["outputs"][name], "source_role": "pc-objects", "source": font["source"]["path"]}
        sprites = profile["sprites"]
        selections = [{"source": sprites["source"], **selected} for selected in sprites["files"]] + profile.get("objects", [])
        for selection in selections:
            name = selection["file"]
            if name in ("", ".", "..") or PurePosixPath(name).name != name or "\\" in name:
                raise ValueError("unsafe object player filename")
            object_file(pc, selection, output / (TARGET + name), script_sdk_tree)
            result["files"][TARGET + name] = {**profile["outputs"][name], "source_role": "pc-objects", "source": selection["source"]["path"]}
        texture_files(pc, profile["font"]["source"], profile.get("textures", []), texture_packs, output, result)
        if "builtin_ui" in profile:
            name = profile["builtin_ui"]["file"]
            if name in ("", ".", "..") or PurePosixPath(name).name != name or "\\" in name:
                raise ValueError("unsafe built-in UI player filename")
            builtin_ui(pc, profile, builtin_extra, output / (TARGET + name))
            result["files"][TARGET + name] = {**profile["outputs"][name], "source_role": "sdk-and-pc-types", "source": "unity_builtin_extra"}
        text_files(profile_path.parent.resolve(strict=True), pc, profile["text_assets"], output)
        for item in profile["text_assets"]["files"]:
            name = item["file"]
            result["files"][TARGET + name] = {
                **profile["outputs"][name],
                "source_role": "pc-and-authored" if "recipe" in item or "manifest" in item or item.get("language") is True else "pc-objects",
                "source": item["recipe"]["path"]
                if "recipe" in item
                else profile["text_assets"]["manifests"]["path"]
                if "manifest" in item
                else "Risk of Rain 2_Data/StreamingAssets/Language/en"
                if item.get("language") is True
                else profile["text_assets"]["source"]["path"],
            }
        if "registry" in profile:
            registry = registry_records(profile_path.parent.resolve(strict=True), profile["registry"], pc, editor_resources, code_request, managed_production)
            name = profile["registry"]["file"]
            if PurePosixPath(name).name != name or name in ("", ".", "..") or "\\" in name:
                raise ValueError("unsafe registry player filename")
            with (output / (TARGET + name)).open("xb") as target:
                W.write_serialized(target, registry["layout"], lambda row: io.BytesIO(registry["bodies"][row["path_id"]]))
            result["files"][TARGET + name] = {"source_role": "pc-sdk-and-authored", "source": profile["registry"]["path"]}
            registry_pins = [(Path(path), (pin["bytes"], pin["sha256"])) for path, pin in registry["provider_pins"].items()]
            if "shared_defaults" in profile:
                selected = profile["shared_defaults"]
                name = selected["file"]
                if PurePosixPath(name).name != name or name in ("", ".", "..") or "\\" in name:
                    raise ValueError("unsafe shared-default player filename")
                registry_pins.extend(shared_defaults(pc, selected, sdk, builtin_extra, registry, record_packs, output / (TARGET + name)))
                result["files"][TARGET + name] = {"source_role": "pc-sdk-and-record-packs", "source": selected["source"]["path"]}
            result["registry_inputs"] = {str(path): {"bytes": pin[0], "sha256": pin[1]} for path, pin in registry_pins}
        elif "shared_defaults" in profile:
            raise ValueError("shared defaults require the source registry")
        if ui_profile is not None:
            if "registry" not in profile or ugui_source is None:
                raise ValueError("source UI requires the generated registry and exact SDK UGUI source")
            ui = OBJECTS.module("_player_ui", Path(__file__).with_name("player_ui.py"))
            produced_ui = ui.produce(
                ui_profile[0], ui_profile[1], pc, profile, builtin_extra, editor_resources, ugui_source, managed_production, registry, output / TARGET
            )
            result["ui"] = produced_ui
            result["files"].update({TARGET + name: row for name, row in produced_ui["files"].items()})
        if stage_context_profile is not None:
            contexts = OBJECTS.module("_player_stage_contexts", Path(__file__).with_name("stage_contexts.py"))
            produced_contexts = contexts.produce(stage_context_profile[0], stage_context_profile[1], pc, output / "stage-context-source")
            for name, row in produced_contexts["files"].items():
                shutil.copyfile(output / "stage-context-source" / name, output / (TARGET + name))
                checked(output / (TARGET + name), (row["bytes"], row["sha256"]))
                result["files"][TARGET + name] = dict(row, source_role="original-stage-contexts")
            result["stage_contexts"] = produced_contexts
        # Re-read persisted files and their providers before declaring success.
        for name, pin in expected.items():
            checked(output / (TARGET + name), pin)
            checked(sources[name], pin)
        for name, row in profile["outputs"].items():
            checked(output / (TARGET + name), (row["bytes"], row["sha256"]))
            result["files"][TARGET + name].update(row)
        for name, source in pc_sources.items():
            row = profile["sources"][name]
            checked(source, (row["bytes"], row["sha256"]))
        if sha(receipt) != converter_receipt_sha256:
            raise ValueError("converter receipt changed during production")
        if "script_properties_sdk" in profile:
            pin = profile["script_properties_sdk"]
            checked(Path(editor_resources).absolute(), (pin["bytes"], pin["sha256"]))
        for path, pin in registry_pins:
            checked(path, pin)
        result["success"] = True
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        result["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True, help="original installation root; output must be disjoint")
    parser.add_argument("--sdk", type=Path, required=True, help="owner's pinned AndroidPlayer SDK root")
    parser.add_argument("--builtin-extra", type=Path, help="owner's pinned editor Resources/unity_builtin_extra; required for built-in UI")
    parser.add_argument("--editor-resources", type=Path, help="owner's pinned editor Resources/unity editor resources; required for selected script properties")
    parser.add_argument("--converter", type=Path, required=True, help="fresh converter directory containing data/ and result.json")
    parser.add_argument("--converter-receipt-sha256", required=True)
    parser.add_argument(
        "--code-request", type=Path, help="existing original-input code request, with target.source and source_inputs.packages; required for registry"
    )
    parser.add_argument("--managed-production", type=Path, help="successful source-produced managed directory; required for registry")
    parser.add_argument("--ui-profile", nargs=2, metavar=("PROFILE", "SHA256"), help="current source Menu profile; requires registry and SDK UGUI source")
    parser.add_argument("--stage-context-profile", nargs=2, metavar=("PROFILE", "SHA256"), help="current original-record stage context profile")
    parser.add_argument("--ugui-source", type=Path, help="exact SDK com.unity.ugui Runtime/UI/Core source directory; required for source Menu")
    parser.add_argument(
        "--record-pack",
        nargs=2,
        action="append",
        default=[],
        metavar=("DIRECTORY", "RECEIPT_SHA256"),
        help="existing source-produced object pack; repeat for shared shaders",
    )
    parser.add_argument(
        "--texture-pack",
        nargs=2,
        action="append",
        default=[],
        metavar=("DIRECTORY", "RECEIPT_SHA256"),
        help="source-produced texture pack and pinned result.json; repeat for each producer",
    )
    parser.add_argument("--output", type=Path, required=True, help="new private target-tree root; parent must exist")
    args = parser.parse_args()
    produce(
        args.profile,
        args.profile_sha256,
        args.pc,
        args.sdk,
        args.converter,
        args.converter_receipt_sha256,
        args.output,
        args.texture_pack,
        args.builtin_extra,
        args.editor_resources,
        args.code_request,
        args.managed_production,
        args.record_pack,
        args.ui_profile,
        args.ugui_source,
        args.stage_context_profile,
    )


if __name__ == "__main__":
    main()
