// Subsystem: read-only survivor output observation owned by IntegratedWorldSession.
// The observer reports native ownership and output facts, never skill-slot causality.
using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

// Pure bounded timing policy for short extra output-observation windows.
// This schedule never queries game objects or changes gameplay state.
public sealed class TransientProjectileWindowSchedule
{
    public const int MaximumWindows = 3;
    public const int MaximumExtraScans = 60;
    public const float WindowSeconds = 1f;
    public const float SampleIntervalSeconds = .05f;
    const float WorldClockToleranceSeconds = .00001f;

    public int requests, accepted, droppedRequests, scans, extraScans, scanBudgetDrops;
    public int completedWindows, expiredWindows;
    public float maximumGapWorldSeconds;
    public bool activeWindow => active;
    bool active, hasLastSample;
    float endsAt, nextSampleAt, lastSampleAt;

    public bool Request(float worldSeconds, bool observerAvailable)
    {
        requests++;
        if (!observerAvailable || float.IsNaN(worldSeconds) || float.IsInfinity(worldSeconds) || worldSeconds < 0 ||
            active || accepted >= MaximumWindows)
        {
            droppedRequests++;
            return false;
        }
        accepted++;
        active = true;
        hasLastSample = false;
        endsAt = worldSeconds + WindowSeconds;
        nextSampleAt = worldSeconds + SampleIntervalSeconds;
        return true;
    }

    // Returns one due scan at most. A delayed update never catches up by
    // repeating scans at the same world timestamp.
    public bool TryTakeScan(float worldSeconds, bool baselineDue, out bool extraScan)
    {
        extraScan = false;
        if (!active)
            return false;
        if (float.IsNaN(worldSeconds) || float.IsInfinity(worldSeconds) || worldSeconds < 0)
            return false;
        if (worldSeconds > endsAt)
        {
            active = false;
            expiredWindows++;
            return false;
        }
        if (hasLastSample && worldSeconds <= lastSampleAt)
            return false;
        // A scheduled baseline scan is still an in-window observation even
        // when the transient cadence deadline has not arrived.
        if (!baselineDue && worldSeconds + WorldClockToleranceSeconds < nextSampleAt)
            return false;

        extraScan = !baselineDue;
        if (extraScan && extraScans >= MaximumExtraScans)
        {
            scanBudgetDrops++;
            nextSampleAt = worldSeconds + SampleIntervalSeconds;
            return false;
        }
        if (hasLastSample)
        {
            float gap = worldSeconds - lastSampleAt;
            if (gap > maximumGapWorldSeconds)
                maximumGapWorldSeconds = gap;
        }
        hasLastSample = true;
        lastSampleAt = worldSeconds;
        nextSampleAt = worldSeconds + SampleIntervalSeconds;
        scans++;
        if (extraScan)
            extraScans++;
        if (worldSeconds >= endsAt)
        {
            active = false;
            completedWindows++;
        }
        return true;
    }

    public bool ExpireIfPast(float worldSeconds)
    {
        if (!active || float.IsNaN(worldSeconds) || float.IsInfinity(worldSeconds) || worldSeconds < 0 || worldSeconds <= endsAt)
            return false;
        active = false;
        expiredWindows++;
        return true;
    }
}

public sealed class SurvivorCombatOutputObserver : IDisposable
{
    public const int DamageHistoryCapacity = 32;
    public const int ProjectileHistoryCapacity = 64;
    public const int MaximumNetworkObjectsPerSample = 4096;
    public const float SampleIntervalSeconds = 1f;

    public const byte AttributionUnknown = 0;
    public const byte AttributionPlayerBody = 1;
    public const byte AttributionPlayerProjectile = 2;
    public const byte AttributionOwnedSummon = 3;

    public const byte ProjectileOwnerUnknown = 0;
    public const byte ProjectileOwnerPlayerBody = 1;
    public const byte ProjectileOwnerPlayerMaster = 2;
    public const byte ProjectileOwnerOwnedSummon = 3;

