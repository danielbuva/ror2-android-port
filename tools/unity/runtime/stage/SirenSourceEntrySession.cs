// Subsystem: integrated stage transport. Owner: IntegratedStageSession.
// Setup: exact source ID 11 before Run's one native stage callback; dispatch
// the complete global callback immediately afterward. Teardown: exact captured
// egg roots and ID-11 identity before additive source-scene retirement.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using RoR2.Networking;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

/// <summary>Observes one routine without changing its yielded values or thrown exception.</summary>
public sealed class SirenSourceEntryObservedRoutine : IEnumerator
{
    readonly IEnumerator inner;
    readonly string operation;
    readonly Action<string, string> onBoundary;
    readonly Action<string, Exception> onFailure;
    bool started, completed;

    public SirenSourceEntryObservedRoutine(IEnumerator inner, string operation, Action<string, string> onBoundary,
                                           Action<string, Exception> onFailure)
    {
        this.inner = inner ?? throw new ArgumentNullException(nameof(inner));
        this.operation = operation ?? throw new ArgumentNullException(nameof(operation));
        this.onBoundary = onBoundary;
        this.onFailure = onFailure;
    }

    void CaptureFailure(Exception error)
    {
        try { onFailure?.Invoke(operation, error); }
        catch { /* Keep the original iterator exception authoritative. */ }
    }

    void CaptureBoundary(string phase)
    {
        try { onBoundary?.Invoke(operation, phase); }
        catch { /* Boundary reporting is best-effort and is not a native iterator failure. */ }
    }

    public object Current
    {
        get
        {
            try { return inner.Current; }
            catch (Exception error) { CaptureFailure(error); throw; }
        }
    }

    public bool MoveNext()
    {
        if (completed)
            return false;
        try
        {
            if (!started)
            {
                started = true;
                CaptureBoundary("entered");
            }
            if (inner.MoveNext())
                return true;
            completed = true;
            CaptureBoundary("returned");
            return false;
        }
        catch (Exception error)
        {
            CaptureFailure(error);
            throw;
        }
    }

    public void Reset()
    {
        try
        {
            inner.Reset();
            started = false;
            completed = false;
        }
        catch (Exception error) { CaptureFailure(error); throw; }
    }
}

/// <summary>
/// Attempt-scoped owner for the original Ship Graveyard toggle controller and
/// its exact native egg-spawner outputs. It never creates or edits egg gameplay
/// objects; GenericSceneSpawnPoint.Start remains the only spawn implementation.
/// </summary>
public sealed class SirenSourceEntrySession : IDisposable
{
    sealed class SourceEgg
    {
        public GameObject toggleTarget, spawner;
        public GenericSceneSpawnPoint spawnPoint;
        public SirenSourceEntrySpawnWitness witness;
        public bool selected;
        public bool observed;
        public bool retired;
        public NetworkIdentity identity;
        public GameObject body;
        public NetworkInstanceId networkId;
        public Vector3 expectedPosition;
        public Quaternion expectedRotation;
    }
    sealed class SourceIdentityState
    {
        public NetworkIdentity identity;
        public bool activeSelf;
    }
    sealed class ToggleTargetState
    {
        public GameObject target;
        public NetworkIdentity identity;
        public bool targetWasNull, identityWasNull;
        public bool activeBefore, registeredBefore, expectedActive, expectedKnown;
    }

    const uint DirectorSceneId = 2;
    const uint ControllerSceneId = 11;
    static readonly int[] GroupWidths = { 1, 2, 4, 3, 32 };
    static readonly int[] GroupMinimums = { 0, 1, 2, 1, 12 };
    static readonly int[] GroupMaximums = { 1, 1, 4, 1, 12 };
    static readonly BindingFlags PrivateStatic = BindingFlags.Static | BindingFlags.NonPublic;
    static readonly BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;
    static readonly FieldInfo ToggleQueueField = typeof(SceneObjectToggleGroup).GetField("activationsQueue", PrivateStatic);
    static readonly FieldInfo ToggleObjectsField = typeof(SceneObjectToggleGroup).GetField("allToggleableObjects", PrivateInstance);
    static readonly FieldInfo ToggleActivationsField = typeof(SceneObjectToggleGroup).GetField("activations", PrivateInstance);
    static readonly Type SpawnGroupType = AppDomain.CurrentDomain.GetAssemblies()
        .Select(assembly => assembly.GetType("RoR2.SceneObjectSpawnGroup", false)).FirstOrDefault(type => type != null);
    static readonly FieldInfo SpawnQueueField = SpawnGroupType?.GetField("activationsQueue", PrivateStatic);
    static readonly MethodInfo ToggleDrain = typeof(SceneObjectToggleGroup).GetMethod("OnServerSceneChanged", PrivateStatic);
    static readonly MethodInfo SpawnDrain = SpawnGroupType?.GetMethod("OnServerSceneChanged", PrivateStatic);
    static readonly FieldInfo GlobalHandlers = typeof(NetworkManagerSystem).GetField("onServerSceneChangedGlobal", PrivateStatic);
    static readonly MethodInfo ResetIdentity = typeof(NetworkIdentity).GetMethod("Reset", PrivateInstance);

    readonly Scene scene;
    readonly PortSession.SirenSourceEntryReport report;
    readonly List<SourceEgg> sourceEggs = new List<SourceEgg>();
    readonly List<SourceIdentityState> foreignSourceIdentities = new List<SourceIdentityState>();
    readonly List<ToggleTargetState> toggleTargetStates = new List<ToggleTargetState>();
    readonly HashSet<uint> networkIdsBefore = new HashSet<uint>();
    GameObject directorRoot;
    NetworkIdentity directorIdentity;
    bool directorRootActivationExpected;
    SceneObjectToggleGroup controller;
    NetworkIdentity controllerIdentity;
    GameObject controllerObject;
    GameObject eggPrefab;
    NetworkHash128 eggAssetId;
    Delegate globalHandlersBefore;
    Delegate dispatchedHandlers;
    NetworkInstanceId controllerNetworkId;
    bool controllerActiveMutationOwned;
    bool controllerSpawnAttempted;
    bool controllerSpawnOwned;
    bool activated;
    bool globalDispatchAttempted;
    bool captureFailure;
    bool globalDispatched;
    bool complete;
    bool cleanupStarted;
    bool disposed;
    int cleanupStep;
    Exception cleanupFirstFailure;

    SirenSourceEntrySession(Scene scene, PortSession.SirenSourceEntryReport report)
    {
        this.scene = scene;
        this.report = report;
    }

