"""Produce a complete qualified prefab bundle's objects from original PC records.

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


def module(name):
    spec = importlib.util.spec_from_file_location("_objects_" + name, Path(__file__).with_name(name + ".py"))
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


def aligned_string(stream, value):
    data = value.encode("utf-8")
    stream.write(struct.pack("<I", len(data)) + data)
    W.padding(stream, 4)


def asset_bundle(selected, identities):
    """Build Unity's release AssetBundle metadata, without target body literals."""
    stream = io.BytesIO()
    aligned_string(stream, selected["name"])
    local = [(0, identity) for identity in sorted(identities)]
    external = selected["external_objects"]
    preload = external + local if selected.get("external_preload_first", False) else local + external
    stream.write(struct.pack("<I", len(preload)))
    for file_id, path_id in preload:
        stream.write(struct.pack("<iq", file_id, path_id))
    stream.write(struct.pack("<I", 1))
    aligned_string(stream, selected["asset"].lower())
    stream.write(struct.pack("<iiiq", 0, len(preload), 0, selected["root"]))
    stream.write(struct.pack("<iiiqI", 0, 0, 0, 0, 1))
    aligned_string(stream, selected["name"])
    stream.write(struct.pack("<I", len(selected["dependencies"])))
    for dependency in selected["dependencies"]:
        aligned_string(stream, dependency)
    # Non-scene release bundle: explicit layout off, path flags, no scene hashes.
    stream.write(struct.pack("<B3xiii", 0, 0, 7, 0))
    return stream.getvalue()


def json_layout(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: json_layout(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_layout(item) for item in value]
    return value


def make_layout(selected, records):
    """Canonical release order: script records first, then remaining path IDs."""
    scripts = sorted(row["path_id"] for row in records if row["type"]["class_id"] == 115)
    physical = sorted(records, key=lambda row: (row["path_id"] not in scripts, row["path_id"]))
    types, objects, bodies = [], [], {}
    offset = 0
    for row in physical:
        typ = copy.deepcopy(row["type"])
        if typ["class_id"] == 114:
            file_id, script = struct.unpack_from("<iq", row["body"], 16)
            if file_id or script not in scripts:
                raise ValueError("MonoBehaviour script absent from produced bundle")
            typ["script_type"] = scripts.index(script)
        if typ not in types:
            types.append(typ)
        offset = (offset + 7) // 8 * 8
        identity = row["path_id"]
        if identity in bodies:
            raise ValueError("duplicate produced object identity")
        bodies[identity] = row["body"]
        objects.append({"path_id": identity, "offset": offset, "bytes": len(row["body"]), "type_id": types.index(typ)})
        offset += len(row["body"])
    externals = [{"empty": "", "guid": bytes(16), "type": 0, "path": "archive:/" + name + "/" + name} for name in selected["externals"]]
    return {
        "engine": "2021.3.45f2",
        "platform": 13,
        "trees": True,
        "types": types,
        "objects": sorted(objects, key=lambda row: row["path_id"]),
        "scripts": [(0, identity) for identity in scripts],
        "externals": externals,
        "ref_types": [],
        "user": "",
    }, bodies


def produce(profile_path, profile_sha256, pc, output, codec_path, codec_sha256):
    if B.sha(profile_path) != profile_sha256:
        raise ValueError("object profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) != {"input_id", "sources", "bundle", "objects"} or profile["input_id"] != M.INPUT_ID:
        raise ValueError("unknown object input profile")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("object output must be new and outside original input")
    expected = sum(row["bytes"] for row in profile["objects"])
    if not 0 < expected <= B.LIMIT:
        raise ValueError("object bundle exceeds bounded producer capacity")
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient object output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": M.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        sources = []
        for selected in profile["sources"]:
            path = M.safe_input(pc, selected["path"])
            before = path.stat()
            if B.sha(path) != selected["sha256"]:
                raise ValueError("original object bundle drift")
            member = B.Bundle(path).member(selected["member"])
            metadata = W.read_serialized(member)
            sources.append((path, before, member, metadata, {row["path_id"]: row for row in metadata["objects"]}))
        records = []
        selected_bundle = profile["bundle"]
        identities = [row["path_id"] for row in profile["objects"] if "source" in row]
        for selected in profile["objects"]:
            if "source" in selected:
                source, identity = selected["source"]
                _, _, member, metadata, objects = sources[source]
                row = objects[identity]
                member.seek(metadata["data_offset"] + row["offset"])
                body = B.exact(member, row["bytes"])
                if hashlib.sha256(body).hexdigest() != selected["source_sha256"]:
                    raise ValueError("original object body drift")
                body = remap(body, selected.get("references", []))
                typ = metadata["types"][row["type_id"]]
            else:
                source = selected["type_source"]
                candidates = [row for row in sources[source][3]["types"] if row["class_id"] == 142]
                if len(candidates) != 1:
                    raise ValueError("missing original AssetBundle type")
                typ = candidates[0]
                body = asset_bundle(selected_bundle, identities)
            if len(body) != selected["bytes"] or hashlib.sha256(body).hexdigest() != selected["sha256"]:
                raise ValueError("produced object differs from accepted hash")
            records.append({"path_id": selected["path_id"], "body": body, "type": typ})
        layout, bodies = make_layout(selected_bundle, records)
        serialized = io.BytesIO()
        W.write_serialized(serialized, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
        data = serialized.getvalue()
        if hashlib.sha256(data).hexdigest() != selected_bundle["serialized_sha256"]:
            raise ValueError("produced serialized structure differs from accepted hash")
        layout["data_offset"] = struct.unpack_from(">q", data, 32)[0]
        layout["bytes"] = len(data)
        serialized_bytes = data
        payload = output / "payload"
        payload.mkdir()
        name = selected_bundle["name"]
        if name in ("", ".", "..") or Path(name).name != name:
            raise ValueError("invalid output bundle name")
        bundle_path = payload / name
        with W.codec(codec_path, codec_sha256) as compress, bundle_path.open("xb") as stream:
            W.write_bundle(stream, [(selected_bundle["member"], 4, len(serialized_bytes), lambda: io.BytesIO(serialized_bytes))], compress)
        if bundle_path.stat().st_size != selected_bundle["bytes"] or B.sha(bundle_path) != selected_bundle["sha256"]:
            raise ValueError("produced UnityFS differs from accepted hash")
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for row in sorted(records, key=lambda row: row["path_id"]):
                body = row["body"]
                index.write(
                    json.dumps(
                        {
                            "bundle": selected_bundle["name"],
                            "member": selected_bundle["member"],
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
        (output / "layout.json").write_text(json.dumps(json_layout(layout), sort_keys=True, indent=2) + "\n")
        for selected, (path, before, _, _, _) in zip(profile["sources"], sources, strict=True):
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or B.sha(path) != selected["sha256"]:
                raise ValueError("original object input changed during production")
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
        receipt["serialized_sha256"] = selected_bundle["serialized_sha256"]
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codec", type=Path, required=True)
    parser.add_argument("--codec-sha256", required=True)
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.codec, args.codec_sha256)


if __name__ == "__main__":
    main()
