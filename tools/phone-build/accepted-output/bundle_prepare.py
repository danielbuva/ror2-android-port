"""Prepare the existing closed-bundle request from pinned producers and policy.

Original source, producer record and emitted destination identities stay separate.
Only measured PPtr fields are rewritten; the existing emitter remains responsible
for final structural, managed and persisted-object qualification.
"""

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


def original_identities(owner, path, source_files=None):
    """Reverse body-producing profile selectors, never schema-only type_source."""
    result = {}

    def add(record, source):
        result.setdefault(tuple(record), set()).add(tuple(source))

    if str(path).endswith(".jsonl.gz"):
        bundles = owner.A.profile_bundles(path)
    else:
        profile = json.loads(path.read_bytes())
        if "bundles" not in profile:
            bundle = profile["bundle"]
            if source_files is not None:
                for source in profile["sources"]:
                    digest = source["sha256"]
                    if source_files.setdefault(source["path"], digest) != digest:
                        raise ValueError("original source file pins disagree")
            for row in profile["objects"]:
                source = row.get("source", row.get("properties_hash", {}).get("behaviour"))
                if source is not None:
                    original = profile["sources"][source[0]]
                    add((bundle["name"], bundle["member"], row["path_id"]), (original["path"], original["member"], source[1]))
            return result
        bundles = profile["bundles"]
    for bundle in bundles:
        if source_files is not None and source_files.setdefault(bundle["path"], bundle["sha256"]) != bundle["sha256"]:
            raise ValueError("original source file pins disagree")
        for member in bundle["members"]:
            for kind in ("objects", "meshes", "textures", "avatars"):
                for row in member.get(kind, []):
                    for target in row["outputs"]:
                        add((target["bundle"], target["member"], target["path_id"]), (bundle["path"], member["name"], row["path_id"]))
    return result


