using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace UnityEngine
{
    public static class Application { public static string streamingAssetsPath = "/fixture"; }
}

internal interface IGameAudioOriginalPassivePcmCapture { }
internal interface IGameAudioOriginalStartupPreparation
{
    bool Prepared { get; }
    string Refusal { get; }
    IEnumerator PrepareBeforeExistingManagerInit();
    void ArmNativeMonitorBeforeInit();
    void AbandonBeforeOriginalInit();
    void PostExactControlMarker();
    bool NativeExactControlObserved();
    bool NativeControlObservationFailed { get; }
    void ObserveEngineTermReturned();
    void ObserveCallbackManagerTermReturned();
}
internal sealed class NativeWwiseDiagPInvokeApi { }
internal sealed class NativeWwiseMonitorLease
{
    internal NativeWwiseMonitorLease(NativeWwiseDiagPInvokeApi api) { }
}
internal sealed class GameAudioOriginalAndroidNativeBootstrap
{
    internal GameAudioOriginalAndroidNativeBootstrap(NativeWwiseMonitorLease lease) { }
    internal IGameAudioOriginalPassivePcmCapture CreatePassivePcmCaptureOwner(bool requested, bool specific) => null;
}
internal sealed class GameAudioOriginalPreparation : IGameAudioOriginalStartupPreparation
{
    internal GameAudioOriginalPreparation(string root, IEnumerable<string> names, string receipt, GameAudioOriginalAndroidNativeBootstrap native) { }
    public bool Prepared => true;
    public string Refusal => null;
    public IEnumerator PrepareBeforeExistingManagerInit() { yield break; }
    public void ArmNativeMonitorBeforeInit() { }
    public void AbandonBeforeOriginalInit() { }
    public void PostExactControlMarker() { }
    public bool NativeExactControlObserved() => false;
    public bool NativeControlObservationFailed => false;
    public void ObserveEngineTermReturned() { }
    public void ObserveCallbackManagerTermReturned() { }
}
internal sealed class GameAudioOriginalRequest
{
    internal GameAudioOriginalRequest(bool requested, string[] names, IGameAudioOriginalStartupPreparation preparation) { }
    internal GameAudioOriginalRequest(bool requested, IEnumerable<string> names, IGameAudioOriginalStartupPreparation preparation,
        bool captureRequested, IGameAudioOriginalPassivePcmCapture capture, bool musicOutputRequested, bool afterAuthoritySkillRequested) { }
}
