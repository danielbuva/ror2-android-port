from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = next(parent for parent in Path(__file__).resolve().parents if (parent / "tools/unity/runtime").is_dir())
SCRATCH = REPO / "work/host-tests/objective-combat-input-failure"
DEFAULT_SOURCE_ROOT = REPO
SOURCE_ROOT = DEFAULT_SOURCE_ROOT
MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
CSC = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")


def extract_csharp_member(text: str, signature: str) -> str:
    """Extract a C# member by its unique signature and balanced braces."""
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed C# member {signature}")


def source_paths(source_root: Path) -> tuple[Path, Path]:
    """Resolve either a repository root or the private two-file overlay root."""
    candidates = (
        (
            source_root / "tools/unity/runtime/stage/TeleporterWorldBoundary.cs",
            source_root / "tools/unity/runtime/world/IntegratedWorldBoundary.cs",
        ),
        (
            source_root / "source-overlay/TeleporterWorldBoundary.cs",
            source_root / "source-overlay/IntegratedWorldBoundary.cs",
        ),
    )
    for teleporter, integrated in candidates:
        if teleporter.is_file() and integrated.is_file():
            return teleporter, integrated
    raise FileNotFoundError("source root must contain the production runtime paths or source-overlay files")


def build_harness(teleporter: Path, integrated: Path) -> str:
    teleporter_text = teleporter.read_text(encoding="utf-8")
    integrated_text = integrated.read_text(encoding="utf-8")
    wrapper = extract_csharp_member(
        teleporter_text,
        "public void ObjectiveCombatInput(CharacterBody player, NovaInputBridge bridge, float elapsed, Vector2 planar,",
    )
    witness_enum = extract_csharp_member(teleporter_text, "internal enum ObjectiveCombatInputFailureStep")
    witness = extract_csharp_member(teleporter_text, "internal sealed class ObjectiveCombatInputFailureWitness")
    # These source anchors ensure the selected wrapper and production witness
    # remain connected; behavior below executes the extracted members in C#.
    if "ObjectiveCombatInputCore(player, bridge, elapsed, planar, constrainToHoldout, null)" not in wrapper:
        raise AssertionError("production opt-out path no longer invokes the core with a null witness")
    if "witness.CaptureFirstFailure(report, error)" not in wrapper or "throw;" not in wrapper:
        raise AssertionError("production catch must capture safely and preserve the original throw")
    report_dto = extract_csharp_member(integrated_text, "public sealed class ObjectiveCombatInputFailureReport")

    program = r"""
using System;
using UnityEngine;

namespace UnityEngine
{
    public class Object
    {
        public bool fakeNull;
        public static implicit operator bool(Object value) => value != null && !value.fakeNull;
    }
    public struct Vector2 { }
}

class CharacterBody : UnityEngine.Object { }
class NovaInputBridge { }

class PortSession
{
    public Runtime r = new Runtime();
    public class Runtime { public WorldReport world = new WorldReport(); public bool diagnosticSkillCoverage; }
    public class WorldReport { public ObjectiveCombatInputFailureReport objectiveCombatInputFailure; }
    REPORT_DTO
}

class SessionCoordinator { public PortSession.Runtime r = new PortSession.Runtime(); }

OBJECTIVE_STEP_ENUM

OBJECTIVE_WITNESS

class TeleporterWorldSession
{
    public SessionCoordinator coordinator = new SessionCoordinator();
    public int coreCalls;
    public ObjectiveCombatInputFailureWitness lastCoreWitness;
    public Exception nextFailure;
    internal ObjectiveCombatInputFailureWitness WitnessForTest => objectiveCombatInputFailureWitness;

    WRAPPER

    private ObjectiveCombatInputFailureWitness objectiveCombatInputFailureWitness;
    private void ObjectiveCombatInputCore(CharacterBody player, NovaInputBridge bridge, float elapsed,
        UnityEngine.Vector2 planar, bool constrainToHoldout, ObjectiveCombatInputFailureWitness witness)
    {
        coreCalls++;
        lastCoreWitness = witness;
        if (witness != null)
        {
            witness.Step = ObjectiveCombatInputFailureStep.PlayerUtility;
            witness.ObservedMask = 0x155;
            witness.ActorIndex = 7;
            witness.PlayerInputBankState = 3;
        }
        if (nextFailure != null) throw nextFailure;
    }
}

class Test
{
    static void Need(bool value, string name) { if (!value) throw new Exception(name); }
    static int Main()
    {
        var player = new CharacterBody();
        var bridge = new NovaInputBridge();
        var session = new TeleporterWorldSession();

        // The default path is the original direct core call: no witness allocation,
        // no diagnostic report, and the original exception remains unhandled here.
        var optOutFailure = new NullReferenceException("opt-out-core");
        session.nextFailure = optOutFailure;
        NullReferenceException optOutObserved = null;
        try { session.ObjectiveCombatInput(player, bridge, 0.1f, new UnityEngine.Vector2()); }
        catch (NullReferenceException observed) { optOutObserved = observed; }
        Need(System.Object.ReferenceEquals(optOutObserved, optOutFailure), "opt-out-original-exception");
        Need(session.coreCalls == 1 && session.lastCoreWitness == null, "opt-out-direct-core-null-witness");
        Need(session.WitnessForTest == null, "opt-out-allocates-no-witness");
        Need(session.coordinator.r.world.objectiveCombatInputFailure == null, "opt-out-writes-no-report");

        // The opt-in wrapper catches only to snapshot, then rethrows the exact same
        // exception instance. Core-side witness values are the production DTO's data.
        session.coordinator.r.diagnosticSkillCoverage = true;
        var firstFailure = new NullReferenceException("first-primary-failure");
        session.nextFailure = firstFailure;
        NullReferenceException firstObserved = null;
        try { session.ObjectiveCombatInput(player, bridge, 0.2f, new UnityEngine.Vector2()); }
        catch (NullReferenceException observed) { firstObserved = observed; }
        Need(System.Object.ReferenceEquals(firstObserved, firstFailure), "diagnostic-rethrows-same-exception");
        Need(session.lastCoreWitness != null && System.Object.ReferenceEquals(session.WitnessForTest, session.lastCoreWitness),
             "diagnostic-reuses-owned-witness");
        var report = session.coordinator.r.world.objectiveCombatInputFailure;
        Need(report != null && report.step == "PlayerUtility" && report.observedMask == 0x155,
             "first-failure-captures-current-witness");
        Need(report.exceptionMessage == "first-primary-failure", "first-failure-message");

        // A later diagnostic NRE starts a new per-call witness but cannot replace
        // the first report already stored on this run.
        var laterFailure = new NullReferenceException("later-failure-must-not-win");
        session.nextFailure = laterFailure;
        NullReferenceException laterObserved = null;
        try { session.ObjectiveCombatInput(player, bridge, 0.3f, new UnityEngine.Vector2()); }
        catch (NullReferenceException observed) { laterObserved = observed; }
        Need(System.Object.ReferenceEquals(laterObserved, laterFailure), "later-rethrows-own-exception");
        Need(System.Object.ReferenceEquals(report, session.coordinator.r.world.objectiveCombatInputFailure),
             "first-report-object-not-overwritten");
        Need(report.exceptionMessage == "first-primary-failure" && report.actorIndex == 7,
             "first-report-values-not-overwritten");

        // Execute the extracted production Reset and UnityState logic against CLR
        // null, Unity fake-null, and live object cases.
        var witness = session.WitnessForTest;
        witness.Step = ObjectiveCombatInputFailureStep.ActorAimPoint;
        witness.ObservedMask = 99;
        witness.ActorIndex = 4;
        witness.PlayerInputBankState = 2;
        var fakeNull = new CharacterBody { fakeNull = true };
        Need(ObjectiveCombatInputFailureWitness.UnityState(null) == 1, "clr-null-state");
        Need(ObjectiveCombatInputFailureWitness.UnityState(fakeNull) == 2, "unity-fake-null-state");
        Need(ObjectiveCombatInputFailureWitness.UnityState(player) == 3, "live-unity-state");
        witness.Reset(fakeNull);
        Need(witness.PlayerState == 2 && witness.Step == ObjectiveCombatInputFailureStep.None,
             "reset-records-fake-null-player-and-clears-step");
        Need(witness.ObservedMask == 0 && witness.ActorIndex == -1 && witness.LastActorSampleIndex == -1,
             "reset-clears-index-and-mask");
        Need(witness.PlayerInputBankState == 0 && witness.ActorBodyState == 0 && witness.UtilitySlotState == 0,
             "reset-clears-read-states");

        Console.WriteLine("objective combat input failure witness tests passed");
        return 0;
    }
}
"""
    return (
        program.replace("REPORT_DTO", report_dto).replace("OBJECTIVE_STEP_ENUM", witness_enum).replace("OBJECTIVE_WITNESS", witness).replace("WRAPPER", wrapper)
    )


class ObjectiveCombatInputFailureWitnessTests(unittest.TestCase):
    def test_extracted_production_wrapper_and_witness(self) -> None:
        teleporter, integrated = source_paths(SOURCE_ROOT)
        program = build_harness(teleporter, integrated)
        self.assertTrue(MONO.is_file(), f"Unity Mono runtime missing: {MONO}")
        self.assertTrue(CSC.is_file(), f"Roslyn compiler missing: {CSC}")
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="compile-", dir=SCRATCH) as tmp:
            source = Path(tmp) / "ObjectiveCombatInputWitness.cs"
            output = Path(tmp) / "ObjectiveCombatInputWitness.exe"
            source.write_text(program, encoding="utf-8")
            compiled = subprocess.run(
                [str(MONO), str(CSC), f"-out:{output}", str(source)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(output)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("objective combat input failure witness tests passed", result.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parsed, remaining = parser.parse_known_args()
    SOURCE_ROOT = parsed.source_root.resolve()
    sys.argv = [sys.argv[0], *remaining]
    unittest.main()
