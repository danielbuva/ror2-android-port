// Opt-in view-only owner using the accepted original Main Camera prefab.
// It preserves the native body, team, CameraTargetParams, PlayerBasic mode,
// SceneCamera and camera callback graph; it never creates a game user.
using System;
using System.Collections;
using System.Globalization;
using System.Reflection;
using RoR2;
using RoR2.CameraModes;
using UnityEngine;

[DefaultExecutionOrder(-10000)]
public sealed class AndroidNativeSourceCameraRigOwner : MonoBehaviour, ICameraStateProvider, IOriginalWwiseCameraListenerState
{
    const string MainCameraPath = "Prefabs/Main Camera";
    const int DisplayLayer = 30;

    public Camera viewCamera { get; private set; }
    public Camera poseCamera { get; private set; }
    public CameraRigController cameraRig { get; private set; }
    public string status { get; private set; }
    public bool ready { get; private set; }

    CharacterBody expectedBody;
    SceneCamera sceneCamera;
    Component guardMarker;
    GameObject stagingRoot;
    Camera previousGlobalSceneCamera;
    bool capturedGlobalSceneCamera, viewReady, overrideInstalled, audioComponentPolicyVerified, terminallyRetired;
    Component sourceDefaultListener, sourceAkGameObject;
    bool sourceDefaultListenerPreserved;
    public bool managedSourceDefaultListenerObserved { get; private set; }
    public ulong sourceDefaultListenerGameObjectId { get; private set; }
    public bool managedSourceDefaultListenerReferencePresent { get; private set; }
    public bool managedSourceDefaultListenerObservationCaptured { get; private set; }
    public bool managedSourceDefaultListenerPresentBeforeDisableCaptured { get; private set; }
    public bool managedSourceDefaultListenerPresentBeforeDisable { get; private set; }
    public bool sourceDefaultListenerInactiveAfterDisable { get; private set; }
    public bool managedSourceDefaultListenerPresentAfterDisableCaptured { get; private set; }
    public bool managedSourceDefaultListenerPresentAfterDisable { get; private set; }
    public bool sourceDefaultListenerTeardownObserved { get; private set; }
    public string sourceDefaultListenerLifecycleState { get; private set; } = "owner_unavailable";
    public string nativeDefaultListenerRegistrationOutcome { get; private set; } = "not_observed_original_wrapper_discards_AKRESULT";
    public string nativeDefaultListenerRemovalOutcome { get; private set; } = "not_observed_original_wrapper_discards_AKRESULT";
    bool sourceListenerTeardownStarted;
    public bool sourceConsoleConfigurationUnavailable { get; private set; }
    public string sourceCameraFidelityState { get; private set; } = "unprepared";

    bool IOriginalWwiseCameraListenerState.ListenerStateEvidenceCaptured => true;
    bool IOriginalWwiseCameraListenerState.SourceDefaultListenerPreserved => sourceDefaultListenerPreserved;
    bool IOriginalWwiseCameraListenerState.SourceDefaultListenerGameObjectIdValid =>
        sourceDefaultListenerPreserved && sourceDefaultListenerGameObjectId != ulong.MaxValue;
    string IOriginalWwiseCameraListenerState.SourceDefaultListenerGameObjectIdText =>
        sourceDefaultListenerPreserved && sourceDefaultListenerGameObjectId != ulong.MaxValue
            ? sourceDefaultListenerGameObjectId.ToString(CultureInfo.InvariantCulture) : string.Empty;
    bool IOriginalWwiseCameraListenerState.SourceDefaultListenerActive =>
        sourceDefaultListener && sourceDefaultListener is Behaviour behaviour && behaviour.isActiveAndEnabled;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerObservationCaptured => managedSourceDefaultListenerObservationCaptured;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerContainsExactReference => managedSourceDefaultListenerReferencePresent;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured => managedSourceDefaultListenerPresentBeforeDisableCaptured;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerContainsExactReferenceBeforeDisable => managedSourceDefaultListenerPresentBeforeDisable;
    bool IOriginalWwiseCameraListenerState.SourceDefaultListenerInactiveAfterDisable => sourceDefaultListenerInactiveAfterDisable;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured => managedSourceDefaultListenerPresentAfterDisableCaptured;
    bool IOriginalWwiseCameraListenerState.ManagedDefaultListenerContainsExactReferenceAfterDisable => managedSourceDefaultListenerPresentAfterDisable;
    bool IOriginalWwiseCameraListenerState.SourceDefaultListenerTeardownObserved => sourceDefaultListenerTeardownObserved;
    string IOriginalWwiseCameraListenerState.SourceDefaultListenerLifecycleState => sourceDefaultListenerLifecycleState;
    string IOriginalWwiseCameraListenerState.NativeDefaultListenerAddOutcome => nativeDefaultListenerRegistrationOutcome;
    string IOriginalWwiseCameraListenerState.NativeDefaultListenerRemoveOutcome => nativeDefaultListenerRemovalOutcome;
    Vector3 cameraLocalPosition;
    Quaternion cameraLocalRotation;

