// Source scene identity transaction. Refuse ambiguous native queues or ownership
// and retain the exact recovery context until owned teardown succeeds.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

namespace LabPort.SourceStageLifecycle
{
internal interface ISourceStageIdentityOwners
{
    // StageRngReady must be backed by the existing Run.Start/Run.AdvanceStage
    // path; it must not read nextUlong or manufacture a replacement RNG.
    bool StageRngReady { get; }
    // These owner calls must either return an owned object or roll back their own
    // partial setup before throwing; abort callbacks must be safe and idempotent.
    // StageGeometrySession owns this source context. First-stage EnemySpine and
    // later-stage transport may already have activated it before this lease is
    // created; require that exact owner rather than invoking Awake twice.
    SceneInfo RequireActiveSceneInfo(Scene scene);
    // Read-only validation used before the temporary Stage is retired. It must
    // verify the exact inactive source root and selected full native deck.
    void PreflightDirectorRoot(Scene scene);
    // Return the exact inactive source root through AutomaticDirectorSession and
    // configure its current stage deck before any root/CombatDirector Awake.
    GameObject PrepareDirectorRoot(Scene scene);
    // Suppress only this owner's two native CombatDirectors while the root is
    // activated/spawned ahead of Run.OnServerSceneChanged; DirectorCore stays on.
    // The bridge must prove disabled MonoBehaviours still receive Awake in the
    // pinned Unity runtime, so native RNG initialization is not skipped.
    void SuspendDirectorBehaviorsForSynchronousActivation(GameObject root);
    void ActivateDirectorForSceneIdentityLifecycle(GameObject root);
    void ValidateDirectorAwakeWhileSuspended(GameObject root);
    void DirectorIdentitySpawned(NetworkIdentity identity);
    void BeginNativeStageBoundary();
    bool CaptureNativeStage(Stage stage);
    void RestoreDirectorBehaviorsAfterServerStageBegin(GameObject root);
    void BeforeDirectorIdentityUnspawn(NetworkIdentity identity);
    // Called after exact identity/queue rollback but before restoring the borrowed
    // SceneDirector's original enabled state under the source root.
    void BeforeDirectorRootRollback(bool nativeQueuesEmpty);
    void RollbackDirectorRoot();
    void RestoreDirectorRoot(GameObject root);
}

internal sealed class SourceStageIdentityLifecycle : IDisposable
{
    sealed class ExpectedIdentity
    {
        public uint sceneId;
        public string name;
        public ExpectedIdentity(uint sceneId, string name)
        {
            this.sceneId = sceneId;
            this.name = name;
        }
    }

    sealed class ExpectedToggleGroup
    {
        public int min, max;
        public string[] names;
        public ExpectedToggleGroup(int min, int max, params string[] names)
        {
            this.min = min;
            this.max = max;
            this.names = names;
        }
    }

    sealed class IdentityState
    {
        public NetworkIdentity identity;
        public bool activeSelf;
        public bool spawned;
        public NetworkInstanceId registeredId;
        public bool hasRegisteredId;
    }

    sealed class ToggleState
    {
        public GameObject target;
        public bool activeSelf;
    }

    static readonly BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;
    static readonly BindingFlags PrivateStatic = BindingFlags.Static | BindingFlags.NonPublic;
    static readonly MethodInfo ResetIdentity = typeof(NetworkIdentity).GetMethod("Reset", PrivateInstance);
    static readonly MethodInfo ForceAuthority =
        typeof(NetworkIdentity).GetMethod("ForceAuthority", PrivateInstance, null, new[] { typeof(bool) }, null);
    static readonly MethodInfo DrainNativeToggleQueue = typeof(SceneObjectToggleGroup).GetMethod("OnServerSceneChanged", PrivateStatic);
    static readonly FieldInfo ToggleQueueField = typeof(SceneObjectToggleGroup).GetField("activationsQueue", PrivateStatic);
    static readonly Type SpawnGroupType = AppDomain.CurrentDomain.GetAssemblies()
                                              .Select(assembly => assembly.GetType("RoR2.SceneObjectSpawnGroup", false))
                                              .FirstOrDefault(type => type != null);
    static readonly FieldInfo SpawnQueueField = SpawnGroupType?.GetField("activationsQueue", PrivateStatic);
    static readonly MethodInfo DrainNativeSpawnQueue = SpawnGroupType?.GetMethod("OnServerSceneChanged", PrivateStatic);
    static readonly Type NetworkManagerSystemType = AppDomain.CurrentDomain.GetAssemblies()
                                                        .Select(assembly => assembly.GetType("RoR2.Networking.NetworkManagerSystem", false))
                                                        .FirstOrDefault(type => type != null);
    static readonly FieldInfo GlobalSceneChangedHandlersField =
        NetworkManagerSystemType?.GetField("onServerSceneChangedGlobal", PrivateStatic);
    static readonly FieldInfo InitializedObjectsField = typeof(SceneObjectToggleGroup).GetField("allToggleableObjects", PrivateInstance);
    static readonly FieldInfo ActivationsField = typeof(SceneObjectToggleGroup).GetField("activations", PrivateInstance);

