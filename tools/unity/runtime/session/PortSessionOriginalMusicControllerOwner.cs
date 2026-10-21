// Process-scoped owner for the accepted original MusicController prefab.
// It mirrors MusicController.Init's asynchronous load/instantiate/preload path,
// replacing only its unavailable RoR2Application.instance parent. It never
// synthesizes a RoR2Application, user, Run, teleporter, scene, or Wwise result.
using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using System.Threading;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;
using RoR2;

public sealed class PortSessionOriginalMusicControllerOwner : MonoBehaviour
{
    const float LoadDeadlineSeconds = 60f;
    const string PrefabPath = OriginalMusicControllerContract.PrefabPath;
    const string ExpectedLegacyKey = OriginalMusicControllerContract.AcceptedLegacyKey;

    static PortSessionOriginalMusicControllerOwner instance;
    AsyncOperationHandle<GameObject> prefabHandle;
    MusicController ownedController;
    GameObject ownedControllerRoot;
    bool started, loadCompleted, stopRequested, termsReturnHandled, preloadCalled, preloadAttempted;
    bool sourcePreloadReturned, sourceSceneCallbackObserverAttached, failedInstanceCleanupPending;
    bool outputObserverInstalled, awaitingInstantiationAwake;
    object pendingAddOutputController;
    int pendingAddOutputResult, pendingAddOutputCount;
    ulong pendingAddOutputId;
    float loadStartedAt;
    int unityThreadId;
    FieldInfo apiBeforeEngineTermField;

    public bool MayReleaseOriginalAudioCatalogLease
    {
        get
        {
            if (!GameAudioOriginalOwner.OriginalTermsReturned)
                return true;
            if (prefabHandle.IsValid() && !prefabHandle.IsDone)
                return false;
            if (ownedController && !snapshot.sourceSceneLoadedCallbackRetiredObserved)
                return false;
            return !ownedController || snapshot.controllerDestroyedObserved;
        }
    }

    [Serializable]
    public sealed class Snapshot
    {
        public bool requested, sourceAudioReady, noAudio, originalTermsReturned, engineInitialized;
        public bool sourcePrefabKeyVerified, sourcePrefabLoaded, exactSourceComponentsVerified;
        public bool instanceCreated, preloadCalled, staticInstanceMatchesOwnedController;
        public bool sourcePrefabWasActiveAtInstantiation;
        public bool sourceMusicControllerEnabled, sourceMusicSystemEnabled;
        public bool sourceAddOutputLifecycleExpected, outputResultObserved, outputAccepted;
        public bool outputDeviceIdValid, removeOutputResultObserved, removeOutputDeviceIdValid;
        public bool outputObservationOwnerMismatch;
        public int outputResultCode, removeOutputResultCode;
        public ulong outputDeviceId, removeOutputDeviceId;
        public bool sceneDefObserved, teleporterObserved, targetCameraInventoryNonempty, targetBodyObserved;
        public bool introSceneLoadedAfterPreload, nonIntroSceneLoadedAfterPreload;
        public bool preloadAttempted;
        public bool sourceSceneLoadedCallbackRetiredObserved;
        public bool sourceCallbackRetirementUnknown, sourcePreloadReturned, failedInstanceCleanupPending;
        public bool beforeTermHookInstalled, passiveBeforeTermComposed;
        public bool ownerCleanupRequested, controllerInactiveObserved, controllerDestroyedObserved;
        public bool listenerWwiseObjectIdValid, loadHandleReleased, failureIsFirst;
        public string phase, firstFailure, sourceKey, sourcePrefabName, outputShareSet;
        public string currentSceneName, teardownEvidence;
        public ulong listenerWwiseObjectId;
        public int ownedMusicControllerInstanceId;
        public float loadElapsedSeconds;
        public string limitations;
    }

    readonly Snapshot snapshot = new Snapshot {
        phase = "not_started",
        outputShareSet = OriginalMusicControllerContract.OutputShareSet,
        outputResultObserved = false,
        outputAccepted = false,
        teardownEvidence = "not_observed",
        limitations = "AddOutput/RemoveOutput result codes are captured only for the exact owned MusicController; accepted output setup, track state/event completion, scene/run ownership, and audible or spatial PCM remain unproven"
    };

