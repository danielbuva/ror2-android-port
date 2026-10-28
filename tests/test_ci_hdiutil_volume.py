"""Host-only tests for bounded optional hdiutil setup and uncertain attach cleanup."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "ci-hdiutil-volume.py"
CI_LOCAL = ROOT / "scripts" / "ci-local.sh"


class HdiutilVolumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ci-hdiutil-test-")
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        fake = self.bin / "hdiutil"
        fake.write_text(
            "#!/bin/sh\n"
            'printf \'%s\\n\' "$*" >> "$HDIUTIL_LOG"\n'
            'phase="$1"\n'
            'if [ "$phase" = create ]; then\n'
            '  case "$HDIUTIL_MODE" in\n'
            '    create-timeout) printf \'%s\' "$$" > "$CHILD_PID"; exec sleep 30 ;;\n'
            "    create-fail) exit 17 ;;\n"
            "  esac\n"
            "fi\n"
            'if [ "$phase" = attach ]; then\n'
            "  shift\n"
            "  mount=''\n"
            "  while [ $# -gt 0 ]; do\n"
            '    if [ "$1" = -mountpoint ]; then shift; mount="$1"; break; fi\n'
            "    shift\n"
            "  done\n"
            '  mkdir -p "$mount"\n'
            "  printf 'preserve' > \"$mount/mounted-sentinel\"\n"
            '  case "$HDIUTIL_MODE" in\n'
            '    attach-timeout) printf \'%s\' "$$" > "$CHILD_PID"; exec sleep 30 ;;\n'
            "    attach-fail) exit 19 ;;\n"
            "  esac\n"
            "fi\n"
        )
        fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(
            PATH=str(self.bin) + os.pathsep + self.env["PATH"],
            HDIUTIL_LOG=str(self.log),
            CHILD_PID=str(self.root / "child.pid"),
        )
        self.image = self.root / "volume.sparseimage"
        self.mount = self.root / "mount"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_helper(self, mode: str, timeout: float = 1.0) -> tuple[subprocess.CompletedProcess[str], float]:
        self.env["HDIUTIL_MODE"] = mode
        started = time.monotonic()
        result = subprocess.run(
            ["python3", str(HELPER), str(timeout), str(self.image), str(self.mount)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result, time.monotonic() - started

    def assert_child_was_stopped(self) -> None:
        pid = int((self.root / "child.pid").read_text())
        time.sleep(0.1)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_create_timeout_reaps_own_cli_and_falls_back_before_attach(self) -> None:
        result, elapsed = self.run_helper("create-timeout")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertLess(elapsed, 6)
        self.assertIn("create timed out", result.stderr)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ["create"])
        self.assert_child_was_stopped()

    def test_attach_timeout_reaps_cli_and_marks_mount_state_uncertain(self) -> None:
        result, elapsed = self.run_helper("attach-timeout")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertLess(elapsed, 6)
        self.assertIn("mount state is uncertain", result.stderr)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ["create", "attach"])
        self.assertTrue((self.mount / "mounted-sentinel").is_file())
        self.assert_child_was_stopped()

    def test_success_preserves_exact_create_and_attach_arguments(self) -> None:
        result, _ = self.run_helper("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertEqual(commands[0], f"create -size 4g -fs Case-sensitive APFS -volname ci-local -type SPARSE {self.image} -quiet")
        self.assertEqual(commands[1], f"attach {self.image} -mountpoint {self.mount} -nobrowse -quiet")

    def test_nonzero_setup_failures_keep_existing_fallback_result(self) -> None:
        result, _ = self.run_helper("create-fail")
        self.assertEqual(result.returncode, 1)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ["create"])
        self.log.unlink()
        result, _ = self.run_helper("attach-fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("attach failed (19)", result.stderr)

    def test_ci_cleanup_preserves_mount_after_uncertain_attach_timeout(self) -> None:
        # Full script fixture: stub only the setup helper's return as timeout-after-mount;
        # the dedicated helper tests above exercise actual timeout/kill/wait behavior.
        repo = self.root / "source"
        scripts = repo / "scripts"
        tests = repo / "tests"
        scripts.mkdir(parents=True)
        tests.mkdir()
        shutil.copy2(CI_LOCAL, scripts / "ci-local.sh")
        shutil.copy2(ROOT / "scripts/ci-local-cache.py", scripts / "ci-local-cache.py")
        (repo / "tools").mkdir()
        (repo / "tools/lab-requirements.txt").write_text("")
        (scripts / "ci-hdiutil-volume.py").write_text(
            "import pathlib, sys\n"
            "pathlib.Path(sys.argv[2]).write_bytes(b'image')\n"
            "mount=pathlib.Path(sys.argv[3]); mount.mkdir(parents=True)\n"
            "(mount/'mounted-sentinel').write_text('keep')\n"
            "raise SystemExit(2)\n"
        )
        for name in ("ruff-committed", "audit-public", "journal-index", "readme-actions"):
            (scripts / f"{name}.py").write_text("print('fixture check passed')\n")
        (tests / "__init__.py").write_text("")
        (tests / "test_fixture.py").write_text("import unittest\nclass Fixture(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
        fakebin = self.root / "full-bin"
        fakebin.mkdir()
        hdiutil = fakebin / "hdiutil"
        hdiutil.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$HDIUTIL_LOG"\nexit 23\n')
        hdiutil.chmod(0o755)
        uname = fakebin / "uname"
        uname.write_text('#!/bin/sh\nprintf "Darwin\\n"\n')
        uname.chmod(0o755)
        sandbox = fakebin / "sandbox-exec"
        sandbox.write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
        sandbox.chmod(0o755)
        env = os.environ.copy()
        env.update(
            PATH=str(fakebin) + os.pathsep + env["PATH"],
            TMPDIR=str(self.root),
            HDIUTIL_LOG=str(self.root / "cleanup-hdiutil.log"),
            GIT_AUTHOR_NAME="CI fixture",
            GIT_COMMITTER_NAME="CI fixture",
            GIT_AUTHOR_EMAIL="ci-fixture",
            GIT_COMMITTER_EMAIL="ci-fixture",
        )
        for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
            env.pop(name, None)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
        subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True, env=env)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True, env=env).strip()
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", head], cwd=repo, check=True, env=env)
        hook_env = env | {
            "GIT_DIR": str(repo / ".git"),
            "GIT_WORK_TREE": str(repo),
            "GIT_INDEX_FILE": str(repo / ".git/index"),
        }
        result = subprocess.run(
            ["bash", str(scripts / "ci-local.sh"), head, head],
            cwd=repo,
            env=hook_env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cleanup_dir = repo / ".git" / "ci-cleanup"
        cleanup_logs = []
        deadline = time.monotonic() + 5
        expected_cleanup = "attach timed out with uncertain mount state; preserving"
        while time.monotonic() < deadline:
            cleanup_logs = list(cleanup_dir.glob("*.log")) if cleanup_dir.exists() else []
            # The trap starts in the background. File creation is not completion.
            if len(cleanup_logs) == 1 and expected_cleanup in cleanup_logs[0].read_text():
                break
            time.sleep(0.02)
        self.assertEqual(len(cleanup_logs), 1, "cleanup trap did not record its outcome")
        self.assertIn("attach timed out with uncertain mount state; preserving", cleanup_logs[0].read_text())
        scratch_dirs = [p for p in self.root.glob("ci-local.*") if p.is_dir()]
        self.assertEqual(len(scratch_dirs), 1, result.stdout + result.stderr)
        scratch = scratch_dirs[0]
        self.assertTrue((scratch / "volume.sparseimage").is_file())
        self.assertTrue((scratch / "case-sensitive" / "mounted-sentinel").is_file())
        self.assertFalse((self.root / "cleanup-hdiutil.log").exists(), "cleanup must not detach after an uncertain attach timeout")


if __name__ == "__main__":
    unittest.main(verbosity=2)
