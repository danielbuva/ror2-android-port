"""Exercise the actual authored Siren null-target sampling policy."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get("ROR2LAB_TEST_ROOT", Path(__file__).resolve().parents[1])).resolve()
SOURCE = ROOT / "tools/unity/runtime/input/SirenEggDiagnosticInput.cs"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = Path(os.environ.get("UNITY_MONO", EDITOR / "MonoBleedingEdge/bin/mono"))
CSC = Path(os.environ.get("UNITY_CSC", EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"))


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
    raise AssertionError(f"unclosed declaration: {name}")


class SustainedNullTargetSourceContractTests(unittest.TestCase):
    def test_actual_owner_only_qualifies_existing_same_egg_no_target_observations(self):
        source = SOURCE.read_text(encoding="utf-8")
        owner = declaration(source, "void TryCaptureEligibilitySnapshot(")
        self.assertIn("SirenTargetEligibilityWitnessPolicy.ObserveSustainedNullTarget", owner)
        self.assertIn("primaryRequested && selectedEggNetworkId != 0 && selectedEgg", owner)
        self.assertIn("observation == SirenNativeTargetObservation.NoTarget", owner)
        self.assertIn("!firstEligibilitySnapshotAttempted", owner)
        self.assertIn("WithinCaptureBudget(report.eligibilitySnapshotAttempts)", owner)
        self.assertIn("first-sustained-null-primary-same-selected-egg", owner)
        self.assertIn("sustainedNullTargetSeconds = sustainedNullElapsed", owner)
        self.assertIn("first-visible-primary-mismatch", owner)
        self.assertIn("delayed-null-same-selected-egg", owner)
        self.assertNotIn("GetTrackingTarget", owner)
        self.assertNotIn("SearchForTarget", owner)
        self.assertNotIn("RefreshCandidates", owner)


class SustainedNullTargetCompiledPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise unittest.SkipTest("Siren authored runtime source is unavailable")
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity Mono/Roslyn host compiler unavailable")

    def test_compiled_production_window_requires_half_second_of_contiguous_samples(self):
        source = SOURCE.read_text(encoding="utf-8")
        window = declaration(source, "public struct SirenNullTargetWitnessWindow")
        evidence = declaration(source, "public struct SirenBullseyeMembershipEvidence")
        policy = declaration(source, "public static class SirenTargetEligibilityWitnessPolicy")
        harness = r"""
public static class Program
{
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    static bool Observe(ref SirenNullTargetWitnessWindow window, bool qualifies, uint egg, float time, out float elapsed)
    {
        return SirenTargetEligibilityWitnessPolicy.ObserveSustainedNullTarget(
            ref window, qualifies, egg, time, out elapsed);
    }
    public static int Main()
    {
        float elapsed;
        var window = new SirenNullTargetWitnessWindow();
        Require(!Observe(ref window, true, 401, 10f, out elapsed) && window.consecutiveSamples == 1,
                "first qualifying sample must start, not satisfy, the window");
        Require(!Observe(ref window, true, 401, 10.25f, out elapsed) && window.consecutiveSamples == 2,
                "exact maximum gap is continuous but only 0.25 seconds have elapsed");
        Require(!Observe(ref window, true, 401, 10.499f, out elapsed) && elapsed < 0.5f,
                "window must remain unqualified before 0.5 seconds");
        Require(Observe(ref window, true, 401, 10.5f, out elapsed) && elapsed == 0.5f,
                "same-egg qualifying samples spanning exactly 0.5 seconds must qualify");

        window = new SirenNullTargetWitnessWindow();
        Require(!Observe(ref window, true, 402, 1f, out elapsed), "gap case did not start");
        Require(!Observe(ref window, true, 402, 1.2501f, out elapsed) && window.consecutiveSamples == 1 &&
                window.firstObservedRealtime == 1.2501f,
                "a gap above 0.25 seconds must restart at this sample");
        Require(!Observe(ref window, true, 402, 1.5f, out elapsed) && elapsed < 0.5f,
                "pre-gap elapsed time must not leak into the restarted window");
        Require(!Observe(ref window, true, 402, 1.75f, out elapsed) && elapsed < 0.5f,
                "restarted window must stay below threshold until its own full duration elapses");
        Require(Observe(ref window, true, 402, 2f, out elapsed) && elapsed >= 0.5f,
                "fresh continuous observations may qualify after the restarted 0.5-second window");

        window = new SirenNullTargetWitnessWindow();
        Require(!Observe(ref window, true, 403, 2f, out elapsed), "long-gap case did not start");
        Require(!Observe(ref window, true, 403, 20f, out elapsed) && window.consecutiveSamples == 1 &&
                window.firstObservedRealtime == 20f,
                "long pause must restart, not count as sustained state");
        Require(!Observe(ref window, true, 404, 20.1f, out elapsed) && window.selectedEggNetworkId == 404 &&
                window.consecutiveSamples == 1,
                "selected egg identity change must restart the window");
        Require(!Observe(ref window, false, 404, 20.2f, out elapsed) && !window.active,
                "nonqualifying observation must clear the window");
        Require(!Observe(ref window, true, 404, 20.3f, out elapsed) && window.consecutiveSamples == 1,
                "elapsed time across a reset must not be retained");
        Require(!Observe(ref window, true, 404, 20.29f, out elapsed) && window.consecutiveSamples == 1 &&
                window.firstObservedRealtime == 20.29f,
                "backward realtime must restart at the current sample");
        Require(!Observe(ref window, true, 404, Single.NaN, out elapsed) && !window.active,
                "non-finite realtime must reset to unknown");
        Require(!Observe(ref window, true, 404, Single.PositiveInfinity, out elapsed) && !window.active,
                "infinite realtime must reset to unknown");
        Require(!Observe(ref window, true, 0, 21f, out elapsed) && !window.active,
                "zero selected-egg identity must not qualify");

        window = new SirenNullTargetWitnessWindow { active = true, selectedEggNetworkId = 405,
            consecutiveSamples = Int32.MaxValue, firstObservedRealtime = 1f, lastObservedRealtime = 1.25f };
        Require(SirenTargetEligibilityWitnessPolicy.ObserveSustainedNullTarget(
                    ref window, true, 405, 1.5f, out elapsed) && window.consecutiveSamples == Int32.MaxValue,
                "sample count must saturate without overflowing");
        Require(SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(0) &&
                SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(1) &&
                !SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(2),
                "the existing two-snapshot capture cap changed");
        Console.WriteLine("siren-sustained-null-target-window-production-contract-passed");
        return 0;
    }
}
"""
        source_text = (
            "using System;\nusing System.Collections.Generic;\nusing UnityEngine;\n"
            "namespace UnityEngine { public static class Mathf { public const float PI = 3.14159265358979323846f; "
            "public static float Cos(float value) { return (float)Math.Cos(value); } } }\n" + window + "\n" + evidence + "\n" + policy + "\n" + harness
        )
        with tempfile.TemporaryDirectory(prefix="siren-null-target-window-") as directory:
            temp = Path(directory)
            source_file, executable = temp / "WindowPolicy.cs", temp / "WindowPolicy.exe"
            source_file.write_text(source_text, encoding="utf-8")
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(executable), str(source_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("siren-sustained-null-target-window-production-contract-passed", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
