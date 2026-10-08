"""Snapshots retain bytes independently while allowing APFS to share storage."""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lab'))
import build

class BuildSnapshotTests(unittest.TestCase):
 def test_snapshot_mutation_preserves_source_and_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'source';target=Path(tmp)/'snapshot'
   source.write_bytes(b'original build artifact');source.chmod(0o640)
   before=source.stat();build.copy_build_artifact(source,target)
   self.assertEqual(target.read_bytes(),source.read_bytes());self.assertNotEqual(target.stat().st_ino,before.st_ino)
   self.assertEqual(target.stat().st_mtime_ns,before.st_mtime_ns);self.assertEqual(target.stat().st_mode&0o777,0o640)
   target.write_bytes(b'next build');self.assertEqual(source.read_bytes(),b'original build artifact')
 def test_unsupported_clone_uses_verified_independent_copy(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'source';target=Path(tmp)/'snapshot';source.write_bytes(b'fallback artifact')
   with patch.object(build.sys,'platform','darwin'),patch.object(build,'run',return_value=SimpleNamespace(returncode=1)):
    build.copy_build_artifact(source,target)
   self.assertEqual(target.read_bytes(),source.read_bytes());self.assertNotEqual(target.stat().st_ino,source.stat().st_ino)
 def test_failed_clone_identity_cannot_publish_snapshot(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'source';target=Path(tmp)/'snapshot';source.write_bytes(b'valid');target.write_bytes(b'corrupt')
   with patch.object(build.sys,'platform','darwin'),patch.object(build,'run',return_value=SimpleNamespace(returncode=0)):
    with self.assertRaisesRegex(RuntimeError,'hash verification failed'):build.copy_build_artifact(source,target)
