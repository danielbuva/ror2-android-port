"""Host accounting uses real children and records failed stages too."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/profile_stage.py"
SPEC = importlib.util.spec_from_file_location("profile_stage", SCRIPT)
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class ConverterProfileStageTests(unittest.TestCase):
    def test_child_accounting_and_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, evidence = root / "workspace", root / "evidence"
            workspace.mkdir()
            (workspace / "input").write_bytes(b"original")
            (workspace / "alias").symlink_to(workspace / "input")
            code = "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'x'*1048576); print('complete')"
            row = PROFILE.measure("pack", [sys.executable, "-c", code, str(workspace / "output")], workspace, evidence)
            self.assertEqual(row["exit_code"], 0)
            self.assertEqual(row["initial_workspace_logical_bytes"], 8)
            self.assertEqual(row["final_workspace_logical_bytes"], 1048584)
            self.assertGreaterEqual(row["peak_workspace_logical_bytes"], 1048584)
            self.assertGreater(row["peak_rss_bytes"], 0)
            self.assertGreater(row["wall_seconds"], 0)
            self.assertGreater(row["user_seconds"] + row["system_seconds"], 0)
            self.assertEqual(json.loads((evidence / "pack.json").read_text()), row)
            self.assertEqual((evidence / "pack.log").read_text(), "complete\n")

    def test_failed_command_records_and_extends_table(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            table = root / "per-stage.md"
            table.write_text("| Stage | Wall |\n| --- | --- |\n\nLimits retained.\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--stage",
                    "sign",
                    "--workspace",
                    str(root),
                    "--evidence",
                    str(root / "receipts"),
                    "--table",
                    str(table),
                    "--",
                    sys.executable,
                    "-c",
                    "print('failed'); raise SystemExit(7)",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 7, result.stderr)
            row = json.loads((root / "receipts/sign.json").read_text())
            self.assertEqual(row["exit_code"], 7)
            self.assertIn(PROFILE.table_row(row) + "\n\nLimits retained.", table.read_text())
            self.assertEqual((root / "receipts/sign.log").read_text(), "failed\n")


if __name__ == "__main__":
    unittest.main()
