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


def produce(selected, records, sources):
    schemas = {}
    graph = {}
    for row in records:
        if row["path_id"] in graph:
            raise ValueError("Duplicate produced prefab graph identity")
        graph[row["path_id"]] = set(pointers(row["body"], row["type"], schemas).values())
    owners = external_owners(selected, sources, schemas)
    ranks = file_ranks(selected)
    groups = sorted(selected["asset_groups"], key=lambda row: guid_key(row["guid"]))
    if not groups or len({row["guid"] for row in groups}) != len(groups) or len({row["path"].lower() for row in groups}) != len(groups):
        raise ValueError("Prefab asset grouping requires unique source paths and GUIDs")
    preloads, containers = [], []
    for group in groups:
        roots = group["roots"]
        if not roots or len(set(roots)) != len(roots):
            raise ValueError("Prefab asset group requires distinct imported roots")
        dependencies = closure(graph, roots, owners)
        if any(file_id not in ranks for file_id, _ in dependencies):
            raise ValueError("Prefab preload references an absent serialized file")
        ordered = sorted(dependencies, key=lambda pointer: (ranks[pointer[0]], pointer[1]))
        containers.extend((group["path"].lower(), len(preloads), len(ordered), root) for root in roots)
        preloads.extend(ordered)
    stream = io.BytesIO()
    O.aligned_string(stream, selected["name"])
    stream.write(struct.pack("<I", len(preloads)))
    for pointer in preloads:
        stream.write(struct.pack("<iq", *pointer))
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