    public static PortSessionOriginalMusicControllerOwner StartForReadyAudio(
        PortSessionOriginalAudioOwner processAudioOwner, bool explicitlyRequested)
    {
        if (!explicitlyRequested)
            return null;
        if (!processAudioOwner)
            throw new InvalidOperationException("Original music owner requires the existing process-scoped audio owner");
        var owner = processAudioOwner.GetComponent<PortSessionOriginalMusicControllerOwner>();
        if (!owner)
            owner = processAudioOwner.gameObject.AddComponent<PortSessionOriginalMusicControllerOwner>();
        instance = owner;
        owner.Begin(explicitlyRequested);
        return owner;
    }

    void Begin(bool explicitlyRequested)
    {
        if (started)
            return;
        started = true;
        unityThreadId = Thread.CurrentThread.ManagedThreadId;
        snapshot.requested = explicitlyRequested;
        snapshot.sourceAudioReady = GameAudioOriginalOwner.Ready;
        snapshot.noAudio = WwiseIntegrationManager.noAudio;
        snapshot.originalTermsReturned = GameAudioOriginalOwner.OriginalTermsReturned;
        snapshot.engineInitialized = AkSoundEngine.IsInitialized();
        bool existing = MusicController.Instance || UnityEngine.Object.FindObjectOfType<MusicController>();
        string sourceKey;
        snapshot.sourcePrefabKeyVerified = LegacyResourcesAPI.GetGuid(PrefabPath, out sourceKey) &&
            sourceKey == ExpectedLegacyKey;
        snapshot.sourceKey = sourceKey;
        if (!OriginalMusicControllerContract.MayStart(explicitlyRequested, snapshot.sourceAudioReady,
                snapshot.noAudio, snapshot.originalTermsReturned, snapshot.engineInitialized, existing,
                snapshot.sourcePrefabKeyVerified))
        {
            Refuse(existing ? "duplicate_original_music_controller" : "original_music_start_gate_refused");
            return;
        }
        try
        {
            InstallMusicOutputObserver();
            InstallBeforeTermCleanupHook();
        }
        catch (Exception error)
        {
            Refuse("original_music_pre_term_hook_install_failed:" + error.GetType().Name);
            return;
        }
        loadStartedAt = Time.realtimeSinceStartup;
        snapshot.phase = "loading_original_music_prefab";
        prefabHandle = LegacyResourcesAPI.LoadAsync<GameObject>(PrefabPath);
        if (!prefabHandle.IsValid())
        {
            Refuse("original_music_prefab_load_handle_invalid");
            return;
        }
        prefabHandle.Completed += OnPrefabLoadCompleted;
        if (prefabHandle.IsDone)
            CompletePrefabLoad(prefabHandle);
    }

    void Update()
    {
        snapshot.loadElapsedSeconds = started && !loadCompleted
            ? Mathf.Max(0f, Time.realtimeSinceStartup - loadStartedAt) : snapshot.loadElapsedSeconds;
        snapshot.sourceAudioReady = GameAudioOriginalOwner.Ready;
        snapshot.noAudio = WwiseIntegrationManager.noAudio;
        snapshot.originalTermsReturned = GameAudioOriginalOwner.OriginalTermsReturned;
        snapshot.engineInitialized = AkSoundEngine.IsInitialized();
        if (started && !loadCompleted && !stopRequested && snapshot.loadElapsedSeconds > LoadDeadlineSeconds)
            Refuse("original_music_prefab_load_deadline_exceeded; lease_retained_until_completion");
        if (ownedController)
        {
            snapshot.staticInstanceMatchesOwnedController = MusicController.Instance == ownedController;
            snapshot.sourceMusicControllerEnabled = ownedController.isActiveAndEnabled;
            snapshot.sourceMusicSystemEnabled = ownedController.enableMusicSystem;
            snapshot.ownedMusicControllerInstanceId = ownedController.GetInstanceID();
            snapshot.targetCameraInventoryNonempty = CameraRigController.readOnlyInstancesList != null &&
                CameraRigController.readOnlyInstancesList.Count > 0;
            snapshot.targetBodyObserved = ownedController.target;
            snapshot.teleporterObserved = TeleporterInteraction.instance;
            snapshot.sceneDefObserved = SceneCatalog.mostRecentSceneDef;
            snapshot.currentSceneName = SceneCatalog.mostRecentSceneDef ? SceneCatalog.mostRecentSceneDef.cachedName : null;
            if (GameAudioOriginalOwner.OriginalTermsReturned && !termsReturnHandled)
                NotifyOriginalTermsReturned();
        }
        if (CanBeginFailedInstanceCleanup())
        {
            try
            {
                DestroyOwnedControllerSynchronously();
                snapshot.phase = "failed_music_instance_destroyed_after_source_callback_retired";
                snapshot.teardownEvidence = "failed owner retained its instantiated source root until the original callback retirement was observed and synchronous Unity destruction completed";
            }
            catch (Exception error)
            {
                Refuse("original_music_failed_instance_destroy_failed:" + error.GetType().Name);
                snapshot.teardownEvidence = "failed instance remains owned because synchronous Unity destruction was not observed";
            }
        }
    }

