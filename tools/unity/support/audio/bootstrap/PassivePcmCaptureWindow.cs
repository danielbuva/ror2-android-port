using System;

// Draft helper for the existing original-audio bootstrap assembly. It observes
// the existing engine's main output; it owns only this temporary callback lease.
// It never posts events, changes Wwise state, or initializes/terminates Wwise.
internal sealed class PassivePcmCaptureWindow
{
    internal const float MaxDurationSeconds = 10.0f;
    internal const float SnapshotIntervalSeconds = 1.0f;
    internal const ulong MaxSuccessfulRenderFrames = 600;
    internal const int MaxPeriodicSnapshots = 9;
    internal const ulong MaxAnalyzedSamples = 1_048_576;

    private readonly NativeWwiseMonitorLease lease;
    private readonly bool requested;
    private readonly bool beforeTermGuardInstalled;
    private readonly Action<Exception> onTermRefusal;
    private NativeWwiseDiagSnapshot baseline;
    private NativeWwiseDiagSnapshot latest;
    private float startedAt;
    private float lastSnapshotAt;
    private ulong startServiceFrames;
    private int periodicSnapshots;
    private bool gameplayArmRequested;
    private bool registrationAttempted;
    private bool registrationMayHaveReachedNative;
    private bool registrationOwned;
    private bool closed;
    private string state;
    private string stopReason;
    private string failure;

    internal PassivePcmCaptureWindow(NativeWwiseMonitorLease lease, bool requested,
        Action<Action> installBeforeEngineTermHandler, Func<Action> readBeforeEngineTermHandler,
        Action<Exception> onTermRefusal)
    {
        this.lease = lease ?? throw new ArgumentNullException(nameof(lease));
        this.requested = requested;
        this.onTermRefusal = onTermRefusal;
        state = requested ? "selected_waiting_for_gameplay_arm" : "disabled";
        if (!requested) return;
        if (installBeforeEngineTermHandler == null || readBeforeEngineTermHandler == null)
        {
            failure = "pre_term_guard_install_or_readback_unavailable";
            state = "term_guard_unavailable";
            closed = true;
            return;
        }
        try
        {
            if (readBeforeEngineTermHandler() != null)
                throw new InvalidOperationException("A pre-Term observer is already owned; refusing to replace it.");
            Action ownedGuard = BeforeOriginalEngineTerm;
            installBeforeEngineTermHandler(ownedGuard);
            if (!Object.ReferenceEquals(readBeforeEngineTermHandler(), ownedGuard))
                throw new InvalidOperationException("The pre-Term observer did not retain the exact owned guard delegate.");
            beforeTermGuardInstalled = true;
        }
        catch (Exception error)
        {
            failure = "pre_term_guard_install_failed:" + error.GetType().Name;
            state = "term_guard_unavailable";
            closed = true;
        }
    }

    internal string State { get { return state; } }
    internal string StopReason { get { return stopReason; } }
    internal string Failure { get { return failure; } }
    internal bool GameplayArmRequested { get { return gameplayArmRequested; } }
    internal float WindowStartRealtimeSinceStartup { get { return startedAt; } }
    internal ulong WindowStartServiceFrames { get { return startServiceFrames; } }
    internal bool RegistrationOwned { get { return registrationOwned; } }

    internal bool RequestGameplayArm()
    {
        if (!requested || closed || !beforeTermGuardInstalled) return false;
        gameplayArmRequested = true;
        if (!registrationAttempted) state = "gameplay_armed_waiting_for_ready_render";
        return true;
    }

