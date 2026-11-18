"""Host-only structural comparison of staged catalog bundles against a pinned lab build."""

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import struct
from zipfile import ZipFile

import catalog_complete as C
import unity_mesh as M


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

    visit(root, ())
    return root, fields


def pointers(body, root):
    """Skip fixed non-reference spans and retain array indices on each PPtr."""
    cursor = 0
    found = {}

    def read(node, field):
        nonlocal cursor
        end = None if node.has_pointer else M.fixed_end(node, cursor)
        if end is not None:
            cursor = end
        elif node.pointer:
            found[field] = struct.unpack_from("<iq", body, cursor)
            cursor += 12
        elif node.flags & 1:
            count = struct.unpack_from("<I", body, cursor)[0]
            cursor += 4
            if len(node.children) != 2 or count > len(body):
                raise ValueError("invalid serialized array")
            element = node.children[1]
            end = None if element.has_pointer else M.fixed_end(element, cursor)
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
            for name in ("globalgamemanagers.assets", "Resources/unity_builtin_extra", "unity default resources"):
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


def compare(inputs, assembly, candidate_apk, candidate_sha, output, emission, only=None):
    request = json.loads(inputs.read_bytes())
    ref = json.loads(assembly.read_bytes())["authored_class_reference"]
    reference_apk = pinned(ref["path"], ref["sha256"])
    candidate_apk = pinned(candidate_apk, candidate_sha)
    baseline = json.loads((reference_apk.parent / "result.json").read_bytes())
    if baseline["apk_sha256"] != ref["sha256"]:
        raise ValueError("reference build result belongs to another APK")
    paths = candidate_paths(request, candidate_apk)
    references = {name: pinned(Path(baseline["payload_directory"]) / name, baseline["payload"][name]) for name in paths}
    candidate = Catalog(paths, candidate_apk)
    reference = Catalog(references, reference_apk)
    sides = {"candidate": candidate, "reference": reference}
    sources, aliases = provenance(emission, candidate, reference)
    output.mkdir(exist_ok=False)
    counts = Counter()
    examined = Counter()
    with (output / "mismatches.jsonl").open("w") as table:

        def emit(cause, **details):
            counts[cause] += 1
            table.write(json.dumps(dict(cause=cause, bundle=bundle, member=member, path_id=pid, **details), separators=(",", ":")) + "\n")

        def edges(side, catalog, body, typ):
            root, _ = schema(typ["tree"])
            result = {}
            for field, ptr in pointers(body, root).items():
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

        for bundle in [only] if only else sorted(paths):
            members = set(candidate.bundles[bundle]) | set(reference.bundles[bundle])
            for member in sorted(members):
                records = {s: c.members[member][2] if member in c.bundles[bundle] else {} for s, c in sides.items()}
                for pid in sorted(records["candidate"].keys() | records["reference"].keys()):
                    types, bodies, links, bindings = {}, {}, {}, {}
                    for side, catalog in sides.items():
                        if pid not in records[side]:
                            continue
                        examined[side] += 1
                        _, typ, body = catalog.record(member, (0, pid))
                        types[side], bodies[side] = typ, body
                        try:
                            if typ["class_id"] != 142:
                                links[side] = edges(side, catalog, body, typ)
                            if typ["class_id"] == 114:
                                bindings[side] = catalog.binding(member, typ, body)
                                if bindings[side] is None:
                                    emit("scriptless", side=side)
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
                        if len(links) == 2:
                            for field in sorted(links["candidate"].keys() | links["reference"].keys(), key=repr):
                                a = links["candidate"].get(field, "absent")
                                b = links["reference"].get(field, "absent")
                                if a != b:
                                    cause = "component-slot" if cid == 1 and field[0] == "m_Component" else "pointer-target"
                                    if isinstance(b, tuple) and aliases.get(b, "unknown") == a:
                                        cause = "canonical-pointer-redirection"
                                    emit(cause, field=field, candidate=a, reference=b)
            table.flush()
            print(bundle, dict(examined), flush=True)
    summary = dict(
        examined=examined,
        mismatches=counts,
        candidate_sha256=candidate_sha,
        reference_sha256=ref["sha256"],
        bundles=[only] if only else sorted(paths),
        reference_payload_outside_stage=sorted(baseline["payload"].keys() - paths.keys()),
    )
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--inputs", required=True, type=Path)
    cli.add_argument("--emission", required=True, type=Path)
    cli.add_argument("--assembly", required=True, type=Path)
    cli.add_argument("--candidate-apk", required=True, type=Path)
    cli.add_argument("--candidate-sha256", required=True)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--bundle", help="inspect only one bundle for a smoke run")
    args = cli.parse_args()
    compare(args.inputs, args.assembly, args.candidate_apk, args.candidate_sha256, args.output, args.emission, args.bundle)
