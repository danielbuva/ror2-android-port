"""Contracts for the proposed Toolbot-only native offhand input sequence."""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
OWNER = REPO_ROOT / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
SESSION = REPO_ROOT / "tools/unity/runtime/session/PortSession.cs"
WORLD = REPO_ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs"


def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unbalanced method: " + signature)


class ToolbotOffhandSequence(unittest.TestCase):
    def setUp(self):
        self.source = OWNER.read_text()

    def test_opt_in_defaults_off_and_preserves_existing_coverage_route(self):
        self.assertIn("bool toolbotOffhand = false", self.source)
        self.assertIn("toolbotOffhandRequested = toolbotOffhandMode", self.source)
        self.assertIn('toolbotOffhandMode ? "toolbot-offhand-sequence" : isolationTarget < 0 ? "all-four-slots"', self.source)
        apply = method(self.source, "public void Apply(float elapsed)")
        self.assertRegex(apply, r"if \(toolbotOffhandMode\)\s*\{\s*ApplyToolbotOffhand\(elapsed\);\s*return;")
        self.assertIn('Stop("all-canonical-callbacks-observed")', self.source)
        self.assertIn("toolbotOffhandRequests", self.source)
        self.assertIn("contextual Cancel SkillDef", self.source)

    def test_live_owner_is_exact_and_only_pulses_native_inputs(self):
        capture = method(self.source, "void CaptureToolbotOffhandIdentity()")
        self.assertIn('BodyCatalog.FindBodyIndex("ToolbotBody")', capture)
        self.assertIn('"ToolbotBodyFireNailgun"', capture)
        self.assertRegex(capture, r'ToolbotSelectedComponentMatches\(\s*0, "ToolbotBodyPrimary1", "ToolbotBodyFireNailgun", 141, 0, 195\)')
        self.assertRegex(capture, r'ToolbotSelectedComponentMatches\(\s*1, "ToolbotBodyPrimary2", "ToolbotBodyFireBuzzsaw", 142, 3, 193\)')
        self.assertRegex(capture, r'ToolbotSelectedComponentMatches\(\s*4, "ToolbotBodySpecialFamily", "ToolbotDualWield", 144, 1, 201\)')
        # Copying native stock into the report is allowed; mutating it is not.
        without_stock_observation = self.source.replace("observation.stock = secondary.stock;", "", 1)
        self.assertNotRegex(without_stock_observation, r"ExecuteIfReady|SetNextState|\.stock\s*=|cooldown\s*=")
        start = method(self.source, "bool BeginToolbotPulse(int slot, float elapsed)")
        self.assertIn("isolatedDiagnosticSkillSlot = slot", start)
        self.assertIn("isolatedDiagnosticSkillPulse = true", start)
        self.assertIn("report.toolbotOffhandRequests >= 2", self.source)
        self.assertIn("SurvivorCombatOutputObserver.Report combatReport", self.source)
        self.assertIn("combatOutput.bodyDamageEvents", self.source)
        self.assertIn("combatOutput.damageFactCount", self.source)

    def test_launch_selector_is_explicit_assisted_and_reaches_existing_owner(self):
        session = SESSION.read_text()
        self.assertIn("public bool diagnosticToolbotOffhand;", session)
        validated = method(session, "if (r.diagnosticToolbotOffhand)")
        self.assertIn('r.selectedSurvivor != "Toolbot"', validated)
        self.assertIn("entry.componentIndex == 1 && entry.familyCatalogIndex == 142", validated)
        self.assertIn("entry.variantIndex == 3 && entry.skillCatalogIndex == 193", validated)
        self.assertIn("entry.componentIndex == 4 && entry.familyCatalogIndex == 144", validated)
        self.assertIn("entry.variantIndex == 1 && entry.skillCatalogIndex == 201", validated)
        self.assertIn("r.developerSkillIsolationAssisted = true", validated)
        world = WORLD.read_text()
        self.assertIn("coordinator.r.diagnosticToolbotOffhand,", world)
        self.assertIn('mode == "toolbot-offhand-sequence"', world)
        self.assertIn("explicit Toolbot offhand selector", world)

    def test_sequence_policy_cannot_skip_native_stance_edge_or_weapon_state(self):
        policy = method(self.source, "public static int AdvanceToolbotOffhandPhase(")
        self.assertIn("specialInputEdge && specialCallbacks", policy)
        self.assertIn("exactDualWieldState && effectiveOffhandOverride && weapon2Present", policy)
        self.assertIn("secondaryInputEdge && secondaryCallbacks", policy)
        self.assertIn("buzzsawOnWeapon2", policy)
        self.assertIn('"EntityStates.Toolbot.ToolbotDualWield"', self.source)
        self.assertIn('"EntityStates.Toolbot.FireBuzzsaw"', self.source)
        self.assertIn('"Weapon2"', self.source)
        calls = re.findall(r"AdvanceToolbotOffhandPhase\((.*?)\)", self.source, re.S)[1:]
        self.assertTrue(calls)
        self.assertTrue(all(len(call.split(",")) == 11 for call in calls), "all production phase calls must supply the full gate tuple")

    @unittest.skipUnless(
        Path(
            os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"),
            "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe",
        ).is_file()
        and Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"), "MonoBleedingEdge/bin/mono").is_file(),
        "pinned Unity Mono compiler/runtime unavailable",
    )
    def test_extracted_production_phase_policy_requires_each_observed_boundary(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        runtime = editor / "MonoBleedingEdge/bin/mono"
        helper = method(self.source, "public static int AdvanceToolbotOffhandPhase(")
        harness = r"""using System;
public static class Program
{
    static void Need(bool ok, string why) { if (!ok) throw new Exception(why); }
    public static void Main()
    {
        int p = 0;
        Need(AdvanceToolbotOffhandPhase(p, false, false, false, false, false, false, false, false, false, false) == 0,
             "no synthetic special pulse");
        p = AdvanceToolbotOffhandPhase(p, true, false, false, false, false, false, false, false, false, false);
        Need(p == 1, "special input pulse starts wait");
        Need(AdvanceToolbotOffhandPhase(p, true, false, true, false, false, false, false, false, false, false) == 1,
             "callback without input edge is insufficient");
        p = AdvanceToolbotOffhandPhase(p, true, true, true, false, false, false, false, false, false, false);
        Need(p == 2, "special edge plus native callback pair");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, false, true, false, false, false, false) == 2,
             "override mismatch blocks secondary");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, true, false, false, false, false, false) == 2,
             "missing Weapon2 blocks secondary");
        p = AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, false, false, false, false);
        Need(p == 3, "only exact stance, override and Weapon2 ready");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, false, false, false, false) == 3,
             "no secondary pulse remains waiting");
        p = AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, true, false, false, false);
        Need(p == 4, "secondary pulse starts callback wait");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, true, true, false, false) == 4,
             "input edge without callback pair is insufficient");
        p = AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, true, true, true, false);
        Need(p == 5, "secondary edge and native callback pair");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, true, true, true, false) == 5,
             "callback without Weapon2 Buzzsaw state is not success");
        Need(AdvanceToolbotOffhandPhase(p, true, true, true, true, true, true, true, true, true, true) == 6,
             "complete only after observed native Weapon2 state");
        Console.WriteLine("production Toolbot offhand phase policy passed");
    }
}"""
        with tempfile.TemporaryDirectory(prefix="toolbot-offhand-policy-") as temp:
            root = Path(temp)
            source = root / "OwnerPolicy.cs"
            program = root / "Harness.cs"
            exe = root / "policy.exe"
            # Put the exact extracted production method beside the host harness.
            program.write_text(harness.replace("public static class Program\n{", "public static class Program\n{\n" + helper + "\n", 1))
            source.write_text("")
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(exe), str(program)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            run = subprocess.run([str(runtime), str(exe)], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("production Toolbot offhand phase policy passed", run.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
