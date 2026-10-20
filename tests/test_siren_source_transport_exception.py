"""Exercise the production Siren transport observer and reporting isolation."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def repository_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "recipe/runtime-sources.json").is_file():
            return parent
    raise AssertionError("repository root not found")


ROOT = repository_root()
SOURCE = Path(
    os.environ.get(
        "SIREN_SOURCE_ENTRY_SESSION",
        ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs",
    )
)
STAGE_SOURCE = Path(
    os.environ.get(
        "SIREN_INTEGRATED_STAGE_BOUNDARY",
        ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs",
    )
)
INPUT_SOURCE = Path(
    os.environ.get(
        "SIREN_NOVA_INPUT_BOUNDARY",
        ROOT / "tools/unity/runtime/input/NovaInputBoundary.cs",
    )
)
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")

FIXTURE = r"""
sealed class SequenceRoutine : IEnumerator
{
    readonly object[] values;
    int index = -1;
    public SequenceRoutine(params object[] values) { this.values = values; }
    public object Current { get { return values[index]; } }
    public bool MoveNext() { return ++index < values.Length; }
    public void Reset() { index = -1; }
}

sealed class ThrowingMoveNextRoutine : IEnumerator
{
    readonly Exception failure;
    public ThrowingMoveNextRoutine(Exception failure) { this.failure = failure; }
    public object Current { get { return null; } }
    public bool MoveNext() { throw failure; }
    public void Reset() { }
}

sealed class ThrowingCurrentRoutine : IEnumerator
{
    readonly Exception failure;
    bool yielded;
    public ThrowingCurrentRoutine(Exception failure) { this.failure = failure; }
    public object Current { get { throw failure; } }
    public bool MoveNext() { if (yielded) return false; yielded = true; return true; }
    public void Reset() { yielded = false; }
}

sealed class ThrowingResetRoutine : IEnumerator
{
    readonly Exception failure;
    public ThrowingResetRoutine(Exception failure) { this.failure = failure; }
    public object Current { get { return null; } }
    public bool MoveNext() { return false; }
    public void Reset() { throw failure; }
}

public static class SirenSourceTransportHarness
{
    static void Assert(bool value, string name) { if (!value) throw new Exception(name); }
    static SirenSourceEntryObservedRoutine Observer(IEnumerator inner, Action<string, string> boundary,
                                                      Action<string, Exception> failure)
    { return new SirenSourceEntryObservedRoutine(inner, "PopulateWholeStage", boundary, failure); }

    static Exception Catch(Action action)
    { try { action(); return null; } catch (Exception error) { return error; } }

    static void TestNormalForwarding()
    {
        var boundaries = new List<string>();
        var yielded = new List<string>();
        var normal = Observer(new SequenceRoutine("one", "two"),
            (operation, phase) => boundaries.Add(operation + ":" + phase),
            (operation, error) => { throw new Exception("unexpected failure callback"); });
        while (normal.MoveNext()) yielded.Add((string)normal.Current);
        Assert(yielded.Count == 2 && yielded[0] == "one" && yielded[1] == "two", "ordinary yields preserved");
        Assert(boundaries.Count == 2 && boundaries[0] == "PopulateWholeStage:entered" &&
            boundaries[1] == "PopulateWholeStage:returned", "ordinary enter/return callbacks ordered");
    }

    static void TestBoundaryCallbackFailuresAreIsolated()
    {
        foreach (string throwAt in new[] { "entered", "returned" })
        {
            var boundaryCalls = new List<string>();
            int failureCalls = 0;
            var wrapped = Observer(new SequenceRoutine("yield"), (operation, phase) =>
            {
                boundaryCalls.Add(operation + ":" + phase);
                if (phase == throwAt) throw new InvalidOperationException("reporting callback " + phase);
            }, (operation, error) => failureCalls++);
            Assert(wrapped.MoveNext(), "throwing " + throwAt + " callback must not suppress native MoveNext");
            Assert((string)wrapped.Current == "yield", "yield survives throwing " + throwAt + " callback");
            Assert(!wrapped.MoveNext(), "throwing return callback must preserve native completion");
            Assert(failureCalls == 0, "boundary reporting failure must not be labeled as native failure");
            Assert(boundaryCalls.Count == 2 && boundaryCalls[0] == "PopulateWholeStage:entered" &&
                boundaryCalls[1] == "PopulateWholeStage:returned", "both boundary callbacks are attempted");
        }
    }