    public PortSession.SirenSourceEntryReport Report => report;
    public IReadOnlyList<NetworkIdentity> CapturedEggIdentities =>
        sourceEggs.Where(row => row.selected && row.observed && row.identity).Select(row => row.identity).ToArray();
    public bool Complete => complete && !disposed;
    public bool CanAdmitOriginalEncounter(bool diagnosticEggInputSelected)
    {
        var original = SirenEncounterSession.SelectSourceEncounter(scene);
        return SirenSourceEntryContract.MayAdmitEncounter(
            Complete && report.exactEggBijection && CapturedEggIdentities.Count == GroupMinimums[4],
            QueueItems(ToggleQueueField).Length == 0,
            QueueItems(SpawnQueueField).Length == 0,
            original && !original.activeSelf && !IsRegistered(original.GetComponent<NetworkIdentity>()),
            !diagnosticEggInputSelected);
    }

    public static SirenSourceEntrySession Prepare(Scene scene, Action<PortSession.SirenSourceEntryReport> retain)
    {
        var report = new PortSession.SirenSourceEntryReport { scene = scene.IsValid() ? scene.name : "invalid", status = "preparing" };
        var owner = new SirenSourceEntrySession(scene, report);
        owner.PreflightSource();
        retain?.Invoke(report);
        return owner;
    }

    void PreflightSource()
    {
        Require(scene.IsValid() && scene.isLoaded && scene.name == SirenEncounterContract.SceneName &&
                    SceneManager.GetActiveScene() == scene && NetworkServer.active && Run.instance &&
                    Stage.instance && Run.instance.stageRng != null,
                "Siren source-entry requires the active loaded Ship Graveyard, server Run/temporary Stage, and initialized native stageRng");
        Require(ToggleQueueField != null && ToggleObjectsField != null && ToggleActivationsField != null && SpawnQueueField != null &&
                    ToggleDrain != null && SpawnDrain != null && GlobalHandlers != null && ResetIdentity != null,
                "Pinned native toggle/spawn queue, identity reset, or global callback contract changed");

        var contextsAsset = Resources.Load<TextAsset>("WholeStageContexts");
        var bootstrapAsset = Resources.Load<TextAsset>("WholeCatalogBootstrap");
        Require(contextsAsset && bootstrapAsset, "Receipt-bound whole-stage metadata/bootstrap is unavailable");
        var contexts = JObject.Parse(contextsAsset.text);
        var bootstrap = JObject.Parse(bootstrapAsset.text);
        Require((int?)contexts["source_identity_schema_version"] == 1 &&
                    (string)contexts["input_id"] == (string)bootstrap["input_id"],
                "Siren source-entry metadata belongs to a different input generation/schema");
        var entry = contexts["stages"]?[SirenEncounterContract.SceneName]?["siren_source_entry"] as JObject;
        Require(entry != null && IsSha256((string)entry["source_scene_sha256"]),
                "Receipt-bound Siren source-entry scene identity metadata is absent/malformed");
        var controllerRows = entry["toggle_controllers"] as JArray;
        Require(controllerRows != null && controllerRows.Count == 1 && (uint?)controllerRows[0]["scene_id"] == ControllerSceneId,
                "Siren metadata must identify exactly one source ID-11 toggle controller");
        var controllerRow = (JObject)controllerRows[0];
        controllerObject = ResolveTransformPath(scene, controllerRow["transform_path"] as JArray);
        controller = controllerObject ? controllerObject.GetComponent<SceneObjectToggleGroup>() : null;
        controllerIdentity = controllerObject ? controllerObject.GetComponent<NetworkIdentity>() : null;
        Require(controllerObject && controller && controllerIdentity && controllerObject.scene == scene &&
                    controllerObject.name == "ToggleGroupController" && controllerIdentity.sceneId.Value == ControllerSceneId &&
                    !controllerObject.activeSelf && !IsRegistered(controllerIdentity),
                "Source ID-11 controller is absent, active, registered, or differs from the exact source component binding");
        ValidateToggleGroups(controller, controllerRow["groups"] as JArray);
        foreach (var target in controller.toggleGroups.SelectMany(group => group.objects))
        {
            var identity = target ? target.GetComponent<NetworkIdentity>() : null;
            toggleTargetStates.Add(new ToggleTargetState {
                target = target, identity = identity,
                targetWasNull = ReferenceEquals(target, null), identityWasNull = ReferenceEquals(identity, null),
                activeBefore = target && target.activeSelf, registeredBefore = IsRegistered(identity)
            });
        }
        Require(toggleTargetStates.Count == GroupWidths.Sum(), "Source toggle target snapshot dimensions changed");
        var encounter = SirenEncounterSession.SelectSourceEncounter(scene);
        var encounterIdentity = encounter.GetComponent<NetworkIdentity>();
        Require(encounter && encounterIdentity.sceneId.Value == SirenEncounterContract.EncounterSceneId &&
                    !encounter.activeSelf && !IsRegistered(encounterIdentity),
                "Original ID-10 encounter must remain inactive and unregistered before source egg entry");
        var expectedIdentities = (entry["network_identities"] as JArray) ?? throw Refuse("Siren source identity map is absent");
        var sourceIdentities = scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren<NetworkIdentity>(true))
            .Where(identity => identity && !identity.sceneId.IsEmpty()).ToArray();
        Require(sourceIdentities.Length == expectedIdentities.Count &&
                    sourceIdentities.Select(identity => identity.sceneId.Value).Distinct().Count() == sourceIdentities.Length,
                "Imported Ship Graveyard nonzero source identity set differs from the receipt-bound metadata");
        foreach (var row in expectedIdentities)
        {
            uint sceneId = (uint)row["scene_id"];
            var matches = sourceIdentities.Where(identity => identity.sceneId.Value == sceneId).ToArray();
            bool hasSingleIdentity = matches.Length == 1;
            string expectedName = (string)row["name"];
            bool expectedActiveSelf = (bool)row["active_self"];
            string actualName = hasSingleIdentity ? matches[0].gameObject.name : "<not-one>";
            bool actualActiveSelf = hasSingleIdentity && matches[0].gameObject.activeSelf;
            bool registered = hasSingleIdentity && IsRegistered(matches[0]);
            Require(hasSingleIdentity && actualName == expectedName && actualActiveSelf == expectedActiveSelf && !registered,
                    "Imported source NetworkIdentity differs from receipt at ID " + sceneId + ": matches=" + matches.Length +
                        ", expectedName='" + expectedName + "', actualName='" + actualName + "', expectedActiveSelf=" + expectedActiveSelf +
                        ", actualActiveSelf=" + actualActiveSelf + ", registered=" + registered);
            bool nativeToggleTarget = toggleTargetStates.Any(target => ReferenceEquals(target.target, matches[0].gameObject));
            if (sceneId == DirectorSceneId)
            {
                directorRoot = matches[0].gameObject;
                directorIdentity = matches[0];
                Require(directorRoot.name == "Director" && directorRoot.scene == scene && !directorRoot.activeSelf &&
                            directorRoot.GetComponent<SceneDirector>() && ReferenceEquals(directorIdentity.gameObject, directorRoot),
                        "Receipt-bound ID-2 Director is not the exact inactive source root before its owned activation");
                VerifyOwnedDirectorIdentityState();
            }
            if (sceneId != ControllerSceneId && sceneId != DirectorSceneId && !nativeToggleTarget)
                foreignSourceIdentities.Add(new SourceIdentityState { identity = matches[0], activeSelf = matches[0].gameObject.activeSelf });
        }

