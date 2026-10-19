"""Presentation build lock coverage; all editor/build work is mocked."""

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
import presentation


class PresentationBuildLockTests(unittest.TestCase):
    def test_host_lock_covers_staging_polling_and_result_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "coordination" / "unity-build.lock"
            phases = []
            code = (
                "from build_lock import host_build_lock\n"
                "import sys\n"
                "try:\n"
                " with host_build_lock(sys.argv[1], operation='competing-builder', timeout=0.12, poll_interval=0.01): pass\n"
                "except TimeoutError as error:\n"
                " print(str(error))\n"
                "else: raise SystemExit('competing builder acquired the lock')\n"
            )

            def mocked_lifecycle(*, stages=False, recovered=False):
                env = dict(os.environ, PYTHONPATH=str(LAB))
                for phase in ("staging", "polling", "result-publication"):
                    phases.append(phase)
                    result = subprocess.run(
                        [sys.executable, "-c", code, str(lock)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True,
                    )
                    self.assertIn('"operation": "presentation payload staging, build and receipt collection"', result.stdout)
                    self.assertIn('"status": "held"', result.stdout)
                return dict(success=True)

            with (
                patch.object(build_lock, "HOST_BUILD_LOCK", lock),
                patch.object(build_lock, "assert_build_unblocked"),
                patch.object(presentation, "_build_payload_locked", side_effect=mocked_lifecycle) as lifecycle,
            ):
                result = presentation.build_payload(stages=True)

            self.assertEqual(result, dict(success=True))
            self.assertEqual(phases, ["staging", "polling", "result-publication"])
            lifecycle.assert_called_once_with(stages=True, recovered=False)
            self.assertEqual(build_lock._read_receipt(lock)["status"], "released")


if __name__ == "__main__":
    unittest.main()
