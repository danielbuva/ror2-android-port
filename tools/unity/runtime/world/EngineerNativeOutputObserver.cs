// Subsystem: survivor output observation. Owner map: docs/ARCHITECTURE.md#ownership.
// Setup: selected live Engineer; teardown: IntegratedWorldSession cleanup.
using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.Networking;

public sealed class EngineerNativeOutputObserver : IDisposable
{
    [Serializable]
    public sealed class Report
    {
        public bool attached, cleaned, serverObserved;
        public string ownerBody, ownerMaster, turretMasterAsset, turretBodyAsset;
        public int mineLive, mineEverObserved, bubbleLive, bubbleDeployedLive, bubbleEverObserved;
        public int bubbleGuardOwnedLive, bubbleGuardEverObserved;
        public int turretMasterLive, turretLive, turretEverObserved, turretSummonEvents, turretOwnershipConfirmed;
        public int ownerBodyIndex, turretBodyIndex, turretMasterIndex;
        public string[] mineStatesObserved = Array.Empty<string>();
    }

    public readonly Report report;
    CharacterMaster ownerMaster;
    BodyIndex ownerBodyIndex, turretBodyIndex;
    MasterCatalog.MasterIndex turretMasterIndex;
    GameObject minePrefab, bubblePrefab, turretMasterPrefab;
    readonly HashSet<int> mineInstanceIds = new HashSet<int>();
    readonly HashSet<int> bubbleInstanceIds = new HashSet<int>();
    readonly HashSet<int> bubbleGuardInstanceIds = new HashSet<int>();
    readonly HashSet<int> turretInstanceIds = new HashSet<int>();
    readonly HashSet<int> turretConfirmedIds = new HashSet<int>();
    readonly HashSet<string> mineStates = new HashSet<string>(StringComparer.Ordinal);
    readonly List<EntityStateMachine> stateMachineScratch = new List<EntityStateMachine>(4);
    bool subscribed;

    public EngineerNativeOutputObserver(CharacterBody exactOwnerBody)
    {
        if (!exactOwnerBody || !exactOwnerBody.master || !NetworkServer.active)
            throw new ArgumentException("Engineer output observation requires the exact live owner and active server");
        ownerBodyIndex = BodyCatalog.FindBodyIndex("EngiBody");
        ownerMaster = exactOwnerBody.master;
        if (!IsReciprocalLiveBody(ownerMaster, exactOwnerBody, ownerBodyIndex))
            throw new InvalidOperationException("Selected original Engineer identity mismatch");

        minePrefab = ResolveProjectile("EngiMine");
        bubblePrefab = ResolveProjectile("EngiBubbleShield");
        turretMasterIndex = MasterCatalog.FindMasterIndex("EngiTurretMaster");
        turretMasterPrefab = MasterCatalog.GetMasterPrefab(turretMasterIndex);
        var turretMasterComponent = turretMasterPrefab ? turretMasterPrefab.GetComponent<CharacterMaster>() : null;
        var catalogTurretBody = turretMasterComponent ? turretMasterComponent.bodyPrefab : null;
        var catalogTurretBodyComponent = catalogTurretBody ? catalogTurretBody.GetComponent<CharacterBody>() : null;
        turretBodyIndex = BodyCatalog.FindBodyIndex("EngiTurretBody");
        if (!minePrefab || !bubblePrefab || !turretMasterPrefab || !turretMasterComponent ||
            MasterCatalog.FindMasterIndex(turretMasterPrefab) != turretMasterIndex || !catalogTurretBodyComponent ||
            turretBodyIndex == BodyIndex.None || catalogTurretBodyComponent.bodyIndex != turretBodyIndex)
            throw new InvalidOperationException("Original Engineer output catalog identities are incomplete");

        report = new Report { ownerBody = exactOwnerBody.name,
                              ownerMaster = ownerMaster.name,
                              turretMasterAsset = turretMasterPrefab.name,
                              turretBodyAsset = catalogTurretBody.name,
                              ownerBodyIndex = (int)ownerBodyIndex,
                              turretBodyIndex = (int)turretBodyIndex,
                              turretMasterIndex = (int)turretMasterIndex,
                              serverObserved = true };
        // Establish the initial scalar sample before subscribing globally. If
        // that sample fails, construction cannot strand a delegate on the event.
        Sample();
        MasterSummon.onServerMasterSummonGlobal += OnServerMasterSummon;
        subscribed = true;
        report.attached = true;
    }

