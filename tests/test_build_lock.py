import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

LAB = Path(__file__).resolve().parents[1] / "scripts" / "lab"
sys.path.insert(0, str(LAB))

from build_lock import (  # noqa: E402
    active_lock_handoff,
    assert_build_unblocked,
    host_build_lock,
)


class HostBuildLockTests(unittest.TestCase):
    def test_nested_same_thread_is_reentrant_and_keeps_outer_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "coordination" / "unity-build.lock"
            with host_build_lock(lock, operation="outer"):
                outer = json.loads(lock.read_text())
                with host_build_lock(lock, operation="inner", timeout=0):
                    nested = json.loads(lock.read_text())
                    self.assertEqual(nested, outer)
                self.assertEqual(json.loads(lock.read_text()), outer)
            receipt = json.loads(lock.read_text())
            self.assertEqual(receipt["status"], "released")
            self.assertEqual(receipt["operation"], "outer")
            self.assertIn("released_at", receipt)
            self.assertTrue(lock.exists(), "persistent lock inode must not be removed")

    def test_timeout_reports_current_owner_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with host_build_lock(lock, operation="parent-test"):
                code = (
                    "from build_lock import host_build_lock\n"
                    "import sys\n"
                    "try:\n"
                    " with host_build_lock(sys.argv[1], operation='child-test', timeout=0.15, poll_interval=0.01): pass\n"
                    "except TimeoutError as error:\n"
                    " print(str(error))\n"
                    "else: raise SystemExit('unexpectedly acquired lock')\n"
                )
                env = dict(os.environ, PYTHONPATH=str(LAB))
                result = subprocess.run(
                    [sys.executable, "-c", code, str(lock)],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=True,
                )
                self.assertIn('"operation": "parent-test"', result.stdout)
                self.assertIn('"status": "held"', result.stdout)

    def test_child_can_share_inherited_descriptor_without_unlocking_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with host_build_lock(lock, operation="parent"):
                # Handoff uses the fixed host path in production. Temporarily
                # point the module at this test lock while remaining isolated.
                import build_lock

                with patch.object(build_lock, "HOST_BUILD_LOCK", lock.resolve()):
                    handoff_env, descriptors = active_lock_handoff()
                self.assertEqual(len(descriptors), 1)
                fd = descriptors[0]
                env = dict(os.environ, PYTHONPATH=str(LAB), **handoff_env)
                code = (
                    "from build_lock import host_build_lock\n"
                    "import sys\n"
                    "with host_build_lock(sys.argv[1], operation='child', inherited_fd=int(sys.argv[2])): print('shared')\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", code, str(lock), str(fd)],
                    env=env,
                    pass_fds=(fd,),
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=True,
                )
                self.assertIn("shared", result.stdout)
                self.assertEqual(json.loads(lock.read_text())["status"], "held")

    def test_coordination_blocker_is_only_checked_for_existence(self):
        with tempfile.TemporaryDirectory() as temp:
            blocker = Path(temp) / "claude-r9.lock"
            blocker.write_text("do not inspect or modify")
            before = blocker.stat()
            with self.assertRaisesRegex(RuntimeError, "active coordination lock"):
                assert_build_unblocked(blocker)
            self.assertEqual(blocker.read_text(), "do not inspect or modify")
            self.assertEqual(blocker.stat().st_mtime_ns, before.st_mtime_ns)

    def test_task_guard_is_opt_in_so_incumbent_clis_keep_working(self):
        import build_lock

        with tempfile.TemporaryDirectory() as temp:
            blocker = Path(temp) / "coordination.lock"
            blocker.write_text("incumbent session owns editor/device")
            with patch.object(build_lock, "CLAUDE_COORDINATION_LOCK", blocker), patch.dict(os.environ, {}, clear=True):
                assert_build_unblocked()
                with patch.dict(os.environ, {"LAB_COORDINATION_GUARD": "1"}):
                    with self.assertRaisesRegex(RuntimeError, "active coordination lock"):
                        assert_build_unblocked()

    def test_direct_editor_build_dispatch_is_rejected(self):
        import build

        with patch.object(build, "assert_build_unblocked") as guard:
            with self.assertRaisesRegex(RuntimeError, "Direct editor build dispatch is disabled"):
                build.editor("lab", "build")
            guard.assert_called_once_with()

    def test_historical_minimal_build_is_refused(self):
        import build

        with patch.object(build, "assert_build_unblocked"), patch.object(build, "run") as child:
            with self.assertRaisesRegex(RuntimeError, "historical minimal-build.*unsupported"):
                build.editor("lab", "minimal-build")
            child.assert_not_called()

    def test_presentation_dispatch_requires_coordinator_and_handoff(self):
        import build
        import build_lock
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with (
                patch.object(build, "HOST_BUILD_LOCK", lock),
                patch.object(build_lock, "HOST_BUILD_LOCK", lock),
                patch.object(build, "assert_build_unblocked"),
            ):
                with patch.object(build, "run") as child:
                    with self.assertRaisesRegex(RuntimeError, "presentation-payload coordinator"):
                        build.editor("lab", "presentation-payload")
                    child.assert_not_called()

                def fake_run(*args, **kwargs):
                    self.assertEqual(json.loads(lock.read_text())["status"], "held")
                    self.assertEqual(kwargs["env"]["ROR2LAB_COORDINATED_BUILD"], "1")
                    self.assertEqual(len(kwargs["pass_fds"]), 1)
                    return SimpleNamespace(stdout=b"mock presentation response")

                with patch.object(build, "run", side_effect=fake_run):
                    with host_build_lock(lock, operation="presentation coordinator"):
                        with build.coordinated_editor_operation():
                            self.assertEqual(build.editor("lab", "presentation-payload"), "mock presentation response")

    def test_editor_entry_refuses_coordination_blocker_before_child_call(self):
        import build

        with tempfile.TemporaryDirectory() as temp:
            blocker = Path(temp) / "claude-r9.lock"
            blocker.touch()
            with patch.object(build, "assert_build_unblocked", side_effect=lambda: assert_build_unblocked(blocker)):
                with patch.object(build, "run") as child:
                    with self.assertRaisesRegex(RuntimeError, "active coordination lock"):
                        build.editor("lab", "inspect")
                    child.assert_not_called()

    def test_editor_child_call_runs_inside_host_lock(self):
        import build
        import build_lock
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with (
                patch.object(build, "HOST_BUILD_LOCK", lock),
                patch.object(build_lock, "HOST_BUILD_LOCK", lock),
                patch.object(build, "assert_build_unblocked"),
            ):
                def fake_run(*args, **kwargs):
                    self.assertEqual(json.loads(lock.read_text())["status"], "held")
                    self.assertEqual(len(kwargs["pass_fds"]), 1)
                    return SimpleNamespace(stdout=b"mock editor response")

                with patch.object(build, "run", side_effect=fake_run):
                    self.assertEqual(build.editor("lab", "inspect"), "mock editor response")
            self.assertEqual(json.loads(lock.read_text())["status"], "released")

    def test_stale_receipt_does_not_block_kernel_lock_acquisition(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(json.dumps({"status": "held", "pid": 1, "operation": "old"}))
            with host_build_lock(lock, operation="new", timeout=0):
                receipt = json.loads(lock.read_text())
                self.assertEqual(receipt["status"], "held")
                self.assertEqual(receipt["operation"], "new")

    def test_receipt_is_released_when_body_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with self.assertRaisesRegex(ValueError, "fixture"):
                with host_build_lock(lock, operation="exception-path"):
                    raise ValueError("fixture")
            self.assertEqual(json.loads(lock.read_text())["status"], "released")
            with host_build_lock(lock, operation="after-exception", timeout=0):
                self.assertEqual(json.loads(lock.read_text())["operation"], "after-exception")

    def test_receipt_write_failure_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with patch("build_lock._write_receipt", side_effect=OSError("receipt failure")):
                with self.assertRaisesRegex(OSError, "receipt failure"):
                    with host_build_lock(lock, operation="write-failure"):
                        self.fail("body must not run without an owner receipt")
            with host_build_lock(lock, operation="reacquire", timeout=0):
                self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
