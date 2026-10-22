using System;

internal sealed class NativeWwiseDiagSnapshot
{
    internal int ArmedState, EngineInitAttempted, CaptureRegistered, CaptureUsed;
    internal ulong SampleCount, CaptureCallbacks, CaptureFrames, FiniteSamples, NonzeroFiniteSamples;
    internal ulong NonfiniteSamples, RejectedBuffers, CappedBuffers, CaptureOutputId;
    internal bool PcmCountersCoherentAfterQuiescence;
}

internal sealed class NativeWwiseMonitorLease
{
    internal bool CaptureRegisterAttempted { get; set; }
    internal bool CaptureRegisterResultKnown { get; set; }
    internal bool CaptureRegisterCallSucceeded { get; set; }
    internal bool CaptureUnregisterCallSucceeded { get; set; }
    internal bool CaptureRegistered { get; set; }
    internal bool CaptureSafeBeforeEngineTerm { get; set; } = true;
    internal bool OutcomeUnknown { get; set; }
    internal bool EngineTermReturnedState { get; set; }
    internal bool CallbackManagerTermReturnedState { get; set; }
    internal bool DisarmAttempted { get; set; }
    internal ulong ArmedState { get; set; }
    internal NativeWwiseDiagSnapshot ObserveSnapshot() { throw new InvalidOperationException("unexpected capture snapshot"); }
    internal NativeWwiseDiagSnapshot RegisterCaptureCallback(GameAudioOriginalPassivePcmCaptureSelection selection) { throw new InvalidOperationException("unexpected capture registration"); }
    internal int UnregisterCalls { get; private set; }
    internal NativeWwiseDiagSnapshot UnregisterCaptureCallback()
    {
        UnregisterCalls++;
        CaptureUnregisterCallSucceeded = true;
        CaptureRegistered = false;
        return new NativeWwiseDiagSnapshot { CaptureRegistered = 0, PcmCountersCoherentAfterQuiescence = true };
    }
    internal void CleanupOwnedCaptureBeforeEngineTerm() { throw new InvalidOperationException("unexpected capture cleanup"); }
}

internal static class InstalledApiCoreFields
{
    internal static Action ApiBeforeEngineTerm;
    internal static Action CoreBeforeEngineTerm;

    internal static void Install(Action handler)
    {
        ApiBeforeEngineTerm = handler;
        CoreBeforeEngineTerm = handler;
    }

    internal static Action Read()
    {
        if (!Object.ReferenceEquals(ApiBeforeEngineTerm, CoreBeforeEngineTerm))
            throw new InvalidOperationException("API/Core guard identity mismatch");
        return ApiBeforeEngineTerm;
    }

    internal static void InvokeApiTermGuard() { ApiBeforeEngineTerm?.Invoke(); }
}
