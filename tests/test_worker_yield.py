from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/worker-yield.py"
SPEC = importlib.util.spec_from_file_location("worker_yield", SCRIPT)
worker_yield = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker_yield
SPEC.loader.exec_module(worker_yield)

NOW = datetime(2026, 11, 27, 21, 0, tzinfo=UTC)


def turn(tokens):
    usage = {"input_tokens": tokens, "cached_input_tokens": 0, "output_tokens": 0}
    return json.dumps({"type": "turn.completed", "usage": usage})


class WorkerYieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ("logs", "status", "park"):
            (self.root / folder).mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def log(self, workstream, stamp, lines):
        path = self.root / "logs" / f"{workstream}-{stamp}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        moment = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()
        os.utime(path, (moment, moment))

    def status(self, workstream, lines):
        (self.root / "status" / f"{workstream}.md").write_text("\n".join(lines) + "\n")

    def test_verdicts_follow_cost_per_merged_pr(self):
        self.log("cheap", "20261127T100000Z", [turn(6_000_000)])
        self.log("steady", "20261127T100000Z", [turn(8_000_000)])
        self.log("costly", "20261127T100000Z", [turn(30_000_000)])
        self.log("idle", "20261127T100000Z", [turn(7_000_000)])
        self.log("starter", "20261127T100000Z", [turn(1_000_000)])
        self.status("cheap", ["2026-11-27T11:00:00Z MERGED PR #10", "2026-11-27T12:00:00Z DONE PR #11"])
        self.status("steady", ["2026-11-27T11:00:00Z merged #12", "2026-11-27T12:00:00Z merged #13"])
        self.status(
            "costly",
            ["2026-11-27T11:00:00Z #14 merged"] + [f"2026-11-27T12:0{i}:00Z ESCALATE: push failed" for i in range(5)],
        )
        # A PR named only by the orchestrator, or not merged, is never credited.
        self.status("idle", ["2026-11-27T11:00:00Z orchestrator: merged #15", "2026-11-27T12:00:00Z MERGED PR #99"])
        merged = {str(n): ("2026-11-27", 100) for n in range(10, 16)}

        text, actionable = worker_yield.report(self.root, 3, merged=merged, now=NOW)

        rows = {
            line.split(" | ")[0][2:]: line.rsplit(" | ", 2)[-1].rstrip(" |")
            for line in text.splitlines()
            if line.startswith("| ") and "Verdict" not in line and "---" not in line and not line.startswith("| 2026")
        }
        self.assertEqual(rows["cheap"], "KEEP")
        self.assertEqual(rows["steady"], "KEEP")
        self.assertEqual(rows["costly"], "PARK")
        self.assertEqual(rows["idle"], "PARK")
        self.assertEqual(rows["starter"], "NEW")
        self.assertEqual(actionable, ["costly", "idle"])

    def test_parked_workers_are_not_actionable_and_quota_ceiling_is_reported(self):
        self.log("idle", "20261126T100000Z", [turn(40_000_000)])
        self.log("idle", "20261127T100000Z", [turn(90_000_000), '{"type":"turn.failed","error":{"message":"You hit your usage limit."}}'])
        (self.root / "park" / "idle").touch()

        text, actionable = worker_yield.report(self.root, 3, merged={}, now=NOW)

        self.assertEqual(actionable, [])
        self.assertIn("| idle | parked |", text)
        self.assertIn("Quota: 1 turn(s) failed on the usage limit", text)
        self.assertIn("Set budget-daily", text)

    def test_budget_lists_workers_to_park_worst_cost_first(self):
        self.log("cheap", "20261127T100000Z", [turn(30_000_000)])
        self.log("dear", "20261127T100000Z", [turn(30_000_000)])
        self.status("cheap", [f"2026-11-27T11:0{i}:00Z MERGED PR #{20 + i}" for i in range(6)])
        self.status("dear", ["2026-11-27T11:00:00Z MERGED PR #30"])
        (self.root / "budget-daily").write_text("45\n")
        merged = {str(n): ("2026-11-27", 10) for n in [20, 21, 22, 23, 24, 25, 30]}

        text, _ = worker_yield.report(self.root, 3, merged=merged, now=NOW)

        self.assertIn("Over budget: active workers spent 60M in the last 24 h against 45M. Park, worst cost per PR first: dear.", text)

    def test_device_contention_is_flagged(self):
        lines = [f"2026-11-27T1{i}:00:00Z dispatcher: granted dev1 to worker{i}" for i in range(4)]
        (self.root / "status" / "budget.log").write_text("\n".join(lines) + "\n")

        text, _ = worker_yield.report(self.root, 3, merged={}, now=NOW)

        self.assertIn("Device-bound: 4 unparked workers took grants on 1 device(s)", text)

    def test_window_excludes_old_logs_and_status(self):
        self.log("old", "20261120T100000Z", [turn(50_000_000)])
        self.status("old", ["2026-11-20T10:00:00Z MERGED PR #10"])

        text, actionable = worker_yield.report(self.root, 3, merged={"10": ("2026-11-20", 5)}, now=NOW)

        self.assertNotIn("| old |", text)
        self.assertEqual(actionable, [])


if __name__ == "__main__":
    unittest.main()
