"""Emit a typed texture readback fixture from current originals and producer packs."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import bundle_prepare as prepare
import bundle_preload as preload
from bundle_endpoints import InputPins
from whole_game_scoreboard import serialized_members


O = preload.O
TEXTURES = {28: "Texture2D", 89: "Cubemap"}
NAME = "source-texture-catalog"
MEMBER = "CAB-f05917d43bafd07cc371ad817060c6ad"


def producer_routes(request, pins, providers):
    """Join profiles to pack rows in explicit supplier priority order."""
    routes = defaultdict(list)
    for supplier in request["suppliers"]:
        profile_path = pins.pin(supplier["profile"])
        profile = json.loads(profile_path.read_bytes())
        receipt_path = pins.pin(supplier["receipt"])
        directory = receipt_path.parent
        receipt, index = providers.provider(directory)
        profile_hash = supplier["profile"]["sha256"]
        if receipt["profile_sha256"] != profile_hash or receipt["input_id"] != profile["input_id"]:
            raise ValueError("Texture producer profile or input differs from receipt")
        for filename, pin in receipt["outputs"].items():
            pins.add(directory / filename, pin)
        types = json.loads((directory / "types.json").read_bytes())
        for bundle in profile["bundles"]:
            for member in bundle["members"]:
                for texture in member["textures"]:
                    target = texture["outputs"][0]
                    key = target["bundle"], target["member"], target["path_id"]
                    row = index[key][0]
                    typ = O.json_layout(types[row["type_id"]])
                    routes[bundle["path"], member["name"]].append((bundle["sha256"], texture, target, row, typ, directory, profile_hash))
    return routes


def original_textures(pc, data, routes):
    paths = sorted((data / "StreamingAssets/aa/StandaloneWindows64").glob("*.bundle"))
    if not paths:
        raise ValueError("No original PC Addressables bundles")
    paths.extend(sorted(path for path in data.iterdir() if path.is_file()))
    for path in paths:
        if not path.resolve().is_relative_to(pc):
            raise ValueError("Texture catalog input escapes original installation")
        relative = path.relative_to(pc).as_posix()
        source_hash = None
        with serialized_members((path, None)) as (kind, members, _):
            for member, stream in members.items():
                metadata = O.W.read_serialized(stream)
                name = member if kind == "bundle" else path.name
                selectors = {}
                for route in routes.get((relative, name), ()):
                    source_hash = source_hash or O.B.sha(path)
                    if route[0] != source_hash:
                        continue
                    texture = route[1]
                    selectors.setdefault(texture.get("path_id", (texture["offset"], texture["bytes"])), route)
                for obj in metadata["objects"]:
                    typ = metadata["types"][obj["type_id"]]
                    class_id = typ["class_id"]
                    if class_id not in TEXTURES:
                        continue
                    identity = obj["path_id"]
                    extent = metadata["data_offset"] + obj["offset"], obj["bytes"]
                    route = selectors.get(identity, selectors.get(extent))
                    if route and (route[1]["offset"], route[1]["bytes"]) != extent:
                        raise ValueError("Original texture extent differs from its profile")
                    yield (relative, name, identity), class_id, route


def prepare_catalog(request_path, output):
    request_path, output = request_path.resolve(strict=True), output.resolve()
    pins = InputPins(request_path.parent, preload)
    request = json.loads(pins.add(request_path).read_bytes())
    pc = pins.path(request["pc"])
    data = pc / request["data"]
    if not data.resolve().is_relative_to(pc) or output.is_relative_to(pc):
        raise ValueError("Texture catalog read/write roots overlap or escape")
    providers = preload.ProducerRecords()
    routes = producer_routes(request, pins, providers)
    output.mkdir(parents=True, exist_ok=False)
    totals = {name: Counter(exact=0, approximate=0, missing=0) for name in TEXTURES.values()}
    schemas = {}
    next_identity = 2  # AssetBundle occupies PathID 1.
    with (
        (output / "selected-records.jsonl").open("x") as records,
        (output / "selected-roots.jsonl").open("x") as roots,
        (output / "coverage.jsonl").open("x") as coverage,
    ):
        for source, class_id, route in original_textures(pc, data, routes):
            name = TEXTURES[class_id]
            witness = dict(source=source, type=name, status="missing")
            if route:
                _, _, target, row, typ, directory, profile_hash = route
                for field in ("hash", "tree", "script_id"):
                    if field in typ:
                        typ[field] = bytes.fromhex(typ[field])
                if typ["class_id"] != class_id:
                    raise ValueError("Produced texture class differs from original")
                destination = NAME, MEMBER, next_identity
                next_identity += 1
                provider = dict(provider=str(directory), record_source=[row["bundle"], row["member"], row["path_id"]], record=profile_hash)
                _, body = providers.record(dict(provider, sha256=row["sha256"]))
                desc = prepare.record_descriptor(preload, {}, destination, body, typ, **provider)
                if any(pid for _, pid in desc["edges"]):
                    raise ValueError("Texture readback fixture needs closed source leaves")
                if "resource" in row:
                    desc["resource"] = row["resource"]
                layout = O.json_layout(typ)
                if schemas.setdefault(desc["schema"], layout) != layout:
                    raise ValueError("Conflicting texture producer types")
                exact = row.get("historical_raw_exact", True) and row["sha256"] == target["sha256"]
                asset = f"assets/lab/texture-catalog/{destination[2]}.asset"
                records.write(json.dumps(desc) + "\n")
                roots.write(json.dumps(dict(destination=destination, class_id=class_id, path=asset)) + "\n")
                witness.update(status="exact" if exact else "approximate", asset=asset, provider=profile_hash, operation=route[1]["operation"])
            totals[name][witness["status"]] += 1
            coverage.write(json.dumps(witness) + "\n")
    pins.check()
    (output / "schemas.json").write_text(json.dumps(schemas) + "\n")
    receipt = dict(success=True, scope="original PC texture identities", exact_relative_to="producer recipe", classes=totals)
    (output / "done.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_catalog(args.request, args.output), indent=2))


if __name__ == "__main__":
    main()
