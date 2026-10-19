#if UNITY_EDITOR
// Exact-editor scalar contracts. No body, network object, native event subscription,
// projectile, damage, buff, or gameplay state is created or installed.
using System;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using RoR2.Projectile;
using UnityEngine.Networking;

public static class SurvivorCombatOutputObserverFixture
{
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static bool HasField(Type type, string name, Type fieldType)
    {
        var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        return field != null && field.FieldType == fieldType;
    }

    public static object RunSourceApiContract()
    {
        var damageEvent =
            typeof(GlobalEventManager).GetEvent("onServerDamageDealt", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        Require(damageEvent != null && damageEvent.EventHandlerType == typeof(Action<DamageReport>),
                "Current source server-damage event signature changed");
        Require(HasField(typeof(DamageReport), "attackerBody", typeof(CharacterBody)) &&
                    HasField(typeof(DamageReport), "attackerMaster", typeof(CharacterMaster)) &&
                    HasField(typeof(DamageReport), "attackerOwnerMaster", typeof(CharacterMaster)) &&
                    HasField(typeof(DamageReport), "damageInfo", typeof(DamageInfo)),
                "Current source DamageReport attribution fields changed");
        Require(HasField(typeof(DamageInfo), "attacker", typeof(UnityEngine.GameObject)) &&
                    HasField(typeof(DamageInfo), "inflictor", typeof(UnityEngine.GameObject)) &&
                    HasField(typeof(DamageInfo), "damageType", typeof(DamageTypeCombo)) &&
                    HasField(typeof(DamageInfo), "procCoefficient", typeof(float)),
                "Current source DamageInfo fields changed");
        Require(HasField(typeof(ProjectileController), "owner", typeof(UnityEngine.GameObject)) &&
                    HasField(typeof(ProjectileController), "catalogIndex", typeof(int)) &&
                    typeof(NetworkBehaviour).IsAssignableFrom(typeof(ProjectileController)),
                "Current source projectile owner/catalog/network contract changed");
        Require(typeof(NetworkIdentity).GetProperty("netId", BindingFlags.Instance | BindingFlags.Public) != null &&
                    typeof(NetworkServer)
                            .GetMethod("FindLocalObject", BindingFlags.Static | BindingFlags.Public, null,
                                       new[] { typeof(NetworkInstanceId) }, null) != null,
                "Current HLAPI server network mapping API changed");
        return new { damageEventSignature = true, reportAttributionFields = true, projectileOwnerAndCatalogFields = true,
                     serverMappingApi = true, noNetworkOrGameplayClaimed = true };
    }

    public static object RunBoundedHistoryContract()
    {
        var report = new SurvivorCombatOutputObserver.Report();
        var retainedIds = new HashSet<uint>();
        for (uint id = 1; id <= SurvivorCombatOutputObserver.ProjectileHistoryCapacity; id++)
            Require(SurvivorCombatOutputObserver.TryRetainProjectileIdentityForFixture(report, retainedIds, id),
                    "Identity below the history cap was not retained");
        uint overflowId = SurvivorCombatOutputObserver.ProjectileHistoryCapacity + 1;
        Require(!SurvivorCombatOutputObserver.TryRetainProjectileIdentityForFixture(report, retainedIds, overflowId) &&
                    !SurvivorCombatOutputObserver.TryRetainProjectileIdentityForFixture(report, retainedIds, overflowId),
                "Overflow identities should remain unretained on each live observation");
        Require(report.projectileHistoryUniqueNetworkIdsRetained == SurvivorCombatOutputObserver.ProjectileHistoryCapacity &&
                    report.projectileHistoryOverflowObservations == 2 &&
                    retainedIds.Count == SurvivorCombatOutputObserver.ProjectileHistoryCapacity,
                "Retained unique IDs or repeated overflow observation counts are misleading");

