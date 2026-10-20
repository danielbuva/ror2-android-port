from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/unity/runtime/world/AutomaticSpawnBoundary.cs"
WITNESS = ROOT / "tools/unity/runtime/input/SirenEggDiagnosticInput.cs"
MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
CSC = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")


def extract_method(text: str, signature: str) -> str:
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
    raise AssertionError(f"unclosed method {signature}")


class ActivationContractTests(unittest.TestCase):
    def test_exact_production_capture_restore_helpers_with_synthetic_components(self) -> None:
        if not (MONO.is_file() and CSC.is_file()):
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        methods = [
            extract_method(SOURCE.read_text(), "internal static HuntressTracker[] CaptureEnabledRootHuntressTrackers"),
            extract_method(SOURCE.read_text(), "internal static int RestoreCapturedEnabledRootHuntressTrackers"),
        ]
        program = r"""
using System;
using System.Linq;
class HuntressTracker
{
    public bool live = true;
    public bool enabled = true;
    public object gameObject = new object();
    public static implicit operator bool(HuntressTracker value) => value != null && value.live;
}
class CharacterBody
{
    public bool live = true;
    public HuntressTracker[] root = Array.Empty<HuntressTracker>();
    public static implicit operator bool(CharacterBody value) => value != null && value.live;
    public T[] GetComponents<T>() where T : class => root.OfType<T>().ToArray();
}
static class ProductionHelpers
{
    METHODS
}
class Test
{
    static void Need(bool value, string name) { if (!value) throw new Exception(name); }
    static int Main()
    {
        var body = new CharacterBody();
        var sourceEnabled = new HuntressTracker();
        var sourceDisabled = new HuntressTracker { enabled = false };
        var destroyed = new HuntressTracker { live = false };
        body.root = new[] { sourceEnabled, sourceDisabled, destroyed };
        var captured = ProductionHelpers.CaptureEnabledRootHuntressTrackers(body);
        Need(captured.Length == 1 && ReferenceEquals(captured[0], sourceEnabled), "capture-only-live-source-enabled-root");
        sourceEnabled.enabled = false;
        Need(ProductionHelpers.RestoreCapturedEnabledRootHuntressTrackers(captured, false) == 0 && !sourceEnabled.enabled,
             "non-integrated-path-does-not-restore");
        Need(ProductionHelpers.RestoreCapturedEnabledRootHuntressTrackers(captured, true) == 1 && sourceEnabled.enabled,
             "integrated-path-restores-captured-source-enabled-root");
        Need(!sourceDisabled.enabled && destroyed.enabled, "never-enables-source-disabled-or-mutates-fake-null");
        var empty = ProductionHelpers.CaptureEnabledRootHuntressTrackers(new CharacterBody());
        Need(empty.Length == 0 && ProductionHelpers.RestoreCapturedEnabledRootHuntressTrackers(empty, true) == 0,
             "no-component-no-op");
        Need(ProductionHelpers.RestoreCapturedEnabledRootHuntressTrackers(null, true) == 0,
             "missing-capture-no-op");
        Console.WriteLine("capture/restore synthetic tests passed");
        return 0;
    }
}
""".replace("METHODS", "\n    ".join(methods))
        scratch = ROOT / "work/host-tests/huntress-tracker-activation"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            source = Path(tmp) / "ActivationContract.cs"
            output = Path(tmp) / "ActivationContract.exe"
            source.write_text(program)
            subprocess.run([str(MONO), str(CSC), f"-out:{output}", str(source)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(MONO), str(output)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("capture/restore synthetic tests passed", result.stdout)

    def test_actual_read_eligibility_helper_truth_table(self) -> None:
        if not (MONO.is_file() and CSC.is_file()):
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")
        method = extract_method(WITNESS.read_text(), "public static bool IsTrackerReadEligible")
        program = r"""
using System;
static class Policy { METHOD }
class Test
{
    static void Need(bool value, string name) { if (!value) throw new Exception(name); }
    static int Main()
    {
        Need(!Policy.IsTrackerReadEligible(false, true, true), "missing-component");
        Need(!Policy.IsTrackerReadEligible(true, false, false), "disabled-component");
        Need(!Policy.IsTrackerReadEligible(true, true, false), "inactive-component");
        Need(Policy.IsTrackerReadEligible(true, true, true), "active-component");
        Console.WriteLine("read eligibility truth table passed");
        return 0;
    }
}
""".replace("METHOD", method)
        scratch = ROOT / "work/host-tests/huntress-tracker-activation"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            source = Path(tmp) / "TrackerReadEligibility.cs"
            output = Path(tmp) / "TrackerReadEligibility.exe"
            source.write_text(program)
            subprocess.run([str(MONO), str(CSC), f"-out:{output}", str(source)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(MONO), str(output)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("read eligibility truth table passed", result.stdout)

    def test_restore_is_ordered_after_source_dependency_checks_and_before_activation(self) -> None:
        text = SOURCE.read_text()
        capture = text.index("var sourceEnabledRootHuntressTrackers = cfg.integratedWorld ?")
        disable = text.index("foreach (var component in body.GetComponents<MonoBehaviour>())", capture)
        dependency_check = text.index('"Original source-enabled root Huntress tracker dependencies"', disable)
        restore = text.index("RestoreCapturedEnabledRootHuntressTrackers(sourceEnabledRootHuntressTrackers", dependency_check)
        activate = text.index("body.gameObject.SetActive(true);", restore)
        self.assertLess(capture, disable)
        self.assertLess(disable, dependency_check)
        self.assertLess(dependency_check, restore)
        self.assertLess(restore, activate)
        self.assertIn("sourceEnabledRootHuntressTrackers, cfg.integratedWorld", text)
        self.assertIn("restoredSourceEnabledRootHuntressTrackers", text)

    def test_target_getter_is_gated_by_actual_component_activation(self) -> None:
        text = WITNESS.read_text()
        self.assertIn("lastNativeTrackerEnabled = tracker.enabled", text)
        self.assertIn("lastNativeTrackerActiveAndEnabled = tracker.isActiveAndEnabled", text)
        gate = text.index("IsTrackerReadEligible(true, tracker.enabled, tracker.isActiveAndEnabled)")
        target_read = text.index("SirenNativeTargetWitnessPolicy.ReadTargetOrThrow(tracker, report)", gate)
        self.assertLess(gate, target_read)
        self.assertEqual(text.count("tracker.GetTrackingTarget()"), 1)
        self.assertIn("SirenNativeTargetObservation.TrackerDisabled", text)
        self.assertIn("SirenNativeTargetObservation.TrackerInactive", text)


if __name__ == "__main__":
    unittest.main()
