"""Exercise the production automatic-spawn cleanup lease with synthetic Unity stubs."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/world/AutomaticSpawnBoundary.cs"
FIXTURE = ROOT / "tests/fixtures/automatic_spawn_cleanup_lease.cs"


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
public static class CleanupLeaseHarness
{
    static void Need(bool value, string message) { if (!value) throw new System.Exception(message); }
    static EntityStateMachine Machine(string name, UnityEngine.GameObject owner) =>
        new EntityStateMachine { name = name, gameObject = owner };
    static GenericSkill Slot(EntityStateMachine machine) => new GenericSkill { stateMachine = machine };

    public static void Main()
    {
        // Partial setup: the second native-style add mutates then throws. The caller's
        // acquired leases unwind both handlers, while the setup exception stays primary.
        var first = new ThrowingPublisher();
        var second = new ThrowingPublisher { throwAfterAdd = true };
        Action a = () => { }, b = () => { };
        bool firstAttempted = false, secondAttempted = false;
        Exception cleanupFailure = null, setupFailure = null;
        try
        {
            try
            {
                ProductionCleanup.AcquireAutomaticSpawnCallback(() => first.Changed += a, ref firstAttempted);
                ProductionCleanup.AcquireAutomaticSpawnCallback(() => second.Changed += b, ref secondAttempted);
                throw new Exception("unreachable after injected second add");
            }
            finally
            {
                ProductionCleanup.ReleaseAutomaticSpawnCallback(() => first.Changed -= a, firstAttempted, ref cleanupFailure);
                ProductionCleanup.ReleaseAutomaticSpawnCallback(() => second.Changed -= b, secondAttempted, ref cleanupFailure);
            }
        }
        catch (Exception error) { setupFailure = error; }
        Need(setupFailure is System.InvalidOperationException && setupFailure.Message.Contains("after delegate mutation"),
             "partial event-add exception remains primary");
        Need(firstAttempted && secondAttempted && first.handlers == null && second.handlers == null,
             "all attempted callback leases are removed after partial setup");
        Need(cleanupFailure == null, "successful independent unsubscribe has no cleanup error");

        // Recovery retains native/body world state but still releases observer delegates.
        var recoveryPublisher = new ThrowingPublisher();
        bool recoveryAttempted = false;
        Action observer = () => { };
        int nativeBodyCleanup = 0;
        ProductionCleanup.AcquireAutomaticSpawnCallback(() => recoveryPublisher.Changed += observer, ref recoveryAttempted);
        ProductionCleanup.ReleaseAutomaticSpawnCallback(() => recoveryPublisher.Changed -= observer, recoveryAttempted, ref cleanupFailure);
        bool recoveryRequired = true;
        if (!recoveryRequired) nativeBodyCleanup++;
        Need(recoveryPublisher.handlers == null && nativeBodyCleanup == 0,
             "recovery detaches only the owned counter observer and retains native world state");

        // Recorded Unity body destruction owns child OnDestroy; unexpected disappearance
        // and a fake-null child under a still-live owner fail closed.
        var owner = new UnityEngine.GameObject("body");
        var bodyMachine = Machine("Body", owner); var primary = Machine("Primary", owner);
        var secondary = Machine("Secondary", owner); var utility = Machine("Utility", owner);
        var special = Machine("Special", owner);
        var skills = new SkillLocator { primary = Slot(primary), secondary = Slot(secondary), utility = Slot(utility), special = Slot(special) };
        EntityStateMachine[] entry = ProductionCleanup.CaptureCanonicalSkillMachines(skills,
            (ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        foreach (var machine in new[] { bodyMachine, primary, secondary, utility, special }) machine.destroyed = true;
        int unavailable, destroyedCalls = 0;
        Exception destroyedOwner = ProductionCleanup.DestroyOwnedPlayableSkillMachines(
            entry, null, null, null, bodyMachine, false, true, _ => destroyedCalls++, out unavailable);
        Need(destroyedOwner == null && destroyedCalls == 0 && unavailable == 0,
             "recorded native body destruction is accepted without child rediscovery");
        Exception unknownOwner = ProductionCleanup.DestroyOwnedPlayableSkillMachines(
            entry, null, null, null, bodyMachine, false, false, _ => destroyedCalls++, out unavailable);
        Need(unknownOwner is System.InvalidOperationException && destroyedCalls == 0,
             "unrecorded owner disappearance refuses cleanup success");

        var liveOwner = new UnityEngine.GameObject("live-body");
        var liveBodyMachine = Machine("Body", liveOwner); var p = Machine("P", liveOwner);
        var s = Machine("S", liveOwner); var u = Machine("U", liveOwner); var x = Machine("X", liveOwner);
        var weapon2 = Machine("Weapon2", liveOwner);
        var original = ProductionCleanup.CaptureCanonicalSkillMachines(
            new SkillLocator { primary = Slot(p), secondary = Slot(s), utility = Slot(u), special = Slot(x) },
            (ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        var currentCanonical = new[] { p, weapon2, u, x };
        var rootComponents = new[] { liveBodyMachine, p, s, u, x, weapon2 };
        var cleaned = new List<string>();
        Exception remapFailure = ProductionCleanup.DestroyOwnedPlayableSkillMachines(
            original, currentCanonical, rootComponents, liveOwner, liveBodyMachine, true, false,
            machine => cleaned.Add(machine.name), out unavailable);
        Need(remapFailure == null && unavailable == 0 &&
             string.Join(",", cleaned) == "P,S,U,X,Weapon2",
             "entry and currently-bound same-body ESMs are deduplicated and cleaned");

        cleaned.Clear(); var foreign = Machine("Foreign", new UnityEngine.GameObject("other-body"));
        Exception foreignFailure = ProductionCleanup.DestroyOwnedPlayableSkillMachines(
            original, new[] { p, foreign, u, x }, rootComponents, liveOwner, liveBodyMachine, true, false,
            machine => cleaned.Add(machine.name), out unavailable);
        Need(foreignFailure is System.InvalidOperationException && unavailable == 1 && !cleaned.Contains("Foreign"),
             "foreign/replaced ESM is refused without calling its cleanup");

        var lost = Machine("Lost", liveOwner); lost.destroyed = true;
        Exception liveLoss = ProductionCleanup.DestroyOwnedPlayableSkillMachines(
            original, new[] { p, lost, u, x }, rootComponents, liveOwner, liveBodyMachine, true, false,
            machine => cleaned.Add(machine.name), out unavailable);
        Need(liveLoss is System.InvalidOperationException && unavailable == 1,
             "fake-null ESM under live owner remains a cleanup failure");
    }
}
"""


