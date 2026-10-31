"""Public index remapping retains source-produced bodies and provenance."""

import hashlib
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
