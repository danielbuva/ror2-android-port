"""Produce a complete qualified prefab or scene bundle's objects from original PC records.

UnityPy 1.25.3 and AssetRipper 1ac666f document the serialized type/script
relationships. Bodies and embedded type trees come from the owner's input;
only explicit PPtr identities and authored bundle-container metadata change.
"""

import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import time


def module(name, path=None):
    spec = importlib.util.spec_from_file_location("_objects_" + name, path or Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


W, M = module("unity_write"), module("mesh_produce")
B = W.B


def remap(body, references):
    """Replace checked 12-byte PPtrs; preserve every other source byte."""
    result = bytearray(body)
    previous = -12
    for row in sorted(references, key=lambda item: item["offset"]):
        offset = row["offset"]
        if type(offset) is not int or offset < previous + 12 or offset % 4 or offset + 12 > len(body):
            raise ValueError("invalid or overlapping PPtr extent")
        if list(struct.unpack_from("<iq", body, offset)) != row["from"]:
            raise ValueError("original PPtr identity drift")
        struct.pack_into("<iq", result, offset, *row["to"])
        previous = offset
    return bytes(result)


def demote_material_keywords(body):
    """Retain original keywords as invalid for the qualified dummy shader.

    The authored dummy shader declares no material keywords. Preserve the
    original valid-then-invalid order, every keyword string and all other
    original material values; no shader/material payload comes from a recipe.
    """
    stream = io.BytesIO(body)

    def string():
        size = B.unpack(stream, "<I")[0]
        B.exact(stream, size)
        B.exact(stream, -stream.tell() % 4)

    string()  # Original material name.
    B.exact(stream, 12)  # Shader PPtr, relocated separately.
    start = stream.tell()
    valid_count = B.unpack(stream, "<I")[0]
    if valid_count > len(body) // 4:
        raise ValueError("invalid material keyword count")
    valid_start = stream.tell()
    for _ in range(valid_count):
        string()
    valid_end = stream.tell()
    invalid_count = B.unpack(stream, "<I")[0]
    if invalid_count > len(body) // 4:
        raise ValueError("invalid material keyword count")
    invalid_start = stream.tell()
    for _ in range(invalid_count):
        string()
    end = stream.tell()
    return body[:start] + struct.pack("<II", 0, valid_count + invalid_count) + body[valid_start:valid_end] + body[invalid_start:end] + body[end:]


def remove_components(body, removals):
    """Apply the existing build's explicit native-audio component omissions."""
    count = struct.unpack_from("<I", body)[0]
    end = 4 + count * 12
    if end > len(body):
        raise ValueError("truncated original GameObject component array")
    selected = {}
    for removal in removals:
        index = removal["index"]
        if type(index) is not int or not 0 <= index < count or index in selected:
            raise ValueError("invalid or repeated omitted component index")
        if struct.unpack_from("<iq", body, 4 + index * 12) != (0, removal["path_id"]):
            raise ValueError("omitted original component identity drift")
        selected[index] = removal["path_id"]
    kept = [body[4 + index * 12 : 16 + index * 12] for index in range(count) if index not in selected]
    return struct.pack("<I", len(kept)) + b"".join(kept) + body[end:]


def aligned_string(stream, value):
    data = value.encode("utf-8")
    stream.write(struct.pack("<I", len(data)) + data)
    W.padding(stream, 4)


def asset_bundle(selected, identities):
    """Build Unity's release AssetBundle metadata, without target body literals."""
    stream = io.BytesIO()
    aligned_string(stream, selected["name"])
    scene = "scene_path" in selected
    if scene:
        preload = []
        assets = [{"path": selected["scene_path"], "root": 0, "preload": []}]
    elif "assets" in selected:
        assets = selected["assets"]
        preload = [pointer for asset in assets for pointer in asset["preload"]]
        if any(file_id == 0 and path_id not in identities for file_id, path_id in preload):
            raise ValueError("container preload references an absent local object")
    else:
        local = [(0, identity) for identity in sorted(identities)]
        external = selected["external_objects"]
        preload = external + local if selected.get("external_preload_first", False) else local + external
        assets = [{"path": selected["asset"], "root": selected["root"], "preload": preload}]
    stream.write(struct.pack("<I", len(preload)))
    for file_id, path_id in preload:
        stream.write(struct.pack("<iq", file_id, path_id))
    stream.write(struct.pack("<I", len(assets)))
    start = 0
    containers = []
    for asset in assets:
        if not scene and asset["root"] not in identities:
            raise ValueError("container root references an absent local object")
        containers.append((asset, start))
        start += len(asset["preload"])
    for asset, start in sorted(containers, key=lambda item: item[0]["path"].lower()):
        aligned_string(stream, asset["path"] if scene else asset["path"].lower())
        stream.write(struct.pack("<iiiq", start, len(asset["preload"]), 0, asset["root"]))
    stream.write(struct.pack("<iiiqI", 0, 0, 0, 0, 1))
    aligned_string(stream, "" if scene else selected["name"])
    dependencies = [] if scene else selected["dependencies"]
    stream.write(struct.pack("<I", len(dependencies)))
    for dependency in dependencies:
        aligned_string(stream, dependency)
    # Release bundle: streamed-scene marker, explicit layout off, path flags.
    stream.write(struct.pack("<B3xiii", scene, 0, 7, 0))
    return stream.getvalue()


def preload_data(bundle, selected, members):
    """Collect scene dependencies from checked relocated external PPtrs."""
    references = set()
    names = {member["name"] for member in members}
    for member in members:
        for row in member["objects"]:
            for reference in row.get("references", []):
                file_id, path_id = reference["to"]
                if not file_id or not path_id:
                    continue
                if not 1 <= file_id <= len(member["externals"]):
                    raise ValueError("scene reference has an absent external file")
                name = member["externals"][file_id - 1]
                if name not in names:
                    references.add((selected["externals"].index(name) + 1, path_id))
    stream = io.BytesIO()
    aligned_string(stream, "")
    stream.write(struct.pack("<I", len(references)))
    for pointer in sorted(references):
        stream.write(struct.pack("<iq", *pointer))
    stream.write(struct.pack("<I", len(bundle["dependencies"])))
    for name in bundle["dependencies"]:
        aligned_string(stream, name)
    stream.write(bytes(1))
    return stream.getvalue()


def json_layout(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: json_layout(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_layout(item) for item in value]
    return value


def make_layout(selected, records, scene_members=()):
    """Canonical release order: script records first, then remaining path IDs."""
    local_scripts = sorted(row["path_id"] for row in records if row["type"]["class_id"] == 115)
    scripts = (
        sorted({struct.unpack_from("<iq", row["body"], 16) for row in records if row["type"]["class_id"] == 114})
        if scene_members
        else [(0, identity) for identity in local_scripts]
    )
    physical = sorted(records, key=lambda row: (row["path_id"] not in local_scripts, row["path_id"]))
    types, objects, bodies = [], [], {}
    offset = 0
    for row in physical:
        typ = copy.deepcopy(row["type"])
        if typ["class_id"] == 114:
            file_id, script = struct.unpack_from("<iq", row["body"], 16)
            if (file_id and not scene_members) or (not file_id and script not in local_scripts) or not 0 <= file_id <= len(selected["externals"]):
                raise ValueError("MonoBehaviour script absent from produced bundle")
            typ["script_type"] = scripts.index((file_id, script))
        if typ not in types:
            types.append(typ)
        offset = (offset + 7) // 8 * 8
        identity = row["path_id"]
        if identity in bodies:
            raise ValueError("duplicate produced object identity")
        bodies[identity] = row["body"]
        objects.append({"path_id": identity, "offset": offset, "bytes": len(row["body"]), "type_id": types.index(typ)})
        offset += len(row["body"])
    # Unity's native resources live outside the AssetBundles.
    native = {"Resources/unity_builtin_extra": 0x0F, "Library/unity default resources": 0x0E}
    externals = [
        {"empty": "", "guid": bytes(8) + bytes([native[name]]) + bytes(7), "type": 0, "path": name}
        if name in native
        else {
            "empty": "",
            "guid": bytes(16),
            "type": 0,
            "path": "archive:/" + (name.removesuffix(".sharedAssets") if name in scene_members else name) + "/" + name,
        }
        for name in selected["externals"]
    ]
    return {
        "engine": "2021.3.45f2",
        "platform": 13,
        "trees": True,
        "types": types,
        "objects": sorted(objects, key=lambda row: row["path_id"]),
        "scripts": scripts,
        "externals": externals,
        "ref_types": [],
        "user": "",
    }, bodies


def record_packs(members, supplied, bundle):
    """Read selected independently produced records; receipts pin their providers."""
    selections = [(member["name"], row) for member in members for row in member["objects"]]
    required = {row["record"] for _, row in selections if "record" in row}
    records, providers = {}, {}
    for directory, receipt_sha256 in supplied:
        directory = Path(directory).resolve(strict=True)
        receipt = directory / "result.json"
        if B.sha(receipt) != receipt_sha256:
            raise ValueError("record producer receipt drift")
        value = json.loads(receipt.read_text())
        profile = value.get("profile_sha256")
        if value.get("success") is not True or value.get("input_id") != M.INPUT_ID or profile not in required or profile in providers:
            raise ValueError("unexpected or unsuccessful record producer")
        if not {"objects.bin", "index.jsonl"} <= value["outputs"].keys() or value["outputs"].keys() - {"objects.bin", "resources.bin", "index.jsonl"}:
            raise ValueError("incomplete record producer outputs")
        providers[profile] = directory, receipt_sha256, value
    if providers.keys() != required:
        raise ValueError("missing source-produced record pack")
    check_record_packs(providers)
    for profile, (directory, _, _) in providers.items():
        wanted = {(member, row["path_id"]) for member, row in selections if row.get("record") == profile}
        with (directory / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                key = row["member"], row["path_id"]
                if row["bundle"] != bundle["name"] or key not in wanted:
                    continue
                if key in records:
                    raise ValueError("duplicate produced record identity")
                records[key] = directory, row
        if not wanted <= records.keys():
            raise ValueError("produced record missing")
    return records, providers


def check_record_packs(providers):
    for directory, receipt_sha256, value in providers.values():
        for name, pin in value["outputs"].items():
            path = directory / name
            if path.stat().st_size != pin["bytes"] or B.sha(path) != pin["sha256"]:
                raise ValueError("record producer output drift")
        if B.sha(directory / "result.json") != receipt_sha256:
            raise ValueError("record producer receipt drift")


def record_extent(path, row):
    offset, size = row["offset"], row["bytes"]
    if type(offset) is not int or type(size) is not int or offset < 0 or not 0 <= size <= B.LIMIT or offset + size > path.stat().st_size:
        raise ValueError("produced record extent escapes pack")
    with path.open("rb") as stream:
        stream.seek(offset)
        data = B.exact(stream, size)
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("produced record extent drift")
    return data


def source_record(sources, selector):
    source, identity = selector
    _, _, member, metadata, objects = sources[source]
    row = objects[identity]
    member.seek(metadata["data_offset"] + row["offset"])
    return B.exact(member, row["bytes"]), metadata["types"][row["type_id"]]


def script_fields(body):
    """Read original release MonoScript identity and its properties-hash extent."""
    stream = io.BytesIO(body)

    def string():
        size = struct.unpack("<I", B.exact(stream, 4))[0]
        value = B.exact(stream, size).decode("utf-8")
        stream.seek((stream.tell() + 3) // 4 * 4)
        return value

    string()  # m_Name
    B.exact(stream, 4)  # m_ExecutionOrder
    offset = stream.tell()
    B.exact(stream, 16)
    return offset, (string(), string(), string())


def produce(profile_path, profile_sha256, pc, output, codec_path, codec_sha256, packs=(), sdk=None):
    if B.sha(profile_path) != profile_sha256:
        raise ValueError("object profile drift")
    profile = json.loads(profile_path.read_text())
    scene = "members" in profile["bundle"]
    required = {"input_id", "sources", "bundle"} | (set() if scene else {"objects"})
    if set(profile) - {"sdk"} != required or profile["input_id"] != M.INPUT_ID:
        raise ValueError("unknown object input profile")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("object output must be new and outside original input")
    selected_bundle = profile["bundle"]
    selected_members = selected_bundle["members"] if scene else [{**selected_bundle, "name": selected_bundle["member"], "objects": profile["objects"]}]
    expected = sum(row["bytes"] for member in selected_members for row in member["objects"])
    if not 0 < expected <= B.LIMIT:
        raise ValueError("object bundle exceeds bounded producer capacity")
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient object output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": M.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        sdk_path, sdk_tree = None, None
        if "sdk" in profile:
            if sdk is None:
                raise ValueError("script properties require the pinned owner SDK")
            sdk_path = M.safe_input(sdk.resolve(strict=True), profile["sdk"]["path"])
            if output.is_relative_to(sdk.resolve()) or B.sha(sdk_path) != profile["sdk"]["sha256"]:
                raise ValueError("SDK script metadata drift or output overlap")
            with sdk_path.open("rb") as stream:
                stream.size = sdk_path.stat().st_size
                metadata = W.read_serialized(stream)
            row = next(row for row in metadata["objects"] if row["path_id"] == profile["sdk"]["path_id"])
            typ = metadata["types"][row["type_id"]]
            if typ["class_id"] != 114:
                raise ValueError("SDK script base is not MonoBehaviour")
            sdk_tree = typ["tree"]
        properties = {}
        identity_owner = module("script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py") if sdk_tree is not None else None
        sources = []
        for selected in profile["sources"]:
            path = M.safe_input(pc, selected["path"])
            before = path.stat()
            if B.sha(path) != selected["sha256"]:
                raise ValueError("original object bundle drift")
            member = B.Bundle(path).member(selected["member"])
            metadata = W.read_serialized(member)
            sources.append((path, before, member, metadata, {row["path_id"]: row for row in metadata["objects"]}))
        records, layouts, members = [], [], []
        packed, providers = record_packs(selected_members, packs, selected_bundle)
        receipt["record_packs"] = {profile: pin for profile, (_, pin, _) in providers.items()}
        resources = {}
        # Load only when needed: the player owner already shares this writer and
        # owns the qualified standalone Sprite recovery arithmetic.
        sprites = module("player_data") if any("importer_guid" in row for member in selected_members for row in member["objects"]) else None
        for selected_member in selected_members:
            member_records = []
            identities = [row["path_id"] for row in selected_member["objects"] if "source" in row or "record" in row]
            for selected in selected_member["objects"]:
                if "record" in selected:
                    directory, row = packed[selected_member["name"], selected["path_id"]]
                    body = record_extent(directory / "objects.bin", row)
                    source, identity = selected["type_source"]
                    typ = sources[source][3]["types"][sources[source][4][identity]["type_id"]]
                    if "resource" in row:
                        resource = row["resource"]
                        extent = resource["stream"]
                        prefix = "archive:/" + selected_member["name"] + "/"
                        name = extent["path"].removeprefix(prefix)
                        if not extent["path"].startswith(prefix) or Path(name).name != name or name == selected_member["name"]:
                            raise ValueError("produced resource belongs to another bundle")
                        data = record_extent(directory / "resources.bin", resource)
                        offset, end = extent["offset"], extent["offset"] + len(data)
                        if extent["size"] != len(data) or offset < 0 or end > B.LIMIT:
                            raise ValueError("produced resource exceeds bounded bundle capacity")
                        resources.setdefault(name, []).append((offset, data))
                elif "source" in selected:
                    source, identity = selected["source"]
                    _, _, member, metadata, objects = sources[source]
                    row = objects[identity]
                    member.seek(metadata["data_offset"] + row["offset"])
                    body = B.exact(member, row["bytes"])
                    if hashlib.sha256(body).hexdigest() != selected["source_sha256"]:
                        raise ValueError("original object body drift")
                    typ = metadata["types"][row["type_id"]]
                    if "remove_components" in selected:
                        if typ["class_id"] != 1:
                            raise ValueError("component omission requires an original GameObject")
                        body = remove_components(body, selected["remove_components"])
                    if "importer_guid" in selected:
                        if typ["class_id"] != 213:
                            raise ValueError("Sprite importer policy requires an original Sprite")
                        if "crop_rectangle_offset" in selected:
                            body = sprites.sprite_crop(body, selected["crop_rectangle_offset"])
                        body = sprites.sprite_key(body, selected["importer_guid"])
                    if "inactive_map_zone" in selected:
                        if selected["inactive_map_zone"] is not True or typ["class_id"] != 1 or not body or body[-1] != 1:
                            raise ValueError("inactive MapZone policy requires an active original GameObject")
                        body = body[:-1] + bytes(1)
                    body = remap(body, selected.get("references", []))
                    if "keyword_policy" in selected:
                        if typ["class_id"] != 21 or selected["keyword_policy"] != "dummy-shader-demote-valid":
                            raise ValueError("unqualified material keyword policy")
                        body = demote_material_keywords(body)
                else:
                    source = selected["type_source"]
                    if isinstance(source, list):
                        _, typ = source_record(sources, source)
                    else:
                        candidates = [row for row in sources[source][3]["types"] if row["class_id"] == 142]
                        if len(candidates) != 1:
                            raise ValueError("missing original AssetBundle type")
                        typ = candidates[0]
                    if selected.get("generate") == "PreloadData":
                        if typ["class_id"] != 150:
                            raise ValueError("scene preload requires original PreloadData type")
                        body = preload_data(selected_bundle, selected_member, selected_members)
                    else:
                        if selected.get("generate", "AssetBundle") != "AssetBundle" or typ["class_id"] != 142:
                            raise ValueError("bundle container requires original AssetBundle type")
                        body = asset_bundle(selected_bundle, identities)
                if "properties_hash" in selected:
                    if sdk_tree is None:
                        raise ValueError("script properties require SDK metadata")
                    selectors = selected["properties_hash"]
                    key = tuple(selectors["script"]), tuple(selectors["behaviour"])
                    if key not in properties:
                        script, script_type = source_record(sources, selectors["script"])
                        _, behaviour_type = source_record(sources, selectors["behaviour"])
                        if script_type["class_id"] != 115 or behaviour_type["class_id"] != 114:
                            raise ValueError("script properties selectors have wrong classes")
                        _, names = script_fields(script)
                        properties[key] = identity_owner.properties_hash(*names, behaviour_type["tree"], sdk_tree)
                    value = properties[key]
                    if typ["class_id"] == 115:
                        offset, _ = script_fields(body)
                        body = body[:offset] + value + body[offset + 16 :]
                    elif typ["class_id"] == 114:
                        typ = copy.deepcopy(typ)
                        typ["hash"] = value
                    else:
                        raise ValueError("script properties require MonoScript or MonoBehaviour")
                if len(body) != selected["bytes"] or hashlib.sha256(body).hexdigest() != selected["sha256"]:
                    raise ValueError("produced object differs from accepted hash")
                member_records.append({"path_id": selected["path_id"], "body": body, "type": typ, "member": selected_member["name"]})
            layout, bodies = make_layout(selected_member, member_records, [member["name"] for member in selected_members] if scene else ())
            serialized = io.BytesIO()
            W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
            serialized_bytes = serialized.getvalue()
            if hashlib.sha256(serialized_bytes).hexdigest() != selected_member["serialized_sha256"]:
                raise ValueError("produced serialized structure differs from accepted hash")
            layout["data_offset"] = struct.unpack_from(">q", serialized_bytes, 32)[0]
            layout["bytes"] = len(serialized_bytes)
            layouts.append({"name": selected_member["name"], **layout} if scene else layout)
            members.append((selected_member["name"], 4, len(serialized_bytes), lambda data=serialized_bytes: io.BytesIO(data)))
            records.extend(sorted(member_records, key=lambda row: row["path_id"]))
        payload = output / "payload"
        payload.mkdir()
        name = selected_bundle["name"]
        if name in ("", ".", "..") or Path(name).name != name:
            raise ValueError("invalid output bundle name")
        bundle_path = payload / name
        for name, extents in resources.items():
            data = bytearray()
            for offset, extent in sorted(extents):
                if offset < len(data):
                    raise ValueError("overlapping produced resource extents")
                data.extend(bytes(offset - len(data)))
                data.extend(extent)
            members.append((name, 0, len(data), lambda data=data: io.BytesIO(data)))
        with W.codec(codec_path, codec_sha256) as compress, bundle_path.open("xb") as stream:
            W.write_bundle(stream, members, compress)
        if bundle_path.stat().st_size != selected_bundle["bytes"] or B.sha(bundle_path) != selected_bundle["sha256"]:
            raise ValueError("produced UnityFS differs from accepted hash")
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for row in records:
                body = row["body"]
                index.write(
                    json.dumps(
                        {
                            "bundle": selected_bundle["name"],
                            "member": row["member"],
                            "path_id": row["path_id"],
                            "offset": data.tell(),
                            "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                data.write(body)
                receipt["objects"] += 1
                receipt["object_bytes"] += len(body)
        (output / "layout.json").write_text(json.dumps(json_layout({"members": layouts} if scene else layouts[0]), sort_keys=True, indent=2) + "\n")
        for selected, (path, before, _, _, _) in zip(profile["sources"], sources, strict=True):
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or B.sha(path) != selected["sha256"]:
                raise ValueError("original object input changed during production")
        check_record_packs(providers)
        if sdk_path is not None and B.sha(sdk_path) != profile["sdk"]["sha256"]:
            raise ValueError("SDK script metadata changed during production")
        with (output / "objects.bin").open("rb") as data:
            for line in (output / "index.jsonl").read_text().splitlines():
                row = json.loads(line)
                data.seek(row["offset"])
                if hashlib.sha256(B.exact(data, row["bytes"])).hexdigest() != row["sha256"]:
                    raise ValueError("persisted object extent drift")
        receipt["outputs"] = {
            name: {"bytes": (output / name).stat().st_size, "sha256": B.sha(output / name)}
            for name in ("objects.bin", "index.jsonl", "layout.json", "payload/" + selected_bundle["name"])
        }
        receipt["serialized_sha256"] = (
            {member["name"]: member["serialized_sha256"] for member in selected_members} if scene else selected_bundle["serialized_sha256"]
        )
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, help="owner's pinned Unity SDK root; required only for script properties derivation")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codec", type=Path, required=True)
    parser.add_argument("--codec-sha256", required=True)
    parser.add_argument(
        "--record-pack",
        nargs=2,
        action="append",
        default=[],
        metavar=("DIRECTORY", "RECEIPT_SHA256"),
        help="independently produced record pack and pinned result.json; repeat for each producer",
    )
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.codec, args.codec_sha256, args.record_pack, args.sdk)


if __name__ == "__main__":
    main()
