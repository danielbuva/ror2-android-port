"""Run extracted Siren cleanup ownership helpers against authored failure doubles."""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
SIREN = ROOT / "tools/unity/runtime/stage/SirenEncounterBoundary.cs"
INTEGRATED = ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs"

FIXTURE = r"""
public static class SirenCleanupHarness
{
    static void Assert(bool value, string name) { if (!value) throw new Exception(name); }
    public static void Main()
    {
        object candidate = new object(), retained = null;
        bool refused = false;
        try { SirenEncounterContract.RetainOwnerAfterPreflight(false, candidate, value => retained = value); }
        catch (InvalidOperationException) { refused = true; }
        Assert(refused && retained == null, "preflight refusal retained owner");
        SirenEncounterContract.RetainOwnerAfterPreflight(true, candidate, value => retained = value);
        Assert(Object.ReferenceEquals(candidate, retained), "preflighted owner not retained");

        bool gate = true;
        Assert(!SirenEncounterContract.CompleteOwnedRecovery(ref gate, 8, 7, true, false) && gate,
               "intervening shared recovery write was cleared");
        Assert(!SirenEncounterContract.CompleteOwnedRecovery(ref gate, 8, 8, true, true) && gate,
               "other owner recovery was cleared");
        Assert(SirenEncounterContract.CompleteOwnedRecovery(ref gate, 8, 8, true, false) && !gate,
               "sole unchanged Siren recovery was not cleared");

        bool subscribed = true, ownsSubscription = true;
        int removeCalls = 0;
        bool removeFailed = false;
        try { SirenEncounterContract.DetachOwnedSubscription(ref ownsSubscription, () => {
            removeCalls++; if (removeCalls == 1) throw new InvalidOperationException("remove"); subscribed = false;
        }); } catch (InvalidOperationException) { removeFailed = true; }
        Assert(removeFailed && subscribed && ownsSubscription, "failed remove lost subscription ownership");
        SirenEncounterContract.DetachOwnedSubscription(ref ownsSubscription, () => { removeCalls++; subscribed = false; });
        Assert(!subscribed && !ownsSubscription && removeCalls == 2, "remove retry failed");

        int cursor = 0, actionCalls = 0;
        Exception first = null, stepFailure;
        Assert(SirenEncounterContract.TryAdvanceOwnedCleanupStep(ref cursor, 0, false, () => actionCalls++, ref first, out stepFailure),
               "unowned cleanup gate failed");
        Assert(actionCalls == 0 && cursor == 1, "unowned active-state cleanup ran");
        cursor = 0;
        Assert(!SirenEncounterContract.TryAdvanceCleanupStep(ref cursor, 0, () => {
            actionCalls++; throw new InvalidOperationException("injected");
        }, ref first, out stepFailure), "injected cleanup error passed");
        Assert(cursor == 0 && Object.ReferenceEquals(first, stepFailure), "failed step advanced or lost first error");
        Assert(SirenEncounterContract.TryAdvanceCleanupStep(ref cursor, 0, () => actionCalls++, ref first, out stepFailure),
               "cleanup retry failed");
        Assert(cursor == 1 && first.Message == "injected", "retry did not advance or preserve first error");
        SirenEncounterContract.TryAdvanceCleanupStep(ref cursor, 0, () => { throw new Exception("reran"); }, ref first, out stepFailure);
        Assert(cursor == 1, "completed cleanup step was not idempotent");

        object owner = new object(), captured = owner;
        bool disposeFailed = false;
        try { SirenEncounterContract.DisposeOwned(ref owner, value => { throw new InvalidOperationException("dispose"); }); }
        catch (InvalidOperationException) { disposeFailed = true; }
        Assert(disposeFailed && Object.ReferenceEquals(owner, captured), "Dispose failure lost owner handle");
        int disposeCalls = 0;
        SirenEncounterContract.DisposeOwned(ref owner, value => disposeCalls++);
        SirenEncounterContract.DisposeOwned(ref owner, value => disposeCalls++);
        Assert(owner == null && disposeCalls == 1, "successful Dispose did not clear exactly once");

        var attach = new InvalidOperationException("attach primary");
        var rollback = new InvalidOperationException("rollback detail");
        Exception primary = null, observed = null;
        try { SirenEncounterContract.RunAttachTransaction(() => { throw attach; }, () => {},
            () => { throw rollback; }, failure => observed = failure); }
        catch (Exception ex) { primary = ex; }
        Assert(Object.ReferenceEquals(primary, attach) && Object.ReferenceEquals(observed, rollback),
               "rollback failure replaced primary attach exception");
        Console.WriteLine("{\"preflight\":true,\"generation\":true,\"detach_retry\":true,\"cursor_retry\":true,\"dispose_retention\":true,\"attach_primary\":true,\"all_passed\":true}");
    }
}
"""


