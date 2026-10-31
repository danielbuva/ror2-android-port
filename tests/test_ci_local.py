"""The push hook's Git environment must not redirect fresh-clone operations."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class CiLocalHookEnvironmentTests(unittest.TestCase):
    def test_hook_repository_variables_do_not_leak_into_clone(self):
        source = Path(__file__).resolve().parents[1] / "scripts/ci-local.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "source"
            scripts = repo / "scripts"
            scripts.mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "tests/__init__.py").write_text("")
            (repo / "tests/test_fixture.py").write_text(
                "import unittest\nclass Fixture(unittest.TestCase):\n    def test_fixture(self):\n        self.assertTrue(True)\n"
            )
            shutil.copy2(source, scripts / "ci-local.sh")
            shutil.copy2(source.parents[1] / "scripts/ci-local-cache.py", scripts / "ci-local-cache.py")
            (repo / "tools").mkdir()
            (repo / "tools/lab-requirements.txt").write_text("")
            shutil.copy2(source.parents[1] / "scripts/ci-hdiutil-volume.py", scripts / "ci-hdiutil-volume.py")
            for name in ("ruff-committed", "audit-public", "journal-index", "readme-actions"):
                (scripts / f"{name}.py").write_text("print('fixture check passed')\n")
            env = os.environ.copy()
            for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
                env.pop(name, None)
            env.update(
                GIT_AUTHOR_NAME="CI fixture",
                GIT_COMMITTER_NAME="CI fixture",
                GIT_AUTHOR_EMAIL="ci-fixture",
                GIT_COMMITTER_EMAIL="ci-fixture",
            )

            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], env=env, stderr=subprocess.STDOUT).decode().strip()

            git("init", "-q")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
            head = git("rev-parse", "HEAD")
            git("update-ref", "refs/remotes/origin/main", head)
            fakebin = root / "bin"
            fakebin.mkdir()
            for name, content in {
                "hdiutil": "#!/bin/sh\nexit 1\n",
                "sandbox-exec": '#!/bin/sh\nshift 2\nexec "$@"\n',
            }.items():
                target = fakebin / name
                target.write_text(content)
                target.chmod(0o755)
            hook_env = env | {
                "GIT_DIR": str(repo / ".git"),
                "GIT_WORK_TREE": str(repo),
                "GIT_INDEX_FILE": str(repo / ".git/index"),
                "PATH": str(fakebin) + os.pathsep + env["PATH"],
                "TMPDIR": str(root),
            }
            # The checks must come from the commit, not another agent's current edits.
            (scripts / "audit-public.py").write_text("raise SystemExit('uncommitted checker')\n")
            result = subprocess.run(
                ["bash", str(scripts / "ci-local.sh"), head, head],
                cwd=repo,
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("all CI steps pass", result.stdout)
            self.assertEqual(result.stdout.count("fixture check passed"), 4)
            self.assertIn("dependency environment created", result.stderr)
            second = subprocess.run(
                ["bash", str(scripts / "ci-local.sh"), head, head],
                cwd=repo,
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("dependency environment reused", second.stderr)
            self.assertIn("source objects reused", second.stderr)
            self.assertEqual(second.stdout.count("fixture check passed"), 4)
            self.assertIn("Ran 1 test", second.stderr)
            self.assertEqual(git("status", "--porcelain"), "M scripts/audit-public.py")
            # A present runner owns the full suite. Its failure must never fall back to
            # serial discovery and turn a failing run into success.
            (scripts / "audit-public.py").write_text("print('fixture check passed')\n")
            (scripts / "host-tests.py").write_text("print('runner failure sentinel')\nraise SystemExit(19)\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "failing runner")
            failed_head = git("rev-parse", "HEAD")
            failure = subprocess.run(
                ["bash", str(scripts / "ci-local.sh"), failed_head, head],
                cwd=repo,
                env=hook_env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(failure.returncode, 19, failure.stdout + failure.stderr)
            self.assertIn("runner failure sentinel", failure.stdout)
            self.assertNotIn("all CI steps pass", failure.stdout)
            self.assertNotIn("Ran 1 test", failure.stderr)
