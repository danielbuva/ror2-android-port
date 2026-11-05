"""Final native-consumer ordering with authored events, never game assemblies/data."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_portable_diagnostic_input import extract_method


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/progression/IntegratedResultsBoundary.cs"
EDITOR = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")) / "MonoBleedingEdge"
DECLARATIONS = ("void ReleaseResultsEvents()", "void FinishResultsStatistics()", "public void Dispose()")


class IntegratedResultsStatisticsSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()
        self.finish = extract_method(self.source, DECLARATIONS[1])
        self.dispose = extract_method(self.source, DECLARATIONS[2])

    def test_final_consumer_runs_after_detach_before_any_context_teardown(self):
        self.assertLess(self.finish.index("resultsStatsFixed = null;"), self.finish.index("ReleaseResultsEvents();"))
        self.assertLess(self.finish.index("ReleaseResultsEvents();"), self.finish.index("resultsStatsProcess();"))
        self.assertLess(self.finish.index("resultsStatsProcess();"), self.finish.index("resultsStatsProcess = null;"))
        self.assertEqual(self.dispose.count("FinishResultsStatistics();"), 1)
        for teardown in ("coordinator.CleanupAndroidProfile();", "PlatformSystems.saveSystem =", 'Call(coordinator.resultsStats, "OnDestroy")'):
            self.assertLess(self.dispose.index("FinishResultsStatistics();"), self.dispose.index(teardown))

    def test_partial_setup_is_allowed_and_failure_is_not_suppressed(self):
        self.assertIn("if (resultsStatsProcess == null)", self.finish)
        self.assertNotIn("catch", self.finish)
        self.assertNotIn("finally", self.finish)
        self.assertNotIn("catch", self.dispose)

    def test_abandon_does_not_manufacture_tick_result_or_discard_events(self):
        for forbidden in (".Clear(", ".Dequeue(", "resultsStatsFixed();", "ObserveIntegratedResults(", "PersistResult(", "BeginGameOver("):
            self.assertNotIn(forbidden, self.finish)
        self.assertNotIn("PersistResult(", self.dispose)
        self.assertNotIn("BeginGameOver(", self.dispose)
        self.assertIn('statManager.GetMethod("ForceUpdate", BindingFlags.Public | BindingFlags.Static)', self.source)

    def test_owned_callback_removal_preserves_prior_and_foreign_subscribers(self):
        release = extract_method(self.source, DECLARATIONS[0])
        self.assertIn("handler.Method.DeclaringType == stats && !priorHandlers.Contains(handler)", release)
        self.assertIn("current = Delegate.Remove(current, handler);", release)
        self.assertNotIn("entry.Key.SetValue(null, entry.Value)", release)


class IntegratedResultsStatisticsHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = EDITOR / "bin/mono"
        compiler = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not cls.mono.is_file() or not compiler.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="results-statistics-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = SOURCE.read_text()
        methods = "\n".join(extract_method(source, declaration) for declaration in DECLARATIONS)
        production = directory / "Production.cs"
        production.write_text(
            "using System; using System.Linq; using System.Reflection; using RoR2.Stats;\npartial class ResultsHarness {\n" + methods + "\n}\n"
        )
        cls.exe = directory / "statistics.exe"
        compiled = subprocess.run(
            [
                str(cls.mono),
                str(compiler),
                "-nologo",
                "-langversion:9",
                "-out:" + str(cls.exe),
                str(production),
                str(ROOT / "tests/fixtures/IntegratedResultsStatisticsHost.cs"),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def case(self, name):
        result = subprocess.run([str(self.mono), str(self.exe), name], text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_late_events_use_native_consumer_before_context_teardown(self):
        self.case("pending")

    def test_successful_repeat_never_reprocesses_or_adds_a_fixed_tick(self):
        self.case("repeat")

    def test_partial_setup_without_consumer_still_releases_owned_handlers(self):
        self.case("partial")

    def test_failed_consumer_retains_context_and_pending_events_for_retry(self):
        self.case("failure")


if __name__ == "__main__":
    unittest.main()
