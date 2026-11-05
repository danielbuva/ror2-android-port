"""Snapshots retain bytes independently while allowing APFS to share storage."""

import errno
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build


class BuildSnapshotTests(unittest.TestCase):
    def test_snapshot_mutation_preserves_source_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "snapshot"
            source.write_bytes(b"original build artifact")
            source.chmod(0o640)
            before = source.stat()
            build.copy_build_artifact(source, target)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertNotEqual(target.stat().st_ino, before.st_ino)
            self.assertEqual(target.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            target.write_bytes(b"next build")
            self.assertEqual(source.read_bytes(), b"original build artifact")

    def test_unsupported_clone_uses_verified_independent_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "snapshot"
            source.write_bytes(b"fallback artifact")
            with patch.object(build.sys, "platform", "darwin"), patch.object(build, "run", return_value=SimpleNamespace(returncode=1)):
                build.copy_build_artifact(source, target)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertNotEqual(target.stat().st_ino, source.stat().st_ino)

    def test_failed_clone_identity_cannot_publish_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "snapshot"
            source.write_bytes(b"valid")

            def corrupt_clone(*args, **kwargs):
                target.write_bytes(b"wrong")
                return SimpleNamespace(returncode=0)

            with patch.object(build.sys, "platform", "darwin"), patch.object(build, "run", side_effect=corrupt_clone):
                with self.assertRaisesRegex(RuntimeError, "hash verification failed"):
                    build.copy_build_artifact(source, target)

    @unittest.skipUnless(sys.platform == "darwin" or hasattr(os, "setxattr"), "extended attributes unavailable")
    def test_mid_copy_xattr_change_requires_matching_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "snapshot"
            source.write_bytes(b"valid")
            clone = build.copy_file_clone

            def metadata_clone(*args, **kwargs):
                clone(*args, **kwargs)
                before = build.file_identity(source)
                try:
                    value = str(before[-1])
                    if sys.platform == "darwin":
                        subprocess.run(["/usr/bin/xattr", "-w", "user.lab.snapshot-test", value, str(source)], check=True, capture_output=True)
                    else:
                        os.setxattr(source, "user.lab.snapshot-test", value.encode())
                except OSError as error:
                    if error.errno in (errno.ENOTSUP, errno.ENOSYS):
                        self.skipTest("filesystem lacks extended attributes")
                    raise
                after = build.file_identity(source)
                self.assertEqual(before[:-1], after[:-1])
                self.assertNotEqual(before[-1], after[-1])
                if corrupt:
                    target.write_bytes(b"wrong")

            for verify, corrupt in ((True, False), (False, False), (True, True), (False, True)):
                with self.subTest(verify=verify, corrupt=corrupt), patch.object(build, "copy_file_clone", side_effect=metadata_clone):
                    log = io.StringIO()
                    with redirect_stderr(log):
                        if not corrupt:
                            self.assertEqual(build.copy_build_artifact(source, target, verify=verify), str(target))
                            self.assertEqual(source.read_bytes(), target.read_bytes())
                            self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
                            self.assertIn("benign ctime-only metadata change", log.getvalue())
                        else:
                            with self.assertRaisesRegex(RuntimeError, "source identity changed"):
                                build.copy_build_artifact(source, target, verify=verify)
                            self.assertEqual(log.getvalue(), "")
