"""Execute the production equipment expansion-mask ownership contract."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools/unity/runtime/world/EnemyRewardBoundary.cs"
SESSION = ROOT / "tools/unity/runtime/session/PortSession.cs"
FIXTURE = ROOT / "tests/fixtures/reward_equipment_mask_lease.cs"
HARNESS = r"""
public static class LeaseHostHarness
{
    static void Check(bool value, string name) { if (!value) throw new System.Exception(name); }
    static void Throws(System.Action action, string message)
    {
        bool threw = false; try { action(); } catch (System.Exception) { threw = true; }
        Check(threw, message);
    }
    public static void Main()
    {
        EquipmentMask.rents = EquipmentMask.returns = 0;
        var expansion = new ExpansionDef { enabled = false };
        EquipmentCatalog.allEquipment = new[] { EquipmentIndex.Base, EquipmentIndex.ExpansionA, EquipmentIndex.ExpansionB };
        EquipmentCatalog.Set(EquipmentIndex.Base, null);
        EquipmentCatalog.Set(EquipmentIndex.ExpansionA, expansion);
        EquipmentCatalog.Set(EquipmentIndex.ExpansionB, expansion);
        var destroyed = new Run { destroyed = true };
        var invalid = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        Throws(() => invalid.Acquire(destroyed), "Unity fake-null Run accepted");
        Check(EquipmentMask.rents == 0 && invalid.Mask == null, "fake-null refusal rented or retained a mask");

        var run = new Run();
        var lease = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        lease.Acquire(run);
        var exact = lease.Mask;
        Check(EquipmentMask.rents == 1 && run.expansionLockedEquipment == exact, "early acquisition didn't attach exact rented mask");
        Check(!exact.Contains(EquipmentIndex.Base) && exact.Contains(EquipmentIndex.ExpansionA) && exact.Contains(EquipmentIndex.ExpansionB),
              "pre-rule refresh failed to lock all required expansions");
        Check(run.expansionChecks == 0, "pre-rule refresh speculated about expansion enablement");
        lease.Acquire(run);
        Check(EquipmentMask.rents == 1 && System.Object.ReferenceEquals(exact, lease.Mask), "same-owner reuse double-rented or swapped mask");
        Throws(() => lease.Acquire(new Run()), "foreign Run accepted existing lease");
        Check(EquipmentMask.rents == 1 && System.Object.ReferenceEquals(exact, run.expansionLockedEquipment), "foreign refusal changed owner");

        expansion.enabled = true;
        Check(lease.Refresh(true) == 0 && run.expansionChecks == 2, "rules-ready refresh did not use native expansion predicate");
        expansion.enabled = false;
        Check(lease.Refresh(true) == 2 && run.expansionChecks == 4, "native expansion disable was not retained");
        lease.Refresh(false);
        Check(run.expansionChecks == 4 && exact.Contains(EquipmentIndex.ExpansionA), "pre-rule refresh lost all-expansions-locked policy");
        lease.Release(); lease.Release();
        Check(run.expansionLockedEquipment == null && EquipmentMask.returns == 1, "normal cleanup did not detach/return once");

        var foreignMask = EquipmentMask.Rent();
        var run2 = new Run { expansionLockedEquipment = foreignMask };
        var refused = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        Throws(() => refused.Acquire(run2), "pre-existing foreign mask overwritten");
        Check(System.Object.ReferenceEquals(foreignMask, run2.expansionLockedEquipment) && EquipmentMask.rents == 2,
              "wrong-owner refusal rented/changed a foreign mask");
        EquipmentMask.Return(foreignMask);

        EquipmentCatalog.Remove(EquipmentIndex.ExpansionB);
        var partialRun = new Run();
        var partial = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        Throws(() => partial.Acquire(partialRun), "invalid catalog identity accepted");
        var partialMask = partial.Mask;
        Check(partialMask != null && System.Object.ReferenceEquals(partialMask, partialRun.expansionLockedEquipment),
              "partial setup lost cleanup ownership");
        partial.Release(); partial.Release();
        Check(partialRun.expansionLockedEquipment == null && EquipmentMask.returns == 3,
              "partial cleanup did not detach/return once");

        EquipmentCatalog.Set(EquipmentIndex.ExpansionB, expansion);
        EquipmentMask.throwOnAdd = EquipmentIndex.ExpansionA;
        var addFailureRun = new Run();
        var addFailure = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        Throws(() => addFailure.Acquire(addFailureRun), "injected population failure accepted");
        var partialAddMask = addFailure.Mask;
        Check(partialAddMask != null && System.Object.ReferenceEquals(partialAddMask, addFailureRun.expansionLockedEquipment),
              "population failure lost the exact cleanup lease");
        addFailure.Release(); addFailure.Release();
        Check(addFailureRun.expansionLockedEquipment == null && EquipmentMask.returns == 4,
              "population-failure cleanup did not return exactly once");
        EquipmentMask.throwOnAdd = null;

        var destroyedReleaseRun = new Run();
        var destroyedRelease = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        destroyedRelease.Acquire(destroyedReleaseRun);
        var destroyedOwned = destroyedRelease.Mask;
        destroyedReleaseRun.destroyed = true;
        destroyedRelease.Release(); destroyedRelease.Release();
        Check(destroyedRelease.Mask == null && System.Object.ReferenceEquals(destroyedReleaseRun.expansionLockedEquipment, destroyedOwned) &&
                  EquipmentMask.returns == 5,
              "destroyed Run cleanup failed to return the owned mask once without dereferencing fake-null Run");

        var replacedRun = new Run();
        var replaced = new PortSession.RewardEquipmentExpansionMaskLease((ok, why) => { if (!ok) throw new System.InvalidOperationException(why); });
        replaced.Acquire(replacedRun);
        var owned = replaced.Mask;
        var replacement = EquipmentMask.Rent();
        replacedRun.expansionLockedEquipment = replacement;
        Throws(() => replaced.Refresh(false), "mask replacement accepted as owned");
        replaced.Release(); replaced.Release();
        Check(System.Object.ReferenceEquals(replacement, replacedRun.expansionLockedEquipment), "cleanup cleared another owner's replacement");
        Check(EquipmentMask.returns == 6 && owned != replacement, "cleanup did not return only detached owned mask once");
        EquipmentMask.Return(replacement);
        Console.WriteLine("{\"fake_null_acquire_refusal\":true,\"same_owner_reuse\":true,\"wrong_owner_refusal\":true,\"truthful_lock_refresh\":true,\"catalog_partial_cleanup\":true,\"population_partial_cleanup\":true,\"destroyed_run_cleanup\":true,\"idempotent_cleanup\":true,\"replacement_preserved\":true}");
    }
}
"""


def extract_class(source, declaration):
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
    raise AssertionError("unclosed class")


class RewardEquipmentMaskLeaseTests(unittest.TestCase):
    def test_production_lease_contract(self):
        editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
        mono = editor / "MonoBleedingEdge/bin/mono"
        compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("pinned Unity host compiler unavailable")
        production = OWNER.read_text()
        lease = extract_class(production, "internal sealed class RewardEquipmentExpansionMaskLease")
        with tempfile.TemporaryDirectory(prefix="reward-equipment-mask-lease-") as temp:
            temp = Path(temp).resolve()
            src = temp / "Lease.cs"
            exe = temp / "Lease.exe"
            pdb = temp / "Lease.pdb"
            ref = temp / "Lease.ref.dll"
            src.write_text(FIXTURE.read_text() + "\npublic sealed partial class PortSession {\n" + lease + "\n}\n" + HARNESS)
            result = subprocess.run(
                [
                    str(mono),
                    str(compiler),
                    "-nologo",
                    "-langversion:9",
                    "-target:exe",
                    "-out:" + str(exe),
                    "-debug:portable",
                    "-pdb:" + str(pdb),
                    "-refout:" + str(ref),
                    str(src),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run = subprocess.run([str(mono), str(exe)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('"replacement_preserved":true', run.stdout)

    def test_integrated_spawn_acquires_before_spawn_and_cleans_before_run_teardown(self):
        session = SESSION.read_text()
        branch = extract_method(session, "IEnumerator OriginalStats")
        acquire = branch.index("PrepareEquipmentExpansionMaskBeforeSpawn();")
        self.assertIn('if (cfg.integratedWorld && r.id.StartsWith("body-state-spawn-state-"))', branch)
        self.assertNotIn('selectedSurvivor == "Toolbot"', branch)
        spawn = branch.index("var spawnRoutine = SpawnBoundary(body, cfg);", acquire)
        cleanup = branch.index("CleanupEquipmentExpansionMaskBeforeRunTeardown();")
        run_disable = branch.index('Call(run, "OnDisable");', cleanup)
        self.assertLess(acquire, spawn)
        self.assertLess(cleanup, run_disable)
        finally_block = branch[branch.index("finally\n        {") :]
        retained = finally_block.index("if (r.sourceStageLifecycleRecoveryRequired)")
        self.assertLess(retained, finally_block.index("else", retained))
        self.assertLess(finally_block.index("else", retained), finally_block.index("CleanupEquipmentExpansionMaskBeforeRunTeardown();"))

    def test_early_cleanup_is_not_gated_by_reward_report_and_recovery_retains_lease(self):
        owner = OWNER.read_text()
        cleanup = extract_method(owner, "void CleanupEquipmentExpansionMaskBeforeRunTeardown()")
        self.assertIn("enemyRewardSession != null", cleanup)
        self.assertNotIn("r.rewards", cleanup)
        session = SESSION.read_text()
        finally_block = session[session.index("finally\n        {", session.index("IEnumerator OriginalStats")) :]
        recovery = finally_block.index("if (r.sourceStageLifecycleRecoveryRequired)")
        retain = finally_block.index("RetainNativeLifecycleObject(run);", recovery)
        cleanup_call = finally_block.index("CleanupEquipmentExpansionMaskBeforeRunTeardown();", recovery)
        else_pos = finally_block.index("else", recovery)
        self.assertLess(recovery, retain)
        self.assertLess(else_pos, cleanup_call)

    def test_reward_prepare_reuses_only_the_exact_early_mask(self):
        owner = OWNER.read_text()
        prepare = extract_class(owner, "public IEnumerator PrepareEnemyRewards(CharacterBody player, SessionConfig cfg)")
        self.assertIn("equipmentMaskLease.Owns(rewardRun)", prepare)
        self.assertIn("equipmentMaskLease.Acquire(rewardRun);", prepare)
        self.assertNotIn("EquipmentMask.Rent()", prepare)
        self.assertLess(prepare.index("equipmentMaskLease.Acquire(rewardRun);"), prepare.index("RefreshRewardEquipmentMask(false);"))
        self.assertIn("EquipmentMask.Rent()", extract_class(owner, "internal sealed class RewardEquipmentExpansionMaskLease"))


def extract_method(source, declaration):
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
    raise AssertionError("unclosed method")


if __name__ == "__main__":
    unittest.main(verbosity=2)
