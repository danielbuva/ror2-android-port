using System;
using System.Runtime.InteropServices;

// Host-testable lease/state machine for the authored single-library bridge.
// INativeWwiseDiagApi is injected only for host contract tests; a fake instance
// does not establish device/native callback evidence.
internal interface INativeWwiseDiagApi
{
    int Arm();
    int IsArmed();
    int PostControl();
    int MarkEngineInitAttempted();
    int DisarmBeforeInit();
    void EngineTermReturned();
    void CallbackManagerTermReturned();
    int DisarmAfterTerm();
    int RegisterCapture();
    int UnregisterCapture();
    long[] Snapshot();
}

internal sealed class NativeWwiseDiagRefusalException : InvalidOperationException
{
    internal NativeWwiseDiagRefusalException(string message) : base(message) { }
}

internal sealed class NativeWwiseDiagSnapshot
{
    internal const int SlotCount = 24;
    internal const ulong ExpectedSchema = 3;
    internal readonly long[] Slots;

    private NativeWwiseDiagSnapshot(long[] values) { Slots = values; }

    internal ulong this[int index] { get { return unchecked((ulong)Slots[index]); } }
    internal int Signed(int index) { return unchecked((int)Slots[index]); }
    internal ulong Callbacks { get { return this[0]; } }
    internal ulong Errors { get { return this[1]; } }
    internal ulong Warnings { get { return this[2]; } }
    internal ulong CaptureCallbacks { get { return this[3]; } }
    internal ulong CaptureFrames { get { return this[4]; } }
    internal ulong SampleCount { get { return this[5]; } }
    internal ulong FiniteSamples { get { return this[6]; } }
    internal ulong NonzeroFiniteSamples { get { return this[7]; } }
    internal ulong NonfiniteSamples { get { return this[8]; } }
    internal ulong RejectedBuffers { get { return this[9]; } }
    internal ulong CappedBuffers { get { return this[10]; } }
    internal ulong CaptureRegistered { get { return this[11]; } }
    internal ulong EngineTermReturnedValue { get { return this[12]; } }
    internal ulong ArmedState { get { return this[13]; } }
    internal int MonitorInstallResult { get { return Signed(14); } }
    internal int CaptureRegisterResult { get { return Signed(15); } }
    internal int CaptureUnregisterResult { get { return Signed(16); } }
    internal ulong CaptureUsed { get { return this[17]; } }
    internal ulong CaptureOutputId { get { return this[18]; } }
    internal int DisarmResult { get { return Signed(19); } }
    internal ulong CallbackManagerTermReturnedValue { get { return this[20]; } }
    internal ulong Schema { get { return this[21]; } }
    internal ulong MonitorControlCallbacks { get { return this[22]; } }
    internal ulong EngineInitAttempted { get { return this[23]; } }

    internal static NativeWwiseDiagSnapshot Parse(long[] values, NativeWwiseDiagSnapshot previous)
    {
        if (values == null || values.Length != SlotCount)
            throw new InvalidOperationException("Native diagnostic snapshot must contain exactly 24 slots.");
        var snapshot = new NativeWwiseDiagSnapshot((long[])values.Clone());
        if (snapshot.Schema != ExpectedSchema)
            throw new InvalidOperationException("Native diagnostic snapshot schema is absent or unsupported.");
        for (int i = 0; i < SlotCount; i++)
        {
            // Four AKRESULT slots are signed int32 values widened by the native bridge.
            if (i == 14 || i == 15 || i == 16 || i == 19) continue;
            // AkOutputDeviceID is an opaque AkUInt64; preserve all 64 bits.
            if (i != 18 && snapshot[i] > long.MaxValue)
                throw new InvalidOperationException("Native diagnostic counter exceeds the managed range.");
            bool monotonic = i <= 10 || i == 12 || i == 13 || i == 17 || i == 20 || i == 22 || i == 23;
            if (previous != null && monotonic && snapshot[i] < previous[i])
                throw new InvalidOperationException("Native diagnostic counters moved backwards.");
        }
        if (snapshot.SampleCount > 1_048_576 || snapshot.FiniteSamples > 1_048_576 ||
            snapshot.NonzeroFiniteSamples > 1_048_576 || snapshot.NonfiniteSamples > 1_048_576 ||
            snapshot.CaptureRegistered > 1 || snapshot.EngineTermReturnedValue > 1 ||
            snapshot.CallbackManagerTermReturnedValue > 1 || snapshot.CaptureUsed > 1 ||
            snapshot.EngineInitAttempted > 1 || snapshot.ArmedState > 3)
            throw new InvalidOperationException("Native diagnostic snapshot violates counter or state invariants.");
        if (previous != null && snapshot.ArmedState < previous.ArmedState)
            throw new InvalidOperationException("Native diagnostic monitor state moved backwards.");
        return snapshot;
    }

