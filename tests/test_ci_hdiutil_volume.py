"""Host-only tests for bounded optional hdiutil setup and uncertain attach cleanup."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def run_helper(self, mode: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        self.env["HDIUTIL_MODE"] = mode
        return subprocess.run(
            ["python3", str(HELPER), str(timeout), str(self.image), str(self.mount)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )

    def assert_child_was_stopped(self) -> None:
        pid = int((self.root / "child.pid").read_text())
        # subprocess.run has killed and waited for the child before returning.
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_create_timeout_reaps_own_cli_and_falls_back_before_attach(self) -> None:
        result = self.run_helper("create-timeout", timeout=1.0)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("create timed out", result.stderr)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ["create"])
        self.assert_child_was_stopped()

    def test_attach_timeout_reaps_cli_and_marks_mount_state_uncertain(self) -> None:
        result = self.run_helper("attach-timeout", timeout=1.0)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("mount state is uncertain", result.stderr)
        self.assertTrue((self.root / "attach.pending").is_file())
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ["create", "attach"])
        self.assertTrue((self.mount / "mounted-sentinel").is_file())
        self.assert_child_was_stopped()

    def test_success_preserves_exact_create_and_attach_arguments(self) -> None:
        result = self.run_helper("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "attach.pending").exists())
        commands = self.log.read_text().splitlines()
        self.assertEqual(commands[0], f"create -size 4g -fs Case-sensitive APFS -volname ci-local -type SPARSE {self.image} -quiet")
        self.assertEqual(commands[1], f"attach {self.image} -mountpoint {self.mount} -nobrowse -quiet")

    def test_nonzero_setup_failures_keep_existing_fallback_result(self) -> None:
        spec = importlib.util.spec_from_file_location("ci_hdiutil_volume", HELPER)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        # Fixed child exit results distinguish nonzero failure from timeout without
        # racing shell startup/mkdir against the real timeout tests' short deadline.
        for statuses, phases, message in (
            ([17], ["create"], "create failed (17)"),
            ([0, 19], ["create", "attach"], "attach failed (19)"),
        ):
            with self.subTest(phases=phases):
                results = [subprocess.CompletedProcess([], status) for status in statuses]
                stderr = io.StringIO()
                with (
                    mock.patch.object(helper.subprocess, "run", side_effect=results) as run,
                    mock.patch.object(sys, "argv", [str(HELPER), "30", str(self.image), str(self.mount)]),
                    mock.patch.object(sys, "stderr", stderr),
                ):
                    self.assertEqual(helper.main(), 1)
                self.assertEqual([call.args[0][1] for call in run.call_args_list], phases)
                self.assertIn(message, stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
