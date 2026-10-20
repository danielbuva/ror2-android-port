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
            self.assertEqual(git("status", "--porcelain"), "")