        eggPrefab = BodyCatalog.FindBodyPrefab("VultureEggBody");
        var eggIdentity = eggPrefab ? eggPrefab.GetComponent<NetworkIdentity>() : null;
        Require(eggPrefab && eggIdentity && !eggIdentity.assetId.Equals(default(NetworkHash128)),
                "Original Vulture Egg body network prefab is unavailable");
        eggAssetId = eggIdentity.assetId;
        var groups = controllerRow["groups"] as JArray;
        var eggRows = groups[4]["objects"] as JArray;
        Require(eggRows != null && eggRows.Count == GroupWidths[4], "Receipt-bound source egg spawner mapping is incomplete");
        foreach (var target in eggRows)
        {
            var nestRoot = ResolveTransformPath(scene, target["transform_path"] as JArray);
            var spawnPoints = nestRoot ? nestRoot.GetComponentsInChildren<GenericSceneSpawnPoint>(true) : Array.Empty<GenericSceneSpawnPoint>();
            var spawner = spawnPoints.Length == 1 ? spawnPoints[0] : null;
            var spawnerObject = spawner ? spawner.gameObject : null;
            var prefabIdentity = spawner && spawner.networkedObjectPrefab
                                    ? spawner.networkedObjectPrefab.GetComponent<NetworkIdentity>() : null;
            Require(nestRoot && nestRoot.scene == scene && !nestRoot.activeSelf && spawner && spawner.enabled &&
                        spawnerObject && spawnerObject.scene == scene && spawnerObject.activeSelf &&
                        ReferenceEquals(spawner.networkedObjectPrefab, eggPrefab) && prefabIdentity &&
                        prefabIdentity.assetId.Equals(eggAssetId),
                    "Receipt-bound VultureNest must contain exactly one enabled typed GenericSceneSpawnPoint for the original egg prefab");
            sourceEggs.Add(new SourceEgg {
                toggleTarget = nestRoot,
                spawner = spawnerObject,
                spawnPoint = spawner,
                expectedPosition = spawner.transform.position,
                expectedRotation = spawner.transform.rotation
            });
        }
        Require(sourceEggs.Select(row => row.spawner).Distinct().Count() == GroupWidths[4],
                "Source egg spawner refs contain duplicates");
        RequireQueueEmpty(ToggleQueueField, "SceneObjectToggleGroup");
        RequireQueueEmpty(SpawnQueueField, "SceneObjectSpawnGroup");
        globalHandlersBefore = ValidateFullNativeMulticast();
        foreach (var identity in NetworkServer.objects.Values)
            if (identity)
                networkIdsBefore.Add(identity.netId.Value);
        report.selected = true;
        report.controllerSceneId = ControllerSceneId;
        report.sourceEggSpawnerCount = sourceEggs.Count;
        report.sourceSceneSha256 = (string)entry["source_scene_sha256"];
        report.status = "source-contract-preflight-passed";
    }

    void VerifyOwnedDirectorIdentityState()
    {
        var current = scene.GetRootGameObjects()
                          .SelectMany(root => root.GetComponentsInChildren<NetworkIdentity>(true))
                          .Where(identity => identity && identity.sceneId.Value == DirectorSceneId)
                          .ToArray();
        var actualIdentity = current.Length == 1 ? current[0] : null;
        var actualRoot = actualIdentity ? actualIdentity.gameObject : null;
        bool active = actualRoot && actualRoot.activeSelf;
        bool registered = actualIdentity && IsRegistered(actualIdentity);
        Require(current.Length == 1 && actualRoot && actualIdentity && actualRoot.scene == scene &&
                    ReferenceEquals(actualIdentity.gameObject, actualRoot) && actualRoot.name == "Director" &&
                    SirenSourceEntryContract.MatchesOwnedSourceDirectorState(directorRoot, actualRoot, directorIdentity, actualIdentity,
                                                                             active, directorRootActivationExpected, registered),
                "Exact source ID-2 Director changed outside its recorded AutomaticDirectorSession activation");
    }

    public void RecordOwnedDirectorActivation(GameObject root)
    {
        Require(!directorRootActivationExpected && ReferenceEquals(root, directorRoot) && root && directorIdentity && root.activeSelf &&
                    root.scene == scene && ReferenceEquals(directorIdentity.gameObject, root) &&
                    directorIdentity.sceneId.Value == DirectorSceneId && !IsRegistered(directorIdentity),
                "AutomaticDirectorSession did not activate the exact unregistered receipt-bound ID-2 Director");
        directorRootActivationExpected = true;
        VerifyOwnedDirectorIdentityState();
    }

    public void ActivateAndSpawnController()
    {
        VerifyOwnedDirectorIdentityState();
        Require(!activated && !complete && NetworkServer.active && Run.instance && Stage.instance &&
                    SceneManager.GetActiveScene() == scene && SirenSourceEntryContract.IsSameScene(controllerObject.scene, scene),
                "Siren source controller activation is out of order or source ownership changed");
        RequireQueueEmpty(ToggleQueueField, "SceneObjectToggleGroup");
        RequireQueueEmpty(SpawnQueueField, "SceneObjectSpawnGroup");
        if (!ReferenceEquals(GlobalHandlers.GetValue(null), globalHandlersBefore))
            throw Refuse("Native scene-changed multicast changed before controller activation");
        foreach (var row in sourceEggs)
        {
            row.witness = row.spawner.AddComponent<SirenSourceEntrySpawnWitness>();
            row.witness.Bind(this, row.spawner);
        }
        try
        {
            controllerObject.SetActive(true);
        }
        finally
        {
            if (controllerObject && controllerObject.activeSelf)
                controllerActiveMutationOwned = true;
        }
        var queued = QueueItems(ToggleQueueField);
        Require(queued.Length == 1 && ReferenceEquals(queued[0], controller),
                "Native toggle Awake did not enqueue exactly the owned ID-11 controller");
        var objects = ToggleObjectsField.GetValue(controller) as GameObject[];
        var bits = ToggleActivationsField.GetValue(controller) as bool[];
        Require(objects != null && bits != null && objects.Length == bits.Length &&
                    objects.Length == GroupWidths.Sum() && ReferenceEquals(objects[0], controller.toggleGroups[0].objects[0]),
                "Native controller Awake did not initialize the exact expected source-choice arrays");
        report.nativeAwakeObserved = true;
        report.nativeActivationChoiceCount = bits.Count(value => value);
        report.selectedNestCount = objects.Skip(GroupWidths.Take(4).Sum()).Zip(bits.Skip(GroupWidths.Take(4).Sum()),
            (target, selected) => target && selected).Count(value => value);
        Require(report.selectedNestCount == GroupMinimums[4],
                "Native stageRng source choice did not select the source-authored 12-nest cohort");
        controllerSpawnAttempted = true;
        try
        {
            NetworkServer.Spawn(controllerObject);
        }
        finally
        {
            CaptureControllerRegistration();
        }
        Require(controllerSpawnOwned && controllerIdentity.isServer && controllerNetworkId.Value != 0 &&
                    ReferenceEquals(NetworkServer.FindLocalObject(controllerNetworkId), controllerObject),
                "Source ID-11 controller failed exact server registration");
        activated = true;
        report.controllerSpawned = true;
        report.controllerNetworkId = controllerNetworkId.Value;
        report.status = "source-controller-owned-before-run-stage-callback";
    }

    public void DispatchAfterNativeRunCallback(Stage stage)
    {
        Require(activated && !globalDispatched && NetworkServer.active && Run.instance && stage &&
                    ReferenceEquals(Stage.instance, stage) && stage.isServer && stage.gameObject.scene == scene &&
                    stage.netId.Value != 0 && ReferenceEquals(NetworkServer.FindLocalObject(stage.netId), stage.gameObject),
                "Full native scene-changed multicast requires the exact newly spawned server Stage after the single Run callback");
        if (!ReferenceEquals(GlobalHandlers.GetValue(null), globalHandlersBefore))
            throw Refuse("Complete native scene-changed multicast changed during Run stage creation");
        dispatchedHandlers = ValidateFullNativeMulticast();
        if (!ReferenceEquals(dispatchedHandlers, globalHandlersBefore))
            throw Refuse("Validated native multicast instance differs from the preflight invocation list");
        CaptureExpectedToggleOutput();
        globalDispatchAttempted = true;
        try
        {
            // Preserve native stock order: Run.OnServerSceneChanged has just
            // returned; dispatch the entire unchanged global multicast once.
            dispatchedHandlers.DynamicInvoke(scene.name);
        }
        catch (TargetInvocationException error)
        {
            report.status = "native-global-multicast-threw";
            report.error = error.InnerException == null ? error.ToString() : error.InnerException.ToString();
            throw Refuse("Complete native scene-changed multicast threw: " + report.error);
        }
        globalDispatched = true;
        report.fullMulticastDispatched = true;
        report.multicastSubscriberCount = dispatchedHandlers.GetInvocationList().Length;
        VerifyNativeToggleApplication();
        foreach (var target in toggleTargetStates)
            if (target.identity)
                Require(IsRegistered(target.identity) == target.registeredBefore,
                        "Native toggle changed registration of a source target identity");
        VerifyOwnedDirectorIdentityState();
        foreach (var state in foreignSourceIdentities)
            Require(state.identity && state.identity.gameObject.activeSelf == state.activeSelf && !IsRegistered(state.identity),
                    "Complete native source toggle multicast changed a foreign scene identity (including ID 10/disabled MapZones)");
        RequireQueueEmpty(ToggleQueueField, "SceneObjectToggleGroup");
        RequireQueueEmpty(SpawnQueueField, "SceneObjectSpawnGroup");
        report.nativeToggleQueueDrained = true;
        report.nativeSpawnQueueDrained = true;
        report.status = "full-multicast-dispatched; awaiting-natural-spawner-start";
    }

    public void CompleteAfterNaturalSpawnerStart()
    {
        Require(globalDispatched && activated && !complete && NetworkServer.active && Stage.instance &&
                    SceneManager.GetActiveScene() == scene,
                "Siren source-entry completion is out of order or lost its native stage/server context");
        var bits = ToggleActivationsField.GetValue(controller) as bool[];
        var objects = ToggleObjectsField.GetValue(controller) as GameObject[];
        Require(bits != null && objects != null && bits.Length == objects.Length,
                "Native toggle choice arrays disappeared before source spawner Start callbacks");
        for (int i = 0; i < sourceEggs.Count; i++)
        {
            var source = sourceEggs[i];
            int index = GroupWidths.Take(4).Sum() + i;
            source.selected = bits[index];
            if (source.selected && (!source.observed || !source.identity || source.networkId.Value == 0))
                throw Refuse("Selected native egg spawner did not synchronously yield an exact networked egg at index " + i);
            if (source.selected && !IsEggAtCapturedSpawnPose(source))
                throw Refuse("Captured original egg moved from its exact serialized source-spawner pose before ID-10 admission");
            if (!source.selected && source.observed)
                throw Refuse("Unselected native egg spawner produced an egg at index " + i);
            if (source.selected && source.spawner.activeSelf)
                throw Refuse("Selected source spawner Start did not deactivate its original spawner GameObject");
        }
        var selected = sourceEggs.Where(row => row.selected).ToArray();
        if (!SirenSourceEntryContract.IsExactBijection(sourceEggs.Select(row => row.spawner).ToArray(),
                selected.Select(row => row.spawner).ToArray(), selected.Select(row => row.identity.gameObject).ToArray(),
                selected.Select(row => row.networkId.Value).ToArray(), selected.Select(row => row.observed).ToArray(),
                GroupMinimums[4]))
            throw Refuse("Natural source-spawner/egg map is not a one-to-one identity bijection");
        foreach (var row in selected)
        {
            if (!row.identity || !row.identity.isServer || row.identity.netId != row.networkId ||
                !ReferenceEquals(NetworkServer.FindLocalObject(row.networkId), row.body) || row.body.scene != scene ||
                !row.identity.assetId.Equals(eggAssetId))
                throw Refuse("Captured original egg identity/server-map membership changed before ID-10 admission");
        }
        VerifyNoUntrackedSourceEggs();
        RequireQueueEmpty(ToggleQueueField, "SceneObjectToggleGroup");
        RequireQueueEmpty(SpawnQueueField, "SceneObjectSpawnGroup");
        report.exactEggBijection = true;
        report.mappedEggCount = selected.Length;
        report.mappedEggNetworkIds = selected.Select(row => row.networkId.Value).ToArray();
        report.mappedSpawnerInstanceIds = selected.Select(row => row.spawner.GetInstanceID()).ToArray();
        complete = true;
        report.status = "source-egg-bijection-proven-before-id-10-admission";
    }

    void VerifyNoUntrackedSourceEggs()
    {
        var expected = sourceEggs.Where(row => row.selected && row.observed && !row.retired)
            .Select(row => row.body).ToArray();
        var identities = NetworkServer.objects.Values
            .Concat(scene.GetRootGameObjects().Where(root => root).SelectMany(root => root.GetComponentsInChildren<NetworkIdentity>(true)))
            .Where(identity => identity && identity.gameObject.scene == scene && identity.assetId.Equals(eggAssetId) &&
                sourceEggs.Any(row => (identity.transform.position - row.expectedPosition).sqrMagnitude <= 1e-8f &&
                    Quaternion.Angle(identity.transform.rotation, row.expectedRotation) <= 0.01f))
            .Select(identity => identity.gameObject).Distinct().ToArray();
        if (identities.Length != expected.Length || expected.Any(body => !body || !identities.Any(actual => ReferenceEquals(actual, body))))
            throw new InvalidOperationException("Source egg census found an unowned or missing network egg at an authored nest pose");
    }

    void CaptureEggAtSpawnerDisable(GameObject spawner)
    {
        if (cleanupStarted || !globalDispatchAttempted)
            return;
        var row = sourceEggs.SingleOrDefault(candidate => ReferenceEquals(candidate.spawner, spawner));
        if (row == null)
        {
            captureFailure = true;
            report.error = "Witness callback came from an unowned source spawner";
            return;
        }
        if (row.observed)
        {
            captureFailure = true;
            report.error = "Source spawner witness fired more than once";
            return;
        }
        try
        {
            var candidates = NetworkServer.objects.Values
                .Where(identity => identity && identity.netId.Value != 0 && !networkIdsBefore.Contains(identity.netId.Value) &&
                                   !sourceEggs.Any(other => other.observed && other.networkId == identity.netId) &&
                                   identity.gameObject.scene == scene && identity.assetId.Equals(eggAssetId) &&
                                   (identity.transform.position - row.expectedPosition).sqrMagnitude <= 1e-8f &&
                                   Quaternion.Angle(identity.transform.rotation, row.expectedRotation) <= 0.01f)
                .ToArray();
            if (candidates.Length != 1)
            {
                captureFailure = true;
                report.error = "Spawner disable did not identify exactly one newly networked original egg at its source pose; candidates=" +
                               candidates.Length;
                return;
            }
            var identity = candidates[0];
            var serverMap = NetworkServer.FindLocalObject(identity.netId);
            if (!ReferenceEquals(serverMap, identity.gameObject) || identity.netId.Value == 0 || !identity.isServer)
            {
                captureFailure = true;
                report.error = "New egg identity lacks exact server map membership at the source spawner disable callback";
                return;
            }
            row.identity = identity;
            row.body = identity.gameObject;
            row.networkId = identity.netId;
            row.observed = true;
            report.observedSpawnerDisableCount++;
        }
        catch (Exception error)
        {
            captureFailure = true;
            report.error = error.ToString();
        }
    }

    void CaptureControllerRegistration()
    {
        if (!controllerIdentity || controllerIdentity.netId.Value == 0 || !controllerIdentity.isServer)
            return;
        controllerNetworkId = controllerIdentity.netId;
        controllerSpawnOwned = ReferenceEquals(NetworkServer.FindLocalObject(controllerNetworkId), controllerObject);
    }

    void CaptureExpectedToggleOutput()
    {
        var bits = ToggleActivationsField.GetValue(controller) as bool[];
        Require(bits != null && bits.Length == toggleTargetStates.Count,
                "Native toggle choices are not ready before full scene callback");
        int eggOffset = GroupWidths.Take(4).Sum();
        for (int index = 0; index < bits.Length; index++)
        {
            toggleTargetStates[index].expectedActive = bits[index];
            toggleTargetStates[index].expectedKnown = true;
            if (index >= eggOffset)
                sourceEggs[index - eggOffset].selected = bits[index];
        }
    }

    void RestoreToggleTargetStates()
    {
        int restoredCount = 0;
        foreach (var state in toggleTargetStates)
        {
            if (!SirenSourceEntryContract.MatchesCapturedObjectPresence(
                    state.targetWasNull, ReferenceEquals(state.target, null), state.target))
                throw new InvalidOperationException("Captured native toggle target was destroyed or changed nullness; retaining source context");
            if (state.targetWasNull)
            {
                if (!state.identityWasNull || !ReferenceEquals(state.identity, null))
                    throw new InvalidOperationException("Null native toggle slot has an inconsistent captured identity; retaining source context");
                restoredCount++;
                continue;
            }
            if (!SirenSourceEntryContract.MatchesCapturedObjectPresence(
                    state.identityWasNull, ReferenceEquals(state.identity, null), state.identity))
                throw new InvalidOperationException("Captured native toggle identity was destroyed or changed nullness; retaining source context");
            var currentIdentity = state.target.GetComponent<NetworkIdentity>();
            if (!ReferenceEquals(currentIdentity, state.identity))
                throw new InvalidOperationException("Native toggle target identity component changed; retaining source context");
            bool expected = state.expectedKnown ? state.expectedActive : state.activeBefore;
            if (!SirenSourceEntryContract.MayRestoreToggleTarget(
                    state.activeBefore, state.target.activeSelf, expected, globalDispatchAttempted, state.expectedKnown))
                throw new InvalidOperationException("Native toggle target changed outside its captured source choice; retaining source context");
            if (!state.identityWasNull && IsRegistered(state.identity) != state.registeredBefore)
                throw new InvalidOperationException("Native toggle target network registration changed; retaining source context");
            if (state.target.activeSelf == state.activeBefore)
            {
                restoredCount++;
                continue;
            }
            if (!globalDispatchAttempted || !state.expectedKnown || state.target.activeSelf != expected)
                throw new InvalidOperationException("Cannot attribute source toggle target active-state change to the owned native multicast");
            state.target.SetActive(state.activeBefore);
            if (state.target.activeSelf != state.activeBefore)
                throw new InvalidOperationException("Exact source toggle target active state did not restore");
            restoredCount++;
        }
        report.nativeToggleTargetCount = restoredCount;
        report.nativeToggleTargetsRestored = restoredCount == toggleTargetStates.Count;
    }

    void VerifyNativeToggleApplication()
    {
        var bits = ToggleActivationsField.GetValue(controller) as bool[];
        var objects = ToggleObjectsField.GetValue(controller) as GameObject[];
        Require(bits != null && objects != null && bits.Length == objects.Length && bits.Length == GroupWidths.Sum(),
                "Native SceneObjectToggleGroup.ApplyActivations output dimensions changed");
        int eggOffset = GroupWidths.Take(4).Sum();
        for (int i = 0; i < sourceEggs.Count; i++)
            sourceEggs[i].selected = bits[eggOffset + i];
        var groups = controller.toggleGroups;
        int start = 0;
        int enabledEggs = 0;
        for (int group = 0; group < groups.Length; group++)
        {
            var source = groups[group];
            int selectedCount = 0;
            for (int i = 0; i < source.objects.Length; i++)
            {
                var target = source.objects[i];
                Require(ReferenceEquals(objects[start + i], target), "Native toggle object flattening differs from serialized group order");
                if (target && bits[start + i])
                {
                    selectedCount++;
                    Require(target.activeSelf, "Native original toggle handler did not activate a selected source target before frame yield");
                }
                else if (target)
                    Require(!target.activeSelf, "Native original toggle handler changed an unselected source target");
            }
            Require(selectedCount >= GroupMinimums[group] && selectedCount <= GroupMaximums[group],
                    "Native RNG-selected source group count violates its serialized range");
            if (group == 4)
                enabledEggs = selectedCount;
            start += source.objects.Length;
        }
        Require(enabledEggs == 12, "Native fixed-count Siren source egg cohort changed from 12");
    }

    static Delegate ValidateFullNativeMulticast()
    {
        var handlers = GlobalHandlers.GetValue(null) as Delegate;
        Require(handlers != null, "Complete native scene-changed multicast is unavailable");
        int toggles = 0, spawns = 0;
        foreach (var callback in handlers.GetInvocationList())
        {
            if (callback.Target == null && callback.Method == ToggleDrain)
                toggles++;
            else if (callback.Target == null && callback.Method == SpawnDrain)
                spawns++;
            else
                throw Refuse("Unsupported native scene-changed subscriber prevents safe full multicast: " +
                             callback.Method.DeclaringType.FullName + "." + callback.Method.Name);
        }
        Require(toggles == 1 && spawns == 1, "Full native multicast must include exactly one toggle and one spawn queue owner");
        return handlers;
    }

    static void ValidateToggleGroups(SceneObjectToggleGroup toggle, JArray expectedGroups)
    {
        Require(expectedGroups != null && expectedGroups.Count == GroupWidths.Length && toggle.toggleGroups != null &&
                    toggle.toggleGroups.Length == GroupWidths.Length, "Source must contain exactly five serialized native toggle groups");
        for (int group = 0; group < GroupWidths.Length; group++)
        {
            var expected = (JObject)expectedGroups[group];
            var targets = expected["objects"] as JArray;
            var actual = toggle.toggleGroups[group];
            Require(actual.objects != null && targets != null && actual.objects.Length == GroupWidths[group] &&
                        targets.Count == GroupWidths[group] && actual.minEnabled == GroupMinimums[group] &&
                        actual.maxEnabled == GroupMaximums[group] && (int)expected["min_enabled"] == GroupMinimums[group] &&
                        (int)expected["max_enabled"] == GroupMaximums[group],
                    "Source toggle group width/range differs from its authored Siren contract at index " + group);
            for (int slot = 0; slot < GroupWidths[group]; slot++)
            {
                var row = (JObject)targets[slot];
                var resolved = (int)row["source_game_object_file_id"] == 0
                                   ? null : ResolveTransformPath(toggle.gameObject.scene, row["transform_path"] as JArray);
                Require(ReferenceEquals(actual.objects[slot], resolved),
                        "Toggle target differs from receipt-bound serialized source reference at " + group + "/" + slot);
            }
        }
    }

    static GameObject ResolveTransformPath(Scene scene, JArray path)
    {
        Require(path != null && path.Count > 0, "Receipt-bound source transform path is empty");
        var root = (JObject)path[0];
        var rootName = (string)root["name"];
        var namedRoots = scene.GetRootGameObjects().Where(candidate => candidate && candidate.name == rootName).ToArray();
        Require((bool?)root["root"] == true && (int?)root["same_name_root_count"] == namedRoots.Length &&
                    (int?)root["same_name_same_shape_count"] == 1 && IsSha256((string)root["root_shape_sha256"]),
                "Receipt-bound root name/shape cohort is ambiguous or changed");
        var matches = namedRoots.Where(candidate => ShapeHash(candidate.transform) == (string)root["root_shape_sha256"]).ToArray();
        Require(matches.Length == 1, "Receipt-bound transform root shape is absent or ambiguous");
        var current = matches[0].transform;
        for (int index = 1; index < path.Count; index++)
        {
            var segment = (JObject)path[index];
            int childIndex = (int)segment["index"];
            Require((bool?)segment["root"] == false && (int?)segment["sibling_count"] == current.childCount &&
                        childIndex >= 0 && childIndex < current.childCount,
                    "Receipt-bound transform child ordering/count changed at segment " + index);
            current = current.GetChild(childIndex);
            Require(current.name == (string)segment["name"], "Receipt-bound transform child name changed at segment " + index);
        }
        return current.gameObject;
    }

    static string ShapeHash(Transform root)
    {
        var text = new System.Text.StringBuilder();
        AppendShape(root, text);
        using (var sha = System.Security.Cryptography.SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.ASCII.GetBytes(text.ToString())))
                .Replace("-", "").ToLowerInvariant();
    }

    static void AppendShape(Transform node, System.Text.StringBuilder text)
    {
        text.Append(Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(node.name))).Append('|')
            .Append(node.childCount).Append('[');
        for (int index = 0; index < node.childCount; index++)
            AppendShape(node.GetChild(index), text);
        text.Append(']');
    }

    static bool IsRegistered(NetworkIdentity identity)
    {
        if (!identity)
            return false;
        return identity.isServer || identity.netId.Value != 0 && !ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), null);
    }

    static object[] QueueItems(FieldInfo field)
    {
        var enumerable = field == null ? null : field.GetValue(null) as IEnumerable;
        return enumerable == null ? Array.Empty<object>() : enumerable.Cast<object>().ToArray();
    }

    static void RequireQueueEmpty(FieldInfo field, string label)
    {
        var queue = QueueItems(field);
        Require(field != null && queue.Length == 0, label + " native queue is not empty before/after owned dispatch");
    }

    static bool IsSha256(string value) => value != null && value.Length == 64 &&
        value.All(character => character >= '0' && character <= '9' || character >= 'a' && character <= 'f');

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw Refuse(message);
    }

    static InvalidOperationException Refuse(string message) => new InvalidOperationException("Siren source-entry refused: " + message);

    public void Dispose()
    {
        if (disposed)
            return;
        cleanupStarted = true;
        Exception stepFailure;
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 0, RetireOwnedEggs,
                                                           ref cleanupFirstFailure, out stepFailure))
            throw CleanupFailure(stepFailure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 1, RemoveWitnesses,
                                                           ref cleanupFirstFailure, out stepFailure))
            throw CleanupFailure(stepFailure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 2, RestoreToggleTargetStates,
                                                           ref cleanupFirstFailure, out stepFailure))
            throw CleanupFailure(stepFailure);
        if (!SirenEncounterContract.TryAdvanceCleanupStep(ref cleanupStep, 3, UnSpawnController,
                                                           ref cleanupFirstFailure, out stepFailure))
            throw CleanupFailure(stepFailure);
        if (!SirenEncounterContract.TryAdvanceOwnedCleanupStep(ref cleanupStep, 4, controllerActiveMutationOwned,
                RestoreControllerActiveState, ref cleanupFirstFailure, out stepFailure))
            throw CleanupFailure(stepFailure);
        disposed = true;
        report.cleanupDisposed = true;
        report.status = "source-eggs-and-id-11-cleaned";
    }

    void RetireOwnedEggs()
    {
        if (!globalDispatchAttempted)
            return;
        bool capturedEggsUnmoved = SirenSourceEntryContract.PendingEggRowsAtCapturedPose(
            sourceEggs, row => row.selected, row => row.observed, row => row.retired, IsEggAtCapturedSpawnPose);
        if (!SirenSourceEntryContract.MayRetireSourceEggs(globalDispatchAttempted,
                complete && report.exactEggBijection, captureFailure, capturedEggsUnmoved))
            throw new InvalidOperationException("Native source egg cohort is incomplete, ambiguous, or moved; retaining source context");
        if (!NetworkServer.active)
            throw new InvalidOperationException("Cannot retire exact Siren source eggs while server is inactive");
        if (sourceEggs.Any(row => row.observed && !row.selected))
            throw new InvalidOperationException("An unselected source spawner produced a captured egg; retaining source context");
        VerifyNoUntrackedSourceEggs();
        SirenSourceEntryContract.RetirePendingEggRows(sourceEggs,
            row => row.selected, row => row.observed, row => row.retired, IsEggAtCapturedSpawnPose,
            row => {
                if (!row.body || !row.identity || row.networkId.Value == 0 || row.identity.netId != row.networkId ||
                    !row.identity.isServer || !ReferenceEquals(NetworkServer.FindLocalObject(row.networkId), row.body))
                    throw new InvalidOperationException("Exact captured egg identity/map changed before cleanup; retaining source context");
            },
            row => {
                NetworkServer.UnSpawn(row.body);
                if (!ReferenceEquals(NetworkServer.FindLocalObject(row.networkId), null))
                    throw new InvalidOperationException("Captured egg network ID remains mapped after UnSpawn");
                UnityEngine.Object.DestroyImmediate(row.body);
                if (row.body)
                    throw new InvalidOperationException("Exact captured egg root did not synchronously retire");
                row.retired = true;
                report.retiredEggCount++;
            });
    }

    void RemoveWitnesses()
    {
        foreach (var row in sourceEggs)
        {
            if (row.witness)
                UnityEngine.Object.DestroyImmediate(row.witness);
            row.witness = null;
        }
    }

    void UnSpawnController()
    {
        if (!controllerSpawnAttempted)
            return;
        RequireQueueEmpty(ToggleQueueField, "SceneObjectToggleGroup");
        RequireQueueEmpty(SpawnQueueField, "SceneObjectSpawnGroup");
        if (controllerNetworkId.Value == 0)
        {
            if (controllerIdentity && controllerIdentity.netId.Value == 0 && !controllerIdentity.isServer &&
                !NetworkServer.objects.Values.Any(identity => identity && ReferenceEquals(identity.gameObject, controllerObject)))
            {
                report.controllerUnspawned = true;
                return;
            }
            throw new InvalidOperationException("Partially registered ID-11 controller has no exact owned network ID for retry cleanup");
        }
        if (!controller || !controllerIdentity || controllerNetworkId.Value == 0)
            throw new InvalidOperationException("Cannot verify the partially spawned exact source controller during retry cleanup");
        var current = NetworkServer.FindLocalObject(controllerNetworkId);
        if (ReferenceEquals(current, controllerObject))
        {
            if (!NetworkServer.active || controllerIdentity.netId != controllerNetworkId)
                throw new InvalidOperationException("Owned source controller server/network ID changed before UnSpawn");
            NetworkServer.UnSpawn(controllerObject);
        }
        if (!ReferenceEquals(NetworkServer.FindLocalObject(controllerNetworkId), null))
            throw new InvalidOperationException("Source controller network ID remains mapped after UnSpawn");
        if (controllerIdentity.netId == controllerNetworkId)
            ResetIdentity.Invoke(controllerIdentity, null);
        if (controllerIdentity.netId.Value != 0 || controllerIdentity.isServer || controllerIdentity.isClient)
            throw new InvalidOperationException("Source controller identity did not reset after UnSpawn");
        controllerSpawnOwned = false;
        report.controllerUnspawned = true;
    }

    void RestoreControllerActiveState()
    {
        if (!controllerObject)
            throw new InvalidOperationException("Exact ID-11 source object disappeared before active-state restoration");
        controllerObject.SetActive(false);
        if (controllerObject.activeSelf)
            throw new InvalidOperationException("Original inactive ID-11 source state did not restore");
        controllerActiveMutationOwned = false;
        report.controllerOriginalInactiveRestored = true;
    }

    Exception CleanupFailure(Exception failure)
    {
        report.cleanupError = failure.GetType().Name + ": " + failure.Message;
        return failure;
    }

    internal void CaptureSpawnerDisable(GameObject spawner) => CaptureEggAtSpawnerDisable(spawner);

    static bool IsEggAtCapturedSpawnPose(SourceEgg row)
    {
        return row != null && row.identity &&
               (row.identity.transform.position - row.expectedPosition).sqrMagnitude <= 1e-8f &&
               Quaternion.Angle(row.identity.transform.rotation, row.expectedRotation) <= 0.01f;
    }
}