    [Serializable]
    public struct DamageFact
    {
        public int frame, attackerBodyIndex, victimBodyIndex, inflictorInstanceId, inflictorCatalogIndex;
        public string attackerBodyCatalogName, victimBodyCatalogName;
        public uint attackerNetworkId, attackerMasterNetworkId, victimNetworkId, victimMasterNetworkId, inflictorNetworkId;
        public float unitySeconds, damageDealt, rawDamage, procCoefficient, positionX, positionY, positionZ;
        public uint damageTypeBits, damageTypeExtendedBits;
        public int dotIndex, attackIdentityIndex;
        public byte attribution, damageSource;
        public bool crit, rejected, inflictorIsMappedProjectile, inflictorOwnerIsPlayerBody;
    }

    [Serializable]
    public struct ProjectileFact
    {
        public int instanceId, catalogIndex, firstFrame, lastFrame;
        public uint networkId;
        public string catalogName;
        public byte ownerKind;
        public bool liveCurrent;
    }

    [Serializable]
    public sealed class Report
    {
        public bool attached, cleaned, inert, serverObserved, projectileScanTruncated;
        public string ownerBody, ownerMaster, status, observerError;
        public int bodyDamageEvents, bodyProjectileDamageEvents, ownedSummonDamageEvents, unknownOwnerDamageEvents;
        public int bodyProjectilesLive, masterOwnedProjectilesLive, summonProjectilesLive, unknownOwnerProjectilesLive;
        public int projectileHistoryUniqueNetworkIdsRetained, projectileHistoryOverflowObservations;
        public int transientWindowRequests, transientWindowsAccepted, transientWindowRequestsDropped;
        public int transientWindowScans, transientWindowExtraScans, transientWindowScanBudgetDrops;
        public int transientWindowObjectCapDrops, transientWindowsCompleted, transientWindowsExpired;
        public int damageFactCount, damageFactNext, projectileFactCount, projectileFactNext;
        public DamageFact[] damageFacts = new DamageFact[DamageHistoryCapacity];
        public ProjectileFact[] projectileFacts = new ProjectileFact[ProjectileHistoryCapacity];
        public float lastDamageUnitySeconds, lastProjectileSampleWorldSeconds, transientWindowMaximumGapWorldSeconds;
    }

    public readonly Report report;
    CharacterBody ownerBody;
    CharacterMaster ownerMaster;
    Action<DamageReport> damageHandler;
    readonly HashSet<uint> seenProjectileNetworkIds = new HashSet<uint>();
    readonly TransientProjectileWindowSchedule transientWindowSchedule = new TransientProjectileWindowSchedule();
    float nextSampleWorldSeconds;
    bool subscribed;

    public SurvivorCombatOutputObserver(CharacterBody exactOwnerBody)
    {
        if (!NetworkServer.active || !exactOwnerBody || !exactOwnerBody.master || exactOwnerBody.master.GetBody() != exactOwnerBody ||
            exactOwnerBody.master.hasBody != true || !IsServerMapped(exactOwnerBody) || !IsServerMapped(exactOwnerBody.master))
            throw new ArgumentException("Combat output observation requires the exact server-mapped live owner body/master",
                                        nameof(exactOwnerBody));

        ownerBody = exactOwnerBody;
        ownerMaster = exactOwnerBody.master;
        report = new Report { ownerBody = exactOwnerBody.name, ownerMaster = ownerMaster.name, status = "attached" };
        Sample(0f);
        if (report.inert)
            return;
        damageHandler = OnServerDamageDealt;
        GlobalEventManager.onServerDamageDealt += damageHandler;
        subscribed = true;
        report.attached = true;
    }

    static bool IsServerMapped(NetworkBehaviour value)
    {
        return NetworkServer.active && value && value.isServer && value.netId.Value != 0 &&
               NetworkServer.FindLocalObject(value.netId) == value.gameObject;
    }

    static bool TryGetMappedProjectile(GameObject inflictor, out ProjectileController projectile)
    {
        projectile = inflictor ? inflictor.GetComponent<ProjectileController>() : null;
        return projectile && IsServerMapped(projectile) && ProjectileCatalog.GetProjectilePrefab(projectile.catalogIndex);
    }

