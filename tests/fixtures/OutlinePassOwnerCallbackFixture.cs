using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace UnityEngine
{
    public class Object
    {
        public static implicit operator bool(Object value) => value != null;
        public static bool operator !(Object value) => value == null;
    }
    public class Component : Object { }
    public class MonoBehaviour : Component { }
    public class Camera : Component
    {
        public delegate void CameraCallback(Camera camera);
        public static event CameraCallback onPreRender;
        readonly Dictionary<Type, Component> components = new Dictionary<Type, Component>();
        public void Add(Component value) => components[value.GetType()] = value;
        public T GetComponent<T>() where T : Component => components.TryGetValue(typeof(T), out var value) ? (T)value : null;
        public static void Raise(Camera camera) => onPreRender?.Invoke(camera);
    }
    public class Material : Object
    {
        public int passCountReads;
        public int passCount => ++passCountReads;
        public Shader shader { get; set; }
    }
    public class Shader : Object
    {
        public string name { get; set; }
        public bool isSupported { get; set; }
    }
    public static class Time
    {
        public static int frameCount = 41;
        public static float realtimeSinceStartup = 12.5f;
    }
}

internal sealed class SceneCamera : UnityEngine.Component
{
    public CameraRigController cameraRigController;
}
internal sealed class CameraRigController : UnityEngine.Component { }
internal sealed class OutlineHighlight : UnityEngine.Component
{
    private UnityEngine.Material highlightMaterial;
    public OutlineHighlight(UnityEngine.Material value) { highlightMaterial = value; }
}

// ACTUAL PRODUCTION REPORT DTO IS INSERTED HERE BY THE PUBLIC TEST WRAPPER.

internal sealed class OwnerCallbackFixture : MonoBehaviour
{
    public Camera viewCamera;
    public CameraRigController cameraRig;
    public SceneCamera sceneCamera;
    public AndroidNativeSourceSkinLifecycle.Report sourceSkinReport;
    OutlineHighlight ownedOutlineHighlight;
    FieldInfo outlineMaterialField;
    bool outlinePassObserverSubscribed;
    bool sourceListenerTeardownStarted, ready, audioComponentPolicyVerified;
    public bool Subscribed => outlinePassObserverSubscribed;
    public AndroidNativeSourceSkinLifecycle.OutlinePassObservation Observation => sourceSkinReport.outlinePassObservation;

    // ACTUAL PRODUCTION METHODS ARE INSERTED HERE BY THE PUBLIC TEST WRAPPER.
    public void Attach() => TryAttachOutlinePassObserver();
    public void Disable() => OnDisable();
    public void DestroyOwner() => OnDestroy();
    void RemoveOwnedOverride() { }
    void RestoreGlobalSceneCameraPointer() { }
    void ReleaseSourceSobel() { } // Separate Sobel fixture executes this production lifecycle.
    public void DisposeOwnedView() { }
}

internal static class FixtureAssertions
{
    static int assertions;
    static void Check(bool value, string label)
    {
        assertions++;
        if (!value) throw new Exception("FAILED: " + label);
    }

    static OwnerCallbackFixture NewOwner(bool withOutline, out UnityEngine.Material material,
        out AndroidNativeSourceSkinLifecycle.OutlinePassObservation report)
    {
        var camera = new Camera();
        var rig = new CameraRigController();
        var scene = new SceneCamera { cameraRigController = rig };
        camera.Add(scene);
        material = new UnityEngine.Material { shader = new UnityEngine.Shader { name = "Hopoo Games/Internal/Outline Highlight", isSupported = true } };
        if (withOutline) camera.Add(new OutlineHighlight(material));
        report = new AndroidNativeSourceSkinLifecycle.OutlinePassObservation { requested = true };
        return new OwnerCallbackFixture { viewCamera = camera, cameraRig = rig, sceneCamera = scene, sourceSkinReport = new AndroidNativeSourceSkinLifecycle.Report { outlinePassObservation = report } };
    }

    static void TestForeignThenOwnedFirstCallbackReadsAndDetaches()
    {
        var owner = NewOwner(true, out var material, out var report);
        owner.Attach();
        report = owner.Observation;
        Check(owner.Subscribed, "setup attaches owned camera callback");
        UnityEngine.Camera.Raise(new UnityEngine.Camera());
        Check(!report.cameraPreRenderObserved && owner.Subscribed, "foreign camera is ignored without consuming the one-shot");
        UnityEngine.Camera.Raise(owner.viewCamera);
        Check(report.cameraPreRenderObserved && report.cameraIdentityMatched, "first exact camera callback is retained state=" + report.state + " observed=" + report.cameraPreRenderObserved + " identity=" + report.cameraIdentityMatched);
        Check(report.materialReadObserved && report.materialPresent, "first valid callback reaches existing material field read");
        Check(report.passCountKnown && material.passCountReads == 1, "first valid callback reads pass count once");
        Check(report.shaderNameMatchesExpected && report.shaderSupportedKnown && report.shaderSupported, "first valid callback records existing shader metadata");
        Check(report.state == "captured_material_state_blit_unobserved", "successful inventory explicitly leaves source blit unobserved");
        Check(!report.sourceBlitInvocationObserved && !report.sourceBlitObservationAvailable, "material inventory does not claim a blit invocation");
        Check(!owner.Subscribed, "owned callback detaches immediately after capture");
        UnityEngine.Camera.Raise(owner.viewCamera);
        Check(material.passCountReads == 1, "later camera event cannot reread material");
    }

    static void TestOwnedIdentityMismatchIsUnknownAndDetaches()
    {
        var owner = NewOwner(true, out var material, out var report);
        owner.sceneCamera.cameraRigController = new CameraRigController();
        owner.Attach();
        report = owner.Observation;
        UnityEngine.Camera.Raise(owner.viewCamera);
        Check(report.cameraPreRenderObserved, "exact camera identity mismatch still records attempted observation");
        Check(report.state == "owned_camera_context_or_outline_identity_mismatch", "mismatched component context stays explicit unknown");
        Check(!report.materialReadObserved && material.passCountReads == 0, "mismatch never reads material");
        Check(!owner.Subscribed, "mismatched owned callback detaches");
    }

    static void TestMissingOutlineAndLifecycleCleanup()
    {
        var missing = NewOwner(false, out _, out var missingReport);
        missing.Attach();
        missingReport = missing.Observation;
        Check(!missing.Subscribed && missingReport.state == "owned_outline_component_missing", "missing exact component refuses setup without subscription");

        var disabled = NewOwner(true, out var disabledMaterial, out var disabledReport);
        disabled.Attach();
        disabledReport = disabled.Observation;
        disabled.Disable();
        Check(!disabled.Subscribed && disabledReport.state == "detached_before_owned_camera_pre_render", "disable removes static delegate");
        UnityEngine.Camera.Raise(disabled.viewCamera);
        Check(disabledMaterial.passCountReads == 0, "disabled owner receives no callback");

        var destroyed = NewOwner(true, out var destroyedMaterial, out _);
        destroyed.Attach();
        destroyed.DestroyOwner();
        Check(!destroyed.Subscribed, "destroy removes static delegate");
        UnityEngine.Camera.Raise(destroyed.viewCamera);
        Check(destroyedMaterial.passCountReads == 0, "destroyed owner receives no callback");
    }

    public static int Main()
    {
        TestForeignThenOwnedFirstCallbackReadsAndDetaches();
        TestOwnedIdentityMismatchIsUnknownAndDetaches();
        TestMissingOutlineAndLifecycleCleanup();
        Console.WriteLine("R34 composed owner callback fixture passed: " + assertions);
        return 0;
    }
}