/// <summary>Transient witness attached only to receipt-bound source spawners.</summary>
public sealed class SirenSourceEntrySpawnWitness : MonoBehaviour
{
    SirenSourceEntrySession owner;
    GameObject source;

    internal void Bind(SirenSourceEntrySession entryOwner, GameObject exactSource)
    {
        owner = entryOwner;
        source = exactSource;
    }

    void OnDisable()
    {
        if (owner != null && source)
            owner.CaptureSpawnerDisable(source);
    }
}

public static class SirenSourceEntryContract
{
    internal static bool MatchesOwnedSourceDirectorState(object capturedRoot, object currentRoot, object capturedIdentity,
                                                         object currentIdentity, bool activeSelf, bool expectedActiveSelf, bool registered)
    {
        return !ReferenceEquals(capturedRoot, null) && ReferenceEquals(capturedRoot, currentRoot) &&
               !ReferenceEquals(capturedIdentity, null) && ReferenceEquals(capturedIdentity, currentIdentity) &&
               activeSelf == expectedActiveSelf && !registered;
    }

    public static bool IsExactBijection<TSpawner, TEgg>(IList<TSpawner> allSpawners, IList<TSpawner> selectedSpawners,
                                                        IList<TEgg> eggRoots, IList<uint> networkIds, IList<bool> observed,
                                                        int expectedCount)
    {
        if (allSpawners == null || selectedSpawners == null || eggRoots == null || networkIds == null || observed == null ||
            expectedCount <= 0 || selectedSpawners.Count != expectedCount || selectedSpawners.Count != eggRoots.Count || eggRoots.Count != networkIds.Count ||
            networkIds.Count != observed.Count || allSpawners.Distinct().Count() != allSpawners.Count ||
            selectedSpawners.Distinct().Count() != selectedSpawners.Count || eggRoots.Distinct().Count() != eggRoots.Count ||
            networkIds.Any(id => id == 0) || networkIds.Distinct().Count() != networkIds.Count || observed.Any(value => !value))
            return false;
        return selectedSpawners.All(spawner => allSpawners.Contains(spawner));
    }

