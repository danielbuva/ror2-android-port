using System;
using System.Reflection;
using RoR2;
using UnityEngine;

static class AdapterContractTests
{
    static int assertions;
    static void Check(bool value, string message)
    {
        assertions++;
        if (!value) throw new Exception("FAILED: " + message);
    }
    static AndroidNativeSourceSkinLifecycle Prepare(out GameObject gameObject, out CharacterModel model,
                                                     out ModelSkinController skin, out Renderer renderer,
                                                     out Material source)
    {
        gameObject = new GameObject("owned source model") { activeSelf = false };
        model = gameObject.AddComponent<CharacterModel>();
        skin = gameObject.AddComponent<ModelSkinController>();
        var animator = gameObject.AddComponent<Animator>();
        animator.runtimeAnimatorController = new RuntimeAnimatorController();
        animator.avatar = new Avatar();
        animator.isInitialized = true;
        animator.layerCount = 1;
        var body = gameObject.AddComponent<CharacterBody>();
        body.skinIndex = 4;
        body.modelLocator = gameObject.AddComponent<ModelLocator>();
        body.modelLocator.modelTransform = gameObject.transform;
        model.body = body;
        skin.currentSkinIndex = -1;
        renderer = gameObject.AddComponent<Renderer>();
        source = new Material("native material");
        model.baseRendererInfos = new[] {
            new CharacterModel.RendererInfo {
                renderer = renderer, defaultMaterial = source, defaultShadowCastingMode = 2, ignoreOverlays = true
            }
        };
        GameAudioOriginalOwner.Ready = false;
        WwiseIntegrationManager.noAudio = true;
        return AndroidNativeSourceSkinLifecycle.PrepareInactive(gameObject, body,
            new AndroidNativeSourceSkinLifecycle.Report { requested = true });
    }
    static AndroidNativeSourceSkinLifecycle.Report GetReport(AndroidNativeSourceSkinLifecycle adapter)
    {
        return (AndroidNativeSourceSkinLifecycle.Report)adapter.GetType().GetField("report", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(adapter);
    }
    static void CallPrivate(object target, string name)
    {
        target.GetType().GetMethod(name, BindingFlags.Instance | BindingFlags.NonPublic).Invoke(target, null);
    }
    static void TestOptInSelectionPolicy()
    {
        Check(!AndroidNativeSkinActivationPolicy.ShouldActivate(false, true, true, true, true), "default-off opt-in");
        Check(!AndroidNativeSkinActivationPolicy.ShouldActivate(true, false, true, true, true), "source-selected gate");
        Check(!AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, false, true, true), "no-audio gate");
        Check(!AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, true, false, true), "authored CharacterModel gate");
        Check(!AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, true, true, false), "authored controller gate");
        Check(AndroidNativeSkinActivationPolicy.ShouldActivate(true, true, true, true, true), "fully qualified opt-in");
    }
    static void TestRefusalDoesNotMutateOwners()
    {
        var go = new GameObject("unqualified") { activeSelf = false };
        var cm = go.AddComponent<CharacterModel>();
        var sc = go.AddComponent<ModelSkinController>();
        var body = go.AddComponent<CharacterBody>();
        body.modelLocator = go.AddComponent<ModelLocator>();
        body.modelLocator.modelTransform = go.transform;
        cm.body = body;
        var animator = go.AddComponent<Animator>();
        animator.runtimeAnimatorController = new RuntimeAnimatorController();
        animator.avatar = new Avatar();
        cm.baseRendererInfos = new[] { new CharacterModel.RendererInfo { renderer = go.AddComponent<Renderer>(), defaultMaterial = new Material("native") } };
        WwiseIntegrationManager.noAudio = false;
        GameAudioOriginalOwner.Ready = false;
        bool refused = false;
        var report = new AndroidNativeSourceSkinLifecycle.Report { requested = true };
        try { AndroidNativeSourceSkinLifecycle.PrepareInactive(go, body, report); }
        catch (InvalidOperationException) { refused = true; }
        Check(refused && cm.enabled && sc.enabled && !go.GetComponent<AndroidNativeSourceSkinLifecycle>(),
              "no-audio gate refuses before mutating model owners");
        Check(report.requested && !report.attached && report.firstFailure.Contains("audio/authored-enabled"),
              "refusal is attached to bounded serializable run report");
    }
    static void TestOriginalAudioReadyBoundaryAllowsOptIn()
    {
        var go = new GameObject("audio-ready source model") { activeSelf = false };
        var model = go.AddComponent<CharacterModel>();
        var skin = go.AddComponent<ModelSkinController>();
        var body = go.AddComponent<CharacterBody>();
        body.modelLocator = go.AddComponent<ModelLocator>();
        body.modelLocator.modelTransform = go.transform;
        model.body = body;
        var animator = go.AddComponent<Animator>();
        animator.runtimeAnimatorController = new RuntimeAnimatorController();
        animator.avatar = new Avatar();
        model.baseRendererInfos = new[] { new CharacterModel.RendererInfo { renderer = go.AddComponent<Renderer>(), defaultMaterial = new Material("native") } };
        WwiseIntegrationManager.noAudio = false;
        GameAudioOriginalOwner.Ready = true;
        var report = new AndroidNativeSourceSkinLifecycle.Report { requested = true };
        var adapter = AndroidNativeSourceSkinLifecycle.PrepareInactive(go, body, report);
        Check(adapter && report.attached && !report.nativeOwnersActive,
              "selected original audio Ready witness permits opt-in source lifecycle without altering native owners");
        GameAudioOriginalOwner.Ready = false;
    }

    static void TestDisabledAuthoredOwnerIsNeverForceEnabled()
    {
        var go = new GameObject("source-disabled owner") { activeSelf = false };
        var model = go.AddComponent<CharacterModel>();
        var skin = go.AddComponent<ModelSkinController>();
        var body = go.AddComponent<CharacterBody>();
        body.modelLocator = go.AddComponent<ModelLocator>();
        body.modelLocator.modelTransform = go.transform;
        model.body = body;
        var animator = go.AddComponent<Animator>();
        animator.runtimeAnimatorController = new RuntimeAnimatorController();
        animator.avatar = new Avatar();
        model.baseRendererInfos = new[] { new CharacterModel.RendererInfo { renderer = go.AddComponent<Renderer>(), defaultMaterial = new Material("native") } };
        skin.enabled = false;
        WwiseIntegrationManager.noAudio = true;
        bool refused = false;
        var report = new AndroidNativeSourceSkinLifecycle.Report { requested = true };
        try { AndroidNativeSourceSkinLifecycle.PrepareInactive(go, body, report); }
        catch (InvalidOperationException) { refused = true; }
        Check(refused && model.enabled && !skin.enabled && !go.GetComponent<AndroidNativeSourceSkinLifecycle>(),
              "source-disabled native controller is not force-enabled or mutated");
        Check(report.requested && !report.attached && !string.IsNullOrEmpty(report.firstFailure),
              "authored-owner refusal is reported truthfully");
    }
    static void TestNativeSkinEventAndMetadata()
    {
        var adapter = Prepare(out var go, out var model, out var skin, out var renderer, out var source);
        Check(adapter && !go.activeInHierarchy, "adapter binds on inactive owned model");
        var report = GetReport(adapter);
        Check(report.requested && report.attached && report.selectedSkinIndex == 4 && !report.nativeOwnersActive,
              "report records opt-in attachment before activation without claiming readiness");
        Check(!adapter.NativeSelectedSkinReady, "native readiness is false until selected SkinDef completion");
        Check(ReferenceEquals(model.baseRendererInfos[0].defaultMaterial, source), "no adaptation before native selected-skin completion");
        skin.CompleteNativeSkin(4);
        Check(adapter.NativeSelectedSkinReady && adapter.NativeAnimatorInitialized,
              "native readiness reads selected controller/avatar/records and Animator state");
        adapter.CaptureNativeState();
        Check(report.selectedSkinReady && report.animatorInitialized && report.currentSkinIndex == 4 &&
                  report.selectedSkinIndex == 4 && report.controllerIdentity.Contains("RuntimeAnimatorController") &&
                  report.avatarIdentity.Contains("Avatar"),
              "read-only snapshot records actual native indexes and object identities");
        var firstCopy = model.baseRendererInfos[0].defaultMaterial;
        Check(firstCopy && !ReferenceEquals(firstCopy, source), "native event uses translated Android copy");
        Check(model.baseRendererInfos[0].defaultShadowCastingMode == 2 && model.baseRendererInfos[0].ignoreOverlays,
              "skin renderer metadata preserved");
        Check(model.forceUpdate && AndroidMaterialPresentation.applyCalls > 0, "native CharacterModel dirty path scheduled");
        var animator = go.GetComponent<Animator>();
        animator.isInitialized = false;
        Check(!adapter.NativeAnimatorInitialized && adapter.NativeSelectedSkinReady,
              "selected native skin readiness remains distinct from Animator initialization");
        animator.isInitialized = true;
        renderer.sharedMaterials = new[] { firstCopy };
        skin.CompleteNativeSkin(5); // wrong/unselected index must not rewrite the body-selected skin
        Check(ReferenceEquals(model.baseRendererInfos[0].defaultMaterial, firstCopy), "nonselected skin notification ignored");
    }
    static void TestActiveInventoryDisplayOwnerPredicate()
    {
        var adapter = Prepare(out var go, out var model, out var skin, out var renderer, out var source);
        var body = go.GetComponent<CharacterBody>();
        var animator = go.GetComponent<Animator>();
        var report = GetReport(adapter);
        skin.CompleteNativeSkin(4);
        go.activeSelf = true;
        adapter.CaptureNativeState();
        Check(adapter.IsActiveInventoryDisplayOwner(body, model, report),
              "exact live source-skin owner and report qualify for exclusive inventory ownership");

        var otherObject = new GameObject("different source");
        var otherBody = otherObject.AddComponent<CharacterBody>();
        otherBody.skinIndex = 4;
        var otherModel = otherObject.AddComponent<CharacterModel>();
        Check(!adapter.IsActiveInventoryDisplayOwner(otherBody, model, report), "different body identity refuses");
        Check(!adapter.IsActiveInventoryDisplayOwner(body, otherModel, report), "different model identity refuses");
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, new AndroidNativeSourceSkinLifecycle.Report { requested = true }),
              "different lifecycle report identity refuses");

        report.currentSkinIndex = 3;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "stale native current skin index refuses");
        adapter.CaptureNativeState();

        var originalController = animator.runtimeAnimatorController;
        var originalAvatar = animator.avatar;
        string controllerName = report.controllerIdentity;
        string avatarName = report.avatarIdentity;
        var sameNamedController = new RuntimeAnimatorController { name = originalController.name };
        animator.runtimeAnimatorController = sameNamedController;
        adapter.CaptureNativeState();
        Check(report.controllerIdentity == controllerName &&
                  !adapter.IsActiveInventoryDisplayOwner(body, model, report),
              "read-only capture cannot bless a same-type/same-name controller replacement");
        animator.runtimeAnimatorController = originalController;
        Check(adapter.IsActiveInventoryDisplayOwner(body, model, report), "restoring exact controller reference restores ownership");

        var sameNamedAvatar = new Avatar { name = originalAvatar.name };
        animator.avatar = sameNamedAvatar;
        adapter.CaptureNativeState();
        Check(report.avatarIdentity == avatarName &&
                  !adapter.IsActiveInventoryDisplayOwner(body, model, report),
              "read-only capture cannot bless a same-type/same-name avatar replacement");
        animator.avatar = originalAvatar;
        Check(adapter.IsActiveInventoryDisplayOwner(body, model, report), "restoring exact avatar reference restores ownership");

        report.controllerIdentity = "diagnostic-only controller text";
        report.avatarIdentity = "diagnostic-only avatar text";
        Check(adapter.IsActiveInventoryDisplayOwner(body, model, report),
              "report identity strings are diagnostic and do not decide object ownership");
        adapter.CaptureNativeState();

        // A real native selected-skin completion is allowed to install a new controller/avatar pair.
        animator.runtimeAnimatorController = new RuntimeAnimatorController { name = originalController.name };
        animator.avatar = new Avatar { name = originalAvatar.name };
        skin.CompleteNativeSkin(4);
        Check(adapter.IsActiveInventoryDisplayOwner(body, model, report),
              "authoritative selected-skin completion updates the owned object snapshot");

        animator.isInitialized = false;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "uninitialized Animator refuses");
        animator.isInitialized = true;
        skin.enabled = false;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "disabled native skin owner refuses");
        skin.enabled = true;
        model.enabled = false;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "disabled native CharacterModel refuses");
        model.enabled = true;
        go.activeSelf = false;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "inactive source model refuses");
        go.activeSelf = true;
        report.displayDeactivated = true;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "display-deactivated lifecycle refuses");
        report.displayDeactivated = false;
        report.ownerDestroyed = true;
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "destroyed lifecycle refuses");
        report.ownerDestroyed = false;
        report.firstFailure = "prior failure";
        Check(!adapter.IsActiveInventoryDisplayOwner(body, model, report), "failed lifecycle refuses");
    }
    static void TestRetirementWaitsForNativeRendererRelease()
    {
        var adapter = Prepare(out var go, out var model, out var skin, out var renderer, out var source);
        skin.CompleteNativeSkin(4);
        var oldCopy = model.baseRendererInfos[0].defaultMaterial;
        renderer.sharedMaterials = new[] { oldCopy };
        var newSource = new Material("next native skin material");
        model.baseRendererInfos = new[] {
            new CharacterModel.RendererInfo {
                renderer = renderer, defaultMaterial = newSource, defaultShadowCastingMode = 1, ignoreOverlays = false
            }
        };
        skin.CompleteNativeSkin(4);
        var newCopy = model.baseRendererInfos[0].defaultMaterial;
        var report = GetReport(adapter);
        Check(!ReferenceEquals(newCopy, oldCopy) && !oldCopy.destroyed, "old renderer copy queued, not eagerly destroyed");
        Check(report.materialCopiesCreated == 2 && report.materialCopiesRetired == 1 && report.materialCopiesReleased == 0,
              "material clone counts follow actual create and retirement callbacks");
        CallPrivate(adapter, "LateUpdate");
        Check(!oldCopy.destroyed, "pending copy retained while renderer still references it");
        renderer.sharedMaterials = new[] { newCopy };
        CallPrivate(adapter, "LateUpdate");
        Check(oldCopy.destroyed && !newCopy.destroyed && !source.destroyed && !newSource.destroyed,
              "only superseded owner clone released after native renderer switched");
        Check(report.materialCopiesReleased == 1, "released clone count follows owner release");
    }
    static void TestBodyLifetimeCleanupUnsubscribesAndReleasesCopies()
    {
        var adapter = Prepare(out var go, out var model, out var skin, out var renderer, out var source);
        skin.CompleteNativeSkin(4);
        var copy = model.baseRendererInfos[0].defaultMaterial;
        int applied = AndroidMaterialPresentation.applyCalls;
        var report = GetReport(adapter);
        CallPrivate(adapter, "OnDestroy");
        skin.CompleteNativeSkin(4);
        Check(copy.destroyed && AndroidMaterialPresentation.releaseCalls > 0, "body destroy releases translated clone");
        Check(AndroidMaterialPresentation.applyCalls == applied, "body destroy removes native skin subscription");
        Check(!source.destroyed, "body destroy never releases the native source material");
        Check(report.ownerDestroyed && !report.attached && report.materialCopiesReleased == 1,
              "body-owner destruction records actual cleanup and native attachment end");
        Check((int)adapter.GetType().GetField("selectedSnapshotSkinIndex", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(adapter) == -1 &&
                  adapter.GetType().GetField("selectedControllerSnapshot", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(adapter) == null &&
                  adapter.GetType().GetField("selectedAvatarSnapshot", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(adapter) == null,
              "owner teardown clears snapshot references without destroying native controller/avatar objects");
    }
    static void TestBoundedVisualSnapshotIsReadOnly()
    {
        var adapter = Prepare(out var go, out var model, out var skin, out var renderer, out var source);
        skin.CompleteNativeSkin(4);
        var animator = go.GetComponent<Animator>();
        var cameraObject = new GameObject("Nova diagnostic camera");
        var camera = cameraObject.AddComponent<Camera>();
        cameraObject.AddComponent<SceneCamera>();
        renderer.name = "Huntress body mesh";
        renderer.enabled = false;
        renderer.isVisible = false;
        renderer.sharedMaterials = new[] { source, null };
        renderer.getSharedMaterialsCalls = 0;
        model.visibility = VisibilityLevel.Invisible;
        model.invisibilityCount = 1;
        bool originalForceUpdate = model.forceUpdate;
        int originalCopies = GetReport(adapter).materialCopiesCreated;

        adapter.CaptureNativeVisualState(camera, animator);
        var report = GetReport(adapter);
        var visual = report.visual;
        Check(visual != null && visual.captured && visual.modelExists && visual.modelInstanceId == model.GetInstanceID(),
              "visual capture records the exact selected native model");
        Check(visual.visibility == "Invisible" && visual.invisibilityCount == 1 && visual.forceUpdate == originalForceUpdate,
              "visual capture reads visibility and blink counter without changing native state");
        Check(visual.cameraExists && visual.cameraHasSceneCamera && !visual.cameraHasRig,
              "owned camera association records SceneCamera presence and missing native rig");
        Check(visual.animatorInstanceId == animator.GetInstanceID() && visual.animatorInitialized && visual.animatorStateCaptured && visual.animatorLayerZeroStateHash == 42,
              "initialized native Animator state is captured at the bounded report point");
        Check(visual.capturedRendererCount == 1 && visual.renderers[0].exists && !visual.renderers[0].enabled &&
                  visual.renderers[0].sampledMaterialCount == 1 && !visual.renderers[0].materialSlotCountKnown &&
                  visual.renderers[0].materialSlotCount == -1 && visual.renderers[0].materialsTruncated &&
                  visual.renderers[0].materialIdentities.Length == 1 && renderer.getSharedMaterialsCalls == 0,
              "renderer evidence samples only the first shared material without unbounded list enumeration");
        Check(visual.renderers[0].rendererRecordMaterialIdentity.Contains("Material") && visual.renderers[0].ignoreOverlays,
              "native renderer-record material and overlay metadata are captured separately from live slots");
        Check(!renderer.enabled && model.visibility == VisibilityLevel.Invisible && report.materialCopiesCreated == originalCopies,
              "capture does not enable renderers, change visibility, or alter material ownership");

        var scene = camera.GetComponent<SceneCamera>();
        var rig = cameraObject.AddComponent<CameraRigController>();
        rig.sceneCam = camera;
        scene.camera = camera;
        scene.cameraRigController = rig;
        CameraRigController.readOnlyInstancesList.Clear();
        CameraRigController.readOnlyInstancesList.Add(rig);
        var cameraOwner = cameraObject.AddComponent<AndroidNativeSourceCameraRigOwner>();
        cameraOwner.ready = true;
        cameraOwner.status = "synthetic ready owner";
        adapter.CaptureNativeVisualState(camera, animator, cameraOwner);
        Check(report.visual.nativeCameraOwnerAttached && report.visual.nativeCameraOwnerReady &&
                  report.visual.nativeCameraOwnerStatus == "synthetic ready owner" && !report.visual.rigOverrideInstalled,
              "bounded visual report consumes the exact camera-owner readiness/status surface and records override ownership separately");
        Check(report.visual.cameraGateObservationRequested && report.visual.cameraGateNextTargetKnown &&
                  report.visual.cameraGateNextTargetMatchesExpected && report.visual.cameraGateTargetKnown &&
                  !report.visual.cameraGateTargetMatchesExpected && report.visual.cameraGateMarkerBindingKnown &&
                  report.visual.cameraGateDelegateKnown && report.visual.cameraGateDelegatePresent &&
                  report.visual.cameraGateContextReadyKnown && !report.visual.cameraGateContextReady &&
                  report.visual.cameraGatePumpCountKnown && report.visual.cameraGatePumpCount == -2 &&
                  report.visual.cameraGateApplicationActive && report.visual.cameraGateDeltaTimeNonzero,
              "visual snapshot preserves gate inputs, separate current/next target state, and the exact pump count");
        Check(report.visual.originalWwiseCameraListener != null &&
                  report.visual.originalWwiseCameraListener.evidenceCaptured &&
                  report.visual.originalWwiseCameraListener.gameObjectId == "987654321" &&
                  report.visual.originalWwiseCameraListener.managedListContainsExactListener &&
                  report.visual.originalWwiseCameraListener.nativeAddOutcome.Contains("not_observed"),
              "skin visual snapshot copies listener lifecycle evidence without inventing native registration");

        cameraOwner.throwListenerActiveRead = true;
        adapter.CaptureNativeVisualState(camera, animator, cameraOwner);
        cameraOwner.throwListenerActiveRead = false;
        Check(!report.visual.captured && report.visual.captureError.Contains("synthetic listener read failure") &&
                  report.visual.originalWwiseCameraListener != null &&
                  !report.visual.originalWwiseCameraListener.evidenceCaptured,
              "a failing Unity listener getter stays a partial unknown report and cannot escape capture");
        cameraOwner.throwListenerActiveRead = false;
        cameraOwner.observationFieldsAvailable = false;
        adapter.CaptureNativeVisualState(camera, animator, cameraOwner);
        Check(report.visual.captured && report.visual.cameraGateObservationRequested &&
                  !report.visual.cameraGateDelegateKnown && !report.visual.cameraGateContextReadyKnown &&
                  !report.visual.cameraGatePumpCountKnown &&
                  report.visual.cameraGateCaptureError.Contains("optional marker originalEarlyUpdate field missing"),
              "optional gate field absence stays unknown and bounded without failing the visual capture");
        cameraOwner.observationFieldsAvailable = true;

        var slots = new Material[10];
        for (int i = 0; i < slots.Length; i++)
            slots[i] = new Material("slot " + i);
        renderer.sharedMaterials = slots;
        model.baseRendererInfos = new[] { model.baseRendererInfos[0] };
        renderer.getSharedMaterialsCalls = 0;
        adapter.CaptureNativeVisualState(camera, animator, cameraOwner);
        Check(!report.visual.renderers[0].materialSlotCountKnown && report.visual.renderers[0].materialSlotCount == -1 &&
                  report.visual.renderers[0].materialsTruncated && report.visual.renderers[0].materialIdentities.Length == 1 &&
                  renderer.getSharedMaterialsCalls == 0,
              "large material slot arrays are not enumerated by visual capture");

        var many = new CharacterModel.RendererInfo[40];
        for (int i = 0; i < many.Length; i++)
        {
            var child = new GameObject("bounded renderer " + i);
            var childRenderer = child.AddComponent<Renderer>();
            many[i] = new CharacterModel.RendererInfo { renderer = childRenderer, defaultMaterial = source };
        }
        model.baseRendererInfos = many;
        adapter.CaptureNativeVisualState(camera, animator);
        Check(report.visual.capturedRendererCount == 32 && report.visual.omittedRendererCount == 8 &&
                  report.visual.renderers.Length == 32,
              "renderer evidence is capped at 32 records with explicit truncation count");

        UnityEngine.Time.throwFrameCount = true;
        adapter.CaptureNativeVisualState(camera, animator);
        UnityEngine.Time.throwFrameCount = false;
        Check(report.visual != null && !report.visual.captured &&
                  report.visual.captureError.Contains("synthetic Unity frame read failure"),
              "Unity read failure is caught and published as a partial diagnostic snapshot");
        UnityEngine.Time.throwFrameCount = false;
        adapter.CaptureNativeVisualState(camera, animator);
        var lastLiveVisual = report.visual;
        int lastLiveSequence = lastLiveVisual.captureSequence;
        adapter.RecordDisplayDeactivated();
        CallPrivate(adapter, "OnDestroy");
        Check(ReferenceEquals(report.visual, lastLiveVisual) && report.visual.captured &&
                  report.visual.captureSequence == lastLiveSequence && report.displayDeactivated && report.ownerDestroyed,
              "teardown preserves the last complete pre-disposal visual sample without Unity reads after destruction");
    }
    public static int Main()
    {
        TestOptInSelectionPolicy();
        TestRefusalDoesNotMutateOwners();
        TestOriginalAudioReadyBoundaryAllowsOptIn();
        TestDisabledAuthoredOwnerIsNeverForceEnabled();
        TestNativeSkinEventAndMetadata();
        TestActiveInventoryDisplayOwnerPredicate();
        TestRetirementWaitsForNativeRendererRelease();
        TestBodyLifetimeCleanupUnsubscribesAndReleasesCopies();
        TestBoundedVisualSnapshotIsReadOnly();
        Console.WriteLine("PASS: " + assertions + " adapter/selection/lifecycle/report assertions");
        return 0;
    }
}