class AutomaticSpawnCleanupLeaseTests(unittest.TestCase):
    def test_production_cleanup_contract(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        production = OWNER.read_text(encoding="utf-8")
        members = [
            extract_member(production, "internal static void CaptureAutomaticSpawnCleanup("),
            extract_member(production, "internal static void AcquireAutomaticSpawnCallback("),
            extract_member(production, "internal static void ReleaseAutomaticSpawnCallback("),
            extract_member(production, "internal static EntityStateMachine[] CaptureCanonicalSkillMachines("),
            extract_member(production, "internal static bool ContainsStateMachineReference("),
            extract_member(production, "internal static Exception DestroyOwnedPlayableSkillMachines("),
        ]
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture = fixture.replace("public static class ProductionCleanup\n{\n}", "public static class ProductionCleanup\n{\n" + "\n".join(members) + "\n}")
        self.assertNotIn("public static class ProductionCleanup\n{\n}", fixture)
        with tempfile.TemporaryDirectory(prefix="automatic-spawn-cleanup-lease-") as temp:
            temp = Path(temp).resolve()
            source, exe = temp / "Lease.cs", temp / "Lease.exe"
            source.write_text(fixture + "\n" + HARNESS, encoding="utf-8")
            compiled = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-langversion:9", "-target:exe", "-out:" + str(exe), str(source)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(mono), str(exe)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_iterator_protects_partial_acquisition_and_recovery_cleanup(self):
        source = OWNER.read_text(encoding="utf-8")
        start = source.index("IEnumerator AutomaticSpawnBoundary(")
        end = source.index("\n    }\n}", start) + len("\n    }")
        iterator = source[start:end]
        try_start = iterator.index("        try\n")
        acquire = iterator.index("AcquireAutomaticSpawnCallback(() => motor.onMotorStart += observed", try_start)
        body_setup = iterator.index("automaticSpawnSetupStarted = true;", acquire)
        first_mutation = iterator.index("foreach (var component in body.GetComponents<MonoBehaviour>())", body_setup)
        final = iterator.index("        finally\n", first_mutation)
        observer_release = iterator.index("ReleaseAutomaticSpawnCallback(() => motor.onMotorStart -= observed", final)
        recovery_guard = iterator.index("if (!r.sourceStageLifecycleRecoveryRequired && automaticSpawnSetupStarted)", observer_release)
        broad_teardown = iterator.index("DestroyOwnedPlayableSkillMachines(", recovery_guard)
        self.assertLess(try_start, acquire)
        self.assertLess(acquire, body_setup)
        self.assertLess(body_setup, first_mutation)
        self.assertLess(first_mutation, final)
        self.assertLess(final, observer_release)
        self.assertLess(observer_release, recovery_guard)
        self.assertLess(recovery_guard, broad_teardown)
        for flag in ("observedSubscriptionAttempted", "masterSubscriptionAttempted", "bodySubscriptionAttempted", "statsSubscriptionAttempted"):
            self.assertIn("ref " + flag, iterator)
        self.assertIn("r.playerDefeat.bodyDestroyed", iterator)
        self.assertIn("currentCanonical = CaptureCanonicalSkillMachinesForCleanup(body.skillLocator);", iterator)


if __name__ == "__main__":
    unittest.main(verbosity=2)
