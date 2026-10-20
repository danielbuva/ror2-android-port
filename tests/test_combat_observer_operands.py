"""Execute the exact production combat observer operand readers with Unity lifetime stubs."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/world/CombatSpineBoundary.cs"
FIXTURE = ROOT / "tests/fixtures/combat_observer_operands.cs"


def extract_member(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed production member: {declaration}")


HARNESS = r"""
public static class OperandHarness
{
    static void Need(bool value, string message) { if (!value) throw new System.Exception(message); }
    static void Main()
    {
        var primaryState = new EntityState();
        var bodyState = new EntityState();
        var machine = new EntityStateMachine { state = primaryState };
        var bodyMachine = new EntityStateMachine { state = bodyState };
        var primary = new GenericSkill { stateMachine = machine };
        var locator = new SkillLocator { primary = primary };
        var player = new CharacterBody { skillLocator = locator };
        var report = new CombatReport();
        EntityState weapon, observedBody;
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(ReferenceEquals(weapon, primaryState) && ReferenceEquals(observedBody, bodyState), "healthy native state identities preserved");
        Need(report.primaryStateAvailable && report.bodyStateAvailable && report.primaryStateUnavailableObservations == 0,
             "healthy reads remain available and do not count absence");
        Need(report.weaponState == typeof(EntityState).FullName && report.bodyState == typeof(EntityState).FullName, "healthy report labels use captured identities");
        Need(player.skillLocatorReads == 1 && locator.primaryReads == 1 && primary.stateMachineReads == 1 &&
             machine.stateReads == 1 && bodyMachine.stateReads == 1, "healthy path reads each native operand once");

        locator.primary = null;
        int beforePrimaryRead = primary.stateMachineReads;
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(primary.stateMachineReads == beforePrimaryRead, "unavailable primary stops before downstream machine read");
        Need(weapon == null && report.primaryStateUnavailableReason == "skillLocator.primary:clr-null" &&
             report.primaryStateUnavailableObservations == 1, "CLR-null primary is explicit and counted");
        Need(ReferenceEquals(observedBody, bodyState), "primary absence does not block body-state observation");

        var fakePrimary = new GenericSkill { destroyed = true };
        locator.primary = fakePrimary;
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(weapon == null && report.primaryStateUnavailableReason == "skillLocator.primary:unity-fake-null",
             "Unity fake-null primary is distinct from CLR-null");

        locator.primary = new GenericSkill { stateMachine = null };
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(weapon == null && report.primaryStateUnavailableReason == "primary.stateMachine:clr-null",
             "CLR-null state machine is explicit");
        locator.primary = new GenericSkill { stateMachine = new EntityStateMachine { destroyed = true } };
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(weapon == null && report.primaryStateUnavailableReason == "primary.stateMachine:unity-fake-null",
             "destroyed state machine is unavailable without dereference");

        locator.primary = new GenericSkill { stateMachine = new EntityStateMachine { state = null } };
        ProductionCombatObserver.Capture(player, bodyMachine, report, out weapon, out observedBody);
        Need(weapon == null && report.primaryStateUnavailableReason == "primary.stateMachine.state:clr-null",
             "null native state is explicit and does not produce a fake state");

        locator.primary = new GenericSkill { stateMachine = new EntityStateMachine { state = primaryState } };
        var bodyMissing = new EntityStateMachine { state = null };
        ProductionCombatObserver.Capture(player, bodyMissing, report, out weapon, out observedBody);
        Need(ReferenceEquals(weapon, primaryState) && observedBody == null &&
             report.bodyStateUnavailableReason == "bodyStateMachine.state:clr-null",
             "body-state gap is reported separately while primary sample remains intact");

        var fakeBody = new CharacterBody { destroyed = true, skillLocator = locator };
        ProductionCombatObserver.ReadPrimary(fakeBody, out weapon, out var unavailable);
        Need(unavailable == "body:unity-fake-null" && fakeBody.skillLocatorReads == 0,
             "fake-null body is distinguished without accessing its locator");

        ProductionCombatObserver.Capture(player, null, report, out weapon, out observedBody);
        Need(ReferenceEquals(weapon, primaryState) && observedBody == null &&
             report.bodyStateUnavailableReason == "bodyStateMachine:clr-null",
             "CLR-null body machine is explicit while primary observation survives");
        var fakeBodyMachine = new EntityStateMachine { destroyed = true };
        ProductionCombatObserver.Capture(player, fakeBodyMachine, report, out weapon, out observedBody);
        Need(observedBody == null && report.bodyStateUnavailableReason == "bodyStateMachine:unity-fake-null",
             "Unity fake-null body machine is distinct");

        var foreign = new System.InvalidOperationException("injected native accessor failure");
        var throwingPrimary = new ThrowingSkillLocator(foreign);
        try
        {
            ProductionCombatObserver.ReadPrimary(
                new CharacterBodyWithThrowingLocator(throwingPrimary), out weapon, out _);
            throw new System.Exception("unexpected accessor exception was swallowed");
        }
        catch (System.InvalidOperationException error)
        {
            Need(ReferenceEquals(error, foreign), "unexpected accessor exception identity is preserved");
        }
    }
}

