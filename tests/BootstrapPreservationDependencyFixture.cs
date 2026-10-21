using System;

internal sealed class GameAudioOriginalAndroidNativeBootstrap
{
    internal NativeWwiseMonitorLease MonitorLease { get; set; }
    internal bool OwnsMonitorLease(NativeWwiseMonitorLease lease) { return Object.ReferenceEquals(MonitorLease, lease); }
}

internal sealed class NativeWwiseMonitorLease
{
    internal bool CaptureSafeBeforeEngineTerm { get; set; }
    internal void CleanupOwnedCaptureBeforeEngineTerm() { }
}

internal sealed class PassivePcmCaptureReport
{
    internal ulong CallbackCount, FrameCount, SampleCount, FiniteSamples, NonzeroFiniteSamples;
    internal ulong NonfiniteSamples, RejectedBuffers, CappedBuffers;
    internal bool OutputIdentityObserved;
    internal bool CaptureOutputDeviceIdObserved;
    internal ulong CaptureOutputDeviceId;
}

internal sealed class PassivePcmCaptureWindow
{
    internal PassivePcmCaptureWindow(NativeWwiseMonitorLease lease, bool requested,
        Action<Action> install, Func<Action> read, Action<Exception> refuse) { }
    internal float WindowStartRealtimeSinceStartup { get; set; }
    internal ulong WindowStartServiceFrames { get; set; }
    internal string State { get; set; }
    internal string StopReason { get; set; }
    internal string Failure { get; set; }
    internal PassivePcmCaptureReport Report { get; } = new PassivePcmCaptureReport();
    internal bool RequestGameplayArm() { return true; }
    internal void FinishGameplayWindow() { }
    internal bool Start(float time, bool ownerReady, bool exactControlObserved, bool serviceObserved, ulong frames) { return true; }
    internal void Tick(float time, bool ownerReady, bool exactControlObserved, ulong frames) { }
    internal void RegisterBeforeEngineTermParticipant(Action participant) { }
    internal void BeforeOriginalEngineTerm() { }
}

internal static class GameAudioOriginalOwner
{
    internal static void RequestPassivePcmTerminalStop(string reason) { }
}

internal static class OriginalOwnerProbeObserver
{
    internal static class Observer
    {
        public static Action BeforeEngineTerm;
        public static void RecordBeforeEngineTerm() { BeforeEngineTerm?.Invoke(); }
    }
}
