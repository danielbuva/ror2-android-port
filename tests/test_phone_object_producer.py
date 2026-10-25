"""Complete source-only prefab fixture; no game bytes or installed Editor."""

from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


P = load("object_producer", ROOT / "tools/phone-build/accepted-output/object_produce.py")
FIXTURE = load("object_bundle_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literal_lz4(data, method):
    """Authored valid literal-only block, independent of a native installation."""
    if not method:
        return data
    size = len(data)
    extra = bytearray()
    if size >= 15:
        remainder = size - 15
        while remainder >= 255:
            extra.append(255)
            remainder -= 255
        extra.append(remainder)
    return bytes([min(size, 15) << 4]) + extra + data


def produce(profile, pin, pc, output):
    with patch.object(P.W, "codec", return_value=nullcontext(literal_lz4)):
        return P.produce(profile, pin, pc, output, Path("authored-codec"), "authored-codec-pin")


def typ(class_id):
    return {
        "class_id": class_id,
        "stripped": 0,
        "script_type": -1,
        "hash": bytes([class_id % 256]) * 16,
        "tree": struct.pack("<II", 1, 0) + bytes(32),
        "dependencies": [],
    }


def container_bytes():
    """Independent literal format fixture using authored asset identifiers."""

    def string(value):
        data = value.encode()
        return struct.pack("<I", len(data)) + data + bytes(-len(data) % 4)

    return (
        string("authored-target")
        + struct.pack("<Iiqiqiq", 3, 0, -7, 0, 2, 1, 88)
        + struct.pack("<I", 1)
        + string("assets/authored.prefab")
        + struct.pack("<iiiq", 0, 3, 0, -7)
        + struct.pack("<iiiqI", 0, 0, 0, 0, 1)
        + string("authored-target")
        + struct.pack("<I", 1)
        + string("authored-dependency")
        + struct.pack("<B3xiii", 0, 0, 7, 0)
    )


def fixture(root):
    pc = root / "pc"
    pc.mkdir()
    source_body = struct.pack("<iq", 0, 51) + b"TAIL"
    target_body = struct.pack("<iq", 0, 2) + b"TAIL"
    script_body = b"META"
    source_layout = {
        "engine": "2021.3.1f1",
        "platform": 19,
        "trees": True,
        "types": [typ(4), typ(115), typ(142)],
        "objects": [{"path_id": 51, "offset": 0, "bytes": 4, "type_id": 1}, {"path_id": 61, "offset": 8, "bytes": 16, "type_id": 0}],
        "scripts": [],
        "externals": [],
        "ref_types": [],
        "user": "",
    }
    original = io.BytesIO()
    P.W.write_serialized(original, source_layout, lambda row: io.BytesIO(script_body if row["path_id"] == 51 else source_body))
    source = pc / "source.bundle"
    source.write_bytes(FIXTURE.bundle([("CAB-source", original.getvalue(), 4)], True))
    selected = {
        "name": "authored-target",
        "member": "CAB-target",
        "asset": "Assets/Authored.prefab",
        "root": -7,
        "dependencies": ["authored-dependency"],
        "externals": ["CAB-dependency"],
        "external_objects": [[1, 88]],
    }
    container = container_bytes()
    bodies = {-7: target_body, 1: container, 2: script_body}
    target_layout = {
        "engine": "2021.3.45f2",
        "platform": 13,
        "trees": True,
        "types": [typ(115), typ(4), typ(142)],
        "objects": [
            {"path_id": -7, "offset": 8, "bytes": 16, "type_id": 1},
            {"path_id": 1, "offset": 24, "bytes": len(container), "type_id": 2},
            {"path_id": 2, "offset": 0, "bytes": 4, "type_id": 0},
        ],
        "scripts": [(0, 2)],
        "externals": [{"empty": "", "guid": bytes(16), "type": 0, "path": "archive:/CAB-dependency/CAB-dependency"}],
        "ref_types": [],
        "user": "",
    }
    target = io.BytesIO()
    P.W.write_serialized(target, target_layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
    selected["serialized_sha256"] = digest(target.getvalue())
    expected_bundle = io.BytesIO()
    P.W.write_bundle(expected_bundle, [("CAB-target", 4, len(target.getvalue()), lambda: io.BytesIO(target.getvalue()))], literal_lz4)
    selected["sha256"] = digest(expected_bundle.getvalue())
    selected["bytes"] = len(expected_bundle.getvalue())
    profile = {
        "input_id": P.M.INPUT_ID,
        "sources": [{"path": source.name, "sha256": P.B.sha(source), "member": "CAB-source"}],
        "bundle": selected,
        "objects": [
            {
                "path_id": -7,
                "source": [0, 61],
                "source_sha256": digest(source_body),
                "bytes": 16,
                "sha256": digest(target_body),
                "references": [{"offset": 0, "from": [0, 51], "to": [0, 2]}],
            },
            {"path_id": 1, "type_source": 0, "bytes": len(container), "sha256": digest(container)},
            {"path_id": 2, "source": [0, 51], "source_sha256": digest(script_body), "bytes": 4, "sha256": digest(script_body)},
        ],
    }
    path = root / "profile.json"
    path.write_text(json.dumps(profile))
    return pc, path, profile, bodies, target.getvalue()


class ObjectProducerTests(unittest.TestCase):
    def test_container_preload_partition_order_is_explicit(self):
        selected = {"name": "authored-bundle", "asset": "Assets/Authored.prefab", "root": 7, "external_objects": [[2, 91], [1, -18]], "dependencies": []}
        for external_first in (False, True):
            with self.subTest(external_first=external_first):
                selected["external_preload_first"] = external_first
                body = P.asset_bundle(selected, [7, -6])
                size = struct.unpack_from("<I", body)[0]
                offset = (4 + size + 3) // 4 * 4
                count = struct.unpack_from("<I", body, offset)[0]
                self.assertEqual(count, 4)
                actual = [struct.unpack_from("<iq", body, offset + 4 + 12 * index) for index in range(count)]
                local, external = [(0, -6), (0, 7)], [(2, 91), (1, -18)]
                self.assertEqual(actual, external + local if external_first else local + external)

    def test_complete_source_only_pack_and_source_derived_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc, profile, _, bodies, expected = fixture(root)
            before = P.B.sha(pc / "source.bundle")
            result = produce(profile, P.B.sha(profile), pc, root / "produced")
            self.assertTrue(result["success"])
            self.assertEqual(result["objects"], 3)
            self.assertEqual(result["serialized_sha256"], digest(expected))
            self.assertEqual((root / "produced/objects.bin").read_bytes(), b"".join(bodies[key] for key in sorted(bodies)))
            layout = json.loads((root / "produced/layout.json").read_text())
            self.assertEqual(layout["data_offset"], 4096)
            self.assertEqual(layout["bytes"], len(expected))
            self.assertEqual(layout["types"][0]["tree"], typ(115)["tree"].hex())
            self.assertEqual(P.B.sha(pc / "source.bundle"), before)
            emitted = P.B.Bundle(root / "produced/payload/authored-target").member("CAB-target")
            self.assertEqual(P.B.exact(emitted, emitted.size), expected)
            rows = [json.loads(line) for line in (root / "produced/index.jsonl").read_text().splitlines()]
            self.assertEqual([row["path_id"] for row in rows], [-7, 1, 2])
            self.assertEqual([row["bundle"] for row in rows], ["authored-target"] * 3)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                produce(profile, P.B.sha(profile), pc, root / "produced")
            with self.assertRaisesRegex(ValueError, "profile drift"):
                produce(profile, "0" * 64, pc, root / "drift-profile")

    def test_failed_source_and_destination_admission_are_receipted(self):
        for failure in ("bundle", "body", "destination", "structure"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pc, path, profile, _, _ = fixture(root)
                if failure == "bundle":
                    (pc / "source.bundle").write_bytes(b"input drift")
                elif failure == "body":
                    profile["objects"][0]["source_sha256"] = "0" * 64
                elif failure == "destination":
                    profile["objects"][0]["sha256"] = "0" * 64
                else:
                    profile["bundle"]["serialized_sha256"] = "0" * 64
                path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    produce(path, P.B.sha(path), pc, root / "failed")
                receipt = json.loads((root / "failed/result.json").read_text())
                self.assertFalse(receipt["success"])
                self.assertIn("error", receipt)

    def test_checked_remap_rejects_overlaps_escape_and_wrong_identity(self):
        body = b"KEEP" + struct.pack("<iq", 4, -500) + b"TAIL"
        row = {"offset": 4, "from": [4, -500], "to": [0, 123]}
        self.assertEqual(P.remap(body, [row]), b"KEEP" + struct.pack("<iq", 0, 123) + b"TAIL")
        for refs in ([row, row], [{**row, "offset": -4}], [{**row, "offset": 8}], [{**row, "offset": 5}], [{**row, "from": [4, -501]}]):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                P.remap(body, refs)

    def test_missing_script_and_duplicate_identity_refuse_layout(self):
        selected = {"externals": []}
        mb = {**typ(114), "script_id": bytes(16)}
        with self.assertRaisesRegex(ValueError, "script absent"):
            P.make_layout(selected, [{"path_id": 3, "type": mb, "body": bytes(16) + struct.pack("<iq", 0, 7)}])
        row = {"path_id": 8, "type": typ(4), "body": b"AUTHORED"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            P.make_layout(selected, [row, row])

    def test_script_table_and_type_indices_follow_produced_script_order(self):
        mono = {**typ(114), "script_id": bytes(16), "script_type": 99}
        body = bytes(16) + struct.pack("<iq", 0, 12) + b"PRESERVED"
        records = [
            {"path_id": 8, "type": mono, "body": body},
            {"path_id": 12, "type": typ(115), "body": b"SECOND"},
            {"path_id": -8, "type": typ(115), "body": b"FIRST"},
        ]
        layout, bodies = P.make_layout({"externals": []}, records)
        self.assertEqual(layout["scripts"], [(0, -8), (0, 12)])
        self.assertEqual(layout["types"][1]["script_type"], 1)
        self.assertEqual(mono["script_type"], 99)
        self.assertEqual(bodies[8], body)
        self.assertEqual([(row["path_id"], row["offset"]) for row in layout["objects"]], [(-8, 0), (8, 16), (12, 8)])


if __name__ == "__main__":
    unittest.main()
