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


class RecordRemapTests(unittest.TestCase):
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
