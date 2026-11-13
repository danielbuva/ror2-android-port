"""Host accounting uses real children and records failed stages too."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools/phone-build/profile_stage.py"
SPEC = importlib.util.spec_from_file_location("profile_stage", SCRIPT)
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class ConverterProfileStageTests(unittest.TestCase):
    def test_detach_uses_same_tracked_profiler_and_terminal_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            done = root / "terminal.json"
            arguments = [
                str(SCRIPT),
                "--detach",
                "--stage",
                "full",
                "--workspace",
                str(root),
                "--evidence",
                str(root),
                "--done-file",
                str(done),
                "--progress-file",
                str(root / "progress.json"),
                "--",
                sys.executable,
                "-c",
                "print('ok')",
            ]
            with patch.object(sys, "argv", arguments), patch.object(PROFILE.subprocess, "Popen") as launch, patch.object(PROFILE, "measure") as measure:
                launch.return_value.pid = 123
                self.assertEqual(PROFILE.main(), 0)
            command = launch.call_args.args[0]
            self.assertEqual(command[:2], [sys.executable, str(SCRIPT)])
            self.assertNotIn("--detach", command)
            self.assertEqual(command[command.index("--done-file") + 1], str(done))
            self.assertEqual(command[command.index("--progress-file") + 1], str((root / "progress.json").resolve()))
            self.assertEqual(command[-4:], ["--", sys.executable, "-c", "print('ok')"])
            self.assertTrue(launch.call_args.kwargs["start_new_session"])
            self.assertEqual(launch.call_args.kwargs["stdin"], subprocess.DEVNULL)
            measure.assert_not_called()
            self.assertFalse(done.exists())
            self.assertTrue((root / "full.supervisor.log").exists())

    def test_process_tree_counts_only_simultaneous_descendants(self):
        rows = "10 1 100\n11 10 200\n12 11 300\n13 1 9000\n"
        self.assertEqual(PROFILE.process_tree_rss(10, rows), 600 * 1024)
        self.assertEqual(PROFILE.process_tree_rss(11, rows), 500 * 1024)
        self.assertEqual(PROFILE.process_tree_rss(99, rows), 0)

    def test_failed_sampling_is_recorded_instead_of_accepting_zero_rss(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(PROFILE, "process_tree_rss", side_effect=RuntimeError("sample failed")):
                row = PROFILE.measure("sample", [sys.executable, "-c", "import time; time.sleep(0.05)"], root, root)
            self.assertEqual(row["measurement_errors"], ["sample failed"])

    def test_samples_join_current_record_progress_to_simultaneous_rss(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            progress = root / "progress.json"
            progress.write_text(json.dumps(dict(phase="records", records_done=2048, records_total=10000)))
            with patch.object(PROFILE, "process_tree_rss", return_value=123456):
                row = PROFILE.measure("sample", [sys.executable, "-c", "import time; time.sleep(0.05)"], root, root, progress_file=progress)
            samples = [json.loads(line) for line in (root / "sample.samples.jsonl").read_text().splitlines()]
            self.assertTrue(samples)
            self.assertEqual(samples[0]["process_tree_rss_bytes"], 123456)
            self.assertEqual((samples[0]["phase"], samples[0]["records_done"], samples[0]["records_total"]), ("records", 2048, 10000))
            self.assertGreaterEqual(samples[0]["seconds"], 0)
            self.assertEqual(row["measurement_errors"], [])

    def test_terminal_is_written_after_cleanup_for_command_and_launch_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                done = root / "terminal.json"
                argv = ["profile_stage", "--stage", "pack", "--workspace", str(root), "--evidence", str(root), "--done-file", str(done), "--", "command"]

                def cleanup(*args, **kwargs):
                    self.assertFalse(done.exists())
                    return subprocess.CompletedProcess(args[0], 0)

                result = {"exit_code": 7}
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(PROFILE, "measure", side_effect=FileNotFoundError("missing") if failure else None, return_value=result),
                ):
                    with patch.object(PROFILE.subprocess, "run", side_effect=cleanup):
                        if failure:
                            with self.assertRaises(FileNotFoundError):
                                PROFILE.main()
                        else:
                            self.assertEqual(PROFILE.main(), 7)
                receipt = json.loads(done.read_text())
                self.assertFalse(receipt["success"])
                self.assertEqual(receipt["cleanup_exit_code"], 0)
                if failure:
                    self.assertEqual(receipt["error"], "missing")

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
