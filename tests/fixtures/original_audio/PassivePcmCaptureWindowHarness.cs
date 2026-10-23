using System;
using System.Globalization;

internal sealed class FakePcmApi : INativeWwiseDiagApi
{
    internal readonly long[] Values = new long[24];
    internal bool ThrowSnapshot;
    internal int RegisterCalls;
    internal int UnregisterCalls;
    internal uint RegisteredMode;
    internal ulong RegisteredOutput;
    internal uint UnregisteredMode;
    internal ulong UnregisteredOutput;
    internal bool FailRegistration;
    internal bool RefuseUnregisterPairMismatch;
    internal int EngineTermReturns;

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
    public void EngineTermReturned() { EngineTermReturns++; Values[12] = 1; }
    public void CallbackManagerTermReturned() { Values[20] = 1; }
    public int DisarmAfterTerm() { Values[13] = 2; return 1; }
    public int RegisterCapture(uint selectorMode, ulong outputSelector)
    {
        RegisterCalls++;
        RegisteredMode = selectorMode;
        RegisteredOutput = outputSelector;
        Values[11] = 1;
        Values[15] = 1;
        Values[17] = 1;
        return FailRegistration ? 0 : 1;
    }
    public int UnregisterCapture(uint selectorMode, ulong outputSelector)
    {
        UnregisterCalls++;
        UnregisteredMode = selectorMode;
        UnregisteredOutput = outputSelector;
        if (RefuseUnregisterPairMismatch &&
            (selectorMode != RegisteredMode || outputSelector != RegisteredOutput)) return 0;
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
        Check(api.RegisteredMode == 0 && api.RegisteredOutput == 0 &&
            api.UnregisteredMode == api.RegisteredMode && api.UnregisteredOutput == api.RegisteredOutput,
            "default main-output selection is registered and unregistered with the same exact selector");
        ownedGuard();
        Check(lease.CaptureSafeBeforeEngineTerm, "original Term guard accepts only confirmed removal");
    }


    private static void ActiveWindowReportExposesValidatedCachedIdentityForJoin()
    {
        const ulong outputId = 4129766362UL;
        var api = new FakePcmApi();
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true,
            delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        GameAudioOriginalPassivePcmCaptureSelection selection;
        Check(GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(true, true, true, outputId, out selection),
            "specific output selector is valid");
        Check(window.RequestGameplayArm(selection), "active identity fixture arms");
        Check(window.Start(10f, true, true, true, 1), "active identity fixture starts from exact live lease");
        var initial = window.Report;
        Check(initial.State == "capturing" && initial.CallbackCount == 0 &&
            !initial.CaptureOutputDeviceIdObserved,
            "active state alone does not invent callback identity before its first observation");
        api.AddPcm();
        api.Values[18] = unchecked((long)outputId);
        window.Tick(11.1f, true, true, 2); // Existing periodic ObserveSnapshot refreshes latest.
        var report = window.Report; // This is the report forwarded by OriginalGameAudioPassivePcmOwner.
        Check(report.State == "capturing", "active report preserves the active state");
        Check(report.CallbackCount == 2 && report.FrameCount == 2 && report.SampleCount == 8,
            "active report exposes only counters from the latest validated cached lease snapshot");
        Check(report.CaptureSelectorObserved && report.CaptureOutputDeviceIdObserved && report.CaptureOutputDeviceId == outputId,
            "active report exposes exact frozen selector and observed callback identity");
        Check(MusicPcmJoinObserver.IsExactWindowEligible(
            report.State == "capturing", true, true, report.CaptureSelectorObserved,
            report.CaptureSelection.Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.SpecificOutput &&
                report.CaptureSelection.SpecificOutputIdKnown, report.CaptureSelection.SpecificOutputId,
            report.CaptureOutputDeviceIdObserved, report.CaptureOutputDeviceId,
            true, outputId, true, false),
            "the unchanged exact-output join eligibility gate admits the truthful active snapshot");
        Check(api.RegisterCalls == 1 && api.UnregisterCalls == 0,
            "reading an active report does not add native calls or stop the capture");
        window.FinishGameplayWindow();
        var stopped = window.Report;
        Check(stopped.State == "captured" && stopped.CaptureOutputDeviceIdObserved && stopped.CaptureOutputDeviceId == outputId,
            "normal stop still produces the terminal report without changing active semantics");
        Check(!MusicPcmJoinObserver.IsExactWindowEligible(
            stopped.State == "capturing", true, true, stopped.CaptureSelectorObserved,
            true, outputId, stopped.CaptureOutputDeviceIdObserved, stopped.CaptureOutputDeviceId,
            true, outputId, true, false),
            "retained terminal output identity cannot admit a query after capture stops");
        Check(api.RegisterCalls == 1 && api.UnregisterCalls == 1,
            "only the normal owner stop unregisters the callback");
    }

