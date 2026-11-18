"""Apply the authored projectile recipe to a previously produced staged prefab bundle."""

import argparse
from contextlib import ExitStack
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile

import bundle_preload as P
import catalog_complete as C

O, W = P.O, C.W
BOUNDARY = ["Assembly-CSharp.dll", "", "SilentProjectileBoundary"]


def patch_records(catalog, member, profile, original, script, sdk_tree):
    """Require a reciprocal projectile component before changing its local binding."""
    _, layout, objects = catalog.members[member]
    (selected_script,) = [row for row in profile["objects"] if row.get("script_identity") == BOUNDARY]
    script_id = selected_script["path_id"]
    O.current_script_identity(script, 115, BOUNDARY)
    if hashlib.sha256(script).hexdigest() != selected_script["sha256"]:
        raise ValueError("produced boundary script differs from recipe")
    _, old_script_type, old_script = catalog.record(member, (0, script_id))
    old_identity = C.script_identity(old_script)
    if old_script_type["class_id"] != 115 or old_identity != ("EventSystem", "UnityEngine.EventSystems", "UnityEngine.UI.dll"):
        raise ValueError("expected a staged EventSystem script")
    replacements = {script_id: script}
    type_updates = {}
    schemas = {}
    for row in profile["objects"]:
        if not row.get("fieldless_script_record") or not any(ref["offset"] == 16 and ref["to"] == [0, script_id] for ref in row["references"]):
            continue
        pid = row["path_id"]
        source_type, source = original(*row["source"])
        if hashlib.sha256(source).hexdigest() != row["source_sha256"]:
            raise ValueError("original component body differs from recipe")
        body = O.remap(source, row["references"])
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ValueError("produced component body differs from recipe")
        _, old, before = catalog.record(member, (0, pid))
        if before[:28] != body[:28] or catalog.managed_identity(member, old, before) != old_identity:
            raise ValueError("staged component owner or script differs")
        owner = struct.unpack_from("<iq", body)
        if {ptr for ptr in P.pointers(before, old, schemas).values() if any(ptr)} != {owner, (0, script_id)}:
            raise ValueError("replacement would remove a staged dependency")
        _, game_object, raw = catalog.record(member, owner)
        if owner[0] or game_object["class_id"] != 1:
            raise ValueError("expected a local projectile GameObject")
        components = [ptr for key, ptr in P.pointers(raw, game_object, schemas).items() if key[:2] == ("m_Component", "Array") and key[-1] == "component"]
        controllers = []
        for ptr in components:
            local, component, data = catalog.record(member, ptr)
            if component["class_id"] == 114 and any(struct.unpack_from("<iq", data, 16)):
                if catalog.managed_identity(local, component, data) == ("ProjectileController", "RoR2.Projectile", "RoR2.dll"):
                    controllers.append((local, struct.unpack_from("<iq", data)))
        if components.count((0, pid)) != 1 or controllers != [(member, owner)]:
            raise ValueError("boundary requires one reciprocal projectile controller")
        if layout["scripts"][old["script_type"]] != (0, script_id):
            raise ValueError("staged script table differs")
        typ = O.fieldless_script_type(body, source_type, script, sdk_tree, C.S)
        index = objects[pid]["type_id"]
        typ = {**typ, "script_type": old["script_type"], "dependencies": old["dependencies"]}
        if type_updates.setdefault(index, typ) != typ:
            raise ValueError("inconsistent fieldless type replacement")
        replacements[pid] = body
    if not type_updates or any(obj["path_id"] not in replacements for obj in objects.values() if obj["type_id"] in type_updates):
        raise ValueError("projectile recipe must cover every user of the replaced type")
    for index, typ in enumerate(layout["types"]):
        if typ["class_id"] == 114 and typ["script_type"] >= 0 and layout["scripts"][typ["script_type"]] == (0, script_id) and index not in type_updates:
            raise ValueError("another serialized type uses the replaced script")
    return replacements, type_updates


