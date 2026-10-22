"""Subprocess contract for inherited Unity host-lock forwarding."""

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

import build_lock


class InheritedBuildLockHandoffTests(unittest.TestCase):
    def test_two_subprocess_hops_retain_lock_and_uninherited_competitor_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "coordination" / "unity-build.lock"
            child_script = Path(temp) / "hop.py"
            child_script.write_text(
                """import json, os, subprocess, sys
from pathlib import Path
import build_lock
lock = Path(sys.argv[1]).resolve()
depth = int(sys.argv[2])
build_lock.HOST_BUILD_LOCK = lock
with build_lock.host_build_lock(lock, operation='inherited-hop'):
    handoff_env, pass_fds = build_lock.active_lock_handoff()
    inherited = os.environ[build_lock.INHERITED_FD_ENV]
    assert handoff_env == {build_lock.INHERITED_FD_ENV: inherited}, handoff_env
    assert pass_fds == (int(inherited),), pass_fds
    if depth:
        result = subprocess.run([sys.executable, __file__, str(lock), str(depth - 1)],
            env=dict(os.environ, **handoff_env), pass_fds=pass_fds,
            text=True, capture_output=True, timeout=5)
        if result.returncode:
            raise SystemExit(result.stderr or result.stdout)
        assert 'grandchild-shared' in result.stdout, result.stdout
    contender_env = dict(os.environ)
    contender_env.pop(build_lock.INHERITED_FD_ENV, None)
    contender = subprocess.run([sys.executable, '-c',
        \"from build_lock import host_build_lock; import sys\\ntry:\\n with host_build_lock(sys.argv[1], operation='competitor', timeout=.12, poll_interval=.01): pass\\nexcept TimeoutError: print('competitor-refused')\\nelse: raise SystemExit('competitor acquired lock')\",
        str(lock)], env=contender_env, text=True, capture_output=True, timeout=5)
    if contender.returncode or 'competitor-refused' not in contender.stdout:
        raise SystemExit(contender.stderr or contender.stdout)
print('grandchild-shared' if depth == 0 else 'child-shared')
""",
                encoding="utf-8",
            )
            with patch.object(build_lock, "HOST_BUILD_LOCK", lock.resolve()):
                with build_lock.host_build_lock(lock, operation="outer-owner"):
                    handoff_env, pass_fds = build_lock.active_lock_handoff()
                    env = dict(os.environ, PYTHONPATH=str(LAB), **handoff_env)
                    result = subprocess.run(
                        [sys.executable, str(child_script), str(lock), "1"],
                        env=env,
                        pass_fds=pass_fds,
                        text=True,
                        capture_output=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                    self.assertIn("child-shared", result.stdout)
                    self.assertEqual(json.loads(lock.read_text())["status"], "held")

    def test_invalid_inherited_descriptor_refuses_instead_of_silently_dropping_handoff(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            code = "import build_lock,sys; from pathlib import Path; build_lock.HOST_BUILD_LOCK=Path(sys.argv[1]); build_lock.active_lock_handoff()"
            env = dict(os.environ, PYTHONPATH=str(LAB), ROR2LAB_UNITY_BUILD_LOCK_FD="987654")
            result = subprocess.run(
                [sys.executable, "-c", code, str(lock)],
                env=env,
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid inherited host Unity build lock descriptor", result.stderr)

    def test_stale_released_descriptor_refuses_handoff(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "unity-build.lock"
            with build_lock.host_build_lock(lock, operation="prior-owner"):
                pass
            fd = os.open(lock, os.O_RDONLY)
            self.addCleanup(os.close, fd)
            code = "import build_lock,sys; from pathlib import Path; build_lock.HOST_BUILD_LOCK=Path(sys.argv[1]); build_lock.active_lock_handoff()"
            env = dict(os.environ, PYTHONPATH=str(LAB), ROR2LAB_UNITY_BUILD_LOCK_FD=str(fd))
            result = subprocess.run(
                [sys.executable, "-c", code, str(lock)],
                env=env,
                pass_fds=(fd,),
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no active owner receipt", result.stderr)


if __name__ == "__main__":
    unittest.main()