    static void TestNativeFailuresKeepIdentityWhenFailureReporterThrows()
    {
        var moveFailure = new InvalidOperationException("native MoveNext");
        Exception recordedMove = null;
        var move = Observer(new ThrowingMoveNextRoutine(moveFailure), (o, p) => { }, (o, e) =>
        { recordedMove = e; throw new Exception("failure reporter MoveNext"); });
        Exception caughtMove = Catch(() => move.MoveNext());
        Assert(ReferenceEquals(recordedMove, moveFailure) && ReferenceEquals(caughtMove, moveFailure),
            "MoveNext original exception recorded and rethrown by identity");

        var currentFailure = new InvalidOperationException("native Current");
        Exception recordedCurrent = null;
        var current = Observer(new ThrowingCurrentRoutine(currentFailure), (o, p) => { }, (o, e) =>
        { recordedCurrent = e; throw new Exception("failure reporter Current"); });
        Assert(current.MoveNext(), "Current fixture advances before getter failure");
        Exception caughtCurrent = Catch(() => { var ignored = current.Current; });
        Assert(ReferenceEquals(recordedCurrent, currentFailure) && ReferenceEquals(caughtCurrent, currentFailure),
            "Current original exception recorded and rethrown by identity");

        var resetFailure = new InvalidOperationException("native Reset");
        Exception recordedReset = null;
        var reset = Observer(new ThrowingResetRoutine(resetFailure), (o, p) => { }, (o, e) =>
        { recordedReset = e; throw new Exception("failure reporter Reset"); });
        Exception caughtReset = Catch(() => reset.Reset());
        Assert(ReferenceEquals(recordedReset, resetFailure) && ReferenceEquals(caughtReset, resetFailure),
            "Reset original exception recorded and rethrown by identity");
    }

    public static void Main()
    {
        TestNormalForwarding();
        TestBoundaryCallbackFailuresAreIsolated();
        TestNativeFailuresKeepIdentityWhenFailureReporterThrows();

        var original = new InvalidOperationException("native SceneDirector.Start refusal");
        Exception recorded = null, caught = null;
        string firstFailure = null, firstPhase = null;
        var failing = Observer(new ThrowingMoveNextRoutine(original), (operation, phase) => { },
            (operation, error) =>
            {
                recorded = error;
                SirenSourceEntryFailureClassification.PreserveFirstFailure(
                    ref firstFailure, ref firstPhase,
                    "Siren source transport " + operation + " threw: " + error.Message,
                    "siren-transport-" + operation);
                throw new Exception("best-effort report save failed");
            });
        try { failing.MoveNext(); }
        catch (Exception error) { caught = error; }
        finally
        {
            Assert(ReferenceEquals(recorded, original), "original failure recorded before enclosing finally");
            SirenSourceEntryFailureClassification.PreserveFirstFailure(
                ref firstFailure, ref firstPhase,
                SirenSourceEntryFailureClassification.FailureMessage(false, false),
                SirenSourceEntryFailureClassification.FailurePhase(false, false));
        }
        Assert(ReferenceEquals(caught, original), "same exception object rethrown after reporter failure");
        Assert(firstFailure == "Siren source transport PopulateWholeStage threw: native SceneDirector.Start refusal" &&
            firstPhase == "siren-transport-PopulateWholeStage", "later finalizer preserves the first failure");
        Console.WriteLine("siren-source-transport-observer-passed");
    }
}
"""


def declaration(source: str, text: str) -> str:
    start = source.index(text)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError("unclosed production declaration")


class SirenSourceTransportExceptionTests(unittest.TestCase):
    def test_compiled_observer_isolates_reporting_and_preserves_native_iteration(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")
        source = SOURCE.read_text()
        observer = declaration(source, "public sealed class SirenSourceEntryObservedRoutine")
        classification = declaration(source, "public static class SirenSourceEntryFailureClassification")
        with tempfile.TemporaryDirectory(prefix="siren-source-transport-") as directory:
            scratch = Path(directory)
            cs = scratch / "SourceTransport.cs"
            exe = scratch / "SourceTransport.exe"
            cs.write_text("using System;\nusing System.Collections;\nusing System.Collections.Generic;\n" + observer + "\n" + classification + "\n" + FIXTURE)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(exe), str(cs)],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(exe)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("siren-source-transport-observer-passed", executed.stdout)

    def test_observer_is_scoped_to_siren_population_and_original_stage_boundaries(self):
        source = STAGE_SOURCE.read_text()
        transport = declaration(source, "public IEnumerator TransportIntegratedStage(")
        self.assertIn("coordinator.r.sirenSourceEntryDiagnosticAttempt", transport)
        self.assertIn("next.name == SirenEncounterContract.SceneName", transport)
        self.assertIn('ObserveSirenTransportRoutine("PopulateWholeStage", population)', transport)
        self.assertIn('ObserveSirenTransportRoutine("BeginOriginalStage", stage)', transport)
        self.assertIn("ManualMoonBoundary.RefuseTransport", transport)
        self.assertIn("ReportSirenTransportException", source)

    def test_input_finalizer_preserves_an_earlier_transport_failure(self):
        source = INPUT_SOURCE.read_text()
        cleanup_position = source.index("bool cleanupObserved =")
        finalizer_start = source.rfind("if (coordinator.r.sirenSourceEntryDiagnosticAttempt)", 0, cleanup_position)
        finalizer = declaration(source[finalizer_start:], "if (coordinator.r.sirenSourceEntryDiagnosticAttempt)")
        self.assertIn("SirenSourceEntryFailureClassification.PreserveFirstFailure", finalizer)
        self.assertIn("SirenSourceEntryRuntimeContract.SourceEntryAndEncounterCleanupObserved", finalizer)
        self.assertNotIn("coordinator.r.firstFailure = coordinator.r.firstFailure ??", finalizer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