    static GameObject ResolveProjectile(string name)
    {
        int index = ProjectileCatalog.FindProjectileIndex(name);
        if (index < 0)
            throw new InvalidOperationException("Original Engineer projectile catalog identity missing: " + name);
        GameObject prefab = ProjectileCatalog.GetProjectilePrefab(index);
        if (!prefab || prefab.name != name || !prefab.GetComponent<ProjectileController>())
            throw new InvalidOperationException("Original Engineer projectile catalog identity missing: " + name);
        return prefab;
    }

    // Pure reference/slot predicate used by the exact-editor fixture. It never
    // mutates a deployable and rejects stale or foreign owner references.
    public static bool IsExactOwnedDeployable(DeployableInfo row, CharacterMaster owner, DeployableSlot expectedSlot)
    {
        return row.slot == expectedSlot && row.deployable && owner && row.deployable.ownerMaster == owner;
    }

    // Native masters leave the backing list null until their first deployable.
    // HG's wrapper exposes that state through its bool conversion; Count and
    // enumeration both require a backing list. Observation must not create it.
    public static int DeployableCount(HG.ReadOnlyList<DeployableInfo> rows)
    {
        return rows ? rows.Count : 0;
    }

    static bool IsServerMapped(NetworkBehaviour value)
    {
        return value && value.isServer && value.netId.Value != 0 && NetworkServer.FindLocalObject(value.netId) == value.gameObject;
    }

    public static bool IsReciprocalLiveBody(CharacterMaster master, CharacterBody body, BodyIndex expectedBodyIndex)
    {
        return NetworkServer.active && master && body && expectedBodyIndex != BodyIndex.None && body.bodyIndex == expectedBodyIndex &&
               master.hasBody && master.GetBody() == body && body.master == master && body.healthComponent && body.healthComponent.alive &&
               IsServerMapped(master) && IsServerMapped(body);
    }

    // This proves ownership of the exact source Collision HurtBox filter slot,
    // not merely that a guard component was cloned onto the root.
    public static bool OwnsSourceBubbleFilter(Deployable deployable)
    {
        if (!deployable)
            return false;
        var collision = deployable.transform.Find("Collision");
        var hurtBox = collision ? collision.GetComponent<HurtBox>() : null;
        var guard = deployable.GetComponent<EngiShieldHitGuard>();
        return collision && hurtBox && guard && guard.OwnsFilterOn(hurtBox);
    }

    void OnServerMasterSummon(MasterSummon.MasterSummonReport summon)
    {
        if (!ownerMaster || !summon.summonMasterInstance || summon.leaderMasterInstance != ownerMaster ||
            !IsReciprocalLiveBody(ownerMaster, summon.leaderBodyInstance, ownerBodyIndex) || summon.masterSummon == null ||
            summon.masterSummon.masterPrefab != turretMasterPrefab)
            return;

        report.turretSummonEvents++;
        var summoned = summon.summonMasterInstance;
        if (!IsReciprocalLiveBody(summoned, summon.summonBodyInstance, turretBodyIndex) || !summoned.minionOwnership ||
            summoned.minionOwnership.ownerMaster != ownerMaster)
            return;

        turretInstanceIds.Add(summoned.GetInstanceID());
        report.turretEverObserved = turretInstanceIds.Count;
        turretConfirmedIds.Add(summoned.GetInstanceID());
        report.turretOwnershipConfirmed = turretConfirmedIds.Count;
    }