    public static AndroidNativeSourceCameraRigOwner Create(Transform ownerRoot, CharacterBody body,
                                                            bool explicitlyRequested, bool selectedSourceModel, bool actualModel,
                                                            AndroidNativeSourceSkinLifecycle.Report sourceReport)
    {
        if (!AndroidNativeSourceCameraRigContract.ShouldCreate(explicitlyRequested, selectedSourceModel, actualModel))
            throw Refuse(sourceReport, "view-only native camera requires an explicit request for the selected actual source model");
        if (!ownerRoot || !body || !body.teamComponent || !body.GetComponent<CameraTargetParams>())
            throw Refuse(sourceReport, "view-only native camera requires the exact source body, team, and original camera parameters");
        bool audioModeCompatible = IsOriginalAudioModeCompatible();
        if (!audioModeCompatible)
            throw Refuse(sourceReport, "view-only camera requires unrequested default-off audio or the original audio owner's complete Ready state; pending, failed, and terminated audio are refused");

        var currentRigs = CameraRigController.readOnlyInstancesList;
        bool inventoryComplete = currentRigs != null && currentRigs.Count <= 32;
        int existingRigsForBody = CountActiveRigsForBody(body);
        if (!AndroidNativeSourceCameraRigContract.CanCreateDedicatedRig(explicitlyRequested, actualModel,
                                                                         audioModeCompatible,
                                                                         inventoryComplete, existingRigsForBody))
            throw Refuse(sourceReport, "cannot add a view-only camera until the active original-rig inventory is complete and none targets this body");

        GameObject prefab = LegacyResourcesAPI.Load<GameObject>(MainCameraPath);
        if (!prefab)
            throw Refuse(sourceReport, "accepted original Main Camera prefab is unavailable");

        var staging = new GameObject("Nova native view-only camera staging");
        staging.transform.SetParent(ownerRoot, false);
        staging.SetActive(false);
        AndroidNativeSourceCameraRigOwner owner = null;
        try
        {
            var clone = UnityEngine.Object.Instantiate(prefab, staging.transform, false);
            var rig = clone.GetComponent<CameraRigController>();
            if (!rig || !rig.sceneCam || !rig.sprintingParticleSystem)
                throw new InvalidOperationException("Original Main Camera prefab lacks CameraRigController, SceneCamera camera, or sprint callback owner");
            var camera = rig.sceneCam;
            var scene = camera.GetComponent<SceneCamera>();
            if (!scene)
                throw new InvalidOperationException("Original Main Camera camera lacks its source SceneCamera component");
            var preparedCamera = AndroidNativeSourceCameraPrerequisites.Prepare(scene, out var prerequisiteFailure);
            if (preparedCamera == null)
                throw new InvalidOperationException("original camera prerequisites unavailable: " + prerequisiteFailure);

            rig.createHud = false;
            rig.enableMusic = false;
            rig.viewer = null;
            rig.nextTarget = body.gameObject;
            var uiObject = rig.uiCam ? rig.uiCam.gameObject : null;
            rig.uiCam = null;
            if (uiObject)
                UnityEngine.Object.DestroyImmediate(uiObject);
            var spectate = clone.GetComponent<CameraRigControllerSpectateControls>();
            if (spectate)
                UnityEngine.Object.DestroyImmediate(spectate);
            // Keep the exact source AkGameObj/AkAudioListener pair only after
            // the original owner and native engine are ready. The source
            // components retain their own Awake/OnEnable/OnDisable/OnDestroy
            // behavior; this owner never calls a native listener API itself.
            bool audioOwnerReady = GameAudioOriginalOwner.OptInRequested && GameAudioOriginalOwner.Ready &&
                !WwiseIntegrationManager.noAudio && !GameAudioOriginalOwner.HasTerminalFailure &&
                !GameAudioOriginalOwner.OriginalTermsReturned;
            bool engineInitialized = AkSoundEngine.IsInitialized();
            if (audioOwnerReady && !engineInitialized)
                throw new InvalidOperationException("original audio owner reports Ready while the current native engine query is false");
            int listenerCount, gameObjectCount;
            bool listenerIsDefault, sameCameraObject;
            bool exactSourcePair = TryGetExactSourceDefaultListenerPair(clone, camera, out var sourceListener,
                out var sourceAkGameObject, out listenerCount, out gameObjectCount, out listenerIsDefault, out sameCameraObject);
            bool preserveSourceListener = OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
                GameAudioOriginalOwner.OptInRequested, GameAudioOriginalOwner.Ready, WwiseIntegrationManager.noAudio,
                GameAudioOriginalOwner.OriginalTermsReturned, engineInitialized,
                MainCameraPath == "Prefabs/Main Camera",
                listenerCount, gameObjectCount, listenerIsDefault, sameCameraObject);
            if (audioOwnerReady && (!exactSourcePair || !preserveSourceListener))
                throw new InvalidOperationException("ready original audio requires the exact pinned default listener and AkGameObj pair from the Main Camera prefab");
            if (preserveSourceListener)
            {
                if (!exactSourcePair)
                    throw new InvalidOperationException("accepted original Main Camera listener/AK game-object pair changed or is not colocated on its SceneCamera");
                if (!owner)
                    owner = clone.AddComponent<AndroidNativeSourceCameraRigOwner>();
                owner.sourceDefaultListener = sourceListener;
                owner.sourceAkGameObject = sourceAkGameObject;
                owner.sourceDefaultListenerPreserved = true;
                owner.sourceDefaultListenerGameObjectId = ulong.MaxValue;
                owner.sourceDefaultListenerLifecycleState = "source_pair_preserved_pending_activation";
                RemoveUnityAudioListeners(clone);
                if (!TryGetExactSourceDefaultListenerPair(clone, camera, out _, out _, out listenerCount,
                    out gameObjectCount, out listenerIsDefault, out sameCameraObject) || HasUnityAudioListeners(clone))
                    throw new InvalidOperationException("source Wwise listener pair was not preserved exactly or a Unity AudioListener remains");
            }
            else
            {
                RemoveOwnedAudioComponents(clone);
                if (!HasNoOwnedAudioComponents(clone))
                    throw new InvalidOperationException("default-off diagnostic clone still contains an audio listener or Wwise object after isolation");
            }

            Vector3 cameraOffset = rig.transform.InverseTransformPoint(camera.transform.position);
            Quaternion cameraRotationOffset = Quaternion.Inverse(rig.transform.rotation) * camera.transform.rotation;
            camera.enabled = false;
            camera.depth = 100;
            camera.cullingMask = 1 << DisplayLayer;

            if (!owner)
                owner = clone.AddComponent<AndroidNativeSourceCameraRigOwner>();
            var marker = AddAndBindOptionalMarker(rig.gameObject, rig, body.gameObject, owner);
            if (!marker)
                throw new InvalidOperationException("current RoR2 module does not contain the exact merged view-only rig marker; destination rebuilds keep camera opt-in unavailable");
            var pose = new GameObject("Nova native view pose").AddComponent<Camera>();
            pose.transform.SetParent(staging.transform, false);
            pose.enabled = false;
            pose.cullingMask = 1 << DisplayLayer;
            pose.orthographic = false;
            pose.nearClipPlane = .05f;
            pose.farClipPlane = 600f;

            owner.Bind(staging, body, rig, scene, camera, pose, marker, cameraOffset, cameraRotationOffset);
            owner.audioComponentPolicyVerified = preserveSourceListener
                ? TryGetExactSourceDefaultListenerPair(clone, camera, out _, out _, out listenerCount,
                    out gameObjectCount, out listenerIsDefault, out sameCameraObject) && !HasUnityAudioListeners(clone)
                : HasNoOwnedAudioComponents(clone);
            if (!owner.audioComponentPolicyVerified)
                throw new InvalidOperationException("camera audio-component policy could not be verified before activation");
            owner.previousGlobalSceneCamera = SceneCamera._camera;
            owner.capturedGlobalSceneCamera = true;
            var activationScope = AndroidNativeSourceCameraPrerequisites.BeginOwnedViewActivation(preparedCamera);
            try
            {
                staging.SetActive(true);
            }
            finally
            {
                activationScope.Dispose();
                owner.sourceConsoleConfigurationUnavailable = activationScope.ConsoleConfigurationUnavailable;
                owner.sourceCameraFidelityState = owner.sourceConsoleConfigurationUnavailable
                    ? "source_prefab_defaults_console_unavailable_reduced_fidelity"
                    : "original_console_configuration_applied";
            }
            owner.CaptureManagedSourceListenerState();
            owner.RestoreGlobalSceneCameraPointer();
            owner.status = owner.WithCameraFidelity(preserveSourceListener
                ? owner.managedSourceDefaultListenerObserved
                    ? "original prefab listener lifecycle preserved; exact listener is in the managed default list; native registration result is unobserved, so no spatial PCM claim is permitted"
                    : "original prefab listener lifecycle preserved; exact managed default-list membership was not observed; no spatial PCM claim is permitted"
                : "waiting for original PlayerBasic target/team and configured native view pose; default-off audio components are isolated; audio spatialization is outside this view-only diagnostic");
            if (!preserveSourceListener)
                owner.sourceDefaultListenerLifecycleState = "not_preserved_default_off";
            return owner;
        }
        catch (Exception exception)
        {
            if (owner)
                owner.RestoreGlobalSceneCameraPointer();
            if (staging)
                UnityEngine.Object.DestroyImmediate(staging);
            sourceReport?.Fail(exception.Message);
            throw;
        }
    }


    const string ViewOnlyMarkerTypeName = "RoR2.AndroidNativeSourceViewOnlyRigMarker";
    static bool markerContractResolved;
    static Type markerTypeCache;
    static FieldInfo markerRigField, markerTargetField, markerOwnerField;
    static MethodInfo markerContextReadyMethod;
    static bool cameraGateFieldsResolved;
    static Type cameraGateFieldsType;
    static FieldInfo cameraGateEarlyUpdateField, cameraGateContextReadyField, cameraGatePumpCountField;
    static string cameraGateFieldsFailure;

    static Type ResolveOptionalMarkerType()
    {
        if (markerContractResolved)
            return markerTypeCache;
        markerContractResolved = true;
        var markerType = typeof(CameraRigController).Assembly.GetType(ViewOnlyMarkerTypeName, false, false);
        if (markerType == null || !typeof(MonoBehaviour).IsAssignableFrom(markerType))
            return null;
        const BindingFlags fields = BindingFlags.Instance | BindingFlags.NonPublic;
        markerRigField = markerType.GetField("rig", fields);
        markerTargetField = markerType.GetField("target", fields);
        markerOwnerField = markerType.GetField("ownerProvider", fields);
        var isBound = markerType.GetMethod("IsBoundTo", BindingFlags.Instance | BindingFlags.Public, null,
            new[] { typeof(CameraRigController), typeof(GameObject), typeof(ICameraStateProvider) }, null);
        var contextReady = markerType.GetMethod("IsOriginalUpdateContextReadyFor", BindingFlags.Instance | BindingFlags.Public, null,
            new[] { typeof(CameraRigController), typeof(GameObject), typeof(ICameraStateProvider) }, null);
        if (markerRigField == null || markerRigField.FieldType != typeof(CameraRigController) ||
            markerTargetField == null || markerTargetField.FieldType != typeof(GameObject) ||
            markerOwnerField == null || markerOwnerField.FieldType != typeof(ICameraStateProvider) ||
            isBound == null || isBound.ReturnType != typeof(bool) || contextReady == null || contextReady.ReturnType != typeof(bool))
            return null;
        markerContextReadyMethod = contextReady;
        markerTypeCache = markerType;
        return markerTypeCache;
    }

    // Resolve optional snapshot-only fields independently from the mandatory
    // marker binding contract above. Missing observation fields never prevent
    // creation of a rig that satisfies the existing binding contract.
    static bool ResolveCameraGateObservationFields(Type markerType, out string failure)
    {
        failure = null;
        if (cameraGateFieldsResolved && cameraGateFieldsType == markerType)
        {
            failure = cameraGateFieldsFailure;
            return string.IsNullOrEmpty(failure);
        }
        cameraGateFieldsResolved = true;
        cameraGateFieldsType = markerType;
        cameraGateEarlyUpdateField = null;
        cameraGateContextReadyField = null;
        cameraGatePumpCountField = null;
        const BindingFlags fields = BindingFlags.Instance | BindingFlags.NonPublic;
        if (markerType == null)
            cameraGateFieldsFailure = "exact marker type unavailable for optional camera gate observation";
        else
        {
            var earlyUpdate = markerType.GetField("originalEarlyUpdate", fields);
            var contextReady = markerType.GetField("originalContextReady", fields);
            var pumpCount = markerType.GetField("originalEarlyUpdatePumpCount", fields);
            if (earlyUpdate == null || earlyUpdate.FieldType != typeof(Action))
                cameraGateFieldsFailure = "optional marker originalEarlyUpdate field missing or not Action";
            else if (contextReady == null || contextReady.FieldType != typeof(bool))
                cameraGateFieldsFailure = "optional marker originalContextReady field missing or not Boolean";
            else if (pumpCount == null || pumpCount.FieldType != typeof(int))
                cameraGateFieldsFailure = "optional marker originalEarlyUpdatePumpCount field missing or not Int32";
            else
            {
                cameraGateEarlyUpdateField = earlyUpdate;
                cameraGateContextReadyField = contextReady;
                cameraGatePumpCountField = pumpCount;
                cameraGateFieldsFailure = null;
            }
        }
        failure = cameraGateFieldsFailure;
        return string.IsNullOrEmpty(failure);
    }

    // Read-only bounded fields collected only by the visual-report snapshot.
    // This never invokes the captured callback or writes any native state.
    public void CaptureUpdateContextObservation(AndroidNativeSourceSkinLifecycle.VisualSnapshot snapshot)
    {
        if (snapshot == null)
            return;
        snapshot.cameraGateObservationRequested = true;
        try
        {
            if (!cameraRig || !expectedBody)
                throw new InvalidOperationException("owned rig or expected body unavailable");
            var expectedTarget = expectedBody.gameObject;
            snapshot.cameraGateExpectedTargetInstanceId = expectedTarget ? expectedTarget.GetInstanceID() : 0;
            snapshot.cameraGateNextTargetInstanceId = cameraRig.nextTarget ? cameraRig.nextTarget.GetInstanceID() : 0;
            snapshot.cameraGateTargetInstanceId = cameraRig.target ? cameraRig.target.GetInstanceID() : 0;
            snapshot.cameraGateNextTargetMatchesExpected = ReferenceEquals(cameraRig.nextTarget, expectedTarget);
            snapshot.cameraGateNextTargetKnown = true;
            snapshot.cameraGateTargetMatchesExpected = ReferenceEquals(cameraRig.target, expectedTarget);
            snapshot.cameraGateTargetKnown = true;
            snapshot.cameraGateRigActive = cameraRig.isActiveAndEnabled && cameraRig.gameObject.activeInHierarchy;
            snapshot.cameraGateRigActiveKnown = true;
            snapshot.cameraGateProviderActive = isActiveAndEnabled && gameObject == cameraRig.gameObject;
            snapshot.cameraGateProviderActiveKnown = true;
            snapshot.cameraGateCutsceneKnown = true;
            snapshot.cameraGateIsCutscene = cameraRig.isCutscene;

            var application = RoR2Application.instance;
            snapshot.cameraGateApplicationPresent = application;
            snapshot.cameraGateApplicationKnown = true;
            snapshot.cameraGateApplicationActive = application && application.isActiveAndEnabled;
            snapshot.cameraGateApplicationActiveKnown = true;
            float deltaTime = Time.deltaTime;
            if (float.IsNaN(deltaTime) || float.IsInfinity(deltaTime))
                throw new InvalidOperationException("camera update delta time is non-finite");
            snapshot.cameraGateDeltaTime = deltaTime;
            snapshot.cameraGateDeltaTimeNonzero = deltaTime != 0f;
            snapshot.cameraGateDeltaTimeKnown = true;

            var marker = guardMarker as MonoBehaviour;
            snapshot.cameraGateMarkerPresent = marker;
            snapshot.cameraGateMarkerPresentKnown = true;
            if (!marker)
                throw new InvalidOperationException("owned view-only marker unavailable");
            snapshot.cameraGateMarkerActive = marker.isActiveAndEnabled;
            snapshot.cameraGateMarkerActiveKnown = true;
            var markerType = ResolveOptionalMarkerType();
            if (markerType == null || marker.GetType() != markerType ||
                markerRigField == null || markerTargetField == null || markerOwnerField == null)
                throw new InvalidOperationException("existing marker binding contract unavailable for observation");

            object markerRig = markerRigField.GetValue(marker);
            object markerTarget = markerTargetField.GetValue(marker);
            object markerOwner = markerOwnerField.GetValue(marker);
            snapshot.cameraGateMarkerBoundToRig = ReferenceEquals(markerRig, cameraRig);
            snapshot.cameraGateMarkerBoundToTarget = ReferenceEquals(markerTarget, expectedTarget);
            snapshot.cameraGateMarkerBoundToProvider = ReferenceEquals(markerOwner, (ICameraStateProvider)this);
            snapshot.cameraGateMarkerBindingKnown = true;

            if (!ResolveCameraGateObservationFields(markerType, out var fieldFailure))
                throw new InvalidOperationException(fieldFailure ?? "optional marker observation fields unavailable");
            object callback = cameraGateEarlyUpdateField.GetValue(marker);
            if (callback != null && !(callback is Action))
                throw new InvalidOperationException("optional originalEarlyUpdate value has wrong runtime type");
            snapshot.cameraGateDelegatePresent = callback is Action;
            snapshot.cameraGateDelegateKnown = true;

            object contextReady = cameraGateContextReadyField.GetValue(marker);
            if (!(contextReady is bool))
                throw new InvalidOperationException("optional originalContextReady value has wrong runtime type");
            snapshot.cameraGateContextReady = (bool)contextReady;
            snapshot.cameraGateContextReadyKnown = true;

            object pumpCount = cameraGatePumpCountField.GetValue(marker);
            if (!(pumpCount is int))
                throw new InvalidOperationException("optional marker pump counter value has wrong runtime type");
            snapshot.cameraGatePumpCount = (int)pumpCount;
            snapshot.cameraGatePumpCountKnown = true;
        }
        catch (Exception error)
        {
            snapshot.cameraGateCaptureError = ShortText(error.GetBaseException().Message, 160);
        }
    }

    static string ShortText(string value, int maxLength)
    {
        if (string.IsNullOrEmpty(value))
            return string.Empty;
        return value.Length <= maxLength ? value : value.Substring(0, maxLength);
    }

    static Component AddAndBindOptionalMarker(GameObject rigObject, CameraRigController rig,
                                               GameObject target, ICameraStateProvider owner)
    {
        var markerType = ResolveOptionalMarkerType();
        if (markerType == null)
            return null;
        var marker = rigObject.AddComponent(markerType);
        if (markerRigField.GetValue(marker) != null || markerTargetField.GetValue(marker) != null ||
            markerOwnerField.GetValue(marker) != null)
            throw new InvalidOperationException("exact merged view-only rig marker is already bound");
        markerRigField.SetValue(marker, rig);
        markerTargetField.SetValue(marker, target);
        markerOwnerField.SetValue(marker, owner);
        if (!ReferenceEquals(markerRigField.GetValue(marker), rig) ||
            !ReferenceEquals(markerTargetField.GetValue(marker), target) ||
            !ReferenceEquals(markerOwnerField.GetValue(marker), owner))
            throw new InvalidOperationException("exact merged view-only rig marker could not retain its owner binding");
        return marker;
    }

    string WithCameraFidelity(string value)
    {
        string fidelity = sourceCameraFidelityState == "source_prefab_defaults_console_unavailable_reduced_fidelity"
            ? "reduced fidelity: source-prefab defaults; original Console absent"
            : sourceCameraFidelityState == "original_console_configuration_applied"
                ? "original Console camera configuration applied"
                : "camera configuration state unavailable";
        return fidelity + "; " + value;
    }

    static InvalidOperationException Refuse(AndroidNativeSourceSkinLifecycle.Report report, string reason)
    {
        report?.Fail(reason);
        return new InvalidOperationException(reason);
    }

    static void RemoveOwnedAudioComponents(GameObject root)
    {
        foreach (var listener in root.GetComponentsInChildren<AudioListener>(true))
            if (listener)
                UnityEngine.Object.DestroyImmediate(listener);
        foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
        {
            if (!component)
                continue;
            if (IsOriginalWwiseComponent(component, "AkAudioListener") ||
                IsOriginalWwiseComponent(component, "AkGameObj"))
                UnityEngine.Object.DestroyImmediate(component);
        }
    }

    void Bind(GameObject staging, CharacterBody body, CameraRigController rig, SceneCamera nativeScene,
              Camera camera, Camera pose, Component marker,
              Vector3 cameraOffset, Quaternion cameraRotationOffset)
    {
        stagingRoot = staging;
        expectedBody = body;
        cameraRig = rig;
        sceneCamera = nativeScene;
        viewCamera = camera;
        poseCamera = pose;
        guardMarker = marker;
        cameraLocalPosition = cameraOffset;
        cameraLocalRotation = cameraRotationOffset;
    }

    public void MarkViewReady()
    {
        viewReady = true;
    }

    static bool IsOriginalAudioModeCompatible()
    {
        return AndroidNativeSourceCameraRigContract.IsAudioModeCompatible(
            WwiseIntegrationManager.noAudio,
            GameAudioOriginalOwner.OptInRequested,
            GameAudioOriginalOwner.Ready,
            GameAudioOriginalOwner.HasTerminalFailure,
            GameAudioOriginalOwner.OriginalTermsReturned);
    }

    static bool HasUnityAudioListeners(GameObject root)
    {
        return root && root.GetComponentsInChildren<AudioListener>(true).Length != 0;
    }

    static void RemoveUnityAudioListeners(GameObject root)
    {
        foreach (var listener in root.GetComponentsInChildren<AudioListener>(true))
            if (listener)
                UnityEngine.Object.DestroyImmediate(listener);
    }

    static bool TryGetExactSourceDefaultListenerPair(GameObject root, Camera sceneCamera,
        out Component listener, out Component akGameObject, out int listenerCount, out int gameObjectCount,
        out bool listenerIsDefault, out bool sameCameraObject)
    {
        listener = null;
        akGameObject = null;
        listenerCount = 0;
        gameObjectCount = 0;
        listenerIsDefault = false;
        sameCameraObject = false;
        if (!root || !sceneCamera)
            return false;
        foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
        {
            if (!component)
                continue;
            if (IsOriginalWwiseComponent(component, "AkAudioListener")) { listenerCount++; listener = component; }
            else if (IsOriginalWwiseComponent(component, "AkGameObj")) { gameObjectCount++; akGameObject = component; }
        }
        if (listenerCount != 1 || gameObjectCount != 1 || !listener || !akGameObject)
            return false;
        sameCameraObject = listener.gameObject == sceneCamera.gameObject && akGameObject.gameObject == sceneCamera.gameObject;
        var defaultField = listener.GetType().GetField("isDefaultListener", BindingFlags.Instance | BindingFlags.Public);
        listenerIsDefault = defaultField != null && defaultField.FieldType == typeof(bool) && (bool)defaultField.GetValue(listener);
        return sameCameraObject && listenerIsDefault;
    }

    static bool IsOriginalWwiseComponent(Component component, string exactTypeName)
    {
        if (!component)
            return false;
        Type type = component.GetType();
        return type.FullName == exactTypeName &&
               type.Assembly.GetName().Name == "AK.Wwise.Unity.MonoBehaviour";
    }

    void CaptureManagedSourceListenerState()
    {
        managedSourceDefaultListenerObserved = false;
        if (!sourceDefaultListenerPreserved || !sourceDefaultListener || !sourceAkGameObject)
            return;
        var listenerType = sourceDefaultListener.GetType();
        var idMethod = listenerType.GetMethod("GetAkGameObjectID", BindingFlags.Instance | BindingFlags.Public,
            null, Type.EmptyTypes, null);
        if (idMethod == null || idMethod.ReturnType != typeof(ulong))
            return;
        sourceDefaultListenerGameObjectId = (ulong)idMethod.Invoke(sourceDefaultListener, null);
        bool found;
        managedSourceDefaultListenerObservationCaptured = TryReadExactManagedListenerMembership(out found);
        managedSourceDefaultListenerReferencePresent = found;
        var defaultField = listenerType.GetField("isDefaultListener", BindingFlags.Instance | BindingFlags.Public);
        bool isDefault = defaultField != null && defaultField.FieldType == typeof(bool) &&
                         (bool)defaultField.GetValue(sourceDefaultListener);
        bool engineInitialized = AkSoundEngine.IsInitialized();
        var listenerBehaviour = sourceDefaultListener as Behaviour;
        managedSourceDefaultListenerObserved = OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            GameAudioOriginalOwner.Ready, WwiseIntegrationManager.noAudio, engineInitialized,
            listenerBehaviour && listenerBehaviour.isActiveAndEnabled, isDefault,
            sourceAkGameObject != null && sourceAkGameObject.gameObject,
            sourceDefaultListenerGameObjectId != ulong.MaxValue, found);
        if (!sourceListenerTeardownStarted && managedSourceDefaultListenerObservationCaptured)
            sourceDefaultListenerLifecycleState = managedSourceDefaultListenerObserved
                ? "preserved_active_managed_list_member" : "preserved_but_active_membership_or_runtime_gate_unmet";
    }

    bool TryReadExactManagedListenerMembership(out bool found)
    {
        found = false;
        if (!sourceDefaultListener)
            return false;
        try
        {
            Type listenerType = sourceDefaultListener.GetType();
            var defaultListenersProperty = listenerType.GetProperty("DefaultListeners", BindingFlags.Static | BindingFlags.Public);
            var defaultListeners = defaultListenersProperty?.GetValue(null, null);
            var listProperty = defaultListeners?.GetType().GetProperty("ListenerList", BindingFlags.Instance | BindingFlags.Public);
            var list = listProperty?.GetValue(defaultListeners, null) as IList;
            if (list == null)
                return false;
            for (int i = 0; i < list.Count; i++)
                if (ReferenceEquals(list[i], sourceDefaultListener)) { found = true; break; }
            return true;
        }
        catch
        {
            return false;
        }
    }

    void LateUpdate()
    {
        if (terminallyRetired)
            return;
        bool audioModeCompatible = IsOriginalAudioModeCompatible();
        if (sourceDefaultListenerPreserved)
        {
            // Readiness can be lost after admission. Retire the preserved source
            // pair through Unity's existing OnDisable path and snapshot the
            // resulting managed-list state; never issue a second native removal.
            bool nativeEngineInitialized = AkSoundEngine.IsInitialized();
            if (OriginalWwiseCameraListenerContract.ShouldClosePreservedSourceListener(
                sourceDefaultListenerPreserved, audioModeCompatible, nativeEngineInitialized))
            {
                string reason = !audioModeCompatible
                    ? "original audio owner readiness ended"
                    : "original Wwise engine is no longer initialized";
                RetireOwnedView(reason + "; source listener teardown state: " + sourceDefaultListenerLifecycleState +
                    "; native removal result remains unobserved");
                return;
            }
        }
        else if (!audioModeCompatible)
        {
            RetireOwnedView("original audio owner is pending, failed, or terminated; diagnostic view owner will not infer silent success");
            return;
        }
        if (!cameraRig || !expectedBody || !viewCamera || !sceneCamera || !guardMarker)
        {
            Refuse("owned original view-only rig or source body was destroyed");
            return;
        }
        if (!cameraRig.isActiveAndEnabled || !cameraRig.gameObject.activeInHierarchy ||
            cameraRig.cameraMode != CameraModePlayerBasic.playerBasic)
        {
            Refuse("owned prefab rig is not active in the original PlayerBasic camera mode");
            return;
        }
        // The source wrapper owns native Add/Remove calls. Re-read only its
        // managed list here; never issue a second native registration.
        CaptureManagedSourceListenerState();
        if (cameraRig.hasOverride && !cameraRig.IsOverrideCam(this))
        {
            Refuse("another original camera provider owns the view rig");
            return;
        }
        if (!viewReady || !poseCamera)
        {
            ready = false;
            RemoveOwnedOverride();
            if (viewCamera.enabled)
                viewCamera.enabled = false;
            status = WithCameraFidelity("native view pose is not configured");
            return;
        }
        // The original SetOverrideCam(null) path calls CameraModeBase.MatchState
        // using the rig's private context dictionary. Wait for the exact original
        // EarlyUpdate context before installing an override, so refusal/teardown
        // cannot enter that path with a default context.
        bool originalContextReady = markerContextReadyMethod != null && guardMarker &&
            (bool)markerContextReadyMethod.Invoke(guardMarker,
                new object[] { cameraRig, expectedBody.gameObject, (ICameraStateProvider)this });
        if (!originalContextReady)
        {
            if (ready || (cameraRig.hasOverride && cameraRig.IsOverrideCam(this)))
                RetireOwnedView("owned original CameraRigController context was lost after camera admission");
            else
            {
                ready = false;
                if (viewCamera.enabled)
                    viewCamera.enabled = false;
                status = WithCameraFidelity("waiting for the owned original CameraRigController update context");
            }
            return;
        }
        if (!overrideInstalled)
        {
            cameraRig.SetOverrideCam(this, 0f);
            overrideInstalled = cameraRig.IsOverrideCam(this);
        }

        var evidence = new AndroidNativeSourceCameraRigContract.Evidence {
            expectedTarget = expectedBody.gameObject,
            liveTarget = cameraRig.target,
            expectedBody = expectedBody,
            liveBody = cameraRig.targetBody,
            expectedTeam = (int)expectedBody.teamComponent.teamIndex,
            liveTeam = (int)cameraRig.targetTeamIndex,
            rigActive = cameraRig.isActiveAndEnabled && cameraRig.gameObject.activeInHierarchy,
            rigInventoryComplete = CameraRigController.readOnlyInstancesList != null &&
                                   CameraRigController.readOnlyInstancesList.Count <= 32,
            activeRigsTargetingBody = CountActiveRigsForBody(expectedBody),
            playerBasicMode = cameraRig.cameraMode == CameraModePlayerBasic.playerBasic,
            sceneCameraReady = sceneCamera.isActiveAndEnabled && viewCamera,
            sceneCameraComponentMatchesCamera = sceneCamera.camera == viewCamera,
            sceneCameraOwnsRig = sceneCamera.cameraRigController == cameraRig,
            cameraOwnedByRig = cameraRig.sceneCam == viewCamera &&
                               viewCamera.GetComponentInParent<CameraRigController>() == cameraRig,
            sprintParticleOwnerPresent = cameraRig.sprintingParticleSystem,
            viewOnlyNoViewer = cameraRig.viewer == null && cameraRig.localUserViewer == null,
            noHud = !cameraRig.createHud && !cameraRig.uiCam && !cameraRig.hud,
            originalControlAllowed = IsUserControlAllowed(cameraRig),
            originalHudAllowed = IsHudAllowed(cameraRig),
            audioComponentPolicySatisfied = audioComponentPolicyVerified,
            viewReady = viewReady && poseCamera,
            overrideOwned = cameraRig.IsOverrideCam(this),
        };
        if (!AndroidNativeSourceCameraRigContract.IsReady(evidence, out var failure))
        {
            Refuse(failure);
            return;
        }
        ready = true;
        if (!viewCamera.enabled)
            viewCamera.enabled = true;
        status = WithCameraFidelity(sourceDefaultListenerPreserved
            ? managedSourceDefaultListenerObserved
                ? "original prefab SceneCamera and PlayerBasic view active; source default listener is in the managed list; native registration result is unobserved, so spatial PCM is not claimed"
                : "original prefab SceneCamera and PlayerBasic view active; source listener is not in the observed managed default list; spatial PCM is not claimed"
            : "original prefab SceneCamera and PlayerBasic view active; default-off audio components remain isolated; spatial PCM is not claimed");
    }

    public bool IsOwnedNullViewerRig(CameraRigController candidate, GameObject target)
    {
        return candidate && expectedBody && cameraRig == candidate && viewCamera && sceneCamera && guardMarker &&
               viewerIsNull(candidate) && target == expectedBody.gameObject && candidate.target == target;
    }

    static bool viewerIsNull(CameraRigController rig) => rig && rig.localUserViewer == null;

    static int CountActiveRigsForBody(CharacterBody body)
    {
        var rigs = CameraRigController.readOnlyInstancesList;
        if (!body || rigs == null || rigs.Count > 32)
            return -1;
        int count = 0;
        for (int i = 0; i < rigs.Count; i++)
        {
            var rig = rigs[i];
            if (rig && rig.isActiveAndEnabled && rig.gameObject.activeInHierarchy &&
                (rig.target == body.gameObject || rig.targetBody == body))
                count++;
        }
        return count;
    }

    static bool HasNoOwnedAudioComponents(GameObject root)
    {
        if (!root || root.GetComponentsInChildren<AudioListener>(true).Length != 0)
            return false;
        foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
        {
            if (!component)
                continue;
            if (IsOriginalWwiseComponent(component, "AkAudioListener") ||
                IsOriginalWwiseComponent(component, "AkGameObj"))
                return false;
        }
        return true;
    }

    void Refuse(string reason)
    {
        if (cameraRig && cameraRig.IsOverrideCam(this) && !HasOriginalUpdateContext())
        {
            RetireOwnedView(reason + "; retiring owned rig because its original context is unavailable");
            return;
        }
        status = WithCameraFidelity(reason);
        ready = false;
        if (viewCamera)
            viewCamera.enabled = false;
        RemoveOwnedOverride();
    }

    void RetireOwnedView(string reason)
    {
        if (terminallyRetired)
            return;
        status = WithCameraFidelity(reason);
        terminallyRetired = true;
        DisposeOwnedView();
        // SetActive(false) above runs the original listener's OnDisable and
        // captures managed membership before destruction. The rig, marker, and
        // provider are all descendants of this one owned staging root, so
        // destroying it retires the stale override graph without invoking
        // SetOverrideCam(null) against an invalid CameraModeContext.
        var retiredRoot = stagingRoot;
        if (retiredRoot)
            Destroy(retiredRoot);
    }

    bool HasOriginalUpdateContext()
    {
        if (markerContextReadyMethod == null || !guardMarker || !cameraRig || !expectedBody)
            return false;
        object result = markerContextReadyMethod.Invoke(guardMarker,
            new object[] { cameraRig, expectedBody.gameObject, (ICameraStateProvider)this });
        return result is bool && (bool)result;
    }

    void RemoveOwnedOverride()
    {
        if (cameraRig && cameraRig.IsOverrideCam(this))
        {
            // Destroying the owned rig lets its original OnDestroy clear the
            // component-owned override when no valid original context remains.
            // Never ask SetOverrideCam(null) to MatchState against a default context.
            if (!HasOriginalUpdateContext())
                return;
            cameraRig.SetOverrideCam(null, 0f);
        }
        overrideInstalled = false;
    }

    public void GetCameraState(CameraRigController controller, ref CameraState state)
    {
        if (controller != cameraRig || !ready || !viewReady || !poseCamera)
            return;
        Quaternion rigRotation = poseCamera.transform.rotation * Quaternion.Inverse(cameraLocalRotation);
        Vector3 scaledOffset = cameraRig.transform.TransformVector(cameraLocalPosition);
        Vector3 adjustedOffset = rigRotation * Quaternion.Inverse(cameraRig.transform.rotation) * scaledOffset;
        state.position = poseCamera.transform.position - adjustedOffset;
        state.rotation = rigRotation;
        state.fov = poseCamera.fieldOfView;
    }

    public bool IsUserLookAllowed(CameraRigController controller) => false;
    public bool IsUserControlAllowed(CameraRigController controller) => true;
    public bool IsHudAllowed(CameraRigController controller) => true;

    public void DisposeOwnedView()
    {
        if (!sourceListenerTeardownStarted && sourceDefaultListenerPreserved)
        {
            sourceListenerTeardownStarted = true;
            CaptureManagedSourceListenerState();
            managedSourceDefaultListenerPresentBeforeDisableCaptured = managedSourceDefaultListenerObservationCaptured;
            managedSourceDefaultListenerPresentBeforeDisable = managedSourceDefaultListenerReferencePresent;
        }
        ready = false;
        audioComponentPolicyVerified = false;
        if (viewCamera)
            viewCamera.enabled = false;
        if (poseCamera)
            poseCamera.enabled = false;
        RemoveOwnedOverride();
        RestoreGlobalSceneCameraPointer();
        if (stagingRoot)
            stagingRoot.SetActive(false);
        if (sourceDefaultListenerPreserved)
        {
            var listenerBehaviour = sourceDefaultListener as Behaviour;
            sourceDefaultListenerInactiveAfterDisable = listenerBehaviour && !listenerBehaviour.isActiveAndEnabled;
            bool afterDisablePresent;
            managedSourceDefaultListenerPresentAfterDisableCaptured = TryReadExactManagedListenerMembership(out afterDisablePresent);
            managedSourceDefaultListenerPresentAfterDisable = afterDisablePresent;
            sourceDefaultListenerTeardownObserved = stagingRoot && !stagingRoot.activeSelf &&
                sourceDefaultListenerInactiveAfterDisable;
            sourceDefaultListenerLifecycleState = sourceDefaultListenerTeardownObserved
                ? managedSourceDefaultListenerPresentAfterDisable
                    ? "deactivated_managed_entry_retained"
                    : "deactivated_managed_entry_removed"
                : "deactivation_not_observed";
            CaptureManagedSourceListenerState();
        }
    }

    void RestoreGlobalSceneCameraPointer()
    {
        if (!capturedGlobalSceneCamera)
            return;
        if (SceneCamera._camera == viewCamera)
            SceneCamera._camera = previousGlobalSceneCamera ? previousGlobalSceneCamera : null;
        capturedGlobalSceneCamera = false;
    }

    void OnDestroy()
    {
        if (!sourceListenerTeardownStarted)
            DisposeOwnedView();
        ready = false;
        audioComponentPolicyVerified = false;
        RemoveOwnedOverride();
        RestoreGlobalSceneCameraPointer();
    }
}