    // Scene is a Unity value type: compare its scene identity by value, never by boxing/reference identity.
    public static bool IsSameScene<TScene>(TScene actual, TScene expected) where TScene : struct
    {
        return actual.Equals(expected);
    }

    public static bool MatchesCapturedObjectPresence(bool wasNull, bool referenceIsNull, bool unityAlive)
    {
        return wasNull ? referenceIsNull : !referenceIsNull && unityAlive;
    }

    public static bool PendingEggRowsAtCapturedPose<T>(IEnumerable<T> rows,
            Func<T, bool> selected, Func<T, bool> observed, Func<T, bool> retired, Func<T, bool> atCapturedPose)
    {
        if (rows == null || selected == null || observed == null || retired == null || atCapturedPose == null)
            return false;
        return rows.Where(row => selected(row) && observed(row) && !retired(row)).All(atCapturedPose);
    }

    public static void RetirePendingEggRows<T>(IEnumerable<T> rows,
            Func<T, bool> selected, Func<T, bool> observed, Func<T, bool> retired, Func<T, bool> atCapturedPose,
            Action<T> validateRetirement, Action<T> retire)
    {
        if (rows == null || selected == null || observed == null || retired == null || atCapturedPose == null ||
            validateRetirement == null || retire == null)
            throw new ArgumentNullException("Source egg retirement callbacks must be complete");
        var pending = rows.Where(row => selected(row) && observed(row) && !retired(row)).Reverse().ToArray();
        if (pending.Any(row => !atCapturedPose(row)))
            throw new InvalidOperationException("Unretired captured source egg moved from its source pose; retaining source context");
        foreach (var row in pending)
            validateRetirement(row);
        foreach (var row in pending)
            retire(row);
    }