    void OnPrefabLoadCompleted(AsyncOperationHandle<GameObject> handle)
    {
        loadCompleted = true;
        CompletePrefabLoad(handle);
    }

    void CompletePrefabLoad(AsyncOperationHandle<GameObject> handle)
    {
        if (snapshot.phase != "loading_original_music_prefab")
        {
            ReleaseLoadHandleIfSafe();
            return;
        }
        snapshot.loadElapsedSeconds = Mathf.Max(0f, Time.realtimeSinceStartup - loadStartedAt);
        GameObject prefab = handle.Status == AsyncOperationStatus.Succeeded ? handle.Result : null;
        MusicController sourceController;
        AkAudioListener sourceListener;
        AkGameObj sourceAkGameObject;
        bool exactSource = InspectSourcePrefab(prefab, out sourceController, out sourceListener, out sourceAkGameObject);
        snapshot.sourcePrefabLoaded = prefab;
        snapshot.sourcePrefabName = prefab ? prefab.name : null;
        snapshot.exactSourceComponentsVerified = exactSource;
        bool timely = snapshot.loadElapsedSeconds <= LoadDeadlineSeconds;
        if (!OriginalMusicControllerContract.MayAcceptLoadCompletion(this, stopRequested,
                GameAudioOriginalOwner.Ready, WwiseIntegrationManager.noAudio,
                GameAudioOriginalOwner.OriginalTermsReturned, AkSoundEngine.IsInitialized(),
                handle.Status == AsyncOperationStatus.Succeeded, timely, exactSource))
        {
            Refuse("original_music_prefab_load_failed_late_or_source_graph_changed");
            ReleaseLoadHandleIfSafe();
            return;
        }
        if (MusicController.Instance || UnityEngine.Object.FindObjectOfType<MusicController>())
        {
            Refuse("duplicate_original_music_controller_appeared_during_async_load");
            ReleaseLoadHandleIfSafe();
            return;
        }

        try
        {
            awaitingInstantiationAwake = true;
            pendingAddOutputCount = 0;
            pendingAddOutputController = null;
            ownedControllerRoot = UnityEngine.Object.Instantiate(prefab, transform, false);
            ownedController = ownedControllerRoot ? ownedControllerRoot.GetComponent<MusicController>() : null;
            awaitingInstantiationAwake = false;
            snapshot.instanceCreated = ownedController;
            snapshot.sourcePrefabWasActiveAtInstantiation = ownedController && ownedController.isActiveAndEnabled;
            if (!ownedController || ownedControllerRoot.GetComponents<MusicController>().Length != 1)
                throw new InvalidOperationException("Instantiated source MusicController component cardinality changed");
            JoinPendingAddOutputToExactOwnedController();
            // Preserve the stock Init completion ordering: active Instantiate
            // first dispatches source Awake/OnEnable, then Preload exactly once.
            preloadAttempted = true;
            snapshot.preloadAttempted = true;
            try
            {
                ownedController.PreloadForCutsceneStart();
                preloadCalled = true;
                snapshot.preloadCalled = true;
                sourcePreloadReturned = true;
                snapshot.sourcePreloadReturned = true;
            }
            finally
            {
                // Register immediately after the source method. It follows the
                // source callback in invocation order, so a later event can
                // witness that source callback's self-removal.
                AttachSourceCallbackRetirementObserver();
            }
            var cloneListeners = ownedControllerRoot.GetComponents<AkAudioListener>();
            var cloneAkGameObjects = ownedControllerRoot.GetComponents<AkGameObj>();
            if (cloneListeners.Length != 1 || cloneAkGameObjects.Length != 1 ||
                !cloneListeners[0].enabled || !cloneListeners[0].isDefaultListener ||
                !cloneAkGameObjects[0].enabled || cloneListeners[0].gameObject != ownedController.gameObject ||
                cloneAkGameObjects[0].gameObject != ownedController.gameObject)
                throw new InvalidOperationException("Instantiated source MusicController listener pair changed");
            snapshot.staticInstanceMatchesOwnedController = MusicController.Instance == ownedController;
            snapshot.sourceMusicControllerEnabled = ownedController.isActiveAndEnabled;
            snapshot.sourceMusicSystemEnabled = ownedController.enableMusicSystem;
            snapshot.sourceAddOutputLifecycleExpected = true; // Active prefab Awake follows original AddOutput; result remains private.
            snapshot.listenerWwiseObjectId = cloneListeners[0].GetAkGameObjectID();
            snapshot.listenerWwiseObjectIdValid = snapshot.listenerWwiseObjectId != ulong.MaxValue;
            snapshot.ownedMusicControllerInstanceId = ownedController.GetInstanceID();
            snapshot.phase = OriginalMusicControllerContract.MayReportPreloaded(
                snapshot.staticInstanceMatchesOwnedController, preloadCalled, snapshot.sourcePrefabWasActiveAtInstantiation,
                snapshot.sourceMusicControllerEnabled) ? (snapshot.outputResultObserved ? "source_controller_preloaded_output_result_observed" : "source_controller_preloaded_output_result_unknown") :
                "preload_called_controller_identity_or_activation_unverified";
        }
        catch (Exception error)
        {
            awaitingInstantiationAwake = false;
            pendingAddOutputController = null;
            pendingAddOutputCount = 0;
            Refuse("original_music_instantiation_or_preload_failed:" + error.GetType().Name);
            stopRequested = true;
            failedInstanceCleanupPending = ownedControllerRoot;
            snapshot.failedInstanceCleanupPending = failedInstanceCleanupPending;
            if (preloadAttempted && (!sourcePreloadReturned || !sourceSceneCallbackObserverAttached))
            {
                // Preload may have partially subscribed before throwing. No
                // later event can prove that callback's identity or retirement.
                snapshot.sourceCallbackRetirementUnknown = true;
                snapshot.teardownEvidence = "Preload did not return with a retirement observer installed; original callback state is unknown and the instantiated root remains owned";
            }
            ReleaseLoadHandleIfSafe();
        }
    }

