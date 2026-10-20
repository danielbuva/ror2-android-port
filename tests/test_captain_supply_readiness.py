"""Native Captain auxiliary readiness and current-placement contracts."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"


class CaptainBeaconCanExecuteOverlay(unittest.TestCase):
    def test_live_predicate_uses_native_can_execute_without_unity_component_enabled_gate(self):
        source = OVERLAY.read_text()
        flow = source.split("void ApplyCaptainSupplyBeacon(float elapsed)", 1)[1].split("void FinishCaptainSupplyBeacon", 1)[0]
        self.assertIn("bool supplyDrop1CanExecute = CaptainSupplyDrop1CanExecute(primaryRemapped,", flow)
        self.assertIn("captainSupplyBeaconComponents[4].CanExecute());", flow)
        self.assertNotIn("captainSupplyBeaconComponents[4].enabled", flow)
        self.assertIn("nativePlacementValid = currentPlacementValid", flow)
        self.assertIn("captainSupplyBeaconCurrentPlacementValid", source)
        self.assertIn("captainSupplyBeaconCurrentPlacementObservation", source)
        self.assertIn("captainSupplyBeaconSupplyDrop1CanExecute", source)

    def test_production_phase_policy_still_requires_native_placement_and_readiness(self):
        unity = Path(
            os.environ.get(
                "UNITY_EDITOR_PATH",
                "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
            )
        )
        compiler = unity / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        runtime = unity / "MonoBleedingEdge/bin/mono"
        if not compiler.is_file() or not runtime.is_file():
            self.skipTest("pinned Unity Roslyn/Mono unavailable")
        source = OVERLAY.read_text()
        start = source.index("public sealed class CaptainSupplyBeaconSequence")
        opening = source.index("{", start)
        depth = 0
        end = None
        for i in range(opening, len(source)):
            depth += source[i] == "{"
            depth -= source[i] == "}"
            if depth == 0:
                end = i + 1
                break
        self.assertIsNotNone(end)
        policy = source[start:end]
        helper_start = source.index("public static bool CaptainSupplyDrop1CanExecute(")
        helper_open = source.index("{", helper_start)
        helper_depth = 0
        helper_end = None
        for i in range(helper_open, len(source)):
            helper_depth += source[i] == "{"
            helper_depth -= source[i] == "}"
            if helper_depth == 0:
                helper_end = i + 1
                break
        self.assertIsNotNone(helper_end)
        helper = source[helper_start:helper_end]
        helper_host = r"""using System;
public static class SurvivorSkillInputCoverage { HELPER }
public static class DisabledSupplyHost
{
    static void Need(bool value, string message) { if (!value) throw new Exception(message); }
    static CaptainSupplyBeaconSequence.Observation Ready(float t) => new CaptainSupplyBeaconSequence.Observation {
        elapsedSeconds=t, exactCaptainOwner=true, exactDefaultSupplySkill=true, isolatedDiagnosticInputOwned=true };
    static CaptainSupplyBeaconSequence AtPlacement(float t)
    {
        var s = new CaptainSupplyBeaconSequence();
        var o=Ready(0); o.specialCanExecute=true; s.Step(o);
        o=Ready(.1f); o.specialInputEdge=true; o.specialAuthorityCallback=true; o.specialServerCallback=true; s.Step(o);
        o=Ready(.2f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true; s.Step(o);
        return s;
    }
    public static void Run()
    {
        bool componentEnabled = false; // Native Captain keeps the auxiliary GenericSkill disabled.
        bool nativeCanExecute = true;
        bool primaryRemapped = true;
        bool supplyReady = SurvivorSkillInputCoverage.CaptainSupplyDrop1CanExecute(primaryRemapped, nativeCanExecute);
        Need(!componentEnabled && supplyReady, "disabled slot must use its native SkillDef.CanExecute result");
        var s = new CaptainSupplyBeaconSequence();
        var o = Ready(0); o.specialCanExecute=true; s.Step(o);
        o=Ready(.1f); o.specialInputEdge=true; o.specialAuthorityCallback=true; o.specialServerCallback=true; s.Step(o);
        o=Ready(.2f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true; s.Step(o);
        o=Ready(.3f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true;
        o.nativePlacementValid=false; o.supplyDrop1CanExecute=supplyReady;
        var blocked=s.Step(o);
        Need(blocked.requestInputSlot==-1 && blocked.phase==CaptainSupplyBeaconSequence.Phase.AwaitingValidPlacement,
             "CanExecute alone must not bypass missing native placement");
        o=Ready(.4f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true;
        o.nativePlacementValid=true; o.supplyDrop1CanExecute=supplyReady;
        var pulse=s.Step(o);
        Need(pulse.requestInputSlot==0 && pulse.phase==CaptainSupplyBeaconSequence.Phase.AwaitingSupplyEdgeAndCallbacks,
             "valid placement plus native CanExecute should request the original primary pulse");

        var noPlacement=AtPlacement(0);
        o=Ready(8.3f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true;
        o.nativePlacementValid=false; o.supplyDrop1CanExecute=true;
        Need(noPlacement.Step(o).outcome=="native-placement-not-valid", "last invalid placement must be named precisely");
        var noReadiness=AtPlacement(0);
        o=Ready(8.3f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true;
        o.nativePlacementValid=true; o.supplyDrop1CanExecute=false;
        Need(noReadiness.Step(o).outcome=="native-supply-drop1-not-ready", "last native readiness failure must be distinct");
        var neither=AtPlacement(0);
        o=Ready(8.3f); o.setupSupplyDropState=true; o.setupPrimaryIsSupplyDrop1=true; o.setupSecondaryIsSupplyDrop2=true;
        o.nativePlacementValid=false; o.supplyDrop1CanExecute=false;
        Need(neither.Step(o).outcome=="native-placement-and-supply-drop1-not-ready", "both last operands must be named");
    }
}""".replace("HELPER", helper)
        fixture = ROOT / "tests/fixtures/CaptainSupplyBeaconPhaseHost.cs"
        with tempfile.TemporaryDirectory(prefix="captain-beacon-placement-") as name:
            work = Path(name)
            policy_file = work / "CaptainSupplyBeaconSequence.cs"
            policy_file.write_text("using System;\n" + policy)
            fixture_file = work / "PhaseHost.cs"
            fixture_file.write_text(fixture.read_text().replace("static void Main()\n    {", "static void Main()\n    {\n        DisabledSupplyHost.Run();", 1))
            helper_file = work / "DisabledSupplyHost.cs"
            helper_file.write_text(helper_host)
            exe = work / "captain-phase-host.exe"
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(exe), str(policy_file), str(fixture_file), str(helper_file)],
                cwd=work,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            ran = subprocess.run(
                [str(runtime), str(exe)],
                cwd=work,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout)
            self.assertIn("Captain supply beacon phase and refusal contracts passed", ran.stdout)


if __name__ == "__main__":
    unittest.main()