        var damage = new SurvivorCombatOutputObserver.Report();
        for (int i = 1; i <= SurvivorCombatOutputObserver.DamageHistoryCapacity + 3; i++)
            SurvivorCombatOutputObserver.PushDamageFactForFixture(
                damage, new SurvivorCombatOutputObserver.DamageFact { damageDealt = i, frame = i });
        int oldestDamage = damage.damageFactNext;
        int newestDamage = (damage.damageFactNext + damage.damageFacts.Length - 1) % damage.damageFacts.Length;
        Require(damage.damageFactCount == SurvivorCombatOutputObserver.DamageHistoryCapacity &&
                    damage.damageFacts[oldestDamage].damageDealt == 4 &&
                    damage.damageFacts[newestDamage].damageDealt == SurvivorCombatOutputObserver.DamageHistoryCapacity + 3,
                "Damage ring must retain the newest bounded sequence");

        var projectiles = new SurvivorCombatOutputObserver.Report();
        for (int i = 1; i <= SurvivorCombatOutputObserver.ProjectileHistoryCapacity + 3; i++)
            SurvivorCombatOutputObserver.PushProjectileFactForFixture(
                projectiles, new SurvivorCombatOutputObserver.ProjectileFact { networkId = (uint)i, firstFrame = i, liveCurrent = true });
        int oldestProjectile = projectiles.projectileFactNext;
        int newestProjectile =
            (projectiles.projectileFactNext + projectiles.projectileFacts.Length - 1) % projectiles.projectileFacts.Length;
        Require(projectiles.projectileFactCount == SurvivorCombatOutputObserver.ProjectileHistoryCapacity &&
                    projectiles.projectileFacts[oldestProjectile].networkId == 4 &&
                    projectiles.projectileFacts[newestProjectile].networkId == SurvivorCombatOutputObserver.ProjectileHistoryCapacity + 3,
                "Projectile fact ring must retain the newest bounded sequence");
        return new { retainedUniqueIds = report.projectileHistoryUniqueNetworkIdsRetained,
                     repeatedOverflowObservations = report.projectileHistoryOverflowObservations, damageAndProjectileRingsCapped = true,
                     noNativeObjectsCreated = true };
    }

    public static object RunFaultAndDisposalContract()
    {
        var report = new SurvivorCombatOutputObserver.Report { attached = true, status = "attached" };
        int detachCalls = 0, releaseCalls = 0;
        var firstError = new InvalidOperationException("synthetic observer read failure");
        Func<bool> retryDetach = delegate
        {
            detachCalls++;
            if (detachCalls == 1)
                throw new InvalidOperationException("synthetic unsubscribe failure");
            return true;
        };
        Action release = delegate
        {
            releaseCalls++;
        };
        SurvivorCombatOutputObserver.RunFaultBoundaryForFixture(report, firstError, retryDetach, release);
        Require(report.inert && report.attached && !report.cleaned && report.status == "observer-error-detach-pending" &&
                    report.observerError != null && report.observerError.Contains("synthetic observer read failure") &&
                    !report.observerError.Contains("unsubscribe") && detachCalls == 1 && releaseCalls == 1,
                "Fault must preserve the pending delegate, retain the first error, and release owner references");

        SurvivorCombatOutputObserver.RunDisposeBoundaryForFixture(report, retryDetach, release);
        Require(report.inert && !report.attached && report.cleaned && report.status == "observer-error-detached" &&
                    report.observerError.Contains("synthetic observer read failure") && detachCalls == 2 && releaseCalls == 2,
                "Dispose must retry the retained delegate and mark cleanup only after successful unsubscribe");
        SurvivorCombatOutputObserver.RunDisposeBoundaryForFixture(report, retryDetach, release);
        Require(detachCalls == 2 && releaseCalls == 2, "Successful disposal must be idempotent");
        return new { faultLatchedAndInert = true,
                     failedDetachRetainedForRetry = true,
                     referencesReleasedBeforeRetry = true,
                     cleanedOnlyAfterSuccessfulDetach = true,
                     disposalIdempotent = true,
                     noNativeEventInstalled = true };
    }
}

#endif // UNITY_EDITOR