    void InstallMusicOutputObserver()
    {
        if (OriginalOwnerProbeObserver.Observer.MusicAddOutputReturned != null ||
            OriginalOwnerProbeObserver.Observer.MusicRemoveOutputReturned != null)
            throw new InvalidOperationException("Music output observer already has an owner");
        OriginalOwnerProbeObserver.Observer.MusicAddOutputReturned = ObserveMusicAddOutput;
        OriginalOwnerProbeObserver.Observer.MusicRemoveOutputReturned = ObserveMusicRemoveOutput;
        outputObserverInstalled = true;
    }

    void ObserveMusicAddOutput(int result, object sourceOwner, ulong outputId)
    {
        if (awaitingInstantiationAwake)
        {
            if (pendingAddOutputCount == 0)
            {
                pendingAddOutputCount = 1;
                pendingAddOutputController = sourceOwner;
                pendingAddOutputResult = result;
                pendingAddOutputId = outputId;
            }
            else
            {
                pendingAddOutputCount = 2; // Saturated ambiguity marker.
                pendingAddOutputController = null;
            }
            return;
        }
        if (ownedController && ReferenceEquals(sourceOwner, (object)ownedController))
            RecordOwnedAddOutput(result, outputId);
        else
            snapshot.outputObservationOwnerMismatch = true;
    }

    void JoinPendingAddOutputToExactOwnedController()
    {
        if (pendingAddOutputCount == 1 && ownedController &&
            ReferenceEquals(pendingAddOutputController, (object)ownedController))
            RecordOwnedAddOutput(pendingAddOutputResult, pendingAddOutputId);
        else if (pendingAddOutputCount != 0)
            snapshot.outputObservationOwnerMismatch = true;
        pendingAddOutputController = null;
        pendingAddOutputCount = 0;
        pendingAddOutputResult = 0;
        pendingAddOutputId = 0;
    }

