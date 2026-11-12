"""Derive prefab container preload lists from produced typed object graphs.

Recipes declare asset GUID/root relationships and checked external component
ownership. Source-produced bodies supply dependencies; accepted preload arrays
and container bodies are never inputs.
"""

import io
import hashlib
import importlib.util
from pathlib import Path
import re
import struct


class EmissionCache:
    """Private transformed bytes; only a fully checked run publishes reuse evidence.

    Callback owners supply every file read by their endpoint/managed checkers in
    cache_inputs. Files are hashed again before publishing or reusing evidence.
    Record entries cache transformations, never endpoint or CLR qualification.
    """

    def __init__(self, directory):
        import sqlite3
        from collections import Counter

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(directory / "emission.sqlite3")
        self.connection.execute("CREATE TABLE IF NOT EXISTS entries (kind TEXT, key TEXT, body BLOB, sha TEXT, PRIMARY KEY(kind,key))")
        self.counts = Counter()

    @staticmethod
    def key(value):
        import json

        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def get(self, kind, key):
        row = self.connection.execute("SELECT body,sha FROM entries WHERE kind=? AND key=?", (kind, key)).fetchone()
        if row is not None and hashlib.sha256(row[0]).hexdigest() == row[1]:
            self.counts[kind + "_hits"] += 1
            return row[0]
        self.counts[kind + "_misses"] += 1
        return None

    def put(self, kind, key, body):
        self.connection.execute("INSERT OR REPLACE INTO entries VALUES (?,?,?,?)", (kind, key, body, hashlib.sha256(body).hexdigest()))

    def close(self):
        self.connection.commit()
        self.connection.close()


def materialize_cached_bundle(result, output, artifacts):
    """Give each dispatcher attempt regular, independently retained artifacts."""
    import json
    import shutil
    import subprocess
    import sys

    output.mkdir(parents=True, exist_ok=False)
    for source, digest in artifacts.items():
        source = Path(source)
        if source.name == "result.json":
            continue
        target = output / source.name
        if sys.platform == "darwin":
            subprocess.run(["cp", "-c", str(source), str(target)], check=True)
        else:
            shutil.copyfile(source, target)
        if O.B.sha(target) != digest:
            raise ValueError("Materialized cache artifact differs")
    result["bundle"] = str((output / Path(result["bundle"]).name).resolve())
    request = output / "request.json"
    if request.is_file():
        value = json.loads(request.read_bytes())
        value["path"] = result["bundle"]
        request.write_text(json.dumps(value, indent=2) + "\n")
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def emission_input_pins(selected, graph_directory, schema_paths, codec, cache_inputs, provider_paths=None):
    """Hash complete provider lineages and explicit callback/code dependencies."""
    import json

    paths = {Path(path).resolve() for path in cache_inputs}
    paths.update(Path(path).resolve() for path in schema_paths)
    paths.update(Path(__file__).parent.glob("*.py"))
    paths.update(graph_directory / name for name in ("done.json", "selected-records.jsonl"))
    if (graph_directory / "selected-roots.jsonl").is_file():
        paths.add(graph_directory / "selected-roots.jsonl")
    if codec is not None:
        paths.add(Path(codec).resolve())
    providers = ProducerRecords(provider_paths)
    pending = {providers.directory(row["provider"]) for row in selected.values()}
    seen = set()
    while pending:
        directory = pending.pop()
        if directory in seen:
            continue
        seen.add(directory)
        receipt = directory / "result.json"
        if not receipt.is_file():
            receipt = directory.parent / "terminal.json"
        paths.update((receipt, directory / "index.jsonl", directory / "objects.bin"))
        for name in ("resources.bin", "witnesses.jsonl"):
            if (directory / name).is_file():
                paths.add(directory / name)
        if "profile_sha256" not in json.loads(receipt.read_text()):
            pending.update(providers.directory(row["provider_before"]) for row in json_rows(directory / "index.jsonl"))
    return {str(path): O.B.sha(path) for path in sorted(paths)}


