// Opt-in owner for the selected player's original async skin lifecycle plus Android material copies.
using System;
using System.Collections.Generic;
using RoR2;
using UnityEngine;

public sealed class AndroidNativeSourceSkinLifecycle : MonoBehaviour
{
    [Serializable]
    public sealed class SceneCameraCallbackRendererSample
    {
        public int rendererInstanceId, sharedMaterialInstanceId;
        public bool rendererExists, rendererActive, rendererEnabled, rendererVisible, sharedMaterialKnown;
    }
    [Serializable]
    public sealed class SceneCameraCallbackSnapshot
    {
        public string status;
        public int callbackCount, frame, sceneCameraInstanceId, cameraInstanceId, rigInstanceId;
        public int modelInstanceId, visibilityValue, invisibilityCount, rendererRecordCount, sampledRendererCount;
        public int trackedModelCount, trackedModelsScanned;
        public float realtime;
        public bool requested, subscriptionActive, callbackObserved, identityMatched, modelStateKnown, rendererJoinKnown;
        public bool modelActive, modelEnabled, forceUpdate;
        public bool trackedModelCountKnown, trackedModelMembershipKnown, trackedModelContainsSelected, trackedModelScanTruncated;
        public bool sharedMaterialCacheKnown, sharedMaterialCacheIsNull, sharedMaterialCacheBucketsComplete;
        public bool materialDirtyKnown, materialDirty;
        public int sharedMaterialCacheOuterLength = -1, sharedMaterialCacheBucketsScanned, sharedMaterialCacheNullBucketCount;
        public int[] sharedMaterialCacheBucketLengths;
        public string materialObservationError;
        public SceneCameraCallbackRendererSample[] renderers;
    }
    [Serializable]
    public sealed class Report
    {
        public SceneCameraCallbackSnapshot sceneCameraCallback;
        public bool requested, attached, nativeOwnersActive, selectedSkinReady, animatorInitialized, displayDeactivated, ownerDestroyed;
        public CharacterModelMaterialCacheOwner.Report materialCacheInitialization;
        public int selectedSkinIndex = -1, currentSkinIndex = -1;
        public string controllerIdentity, avatarIdentity, firstFailure, cameraAdmissionFailure;
        public int materialCopiesCreated, materialCopiesRetired, materialCopiesReleased;
        public VisualSnapshot visual;
        public void Fail(string reason)
        {
            if (string.IsNullOrEmpty(firstFailure) && !string.IsNullOrEmpty(reason))
                firstFailure = reason.Length > 256 ? reason.Substring(0, 256) : reason;
        }
    }
    [Serializable]
    public sealed class VisualRendererSnapshot
    {
        public int index, instanceId, layer, defaultShadowCastingMode, materialSlotCount, sampledMaterialCount, sampledNullMaterialSlots;
        public string rendererType, rendererName, meshIdentity, rendererRecordMaterialIdentity;
        public bool exists, active, enabled, visible, ignoreOverlays, materialsTruncated, sampledNamesTruncated, materialSlotCountKnown;
        public Vector3 boundsCenter, boundsExtents;
        public string[] materialIdentities;
        public bool screenBoundsKnown, crossesNearClip, hasBehindCameraCorner;
        public float screenMinX, screenMinY, screenMaxX, screenMaxY, viewMinZ, viewMaxZ;
        public int sampledNamedMaterialCount;
        public string[] sampledMaterialNames, sampledShaderNames;
    }
    [Serializable]
    public sealed class VisualCameraSnapshot
    {
        public int instanceId, clearFlags, cullingMask, targetDisplay;
        public bool exists, ownedSourceCamera, active, enabled, orthographic, targetTexturePresent, scalarValuesFinite;
        public float depth, nearClip, farClip, fieldOfView, rectX, rectY, rectWidth, rectHeight;
        public Vector3 position;
        public Quaternion rotation;
    }
    [Serializable]
    public sealed class VisualRenderEvidence
    {
        public int frame, observedCameraCount, capturedCameraCount, omittedCameraCount;
        public int observedRendererCount, capturedRendererCount, omittedRendererCount;
        public float realtime;
        public bool cameraInventoryKnown, cameraInventoryTruncated;
        public VisualCameraSnapshot[] cameras;
        public VisualRenderEvidenceRenderer[] renderers;
    }
    [Serializable]
    public sealed class VisualRenderEvidenceRenderer
    {
        public int index, instanceId, materialSlotCount, sampledMaterialCount, sampledNullMaterialSlots, sampledNamedMaterialCount;
        public bool boundsKnown, screenBoundsKnown, crossesNearClip, hasBehindCameraCorner, materialsTruncated, sampledNamesTruncated;
        public Vector3 boundsCenter, boundsExtents;
        public float screenMinX, screenMinY, screenMaxX, screenMaxY, viewMinZ, viewMaxZ;
        public string[] materialNames, shaderNames;
    }
    [Serializable]
    public sealed class VisualCameraRigSnapshot
    {
        public int rigInstanceId, targetInstanceId, targetBodyInstanceId, targetTeamIndex;
        public int firstPersonTargetInstanceId, targetParamsInstanceId, sceneCameraInstanceId, sceneCameraRigInstanceId;
        public int viewerInstanceId, localUserInstanceId, cachedBodyInstanceId, viewerCameraRigInstanceId, localUserCameraRigInstanceId;
        public bool exists, active, viewerPresent, localUserViewerPresent, cameraEnabled, sceneCameraOwnerMatchesRig;
        public bool viewerIsLocalPlayer, viewerLocalUserMatches, localUserNetworkUserMatches, cachedBodyMatchesTarget, canonicalRigLinksMatch;
        public bool enableFading, hasOverride;
        public string cameraMode;
        public Vector3 rigPosition, cameraPosition;
        public float fadeStartDistance, fadeEndDistance;
    }
    [Serializable]
    public sealed class VisualSnapshot
    {
        public int captureSequence, frame, modelInstanceId, visibilityValue, invisibilityCount, rendererRecordCount;
        public int capturedRendererCount, omittedRendererCount, cameraInstanceId, sceneCameraInstanceId, rigInstanceId;
        public int rigTargetInstanceId, rigTargetBodyInstanceId, rigTargetTeamIndex, firstPersonTargetInstanceId;
        public int rigTargetParamsInstanceId, bodyCameraTargetParamsInstanceId;
        public int localNetworkUserCount, networkUserCount, registeredLocalUserCount, matchingLocalUserCount;
        public int selectedBodyMasterInstanceId, selectedBodyPlayerControllerInstanceId, selectedBodyNetworkUserInstanceId;
        public int selectedBodyLocalUserInstanceId, selectedBodyLocalUserCachedBodyInstanceId, selectedBodyLocalUserCameraRigInstanceId;
        public int globalSceneCameraInstanceId;
        public int observedCameraRigCount, capturedCameraRigCount, omittedCameraRigCount, capturedMatchingBodyRigCount;
        public bool cameraRigInventoryComplete;
        public VisualCameraRigSnapshot[] cameraRigs;
        public VisualRenderEvidence renderEvidence;
        [NonSerialized] public VisualCameraSnapshot[] pendingRenderCameras;
        public float realtime;
        public bool captured, modelExists, modelActive, modelEnabled, forceUpdate;
        public bool cameraExists, cameraActive, cameraEnabled, cameraHasSceneCamera, sceneCameraEnabled, cameraHasRig;
        public bool rigActive, sceneCameraOwnerMatchesRig, sceneCameraComponentMatchesCamera;
        public bool selectedBodyHasMaster, selectedBodyHasPlayerController, selectedBodyNetworkUserIsLocal;
        public bool localUserContextInventoryComplete, selectedBodyNetworkUserInLocalPlayerList;
        public bool selectedBodyNetworkUserHasRegisteredLocalUser, selectedBodyLocalUserCachedBodyMatches, selectedBodyCanonicalRigLinksMatch;
        public bool rigOverrideInstalled, globalSceneCameraIsOwnedView;
        public bool nativeCameraOwnerAttached, nativeCameraOwnerReady;
        public bool cameraGateObservationRequested;
        public bool cameraGateNextTargetKnown, cameraGateNextTargetMatchesExpected, cameraGateTargetKnown, cameraGateTargetMatchesExpected;
        public bool cameraGateRigActiveKnown, cameraGateRigActive, cameraGateProviderActiveKnown, cameraGateProviderActive;
        public bool cameraGateMarkerPresentKnown, cameraGateMarkerPresent, cameraGateMarkerActiveKnown, cameraGateMarkerActive;
        public bool cameraGateMarkerBindingKnown, cameraGateMarkerBoundToRig, cameraGateMarkerBoundToTarget, cameraGateMarkerBoundToProvider;
        public bool cameraGateDelegateKnown, cameraGateDelegatePresent, cameraGateContextReadyKnown, cameraGateContextReady;
        public bool cameraGatePumpCountKnown, cameraGateApplicationKnown, cameraGateApplicationPresent;
        public bool cameraGateApplicationActiveKnown, cameraGateApplicationActive, cameraGateDeltaTimeKnown, cameraGateDeltaTimeNonzero;
        public bool cameraGateCutsceneKnown, cameraGateIsCutscene;
        public int cameraGateExpectedTargetInstanceId, cameraGateNextTargetInstanceId, cameraGateTargetInstanceId, cameraGatePumpCount;
        public float cameraGateDeltaTime;
        public OriginalWwiseCameraListenerSnapshot originalWwiseCameraListener;
        public bool animatorExists, animatorActive, animatorEnabled, animatorInitialized, animatorStateCaptured;
        public int animatorInstanceId, animatorLayerZeroStateHash;
        public float animatorLayerZeroNormalizedTime;
        public string visibility, cameraName, sceneCameraName, cameraMode, nativeCameraOwnerStatus, animatorControllerIdentity, animatorAvatarIdentity, captureError, cameraGateCaptureError;
        public Vector3 viewCameraPosition, rigCameraPosition;
        public VisualRendererSnapshot[] renderers;
    }
    const int MaxVisualRendererRecords = 32;
    const int MaxVisualMaterialSlots = 8;
    const int MaxRenderCameras = 12;
    int visualCaptureSequence;
    bool renderEvidenceCaptured;
    VisualRenderEvidence cachedRenderEvidence;
    readonly Camera[] renderCameraScratch = new Camera[MaxRenderCameras];
    Report report;
    SceneCamera subscribedSceneCamera;
    bool sceneCameraSubscribed;
    Camera subscribedCamera;
    CameraRigController subscribedRig;
    SceneCameraCallbackSnapshot sceneCameraCallback;

