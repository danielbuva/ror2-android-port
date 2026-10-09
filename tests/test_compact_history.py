import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('compact_history', Path(__file__).resolve().parents[1] / 'scripts/compact-history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class HistoryStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = 'work/experiments/scene-runtime/closed/stage'
        self.tree = self.root / self.target
        (self.tree / 'nested/empty').mkdir(parents=True)
        (self.tree / 'nested/a.txt').write_bytes(b'original bytes\n' * 300)
        (self.tree / 'b.txt').write_bytes((self.tree / 'nested/a.txt').read_bytes())
        (self.tree / 'b.txt').chmod(0o755)
        self.storage = history.Storage(self.root)

    def test_lossless_deduplicated_restore_with_independent_files(self):
        original = history.entries(self.tree)
        receipt = history.retire(self.root, self.storage, self.target, [])
        self.assertFalse(self.tree.exists())
        self.assertEqual(self.storage.new_blobs, 1)
        self.assertEqual(receipt['files'], 2)
        history.restore(self.root, self.storage, self.target)
        restored = history.entries(self.tree)
        self.assertEqual([(r['path'], r['mode'], r['mtime_ns']) for r in original],
                         [(r['path'], r['mode'], r['mtime_ns']) for r in restored])
        self.assertEqual((self.tree / 'nested/a.txt').read_bytes(), b'original bytes\n' * 300)
        (self.tree / 'b.txt').write_text('changed after restore')
        self.assertNotEqual((self.tree / 'nested/a.txt').read_text(), 'changed after restore')
        history.restore(self.root, self.storage, self.target, 'work/second-restore')
        self.assertEqual((self.root / 'work/second-restore/b.txt').read_bytes(), b'original bytes\n' * 300)

    def test_protected_ancestor_and_descendant_rejected(self):
        for protected in ([str(Path(self.target).parent)], [self.target + '/nested/a.txt']):
            with self.assertRaises(ValueError):
                history.retire(self.root, self.storage, self.target, protected)
        self.assertTrue(self.tree.exists())

    def test_workspace_and_cache_receipts_are_ineligible(self):
        for target in ('work/lab-project/Assets', 'work/build-cache/key',
                       'work/build-cache/key/result.json', '../outside', '/outside'):
            with self.assertRaises(ValueError):
                history.eligible(self.root, target, [])

    def test_symlink_does_not_delete_its_target(self):
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        (self.tree / 'alias').symlink_to(outside)
        with self.assertRaises(ValueError):
            history.retire(self.root, self.storage, self.target, [])
        self.assertEqual(outside.read_text(), 'keep')
        self.assertTrue(self.tree.exists())

    def test_changed_tree_is_not_deleted(self):
        save = self.storage.save

        def change_source(source, record):
            save(source, record)
            (self.tree / 'new.txt').write_text('late writer')

        with patch.object(self.storage, 'save', side_effect=change_source):
            with self.assertRaises(ValueError):
                history.retire(self.root, self.storage, self.target, [])
        self.assertTrue((self.tree / 'new.txt').exists())

    def test_deliberately_pruned_output_cannot_claim_restoration(self):
        history.retire(self.root, self.storage, self.target, [])
        marker = self.tree.with_name('stage.retired.json')
        receipt = json.loads(marker.read_text())
        receipt['recoverable'] = False
        marker.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'rebuild'):
            history.restore(self.root, self.storage, self.target)
        self.assertFalse(self.tree.exists())

    def test_corrupt_blob_prevents_retirement_and_restore(self):
        receipt = history.retire(self.root, self.storage, self.target, [])
        blob = next((self.root / history.STORE / 'blobs').rglob('*.gz'))
        blob.write_bytes(b'broken')
        with self.assertRaises((ValueError, OSError, EOFError)):
            history.restore(self.root, self.storage, self.target)
        self.assertFalse(self.tree.exists())
        self.tree.mkdir()
        (self.tree / 'a.txt').write_bytes(b'original bytes\n' * 300)
        (self.tree.with_name('stage.retired.json')).unlink()
        with self.assertRaises((ValueError, OSError, EOFError)):
            history.retire(self.root, history.Storage(self.root), self.target, [])
        self.assertTrue((self.tree / 'a.txt').exists())
        self.assertEqual(receipt['files'], 2)


if __name__ == '__main__':
    unittest.main()
