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
            signature = target, tuple(proof["source_target"]), json.dumps(expected, sort_keys=True)
            valid[signature] = target
        if len(valid) != 1:
            raise ValueError(f"External field lacks a unique persisted endpoint: {owner} {field} ({len(valid)})")
        targets[field] = next(iter(valid.values()))
    return targets


def relocate_external_fields(value, body, typ, targets, externals):
    """Allocate qualified fields by destination member, never by an old slot."""
    if len(set(externals)) != len(externals) or value["destination"][1] in externals:
        raise ValueError("Ambiguous external member allocation")
    members = {value["destination"][1]: tuple(value["destination"][:2])}
    for target in targets.values():
        identity = tuple(target[:2])
        if members.setdefault(target[1], identity) != identity:
            raise ValueError("Ambiguous external member allocation")
    fields = pointers(body, typ, {})
    required = {field for field, (fid, pid) in fields.items() if fid and pid}
    if set(targets) != required:
        raise ValueError("External relocation requires complete per-field coverage")
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


def produce_graph(selected, graph, sources):
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
    for group in groups:
        roots = group["roots"]
        if not roots or len(set(roots)) != len(roots):
            raise ValueError("Prefab asset group requires distinct imported roots")
        dependencies = closure(graph, roots, owners)
        if any(file_id not in ranks for file_id, _ in dependencies):
            raise ValueError("Prefab preload references an absent serialized file")
        ordered = sorted(dependencies, key=lambda pointer: (ranks[pointer[0]], pointer[1]))
        containers.extend((group["path"].lower(), preload_count, len(ordered), root) for root in roots)
        for pointer in ordered:
            stream.write(struct.pack("<iq", *pointer))
        preload_count += len(ordered)
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


def emit_closed_native(
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
    endpoint_record=None,
    managed_check=None,
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
    graph_directory, output = Path(graph_directory), Path(output)
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
            and (Path(row["provider"]) / "result.json").is_file()
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
    while required is None:
        missing = [key for key, row in selected.items() if any(pid and (*key[:2], pid) not in selected for _, pid in row["edges"])]
        if not missing:
            break
        for key in missing:
            del selected[key]
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

    def read_external(target):
        if endpoint_record is None:
            raise ValueError("Required external endpoint reader absent")
        value, raw, typ = endpoint_record(target)
        pin = json.dumps(value, sort_keys=True), hashlib.sha256(raw).hexdigest(), full_type_key(typ)
        if endpoint_pins.setdefault(tuple(target), pin) != pin:
            raise ValueError("Persisted external endpoint drift")
        return value, raw, typ

    by_provider = defaultdict(list)
    for row in selected.values():
        by_provider[row["provider"]].append(row)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=".emission-", dir=output) as scratch:
        store = Path(scratch) / "bodies.bin"
        objects, graph, bodymap, source_pins, cache = [], {}, {}, {}, {}
        resource_extents, resource_rows, emitted_hashes = [], [], {}
        qualified_targets, managed_rows = {}, {}
        resource_size = 0
        resource_member = member + ".resS"
        resource_path = "archive:/" + member + "/" + resource_member
        with store.open("wb") as destination:
            for provider, values in by_provider.items():
                directory = Path(provider)
                receipt = json.loads((directory / "result.json").read_text())
                if receipt.get("success") is not True or {row["record"] for row in values} != {receipt["profile_sha256"]}:
                    raise ValueError("Unexpected or unsuccessful native provider")
                pin = dict(receipt_sha256=O.B.sha(directory / "result.json"), index_sha256=O.B.sha(directory / "index.jsonl"))
                if pin["index_sha256"] != receipt["outputs"]["index.jsonl"]["sha256"]:
                    raise ValueError("Native provider index drift")
                source_pins[provider] = pin
                index = {}
                for row in json_rows(directory / "index.jsonl"):
                    identity = row["bundle"], row["member"], row["path_id"]
                    if identity in index:
                        raise ValueError("Duplicate native provider identity")
                    index[identity] = row
                for value in values:
                    identity = value["destination"][2]
                    row = index[tuple(value["record_source"])]
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
                    body = O.record_extent(directory / "objects.bin", row)
                    edges = set(pointers(body, typ, cache).values())
                    if edges != set(map(tuple, value["edges"])):
                        raise ValueError("Measured native pointers differ from selected graph")
                    if required is not None:
                        targets = qualify_external_fields(value, body, typ, proofs.get(tuple(value["destination"]), ()), read_external)
                        qualified_targets[identity] = targets
                        body = relocate_external_fields(value, body, typ, targets, externals)
                        if typ["class_id"] == 114:
                            managed_rows[identity] = value, typ
                        edges = set(pointers(body, typ, cache).values())
                    if row.get("resource"):
                        resource_size = (resource_size + 15) // 16 * 16
                        body, descriptor = repack_stream(body, typ, row["resource"], resource_size, resource_path, cache)
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
            container_body = produce_graph(dict(name=name, member=member, externals=externals, dependencies=dependencies, asset_groups=groups), graph, {})
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
        # Read the actual final container, metadata and every persisted body.
        stream = W.B.Bundle(bundle).member(member)
        read = W.read_serialized(stream)
        if any(read[key] != layout[key] for key in ("types", "objects", "scripts", "externals")):
            raise ValueError("Emitted native metadata differs")
        final_objects = {row["path_id"]: row for row in read["objects"]}

        def read_final(target):
            if tuple(target[:2]) != (name, member):
                return read_produced(target)
            row = final_objects[target[2]]
            stream.seek(read["data_offset"] + row["offset"])
            value = selected[tuple(target)]
            raw = O.B.exact(stream, row["bytes"])
            typ = read["types"][row["type_id"]]
            if required is not None:
                typ = qualified_final_type(raw, typ, read["scripts"], typed[value["full_type"]])
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
        producer_pins=source_pins,
        seconds=time.monotonic() - started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
    )
    if required is not None:
        result["required_set_accepted"] = True
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
    return result


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Emit an explicitly partial, closed native bundle from source-produced records")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--schema", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument("--codec", type=Path, help="pinned LZ4 helper; compresses UnityFS blocks without changing member bytes")
    parser.add_argument("--codec-sha256")
    args = parser.parse_args()
    print(
        json.dumps(
            emit_closed_native(args.graph, args.schema, args.output, args.bundle, args.member, codec=args.codec, codec_sha256=args.codec_sha256), indent=2
        )
    )


if __name__ == "__main__":
    main()