    internal bool PcmCountersCoherentAfterQuiescence
    {
        get
        {
            return NonzeroFiniteSamples <= FiniteSamples && FiniteSamples <= SampleCount &&
                NonfiniteSamples <= SampleCount && FiniteSamples + NonfiniteSamples == SampleCount;
        }
    }
}

// Native callback totals are cumulative and never reset between startup phases.
// Freeze the two report values at their actual observation points instead of
// exposing a hard-coded zero or a later cumulative total as a phase count.
internal sealed class NativeMonitorCallbackPhaseCounts
{
    private bool preInitCaptured;
    private bool postInitCaptured;
    private ulong preInitCallbacks;
    private ulong postInitCallbacks;

    internal ulong PreInitCallbacks { get { return preInitCaptured ? preInitCallbacks : 0; } }
    internal ulong PostInitCallbacks { get { return postInitCaptured ? postInitCallbacks : 0; } }

    internal void CapturePreInit(NativeWwiseDiagSnapshot snapshot)
    {
        if (snapshot == null) throw new ArgumentNullException("snapshot");
        if (preInitCaptured || postInitCaptured)
            throw new InvalidOperationException("Pre-Init monitor callback snapshot is already frozen.");
        preInitCallbacks = snapshot.Callbacks;
        preInitCaptured = true;
    }

    internal void CapturePostInitAfterExactControl(NativeWwiseDiagSnapshot snapshot, bool exactControlObserved)
    {
        if (!exactControlObserved)
            throw new InvalidOperationException("Post-Init callback snapshot requires the exact native control marker.");
        if (snapshot == null) throw new ArgumentNullException("snapshot");
        if (!preInitCaptured || postInitCaptured)
            throw new InvalidOperationException("Post-Init monitor callback snapshot is outside its one-shot phase.");
        if (snapshot.Callbacks < preInitCallbacks)
            throw new InvalidOperationException("Native monitor callback total decreased across the phase boundary.");
        postInitCallbacks = snapshot.Callbacks - preInitCallbacks;
        postInitCaptured = true;
    }
}

internal sealed class NativeWwiseMonitorLease
{
    private const int AkSuccess = 1;
    private readonly INativeWwiseDiagApi api;
    private NativeWwiseDiagSnapshot latest;
    private bool armAttempted, captureRegisterAttempted, captureUnregisterAttempted;
    private bool captureRegisterResultKnown, captureRegisterCallSucceeded, captureUnregisterCallSucceeded;
    private bool engineInitAttempted, engineTermReturned, callbackManagerTermReturned, disarmAttempted;
    private bool postInitControlAttempted, postInitControlObserved;
    private ulong postInitControlBaseline;
    private bool outcomeUnknown;

    internal NativeWwiseMonitorLease(INativeWwiseDiagApi api)
    {
        this.api = api ?? throw new ArgumentNullException(nameof(api));
    }

    internal bool OutcomeUnknown { get { return outcomeUnknown; } }
    internal bool Armed { get { return latest != null && latest.ArmedState == 1; } }
    internal bool CaptureRegistered { get { return latest != null && latest.CaptureRegistered == 1; } }
    internal bool CaptureRegisterAttempted { get { return captureRegisterAttempted; } }
    internal bool CaptureRegisterResultKnown { get { return captureRegisterResultKnown; } }
    internal bool CaptureRegisterCallSucceeded { get { return captureRegisterCallSucceeded; } }
    internal bool CaptureUnregisterCallSucceeded { get { return captureUnregisterCallSucceeded; } }
    // Term is safe with respect to this callback only when a registration
    // result is known and either it failed or its matching unregister succeeded.
    internal bool CaptureSafeBeforeEngineTerm
    {
        get
        {
            if (!captureRegisterAttempted) return true;
            if (!captureRegisterResultKnown) return false;
            if (!captureRegisterCallSucceeded) return true;
            return captureUnregisterCallSucceeded;
        }
    }
    internal bool CaptureUnregisterAttempted { get { return captureUnregisterAttempted; } }
    internal bool EngineInitAttempted { get { return engineInitAttempted || (latest != null && latest.EngineInitAttempted == 1); } }
    internal bool EngineTermReturnedState { get { return engineTermReturned; } }
    internal bool CallbackManagerTermReturnedState { get { return callbackManagerTermReturned; } }
    internal bool DisarmAttempted { get { return disarmAttempted; } }
    internal bool PostInitControlAttempted { get { return postInitControlAttempted; } }
    internal bool PostInitControlObserved { get { return postInitControlObserved; } }
    internal ulong ArmedState { get { return latest == null ? 0 : latest.ArmedState; } }
    internal ulong EngineTermReturnedValue { get { return latest == null ? 0 : latest.EngineTermReturnedValue; } }
    internal ulong CallbackManagerTermReturnedValue { get { return latest == null ? 0 : latest.CallbackManagerTermReturnedValue; } }
    internal NativeWwiseDiagSnapshot Latest { get { return latest; } }