    public static bool MayRestoreToggleTarget(bool activeBefore, bool activeNow, bool expectedActive,
                                             bool dispatchAttempted, bool expectedKnown)
    {
        return activeNow == activeBefore || dispatchAttempted && expectedKnown && activeNow == expectedActive;
    }

    public static bool MayAdmitEncounter(bool sourceBijection, bool toggleQueueEmpty, bool spawnQueueEmpty,
                                         bool originalEncounterInactive, bool diagnosticEggInputOff)
    {
        return sourceBijection && toggleQueueEmpty && spawnQueueEmpty && originalEncounterInactive && diagnosticEggInputOff;
    }

    public static bool MayRetireSourceEggs(bool globalDispatchAttempted, bool exactSourceBijection,
                                           bool captureAmbiguous, bool capturedEggsUnmoved)
    {
        return !globalDispatchAttempted || exactSourceBijection && !captureAmbiguous && capturedEggsUnmoved;
    }
}


public static class SirenSourceEntryFailureClassification
{
    public static string FailureMessage(bool registrationObserved, bool cleanupObserved)
    {
        if (!registrationObserved)
            return "Siren source-entry registration was not observed; exact owner cleanup was not evaluated";
        return cleanupObserved ? null : "Siren source-entry registration was observed but exact owner cleanup was not";
    }

