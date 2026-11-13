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
        (self.primary / "scripts").mkdir()
        (self.primary / "scripts/prune-generated.py").write_text("raise SystemExit(0)\n")
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

    def test_iteration_modes_keep_source_restoration_and_select_exact_action(self):
        for mode, action in (("export-splice", "whole-catalog-fast-build"), ("scripts-only", "whole-catalog-scripts-build")):
            with self.subTest(mode=mode), patch.object(shared, "invoke", side_effect=self.invoke):
                result = shared.build_shared_checkout(root=self.worker, iteration_mode=mode)
            self.assertTrue(result["restored"])
            self.assertEqual(self.calls[-1], ["prototype", "--action", action])
            self.assertEqual(self.git("rev-parse", "HEAD"), self.original)

    def test_iteration_refuses_full_content_symbols_and_capture_before_checkout(self):
        for extra in ({"code_only": False}, {"android_symbols": "debugging"}, {"capture_player_linker_inputs": True}):
            with self.subTest(extra=extra), patch.object(shared, "invoke") as invoke, self.assertRaises(ValueError):
                shared.build_shared_checkout(root=self.worker, iteration_mode="export-splice", **extra)
            invoke.assert_not_called()
            self.assertEqual(self.git("rev-parse", "HEAD"), self.original)

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

    def test_full_build_headroom_gate_refuses_before_checkout(self):
        with patch.object(shared.shutil, "disk_usage", return_value=SimpleNamespace(free=99 * 1024**3)):
            with patch.object(shared, "invoke") as invoke, self.assertRaisesRegex(RuntimeError, "100 GiB"):
                shared.build_shared_checkout(root=self.worker, code_only=False)
        invoke.assert_not_called()
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)

    def test_code_only_uses_ordinary_preflight_below_full_build_floor(self):
        with patch.object(shared.shutil, "disk_usage", return_value=SimpleNamespace(free=74 * 1024**3)):
            with patch.object(shared, "invoke", side_effect=self.invoke):
                result = shared.build_shared_checkout(root=self.worker)
        self.assertTrue(result["success"])
        self.assertEqual(self.calls[0], ["preflight", "--host-only"])
        self.assertEqual(self.calls[1], ["prototype", "--action", "whole-catalog-code-build"])

    def request(self):
        output = self.primary / "work/coordination/request-build"
        path = self.primary / "work/coordination/request.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(source_commit=self.target, full=True, output=str(output))))
        return path, output

    def test_request_smoke_does_not_build_or_write_terminal(self):
        request, output = self.request()
        with patch.object(shared, "ROOT", self.worker), patch.object(shared, "build_shared_checkout") as build:
            result = shared.run_request(request, dry_run=True)
        self.assertTrue(result["smoke"])
        build.assert_not_called()
        self.assertFalse(output.exists())

    def test_request_failure_retains_terminal_after_source_restoration_and_prune(self):
        request, output = self.request()
        # A real failing preflight exercises restoration, then the tracked
        # fixture command stands in for the storage-pruning CLI.

        def fail(*args, **kwargs):
            self.invoke(*args, **kwargs)
            raise RuntimeError("fixture build failure")

        with patch.object(shared, "ROOT", self.worker), patch.object(shared, "invoke", side_effect=fail):
            result = shared.run_request(request)
        self.assertFalse(result["success"])
        self.assertIn("fixture build failure", result["error"])
        self.assertEqual(result["prune_exit"], 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.original)
        self.assertEqual(json.loads((output / "terminal.done.json").read_text()), result)

    def test_child_source_drift_writes_failure_terminal(self):
        request, output = self.request()
        shared.git(self.worker, "commit", "--allow-empty", "-m", "source moved after dispatch")
        with patch.object(shared, "ROOT", self.worker), patch.object(shared, "build_shared_checkout") as build:
            result = shared.run_request(request)
        build.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("no longer matches", result["error"])
        self.assertTrue((output / "terminal.done.json").exists())

    def test_detach_sources_toolchain_and_creates_new_session(self):
        request, output = self.request()
        with patch.object(shared, "ROOT", self.worker), patch.object(shared, "Popen") as launch:
            launch.return_value.pid = 123
            result = shared.run_request(request, detach=True)
        self.assertEqual(result["pid"], 123)
        arguments, kwargs = launch.call_args
        self.assertIn('source "$1/scripts/env.sh"', arguments[0][2])
        self.assertTrue(kwargs["start_new_session"])
        self.assertTrue((output / "job.json").exists())
        self.assertFalse((output / "terminal.done.json").exists())

    def test_storage_wait_starts_only_after_capacity_recovers(self):
        with patch.object(shared.shutil, "disk_usage", side_effect=[SimpleNamespace(free=99 * 1024**3), SimpleNamespace(free=101 * 1024**3)]):
            with patch.object(shared.time, "sleep") as sleep:
                shared.wait_for_storage(self.primary, 60)
        sleep.assert_called_once()

    def test_storage_wait_timeout_records_failure_without_build(self):
        request, output = self.request()
        data = json.loads(request.read_text())
        data["storage_wait_seconds"] = 1
        request.write_text(json.dumps(data))
        with (
            patch.object(shared, "ROOT", self.worker),
            patch.object(shared.shutil, "disk_usage", return_value=SimpleNamespace(free=99 * 1024**3)),
            patch.object(shared.time, "monotonic", side_effect=[0, 2]),
            patch.object(shared, "build_shared_checkout") as build,
        ):
            result = shared.run_request(request)
        build.assert_not_called()
        self.assertIn("storage wait expired", result["error"])
        self.assertFalse(result["success"])
        self.assertTrue((output / "terminal.done.json").exists())


if __name__ == "__main__":
    unittest.main()
