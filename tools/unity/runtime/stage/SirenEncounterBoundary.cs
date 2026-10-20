// Subsystem: stage transport (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Setup: SirenEncounterSession.Attach after original stage entry; observe from stage tick;
// teardown: SirenEncounterSession.Dispose before additive scene unload.
using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Shared runtime contracts only. The UnityEditor fixture calls this class; the
// stage owner must never depend on an editor-only host assembly.
public static class SirenEncounterContract
{
    public const string SceneName = "shipgraveyard";
    public const string EncounterObjectName = "SuperRoboBallEncounter";
    public const uint EncounterSceneId = 10;

    public static void RetainOwnerAfterPreflight<T>(bool preflightPassed, T owner, Action<T> retainOwner)
    {
        if (!preflightPassed)
            throw new InvalidOperationException("Cannot retain a Siren owner whose identity preflight did not pass");
        retainOwner?.Invoke(owner);
    }

    public static bool CompleteOwnedRecovery(ref bool sharedRecoveryRequired, long currentGeneration,
                                             long ownerGeneration, bool thisOwnerMayClear, bool anotherOwnerStillRequiresRecovery)
    {
        if (!thisOwnerMayClear || anotherOwnerStillRequiresRecovery || currentGeneration != ownerGeneration)
            return false;
        sharedRecoveryRequired = false;
        return true;
    }

    public static void DetachOwnedSubscription(ref bool ownsSubscription, Action detach)
    {
        if (!ownsSubscription)
            return;
        detach();
        ownsSubscription = false;
    }

    // Production cleanup uses this cursor so a failed operation remains the
    // next operation on retry. The cursor advances only after the action returns.
    public static bool TryAdvanceCleanupStep(ref int completedStep, int requestedStep, Action operation,
                                             ref Exception firstFailure, out Exception stepFailure)
    {
        stepFailure = null;
        if (completedStep > requestedStep)
            return true;
        if (completedStep != requestedStep)
            throw new InvalidOperationException("Cleanup steps must run in their declared order");
        try
        {
            operation();
            completedStep++;
            return true;
        }
        catch (Exception exception)
        {
            stepFailure = exception;
            if (firstFailure == null)
                firstFailure = exception;
            return false;
        }
    }

    public static bool TryAdvanceOwnedCleanupStep(ref int completedStep, int requestedStep, bool ownershipAcquired,
                                                  Action operation, ref Exception firstFailure, out Exception stepFailure)
    {
        return TryAdvanceCleanupStep(ref completedStep, requestedStep,
            () => { if (ownershipAcquired) operation(); }, ref firstFailure, out stepFailure);
    }

    // Do not drop the sole owner handle until its Dispose has actually returned.
    public static void DisposeOwned<T>(ref T owner, Action<T> dispose) where T : class
    {
        var current = owner;
        if (current == null)
            return;
        dispose(current);
        if (ReferenceEquals(owner, current))
            owner = null;
        else
            throw new InvalidOperationException("Owned Siren cleanup handle changed while its captured owner was disposing");
    }

    public static T SelectOriginalInactiveEncounter<T>(System.Collections.Generic.IEnumerable<T> candidates,
                                                        Func<T, string> sceneName, Func<T, string> objectName,
                                                        Func<T, uint> sceneId, Func<T, bool> activeSelf,
                                                        Func<T, bool> sourceContract)
    {
        if (candidates == null || sceneName == null || objectName == null || sceneId == null || activeSelf == null ||
            sourceContract == null)
            throw new ArgumentNullException("Encounter selection requires candidates and all source-contract readers");
        var identities = candidates.Where(candidate => sceneId(candidate) == EncounterSceneId).ToArray();
        if (identities.Length != 1)
            throw new InvalidOperationException("Expected exactly one original Ship Graveyard encounter identity with scene ID 10");
        var selected = identities[0];
        if (sceneName(selected) != SceneName || objectName(selected) != EncounterObjectName)
            throw new InvalidOperationException("Scene ID 10 no longer identifies the original Ship Graveyard encounter object");
        if (activeSelf(selected))
            throw new InvalidOperationException("Original Ship Graveyard encounter must retain its authored inactive state");
        if (!sourceContract(selected))
            throw new InvalidOperationException("Original Ship Graveyard encounter component or serialized-card contract changed");
        return selected;
    }