    public static string FailurePhase(bool registrationObserved, bool cleanupObserved)
    {
        if (!registrationObserved)
            return "siren-source-entry-registration";
        return cleanupObserved ? null : "siren-source-entry-cleanup";
    }

    public static bool PreserveFirstFailure(ref string currentMessage, ref string currentPhase, string message, string phase)
    {
        if (!string.IsNullOrEmpty(currentMessage))
            return false;
        currentMessage = message;
        currentPhase = phase;
        return true;
    }
}

/// <summary>Pure report gate shared by the automatic runner and host assessor.</summary>
public static class SirenSourceEntryRuntimeContract
{
    public static bool SourceEntryAndEncounterCleanupObserved(PortSession.StageProgressReport progress)
    {
        if (progress == null || progress.sirenSourceEntries == null || progress.sirenEncounters == null)
            return false;
        var source = progress.sirenSourceEntries.LastOrDefault();
        var encounter = progress.sirenEncounters.LastOrDefault();
        return source != null && encounter != null && source.cleanupDisposed && source.retiredEggCount == 12 &&
            source.controllerUnspawned && source.controllerOriginalInactiveRestored && source.nativeToggleTargetsRestored &&
            source.nativeToggleTargetCount == 42 && string.IsNullOrEmpty(source.cleanupError) &&
            encounter.cleanupDisposed && encounter.networkObjectUnspawned && encounter.originalActiveRestored &&
            string.IsNullOrEmpty(encounter.cleanupError);
    }