    private static void UnknownSnapshotUsesOneCleanupOnlyUnregister()
    {
        var api = new FakePcmApi();
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true, delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        Check(window.RequestGameplayArm(), "gameplay arm accepted");
        Check(window.Start(0f, true, true, true, 1), "capture starts before injected snapshot failure");
        api.AddPcm();
        window.Tick(1.1f, true, true, 2); // A valid cached live sample precedes the injected unknown result.
        Check(window.Report.SampleCount == 8, "the latest validated active snapshot is visible before failure");
        api.ThrowSnapshot = true;
        window.Tick(2.2f, true, true, 3);
        Check(window.State == "outcome_unknown" && !lease.CaptureSafeBeforeEngineTerm, "snapshot failure retains an unknown live registration");
        Check(window.Report.SampleCount == 0 && !window.Report.CaptureOutputDeviceIdObserved,
            "unknown registration/removal state does not expose the last active snapshot as current telemetry");
        api.ThrowSnapshot = false;
        ownedGuard();
        Check(api.UnregisterCalls == 1 && lease.CaptureSafeBeforeEngineTerm, "pre-Term cleanup performs one reverse call without resnapshot");
        Check(window.Report.SampleCount == 0, "unknown snapshot is not promoted to a successful PCM report");
    }

    private static PassivePcmCaptureReport CaptureIdentity(ulong outputId, bool callback)
    {
        var api = new FakePcmApi();
        api.Values[18] = unchecked((long)outputId);
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true,
            delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        Check(window.RequestGameplayArm(), "identity fixture gameplay arm accepted");
        Check(window.Start(1f, true, true, true, 1), "identity fixture capture starts");
        if (callback)
        {
            api.AddPcm();
            api.Values[18] = unchecked((long)outputId);
            window.Tick(1.1f, true, true, 2);
        }
        window.FinishGameplayWindow();
        return window.Report;
    }

    private static void FullWidthOutputIdsSurviveSnapshotAndDecimalEncoding()
    {
        const ulong highBit = 0xF123456789ABCDEFUL;
        const ulong maximum = ulong.MaxValue;
        var highReport = CaptureIdentity(highBit, true);
        Check(highReport.CaptureOutputDeviceIdObserved && highReport.CaptureOutputDeviceId == highBit,
            "slot 18 high-bit output identity remains an exact unsigned 64-bit value");
        string highDecimal = GameAudioOriginalPassivePcmIdentity.ToDecimalString(highReport.CaptureOutputDeviceId);
        Check(highDecimal == "17375808098319191535" && ulong.Parse(highDecimal, CultureInfo.InvariantCulture) == highBit,
            "high-bit companion decimal string round-trips without floating-point conversion");

        var maximumReport = CaptureIdentity(maximum, true);
        Check(maximumReport.CaptureOutputDeviceIdObserved && maximumReport.CaptureOutputDeviceId == maximum,
            "slot 18 preserves ulong.MaxValue bit-for-bit");
        string maximumDecimal = GameAudioOriginalPassivePcmIdentity.ToDecimalString(maximumReport.CaptureOutputDeviceId);
        Check(maximumDecimal == "18446744073709551615" && ulong.Parse(maximumDecimal, CultureInfo.InvariantCulture) == maximum,
            "maximum unsigned ID has an exact decimal JSON companion");

        var zeroReport = CaptureIdentity(0, true);
        Check(zeroReport.CaptureOutputDeviceIdObserved && zeroReport.CaptureOutputDeviceId == 0,
            "zero is retained as a known callback value rather than treated as unknown");

        var staleReport = CaptureIdentity(maximum, false);
        Check(!staleReport.CaptureOutputDeviceIdObserved && staleReport.CaptureOutputDeviceId == 0,
            "a nonzero stale slot without a callback in this window remains unknown");
    }


    private static void SpecificOutputPreservesFullWidthPairThroughRemoval()
    {
        const ulong highBitOutput = 0xF123456789ABCDEFUL;
        GameAudioOriginalPassivePcmCaptureSelection selection;
        Check(GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, true, highBitOutput, out selection), "exact owned successful output is selectable");
        Check(selection.Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.SpecificOutput &&
            selection.IsWellFormed && selection.NativeOutputSelector == highBitOutput,
            "specific selector preserves all 64 output-ID bits");