    CharacterModel model;
    ModelSkinController skinController;
    Animator animator;
    RuntimeAnimatorController selectedControllerSnapshot;
    Avatar selectedAvatarSnapshot;
    int selectedSnapshotSkinIndex = -1;
    readonly Dictionary<Material, Material> translatedBySource = new Dictionary<Material, Material>();
    readonly Dictionary<Material, Material> sourceByTranslated = new Dictionary<Material, Material>();
    readonly List<Material> owned = new List<Material>();
    readonly List<Material> retired = new List<Material>();
    readonly HashSet<Material> currentSources = new HashSet<Material>();
    readonly HashSet<Renderer> referencedRenderers = new HashSet<Renderer>();
    readonly List<Material> sharedMaterialsScratch = new List<Material>();

    // Computed only from native owner state: no local "loaded" flag is set.
    public bool NativeSelectedSkinReady
    {
        get
        {
            return model && skinController && model.body && animator &&
                   skinController.currentSkinIndex == (int)model.body.skinIndex &&
                   animator.runtimeAnimatorController && animator.avatar &&
                   model.baseRendererInfos != null && model.baseRendererInfos.Length > 0;
        }
    }

    public bool NativeAnimatorInitialized => NativeSelectedSkinReady && animator.isInitialized;

    public static AndroidNativeSourceSkinLifecycle PrepareInactive(GameObject modelObject, CharacterBody expectedBody, Report report)
    {
        if (report == null)
            throw new ArgumentNullException(nameof(report));
        report.requested = true;
        if (!modelObject)
            throw Refuse(report, "Selected source model is missing");
        if (modelObject.activeInHierarchy)
            throw Refuse(report, "Native skin lifecycle must bind before source model activation");
        // This property is true only when the exact-input optional presentation transform was staged.
        // It guards CharacterModel.OnEnable's original RtpcSetter constructor/flush boundary.
        // Safe source-model activation requires either the deliberate silent
        // path or the same original Wwise owner's fully observed Ready state.
        bool audioLifecycleSafeBoundary = WwiseIntegrationManager.noAudio || GameAudioOriginalOwner.Ready;
        var model = modelObject.GetComponent<CharacterModel>();
        var skin = modelObject.GetComponent<ModelSkinController>();
        var animator = modelObject.GetComponentInChildren<Animator>(true);
        if (!model || !skin || !animator || !model.body || !expectedBody || model.body != expectedBody ||
            !expectedBody.modelLocator || expectedBody.modelLocator.modelTransform != modelObject.transform)
            throw Refuse(report, "Selected source model/body/catalog linkage is incomplete or mismatched");
        // Only continue when both native callbacks were enabled by the selected source prefab.
        // Do not force-enable a source-disabled callback.
        if (!AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, audioLifecycleSafeBoundary, model.enabled, skin.enabled))
            throw Refuse(report, "Opt-in source skin lifecycle refused by source/audio/authored-enabled gate");

        // Initialize only this retained original cache after source/catalog/audio gates and
        // before adding/enabling the lifecycle owner or activating the selected model.
        var cacheInitialization = CharacterModelMaterialCacheOwner.EnsureInitialized(
            typeof(CharacterModel), typeof(Material[][]));
        report.materialCacheInitialization = CharacterModelMaterialCacheOwner.CaptureReport(cacheInitialization);
        if (cacheInitialization.outcome != CharacterModelMaterialCacheOwner.Outcome.Initialized &&
            cacheInitialization.outcome != CharacterModelMaterialCacheOwner.Outcome.AlreadyInitialized)
            throw Refuse(report, "Original CharacterModel shared-material cache initialization failed");