    static readonly ExpectedIdentity[] GolemplainsIdentities = { new ExpectedIdentity(1, "Director"), new ExpectedIdentity(2, "NewtStatue"),
                                                                 new ExpectedIdentity(3, "NewtStatue"),
                                                                 new ExpectedIdentity(4, "NewtStatue"),
                                                                 new ExpectedIdentity(5, "ToggleGroupController") };

    static readonly ExpectedIdentity[] LakesIdentities = { new ExpectedIdentity(1, "Chest2"),
                                                           new ExpectedIdentity(2, "Director"),
                                                           new ExpectedIdentity(3, "NewtStatueCaveWall"),
                                                           new ExpectedIdentity(4, "NewtStatueShipParts"),
                                                           new ExpectedIdentity(5, "NewtStatueWaterfall"),
                                                           new ExpectedIdentity(6, "Scrapper"),
                                                           new ExpectedIdentity(7, "ToggleGroupController"),
                                                           new ExpectedIdentity(8, "WakeStageEvent") };

    static readonly ExpectedToggleGroup[] GolemplainsGroups = { new ExpectedToggleGroup(1, 1, "NewtStatue", "NewtStatue", "NewtStatue") };

    static readonly ExpectedToggleGroup[] LakesGroups = {
        new ExpectedToggleGroup(1, 2, "TG Island 01", "TG Island 02", "TG Island 03"), new ExpectedToggleGroup(0, 1, "TG NE Cave  01"),
        new ExpectedToggleGroup(1, 1, "TG Cave Wall 01", "NewtStatueCaveWall", "NewtStatueShipParts"),
        new ExpectedToggleGroup(2, 6, "TLArchiBeamA", "TLArchiBeamC", "TLArchiBeamA", "TLArchiBeamC", "TLArchiBeamC", "TLArchiBeamB",
                                "TLArchiBeamA", "TLArchiBeamA", "TLArchiBeamC", "TLArchiCover", "TLArchiRampB", "TLArchiRampB"),
        new ExpectedToggleGroup(1, 1, "Scrapper", "Chest2")
    };

    readonly Scene scene;
    readonly ISourceStageIdentityOwners owners;
    readonly List<IdentityState> identities = new List<IdentityState>();
    readonly List<ToggleState> toggleStates = new List<ToggleState>();
    NetworkIdentity[] nativeSweepOrder = Array.Empty<NetworkIdentity>();
    SceneObjectToggleGroup toggle;
    GameObject directorRoot;
    SceneInfo sourceSceneInfo;
    bool identitiesPrepared;
    bool stageCallbackCompleted;
    bool serverStageBeginObserved;
    bool toggleQueueDispatched;
    bool nativeStageCaptured;
    Stage capturedNativeStage;
    GameObject capturedNativeStageHost;
    NetworkInstanceId capturedNativeStageId;
    bool disposed;

    SourceStageIdentityLifecycle(Scene scene, ISourceStageIdentityOwners owners)
    {
        this.scene = scene;
        this.owners = owners;
    }

