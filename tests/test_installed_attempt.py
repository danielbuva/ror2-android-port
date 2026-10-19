import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_ROOT / "scripts/lab"))

from installed_attempt import attempt_from_installed


class InstalledAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apk = self.root / "synthetic-lab.apk"
        self.apk.write_bytes(b"synthetic APK bytes")
        self.receipt = {
            "apk": str(self.apk),
            "apk_sha256": hashlib.sha256(self.apk.read_bytes()).hexdigest(),
        }

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def loader(configs):
        objects = []
        for config in configs:
            raw = json.dumps(config).encode("utf-8")
            objects.append(SimpleNamespace(
                type=SimpleNamespace(name="TextAsset"),
                read=lambda raw=raw: SimpleNamespace(m_Name="MovementBatchProbe", m_Script=raw),
            ))
        return lambda path: SimpleNamespace(objects=objects)

    def test_reads_unique_attempt_from_hash_verified_receipt_apk(self):
        seen = []
        expected_bytes = self.apk.read_bytes()
        def load(data):
            seen.append(data)
            return self.loader([{"attempt": "attempt-in-apk"}])(data)
        self.assertEqual(attempt_from_installed(self.receipt, loader=load), "attempt-in-apk")
        self.assertEqual(seen, [expected_bytes])

    def test_rejects_changed_apk_before_parsing(self):
        self.apk.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "bytes changed"):
            attempt_from_installed(self.receipt, loader=lambda _: self.fail("must not parse"))

    def test_parser_receives_verified_snapshot_if_file_changes_after_hashing(self):
        original = self.apk.read_bytes()
        def mutate_after_snapshot(data):
            self.assertEqual(data, original)
            self.apk.write_bytes(b"replacement bytes after digest check")
            return self.loader([{"attempt": "attempt-from-verified-snapshot"}])(data)
        self.assertEqual(attempt_from_installed(self.receipt, loader=mutate_after_snapshot),
                         "attempt-from-verified-snapshot")
        self.assertNotEqual(hashlib.sha256(self.apk.read_bytes()).hexdigest(), self.receipt["apk_sha256"])

    def test_rejects_missing_or_ambiguous_textasset(self):
        for configs in ([], [{"attempt": "one"}, {"attempt": "two"}]):
            with self.subTest(count=len(configs)), self.assertRaisesRegex(RuntimeError, "exactly one"):
                attempt_from_installed(self.receipt, loader=self.loader(configs))

    def test_rejects_invalid_json_or_missing_attempt(self):
        invalid = lambda _: SimpleNamespace(objects=[SimpleNamespace(
            type=SimpleNamespace(name="TextAsset"),
            read=lambda: SimpleNamespace(m_Name="MovementBatchProbe", m_Script=b"not-json"),
        )])
        with self.assertRaisesRegex(RuntimeError, "Cannot read"):
            attempt_from_installed(self.receipt, loader=invalid)
        with self.assertRaisesRegex(RuntimeError, "no valid attempt"):
            attempt_from_installed(self.receipt, loader=self.loader([{}]))

    def test_rejects_incomplete_receipt_and_missing_apk(self):
        with self.assertRaisesRegex(RuntimeError, "lacks APK path/hash"):
            attempt_from_installed({"apk_sha256": self.receipt["apk_sha256"]})
        missing = dict(self.receipt, apk=str(self.root / "absent.apk"))
        with self.assertRaisesRegex(RuntimeError, "missing"):
            attempt_from_installed(missing)


if __name__ == "__main__":
    unittest.main()
