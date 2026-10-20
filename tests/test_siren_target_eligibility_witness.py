"""Execute the authored Siren eligibility and exception-preservation contracts."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/input/SirenEggDiagnosticInput.cs"
SCRATCH = ROOT / "work/host-tests/siren-target-eligibility"
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


class EligibilitySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("Pinned Unity host compiler unavailable")

    def test_production_policy_fake_null_range_cone_unknown_and_budget(self):
        source = SOURCE.read_text()
        membership = declaration(source, "public struct SirenBullseyeMembershipEvidence")
        policy = declaration(source, "public static class SirenTargetEligibilityWitnessPolicy")
        program = r"""
namespace UnityEngine
{
    public static class Mathf
    {
        public const float PI = 3.14159265358979323846f;
        public static float Cos(float value) { return (float)Math.Cos(value); }
    }
}
public sealed class FakeUnityNull
{
    public bool Destroyed;
    public static bool operator ==(FakeUnityNull left, FakeUnityNull right)
    {
        if (Object.ReferenceEquals(left, right)) return true;
        return Object.ReferenceEquals(left, null) ? right.Destroyed : left.Destroyed && Object.ReferenceEquals(right, null);
    }
    public static bool operator !=(FakeUnityNull left, FakeUnityNull right) { return !(left == right); }
    public override bool Equals(object other) { return Object.ReferenceEquals(this, other); }
    public override int GetHashCode() { return base.GetHashCode(); }
}
public static class Program
{
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    public static int Main()
    {
        var selected = new FakeUnityNull { Destroyed = false };
        var registry = new List<FakeUnityNull> { selected };
        SirenBullseyeMembershipEvidence found, other;
        SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(registry, selected, null, 4, out found, out other);
        Require(found.available && found.known && found.present && !found.truncated && other.available && !other.known,
                "exact reference membership or missing-target unknown failed");

        var fakeNull = new FakeUnityNull { Destroyed = true };
        Require(fakeNull == null && !Object.ReferenceEquals(fakeNull, null), "fake-null fixture invalid");
        SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(new List<FakeUnityNull> { fakeNull }, fakeNull, null, 4,
                                                               out var fakeNullEvidence, out var nullEvidence);
        Require(fakeNullEvidence.available && fakeNullEvidence.known && fakeNullEvidence.present && nullEvidence.available &&
                !nullEvidence.known, "membership used overloaded Unity-style null or fabricated null-target absence");

        SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(
            new List<FakeUnityNull> { new FakeUnityNull(), new FakeUnityNull(), selected }, selected, fakeNull, 2,
            out var truncatedAbsent, out var truncatedPresent);
        Require(truncatedAbsent.available && truncatedAbsent.truncated && !truncatedAbsent.known &&
                !truncatedAbsent.present && truncatedAbsent.scannedCount == 2,
                "truncated scan fabricated a negative membership result");
        SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(
            new List<FakeUnityNull> { selected, new FakeUnityNull(), new FakeUnityNull() }, selected, selected, 1,
            out var positiveTruncated, out var alsoPositiveTruncated);
        Require(positiveTruncated.truncated && positiveTruncated.known && positiveTruncated.present &&
                alsoPositiveTruncated.known && alsoPositiveTruncated.present,
                "positive exact membership should remain known when the bounded scan truncates");
        SirenTargetEligibilityWitnessPolicy.ScanMembershipPair<FakeUnityNull>(null, selected, null, 2,
                                                                               out var unavailable, out var alsoUnavailable);
        Require(!unavailable.available && !unavailable.known && !unavailable.present && !alsoUnavailable.available,
                "missing registry must remain explicitly unknown");

        bool range, cone;
        Require(SirenTargetEligibilityWitnessPolicy.TryMeasureRangeAndCone(30f, 0.9f, 60f, 30f, out range, out cone) &&
                range && cone, "finite in-range/in-cone observation rejected");
        Require(SirenTargetEligibilityWitnessPolicy.TryMeasureRangeAndCone(61f, 0.8f, 60f, 30f, out range, out cone) &&
                !range && !cone, "finite out-of-range/out-of-cone observation accepted");
        Require(!SirenTargetEligibilityWitnessPolicy.TryMeasureRangeAndCone(float.NaN, 1f, 60f, 30f, out range, out cone) &&
                !range && !cone, "non-finite geometry must remain unknown");

        Require(SirenTargetEligibilityWitnessPolicy.ShouldCaptureFirstMismatch(false, true, true, 411, 417),
                "first visible mismatch was not selected");
        Require(!SirenTargetEligibilityWitnessPolicy.ShouldCaptureFirstMismatch(true, true, true, 411, 417) &&
                !SirenTargetEligibilityWitnessPolicy.ShouldCaptureFirstMismatch(false, false, true, 411, 417),
                "first snapshot repeated or captured without visible primary");
        Require(SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(true, true, 0.5f) &&
                !SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(true, true, 0.49f) &&
                !SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(false, true, 1f) &&
                !SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(true, false, 1f) &&
                !SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(true, true, float.PositiveInfinity),
                "delayed null snapshot timing or unknown guard failed");
        Require(SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(0) &&
                SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(1) &&
                !SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(2) &&
                !SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(-1),
                "two-snapshot per-stage budget was not enforced");
        Console.WriteLine("siren-target-eligibility-snapshot-production-contract-passed");
        return 0;
    }
}
"""
        source_text = "using System;\nusing System.Collections.Generic;\nusing UnityEngine;\n" + membership + "\n" + policy + "\n" + program
        with tempfile.TemporaryDirectory(prefix="target-snapshot-", dir=SCRATCH) as td:
            temp = Path(td)
            cs, exe = temp / "SnapshotPolicy.cs", temp / "SnapshotPolicy.exe"
            cs.write_text(source_text)
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(exe), str(cs)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("siren-target-eligibility-snapshot-production-contract-passed", result.stdout)

    def test_native_getter_wrapper_rethrows_same_exception_before_input_action(self):
        source = SOURCE.read_text()
        method = declaration(source, "public static HurtBox ReadTargetOrThrow(")
        program = r"""
