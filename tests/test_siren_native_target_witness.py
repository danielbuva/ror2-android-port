"""Host-only tests for authored Siren ranking and native-target witness code."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "tools/unity/runtime"
INPUT = SOURCE_ROOT / "input/SirenEggDiagnosticInput.cs"
TARGETS = SOURCE_ROOT / "stage/SirenEncounterEggTargets.cs"
WORLD = SOURCE_ROOT / "world/IntegratedWorldBoundary.cs"
STAGE = SOURCE_ROOT / "stage/IntegratedStageBoundary.cs"
FIXTURE = SOURCE_ROOT.parents[1] / "catalog/SirenEggDiagnosticInputExactEditorFixture.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = Path(os.environ.get("UNITY_MONO", EDITOR / "MonoBleedingEdge/bin/mono"))
CSC = Path(
    os.environ.get(
        "UNITY_CSC",
        EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe",
    )
)


def declaration(source: str, name: str) -> str:
    start = source.index(name)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed declaration {name}")


class SirenNativeTargetWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity host compiler unavailable")

    def test_production_ranking_and_witness_accounting(self):
        text = INPUT.read_text()
        report = declaration(text, "public sealed class SirenEggInputReport")
        ranking = declaration(text, "public static class SirenEggTargetSelectionPolicy")
        observation = declaration(text, "public enum SirenNativeTargetObservation")
        witness = declaration(text, "public static class SirenNativeTargetWitnessPolicy")
        source = (
            "using System;\n"
            + report
            + "\n"
            + ranking
            + "\n"
            + observation
            + "\n"
            + witness
            + r"""