    void RecordOwnedAddOutput(int result, ulong outputId)
    {
        snapshot.outputResultObserved = true;
        snapshot.outputResultCode = result;
        snapshot.outputAccepted = result == (int)AKRESULT.AK_Success;
        snapshot.outputDeviceIdValid = snapshot.outputAccepted;
        snapshot.outputDeviceId = snapshot.outputAccepted ? outputId : 0;
    }

    void ObserveMusicRemoveOutput(int result, object sourceOwner, ulong outputId)
    {
        if (!ownedController || !ReferenceEquals(sourceOwner, (object)ownedController))
        {
            snapshot.outputObservationOwnerMismatch = true;
            return;
        }
        snapshot.removeOutputResultObserved = true;
        snapshot.removeOutputResultCode = result;
        snapshot.removeOutputDeviceIdValid = snapshot.outputDeviceIdValid && outputId == snapshot.outputDeviceId;
        snapshot.removeOutputDeviceId = snapshot.removeOutputDeviceIdValid ? outputId : 0;
    }

    void DetachMusicOutputObserver()
    {
        if (!outputObserverInstalled) return;
        if (OriginalOwnerProbeObserver.Observer.MusicAddOutputReturned == (Action<int, object, ulong>)ObserveMusicAddOutput)
            OriginalOwnerProbeObserver.Observer.MusicAddOutputReturned = null;
        if (OriginalOwnerProbeObserver.Observer.MusicRemoveOutputReturned == (Action<int, object, ulong>)ObserveMusicRemoveOutput)
            OriginalOwnerProbeObserver.Observer.MusicRemoveOutputReturned = null;
        outputObserverInstalled = false;
    }

    void AttachSourceCallbackRetirementObserver()
    {
        if (sourceSceneCallbackObserverAttached)
            return;
        UnityEngine.SceneManagement.SceneManager.sceneLoaded += ObserveSceneLoadedAfterPreload;
        sourceSceneCallbackObserverAttached = true;
    }

    // Called by Update and exercised by the host fixture against this compiled
    // owner. A failed instance may be destroyed only after the callback is
    // known to be absent or its ordered retirement was observed.
    internal bool CanBeginFailedInstanceCleanup()
    {
        return stopRequested && failedInstanceCleanupPending &&
            !snapshot.sourceCallbackRetirementUnknown &&
            (!sourceSceneCallbackObserverAttached || snapshot.sourceSceneLoadedCallbackRetiredObserved);
    }

    void ObserveSceneLoadedAfterPreload(UnityEngine.SceneManagement.Scene scene,
        UnityEngine.SceneManagement.LoadSceneMode mode)
    {
        if (scene.name == "intro")
        {
            snapshot.introSceneLoadedAfterPreload = true;
            return;
        }
        snapshot.nonIntroSceneLoadedAfterPreload = true;
        if (!sourcePreloadReturned)
        {
            snapshot.sourceCallbackRetirementUnknown = true;
            snapshot.sourceSceneLoadedCallbackRetiredObserved = false;
            snapshot.teardownEvidence = "a non-intro scene was observed after Preload failed, but source callback retirement remains unknown";
        }
        else
        {
            snapshot.sourceSceneLoadedCallbackRetiredObserved = true;
        }
        if (GameAudioOriginalOwner.OriginalTermsReturned && sourcePreloadReturned)
            snapshot.teardownEvidence = "non-intro scene callback observed after original Terms; source handler retired after its callback; output call ordering remains unknown";
        UnityEngine.SceneManagement.SceneManager.sceneLoaded -= ObserveSceneLoadedAfterPreload;
        sourceSceneCallbackObserverAttached = false;
    }

    static bool InspectSourcePrefab(GameObject prefab, out MusicController controller,
        out AkAudioListener listener, out AkGameObj akGameObject)
    {
        controller = null;
        listener = null;
        akGameObject = null;
        if (!prefab || prefab.name != "MusicController")
            return false;
        var controllers = prefab.GetComponents<MusicController>();
        var listeners = prefab.GetComponents<AkAudioListener>();
        var gameObjects = prefab.GetComponents<AkGameObj>();
        if (controllers.Length != 1 || listeners.Length != 1 || gameObjects.Length != 1)
            return false;
        controller = controllers[0]; listener = listeners[0]; akGameObject = gameObjects[0];
        return controller && controller.enabled && controller.enableMusicSystem &&
            listener && listener.enabled && listener.isDefaultListener &&
            akGameObject && akGameObject.enabled && listener.gameObject == controller.gameObject &&
            akGameObject.gameObject == controller.gameObject;
    }

