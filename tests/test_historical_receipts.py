"""Synthetic receipts only; no retained game evidence or private replay required."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import historical_receipts as receipts
import input_migration
from common import write


class HistoricalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = "work/retained/optional-presentation-transformation.json"
        self.data = dict(
            input_sha256="a" * 64,
            output_sha256="b" * 64,
            assembly_identity_preserved=True,
            type_field_method_contracts_preserved=True,
            module_identity_preserved=True,
            methods=["System.Void Fixture::Tick()"],
        )
        self.save_source()

    def save_source(self):
        write(self.root / self.source, self.data)
        self.digest = hashlib.sha256((self.root / self.source).read_bytes()).hexdigest()

    def pin(self):
        return receipts.pin(receipts.NAME, self.source, self.digest, root=self.root)

    def resolve(self, identity="a" * 64):
        return receipts.resolve(receipts.NAME, root=self.root, original_sha256=identity)

    def test_preserves_bytes_and_selection_at_non_timestamp_path(self):
        before = (self.root / self.source).read_bytes()
        selected = self.pin()
        self.assertEqual(self.resolve(), (self.data, selected))
        self.assertEqual((self.root / self.source).read_bytes(), before)
        self.assertEqual(selected["sha256"], self.digest)

    def test_missing_selection_fails_before_inventory_or_output(self):
        work = self.root / "work"
        baseline = work / "preserved"
        write(work / "inputs/latest-preserved.json", dict(path=str(baseline), input_id="fixture"))
        write(baseline / "receipt.json", dict(success=True, input_id="fixture"))
        write(baseline / "metadata/files.json", dict(files=[dict(path="Risk of Rain 2_Data/Managed/RoR2.dll", sha256="a" * 64)]))
        with patch.object(input_migration, "ROOT", self.root), patch.object(input_migration, "WORK", work), patch("inventory.inspect") as inspect:
            with self.assertRaisesRegex(RuntimeError, "Missing named historical receipt"):
                input_migration.check_update()
            inspect.assert_not_called()
        self.assertFalse((work / "experiments").exists())

    def test_does_not_replace_existing_selection(self):
        self.pin()
        with self.assertRaises(FileExistsError):
            self.pin()
        self.resolve()

    def test_rejects_drift_and_missing_source(self):
        self.pin()
        (self.root / self.source).write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            self.resolve()
        (self.root / self.source).unlink()
        with self.assertRaisesRegex(RuntimeError, "restore the specific retained evidence"):
            self.resolve()

    def test_rejects_wrong_preserved_input(self):
        self.pin()
        with self.assertRaisesRegex(RuntimeError, "does not match preserved"):
            self.resolve("c" * 64)

    def test_rejects_wrong_expected_hash(self):
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            receipts.pin(receipts.NAME, self.source, "c" * 64, root=self.root)
        self.assertFalse((self.root / "work/config").exists())

    def test_rejects_invalid_contracts(self):
        for changes in ({"methods": []}, {"methods": ["x", "x"]}, {"methods": [1]}, {"input_sha256": "bad"}, {"module_identity_preserved": False}):
            with self.subTest(changes=changes):
                original = self.data.copy()
                self.data.update(changes)
                self.save_source()
                with self.assertRaises(RuntimeError):
                    self.pin()
                self.data = original

    def test_rejects_unknown_name_and_escaping_or_symlink_paths(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown historical receipt"):
            receipts.pin("../other", self.source, self.digest, root=self.root)
        for path in ("outside.json", "/tmp/outside.json", "work/../outside.json"):
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "under ignored work"):
                receipts.pin(receipts.NAME, path, self.digest, root=self.root)
        (self.root / "work/link").symlink_to(self.root / "work/retained", target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinks"):
            receipts.pin(receipts.NAME, "work/link/optional-presentation-transformation.json", self.digest, root=self.root)

    def test_rejects_selection_identity_tampering(self):
        selection = self.pin()
        selection["name"] = "different"
        write(self.root / "work/config/historical-receipts" / (receipts.NAME + ".json"), selection)
        with self.assertRaisesRegex(RuntimeError, "schema/name"):
            self.resolve()


if __name__ == "__main__":
    unittest.main()
