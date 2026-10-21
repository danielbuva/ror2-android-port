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
    const float MusicObservationIntervalSeconds = 0.5f;
    const float GlobalRtpcObservationIntervalSeconds = 1.0f;
    const string PrefabPath = OriginalMusicControllerContract.PrefabPath;
    const string ExpectedLegacyKey = OriginalMusicControllerContract.AcceptedLegacyKey;

    static PortSessionOriginalMusicControllerOwner instance;
    AsyncOperationHandle<GameObject> prefabHandle;
    MusicController ownedController;
    GameObject ownedControllerRoot;
    TriggerIntroMusicStart startupMusicTrigger;
    GameObject startupMusicTriggerRoot;
    bool started, loadCompleted, stopRequested, termsReturnHandled, preloadCalled, preloadAttempted;
    bool sourcePreloadReturned, sourceSceneCallbackObserverAttached, failedInstanceCleanupPending;
    bool outputObserverInstalled, awaitingInstantiationAwake;
    object pendingAddOutputController;
    int pendingAddOutputResult, pendingAddOutputCount;
    ulong pendingAddOutputId;
    float loadStartedAt;
    int unityThreadId;
    FieldInfo apiBeforeEngineTermField;
    PropertyInfo currentTrackGetter;
    FieldInfo pickTrackHookField;
    FieldInfo[] musicRtpcFields;
    FieldInfo musicRtpcValueField;
    float nextMusicObservationAt;
    float nextGlobalRtpcObservationAt;
    static bool processStartupTriggerAttempted;

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
        [Serializable]
        public sealed class RtpcObservation
        {
            public string name;
            public bool queryAttempted, resultObserved, valueObserved;
            public int resultCode, requestedValueType, returnedValueType;
            public float value, sampleRealtime;
        }

        [Serializable]
        public sealed class SourceMusicParameterObservation
        {
            public string name;
            public bool valueObserved;
            public float value, sampleRealtime;
        }

        public bool requested, sourceAudioReady, noAudio, originalTermsReturned, engineInitialized;
        public bool sourcePrefabKeyVerified, sourcePrefabLoaded, exactSourceComponentsVerified;
        public bool instanceCreated, preloadCalled, staticInstanceMatchesOwnedController;
        public bool sourcePrefabWasActiveAtInstantiation;
        public bool sourceMusicControllerEnabled, sourceMusicSystemEnabled;
        public bool sourceAddOutputLifecycleExpected, outputResultObserved, outputAccepted;
        public bool startupTriggerAttempted, startupTriggerActivationRequested, startupTriggerRetiredObserved;
        public string startupTriggerTiming;
        public bool outputDeviceIdValid, removeOutputResultObserved, removeOutputDeviceIdValid;
        public bool outputObservationOwnerMismatch;
        public int outputResultCode, removeOutputResultCode;
        public ulong outputDeviceId, removeOutputDeviceId;
        public bool sceneDefObserved, teleporterObserved, targetCameraInventoryNonempty, targetBodyObserved;
        public bool teleporterIdleObserved, teleporterIdle;
        public bool sceneTrackGateObserved, sceneMainTrackPresent, sceneBossTrackPresent;
        public bool sceneTrackHookObservationKnown, sceneTrackHookPresent;
        public bool currentTrackGetterAvailable, currentTrackObservationAttempted, currentTrackObserved, currentTrackPresent;
        public bool musicObservationOwnerAlive, musicObservationAttempted, musicObservationSucceeded;
        public bool ownedListenerObserved, ownedListenerEnabled, ownedListenerDefault;
        public bool ownedListenerMembershipObserved, ownedListenerInManagedDefaultList;
        public bool managedDefaultListenerCountObserved;
        public int managedDefaultListenerCount, currentTrackInstanceId;
        public string sceneTrackCandidateKind, sceneTrackCandidateName, currentTrackName;
        public string musicObservationFailure;
        public float musicObservationRealtime;
        public RtpcObservation[] globalRtpcs;
        public SourceMusicParameterObservation[] sourceMusicParameters;
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
        startupTriggerTiming = "adapted_process_start_not_stock_splash_timeline",
        teardownEvidence = "not_observed",
        limitations = "AddOutput/RemoveOutput results belong to the exact owned MusicController; global RTPC queries and original managed track/context values are observations only. Original PostEvent/SetState results are discarded and remain unobserved; none of these observations proves track playback, native listener registration, or audibility",
        globalRtpcs = new[] {
            new Snapshot.RtpcObservation { name = "Volume_Master" },
            new Snapshot.RtpcObservation { name = "Volume_MSX" },
            new Snapshot.RtpcObservation { name = "Parent_Volume_MSX" }
        },
        sourceMusicParameters = new[] {
            new Snapshot.SourceMusicParameterObservation { name = "playerHealth" },
            new Snapshot.SourceMusicParameterObservation { name = "enemyValue" },
            new Snapshot.SourceMusicParameterObservation { name = "teleporterProximity" },
            new Snapshot.SourceMusicParameterObservation { name = "teleporterDirection" },
            new Snapshot.SourceMusicParameterObservation { name = "teleporterPlayerStatus" }
        }
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
            TryActivateOriginalStartupTrigger();
            SampleSourceMusicContextSafely();
        }
        else
            ExpireMusicObservationIfOwnerMissing();
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

    // Attempt the original component lifecycle only after the existing owner
    // joins a successful source AddOutput queue result to this exact controller.
    // Queue acceptance does not prove native activation or playback. This adapter
    // does not call StartIntroMusic or any Wwise API directly.
    void TryActivateOriginalStartupTrigger()
    {
        bool sameOwnedSingleton = ownedController && MusicController.Instance == ownedController;
        bool ownerFailed = !String.IsNullOrEmpty(snapshot.firstFailure) ||
            failedInstanceCleanupPending || snapshot.sourceCallbackRetirementUnknown;
        bool mayActivate = OriginalMusicControllerContract.MayActivate(
            snapshot.requested, instance == this && this && isActiveAndEnabled,
            GameAudioOriginalOwner.Ready, WwiseIntegrationManager.noAudio,
            AkSoundEngine.IsInitialized(), GameAudioOriginalOwner.OriginalTermsReturned,
            stopRequested, ownerFailed, snapshot.ownerCleanupRequested,
            sourcePreloadReturned && preloadCalled, sameOwnedSingleton,
            ownedController && ownedController.isActiveAndEnabled,
            snapshot.sourceAddOutputLifecycleExpected,
            snapshot.outputResultObserved, snapshot.outputAccepted,
            snapshot.outputResultCode, (int)AKRESULT.AK_Success,
            snapshot.outputDeviceIdValid, snapshot.outputObservationOwnerMismatch,
            snapshot.staticInstanceMatchesOwnedController,
            processStartupTriggerAttempted);

        if (!OriginalMusicControllerContract.TryClaimActivation(
                ref processStartupTriggerAttempted, mayActivate))
            return;
        snapshot.startupTriggerAttempted = true;
        try
        {
            var triggerRoot = new GameObject("OriginalMusicStartupTrigger");
            startupMusicTriggerRoot = triggerRoot;
            triggerRoot.SetActive(false);
            triggerRoot.transform.SetParent(transform, false);
            startupMusicTrigger = triggerRoot.AddComponent<TriggerIntroMusicStart>();
            snapshot.startupTriggerActivationRequested = true;
            triggerRoot.SetActive(true); // Runs the original component's OnEnable.
            startupMusicTrigger.enabled = false;
            triggerRoot.SetActive(false);
            snapshot.startupTriggerRetiredObserved = !startupMusicTrigger.isActiveAndEnabled;
            snapshot.startupTriggerTiming = "adapted_process_start_not_stock_splash_timeline";
            RetireOriginalStartupTrigger();
        }
        catch (Exception error)
        {
            Refuse("original_music_startup_trigger_activation_failed:" + error.GetType().Name);
            RetireOriginalStartupTrigger();
        }
    }

    void RetireOriginalStartupTrigger()
    {
        if (startupMusicTrigger)
            startupMusicTrigger.enabled = false;
        if (startupMusicTriggerRoot)
        {
            if (startupMusicTriggerRoot.activeSelf)
                startupMusicTriggerRoot.SetActive(false);
            UnityEngine.Object.Destroy(startupMusicTriggerRoot);
            startupMusicTriggerRoot = null;
        }
        if (startupMusicTrigger)
            snapshot.startupTriggerRetiredObserved = !startupMusicTrigger.isActiveAndEnabled;
        startupMusicTrigger = null;
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
            TryBindMusicObservationMembers(typeof(MusicController));
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

    void TryBindMusicObservationMembers(Type controllerType)
    {
        currentTrackGetter = null;
        pickTrackHookField = null;
        musicRtpcFields = null;
        musicRtpcValueField = null;
        snapshot.currentTrackGetterAvailable = false;
        snapshot.sceneTrackHookObservationKnown = false;
        try
        {
            BindMusicObservationMembers(controllerType);
        }
        catch (Exception error)
        {
            ClearMusicObservation("binding_failed:" + error.GetType().Name);
        }
    }

    void BindMusicObservationMembers(Type controllerType)
    {
        if (controllerType == null)
            throw new ArgumentNullException("controllerType");
        PropertyInfo trackProperty = controllerType.GetProperty("currentTrack",
            BindingFlags.Instance | BindingFlags.NonPublic);
        MethodInfo getter = trackProperty == null ? null : trackProperty.GetGetMethod(true);
        currentTrackGetter = getter != null && getter.GetParameters().Length == 0 &&
            getter.ReturnType == typeof(MusicTrackDef) ? trackProperty : null;
        snapshot.currentTrackGetterAvailable = currentTrackGetter != null;
        pickTrackHookField = controllerType.GetField("pickTrackHook", BindingFlags.Static | BindingFlags.NonPublic);
        snapshot.sceneTrackHookObservationKnown = false;

        var names = new[] {
            "rtpcPlayerHealthValue", "rtpcEnemyValue", "rtpcTeleporterProximityValue",
            "rtpcTeleporterDirectionValue", "rtpcTeleporterPlayerStatus"
        };
        musicRtpcFields = new FieldInfo[names.Length];
        for (int i = 0; i < names.Length; i++)
            musicRtpcFields[i] = controllerType.GetField(names[i], BindingFlags.Instance | BindingFlags.NonPublic);
        Type setterType = controllerType.Assembly.GetType("RoR2.WwiseUtils.RtpcSetter", false);
        musicRtpcValueField = setterType == null ? null : setterType.GetField("value", BindingFlags.Instance | BindingFlags.Public);
        if (musicRtpcValueField != null && musicRtpcValueField.FieldType != typeof(float))
            musicRtpcValueField = null;
        nextMusicObservationAt = 0f;
        nextGlobalRtpcObservationAt = 0f;
    }

    // Read-only scalar diagnostics. The owner neither calls PickCurrentTrack nor
    // changes MusicController, Wwise state, volume, event, listener, or output.
    void SampleSourceMusicContextSafely()
    {
        try
        {
            ObserveSourceMusicContext();
        }
        catch (Exception error)
        {
            ClearMusicObservation("sample_failed:" + error.GetType().Name);
            snapshot.musicObservationAttempted = true;
            snapshot.musicObservationRealtime = Time.realtimeSinceStartup;
        }
    }

    void ExpireMusicObservationIfOwnerMissing()
    {
        if (!ownedController && snapshot.musicObservationOwnerAlive)
            ClearMusicObservation("source_controller_missing_or_destroyed");
    }

    void ObserveSourceMusicContext()
    {
        float now = Time.realtimeSinceStartup;
        if (now < nextMusicObservationAt)
            return;
        nextMusicObservationAt = now + MusicObservationIntervalSeconds;
        ClearMusicObservation(null);
        snapshot.musicObservationAttempted = true;
        snapshot.musicObservationOwnerAlive = ownedController;
        snapshot.musicObservationRealtime = now;
        if (!ownedController)
        {
            snapshot.currentTrackObservationAttempted = false;
            snapshot.currentTrackObserved = false;
            snapshot.sceneTrackGateObserved = false;
            return;
        }

        SceneDef scene = SceneCatalog.mostRecentSceneDef;
        TeleporterInteraction teleporter = TeleporterInteraction.instance;
        snapshot.sceneDefObserved = scene;
        snapshot.currentSceneName = scene ? scene.cachedName : null;
        snapshot.teleporterObserved = teleporter;
        snapshot.teleporterIdleObserved = teleporter;
        snapshot.teleporterIdle = teleporter && teleporter.isIdle;
        snapshot.sceneTrackGateObserved = true;
        snapshot.sceneMainTrackPresent = scene && scene.mainTrack;
        snapshot.sceneBossTrackPresent = scene && scene.bossTrack;
        snapshot.sceneTrackCandidateKind = ClassifySceneTrackCandidate(
            ownedController.enableMusicSystem, scene, teleporter,
            teleporter && teleporter.isIdle,
            snapshot.sceneBossTrackPresent, snapshot.sceneMainTrackPresent);
        snapshot.sceneTrackCandidateName = snapshot.sceneTrackCandidateKind == "boss_track"
            ? scene.bossTrack.name
            : (snapshot.sceneTrackCandidateKind == "main_track" ? scene.mainTrack.name : null);
        try
        {
            snapshot.sceneTrackHookObservationKnown = pickTrackHookField != null;
            snapshot.sceneTrackHookPresent = pickTrackHookField != null && pickTrackHookField.GetValue(null) != null;
        }
        catch
        {
            snapshot.sceneTrackHookObservationKnown = false;
            snapshot.sceneTrackHookPresent = false;
        }

        snapshot.currentTrackObservationAttempted = true;
        snapshot.currentTrackObserved = false;
        snapshot.currentTrackPresent = false;
        snapshot.currentTrackName = null;
        snapshot.currentTrackInstanceId = 0;
        if (currentTrackGetter != null)
        {
            try
            {
                MusicTrackDef current = currentTrackGetter.GetValue(ownedController, null) as MusicTrackDef;
                snapshot.currentTrackObserved = true;
                snapshot.currentTrackPresent = current;
                snapshot.currentTrackName = current ? current.name : null;
                snapshot.currentTrackInstanceId = current ? current.GetInstanceID() : 0;
            }
            catch
            {
                snapshot.currentTrackObserved = false;
            }
        }

        ObserveSourceMusicParameters(now);
        ObserveOwnedListenerMembership();
        if (now >= nextGlobalRtpcObservationAt)
        {
            nextGlobalRtpcObservationAt = now + GlobalRtpcObservationIntervalSeconds;
            ObserveGlobalRtpcs(now);
        }
        snapshot.musicObservationSucceeded = true;
    }

    void ClearMusicObservation(string failure)
    {
        snapshot.musicObservationAttempted = false;
        snapshot.musicObservationSucceeded = false;
        snapshot.musicObservationFailure = failure;
        snapshot.musicObservationRealtime = 0f;
        snapshot.musicObservationOwnerAlive = ownedController;
        snapshot.currentTrackObservationAttempted = false;
        snapshot.currentTrackObserved = false;
        snapshot.currentTrackPresent = false;
        snapshot.currentTrackName = null;
        snapshot.currentTrackInstanceId = 0;
        snapshot.currentTrackGetterAvailable = currentTrackGetter != null;
        snapshot.sceneDefObserved = false;
        snapshot.currentSceneName = null;
        snapshot.teleporterObserved = false;
        snapshot.teleporterIdleObserved = false;
        snapshot.teleporterIdle = false;
        snapshot.sceneTrackGateObserved = false;
        snapshot.sceneMainTrackPresent = false;
        snapshot.sceneBossTrackPresent = false;
        snapshot.sceneTrackCandidateKind = null;
        snapshot.sceneTrackCandidateName = null;
        snapshot.sceneTrackHookObservationKnown = false;
        snapshot.sceneTrackHookPresent = false;
        snapshot.ownedListenerObserved = false;
        snapshot.ownedListenerEnabled = false;
        snapshot.ownedListenerDefault = false;
        snapshot.ownedListenerMembershipObserved = false;
        snapshot.ownedListenerInManagedDefaultList = false;
        snapshot.managedDefaultListenerCountObserved = false;
        snapshot.managedDefaultListenerCount = 0;
        if (snapshot.sourceMusicParameters != null)
            foreach (Snapshot.SourceMusicParameterObservation item in snapshot.sourceMusicParameters)
            {
                item.valueObserved = false;
                item.value = 0f;
                item.sampleRealtime = 0f;
            }
        if (failure != null && snapshot.globalRtpcs != null)
            foreach (Snapshot.RtpcObservation item in snapshot.globalRtpcs)
            {
                item.queryAttempted = false;
                item.resultObserved = false;
                item.valueObserved = false;
                item.resultCode = 0;
                item.requestedValueType = -1;
                item.returnedValueType = -1;
                item.value = 0f;
                item.sampleRealtime = 0f;
            }
    }

    void ObserveSourceMusicParameters(float now)
    {
        if (musicRtpcFields == null || musicRtpcValueField == null || snapshot.sourceMusicParameters == null)
            return;
        for (int i = 0; i < snapshot.sourceMusicParameters.Length; i++)
        {
            Snapshot.SourceMusicParameterObservation item = snapshot.sourceMusicParameters[i];
            item.sampleRealtime = now;
            item.valueObserved = false;
            item.value = 0f;
            FieldInfo source = i < musicRtpcFields.Length ? musicRtpcFields[i] : null;
            if (source == null)
                continue;
            try
            {
                object setter = source.GetValue(ownedController);
                if (setter == null)
                    continue;
                float value = (float)musicRtpcValueField.GetValue(setter);
                if (Single.IsNaN(value) || Single.IsInfinity(value))
                    continue;
                item.value = value;
                item.valueObserved = true;
            }
            catch
            {
                item.valueObserved = false;
            }
        }
    }

    void ObserveOwnedListenerMembership()
    {
        AkAudioListener listener = ownedControllerRoot ? ownedControllerRoot.GetComponent<AkAudioListener>() : null;
        snapshot.ownedListenerObserved = listener;
        snapshot.ownedListenerEnabled = listener && listener.isActiveAndEnabled;
        snapshot.ownedListenerDefault = listener && listener.isDefaultListener;
        snapshot.ownedListenerMembershipObserved = false;
        snapshot.ownedListenerInManagedDefaultList = false;
        snapshot.managedDefaultListenerCountObserved = false;
        snapshot.managedDefaultListenerCount = 0;
        if (!listener)
            return;
        try
        {
            var listeners = AkAudioListener.DefaultListeners.ListenerList;
            if (listeners == null)
                return;
            snapshot.managedDefaultListenerCount = listeners.Count;
            snapshot.managedDefaultListenerCountObserved = true;
            snapshot.ownedListenerInManagedDefaultList = listeners.Contains(listener);
            snapshot.ownedListenerMembershipObserved = true;
        }
        catch
        {
            snapshot.ownedListenerMembershipObserved = false;
            snapshot.managedDefaultListenerCountObserved = false;
        }
    }

    void ObserveGlobalRtpcs(float now)
    {
        if (snapshot.globalRtpcs == null)
            return;
        foreach (Snapshot.RtpcObservation item in snapshot.globalRtpcs)
        {
            item.sampleRealtime = now;
            item.queryAttempted = false;
            item.resultObserved = false;
            item.valueObserved = false;
            item.resultCode = 0;
            item.returnedValueType = -1;
            item.requestedValueType = (int)AkQueryRTPCValue.RTPCValue_Global;
            item.value = 0f;
            if (!snapshot.engineInitialized)
                continue;
            item.queryAttempted = true;
            int valueType = item.requestedValueType;
            float value;
            try
            {
                AKRESULT result = AkSoundEngine.GetRTPCValue(item.name,
                    AkSoundEngine.AK_INVALID_GAME_OBJECT, AkSoundEngine.AK_INVALID_PLAYING_ID,
                    out value, ref valueType);
                item.resultObserved = true;
                item.resultCode = (int)result;
                item.returnedValueType = valueType;
                item.valueObserved = IsSuccessfulGlobalRtpcRead(result, value, valueType);
                if (item.valueObserved)
                    item.value = value;
            }
            catch
            {
                // A diagnostic query failure stays unknown and cannot interrupt the source owner.
                item.resultObserved = false;
                item.valueObserved = false;
            }
        }
    }

    internal static string ClassifySceneTrackCandidate(bool musicEnabled, bool sceneObserved,
        bool teleporterObserved, bool teleporterIsIdle, bool bossTrackPresent, bool mainTrackPresent)
    {
        if (!musicEnabled) return "music_disabled";
        if (!sceneObserved) return "scene_missing";
        if (teleporterObserved && !teleporterIsIdle && bossTrackPresent) return "boss_track";
        if (mainTrackPresent) return "main_track";
        return "no_scene_track";
    }

    internal static bool IsSuccessfulGlobalRtpcRead(AKRESULT result, float value, int valueType)
    {
        return result == AKRESULT.AK_Success && valueType == (int)AkQueryRTPCValue.RTPCValue_Global &&
            !Single.IsNaN(value) && !Single.IsInfinity(value);
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
        RetireOriginalStartupTrigger();
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
        // Teardown and report saving can share a frame before another Update.
        // Invalidate live context immediately without sampling or native queries.
        instance.ExpireMusicObservationIfOwnerMissing();
        return instance.snapshot;
    }
}