public sealed class HurtBox { }
public sealed class HuntressTracker
{
    public Exception Failure;
    public HurtBox GetTrackingTarget() { throw Failure; }
}
public sealed class SirenEggInputReport
{
    public int nativeTargetReadErrors;
    public string lastNativeTargetReadErrorType;
}
public static class Program
{
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    public static int Main()
    {
        var report = new SirenEggInputReport();
        var original = new InvalidOperationException("native getter failure");
        var tracker = new HuntressTracker { Failure = original };
        int inputActions = 0;
        Exception caught = null;
        try
        {
            var target = SirenNativeTargetWitnessPolicy.ReadTargetOrThrow(tracker, report);
            inputActions++;
        }
        catch (Exception error) { caught = error; }
        Require(Object.ReferenceEquals(caught, original), "wrapper replaced the native exception");
        Require(inputActions == 0, "input action continued after native getter failure");
        Require(report.nativeTargetReadErrors == 1 &&
                report.lastNativeTargetReadErrorType == typeof(InvalidOperationException).FullName,
                "separate read-error evidence was not recorded");
        Console.WriteLine("siren-native-getter-rethrow-contract-passed");
        return 0;
    }
}
"""
        support = "using System;\n" + "public static class SirenNativeTargetWitnessPolicy\n{\n" + method + "\n}\n" + program
        with tempfile.TemporaryDirectory(prefix="target-rethrow-", dir=SCRATCH) as td:
            temp = Path(td)
            cs, exe = temp / "GetterRethrow.cs", temp / "GetterRethrow.exe"
            cs.write_text(support)
            compiled = subprocess.run(
                [str(MONO), str(CSC), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(exe), str(cs)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("siren-native-getter-rethrow-contract-passed", result.stdout)

    def test_runtime_is_one_shot_read_only_and_records_unknowns(self):
        source = SOURCE.read_text()
        report = declaration(source, "public sealed class SirenEggInputReport")
        self.assertIn("nativeTargetReadErrors", report)
        self.assertIn("lastNativeTargetReadErrorType", report)
        self.assertIn("firstMismatchEligibilitySnapshot", report)
        self.assertIn("delayedNullEligibilitySnapshot", report)
        self.assertIn("eligibilitySnapshotErrors", report)
        self.assertNotIn("List<", report)
        policy = declaration(source, "public static class SirenTargetEligibilityWitnessPolicy")
        self.assertIn("ReferenceEquals(candidate, firstTarget)", policy)
        self.assertIn("first.known = !truncated", policy)
        sample = declaration(source, "void CaptureEligibilitySnapshot")
        target_read = declaration(source, "void ObserveNativeHuntressTarget")
        geometry = declaration(source, "static void MeasureEligibilityGeometry")
        self.assertIn("before-current-frame-diagnostic-aim-write;cached-target-age-unknown", sample)
        self.assertIn("HurtBox.readOnlyBullseyesList", sample)
        self.assertIn("HurtBox selectedHurtBox = selectedEgg.mainHurtBox", sample)
        self.assertIn("HealthComponent targetHealth = nativeTarget.healthComponent", sample)
        self.assertIn("Physics.Raycast(origin, direction, out hit, direction.magnitude", geometry)
        self.assertIn("LayerIndex.world.mask,", geometry)
        self.assertIn("QueryTriggerInteraction.UseGlobal", geometry)
        self.assertIn("catch (Exception error)", sample)
        self.assertIn("SirenNativeTargetWitnessPolicy.ReadTargetOrThrow(tracker, report)", target_read)
        self.assertNotIn("=> tracker.GetTrackingTarget()", target_read)
        read_wrapper = declaration(source, "public static HurtBox ReadTargetOrThrow(")
        self.assertIn("catch (Exception error)", read_wrapper)
        self.assertIn("throw;", read_wrapper)
        self.assertNotIn("TargetReadError", target_read)
        self.assertLess(source.index("ObserveNativeHuntressTarget(player, egg"), source.index("bridge.aim = new Vector2"))
        self.assertIn("snapshot.captured = false", sample)
        for forbidden in ("SearchForTarget(", "RefreshCandidates(", "GetTrackingTarget(", "GetField(", "GetProperty(", "FindObjectsOfType"):
            self.assertNotIn(forbidden, sample)
        self.assertIn("MaximumGlobalBullseyeScanCount = 4096", policy)
        self.assertIn("WithinCaptureBudget(report.eligibilitySnapshotAttempts)", source)
        self.assertIn("observation == SirenNativeTargetObservation.NoTarget", source)
        self.assertIn("selectedEggNetworkId == firstEligibilitySnapshotSelectedId", source)
        self.assertIn('"first-visible-primary-mismatch"', source)
        self.assertIn('"delayed-null-same-selected-egg"', source)
        self.assertEqual(source.count("SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(HurtBox.readOnlyBullseyesList"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
