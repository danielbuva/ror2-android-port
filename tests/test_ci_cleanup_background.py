"""Keep temporary CI filesystem cleanup separate from verification status."""

from pathlib import Path
import shutil
import subprocess
import unittest


class CiCleanupBackgroundTests(unittest.TestCase):
    def test_blocked_detach_does_not_hold_exit_or_remove_mounted_scratch(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("Bash is unavailable")
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [bash, str(root / "tests/test_ci_cleanup_background.sh"), str(root / "scripts/ci-local.sh")],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mounted scratch preservation passed", result.stdout)