    // Called from the persistent PortSession owner's Update, never from an AK
    // callback or the injected RenderAudio return site.
    internal void Tick(float realtimeSinceStartup, bool ownerReady, bool exactControlObserved,
        ulong successfulOriginalRenderFrames)
    {
        if (!requested || !gameplayArmRequested || closed || !String.Equals(state, "capturing", StringComparison.Ordinal)) return;
        try
        {
            float elapsed = realtimeSinceStartup - startedAt;
            ulong rendered = successfulOriginalRenderFrames >= startServiceFrames
                ? successfulOriginalRenderFrames - startServiceFrames : 0;
            if (elapsed >= MaxDurationSeconds)
            {
                Stop("duration_limit", false);
                return;
            }
            if (rendered >= MaxSuccessfulRenderFrames)
            {
                Stop("render_frame_limit", false);
                return;
            }
            if (!ownerReady || !exactControlObserved)
            {
                Stop("owner_or_exact_control_lost", false);
                return;
            }
            if (realtimeSinceStartup - lastSnapshotAt >= SnapshotIntervalSeconds &&
                periodicSnapshots < MaxPeriodicSnapshots)
            {
                latest = lease.ObserveSnapshot();
                periodicSnapshots++;
                lastSnapshotAt = realtimeSinceStartup;
                if (latest.SampleCount >= MaxAnalyzedSamples)
                {
                    Stop("sample_limit", false);
                    return;
                }
            }
        }
        catch (Exception error)
        {
            failure = "capture_tick_unknown:" + error.GetType().Name;
            state = "outcome_unknown";
            closed = true;
        }
    }

    // Close the passive observation when the actual playable session ends.
    // This keeps the capture bounded by gameplay and never delays original Term
    // or session cleanup merely to fill the requested window.
    internal void FinishGameplayWindow()
    {
        if (!requested || closed) return;
        if (registrationMayHaveReachedNative && !lease.CaptureSafeBeforeEngineTerm)
        {
            failure = failure ?? "capture_registration_outcome_unknown_at_session_end";
            state = "outcome_unknown";
            closed = true;
            var refusal = new InvalidOperationException("Passive capture registration remains unresolved at the end of the gameplay window.");
            try { onTermRefusal?.Invoke(refusal); } catch { }
            return;
        }
        if (registrationOwned)
        {
            Stop("playable_session_completed", false);
            return;
        }
        stopReason = "playable_session_completed_before_capture_start";
        state = "not_started_session_completed";
        closed = true;
    }

    // Start only after the unchanged original engine is ready, the exact
    // post-Init control has been observed, and a successful original service
    // frame has already returned. Registration is single-shot per process.
    internal bool Start(float realtimeSinceStartup, bool ownerReady, bool exactControlObserved,
        bool successfulOriginalRenderAlreadyObserved, ulong successfulOriginalRenderFrames)
    {
        if (!requested || !gameplayArmRequested || closed || registrationAttempted) return false;
        if (!beforeTermGuardInstalled)
        {
            failure = "pre_term_guard_not_installed";
            state = "term_guard_unavailable";
            closed = true;
            return false;
        }
        if (!ownerReady || !exactControlObserved || !successfulOriginalRenderAlreadyObserved)
        {
            state = "gameplay_armed_waiting_for_ready_render";
            return false;
        }
        registrationAttempted = true;
        try
        {
            baseline = lease.ObserveSnapshot();
            if (baseline.ArmedState != 1 || baseline.EngineInitAttempted != 1 ||
                baseline.CaptureRegistered != 0 || baseline.CaptureUsed != 0)
                throw new InvalidOperationException("Native bridge state is not ready for one passive capture lease.");
            registrationMayHaveReachedNative = true;
            latest = lease.RegisterCaptureCallback();
            registrationOwned = true;
            registrationMayHaveReachedNative = false;
            startedAt = lastSnapshotAt = realtimeSinceStartup;
            startServiceFrames = successfulOriginalRenderFrames;
            state = "capturing";
            return true;
        }
        catch (Exception error)
        {
            failure = "capture_start_refused_or_unknown:" + error.GetType().Name;
            state = registrationMayHaveReachedNative ? "registration_cleanup_pending" : "start_refused";
            closed = !registrationMayHaveReachedNative;
            return false;
        }
    }

