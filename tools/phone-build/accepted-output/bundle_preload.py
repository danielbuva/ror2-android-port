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
    validate_graph(graph, len(selected["externals"]))
    owners = external_owners(selected, sources, schemas)
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


def emit_closed_native(graph_directory, schema_paths, output, name, member):
    """Emit the declared local/native subset of a qualified producer graph.

    This is explicitly partial, even when all eligible records close. Bodies,
    native schemas and actual PPtrs are checked independently of graph claims.
    No historical bundle, accepted body or comparator is an input.
    """
    from collections import Counter, defaultdict
    import json
    import tempfile
    import time
    import resource
    import sys

    M = module("bundle_manifest")
    W = M.W
    S = module("object_stream")
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
    selected = {
        key: row
        for key, row in all_records.items()
        if key[:2] == (name, member)
        and (Path(row["provider"]) / "result.json").is_file()
        and row.get("schema")
        and row["class_id"] not in (114, 115, 142)
        and (not row.get("resource") or row["class_id"] in (28, 89, 43))
        and all(edge[0] == 0 for edge in row.get("edges", [[1, 1]]))
    }
    while True:
        missing = [key for key, row in selected.items() if any(pid and (*key[:2], pid) not in selected for _, pid in row["edges"])]
        if not missing:
            break
        for key in missing:
            del selected[key]
    schemas, schema_pins = {}, {}
    needed = {row["schema"] for row in selected.values()}
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
        if hashlib.sha256(typ["tree"]).hexdigest() != key or typ["script_type"] != -1:
            raise ValueError("Native schema identity differs")
        typ.setdefault("dependencies", [])
        typed[key] = typ
    by_provider = defaultdict(list)
    for row in selected.values():
        by_provider[row["provider"]].append(row)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=".emission-", dir=output) as scratch:
        store = Path(scratch) / "bodies.bin"
        objects, graph, bodymap, source_pins, cache = [], {}, {}, {}, {}
        resource_extents, resource_rows, emitted_hashes = [], [], {}
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
                    typ = typed[value["schema"]]
                    if row.get("resource") != value.get("resource") or (row["bytes"], row["sha256"]) != (value["bytes"], value["sha256"]):
                        raise ValueError("Native provider record or resource drift")
                    if (
                        typ["class_id"] != value["class_id"]
                        or (value.get("native_type_hash") and typ["hash"].hex() != value["native_type_hash"])
                        or (row.get("native_type_hash") and typ["hash"].hex() != row["native_type_hash"])
                    ):
                        raise ValueError("Native type identity differs")
                    body = O.record_extent(directory / "objects.bin", row)
                    edges = set(pointers(body, typ, cache).values())
                    if edges != set(map(tuple, value["edges"])):
                        raise ValueError("Measured native pointers differ from selected graph")
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
        validate_graph(graph, 0)
        grouped = defaultdict(list)
        for row in json_rows(graph_directory / "selected-roots.jsonl"):
            key = tuple(row["destination"])
            if key in selected and row["class_id"] in NATIVE_ROOT_TYPES:
                if row["class_id"] != selected[key]["class_id"]:
                    raise ValueError("Native root type differs from produced object")
                grouped[row["path"].lower()].append(row)
        roots = [rows[0] for rows in grouped.values() if len({tuple(row["destination"]) for row in rows}) == 1]
        if not roots:
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
        container_body = W.write_shader_body(W.shader_node(container_type["tree"]), container)
        container_id = 1
        while container_id in graph:
            container_id += 1
        objects.append(dict(path_id=container_id, type=container_type, body_bytes=len(container_body), prefix=container_body[:32]))
        layout, _ = O.make_layout(dict(externals=[]), objects, include_bodies=False)

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
        with bundle.open("wb") as stream:
            W.write_bundle(stream, members, lambda block, method: block, flags=0x40)
        # Read the actual final container, metadata and every persisted body.
        stream = W.B.Bundle(bundle).member(member)
        read = W.read_serialized(stream)
        if read["types"] != layout["types"] or read["objects"] != layout["objects"] or read["scripts"] or read["externals"]:
            raise ValueError("Emitted native metadata differs")
        for row in read["objects"]:
            stream.seek(read["data_offset"] + row["offset"])
            data = O.B.exact(stream, row["bytes"])
            identity = row["path_id"]
            expected = hashlib.sha256(container_body).hexdigest() if identity == container_id else emitted_hashes[identity]
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Emitted native body differs")
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
        records=len(selected),
        resource_records=len(resource_rows),
        resource_bytes=resource_size,
        roots=len(roots),
        preloads=len(preloads),
        classes=dict(Counter(row["class_id"] for row in selected.values())),
        typed_classes=dict(Counter(row["type"] for row in assets)),
        graph_receipt_sha256=O.B.sha(graph_directory / "done.json"),
        selected_records_sha256=O.B.sha(graph_directory / "selected-records.jsonl"),
        selected_roots_sha256=O.B.sha(graph_directory / "selected-roots.jsonl"),
        source_type_pins=schema_pins,
        producer_pins=source_pins,
        seconds=time.monotonic() - started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
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
    args = parser.parse_args()
    print(json.dumps(emit_closed_native(args.graph, args.schema, args.output, args.bundle, args.member), indent=2))


if __name__ == "__main__":
    main()