        var api = new FakePcmApi();
        api.RefuseUnregisterPairMismatch = true;
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        var window = new PassivePcmCaptureWindow(lease, true,
            delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, null);
        Check(window.RequestGameplayArm(selection), "specific-output selection arms at the gameplay boundary");
        Check(window.Start(1f, true, true, true, 1), "specific-output capture starts after readiness and a service frame");
        Check(api.RegisteredMode == (uint)GameAudioOriginalPassivePcmCaptureSelectorMode.SpecificOutput &&
            api.RegisteredOutput == highBitOutput, "register receives the exact mode and high-bit output ID");
        api.AddPcm();
        api.Values[18] = unchecked((long)highBitOutput);
        window.Tick(1.1f, true, true, 2);
        window.FinishGameplayWindow();
        var report = window.Report;
        Check(report.State == "captured" && report.CaptureSelectorObserved &&
            report.CaptureSelection.SpecificOutputId == highBitOutput,
            "report retains the frozen specific-output selector");
        Check(report.CaptureOutputDeviceIdObserved && report.CaptureOutputDeviceId == highBitOutput,
            "callback output identity remains a distinct exact unsigned 64-bit value");
        Check(api.UnregisterCalls == 1 && api.UnregisteredMode == api.RegisteredMode &&
            api.UnregisteredOutput == api.RegisteredOutput && lease.CaptureSafeBeforeEngineTerm,
            "unregister uses the exact registered selector pair");
    }

    private static void InvalidOrFailedSpecificOutputNeverFallsBackToMain()
    {
        GameAudioOriginalPassivePcmCaptureSelection selection;
        Check(!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            false, true, true, 55, out selection), "unowned output is refused");
        Check(!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, false, true, 55, out selection), "unsuccessful AddOutput is refused");
        Check(!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, false, 55, out selection), "unknown output ID is refused");
        Check(!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, true, 0, out selection), "main-output sentinel cannot masquerade as specific output");
        Check(!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, true, ulong.MaxValue, out selection), "invalid maximum sentinel is refused");

        Check(GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, true, 55, out selection), "valid selector setup");
        var failedApi = new FakePcmApi { FailRegistration = true };
        var failedLease = ReadyLease(failedApi);
        Action failedGuard = null;
        var failedWindow = new PassivePcmCaptureWindow(failedLease, true,
            delegate(Action value) { failedGuard = value; }, delegate { return failedGuard; }, null);
        Check(failedWindow.RequestGameplayArm(selection), "valid selector can arm before native result");
        Check(!failedWindow.Start(1f, true, true, true, 1), "known registration failure refuses capture");
        failedWindow.BeforeOriginalEngineTerm();
        Check(failedApi.RegisterCalls == 1 && failedApi.UnregisterCalls == 0 &&
            failedLease.CaptureSafeBeforeEngineTerm,
            "known failed registration owns no callback and never falls back or unregisters");
    }

    private static void UnregisterPairFailureKeepsTermFailClosed()
    {
        GameAudioOriginalPassivePcmCaptureSelection selection;
        Check(GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(
            true, true, true, 91, out selection), "valid selector setup for removal refusal");
        var api = new FakePcmApi { RefuseUnregisterPairMismatch = true };
        var lease = ReadyLease(api);
        Action ownedGuard = null;
        int refusals = 0;
        var window = new PassivePcmCaptureWindow(lease, true,
            delegate(Action value) { ownedGuard = value; }, delegate { return ownedGuard; }, error => refusals++);
        Check(window.RequestGameplayArm(selection), "pair-refusal capture arms");
        Check(window.Start(1f, true, true, true, 1), "pair-refusal capture starts");
        api.RegisteredOutput = 92; // Simulate an inconsistent native registration ledger.
        window.FinishGameplayWindow();
        Check(window.State == "outcome_unknown" && !lease.CaptureSafeBeforeEngineTerm,
            "inconsistent output pair leaves callback ownership unresolved");
        bool refused = false;
        try { window.BeforeOriginalEngineTerm(); }
        catch (InvalidOperationException) { refused = true; }
        Check(refused && refusals == 1 && api.UnregisterCalls == 1 && api.EngineTermReturns == 0,
            "wrong selector pair refuses the existing Term guard without retry or Term marker");
    }

    private static int Main()
    {
        NoOpGuardRefusesBeforeRegistration();
        DefaultOffNeverCallsNativeCapture();
        BoundedCaptureRemovesBeforeTerm();
        ActiveWindowReportExposesValidatedCachedIdentityForJoin();
        UnknownSnapshotUsesOneCleanupOnlyUnregister();
        FullWidthOutputIdsSurviveSnapshotAndDecimalEncoding();
        SpecificOutputPreservesFullWidthPairThroughRemoval();
        InvalidOrFailedSpecificOutputNeverFallsBackToMain();
        UnregisterPairFailureKeepsTermFailClosed();
        Console.WriteLine("PASS PCM guard, bounded counters, active exact-output join eligibility, selector pairing, full-width IDs, and fail-closed cleanup");
        return 0;
    }
}