    // Must run at the verified pre-teardown point in the original Term method,
    // before it changes offline rendering or stops/unregisters/clears game state.
    // Native Term is permitted only after the exact callback is proven absent.
    // If native registration returned success but a later snapshot poisoned the
    // lease, make one cleanup-only unregister call and do not snapshot again.
    // If registration or removal is genuinely unresolved, throw before original
    // Term so the callback cannot outlive its engine.
    internal void BeforeOriginalEngineTerm()
    {
        if (!requested) return;
        if (!lease.CaptureRegisterAttempted)
        {
            closed = true;
            return;
        }
        if (lease.CaptureRegisterResultKnown && !lease.CaptureRegisterCallSucceeded)
        {
            // The bridge returned a non-success AKRESULT; its contract does not
            // own a callback on this path.
            closed = true;
            state = "start_refused";
            return;
        }
        if (!lease.CaptureUnregisterCallSucceeded)
        {
            if (lease.OutcomeUnknown)
            {
                try
                {
                    lease.CleanupOwnedCaptureBeforeEngineTerm();
                    registrationOwned = false;
                    registrationMayHaveReachedNative = false;
                    stopReason = "original_engine_term_cleanup_only";
                    state = "capture_removed_snapshot_unknown";
                    closed = true;
                }
                catch (Exception error)
                {
                    failure = "capture_cleanup_unknown:" + error.GetType().Name;
                }
            }
            else if (registrationOwned || lease.CaptureRegistered)
            {
                Stop("original_engine_term", true);
            }
        }
        if (!lease.CaptureSafeBeforeEngineTerm)
        {
            failure = failure ?? "capture_registration_or_removal_unresolved";
            state = "outcome_unknown";
            closed = true;
            var refusal = new InvalidOperationException("Refusing original engine Term while this diagnostic capture callback may still be registered.");
            try { onTermRefusal?.Invoke(refusal); }
            catch { /* preserve the original fail-closed Term refusal */ }
            throw refusal;
        }
        closed = true;
    }

    private void Stop(string reason, bool beforeTerm)
    {
        if (closed) return;
        stopReason = reason;
        try
        {
            if (registrationOwned)
            {
                latest = lease.UnregisterCaptureCallback();
                registrationOwned = false;
            }
            if (baseline == null || latest == null || latest.CaptureRegistered != 0 ||
                !latest.PcmCountersCoherentAfterQuiescence)
                throw new InvalidOperationException("Final post-unregister PCM snapshot is incomplete or incoherent.");
            state = beforeTerm ? "captured_before_term" : "captured";
            closed = true;
        }
        catch (Exception error)
        {
            failure = "capture_stop_unknown:" + error.GetType().Name;
            state = "outcome_unknown";
            if (lease.CaptureUnregisterCallSucceeded) registrationOwned = false;
            // Otherwise retain ownership and let the pre-Term gate refuse Term.
            closed = true;
        }
    }

    internal PassivePcmCaptureReport Report { get { return CreateReport(); } }

    private PassivePcmCaptureReport CreateReport()
    {
        if (baseline == null || latest == null || (state != "captured" && state != "captured_before_term"))
            return new PassivePcmCaptureReport(state, stopReason, failure, 0, 0, 0, 0, 0, 0, 0, 0, false);
        return new PassivePcmCaptureReport(state, stopReason, failure,
            latest.CaptureCallbacks - baseline.CaptureCallbacks,
            latest.CaptureFrames - baseline.CaptureFrames,
            latest.SampleCount - baseline.SampleCount,
            latest.FiniteSamples - baseline.FiniteSamples,
            latest.NonzeroFiniteSamples - baseline.NonzeroFiniteSamples,
            latest.NonfiniteSamples - baseline.NonfiniteSamples,
            latest.RejectedBuffers - baseline.RejectedBuffers,
            latest.CappedBuffers - baseline.CappedBuffers,
            latest.CaptureOutputId != 0);
    }
}

// Bounded counters only. No sample bytes, filenames, event IDs, or device ID.
internal sealed class PassivePcmCaptureReport
{
    internal readonly string State;
    internal readonly string StopReason;
    internal readonly string Failure;
    internal readonly ulong CallbackCount, FrameCount, SampleCount, FiniteSamples;
    internal readonly ulong NonzeroFiniteSamples, NonfiniteSamples, RejectedBuffers, CappedBuffers;
    internal readonly bool OutputIdentityObserved;

    internal PassivePcmCaptureReport(string state, string stopReason, string failure,
        ulong callbacks, ulong frames, ulong samples, ulong finite, ulong nonzero,
        ulong nonfinite, ulong rejected, ulong capped, bool outputIdentityObserved)
    {
        State = state; StopReason = stopReason; Failure = failure;
        CallbackCount = callbacks; FrameCount = frames; SampleCount = samples;
        FiniteSamples = finite; NonzeroFiniteSamples = nonzero; NonfiniteSamples = nonfinite;
        RejectedBuffers = rejected; CappedBuffers = capped;
        OutputIdentityObserved = outputIdentityObserved;
    }
}
