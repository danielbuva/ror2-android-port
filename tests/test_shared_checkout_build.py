"""Real temporary Git worktrees exercise the shared build's source boundary."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import build_lock
import shared_checkout_build as shared


class SharedCheckoutBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.primary = base / "primary"
        self.worker = base / "worker"
        self.primary.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "fixture.invalid")
        self.git("config", "user.name", "Fixture")
        (self.primary / ".gitignore").write_text("work/\n")
        (self.primary / "dev").write_text("fixture\n")
        (self.primary / "owner.txt").write_text("main source\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture main")
        self.original = self.git("rev-parse", "HEAD")
        self.git("worktree", "add", "-b", "worker", str(self.worker))
        (self.worker / "owner.txt").write_text("worker source\n")
        shared.git(self.worker, "commit", "-am", "fixture worker")
        self.target = shared.git(self.worker, "rev-parse", "HEAD")
        self.lock = self.primary / "work/coordination/unity-build.lock"
        self.calls = []
        # These source/lock tests build nothing. CI's disk capacity must not
        # determine whether their synthetic Git transitions can be exercised.
        capacity = patch.object(shared.shutil, "disk_usage", return_value=SimpleNamespace(free=200 * 1024**3))
        capacity.start()
        self.addCleanup(capacity.stop)

    def git(self, *args):
        return shared.git(self.primary, *args)

    def invoke(self, root, arguments, *, env, pass_fds):
        self.assertEqual(root, self.primary)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.target)
        self.assertEqual((root / "owner.txt").read_text(), "worker source\n")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "HEAD")
        build_lock.assert_host_build_lock_held(self.lock)
        self.assertEqual(int(env[build_lock.INHERITED_FD_ENV]), pass_fds[0])
        self.assertEqual(os.fstat(pass_fds[0]).st_ino, self.lock.stat().st_ino)
        self.calls.append(arguments)

    def test_build_uses_committed_source_inherits_mutex_and_restores_branch(self):
        with patch.object(shared, "invoke", side_effect=self.invoke):
            result = shared.build_shared_checkout(root=self.worker, capture_player_linker_inputs=True, capture_il2cpp_invocation=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["restored"])
        self.assertEqual(self.calls[0], ["preflight", "--host-only"])
        self.assertEqual(
            self.calls[1],
            ["prototype", "--action", "whole-catalog-code-build", "--capture-player-linker-inputs", "--capture-il2cpp-invocation"],
        )
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual((self.primary / "owner.txt").read_text(), "main source\n")
        self.assertEqual(json.loads(self.lock.read_text())["status"], "released")

    def test_failed_build_restores_source_and_retains_failure_receipt(self):
        def fail(*args, **kwargs):
            self.invoke(*args, **kwargs)
            raise subprocess.CalledProcessError(1, "fixture-preflight")

        with patch.object(shared, "invoke", side_effect=fail), self.assertRaises(subprocess.CalledProcessError):
            shared.build_shared_checkout(root=self.worker)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)
        receipt = json.loads(next((self.primary / "work/coordination/shared-builds").glob("*.json")).read_text())
        self.assertFalse(receipt["success"])
        self.assertTrue(receipt["restored"])

    def test_dirty_primary_is_refused_before_checkout_or_build(self):
        (self.primary / "owner.txt").write_text("another worker's changes\n")
        with patch.object(shared, "invoke") as invoke, self.assertRaisesRegex(RuntimeError, "clean source checkouts"):
            shared.build_shared_checkout(root=self.worker)
        invoke.assert_not_called()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)
        self.assertEqual((self.primary / "owner.txt").read_text(), "another worker's changes\n")

    def test_concurrent_source_edit_is_preserved_instead_of_reset(self):
        def edit(*args, **kwargs):
            self.invoke(*args, **kwargs)
            (self.primary / "owner.txt").write_text("concurrent edit\n")
            raise RuntimeError("fixture concurrent edit")

        with patch.object(shared, "invoke", side_effect=edit), self.assertRaises(RuntimeError):
            shared.build_shared_checkout(root=self.worker)
        self.assertEqual((self.primary / "owner.txt").read_text(), "concurrent edit\n")
        receipt = json.loads(next((self.primary / "work/coordination/shared-builds").glob("*.json")).read_text())
        self.assertFalse(receipt["success"])
        self.assertFalse(receipt["restored"])

    def test_unfinished_git_operation_is_refused(self):
        marker = Path(self.git("rev-parse", "--git-path", "MERGE_HEAD"))
        marker = marker if marker.is_absolute() else self.primary / marker
        marker.write_text(self.original + "\n")
        with patch.object(shared, "invoke") as invoke, self.assertRaisesRegex(RuntimeError, "unfinished Git operation"):
            shared.build_shared_checkout(root=self.worker)
        invoke.assert_not_called()

    def test_real_build_headroom_gate_refuses_before_checkout(self):
        with patch.object(shared.shutil, "disk_usage", return_value=SimpleNamespace(free=99 * 1024**3)):
            with patch.object(shared, "invoke") as invoke, self.assertRaisesRegex(RuntimeError, "100 GiB"):
                shared.build_shared_checkout(root=self.worker)
        invoke.assert_not_called()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)


if __name__ == "__main__":
    unittest.main()