def module(name):
    spec = importlib.util.spec_from_file_location("_preload_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


O, A = module("object_produce"), module("record_produce")


def pointers(body, typ, schemas):
    key = typ["tree"]
    if key not in schemas:
        schemas[key] = A.SCHEMA.type_tree(io.BytesIO(key))
    spans = A.fields(body, schemas[key])[1]
    return {
        path: struct.unpack_from("<iq", body, start)
        for path, (start, end) in spans.items()
        if end - start == 12 and path + ("m_FileID",) in spans and path + ("m_PathID",) in spans
    }


def full_type_key(typ):
    """Identity before make_layout assigns destination script-table indices."""
    import json

    return hashlib.sha256(json.dumps(O.json_layout(typ), sort_keys=True).encode()).hexdigest()


def qualified_final_type(body, typ, scripts, qualified):
    """Recover a qualified type identity from actual final-file metadata.

    make_layout allocates script indices in the destination file. Prove that
    allocation against the persisted object's schema-declared m_Script before
    restoring only the original index; every other type field must stay exact.
    The caller must obtain body, typ and scripts from the same final member.
    """
    restored = dict(typ)
    if typ["class_id"] == 114:
        fields = pointers(body, typ, {})
        script = fields.get(("m_Script",), fields.get(("#490",)))
        index = typ["script_type"]
        if script != (0, 0):
            if script is None or not 0 <= index < len(scripts) or tuple(scripts[index]) != script:
                raise ValueError("Final object and type script relationship differ")
            restored["script_type"] = qualified["script_type"]
    if full_type_key(restored) != full_type_key(qualified):
        raise ValueError("Final full type identity differs")
    return restored


def qualify_null_script_base(body, typ, source_type):
    """Check the original scriptless base without inventing a CLR binding.

    The caller reads source_type from a hash-pinned original, including an
    explicit missing_script_base.type_source when the producer used one.
    Returned pointers still require normal endpoint qualification.
    """
    if (
        full_type_key(typ) != full_type_key(source_type)
        or typ["class_id"] != 114
        or len(body) != 32
        or typ["script_type"] != -1
        or typ["hash"] != bytes(16)
        or typ["script_id"] != bytes(16)
    ):
        raise ValueError("Scriptless base differs from pinned original type")
    fields = pointers(body, typ, {})
    scripts = [pointer for field, pointer in fields.items() if field in (("m_Script",), ("#490",))]
    if scripts != [(0, 0)]:
        raise ValueError("Scriptless base requires one null script field")
    return fields


def qualify_external_fields(value, body, typ, proofs, endpoint_record):
    """Qualify each non-null external field against a persisted endpoint.

    endpoint_record(target) returns (selected_row, actual_body, qualified_type).
    Its caller owns receipt/index validation and final-file metadata readback;
    these bytes must come from the container being qualified. Type identity is
    the qualified type before destination script-table index allocation.
    This proves field routes, not current CLR compatibility or loadability.
    """
    import json

    owner = tuple(value["destination"])
    schema = hashlib.sha256(typ["tree"]).hexdigest()
    owner_sha = hashlib.sha256(body).hexdigest()
    if (
        (len(body), owner_sha) != (value["bytes"], value["sha256"])
        or schema != value["schema"]
        or full_type_key(typ) != value["full_type"]
        or typ["class_id"] != value["class_id"]
        or typ["hash"].hex() != value["native_type_hash"]
    ):
        raise ValueError("External field owner body or full type differs")
    fields = pointers(body, typ, {})
    if set(fields.values()) != set(map(tuple, value["edges"])):
        raise ValueError("External field owner measured pointers differ")
    candidates = {}
    for proof in proofs:
        key = (
            proof.get("effective_provider", proof["provider"]),
            tuple(proof["owner"]),
            proof["owner_sha256"],
            proof["schema_sha256"],
        )
        if key != (value["provider"], owner, owner_sha, schema) or proof.get("rewrite_required"):
            continue
        candidates.setdefault(tuple(proof["field"]), []).append(proof)
    targets = {}
    endpoint_cache = {}
    for field, pointer in fields.items():
        if not pointer[0] or not pointer[1]:
            continue
        valid = {}
        for proof in candidates.get(field, []):
            if tuple(proof["from"]) != pointer:
                continue
            target = tuple(proof["target"])
            if target not in endpoint_cache:
                endpoint_cache[target] = endpoint_record(target)
            endpoint, raw, endpoint_type = endpoint_cache[target]
            digest = hashlib.sha256(raw).hexdigest()
            full = full_type_key(endpoint_type)
            expected = proof["endpoint_type"]
            source_target = proof["source_target"]
            if source_target is None:
                # Generated SDK/registry bodies have no original object body.
                # Their caller-qualified producer evidence must survive into
                # the field proof, alongside the actual emitted extent below.
                provenance = endpoint.get("generated_provenance")
                if not provenance or expected.get("generated_provenance") != provenance or expected.get("source_sha256") is not None:
                    continue
            if (
                tuple(endpoint["destination"]) != target
                or endpoint.get("source") != proof["source_target"]
                or (len(raw), digest) != (endpoint["bytes"], endpoint["sha256"])
                or full != endpoint["full_type"]
                or hashlib.sha256(endpoint_type["tree"]).hexdigest() != endpoint["schema"]
                or endpoint_type["class_id"] != endpoint["class_id"]
                or endpoint_type["hash"].hex() != endpoint["native_type_hash"]
                or (endpoint_type["class_id"], endpoint_type["hash"].hex(), full) != (expected["class_id"], expected["native_type_hash"], expected["full_type"])
            ):
                continue
            # source_sha256 witnesses the ORIGINAL body, not the produced body.
            # The produced extent is bound by emitted_witnesses instead.
            if not any(
                (w[0], tuple(w[1]), w[2], w[3], w[4]) == (endpoint["provider"], tuple(endpoint["record_source"]), digest, len(raw), full)
                for w in expected["emitted_witnesses"]
            ):
                continue
            pointers(raw, endpoint_type, {})
            signature = target, tuple(source_target) if source_target is not None else None, json.dumps(expected, sort_keys=True)
            valid[signature] = target
        if len(valid) != 1:
            raise ValueError(f"External field lacks a unique persisted endpoint: {owner} {field} ({len(valid)})")
        targets[field] = next(iter(valid.values()))
    return targets


def checked_fields(record, raw, native):
    """Check an actual endpoint's extent, full native type and measured fields."""
    if (
        (len(raw), hashlib.sha256(raw).hexdigest()) != (record["bytes"], record["sha256"])
        or full_type_key(native) != record["full_type"]
        or hashlib.sha256(native["tree"]).hexdigest() != record["schema"]
        or native["class_id"] != record["class_id"]
        or native["hash"].hex() != record["native_type_hash"]
    ):
        raise ValueError("Structural route body or full type differs")
    fields = pointers(raw, native, {})
    if set(fields.values()) != set(map(tuple, record["edges"])):
        raise ValueError("Structural route measured pointers differ")
    return fields


def qualify_structural_fields(value, body, typ, routes, endpoint_record):
    """Check complete current routes without historical field provenance.

    The caller binds routes and selected descriptors to its current census and
    reads actual complete endpoint bodies/types from pinned inputs. Source
    provenance is diagnostic; current CLR compatibility remains a separate
    required emission check. No absent body or inferred type is admitted.
    """

    owner = tuple(value["destination"])
    fields = checked_fields(value, body, typ)
    nonnull = {field: pointer for field, pointer in fields.items() if pointer[1]}
    targets = {}
    for route in routes:
        field, pointer, target = tuple(route["field"]), tuple(route["pointer"]), tuple(route["target"])
        if field in targets or nonnull.get(field) != pointer or len(target) != 3 or target[2] != pointer[1]:
            raise ValueError("Structural route field or pointer differs")
        if not pointer[0] and target != (*owner[:2], pointer[1]):
            raise ValueError("Structural local route changes its member")
        endpoint, raw, native = endpoint_record(target)
        if tuple(endpoint["destination"]) != target:
            raise ValueError("Structural route endpoint identity differs")
        checked_fields(endpoint, raw, native)
        targets[field] = target
    if set(targets) != set(nonnull):
        raise ValueError("Structural routes require every nonnull field")
    return {field: target for field, target in targets.items() if nonnull[field][0]}


def relocate_external_fields(value, body, typ, targets, externals):
    """Allocate qualified fields by destination member, never by an old slot."""
    fields = pointers(body, typ, {})
    required = {field for field, (fid, pid) in fields.items() if fid and pid}
    if set(targets) != required:
        raise ValueError("External relocation requires complete per-field coverage")
    return relocate_pointer_fields(value, body, typ, targets, externals)


def relocate_pointer_fields(value, body, typ, targets, externals):
    """Apply source-qualified, parent-specific routes to local or external fields.

    A shared old path ID does not identify a source object: callers supply each
    field's qualified endpoint. Other fields and all non-pointer data survive.
    """
    if len(set(externals)) != len(externals) or value["destination"][1] in externals:
        raise ValueError("Ambiguous external member allocation")
    members = {value["destination"][1]: tuple(value["destination"][:2])}
    for target in targets.values():
        identity = tuple(target[:2])
        if members.setdefault(target[1], identity) != identity:
            raise ValueError("Ambiguous external member allocation")
    fields = pointers(body, typ, {})
    if any(field not in fields or not fields[field][1] for field in targets):
        raise ValueError("Relocation requires an existing non-null pointer field")
    references = []
    for field, target in targets.items():
        if not target[2]:
            raise ValueError("External relocation target is null")
        if tuple(target[:2]) == tuple(value["destination"][:2]):
            pointer = (0, target[2])
        else:
            if target[1] == value["destination"][1] or target[1] not in externals:
                raise ValueError("External relocation member absent or ambiguous")
            pointer = (externals.index(target[1]) + 1, target[2])
        references.append(dict(field=list(field), **{"from": list(fields[field]), "to": list(pointer)}))
    result = O.remap_record(body, typ, references, externals)
    actual = pointers(result, typ, {})
    revised = {tuple(row["field"]): tuple(row["to"]) for row in references}
    if actual != {field: revised.get(field, pointer) for field, pointer in fields.items()}:
        raise ValueError("External relocation changed an unqualified field")
    return result


def external_owners(selected, sources, schemas):
    result = {}
    for row in selected.get("external_component_owners", []):
        source, identity = row["source"]
        body, typ = O.source_record(sources, row["source"])
        owner_body, owner_typ = O.source_record(sources, [source, row["owner_source"]])
        if hashlib.sha256(body).hexdigest() != row["body_sha256"] or hashlib.sha256(owner_body).hexdigest() != row["owner_body_sha256"]:
            raise ValueError("Original external component ownership body drift")
        fields = pointers(body, typ, schemas)
        # Unity common-string offset 374 is m_GameObject in compact type trees.
        if fields.get(("m_GameObject",), fields.get(("#374",))) != (0, row["owner_source"]):
            raise ValueError("Original external component GameObject owner differs")
        if owner_typ["class_id"] != 1 or (0, identity) not in pointers(owner_body, owner_typ, schemas).values():
            raise ValueError("Original external GameObject component membership differs")
        pointer, owner = tuple(row["to"]), tuple(row["owner"])
        if pointer[0] != owner[0] or not 1 <= pointer[0] <= len(selected["externals"]) or not pointer[1] or not owner[1] or pointer in result:
            raise ValueError("External component destination ownership differs")
        result[pointer] = owner
    return result


def file_ranks(selected):
    native = {"Resources/unity_builtin_extra": 0x0F, "Library/unity default resources": 0x0E}
    names = [selected["member"], *selected["externals"]]
    keys = [(0, -native[name], "") if name in native else (1, 0, name.rsplit("/", 1)[-1]) for name in names]
    if len(set(keys)) != len(keys):
        raise ValueError("Ambiguous prefab preload serialized-file identity")
    return {file_id: rank for rank, file_id in enumerate(sorted(range(len(names)), key=keys.__getitem__))}


def guid_key(guid):
    if not isinstance(guid, str) or re.fullmatch(r"[a-f0-9]{32}", guid) is None:
        raise ValueError("Prefab asset GUID must name an original or authored importer")
    return tuple(int(guid[i : i + 8][::-1], 16) for i in range(0, 32, 8))


def closure(graph, roots, owners):
    seen, references, pending = set(), set(), list(roots)
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        if identity not in graph:
            raise ValueError("Prefab dependency references an absent produced local object")
        seen.add(identity)
        references.add((0, identity))
        for pointer in graph[identity]:
            file_id, path_id = pointer
            if not path_id:
                continue
            if file_id:
                references.add(pointer)
                if pointer in owners:
                    references.add(owners[pointer])
            elif path_id not in seen:
                pending.append(path_id)
    return references


def validate_graph(graph, external_count):
    """Validate every produced object, including objects outside asset roots."""
    for identity, pointers in graph.items():
        for file_id, path_id in pointers:
            if not 0 <= file_id <= external_count:
                raise ValueError(f"Produced object {identity} references an absent serialized file")
            if path_id and not file_id and path_id not in graph:
                raise ValueError(f"Produced object {identity} references an absent produced local object {path_id}")


def produce(selected, records, sources):
    schemas = {}
    graph = {}
    for row in records:
        if row["path_id"] in graph:
            raise ValueError("Duplicate produced prefab graph identity")
        graph[row["path_id"]] = set(pointers(row["body"], row["type"], schemas).values())
    return produce_graph(selected, graph, sources)


def preload_seeds(selected, group, endpoint_record):
    """Keep explicit destination seeds separate from advertised subassets.

    External seeds have no parent field to qualify their endpoint. Read and
    check their actual staged body/type even when a complete output is cached.
    """
    local, external, seen = [], [], set()
    for value in group.get("preload_roots", []):
        target = tuple(value)
        if len(target) != 3 or not isinstance(target[2], int) or not target[2] or target in seen:
            raise ValueError("Preload roots require distinct nonnull destination triples")
        seen.add(target)
        if target[:2] == (selected["name"], selected["member"]):
            local.append(target[2])
        else:
            if target[1] == selected["member"] or target[1] not in selected["externals"]:
                raise ValueError("Preload root serialized member absent or ambiguous")
            if endpoint_record is None:
                raise ValueError("External preload root requires an actual endpoint reader")
            record, raw, native = endpoint_record(target)
            if tuple(record["destination"]) != target:
                raise ValueError("Preload root endpoint identity differs")
            checked_fields(record, raw, native)
            external.append((selected["externals"].index(target[1]) + 1, target[2]))
    return local, external


def check_preload_seeds(required, endpoint_record):
    for group in required["asset_groups"]:
        local, _ = preload_seeds(required, group, endpoint_record)
        if any(identity not in required["path_ids"] for identity in [*group["roots"], *local]):
            raise ValueError("Required asset group root or preload root absent")


def produce_graph(selected, graph, sources, *, emission_cache=None, endpoint_record=None):
    """Frame grouped preloads from the emitter's fully parsed body graph."""
    validate_graph(graph, len(selected["externals"]))
    owners = external_owners(selected, sources, {})
    ranks = file_ranks(selected)
    groups = sorted(selected["asset_groups"], key=lambda row: guid_key(row["guid"]))
    if not groups or len({row["guid"] for row in groups}) != len(groups) or len({row["path"].lower() for row in groups}) != len(groups):
        raise ValueError("Prefab asset grouping requires unique source paths and GUIDs")
    stream = io.BytesIO()
    O.aligned_string(stream, selected["name"])
    count_offset = stream.tell()
    stream.write(bytes(4))
    preload_count, containers = 0, []
    if emission_cache is not None:
        scope = EmissionCache.key(dict(code=O.B.sha(Path(__file__)), ranks=sorted(ranks.items())))
        node_keys = {
            identity: EmissionCache.key([sorted(edges), [(pointer, owners.get(pointer)) for pointer in sorted(edges) if pointer[0] and pointer[1]]])
            for identity, edges in graph.items()
        }
    for group in groups:
        roots = group["roots"]
        if not roots or len(set(roots)) != len(roots):
            raise ValueError("Prefab asset group requires distinct imported roots")
        local, external = preload_seeds(selected, group, endpoint_record)
        seeds = sorted(set(roots) | set(local))
        if any(identity not in graph for identity in seeds):
            raise ValueError("Required asset group root or preload root absent")
        external = set(external)
        external.update(owners[pointer] for pointer in list(external) if pointer in owners)
        packed = None
        if emission_cache is not None:
            group_scope = EmissionCache.key([scope, roots, seeds, sorted(external)])
            previous = emission_cache.get("group_members", group_scope)
            members = [row[0] for row in struct.iter_unpack("<q", previous)] if previous is not None else seeds
            key = EmissionCache.key([group_scope, [(identity, node_keys.get(identity)) for identity in members]])
            packed = emission_cache.get("groups", key)
        if packed is None:
            dependencies = closure(graph, seeds, owners) | external
            if any(file_id not in ranks for file_id, _ in dependencies):
                raise ValueError("Prefab preload references an absent serialized file")
            ordered = sorted(dependencies, key=lambda pointer: (ranks[pointer[0]], pointer[1]))
            packed = b"".join(struct.pack("<iq", *pointer) for pointer in ordered)
            if emission_cache is not None:
                # Old reachable members are an invalidation witness, not closure
                # input. Any changed edge/owner triggers a fresh traversal.
                members = sorted(path_id for file_id, path_id in dependencies if not file_id)
                key = EmissionCache.key([group_scope, [(identity, node_keys[identity]) for identity in members]])
                emission_cache.put("groups", key, packed)
                emission_cache.put("group_members", group_scope, b"".join(struct.pack("<q", identity) for identity in members))
        count = len(packed) // 12
        containers.extend((group["path"].lower(), preload_count, count, root) for root in roots)
        stream.write(packed)
        preload_count += count
    end = stream.tell()
    stream.seek(count_offset)
    stream.write(struct.pack("<I", preload_count))
    stream.seek(end)
    stream.write(struct.pack("<I", len(containers)))
    for path, start, count, root in sorted(containers, key=lambda row: row[0]):
        O.aligned_string(stream, path)
        stream.write(struct.pack("<iiiq", start, count, 0, root))
    stream.write(struct.pack("<iiiqI", 0, 0, 0, 0, 1))
    O.aligned_string(stream, selected["name"])
    stream.write(struct.pack("<I", len(selected["dependencies"])))
    for dependency in selected["dependencies"]:
        O.aligned_string(stream, dependency)
    stream.write(struct.pack("<B3xiii", False, 0, 7, 0))
    return stream.getvalue()


# Single-object native roots only. Ordered Sprite/subasset groups retain their
# existing metadata owner; this partial emitter must not guess those identities.
NATIVE_ROOT_TYPES = {
    850595691: "LightingSettings",
    43: "Mesh",
    90: "Avatar",
    74: "AnimationClip",
    21: "Material",
    48: "Shader",
    28: "Texture2D",
    89: "Cubemap",
    319: "AvatarMask",
    134: "PhysicMaterial",
    221: "AnimatorOverrideController",
}


def json_rows(path):
    import json

    with path.open() as stream:
        yield from map(json.loads, stream)


def repack_stream(body, typ, resource, offset, path, schemas):
    """Relocate only the schema-owned StreamingInfo, retaining every PPtr."""
    descriptor = resource.get("stream", resource.get("destination"))
    if not descriptor or descriptor["size"] != resource["bytes"]:
        raise ValueError("Native resource descriptor differs")
    tree = typ["tree"]
    if tree not in schemas:
        schemas[tree] = A.SCHEMA.type_tree(io.BytesIO(tree))
    spans = A.fields(body, schemas[tree])[1]
    start, end = spans[("m_StreamData",)]
    T = module("texture_produce")
    original = struct.pack("<QI", descriptor["offset"], descriptor["size"]) + T.text(descriptor["path"])
    if body[start:end] != original:
        raise ValueError("Native resource body descriptor drift")
    emitted = dict(offset=offset, size=resource["bytes"], path=path)
    result = body[:start] + struct.pack("<QI", offset, resource["bytes"]) + T.text(path) + body[end:]
    if pointers(result, typ, schemas) != pointers(body, typ, schemas):
        raise ValueError("Native resource relocation changed pointers")
    return result, emitted


class ProducerRecords:
    """Read original and retained relocation packs with per-record provenance.

    A relocation receipt pins its own extents, index and field witnesses. Each
    index row retains the preceding provider/body pin; follow those rows to the
    original profile instead of assigning one profile to a mixed pack. Schema,
    PPtr and final endpoint qualification still belong to the emitter.
    """

    def __init__(self, provider_paths=None):
        self.cache = {}
        self.pins = {}
        self.provider_paths = provider_paths or {}

    def directory(self, name):
        """Relocate file access while preserving the provider's proof identity."""
        return Path(self.provider_paths.get(str(name), name)).resolve()

    def provider(self, directory):
        import json

        directory = Path(directory).resolve()
        if directory not in self.cache:
            receipt_path = directory / "result.json"
            if not receipt_path.is_file():
                receipt_path = directory.parent / "terminal.json"
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("success") is not True:
                raise ValueError("Unsuccessful native provider")
            pin = dict(receipt_sha256=O.B.sha(receipt_path), index_sha256=O.B.sha(directory / "index.jsonl"))
            if "profile_sha256" in receipt:
                expected = receipt["outputs"]["index.jsonl"]["sha256"]
            else:
                expected = receipt["index_sha256"]
                pin.update(objects_sha256=O.B.sha(directory / "objects.bin"), witnesses_sha256=O.B.sha(directory / "witnesses.jsonl"))
                if pin["objects_sha256"] != receipt["objects_sha256"] or pin["witnesses_sha256"] != receipt["witnesses_sha256"]:
                    raise ValueError("Retained native provider extent or witness drift")
            if pin["index_sha256"] != expected:
                raise ValueError("Native provider index drift")
            index = {}
            for row in json_rows(directory / "index.jsonl"):
                identity = row["bundle"], row["member"], row["path_id"]
                copies = index.setdefault(identity, [])
                if copies and {k: v for k, v in row.items() if k != "offset"} != {k: v for k, v in copies[0].items() if k != "offset"}:
                    raise ValueError("Conflicting native provider identity")
                copies.append(row)
            self.pins[str(directory)] = pin
            self.cache[directory] = receipt, index
        return self.cache[directory]

    def record(self, value):
        directory = self.directory(value["provider"])
        key, expected = tuple(value["record_source"]), value["sha256"]
        seen, first = set(), None
        while True:
            if directory in seen:
                raise ValueError("Native provider lineage cycle")
            seen.add(directory)
            receipt, index = self.provider(directory)
            copies = index[key]
            row = copies[0]
            if row["sha256"] != expected:
                raise ValueError("Native provider lineage body differs")
            body = O.record_extent(directory / "objects.bin", row)
            for copy in copies[1:]:
                if O.record_extent(directory / "objects.bin", copy) != body:
                    raise ValueError("Duplicate native provider extent differs")
            if first is None:
                first = row, body
            if "profile_sha256" in receipt:
                if value["record"] != receipt["profile_sha256"]:
                    raise ValueError("Original native provider profile differs")
                return first
            expected = row["body_before_sha256"]
            directory = self.directory(row["provider_before"])


def retain_type_metadata(records, output, qualify):
    """Persist checked managed hash corrections without copying object bytes.

    records contains (selected, before_type, current_type). The caller obtains
    complete layouts from pinned sources and qualify(selected, body, type)
    must prove the current MonoScript/schema contract, returning its witness.
    Only the native hash may change; original producer profiles remain pinned
    through the existing retained-provider lineage. This does not admit a graph.
    """
    import json
    from collections import defaultdict

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    providers = ProducerRecords()
    groups = defaultdict(list)
    for value, before, current in records:
        groups[str(Path(value["provider"]).resolve())].append((value, before, current))
    revised = []
    for ordinal, (provider, values) in enumerate(sorted(groups.items())):
        directory = output / str(ordinal)
        directory.mkdir()
        (directory / "objects.bin").symlink_to(Path(provider) / "objects.bin")
        if (Path(provider) / "resources.bin").is_file():
            (directory / "resources.bin").symlink_to(Path(provider) / "resources.bin")
        index, witnesses = [], []
        for value, before, current in values:
            row, body = providers.record(value)
            if (
                before["class_id"] != 114
                or full_type_key({**current, "hash": before["hash"]}) != full_type_key(before)
                or before["hash"] == current["hash"]
                or value.get("native_type_hash") != before["hash"].hex()
                or row.get("native_type_hash", before["hash"].hex()) != before["hash"].hex()
                or value["schema"] != hashlib.sha256(current["tree"]).hexdigest()
                or (value["bytes"], value["sha256"]) != (len(body), hashlib.sha256(body).hexdigest())
            ):
                raise ValueError("Retained type correction changes more than native hash or differs from provider")
            evidence = qualify(value, body, current)
            if not evidence:
                raise ValueError("Retained type correction lacks current managed witness")
            full = full_type_key(current)
            index.append(
                {**row, "native_type_hash": current["hash"].hex(), "full_type": full, "provider_before": provider, "body_before_sha256": value["sha256"]}
            )
            witnesses.append(
                dict(
                    destination=value["destination"],
                    source=value.get("source"),
                    body_sha256=value["sha256"],
                    before_type=O.json_layout(before),
                    current_type=O.json_layout(current),
                    current_managed=evidence,
                )
            )
            revised.append({**value, "provider": str(directory.resolve()), "native_type_hash": current["hash"].hex(), "full_type": full})
        for name, rows in (("index.jsonl", index), ("witnesses.jsonl", witnesses)):
            (directory / name).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        receipt = dict(
            success=True,
            index_sha256=O.B.sha(directory / "index.jsonl"),
            objects_sha256=O.B.sha(directory / "objects.bin"),
            witnesses_sha256=O.B.sha(directory / "witnesses.jsonl"),
        )
        (directory / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return revised


def emit_closed_native(*args, cache_directory=None, cache_inputs=None, **kwargs):
    """Emit checked native content, optionally reusing pinned private outputs.

    cache_inputs must enumerate all files consumed by endpoint_record and
    managed_check, including their code, current CLR/SDK metadata and containers.
    A whole-output hit returns a reference to the prior bundle (no payload copy).
    """
    from contextlib import closing

    if cache_directory is None:
        return _emit_closed_native(*args, **kwargs)
    if cache_inputs is None:
        raise ValueError("Emission cache requires explicit callback input files")
    with closing(EmissionCache(cache_directory)) as cache:
        return _emit_closed_native(*args, emission_cache=cache, cache_inputs=cache_inputs, **kwargs)


def _emit_closed_native(
    graph_directory,
    schema_paths,
    output,
    name,
    member,
    *,
    codec=None,
    codec_sha256=None,
    required=None,
    field_proofs=(),
    structural_routes=None,
    endpoint_record=None,
    managed_check=None,
    emission_cache=None,
    cache_inputs=(),
    provider_paths=None,
):
    """Emit the declared local/native subset of a qualified producer graph.

    This is explicitly partial, even when all eligible records close. Bodies,
    native schemas and actual PPtrs are checked independently of graph claims.
    No historical bundle, accepted body or comparator is an input.

    required selects exact path_ids and GUID/asset_groups, with explicit
    externals/dependencies. This mode never drops an object or root. Its caller
    supplies the receipt/index/actual-final-container endpoint reader used by
    qualify_external_fields, and a current-CLR managed_check(value, body, type,
    read_record). The checker must reject incompatible schemas/scripts; it runs
    again against persisted output. Without these qualifications emission fails.
    Alternatively structural_routes maps each selected destination tuple to all
    current nonnull field/pointer/target edges, with original field provenance
    diagnostic. Complete actual endpoint checks and managed checks still apply.
    This Python integration boundary does not admit a whole catalog or player.
    """
    from collections import Counter, defaultdict
    from contextlib import nullcontext
    import json
    import tempfile
    import time
    import resource
    import sys

    M = module("bundle_manifest")
    W = M.W
    S = module("object_stream")
    if (codec is None) != (codec_sha256 is None):
        raise ValueError("Native bundle compression requires both codec and SHA-256")
    started = time.monotonic()
    stage_start = started
    stages = {}

    def stage(label):
        nonlocal stage_start
        now = time.monotonic()
        stages[label] = dict(
            seconds=now - stage_start, peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        )
        stage_start = now

    graph_directory, output = Path(graph_directory), Path(output)
    schema_paths, field_proofs = list(schema_paths), list(field_proofs)
    retained = json.loads((graph_directory / "done.json").read_text())
    if retained.get("success") is not True:
        raise ValueError("Unsuccessful source graph")
    all_records = {}
    for row in json_rows(graph_directory / "selected-records.jsonl"):
        key = tuple(row["destination"])
        if key in all_records:
            raise ValueError("Duplicate selected destination")
        all_records[key] = row
    selected = (
        {}
        if required is not None
        else {
            key: row
            for key, row in all_records.items()
            if key[:2] == (name, member)
            and (ProducerRecords(provider_paths).directory(row["provider"]) / "result.json").is_file()
            and row.get("schema")
            and row["class_id"] not in (114, 115, 142)
            and (not row.get("resource") or row["class_id"] in (28, 89, 43))
            and all(edge[0] == 0 for edge in row.get("edges", [[1, 1]]))
        }
    )
    if required is not None:
        identities = required["path_ids"]
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("Required object set must be nonempty and distinct")
        missing = sorted(identity for identity in identities if (name, member, identity) not in all_records)
        if missing:
            raise ValueError(f"Required produced objects absent: {missing}")
        selected = {(name, member, identity): all_records[name, member, identity] for identity in identities}
        if any(row["class_id"] == 142 for row in selected.values()):
            raise ValueError("Required object set must exclude the regenerated AssetBundle container")
        if any(row["class_id"] == 114 for row in selected.values()) and managed_check is None:
            raise ValueError("Required managed objects need current CLR qualification")
        check_preload_seeds(dict(required, name=name, member=member), endpoint_record)
    while required is None:
        missing = [key for key, row in selected.items() if any(pid and (*key[:2], pid) not in selected for _, pid in row["edges"])]
        if not missing:
            break
        for key in missing:
            del selected[key]
    if emission_cache is not None:
        input_pins = emission_input_pins(selected, graph_directory, schema_paths, codec, cache_inputs, provider_paths)
        # Routes are field-qualified and can include endpoints outside selected.
        request_key = EmissionCache.key(
            dict(
                inputs=input_pins,
                name=name,
                member=member,
                required=required,
                codec_sha256=codec_sha256,
                field_proofs=field_proofs,
                structural_routes=None if structural_routes is None else sorted((list(key), value) for key, value in structural_routes.items()),
            )
        )
        saved = emission_cache.get("outputs", request_key)
        if saved is not None:
            saved = json.loads(saved)
            if all(Path(path).is_file() and O.B.sha(Path(path)) == digest for path, digest in saved["outputs"].items()):
                if emission_input_pins(selected, graph_directory, schema_paths, codec, cache_inputs, provider_paths) != input_pins:
                    raise ValueError("Emission cache input drift")
                stage("reuse_validation")
                result = saved["result"]
                result.update(
                    seconds=time.monotonic() - started,
                    stages=stages,
                    cache=dict(emission_cache.counts),
                    cache_reused=True,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                )
                return materialize_cached_bundle(result, output, saved["outputs"])
    stage("input_identity")
    schemas, schema_pins = {}, {}
    needed = {row["full_type"] if required is not None else row["schema"] for row in selected.values()}
    for schema_path in map(Path, schema_paths):
        schema_pins[str(schema_path)] = O.B.sha(schema_path)
        for key, typ in json.loads(schema_path.read_text()).items():
            if key not in needed:
                continue
            if key in schemas and schemas[key] != typ:
                raise ValueError("Conflicting complete native schema")
            schemas[key] = typ
    typed = {}
    for key in needed:
        typ = dict(schemas[key])
        for field in ("tree", "hash", "script_id"):
            if field in typ:
                typ[field] = bytes.fromhex(typ[field])
        valid_identity = full_type_key(typ) == key if required is not None else hashlib.sha256(typ["tree"]).hexdigest() == key and typ["script_type"] == -1
        if not valid_identity:
            raise ValueError("Native schema identity differs")
        if required is None:
            typ.setdefault("dependencies", [])
        typed[key] = typ
    externals = [] if required is None else list(required["externals"])
    dependencies = [] if required is None else list(required["dependencies"])
    if len(set(externals)) != len(externals) or member in externals:
        raise ValueError("Ambiguous required external member table")
    proofs = {}
    for proof in field_proofs:
        proofs.setdefault(tuple(proof["owner"]), []).append(proof)
    endpoint_pins = {}
    from collections import OrderedDict

    external_bodies = OrderedDict()
    external_bytes = 0

    def read_external(target):
        nonlocal external_bytes
        target = tuple(target)
        if target in external_bodies:
            external_bodies.move_to_end(target)
            return external_bodies[target]
        if endpoint_record is None:
            raise ValueError("Required external endpoint reader absent")
        value, raw, typ = endpoint_record(target)
        pin = json.dumps(value, sort_keys=True), hashlib.sha256(raw).hexdigest(), full_type_key(typ)
        if endpoint_pins.setdefault(tuple(target), pin) != pin:
            raise ValueError("Persisted external endpoint drift")
        external_bodies[target] = value, raw, typ
        external_bytes += len(raw)
        while external_bytes > 32 * 1024 * 1024 and external_bodies:
            _, (_, prior, _) = external_bodies.popitem(last=False)
            external_bytes -= len(prior)
        return value, raw, typ

    by_provider = defaultdict(list)
    for row in selected.values():
        by_provider[row["provider"]].append(row)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=".emission-", dir=output) as scratch:
        store = Path(scratch) / "bodies.bin"
        objects, graph, bodymap, cache = [], {}, {}, {}
        providers = ProducerRecords(provider_paths)
        resource_extents, resource_rows, emitted_hashes = [], [], {}
        qualified_targets, managed_rows = {}, {}
        resource_size = 0
        resource_member = member + ".resS"
        resource_path = "archive:/" + member + "/" + resource_member
        transform_code = (
            EmissionCache.key({path: digest for path, digest in input_pins.items() if Path(path).parent == Path(__file__).parent})
            if emission_cache is not None
            else None
        )
        with store.open("wb") as destination:
            for provider, values in by_provider.items():
                directory = providers.directory(provider)
                for value in values:
                    identity = value["destination"][2]
                    row, body = providers.record(value)
                    typ = typed[value["full_type"] if required is not None else value["schema"]]
                    if row.get("resource") != value.get("resource") or (row["bytes"], row["sha256"]) != (value["bytes"], value["sha256"]):
                        raise ValueError("Native provider record or resource drift")
                    if (
                        typ["class_id"] != value["class_id"]
                        or (value.get("native_type_hash") and typ["hash"].hex() != value["native_type_hash"])
                        or (row.get("native_type_hash") and typ["hash"].hex() != row["native_type_hash"])
                        or hashlib.sha256(typ["tree"]).hexdigest() != value["schema"]
                    ):
                        raise ValueError("Native type identity differs")
                    edges = set(pointers(body, typ, cache).values())
                    if edges != set(map(tuple, value["edges"])):
                        raise ValueError("Measured native pointers differ from selected graph")
                    targets = {}
                    if required is not None:
                        if structural_routes is None:
                            targets = qualify_external_fields(value, body, typ, proofs.get(tuple(value["destination"]), ()), read_external)
                        else:
                            targets = qualify_structural_fields(value, body, typ, structural_routes[tuple(value["destination"])], read_external)
                        qualified_targets[identity] = targets
                        if typ["class_id"] == 114:
                            managed_rows[identity] = value, typ
                    offset = (resource_size + 15) // 16 * 16 if row.get("resource") else None
                    record_key = (
                        EmissionCache.key(
                            dict(
                                body=value["sha256"],
                                bytes=value["bytes"],
                                type=full_type_key(typ),
                                destination=value["destination"],
                                targets=sorted((list(field), target) for field, target in targets.items()),
                                externals=externals,
                                resource=row.get("resource"),
                                resource_offset=offset,
                                resource_path=resource_path,
                                code=transform_code,
                            )
                        )
                        if emission_cache is not None
                        else None
                    )
                    reused = emission_cache.get("records", record_key) if emission_cache is not None else None
                    if reused is None and required is not None:
                        body = relocate_external_fields(value, body, typ, targets, externals)
                    if row.get("resource"):
                        resource_size = offset
                        descriptor = dict(offset=offset, size=row["resource"]["bytes"], path=resource_path)
                        if reused is None:
                            body, descriptor = repack_stream(body, typ, row["resource"], resource_size, resource_path, cache)
                    if reused is not None:
                        body = reused
                    elif emission_cache is not None:
                        emission_cache.put("records", record_key, body)
                    edges = set(pointers(body, typ, cache).values())
                    if row.get("resource"):
                        resource_extents.append((resource_size, directory / "resources.bin", row["resource"]))
                        resource_rows.append(
                            dict(
                                path_id=identity,
                                source_body_sha256=row["sha256"],
                                source_resource=row["resource"],
                                emitted=descriptor,
                                emitted_body_sha256=hashlib.sha256(body).hexdigest(),
                            )
                        )
                        resource_size += row["resource"]["bytes"]
                    emitted_hashes[identity] = hashlib.sha256(body).hexdigest()
                    graph[identity] = edges
                    bodymap[identity] = destination.tell(), len(body)
                    destination.write(body)
                    objects.append(dict(path_id=identity, type=typ, body_bytes=len(body), prefix=body[:32]))
        stage("records")
        validate_graph(graph, len(externals))
        if required is not None and set(graph) != set(required["path_ids"]):
            raise ValueError("Emitted required object set differs")

        def read_produced(target):
            if tuple(target[:2]) != (name, member):
                return read_external(target)
            value = selected[tuple(target)]
            offset, size = bodymap[target[2]]
            with store.open("rb") as stream:
                stream.seek(offset)
                raw = O.B.exact(stream, size)
            return value, raw, typed[value["full_type"]]

        for identity, (value, typ) in managed_rows.items():
            managed_check(value, read_produced((name, member, identity))[1], typ, read_produced)
        stage("managed_qualification")
        grouped = defaultdict(list)
        for row in () if required is not None else json_rows(graph_directory / "selected-roots.jsonl"):
            key = tuple(row["destination"])
            if key in selected and row["class_id"] in NATIVE_ROOT_TYPES:
                if row["class_id"] != selected[key]["class_id"]:
                    raise ValueError("Native root type differs from produced object")
                grouped[row["path"].lower()].append(row)
        roots = [rows[0] for rows in grouped.values() if len({tuple(row["destination"]) for row in rows}) == 1]
        if not roots and required is None:
            raise ValueError("No unambiguous native roots in closed subset")
        preloads, containers, assets = [], [], []
        for root in sorted(roots, key=lambda row: row["path"].lower()):
            identity, path = root["destination"][2], root["path"].lower()
            dependencies = sorted(closure(graph, [identity], {}))
            containers.append((path, dict(preloadIndex=len(preloads), preloadSize=len(dependencies), asset=dict(m_FileID=0, m_PathID=identity))))
            preloads.extend(dict(m_FileID=fid, m_PathID=pid) for fid, pid in dependencies)
            assets.append(dict(name=path, type=NATIVE_ROOT_TYPES[root["class_id"]]))
        container = dict(
            m_Name=name,
            m_PreloadTable=preloads,
            m_Container=containers,
            m_MainAsset=dict(preloadIndex=0, preloadSize=0, asset=dict(m_FileID=0, m_PathID=0)),
            m_RuntimeCompatibility=1,
            m_AssetBundleName=name,
            m_Dependencies=[],
            m_IsStreamedSceneAssetBundle=False,
            m_ExplicitDataLayout=0,
            m_PathFlags=7,
            m_SceneHashes=[],
        )
        container_type = M.schemas()[0]
        container_type["dependencies"] = []
        if required is None:
            container_body = W.write_shader_body(W.shader_node(container_type["tree"]), container)
        else:
            groups = required["asset_groups"]
            for group in groups:
                if any(identity not in graph for identity in group["roots"]):
                    raise ValueError("Required asset group root absent")
            # produce retains GUID order and every root/subasset of each path.
            container_body = produce_graph(
                dict(name=name, member=member, externals=externals, dependencies=dependencies, asset_groups=groups),
                graph,
                {},
                emission_cache=emission_cache,
                endpoint_record=read_produced,
            )
            roots = [
                dict(path=group["path"], destination=[name, member, identity], class_id=selected[name, member, identity]["class_id"])
                for group in groups
                for identity in group["roots"]
            ]
            assets = required["assets"]
            if {row["name"].lower() for row in assets} != {group["path"].lower() for group in groups} or any(not row["type"] for row in assets):
                raise ValueError("Required typed-load requests must cover every asset group")
            count_stream = io.BytesIO(container_body)
            module("catalog_complete").text(count_stream)
            preloads = range(O.B.unpack(count_stream, "<I")[0])
        stage("preload_groups")
        container_id = 1
        while container_id in graph:
            container_id += 1
        objects.append(dict(path_id=container_id, type=container_type, body_bytes=len(container_body), prefix=container_body[:32]))
        external_scripts = {
            struct.unpack_from("<iq", row["prefix"], 16)
            for row in objects
            if row["type"]["class_id"] == 114 and struct.unpack_from("<iq", row["prefix"], 16)[0]
        }
        layout, _ = O.make_layout(dict(externals=externals), objects, include_bodies=False, external_scripts=external_scripts)

        def body(row):
            if row["path_id"] == container_id:
                return io.BytesIO(container_body)
            offset, _ = bodymap[row["path_id"]]
            body_stream.seek(offset)
            return body_stream

        serialized = Path(scratch) / "serialized.assets"
        with store.open("rb") as body_stream, serialized.open("wb") as stream:
            W.write_serialized(stream, layout, body)
        members = [(member, 4, serialized.stat().st_size, lambda: serialized.open("rb"))]
        if resource_extents:
            resource_file = Path(scratch) / "resources.resS"
            S.resource(resource_file, resource_extents, 0, W, O.B.LIMIT)
            members.append((resource_member, 0, resource_file.stat().st_size, lambda: resource_file.open("rb")))
        bundle = output / (name + ".bundle")
        compression = W.codec(codec, codec_sha256) if codec is not None else nullcontext(lambda block, method: block)
        with compression as compress, bundle.open("wb") as stream:
            W.write_bundle(stream, members, compress, flags=0x243 if codec is not None else 0x40)
        stage("serialize_compress")
        # Read the actual final container, metadata and every persisted body.
        # Reset endpoint bytes between phases: a warm read must never hide drift.
        external_bodies.clear()
        external_bytes = 0
        stream = W.B.Bundle(bundle).member(member)
        read = W.read_serialized(stream)
        if any(read[key] != layout[key] for key in ("types", "objects", "scripts", "externals")):
            raise ValueError("Emitted native metadata differs")
        final_objects = {row["path_id"]: row for row in read["objects"]}
        final_bodies = OrderedDict()
        final_bytes = 0

        def read_final(target):
            nonlocal final_bytes
            if tuple(target[:2]) != (name, member):
                return read_produced(target)
            target = tuple(target)
            if target in final_bodies:
                final_bodies.move_to_end(target)
                return final_bodies[target]
            row = final_objects[target[2]]
            stream.seek(read["data_offset"] + row["offset"])
            value = selected[tuple(target)]
            raw = O.B.exact(stream, row["bytes"])
            typ = read["types"][row["type_id"]]
            if required is not None:
                typ = qualified_final_type(raw, typ, read["scripts"], typed[value["full_type"]])
            final_bodies[target] = value, raw, typ
            final_bytes += len(raw)
            while final_bytes > 32 * 1024 * 1024 and final_bodies:
                _, (_, prior, _) = final_bodies.popitem(last=False)
                final_bytes -= len(prior)
            return value, raw, typ

        for row in read["objects"]:
            stream.seek(read["data_offset"] + row["offset"])
            data = O.B.exact(stream, row["bytes"])
            identity = row["path_id"]
            expected = hashlib.sha256(container_body).hexdigest() if identity == container_id else emitted_hashes[identity]
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Emitted native body differs")
            if required is not None and identity != container_id:
                value = selected[name, member, identity]
                typ = qualified_final_type(data, read["types"][row["type_id"]], read["scripts"], typed[value["full_type"]])
                fields = pointers(data, typ, cache)
                if set(fields.values()) != graph[identity]:
                    raise ValueError("Persisted required object references differ")
                for field, target in qualified_targets[identity].items():
                    expected_pointer = (0, target[2]) if tuple(target[:2]) == (name, member) else (externals.index(target[1]) + 1, target[2])
                    if fields[field] != expected_pointer:
                        raise ValueError("Persisted qualified external field differs")
                    endpoint, raw, endpoint_type = read_final(target)
                    if tuple(target[:2]) != (name, member) and (
                        (len(raw), hashlib.sha256(raw).hexdigest()) != (endpoint["bytes"], endpoint["sha256"])
                        or full_type_key(endpoint_type) != endpoint["full_type"]
                    ):
                        raise ValueError("Persisted external endpoint drift")
                if typ["class_id"] == 114:
                    managed_check(selected[name, member, identity], data, typ, read_final)
        if resource_extents:
            resource_stream = W.B.Bundle(bundle).member(resource_member)
            for row in resource_rows:
                resource_stream.seek(row["emitted"]["offset"])
                remaining, digest = row["emitted"]["size"], hashlib.sha256()
                while remaining:
                    part = O.B.exact(resource_stream, min(remaining, S.CHUNK))
                    digest.update(part)
                    remaining -= len(part)
                if digest.hexdigest() != row["source_resource"]["sha256"]:
                    raise ValueError("Emitted native resource differs")
        digest = O.B.sha(bundle)
        stage("persisted_validation")
    gaps = dict(
        complete=False,
        full_graph_selected=len(all_records),
        emitted_records=len(selected),
        omitted_records=len(all_records) - len(selected),
        full_graph_blocks=retained.get("blocks"),
        full_graph_block_counts=retained.get("block_counts"),
        ambiguous_root_paths=[path for path, rows in grouped.items() if len({tuple(row["destination"]) for row in rows}) > 1],
        policy="Closed native/local subset; external endpoints, managed bindings and ordered Sprite cohorts remain excluded. No full catalog or gameplay admission.",
    )
    result = dict(
        success=True,
        structural_accepted=True,
        typed_load_accepted=False,
        whole_game_complete=False,
        device_accepted=False,
        bundle=str(bundle.resolve()),
        sha256=digest,
        bytes=bundle.stat().st_size,
        compression=dict(method="lz4", codec_sha256=codec_sha256) if codec is not None else dict(method="none"),
        records=len(selected),
        resource_records=len(resource_rows),
        resource_bytes=resource_size,
        roots=len(roots),
        preloads=len(preloads),
        classes=dict(Counter(row["class_id"] for row in selected.values())),
        typed_classes=dict(Counter(row["type"] for row in assets)),
        graph_receipt_sha256=O.B.sha(graph_directory / "done.json"),
        selected_records_sha256=O.B.sha(graph_directory / "selected-records.jsonl"),
        selected_roots_sha256=O.B.sha(graph_directory / "selected-roots.jsonl") if required is None else None,
        source_type_pins=schema_pins,
        producer_pins=providers.pins,
        seconds=time.monotonic() - started,
        stages=stages,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
    )
    if required is not None:
        result["required_set_accepted"] = True
        result["field_qualification"] = "structural-current-routes" if structural_routes is not None else "source-provenance"
        result["required_request_sha256"] = hashlib.sha256(json.dumps(required, sort_keys=True).encode()).hexdigest()
        result["qualified_endpoint_pins"] = [
            dict(destination=list(target), selected_row_sha256=hashlib.sha256(pin[0].encode()).hexdigest(), body_sha256=pin[1], full_type=pin[2])
            for target, pin in sorted(endpoint_pins.items())
        ]
        gaps.update(
            required_records=len(selected),
            complete=False,
            policy="Exact requested object set; whole catalog, Unity typed load and device acceptance remain open.",
        )
    for filename, value in (
        ("result.json", result),
        ("gaps.json", gaps),
        ("roots.json", roots),
        ("request.json", dict(path=str(bundle.resolve()), sha256=digest, assets=assets)),
    ):
        (output / filename).write_text(json.dumps(value, indent=2) + "\n")
    if resource_rows:
        (output / "resources.jsonl").write_text("".join(json.dumps(row) + "\n" for row in resource_rows))
    if emission_cache is not None:
        if emission_input_pins(selected, graph_directory, schema_paths, codec, cache_inputs, provider_paths) != input_pins:
            raise ValueError("Emission cache input drift")
        stage("input_revalidation")
        result.update(cache=dict(emission_cache.counts), cache_reused=False, seconds=time.monotonic() - started)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        emission_cache.put(
            "outputs",
            request_key,
            json.dumps(
                dict(
                    result=result,
                    outputs={str(path.resolve()): O.B.sha(path) for path in output.iterdir() if path.is_file()},
                )
            ).encode(),
        )
    return result


def repack_canonical_aliases(
    source,
    output,
    required,
    aliases,
    selected_records,
    qualified_types,
    canonical_profile,
    canonical_bundle,
    *,
    codec=None,
    codec_sha256=None,
    cache_directory=None,
    endpoint_record=None,
):
    """Route consumers to explicit catalog owners after strict native emission.

    The caller supplies the qualified emitted bundle and its selection/types,
    plus source-body aliases and the canonical producer profile/container.
    Structural routes remain immutable. This bounded pass preserves duplicate
    objects and their reciprocal native ownership; it never establishes Unity
    typed load, current-CLR qualification or device acceptance itself.
    """
    from contextlib import closing, nullcontext
    import copy
    import json
    import resource
    import sys
    import tempfile
    import time

    W = module("unity_write")
    source, output, canonical_bundle = Path(source), Path(output), Path(canonical_bundle)
    aliases, selected_records = list(aliases), list(selected_records)
    name, member = required["name"], required["member"]
    canonical = canonical_profile["bundle"]
    check_preload_seeds(required, endpoint_record)
    if (codec is None) != (codec_sha256 is None):
        raise ValueError("Canonical repack compression needs codec and SHA-256")
    paths = [source, canonical_bundle, *Path(__file__).parent.glob("*.py")]
    if codec is not None:
        paths.append(Path(codec))

    def pins():
        return {str(path.resolve()): O.B.sha(path) for path in paths}

    started, input_pins = time.monotonic(), pins()
    request_key = EmissionCache.key(
        dict(
            inputs={path: digest for path, digest in input_pins.items() if path != str(source.resolve())},
            source_sha256=input_pins[str(source.resolve())],
            required=required,
            aliases=aliases,
            selected=selected_records,
            qualified_types=qualified_types,
            canonical_profile=canonical_profile,
            codec_sha256=codec_sha256,
        )
    )
    with closing(EmissionCache(cache_directory)) if cache_directory is not None else nullcontext(None) as emission_cache:
        saved = emission_cache.get("canonical", request_key) if emission_cache is not None else None
        if saved is not None:
            result = json.loads(saved)
            if Path(result["bundle"]).is_file() and O.B.sha(Path(result["bundle"])) == result["sha256"]:
                if pins() != input_pins:
                    raise ValueError("Canonical repack input drift")
                result.update(cache_reused=True, inputs=input_pins, seconds=time.monotonic() - started)
                return materialize_cached_bundle(result, output, {result["bundle"]: result["sha256"]})
        mapping = {tuple(row["duplicate"]): row for row in aliases}
        selected = {tuple(row["destination"]): row for row in selected_records if tuple(row["destination"]) in mapping}
        if not mapping or len(mapping) != len(aliases) or selected.keys() != mapping.keys():
            raise ValueError("Canonical aliases require distinct selected duplicate endpoints")
        bundle, target_bundle = W.B.Bundle(source), W.B.Bundle(canonical_bundle)
        with bundle.member(member) as stream, target_bundle.member(canonical["member"]) as target_stream:
            layout, target_layout = W.read_serialized(stream), W.read_serialized(target_stream)
            objects = {row["path_id"]: row for row in layout["objects"]}
            target_objects = {row["path_id"]: row for row in target_layout["objects"]}
            externals = [row["path"].rsplit("/", 1)[-1] if row["path"].startswith("archive:/") else row["path"] for row in layout["externals"]]
            if externals != required["externals"] or canonical["member"] not in externals:
                raise ValueError("Canonical repack must preserve the external member table")
            native = module("catalog_complete").ProducedMembers()
            native.add(member, stream, name)
            native.add(canonical["member"], target_stream, canonical["name"])
            specifications = {row["path_id"]: row for row in canonical_profile["objects"]}
            schemas, ownership, component_arrays, proof = {}, {}, {}, []

            def record(handle, metadata, obj):
                handle.seek(metadata["data_offset"] + obj["offset"])
                return W.B.exact(handle, obj["bytes"])

            for key, alias in mapping.items():
                value, destination = selected[key], tuple(alias["canonical"])
                if (
                    key[:2] != (name, member)
                    or destination[:2] != (canonical["name"], canonical["member"])
                    or tuple(value.get("source", ())) != tuple(alias["source"])
                    or value["sha256"] != alias["duplicate_body_sha256"]
                    or value["full_type"] != alias["duplicate_full_type"]
                ):
                    raise ValueError("Canonical source or selected identity differs")
                specification = specifications[destination[2]]
                selector = specification.get("properties_hash", {}).get("behaviour", specification.get("source"))
                if selector is None:
                    raise ValueError("Canonical alias needs original body provenance, not type_source")
                original = canonical_profile["sources"][selector[0]]
                if [original["path"], original["member"], selector[1]] != alias["source"]:
                    raise ValueError("Canonical profile selects a different original body")
                old, new = objects[key[2]], target_objects[destination[2]]
                old_body, new_body = record(stream, layout, old), record(target_stream, target_layout, new)
                old_type, new_type = layout["types"][old["type_id"]], target_layout["types"][new["type_id"]]
                qualified = {k: bytes.fromhex(v) if k in ("tree", "hash", "script_id") else v for k, v in qualified_types[value["full_type"]].items()}
                qualified_final_type(old_body, old_type, layout["scripts"], qualified)
                qualified_final_type(new_body, new_type, target_layout["scripts"], new_type)
                if old_type["class_id"] != alias["duplicate_class_id"] or {k: v for k, v in old_type.items() if k != "script_type"} != {
                    k: v for k, v in new_type.items() if k != "script_type"
                }:
                    raise ValueError("Canonical full native/script/schema type differs")
                pointers(old_body, old_type, schemas)
                pointers(new_body, new_type, schemas)
                if old_type["class_id"] == 1:
                    for duplicate, pid, body, typ, handle, metadata, members in (
                        (True, key[2], old_body, old_type, stream, layout, objects),
                        (False, destination[2], new_body, new_type, target_stream, target_layout, target_objects),
                    ):
                        for component_field, (fid, component_pid) in pointers(body, typ, schemas).items():
                            if fid or component_pid not in members:
                                raise ValueError("Catalog GameObject component must be present and local")
                            component = members[component_pid]
                            component_body = record(handle, metadata, component)
                            fields = pointers(component_body, metadata["types"][component["type_id"]], schemas)
                            owner_field = ("m_GameObject",) if ("m_GameObject",) in fields else ("#374",)
                            if fields.get(owner_field) != (0, pid):
                                raise ValueError("Catalog GameObject/component reciprocal ownership differs")
                            if duplicate:
                                component_arrays[pid, component_field] = (fid, component_pid)
                                owner_key = component_pid, owner_field
                                if owner_key in ownership:
                                    raise ValueError("Component has repeated duplicate GameObject owners")
                                ownership[owner_key] = pid
                identity = None
                if old_type["class_id"] == 114:
                    identity = native.managed_identity(canonical["member"], new_type, new_body)
                    if native.managed_identity(member, old_type, old_body) != identity:
                        raise ValueError("Canonical and duplicate managed identities differ")
                proof.append(
                    dict(
                        **alias,
                        emitted_duplicate_sha256=hashlib.sha256(old_body).hexdigest(),
                        canonical_sha256=hashlib.sha256(new_body).hexdigest(),
                        canonical_script_identity=identity,
                    )
                )
            replacements, graph, hashes, changes = {}, {}, {}, []
            container = None
            for pid, obj in objects.items():
                body, typ = record(stream, layout, obj), layout["types"][obj["type_id"]]
                hashes[pid] = hashlib.sha256(body).hexdigest()
                if typ["class_id"] == 142:
                    if container is not None:
                        raise ValueError("Multiple AssetBundle containers")
                    container = pid
                    continue
                fields = pointers(body, typ, schemas)
                targets = {
                    field: tuple(mapping[name, member, pointer[1]]["canonical"])
                    for field, pointer in fields.items()
                    if pointer[0] == 0 and (name, member, pointer[1]) in mapping and (pid, field) not in ownership
                }
                if targets:
                    revised_body = relocate_pointer_fields({"destination": [name, member, pid]}, body, typ, targets, externals)
                    expected = bytearray(body)
                    spans = A.fields(body, schemas[typ["tree"]])[1]
                    for field, target in targets.items():
                        begin, end = spans[field]
                        if end - begin != 12:
                            raise ValueError("Canonical field must be a complete PPtr")
                        struct.pack_into("<iq", expected, begin, externals.index(target[1]) + 1, target[2])
                        changes.append(dict(owner=pid, field=list(field), target=target))
                    if revised_body != bytes(expected):
                        raise ValueError("Canonical relocation changed unrelated bytes")
                    body = replacements[pid] = revised_body
                for field, pointer in pointers(body, typ, schemas).items():
                    if (pid, field) in component_arrays and pointer != component_arrays[pid, field]:
                        raise ValueError("Canonical repack changed GameObject component membership")
                graph[pid] = set(pointers(body, typ, schemas).values())
                for field, pointer in pointers(body, typ, schemas).items():
                    if (pid, field) in ownership:
                        if pointer != (0, ownership[pid, field]):
                            raise ValueError("Canonical repack changed reciprocal component ownership")
                    elif pointer[0] == 0 and (name, member, pointer[1]) in mapping:
                        raise ValueError("Canonical repack retained a consumer alias")
            if container is None or set(graph) != set(required["path_ids"]):
                raise ValueError("Canonical repack required object set differs")
            validate_graph(graph, len(externals))
            replacements[container] = produce_graph(required, graph, {}, emission_cache=emission_cache, endpoint_record=endpoint_record)
            revised = copy.deepcopy(layout)
            offset = 0
            for obj in sorted(revised["objects"], key=lambda row: row["offset"]):
                offset = (offset + 7) // 8 * 8
                obj["offset"] = offset
                obj["bytes"] = len(replacements[obj["path_id"]]) if obj["path_id"] in replacements else objects[obj["path_id"]]["bytes"]
                offset += obj["bytes"]
            revised["bytes"] = revised["data_offset"] + offset
            output.mkdir(parents=True, exist_ok=False)
            with tempfile.TemporaryDirectory(prefix=".canonical-", dir=output) as scratch:
                temporary = Path(scratch) / "serialized"

                def body_for(obj):
                    if obj["path_id"] in replacements:
                        return io.BytesIO(replacements[obj["path_id"]])
                    stream.seek(layout["data_offset"] + objects[obj["path_id"]]["offset"])
                    return stream

                with temporary.open("xb") as handle:
                    W.write_serialized(handle, revised, body_for)
                target = output / (name + ".bundle")
                members = [
                    (m, flags, temporary.stat().st_size if m == member else size, lambda m=m: temporary.open("rb") if m == member else bundle.member(m))
                    for m, (_, size, flags) in bundle.members.items()
                ]
                compression = W.codec(codec, codec_sha256) if codec is not None else nullcontext(lambda block, method: block)
                with compression as compress, target.open("xb") as handle:
                    W.write_bundle(handle, members, compress, engine=layout["engine"], flags=0x243 if codec is not None else 0x40)
            actual = W.B.Bundle(target)
            with actual.member(member) as persisted:
                metadata = W.read_serialized(persisted)
                if metadata != revised:
                    raise ValueError("Persisted canonical metadata differs")
                for obj in metadata["objects"]:
                    pid = obj["path_id"]
                    raw = record(persisted, metadata, obj)
                    expected = hashlib.sha256(replacements[pid]).hexdigest() if pid in replacements else hashes[pid]
                    if hashlib.sha256(raw).hexdigest() != expected:
                        raise ValueError("Persisted canonical body differs")
                    if pid != container and set(pointers(raw, metadata["types"][obj["type_id"]], schemas).values()) != graph[pid]:
                        raise ValueError("Persisted canonical pointer graph differs")
            for other in bundle.members:
                if other != member:
                    with bundle.member(other) as before, actual.member(other) as after:

                        def digest(handle):
                            value = hashlib.sha256()
                            while block := handle.read(1024 * 1024):
                                value.update(block)
                            return value.digest()

                        if digest(before) != digest(after):
                            raise ValueError("Canonical repack changed unrelated member")
        if pins() != input_pins:
            raise ValueError("Canonical repack input drift")
        result = dict(
            success=True,
            non_final=True,
            typed_load_accepted=False,
            device_accepted=False,
            bundle=str(target),
            sha256=O.B.sha(target),
            bytes=target.stat().st_size,
            canonical_roots=len(mapping),
            preserved_reciprocal_owner_fields=len(ownership),
            changed_fields=len(changes),
            changed_objects=len(replacements) - 1,
            source_identity_proof=proof,
            ownership=[dict(component=pid, field=field, owner=owner) for (pid, field), owner in ownership.items()],
            inputs=input_pins,
            request_sha256=request_key,
            cache_reused=False,
            seconds=time.monotonic() - started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        )
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        if emission_cache is not None:
            emission_cache.put("canonical", request_key, json.dumps(result).encode())
        return result


def catalog_artifacts(required, final, output):
    """Declare the checked emitted container, independently of its alias donor.

    The emitter/repacker has already checked these groups against final bytes.
    Keep the same declaration for catalog ownership; do not rerun production or
    copy the bundle into a second artifact directory.
    """
    import json

    profile = Path(output) / "catalog-profile.json"
    profile.write_text(json.dumps(dict(bundle={key: required[key] for key in ("name", "member", "asset_groups")}), indent=2) + "\n")

    def pin(path):
        path = Path(path).resolve(strict=True)
        return dict(path=str(path), bytes=path.stat().st_size, sha256=O.B.sha(path))

    return dict(catalog_profile=pin(profile), catalog_bundle=pin(final["bundle"]))


def produce_request(inputs, output, *, cache_directory=None):
    """Run the checked emitter/repacker with explicit, request-relative inputs."""
    from contextlib import closing
    import json
    from types import SimpleNamespace

    inputs = Path(inputs).resolve(strict=True)
    request = json.loads(inputs.read_bytes())
    required_keys = {"schema", "graph", "schemas", "required", "routes", "endpoints", "staged", "managed_inputs", "game_root", "codec", "bundle", "member"}
    if set(request) - {"canonical", "null_script_sources", "provider_paths"} != required_keys or request["schema"] != "owner-bundle-preload-inputs-v1":
        raise ValueError("unsupported bundle preload input contract")
    E = module("bundle_endpoints")
    owner = SimpleNamespace(**globals())
    pins = E.InputPins(inputs.parent, owner)
    pins.add(inputs)
    provider_paths = {}
    if "provider_paths" in request:
        path = pins.pin(request["provider_paths"])
        aliases = json.loads(path.read_bytes())
        if not isinstance(aliases, dict) or any(
            not isinstance(key, str) or not key or not isinstance(value, str) or not value for key, value in aliases.items()
        ):
            raise ValueError("native provider paths require nonempty source/directory strings")
        for source, value in aliases.items():
            directory = pins.path(value, path.parent)
            if not directory.is_dir() and not directory.is_file():
                raise ValueError("provider path must name a directory or serialized file")
            provider_paths[source] = directory
    graph_files = {name: pins.pin(value) for name, value in request["graph"].items()}
    if not {"done.json", "selected-records.jsonl"} <= graph_files.keys() or set(graph_files) - {"done.json", "selected-records.jsonl", "selected-roots.jsonl"}:
        raise ValueError("explicit graph receipt/records and optional roots required")
    graph = graph_files["done.json"].parent
    if any(path != graph / name for name, path in graph_files.items()):
        raise ValueError("graph files must retain their declared directory and names")
    if (graph / "selected-roots.jsonl").is_file() and "selected-roots.jsonl" not in graph_files:
        raise ValueError("graph roots require an explicit input pin")
    schema_paths = [pins.pin(value) for value in request["schemas"]]
    types = {}
    for path in schema_paths:
        for key, value in json.loads(path.read_bytes()).items():
            if key in types and types[key] != value:
                raise ValueError("Conflicting complete native schema")
            types[key] = value
    selected = {}
    for path in (pins.pin(request["endpoints"]), graph_files["selected-records.jsonl"]):
        for value in json_rows(path):
            key = tuple(value["destination"])
            if key in selected and selected[key] != value:
                raise ValueError("Conflicting endpoint descriptor")
            selected[key] = value
    required = pins.read(request["required"])
    for key in ("name", "member"):
        expected = request["bundle" if key == "name" else key]
        if key in required and required[key] != expected:
            raise ValueError("Required bundle/member identity differs")
        required[key] = expected
    routes = {}
    for value in json_rows(pins.pin(request["routes"])):
        key = tuple(value["owner"])
        if key in routes:
            raise ValueError("Duplicate structural route owner")
        routes[key] = value["edges"]
    codec = pins.pin(request["codec"])
    canonical = request.get("canonical")
    if canonical is not None:
        aliases, profile = pins.read(canonical["aliases"]), pins.read(canonical["profile"])
        canonical_bundle = pins.pin(canonical["bundle"])
    root = Path(__file__).resolve().parents[3]
    for path in (root / "scripts/lab").glob("*.py"):
        pins.add(path)
    with closing(E.Qualification(owner, pins, request, selected, types, required, provider_paths=provider_paths)) as qualification:
        qualification.setup()
        # Populate external managed readback even when emission reuses an output.
        for target in sorted({tuple(edge["target"]) for edges in routes.values() for edge in edges if tuple(edge["target"][:2]) != qualification.member}):
            qualification.endpoints(target)
        emission = emit_closed_native(
            graph,
            schema_paths,
            Path(output) / "emitted",
            request["bundle"],
            request["member"],
            codec=codec,
            codec_sha256=request["codec"]["sha256"],
            required=required,
            structural_routes=routes,
            endpoint_record=qualification.endpoints,
            managed_check=qualification.check,
            cache_directory=cache_directory,
            cache_inputs=pins.files,
            provider_paths=provider_paths,
        )
        qualification.check_final(emission["bundle"])
        final = emission
        if canonical is not None:
            final = repack_canonical_aliases(
                emission["bundle"],
                Path(output) / "canonical",
                required=required,
                aliases=aliases,
                selected_records=list(selected.values()),
                qualified_types=types,
                canonical_profile=profile,
                canonical_bundle=canonical_bundle,
                codec=codec,
                codec_sha256=request["codec"]["sha256"],
                cache_directory=cache_directory,
                endpoint_record=qualification.endpoints,
            )
            qualification.check_final(final["bundle"])
        pins.check()
        result = dict(
            success=True,
            bundle=final["bundle"],
            sha256=final["sha256"],
            emission=emission,
            canonical=None if canonical is None else final,
            **catalog_artifacts(required, final, output),
            typed_load_accepted=False,
            device_accepted=False,
        )
        (Path(output) / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Emit an explicitly partial, closed native bundle from source-produced records")
    parser.add_argument("--inputs", type=Path, help="explicit checked emission/canonical request; paths relative to this file")
    parser.add_argument("--cache", type=Path, help="private incremental emission/preload/repack cache")
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--schema", type=Path, action="append")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle")
    parser.add_argument("--member")
    parser.add_argument("--codec", type=Path, help="pinned LZ4 helper; compresses UnityFS blocks without changing member bytes")
    parser.add_argument("--codec-sha256")
    args = parser.parse_args()
    if args.inputs is not None:
        if any(value is not None for value in (args.graph, args.schema, args.bundle, args.member, args.codec, args.codec_sha256)):
            parser.error("--inputs cannot be combined with legacy emission inputs")
        print(json.dumps(produce_request(args.inputs, args.output, cache_directory=args.cache), indent=2))
        return
    if args.cache is not None or any(value is None for value in (args.graph, args.schema, args.bundle, args.member)):
        parser.error("legacy emission requires --graph, --schema, --bundle and --member; --cache requires --inputs")
    print(
        json.dumps(
            emit_closed_native(args.graph, args.schema, args.output, args.bundle, args.member, codec=args.codec, codec_sha256=args.codec_sha256), indent=2
        )
    )


if __name__ == "__main__":
    main()