    // Construct and retain the owner before mutation. If native Awake queues a group
    // and subsequent validation fails, the caller must keep this handle and the scene
    // alive instead of losing ownership through a throwing factory.
    // Call the read-only preflight while the temporary Stage still exists, before
    // the caller retires it. Create repeats the checks after that retirement.
    public static void PreflightBeforeStageRelease(Scene scene, ISourceStageIdentityOwners owners)
    {
        if (owners == null)
            throw new ArgumentNullException("owners");
        if (!scene.IsValid() || !scene.isLoaded || (scene.name != "golemplains" && scene.name != "lakes") ||
            SceneManager.GetActiveScene() != scene || !NetworkServer.active || !Run.instance || !owners.StageRngReady)
            throw Refuse("preflight requires the active supported source scene, server Run, and initialized native stage RNG");
        var sourceInfo = owners.RequireActiveSceneInfo(scene);
        if (!sourceInfo || SceneInfo.instance != sourceInfo || sourceInfo.gameObject.scene != scene || !ClassicStageInfo.instance ||
            ClassicStageInfo.instance.gameObject.scene != scene)
            throw Refuse("preflight requires the exact StageGeometry-owned SceneInfo/ClassicStageInfo");
        owners.PreflightDirectorRoot(scene);
        if (NetworkManagerSystemType == null || GlobalSceneChangedHandlersField == null || SpawnGroupType == null ||
            DrainNativeSpawnQueue == null)
            throw Refuse("the pinned native scene-changed event contract changed");
        RequireQueueEmpty<SceneObjectToggleGroup>(ToggleQueueField, "SceneObjectToggleGroup");
        RequireSpawnQueueEmpty();
        RequireKnownGlobalSceneChangedSubscribers();
        var probe = new SourceStageIdentityLifecycle(scene, owners);
        probe.ValidateGlobalSceneIdentityCohort(SceneSpec(scene.name).identities);
    }

    public static SourceStageIdentityLifecycle Create(Scene scene, ISourceStageIdentityOwners owners)
    {
        if (owners == null)
            throw new ArgumentNullException("owners");
        if (!scene.IsValid() || !scene.isLoaded || (scene.name != "golemplains" && scene.name != "lakes") ||
            SceneManager.GetActiveScene() != scene)
            throw Refuse("requires the exact active generated Golemplains or Lakes source scene");
        if (!NetworkServer.active || !Run.instance || Stage.instance || !owners.StageRngReady)
            throw Refuse("requires a ready server Run/stage RNG and no previous Stage");
        if (ResetIdentity == null || ForceAuthority == null || DrainNativeToggleQueue == null || ToggleQueueField == null ||
            SpawnQueueField == null || InitializedObjectsField == null || ActivationsField == null)
            throw Refuse("the pinned e544 private lifecycle contract changed");
        if (NetworkManagerSystemType == null || GlobalSceneChangedHandlersField == null || SpawnGroupType == null ||
            DrainNativeSpawnQueue == null)
            throw Refuse("the pinned native scene-changed event contract changed");

        // Repeat preflight after the caller retired the temporary Stage; never
        // clear or drain a static queue to force progress.
        PreflightBeforeStageRelease(scene, owners);
        return new SourceStageIdentityLifecycle(scene, owners);
    }

    public void Prepare()
    {
        if (disposed || sourceSceneInfo || identitiesPrepared)
            throw Refuse("owner setup was already attempted");
        var spec = SceneSpec(scene.name);
        try
        {
            sourceSceneInfo = owners.RequireActiveSceneInfo(scene);
            if (!sourceSceneInfo || SceneInfo.instance != sourceSceneInfo || sourceSceneInfo.gameObject.scene != scene ||
                !ClassicStageInfo.instance || ClassicStageInfo.instance.gameObject.scene != scene)
                throw Refuse("the existing StageGeometry owner does not own the exact active source SceneInfo/ClassicStageInfo");
            ValidateGlobalSceneIdentityCohort(spec.identities);

            directorRoot = owners.PrepareDirectorRoot(scene);
            if (!directorRoot || directorRoot.scene != scene || directorRoot.name != "Director" || directorRoot.activeSelf ||
                directorRoot.GetComponent<NetworkIdentity>() == null)
                throw Refuse("the existing Director owner cannot lend its exact inactive source identity");
            ValidateGlobalSceneIdentityCohort(spec.identities);
            var toggles = scene.GetRootGameObjects()
                              .SelectMany(root => root.GetComponentsInChildren<SceneObjectToggleGroup>(true))
                              .Where(component => component && component.gameObject.scene == scene)
                              .ToArray();
            if (toggles.Length != 1 || toggles[0].gameObject.name != "ToggleGroupController" ||
                toggles[0].GetComponent<NetworkIdentity>() == null ||
                toggles[0].GetComponent<NetworkIdentity>().sceneId.Value != spec.toggleSceneId)
                throw Refuse("the exact source toggle controller identity is missing or ambiguous");
            toggle = toggles[0];
            CaptureIdentityState(spec.identities);
            ValidateToggleGroups(spec.groups);
            CaptureToggleTargets();
            ActivateAndSpawnAll(spec.identities);
            identitiesPrepared = true;
            RequireOwnedToggleQueue();
            RequireSpawnQueueEmpty();
        }
        catch (Exception primary)
        {
            // Native static queues cannot be cleared safely. Try exact owned rollback
            // only when both queues are empty; never replace the setup failure.
            try
            {
                if (sourceSceneInfo && SceneInfo.instance == sourceSceneInfo &&
                    QueueItems<SceneObjectToggleGroup>(ToggleQueueField).Length == 0 && SpawnQueueCount() == 0)
                    AbortBeforeBoundary();
            }
            catch (Exception rollback)
            {
                primary.Data["SourceStageRollbackFailure"] = rollback;
            }
            var secondary = new List<Exception>();
            foreach (string key in new[] { "FirstStageDirectorRollbackFailure", "SourceStageRollbackFailure" })
                if (primary.Data[key] is Exception failure)
                    secondary.Add(failure);
            if (secondary.Count > 0)
                throw new AggregateException("Source-stage setup failed; the original failure is first, followed by rollback failures",
                                             new[] { primary }.Concat(secondary));
            throw;
        }
    }