def rewrite(bundle, member, catalog, replacements, type_updates, destination, compressor):
    stream, layout, objects = catalog.members[member]
    revised = copy.deepcopy(layout)
    for index, typ in type_updates.items():
        revised["types"][index] = typ
    physical = sorted(revised["objects"], key=lambda obj: obj["offset"])
    offset = 0
    for obj in physical:
        offset = (offset + 7) & ~7
        obj["offset"] = offset
        if obj["path_id"] in replacements:
            obj["bytes"] = len(replacements[obj["path_id"]])
        offset += obj["bytes"]
    revised["bytes"] = revised["data_offset"] + offset

    def body(obj):
        pid = obj["path_id"]
        if pid in replacements:
            return io.BytesIO(replacements[pid])
        stream.seek(layout["data_offset"] + objects[pid]["offset"])
        return stream

    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        serialized = Path(tmp) / "serialized"
        with serialized.open("xb") as handle:
            W.write_serialized(handle, revised, body)
        members = [
            (name, flags, revised["bytes"] if name == member else size, lambda name=name: serialized.open("rb") if name == member else bundle.member(name))
            for name, (_, size, flags) in bundle.members.items()
        ]
        packed = Path(tmp) / "bundle"
        with packed.open("xb") as handle:
            W.write_bundle(handle, members, compressor, engine=layout["engine"], version=bundle.identity[0], flags=bundle.identity[3])
        result = W.B.Bundle(packed)
        if [(name, flags, size) for name, (_, size, flags) in result.members.items()] != [row[:3] for row in members]:
            raise ValueError("persisted member directory differs")
        with result.member(member) as actual:
            if W.read_serialized(actual) != revised:
                raise ValueError("persisted serialized metadata differs")
            for obj in physical:
                actual.seek(revised["data_offset"] + obj["offset"])
                if W.B.exact(actual, obj["bytes"]) != W.B.exact(body(obj), obj["bytes"]):
                    raise ValueError("persisted staged body differs")
        for name in bundle.members:
            if name != member:
                with bundle.member(name) as before, result.member(name) as after:
                    while block := before.read(1024 * 1024):
                        if after.read(len(block)) != block:
                            raise ValueError("persisted resource member differs")
        # Link only the fully checked output, refusing an existing destination.
        destination.hardlink_to(packed)


def produce(args):
    profile = json.loads(args.recipe.read_bytes())
    member = profile["bundle"]["member"]
    bundle = W.B.Bundle(args.bundle)
    catalog = C.ProducedMembers()
    sdk = O.M.safe_input(args.sdk.resolve(), profile["sdk"]["path"])
    if W.B.sha(sdk) != profile["sdk"]["sha256"] or W.B.sha(args.bundle) != args.bundle_sha256:
        raise ValueError("staged source bundle or SDK drift")
    sdk_tree = O.source_record_type(sdk, sdk.name, profile["sdk"]["path_id"], 114)["tree"]
    with ExitStack() as stack:
        catalog.add(member, stack.enter_context(bundle.member(member)), profile["bundle"]["name"])
        registry = stack.enter_context(args.registry.open("rb"))
        registry.size = args.registry.stat().st_size
        catalog.add("registry", registry, "@player")
        _, layout, rows = catalog.members["registry"]
        scripts = []
        for pid, row in rows.items():
            if layout["types"][row["type_id"]]["class_id"] == 115:
                raw = catalog.record("registry", (0, pid))[2]
                if C.script_identity(raw) == tuple(reversed(BOUNDARY)):
                    scripts.append(raw)
        (script,) = scripts
        sources = {}

        def original(index, pid):
            if index not in sources:
                pin = profile["sources"][index]
                path = O.M.safe_input(args.game.resolve(), pin["path"])
                if W.B.sha(path) != pin["sha256"]:
                    raise ValueError("original source bundle drift")
                stream = stack.enter_context(O.source_member(path, pin["member"]))
                metadata = W.read_serialized(stream)
                sources[index] = (path, None, stream, metadata, {obj["path_id"]: obj for obj in metadata["objects"]})
            raw, typ = O.source_record(sources, (index, pid))
            return typ, raw

        replacements, updates = patch_records(catalog, member, profile, original, script, sdk_tree)
        with W.codec(args.codec, args.codec_sha256) as compressor:
            rewrite(bundle, member, catalog, replacements, updates, args.output, compressor)
    return dict(
        bundle=profile["bundle"]["name"],
        source_sha256=args.bundle_sha256,
        sha256=W.B.sha(args.output),
        bytes=args.output.stat().st_size,
        components=len(replacements) - 1,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("recipe", "game", "sdk", "bundle", "registry", "codec", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--codec-sha256", required=True)
    print(json.dumps(produce(parser.parse_args())))