public sealed class ThrowingSkillLocator : SkillLocator
{
    public readonly System.InvalidOperationException failure;
    public ThrowingSkillLocator(System.InvalidOperationException error) { failure = error; }
    public override GenericSkill primary { get { throw failure; } set { base.primary = value; } }
}
public sealed class CharacterBodyWithThrowingLocator : CharacterBody
{
    readonly ThrowingSkillLocator value;
    public CharacterBodyWithThrowingLocator(ThrowingSkillLocator locator) { value = locator; }
    public override SkillLocator skillLocator { get { return value; } set { } }
}
"""


class CombatObserverOperandTests(unittest.TestCase):
    def test_production_operand_readers_execute_against_lifetime_stubs(self):
        editor = Path(
            os.environ.get(
                "UNITY_EDITOR_PATH",
                "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
            )
        )
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        source = OWNER.read_text(encoding="utf-8")
        members = [
            extract_member(source, "static bool TryReadPrimaryWeaponState("),
            extract_member(source, "static bool TryReadBodyState("),
            extract_member(source, "static void CaptureCombatStateOperands("),
        ]
        fixture = FIXTURE.read_text(encoding="utf-8").replace(
            "// Production helper members are inserted here by the host test.",
            "\n".join(members),
        )
        scratch_root = ROOT / "work/host-tests"
        scratch_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="toolbot-combat-observer-", dir=scratch_root) as temporary:
            temporary = Path(temporary)
            cs, exe = temporary / "Observer.cs", temporary / "Observer.exe"
            cs.write_text(fixture + "\n" + HARNESS, encoding="utf-8")
            compiled = subprocess.run(
                [
                    str(mono),
                    str(compiler),
                    "-nologo",
                    "-langversion:9",
                    "-target:exe",
                    "-out:" + str(exe),
                    str(cs),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(mono), str(exe)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_observer_uses_one_captured_operand_set_and_does_not_write_native_state(
        self,
    ):
        source = OWNER.read_text(encoding="utf-8")
        start = source.index("public void ObserveCombat(CharacterBody player, EntityStateMachine machine)")
        body = extract_member(
            source,
            "public void ObserveCombat(CharacterBody player, EntityStateMachine machine)",
        )
        self.assertIn(
            "CaptureCombatStateOperands(player, machine, coordinator.r.combat, out weapon, out bodyState);",
            body,
        )
        self.assertNotIn("player.skillLocator.primary.stateMachine.state", body)
        self.assertIn("weapon != null && weapon != lastCombatWeapon", body)
        self.assertIn("bodyState != null && bodyState != lastCombatBody", body)
        self.assertNotIn("SetNextState", body)
        self.assertNotIn("SetSkillOverride", body)
        self.assertNotIn("stock =", body)
        self.assertGreater(start, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