        var lifecycle = modelObject.GetComponent<AndroidNativeSourceSkinLifecycle>();
        if (!lifecycle)
            lifecycle = modelObject.AddComponent<AndroidNativeSourceSkinLifecycle>();
        lifecycle.Bind(model, skin, animator, report);
        return lifecycle;
    }

    static InvalidOperationException Refuse(Report report, string reason)
    {
        report.Fail(reason);
        return new InvalidOperationException(reason);
    }

    void Bind(CharacterModel sourceModel, ModelSkinController sourceSkinController, Animator sourceAnimator, Report sourceReport)
    {
        if (model)
        {
            if (model != sourceModel || skinController != sourceSkinController || animator != sourceAnimator)
                throw new InvalidOperationException("Native skin lifecycle cannot change source model ownership");
            return;
        }
        model = sourceModel;
        skinController = sourceSkinController;
        animator = sourceAnimator;
        report = sourceReport;
        report.attached = true;
        CaptureNativeState();
        // Subscribe before enabling/activating the model, so Start-triggered native async skin
        // application cannot complete before Android sees the source's completion notification.
        skinController.onSkinApplied += OnSkinApplied;
        ApplyAlreadyCompletedSkin();
    }

    void OnSkinApplied(int appliedIndex)
    {
        if (!model || !skinController || !model.body || appliedIndex != (int)model.body.skinIndex ||
            skinController.currentSkinIndex != appliedIndex)
            return;
        if (!CaptureSelectedAnimatorSnapshot(appliedIndex))
            return;
        report.selectedSkinIndex = appliedIndex;
        CaptureNativeState();
        TranslateCurrentNativeRecords();
    }

    void ApplyAlreadyCompletedSkin()
    {
        if (!NativeSelectedSkinReady)
            return;
        if (!CaptureSelectedAnimatorSnapshot(skinController.currentSkinIndex))
            return;
        report.selectedSkinIndex = skinController.currentSkinIndex;
        CaptureNativeState();
        TranslateCurrentNativeRecords();
    }

    bool CaptureSelectedAnimatorSnapshot(int appliedIndex)
    {
        if (!NativeSelectedSkinReady || !model.body || appliedIndex != (int)model.body.skinIndex ||
            skinController.currentSkinIndex != appliedIndex || !animator.runtimeAnimatorController || !animator.avatar)
            return false;
        // This snapshot is written only at the native selected-skin completion boundary.
        // CaptureNativeState remains diagnostic and cannot bless a later replacement.
        selectedControllerSnapshot = animator.runtimeAnimatorController;
        selectedAvatarSnapshot = animator.avatar;
        selectedSnapshotSkinIndex = appliedIndex;
        return true;
    }

    // True only while this exact live owner still owns the selected model's native
    // inventory callback. Call only at setup and inventory-change boundaries.
    public bool IsActiveInventoryDisplayOwner(CharacterBody expectedBody, CharacterModel expectedModel, Report expectedReport)
    {
        int selectedIndex = expectedBody ? (int)expectedBody.skinIndex : -1;
        var evidence = new AndroidNativeItemDisplayDispatch.OwnerEvidence {
            expectedBody = expectedBody,
            ownerBody = model ? model.body : null,
            expectedModel = expectedModel,
            ownerModel = model,
            expectedReport = expectedReport,
            ownerReport = report,
            componentActive = this && isActiveAndEnabled && gameObject.activeInHierarchy &&
                              expectedModel && gameObject == expectedModel.gameObject,
            modelEnabled = model && model.enabled,
            modelActive = model && model.gameObject.activeInHierarchy && expectedBody && expectedBody.modelLocator &&
                          expectedBody.modelLocator.modelTransform == model.transform,
            skinControllerEnabled = skinController && skinController.enabled && skinController.gameObject.activeInHierarchy,
            reportRequested = report != null && report.requested,
            reportAttached = report != null && report.attached,
            reportNativeOwnersActive = report != null && report.nativeOwnersActive,
            selectedSkinReady = NativeSelectedSkinReady,
            animatorInitialized = NativeAnimatorInitialized && animator && animator.enabled,
            selectedIndexMatches = selectedIndex >= 0 && skinController && skinController.currentSkinIndex == selectedIndex &&
                                   report != null && report.selectedSkinIndex == selectedIndex &&
                                   report.currentSkinIndex == selectedIndex,
            expectedController = selectedControllerSnapshot,
            liveController = animator ? animator.runtimeAnimatorController : null,
            expectedAvatar = selectedAvatarSnapshot,
            liveAvatar = animator ? animator.avatar : null,
            expectedSelectedIndex = selectedSnapshotSkinIndex,
            liveSelectedIndex = skinController ? skinController.currentSkinIndex : -1,
            notDeactivatedOrDestroyed = report != null && !report.displayDeactivated && !report.ownerDestroyed,
            noFailure = report != null && string.IsNullOrEmpty(report.firstFailure)
        };
        return AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence);
    }

    public void CaptureNativeState()
    {
        if (report == null)
            return;
        report.attached = !ReferenceEquals(model, null);
        report.nativeOwnersActive = model && skinController && model.enabled && skinController.enabled && model.gameObject.activeInHierarchy;
        report.selectedSkinIndex = model && model.body ? (int)model.body.skinIndex : -1;
        report.currentSkinIndex = skinController ? skinController.currentSkinIndex : -1;
        report.selectedSkinReady = NativeSelectedSkinReady;
        report.animatorInitialized = report.selectedSkinReady && animator.isInitialized;
        report.controllerIdentity = Identity(animator ? animator.runtimeAnimatorController : null);
        report.avatarIdentity = Identity(animator ? animator.avatar : null);
    }

    // Read-only, bounded visual evidence for the selected source model and the
    // Nova-owned camera. Called only at the existing report-save cadence.
    public void CaptureNativeVisualState(Camera ownedCamera, Animator sourceAnimator,
                                         AndroidNativeSourceCameraRigOwner nativeCameraOwner = null)
    {
        if (report == null)
            return;
        var snapshot = new VisualSnapshot();
        // Publish the partial snapshot before the first Unity-object read. A
        // destroyed native object or an exceptional Unity getter must remain a
        // serializable diagnostic failure, never escape this observer.
        report.visual = snapshot;
        snapshot.renderEvidence = cachedRenderEvidence;
        snapshot.originalWwiseCameraListener = OriginalWwiseCameraListenerContract.CaptureSnapshot(null);
        snapshot.captureSequence = ++visualCaptureSequence;
        try
        {
            snapshot.originalWwiseCameraListener = OriginalWwiseCameraListenerContract.CaptureSnapshot(nativeCameraOwner);
            snapshot.frame = Time.frameCount;
            snapshot.realtime = Time.realtimeSinceStartup;
            if (!model)
                throw new InvalidOperationException("Selected source model is unavailable during visual capture");
            snapshot.modelExists = true;
            snapshot.modelInstanceId = model.GetInstanceID();
            CaptureLocalCameraContext(snapshot, model.body);
            snapshot.modelActive = model.gameObject.activeInHierarchy;
            snapshot.modelEnabled = model.enabled;
            snapshot.visibility = model.visibility.ToString();
            snapshot.visibilityValue = (int)model.visibility;
            snapshot.invisibilityCount = model.invisibilityCount;
            snapshot.forceUpdate = model.forceUpdate;
            var liveRigs = CameraRigController.readOnlyInstancesList;
            snapshot.observedCameraRigCount = liveRigs != null ? liveRigs.Count : 0;
            snapshot.cameraRigInventoryComplete = snapshot.observedCameraRigCount <= 32;
            int rigCount = Math.Min(snapshot.observedCameraRigCount, 32);
            snapshot.capturedCameraRigCount = rigCount;
            snapshot.omittedCameraRigCount = Math.Max(0, snapshot.observedCameraRigCount - rigCount);
            snapshot.cameraRigs = new VisualCameraRigSnapshot[rigCount];
            for (int i = 0; i < rigCount; i++)
            {
                var rig = liveRigs[i];
                var item = new VisualCameraRigSnapshot { exists = rig };
                snapshot.cameraRigs[i] = item;
                if (!rig)
                    continue;
                item.rigInstanceId = rig.GetInstanceID();
                item.active = rig.isActiveAndEnabled && rig.gameObject.activeInHierarchy;
                item.targetInstanceId = rig.target ? rig.target.GetInstanceID() : 0;
                item.targetBodyInstanceId = rig.targetBody ? rig.targetBody.GetInstanceID() : 0;
                item.targetTeamIndex = (int)rig.targetTeamIndex;
                if (rig.targetBody == model.body)
                    snapshot.capturedMatchingBodyRigCount++;
                item.firstPersonTargetInstanceId = rig.firstPersonTarget ? rig.firstPersonTarget.GetInstanceID() : 0;
                item.targetParamsInstanceId = rig.targetParams ? rig.targetParams.GetInstanceID() : 0;
                item.viewerPresent = rig.viewer != null;
                item.localUserViewerPresent = rig.localUserViewer != null;
                item.viewerInstanceId = rig.viewer ? rig.viewer.GetInstanceID() : 0;
                item.localUserInstanceId = rig.localUserViewer != null ? rig.localUserViewer.id : -1;
                item.viewerIsLocalPlayer = rig.viewer && rig.viewer.isLocalPlayer;
                item.viewerLocalUserMatches = rig.viewer && rig.viewer.localUser == rig.localUserViewer;
                item.localUserNetworkUserMatches = rig.localUserViewer != null && rig.localUserViewer.currentNetworkUser == rig.viewer;
                item.cachedBodyInstanceId = rig.localUserViewer != null && rig.localUserViewer.cachedBody
                    ? rig.localUserViewer.cachedBody.GetInstanceID() : 0;
                item.cachedBodyMatchesTarget = rig.localUserViewer != null && rig.localUserViewer.cachedBody == rig.targetBody;
                item.viewerCameraRigInstanceId = rig.viewer && rig.viewer.cameraRigController
                    ? rig.viewer.cameraRigController.GetInstanceID() : 0;
                item.localUserCameraRigInstanceId = rig.localUserViewer != null && rig.localUserViewer.cameraRigController
                    ? rig.localUserViewer.cameraRigController.GetInstanceID() : 0;
                item.canonicalRigLinksMatch = item.viewerIsLocalPlayer && item.viewerLocalUserMatches &&
                                              item.localUserNetworkUserMatches && item.cachedBodyMatchesTarget &&
                                              item.viewerCameraRigInstanceId == item.rigInstanceId &&
                                              item.localUserCameraRigInstanceId == item.rigInstanceId;
                item.enableFading = rig.enableFading;
                item.fadeStartDistance = rig.fadeStartDistance;
                item.fadeEndDistance = rig.fadeEndDistance;
                item.hasOverride = rig.hasOverride;
                item.cameraMode = rig.cameraMode != null ? ShortText(rig.cameraMode.GetType().FullName, 96) : string.Empty;
                item.rigPosition = rig.transform.position;
                var rigCamera = rig.sceneCam;
                item.cameraEnabled = rigCamera && rigCamera.isActiveAndEnabled;
                item.cameraPosition = rigCamera ? rigCamera.transform.position : Vector3.zero;
                item.sceneCameraInstanceId = rigCamera ? rigCamera.GetInstanceID() : 0;
                var rigSceneCamera = rigCamera ? rigCamera.GetComponent<SceneCamera>() : null;
                item.sceneCameraRigInstanceId = rigSceneCamera && rigSceneCamera.cameraRigController
                    ? rigSceneCamera.cameraRigController.GetInstanceID() : 0;
                item.sceneCameraOwnerMatchesRig = rigSceneCamera && rigSceneCamera.cameraRigController == rig;
            }
            var records = model.baseRendererInfos;
            snapshot.rendererRecordCount = records != null ? records.Length : 0;
            snapshot.cameraExists = ownedCamera;
            snapshot.cameraName = ownedCamera ? ShortText(ownedCamera.name, 96) : string.Empty;
            snapshot.cameraInstanceId = ownedCamera ? ownedCamera.GetInstanceID() : 0;
            snapshot.cameraActive = ownedCamera && ownedCamera.gameObject.activeInHierarchy;
            snapshot.cameraEnabled = ownedCamera && ownedCamera.enabled;
            snapshot.animatorExists = sourceAnimator;
            snapshot.animatorInstanceId = sourceAnimator ? sourceAnimator.GetInstanceID() : 0;
            snapshot.animatorActive = sourceAnimator && sourceAnimator.gameObject.activeInHierarchy;
            snapshot.animatorEnabled = sourceAnimator && sourceAnimator.enabled;
            snapshot.animatorInitialized = sourceAnimator && sourceAnimator.isInitialized;
            snapshot.animatorControllerIdentity = Identity(sourceAnimator ? sourceAnimator.runtimeAnimatorController : null);
            snapshot.animatorAvatarIdentity = Identity(sourceAnimator ? sourceAnimator.avatar : null);
            if (ownedCamera)
            {
                var sceneCamera = ownedCamera.GetComponent<SceneCamera>();
                snapshot.cameraHasSceneCamera = sceneCamera;
                snapshot.sceneCameraEnabled = sceneCamera && sceneCamera.enabled;
                snapshot.sceneCameraName = sceneCamera ? ShortText(sceneCamera.name, 96) : string.Empty;
                snapshot.sceneCameraInstanceId = sceneCamera ? sceneCamera.GetInstanceID() : 0;
                var rig = sceneCamera ? sceneCamera.cameraRigController : null;
                TryBindSceneCameraObservation(sceneCamera, ownedCamera, rig);
                snapshot.cameraHasRig = rig;
                snapshot.rigInstanceId = rig ? rig.GetInstanceID() : 0;
                if (rig)
                {
                    snapshot.nativeCameraOwnerAttached = nativeCameraOwner != null;
                    snapshot.nativeCameraOwnerReady = nativeCameraOwner != null && nativeCameraOwner.ready;
                    snapshot.nativeCameraOwnerStatus = nativeCameraOwner != null ? ShortText(nativeCameraOwner.status, 160) : string.Empty;
                    snapshot.globalSceneCameraInstanceId = SceneCamera._camera ? SceneCamera._camera.GetInstanceID() : 0;
                    snapshot.globalSceneCameraIsOwnedView = SceneCamera._camera == ownedCamera;
                    snapshot.rigActive = rig.isActiveAndEnabled && rig.gameObject.activeInHierarchy;
                    snapshot.sceneCameraOwnerMatchesRig = sceneCamera.cameraRigController == rig && rig.sceneCam == ownedCamera;
                    snapshot.sceneCameraComponentMatchesCamera = sceneCamera.camera == ownedCamera;
                    snapshot.rigOverrideInstalled = nativeCameraOwner != null && rig.IsOverrideCam(nativeCameraOwner);
                    snapshot.rigTargetInstanceId = rig.target ? rig.target.GetInstanceID() : 0;
                    snapshot.rigTargetBodyInstanceId = rig.targetBody ? rig.targetBody.GetInstanceID() : 0;
                    snapshot.rigTargetTeamIndex = (int)rig.targetTeamIndex;
                    snapshot.rigTargetParamsInstanceId = rig.targetParams ? rig.targetParams.GetInstanceID() : 0;
                    var bodyCameraTargetParams = model.body ? model.body.GetComponent<CameraTargetParams>() : null;
                    snapshot.bodyCameraTargetParamsInstanceId = bodyCameraTargetParams ? bodyCameraTargetParams.GetInstanceID() : 0;
                    snapshot.firstPersonTargetInstanceId = rig.firstPersonTarget ? rig.firstPersonTarget.GetInstanceID() : 0;
                    snapshot.cameraMode = rig.cameraMode != null ? ShortText(rig.cameraMode.GetType().FullName, 96) : string.Empty;
                    snapshot.viewCameraPosition = ownedCamera.transform.position;
                    snapshot.rigCameraPosition = rig.transform.position;
                }
            }
            if (!nativeCameraOwner)
                snapshot.nativeCameraOwnerStatus = ShortText(report.cameraAdmissionFailure, 160);
            else
                nativeCameraOwner.CaptureUpdateContextObservation(snapshot);
            if (sourceAnimator && sourceAnimator.isInitialized && sourceAnimator.layerCount > 0)
            {
                var state = sourceAnimator.GetCurrentAnimatorStateInfo(0);
                snapshot.animatorLayerZeroStateHash = state.fullPathHash;
                snapshot.animatorLayerZeroNormalizedTime = state.normalizedTime;
                snapshot.animatorStateCaptured = true;
            }
            int count = records != null ? Math.Min(records.Length, MaxVisualRendererRecords) : 0;
            snapshot.capturedRendererCount = count;
            snapshot.omittedRendererCount = Math.Max(0, snapshot.rendererRecordCount - count);
            snapshot.renderers = new VisualRendererSnapshot[count];
            bool captureRenderEvidenceNow = !renderEvidenceCaptured && NativeSelectedSkinReady && ownedCamera &&
                                           nativeCameraOwner != null && nativeCameraOwner.ready;
            if (captureRenderEvidenceNow)
            {
                try { CaptureRenderCameraStack(snapshot, ownedCamera); }
                finally { Array.Clear(renderCameraScratch, 0, renderCameraScratch.Length); }
            }
            for (int i = 0; i < count; i++)
            {
                var renderer = records[i].renderer;
                var item = new VisualRendererSnapshot { index = i, exists = renderer };
                snapshot.renderers[i] = item;
                item.rendererRecordMaterialIdentity = Identity(records[i].defaultMaterial);
                item.defaultShadowCastingMode = (int)records[i].defaultShadowCastingMode;
                item.ignoreOverlays = records[i].ignoreOverlays;
                if (!renderer)
                    continue;
                item.instanceId = renderer.GetInstanceID();
                item.rendererType = ShortText(renderer.GetType().FullName, 96);
                item.rendererName = ShortText(renderer.name, 96);
                item.layer = renderer.gameObject.layer;
                item.active = renderer.gameObject.activeInHierarchy;
                item.enabled = renderer.enabled;
                item.visible = renderer.isVisible;
                var bounds = renderer.bounds;
                item.boundsCenter = bounds.center;
                item.boundsExtents = bounds.extents;
                Mesh mesh = null;
                var skinned = renderer as SkinnedMeshRenderer;
                if (skinned)
                    mesh = skinned.sharedMesh;
                else
                {
                    var filter = renderer.GetComponent<MeshFilter>();
                    if (filter)
                        mesh = filter.sharedMesh;
                }
                item.meshIdentity = Identity(mesh);
                // Unity 2021.3 exposes all shared materials as a list, so avoid
                // enumerating an unbounded slot array at this 5-second cadence.
                // Sample only the non-instantiating first sharedMaterial getter.
                item.materialSlotCount = -1;
                item.materialSlotCountKnown = false;
                item.materialsTruncated = true;
                if (captureRenderEvidenceNow)
                    CaptureFirstRendererMaterial(item, renderer);
                else
                {
                    var material = renderer.sharedMaterial;
                    item.sampledMaterialCount = material ? 1 : 0;
                    item.sampledNullMaterialSlots = 0;
                    item.materialIdentities = material
                        ? new[] { ShortText(Identity(material) + "|" + (material.shader ? material.shader.name : "<null-shader>"), 192) }
                        : Array.Empty<string>();
                }
                if (captureRenderEvidenceNow && ownedCamera)
                    CaptureRendererProjection(item, ownedCamera, bounds);
            }
            if (captureRenderEvidenceNow)
            {
                cachedRenderEvidence = BuildRenderEvidence(snapshot);
                renderEvidenceCaptured = cachedRenderEvidence != null;
                snapshot.renderEvidence = cachedRenderEvidence;
            }
            snapshot.captured = true;
        }
        catch (Exception error)
        {
            snapshot.captureError = ShortText(error.GetBaseException().Message, 192);
            snapshot.captured = false;
        }
        report.visual = snapshot;
    }

    void TryBindSceneCameraObservation(SceneCamera candidate, Camera camera, CameraRigController rig)
    {
        if (report == null)
            return;
        if (sceneCameraCallback == null)
        {
            sceneCameraCallback = new SceneCameraCallbackSnapshot { requested = true, status = "refused" };
            report.sceneCameraCallback = sceneCameraCallback;
        }
        if (sceneCameraSubscribed)
        {
            if (candidate != subscribedSceneCamera || camera != subscribedCamera || rig != subscribedRig)
                sceneCameraCallback.status = "identityChanged";
            return;
        }
        if (!candidate || !camera || !rig || candidate.camera != camera || candidate.cameraRigController != rig ||
            rig.sceneCam != camera || !model || !model.body || rig.targetBody != model.body ||
            !candidate.isActiveAndEnabled || !camera.isActiveAndEnabled || !rig.isActiveAndEnabled)
        {
            sceneCameraCallback.status = "refused";
            return;
        }
        subscribedSceneCamera = candidate;
        subscribedCamera = camera;
        subscribedRig = rig;
        try
        {
            SceneCamera.onSceneCameraPreRender += CaptureOwnedSceneCameraPreRender;
            sceneCameraSubscribed = true;
            sceneCameraCallback.subscriptionActive = true;
            sceneCameraCallback.status = "subscribed";
            sceneCameraCallback.sceneCameraInstanceId = candidate.GetInstanceID();
            sceneCameraCallback.cameraInstanceId = camera.GetInstanceID();
            sceneCameraCallback.rigInstanceId = rig.GetInstanceID();
            sceneCameraCallback.modelInstanceId = model.GetInstanceID();
        }
        catch
        {
            sceneCameraCallback.status = "subscribeFailed";
            sceneCameraCallback.subscriptionActive = false;
            subscribedSceneCamera = null;
            subscribedCamera = null;
            subscribedRig = null;
        }
    }

    void CaptureOwnedSceneCameraPreRender(SceneCamera value)
    {
        if (!sceneCameraSubscribed || sceneCameraCallback == null || sceneCameraCallback.callbackObserved)
            return;
        if (!value || value != subscribedSceneCamera)
            return;
        sceneCameraCallback.callbackObserved = true;
        sceneCameraCallback.callbackCount = 1;
        try
        {
            var camera = value.camera;
            var rig = value.cameraRigController;
            bool exact = value == subscribedSceneCamera && camera == subscribedCamera && rig == subscribedRig &&
                         camera && rig && rig.sceneCam == camera && model && model.body && rig.targetBody == model.body;
            sceneCameraCallback.identityMatched = exact;
            if (!exact)
            {
                sceneCameraCallback.status = "callbackIdentityMismatch";
                return;
            }
            sceneCameraCallback.frame = Time.frameCount;
            sceneCameraCallback.realtime = Time.realtimeSinceStartup;
            CaptureTrackedModelMembership(sceneCameraCallback);
            sceneCameraCallback.modelInstanceId = model.GetInstanceID();
            sceneCameraCallback.modelActive = model.gameObject.activeInHierarchy;
            sceneCameraCallback.modelEnabled = model.enabled;
            sceneCameraCallback.forceUpdate = model.forceUpdate;
            sceneCameraCallback.visibilityValue = (int)model.visibility;
            sceneCameraCallback.invisibilityCount = model.invisibilityCount;
            sceneCameraCallback.modelStateKnown = true;
            var records = model.baseRendererInfos;
            sceneCameraCallback.rendererRecordCount = records != null ? records.Length : 0;
            int count = records != null ? Math.Min(records.Length, 12) : 0;
            var samples = new SceneCameraCallbackRendererSample[count];
            for (int i = 0; i < count; i++)
            {
                var renderer = records[i].renderer;
                var sample = new SceneCameraCallbackRendererSample { rendererExists = renderer };
                samples[i] = sample;
                if (!renderer)
                    continue;
                sample.rendererInstanceId = renderer.GetInstanceID();
                sample.rendererActive = renderer.gameObject.activeInHierarchy;
                sample.rendererEnabled = renderer.enabled;
                sample.rendererVisible = renderer.isVisible;
                var material = renderer.sharedMaterial;
                sample.sharedMaterialKnown = true;
                sample.sharedMaterialInstanceId = material ? material.GetInstanceID() : 0;
            }
            sceneCameraCallback.renderers = samples;
            sceneCameraCallback.sampledRendererCount = count;
            sceneCameraCallback.rendererJoinKnown = records != null;
            CaptureCharacterModelMaterialState(sceneCameraCallback);
            sceneCameraCallback.status = "captured";
        }
        catch
        {
            sceneCameraCallback.status = "captureFailed";
            sceneCameraCallback.modelStateKnown = false;
            sceneCameraCallback.rendererJoinKnown = false;
            sceneCameraCallback.renderers = null;
        }
    }

    // Bounded, read-only source-state evidence. Never retain the cache or its Material references.
    void CaptureCharacterModelMaterialState(SceneCameraCallbackSnapshot snapshot)
    {
        if (snapshot == null || !model)
            return;

        try
        {
            var cacheField = typeof(CharacterModel).GetField("sharedMaterialArrays",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
            if (cacheField == null || cacheField.FieldType != typeof(Material[][]))
            {
                snapshot.materialObservationError = "shared material cache field missing or wrong type";
            }
            else
            {
                var cache = cacheField.GetValue(null) as Material[][];
                snapshot.sharedMaterialCacheKnown = true;
                snapshot.sharedMaterialCacheIsNull = cache == null;
                if (cache != null)
                {
                    const int maxBuckets = 16;
                    int count = Math.Min(cache.Length, maxBuckets);
                    var lengths = new int[count];
                    int nullBuckets = 0;
                    for (int i = 0; i < count; i++)
                    {
                        var bucket = cache[i];
                        if (bucket == null)
                        {
                            lengths[i] = -1;
                            nullBuckets++;
                        }
                        else
                        {
                            lengths[i] = bucket.Length;
                        }
                    }
                    snapshot.sharedMaterialCacheOuterLength = cache.Length;
                    snapshot.sharedMaterialCacheBucketLengths = lengths;
                    snapshot.sharedMaterialCacheBucketsScanned = count;
                    snapshot.sharedMaterialCacheNullBucketCount = nullBuckets;
                    snapshot.sharedMaterialCacheBucketsComplete = count == cache.Length;
                }
            }
        }
        catch (Exception error)
        {
            snapshot.sharedMaterialCacheKnown = false;
            if (string.IsNullOrEmpty(snapshot.materialObservationError))
            {
                snapshot.materialObservationError = "shared material cache read failed: " + error.GetType().Name;
            }
        }

        try
        {
            snapshot.materialDirty = model.GetMaterialsDirty();
            snapshot.materialDirtyKnown = true;
        }
        catch (Exception error)
        {
            if (string.IsNullOrEmpty(snapshot.materialObservationError))
                snapshot.materialObservationError = "material dirty read failed: " + error.GetType().Name;
        }
    }

    void CaptureTrackedModelMembership(SceneCameraCallbackSnapshot snapshot)
    {
        const int maxTrackedModelScan = 256;
        try
        {
            var tracked = InstanceTracker.GetInstancesList<CharacterModel>();
            if (tracked == null)
                return;
            int count = tracked.Count;
            snapshot.trackedModelCount = count;
            snapshot.trackedModelCountKnown = true;
            snapshot.trackedModelScanTruncated = count > maxTrackedModelScan;
            int scanCount = Math.Min(count, maxTrackedModelScan);
            for (int i = 0; i < scanCount; i++)
            {
                var candidate = tracked[i];
                snapshot.trackedModelsScanned++;
                if (ReferenceEquals(candidate, model))
                {
                    snapshot.trackedModelMembershipKnown = true;
                    snapshot.trackedModelContainsSelected = true;
                    return;
                }
            }
            if (!snapshot.trackedModelScanTruncated)
                snapshot.trackedModelMembershipKnown = true;
        }
        catch
        {
            // Membership is optional evidence. Preserve callback/model observations and leave this join unknown.
            snapshot.trackedModelCountKnown = false;
            snapshot.trackedModelMembershipKnown = false;
            snapshot.trackedModelContainsSelected = false;
        }
    }

    void UnsubscribeSceneCameraObservation()
    {
        if (sceneCameraSubscribed)
        {
            try { SceneCamera.onSceneCameraPreRender -= CaptureOwnedSceneCameraPreRender; }
            catch { if (sceneCameraCallback != null) sceneCameraCallback.status = "unsubscribeFailed"; }
            sceneCameraSubscribed = false;
        }
        if (sceneCameraCallback != null)
        {
            sceneCameraCallback.subscriptionActive = false;
            if (sceneCameraCallback.status == "subscribed" || sceneCameraCallback.status == "captured")
                sceneCameraCallback.status = sceneCameraCallback.callbackObserved ? "capturedUnsubscribed" : "unsubscribedBeforeCallback";
        }
        subscribedSceneCamera = null;
        subscribedCamera = null;
        subscribedRig = null;
    }

    void CaptureRenderCameraStack(VisualSnapshot snapshot, Camera ownedCamera)
    {
        int observed;
        try
        {
            observed = Camera.allCamerasCount;
        }
        catch
        {
            CaptureOwnedCameraOnly(snapshot, ownedCamera, -1);
            return;
        }

        // Unity 2021.3 validates GetAllCameras buffer length against the live
        // allCamerasCount and throws when it is too small. Never request a
        // truncated copy: over-cap inventories are explicitly unknown and the
        // exact owned camera is retained as a one-record diagnostic.
        if (observed < 0 || observed > MaxRenderCameras)
        {
            CaptureOwnedCameraOnly(snapshot, ownedCamera, observed);
            return;
        }

        int copied;
        try
        {
            copied = Camera.GetAllCameras(renderCameraScratch);
        }
        catch
        {
            // Count can grow after the first read. Treat this as a race, keep
            // the exact owned camera, and continue renderer projection.
            CaptureOwnedCameraOnly(snapshot, ownedCamera, observed, false);
            return;
        }

        if (copied != observed || copied < 0 || copied > MaxRenderCameras)
        {
            CaptureOwnedCameraOnly(snapshot, ownedCamera, observed, false);
            return;
        }

        bool ownedPresent = false;
        for (int i = 0; i < copied; i++)
            if (renderCameraScratch[i] == ownedCamera)
                ownedPresent = true;
        if (!ownedPresent && ownedCamera && ownedCamera.isActiveAndEnabled)
        {
            // A stable active-camera census that omits its exact enabled owner
            // is inconsistent. Avoid presenting a partial stack as complete.
            CaptureOwnedCameraOnly(snapshot, ownedCamera, observed, false);
            return;
        }

        int outputCount = copied + (!ownedPresent && ownedCamera ? 1 : 0);
        bool replaceLastWithOwned = outputCount > MaxRenderCameras;
        if (replaceLastWithOwned)
            outputCount = MaxRenderCameras;
        snapshot.pendingRenderCameras = new VisualCameraSnapshot[outputCount];
        for (int i = 0; i < outputCount; i++)
        {
            Camera camera = replaceLastWithOwned && i == outputCount - 1
                ? ownedCamera
                : i < copied ? renderCameraScratch[i] : ownedCamera;
            snapshot.pendingRenderCameras[i] = CaptureCamera(camera, camera == ownedCamera);
        }
        pendingCameraCount = observed;
        pendingCapturedCameraCount = outputCount;
        pendingOmittedCameraCount = Math.Max(0, observed - copied) + (replaceLastWithOwned ? 1 : 0);
        pendingCameraInventoryKnown = true;
        pendingCameraInventoryTruncated = pendingOmittedCameraCount > 0;
    }

    int pendingCameraCount, pendingCapturedCameraCount, pendingOmittedCameraCount;
    bool pendingCameraInventoryKnown, pendingCameraInventoryTruncated;

    void CaptureOwnedCameraOnly(VisualSnapshot snapshot, Camera ownedCamera, int observed, bool omittedCountKnown = true)
    {
        snapshot.pendingRenderCameras = ownedCamera
            ? new[] { CaptureCamera(ownedCamera, true) }
            : Array.Empty<VisualCameraSnapshot>();
        pendingCameraCount = observed;
        pendingCapturedCameraCount = snapshot.pendingRenderCameras.Length;
        pendingOmittedCameraCount = omittedCountKnown && observed >= 0
            ? Math.Max(0, observed - (ownedCamera && ownedCamera.isActiveAndEnabled ? 1 : 0))
            : -1;
        pendingCameraInventoryKnown = false;
        pendingCameraInventoryTruncated = true;
    }

    VisualRenderEvidence BuildRenderEvidence(VisualSnapshot snapshot)
    {
        var evidence = new VisualRenderEvidence
        {
            frame = snapshot.frame,
            realtime = snapshot.realtime,
            observedCameraCount = pendingCameraCount,
            capturedCameraCount = pendingCapturedCameraCount,
            omittedCameraCount = pendingOmittedCameraCount,
            observedRendererCount = snapshot.rendererRecordCount,
            capturedRendererCount = snapshot.capturedRendererCount,
            omittedRendererCount = snapshot.omittedRendererCount,
            cameraInventoryKnown = pendingCameraInventoryKnown,
            cameraInventoryTruncated = pendingCameraInventoryTruncated,
            cameras = snapshot.pendingRenderCameras,
            renderers = CloneRenderers(snapshot.renderers)
        };
        return evidence;
    }

    static VisualRenderEvidenceRenderer[] CloneRenderers(VisualRendererSnapshot[] source)
    {
        if (source == null)
            return null;
        var copy = new VisualRenderEvidenceRenderer[source.Length];
        for (int i = 0; i < source.Length; i++)
        {
            var item = source[i];
            if (item == null)
                continue;
            copy[i] = new VisualRenderEvidenceRenderer
            {
                index = item.index,
                instanceId = item.instanceId,
                materialSlotCount = item.materialSlotCount,
                sampledMaterialCount = item.sampledMaterialCount,
                sampledNullMaterialSlots = item.sampledNullMaterialSlots,
                sampledNamedMaterialCount = item.sampledNamedMaterialCount,
                boundsKnown = item.exists,
                materialsTruncated = item.materialsTruncated,
                sampledNamesTruncated = item.sampledNamesTruncated,
                boundsCenter = item.boundsCenter,
                boundsExtents = item.boundsExtents,
                screenBoundsKnown = item.screenBoundsKnown,
                crossesNearClip = item.crossesNearClip,
                hasBehindCameraCorner = item.hasBehindCameraCorner,
                screenMinX = item.screenMinX,
                screenMinY = item.screenMinY,
                screenMaxX = item.screenMaxX,
                screenMaxY = item.screenMaxY,
                viewMinZ = item.viewMinZ,
                viewMaxZ = item.viewMaxZ,
                materialNames = item.sampledMaterialNames != null ? (string[])item.sampledMaterialNames.Clone() : null,
                shaderNames = item.sampledShaderNames != null ? (string[])item.sampledShaderNames.Clone() : null
            };
        }
        return copy;
    }

    static VisualCameraSnapshot CaptureCamera(Camera camera, bool ownedSourceCamera)
    {
        if (!camera)
            return new VisualCameraSnapshot();
        var rect = camera.rect;
        return new VisualCameraSnapshot
        {
            exists = true,
            instanceId = camera.GetInstanceID(),
            ownedSourceCamera = ownedSourceCamera,
            active = camera.gameObject.activeInHierarchy,
            enabled = camera.isActiveAndEnabled,
            depth = camera.depth,
            clearFlags = (int)camera.clearFlags,
            cullingMask = camera.cullingMask,
            nearClip = camera.nearClipPlane,
            farClip = camera.farClipPlane,
            fieldOfView = camera.fieldOfView,
            orthographic = camera.orthographic,
            rectX = rect.x,
            rectY = rect.y,
            rectWidth = rect.width,
            rectHeight = rect.height,
            targetDisplay = camera.targetDisplay,
            targetTexturePresent = camera.targetTexture,
            position = camera.transform.position,
            rotation = camera.transform.rotation,
            scalarValuesFinite = Finite(camera.depth) && Finite(camera.nearClipPlane) && Finite(camera.farClipPlane) &&
                                 Finite(camera.fieldOfView) && Finite(rect.x) && Finite(rect.y) &&
                                 Finite(rect.width) && Finite(rect.height) &&
                                 Finite(camera.transform.position.x) && Finite(camera.transform.position.y) &&
                                 Finite(camera.transform.position.z) && Finite(camera.transform.rotation.x) &&
                                 Finite(camera.transform.rotation.y) && Finite(camera.transform.rotation.z) &&
                                 Finite(camera.transform.rotation.w)
        };
    }

    void CaptureFirstRendererMaterial(VisualRendererSnapshot item, Renderer renderer)
    {
        // Preserve the lifecycle report's existing first-shared-material
        // observation. Do not enumerate a renderer's full material array here:
        // Unity exposes no slot count that is safe to query without materializing
        // the complete list, so the total and all later names remain unknown.
        var material = renderer.sharedMaterial;
        item.materialSlotCount = -1;
        item.materialSlotCountKnown = false;
        item.materialsTruncated = true;
        item.sampledMaterialCount = material ? 1 : 0;
        item.sampledNullMaterialSlots = 0;
        item.sampledNamedMaterialCount = material ? 1 : 0;
        item.sampledNamesTruncated = true;
        item.materialIdentities = material
            ? new[] { ShortText(Identity(material) + "|" + (material.shader ? material.shader.name : "<null-shader>"), 192) }
            : Array.Empty<string>();
        item.sampledMaterialNames = material ? new[] { ShortText(material.name, 96) } : Array.Empty<string>();
        item.sampledShaderNames = material && material.shader ? new[] { ShortText(material.shader.name, 96) } : Array.Empty<string>();
    }

    static void CaptureRendererProjection(VisualRendererSnapshot item, Camera camera, Bounds bounds)
    {
        Vector3 min = bounds.min;
        Vector3 max = bounds.max;
        float minX = float.PositiveInfinity, minY = float.PositiveInfinity;
        float maxX = float.NegativeInfinity, maxY = float.NegativeInfinity;
        float minZ = float.PositiveInfinity, maxZ = float.NegativeInfinity;
        for (int i = 0; i < 8; i++)
        {
            Vector3 corner = new Vector3((i & 1) == 0 ? min.x : max.x,
                                         (i & 2) == 0 ? min.y : max.y,
                                         (i & 4) == 0 ? min.z : max.z);
            Vector3 projected = camera.WorldToScreenPoint(corner);
            if (!Finite(projected.x) || !Finite(projected.y) || !Finite(projected.z))
                return;
            minX = Math.Min(minX, projected.x);
            minY = Math.Min(minY, projected.y);
            maxX = Math.Max(maxX, projected.x);
            maxY = Math.Max(maxY, projected.y);
            minZ = Math.Min(minZ, projected.z);
            maxZ = Math.Max(maxZ, projected.z);
        }
        item.screenMinX = minX;
        item.screenMinY = minY;
        item.screenMaxX = maxX;
        item.screenMaxY = maxY;
        item.viewMinZ = minZ;
        item.viewMaxZ = maxZ;
        item.hasBehindCameraCorner = minZ <= 0f;
        item.crossesNearClip = minZ < camera.nearClipPlane && maxZ >= camera.nearClipPlane;
        item.screenBoundsKnown = true;
    }

    static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    static void CaptureLocalCameraContext(VisualSnapshot snapshot, CharacterBody selectedBody)
    {
        var allUsers = NetworkUser.readOnlyInstancesList;
        var localUsers = NetworkUser.readOnlyLocalPlayersList;
        var registeredLocalUsers = LocalUserManager.readOnlyLocalUsersList;
        snapshot.networkUserCount = allUsers != null ? allUsers.Count : -1;
        snapshot.localNetworkUserCount = localUsers != null ? localUsers.Count : -1;
        snapshot.registeredLocalUserCount = registeredLocalUsers != null ? registeredLocalUsers.Count : -1;
        snapshot.localUserContextInventoryComplete = allUsers != null && localUsers != null && registeredLocalUsers != null &&
            allUsers.Count <= 32 && localUsers.Count <= 32 && registeredLocalUsers.Count <= 32;
        if (!selectedBody)
            return;
        var master = selectedBody.master;
        snapshot.selectedBodyHasMaster = master;
        snapshot.selectedBodyMasterInstanceId = master ? master.GetInstanceID() : 0;
        var playerController = master ? master.playerCharacterMasterController : null;
        snapshot.selectedBodyHasPlayerController = playerController;
        snapshot.selectedBodyPlayerControllerInstanceId = playerController ? playerController.GetInstanceID() : 0;
        var bodyUser = playerController ? playerController.networkUser : null;
        snapshot.selectedBodyNetworkUserInstanceId = bodyUser ? bodyUser.GetInstanceID() : 0;
        snapshot.selectedBodyNetworkUserIsLocal = bodyUser && bodyUser.isLocalPlayer;
        if (!bodyUser || registeredLocalUsers == null || registeredLocalUsers.Count > 32)
            return;
        var local = bodyUser.localUser;
        if (localUsers != null && localUsers.Count <= 32)
            for (int i = 0; i < localUsers.Count; i++)
                if (localUsers[i] == bodyUser)
                {
                    snapshot.selectedBodyNetworkUserInLocalPlayerList = true;
                    break;
                }
        snapshot.selectedBodyLocalUserInstanceId = local != null ? local.id : -1;
        if (local == null)
            return;
        snapshot.selectedBodyLocalUserCachedBodyInstanceId = local.cachedBody ? local.cachedBody.GetInstanceID() : 0;
        snapshot.selectedBodyLocalUserCameraRigInstanceId = local.cameraRigController ? local.cameraRigController.GetInstanceID() : 0;
        bool registered = false;
        for (int i = 0; i < registeredLocalUsers.Count; i++)
            if (registeredLocalUsers[i] == local)
            {
                registered = true;
                break;
            }
        snapshot.selectedBodyNetworkUserHasRegisteredLocalUser = registered && local.currentNetworkUser == bodyUser;
        snapshot.selectedBodyLocalUserCachedBodyMatches = local.cachedBody == selectedBody;
        var rig = bodyUser.cameraRigController;
        snapshot.selectedBodyCanonicalRigLinksMatch = rig && rig.viewer == bodyUser && rig.localUserViewer == local &&
                                                       local.cameraRigController == rig && rig.targetBody == selectedBody &&
                                                       rig.target == selectedBody.gameObject;
        if (registeredLocalUsers.Count <= 32 && localUsers != null && localUsers.Count <= 32)
            for (int i = 0; i < registeredLocalUsers.Count; i++)
                if (registeredLocalUsers[i] != null && registeredLocalUsers[i].cachedBody == selectedBody &&
                    registeredLocalUsers[i].currentNetworkUser)
                    snapshot.matchingLocalUserCount++;
    }

    static string Identity(UnityEngine.Object value)
    {
        if (!value)
            return string.Empty;
        string identity = value.GetType().FullName + ":" + value.name;
        return identity.Length > 160 ? identity.Substring(0, 160) : identity;
    }

    static string ShortText(string value, int maximum)
    {
        if (string.IsNullOrEmpty(value))
            return string.Empty;
        return value.Length > maximum ? value.Substring(0, maximum) : value;
    }

    public void RecordDisplayDeactivated()
    {
        if (report == null)
            return;
        report.displayDeactivated = true;
        report.nativeOwnersActive = false;
    }

    Material NativeSource(Material value)
    {
        Material source;
        return value && sourceByTranslated.TryGetValue(value, out source) ? source : value;
    }

    Material Translate(Material value)
    {
        var source = NativeSource(value);
        if (!source)
            return null;
        currentSources.Add(source);
        Material copy;
        if (translatedBySource.TryGetValue(source, out copy) && copy)
        {
            retired.Remove(copy);
            return copy;
        }
        copy = new Material(source);
        AndroidMaterialPresentation.Apply(source, copy);
        translatedBySource.Add(source, copy);
        sourceByTranslated.Add(copy, source);
        owned.Add(copy);
        if (report != null)
            report.materialCopiesCreated++;
        return copy;
    }

    void TranslateCurrentNativeRecords()
    {
        if (!NativeSelectedSkinReady)
            return;
        currentSources.Clear();
        var records = model.baseRendererInfos;
        for (int i = 0; i < records.Length; i++)
        {
            var record = records[i];
            if (record.renderer)
                referencedRenderers.Add(record.renderer);
            // Keep the complete native RendererInfo (renderer, defaultShadowCastingMode,
            // ignoreOverlays, and future fields) and replace only its material reference.
            record.defaultMaterial = Translate(record.defaultMaterial);
            records[i] = record;
        }
        model.baseRendererInfos = records;
        // CharacterModel's source Update consumes these records and refreshes actual slots.
        model.forceUpdate = true;
        QueueNoLongerSelectedCopies();
        RetireIfNativeOwnersReleasedCopies();
    }

    void QueueNoLongerSelectedCopies()
    {
        for (int i = 0; i < owned.Count; i++)
        {
            var copy = owned[i];
            Material source;
            if (copy && sourceByTranslated.TryGetValue(copy, out source) && !currentSources.Contains(source) && !retired.Contains(copy))
            {
                retired.Add(copy);
                if (report != null)
                    report.materialCopiesRetired++;
            }
        }
    }

    void LateUpdate()
    {
        // Skin swaps are rare. Scan only pending old copies, never every model renderer per frame.
        if (retired.Count != 0)
            RetireIfNativeOwnersReleasedCopies();
    }

    void RetireIfNativeOwnersReleasedCopies()
    {
        for (int i = retired.Count - 1; i >= 0; i--)
        {
            var copy = retired[i];
            if (copy && IsReferencedByNativeModel(copy))
                continue;
            ReleaseOwnedCopy(copy);
        }
    }

    bool IsReferencedByNativeModel(Material sought)
    {
        if (model)
        {
            var records = model.baseRendererInfos;
            if (records != null)
                foreach (var record in records)
                    if (ReferenceEquals(record.defaultMaterial, sought))
                        return true;
        }
        foreach (var renderer in referencedRenderers)
        {
            if (!renderer)
                continue;
            sharedMaterialsScratch.Clear();
            renderer.GetSharedMaterials(sharedMaterialsScratch);
            foreach (var material in sharedMaterialsScratch)
                if (ReferenceEquals(material, sought))
                    return true;
        }
        return false;
    }

    void ReleaseOwnedCopy(Material copy)
    {
        if (ReferenceEquals(copy, null))
            return;
        AndroidMaterialPresentation.Release(copy);
        Material source;
        if (sourceByTranslated.TryGetValue(copy, out source))
        {
            Material current;
            if (translatedBySource.TryGetValue(source, out current) && ReferenceEquals(current, copy))
                translatedBySource.Remove(source);
            sourceByTranslated.Remove(copy);
        }
        if (copy)
            Destroy(copy);
        if (report != null)
            report.materialCopiesReleased++;
        owned.Remove(copy);
        retired.Remove(copy);
    }

    void OnDestroy()
    {
        UnsubscribeSceneCameraObservation();
        if (!ReferenceEquals(skinController, null))
            skinController.onSkinApplied -= OnSkinApplied;
        selectedControllerSnapshot = null;
        selectedAvatarSnapshot = null;
        selectedSnapshotSkinIndex = -1;
        if (report != null)
        {
            report.ownerDestroyed = true;
            report.attached = false;
            report.nativeOwnersActive = false;
        }
        // This component shares the native model/body destruction lifetime. Display deactivation
        // does not release native skin handles or dispose this owner.
        for (int i = owned.Count - 1; i >= 0; i--)
            ReleaseOwnedCopy(owned[i]);
        owned.Clear();
        retired.Clear();
        currentSources.Clear();
        referencedRenderers.Clear();
        sharedMaterialsScratch.Clear();
        translatedBySource.Clear();
        sourceByTranslated.Clear();
    }
}
