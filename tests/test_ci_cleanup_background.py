"""Keep temporary CI filesystem cleanup separate from verification status."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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

    def test_linux_removes_scratch_before_exit_without_hdiutil(self):
        bash = shutil.which("bash")
        rm = shutil.which("rm")
        if not bash or not rm:
            self.skipTest("Bash or rm is unavailable")
        source = Path(__file__).resolve().parents[1] / "scripts/ci-local.sh"
        cleanup = "cleanup() {" + source.read_text().split("cleanup() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
        with tempfile.TemporaryDirectory(prefix="ci-cleanup-linux-") as temporary:
            root = Path(temporary)
            scratch = root / "scratch"
            # Even a directory bearing the macOS mountpoint's name must not invoke
            # hdiutil on Linux, which never creates or attaches a volume.
            (scratch / "case-sensitive").mkdir(parents=True)
            (scratch / "sentinel").write_text("fixture")
            fakebin = root / "bin"
            fakebin.mkdir()
            for name, content in {
                "uname": '#!/bin/sh\nprintf "Linux\\n"\n',
                "rm": f'#!/bin/sh\nsleep 0.2\nexec "{rm}" "$@"\n',
                "hdiutil": '#!/bin/sh\ntouch "$HDIUTIL_CALLED"\nexit 1\n',
            }.items():
                program = fakebin / name
                program.write_text(content)
                program.chmod(0o755)
            runner = root / "runner.sh"
            runner.write_text(
                'set -euo pipefail\nscratch="$FIXTURE_SCRATCH"\nvolume="$scratch/case-sensitive"\n'
                'cleanup_log="$FIXTURE_LOG"\n' + cleanup + "trap cleanup EXIT\nexit 37\n"
            )
            env = os.environ | {
                "PATH": str(fakebin) + os.pathsep + os.environ["PATH"],
                "FIXTURE_SCRATCH": str(scratch),
                "FIXTURE_LOG": str(root / "cleanup.log"),
                "HDIUTIL_CALLED": str(root / "hdiutil-called"),
            }
            result = subprocess.run([bash, str(runner)], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
            self.assertFalse(scratch.exists(), "Linux cleanup returned before its delayed rm finished")
            self.assertFalse((root / "hdiutil-called").exists())
            self.assertIn("cleanup: scratch removed", (root / "cleanup.log").read_text())