    public Stage CapturedNativeStage => nativeStageCaptured ? capturedNativeStage : null;
    public GameObject CapturedNativeStageHost => nativeStageCaptured ? capturedNativeStageHost : null;
    public NetworkInstanceId CapturedNativeStageId => capturedNativeStageId;
    public bool HasCapturedNativeStage => nativeStageCaptured;

    public void CompleteAtBeginOriginalStage()
    {
        if (disposed || !identitiesPrepared || stageCallbackCompleted || toggleQueueDispatched || SceneManager.GetActiveScene() != scene ||
            !NetworkServer.active || !Run.instance || !owners.StageRngReady)
            throw Refuse("native stage handoff is out of order or lost its source ownership");
        RequireOwnedToggleQueue();
        RequireSpawnQueueEmpty();
        var nativeHandlers = RequireKnownGlobalSceneChangedSubscribers();

        if (Stage.instance)
            throw Refuse("a Stage appeared before the owned native Run callback");
        owners.BeginNativeStageBoundary();
        try
        {
            Run.instance.OnServerSceneChanged(scene.name); // Exact native callback; creates Stage synchronously.
        }
        finally
        {
            // Run.BeginStage installs Stage.instance before NetworkServer.Spawn.
            // Capture every candidate, including one whose native spawn failed,
            // before any later assertion or callback can throw.
            var candidate = Stage.instance;
            if (candidate)
            {
                bool captured = false;
                try
                {
                    captured = owners.CaptureNativeStage(candidate);
                }
                catch
                {
                    captured = false;
                }
                if (captured)
                {
                    var identity = candidate.GetComponent<NetworkIdentity>();
                    if (identity &&
                        FirstStageDiagnosticGate.HasExactStageCapture(
                            true, ReferenceEquals(Stage.instance, candidate), ReferenceEquals(candidate.gameObject, identity.gameObject),
                            candidate.isServer && identity.isServer, identity.netId.Value, candidate.netId.Value,
                            identity.netId.Value != 0 &&
                                ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), candidate.gameObject)) &&
                        candidate.gameObject.scene == scene)
                    {
                        capturedNativeStage = candidate;
                        capturedNativeStageHost = candidate.gameObject;
                        capturedNativeStageId = identity.netId;
                        nativeStageCaptured = true;
                    }
                }
            }
        }
        if (!nativeStageCaptured || !capturedNativeStage || !capturedNativeStageHost ||
            !ReferenceEquals(Stage.instance, capturedNativeStage) ||
            !ReferenceEquals(capturedNativeStage.gameObject, capturedNativeStageHost) || !capturedNativeStage.isServer ||
            capturedNativeStageId.Value == 0 || capturedNativeStage.netId != capturedNativeStageId ||
            capturedNativeStageHost.scene != scene ||
            !ReferenceEquals(NetworkServer.FindLocalObject(capturedNativeStageId), capturedNativeStageHost))
            throw Refuse("Run did not synchronously create and register the exact owned original Stage");
        stageCallbackCompleted = true;