    static string NativeBodyCatalogNameForFact(BodyIndex bodyIndex)
    {
        if (bodyIndex == BodyIndex.None)
            return string.Empty;
        return BodyCatalog.GetBodyName(bodyIndex) ?? string.Empty;
    }

    static uint NetworkId(NetworkBehaviour value)
    {
        return value && value.netId.Value != 0 ? value.netId.Value : 0;
    }

    bool IsExactOwnedSummon(CharacterMaster master, CharacterBody body)
    {
        if (!ownerMaster || !master || !body || master == ownerMaster || body.master != master || !master.hasBody ||
            master.GetBody() != body || !master.minionOwnership || master.minionOwnership.ownerMaster != ownerMaster)
            return false;
        return IsServerMapped(master) && IsServerMapped(body);
    }

    void OnServerDamageDealt(DamageReport damage)
    {
        if (report.cleaned || report.inert)
            return;
        try
        {
            if (!NetworkServer.active || damage == null || !ownerBody || !ownerMaster)
                return;
            byte attribution = AttributionUnknown;
            bool relevant = false;
            if (damage.attackerBody == ownerBody)
            {
                relevant = true;
                attribution = AttributionPlayerBody;
                report.bodyDamageEvents++;
                ProjectileController inflictorProjectile;
                if (damage.damageInfo != null && TryGetMappedProjectile(damage.damageInfo.inflictor, out inflictorProjectile) &&
                    inflictorProjectile.owner == ownerBody.gameObject)
                {
                    attribution = AttributionPlayerProjectile;
                    report.bodyProjectileDamageEvents++;
                }
            }
            else if (damage.attackerOwnerMaster == ownerMaster)
            {
                relevant = true;
                if (IsExactOwnedSummon(damage.attackerMaster, damage.attackerBody))
                {
                    attribution = AttributionOwnedSummon;
                    report.ownedSummonDamageEvents++;
                }
                else
                {
                    report.unknownOwnerDamageEvents++;
                }
            }
            if (!relevant || damage.damageInfo == null)
                return;

            var info = damage.damageInfo;
            ProjectileController projectile;
            bool mappedProjectile = TryGetMappedProjectile(info.inflictor, out projectile);
            var fact = new DamageFact { frame = Time.frameCount,
                                        attackerBodyIndex = damage.attackerBody ? (int)damage.attackerBody.bodyIndex : (int)BodyIndex.None,
                                        victimBodyIndex = damage.victimBody ? (int)damage.victimBody.bodyIndex : (int)BodyIndex.None,
                                        attackerBodyCatalogName = NativeBodyCatalogNameForFact(
                                            damage.attackerBody ? damage.attackerBody.bodyIndex : BodyIndex.None),
                                        victimBodyCatalogName =
                                            NativeBodyCatalogNameForFact(damage.victimBody ? damage.victimBody.bodyIndex : BodyIndex.None),
                                        attackerNetworkId = damage.attackerBody ? NetworkId(damage.attackerBody) : 0,
                                        attackerMasterNetworkId = damage.attackerMaster ? NetworkId(damage.attackerMaster) : 0,
                                        victimNetworkId = damage.victimBody ? NetworkId(damage.victimBody) : 0,
                                        victimMasterNetworkId = damage.victimMaster ? NetworkId(damage.victimMaster) : 0,
                                        inflictorInstanceId = info.inflictor ? info.inflictor.GetInstanceID() : 0,
                                        inflictorNetworkId = mappedProjectile ? NetworkId(projectile) : 0,
                                        inflictorCatalogIndex = mappedProjectile ? projectile.catalogIndex : -1,
                                        unitySeconds = Time.time,
                                        damageDealt = damage.damageDealt,
                                        rawDamage = info.damage,
                                        procCoefficient = info.procCoefficient,
                                        positionX = info.position.x,
                                        positionY = info.position.y,
                                        positionZ = info.position.z,
                                        damageTypeBits = (uint)info.damageType.damageType,
                                        damageTypeExtendedBits = (uint)info.damageType.damageTypeExtended,
                                        damageSource = (byte)info.damageType.damageSource,
                                        attackIdentityIndex = (int)info.damageType.attackIdentityIndex,
                                        dotIndex = (int)damage.dotType,
                                        attribution = attribution,
                                        crit = info.crit,
                                        rejected = info.rejected,
                                        inflictorIsMappedProjectile = mappedProjectile,
                                        inflictorOwnerIsPlayerBody = mappedProjectile && projectile.owner == ownerBody.gameObject };
            PushDamageFact(report, fact);
            report.lastDamageUnitySeconds = Time.time;
        }
        catch (Exception error)
        {
            FailObserver(error);
        }
    }

