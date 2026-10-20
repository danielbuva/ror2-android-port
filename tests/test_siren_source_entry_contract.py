"""Compile and exercise the pure production source-entry ownership predicates."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/stage/SirenSourceEntrySession.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")

FIXTURE = r"""
public static class SourceEntryContractHarness
{
    static void Assert(bool value, string name) { if (!value) throw new Exception(name); }
    public static void Main()
    {
        var all = new[] { "nest-a", "nest-b", "nest-c" };
        var selected = new[] { "nest-a", "nest-c" };
        var eggs = new[] { "egg-a", "egg-c" };
        var ids = new uint[] { 101, 102 };
        var observed = new[] { true, true };
        Assert(SirenSourceEntryContract.IsExactBijection(all, selected, eggs, ids, observed, 2), "complete bijection");
        Assert(!SirenSourceEntryContract.IsExactBijection(all, selected, eggs, new uint[] { 101, 101 }, observed, 2), "duplicate IDs");
        Assert(!SirenSourceEntryContract.IsExactBijection(all, selected, eggs, new uint[] { 0, 102 }, observed, 2), "zero ID");
        Assert(!SirenSourceEntryContract.IsExactBijection(all, selected, eggs, ids, new[] { true, false }, 2), "missing witness");
        Assert(!SirenSourceEntryContract.IsExactBijection(all, new[] { "outside" }, eggs, ids, observed, 2), "foreign source");
        Assert(SirenSourceEntryContract.MayAdmitEncounter(true, true, true, true, true), "valid ID-10 admission");
        Assert(!SirenSourceEntryContract.MayAdmitEncounter(true, false, true, true, true), "pending toggle queue");
        Assert(!SirenSourceEntryContract.MayAdmitEncounter(true, true, true, false, true), "active ID 10");
        Assert(!SirenSourceEntryContract.MayAdmitEncounter(true, true, true, true, false), "egg input selected");
        Assert(SirenSourceEntryContract.MayRetireSourceEggs(false, false, false, true), "no-dispatch cleanup has no source cohort");
        Assert(SirenSourceEntryContract.MayRetireSourceEggs(true, true, false, true), "complete witnessed source cohort cleanup");
        Assert(!SirenSourceEntryContract.MayRetireSourceEggs(true, false, false, true), "incomplete source cohort retains context");
        Assert(!SirenSourceEntryContract.MayRetireSourceEggs(true, true, true, true), "ambiguous source observation retains context");
        Assert(!SirenSourceEntryContract.MayRetireSourceEggs(true, true, false, false), "moved captured egg retains context");
        Assert(SirenSourceEntryContract.MatchesCapturedObjectPresence(true, true, false), "intentional null slot remains valid");
        Assert(SirenSourceEntryContract.MatchesCapturedObjectPresence(false, false, true), "captured target or identity remains alive");
        Assert(!SirenSourceEntryContract.MatchesCapturedObjectPresence(false, false, false), "destroyed captured target or identity refuses cleanup");
        Assert(!SirenSourceEntryContract.MatchesCapturedObjectPresence(false, true, false), "captured non-null becoming CLR null refuses cleanup");
        Assert(!SirenSourceEntryContract.MatchesCapturedObjectPresence(true, false, true), "unexpected object in captured null slot refuses cleanup");
        Assert(SirenSourceEntryContract.MayRestoreToggleTarget(false, false, true, false, false), "untouched target");
        Assert(SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, true, true), "captured native choice");
        Assert(!SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, false, true), "unowned mutation");
        Assert(!SirenSourceEntryContract.MayRestoreToggleTarget(false, true, false, true, true), "wrong native choice");
        Assert(!SirenSourceEntryContract.MayRestoreToggleTarget(false, true, true, true, false), "unknown expected state");
        System.Console.WriteLine("source-entry-contract-all-passed");
    }
}
"""


def declaration(source, text):
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
    raise AssertionError("Unclosed production declaration")


class SourceEntryContractTests(unittest.TestCase):
    def test_source_entry_production_predicates(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")
        contract = declaration(SOURCE.read_text(), "public static class SirenSourceEntryContract")
        with tempfile.TemporaryDirectory(prefix="siren-source-entry-contract-") as directory:
            scratch = Path(directory)
            source = scratch / "SourceEntryContract.cs"
            output = scratch / "SourceEntryContract.exe"
            source.write_text("using System;\nusing System.Collections.Generic;\nusing System.Linq;\n" + contract + "\n" + FIXTURE)
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)], cwd=scratch, capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("source-entry-contract-all-passed", executed.stdout)

    def test_runtime_cleanup_refuses_destroyed_captured_toggle_objects(self):
        source = SOURCE.read_text()
        restore = declaration(source, "void RestoreToggleTargetStates()")
        self.assertIn("state.targetWasNull", restore)
        self.assertIn("state.identityWasNull", restore)
        self.assertIn("MatchesCapturedObjectPresence", restore)
        self.assertIn("ReferenceEquals(currentIdentity, state.identity)", restore)
        self.assertIn("retaining source context", restore)
        self.assertIn("report.nativeToggleTargetCount = restoredCount", restore)
        self.assertIn("report.nativeToggleTargetsRestored = restoredCount == toggleTargetStates.Count", restore)
        self.assertLess(
            restore.index("report.nativeToggleTargetCount = restoredCount"),
            restore.index("report.nativeToggleTargetsRestored = restoredCount == toggleTargetStates.Count"),
        )

    def test_runtime_cleanup_is_gated_by_exact_bijection_ambiguity_and_pose(self):
        source = SOURCE.read_text()
        cleanup = declaration(source, "void RetireOwnedEggs()")
        completion = declaration(source, "public void CompleteAfterNaturalSpawnerStart()")
        self.assertIn("MayRetireSourceEggs(globalDispatchAttempted", cleanup)
        self.assertIn("complete && report.exactEggBijection", cleanup)
        self.assertIn("captureFailure", cleanup)
        self.assertIn("capturedEggsUnmoved", cleanup)
        self.assertIn("IsEggAtCapturedSpawnPose(source)", completion)
        pose = declaration(source, "static bool IsEggAtCapturedSpawnPose(SourceEgg row)")
        self.assertIn("row.expectedPosition", pose)
        self.assertIn("row.expectedRotation", pose)
        self.assertIn("Quaternion.Angle", pose)


if __name__ == "__main__":
    unittest.main(verbosity=2)
