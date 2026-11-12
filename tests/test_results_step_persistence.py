"""Execute sparse results markers with the production first-failure checkpoint."""

from pathlib import Path
import unittest

from test_native_commerce_release_order import braced_block
from test_retained_catalog_dependencies import execute_host

ROOT = Path(__file__).resolve().parents[1]


class ResultsStepPersistenceTests(unittest.TestCase):
    def test_completion_and_failed_check_retain_latest_step(self):
        results = (ROOT / "tools/unity/runtime/progression/IntegratedResultsBoundary.cs").read_text()
        session = (ROOT / "tools/unity/runtime/session/PortSession.cs").read_text()
        fixture = (ROOT / "tests/fixtures/results_step_persistence_host.cs").read_text()
        fixture = fixture.replace("// RESULTS_STEP", braced_block(results, "void ResultsStep(string value)"))
        fixture = fixture.replace("// CHECK", braced_block(session, "void Check(bool value, string message)"))
        result = execute_host(fixture, "results-step-persistence")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "results step persistence PASS")


if __name__ == "__main__":
    unittest.main()
