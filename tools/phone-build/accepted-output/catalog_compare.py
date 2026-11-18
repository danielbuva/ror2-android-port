"""Host-only structural comparison of staged catalog bundles against a pinned lab build."""

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
from zipfile import ZipFile

import catalog_complete as C
import unity_mesh as M

CHARACTER_MASTER = ("CharacterMaster", "RoR2", "RoR2.dll")
ITEM_DISPLAY_RULE_SET = ("ItemDisplayRuleSet", "RoR2", "RoR2.dll")
DISPLAY_STRING_FIELDS = {"childName", "m_AssetGUID", "m_SubObjectName"}
DISPLAY_FIXED_FIELDS = {"ruleType", "limbMask", "localPos", "localAngles", "localScale"}
DISPLAY_POINTER_FIELDS = {"itemDisplayRuleSet", "keyAsset", "followerPrefab"}


def pinned(path, digest):
    path = Path(path)
    if C.W.B.sha(path) != digest:
        raise ValueError("comparison input hash differs: " + str(path))
    return path


@lru_cache(maxsize=None)
def schema(tree):
    root = M.type_tree(io.BytesIO(tree))
    fields = set()

    def visit(node, path):
        names = [child.name for child in node.children]
        node.pointer = names == ["m_FileID", "m_PathID"] and node.size == 12
        for child in node.children:
            visit(child, path + (child.name,))
        fields.add((path, node.kind))
        node.has_pointer = node.pointer or any(child.has_pointer for child in node.children)
        node.display_string = node.kind == "string" and node.name in DISPLAY_STRING_FIELDS
        node.display_fixed = node.name in DISPLAY_FIXED_FIELDS
        node.has_display_field = node.display_string or node.display_fixed or any(child.has_display_field for child in node.children)

    visit(root, ())
    return root, fields


def pointers(body, root, display_fields=None):
    """Retain indexed PPtrs and, when requested, serialized display rule values."""
    cursor = 0
    found = {}

    def read(node, field):
        nonlocal cursor
        end = None if node.has_pointer or (display_fields is not None and node.has_display_field) else M.fixed_end(node, cursor)
        if end is not None:
            cursor = end
        elif node.pointer:
            found[field] = struct.unpack_from("<iq", body, cursor)
            cursor += 12
        elif display_fields is not None and node.display_string:
            size = struct.unpack_from("<I", body, cursor)[0]
            cursor += 4
            display_fields[field] = body[cursor : cursor + size].decode("utf-8")
            cursor += size
            if node.children[0].meta & 0x4000:
                cursor = (cursor + 3) & ~3
        elif display_fields is not None and node.display_fixed:
            end = M.fixed_end(node, cursor)
            if end is None:
                raise ValueError("unknown display value extent")
            display_fields[field] = body[cursor:end].hex()
            cursor = end
        elif node.flags & 1:
            count = struct.unpack_from("<I", body, cursor)[0]
            cursor += 4
            if len(node.children) != 2 or count > len(body):
                raise ValueError("invalid serialized array")
            element = node.children[1]
            end = None if element.has_pointer or (display_fields is not None and element.has_display_field) else M.fixed_end(element, cursor)
            if end is not None and count:
                cursor = end + (count - 1) * (M.fixed_end(element, end) - end)
            else:
                for index in range(count):
                    read(element, field + (index,))
        elif node.children:
            for child in node.children:
                read(child, field + (child.name,))
        else:
            raise ValueError("unknown field extent")
        if node.meta & 0x4000:
            cursor = (cursor + 3) & ~3
        if cursor > len(body):
            raise ValueError("field exceeds object body")

    read(root, ())
    if cursor != len(body):
        raise ValueError("incomplete serialized object")
    return found


