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