    public static void RunAttachTransaction(Action activate, Action spawn, Action rollback,
                                            Action<Exception> onRollbackFailure = null)
    {
        if (activate == null || spawn == null || rollback == null)
            throw new ArgumentNullException("Siren attach transaction requires activation, spawn, and rollback actions");
        try
        {
            activate();
            spawn();
        }
        catch
        {
            try
            {
                rollback();
            }
            catch (Exception cleanupFailure)
            {
                // Preserve the attach failure; rollback owns its own finally-based restoration.
                try { onRollbackFailure?.Invoke(cleanupFailure); }
                catch { /* Recovery reporting cannot replace the attach failure. */ }
            }
            throw;
        }
    }
}

public sealed partial class PortSession
{
    [Serializable]
    public class SirenEncounterReport
    {
        public string scene, encounterState, observation;
        public bool sourceOwnerAttached, listenerStateActive, eggBodiesObserved, nativeEggRegistrationObserved, nativeEncounterStarted,
            nativeEncounterCompleted, networkObjectUnspawned, retirementPreflightPassed, retirementRequestsIssued,
            retirementRefusedForeignMember, cleanupDisposed, originalActiveRestored, sceneInstanceDestroyed;
        public bool nativeEggRegistrationMatchesSourceEntry;
        public int diagnosticSourceEggCandidatesObserved, nativeEggSlotsRegistered;
        public int observedEggBodyCount, nativeBossMembers, observationSamples, encounterSquadMembersAtCleanup,
            retiredBossBodiesRequested, retiredBossMastersRequested, retiredProbeBodiesRequested,
            retiredProbeMastersRequested;
        public uint identitySceneId, networkId;
        public uint[] sourceEntryEggNetworkIds, nativeRegisteredEggNetworkIds;
        public string cleanupError;
    }
}

/// <summary>
/// Owns only the original inactive Ship Graveyard scene identity with ID 10.
/// The source FSM, ScriptedCombatEncounter, BossGroup and spawn card remain the
/// native encounter implementation.
/// </summary>
public sealed partial class SirenEncounterSession : IDisposable
{
    sealed class OwnedMaster
    {
        public CharacterMaster master;
        public NetworkInstanceId networkId;
        public NetworkInstanceId ownerNetworkId;
        public bool bodyDestroyRequestCompleted;
        public bool masterDestroyRequestCompleted;
    }

    const float ObservationIntervalSeconds = 0.5f;
    const string OriginalBossBodyName = "SuperRoboBallBossBody";
    const string OriginalProbeBodyName = "RoboBallMiniBody";
    Scene scene;
    GameObject encounterObject;
    NetworkIdentity identity;
    EntityStateMachine stateMachine;
    ScriptedCombatEncounter encounter;
    BossGroup bossGroup;
    readonly bool originalActiveSelf;
    bool ownsNetworkSpawn;
    bool ownsActivatedSceneInstance;
    bool ownsActiveStateMutation;
    bool ownsBossDefeatObservation;
    bool ownsSquadMemberObservation;
    bool ownsMinionSummonObservation;
    bool cleanupStarted;
    bool disposed;
    int cleanupStep;
    Exception cleanupFirstFailure;
    NetworkIdentity[] expectedSourceEggs;
    float nextObservationAt;
    readonly List<OwnedMaster> ownedBossMasters = new List<OwnedMaster>();
    readonly List<OwnedMaster> ownedProbeMasters = new List<OwnedMaster>();
    readonly HashSet<uint> ownedBossNetworkIds = new HashSet<uint>();

    public PortSession.SirenEncounterReport Report { get; private set; }