        // Invoke only the fully validated offline-safe multicast. Validation
        // refuses a present Steamworks subscriber; method-name allowlisting is
        // not proof that its platform initialization path is safe offline.
        var queued = QueueItems<SceneObjectToggleGroup>(ToggleQueueField);
        if (queued.Length != 1 || !ReferenceEquals(queued[0], toggle) || toggle.gameObject.scene != scene)
            throw Refuse("toggle queue ownership changed at the Run/Stage boundary");
        if (!ReferenceEquals(GlobalSceneChangedHandlersField.GetValue(null), nativeHandlers))
            throw Refuse("native scene-changed subscribers changed during Run/Stage creation");
        nativeHandlers.DynamicInvoke(scene.name);
        toggleQueueDispatched = true;
        RequireQueueEmpty<SceneObjectToggleGroup>(ToggleQueueField, "SceneObjectToggleGroup");
        RequireSpawnQueueEmpty();
        VerifyNativeActivationResult(SceneSpec(scene.name).groups);
    }

    // Called by IntegratedStageSession after the genuine server Stage-begin callback
    // fires. This is not evidence that the client-side Start coroutine or
    // onStageStartGlobal completed; offline local-user startup remains unavailable.
    public void ObserveServerStageBegin()
    {
        if (disposed || !stageCallbackCompleted || !toggleQueueDispatched || serverStageBeginObserved ||
            SceneManager.GetActiveScene() != scene || !NetworkServer.active || !Run.instance || !nativeStageCaptured ||
            !ReferenceEquals(Stage.instance, capturedNativeStage) ||
            !ReferenceEquals(capturedNativeStage.gameObject, capturedNativeStageHost) || !capturedNativeStage.isServer ||
            capturedNativeStage.netId != capturedNativeStageId || capturedNativeStageId.Value == 0 ||
            capturedNativeStageHost.scene != scene ||
            !ReferenceEquals(NetworkServer.FindLocalObject(capturedNativeStageId), capturedNativeStageHost))
            throw Refuse("genuine server Stage-begin event was not observed for the exact captured source Stage identity");
        owners.RestoreDirectorBehaviorsAfterServerStageBegin(directorRoot);
        serverStageBeginObserved = true;
    }

    public bool IsSafeToUnload
    {
        get {
            return disposed && !Stage.instance && identities.All(state => !state.spawned) &&
                   QueueItems<SceneObjectToggleGroup>(ToggleQueueField).Length == 0 && SpawnQueueCount() == 0;
        }
    }

    public NetworkIdentity[] OwnedIdentities => identities.Select(state => state.identity).ToArray();
    public uint[] CapturedNativeSceneIdentityOrder => nativeSweepOrder.Select(identity => identity.sceneId.Value).ToArray();
    public bool NativeActivationQueuesEmpty => QueueItems<SceneObjectToggleGroup>(ToggleQueueField).Length == 0 && SpawnQueueCount() == 0;

    // The caller must retain this handle if Prepare throws. This rollback is
    // available only before Run.OnServerSceneChanged and only when both native
    // static queues are empty; a queued group stays owned by the loaded scene.
    public void AbortBeforeBoundary()
    {
        if (disposed)
            return;
        if (stageCallbackCompleted || toggleQueueDispatched)
            throw Refuse("pre-boundary abort is no longer valid");
        if (QueueItems<SceneObjectToggleGroup>(ToggleQueueField).Length != 0 || SpawnQueueCount() != 0)
            throw Refuse("cannot abort while native source-group queues hold objects");
        if (SceneManager.GetActiveScene() != scene)
            throw Refuse("source scene must remain active until pre-boundary rollback completes");
        var directorIdentity = directorRoot ? directorRoot.GetComponent<NetworkIdentity>() : null;
        if (directorIdentity && directorIdentity.isServer)
            owners.BeforeDirectorIdentityUnspawn(directorIdentity);
        RollbackOwnedIdentities();
        foreach (var target in toggleStates)
            if (target.target)
                target.target.SetActive(target.activeSelf);
        RequireQueueEmpty<SceneObjectToggleGroup>(ToggleQueueField, "SceneObjectToggleGroup");
        RequireSpawnQueueEmpty();
        owners.BeforeDirectorRootRollback(NativeActivationQueuesEmpty);
        owners.RollbackDirectorRoot();
        if (SceneInfo.instance != sourceSceneInfo || !ClassicStageInfo.instance || ClassicStageInfo.instance.gameObject.scene != scene)
            throw Refuse("source StageGeometry context changed during pre-boundary rollback");
        disposed = true;
    }

    public void Dispose()
    {
        if (disposed)
            return;
        if (Stage.instance)
            throw Refuse("refusing source identity teardown while the owned objective Stage is still live");
        if (!toggleQueueDispatched || QueueItems<SceneObjectToggleGroup>(ToggleQueueField).Length != 0 || SpawnQueueCount() != 0)
            throw Refuse("refusing teardown/unload while native static source-group queues are pending");
        if (!NetworkServer.active || SceneManager.GetActiveScene() != scene)
            throw Refuse("server must remain active until every owned source identity is unspawned");

        var directorIdentity = directorRoot ? directorRoot.GetComponent<NetworkIdentity>() : null;
        if (directorIdentity && directorIdentity.isServer)
            owners.BeforeDirectorIdentityUnspawn(directorIdentity);
        RollbackOwnedIdentities();
        if (directorRoot)
            owners.RestoreDirectorRoot(directorRoot);
        foreach (var target in toggleStates)
            if (target.target)
                target.target.SetActive(target.activeSelf);
        if (SceneInfo.instance != sourceSceneInfo || !ClassicStageInfo.instance || ClassicStageInfo.instance.gameObject.scene != scene)
            throw Refuse("StageGeometry scene context changed before its owner deactivated it");
        disposed = true;
    }

    void ValidateGlobalSceneIdentityCohort(ExpectedIdentity[] expected)
    {
        var global = Resources.FindObjectsOfTypeAll<NetworkIdentity>()
                         .Where(identity => identity && identity.gameObject.hideFlags != HideFlags.NotEditable &&
                                            identity.gameObject.hideFlags != HideFlags.HideAndDontSave && !identity.sceneId.IsEmpty())
                         .ToArray();
        if (global.Any(identity => !identity.gameObject.scene.IsValid() || !identity.gameObject.scene.isLoaded ||
                                   identity.gameObject.scene != scene))
            throw Refuse("foreign or non-scene NetworkServer.SpawnObjects candidate is present");

        var actual = global.Select(identity => new ExpectedIdentity(identity.sceneId.Value, identity.gameObject.name))
                         .OrderBy(identity => identity.sceneId)
                         .ToArray();
        var wanted = expected.OrderBy(identity => identity.sceneId).ToArray();
        if (actual.Length != wanted.Length ||
            actual.Where((identity, index) => identity.sceneId != wanted[index].sceneId || identity.name != wanted[index].name).Any())
            throw Refuse("complete generated source identity cohort differs from the audited scene manifest");
        if (actual.GroupBy(identity => identity.sceneId).Any(group => group.Count() != 1))
            throw Refuse("duplicate source scene identity value");
        // HLAPI uses the Resources array order in both loops. Keep that exact order:
        // Director Awake and ToggleGroup Generate consume Run.stageRng during activation.
        if (global.Any(IsRegisteredIdentity))
            throw Refuse("source identity cohort contains a pre-registered NetworkIdentity");
        nativeSweepOrder = global;
    }

    void CaptureIdentityState(ExpectedIdentity[] expected)
    {
        identities.Clear();
        var map = nativeSweepOrder;
        if (map.Length != expected.Length)
            throw Refuse("scene-local identity count changed during ownership setup");
        var specs = expected.ToDictionary(spec => spec.sceneId);
        foreach (var identity in map)
        {
            var sceneId = identity.sceneId.Value;
            ExpectedIdentity spec;
            if (!specs.TryGetValue(sceneId, out spec) || identity.gameObject.name != spec.name || identity.gameObject.activeSelf)
                throw Refuse("expected inactive source identity missing/changed: sceneId=" + sceneId + " name=" + identity.gameObject.name);
            if (IsRegisteredIdentity(identity))
                throw Refuse("refusing to Reset a source identity that is already registered: sceneId=" + sceneId);
            identities.Add(new IdentityState { identity = identity, activeSelf = identity.gameObject.activeSelf });
        }
    }

    void ValidateToggleGroups(ExpectedToggleGroup[] expected)
    {
        var groups = toggle.toggleGroups;
        if (groups == null || groups.Length != expected.Length)
            throw Refuse("source toggle group count changed");
        for (int i = 0; i < groups.Length; i++)
        {
            var group = groups[i];
            var contract = expected[i];
            if (group.objects == null || group.minEnabled != contract.min || group.maxEnabled != contract.max ||
                group.objects.Length != contract.names.Length ||
                group.objects.Where((obj, index) => !obj || obj.gameObject.scene != scene || obj.name != contract.names[index]).Any() ||
                group.objects.Distinct().Count() != group.objects.Length)
                throw Refuse("source toggle group serialized refs/ranges changed at index " + i);
        }
    }

    void CaptureToggleTargets()
    {
        foreach (var target in toggle.toggleGroups.SelectMany(group => group.objects))
        {
            if (toggleStates.All(state => !ReferenceEquals(state.target, target)))
                toggleStates.Add(new ToggleState { target = target, activeSelf = target.activeSelf });
        }
    }

    void ActivateAndSpawnAll(ExpectedIdentity[] expected)
    {
        // Match stock's two-pass ordering. Reset all identities before any Awake;
        // then activate the full source cohort before spawning any identity.
        foreach (var state in identities)
            ResetIdentity.Invoke(state.identity, null);
        owners.SuspendDirectorBehaviorsForSynchronousActivation(directorRoot);
        foreach (var state in identities)
        {
            if (state.identity.gameObject == directorRoot)
                owners.ActivateDirectorForSceneIdentityLifecycle(directorRoot);
            else
                state.identity.gameObject.SetActive(true);
        }
        var spec = SceneSpec(scene.name);
        var toggles = scene.GetRootGameObjects()
                          .SelectMany(root => root.GetComponentsInChildren<SceneObjectToggleGroup>(true))
                          .Where(component => component && component.gameObject.scene == scene)
                          .ToArray();
        if (toggles.Length != 1 || !ReferenceEquals(toggles[0], toggle) ||
            toggles[0].GetComponent<NetworkIdentity>().sceneId.Value != spec.toggleSceneId ||
            InitializedObjectsField.GetValue(toggles[0]) == null || ActivationsField.GetValue(toggles[0]) == null)
            throw Refuse("native toggle Awake/Generate did not initialize the audited controller exactly once");
        if (toggles[0].toggleGroups.Sum(group => group.objects.Length) !=
            ((GameObject[])InitializedObjectsField.GetValue(toggles[0])).Length)
            throw Refuse("native toggle Awake array does not match the serialized object references");
        if (!ReferenceEquals(toggles[0], toggle))
            throw Refuse("source toggle controller changed during identity activation");
        owners.ValidateDirectorAwakeWhileSuspended(directorRoot);

        foreach (var state in identities)
        {
            state.spawned = true; // Spawn can throw after partially registering an object.
            try
            {
                NetworkServer.Spawn(state.identity.gameObject);
            }
            finally
            {
                if (state.identity && state.identity.netId.Value != 0 && state.identity.isServer)
                {
                    state.registeredId = state.identity.netId;
                    state.hasRegisteredId = true;
                }
            }
            if (!state.identity.isServer || state.identity.netId.Value == 0)
                throw Refuse("source identity did not register on the local server: " + state.identity.gameObject.name);
            ForceAuthority.Invoke(state.identity, new object[] { true });
            if (state.identity.gameObject == directorRoot)
                owners.DirectorIdentitySpawned(state.identity);
        }
        if (identities.Select(state => state.identity.sceneId.Value).Distinct().Count() != expected.Length)
            throw Refuse("source identity spawn cohort is not unique");
    }

    void RequireOwnedToggleQueue()
    {
        var queued = QueueItems<SceneObjectToggleGroup>(ToggleQueueField);
        if (queued.Length != 1 || !ReferenceEquals(queued[0], toggle) || toggle.gameObject.scene != scene)
            throw Refuse("native toggle queue contains a missing, duplicate, or foreign group");
    }

    void VerifyNativeActivationResult(ExpectedToggleGroup[] expected)
    {
        var nativeGroups = (bool[])ActivationsField.GetValue(toggle);
        var objects = (GameObject[])InitializedObjectsField.GetValue(toggle);
        if (nativeGroups == null || objects == null || nativeGroups.Length != objects.Length ||
            nativeGroups.Length != expected.Sum(group => group.names.Length))
            throw Refuse("native toggle activation result dimensions changed");
        for (int i = 0; i < objects.Length; i++)
            if (!objects[i] || objects[i].activeSelf != nativeGroups[i])
                throw Refuse("original ApplyActivations did not apply its native bit at index " + i);
        // The values are read-only evidence here; no activation bits are authored.
    }

    void RollbackOwnedIdentities()
    {
        foreach (var state in identities.AsEnumerable().Reverse())
        {
            GameObject registeredObject = null;
            if (state.hasRegisteredId)
                registeredObject = NetworkServer.FindLocalObject(state.registeredId);
            if (state.spawned && state.identity && NetworkServer.active && state.identity.isServer)
            {
                if (!state.hasRegisteredId || state.identity.netId != state.registeredId ||
                    !ReferenceEquals(registeredObject, state.identity.gameObject))
                    throw Refuse("owned source identity registration changed before UnSpawn");
                if (state.identity.gameObject == directorRoot)
                    owners.BeforeDirectorIdentityUnspawn(state.identity);
                NetworkServer.UnSpawn(state.identity.gameObject);
                registeredObject = NetworkServer.FindLocalObject(state.registeredId);
            }
            if (state.hasRegisteredId && !ReferenceEquals(registeredObject, null))
                throw Refuse("captured source NetworkInstanceId was re-registered by a foreign object");
            if (state.identity)
            {
                if (state.identity.netId.Value != 0)
                {
                    var currentRegistration = NetworkServer.FindLocalObject(state.identity.netId);
                    if (!ReferenceEquals(currentRegistration, null))
                        throw Refuse("source identity was re-registered under a current or foreign NetworkInstanceId");
                }
                if (state.hasRegisteredId && (state.identity.netId != state.registeredId || state.identity.isServer))
                    ResetIdentity.Invoke(state.identity, null);
                if (state.identity.netId.Value != 0 || state.identity.isServer)
                    throw Refuse("owned source NetworkIdentity.Reset did not clear the unspawned identity");
                if (state.identity.gameObject != directorRoot)
                    state.identity.gameObject.SetActive(state.activeSelf);
            }
            state.spawned = false;
        }
    }

    static bool IsRegisteredIdentity(NetworkIdentity identity)
    {
        if (!identity)
            return false;
        if (identity.isServer)
            return true;
        return identity.netId.Value != 0 && !ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), null);
    }

    static void RequireQueueEmpty<T>(FieldInfo queueField, string label)
        where T : class
    {
        if (queueField == null || QueueItems<T>(queueField).Length != 0)
            throw Refuse(label + " static queue is nonempty; refusing to drain foreign/pending groups");
    }

    static void RequireSpawnQueueEmpty()
    {
        if (SpawnGroupType == null || SpawnQueueField == null || SpawnQueueCount() != 0)
            throw Refuse("SceneObjectSpawnGroup static queue is nonempty or its pinned runtime type changed");
    }

    static Delegate RequireKnownGlobalSceneChangedSubscribers()
    {
        var callbacks = GlobalSceneChangedHandlersField?.GetValue(null) as Delegate;
        if (callbacks == null)
            throw Refuse("native global scene-changed callback list is unavailable");
        int toggleHandlers = 0;
        int spawnHandlers = 0;
        foreach (var callback in callbacks.GetInvocationList())
        {
            if (callback.Method == DrainNativeToggleQueue && callback.Target == null)
                toggleHandlers++;
            else if (callback.Method == DrainNativeSpawnQueue && callback.Target == null)
                spawnHandlers++;
            else
                throw Refuse("unknown native global scene-changed subscriber: " + callback.Method.DeclaringType.FullName + "." +
                             callback.Method.Name);
        }
        if (toggleHandlers != 1 || spawnHandlers != 1)
            throw Refuse("expected exactly one offline-safe toggle and spawn handler; platform/unknown handlers are unsupported");
        return callbacks;
    }

    static int SpawnQueueCount()
    {
        if (SpawnQueueField == null || SpawnGroupType == null)
            return -1;
        var queue = SpawnQueueField.GetValue(null) as IEnumerable;
        if (queue == null)
            return -1;
        var items = queue.Cast<object>().ToArray();
        if (items.Any(item => item == null || !SpawnGroupType.IsInstanceOfType(item)))
            return -1;
        return items.Length;
    }

    static T[] QueueItems<T>(FieldInfo queueField)
        where T : class
    {
        var queue = queueField?.GetValue(null) as IEnumerable;
        if (queue == null)
            return Array.Empty<T>();
        return queue.Cast<object>().OfType<T>().ToArray();
    }

    static InvalidOperationException Refuse(string reason)
    {
        return new InvalidOperationException("Source-stage identity lifecycle refused: " + reason);
    }

    static (ExpectedIdentity[] identities, ExpectedToggleGroup[] groups, uint toggleSceneId) SceneSpec(string scene)
    {
        if (scene == "golemplains")
            return (GolemplainsIdentities, GolemplainsGroups, 5);
        if (scene == "lakes")
            return (LakesIdentities, LakesGroups, 7);
        throw Refuse("unsupported source scene " + scene);
    }
}
}
