// Source scene identity transaction. Refuse ambiguous native queues or ownership
// and retain the exact recovery context until owned teardown succeeds.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json.Linq;
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
    // Bind only audited borrowed source interactables before any source target activates.
    void PrepareSourceInteractableTables(Scene scene, NetworkIdentity[] sourceIdentities, GameObject[] toggleTargets);
    // Restore exact borrowed fields after identity unspawn and before toggle targets restore.
    void RestoreSourceInteractableTables(Scene scene);
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
        public bool activeSelf;
        public ExpectedIdentity(uint sceneId, string name, bool activeSelf)
        {
            this.sceneId = sceneId;
            this.name = name;
            this.activeSelf = activeSelf;
        }
    }

    sealed class ExpectedToggleGroup
    {
        public int min, max;
        public GameObject[] targets;
        public ExpectedToggleGroup(int min, int max, GameObject[] targets)
        {
            this.min = min;
            this.max = max;
            this.targets = targets;
        }
    }

    sealed class SceneSpecData
    {
        public ExpectedIdentity[] identities;
        public ExpectedToggleGroup[] groups;
        public uint toggleSceneId;
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

    static readonly HashSet<string> SupportedScenes = new HashSet<string>(StringComparer.Ordinal) { "golemplains", "lakes" };

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
        probe.ValidateGlobalSceneIdentityCohort(SceneSpec(scene).identities);
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
        var spec = SceneSpec(scene);
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
            owners.PrepareSourceInteractableTables(scene, identities.Select(state => state.identity).ToArray(),
                                                   toggleStates.Select(state => state.target).ToArray());
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
        VerifyNativeActivationResult(SceneSpec(scene).groups);
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
        owners.RestoreSourceInteractableTables(scene);
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
        owners.RestoreSourceInteractableTables(scene);
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

        var actual =
            global
                .Select(identity => new ExpectedIdentity(identity.sceneId.Value, identity.gameObject.name, identity.gameObject.activeSelf))
                .OrderBy(identity => identity.sceneId)
                .ToArray();
        var wanted = expected.OrderBy(identity => identity.sceneId).ToArray();
        if (actual.Length != wanted.Length ||
            actual
                .Where((identity, index) => identity.sceneId != wanted[index].sceneId || identity.name != wanted[index].name ||
                                            identity.activeSelf != wanted[index].activeSelf)
                .Any())
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
            if (!specs.TryGetValue(sceneId, out spec) || identity.gameObject.name != spec.name ||
                identity.gameObject.activeSelf != spec.activeSelf)
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
                group.objects.Length != contract.targets.Length ||
                group.objects
                    .Where((obj, index) => !ReferenceEquals(obj, contract.targets[index]) ||
                                           (!ReferenceEquals(obj, null) && obj.gameObject.scene != scene))
                    .Any() ||
                group.objects.Where(obj => !ReferenceEquals(obj, null)).Distinct().Count() !=
                    group.objects.Count(obj => !ReferenceEquals(obj, null)))
                throw Refuse("source toggle group serialized refs/ranges changed at index " + i);
        }
    }

    void CaptureToggleTargets()
    {
        foreach (var target in toggle.toggleGroups.SelectMany(group => group.objects))
        {
            if (!ReferenceEquals(target, null) && toggleStates.All(state => !ReferenceEquals(state.target, target)))
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
        var spec = SceneSpec(scene);
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
            nativeGroups.Length != expected.Sum(group => group.targets.Length))
            throw Refuse("native toggle activation result dimensions changed");
        for (int i = 0; i < objects.Length; i++)
            if (!ReferenceEquals(objects[i], null) && objects[i].activeSelf != nativeGroups[i])
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
                // Native HLAPI UnSpawn marks this identity for reset. In host mode,
                // NetworkIdentity.OnNetworkDestroy clears isServer but retains netId,
                // so isServer cannot decide whether the captured ID still needs Reset.
                if (state.hasRegisteredId && state.identity.netId == state.registeredId)
                    ResetIdentity.Invoke(state.identity, null);
                else if (state.identity.netId.Value != 0)
                    throw Refuse("owned source identity retained an unexpected NetworkInstanceId after UnSpawn");
                if (state.identity.netId.Value != 0 || state.identity.isServer || state.identity.isClient)
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

    static SceneSpecData SceneSpec(Scene scene)
    {
        if (!scene.IsValid() || !SupportedScenes.Contains(scene.name))
            throw Refuse("unsupported source scene " + (scene.IsValid() ? scene.name : "<invalid>"));
        var contextAsset = Resources.Load<TextAsset>("WholeStageContexts");
        var bootstrapAsset = Resources.Load<TextAsset>("WholeCatalogBootstrap");
        if (!contextAsset || !bootstrapAsset)
            throw Refuse("source identity metadata/bootstrap resource is missing");
        var contexts = JObject.Parse(contextAsset.text);
        var bootstrap = JObject.Parse(bootstrapAsset.text);
        if ((int?)contexts["source_identity_schema_version"] != 1 || (string)contexts["input_id"] != (string)bootstrap["input_id"])
            throw Refuse("source identity metadata schema/input generation is incompatible");
        var entry = contexts["stages"]?[scene.name]?["source_identity_lifecycle"] as JObject;
        if (entry == null || (int?)entry["schema_version"] != 1 || !IsSha256((string)entry["source_scene_sha256"]))
            throw Refuse("receipt-bound source identity metadata is missing or malformed: " + scene.name);

        var identityRows = entry["network_identities"] as JArray;
        if (identityRows == null)
            throw Refuse("source NetworkIdentity cohort is missing: " + scene.name);
        var identities =
            identityRows
                .Select(row => new ExpectedIdentity(checked((uint)(int)row["scene_id"]), (string)row["name"], (bool)row["active_self"]))
                .ToArray();
        if (identities.Length == 0 || identities.Any(row => row.sceneId == 0 || String.IsNullOrEmpty(row.name)) ||
            identities.Select(row => row.sceneId).Distinct().Count() != identities.Length)
            throw Refuse("source NetworkIdentity metadata contains empty/duplicate IDs: " + scene.name);

        var controllerRows = entry["toggle_controllers"] as JArray;
        if (controllerRows == null || controllerRows.Count != 1)
            throw Refuse("supported source scene must have exactly one audited toggle controller: " + scene.name);
        var controller = (JObject)controllerRows[0];
        if ((int?)controller["scene_id"] == null || (int)controller["source_component_file_id"] <= 0 ||
            (int)controller["source_game_object_file_id"] <= 0)
            throw Refuse("toggle controller lacks serialized source identity: " + scene.name);
        var controllerSceneId = checked((uint)(int)controller["scene_id"]);
        var controllerIdentity = identities.Where(row => row.sceneId == controllerSceneId && row.name == "ToggleGroupController").ToArray();
        if (controllerIdentity.Length != 1)
            throw Refuse("toggle controller scene ID does not map to its audited identity: " + scene.name);
        var controllerObject = ResolveTransformPath(scene, controller["transform_path"] as JArray);
        if (!controllerObject || controllerObject.name != "ToggleGroupController")
            throw Refuse("serialized transform path did not resolve the exact toggle controller: " + scene.name);
        var toggle = controllerObject.GetComponent<SceneObjectToggleGroup>();
        var identity = controllerObject.GetComponent<NetworkIdentity>();
        if (!toggle || !identity || identity.sceneId.Value != controllerSceneId)
            throw Refuse("resolved toggle controller component/identity differs from metadata: " + scene.name);

        var groupRows = controller["groups"] as JArray;
        if (groupRows == null)
            throw Refuse("serialized toggle groups are missing: " + scene.name);
        var groups = new ExpectedToggleGroup[groupRows.Count];
        for (int groupIndex = 0; groupIndex < groupRows.Count; groupIndex++)
        {
            var group = (JObject)groupRows[groupIndex];
            var slots = group["objects"] as JArray;
            if (slots == null)
                throw Refuse("toggle slot array is missing at group " + groupIndex);
            var targets = new GameObject[slots.Count];
            for (int slotIndex = 0; slotIndex < slots.Count; slotIndex++)
            {
                var slot = (JObject)slots[slotIndex];
                int sourceId = (int)slot["source_game_object_file_id"];
                var path = slot["transform_path"] as JArray;
                if (sourceId == 0)
                {
                    if (path != null)
                        throw Refuse("serialized null toggle slot has a fabricated transform path at " + groupIndex + "/" + slotIndex);
                    targets[slotIndex] = null;
                }
                else
                {
                    if (sourceId < 0 || path == null)
                        throw Refuse("non-null toggle slot has no source ID/path binding at " + groupIndex + "/" + slotIndex);
                    targets[slotIndex] = ResolveTransformPath(scene, path);
                    if (!targets[slotIndex] || targets[slotIndex].scene != scene)
                        throw Refuse("serialized toggle target did not resolve in the exact source scene at " + groupIndex + "/" +
                                     slotIndex);
                }
            }
            groups[groupIndex] = new ExpectedToggleGroup((int)group["min_enabled"], (int)group["max_enabled"], targets);
        }
        return new SceneSpecData { identities = identities, groups = groups, toggleSceneId = controllerSceneId };
    }

    static GameObject ResolveTransformPath(Scene scene, JArray path)
    {
        if (path == null || path.Count == 0)
            throw Refuse("serialized transform path is empty");
        var root = (JObject)path[0];
        if ((bool?)root["root"] != true || (int?)root["same_name_same_shape_count"] != 1 || (int?)root["same_name_root_count"] < 1 ||
            !IsSha256((string)root["root_shape_sha256"]))
            throw Refuse("serialized root binding is ambiguous or malformed");
        string rootName = (string)root["name"];
        var roots = scene.GetRootGameObjects();
        var namedRoots = roots.Where(candidate => candidate && candidate.name == rootName).ToArray();
        if (namedRoots.Length != (int)root["same_name_root_count"])
            throw Refuse("scene root name cohort changed: " + rootName);
        var matchingRoots = namedRoots.Where(candidate => ShapeHash(candidate.transform) == (string)root["root_shape_sha256"]).ToArray();
        if (matchingRoots.Length != 1)
            throw Refuse("serialized scene root shape is missing or ambiguous: " + rootName);
        Transform current = matchingRoots[0].transform;
        for (int i = 1; i < path.Count; i++)
        {
            var segment = (JObject)path[i];
            int index = (int)segment["index"];
            int siblingCount = (int)segment["sibling_count"];
            if ((bool?)segment["root"] != false || current.childCount != siblingCount || index < 0 || index >= current.childCount)
                throw Refuse("serialized transform child shape/index changed at segment " + i);
            current = current.GetChild(index);
            if (current.name != (string)segment["name"])
                throw Refuse("serialized transform child name changed at segment " + i);
        }
        return current.gameObject;
    }

    static string ShapeHash(Transform root)
    {
        var signature = new StringBuilder();
        AppendShape(root, signature);
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.ASCII.GetBytes(signature.ToString())))
            .Replace("-", "")
            .ToLowerInvariant();
    }

    static void AppendShape(Transform node, StringBuilder signature)
    {
        signature.Append(Convert.ToBase64String(Encoding.UTF8.GetBytes(node.name))).Append('|').Append(node.childCount).Append('[');
        for (int i = 0; i < node.childCount; i++)
            AppendShape(node.GetChild(i), signature);
        signature.Append(']');
    }

    static bool IsSha256(string value)
    {
        return value != null && value.Length == 64 &&
               value.All(character => (character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'));
    }
}
}
