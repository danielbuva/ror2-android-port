// Subsystem: native Siren encounter observation. Owner: SirenEncounterSession.
// Setup: exact source encounter; teardown: ClearDiagnosticEggCandidates.
// Reads native registration and validates targets without changing gameplay.
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

public sealed partial class SirenEncounterSession
{
    static readonly FieldInfo ListeningHasRegisteredEggsField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening)
            .GetField("hasRegisteredEggs", BindingFlags.Instance | BindingFlags.NonPublic);
    static readonly FieldInfo ListeningEggListField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening).GetField("eggList", BindingFlags.Instance | BindingFlags.NonPublic);

    struct DiagnosticEggCandidate
    {
        public CharacterBody body;
        public string nativeListenerName;
    }
    readonly List<DiagnosticEggCandidate> diagnosticSourceEggCache = new List<DiagnosticEggCandidate>();
    GameObject originalEggBodyPrefab;
    BodyIndex originalEggBodyIndex;
    NetworkHash128 originalEggAssetId;
    EntityStates.Missions.SuperRoboBallEncounter.Listening observedNativeListeningState;
    List<GameObject> observedNativeEggList;
    bool nativeEggRegistrationObserved;

    public int DiagnosticSceneHandle => scene.IsValid() ? scene.handle : 0;
    public bool DiagnosticSceneActive => IsCurrentSceneOwner();
    public bool DiagnosticOwnerAttached => IsLiveNetworkOwner();
    public bool NativeEncounterStarted => encounter && encounter.hasSpawnedServer;
    public bool NativeEggRegistrationObserved => nativeEggRegistrationObserved && observedNativeListeningState != null;
    public int NativeEggSlotsRegistered => NativeEggRegistrationObserved && observedNativeEggList != null ? observedNativeEggList.Count : 0;
    public bool DiagnosticListenerActive => IsLiveNetworkOwner() && stateMachine &&
                                            stateMachine.state is EntityStates.Missions.SuperRoboBallEncounter.Listening &&
                                            !NativeEncounterStarted;

    public void PrepareDiagnosticEggSourceContract()
    {
        if (ListeningHasRegisteredEggsField == null || ListeningHasRegisteredEggsField.FieldType != typeof(bool) ||
            ListeningEggListField == null || ListeningEggListField.FieldType != typeof(List<GameObject>) ||
            !ListeningHasRegisteredEggsField.IsPrivate || !ListeningEggListField.IsPrivate)
            throw new InvalidOperationException("Original Listening egg-registration fields changed from the accepted source contract");
        originalEggBodyPrefab = BodyCatalog.FindBodyPrefab("VultureEggBody");
        originalEggBodyIndex = BodyCatalog.FindBodyIndex("VultureEggBody");
        var originalIdentity = originalEggBodyPrefab ? originalEggBodyPrefab.GetComponent<NetworkIdentity>() : null;
        if (!originalEggBodyPrefab || originalEggBodyIndex == BodyIndex.None || !originalIdentity)
            throw new InvalidOperationException("Original Vulture Egg prefab/body/network identity is unavailable");
        originalEggAssetId = originalIdentity.assetId;
        if (originalEggAssetId.Equals(default(NetworkHash128)))
            throw new InvalidOperationException("Original Vulture Egg network asset ID is empty");
    }

    // Reflection is intentionally sampled only at the existing 0.5 second
    // observation cadence. The private native list is read-only and the exact
    // Listening object is retained so a replacement state cannot inherit its
    // registration snapshot.
    public void ObserveNativeEggRegistration()
    {
        var current = stateMachine ? stateMachine.state as EntityStates.Missions.SuperRoboBallEncounter.Listening : null;
        if (!ReferenceEquals(current, observedNativeListeningState))
        {
            ObserveNativeListeningStateChange(current);
            observedNativeListeningState = current;
            observedNativeEggList = null;
            nativeEggRegistrationObserved = false;
            diagnosticSourceEggCache.Clear();
        }
        if (current == null || !IsLiveNetworkOwner() || NativeEncounterStarted)
            return;
        if (!(bool)ListeningHasRegisteredEggsField.GetValue(current))
            return;
        var registered = ListeningEggListField.GetValue(current) as List<GameObject>;
        if (registered == null)
            throw new InvalidOperationException("Original Listening reports registered eggs but its native egg list is null");
        observedNativeEggList = registered;
        nativeEggRegistrationObserved = true;
        if (expectedSourceEggs != null)
        {
            var identities = registered.Select(gameObject => gameObject ? gameObject.GetComponent<NetworkIdentity>() : null).ToArray();
            Report.nativeRegisteredEggNetworkIds = identities.Where(identity => identity).Select(identity => identity.netId.Value).ToArray();
            Report.nativeEggRegistrationMatchesSourceEntry = identities.Length == expectedSourceEggs.Length &&
                identities.All(identity => identity && identity.isServer && identity.netId.Value != 0 &&
                    ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), identity.gameObject)) &&
                identities.Select(identity => identity.gameObject).Distinct().Count() == expectedSourceEggs.Length &&
                expectedSourceEggs.All(expected => expected && identities.Any(actual => ReferenceEquals(actual, expected)));
        }
    }

    bool IsCurrentNativeRegisteredEgg(GameObject candidate)
    {
        if (!candidate || !DiagnosticListenerActive || !NativeEggRegistrationObserved || observedNativeEggList == null)
            return false;
        var current = stateMachine ? stateMachine.state as EntityStates.Missions.SuperRoboBallEncounter.Listening : null;
        if (!ReferenceEquals(current, observedNativeListeningState))
            return false;
        return SirenEggSourceContract.IsExactNativeRegisteredMember(observedNativeEggList, candidate);
    }

    // Called from SirenEncounterSession.Observe after the existing 0.5 second
    // bound. This is also the original Listener population sample: it counts
    // every body whose native runtime name contains VultureEgg, while caching
    // only exact-list registered, fully revalidated source instances when the
    // same native Listening state instance is live.
    public int RefreshDiagnosticEggCandidates(IList<CharacterBody> bodies)
    {
        diagnosticSourceEggCache.Clear();
        bool mayCache = DiagnosticListenerActive && NativeEggRegistrationObserved && !NativeEncounterStarted;
        int observedEggCount = 0;
        if (bodies != null)
        {
            for (int i = 0; i < bodies.Count; i++)
            {
                CharacterBody body = bodies[i];
                if (!body)
                    continue;
                string nativeListenerName = body.name;
                if (nativeListenerName.IndexOf("VultureEgg", StringComparison.Ordinal) < 0)
                    continue;
                observedEggCount++;
                if (mayCache && IsCurrentDiagnosticSourceEgg(body, nativeListenerName))
                    diagnosticSourceEggCache.Add(new DiagnosticEggCandidate { body = body, nativeListenerName = nativeListenerName });
            }
        }
        if (Report != null)
            Report.diagnosticSourceEggCandidatesObserved = diagnosticSourceEggCache.Count;
        return observedEggCount;
    }

    public bool CollectRevalidatedDiagnosticEggs(List<CharacterBody> destination)
    {
        if (destination == null)
            throw new ArgumentNullException(nameof(destination));
        destination.Clear();
        if (!DiagnosticListenerActive || NativeEncounterStarted)
            return true;
        if (!SirenEggTargetSelectionPolicy.IsCandidateCountSupported(diagnosticSourceEggCache.Count))
        {
            if (Report != null)
                Report.diagnosticSourceEggCandidatesObserved = diagnosticSourceEggCache.Count;
            return false;
        }
        for (int i = diagnosticSourceEggCache.Count - 1; i >= 0; i--)
        {
            DiagnosticEggCandidate cached = diagnosticSourceEggCache[i];
            CharacterBody candidate = cached.body;
            if (!IsCurrentDiagnosticSourceEgg(candidate, cached.nativeListenerName))
            {
                diagnosticSourceEggCache.RemoveAt(i);
                continue;
            }
            destination.Add(candidate);
        }
        if (Report != null)
            Report.diagnosticSourceEggCandidatesObserved = diagnosticSourceEggCache.Count;
        return true;
    }

    public CharacterBody NearestRevalidatedDiagnosticEgg(Vector3 position)
    {
        if (!DiagnosticListenerActive || NativeEncounterStarted)
            return null;
        CharacterBody nearest = null;
        float nearestSqr = float.PositiveInfinity;
        for (int i = diagnosticSourceEggCache.Count - 1; i >= 0; i--)
        {
            DiagnosticEggCandidate cached = diagnosticSourceEggCache[i];
            CharacterBody candidate = cached.body;
            if (!IsCurrentDiagnosticSourceEgg(candidate, cached.nativeListenerName))
            {
                diagnosticSourceEggCache.RemoveAt(i);
                continue;
            }
            float sqr = (candidate.corePosition - position).sqrMagnitude;
            if (sqr < nearestSqr)
            {
                nearestSqr = sqr;
                nearest = candidate;
            }
        }
        if (Report != null)
            Report.diagnosticSourceEggCandidatesObserved = diagnosticSourceEggCache.Count;
        return nearest;
    }

    public bool IsCurrentDiagnosticSourceEgg(CharacterBody body)
    {
        for (int i = diagnosticSourceEggCache.Count - 1; i >= 0; i--)
        {
            DiagnosticEggCandidate cached = diagnosticSourceEggCache[i];
            if (cached.body == body)
                return IsCurrentDiagnosticSourceEgg(body, cached.nativeListenerName);
        }
        return false;
    }

    bool IsCurrentDiagnosticSourceEgg(CharacterBody body, string nativeListenerName)
    {
        if (!body || !originalEggBodyPrefab || !DiagnosticListenerActive || NativeEncounterStarted)
            return false;

        Scene candidateScene = body.gameObject.scene;
        CharacterBody sourcePrefabBody = originalEggBodyPrefab.GetComponent<CharacterBody>();
        HealthComponent health = body.healthComponent;
        HurtBoxGroup group = body.hurtBoxGroup;
        HurtBox main = body.mainHurtBox;
        NetworkIdentity candidateIdentity = body.GetComponent<NetworkIdentity>();
        bool sceneLoaded = candidateScene.IsValid() && candidateScene.isLoaded;
        bool exactNetworkMapObject = candidateIdentity && candidateIdentity.netId.Value != 0 &&
                                     NetworkServer.FindLocalObject(candidateIdentity.netId) == body.gameObject;
        bool registeredByCurrentNativeListener = IsCurrentNativeRegisteredEgg(body.gameObject);
        bool sourceNetworkIdentity = candidateIdentity && candidateIdentity.assetId.Equals(originalEggAssetId);
        bool sourceBodyIdentity = body.bodyIndex == originalEggBodyIndex && sourcePrefabBody &&
                                  BodyCatalog.GetBodyPrefab(body.bodyIndex) == originalEggBodyPrefab;

        var evidence =
            new SirenEggCandidateEvidence { ownerLive = IsLiveNetworkOwner() && DiagnosticListenerActive && !NativeEncounterStarted,
                                            candidateSceneLoaded = sceneLoaded,
                                            candidateSceneHandle = candidateScene.IsValid() ? candidateScene.handle : 0,
                                            ownerSceneHandle = scene.IsValid() ? scene.handle : 0,
                                            activeSceneHandle = SceneManager.GetActiveScene().handle,
                                            bodyName = nativeListenerName,
                                            bodyIndex = (int)body.bodyIndex,
                                            expectedBodyIndex = (int)originalEggBodyIndex,
                                            nativeRegisteredEggCount = NativeEggSlotsRegistered,
                                            nativeRegistrationObserved = NativeEggRegistrationObserved,
                                            nativeListeningInstanceMatches =
                                                stateMachine && ReferenceEquals(stateMachine.state, observedNativeListeningState),
                                            nativeRegisteredListContainsCandidate = registeredByCurrentNativeListener,
                                            identityIsServer = candidateIdentity && candidateIdentity.isServer,
                                            hasNonzeroNetworkId = candidateIdentity && candidateIdentity.netId.Value != 0,
                                            sourceAssetIdMatches = sourceNetworkIdentity && sourceBodyIdentity,
                                            networkMapOwnsExactObject = exactNetworkMapObject,
                                            healthExists = health,
                                            healthAlive = health && health.alive,
                                            hurtBoxGroupExists = group,
                                            mainHurtBoxExists = main,
                                            groupOwnsMainHurtBox = group && group.mainHurtBox == main,
                                            mainHurtBoxBullseye = main && main.isBullseye,
                                            mainHurtBoxEnabled = main && main.enabled,
                                            mainHurtBoxActive = main && main.gameObject.activeInHierarchy,
                                            hurtBoxUsesSameHealthComponent = main && health && main.healthComponent == health };
        return SirenEggSourceContract.IsEligible(evidence);
    }

    bool IsCurrentSceneOwner()
    {
        return !disposed && scene.IsValid() && scene.isLoaded && scene.name == SirenEncounterContract.SceneName &&
               SceneManager.GetActiveScene() == scene;
    }

    bool IsLiveNetworkOwner()
    {
        return IsCurrentSceneOwner() && NetworkServer.active && encounterObject && identity && identity.isServer &&
               identity.netId.Value != 0 && identity.sceneId.Value == SirenEncounterContract.EncounterSceneId &&
               encounterObject.scene == scene && NetworkServer.FindLocalObject(identity.netId) == encounterObject;
    }

    public void ClearDiagnosticEggCandidates()
    {
        ReleaseNativeListeningSnapshotBaseline();
        diagnosticSourceEggCache.Clear();
        originalEggBodyPrefab = null;
        originalEggBodyIndex = BodyIndex.None;
        originalEggAssetId = default(NetworkHash128);
        observedNativeListeningState = null;
        observedNativeEggList = null;
        nativeEggRegistrationObserved = false;
    }
}