public static class Program
{
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    public static int Main()
    {
        Require(SirenEggTargetSelectionPolicy.Prefer(true, 100f, true, false, 4f), "visible target did not outrank nearer occluded target");
        Require(!SirenEggTargetSelectionPolicy.Prefer(false, Single.NaN, false, false, 0f), "NaN distance was accepted");
        Require(SirenEggTargetSelectionPolicy.IsCandidateCountSupported(12) &&
                !SirenEggTargetSelectionPolicy.IsCandidateCountSupported(13) &&
                !SirenEggTargetSelectionPolicy.IsCandidateCountSupported(-1), "candidate limit was not strict");

        var report = new SirenEggInputReport();
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.TrackerUnavailable, 41, 0, true);
        Require(report.nativeTrackerWitnessSamples == 1 && report.nativeTrackerUnavailableSamples == 1,
                "missing tracker must be unknown, not an empty native target");
        Require(report.nativeTargetNullSamples == 0 && report.primaryRequestedNativeUnknownSamples == 1,
                "missing tracker was misclassified");
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.NoTarget, 41, 0, false);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.DestroyedTarget, 41, 0, false);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.HealthUnavailable, 41, 0, false);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.IdentityUnavailable, 41, 0, false);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.ZeroNetworkId, 41, 0, false);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.IdentifiedTarget, 41, 41, true);
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.IdentifiedTarget, 41, 99, true);
        Require(report.nativeTrackerWitnessSamples == 8 && report.nativeTrackerUnavailableSamples == 1 &&
                report.nativeTargetNullSamples == 1 && report.nativeTargetDestroyedSamples == 1 &&
                report.nativeTargetHealthUnavailableSamples == 1 && report.nativeTargetIdentityUnavailableSamples == 1 &&
                report.nativeTargetZeroNetworkIdSamples == 1 && report.nativeTargetIdentifiedSamples == 2,
                "observation states must remain separately counted");
        Require(report.nativeTargetMatchesSelectedSamples == 1 && report.nativeTargetDiffersSelectedSamples == 1 &&
                report.primaryRequestedSamples == 3 && report.primaryReleasedSamples == 5 &&
                report.primaryRequestedNativeUnknownSamples == 1 && report.primaryRequestedNativeMatchSamples == 1 &&
                report.primaryRequestedNativeMismatchSamples == 1,
                "native match and primary-request outcomes must be counted without collapsing unknowns");
        Require(report.firstSelectedEggNetworkId == 41 && report.lastSelectedEggNetworkId == 41 &&
                report.firstNativeHuntressTargetNetworkId == 41 && report.lastNativeHuntressTargetNetworkId == 99 &&
                report.lastNativeTargetObservation == "identified-target" && !report.lastNativeTargetMatchesSelected,
                "first/last IDs or last mismatch witness were not retained");
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.NoTarget, 41, 0, false);
        Require(report.lastNativeHuntressTargetNetworkId == 0 && report.firstNativeHuntressTargetNetworkId == 41 &&
                report.lastNativeTargetObservation == "no-target", "last-sample unknown target did not clear stale ID");
        report.nativeTrackerWitnessSamples = Int32.MaxValue;
        SirenNativeTargetWitnessPolicy.Record(report, SirenNativeTargetObservation.NoTarget, 41, 0, false);
        Require(report.nativeTrackerWitnessSamples == Int32.MaxValue, "witness counter overflowed");
        Console.WriteLine("siren-native-target-witness-production-contract-passed");
        return 0;
    }
}
"""
        )
        scratch = ROOT / "work/host-tests/siren-native-target"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="contract-", dir=scratch) as td:
            tmp = Path(td)
            src, exe = tmp / "Witness.cs", tmp / "Witness.exe"
            src.write_text(source)
            compiled = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-langversion:9",
                    "-target:exe",
                    "-out:" + str(exe),
                    str(src),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("siren-native-target-witness-production-contract-passed", result.stdout)

    def test_runtime_witness_uses_real_tracker_and_is_bounded(self):
        source = INPUT.read_text()
        sample = declaration(source, "void ObserveNativeHuntressTarget")
        self.assertIn("player.GetComponent<HuntressTracker>()", sample)
        self.assertIn("tracker.GetTrackingTarget()", sample)
        self.assertIn("ReferenceEquals(nativeTarget, null)", sample)
        self.assertIn("else if (!nativeTarget)", sample)
        self.assertIn(
            "targetHealth.gameObject.GetComponent<UnityEngine.Networking.NetworkIdentity>()",
            sample,
        )
        self.assertIn("targetIdentity.netId.Value", sample)
        self.assertIn("nativeTarget.teamIndex", sample)
        self.assertIn("tracker.maxTrackingDistance", sample)
        self.assertIn("tracker.maxTrackingAngle", sample)
        self.assertIn("tracker.trackerUpdateFrequency", sample)
        self.assertIn("lastNativeTargetCurrentDistance", sample)
        self.assertIn("lastNativeTargetCurrentAimDot", sample)
        self.assertNotIn("GetField(", sample)
        self.assertNotIn("GetProperty(", sample)
        self.assertNotIn("Physics.", sample)
        self.assertNotIn("new ", sample)
        self.assertIn("SirenNativeTargetWitnessPolicy.Record(report, observation", sample)
        self.assertIn("ObserveNativeHuntressTarget(player, selectedEggNetworkId, visible)", source)
        self.assertIn("bridge.diagnosticPrimary = visible", source)
        self.assertIn('"visible-egg-requested-primary"', source)
        self.assertIn('"no-visible-egg-primary-released"', source)
        self.assertIn(
            "if (!context.RevalidatedSourceEggs(player.corePosition, sourceEggCandidates))",
            source,
        )
        self.assertIn("CharacterBody egg = hasVisible ? visibleEgg : nearestEgg", source)
        self.assertIn("if (!context.Selected)", source)
        self.assertLess(
            source.index("if (!context.Selected)"),
            source.index("ObserveNativeHuntressTarget(player, selectedEggNetworkId, visible)"),
        )

        targets, world, stage = (
            TARGETS.read_text(),
            WORLD.read_text(),
            STAGE.read_text(),
        )
        self.assertIn("CollectRevalidatedDiagnosticEggs(destination)", stage)
        self.assertIn(
            "if (!SirenEggTargetSelectionPolicy.IsCandidateCountSupported(diagnosticSourceEggCache.Count))",
            targets,
        )
        self.assertLess(
            targets.index(
                "destination.Clear();",
                targets.index("CollectRevalidatedDiagnosticEggs"),
            ),
            targets.index(
                "if (!SirenEggTargetSelectionPolicy.IsCandidateCountSupported",
                targets.index("CollectRevalidatedDiagnosticEggs"),
            ),
        )
        self.assertIn("RevalidatedSirenDiagnosticEggs(position,destination)", "".join(world.split()))
        self.assertIn(
            "IsCurrentDiagnosticSourceEgg(candidate,cached.nativeListenerName)",
            "".join(targets.split()),
        )
        self.assertIn("context.IsCurrentSourceEgg(candidate)", source)
        self.assertIn("context.IsCurrentSourceEgg(egg)", source)
        self.assertIn("context.ShouldYieldToExistingWorldCombat(player)", source)
        self.assertIn("context.ManualTakeover", source)
        self.assertIn("context.NativeEncounterStarted", source)
        fixture = FIXTURE.read_text()
        self.assertIn("VerifyVisibleRegisteredEggPreference()", fixture)

    def test_report_is_fixed_scalar_storage_not_per_sample_list(self):
        source = INPUT.read_text()
        report = declaration(source, "public sealed class SirenEggInputReport")
        self.assertIn("firstNativeHuntressTargetNetworkId", report)
        self.assertIn("lastNativeHuntressTargetNetworkId", report)
        self.assertNotIn("List<", report)
        self.assertNotIn("[]", report)
        policy = declaration(source, "public static class SirenNativeTargetWitnessPolicy")
        self.assertNotIn("ToString()", policy)
        self.assertNotIn("new ", policy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