    public static bool NativeListeningRegistrationMatchesSourceEntry(PortSession.StageProgressReport progress)
    {
        if (progress == null || progress.sirenSourceEntries == null || progress.sirenEncounters == null)
            return false;
        var source = progress.sirenSourceEntries.LastOrDefault();
        var encounter = progress.sirenEncounters.LastOrDefault();
        if (source == null || encounter == null || !source.selected ||
            source.status != "source-egg-bijection-proven-before-id-10-admission" ||
            !source.fullMulticastDispatched || !source.nativeToggleQueueDrained || !source.nativeSpawnQueueDrained ||
            !source.exactEggBijection || !source.nativeAwakeObserved || !source.controllerSpawned ||
            source.sourceEggSpawnerCount != 32 || source.selectedNestCount != 12 || source.observedSpawnerDisableCount != 12 ||
            source.mappedEggCount != 12 || source.multicastSubscriberCount <= 0 || source.mappedEggNetworkIds == null ||
            source.mappedEggNetworkIds.Length != 12 || source.mappedEggNetworkIds.Any(id => id == 0) ||
            source.mappedEggNetworkIds.Distinct().Count() != 12 || source.controllerSceneId != 11 ||
            source.controllerNetworkId == 0 || encounter.scene != SirenEncounterContract.SceneName ||
            encounter.identitySceneId != SirenEncounterContract.EncounterSceneId || encounter.networkId == 0 ||
            !encounter.sourceOwnerAttached || !encounter.listenerStateActive ||
            !encounter.nativeEggRegistrationObserved || !encounter.nativeEggRegistrationMatchesSourceEntry ||
            encounter.nativeEggSlotsRegistered != 12 || encounter.sourceEntryEggNetworkIds == null ||
            encounter.nativeRegisteredEggNetworkIds == null || encounter.sourceEntryEggNetworkIds.Length != 12 ||
            encounter.nativeRegisteredEggNetworkIds.Length != 12 ||
            encounter.sourceEntryEggNetworkIds.Any(id => id == 0) || encounter.nativeRegisteredEggNetworkIds.Any(id => id == 0))
            return false;
        var ids = source.mappedEggNetworkIds.ToHashSet();
        return ids.SetEquals(encounter.sourceEntryEggNetworkIds) && ids.SetEquals(encounter.nativeRegisteredEggNetworkIds);
    }
}