class Catalog(C.ProducedMembers):
    def __init__(self, paths, apk):
        super().__init__()
        self.names = {}
        for name, path in paths.items():
            bundle = C.W.B.Bundle(path)
            for member in bundle.members:
                if not member.endswith((".resS", ".resource")):
                    self.add(member, bundle.member(member), name)
                    self.names[member] = name
        with ZipFile(apk) as archive:
            self.player_types = C.il2cpp_type_identities(archive.read("assets/bin/Data/Managed/Metadata/global-metadata.dat"))
            for name in ("globalgamemanagers.assets", "Resources/unity_builtin_extra", "unity default resources", "level0"):
                raw = archive.read("assets/bin/Data/" + name)
                stream = io.BytesIO(raw)
                stream.size = len(raw)
                self.add(name.split("/")[-1], stream, "@player")

    def endpoint(self, member, pointer):
        fid, pid = pointer
        if not fid and not pid:
            return None
        externals = self.members[member][1]["externals"]
        if not 0 <= fid <= len(externals):
            return ("invalid-file-id", member, fid, pid)
        owner = externals[fid - 1]["path"].rsplit("/", 1)[-1] if fid else member
        if owner not in self.members or pid not in self.members[owner][2]:
            return ("missing-target", owner, pid)
        return (owner, pid)

    @lru_cache(maxsize=16384)
    def script(self, member, script_id, ptr):
        _, script_type, raw = self.record(member, ptr)
        identity = C.script_identity(raw)
        if script_type["class_id"] != 115 or C.S.md4("".join(identity).encode()) != script_id:
            raise ValueError("script identity differs from serialized type")
        if identity not in self.player_types:
            raise ValueError("script type absent from player")
        return identity

    def binding(self, member, typ, body):
        pointer = struct.unpack_from("<iq", body, 16)
        if pointer == (0, 0):
            return None
        scripts = self.members[member][1]["scripts"]
        index = typ["script_type"]
        if not 0 <= index < len(scripts) or scripts[index] != pointer:
            raise ValueError("script table disagrees with object")
        return self.script(member, typ["script_id"], pointer)


def container_table(body):
    """Retain the preload extent in packed form, including duplicate container rows."""
    stream = io.BytesIO(body)
    C.text(stream)
    count = C.W.B.unpack(stream, "<I")[0]
    offset = stream.tell()
    stream.seek(offset + count * 12)
    rows = {}
    for _ in range(C.W.B.unpack(stream, "<I")[0]):
        name = C.text(stream)
        start, size, fid, pid = C.W.B.unpack(stream, "<iiiq")
        if min(start, size) < 0 or start + size > count:
            raise ValueError("invalid container preload extent")
        rows.setdefault((name, fid, pid), []).append((start, size))
    main = C.W.B.unpack(stream, "<iiiq")
    C.W.B.exact(stream, 4)
    C.text(stream)
    dependencies = [C.text(stream) for _ in range(C.W.B.unpack(stream, "<I")[0])]
    return memoryview(body)[offset : offset + count * 12], rows, main, dependencies


def containers(catalog, member, body):
    packed, rows, main, dependencies = container_table(body)
    groups = {}
    for (name, fid, pid), extents in rows.items():
        endpoint = catalog.endpoint(member, (fid, pid))
        groups[name, endpoint] = groups.get((name, endpoint), []) + extents
    return packed, groups, main, dependencies


def provenance(emission, candidate, reference):
    """Candidate witnesses annotate reused keys. They never establish baseline identity."""

    def document(pin):
        return json.loads(pinned(pin["path"], pin["sha256"]).read_bytes())

    req = json.loads(emission.read_bytes())
    conflicts = set()
    for member, bundle in candidate.names.items():
        if member not in reference.bundles.get(bundle, []):
            continue
        _, a, objects = candidate.members[member]
        _, b, prior = reference.members[member]
        for pid in objects.keys() & prior.keys():
            if a["types"][objects[pid]["type_id"]]["class_id"] != b["types"][prior[pid]["type_id"]]["class_id"]:
                conflicts.add((bundle, member, pid))
    sources = {}
    pins = [req["graph"]["selected-records.jsonl"], req["endpoints"]]
    if "extension" in req:
        pins.append(document(req["extension"])["candidates"])
    for pin in pins:
        with pinned(pin["path"], pin["sha256"]).open() as stream:
            for line in stream:
                row = json.loads(line)
                key = tuple(row["destination"])
                if key in conflicts and row.get("source"):
                    sources[key] = row["source"]
    aliases = {}
    for row in document(req["canonical"]["aliases"]):
        old, new = row["duplicate"], row["canonical"]
        aliases[tuple(old[1:])] = tuple(new[1:])
    return sources, aliases


def candidate_paths(request, candidate_apk):
    paths = {}
    with ZipFile(candidate_apk) as archive:
        for name, row in request["bundles"].items():
            paths[name] = pinned(row["path"], row["sha256"])
            with archive.open("assets/owner-bootstrap/data/" + name) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                    raise ValueError("candidate APK differs from catalog input: " + name)
    return paths