    public void Sample(float elapsedWorldSeconds)
    {
        if (report.cleaned || report.inert)
            return;
        try
        {
            if (!ownerBody || !ownerMaster || !NetworkServer.active || float.IsNaN(elapsedWorldSeconds) ||
                float.IsInfinity(elapsedWorldSeconds) || elapsedWorldSeconds < 0)
                return;
            bool baselineDue = elapsedWorldSeconds >= nextSampleWorldSeconds;
            if (baselineDue)
                nextSampleWorldSeconds = elapsedWorldSeconds + SampleIntervalSeconds;
            bool windowWasActive = transientWindowSchedule.activeWindow;
            bool extraScan;
            bool transientWindowDue = transientWindowSchedule.TryTakeScan(elapsedWorldSeconds, baselineDue, out extraScan);
            bool expiredWindow = transientWindowSchedule.ExpireIfPast(elapsedWorldSeconds);
            if (windowWasActive || transientWindowDue || extraScan || expiredWindow)
                CopyTransientWindowCounters();
            if (!baselineDue && !transientWindowDue)
                return;
            ScanProjectiles(elapsedWorldSeconds, transientWindowDue);
        }
        catch (Exception error)
        {
            FailObserver(error);
        }
    }

    public void RequestTransientProjectileWindow(float elapsedWorldSeconds)
    {
        bool available = !report.cleaned && !report.inert;
        transientWindowSchedule.Request(elapsedWorldSeconds, available);
        CopyTransientWindowCounters();
    }

    void CopyTransientWindowCounters()
    {
        report.transientWindowRequests = transientWindowSchedule.requests;
        report.transientWindowsAccepted = transientWindowSchedule.accepted;
        report.transientWindowRequestsDropped = transientWindowSchedule.droppedRequests;
        report.transientWindowScans = transientWindowSchedule.scans;
        report.transientWindowExtraScans = transientWindowSchedule.extraScans;
        report.transientWindowScanBudgetDrops = transientWindowSchedule.scanBudgetDrops;
        report.transientWindowsCompleted = transientWindowSchedule.completedWindows;
        report.transientWindowsExpired = transientWindowSchedule.expiredWindows;
        report.transientWindowMaximumGapWorldSeconds = transientWindowSchedule.maximumGapWorldSeconds;
    }

