"""Caller adapters for actual staged members; no source/ID fallback.

Shared qualification owner extracted from J1394/J1395. EditorKit 4128710f EntryLookup's type
and component restrictions inform the typed endpoint boundary. Input
descriptors MUST already qualify final bytes (including resource repacks).
This reader cannot turn discovery rows into endpoint admission.
"""

import hashlib
import importlib.util
import json
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("endpoint_script_identity", Path(__file__).resolve().parents[3] / "scripts/lab/script_identity.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


def managed_production(pins, provider_pin, receipt_pin):
    """Use the registry owner's common produced/refresh admission contract."""
    return SCRIPT.managed_providers(pins, provider_pin, receipt_pin)


def generate_managed(request_path, output):
    """Build current CLR witnesses with the existing metadata-only Cecil reader."""
    import shutil
    import subprocess
    import time

    import bundle_preload as owner

    request_path, output = Path(request_path).resolve(), Path(output).resolve()
    request = json.loads(request_path.read_bytes())
    pins = InputPins(request_path.parent, owner)
    if "input_paths" in request:
        pins.relocate(request["input_paths"])
    providers = managed_production(pins, request["managed_providers"], request["managed_receipt"])
    provider_base = pins.pin(request["managed_providers"]).parent
    providers = {name: dict(value, path=str(pins.path(value["path"], provider_base))) for name, value in providers.items()}
    for value in providers.values():
        path = Path(value["path"])
        pins.add(path, dict(bytes=path.stat().st_size, sha256=value["sha256"]))
    registry = pins.read(request["registry_receipt"])
    if registry.get("success") is not True:
        raise ValueError("final player registry production unsuccessful")
    registry_base = pins.pin(request["registry_receipt"]).parent
    aliases = pins.read(request["provider_aliases"]) if "provider_aliases" in request else {}
    alias_base = pins.pin(request["provider_aliases"]).parent if "provider_aliases" in request else registry_base
    aliases = {name: str(pins.add(pins.path(aliases.get(name, name), alias_base), pin)) for name, pin in registry["provider_pins"].items()}
    tools = request["tools"]
    launcher, compiler, cecil, runtimeconfig = (pins.pin(tools[key]) for key in ("dotnet", "compiler", "cecil", "runtimeconfig"))
    references = [pins.pin(row) for row in tools["references"]]
    source = pins.add(Path(__file__).resolve().parents[3] / "tools/phone-build/metadata/Program.cs")
    if any(path.is_relative_to(output) for path in pins.files):
        raise ValueError("managed witness output overlaps inputs")
    output.mkdir(parents=True, exist_ok=False)
    result = dict(success=False, executes_inputs=False)
    started = time.monotonic()

    def write(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n")

    def execute(command, label):
        with (output / (label + ".log")).open("xb") as log:
            subprocess.run(list(map(str, command)), cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

    try:
        tool = output / "MetadataInventory.dll"
        imports = output / "GlobalUsings.cs"
        imports.write_text("".join("global using global::" + name + ";\n" for name in ("System", "System.Collections.Generic", "System.IO", "System.Linq")))
        execute(
            [
                launcher,
                "exec",
                compiler,
                "-noconfig",
                "-nostdlib+",
                "-langversion:latest",
                "-deterministic+",
                "-nullable:enable",
                "-target:exe",
                "-out:" + str(tool),
                "-r:" + str(cecil),
                *("-r:" + str(path) for path in references),
                source,
                imports,
            ],
            "metadata-compile",
        )
        shutil.copyfile(cecil, output / "Mono.Cecil.dll")
        shutil.copyfile(runtimeconfig, output / "MetadataInventory.runtimeconfig.json")
        write("metadata-inputs.json", dict(assemblies=[dict(group="current", path=value["path"]) for value in providers.values()]))
        execute([launcher, "exec", tool, output / "metadata-inputs.json", output / "metadata.json"], "metadata-inspect")
        write("providers.json", providers)
        write("runtime-request.json", dict(managed=providers))
        write("provider-aliases.json", aliases)
        current_providers(
            owner,
            pins,
            {
                key: dict(path=str(output / name), bytes=(output / name).stat().st_size, sha256=owner.O.B.sha(output / name))
                for key, name in (("runtime_request", "runtime-request.json"), ("managed_providers", "providers.json"), ("metadata", "metadata.json"))
            },
        )
        pins.check()
        result.update(success=True, managed_providers=len(providers), provider_aliases=len(aliases))
    finally:
        result.update(
            elapsed_seconds=time.monotonic() - started, input_pins={str(path): pin for path, pin in pins.files.items() if not path.is_relative_to(output)}
        )
        write("result.json", result)
    return result


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


_graph_schemas = {}


def _graph_fields(task):
    """CPU worker: inspect immutable bytes only, never inherited seek handles."""
    import bundle_preload

    value, raw, typ = task
    return [[list(field), list(pointer)] for field, pointer in bundle_preload.checked_fields(value, raw, typ, _graph_schemas).items()]


def audit_graph(
    owner,
    roots,
    read_record,
    member_tables,
    *,
    structural_routes,
    managed_check,
    cache_directory,
    cache_inputs,
    managed_context,
    workers=1,
):
    """Walk current roots, reusing body/schema proofs and current managed checks.

    Actual record readers still admit current provider lineage and return actual
    bytes on each run. Cached fields bind those bytes and the complete native
    type. Adjacency is rebuilt from current routes/member tables; reciprocal
    checks always inspect current neighbors. Managed proofs separately bind
    the caller's complete CLR/SDK policy and every endpoint the checker read.
    The caller must enumerate every input/code file consumed by its callbacks.
    This pre-emission audit never replaces final persisted-file qualification.
    """
    from collections import Counter, deque
    from concurrent.futures import ProcessPoolExecutor
    from contextlib import ExitStack
    import importlib
    from itertools import islice
    import multiprocessing
    import resource
    import sys
    import time
    import traceback

    started = time.monotonic()
    paths = {Path(path).resolve() for path in cache_inputs}
    paths.update(Path(__file__).parent.glob("*.py"))

    def pins():
        return {str(path): owner.O.B.sha(path) for path in sorted(paths)}

    before = pins()
    code = owner.EmissionCache.key({path: sha for path, sha in before.items() if Path(path).parent == Path(__file__).parent})
    context = owner.EmissionCache.key(managed_context)
    roots = list(dict.fromkeys(map(tuple, roots)))
    summaries, pending, scheduled, seen = {}, deque(roots), set(roots), set()
    classes, blocked, reciprocal = Counter(), [], 0
    type_keys = {}
    table_cache = {}
    with ExitStack() as stack:
        cache = owner.EmissionCache(cache_directory)
        stack.callback(cache.close)
        pool = None
        if workers > 1:
            # CLI only. Workers receive bytes and never touch readers or SQLite.
            # Fork avoids executing a caller's top-level pipeline as __main__.
            sys.path.insert(0, str(Path(__file__).parent))
            worker = importlib.import_module("bundle_endpoints")._graph_fields
            pool = stack.enter_context(ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")))

        def prepare(key):
            value, raw, typ = read_record(key)
            if tuple(value["destination"]) != key:
                raise ValueError("Graph endpoint identity differs")
            # Hash actual bytes even on a hit. Neither a descriptor nor a
            # provider's changed aggregate pin can stand in for this read.
            native = tuple(sorted((name, tuple(item) if isinstance(item, list) else item) for name, item in typ.items()))
            if native not in type_keys:
                type_keys[native] = owner.full_type_key(typ)
            proof = cache.key(
                dict(
                    body=digest(raw),
                    size=len(raw),
                    native=type_keys[native],
                    code=code,
                    expected={name: value[name] for name in ("bytes", "sha256", "full_type", "schema", "class_id", "native_type_hash", "edges")},
                )
            )
            saved = cache.get("graph_fields", proof)
            return value, raw, typ, proof, json.loads(saved) if saved is not None else None

        def install(key, task, fields):
            value, raw, typ, proof, saved = task
            if saved is None:
                cache.put("graph_fields", proof, json.dumps(fields, separators=(",", ":")).encode())
            fields = {tuple(field): tuple(pointer) for field, pointer in fields}
            routes = structural_routes.get(key)
            adjacency = {}
            if routes is not None:
                nonnull = {field: pointer for field, pointer in fields.items() if pointer[1]}
                for row in routes:
                    field, pointer, target = tuple(row["field"]), tuple(row["pointer"]), tuple(row["target"])
                    if field in adjacency or nonnull.get(field) != pointer or len(target) != 3 or target[2] != pointer[1]:
                        raise ValueError("Graph structural route differs")
                    if not pointer[0] and target != (*key[:2], pointer[1]):
                        raise ValueError("Graph local route changes member")
                    adjacency[field] = target
                if set(adjacency) != set(nonnull):
                    raise ValueError("Graph structural routes incomplete")
            else:
                if key[:2] not in table_cache:
                    table_cache[key[:2]] = member_tables(value)
                tables = table_cache[key[:2]]
                for field, (fid, pid) in fields.items():
                    if not pid:
                        continue
                    if not 0 <= fid <= len(tables):
                        raise ValueError("Graph file ID outside actual member table")
                    adjacency[field] = (*(tables[fid - 1] if fid else key[:2]), pid)
            signature = cache.key(
                dict(
                    proof=proof,
                    adjacency=sorted((list(f), t) for f, t in adjacency.items()),
                    destination=key,
                    script_identity=value.get("current_registry_identity") if typ["class_id"] == 115 else None,
                )
            )
            summaries[key] = dict(signature=signature, fields=fields, adjacency=adjacency, class_id=typ["class_id"])

        def summary(key):
            key = tuple(key)
            if key not in summaries:
                task = prepare(key)
                install(key, task, task[4] if task[4] is not None else _graph_fields(task[:3]))
            return summaries[key]

        def managed(key, item):
            value, raw, typ = read_record(key)

            def managed_key():
                return cache.key(
                    dict(
                        record=item["signature"],
                        context=context,
                        code=code,
                        identity=value.get("current_registry_identity"),
                        source=value.get("source"),
                        policies=value.get("policies"),
                    )
                )

            proof = managed_key()
            saved = cache.get("graph_managed", proof)
            if saved is not None:
                deps = json.loads(saved)
                if all(summary(tuple(target))["signature"] == signature for target, signature in deps):
                    return
            dependencies = {}

            def endpoint(target):
                target = tuple(target)
                dependencies[target] = summary(target)["signature"]
                return read_record(target)

            managed_check(value, raw, typ, endpoint)
            saved = json.dumps(sorted((list(k), v) for k, v in dependencies.items())).encode()
            cache.put("graph_managed", proof, saved)
            cache.put("graph_managed", managed_key(), saved)

        while pending:
            batch = []
            for key in islice(pending, 256):
                if key in summaries:
                    continue
                try:
                    batch.append((key, prepare(key)))
                except Exception:
                    # Preserve the ordinary ordered per-node failure below.
                    continue
            misses = [(key, task) for key, task in batch if task[4] is None]
            if pool is not None and misses:
                futures = [(key, task, pool.submit(worker, task[:3])) for key, task in misses]
                for key, task, future in futures:
                    try:
                        install(key, task, future.result())
                    except Exception:
                        pass  # The serial path records the exact first failure.
            else:
                for key, task in misses:
                    try:
                        install(key, task, _graph_fields(task[:3]))
                    except Exception:
                        pass
            for key, task in batch:
                if task[4] is not None:
                    try:
                        install(key, task, task[4])
                    except Exception:
                        pass
            count = min(256, len(pending))
            for _ in range(count):
                key = pending.popleft()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    item = summary(key)
                    classes[item["class_id"]] += 1
                    if item["class_id"] == 114:
                        managed(key, item)
                    for target in item["adjacency"].values():
                        if target not in scheduled:
                            scheduled.add(target)
                            pending.append(target)
                    if item["class_id"] == 1:
                        for field in item["fields"]:
                            target = item["adjacency"].get(field)
                            if target is None:
                                raise ValueError("null GameObject component")
                            child = summary(target)
                            if child["adjacency"].get(("m_GameObject",), child["adjacency"].get(("#374",))) != key:
                                raise ValueError("nonreciprocal component " + str(target))
                            reciprocal += 1
                    elif item["class_id"] in (4, 224):
                        parent = item["adjacency"].get(("m_Father",))
                        if parent is not None and key not in {
                            target for field, target in summary(parent)["adjacency"].items() if field and field[0] in ("m_Children", "#83")
                        }:
                            raise ValueError("Transform parent omits child")
                        for field, target in item["adjacency"].items():
                            if field and field[0] in ("m_Children", "#83") and summary(target)["adjacency"].get(("m_Father",)) != key:
                                raise ValueError("Transform child has different parent")
                except Exception:
                    blocked.append(dict(destination=list(key), error=traceback.format_exc()))
        if pins() != before:
            raise ValueError("Graph audit input changed during validation")
        return dict(
            visited=len(seen),
            classes=dict(classes),
            reciprocal_components=reciprocal,
            blocked=blocked,
            cache=dict(cache.counts),
            seconds=time.monotonic() - started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
            workers=workers,
        )


class FinalMembers:
    def __init__(self, owner, selected, qualified_types):
        self.P = owner
        self.C = owner.module("catalog_complete")
        self.members = self.C.ProducedMembers()
        self.selected = selected
        self.types = qualified_types
        self.member_bundles = {}
        self.pins = {}
        self.actual = {}
        self.aliases = {}
        self.sdk_leaves = {}
        self.sdk_full = {}
        self.member_pins = {}

    def add(self, bundle_name, pin, resource_member=None):
        path = Path(pin["path"])
        actual_pin = dict(bytes=path.stat().st_size, sha256=self.C.W.B.sha(path))
        if actual_pin != {k: pin[k] for k in actual_pin}:
            raise ValueError("staged file pin differs: " + str(path))
        self.pins[str(path)] = actual_pin
        if resource_member is not None:
            stream = path.open("rb")
            stream.size = path.stat().st_size
            self._add_member(bundle_name, resource_member, stream)
        else:
            bundle = self.C.W.B.Bundle(path)
            for member in bundle.members:
                if not member.endswith((".resS", ".resource")):
                    self._add_member(bundle_name, member, bundle.member(member))

    def _add_member(self, bundle, member, stream):
        if member in self.members.members:
            raise ValueError("actual member belongs to multiple bundles: " + member)
        self.declare_member(bundle, member)
        self.members.add(member, stream, bundle)

    def declare_member(self, bundle, member):
        # Whole-game is read through its retained/final extent reader. Its
        # identity must still resolve in an external staged member's table.
        if self.member_bundles.setdefault(member, bundle) != bundle:
            raise ValueError("serialized member owner differs: " + member)
        for alias in (member, member.rsplit("/", 1)[-1]):
            if self.aliases.setdefault(alias, member) != member:
                raise ValueError("actual serialized member alias ambiguous: " + alias)

    def add_sdk(self, pin, canonical_member, leaf_witnesses=()):
        # These witnesses come from sdk_serialized_leaves_v2's original/Android
        # body/native/full-layout/empty-PPtr proof, not from a missing type tree.
        self.add("sdk", pin, resource_member=canonical_member)
        self.member_pins[canonical_member] = pin
        for witness in leaf_witnesses:
            key = tuple(witness["destination"])
            if (
                key[:2] != ("sdk", canonical_member)
                or witness["provider_file_sha256"] != pin["sha256"]
                or witness["provider_kind"] != "serialized_file"
                or witness["class_id"] != 43
                or witness["edges"]
            ):
                raise ValueError("SDK leaf witness differs from actual resource pin")
            if self.selected[key] != witness:
                raise ValueError("SDK leaf descriptor differs from qualified witness")
            self.sdk_leaves[key] = witness

    def qualify_sdk_full(self, canonical_member, witnesses, *, provider_paths=None):
        """Admit exact full-resource descriptors, independently of leaf proofs.

        The caller supplies source-qualified descriptors and full layouts.
        This only restores an absent tree after every other native metadata
        field matches. Actual extent, complete fields and recursive targets
        are checked by record/target, never inferred from a path ID.
        """
        pin = self.member_pins[canonical_member]
        for witness in witnesses:
            key = tuple(witness["destination"])
            if (
                key[:2] != ("sdk", canonical_member)
                or witness["provider_file_sha256"] != pin["sha256"]
                or witness["provider_kind"] != "serialized_file"
                or Path((provider_paths or {}).get(witness["provider"], witness["provider"])).resolve() != Path(pin["path"]).resolve()
                or self.selected[key] != witness
                or witness["type_layout"] != self.types[witness["full_type"]]
            ):
                raise ValueError("SDK full witness differs from actual resource pin")
            self.sdk_full[key] = witness

    def target(self, member, pointer):
        member = self.aliases.get(member, member)
        fid, pid = pointer
        layout = self.members.members[member][1]
        if not 0 <= fid <= len(layout["externals"]) or not pid:
            raise ValueError("actual file ID outside serialized member table")
        if fid:
            alias = layout["externals"][fid - 1]["path"].rsplit("/", 1)[-1]
            member = self.aliases[alias]
        if member in self.members.members and pid not in self.members.members[member][2]:
            raise ValueError("actual serialized endpoint absent")
        return self.member_bundles[member], member, pid

    def member_tables(self, value):
        member = value["destination"][1]
        layout = self.members.members[member][1]
        result = []
        for external in layout["externals"]:
            alias = external["path"].rsplit("/", 1)[-1]
            resolved = self.aliases[alias]
            result.append((self.member_bundles[resolved], resolved))
        return result

    def record(self, target):
        target = tuple(target)
        bundle, member, pid = target
        if self.member_bundles.get(member) != bundle:
            raise ValueError("explicit staged member/bundle identity differs")
        descriptor = self.selected[target]
        _, typ, raw = self.members.record(member, (0, pid))
        layout = self.members.members[member][1]
        full = self.types[descriptor["full_type"]]
        qualified = dict(full)
        for field in ("tree", "hash", "script_id"):
            if field in qualified:
                qualified[field] = bytes.fromhex(qualified[field])
        if not typ.get("tree") and target in self.sdk_full:
            witness = self.sdk_full[target]
            # The serialized-v22 trees flag gates both tree bytes and the
            # dependency vector (unity_write.read_serialized). Only an empty
            # qualified vector may be recovered from this tree-free resource.
            if layout["trees"] or "dependencies" in typ or qualified.get("dependencies") != []:
                raise ValueError("SDK full missing-tree dependency metadata differs")
            restored = dict(typ, tree=qualified["tree"], dependencies=[])
            if witness["type_layout"] != full or self.P.full_type_key(restored) != descriptor["full_type"]:
                raise ValueError("actual typetree-free SDK full metadata differs")
            typ = restored
        elif not typ.get("tree") and target in self.sdk_leaves:
            witness = self.sdk_leaves[target]
            if (
                typ["class_id"] != 43
                or typ["hash"] != qualified["hash"]
                or qualified["class_id"] != 43
                or witness["type_layout"] != full
                or self.P.full_type_key(qualified) != descriptor["full_type"]
                or self.P.pointers(raw, qualified, {})
            ):
                raise ValueError("actual typetree-free SDK leaf differs from source proof")
            typ = qualified
        else:
            typ = self.P.qualified_final_type(raw, typ, layout["scripts"], qualified)
        if (
            (len(raw), digest(raw)) != (descriptor["bytes"], descriptor["sha256"])
            or typ["class_id"] != descriptor["class_id"]
            or typ["hash"].hex() != descriptor["native_type_hash"]
            or digest(typ["tree"]) != descriptor["schema"]
            or set(self.P.pointers(raw, typ, {}).values()) != set(map(tuple, descriptor["edges"]))
        ):
            raise ValueError("actual staged endpoint differs from qualified descriptor")
        self.actual[target] = descriptor["sha256"]
        return descriptor, raw, typ

    def check_pins(self):
        for path, pin in self.pins.items():
            path = Path(path)
            if (path.stat().st_size, self.C.W.B.sha(path)) != (
                pin["bytes"],
                pin["sha256"],
            ):
                raise ValueError("staged input changed during emission")

    def close(self):
        for stream, _, _ in self.members.members.values():
            close = getattr(stream, "close", None)
            if close:
                close()


def managed_checker(
    owner,
    identity_owner,
    current,
    normalizer,
    sdk_tree,
    member_tables,
    registry_scripts,
    original_script_properties,
    null_script_source_type=None,
):
    """Check actual script readback before AND after final file allocation.

    member_tables(value) returns the actual ordered external-member identities
    for this body. The emitter member uses required.externals; staged members
    use their own persisted metadata, never a synthetic scene table.
    """

    properties_cache = {}

    def check(value, raw, typ, read_record):
        fields = owner.pointers(raw, typ, {})
        scripts = [p for field, p in fields.items() if field in (("m_Script",), ("#490",))]
        if scripts == [(0, 0)] and null_script_source_type is not None:
            owner.qualify_null_script_base(raw, typ, null_script_source_type(value))
            return None
        if len(scripts) != 1 or not scripts[0][1]:
            raise ValueError("actual managed script field absent or ambiguous")
        fid, pid = scripts[0]
        member = tuple(value["destination"][:2])
        if fid:
            externals = member_tables(value)
            if not 1 <= fid <= len(externals):
                raise ValueError("actual script file ID outside member table")
            member = tuple(externals[fid - 1])
        script_value, script_raw, script_type = read_record((*member, pid))
        if script_type["class_id"] != 115:
            raise ValueError("actual m_Script is not MonoScript")
        offset, (name, namespace, assembly) = owner.O.script_fields(script_raw)
        identity = assembly, namespace, name
        if tuple(value["current_registry_identity"]) != identity:
            raise ValueError("actual managed/current registry identity differs")
        if tuple(script_value["current_registry_identity"]) != identity:
            raise ValueError("actual MonoScript/current registry identity differs")
        if typ["script_id"] != identity_owner.md4((name + namespace + assembly).encode()):
            raise ValueError("actual managed serialized script ID differs")
        clr = current[identity]
        properties = script_raw[offset : offset + 16].hex()
        expected_script, _ = registry_scripts[identity]
        if script_raw != expected_script:
            raise ValueError("actual MonoScript differs from pinned current registry")
        if clr.get("unsupported"):
            if not clr.get("unchanged_provider_sha256") or typ["tree"].hex() not in clr["source_trees"]:
                raise ValueError("unsupported current CLR lacks unchanged provider/source tree")
            if properties != original_script_properties[identity]:
                raise ValueError("unsupported current CLR original script properties differ")
        else:
            schema_key = identity, typ["tree"]
            if schema_key not in properties_cache:
                nodes = identity_owner._tree(normalizer.editor_curves(identity_owner.tree_nodes(typ["tree"])))
                properties_cache[schema_key] = identity_owner.properties_hash(name, namespace, assembly, nodes, sdk_tree).hex()
            computed = properties_cache[schema_key]
            if computed != clr["properties"] or properties != computed:
                raise ValueError("actual managed schema differs from current CLR")
        if typ["hash"].hex() != properties:
            raise ValueError("actual managed native hash differs from MonoScript")
        return identity

    return check


class EndpointRecords:
    """One explicit owner boundary, swapped to actual whole-game after emission.

    Producer descriptor/extent reconciliation stays the retained reader's job.
    Staged descriptors must already bind resource repack/relocation receipts.
    """

    def __init__(self, member, retained_record, staged, check_managed):
        from collections import OrderedDict

        self.member = tuple(member)
        self.local_record = retained_record
        self.staged = staged
        self.check_managed = check_managed
        self.checked_external_managed = set()
        self.records = OrderedDict()

    def record(self, target):
        """Read one immutable input epoch; final readback starts a fresh epoch."""
        target = tuple(target)
        if target[:2] == self.member:
            return self.local_record(target)
        if target not in self.records:
            self.records[target] = self.staged.record(target)
            if len(self.records) > 256:
                self.records.popitem(last=False)
        self.records.move_to_end(target)
        return self.records[target]

    def __call__(self, target):
        target = tuple(target)
        if target[:2] == self.member:
            return self.local_record(target)
        value, body, typ = self.record(target)
        if typ["class_id"] == 114 and target not in self.checked_external_managed:
            self.check_managed(value, body, typ, self)
            self.checked_external_managed.add(target)
        return value, body, typ

    def check_final(self, final_local_record):
        # External MonoBehaviours may refer to a script in whole-game. Recheck
        # against its final persisted bytes after the emitter installs the file.
        self.local_record = final_local_record
        targets = sorted(self.checked_external_managed)
        self.checked_external_managed.clear()
        self.records.clear()
        for target in targets:
            self(target)
        self.staged.check_pins()


class InputPins:
    """Resolve request-relative files and retain the complete checker input set."""

    def __init__(self, base, owner):
        self.base, self.owner, self.files = Path(base), owner, {}
        self.paths = {}

    def relocate(self, value):
        mapping = self.read(value)
        base = self.pin(value).parent
        self.paths = {str(Path(name)): (Path(target) if Path(target).is_absolute() else base / target) for name, target in mapping.items()}

    def path(self, name, base=None):
        path = Path(name)
        path = path if path.is_absolute() else (base or self.base) / path
        return self.paths.get(str(path), path).resolve(strict=True)

    def add(self, path, expected=None):
        path = self.path(path)
        actual = dict(bytes=path.stat().st_size, sha256=self.owner.O.B.sha(path))
        if expected is not None and any(actual[key] != expected[key] for key in actual):
            raise ValueError("bundle qualification input differs: " + str(path))
        if path in self.files and self.files[path] != actual:
            raise ValueError("bundle qualification input changed: " + str(path))
        self.files[path] = actual
        return path

    def pin(self, value):
        if set(value) != {"path", "bytes", "sha256"}:
            raise ValueError("bundle qualification requires an explicit file pin")
        return self.add(value["path"], value)

    def read(self, value):
        return json.loads(self.pin(value).read_bytes())

    def check(self):
        for path, expected in list(self.files.items()):
            self.add(path, expected)


def current_providers(owner, pins, inputs):
    """Compare original bindings before resolving corresponding relative paths."""
    runtime = pins.read(inputs["runtime_request"])
    providers = pins.read(inputs["managed_providers"])
    if runtime["managed"] != providers:
        raise ValueError("Runtime managed provider differs")
    metadata = pins.read(inputs["metadata"])
    base = pins.pin(inputs["managed_providers"]).parent
    normalized = {}
    for name, value in providers.items():
        path = pins.path(value["path"], base)
        pins.add(path, dict(bytes=path.stat().st_size, sha256=value["sha256"]))
        normalized[name] = dict(value, path=str(path))
    for row in metadata["assemblies"]:
        if row["group"] == "current":
            value = providers[row["module_name"]]
            if (row["path"], row["sha256"]) != (value["path"], value["sha256"]):
                raise ValueError("Metadata provider path/hash differs")
            row["path"] = normalized[row["module_name"]]["path"]
    root = Path(__file__).resolve().parents[3]
    module = owner.O.module("_bundle_current_metadata", root / "scripts/lab/phone_managed_types.py")
    universe = module.MetadataUniverse(metadata, "current")
    universe.bind_current_providers(normalized)
    return universe


def managed_context(owner, pins, inputs):
    """Build the existing current-registry checker from explicit pinned inputs."""
    O = owner.O
    receipt = pins.read(inputs["registry_receipt"])
    aliases = pins.read(inputs["provider_aliases"])
    alias_base = pins.pin(inputs["provider_aliases"]).parent
    if receipt["success"] is not True:
        raise ValueError("Registry production unsuccessful")
    for name, value in receipt["provider_pins"].items():
        pins.add(pins.path(aliases.get(name, name), alias_base), value)
    schemas = pins.pin(inputs["registry_schemas"])
    if inputs["registry_schemas"]["sha256"] != receipt["schemas"]["sha256"]:
        raise ValueError("Registry schema receipt differs")
    current = {tuple(value["identity"]): value for value in json.loads(schemas.read_bytes())}
    registry = pins.pin(inputs["registry_body"])
    if any(inputs["registry_body"][key] != receipt["files"][registry.name][key] for key in ("bytes", "sha256")):
        raise ValueError("Registry body receipt differs")
    scripts = {}
    with registry.open("rb") as stream:
        stream.size = registry.stat().st_size
        metadata = O.W.read_serialized(stream)
        for row in metadata["objects"]:
            typ = metadata["types"][row["type_id"]]
            if typ["class_id"] == 115:
                stream.seek(metadata["data_offset"] + row["offset"])
                raw = O.B.exact(stream, row["bytes"])
                _, (name, namespace, assembly) = O.script_fields(raw)
                scripts[assembly, namespace, name] = raw, typ
    root = Path(__file__).resolve().parents[3]
    identity = O.module("_bundle_script_identity", root / "scripts/lab/script_identity.py")
    profile_path = pins.add(root / "recipe/owner-player-registry.json")
    profile = json.loads(profile_path.read_bytes())["script_properties_sdk"]
    sdk = pins.pin(inputs["properties_sdk"])
    if inputs["properties_sdk"]["sha256"] != profile["sha256"]:
        raise ValueError("Properties SDK differs from authored registry profile")
    with sdk.open("rb") as stream:
        stream.size = sdk.stat().st_size
        metadata = O.W.read_serialized(stream)
    typ = metadata["types"][next(row for row in metadata["objects"] if row["path_id"] == profile["path_id"])["type_id"]]
    curves = [nodes for layout in metadata["types"] if layout.get("tree") for nodes in identity._native_subtrees(layout["tree"], "AnimationCurve")]
    normalizer = identity._RegistryTypes.__new__(identity._RegistryTypes)
    normalizer.native_templates = {"AnimationCurve": next(nodes for nodes in curves if any(node["name"] == "tangentMode" for node in nodes))}
    original = {tuple(value["identity"]): value["properties"] for value in pins.read(inputs["original_script_properties"])}
    return dict(
        identity_owner=identity, current=current, normalizer=normalizer, sdk_tree=typ["tree"], registry_scripts=scripts, original_script_properties=original
    )


class Qualification:
    """Own staged streams and current managed endpoints for one bundle request."""

    def __init__(self, owner, pins, request, selected, types, required, *, provider_paths=None):
        self.owner, self.pins, self.request = owner, pins, request
        self.member = request["bundle"], request["member"]
        self.selected, self.types = selected, types
        self.required = required
        self.staged = FinalMembers(owner, selected, types)
        self.final = None
        self.producer = owner.ProducerRecords(provider_paths)
        self.external_members = []

    def setup(self):
        request, pins, owner = self.request, self.pins, self.owner
        self.staged.declare_member(*self.member)
        for row in request["staged"]:
            path = pins.pin(row["file"])
            pin = dict(row["file"], path=str(path))
            if row["bundle"] == "sdk":
                self.staged.add_sdk(pin, row["member"], pins.read(row["leaves"]) if "leaves" in row else ())
                if "full" in row:
                    self.staged.qualify_sdk_full(row["member"], pins.read(row["full"]), provider_paths=self.producer.provider_paths)
            else:
                self.staged.add(row["bundle"], pin)
        self.external_members = [
            (self.staged.member_bundles[self.staged.aliases[member]], self.staged.aliases[member]) for member in self.required["externals"]
        ]
        self.game = pins.path(request["game_root"])
        self.null_sources = {tuple(row["destination"]): row["type_source"] for row in request.get("null_script_sources", [])}
        # Null-script originals are included before an output cache lookup.
        for source in self.null_sources.values():
            path = owner.O.M.safe_input(self.game, source["bundle"])
            pins.add(path, dict(bytes=path.stat().st_size, sha256=source["bundle_sha256"]))
        if any(value["class_id"] == 114 for value in self.selected.values()):
            self.universe = current_providers(owner, pins, request["managed_inputs"])
            context = managed_context(owner, pins, request["managed_inputs"])
            self.baseline = managed_checker(owner, **context, member_tables=self.tables, null_script_source_type=self.null_source)
        self.endpoints = EndpointRecords(self.member, self.retained, self.staged, self.check)
        return self

    def typ(self, value):
        return {key: bytes.fromhex(item) if key in ("tree", "hash", "script_id") else item for key, item in self.types[value["full_type"]].items()}

    def retained(self, target):
        value = self.selected[tuple(target)]
        _, raw = self.producer.record(value)
        return value, raw, self.typ(value)

    def tables(self, value):
        return self.external_members if tuple(value["destination"][:2]) == self.member else self.staged.member_tables(value)

    def null_source(self, value):
        source = self.null_sources[tuple(value["destination"])]
        policy = value.get("policies", {}).get("missing_script_base")
        if policy and source != policy["type_source"]:
            raise ValueError("Null-script selector differs from explicit policy")
        if not policy and [source["bundle"], source["member"], source["path_id"]] != value["source"]:
            raise ValueError("Null-script selector differs from original owner")
        path = self.owner.O.M.safe_input(self.game, source["bundle"])
        with self.owner.O.source_member(path, source["member"]) as stream:
            metadata = self.owner.O.W.read_serialized(stream)
            row = next(row for row in metadata["objects"] if row["path_id"] == source["path_id"])
            stream.seek(metadata["data_offset"] + row["offset"])
            raw = self.owner.O.B.exact(stream, row["bytes"])
        if digest(raw) != source["sha256"]:
            raise ValueError("Null-script original body drift")
        return metadata["types"][row["type_id"]]

    def check(self, value, raw, typ, endpoint):
        fields = self.owner.pointers(raw, typ, {})
        script = fields.get(("m_Script",), fields.get(("#490",)))
        if script and script[1]:
            fid, pid = script
            member = tuple(value["destination"][:2])
            if fid:
                tables = self.tables(value)
                if not 1 <= fid <= len(tables):
                    raise ValueError("actual script file ID outside member table")
                member = tables[fid - 1]
            script_value, script_raw, _ = endpoint((*member, pid))
            _, (name, namespace, assembly) = self.owner.O.script_fields(script_raw)
            identity = [assembly, namespace, name]
            value.setdefault("current_registry_identity", identity)
            script_value.setdefault("current_registry_identity", identity)
            self.universe.registry(identity)
        return self.baseline(value, raw, typ, endpoint)

    def check_final(self, path):
        if self.final is not None:
            self.final.close()
        self.final = FinalMembers(self.owner, self.selected, self.types)
        self.final.add(self.member[0], dict(path=str(path), bytes=Path(path).stat().st_size, sha256=self.owner.O.B.sha(Path(path))))

        def persisted(target):
            value = self.selected[tuple(target)]
            _, typ, raw = self.final.members.record(self.member[1], (0, target[2]))
            typ = self.owner.qualified_final_type(raw, typ, self.final.members.members[self.member[1]][1]["scripts"], self.typ(value))
            return value, raw, typ

        # A complete-output cache hit skips the emitter's callbacks. Revisit
        # local and external managed bodies against the final script allocation.
        self.endpoints.local_record = persisted
        for pid in self.required["path_ids"]:
            target = (*self.member, pid)
            value = self.selected[target]
            if value["class_id"] == 114:
                value, raw, typ = persisted(target)
                self.check(value, raw, typ, self.endpoints)
        self.endpoints.check_final(persisted)
        self.pins.check()

    def close(self):
        self.staged.close()
        if self.final is not None:
            self.final.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate current provider/CLR witnesses without executing input assemblies")
    parser.add_argument("--managed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate_managed(args.managed, args.output)
