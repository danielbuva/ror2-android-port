using System;
using System.Reflection;
using RoR2;
using UnityEngine;

sealed class Owner : MonoBehaviour, ICameraStateProvider { }

static class DelegateRetryProgram
{
    static void Check(bool value, string name)
    {
        if (!value)
            throw new Exception("failed: " + name);
    }

    static AndroidNativeSourceViewOnlyRigMarker Bind(
        GameObject rigObject, CameraRigController rig, GameObject target, Owner owner)
    {
        var marker = rigObject.Add(new AndroidNativeSourceViewOnlyRigMarker());
        marker.Bind(rig, target, owner);
        typeof(AndroidNativeSourceViewOnlyRigMarker)
            .GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(marker, null);
        return marker;
    }

    static Delegate BoundDelegate(AndroidNativeSourceViewOnlyRigMarker marker)
    {
        return (Delegate)typeof(AndroidNativeSourceViewOnlyRigMarker)
            .GetField("originalEarlyUpdate", BindingFlags.Instance | BindingFlags.NonPublic)
            .GetValue(marker);
    }

    static void Pump(AndroidNativeSourceViewOnlyRigMarker marker)
    {
        typeof(AndroidNativeSourceViewOnlyRigMarker)
            .GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(marker, null);
    }

    static void Main()
    {
        var rigObject = new GameObject();
        var rig = rigObject.Add(new CameraRigController());
        var owner = rigObject.Add(new Owner());
        var target = new GameObject();
        var marker = Bind(rigObject, rig, target, owner);

        Check(BoundDelegate(marker) == null, "unready nextTarget does not bind during Awake");
        Pump(marker);
        Check(rig.originalCalls == 0 && BoundDelegate(marker) == null, "unready nextTarget cannot pump or bind");

        rig.nextTarget = target;
        owner.isActiveAndEnabled = false;
        Pump(marker);
        Check(rig.originalCalls == 0 && BoundDelegate(marker) == null, "inactive owner cannot bind or pump");

        owner.isActiveAndEnabled = true;
        Time.deltaTime = 0f;
        Pump(marker);
        var firstBinding = BoundDelegate(marker);
        Check(firstBinding != null && rig.originalCalls == 1 && rig.target == target,
            "later exact readiness binds and dispatches original callback");
        Check(!marker.IsOriginalUpdateContextReadyFor(rig, target, owner),
            "zero-time callback does not claim source camera context");

        Time.deltaTime = 0.016f;
        Pump(marker);
        Check(rig.originalCalls == 2 && ReferenceEquals(firstBinding, BoundDelegate(marker)),
            "later pump reuses the single bound delegate");
        Check(marker.IsOriginalUpdateContextReadyFor(rig, target, owner),
            "nonzero original callback admits its context");

        rig.nextTarget = new GameObject();
        Pump(marker);
        Check(rig.originalCalls == 2 && !marker.IsOriginalUpdateContextReadyFor(rig, target, owner),
            "mismatched nextTarget refuses callback and context");

        rig.nextTarget = target;
        rig.throwOnOriginalCall = true;
        bool callbackFailed = false;
        try
        {
            Pump(marker);
        }
        catch (TargetInvocationException exception)
        {
            callbackFailed = exception.InnerException is InvalidOperationException;
        }
        Check(callbackFailed && !marker.IsOriginalUpdateContextReadyFor(rig, target, owner),
            "original callback exception propagates and clears context admission");
        rig.throwOnOriginalCall = false;
        Pump(marker);
        Check(rig.originalCalls == 4 && marker.IsOriginalUpdateContextReadyFor(rig, target, owner),
            "subsequent exact callback can recover context after exception");

        Console.WriteLine("PASS delayed exact-owner binding, single delegate reuse, target/time gates, and callback exception semantics");
    }
}
