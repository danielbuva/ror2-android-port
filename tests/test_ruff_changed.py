"""Run CI's Ruff gate locally on every Python file that differs from origin/main.

CI checks the Python files a push changes (`.github/workflows/host-tests.yml`); without this,
an unformatted file only fails after it is pushed. Run `ruff format <file>` (the pinned
ruff==0.11.13 from tools/lab-requirements.txt) and `ruff check <file>` to fix a failure.
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def ruff():
    candidate = Path(sys.executable).with_name("ruff")
    return str(candidate) if candidate.is_file() else shutil.which("ruff")


class RuffChangedFilesTests(unittest.TestCase):
    def test_changed_python_files_pass_ci_ruff_gate(self):
        if git("rev-parse", "--verify", "--quiet", "origin/main").returncode != 0:
            self.skipTest("no origin/main reference (fresh CI clone runs its own Ruff step)")
        tool = ruff()
        self.assertIsNotNone(tool, "ruff is missing: uv pip install --python .local/lab-venv/bin/python ruff==0.11.13")
        changed = git("diff", "--name-only", "--diff-filter=ACMR", "origin/main", "--", "*.py").stdout.split()
        untracked = git("ls-files", "--others", "--exclude-standard", "--", "*.py").stdout.split()
        files = sorted({path for path in changed + untracked if (ROOT / path).is_file()})
        if not files:
            return
        for args in (["check"], ["format", "--check"]):
            result = subprocess.run([tool, *args, "--", *files], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, "ruff " + " ".join(args) + " fails (CI will too):\n" + result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
