"""Independent authored Avatar table/range fixtures, without game data."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


A = load("avatar_producer", ROOT / "tools/phone-build/accepted-output/avatar_produce.py")
FIXTURE = load("authored_bundle_fixture", ROOT / "tests/test_phone_mesh_producer.py")


def entry(key, value):
    data = value.encode("utf-8")
    return struct.pack("<II", key, len(data)) + data + bytes(-len(data) % 4)


class AvatarProducerTests(unittest.TestCase):
    def test_order_preserves_all_original_entry_and_surrounding_bytes(self):
        rows = [entry(9, "Root/Ēta"), entry(4, ""), entry(3, "Bone/𐐷")]
        table = struct.pack("<I", 3) + b"".join(rows)
        body = b"PREFIX!!" + table + b"SUFFIX!!"
        result = A.reorder(body, (8, len(table)), [2, 0, 1])
        self.assertEqual(result, b"PREFIX!!" + struct.pack("<I", 3) + rows[2] + rows[0] + rows[1] + b"SUFFIX!!")
        self.assertEqual(A.reorder(body, (8, len(table)), [0, 1, 2]), body)

    def test_rejects_nonbijective_or_escaped_source_table(self):
        table = struct.pack("<I", 2) + entry(1, "a") + entry(2, "b")
        for order in ([0, 0], [0], [0, 2], [False, 1]):
            with self.subTest(order=order), self.assertRaises(ValueError):
                A.reorder(table, (0, len(table)), order)
        for field in ((1, len(table) - 1), (0, len(table) - 1), (0, len(table) + 1), (-4, len(table))):
            with self.subTest(field=field), self.assertRaises(ValueError):
                A.reorder(table, field, [1, 0])
        damaged = bytearray(table)
        struct.pack_into("<I", damaged, 8, 100000)
        with self.assertRaises(ValueError):
            A.reorder(damaged, (0, len(damaged)), [1, 0])

    def test_source_only_pack_persistence_input_drift_and_existing_output(self):
        body = b"HEADER!!" + struct.pack("<I", 2) + entry(7, "First") + entry(8, "Second") + b"TAIL"
        field = [8, len(body) - 12]
        expected = A.reorder(body, field, [1, 0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pc = root / "pc"
            pc.mkdir()
            source = pc / "authored.bundle"
            source.write_bytes(FIXTURE.bundle([("CAB-authored", b"LEAD" + body + b"END!", 4)], True))
            pin = A.BUNDLE.sha(source)
            avatar = {
                "path_id": 99,
                "offset": 4,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "tos_field": field,
                "outputs": [
                    {
                        "bundle": "target",
                        "member": "CAB-target",
                        "path_id": -456,
                        "sha256": hashlib.sha256(expected).hexdigest(),
                        "bytes": len(expected),
                        "order": [1, 0],
                    }
                ],
            }
            profile = {
                "input_id": A.MESH.INPUT_ID,
                "bundles": [{"path": source.name, "sha256": pin, "members": [{"name": "CAB-authored", "avatars": [avatar]}]}],
            }
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile))
            result = A.produce(profile_path, A.BUNDLE.sha(profile_path), pc, root / "output")
            self.assertTrue(result["success"])
            self.assertEqual((root / "output/objects.bin").read_bytes(), expected)
            self.assertEqual(A.BUNDLE.sha(source), pin)
            with self.assertRaises(ValueError):
                A.produce(profile_path, A.BUNDLE.sha(profile_path), pc, root / "output")
            with self.assertRaisesRegex(ValueError, "profile drift"):
                A.produce(profile_path, "0" * 64, pc, root / "bad-profile")
            source.write_bytes(b"authored drift")
            with self.assertRaisesRegex(ValueError, "bundle drift"):
                A.produce(profile_path, A.BUNDLE.sha(profile_path), pc, root / "bad-input")
            self.assertFalse(json.loads((root / "bad-input/result.json").read_text())["success"])


if __name__ == "__main__":
    unittest.main()
