using System;
using System.Reflection;
using RoR2;
using UnityEngine;

sealed class Owner : MonoBehaviour, ICameraStateProvider { }
static class Program
{
    static void Check(bool value, string name) { if (!value) throw new Exception("failed: " + name); }
    static AndroidNativeSourceViewOnlyRigMarker Bind(GameObject rigObject, CameraRigController rig, GameObject target, Owner owner)
    {
        var marker = rigObject.Add(new AndroidNativeSourceViewOnlyRigMarker());
        marker.Bind(rig, target, owner);
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(marker, null);
        return marker;
    }
    static void Main()
    {
        var rigObject = new GameObject();
        var rig = rigObject.Add(new CameraRigController());
        var owner = rigObject.Add(new Owner());
        var target = new GameObject();
        rig.nextTarget = target;
        var marker = Bind(rigObject, rig, target, owner);
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(marker, null);
        Check(rig.originalCalls == 1 && rig.target == target && rig.contextRig == rig, "exact bound rig dispatches original method and generates context");
        Check(marker.IsOriginalUpdateContextReadyFor(rig, target, owner), "owner observes context after original callback");

        var otherObject = new GameObject();
        var otherRig = otherObject.Add(new CameraRigController());
        var otherOwner = otherObject.Add(new Owner());
        var otherTarget = new GameObject();
        otherRig.nextTarget = otherTarget;
        var wrong = Bind(otherObject, otherRig, otherTarget, otherOwner);
        otherRig.nextTarget = new GameObject();
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 0 && !wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "mismatched next target is refused");
        otherRig.nextTarget = otherTarget;
        otherRig.localUserViewer = new object();
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 0, "non-null viewer is refused");
        otherRig.localUserViewer = null;
        Time.deltaTime = 0f;
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 1 && otherRig.target == otherTarget && !wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "zero-time original update sets target but does not claim context");
        Time.deltaTime = 0.016f;
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 2 && wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "context is admitted only after nonzero-time original update");
        RoR2Application.instance = new RoR2Application { isActiveAndEnabled = true };
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 2 && wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "active original application is not double-dispatched and prior context remains valid");
        RoR2Application.instance = null;
        otherOwner.isActiveAndEnabled = true;
        otherRig.throwOnOriginalCall = true;
        try { typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null); }
        catch (TargetInvocationException) { }
        Check(!wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "original callback exception clears context admission");
        otherRig.throwOnOriginalCall = false;
        otherOwner.isActiveAndEnabled = false;
        typeof(AndroidNativeSourceViewOnlyRigMarker).GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(wrong, null);
        Check(otherRig.originalCalls == 3 && !wrong.IsOriginalUpdateContextReadyFor(otherRig, otherTarget, otherOwner), "inactive owner cannot pump or retain an admitted context");
        var ownedCamera = new SceneCamera();
        var otherCamera = new SceneCamera();
        AndroidNativeSourceViewOnlyRigMarker.BeginOwnedSceneCameraActivation(ownedCamera);
        Check(!AndroidNativeSourceViewOnlyRigMarker.ShouldSkipMissingConsole(otherCamera, false), "foreign SceneCamera never skips original setup");
        Check(!AndroidNativeSourceViewOnlyRigMarker.ShouldSkipMissingConsole(ownedCamera, true), "real Console presence preserves original setup");
        Check(AndroidNativeSourceViewOnlyRigMarker.ShouldSkipMissingConsole(ownedCamera, false), "only the owned camera skips unavailable Console setup");
        Check(AndroidNativeSourceViewOnlyRigMarker.EndOwnedSceneCameraActivation(ownedCamera), "scope records reduced-fidelity defaults use");
        Check(!AndroidNativeSourceViewOnlyRigMarker.ShouldSkipMissingConsole(ownedCamera, false), "ended scope cannot affect later activation");
        AndroidNativeSourceViewOnlyRigMarker.BeginOwnedSceneCameraActivation(ownedCamera);
        Check(!AndroidNativeSourceViewOnlyRigMarker.EndOwnedSceneCameraActivation(ownedCamera), "Console-present/no-skip scope reports original configuration status");
        bool duplicateRefused = false;
        AndroidNativeSourceViewOnlyRigMarker.BeginOwnedSceneCameraActivation(ownedCamera);
        try { AndroidNativeSourceViewOnlyRigMarker.BeginOwnedSceneCameraActivation(otherCamera); }
        catch (InvalidOperationException) { duplicateRefused = true; }
        Check(duplicateRefused, "overlapping activation token is refused");
        AndroidNativeSourceViewOnlyRigMarker.EndOwnedSceneCameraActivation(ownedCamera);
        Console.WriteLine("PASS owned-only original EarlyUpdate pump, exact SceneCamera Console scope, and reduced-fidelity status");
    }
}