    public void NotifyOriginalTermsReturned()
    {
        if (!started || termsReturnHandled)
            return;
        termsReturnHandled = true;
        snapshot.originalTermsReturned = true;
        // The injected Term callback already destroyed the controller before
        // native Term. Preserve that success when the later session poll sees
        // Term return; do not relabel it as an unobserved/retained controller.
        if (snapshot.controllerDestroyedObserved)
            return;
        snapshot.ownerCleanupRequested = true;
        snapshot.teardownEvidence = "original Terms observed; controller disabled and its prefab/catalog lease retained because Term versus RemoveOutput ordering is unverified";
        snapshot.phase = "original_terms_observed_controller_retained_output_removal_unobserved";
        if (ownedController)
        {
            // Suppress future track decisions without invoking the source
            // OnDestroy, which would remove the output after Term ordering is
            // already unknown. Its OnDisable callback remains source-owned.
            ownedController.enabled = false;
            snapshot.controllerInactiveObserved = !ownedController.isActiveAndEnabled;
        }
    }

    void InstallBeforeTermCleanupHook()
    {
        Action handler = BeforeOriginalAudioTerm;
        if (TryRegisterWithExistingPassiveCaptureOwner(handler))
        {
            snapshot.beforeTermHookInstalled = true;
            snapshot.passiveBeforeTermComposed = true;
            snapshot.teardownEvidence = "music cleanup registered behind the existing passive-capture pre-Term guard";
            return;
        }

        apiBeforeEngineTermField = ResolveApiBeforeEngineTermField();
        Action coreExisting = OriginalOwnerProbeObserver.Observer.BeforeEngineTerm;
        Action apiExisting = apiBeforeEngineTermField.GetValue(null) as Action;
        if (coreExisting != null || apiExisting != null)
            throw new InvalidOperationException("An existing pre-Term guard has no known composition owner; refusing to replace it.");
        try
        {
            apiBeforeEngineTermField.SetValue(null, handler);
            OriginalOwnerProbeObserver.Observer.BeforeEngineTerm = handler;
            if (!ReferenceEquals(apiBeforeEngineTermField.GetValue(null), handler) ||
                !ReferenceEquals(OriginalOwnerProbeObserver.Observer.BeforeEngineTerm, handler))
                throw new InvalidOperationException("Music pre-Term guard did not retain one identical API/Core delegate.");
            snapshot.beforeTermHookInstalled = true;
            snapshot.teardownEvidence = "music cleanup owns the sole API/Core pre-Term guard; no passive capture guard was selected";
        }
        catch
        {
            // Clear only the exact delegate installed by this attempt. Never
            // overwrite or erase a concurrently established guard.
            if (ReferenceEquals(apiBeforeEngineTermField.GetValue(null), handler))
                apiBeforeEngineTermField.SetValue(null, null);
            if (ReferenceEquals(OriginalOwnerProbeObserver.Observer.BeforeEngineTerm, handler))
                OriginalOwnerProbeObserver.Observer.BeforeEngineTerm = null;
            throw;
        }
    }

