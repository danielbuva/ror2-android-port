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
        bool refused = false;
        var report = new AndroidNativeSourceSkinLifecycle.Report { requested = true };
        try { AndroidNativeSourceSkinLifecycle.PrepareInactive(go, body, report); }
        catch (InvalidOperationException) { refused = true; }
        Check(refused && cm.enabled && sc.enabled && !go.GetComponent<AndroidNativeSourceSkinLifecycle>(),
              "no-audio gate refuses before mutating model owners");
        Check(report.requested && !report.attached && report.firstFailure.Contains("audio/authored-enabled"),
              "refusal is attached to bounded serializable run report");
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
    }
    public static int Main()
    {
        TestOptInSelectionPolicy();
        TestRefusalDoesNotMutateOwners();
        TestDisabledAuthoredOwnerIsNeverForceEnabled();
        TestNativeSkinEventAndMetadata();
        TestRetirementWaitsForNativeRendererRelease();
        TestBodyLifetimeCleanupUnsubscribesAndReleasesCopies();
        Console.WriteLine("PASS: " + assertions + " adapter/selection/lifecycle/report assertions");
        return 0;
    }
}
