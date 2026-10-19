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

    public static void RunAttachTransaction(Action activate, Action spawn, Action rollback)
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
            catch
            {
                // Preserve the attach failure; rollback owns its own finally-based restoration.
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
        public int diagnosticSourceEggCandidatesObserved, nativeEggSlotsRegistered;
        public int observedEggBodyCount, nativeBossMembers, observationSamples, encounterSquadMembersAtCleanup,
            retiredBossBodiesRequested, retiredBossMastersRequested, retiredProbeBodiesRequested,
            retiredProbeMastersRequested;
        public uint identitySceneId, networkId;
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
    bool ownsBossDefeatObservation;
    bool ownsSquadMemberObservation;
    bool ownsMinionSummonObservation;
    bool disposed;
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

    public static SirenEncounterSession Attach(Scene scene, Action<PortSession.SirenEncounterReport> onReportSelected = null)
    {
        if (!NetworkServer.active)
            throw new InvalidOperationException("Siren encounter source identity requires the active local server");
        var selected = SelectSourceEncounter(scene);
        var owner = new SirenEncounterSession(scene, selected, selected.GetComponent<NetworkIdentity>(),
            selected.GetComponent<EntityStateMachine>(), selected.GetComponent<ScriptedCombatEncounter>(),
            selected.GetComponent<BossGroup>());
        owner.PrepareDiagnosticEggSourceContract();
        if (owner.identity.isServer || owner.identity.netId.Value != 0)
            throw new InvalidOperationException("Original Siren encounter identity is already server-spawned; refusing ownership transfer");
        onReportSelected?.Invoke(owner.Report);

        SirenEncounterContract.RunAttachTransaction(
            () =>
            {
                BossGroup.onBossGroupDefeatedServer += owner.OnBossGroupDefeatedServer;
                owner.ownsBossDefeatObservation = true;
                owner.ownsActivatedSceneInstance = true;
                owner.ownsNetworkSpawn = true;
                selected.SetActive(true);
                owner.encounter.combatSquad.onMemberAddedServer += owner.OnEncounterMemberAddedServer;
                owner.ownsSquadMemberObservation = true;
                // MasterSummon's report follows Spawn/Respawn. Its earlier
                // ownership-change event occurs before the minion has a netId.
                MasterSummon.onServerMasterSummonGlobal += owner.OnMinionSummoned;
                owner.ownsMinionSummonObservation = true;
            },
            () =>
            {
                NetworkServer.Spawn(selected);
                if (!owner.identity.isServer || owner.identity.netId.Value == 0)
                    throw new InvalidOperationException("Original Siren encounter identity did not acquire a server network ID");

                owner.Report.sourceOwnerAttached = true;
                owner.Report.networkId = owner.identity.netId.Value;
                owner.Report.networkObjectUnspawned = false;
                owner.Observe(force: true);
            },
            owner.Release);
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
        if (!disposed && defeated == bossGroup && encounter && encounter.hasSpawnedServer)
        {
            Report.nativeEncounterCompleted = true;
            Report.observation = "original-native-encounter-started-and-exact-boss-group-defeat-event-observed";
        }
    }

    void OnEncounterMemberAddedServer(CharacterMaster member)
    {
        if (disposed || !NetworkServer.active || !member || member.teamIndex != TeamIndex.Monster ||
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
        if (disposed || !NetworkServer.active || !ownership || !summon.leaderMasterInstance)
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
        if (disposed || !encounterObject || !encounterObject.activeInHierarchy)
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
        disposed = true;
        Exception firstFailure = null;
        Action<Action> attempt = operation =>
        {
            try
            {
                operation();
            }
            catch (Exception exception)
            {
                if (firstFailure == null)
                    firstFailure = exception;
                Report.cleanupError = string.IsNullOrEmpty(Report.cleanupError)
                    ? exception.GetType().Name + ": " + exception.Message
                    : Report.cleanupError + " | " + exception.GetType().Name + ": " + exception.Message;
            }
        };

        if (ownsBossDefeatObservation)
        {
            attempt(() => BossGroup.onBossGroupDefeatedServer -= OnBossGroupDefeatedServer);
            ownsBossDefeatObservation = false;
        }

        if (ownsSquadMemberObservation)
        {
            attempt(() =>
            {
                if (encounter && encounter.combatSquad)
                    encounter.combatSquad.onMemberAddedServer -= OnEncounterMemberAddedServer;
            });
            ownsSquadMemberObservation = false;
        }

        if (ownsMinionSummonObservation)
        {
            attempt(() => MasterSummon.onServerMasterSummonGlobal -= OnMinionSummoned);
            ownsMinionSummonObservation = false;
        }

        attempt(RetireEncounterSquadMembers);
        attempt(UnSpawnOwnedEncounter);
        attempt(RestoreEncounterActiveState);
        attempt(DestroyOwnedSourceSceneInstance);

        Report.cleanupDisposed = true;
        Report.observation = "owner-disposed; body-destruction-requests=" + Report.retiredBossBodiesRequested +
            "; master-destruction-requests=" + Report.retiredBossMastersRequested +
            "; probe-body-destruction-requests=" + Report.retiredProbeBodiesRequested +
            "; probe-master-destruction-requests=" + Report.retiredProbeMastersRequested +
            "; original-active-restored=" + Report.originalActiveRestored +
            "; scene-instance-destroyed=" + Report.sceneInstanceDestroyed +
            "; network-unspawned=" + Report.networkObjectUnspawned +
            (string.IsNullOrEmpty(Report.cleanupError) ? "" : "; cleanup-error=" + Report.cleanupError);

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
        if (firstFailure != null)
            throw firstFailure;
    }

    void RetireEncounterSquadMembers()
    {
        if (!encounter || !encounter.combatSquad)
            return;

        if (!NetworkServer.active)
            throw new InvalidOperationException("Cannot retire original Siren encounter actors while the server is inactive");

        var members = encounter.combatSquad.readOnlyMembersList.Where(member => member).ToArray();
        Report.encounterSquadMembersAtCleanup = members.Length;
        var roots = ownedBossMasters.Where(entry => entry.master).ToArray();
        var probes = ownedProbeMasters.Where(entry => entry.master).ToArray();

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
            ValidateOwnedMaster(entry, OriginalBossBodyName, NetworkInstanceId.Invalid, "native boss");
        foreach (var entry in probes)
        {
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
            RequestDestroy(entry.master, isProbe: true);
        foreach (var entry in roots)
            RequestDestroy(entry.master, isProbe: false);
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

    void RequestDestroy(CharacterMaster member, bool isProbe)
    {
        var body = member.GetBody();
        var bodyObject = body ? body.gameObject : null;
        var masterObject = member.gameObject;
        if (bodyObject)
        {
            NetworkServer.Destroy(bodyObject);
            if (isProbe)
                Report.retiredProbeBodiesRequested++;
            else
                Report.retiredBossBodiesRequested++;
            Report.retirementRequestsIssued = true;
        }
        if (masterObject)
        {
            NetworkServer.Destroy(masterObject);
            if (isProbe)
                Report.retiredProbeMastersRequested++;
            else
                Report.retiredBossMastersRequested++;
            Report.retirementRequestsIssued = true;
        }
    }

    void UnSpawnOwnedEncounter()
    {
        try
        {
            if (ownsNetworkSpawn && identity && identity.netId.Value != 0)
            {
                if (!NetworkServer.active)
                    throw new InvalidOperationException("Cannot unspawn original Siren encounter identity while the server is inactive");
                var capturedNetworkId = identity.netId;
                NetworkServer.UnSpawn(encounterObject);
                if (NetworkServer.FindLocalObject(capturedNetworkId) == encounterObject)
                    throw new InvalidOperationException("Original Siren encounter identity remains registered after NetworkServer.UnSpawn");
                Report.networkObjectUnspawned = true;
            }
        }
        finally
        {
            ownsNetworkSpawn = false;
        }
    }

    void RestoreEncounterActiveState()
    {
        if (encounterObject)
            encounterObject.SetActive(originalActiveSelf);
        Report.originalActiveRestored = encounterObject && encounterObject.activeSelf == originalActiveSelf;
        Report.sourceOwnerAttached = false;
    }

    void DestroyOwnedSourceSceneInstance()
    {
        if (!ownsActivatedSceneInstance)
            return;
        if (!NetworkServer.active)
            throw new InvalidOperationException("Cannot synchronously destroy the owned Siren scene instance while the server is inactive");
        if (encounterObject && (!scene.IsValid() || !scene.isLoaded || scene.name != SirenEncounterContract.SceneName ||
            encounterObject.scene != scene || encounterObject.name != SirenEncounterContract.EncounterObjectName ||
            !identity || identity.sceneId.Value != SirenEncounterContract.EncounterSceneId))
            throw new InvalidOperationException("Refusing to synchronously destroy an object that no longer matches the owned Ship Graveyard scene identity");
        if (encounterObject)
            UnityEngine.Object.DestroyImmediate(encounterObject);
        Report.sceneInstanceDestroyed = !encounterObject;
        if (!Report.sceneInstanceDestroyed)
            throw new InvalidOperationException("Owned Siren source scene instance remained alive after synchronous destruction");
        ownsActivatedSceneInstance = false;
    }

    public void Dispose()
    {
        Release();
    }
}