    void ScanProjectiles(float elapsedWorldSeconds, bool transientWindowDue)
    {
        report.serverObserved = true;
        report.projectileScanTruncated = false;
        MarkAllProjectileFactsNotLive(report);
        report.bodyProjectilesLive = 0;
        report.masterOwnedProjectilesLive = 0;
        report.summonProjectilesLive = 0;
        report.unknownOwnerProjectilesLive = 0;

        int visited = 0;
        foreach (NetworkIdentity identity in NetworkServer.objects.Values)
        {
            if (visited++ >= MaximumNetworkObjectsPerSample)
            {
                report.projectileScanTruncated = true;
                if (transientWindowDue)
                    report.transientWindowObjectCapDrops++;
                break;
            }
            if (!identity || !identity.isServer || identity.netId.Value == 0 ||
                NetworkServer.FindLocalObject(identity.netId) != identity.gameObject)
                continue;
            var projectile = identity.GetComponent<ProjectileController>();
            if (!projectile || !IsServerMapped(projectile) || projectile.netId != identity.netId)
                continue;
            byte ownerKind = ResolveProjectileOwner(projectile.owner);
            if (ownerKind == ProjectileOwnerUnknown)
            {
                report.unknownOwnerProjectilesLive++;
                continue;
            }

            if (ownerKind == ProjectileOwnerPlayerBody)
                report.bodyProjectilesLive++;
            else if (ownerKind == ProjectileOwnerPlayerMaster)
                report.masterOwnedProjectilesLive++;
            else if (ownerKind == ProjectileOwnerOwnedSummon)
                report.summonProjectilesLive++;

            uint networkId = projectile.netId.Value;
            if (!seenProjectileNetworkIds.Contains(networkId))
            {
                if (!TryRetainProjectileIdentity(report, seenProjectileNetworkIds, networkId))
                    continue;
                var prefab = ProjectileCatalog.GetProjectilePrefab(projectile.catalogIndex);
                var fact = new ProjectileFact { instanceId = projectile.GetInstanceID(),
                                                networkId = networkId,
                                                catalogIndex = projectile.catalogIndex,
                                                catalogName = prefab ? prefab.name : "unresolved-catalog-index",
                                                firstFrame = Time.frameCount,
                                                lastFrame = Time.frameCount,
                                                ownerKind = ownerKind,
                                                liveCurrent = true };
                PushProjectileFact(report, fact);
            }
            else
            {
                RefreshProjectileFact(report, networkId, Time.frameCount, ownerKind);
            }
        }
        report.lastProjectileSampleWorldSeconds = elapsedWorldSeconds;
    }
    byte ResolveProjectileOwner(GameObject projectileOwner)
    {
        if (!projectileOwner)
            return ProjectileOwnerUnknown;
        if (projectileOwner == ownerBody.gameObject)
            return ProjectileOwnerPlayerBody;
        if (projectileOwner == ownerMaster.gameObject)
            return ProjectileOwnerPlayerMaster;

        var ownerBodyComponent = projectileOwner.GetComponent<CharacterBody>();
        if (!ownerBodyComponent || !ownerBodyComponent.master)
            return ProjectileOwnerUnknown;
        if (ownerBodyComponent.master == ownerMaster && ownerMaster.GetBody() == ownerBodyComponent)
            return ProjectileOwnerPlayerBody;
        return IsExactOwnedSummon(ownerBodyComponent.master, ownerBodyComponent) ? ProjectileOwnerOwnedSummon : ProjectileOwnerUnknown;
    }

    static void PushDamageFact(Report target, DamageFact fact)
    {
        if (target.damageFacts == null || target.damageFacts.Length == 0)
            return;
        target.damageFacts[target.damageFactNext] = fact;
        target.damageFactNext = (target.damageFactNext + 1) % target.damageFacts.Length;
        if (target.damageFactCount < target.damageFacts.Length)
            target.damageFactCount++;
    }

    static void PushProjectileFact(Report target, ProjectileFact fact)
    {
        if (target.projectileFacts == null || target.projectileFacts.Length == 0)
            return;
        target.projectileFacts[target.projectileFactNext] = fact;
        target.projectileFactNext = (target.projectileFactNext + 1) % target.projectileFacts.Length;
        if (target.projectileFactCount < target.projectileFacts.Length)
            target.projectileFactCount++;
    }

    static void MarkAllProjectileFactsNotLive(Report target)
    {
        var facts = target.projectileFacts;
        for (int i = 0; i < target.projectileFactCount; i++)
        {
            int index = target.projectileFactCount < facts.Length ? i : (target.projectileFactNext + i) % facts.Length;
            var fact = facts[index];
            fact.liveCurrent = false;
            facts[index] = fact;
        }
    }

    static void RefreshProjectileFact(Report target, uint networkId, int frame, byte ownerKind)
    {
        var facts = target.projectileFacts;
        for (int i = 0; i < target.projectileFactCount; i++)
        {
            int index = target.projectileFactCount < facts.Length ? i : (target.projectileFactNext + i) % facts.Length;
            if (facts[index].networkId != networkId)
                continue;
            var fact = facts[index];
            fact.lastFrame = frame;
            fact.ownerKind = ownerKind;
            fact.liveCurrent = true;
            facts[index] = fact;
            return;
        }
    }

#if UNITY_EDITOR
    public static void PushDamageFactForFixture(Report target, DamageFact fact)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));
        PushDamageFact(target, fact);
    }

    public static void PushProjectileFactForFixture(Report target, ProjectileFact fact)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));
        PushProjectileFact(target, fact);
    }