    SirenEncounterSession(Scene scene, GameObject encounterObject, NetworkIdentity identity,
                          EntityStateMachine stateMachine, ScriptedCombatEncounter encounter, BossGroup bossGroup)
    {
        this.scene = scene;
        this.encounterObject = encounterObject;
        this.identity = identity;
        this.stateMachine = stateMachine;
        this.encounter = encounter;
        this.bossGroup = bossGroup;
        originalActiveSelf = encounterObject.activeSelf;
        Report = new PortSession.SirenEncounterReport
        {
            scene = scene.name,
            identitySceneId = identity.sceneId.Value,
            observation = "source-owner-selected; native-listener-and-eggs-unobserved",
            networkObjectUnspawned = true
        };
    }

    public static GameObject SelectSourceEncounter(Scene scene)
    {
        if (!scene.IsValid() || !scene.isLoaded || scene.name != SirenEncounterContract.SceneName)
            throw new InvalidOperationException("Siren encounter owner requires the loaded original shipgraveyard scene");
        var candidates = scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<Transform>(true))
            .Select(transform => transform.gameObject)
            .Where(gameObject => gameObject.GetComponent<NetworkIdentity>())
            .ToArray();

        return SirenEncounterContract.SelectOriginalInactiveEncounter(
            candidates,
            gameObject => gameObject.scene.name,
            gameObject => gameObject.name,
            gameObject => gameObject.GetComponent<NetworkIdentity>().sceneId.Value,
            gameObject => gameObject.activeSelf,
            HasOriginalEncounterContract);
    }

    public static SirenEncounterSession Attach(Scene scene, Action<PortSession.SirenEncounterReport> onReportSelected = null,
                                                Action<SirenEncounterSession> retainOwner = null,
                                                Action<Exception> onCleanupFailure = null,
                                                NetworkIdentity[] expectedSourceEggs = null)
    {
        if (!NetworkServer.active)
            throw new InvalidOperationException("Siren encounter source identity requires the active local server");
        var selected = SelectSourceEncounter(scene);
        var owner = new SirenEncounterSession(scene, selected, selected.GetComponent<NetworkIdentity>(),
            selected.GetComponent<EntityStateMachine>(), selected.GetComponent<ScriptedCombatEncounter>(),
            selected.GetComponent<BossGroup>());
        owner.PrepareDiagnosticEggSourceContract();
        if (expectedSourceEggs != null)
        {
            if (expectedSourceEggs.Length != 12 || expectedSourceEggs.Any(egg => !egg || !egg.isServer || egg.netId.Value == 0 ||
                    !ReferenceEquals(NetworkServer.FindLocalObject(egg.netId), egg.gameObject)) ||
                expectedSourceEggs.Select(egg => egg.netId.Value).Distinct().Count() != expectedSourceEggs.Length ||
                expectedSourceEggs.Any(egg => egg.gameObject.scene != scene || !egg.assetId.Equals(owner.originalEggAssetId)))
                throw new InvalidOperationException("Siren source-entry handoff requires twelve exact registered original egg identities");
            owner.expectedSourceEggs = expectedSourceEggs.ToArray();
            owner.Report.sourceEntryEggNetworkIds = owner.expectedSourceEggs.Select(egg => egg.netId.Value).ToArray();
        }
        if (owner.identity.isServer || owner.identity.netId.Value != 0)
            throw new InvalidOperationException("Original Siren encounter identity is already server-spawned; refusing ownership transfer");
        onReportSelected?.Invoke(owner.Report);
        // The coordinator retains the owner after all preflight and immediately
        // before the first owned event/source mutation.
        SirenEncounterContract.RetainOwnerAfterPreflight(
            !owner.identity.isServer && owner.identity.netId.Value == 0, owner, retainOwner);

        SirenEncounterContract.RunAttachTransaction(
            () =>
            {
                BossGroup.onBossGroupDefeatedServer += owner.OnBossGroupDefeatedServer;
                owner.ownsBossDefeatObservation = true;
                try
                {
                    selected.SetActive(true);
                }
                finally
                {
                    if (selected && selected.activeSelf != owner.originalActiveSelf)
                    {
                        owner.ownsActiveStateMutation = true;
                        owner.ownsActivatedSceneInstance = true;
                    }
                }
                owner.encounter.combatSquad.onMemberAddedServer += owner.OnEncounterMemberAddedServer;
                owner.ownsSquadMemberObservation = true;
                // MasterSummon's report follows Spawn/Respawn. Its earlier
                // ownership-change event occurs before the minion has a netId.
                MasterSummon.onServerMasterSummonGlobal += owner.OnMinionSummoned;
                owner.ownsMinionSummonObservation = true;
            },
            () =>
            {
                try
                {
                    NetworkServer.Spawn(selected);
                }
                finally
                {
                    owner.CaptureNetworkSpawnOwnership();
                }
                if (!owner.identity.isServer || owner.identity.netId.Value == 0)
                    throw new InvalidOperationException("Original Siren encounter identity did not acquire a server network ID");

                owner.Report.sourceOwnerAttached = true;
                owner.Report.networkId = owner.identity.netId.Value;
                owner.Report.networkObjectUnspawned = false;
                owner.Observe(force: true);
            },
            owner.Release,
            cleanupFailure =>
            {
                if (string.IsNullOrEmpty(owner.Report.cleanupError))
                    owner.Report.cleanupError = cleanupFailure.GetType().Name + ": " + cleanupFailure.Message;
                onCleanupFailure?.Invoke(cleanupFailure);
            });
        return owner;
    }

    static bool HasOriginalEncounterContract(GameObject gameObject)
    {
        if (!gameObject || gameObject.scene.name != SirenEncounterContract.SceneName || !gameObject.transform.parent ||
            gameObject.transform.parent.name != "HOLDER: Boss Encounter" ||
            !gameObject.transform.parent.gameObject.activeInHierarchy)
            return false;

        var identities = gameObject.GetComponents<NetworkIdentity>();
        var stateMachines = gameObject.GetComponents<EntityStateMachine>();
        var encounters = gameObject.GetComponents<ScriptedCombatEncounter>();
        var bossGroups = gameObject.GetComponents<BossGroup>();
        var squads = gameObject.GetComponents<CombatSquad>();
        var eventFunctions = gameObject.GetComponents<EventFunctions>();
        if (identities.Length != 1 || stateMachines.Length != 1 || encounters.Length != 1 || bossGroups.Length != 1 ||
            squads.Length != 1 || eventFunctions.Length != 1)
            return false;
        if (!identities[0].enabled || !stateMachines[0].enabled || !encounters[0].enabled || !bossGroups[0].enabled ||
            !squads[0].enabled || !eventFunctions[0].enabled)
            return false;

        var machine = stateMachines[0];
        if (machine.initialStateType.stateType != typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening) ||
            machine.mainStateType.stateType != typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening))
            return false;

        var scripted = encounters[0];
        return !squads[0].propagateMembershipToSummons && !scripted.spawnOnStart &&
               scripted.teamIndex == TeamIndex.Monster && scripted.spawns != null && scripted.spawns.Length == 1 && scripted.spawns[0].spawnCard &&
               scripted.spawns[0].spawnCard.name == "cscSuperRoboBallBoss";
    }

    void OnBossGroupDefeatedServer(BossGroup defeated)
    {
        if (!disposed && !cleanupStarted && defeated == bossGroup && encounter && encounter.hasSpawnedServer)
        {
            Report.nativeEncounterCompleted = true;
            Report.observation = "original-native-encounter-started-and-exact-boss-group-defeat-event-observed";
        }
    }

    void OnEncounterMemberAddedServer(CharacterMaster member)
    {
        if (disposed || cleanupStarted || !NetworkServer.active || !member || member.teamIndex != TeamIndex.Monster ||
            member.playerCharacterMasterController || member.bodyPrefab != BodyCatalog.FindBodyPrefab(OriginalBossBodyName) ||
            member.netId.Value == 0 || ownedBossNetworkIds.Contains(member.netId.Value))
            return;

        ownedBossNetworkIds.Add(member.netId.Value);
        ownedBossMasters.Add(new OwnedMaster { master = member, networkId = member.netId });
    }

    void OnMinionSummoned(MasterSummon.MasterSummonReport summon)
    {
        var master = summon.summonMasterInstance;
        var ownership = master ? master.minionOwnership : null;
        if (disposed || cleanupStarted || !NetworkServer.active || !ownership || !summon.leaderMasterInstance)
            return;

        var ownerId = ownership.NetworkownerMasterId;
        if (ownerId.Value == 0 || !ownedBossNetworkIds.Contains(ownerId.Value))
            return;

        var owner = ownedBossMasters.FirstOrDefault(candidate => candidate.networkId == ownerId);
        if (owner == null || !owner.master || owner.master.netId != ownerId ||
            summon.leaderMasterInstance != owner.master ||
            NetworkServer.FindLocalObject(ownerId) != owner.master.gameObject)
            return;

        if (!master || master.teamIndex != TeamIndex.Monster || master.playerCharacterMasterController ||
            master.bodyPrefab != BodyCatalog.FindBodyPrefab(OriginalProbeBodyName) || master.netId.Value == 0 ||
            ownedProbeMasters.Any(candidate => candidate.networkId == master.netId))
            return;

        ownedProbeMasters.RemoveAll(candidate => !candidate.master);
        ownedProbeMasters.Add(new OwnedMaster { master = master, networkId = master.netId, ownerNetworkId = ownerId });
    }

    /// <summary>
    /// Samples native state at most twice per second. Egg count mirrors only the
    /// source Listener's name-based population observation; it does not infer
    /// eggs destroyed, encounter eligibility, or encounter completion.
    /// </summary>
    public void Observe(bool force = false)
    {
        if (disposed || cleanupStarted || !encounterObject || !encounterObject.activeInHierarchy)
            return;
        if (!force && Time.unscaledTime < nextObservationAt)
            return;
        nextObservationAt = Time.unscaledTime + ObservationIntervalSeconds;

        var bodies = CharacterBody.readOnlyInstancesList;
        ObserveNativeEggRegistration();
        int eggCount = RefreshDiagnosticEggCandidates(bodies);
        Report.listenerStateActive = stateMachine && stateMachine.state is EntityStates.Missions.SuperRoboBallEncounter.Listening;
        Report.nativeEggRegistrationObserved = NativeEggRegistrationObserved;
        Report.nativeEggSlotsRegistered = NativeEggRegistrationObserved ? NativeEggSlotsRegistered : 0;
        Report.eggBodiesObserved = eggCount > 0;
        Report.observedEggBodyCount = eggCount;
        Report.nativeEncounterStarted = encounter && encounter.hasSpawnedServer;
        Report.nativeBossMembers = bossGroup && bossGroup.combatSquad ? bossGroup.combatSquad.memberCount : 0;
        Report.encounterState = !stateMachine || stateMachine.state == null ? "uninitialized" : stateMachine.state.GetType().FullName;
        Report.sourceOwnerAttached = identity && identity.isServer && identity.netId.Value != 0;
        Report.networkId = identity ? identity.netId.Value : 0;
        Report.networkObjectUnspawned = !identity || identity.netId.Value == 0;
        Report.observationSamples++;
        if (!Report.nativeEncounterCompleted && !Report.nativeEncounterStarted)
            Report.observation = !Report.listenerStateActive
                ? "source-owner-attached; native-listener-state-not-observed; encounter-eligibility-unproven"
                : !Report.nativeEggRegistrationObserved
                    ? "native-listener-state-active; native-egg-registration-not-observed; encounter-eligibility-unproven"
                    : Report.nativeEggSlotsRegistered == 0
                        ? "native-listener-registered-zero-egg-slots; no-eligible-target; encounter-eligibility-unproven"
                : eggCount == 0
                    ? "native-listener-state-active; no-live-vulture-egg-bodies-observed; eligibility-unproven"
                    : "native-listener-state-and-live-vulture-egg-bodies-observed; encounter-start-unproven";
        else if (!Report.nativeEncounterCompleted)
            Report.observation = "native-scripted-encounter-start-observed; boss-group-completion-unobserved";
    }

    void Release()
    {
        if (disposed)
            return;
        cleanupStarted = true;
        Exception failure;
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 0, () =>
        {
            SirenEncounterContract.DetachOwnedSubscription(ref ownsBossDefeatObservation,
                () => BossGroup.onBossGroupDefeatedServer -= OnBossGroupDefeatedServer);
        }, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 1, () =>
        {
            SirenEncounterContract.DetachOwnedSubscription(ref ownsSquadMemberObservation, () =>
            {
                if (!encounter || !encounter.combatSquad)
                    throw new InvalidOperationException("Cannot detach the Siren squad observer from its exact captured native component");
                encounter.combatSquad.onMemberAddedServer -= OnEncounterMemberAddedServer;
            });
        }, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 2, () =>
        {
            SirenEncounterContract.DetachOwnedSubscription(ref ownsMinionSummonObservation,
                () => MasterSummon.onServerMasterSummonGlobal -= OnMinionSummoned);
        }, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceOwnedCleanupStep(ref cleanupStep, 3,
                ownsActivatedSceneInstance || ownedBossMasters.Count != 0 || ownedProbeMasters.Count != 0,
                RetireEncounterSquadMembers, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 4, UnSpawnOwnedEncounter,
                                                           ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceOwnedCleanupStep(ref cleanupStep, 5, ownsActiveStateMutation,
                RestoreEncounterActiveState, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);
        if (!SirenEncounterContract.TryAdvanceOwnedCleanupStep(ref cleanupStep, 6, ownsActivatedSceneInstance,
                DestroyOwnedSourceSceneInstance, ref cleanupFirstFailure, out failure))
            ThrowCleanupFailure(failure);

        ClearDiagnosticEggCandidates();
        scene = default(Scene);
        encounterObject = null;
        identity = null;
        stateMachine = null;
        encounter = null;
        bossGroup = null;
        ownedBossMasters.Clear();
        ownedProbeMasters.Clear();
        ownedBossNetworkIds.Clear();
        disposed = true;
        Report.cleanupDisposed = true;
        Report.observation = "owner-disposed; body-destruction-requests=" + Report.retiredBossBodiesRequested +
            "; master-destruction-requests=" + Report.retiredBossMastersRequested +
            "; probe-body-destruction-requests=" + Report.retiredProbeBodiesRequested +
            "; probe-master-destruction-requests=" + Report.retiredProbeMastersRequested +
            "; original-active-restored=" + Report.originalActiveRestored +
            "; scene-instance-destroyed=" + Report.sceneInstanceDestroyed +
            "; network-unspawned=" + Report.networkObjectUnspawned +
            (string.IsNullOrEmpty(Report.cleanupError) ? "" : "; recovered-after-cleanup-error=" + Report.cleanupError);
    }

    void ThrowCleanupFailure(Exception failure)
    {
        if (string.IsNullOrEmpty(Report.cleanupError))
            Report.cleanupError = failure.GetType().Name + ": " + failure.Message;
        throw failure;
    }

    void RetireEncounterSquadMembers()
    {
        if (!ownsActivatedSceneInstance && ownedBossMasters.Count == 0 && ownedProbeMasters.Count == 0)
            return;
        if (!encounter || !encounter.combatSquad)
            throw new InvalidOperationException("Cannot verify the exact captured Siren squad during actor cleanup");

        if (!NetworkServer.active)
            throw new InvalidOperationException("Cannot retire original Siren encounter actors while the server is inactive");

        var members = encounter.combatSquad.readOnlyMembersList.Where(member => member).ToArray();
        Report.encounterSquadMembersAtCleanup = members.Length;
        var roots = ownedBossMasters.ToArray();
        var probes = ownedProbeMasters.ToArray();

        // Every live squad member must match a master captured from this exact
        // source squad. Probe ownership is tracked only from the native ownership
        // summon report for one of those captured boss network IDs.
        foreach (var member in members)
        {
            if (!roots.Any(entry => entry.master == member && entry.networkId == member.netId))
            {
                Report.retirementRefusedForeignMember = true;
                throw new InvalidOperationException("Refusing to retire a Siren squad member that was not observed as an owned native boss");
            }
        }

        foreach (var entry in roots)
            if (!entry.masterDestroyRequestCompleted)
                ValidateOwnedMaster(entry, OriginalBossBodyName, NetworkInstanceId.Invalid, "native boss");
        foreach (var entry in probes)
        {
            if (entry.masterDestroyRequestCompleted)
                continue;
            if (!entry.master)
                throw new InvalidOperationException("A captured Siren probe disappeared before its native destroy request was recorded");
            var ownership = entry.master.minionOwnership;
            if (!ownership || !ownedBossNetworkIds.Contains(entry.ownerNetworkId.Value) ||
                ownership.NetworkownerMasterId != entry.ownerNetworkId)
            {
                Report.retirementRefusedForeignMember = true;
                throw new InvalidOperationException("Refusing to retire a native probe whose current owner is not an observed Siren boss");
            }
            var registeredOwner = NetworkServer.FindLocalObject(ownership.NetworkownerMasterId);
            if (registeredOwner && !roots.Any(root => root.networkId == ownership.NetworkownerMasterId &&
                                                       root.master && root.master.gameObject == registeredOwner))
            {
                Report.retirementRefusedForeignMember = true;
                throw new InvalidOperationException("Refusing to retire a native probe after its owner network ID resolved to a different master");
            }
            ValidateOwnedMaster(entry, OriginalProbeBodyName, entry.ownerNetworkId, "native probe");
        }

        Report.retirementPreflightPassed = true;
        foreach (var entry in probes)
            RequestDestroy(entry, isProbe: true);
        foreach (var entry in roots)
            RequestDestroy(entry, isProbe: false);
    }

    void ValidateOwnedMaster(OwnedMaster entry, string expectedBodyName, NetworkInstanceId expectedOwner, string label)
    {
        var member = entry.master;
        if (!member || member.netId != entry.networkId || member.netId.Value == 0 ||
            NetworkServer.FindLocalObject(entry.networkId) != member.gameObject ||
            member.teamIndex != TeamIndex.Monster || member.playerCharacterMasterController ||
            member.bodyPrefab != BodyCatalog.FindBodyPrefab(expectedBodyName))
        {
            Report.retirementRefusedForeignMember = true;
            throw new InvalidOperationException("Refusing to retire a Siren " + label + " whose live identity or native body contract changed");
        }

        if (expectedOwner != NetworkInstanceId.Invalid &&
            (!member.minionOwnership || member.minionOwnership.NetworkownerMasterId != expectedOwner))
        {
            Report.retirementRefusedForeignMember = true;
            throw new InvalidOperationException("Refusing to retire a Siren " + label + " after its native owner changed");
        }
        if (expectedOwner == NetworkInstanceId.Invalid && member.minionOwnership &&
            member.minionOwnership.NetworkownerMasterId != NetworkInstanceId.Invalid)
        {
            Report.retirementRefusedForeignMember = true;
            throw new InvalidOperationException("Refusing to retire a Siren " + label + " after it acquired a foreign owner");
        }
    }

    void RequestDestroy(OwnedMaster entry, bool isProbe)
    {
        if (entry.masterDestroyRequestCompleted)
            return;
        if (!entry.master)
            throw new InvalidOperationException("Captured Siren master disappeared before its native destroy request was recorded");
        if (!entry.bodyDestroyRequestCompleted)
        {
            var body = entry.master.GetBody();
            var bodyObject = body ? body.gameObject : null;
            if (bodyObject)
            {
                NetworkServer.Destroy(bodyObject);
                if (isProbe)
                    Report.retiredProbeBodiesRequested++;
                else
                    Report.retiredBossBodiesRequested++;
                Report.retirementRequestsIssued = true;
            }
            entry.bodyDestroyRequestCompleted = true;
        }
        var masterObject = entry.master.gameObject;
        if (masterObject)
        {
            NetworkServer.Destroy(masterObject);
            if (isProbe)
                Report.retiredProbeMastersRequested++;
            else
                Report.retiredBossMastersRequested++;
            Report.retirementRequestsIssued = true;
        }
        entry.masterDestroyRequestCompleted = true;
    }

    void UnSpawnOwnedEncounter()
    {
        if (!ownsNetworkSpawn)
        {
            if (!identity || identity.netId.Value != 0 || identity.isServer || !Report.networkObjectUnspawned)
                throw new InvalidOperationException("Encounter spawn left an identity state the Siren owner cannot prove it owns or has retired");
            return;
        }
        if (ownsNetworkSpawn)
        {
            if (!identity || !encounterObject)
                throw new InvalidOperationException("Cannot verify the exact owned Siren identity before NetworkServer.UnSpawn");
            var capturedNetworkId = Report.networkId != 0 ? new NetworkInstanceId(Report.networkId) : identity.netId;
            if (capturedNetworkId.Value == 0)
                throw new InvalidOperationException("Owned Siren encounter has no captured network ID to retire");
            var registered = NetworkServer.FindLocalObject(capturedNetworkId);
            if (registered && registered != encounterObject)
                throw new InvalidOperationException("Refusing to unspawn a Siren network ID now mapped to a foreign object");
            if (registered == encounterObject)
            {
                if (!NetworkServer.active)
                    throw new InvalidOperationException("Cannot unspawn original Siren encounter identity while the server is inactive");
                if (identity.netId != capturedNetworkId)
                    throw new InvalidOperationException("Original Siren encounter network ID changed before unspawn");
                NetworkServer.UnSpawn(encounterObject);
            }
            if (NetworkServer.FindLocalObject(capturedNetworkId))
                throw new InvalidOperationException("Original Siren encounter network ID remains registered after NetworkServer.UnSpawn");
            Report.networkObjectUnspawned = true;
            ownsNetworkSpawn = false;
        }
    }

    void RestoreEncounterActiveState()
    {
        if (!ownsActiveStateMutation)
            return;
        if (!encounterObject)
            throw new InvalidOperationException("Cannot verify restoration of the exact owned Siren scene instance active state");
        encounterObject.SetActive(originalActiveSelf);
        Report.originalActiveRestored = encounterObject.activeSelf == originalActiveSelf;
        if (!Report.originalActiveRestored)
            throw new InvalidOperationException("Original Siren scene instance active state did not restore");
        ownsActiveStateMutation = false;
        Report.sourceOwnerAttached = false;
    }

    void DestroyOwnedSourceSceneInstance()
    {
        if (!ownsActivatedSceneInstance)
            return;
        if (!Report.networkObjectUnspawned)
            throw new InvalidOperationException("Cannot destroy the Siren scene identity before its network registration is proven retired");
        if (!NetworkServer.active)
            throw new InvalidOperationException("Cannot synchronously destroy the owned Siren scene instance while the server is inactive");
        if (!encounterObject || !identity)
            throw new InvalidOperationException("Exact owned Siren scene object or identity disappeared before owner destruction");
        if (!scene.IsValid() || !scene.isLoaded || scene.name != SirenEncounterContract.SceneName ||
            encounterObject.scene != scene || encounterObject.name != SirenEncounterContract.EncounterObjectName ||
            identity.sceneId.Value != SirenEncounterContract.EncounterSceneId)
            throw new InvalidOperationException("Refusing to synchronously destroy an object that no longer matches the owned Ship Graveyard scene identity");
        UnityEngine.Object.DestroyImmediate(encounterObject);
        Report.sceneInstanceDestroyed = !encounterObject;
        if (!Report.sceneInstanceDestroyed)
            throw new InvalidOperationException("Owned Siren source scene instance remained alive after synchronous destruction");
        ownsActivatedSceneInstance = false;
    }

    void CaptureNetworkSpawnOwnership()
    {
        if (!identity)
            return;
        var capturedId = identity.netId;
        if (capturedId.Value != 0 || identity.isServer)
        {
            Report.networkId = capturedId.Value;
            Report.networkObjectUnspawned = false;
        }
        if (capturedId.Value != 0 && NetworkServer.FindLocalObject(capturedId) == encounterObject)
            ownsNetworkSpawn = true;
    }

    public void Dispose()
    {
        Release();
    }
}
