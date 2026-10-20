"""CI's Ruff step on committed, unpushed Python files (scripts/ruff-committed.py).

Only committed content is checked, so another session's uncommitted work in the shared
checkout never fails this test. The tracked pre-push hook runs the same check.
"""

import importlib.util
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ruff_committed", ROOT / "scripts/ruff-committed.py")
ruff_committed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ruff_committed)


class RuffCommittedTests(unittest.TestCase):
    def test_unpushed_commits_pass_ci_ruff_step(self):
        if subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", "origin/main"], capture_output=True).returncode:
            self.skipTest("no origin/main reference (a fresh CI clone runs its own Ruff step)")
        base = ruff_committed.git("merge-base", "origin/main", "HEAD").strip()
        code, message = ruff_committed.check(base, "HEAD")
        self.assertEqual(code, 0, message)


if __name__ == "__main__":
    unittest.main()