    internal NativeWwiseDiagSnapshot ObserveSnapshot()
    {
        EnsureUsable();
        try { return ReadSnapshot(); }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    // Registration is the only pre-Init operation. Callback coverage is not
    // inferred from the raw monitor registration or from a generic callback.
    internal NativeWwiseDiagSnapshot ArmBeforeInit()
    {
        if (armAttempted || outcomeUnknown) throw new InvalidOperationException("Native monitor arm is single-shot.");
        armAttempted = true;
        try
        {
            RequireSuccess(api.Arm(), "native monitor arm");
            if (api.IsArmed() != 1) throw new InvalidOperationException("Native bridge did not report armed state.");
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.ArmedState != 1 || snapshot.MonitorInstallResult != AkSuccess || snapshot.EngineInitAttempted != 0)
                throw new InvalidOperationException("Native monitor registration snapshot is inconsistent.");
            return snapshot;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    // Call immediately before entering AkSoundEngine.Init. The native latch is
    // authoritative for refusing the special no-Init detach path.
    internal NativeWwiseDiagSnapshot MarkEngineInitAttempted()
    {
        EnsureUsable();
        if (!Armed || EngineInitAttempted || engineTermReturned || captureRegisterAttempted)
            throw new InvalidOperationException("Engine Init attempt marker is out of order.");
        try
        {
            RequireSuccess(api.MarkEngineInitAttempted(), "native engine Init-attempt marker");
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.EngineInitAttempted != 1 || snapshot.ArmedState != 1)
                throw new InvalidOperationException("Native engine Init-attempt marker was not recorded.");
            engineInitAttempted = true;
            return snapshot;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    // Post once after engine and callback-manager initialization. Poll this from
    // the Unity Update loop; only the dedicated exact-message counter can prove it.
    internal NativeWwiseDiagSnapshot BeginPostInitControlObservation()
    {
        EnsureUsable();
        if (!Armed || !EngineInitAttempted || engineTermReturned || postInitControlAttempted)
            throw new InvalidOperationException("Post-Init monitor control is outside its single allowed window.");
        postInitControlAttempted = true;
        try
        {
            NativeWwiseDiagSnapshot before = ReadSnapshot();
            if (before.EngineInitAttempted != 1 || before.ArmedState != 1)
                throw new InvalidOperationException("Post-Init control lacks an active native engine marker.");
            postInitControlBaseline = before.MonitorControlCallbacks;
            RequireSuccess(api.PostControl(), "post-Init monitor control");
            return ReadSnapshot();
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal NativeWwiseDiagSnapshot PollPostInitControl()
    {
        EnsureUsable();
        if (!postInitControlAttempted || engineTermReturned)
            throw new InvalidOperationException("Post-Init monitor poll is outside its live observation window.");
        try
        {
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.MonitorControlCallbacks > postInitControlBaseline)
                postInitControlObserved = true;
            return snapshot;
        }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal NativeWwiseDiagSnapshot RegisterCaptureCallback()
    {
        EnsureUsable();
        if (captureRegisterAttempted || engineTermReturned || !postInitControlObserved)
            throw new InvalidOperationException("Output capture callback registration requires post-Init exact-control coverage and is single-shot.");
        captureRegisterAttempted = true;
        try
        {
            int result = api.RegisterCapture();
            captureRegisterResultKnown = true;
            RequireSuccess(result, "native output callback registration");
            // Record native ownership before the following snapshot: a snapshot
            // failure must not erase proof that this exact callback registered.
            captureRegisterCallSucceeded = true;
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.CaptureRegistered != 1 || snapshot.CaptureRegisterResult != AkSuccess || snapshot.CaptureUsed != 1)
                throw new InvalidOperationException("Native output callback registration snapshot is inconsistent.");
            return snapshot;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal NativeWwiseDiagSnapshot UnregisterCaptureCallback()
    {
        EnsureUsable();
        if (!captureRegisterAttempted || captureUnregisterAttempted || engineTermReturned || !CaptureRegistered)
            throw new InvalidOperationException("Native output callback unregister lacks one live owned registration.");
        captureUnregisterAttempted = true;
        try
        {
            int result = api.UnregisterCapture();
            RequireSuccess(result, "native output callback unregister");
            // AK_Success is the bridge's authoritative removal result. Preserve
            // it even if the optional verification snapshot fails afterwards.
            captureUnregisterCallSucceeded = true;
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.CaptureRegistered != 0 || snapshot.CaptureUnregisterResult != AkSuccess)
                throw new InvalidOperationException("Native output callback unregister snapshot is inconsistent.");
            return snapshot;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    // Cleanup-only exception to the normal unknown-outcome guard. The bridge
    // contract sets capture_registered only on successful RegisterCapture and
    // clears it only on successful UnregisterCapture. This permits exactly one
    // reverse call for this lease, but never snapshots, retries, or other API
    // calls. A failed/throwing unregister leaves Term unsafe.
    internal bool CleanupOwnedCaptureBeforeEngineTerm()
    {
        if (!outcomeUnknown || !captureRegisterAttempted || !captureRegisterResultKnown || !captureRegisterCallSucceeded ||
            captureUnregisterAttempted || captureUnregisterCallSucceeded || engineTermReturned)
            throw new NativeWwiseDiagRefusalException("Cleanup-only unregister requires this lease's known successful, still-live capture registration.");
        captureUnregisterAttempted = true;
        try
        {
            RequireSuccess(api.UnregisterCapture(), "cleanup-only native output callback unregister");
            captureUnregisterCallSucceeded = true;
            return true;
        }
        catch (NativeWwiseDiagRefusalException) { outcomeUnknown = true; throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal void RecordEngineTermReturned()
    {
        EnsureUsable();
        if (!Armed || !EngineInitAttempted || engineTermReturned) throw new InvalidOperationException("Engine Term return marker is out of order or duplicated.");
        try { api.EngineTermReturned(); engineTermReturned = true; }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal void RecordCallbackManagerTermReturned()
    {
        EnsureUsable();
        if (!engineTermReturned || callbackManagerTermReturned || disarmAttempted)
            throw new InvalidOperationException("Callback-manager Term return marker requires one returned engine Term.");
        try
        {
            if (CaptureRegistered) throw new NativeWwiseDiagRefusalException("Capture callback still owns its registration.");
            api.CallbackManagerTermReturned();
            callbackManagerTermReturned = true;
            NativeWwiseDiagSnapshot snapshot = ReadSnapshot();
            if (snapshot.EngineTermReturnedValue != 1 || snapshot.CallbackManagerTermReturnedValue != 1 || snapshot.ArmedState != 1)
                throw new InvalidOperationException("Term-return markers or armed monitor state are inconsistent.");
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal NativeWwiseDiagSnapshot DisarmBeforeInit()
    {
        EnsureUsable();
        if (!Armed || EngineInitAttempted || captureRegisterAttempted || captureUnregisterAttempted ||
            engineTermReturned || callbackManagerTermReturned || disarmAttempted)
            throw new NativeWwiseDiagRefusalException("Pre-Init disarm requires an armed lease with authoritative no-Init and no-capture state.");
        try
        {
            NativeWwiseDiagSnapshot before = ReadSnapshot();
            if (before.ArmedState != 1 || before.EngineInitAttempted != 0 ||
                before.CaptureRegistered != 0 || before.CaptureUsed != 0)
                throw new NativeWwiseDiagRefusalException("Fresh native snapshot does not prove safe pre-Init disarm conditions.");
            disarmAttempted = true;
            RequireSuccess(api.DisarmBeforeInit(), "native monitor pre-Init disarm");
            NativeWwiseDiagSnapshot after = ReadSnapshot();
            if (after.ArmedState != 3 || after.DisarmResult != AkSuccess || after.EngineInitAttempted != 0 ||
                after.CaptureRegistered != 0 || after.CaptureUsed != 0)
                throw new InvalidOperationException("Native pre-Init disarm snapshot is inconsistent.");
            return after;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    internal NativeWwiseDiagSnapshot DisarmAfterReturnedTerms()
    {
        EnsureUsable();
        if (!engineTermReturned || !callbackManagerTermReturned || disarmAttempted)
            throw new InvalidOperationException("Native monitor disarm requires returned engine and callback-manager Terms.");
        try
        {
            NativeWwiseDiagSnapshot before = ReadSnapshot();
            if (before.EngineTermReturnedValue != 1 || before.CallbackManagerTermReturnedValue != 1 || before.ArmedState != 1)
                throw new InvalidOperationException("Term-return markers or armed monitor state are inconsistent before disarm.");
            disarmAttempted = true;
            RequireSuccess(api.DisarmAfterTerm(), "native monitor post-Term disarm");
            NativeWwiseDiagSnapshot afterDisarm = ReadSnapshot();
            if (afterDisarm.ArmedState != 3 || afterDisarm.DisarmResult != AkSuccess ||
                afterDisarm.EngineTermReturnedValue != 1 || afterDisarm.CallbackManagerTermReturnedValue != 1)
                throw new InvalidOperationException("Native monitor disarm snapshot is inconsistent.");
            return afterDisarm;
        }
        catch (NativeWwiseDiagRefusalException) { throw; }
        catch (Exception) { outcomeUnknown = true; throw; }
    }

    private NativeWwiseDiagSnapshot ReadSnapshot()
    {
        NativeWwiseDiagSnapshot snapshot = NativeWwiseDiagSnapshot.Parse(api.Snapshot(), latest);
        latest = snapshot;
        return snapshot;
    }

    private void EnsureUsable()
    {
        if (outcomeUnknown) throw new InvalidOperationException("Native diagnostic bridge outcome is unknown; retain owner and stop native calls.");
    }

    private static void RequireSuccess(int result, string operation)
    {
        if (result != AkSuccess) throw new NativeWwiseDiagRefusalException(operation + " returned " + result + ".");
    }
}

// The production adapter imports only extension exports from the already-owned
// AkSoundEngine library; it never loads another engine or initializes Wwise.
internal sealed class NativeWwiseDiagPInvokeApi : INativeWwiseDiagApi
{
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_MonitorArm")]
    private static extern int NativeArm();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_MonitorIsArmed")]
    private static extern int NativeIsArmed();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_PostMonitorControl")]
    private static extern int NativePostControl();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_MarkEngineInitAttempted")]
    private static extern int NativeMarkEngineInitAttempted();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_MonitorDisarmBeforeInit")]
    private static extern int NativeDisarmBeforeInit();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_EngineTermReturned")]
    private static extern void NativeEngineTermReturned();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_CallbackManagerTermReturned")]
    private static extern void NativeCallbackManagerTermReturned();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_MonitorDisarmAfterTerm")]
    private static extern int NativeDisarmAfterTerm();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_CaptureRegister")]
    private static extern int NativeCaptureRegister();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_CaptureUnregister")]
    private static extern int NativeCaptureUnregister();
    [DllImport("AkSoundEngine", EntryPoint = "WwiseDiag_Snapshot")]
    private static extern void NativeSnapshot(IntPtr output, uint capacity);

    public int Arm() { return NativeArm(); }
    public int IsArmed() { return NativeIsArmed(); }
    public int PostControl() { return NativePostControl(); }
    public int MarkEngineInitAttempted() { return NativeMarkEngineInitAttempted(); }
    public int DisarmBeforeInit() { return NativeDisarmBeforeInit(); }
    public void EngineTermReturned() { NativeEngineTermReturned(); }
    public void CallbackManagerTermReturned() { NativeCallbackManagerTermReturned(); }
    public int DisarmAfterTerm() { return NativeDisarmAfterTerm(); }
    public int RegisterCapture() { return NativeCaptureRegister(); }
    public int UnregisterCapture() { return NativeCaptureUnregister(); }

    public long[] Snapshot()
    {
        IntPtr memory = Marshal.AllocHGlobal(NativeWwiseDiagSnapshot.SlotCount * sizeof(long));
        if (memory == IntPtr.Zero) throw new OutOfMemoryException("Native diagnostic snapshot buffer allocation failed.");
        try
        {
            for (int i = 0; i < NativeWwiseDiagSnapshot.SlotCount; i++)
                Marshal.WriteInt64(memory, i * sizeof(long), 0);
            NativeSnapshot(memory, NativeWwiseDiagSnapshot.SlotCount);
            var values = new long[NativeWwiseDiagSnapshot.SlotCount];
            for (int i = 0; i < values.Length; i++)
                values[i] = Marshal.ReadInt64(memory, i * sizeof(long));
            return values;
        }
        finally { Marshal.FreeHGlobal(memory); }
    }
}
