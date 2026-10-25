"""Produce named accepted player-data files from explicit SDK/converter inputs.

This source-only cohort includes original font and text records and authored
JSON resources, not the remaining startup data or bundles. No accepted APK, replay packet or Unity
project is read. Outputs and receipts remain private; this command does not
install or qualify a player.
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


def object_file(pc, selected, destination):
    """Reuse original player-object bodies and source type identities.

    UnityPy/AssetRipper's PPtr relationship is the same checked remap performed
    by object_produce; the player strips source type trees and retains only its
    selected original external dependency. No font or image data is introduced.
    """
    source = selected["source"]
    path = OBJECTS.M.safe_input(pc, source["path"])
    checked(path, (source["bytes"], source["sha256"]))
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
            if typ not in types:
                types.append(typ)
            offset = (offset + 7) // 8 * 8
            identity = target["path_id"]
            rows.append({"path_id": identity, "offset": offset, "bytes": target["bytes"], "type_id": types.index(typ)})
            selections[identity] = (target, row)
            offset += target["bytes"]
        layout = {
            "engine": original["engine"],
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
            if types[target["type_id"]]["class_id"] == 114 and list(struct.unpack_from("<iq", data, 16)) != selected["script"]:
                raise ValueError("player object script relationship differs")
            if hashlib.sha256(data).hexdigest() != selection["sha256"]:
                raise ValueError("produced player object differs")
            return io.BytesIO(data)

        with destination.open("xb") as output:
            W.write_serialized(output, layout, body)
        checked(path, (source["bytes"], source["sha256"]))


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
            "engine": original["engine"],
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


def produce(profile_path, profile_sha256, pc, sdk, converter, converter_receipt_sha256, output):
    """Write a new target tree; never use target bytes as a source provider."""
    profile_path = Path(profile_path)
    if sha(profile_path) != profile_sha256:
        raise ValueError("player-data profile drift")
    profile = json.loads(profile_path.read_text())
    if (
        set(profile) - {"script_objects"} != {"input_id", "sources", "outputs", "project_assemblies", "font", "text_assets", "sprites"}
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
        object_file(pc, font, output / (TARGET + name))
        result["files"][TARGET + name] = {**profile["outputs"][name], "source_role": "pc-objects", "source": font["source"]["path"]}
        sprites = profile["sprites"]
        selections = [{"source": sprites["source"], **selected} for selected in sprites["files"]] + profile.get("script_objects", [])
        for selection in selections:
            name = selection["file"]
            if name in ("", ".", "..") or PurePosixPath(name).name != name or "\\" in name:
                raise ValueError("unsafe sprite player filename")
            object_file(pc, selection, output / (TARGET + name))
            result["files"][TARGET + name] = {**profile["outputs"][name], "source_role": "pc-objects", "source": selection["source"]["path"]}
        text_files(profile_path.parent.resolve(strict=True), pc, profile["text_assets"], output)
        for item in profile["text_assets"]["files"]:
            name = item["file"]
            result["files"][TARGET + name] = {
                **profile["outputs"][name],
                "source_role": "pc-and-authored" if "recipe" in item else "pc-objects",
                "source": item["recipe"]["path"] if "recipe" in item else profile["text_assets"]["source"]["path"],
            }
        # Re-read persisted files and their providers before declaring success.
        for name, pin in expected.items():
            checked(output / (TARGET + name), pin)
            checked(sources[name], pin)
        for name, row in profile["outputs"].items():
            checked(output / (TARGET + name), (row["bytes"], row["sha256"]))
        for name, source in pc_sources.items():
            row = profile["sources"][name]
            checked(source, (row["bytes"], row["sha256"]))
        if sha(receipt) != converter_receipt_sha256:
            raise ValueError("converter receipt changed during production")
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
    parser.add_argument("--converter", type=Path, required=True, help="fresh converter directory containing data/ and result.json")
    parser.add_argument("--converter-receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True, help="new private target-tree root; parent must exist")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.sdk, args.converter, args.converter_receipt_sha256, args.output)


if __name__ == "__main__":
    main()
