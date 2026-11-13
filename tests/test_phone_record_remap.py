"""Public index remapping retains source-produced bodies and provenance."""

import hashlib
import importlib.util
import json
import struct
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("record_remap", ROOT / "tools/phone-build/accepted-output/record_remap.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("remap_fixture", ROOT / "tests/test_phone_record_producer.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


class RecordRemapTests(unittest.TestCase):
    def test_current_script_uses_identity_and_receipt_instead_of_historical_id_or_body(self):
        def text(value):
            raw = value.encode()
            return struct.pack("<I", len(raw)) + raw + bytes(-len(raw) % 4)

        identity = ["Fixture.dll", "Authored", "CurrentScript"]
        body = text(identity[2]) + struct.pack("<i", -1000) + b"p" * 16
        body += text(identity[2]) + text(identity[1]) + text(identity[0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "registry.assets"
            path.write_bytes(F.serialized(body, F.F.node("Base", len(body), kind="UInt8"), class_id=115))
            receipt = {"profile_sha256": "b" * 64, "files": {path.name: {"bytes": path.stat().st_size, "sha256": R.O.B.sha(path)}}}
            selected = {"source": [path.name, 9000], "class_id": 115, "bytes": 1, "sha256": "0" * 64, "script_identity": identity}
            row, actual, definition = R.serialized_records(root, receipt, selected)
            self.assertEqual(definition["class_id"], 115)
            self.assertEqual(actual, body)
            self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(row["source_produced"]["path_id"], 77)
            self.assertEqual(row["source_produced"]["script_identity"], identity)
            self.assertFalse(row["source_produced"]["historical_raw_exact"])
            with self.assertRaisesRegex(ValueError, "identity"):
                R.serialized_records(root, receipt, dict(selected, script_identity=["Other.dll", *identity[1:]]))
            with self.assertRaisesRegex(ValueError, "MonoScript"):
                R.serialized_records(root, receipt, dict(selected, class_id=21))
            with self.assertRaisesRegex(ValueError, "native type"):
                R.serialized_records(root, receipt, dict(selected, native_type_hash="ff" * 16))
            R.O.current_script_identity(body, 115, identity)
            with self.assertRaisesRegex(ValueError, "identity"):
                R.O.current_script_identity(body, 115, ["Other.dll", *identity[1:]])

    def test_serialized_supplier_extracts_selected_record_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supplier = root / "supplier"
            supplier.mkdir()
            body = b"authored script body"
            path = supplier / "registry.assets"
            path.write_bytes(F.serialized(body, F.F.node("Base", len(body), kind="UInt8"), class_id=115))
            receipt = {
                "success": True,
                "input_id": R.O.M.INPUT_ID,
                "profile_sha256": "b" * 64,
                "files": {path.name: {"bytes": path.stat().st_size, "sha256": R.O.B.sha(path)}},
            }
            (supplier / "result.json").write_text(json.dumps(receipt))
            selected = {
                "source_profile_sha256": "b" * 64,
                "source": [path.name, 77],
                "class_id": 115,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "destination": ["bundle", "member", 99],
            }
            profile = root / "profile.json"
            profile.write_text(json.dumps({"input_id": receipt["input_id"], "records": [selected]}))
            R.produce(profile, R.O.B.sha(profile), [], root / "output", [(supplier, R.O.B.sha(supplier / "result.json"))])
            self.assertEqual((root / "output/objects.bin").read_bytes(), body)
            row = json.loads((root / "output/index.jsonl").read_text())
            self.assertEqual(row["source_produced"]["file_sha256"], receipt["files"][path.name]["sha256"])
            self.assertEqual(row["path_id"], 99)
            self.assertEqual(row["native_type_hash"], bytes(16).hex())
            types = json.loads((root / "output/types.json").read_text())
            self.assertEqual(types[row["type_id"]]["class_id"], 115)
            self.assertEqual(types[row["type_id"]]["hash"], bytes(16).hex())
            changed = dict(selected, bytes=1, sha256="0" * 64)
            row, actual, _ = R.serialized_records(supplier, receipt, changed, comparison="diagnostic")
            self.assertEqual(actual, body)
            self.assertEqual(row["bytes"], len(body))
            self.assertFalse(row["source_produced"]["historical_raw_exact"])
            with self.assertRaisesRegex(ValueError, "native type"):
                R.serialized_records(supplier, receipt, dict(selected, native_type_hash="ff" * 16))
            with self.assertRaisesRegex(ValueError, "class or size"):
                R.serialized_records(supplier, receipt, dict(selected, class_id=21))
            with self.assertRaises(ValueError):
                R.serialized_records(supplier, receipt, dict(selected, source=["../registry.assets", 77]))
            path.write_bytes(path.read_bytes() + b"drift")
            with self.assertRaisesRegex(ValueError, "file drift"):
                R.serialized_records(supplier, receipt, selected)

    def test_remapped_shader_retains_body_dependencies_and_supplier_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "supplier"
            pack.mkdir()
            body = b"authored shader fixture"
            (pack / "objects.bin").write_bytes(body)
            row = {
                "bundle": "source",
                "member": "source-member",
                "path_id": 10,
                "offset": 0,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "dependencies": [{"source": {"member": "original", "path_id": 42}, "to": [1, 6]}],
            }
            (pack / "index.jsonl").write_text(json.dumps(row) + "\n")
            receipt = {
                "success": True,
                "input_id": R.O.M.INPUT_ID,
                "profile_sha256": "a" * 64,
                "outputs": {name: {"bytes": (pack / name).stat().st_size, "sha256": R.O.B.sha(pack / name)} for name in ("objects.bin", "index.jsonl")},
            }
            (pack / "result.json").write_text(json.dumps(receipt))
            supplier_pin = R.O.B.sha(pack / "result.json")
            profile = root / "profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "input_id": receipt["input_id"],
                        "records": [
                            {
                                "source_profile_sha256": receipt["profile_sha256"],
                                "source": ["source", "source-member", 10],
                                "destination": ["destination", "destination-member", 99],
                                "bytes": len(body),
                                "sha256": row["sha256"],
                            }
                        ],
                    }
                )
            )
            result = R.produce(profile, R.O.B.sha(profile), [(pack, supplier_pin)], root / "output")
            emitted = json.loads((root / "output/index.jsonl").read_text())
            self.assertEqual((root / "output/objects.bin").read_bytes(), body)
            self.assertEqual(emitted, dict(row, bundle="destination", member="destination-member", path_id=99))
            self.assertEqual(result["supplier_receipts"], {"a" * 64: supplier_pin})
            self.assertEqual((pack / "objects.bin").read_bytes(), body)

    def test_supplier_local_type_ids_are_reindexed_without_losing_final_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packs, records, definitions = [], [], []
            for number in range(2):
                pack = root / str(number)
                pack.mkdir()
                body = b"authored body"
                definition = {
                    "class_id": 114,
                    "stripped": 0,
                    "script_type": -1,
                    "script_id": (bytes([number]) * 16).hex(),
                    "hash": (bytes([number + 1]) * 16).hex(),
                    "tree": bytes([number, 2, 3]).hex(),
                    "dependencies": [],
                }
                definitions.append(definition)
                (pack / "objects.bin").write_bytes(body)
                row = {
                    "bundle": "source",
                    "member": "member",
                    "path_id": 7,
                    "offset": 0,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "type_id": 0,
                }
                (pack / "index.jsonl").write_text(json.dumps(row) + "\n")
                (pack / "types.json").write_text(json.dumps([definition]))
                profile_pin = str(number + 1) * 64
                receipt = {
                    "success": True,
                    "input_id": R.O.M.INPUT_ID,
                    "profile_sha256": profile_pin,
                    "outputs": {
                        name: {"bytes": (pack / name).stat().st_size, "sha256": R.O.B.sha(pack / name)} for name in ("objects.bin", "index.jsonl", "types.json")
                    },
                }
                (pack / "result.json").write_text(json.dumps(receipt))
                packs.append((pack, R.O.B.sha(pack / "result.json")))
                records.append(
                    {
                        "source_profile_sha256": profile_pin,
                        "source": ["source", "member", 7],
                        "destination": ["destination", "member", 99 + number],
                        "bytes": len(body),
                        "sha256": row["sha256"],
                    }
                )
            profile = root / "profile.json"
            profile.write_text(json.dumps({"input_id": R.O.M.INPUT_ID, "records": records}))
            result = R.produce(profile, R.O.B.sha(profile), packs, root / "output")
            rows = [json.loads(line) for line in (root / "output/index.jsonl").read_text().splitlines()]
            types = json.loads((root / "output/types.json").read_text())
            self.assertEqual([types[row["type_id"]] for row in rows], definitions)
            self.assertNotEqual(rows[0]["type_id"], rows[1]["type_id"])
            self.assertEqual(result["outputs"]["types.json"]["sha256"], R.O.B.sha(root / "output/types.json"))
            (packs[0][0] / "types.json").write_text("[]")
            with self.assertRaises(ValueError):
                R.produce(profile, R.O.B.sha(profile), packs, root / "drift")


if __name__ == "__main__":
    unittest.main()