    public void Sample()
    {
        if (report.cleaned || !ownerMaster || !NetworkServer.active)
            return;
        report.serverObserved = true;
        int mineLive = 0, bubbleLive = 0, bubbleDeployed = 0, bubbleGuardOwnedLive = 0;
        int turretMasterLive = 0, turretLive = 0;
        var deployables = ownerMaster.GetDeployables();
        int deployableCount = DeployableCount(deployables);
        for (int i = 0; i < deployableCount; i++)
        {
            DeployableInfo row = deployables[i];
            Deployable deployable = row.deployable;
            if (!deployable || deployable.ownerMaster != ownerMaster)
                continue;
            if (row.slot == DeployableSlot.EngiMine && IsExactOwnedDeployable(row, ownerMaster, DeployableSlot.EngiMine))
            {
                var controller = deployable.GetComponent<ProjectileController>();
                if (controller && IsServerMapped(controller) && controller.catalogIndex == ProjectileCatalog.GetProjectileIndex(minePrefab))
                {
                    mineLive++;
                    mineInstanceIds.Add(deployable.GetInstanceID());
                    RecordMineState(deployable.gameObject);
                }
            }
            else if (row.slot == DeployableSlot.EngiBubbleShield &&
                     IsExactOwnedDeployable(row, ownerMaster, DeployableSlot.EngiBubbleShield))
            {
                var controller = deployable.GetComponent<ProjectileController>();
                if (controller && IsServerMapped(controller) &&
                    controller.catalogIndex == ProjectileCatalog.GetProjectileIndex(bubblePrefab))
                {
                    bubbleLive++;
                    bubbleInstanceIds.Add(deployable.GetInstanceID());
                    if (HasNativeState<EntityStates.Engi.EngiBubbleShield.Deployed>(deployable.gameObject))
                        bubbleDeployed++;
                    if (OwnsSourceBubbleFilter(deployable))
                    {
                        bubbleGuardOwnedLive++;
                        bubbleGuardInstanceIds.Add(deployable.GetInstanceID());
                    }
                }
            }
            else if (row.slot == DeployableSlot.EngiTurret && IsExactOwnedDeployable(row, ownerMaster, DeployableSlot.EngiTurret))
            {
                var summoned = deployable.GetComponent<CharacterMaster>();
                if (summoned && IsServerMapped(summoned) && MasterCatalog.FindMasterIndex(summoned.gameObject) == turretMasterIndex &&
                    summoned.minionOwnership && summoned.minionOwnership.ownerMaster == ownerMaster)
                {
                    turretInstanceIds.Add(summoned.GetInstanceID());
                    turretMasterLive++;
                    var turretBody = summoned.GetBody();
                    if (IsReciprocalLiveBody(summoned, turretBody, turretBodyIndex))
                    {
                        turretLive++;
                        turretConfirmedIds.Add(summoned.GetInstanceID());
                    }
                }
            }
        }
        report.mineLive = mineLive;
        report.mineEverObserved = mineInstanceIds.Count;
        report.bubbleLive = bubbleLive;
        report.bubbleDeployedLive = bubbleDeployed;
        report.bubbleEverObserved = bubbleInstanceIds.Count;
        report.bubbleGuardOwnedLive = bubbleGuardOwnedLive;
        report.bubbleGuardEverObserved = bubbleGuardInstanceIds.Count;
        report.turretMasterLive = turretMasterLive;
        report.turretLive = turretLive;
        report.turretEverObserved = turretInstanceIds.Count;
        report.turretOwnershipConfirmed = turretConfirmedIds.Count;
    }

    void RecordMineState(GameObject mine)
    {
        stateMachineScratch.Clear();
        mine.GetComponents(stateMachineScratch);
        var changed = false;
        foreach (EntityStateMachine machine in stateMachineScratch)
            if (machine && machine.state != null)
                changed |= mineStates.Add(machine.state.GetType().FullName);
        if (changed)
            report.mineStatesObserved = CopyMineStates();
    }

    bool HasNativeState<TState>(GameObject instance)
        where TState : EntityStates.EntityState
    {
        stateMachineScratch.Clear();
        instance.GetComponents(stateMachineScratch);
        foreach (EntityStateMachine machine in stateMachineScratch)
            if (machine && machine.state is TState)
                return true;
        return false;
    }

    string[] CopyMineStates()
    {
        var result = new string[mineStates.Count];
        mineStates.CopyTo(result);
        Array.Sort(result, StringComparer.Ordinal);
        return result;
    }

    public void Dispose()
    {
        if (report.cleaned)
            return;
        if (subscribed)
        {
            MasterSummon.onServerMasterSummonGlobal -= OnServerMasterSummon;
            subscribed = false;
        }
        report.attached = false;
        report.cleaned = true;
        ownerMaster = null;
        minePrefab = null;
        bubblePrefab = null;
        turretMasterPrefab = null;
        mineInstanceIds.Clear();
        bubbleInstanceIds.Clear();
        bubbleGuardInstanceIds.Clear();
        turretInstanceIds.Clear();
        turretConfirmedIds.Clear();
        mineStates.Clear();
        stateMachineScratch.Clear();
    }
}
