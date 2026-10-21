using System;

internal sealed class FakePcmApi : INativeWwiseDiagApi
{
    internal readonly long[] Values = new long[24];
    internal bool ThrowSnapshot;
    internal int RegisterCalls;
    internal int UnregisterCalls;

    internal FakePcmApi()
    {
        Values[14] = 1;
        Values[21] = 3;
    }

    public int Arm() { Values[13] = 1; return 1; }
    public int IsArmed() { return 1; }
    public int PostControl() { Values[22]++; return 1; }
    public int MarkEngineInitAttempted() { Values[23] = 1; return 1; }
    public int DisarmBeforeInit() { Values[13] = 2; return 1; }
    public void EngineTermReturned() { Values[12] = 1; }
    public void CallbackManagerTermReturned() { Values[20] = 1; }
    public int DisarmAfterTerm() { Values[13] = 2; return 1; }
    public int RegisterCapture()
    {
        RegisterCalls++;
        Values[11] = 1;
        Values[15] = 1;
        Values[17] = 1;
        return 1;
    }
    public int UnregisterCapture()
    {
        UnregisterCalls++;
        Values[11] = 0;
        Values[16] = 1;
        return 1;
    }
    public long[] Snapshot()
    {
        if (ThrowSnapshot) throw new InvalidOperationException("synthetic snapshot refusal");
        return (long[])Values.Clone();
    }

    internal void AddPcm()
    {
        Values[3] += 2;
        Values[4] += 2;
        Values[5] += 8;
        Values[6] += 8;
        Values[7] += 3;
        Values[18] = 77;
    }
}

internal static class PassivePcmCaptureWindowHarness
{
    private static void Check(bool value, string message)
    {
        if (!value) throw new Exception(message);
    }

    private static NativeWwiseMonitorLease ReadyLease(FakePcmApi api)
    {
        var lease = new NativeWwiseMonitorLease(api);
        lease.ArmBeforeInit();
        lease.MarkEngineInitAttempted();
        lease.BeginPostInitControlObservation();
        lease.PollPostInitControl();
        Check(lease.PostInitControlObserved, "exact control witness is required before capture");
        return lease;
    }

    private static void NoOpGuardRefusesBeforeRegistration()
    {
        var api = new FakePcmApi();
        var window = new PassivePcmCaptureWindow(ReadyLease(api), true, delegate(Action ignored) { }, delegate { return null; }, null);
        Check(!window.RequestGameplayArm(), "missing guard must refuse gameplay arm");
        Check(!window.Start(100f, true, true, true, 1), "missing guard must refuse capture startup");
        Check(api.RegisterCalls == 0, "guard failure must happen before native registration");
    }

    private static void DefaultOffNeverCallsNativeCapture()
    {
        var api = new FakePcmApi();
        var window = new PassivePcmCaptureWindow(ReadyLease(api), false, delegate(Action ignored) { }, delegate { return null; }, null);
        Check(!window.RequestGameplayArm(), "default-off selection cannot arm");
        Check(!window.Start(0f, true, true, true, 1), "default-off selection cannot start");
        window.FinishGameplayWindow();
        window.FinishGameplayWindow();
        Check(api.RegisterCalls == 0 && api.UnregisterCalls == 0, "default-off close never calls native capture");
    }

    private static void BoundedCaptureRemovesBeforeTerm()
    {
        var api = new FakePcmApi();
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true, delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        Check(!window.Start(100f, true, true, true, 1), "capture must wait for the playable-world arm");
        Check(api.RegisterCalls == 0, "readiness alone cannot register a capture callback");
        Check(window.RequestGameplayArm(), "verified playable-world boundary arms one capture");
        Check(window.Start(100f, true, true, true, 1), "ready original render frame admits one armed capture");
        api.AddPcm();
        window.Tick(101.1f, true, true, 2);
        window.FinishGameplayWindow();
        window.FinishGameplayWindow();
        var report = window.Report;
        Check(report.State == "captured" && report.StopReason == "playable_session_completed" && report.CallbackCount == 2 && report.FrameCount == 2,
            "partial gameplay-window counters are reported after early session completion");
        Check(report.SampleCount == 8 && report.FiniteSamples == 8 && report.NonzeroFiniteSamples == 3, "finite and nonzero counters are preserved");
        Check(report.OutputIdentityObserved && api.UnregisterCalls == 1 && lease.CaptureSafeBeforeEngineTerm, "owned callback is removed exactly once before Term");
        ownedGuard();
        Check(lease.CaptureSafeBeforeEngineTerm, "original Term guard accepts only confirmed removal");
    }

    private static void UnknownSnapshotUsesOneCleanupOnlyUnregister()
    {
        var api = new FakePcmApi();
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true, delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        Check(window.RequestGameplayArm(), "gameplay arm accepted");
        Check(window.Start(0f, true, true, true, 1), "capture starts before injected snapshot failure");
        api.ThrowSnapshot = true;
        window.Tick(1.1f, true, true, 2);
        Check(window.State == "outcome_unknown" && !lease.CaptureSafeBeforeEngineTerm, "snapshot failure retains an unknown live registration");
        api.ThrowSnapshot = false;
        ownedGuard();
        Check(api.UnregisterCalls == 1 && lease.CaptureSafeBeforeEngineTerm, "pre-Term cleanup performs one reverse call without resnapshot");
        Check(window.Report.SampleCount == 0, "unknown snapshot is not promoted to a successful PCM report");
    }

    private static int Main()
    {
        NoOpGuardRefusesBeforeRegistration();
        DefaultOffNeverCallsNativeCapture();
        BoundedCaptureRemovesBeforeTerm();
        UnknownSnapshotUsesOneCleanupOnlyUnregister();
        Console.WriteLine("PASS PCM owner guard, bounded counters, and unknown-outcome cleanup contract");
        return 0;
    }
}