def method(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError("Unclosed production declaration: " + declaration)


def extracted_contract():
    source = SIREN.read_text()
    declarations = [
        "public static void RetainOwnerAfterPreflight<T>(",
        "public static bool CompleteOwnedRecovery(",
        "public static void DetachOwnedSubscription(",
        "public static bool TryAdvanceCleanupStep(",
        "public static bool TryAdvanceOwnedCleanupStep(",
        "public static void RunAttachTransaction(",
        "public static void DisposeOwned<T>(",
    ]
    snippets = [method(source, declaration) for declaration in declarations]
    owner = method(source, "void Release()")
    attach = method(source, "public static SirenEncounterSession Attach(")
    integrated = INTEGRATED.read_text()
    cleanup = method(integrated, "void CleanupSirenEncounter()")
    dispose = method(integrated, "public void Dispose()")
    if "TryAdvanceOwnedCleanupStep(ref cleanupStep, 5, ownsActiveStateMutation" not in owner:
        raise AssertionError("Release must restore active state only when this owner changed it")
    if "TryAdvanceOwnedCleanupStep(ref cleanupStep, 6, ownsActivatedSceneInstance" not in owner:
        raise AssertionError("Release must destroy only its activated scene instance")
    if owner.index("ClearDiagnosticEggCandidates();") > owner.index("Report.cleanupDisposed = true;"):
        raise AssertionError("Release publishes completion before transient cleanup")
    if attach.index("owner.identity.isServer || owner.identity.netId.Value != 0") > attach.index("RetainOwnerAfterPreflight("):
        raise AssertionError("Attach retains an owner before identity preflight")
    if "cleanupFailure =>" not in method(integrated, "void AttachSirenEncounterIfPresent()"):
        raise AssertionError("Attach rollback failure does not reach the coordinator")
    if "CompleteOwnedRecovery(" not in cleanup or "sirenCleanupRecoveryGeneration" not in cleanup:
        raise AssertionError("Coordinator does not use the generation checked by the cleanup gate")
    if dispose.index("Native first-stage recovery owner must retire Stage") > dispose.index("CleanupSirenEncounter();"):
        raise AssertionError("Siren retry may precede native Stage retirement")
    return "using System;\npublic static class SirenEncounterContract {\n" + "\n".join(snippets) + "\n}\n" + FIXTURE


def recovery_writer_inventory():
    runtime = ROOT / "tools/unity/runtime"
    sources = sorted(runtime.rglob("*.cs"))
    direct = []
    callers = set()
    for path in sources:
        text = path.read_text()
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"sourceStageLifecycleRecoveryRequired\s*=", line):
                if path.name != "PortSession.cs" or "r.sourceStageLifecycleRecoveryRequired = required" not in line:
                    direct.append(f"{path.relative_to(ROOT)}:{number}")
            if "MarkSourceStageLifecycleRecovery(" in line:
                callers.add(str(path.relative_to(ROOT)))
    if direct:
        raise AssertionError("Shared recovery gate has noncentral writers: " + ", ".join(direct))
    if not {
        "tools/unity/runtime/stage/IntegratedStageBoundary.cs",
        "tools/unity/runtime/stage/TeleporterWorldBoundary.cs",
        "tools/unity/runtime/world/IntegratedWorldBoundary.cs",
        "tools/unity/runtime/world/WholeInteractableBoundary.cs",
    }.issubset(callers):
        raise AssertionError("The known recovery owners are absent from the central writer inventory: " + repr(callers))
    return {"runtime_source_count": len(sources), "writer_callers": sorted(callers)}


class SirenCleanupOwnershipTests(unittest.TestCase):
    def test_all_shared_recovery_writers_are_centralized(self):
        inventory = recovery_writer_inventory()
        self.assertGreater(inventory["runtime_source_count"], 0)

    def test_extracted_production_ownership_helpers(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="siren-cleanup-ownership-") as directory:
            scratch = Path(directory)
            source = scratch / "SirenCleanupOwnership.cs"
            output = scratch / "SirenCleanupOwnership.exe"
            source.write_text(extracted_contract())
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)], cwd=scratch, capture_output=True, text=True
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            result = json.loads(executed.stdout)
            self.assertTrue(result["all_passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