    static bool TryRegisterWithExistingPassiveCaptureOwner(Action handler)
    {
        // This adapter is compiled into GameAudioOriginalBootstrap, while this
        // owner lives in Assembly-CSharp. Resolve the exact loaded bootstrap
        // assembly instead of assuming both types share an assembly.
        Assembly bootstrap = Assembly.Load(new AssemblyName("GameAudioOriginalBootstrap"));
        var bootstrapAssemblies = AppDomain.CurrentDomain.GetAssemblies()
            .Where(assembly => String.Equals(assembly.FullName, bootstrap.FullName, StringComparison.Ordinal)).ToArray();
        if (bootstrapAssemblies.Length != 1)
            throw new InvalidOperationException("The accepted audio bootstrap identity is not loaded exactly once.");
        Type ownerType = bootstrapAssemblies[0].GetType("OriginalGameAudioPassivePcmOwner", false, false);
        if (ownerType == null)
            throw new InvalidOperationException("The accepted passive capture owner type is unavailable.");
        PropertyInfo processOwnerProperty = ownerType.GetProperty("ProcessLifetimeOwner",
            BindingFlags.NonPublic | BindingFlags.Static);
        MethodInfo register = ownerType.GetMethod("RegisterMusicBeforeTerm",
            BindingFlags.NonPublic | BindingFlags.Static);
        if (processOwnerProperty == null || register == null || register.ReturnType != typeof(bool) ||
            register.GetParameters().Length != 1 || register.GetParameters()[0].ParameterType != typeof(Action))
            throw new InvalidOperationException("The passive capture owner lacks the pinned supplemental Term registration contract.");
        if (processOwnerProperty.GetValue(null, null) == null)
            return false;
        try
        {
            return (bool)register.Invoke(null, new object[] { handler });
        }
        catch (TargetInvocationException error)
        {
            throw new InvalidOperationException("The passive capture owner refused music Term registration.", error.InnerException ?? error);
        }
    }

    static FieldInfo ResolveApiBeforeEngineTermField()
    {
        const string apiAssemblyName = "AK.Wwise.Unity.API";
        const string observerAssemblyName = "OriginalOwnerProbeObserver";
        const string typeName = "OriginalOwnerProbeObserver.Observer";
        Assembly api = Assembly.Load(new AssemblyName(apiAssemblyName));
        var references = api.GetReferencedAssemblies()
            .Where(reference => String.Equals(reference.Name, observerAssemblyName, StringComparison.Ordinal)).ToArray();
        if (references.Length != 1)
            throw new InvalidOperationException("Wwise API does not reference exactly one pinned pre-Term observer assembly.");
        var loaded = AppDomain.CurrentDomain.GetAssemblies()
            .Where(assembly => String.Equals(assembly.FullName, references[0].FullName, StringComparison.Ordinal)).ToArray();
        if (loaded.Length > 1)
            throw new InvalidOperationException("The pinned pre-Term observer identity is loaded more than once.");
        Assembly observerAssembly = loaded.Length == 1 ? loaded[0] : Assembly.Load(references[0]);
        if (!String.Equals(observerAssembly.FullName, references[0].FullName, StringComparison.Ordinal))
            throw new InvalidOperationException("Loaded pre-Term observer identity differs from the API reference.");
        Type observer = observerAssembly.GetType(typeName, false, false);
        Type coreObserver = typeof(OriginalOwnerProbeObserver.Observer);
        if (observer == null || coreObserver != observer || coreObserver.Assembly.FullName != observerAssembly.FullName)
            throw new InvalidOperationException("Core and API do not bind the same exact pre-Term observer type identity.");
        FieldInfo field = observer == null ? null : observer.GetField("BeforeEngineTerm", BindingFlags.Public | BindingFlags.Static);
        MethodInfo method = observer == null ? null : observer.GetMethod("RecordBeforeEngineTerm", BindingFlags.Public | BindingFlags.Static);
        if (field == null || field.FieldType != typeof(Action) || !field.IsStatic || method == null ||
            method.ReturnType != typeof(void) || method.GetParameters().Length != 0 || !method.IsStatic)
            throw new InvalidOperationException("The API observer does not expose the exact Action pre-Term hook contract.");
        return field;
    }

