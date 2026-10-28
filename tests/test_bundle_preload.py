"""Authored contracts for typed prefab dependency/group framing."""

import hashlib
import importlib
import io
from pathlib import Path
import struct
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
