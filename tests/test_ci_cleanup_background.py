"""Cleanup is now synchronous and bounded; failed mount reconciliation preserves."""

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("ci_scratch", Path(__file__).resolve().parents[1] / "scripts/ci-scratch.py")
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class CleanupTimeoutTests(unittest.TestCase):
    def test_inventory_and_detach_have_finite_timeouts(self):
        with mock.patch.object(cleanup.subprocess, "run", side_effect=subprocess.TimeoutExpired("hdiutil", 30)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                cleanup.devices(Path("/synthetic/volume.sparseimage"))
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        with mock.patch.object(cleanup, "devices", return_value={"/dev/disk71"}):
            with mock.patch.object(cleanup.subprocess, "run", side_effect=subprocess.TimeoutExpired("hdiutil", 30)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    cleanup.detach(Path("/synthetic/volume.sparseimage"))
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
