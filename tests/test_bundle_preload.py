"""Authored contracts for typed prefab dependency/group framing."""

import hashlib
from contextlib import nullcontext
import importlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace as Node
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"))
P = importlib.import_module("bundle_preload")


def node(name, kind="int", size=4, children=()):
    return Node(name=name, kind=kind, size=size, flags=0, meta=0, children=list(children))


def pointer(name):
    return node(name, "PPtr<Object>", 12, (node("m_FileID"), node("m_PathID", "SInt64", 8)))


class BundlePreloadTests(unittest.TestCase):
    def test_scriptless_base_requires_pinned_type_and_preserves_owner_pointer(self):
        M = P.module("bundle_manifest")
        nodes = [dict(type="MonoBehaviour", name="Base", size=-1, level=0, meta=0, flags=0, version=1)]
        for name, kind in (("m_GameObject", "GameObject"), ("m_Script", "MonoScript")):
            nodes.extend(
                dict(type=t, name=n, size=s, level=l, meta=0, flags=0, version=1)
                for t, n, s, l in ((f"PPtr<{kind}>", name, 12, 1), ("int", "m_FileID", 4, 2), ("SInt64", "m_PathID", 8, 2))
            )
        nodes.append(dict(type="SInt64", name="authoredTail", size=8, level=1, meta=0, flags=0, version=1))
        typ = dict(class_id=114, stripped=0, script_type=-1, script_id=bytes(16), hash=bytes(16), tree=M.S._tree(nodes), dependencies=[])
        body = struct.pack("<iqiqq", 1, 42, 0, 0, 0)
        fields = P.qualify_null_script_base(body, typ, typ)
        self.assertEqual(fields, {("m_GameObject",): (1, 42), ("m_Script",): (0, 0)})
        for field, value in (("class_id", 115), ("script_type", 0), ("hash", b"x" * 16), ("script_id", b"x" * 16)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "pinned original"):
                changed = {**typ, field: value}
                P.qualify_null_script_base(body, changed, changed)
        with self.assertRaisesRegex(ValueError, "pinned original"):
            P.qualify_null_script_base(body, typ, {**typ, "dependencies": [1]})
        with self.assertRaisesRegex(ValueError, "pinned original"):
            P.qualify_null_script_base(body[:-1], typ, typ)
        with self.assertRaisesRegex(ValueError, "one null script"):
            P.qualify_null_script_base(struct.pack("<iqiqq", 1, 42, 0, 7, 0), typ, typ)

    def test_retained_type_metadata_keeps_original_profile_and_immutable_extents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, types, values, _ = self.required_graph(root)
            source = next(iter(json.loads(types.read_text()).values()))
            before = {**source, "class_id": 114, "tree": bytes.fromhex(source["tree"]), "hash": bytes.fromhex(source["hash"])}
            current = {**before, "hash": b"n" * 16}
            value = {**values[0], "class_id": 114, "full_type": P.full_type_key(before)}
            original = Path(value["provider"])
            original_index = (original / "index.jsonl").read_bytes()
            original_body = (original / "objects.bin").read_bytes()
            seen = []

            def qualify(selected, body, typ):
                seen.append((selected, body, typ))
                return {"identity": ["assembly", "namespace", "script"], "properties": typ["hash"].hex()}

            revised = P.retain_type_metadata([(value, before, current)], root / "corrected", qualify)[0]
            index, body = P.ProducerRecords().record(revised)
            self.assertEqual(index["native_type_hash"], current["hash"].hex())
            self.assertEqual(revised["record"], value["record"])
            self.assertEqual(revised["sha256"], value["sha256"])
            self.assertEqual(revised["full_type"], P.full_type_key(current))
            self.assertEqual(seen, [(value, body, current)])
            self.assertTrue((Path(revised["provider"]) / "objects.bin").is_symlink())
            self.assertEqual((original / "index.jsonl").read_bytes(), original_index)
            self.assertEqual((original / "objects.bin").read_bytes(), original_body)
            with self.assertRaisesRegex(ValueError, "more than native hash"):
                P.retain_type_metadata([(value, before, {**current, "dependencies": [3]})], root / "bad-layout", qualify)
            with self.assertRaisesRegex(ValueError, "lacks current managed witness"):
                P.retain_type_metadata([(value, before, current)], root / "no-proof", lambda *args: None)

    def test_contextual_local_routes_do_not_alias_shared_path_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            owner, body, typ, *_ = self.external_contract(Path(directory))
            # Two distinct original source objects had collapsed onto one local
            # destination. Repair the qualified field, not every matching ID.
            body = struct.pack("<iqiqi", 0, 100, 0, 100, 73)
            first = {("first",): ("authored", "CAB-authored", 201)}
            result = P.relocate_pointer_fields(owner, body, typ, first, [])
            self.assertEqual(struct.unpack("<iqiqi", result), (0, 201, 0, 100, 73))
            second = {("second",): ("dependency", "CAB-dependency", 301)}
            result = P.relocate_pointer_fields(owner, result, typ, second, ["CAB-dependency"])
            self.assertEqual(struct.unpack("<iqiqi", result), (0, 201, 1, 301, 73))
            with self.assertRaisesRegex(ValueError, "existing non-null pointer"):
                P.relocate_pointer_fields(owner, body, typ, {("absent",): first[("first",)]}, [])
            with self.assertRaisesRegex(ValueError, "complete per-field"):
                P.relocate_external_fields(owner, result, typ, {}, ["CAB-dependency"])

    def test_final_type_proves_reallocated_script_slot_and_preserves_full_identity(self):
        M = P.module("bundle_manifest")
        nodes = [dict(type="MonoBehaviour", name="Base", size=-1, level=0, meta=0, flags=0, version=1)]
        nodes.extend(
            dict(type=kind, name=field, size=size, level=level, meta=0, flags=0, version=1)
            for kind, field, size, level in (
                ("PPtr<MonoScript>", "m_Script", 12, 1),
                ("int", "m_FileID", 4, 2),
                ("SInt64", "m_PathID", 8, 2),
            )
        )
        qualified = dict(class_id=114, stripped=0, script_type=19, script_id=b"s" * 16, hash=b"h" * 16, tree=M.S._tree(nodes), dependencies=[])
        final = {**qualified, "script_type": 0}
        body = struct.pack("<iq", 2, 45)
        self.assertEqual(P.qualified_final_type(body, final, [(2, 45)], qualified), qualified)
        self.assertEqual(final["script_type"], 0)
        for scripts in ([], [(2, 46)], [(0, 45)]):
            with self.subTest(scripts=scripts), self.assertRaisesRegex(ValueError, "script relationship"):
                P.qualified_final_type(body, final, scripts, qualified)
        for field, value in (("hash", b"x" * 16), ("script_id", b"x" * 16), ("stripped", 1), ("dependencies", [3])):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "full type identity"):
                P.qualified_final_type(body, {**final, field: value}, [(2, 45)], qualified)

    def external_contract(self, root):
        M = P.module("bundle_manifest")
        nodes = [dict(type="PhysicMaterial", name="Base", size=-1, level=0, meta=0, flags=0, version=1)]
        for name in ("first", "second"):
            nodes.extend(
                dict(type=kind, name=field, size=size, level=level, meta=0, flags=0, version=1)
                for kind, field, size, level in (("PPtr<Object>", name, 12, 1), ("int", "m_FileID", 4, 2), ("SInt64", "m_PathID", 8, 2))
            )
        nodes.append(dict(type="int", name="tail", size=4, level=1, meta=0, flags=0, version=1))
        typ = dict(class_id=134, stripped=0, script_type=-1, hash=bytes.fromhex("ab" * 16), tree=M.S._tree(nodes))
        body = struct.pack("<iqiqi", 1, 100, 1, 100, 73)

        def selected(destination, raw, provider):
            return dict(
                destination=destination,
                source=["original", "source-member", destination[2]],
                provider=provider,
                record_source=["producer-source", "producer-member", destination[2] + 1],
                bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                schema=hashlib.sha256(typ["tree"]).hexdigest(),
                full_type=P.full_type_key(typ),
                class_id=134,
                native_type_hash=typ["hash"].hex(),
                edges=sorted(set(P.pointers(raw, typ, {}).values())),
            )

        owner = selected(["authored", "CAB-authored", 10], body, "effective-provider")
        raw = struct.pack("<iqiqi", 0, 0, 0, 0, 91)
        endpoints = {}
        proofs = []
        for field, target in (("first", ["dependency", "CAB-dependency", 100]), ("second", ["authored", "CAB-authored", 20])):
            endpoint = selected(target, raw, "endpoint-provider")
            path = root / field
            path.write_bytes(raw)
            endpoints[tuple(target)] = endpoint, path, typ
            proofs.append(
                dict(
                    provider="original-provider",
                    effective_provider=owner["provider"],
                    owner=owner["destination"],
                    field=[field],
                    owner_sha256=owner["sha256"],
                    schema_sha256=owner["schema"],
                    **{"from": [1, 100]},
                    source_target=endpoint["source"],
                    target=target,
                    endpoint_type=dict(
                        class_id=134,
                        native_type_hash=typ["hash"].hex(),
                        full_type=endpoint["full_type"],
                        source_sha256="cd" * 32,
                        emitted_witnesses=[[endpoint["provider"], endpoint["record_source"], endpoint["sha256"], len(raw), endpoint["full_type"]]],
                    ),
                )
            )

        def read_endpoint(target):
            endpoint, path, endpoint_type = endpoints[target]
            return endpoint, path.read_bytes(), endpoint_type

        return owner, body, typ, proofs, endpoints, read_endpoint

    def test_external_fields_qualify_distinct_routes_for_the_same_old_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            owner, body, typ, proofs, _, read = self.external_contract(Path(tmp))
            targets = P.qualify_external_fields(owner, body, typ, proofs + [proofs[0]], read)
            actual = P.relocate_external_fields(owner, body, typ, targets, ["CAB-dependency"])
            self.assertEqual(P.pointers(actual, typ, {}), {("first",): (1, 100), ("second",): (0, 20)})
            self.assertEqual(actual[-4:], body[-4:])
            self.assertEqual(set(targets), {("first",), ("second",)})

    def test_structural_routes_check_complete_current_fields_without_source_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            owner, _, typ, proofs, endpoints, read = self.external_contract(Path(tmp))
            body = struct.pack("<iqiqi", 1, 100, 0, 20, 73)
            owner.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), edges=[[1, 100], [0, 20]])
            fields = P.pointers(body, typ, {})
            routes = [dict(field=p["field"], pointer=fields[tuple(p["field"])], target=p["target"]) for p in proofs]
            for endpoint, _, _ in endpoints.values():
                endpoint.pop("source")
            targets = P.qualify_structural_fields(owner, body, typ, routes, read)
            self.assertEqual(targets, {("first",): ("dependency", "CAB-dependency", 100)})
            self.assertEqual(P.relocate_external_fields(owner, body, typ, targets, ["CAB-dependency"]), body)
            with self.assertRaisesRegex(ValueError, "every nonnull field"):
                P.qualify_structural_fields(owner, body, typ, routes[:1], read)
            with self.assertRaisesRegex(ValueError, "field or pointer"):
                P.qualify_structural_fields(owner, body, typ, routes + routes[:1], read)
            endpoints["dependency", "CAB-dependency", 100][1].write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "body or full type"):
                P.qualify_structural_fields(owner, body, typ, routes, read)

    def test_external_fields_require_each_field_proof_and_effective_provider(self):
        import copy

        for failure in ("missing", "provider", "body", "schema", "pointer", "source", "aggregate", "witness"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                owner, body, typ, proofs, _, read = self.external_contract(Path(tmp))
                proofs = copy.deepcopy(proofs)
                if failure == "missing":
                    proofs.pop()
                elif failure == "provider":
                    proofs[1]["effective_provider"] = "original-provider"
                elif failure == "body":
                    proofs[1]["owner_sha256"] = "00" * 32
                elif failure == "schema":
                    proofs[1]["schema_sha256"] = "00" * 32
                elif failure == "pointer":
                    proofs[1]["from"] = [1, 999]
                elif failure == "source":
                    proofs[1]["source_target"] = ["other", "source-member", 20]
                elif failure == "aggregate":
                    proofs[1]["field"] = ["first"]
                else:
                    proofs[1]["endpoint_type"]["emitted_witnesses"][0][1] = proofs[1]["target"]
                with self.assertRaisesRegex(ValueError, "unique persisted endpoint"):
                    P.qualify_external_fields(owner, body, typ, proofs, read)

    def test_generated_endpoint_keeps_producer_provenance_without_original_source(self):
        import copy

        with tempfile.TemporaryDirectory() as tmp:
            owner, body, typ, proofs, endpoints, read = self.external_contract(Path(tmp))
            proof = proofs[0]
            endpoint, _, _ = endpoints[tuple(proof["target"])]
            provenance = {"producer": "registry", "receipt": {"sha256": "ef" * 32}}
            endpoint.update(source=None, generated_provenance=provenance)
            proof["source_target"] = None
            proof["endpoint_type"].update(source_sha256=None, generated_provenance=provenance)
            self.assertEqual(P.qualify_external_fields(owner, body, typ, proofs, read)[("first",)], tuple(proof["target"]))
            for change in ({"generated_provenance": None}, {"generated_provenance": {"producer": "other"}}, {"source_sha256": "cd" * 32}):
                bad = copy.deepcopy(proofs)
                bad[0]["endpoint_type"].update(change)
                with self.assertRaisesRegex(ValueError, "unique persisted endpoint"):
                    P.qualify_external_fields(owner, body, typ, bad, read)

    def test_external_fields_reject_conflicting_qualified_targets(self):
        import copy

        with tempfile.TemporaryDirectory() as tmp:
            owner, body, typ, proofs, _, read = self.external_contract(Path(tmp))
            conflict = copy.deepcopy(proofs[1])
            conflict["field"] = ["first"]
            with self.assertRaisesRegex(ValueError, r"unique persisted endpoint.*\(2\)"):
                P.qualify_external_fields(owner, body, typ, proofs + [conflict], read)

    def test_external_fields_read_actual_endpoint_bytes_and_full_types(self):
        for failure in ("bytes", "native", "script", "class", "destination"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                owner, body, typ, proofs, endpoints, read = self.external_contract(Path(tmp))
                key = tuple(proofs[0]["target"])
                endpoint, path, endpoint_type = endpoints[key]
                endpoint_type = dict(endpoint_type)
                if failure == "bytes":
                    path.write_bytes(path.read_bytes()[:-1] + b"x")
                elif failure == "native":
                    endpoint_type["hash"] = bytes.fromhex("ef" * 16)
                elif failure == "script":
                    endpoint_type["script_type"] = 2
                elif failure == "class":
                    endpoint_type["class_id"] = 21
                else:
                    endpoint["destination"] = ["other", "CAB-dependency", 100]
                endpoints[key] = endpoint, path, endpoint_type
                with self.assertRaisesRegex(ValueError, "unique persisted endpoint"):
                    P.qualify_external_fields(owner, body, typ, proofs, read)

    def test_external_relocation_cannot_omit_fields_or_reuse_ambiguous_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            owner, body, typ, proofs, _, read = self.external_contract(Path(tmp))
            targets = P.qualify_external_fields(owner, body, typ, proofs, read)
            with self.assertRaisesRegex(ValueError, "complete per-field coverage"):
                P.relocate_external_fields(owner, body, typ, {("first",): targets[("first",)]}, ["CAB-dependency"])
            for externals in ([], ["CAB-dependency", "CAB-dependency"], ["CAB-dependency", "CAB-authored"]):
                with self.subTest(externals=externals), self.assertRaisesRegex(ValueError, "member.*absent|Ambiguous"):
                    P.relocate_external_fields(owner, body, typ, targets, externals)
            ambiguous = {**targets, ("second",): ("other-bundle", "CAB-dependency", 20)}
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                P.relocate_external_fields(owner, body, typ, ambiguous, ["CAB-dependency"])

    def native_graph(self, root):
        M = P.module("bundle_manifest")
        tree = M.S._tree(
            [
                dict(type="PhysicMaterial", name="Base", size=-1, level=0, meta=0, flags=0, version=1),
                dict(type="PPtr<Object>", name="link", size=12, level=1, meta=0, flags=0, version=1),
                dict(type="int", name="m_FileID", size=4, level=2, meta=0, flags=0, version=1),
                dict(type="SInt64", name="m_PathID", size=8, level=2, meta=0, flags=0, version=1),
            ]
        )
        schema = hashlib.sha256(tree).hexdigest()
        types = root / "types.json"
        types.write_text(json.dumps({schema: dict(class_id=134, stripped=0, script_type=-1, hash="ab" * 16, tree=tree.hex())}))
        rows = []
        # Two providers and a cycle must close. A dangling record and its parent,
        # an external edge and a streamed resource must be explicitly omitted.
        for identity, file_id, target in ((10, 0, 20), (20, 0, 10), (30, 0, 999), (31, 0, 30), (40, 1, 10), (50, 0, 0)):
            provider = root / str(identity)
            provider.mkdir()
            data = struct.pack("<iq", file_id, target)
            (provider / "objects.bin").write_bytes(data)
            pin = hashlib.sha256(data).hexdigest()
            index = dict(bundle="source", member="native", path_id=identity, bytes=len(data), offset=0, sha256=pin)
            if identity == 50:
                index["resource"] = {"bytes": 8}
            index_path = provider / "index.jsonl"
            index_path.write_text(json.dumps(index) + "\n")
            receipt = dict(success=True, profile_sha256="profile-" + str(identity), outputs={"index.jsonl": dict(sha256=P.O.B.sha(index_path))})
            (provider / "result.json").write_text(json.dumps(receipt))
            row = dict(
                destination=["authored", "CAB-authored", identity],
                provider=str(provider),
                schema=schema,
                class_id=134,
                native_type_hash="ab" * 16,
                record=receipt["profile_sha256"],
                record_source=["source", "native", identity],
                bytes=len(data),
                sha256=pin,
                edges=[[file_id, target]],
            )
            if "resource" in index:
                row["resource"] = index["resource"]
            rows.append(row)
        graph = root / "graph"
        graph.mkdir()
        (graph / "done.json").write_text(json.dumps(dict(success=True, blocks=1)))
        (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        roots = [dict(path="Assets/Root.asset", destination=rows[0]["destination"], class_id=134)]
        (graph / "selected-roots.jsonl").write_text("".join(json.dumps(row) + "\n" for row in roots))
        return graph, types, rows

    def test_partial_native_emission_checks_final_bodies_types_and_closed_preloads(self):
        import UnityPy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types, _ = self.native_graph(root)
            output = root / "emitted"
            result = P.emit_closed_native(graph, [types], output, "authored", "CAB-authored")
            self.assertEqual((result["records"], result["roots"], result["preloads"]), (2, 1, 2))
            self.assertFalse(result["whole_game_complete"])
            self.assertFalse(result["typed_load_accepted"])
            self.assertFalse(result["device_accepted"])
            gaps = json.loads((output / "gaps.json").read_text())
            self.assertEqual(gaps["omitted_records"], 4)
            objects = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(result["bundle"]).objects}
            self.assertEqual(objects[10]["link"]["m_PathID"], 20)
            self.assertEqual(objects[20]["link"]["m_PathID"], 10)
            container = objects[1]
            self.assertEqual(container["m_PreloadTable"], [dict(m_FileID=0, m_PathID=i) for i in (10, 20)])
            self.assertEqual(dict(container["m_Container"])["assets/root.asset"], dict(preloadIndex=0, preloadSize=2, asset=dict(m_FileID=0, m_PathID=10)))
            request = json.loads((output / "request.json").read_text())
            self.assertEqual(request["sha256"], P.O.B.sha(Path(result["bundle"])))
            self.assertEqual(request["assets"], [dict(name="assets/root.asset", type="PhysicMaterial")])
            self.assertEqual(sorted(path.name for path in output.iterdir()), ["authored.bundle", "gaps.json", "request.json", "result.json", "roots.json"])

    def required_graph(self, root):
        graph, types, rows = self.native_graph(root)
        typ = next(iter(json.loads(types.read_text()).values()))
        typ["dependencies"] = []
        binary = {**typ, "tree": bytes.fromhex(typ["tree"]), "hash": bytes.fromhex(typ["hash"])}
        key = P.full_type_key(binary)
        types.write_text(json.dumps({key: typ}))
        for row in rows:
            row["full_type"] = key
        (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        required = dict(
            path_ids=[10, 20],
            externals=[],
            dependencies=[],
            asset_groups=[dict(guid="12" * 16, path="Assets/Root.asset", roots=[10, 20])],
            assets=[dict(name="assets/root.asset", type="PhysicMaterial")],
        )
        return graph, types, rows, required

    def test_required_emission_follows_mixed_retained_profiles_and_actual_extents(self):
        import UnityPy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types, selected, required = self.required_graph(root)
            original = [dict(row) for row in selected[:2]]

            def retain(name, values):
                folder = root / name
                directory = folder / "records"
                directory.mkdir(parents=True)
                index, blob = [], bytearray()
                for value in values:
                    before = Path(value["provider"])
                    prior = next(row for row in P.json_rows(before / "index.jsonl") if row["path_id"] == value["record_source"][2])
                    body = P.O.record_extent(before / "objects.bin", prior)
                    index.append({**prior, "offset": len(blob), "provider_before": str(before), "body_before_sha256": value["sha256"]})
                    blob.extend(body)
                    value["provider"] = str(directory)
                (directory / "objects.bin").write_bytes(blob)
                (directory / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in index))
                (directory / "witnesses.jsonl").write_text("")
                receipt = dict(
                    success=True,
                    index_sha256=P.O.B.sha(directory / "index.jsonl"),
                    objects_sha256=P.O.B.sha(directory / "objects.bin"),
                    witnesses_sha256=P.O.B.sha(directory / "witnesses.jsonl"),
                )
                (folder / "terminal.json").write_text(json.dumps(receipt))
                return directory

            retain("first", selected[:2])
            retained = retain("second", selected[:2])
            (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in selected))
            result = P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored", required=required)
            objects = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(result["bundle"]).objects}
            self.assertEqual((objects[10]["link"]["m_PathID"], objects[20]["link"]["m_PathID"]), (20, 10))
            self.assertEqual(len(result["producer_pins"]), 4)
            for before, value in zip(original, selected):
                self.assertEqual(P.ProducerRecords().record(value)[1], (Path(before["provider"]) / "objects.bin").read_bytes())
            wrong_profile = {**selected[0], "record": selected[1]["record"]}
            with self.assertRaisesRegex(ValueError, "profile differs"):
                P.ProducerRecords().record(wrong_profile)
            (Path(original[0]["provider"]) / "objects.bin").write_bytes(b"x" * 12)
            with self.assertRaisesRegex(ValueError, "extent drift"):
                P.ProducerRecords().record(selected[0])
            (retained / "witnesses.jsonl").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "witness drift"):
                P.ProducerRecords().record(selected[0])

    def test_provider_duplicate_copies_require_identical_metadata_and_valid_extents(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, selected, _ = self.required_graph(Path(tmp))
            value = selected[0]
            provider = Path(value["provider"])
            index = provider / "index.jsonl"
            row = next(P.json_rows(index))
            body = (provider / "objects.bin").read_bytes()
            copy = {**row, "offset": len(body)}
            (provider / "objects.bin").write_bytes(body + body)

            def pin_rows(rows):
                index.write_text("".join(json.dumps(item) + "\n" for item in rows))
                receipt = provider / "result.json"
                document = json.loads(receipt.read_text())
                document["outputs"]["index.jsonl"]["sha256"] = P.O.B.sha(index)
                receipt.write_text(json.dumps(document))

            pin_rows([row, copy])
            self.assertEqual(P.ProducerRecords().record(value)[1], body)
            pin_rows([row, {**copy, "native_type_hash": "cd" * 16}])
            with self.assertRaisesRegex(ValueError, "Conflicting native provider identity"):
                P.ProducerRecords().record(value)
            pin_rows([row, copy])
            (provider / "objects.bin").write_bytes(body + b"x" * len(body))
            with self.assertRaisesRegex(ValueError, "extent drift"):
                P.ProducerRecords().record(value)

    def test_required_emission_preserves_exact_objects_and_multiple_subasset_roots(self):
        import UnityPy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types, _, required = self.required_graph(root)
            result = P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored", required=required)
            self.assertTrue(result["required_set_accepted"])
            self.assertEqual((result["records"], result["roots"], result["preloads"]), (2, 2, 2))
            objects = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(result["bundle"]).objects}
            self.assertEqual(set(objects), {1, 10, 20})
            containers = objects[1]["m_Container"]
            self.assertEqual([row[0] for row in containers], ["assets/root.asset"] * 2)
            self.assertEqual([row[1]["asset"]["m_PathID"] for row in containers], [10, 20])
            self.assertEqual([row[1]["preloadIndex"] for row in containers], [0, 0])
            self.assertFalse(result["whole_game_complete"])
            self.assertFalse(result["typed_load_accepted"])

    def test_required_emission_rejects_missing_and_dangling_objects_without_pruning(self):
        for identities, message in (([10, 999], "Required produced objects absent"), ([10, 30], "absent produced local object"), ([10, 10], "distinct")):
            with self.subTest(identities=identities), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                graph, types, _, required = self.required_graph(root)
                required["path_ids"] = identities
                with self.assertRaisesRegex(ValueError, message):
                    P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored", required=required)

    def test_required_emission_does_not_resolve_full_type_by_shared_schema(self):
        for failure in ("absent_full_type", "changed_native_hash"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                graph, types, _, required = self.required_graph(root)
                table = json.loads(types.read_text())
                key, typ = next(iter(table.items()))
                if failure == "absent_full_type":
                    table = {hashlib.sha256(bytes.fromhex(typ["tree"])).hexdigest(): typ}
                else:
                    typ["hash"] = "00" * 16
                types.write_text(json.dumps(table))
                with self.assertRaises((KeyError, ValueError)):
                    P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored", required=required)

    def test_required_emission_rejects_unqualified_managed_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types, rows, required = self.required_graph(root)
            rows[0]["class_id"] = 114
            (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "current CLR qualification"):
                P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored", required=required)

    def test_required_emission_relocates_fields_and_rereads_actual_external_endpoints(self):
        import UnityPy

        for structural, drift in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(structural=structural, drift=drift), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                owner, body, typ, proofs, endpoints, read = self.external_contract(root)
                if structural:
                    body = struct.pack("<iqiqi", 1, 100, 1, 20, 73)
                    owner.update(sha256=hashlib.sha256(body).hexdigest(), edges=[[1, 100], [1, 20]])
                    owner.pop("source")
                    for endpoint, _, _ in endpoints.values():
                        endpoint.pop("source")
                typ["dependencies"] = []
                full_type = P.full_type_key(typ)
                local = endpoints["authored", "CAB-authored", 20][0]
                rows = [owner, local]
                for value, raw in ((owner, body), (local, endpoints[tuple(local["destination"])][1].read_bytes())):
                    directory = root / str(value["destination"][2])
                    directory.mkdir()
                    value.update(provider=str(directory), full_type=full_type, record="profile")
                    (directory / "objects.bin").write_bytes(raw)
                    index = dict(zip(("bundle", "member", "path_id"), value["record_source"]))
                    index.update(offset=0, bytes=len(raw), sha256=value["sha256"])
                    (directory / "index.jsonl").write_text(json.dumps(index) + "\n")
                    (directory / "result.json").write_text(
                        json.dumps(dict(success=True, profile_sha256="profile", outputs={"index.jsonl": dict(sha256=P.O.B.sha(directory / "index.jsonl"))}))
                    )
                for proof in proofs:
                    endpoint, _, _ = endpoints[tuple(proof["target"])]
                    endpoint["full_type"] = full_type
                    proof["effective_provider"] = owner["provider"]
                    proof["endpoint_type"].update(
                        full_type=full_type,
                        emitted_witnesses=[[endpoint["provider"], endpoint["record_source"], endpoint["sha256"], endpoint["bytes"], full_type]],
                    )
                graph = root / "graph"
                graph.mkdir()
                (graph / "done.json").write_text(json.dumps(dict(success=True)))
                (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                types = root / "types.json"
                types.write_text(json.dumps({full_type: P.O.json_layout(typ)}))
                required = dict(
                    path_ids=[10, 20],
                    externals=["CAB-dependency"],
                    dependencies=["dependency"],
                    asset_groups=[dict(guid="12" * 16, path="Assets/Root.asset", roots=[10])],
                    assets=[dict(name="assets/root.asset", type="PhysicMaterial")],
                )
                calls = 0

                def read_actual(target):
                    nonlocal calls
                    if target == ("dependency", "CAB-dependency", 100):
                        calls += 1
                        if drift and calls == 2:
                            endpoints[target][1].write_bytes(b"changed")
                    return read(target)

                def emit():
                    routes = None
                    if structural:
                        fields = P.pointers(body, typ, {})
                        routes = {
                            tuple(owner["destination"]): [dict(field=p["field"], pointer=fields[tuple(p["field"])], target=p["target"]) for p in proofs],
                            tuple(local["destination"]): [],
                        }
                    return P.emit_closed_native(
                        graph,
                        [types],
                        root / "emitted",
                        "authored",
                        "CAB-authored",
                        required=required,
                        field_proofs=() if structural else proofs,
                        structural_routes=routes,
                        endpoint_record=read_actual,
                    )

                if drift:
                    with self.assertRaisesRegex(ValueError, "Persisted external endpoint drift"):
                        emit()
                    self.assertFalse((root / "emitted/result.json").exists())
                else:
                    result = emit()
                    self.assertEqual(result["field_qualification"], "structural-current-routes" if structural else "source-provenance")
                    self.assertEqual(calls, 2)
                    self.assertEqual(len(result["qualified_endpoint_pins"]), 2)
                    objects = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(result["bundle"]).objects}
                    self.assertEqual(objects[10]["first"], dict(m_FileID=1, m_PathID=100))
                    self.assertEqual(objects[10]["second"], dict(m_FileID=0, m_PathID=20))
                    self.assertEqual(objects[1]["m_Dependencies"], ["dependency"])
                    self.assertEqual(result["preloads"], 3)

    def test_native_emission_rejects_observed_duplicate_and_pointer_drift(self):
        for failure in ("duplicate", "pointer", "type", "body", "index"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                graph, types, rows = self.native_graph(root)
                if failure == "duplicate":
                    rows.append(rows[0])
                elif failure == "pointer":
                    rows[0]["edges"] = [[0, 10]]
                elif failure == "type":
                    rows[0]["native_type_hash"] = "00" * 16
                elif failure == "body":
                    (root / "10/objects.bin").write_bytes(bytes(12))
                else:
                    with (root / "10/index.jsonl").open("a") as stream:
                        stream.write("\n")
                (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                with self.assertRaisesRegex(
                    ValueError, "Duplicate selected|Measured native pointers|Native type identity|record extent drift|provider index drift"
                ):
                    P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored")

    def streamed_graph(self, root):
        graph, types, rows = self.native_graph(root)
        schemas = json.loads(types.read_text())
        M = P.module("bundle_manifest")
        for identity, cid in ((60, 28), (70, 89), (80, 43)):
            tree = M.S._tree(
                [
                    dict(type=P.NATIVE_ROOT_TYPES[cid], name="Base", size=-1, level=0, meta=0, flags=0, version=1),
                    dict(type="PPtr<Object>", name="link", size=12, level=1, meta=0, flags=0, version=1),
                    dict(type="int", name="m_FileID", size=4, level=2, meta=0, flags=0, version=1),
                    dict(type="SInt64", name="m_PathID", size=8, level=2, meta=0, flags=0, version=1),
                    dict(type="StreamingInfo", name="m_StreamData", size=-1, level=1, meta=0, flags=0, version=1),
                    dict(type="UInt64", name="offset", size=8, level=2, meta=0, flags=0, version=1),
                    dict(type="unsigned int", name="size", size=4, level=2, meta=0, flags=0, version=1),
                    dict(type="string", name="path", size=-1, level=2, meta=0, flags=0, version=1),
                    dict(type="Array", name="Array", size=-1, level=3, meta=0x4000, flags=1, version=1),
                    dict(type="int", name="size", size=4, level=4, meta=0, flags=0, version=1),
                    dict(type="char", name="data", size=1, level=4, meta=0, flags=0, version=1),
                    dict(type="int", name="tail", size=4, level=1, meta=0, flags=0, version=1),
                ]
            )
            schema = hashlib.sha256(tree).hexdigest()
            schemas[schema] = dict(class_id=cid, stripped=0, script_type=-1, hash="cd" * 16, tree=tree.hex())
            provider = root / str(identity)
            provider.mkdir()
            payload = bytes([identity]) * 19
            resource = dict(offset=5, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            descriptor = dict(offset=0, size=len(payload), path="old-" + str(identity) + ".resS")
            resource["destination" if cid == 43 else "stream"] = descriptor
            body = struct.pack("<iqQI", 0, 10, 0, len(payload)) + P.module("texture_produce").text(descriptor["path"]) + struct.pack("<i", 123)
            (provider / "objects.bin").write_bytes(body)
            (provider / "resources.bin").write_bytes(b"pad!!" + payload)
            index = dict(
                bundle="source", member="native", path_id=identity, offset=0, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), resource=resource
            )
            index_path = provider / "index.jsonl"
            index_path.write_text(json.dumps(index) + "\n")
            receipt = dict(success=True, profile_sha256="stream-" + str(identity), outputs={"index.jsonl": dict(sha256=P.O.B.sha(index_path))})
            (provider / "result.json").write_text(json.dumps(receipt))
            rows.append(
                dict(
                    destination=["authored", "CAB-authored", identity],
                    provider=str(provider),
                    schema=schema,
                    class_id=cid,
                    native_type_hash="cd" * 16,
                    record=receipt["profile_sha256"],
                    record_source=["source", "native", identity],
                    bytes=len(body),
                    sha256=index["sha256"],
                    resource=resource,
                    edges=[[0, 10]],
                )
            )
        types.write_text(json.dumps(schemas))
        (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        with (graph / "selected-roots.jsonl").open("a") as stream:
            for row in rows[-3:]:
                stream.write(
                    json.dumps(dict(path="Assets/" + str(row["class_id"]) + ".asset", destination=row["destination"], class_id=row["class_id"])) + "\n"
                )
        return graph, types

    def test_streamed_native_records_repack_independent_offsets_and_preserve_pointers(self):
        import UnityPy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types = self.streamed_graph(root)
            result = P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored")
            self.assertEqual((result["records"], result["resource_records"], result["resource_bytes"]), (5, 3, 83))
            objects = {obj.path_id: obj.read_typetree() for obj in UnityPy.load(result["bundle"]).objects}
            resource = P.O.B.Bundle(Path(result["bundle"])).member("CAB-authored.resS")
            receipts = [json.loads(line) for line in (root / "emitted/resources.jsonl").read_text().splitlines()]
            for identity, offset, receipt in zip((60, 70, 80), (0, 32, 64), receipts):
                descriptor = objects[identity]["m_StreamData"]
                self.assertEqual(descriptor, dict(offset=offset, size=19, path="archive:/CAB-authored/CAB-authored.resS"))
                self.assertEqual(objects[identity]["link"], dict(m_FileID=0, m_PathID=10))
                self.assertEqual(objects[identity]["tail"], 123)
                resource.seek(offset)
                self.assertEqual(resource.read(19), bytes([identity]) * 19)
                self.assertNotEqual(receipt["source_body_sha256"], receipt["emitted_body_sha256"])

    def test_streamed_native_rejects_descriptor_or_resource_extent_drift(self):
        for failure in ("descriptor", "resource"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                graph, types = self.streamed_graph(root)
                if failure == "descriptor":
                    rows = [json.loads(line) for line in (graph / "selected-records.jsonl").read_text().splitlines()]
                    rows[-1]["resource"]["destination"]["offset"] = 100
                    index_path = root / "80/index.jsonl"
                    index = json.loads(index_path.read_text())
                    index["resource"] = rows[-1]["resource"]
                    index_path.write_text(json.dumps(index) + "\n")
                    receipt_path = root / "80/result.json"
                    receipt = json.loads(receipt_path.read_text())
                    receipt["outputs"]["index.jsonl"]["sha256"] = P.O.B.sha(index_path)
                    receipt_path.write_text(json.dumps(receipt))
                    (graph / "selected-records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                else:
                    (root / "60/resources.bin").write_bytes(bytes(24))
                with self.assertRaisesRegex(ValueError, "resource body descriptor drift|record extent drift"):
                    P.emit_closed_native(graph, [types], root / "emitted", "authored", "CAB-authored")

    def test_compressed_native_preserves_serialized_and_streamed_member_bytes(self):
        import lz4.block
        import UnityPy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph, types = self.streamed_graph(root)
            plain = P.emit_closed_native(graph, [types], root / "plain", "authored", "CAB-authored")
            manifest = P.module("bundle_manifest")
            original_module = P.module

            def compress(data, method):
                self.assertEqual(method, 3)
                return lz4.block.compress(data, store_size=False)

            with (
                patch.object(P, "module", side_effect=lambda name: manifest if name == "bundle_manifest" else original_module(name)),
                patch.object(manifest.W, "codec", return_value=nullcontext(compress)) as codec,
            ):
                packed = P.emit_closed_native(graph, [types], root / "packed", "authored", "CAB-authored", codec=Path("helper"), codec_sha256="ab" * 32)
            codec.assert_called_once_with(Path("helper"), "ab" * 32)
            self.assertEqual(packed["compression"], dict(method="lz4", codec_sha256="ab" * 32))
            self.assertLess(packed["bytes"], plain["bytes"])
            a, b = (P.O.B.Bundle(Path(result["bundle"])) for result in (plain, packed))
            self.assertEqual(a.members, b.members)
            for name in a.members:
                with a.member(name) as left, b.member(name) as right:
                    self.assertEqual(left.read(), right.read())
            self.assertEqual(len(UnityPy.load(packed["bundle"]).objects), 6)

    def test_owner_loads_with_isolated_standard_library_only_python(self):
        path = Path(P.__file__).resolve()
        code = (
            "import importlib.util; s=importlib.util.spec_from_file_location('isolated_preload',"
            + repr(str(path))
            + "); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)"
        )
        result = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_only_schema_declared_pointers_form_graph_edges(self):
        root = node("Root", size=24, children=(pointer("owner"), node("opaque", size=12)))
        body = struct.pack("<iqiq", 0, -19, 1, 999)
        self.assertEqual(P.pointers(body, {"tree": b"authored"}, {b"authored": root}), {("owner",): (0, -19)})

    def test_group_closure_uses_all_subassets_and_native_guid_file_order(self):
        selected = {
            "name": "authored",
            "member": "CAB-a",
            "externals": ["archive:/CAB-b/CAB-b", "Resources/unity_builtin_extra"],
            "dependencies": ["dependency"],
            "asset_groups": [
                {"path": "assets/z.asset", "guid": "10000000" + "0" * 24, "roots": [30, 10]},
                {"path": "assets/a.asset", "guid": "01000000" + "0" * 24, "roots": [20]},
            ],
        }
        graph = {30: {(0, 10), (2, 6)}, 10: {(0, 30), (1, 100)}, 20: set()}
        records = [{"path_id": identity, "body": identity, "type": {}} for identity in graph]
        with patch.object(P, "pointers", side_effect=lambda body, typ, schemas: {str(i): p for i, p in enumerate(graph[body])}):
            body = P.produce(selected, records, [])
        stream = io.BytesIO(body)

        def text():
            size = struct.unpack("<I", stream.read(4))[0]
            value = stream.read(size).decode()
            stream.seek((-stream.tell()) % 4, 1)
            return value

        self.assertEqual(text(), "authored")
        self.assertEqual(struct.unpack("<I", stream.read(4))[0], 5)
        self.assertEqual([struct.unpack("<iq", stream.read(12)) for _ in range(5)], [(2, 6), (0, 10), (0, 30), (1, 100), (0, 20)])
        self.assertEqual(struct.unpack("<I", stream.read(4))[0], 3)
        entries = [(text(), struct.unpack("<iiiq", stream.read(20))) for _ in range(3)]
        self.assertEqual(entries, [("assets/a.asset", (4, 1, 0, 20)), ("assets/z.asset", (0, 4, 0, 30)), ("assets/z.asset", (0, 4, 0, 10))])

    def test_external_component_owner_requires_original_backlink_and_membership(self):
        component = struct.pack("<iq", 0, 11)
        owner = struct.pack("<iq", 0, 22)
        schemas = {b"component": node("Root", children=(pointer("#374"),)), b"owner": node("Root", children=(pointer("m_Component"),))}
        original = {(0, 22): (component, {"class_id": 108, "tree": b"component"}), (0, 11): (owner, {"class_id": 1, "tree": b"owner"})}
        row = {
            "source": [0, 22],
            "owner_source": 11,
            "body_sha256": hashlib.sha256(component).hexdigest(),
            "owner_body_sha256": hashlib.sha256(owner).hexdigest(),
            "to": [1, 200],
            "owner": [1, 100],
        }
        selected = {"externals": ["external"], "external_component_owners": [row]}
        with patch.object(P.O, "source_record", side_effect=lambda sources, key: original[tuple(key)]):
            self.assertEqual(P.external_owners(selected, [], schemas), {(1, 200): (1, 100)})
            row["owner_source"] = 12
            original[0, 12] = original[0, 11]
            with self.assertRaisesRegex(ValueError, "GameObject owner differs"):
                P.external_owners(selected, [], schemas)

    def test_orphan_records_cannot_hide_dangling_or_invalid_file_pointers(self):
        for pointer in ((0, 999), (2, 17), (-1, 17), (2, 0)):
            with self.subTest(pointer=pointer), self.assertRaisesRegex(ValueError, "Produced object 20 references an absent"):
                P.validate_graph({10: set(), 20: {pointer}}, 1)
        P.validate_graph({10: {(0, 20)}, 20: {(0, 10), (1, 17), (0, 0)}}, 1)


if __name__ == "__main__":
    unittest.main()