def typed_catalog_identity(receipt, request, candidate_apk):
    document = json.loads(receipt.read_bytes())
    evidence = document["masterBodyIdentity"]
    with ZipFile(candidate_apk) as archive, archive.open("assets/owner-bootstrap/data/whole-catalog.json") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != evidence["metadataSha256"]:
            raise ValueError("typed master identity metadata differs from candidate APK")
    if not evidence["bundles"] or any(request["bundles"].get(name, {}).get("sha256") != digest for name, digest in evidence["bundles"].items()):
        raise ValueError("typed master identity bundle pins differ from candidate APK")
    definitions = document.get("definitionIdentity")
    if definitions is not None and definitions["sourceMetadataSha256"] != request.get("source_additions", {}).get("metadata", {}).get("sha256"):
        raise ValueError("typed definition source metadata differs from catalog request")
    return evidence, definitions, document.get("displayIdentity")


def source_game_objects(game, bundle, pin, expected_paths):
    """Read typed local container roots from one accepted original bundle."""
    path = pinned(game / pin["path"], pin["sha256"])
    roots = {}
    source = C.W.B.Bundle(path)
    for member in source.members:
        if member.endswith((".resS", ".resource")):
            continue
        with source.member(member) as stream:
            layout = C.W.read_serialized(stream)
            objects = {row["path_id"]: row for row in layout["objects"]}
            for row in objects.values():
                if layout["types"][row["type_id"]]["class_id"] != 142:
                    continue
                stream.seek(layout["data_offset"] + row["offset"])
                _, entries, _, _ = container_table(C.W.B.exact(stream, row["bytes"]))
                for name, file_id, path_id in entries:
                    key = name.casefold()
                    if key not in expected_paths:
                        continue
                    target = objects.get(path_id)
                    if file_id or target is None or layout["types"][target["type_id"]]["class_id"] != 1:
                        raise ValueError(f"original display root is not a local GameObject: {bundle}:{name}")
                    roots.setdefault(key, set()).add((pin["path"], member, path_id))
    return roots


def missing_display_addresses(displays):
    addresses = {
        row["address"]
        for row in displays["failures"]
        if row.get("check") == "follower" or ("check" not in row and row.get("rule") is not None and not row["follower"])
    }
    if any(not isinstance(address, str) or not address for address in addresses):
        raise ValueError("unresolved display follower has no address")
    return addresses


def source_display_roots(inputs, fixture, candidate_apk, inventory, game):
    """Select missing follower locations and their source GameObject records."""
    sys.path.insert(0, str(C.ROOT / "scripts/lab"))
    from catalog_reader import read_shipped

    request = json.loads(inputs.read_bytes())
    _, definitions, displays = typed_catalog_identity(fixture, request, candidate_apk)
    if not definitions or not definitions["complete"] or not displays or not displays["complete"]:
        raise ValueError("display discovery requires a complete typed body fixture")
    source_pin = request["source_additions"]["metadata"]
    metadata_path = inputs.parent / source_pin["path"]
    metadata = json.loads(pinned(metadata_path, source_pin["sha256"]).read_bytes())
    accepted = json.loads(inventory.read_bytes())
    if accepted["input_id"] != metadata["input_id"]:
        raise ValueError("display discovery inventory differs from source input")
    catalogs = [row for row in accepted["files"] if row["path"].endswith("/StreamingAssets/aa/catalog.json")]
    if len(catalogs) != 1 or catalogs[0]["sha256"] != metadata["source_catalog_sha256"]:
        raise ValueError("display discovery catalog differs from accepted input")
    source_catalog = pinned(game / catalogs[0]["path"], metadata["source_catalog_sha256"])
    source = read_shipped(source_catalog, "", {"labels": {}, "providers": {}})
    files = {}
    for row in accepted["files"]:
        if Path(row["path"]).suffix == ".bundle":
            files.setdefault(Path(row["path"]).name, []).append(row)

    addresses = missing_display_addresses(displays)
    locations = {row["id"]: row for row in metadata["locations"] if row["type"].split(",", 1)[0] == "UnityEngine.GameObject"}
    original = {row["id"]: row for row in source["locations"]}
    source_keys = {row["key"]: row["locations"] for row in metadata["keys"] if row.get("keyType", "System.String") == "System.String"}
    original_keys = {row["key"]: row["locations"] for row in source["keys"] if row["keyType"] == "System.String"}
    published = {row["id"] for row in json.loads(pinned(inputs.parent / request["metadata"]["path"], request["metadata"]["sha256"]).read_bytes())["locations"]}
    published.update(request["source_additions"]["locations"])
    groups = {}
    for address in sorted(addresses):
        targets = [identity for identity in source_keys.get(address, ()) if identity in locations]
        if len(targets) != 1 or targets[0] in published:
            raise ValueError(f"expected one unpublished source display location: {address}")
        (identity,) = targets
        row = original[identity]
        active = locations[identity]
        if identity not in original_keys.get(address, ()) or (row["type"], row["primaryKey"]) != (active["type"], active["primaryKey"]):
            raise ValueError(f"source display location identity differs: {identity}")
        path = row["internalId"].casefold()
        dependencies = source["dependencySets"][row["dependencySet"]]
        if not dependencies or not original[dependencies[0]]["bundle"]:
            raise ValueError(f"source display location has no owning bundle: {identity}")
        basename = original[dependencies[0]]["internalId"].replace("\\", "/").rsplit("/", 1)[-1]
        groups.setdefault(basename, []).append((path, identity, address))

    rows = []
    for bundle, group in sorted(groups.items()):
        pins = files.get(bundle, ())
        if len(pins) != 1:
            raise ValueError(f"expected one accepted display bundle: {bundle}")
        roots = source_game_objects(game, bundle, pins[0], {path for path, _, _ in group})
        for path, identity, address in group:
            targets = roots.get(path, ())
            if len(targets) != 1:
                raise ValueError(f"expected one original display GameObject: {bundle}:{path}")
            rows.append(dict(location=identity, guid=address, path=locations[identity]["path"], source=list(next(iter(targets)))))
    return sorted(rows, key=lambda row: row["location"])