def prepare(owner, inputs, output):
    """Derive graph, schemas, current field routes and retained relocation packs."""
    E = owner.module("bundle_endpoints")
    inputs, output = Path(inputs).resolve(strict=True), Path(output).resolve()
    pins = E.InputPins(inputs.parent, owner)
    pins.add(inputs)
    request = json.loads(inputs.read_bytes())
    if (
        set(request) != {"schema", "policy", "suppliers", "staged", "managed_inputs", "game_root", "codec"}
        or request["schema"] != "owner-bundle-preload-prepare-v1"
    ):
        raise ValueError("unsupported bundle preparation contract")
    policy = pins.read(request["policy"])
    required_keys = {"bundle", "member", "bindings", "asset_groups", "assets"}
    if not required_keys <= policy.keys() or set(policy) - required_keys - {"field_routes", "staged_bindings", "canonical"}:
        raise ValueError("unsupported bundle preparation policy")
    member = policy["bundle"], policy["member"]
    game = pins.path(request["game_root"])
    if output.is_relative_to(game) or game.is_relative_to(output):
        raise ValueError("preparation output must be separate from original input")
    pins.pin(request["codec"])
    suppliers, providers, profiles, source_files = {}, {}, {}, {}
    for supplier in request["suppliers"]:
        name = supplier["name"]
        if name in suppliers:
            raise ValueError("duplicate preparation supplier")
        paths = {key: pins.pin(supplier[key]) for key in ("profile", "receipt", "objects", "index", "types")}
        directory = paths["objects"].parent
        if any(paths[key] != directory / filename for key, filename in (("objects", "objects.bin"), ("index", "index.jsonl"), ("types", "types.json"))):
            raise ValueError("supplier files must retain their pack directory")
        receipt = json.loads(paths["receipt"].read_bytes())
        actual_receipt = directory / "result.json"
        if not actual_receipt.is_file():
            actual_receipt = directory.parent / "terminal.json"
        if paths["receipt"] != actual_receipt:
            raise ValueError("supplier receipt must belong to its pack")
        # Check this pack's own final table before interpreting any type_id.
        expected = receipt["outputs"]["types.json"]
        if any(supplier["types"][key] != expected[key] for key in ("bytes", "sha256")):
            raise ValueError("supplier final type table differs from receipt")
        types = json.loads(paths["types"].read_bytes())
        if not isinstance(types, list):
            raise ValueError("supplier final type table must be a list")
        logical = supplier.get("provider", str(directory))
        if logical in providers and providers[logical] != directory:
            raise ValueError("ambiguous supplier provider")
        providers[logical] = directory
        profiles[name] = original_identities(owner, paths["profile"], source_files)
        suppliers[name] = SimpleNamespace(paths=paths, types=types, provider=logical, profile_sha=owner.O.B.sha(paths["profile"]))
    producer = owner.ProducerRecords(providers)
    bindings, sources = {}, {}
    for row in policy["bindings"]:
        destination = tuple(row["destination"])
        if destination[:2] != member or destination in bindings or not destination[2]:
            raise ValueError("duplicate or foreign emitted destination")
        if row["supplier"] not in suppliers:
            raise ValueError("unknown binding supplier")
        candidates = profiles[row["supplier"]].get(tuple(row["record_source"]), set())
        source = tuple(row["source"]) if "source" in row else next(iter(candidates)) if len(candidates) == 1 else None
        if source is None or source not in candidates:
            raise ValueError("original body source absent or ambiguous")
        bindings[destination] = dict(row, source=list(source))
        sources.setdefault(source, set()).add(destination)
    for row in policy.get("staged_bindings", []):
        sources.setdefault(tuple(row["source"]), set()).add(tuple(row["destination"]))
    overrides = {}
    for row in policy.get("field_routes", []):
        key = tuple(row["owner"]), tuple(row["field"])
        if key in overrides:
            raise ValueError("duplicate exceptional field route")
        overrides[key] = row
    used, selected, types, routes, raw_records = set(), {}, {}, {}, {}
    output.mkdir(parents=True, exist_ok=False)

    def write(name, value, lines=False):
        path = output / name
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in value) if lines else json.dumps(value, sort_keys=True, indent=2) + "\n")
        return dict(path=str(path), bytes=path.stat().st_size, sha256=owner.O.B.sha(path))

    def layout(value):
        return {key: bytes.fromhex(item) if key in ("tree", "hash", "script_id") else item for key, item in value.items()}

    def descriptor(target, body, typ, **extra):
        full = owner.full_type_key(typ)
        types[full] = owner.O.json_layout(typ)
        return dict(
            destination=list(target),
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            class_id=typ["class_id"],
            native_type_hash=typ["hash"].hex(),
            schema=hashlib.sha256(typ["tree"]).hexdigest(),
            full_type=full,
            edges=[list(edge) for edge in sorted(set(owner.pointers(body, typ, {}).values()))],
            **extra,
        )

    with ExitStack() as stack:
        originals = {}

        def original(source):
            path, source_member, pid = source
            key = path, source_member
            if key not in originals:
                source_path = owner.O.M.safe_input(game, path)
                pins.add(source_path, dict(bytes=source_path.stat().st_size, sha256=source_files[path]))
                stream = stack.enter_context(owner.O.source_member(source_path, source_member))
                metadata = owner.O.W.read_serialized(stream)
                originals[key] = stream, metadata, {row["path_id"]: row for row in metadata["objects"]}
            stream, metadata, rows = originals[key]
            row = rows[pid]
            stream.seek(metadata["data_offset"] + row["offset"])
            return owner.O.B.exact(stream, row["bytes"]), metadata["types"][row["type_id"]], metadata

        staged_descriptors = {}
        staged = E.FinalMembers(owner, staged_descriptors, types)
        stack.callback(staged.close)
        staged.declare_member(*member)
        normalized_staged = []
        for row in request["staged"]:
            pin = dict(row["file"], path=str(pins.pin(row["file"])))
            normalized = dict(row, file=pin)
            for key in ("leaves", "full"):
                if key in row:
                    normalized[key] = dict(row[key], path=str(pins.pin(row[key])))
            if row["bundle"] == "sdk":
                leaves = pins.read(row["leaves"]) if "leaves" in row else []
                full = pins.read(row["full"]) if "full" in row else []
                for witness in leaves + full:
                    target = tuple(witness["destination"])
                    if target in staged_descriptors and staged_descriptors[target] != witness:
                        raise ValueError("conflicting staged SDK witness")
                    staged_descriptors[target] = witness
                    types[witness["full_type"]] = witness["type_layout"]
                    providers[witness["provider"]] = Path(pin["path"])
                staged.add_sdk(pin, row["member"], leaves)
                if full:
                    staged.qualify_sdk_full(row["member"], full, provider_paths=providers)
            else:
                staged.add(row["bundle"], pin)
            normalized_staged.append(normalized)

        def source_target(source, metadata, pointer):
            fid, pid = pointer
            if not 0 <= fid <= len(metadata["externals"]):
                raise ValueError("source pointer outside member table")
            target_member = source[1] if not fid else metadata["externals"][fid - 1]["path"]
            if target_member.startswith("archive:/"):
                target_member = target_member.rsplit("/", 1)[-1]
            candidates = {
                destination
                for identity, destinations in sources.items()
                if identity[1:] == (target_member, pid) and (fid or identity[0] == source[0])
                for destination in destinations
            }
            if len(candidates) != 1:
                raise ValueError("source endpoint absent or ambiguous: " + str((source, pointer)))
            return next(iter(candidates))

        def read(target):
            target = tuple(target)
            if target in raw_records:
                return raw_records[target]
            if target[:2] == member:
                if target not in bindings:
                    raise ValueError("required produced body absent")
                binding = bindings[target]
                supplier = suppliers[binding["supplier"]]
                _, index = producer.provider(producer.directory(supplier.provider))
                row = index[tuple(binding["record_source"])][0]
                if not isinstance(row["type_id"], int) or not 0 <= row["type_id"] < len(supplier.types):
                    raise ValueError("supplier record type outside final table")
                typ = layout(supplier.types[row["type_id"]])
                value = dict(provider=supplier.provider, record_source=binding["record_source"], record=supplier.profile_sha, sha256=row["sha256"])
                actual, body = producer.record(value)
                if actual != row:
                    raise ValueError("supplier record changed")
                value = descriptor(
                    target, body, typ, provider=supplier.provider, record_source=binding["record_source"], record=supplier.profile_sha, source=binding["source"]
                )
                if "resource" in row:
                    value["resource"] = row["resource"]
                original(binding["source"])
            else:
                if target in staged_descriptors:
                    value, body, typ = staged.record(target)
                else:
                    source_member, typ, body = staged.members.record(target[1], (0, target[2]))
                    if source_member != target[1] or staged.member_bundles[source_member] != target[0]:
                        raise ValueError("staged endpoint owner differs")
                    value = descriptor(target, body, typ)
            raw_records[target] = value, body, typ
            return value, body, typ

        pending = []
        for group in policy["asset_groups"]:
            pending.extend((*member, pid) for pid in group["roots"])
            pending.extend(tuple(target) for target in group.get("preload_roots", []))
        while pending:
            target = pending.pop()
            if target in selected:
                continue
            value, body, typ = read(target)
            selected[target] = value
            fields = owner.pointers(body, typ, {})
            edges = []
            for field, pointer in sorted(fields.items()):
                if not pointer[1]:
                    continue
                key = target, field
                if key in overrides:
                    override = overrides[key]
                    if list(pointer) != override["pointer"]:
                        raise ValueError("exceptional field route pointer differs")
                    endpoint = tuple(override["target"])
                    used.add(key)
                elif target[:2] == member:
                    namespace = bindings[target].get("pointer_namespace")
                    if namespace is not None:
                        fid, pid = pointer
                        if not 0 <= fid < len(namespace):
                            raise ValueError("produced pointer outside declared member table")
                        endpoint = (*namespace[fid], pid)
                    else:
                        source = value["source"]
                        _, _, metadata = original(source)
                        endpoint = source_target(source, metadata, pointer)
                else:
                    endpoint = staged.target(target[1], pointer)
                read(endpoint)
                edges.append(dict(field=list(field), pointer=list(pointer), target=list(endpoint)))
                pending.append(endpoint)
            routes[target] = edges
        if used != overrides.keys():
            raise ValueError("unused exceptional field route")
        externals = sorted({target[1] for target in selected if target[:2] != member})
        canonical = policy.get("canonical")
        if canonical is not None:
            canonical_profile = pins.read(canonical["profile"])
            pins.pin(canonical["bundle"])
            donor = canonical_profile["bundle"]
            externals = sorted(set(externals) | {donor["member"]})
        # Persist one retained pack per supplier; record keys and lineage remain
        # unchanged even when unrelated sources share the same numeric path ID.
        retained = {}
        for target in sorted(selected):
            if target[:2] != member:
                continue
            value, body, typ = raw_records[target]
            supplier_name = bindings[target]["supplier"]
            pack = retained.setdefault(supplier_name, dict(blob=bytearray(), rows=[], witnesses=[], types=[]))
            targets = {tuple(edge["field"]): tuple(edge["target"]) for edge in routes[target]}
            revised = owner.relocate_pointer_fields(value, body, typ, targets, externals)
            # ProducerRecords uses the same record key throughout the lineage.
            if any(tuple(row[key] for key in ("bundle", "member", "path_id")) == tuple(value["record_source"]) for row in pack["rows"]):
                raise ValueError("one supplier record maps to multiple emitted bodies")
            prior, _ = producer.record(value)
            row = dict(
                prior,
                offset=len(pack["blob"]),
                bytes=len(revised),
                sha256=hashlib.sha256(revised).hexdigest(),
                provider_before=value["provider"],
                body_before_sha256=value["sha256"],
                type_id=len(pack["types"]),
            )
            pack["blob"].extend(revised)
            pack["rows"].append(row)
            pack["types"].append(owner.O.json_layout(typ))
            pack["witnesses"].append(dict(destination=list(target), source=value["source"], fields=routes[target]))
            selected[target] = descriptor(target, revised, typ, **{key: value[key] for key in ("provider", "record_source", "record", "source")})
            if "resource" in value:
                selected[target]["resource"] = value["resource"]
            selected[target]["provider"] = str(output / ("retained-" + str(list(suppliers).index(supplier_name))))
            fields = owner.pointers(revised, typ, {})
            routes[target] = [dict(edge, pointer=list(fields[tuple(edge["field"])])) for edge in routes[target]]
        for name, pack in retained.items():
            directory = output / ("retained-" + str(list(suppliers).index(name)))
            directory.mkdir()
            (directory / "objects.bin").write_bytes(pack["blob"])
            for filename, rows in (("index.jsonl", pack["rows"]), ("witnesses.jsonl", pack["witnesses"])):
                (directory / filename).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            (directory / "types.json").write_text(json.dumps(pack["types"], sort_keys=True) + "\n")
            source_resource = suppliers[name].paths["objects"].parent / "resources.bin"
            if source_resource.is_file():
                (directory / "resources.bin").symlink_to(pins.add(source_resource))
            receipt = dict(
                success=True,
                **{
                    key + "_sha256": owner.O.B.sha(directory / filename)
                    for key, filename in (("index", "index.jsonl"), ("objects", "objects.bin"), ("witnesses", "witnesses.jsonl"))
                },
                outputs={"types.json": dict(bytes=(directory / "types.json").stat().st_size, sha256=owner.O.B.sha(directory / "types.json"))},
            )
            (directory / "result.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
        # Every lineage file actually read is part of preparation's retained pin set.
        for directory in producer.pins:
            directory = Path(directory)
            receipt = directory / "result.json"
            pins.add(receipt if receipt.is_file() else directory.parent / "terminal.json")
            for filename in ("index.jsonl", "objects.bin", "witnesses.jsonl", "types.json", "resources.bin"):
                if (directory / filename).is_file():
                    pins.add(directory / filename)
        original_properties, null_sources = {}, []
        for target, value in selected.items():
            if target[:2] != member or value["class_id"] != 114:
                continue
            source = value["source"]
            body, original_type, metadata = original(source)
            fields = owner.pointers(body, original_type, {})
            script = fields.get(("m_Script",), fields.get(("#490",)))
            if script == (0, 0):
                null_sources.append(
                    dict(
                        destination=list(target),
                        type_source=dict(
                            bundle=source[0],
                            member=source[1],
                            path_id=source[2],
                            bundle_sha256=owner.O.B.sha(game / source[0]),
                            sha256=hashlib.sha256(body).hexdigest(),
                        ),
                    )
                )
            elif script is not None:
                fid, pid = script
                script_member = source[1] if not fid else metadata["externals"][fid - 1]["path"].rsplit("/", 1)[-1]
                script_sources = {identity[:2] for identity in sources if identity[1] == script_member}
                if not fid:
                    script_sources = {tuple(source[:2])}
                if len(script_sources) != 1:
                    raise ValueError("original MonoScript member absent or ambiguous")
                raw, script_type, _ = original((*next(iter(script_sources)), pid))
                identity_owner = owner.O.module("_prepare_script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py")
                properties = owner.O.original_script_properties(raw, script_type, original_type, original_type, identity_owner).hex()
                identity = tuple(owner.O.script_fields(raw)[1][::-1])
                if identity in original_properties and original_properties[identity] != properties:
                    raise ValueError("conflicting original script properties")
                original_properties[identity] = properties
        graph = {
            "done.json": write("done.json", dict(success=True, blocks=0)),
            "selected-records.jsonl": write("selected-records.jsonl", [selected[key] for key in sorted(selected) if key[:2] == member], True),
        }
        required = dict(
            name=member[0],
            member=member[1],
            path_ids=sorted(key[2] for key in selected if key[:2] == member),
            externals=externals,
            dependencies=sorted({key[0] for key in selected if key[:2] != member and key[0] != "sdk"} | ({donor["name"]} if canonical else set())),
            asset_groups=policy["asset_groups"],
            assets=policy["assets"],
        )
        managed = dict(request["managed_inputs"])
        for key, pin in managed.items():
            managed[key] = dict(pin, path=str(pins.pin(pin)))
        managed["original_script_properties"] = write(
            "original-script-properties.json", [dict(identity=list(key), properties=value) for key, value in sorted(original_properties.items())]
        )
        prepared = dict(
            schema="owner-bundle-preload-inputs-v1",
            graph=graph,
            schemas=[write("schemas.json", types)],
            required=write("required.json", required),
            routes=write("routes.jsonl", [dict(owner=list(key), edges=routes[key]) for key in sorted(routes) if key[:2] == member], True),
            endpoints=write("endpoints.jsonl", [selected[key] for key in sorted(selected) if key[:2] != member], True),
            staged=normalized_staged,
            managed_inputs=managed,
            game_root=str(game),
            codec=dict(request["codec"], path=str(pins.pin(request["codec"]))),
            bundle=member[0],
            member=member[1],
            provider_paths=write("provider-paths.json", {key: str(value) for key, value in providers.items()}),
            null_script_sources=null_sources,
        )
        if canonical:
            donor_sources = original_identities(owner, pins.pin(canonical["profile"]))
            aliases = []
            for pair in canonical["pairs"]:
                duplicate, endpoint = tuple(pair["duplicate"]), tuple(pair["canonical"])
                value = selected[duplicate]
                if set(donor_sources.get(endpoint, ())) != {tuple(value["source"])}:
                    raise ValueError("canonical donor original body identity differs")
                if endpoint[:2] != (donor["name"], donor["member"]):
                    raise ValueError("canonical endpoint belongs to a different donor")
                aliases.append(
                    dict(
                        duplicate=list(duplicate),
                        canonical=list(endpoint),
                        source=value["source"],
                        duplicate_body_sha256=value["sha256"],
                        duplicate_class_id=value["class_id"],
                        duplicate_full_type=value["full_type"],
                    )
                )
            prepared["canonical"] = dict(
                aliases=write("canonical-aliases.json", aliases),
                profile=dict(canonical["profile"], path=str(pins.pin(canonical["profile"]))),
                bundle=dict(canonical["bundle"], path=str(pins.pin(canonical["bundle"]))),
            )
        pins.check()
        result = dict(
            success=True,
            request=write("inputs.json", prepared),
            records=len(required["path_ids"]),
            endpoints=len(selected) - len(required["path_ids"]),
            input_pins={str(path): pin for path, pin in pins.files.items()},
            typed_load_accepted=False,
            device_accepted=False,
        )
        write("result.json", result)
        return result
