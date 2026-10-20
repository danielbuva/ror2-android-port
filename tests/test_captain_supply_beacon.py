import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lab"))
import survivor_check


class CaptainSupplyBeaconContracts(unittest.TestCase):
    def test_selector_is_default_off_and_strictly_exclusive(self):
        ordinary = survivor_check.survivor_selection("attempt", "Captain")
        self.assertNotIn("diagnosticCaptainSupplyBeacon", ordinary)
        selected = survivor_check.survivor_selection("attempt", "Captain", captain_supply_beacon=True)
        self.assertTrue(selected["diagnosticCaptainSupplyBeacon"])
        self.assertTrue(selected["developerSurvivorOverride"])
        self.assertIn("Assisted", selected["debugOptions"]["purpose"])
        self.assertNotIn("profile", selected)
        for kwargs in (
            {"survivor": "Commando", "captain_supply_beacon": True},
            {"survivor": "Captain", "skill_slot": "special", "captain_supply_beacon": True},
            {"survivor": "Captain", "skill_variant_override": {"survivor": "Captain", "entries": []}, "captain_supply_beacon": True},
            {"survivor": "Captain", "toolbot_offhand": True, "captain_supply_beacon": True},
        ):
            survivor = kwargs.pop("survivor")
            with self.assertRaises(ValueError):
                survivor_check.survivor_selection("attempt", survivor, **kwargs)

    def test_check_refuses_batches_and_conflicting_modes_before_device_access(self):
        for args in (
            ("all",),
            ("Captain,Commando",),
        ):
            with self.assertRaises(ValueError):
                survivor_check.check_survivors(args[0], captain_supply_beacon=True)
        with self.assertRaises(ValueError):
            survivor_check.check_survivors("Captain", skill_slot="special", captain_supply_beacon=True)
        with self.assertRaises(ValueError):
            survivor_check.check_survivors("Captain", skill_variants="unused.json", captain_supply_beacon=True)

    def test_runtime_owner_uses_read_only_native_witnesses_and_owned_edge_counter(self):
        owner = (ROOT / "tools" / "unity" / "runtime" / "input" / "SurvivorSkillInputCoverage.cs").read_text()
        self.assertEqual(owner.count("using System;"), 1)
        self.assertLess(owner.index("using System;"), owner.index("public sealed class SurvivorSkillInputCoverage"))
        self.assertLess(owner.index("using System;"), owner.index("public sealed class CaptainSupplyBeaconSequence"))
        self.assertIn("SetDiagnosticInputEdgeWitness(true)", owner)
        self.assertIn("TryGetDiagnosticInputEdgeCount(slot, out captainPulseEdgeBaseline)", owner)
        self.assertIn("ClassifyDiagnosticInputEdge(captainPulseEdgeBaseline, current", owner)
        self.assertIn("GetDeployableCount(DeployableSlot.CaptainSupplyDrop)", owner)
        self.assertIn("CaptainSetupSupplyBeaconIdentityMatches(captainSpecialSkillDef.activationStateMachineName,", owner)
        self.assertIn("captainSpecialStateType.FullName", owner)
        self.assertIn("captainSupplyBeaconDeployablePresentAtReturn", owner)
        self.assertIn('GetField("currentPlacementInfo"', owner)
        self.assertIn('GetField("ok"', owner)
        self.assertNotIn("currentPlacementInfo =", owner)
        captain_flow = owner.split("void ApplyCaptainSupplyBeacon(float elapsed)", 1)[1].split("void FinishCaptainSupplyBeacon", 1)[0]
        self.assertNotIn("ExecuteIfReady", captain_flow)
        self.assertNotIn("ForceState", captain_flow)
        self.assertNotIn("cooldownRemaining =", captain_flow)
        self.assertNotIn("stock =", captain_flow)
        teardown = owner.split("public void Dispose()", 1)[1]
        captain_dispose = teardown.split("if (toolbotOffhandMode && bridge)", 1)[0]
        self.assertIn("if (!unresolvedNativeState)", captain_dispose)
        self.assertIn("SetDiagnosticInputEdgeWitness(false)", captain_dispose)

    def test_exact_owner_policies_compile_and_execute_offline(self):
        unity = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        compiler = unity / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        runtime = unity / "MonoBleedingEdge/bin/mono"
        if not compiler.is_file() or not runtime.is_file():
            self.skipTest("pinned Unity Roslyn/Mono unavailable")
        owner = (ROOT / "tools" / "unity" / "runtime" / "input" / "SurvivorSkillInputCoverage.cs").read_text()

        def block(signature):
            start = owner.index(signature)
            opening = owner.index("{", start)
            depth = 0
            for end in range(opening, len(owner)):
                depth += owner[end] == "{"
                depth -= owner[end] == "}"
                if depth == 0:
                    return owner[start : end + 1]
            raise AssertionError("unbalanced C# source block: " + signature)

        enum = re.search(r"public enum DiagnosticInputEdgeStatus\s*\{[^}]+\}", owner).group(0)
        classifier = block("public static DiagnosticInputEdgeStatus ClassifyDiagnosticInputEdge(")
        policy = block("public sealed class CaptainSupplyBeaconSequence")
        source = ROOT / "tests" / "fixtures" / "CaptainSupplyBeaconPhaseHost.cs"
        phase_host = source.read_text()
        phase_host = phase_host.replace("static void Main()\n    {", "static void Main()\n    {\n        EdgeHost.Run();", 1)
        edge_host = """using System;
public static class EdgeHost
{
    static void Need(bool condition, string message) { if (!condition) throw new Exception(message); }
    public static void Run()
    {
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(7, 7, true, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.None, "no edge");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(7, 8, false, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.None, "same tick");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(7, 8, true, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.Fresh, "one later edge");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(8, 9, true, true) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.Multiple, "second edge for one pulse");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(7, 6, true, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.CounterReset, "counter reset");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(-1, 0, true, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.CounterReset, "negative baseline");
        Need(SurvivorSkillInputCoverage.ClassifyDiagnosticInputEdge(7, 9, true, false) == SurvivorSkillInputCoverage.DiagnosticInputEdgeStatus.Multiple, "ambiguous edge delta");
    }
}
public static class SurvivorSkillInputCoverage
{
    ENUM
    CLASSIFIER
}"""
        edge_host = edge_host.replace("ENUM", enum).replace("CLASSIFIER", classifier)
        with tempfile.TemporaryDirectory(prefix="captain-supply-host-") as temp_name:
            temp = Path(temp_name)
            policy_file = temp / "CaptainSupplyBeaconSequence.cs"
            policy_file.write_text("using System;\n" + policy)
            phase_file = temp / "PhaseHost.cs"
            phase_file.write_text(phase_host)
            edge_file = temp / "EdgeHost.cs"
            edge_file.write_text(edge_host)
            exe = temp / "captain-phase-host.exe"
            compile_result = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(exe), str(policy_file), str(phase_file), str(edge_file)],
                cwd=temp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
            run = subprocess.run([str(runtime), str(exe)], cwd=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("Captain supply beacon phase and refusal contracts passed", run.stdout)

    def test_assessor_requires_registered_native_output_and_lifetime_return(self):
        first = {"profile": {"appliedRuns": 13}}
        coverage = {
            "mode": "captain-supply-beacon-sequence",
            "captainSupplyBeaconRequested": True,
            "captainSupplyBeaconDefaultIdentityValidated": True,
            "captainSupplyBeaconSpecialEdgeObserved": True,
            "captainSupplyBeaconSupplyEdgeObserved": True,
            "captainSupplyBeaconSetupStateObserved": True,
            "captainSupplyBeaconSlotRemapObserved": True,
            "captainSupplyBeaconCallStateObserved": True,
            "captainSupplyBeaconDeployablePresentAtReturn": True,
            "captainSupplyBeaconOutcome": "captain-supply-beacon-sequence-complete",
            "captainSupplyBeaconPhase": 7,
            "captainSupplyBeaconRequests": 2,
            "captainSupplyBeaconPlacementValid": True,
            "captainSupplyBeaconDeployableRegistered": True,
            "captainSupplyBeaconDeployablesBefore": 0,
            "captainSupplyBeaconDeployablesAfter": 1,
            "captainSupplyBeaconPendingNativeState": False,
            "captainSupplyBeaconBodyState": "EntityStates.GenericCharacterMain",
            "captainSpecialAuthorityBefore": 0,
            "captainSpecialAuthorityAfter": 1,
            "captainSpecialServerBefore": 0,
            "captainSpecialServerAfter": 1,
            "captainSupplyAuthorityBefore": 0,
            "captainSupplyAuthorityAfter": 1,
            "captainSupplyServerBefore": 0,
            "captainSupplyServerAfter": 1,
            "slots": [
                {"requests": 1, "inputBankEdges": 1},
                {"requests": 0, "inputBankEdges": 0},
                {"requests": 0, "inputBankEdges": 0},
                {"requests": 1, "inputBankEdges": 1},
            ],
        }
        final = {
            "phase": "integrated-world-playing",
            "skillInputCoverage": coverage,
            "debugAcceleration": {"everAssisted": True},
            "profile": {"appliedRuns": 13},
            "stageProgress": {"transitions": 0, "transporting": False},
            "stage": {"scene": "lakes"},
            "survivorSkills": {
                "components": [
                    {"componentIndex": 3, "authorityActivations": 1, "serverActivations": 1},
                    {"componentIndex": 4, "authorityActivations": 1, "serverActivations": 1},
                ]
            },
        }
        self.assertEqual([], survivor_check.assess_captain_supply_beacon("captain-supply-beacon-sequence-complete", first, final, []))
        broken = dict(final)
        broken["skillInputCoverage"] = dict(coverage, captainSupplyBeaconDeployableRegistered=False, captainSupplyBeaconPendingNativeState=True)
        self.assertTrue(survivor_check.assess_captain_supply_beacon("captain-supply-beacon-sequence-complete", first, broken, []))


if __name__ == "__main__":
    unittest.main()