#endif

    static bool TryRetainProjectileIdentity(Report target, HashSet<uint> retainedIds, uint networkId)
    {
        if (networkId == 0 || retainedIds.Contains(networkId))
            return false;
        if (retainedIds.Count >= ProjectileHistoryCapacity)
        {
            target.projectileHistoryOverflowObservations++;
            return false;
        }
        retainedIds.Add(networkId);
        target.projectileHistoryUniqueNetworkIdsRetained++;
        return true;
    }

#if UNITY_EDITOR
    public static bool TryRetainProjectileIdentityForFixture(Report target, HashSet<uint> retainedIds, uint networkId)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));
        if (retainedIds == null)
            throw new ArgumentNullException(nameof(retainedIds));
        return TryRetainProjectileIdentity(target, retainedIds, networkId);
    }
#endif

    static void RecordFirstObserverError(Report target, Exception error)
    {
        if (target.observerError != null)
            return;
        string message;
        try
        {
            message = error == null ? "unknown observer failure" : error.GetType().Name + ": " + error.Message;
        }
        catch
        {
            message = "observer failure (message unavailable)";
        }
        if (message.Length > 256)
            message = message.Substring(0, 256);
        target.observerError = message;
    }

    static bool TryDetachBoundary(Report target, Func<bool> detach)
    {
        try
        {
            return detach == null || detach();
        }
        catch (Exception error)
        {
            RecordFirstObserverError(target, error);
            return false;
        }
    }

    static void RunFaultBoundary(Report target, Exception error, Func<bool> detach, Action release)
    {
        if (target.inert || target.cleaned)
            return;
        RecordFirstObserverError(target, error);
        target.inert = true;
        target.status = "observer-error";
        bool detached = TryDetachBoundary(target, detach);
        if (detached)
            target.attached = false;
        else
            target.status = "observer-error-detach-pending";
        try
        {
            if (release != null)
                release();
        }
        catch (Exception releaseError)
        {
            RecordFirstObserverError(target, releaseError);
        }
    }

#if UNITY_EDITOR
    public static void RunFaultBoundaryForFixture(Report target, Exception error, Func<bool> detach, Action release)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));
        RunFaultBoundary(target, error, detach, release);
    }
#endif

    bool DetachExactHandler()
    {
        if (!subscribed || damageHandler == null)
        {
            subscribed = false;
            damageHandler = null;
            return true;
        }

        GlobalEventManager.onServerDamageDealt -= damageHandler;
        subscribed = false;
        damageHandler = null;
        return true;
    }

    void ReleaseOwnerReferences()
    {
        ownerBody = null;
        ownerMaster = null;
        seenProjectileNetworkIds.Clear();
    }

    void FailObserver(Exception error)
    {
        RunFaultBoundary(report, error, DetachExactHandler, ReleaseOwnerReferences);
    }

    static void RunDisposeBoundary(Report target, Func<bool> detach, Action release)
    {
        if (target.cleaned)
            return;
        bool detached = TryDetachBoundary(target, detach);
        try
        {
            if (release != null)
                release();
        }
        catch (Exception error)
        {
            RecordFirstObserverError(target, error);
        }
        if (detached)
        {
            target.attached = false;
            target.cleaned = true;
            if (!target.inert)
                target.status = "cleaned";
            else
                target.status = "observer-error-detached";
        }
        else
        {
            target.inert = true;
            target.status = "observer-error-detach-pending";
        }
    }

#if UNITY_EDITOR
    public static void RunDisposeBoundaryForFixture(Report target, Func<bool> detach, Action release)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));
        RunDisposeBoundary(target, detach, release);
    }
#endif

    public void Dispose()
    {
        RunDisposeBoundary(report, DetachExactHandler, ReleaseOwnerReferences);
    }
}