    // Synchronous because the transformed API invokes this immediately before
    // its original Term body. Unity Destroy is deferred past that call, so use
    // DestroyImmediate only after checking the exact source callback has
    // retired and we are still on the Unity thread that owns the object.
    void BeforeOriginalAudioTerm()
    {
        if (!started || snapshot.controllerDestroyedObserved)
            return;
        bool onOwningThread = Thread.CurrentThread.ManagedThreadId == unityThreadId;
        bool loadPending = !loadCompleted && prefabHandle.IsValid();
        if (!OriginalMusicControllerContract.MayRunBeforeTermCleanup(onOwningThread, loadPending,
                sourceSceneCallbackObserverAttached, snapshot.sourceSceneLoadedCallbackRetiredObserved,
                snapshot.sourceCallbackRetirementUnknown))
        {
            string reason = !onOwningThread ? "off its owning Unity thread" :
                (loadPending ? "while the source MusicController load is pending" :
                    "before the source MusicController sceneLoaded callback retired");
            Refuse("original_music_pre_term_cleanup_refused:" + reason);
            snapshot.teardownEvidence = "pre-Term guard refused native Term before changing the live source controller";
            throw new InvalidOperationException("Refusing original Term " + reason + ".");
        }
        if (!ownedControllerRoot && !ownedController)
        {
            ReleaseLoadHandleIfSafe();
            snapshot.controllerDestroyedObserved = true;
            snapshot.teardownEvidence = "no source controller was instantiated; pre-Term music cleanup is complete";
            return;
        }

        stopRequested = true;
        snapshot.ownerCleanupRequested = true;
        snapshot.phase = "source_controller_destroyed_synchronously_before_original_term";
        snapshot.teardownEvidence = "source callback retirement observed; Unity destroyed the owned source object through its original OnDestroy before Term";
        DestroyOwnedControllerSynchronously();
        snapshot.phase = "source_controller_destroyed_before_original_term_output_result_unobserved";
    }

    void DestroyOwnedControllerSynchronously()
    {
        if (!ownedControllerRoot)
        {
            if (ownedController)
                throw new InvalidOperationException("Owned MusicController reference exists without its retained root");
            snapshot.controllerDestroyedObserved = true;
            ownedController = null;
            ownedControllerRoot = null;
            failedInstanceCleanupPending = false;
            snapshot.failedInstanceCleanupPending = false;
            ReleaseLoadHandleIfSafe();
            return;
        }
        if (ownedController)
        {
            ownedController.enabled = false;
            snapshot.controllerInactiveObserved = !ownedController.isActiveAndEnabled;
        }
        try { UnityEngine.Object.DestroyImmediate(ownedControllerRoot); }
        catch (Exception error)
        {
            Refuse("original_music_destroy_before_term_failed:" + error.GetType().Name);
            snapshot.teardownEvidence = "synchronous source destruction threw; Term must remain refused";
            throw;
        }
        if (ownedControllerRoot || ownedController)
            throw new InvalidOperationException("Original MusicController destruction did not complete synchronously.");
        ownedController = null;
        ownedControllerRoot = null;
        snapshot.controllerDestroyedObserved = true;
        failedInstanceCleanupPending = false;
        snapshot.failedInstanceCleanupPending = false;
        ReleaseLoadHandleIfSafe();
    }

    void ReleaseLoadHandleIfSafe()
    {
        if (!prefabHandle.IsValid() || !prefabHandle.IsDone)
            return;
        Addressables.Release(prefabHandle);
        prefabHandle = default(AsyncOperationHandle<GameObject>);
        snapshot.loadHandleReleased = true;
    }

    void Refuse(string failure)
    {
        if (string.IsNullOrEmpty(snapshot.firstFailure))
        {
            snapshot.firstFailure = failure.Length > 240 ? failure.Substring(0, 240) : failure;
            snapshot.failureIsFirst = true;
        }
        if (snapshot.phase != "source_controller_preloaded_output_unobserved")
            snapshot.phase = "refused_or_failed_closed";
    }

    void OnDestroy()
    {
        DetachMusicOutputObserver();
        if (sourceSceneCallbackObserverAttached)
        {
            if (!snapshot.sourceSceneLoadedCallbackRetiredObserved)
            {
                snapshot.sourceCallbackRetirementUnknown = true;
                snapshot.teardownEvidence = "music owner was destroyed before its source callback retirement was observed; original callback state remains unknown and the source root is retained";
            }
            UnityEngine.SceneManagement.SceneManager.sceneLoaded -= ObserveSceneLoadedAfterPreload;
            sourceSceneCallbackObserverAttached = false;
        }
        // This owner is attached to the persistent audio owner. Do not
        // explicitly destroy the source controller here: Unity shutdown and
        // Wwise Term ordering are not observable. Leave source OnDestroy and
        // RemoveOutput to the process lifecycle.
    }

    public static Snapshot CaptureSnapshot()
    {
        if (!instance)
            return new Snapshot { phase = "owner_unavailable", teardownEvidence = "not_observed",
                outputShareSet = OriginalMusicControllerContract.OutputShareSet,
                limitations = "music owner has not been admitted; output and playback are unobserved" };
        return instance.snapshot;
    }
}