def compare(inputs, assembly, candidate_apk, candidate_sha, output, emission, only=None, typed_fixture=None, pc=None):
    import catalog_physics as physics

    request = json.loads(inputs.read_bytes())
    ref = json.loads(assembly.read_bytes())["authored_class_reference"]
    reference_apk = pinned(ref["path"], ref["sha256"])
    candidate_apk = pinned(candidate_apk, candidate_sha)
    baseline = json.loads((reference_apk.parent / "result.json").read_bytes())
    if baseline["apk_sha256"] != ref["sha256"]:
        raise ValueError("reference build result belongs to another APK")
    paths = candidate_paths(request, candidate_apk)
    identity, definitions, displays = typed_catalog_identity(typed_fixture, request, candidate_apk) if typed_fixture else (None, None, None)
    references = {name: pinned(Path(baseline["payload_directory"]) / name, baseline["payload"][name]) for name in paths.keys() & baseline["payload"].keys()}
    candidate = Catalog(paths, candidate_apk)
    reference = Catalog(references, reference_apk)
    sides = {"candidate": candidate, "reference": reference}
    sources, aliases = provenance(emission, candidate, reference)
    output.mkdir(exist_ok=False)
    counts = Counter()
    examined = Counter()
    with (output / "mismatches.jsonl").open("w") as table:
        if identity is not None:
            failures = list(identity["failures"])
            if not identity["complete"] or not identity["bodies"] or not identity["masters"]:
                failures.append(dict(error="typed master identity inspection incomplete"))
            for failure in failures:
                counts["typed-master-body-identity"] += 1
                table.write(json.dumps(dict(cause="typed-master-body-identity", side="candidate", **failure), separators=(",", ":")) + "\n")
        if definitions is not None:
            failures = list(definitions["failures"])
            if not definitions["complete"] or not definitions["families"] or not definitions["publication"]:
                failures.append(dict(error="typed definition inspection incomplete"))
            for failure in failures:
                counts["typed-definition-identity"] += 1
                table.write(json.dumps(dict(cause="typed-definition-identity", side="candidate", **failure), separators=(",", ":")) + "\n")
        if displays is not None:
            failures = list(displays["failures"])
            if not displays["complete"] or not displays["prefabs"] or len(displays["bodies"]) != identity["bodies"]:
                failures.append(dict(error="typed body display inspection incomplete"))
            for failure in failures:
                counts["typed-item-display-identity"] += 1
                table.write(json.dumps(dict(cause="typed-item-display-identity", side="candidate", **failure), separators=(",", ":")) + "\n")

        def emit(cause, **details):
            counts[cause] += 1
            table.write(json.dumps(dict(cause=cause, bundle=bundle, member=member, path_id=pid, **details), separators=(",", ":")) + "\n")

        def edges(side, catalog, body, typ, display_fields):
            root, _ = schema(typ["tree"])
            result = {}
            for field, ptr in pointers(body, root, display_fields).items():
                target = catalog.endpoint(member, ptr)
                if target and len(target) != 2:
                    emit("unresolved-pointer", side=side, field=field, pointer=ptr, target=target)
                result[field] = target
            return result

        def preloads():
            tables = {s: containers(c, member, bodies[s]) for s, c in sides.items() if s in types and types[s]["class_id"] == 142}
            groups = set().union(*(v[1] for v in tables.values()))
            for side, (packed, _, main, _) in tables.items():
                # Validate the entire table, including entries outside advertised ranges.
                unique = set(struct.iter_unpack("<iq", packed))
                unique.add(tuple(main[2:]))
                for ptr in unique:
                    target = sides[side].endpoint(member, ptr)
                    if target and len(target) != 2:
                        emit("unresolved-preload", side=side, pointer=ptr, target=target)
            if len(tables) != 2:
                return
            if set(tables["candidate"][3]) != set(tables["reference"][3]):
                emit("bundle-dependencies", candidate=tables["candidate"][3], reference=tables["reference"][3])
            for key in sorted(groups, key=repr):
                rows = {s: t[1].get(key, []) for s, t in tables.items()}
                if len(rows["candidate"]) != len(rows["reference"]):
                    emit("container-membership", container=key, candidate=len(rows["candidate"]), reference=len(rows["reference"]))
                for a, b in zip(rows["candidate"], rows["reference"]):
                    sets = []
                    for side, (start, size) in (("candidate", a), ("reference", b)):
                        block = tables[side][0][start * 12 : (start + size) * 12]
                        sets.append({sides[side].endpoint(member, ptr) for ptr in struct.iter_unpack("<iq", block)})
                    if sets[0] != sets[1]:
                        emit(
                            "preload-set", container=key, candidate_only=sorted(sets[0] - sets[1], key=repr), reference_only=sorted(sets[1] - sets[0], key=repr)
                        )

        bundles = [only] if only else sorted(paths)
        for bundle in bundles:
            members = set(candidate.bundles.get(bundle, ())) | set(reference.bundles.get(bundle, ()))
            for member in sorted(members):
                records = {s: c.members[member][2] if member in c.bundles.get(bundle, ()) else {} for s, c in sides.items()}
                for pid in sorted(records["candidate"].keys() | records["reference"].keys()):
                    types, bodies, links, bindings = {}, {}, {}, {}
                    display_fields = {}
                    for side, catalog in sides.items():
                        if pid not in records[side]:
                            continue
                        examined[side] += 1
                        _, typ, body = catalog.record(member, (0, pid))
                        types[side], bodies[side] = typ, body
                        try:
                            if typ["class_id"] == 114:
                                bindings[side] = catalog.binding(member, typ, body)
                                if bindings[side] is None:
                                    emit("scriptless", side=side)
                                if bindings[side] == ITEM_DISPLAY_RULE_SET:
                                    display_fields[side] = {}
                            if typ["class_id"] != 142:
                                links[side] = edges(side, catalog, body, typ, display_fields.get(side))
                        except (ValueError, KeyError, struct.error) as exc:
                            emit("object-inspection", side=side, error=str(exc))
                    if any(t["class_id"] == 142 for t in types.values()):
                        preloads()
                    if len(types) != 2:
                        emit("unmatched-object", side=next(iter(types)), class_id=next(iter(types.values()))["class_id"])
                    elif types["candidate"]["class_id"] != types["reference"]["class_id"]:
                        emit(
                            "shared-key-class-conflict",
                            candidate_source=sources.get((bundle, member, pid)),
                            classes={s: t["class_id"] for s, t in types.items()},
                        )
                    else:
                        cid = types["candidate"]["class_id"]
                        type_keys = {side: (typ["hash"].hex(), typ["stripped"]) for side, typ in types.items()}
                        if type_keys["candidate"] != type_keys["reference"]:
                            emit("type-metadata", metadata=type_keys)
                        if cid == 142:
                            continue
                        if types["candidate"].get("tree") != types["reference"].get("tree"):
                            fields = [schema(t["tree"])[1] for t in types.values() if "tree" in t]
                            if len(fields) == 2 and fields[0] != fields[1]:
                                emit("serialized-fields", candidate_only=sorted(fields[0] - fields[1]), reference_only=sorted(fields[1] - fields[0]))
                        if cid == 114 and bindings.get("candidate") != bindings.get("reference"):
                            emit("script-binding", identities=bindings)
                        if len(display_fields) == 2:
                            a, b = display_fields["candidate"], display_fields["reference"]
                            for field in sorted(a.keys() | b.keys(), key=repr):
                                if a.get(field) != b.get(field):
                                    emit("item-display-rule-field", field=field, candidate=a.get(field), reference=b.get(field))
                        if len(links) == 2:
                            for field in sorted(links["candidate"].keys() | links["reference"].keys(), key=repr):
                                a = links["candidate"].get(field, "absent")
                                b = links["reference"].get(field, "absent")
                                if a != b:
                                    cause = "component-slot" if cid == 1 and field[0] == "m_Component" else "pointer-target"
                                    if field == ("bodyPrefab",) and CHARACTER_MASTER in bindings.values():
                                        cause = "character-master-body-target"
                                    if (
                                        field
                                        and field[-1] in DISPLAY_POINTER_FIELDS
                                        and (field[-1] == "itemDisplayRuleSet" or ITEM_DISPLAY_RULE_SET in bindings.values())
                                    ):
                                        cause = "item-display-pointer-target"
                                    if isinstance(b, tuple) and aliases.get(b, "unknown") == a:
                                        cause = "canonical-pointer-redirection"
                                    emit(cause, field=field, candidate=a, reference=b)
            table.flush()
            print(bundle, dict(examined), flush=True)
        bundle, member, pid = "@player", "globalgamemanagers", None
        managers = physics.compare_managers(candidate_apk, reference_apk, pc, pinned, emit)

        def emit_physics(cause, **details):
            counts[cause] += 1
            table.write(json.dumps(dict(cause=cause, **details), separators=(",", ":")) + "\n")

        objects = physics.compare_objects(sides, [*bundles, "@player"], container_table, emit_physics)
    summary = dict(
        examined=examined,
        mismatches=counts,
        candidate_sha256=candidate_sha,
        reference_sha256=ref["sha256"],
        bundles=bundles,
        physics=dict(managers=managers, **objects),
        reference_payload_outside_stage=sorted(baseline["payload"].keys() - paths.keys()),
    )
    if identity is not None:
        summary["typed_master_body_identity"] = {key: identity[key] for key in ("complete", "bodies", "masters", "metadataSha256", "bundles")}
    if definitions is not None:
        summary["typed_definition_identity"] = {key: value for key, value in definitions.items() if key != "failures"}
    if displays is not None:
        summary["typed_item_display_identity"] = {key: value for key, value in displays.items() if key not in {"failures", "slots"}}
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--inputs", required=True, type=Path)
    cli.add_argument("--emission", type=Path)
    cli.add_argument("--assembly", type=Path)
    cli.add_argument("--candidate-apk", required=True, type=Path)
    cli.add_argument("--candidate-sha256", required=True)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--bundle", help="inspect only one bundle for a smoke run")
    cli.add_argument("--typed-fixture", type=Path, help="join the candidate's exact-editor catalog identity report")
    cli.add_argument("--pc", type=Path, help="original game installation")
    cli.add_argument("--discover-display-roots", action="store_true", help="discover missing display roots from the original catalog")
    cli.add_argument("--inventory", type=Path, help="accepted input inventory for display root discovery")
    args = cli.parse_args()
    if args.discover_display_roots:
        if not all((args.inventory, args.pc, args.typed_fixture)):
            cli.error("display root discovery requires --inventory, --pc and --typed-fixture")
        candidate = pinned(args.candidate_apk, args.candidate_sha256)
        rows = source_display_roots(args.inputs, args.typed_fixture, candidate, args.inventory, args.pc)
        with args.output.open("x") as handle:
            json.dump(rows, handle, indent=2)
            handle.write("\n")
    else:
        if not all((args.emission, args.assembly)):
            cli.error("bundle comparison requires --emission and --assembly")
        compare(args.inputs, args.assembly, args.candidate_apk, args.candidate_sha256, args.output, args.emission, args.bundle, args.typed_fixture, args.pc)
