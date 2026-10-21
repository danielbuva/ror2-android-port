using System;
using System.Collections;
using System.Collections.Generic;

// Application startup admission + readiness gate for the original Wwise owner.
// This type never calls Wwise Init/Term/LoadBank/PostCallbacks/RenderAudio and
// never creates another AkInitializer, AudioManager, listener, or process host.
public interface IGameAudioOriginalStartupPreparation
{
    // Must return true only after validating the request-bound payload receipt,
    // copying/validating the full bank cohort at the path used by the original
    // Android AkBasePathGetter, loading the pinned native library, installing the
    // Android resolver, and arming the accepted monitor before original Init.
    // It must not call engine Init or instantiate Wwise components.
    IEnumerator PrepareBeforeExistingManagerInit();
    // Called synchronously at the injected instruction immediately before the
    // original AkSoundEngine.Init call. It must throw on monitor-arm refusal.
    void ArmNativeMonitorBeforeInit();
    // Called only after the original InitializeSoundEngine returns true. The
    // accepted method may or may not have its optional delegate assigned; this
    // observer makes no claim about that optional call's existence.
    void PostExactControlMarker();
    // Queried only after the original RenderAudio return witness for a frame.
    bool NativeExactControlObserved();
    // True only for a terminal lease error; a false marker poll is pending.
    bool NativeControlObservationFailed { get; }
    // Forwarded only after the corresponding original owner's Term returns.
    void ObserveEngineTermReturned();
    void ObserveCallbackManagerTermReturned();
    // Must undo only pre-Init preparation (for example the temporary platform
    // resolver) and be a no-op after the exact native Init-attempt marker.
    void AbandonBeforeOriginalInit();
    bool Prepared { get; }
    string Refusal { get; }
}

public static class GameAudioOriginalOwner
{
    private static readonly object Sync = new object();
    private static GameAudioOriginalReadiness readiness;
    private static IGameAudioOriginalStartupPreparation preparation;
    private static IGameAudioOriginalPassivePcmCapture passiveCapture;
    private static ulong successfulOriginalRenderFrames;
    private static bool passiveCaptureStopRequested;
    private static bool optInRequested;
    private static bool configured;
    private static bool prepareAttempted;
    private static bool originalManagerInitClaimed;
    private static bool originalManagerInitReturned;
    // Independent of readiness: once the Java loader returned successfully the
    // exact native IsInitialized query is safe and truthful even if later bank
    // or monitor readiness fails. Keep it available until process exit so the
    // original AkInitializer can run its own failure/Term path.
    private static bool nativeLibraryLoaded;
    private static bool nativeInitAttemptObserved;
    private static string failure;
    private static int postCallbacksResult;
    private static bool postCallbacksSeen;
    private static int engineTermReturns;
    private static int callbackManagerTermReturns;
    private static bool pointSoundDiagnosticConfigured;

    // Called once from generated, request-bound composition configuration. No
    // generated acceptance record means no provider and therefore no startup.
    public static void Configure(bool requested, IEnumerable<string> sourceBankNames,
        IGameAudioOriginalStartupPreparation acceptedPreparation, IGameAudioOriginalPassivePcmCapture acceptedPassiveCapture = null,
        bool passivePcmCaptureRequested = false)
    {
        lock (Sync)
        {
            if (configured || prepareAttempted || readiness != null)
                throw new InvalidOperationException("Original audio selection is immutable after startup preparation.");
            configured = true;
            optInRequested = requested;
            if (!requested)
            {
                if (passivePcmCaptureRequested || acceptedPassiveCapture != null)
                    throw new InvalidOperationException("Passive PCM capture cannot be selected without original audio.");
                return;
            }
            if (passivePcmCaptureRequested != (acceptedPassiveCapture != null))
                throw new InvalidOperationException("Passive PCM selection and bootstrap-owned capture instance disagree.");
            if (sourceBankNames == null || acceptedPreparation == null)
            {
                failure = "selected_original_audio_missing_manifest_or_preparation";
                return;
            }
            readiness = new GameAudioOriginalReadiness(sourceBankNames);
            preparation = acceptedPreparation;
            passiveCapture = acceptedPassiveCapture;
            WireOriginalObserver();
        }
    }

    // Called by PortSession after the offline menu and before player creation.
    // It does not advance RoR2Application.InitializeGameRoutine or its unrelated
    // platform, profile, and network startup path.
    public static IEnumerator PrepareBeforeOriginalManagerInit()
    {
        IGameAudioOriginalStartupPreparation selectedPreparation;
        lock (Sync)
        {
            if (!optInRequested || prepareAttempted) return EmptyRoutine();
            prepareAttempted = true;
            selectedPreparation = preparation;
        }
        if (readiness == null || selectedPreparation == null)
        {
            lock (Sync) failure = failure ?? "accepted_original_audio_configuration_missing";
            return EmptyRoutine();
        }
        return PrepareConfiguredStartup(selectedPreparation);
    }

    private static IEnumerator EmptyRoutine() { yield break; }

    private static IEnumerator PrepareConfiguredStartup(
        IGameAudioOriginalStartupPreparation selectedPreparation)
    {
        IEnumerator preparationRoutine = null;
        bool preparationReturned = false;
        try
        {
            try { preparationRoutine = selectedPreparation.PrepareBeforeExistingManagerInit(); }
            catch (Exception e)
            {
                lock (Sync) failure = "preparation_threw:" + e.GetType().Name;
            }
            if (preparationRoutine != null)
                while (true)
                {
                    bool moved;
                    object current;
                    try { moved = preparationRoutine.MoveNext(); current = moved ? preparationRoutine.Current : null; }
                    catch (Exception e)
                    {
                        lock (Sync) failure = "preparation_coroutine_threw:" + e.GetType().Name;
                        break;
                    }
                    if (!moved) break;
                    yield return current;
                }

            lock (Sync)
            {
                bool prepared = selectedPreparation.Prepared;
                if (!prepared)
                {
                    failure = failure ?? (String.IsNullOrEmpty(selectedPreparation.Refusal)
                        ? "original_audio_preparation_refused" : selectedPreparation.Refusal);
                    readiness.SelectAndPrepare(true, false, false, false);
                }
                else
                {
                    // Prepared means the bootstrap verified all staged bytes, native
                    // library, resolver and pre-Init monitor arm. Engine/bank/control
                    // success remains observed through the original Wwise lifecycle.
                    readiness.SelectAndPrepare(true, true, true, true);
                }
                preparationReturned = prepared;
            }
        }
        finally
        {
            if (!preparationReturned)
            {
                try { (preparationRoutine as IDisposable)?.Dispose(); }
                catch (Exception error) { lock (Sync) failure = failure ?? "preparation_dispose_threw:" + error.GetType().Name; }
                AbandonBeforeOriginalInit(selectedPreparation);
            }
        }
    }

    // PortSession invokes the existing static WwiseIntegrationManager.Init only
    // after this one-shot claim. Its two original async prefab loads and all
    // original AkInitializer/AudioManager lifecycles remain unchanged.
    public static bool TryBeginOriginalManagerInit()
    {
        lock (Sync)
        {
            if (!optInRequested || originalManagerInitClaimed || readiness == null || !readiness.StartupSelected)
                return false;
            originalManagerInitClaimed = true;
            return true;
        }
    }

    // One process-lifetime owner spans scene/run PortSession replacement. A later
    // session observes this claim and waits on the same readiness state; it must
    // never configure a second monitor or issue a second pair of prefab loads.
    public static bool OriginalManagerInitClaimed
    { get { lock (Sync) return originalManagerInitClaimed; } }
    public static bool OriginalManagerInitReturned
    { get { lock (Sync) return originalManagerInitReturned; } }
    public static bool NativeApiCallsAvailable
    { get { lock (Sync) return nativeLibraryLoaded; } }
    public static bool OptInRequested
    { get { lock (Sync) return optInRequested; } }
    public static bool NativeInitAttemptObserved
    { get { lock (Sync) return nativeInitAttemptObserved; } }
    public static bool OriginalTermsReturned
    { get { lock (Sync) return engineTermReturns > 0 && callbackManagerTermReturns > 0; } }
    public static bool PassiveCaptureStopRequested
    { get { lock (Sync) return passiveCaptureStopRequested || (passiveCapture != null && passiveCapture.TerminalStopRequested); } }
    public static ulong SuccessfulOriginalRenderFrames
    { get { lock (Sync) return successfulOriginalRenderFrames; } }
    public static bool PassiveCaptureArmRequested
    { get { lock (Sync) return passiveCapture != null && passiveCapture.ArmRequested; } }

    // A capture request is armed only by the verified playable-world boundary,
    // never by process startup or Wwise readiness alone.
    public static bool ArmPassiveCaptureAtGameplayBoundary(bool explicitlyRequested, bool playableWorldStarted)
    {
        IGameAudioOriginalPassivePcmCapture selected;
        lock (Sync)
        {
            if (!explicitlyRequested || !playableWorldStarted || !optInRequested || passiveCapture == null) return false;
            selected = passiveCapture;
        }
        return selected.RequestGameplayArm();
    }
    public static void FinishPassiveCaptureGameplayWindow()
    {
        IGameAudioOriginalPassivePcmCapture selected;
        lock (Sync) selected = passiveCapture;
        selected?.FinishGameplayWindow();
    }

    public static IGameAudioOriginalPassivePcmCapture PassiveCapture
    { get { lock (Sync) return passiveCapture; } }

    // Called only by the existing PortSessionOriginalAudioOwner.Update. This is
    // an observer tick; it never invokes Wwise service or changes engine state.
    public static void TickPassiveCapture(float realtimeSinceStartup)
    {
        IGameAudioOriginalPassivePcmCapture selected;
        bool ready, exactControl;
        ulong frames;
        lock (Sync)
        {
            selected = passiveCapture;
            ready = readiness != null && readiness.IsReady;
            exactControl = readiness != null && readiness.ControlObserved;
            frames = successfulOriginalRenderFrames;
        }
        selected?.Tick(realtimeSinceStartup, ready, exactControl, frames);
    }

    public static void RequestPassivePcmTerminalStop(string reason)
    {
        lock (Sync)
        {
            passiveCaptureStopRequested = true;
            failure = failure ?? ("passive_pcm_terminal_stop:" + (reason ?? "unknown"));
            readiness?.RecordTerminalFailure();
        }
    }

    private static void RecordBeforeOriginalEngineTerm()
    {
        IGameAudioOriginalPassivePcmCapture selected;
        lock (Sync) selected = passiveCapture;
        selected?.BeforeOriginalEngineTerm();
    }
    public static bool CanReleaseCatalogLease(bool managerInitClaimed, bool nativeInitAttemptObserved, bool termsReturned)
    {
        return (!managerInitClaimed && !nativeInitAttemptObserved) || termsReturned;
    }
    public static void RecordNativeLibraryLoaded()
    {
        lock (Sync)
        {
            if (!optInRequested) throw new InvalidOperationException("Native Wwise library loaded without an accepted original-audio request.");
            nativeLibraryLoaded = true;
        }
    }
    public static bool HasTerminalFailure
    { get { lock (Sync) return failure != null || (readiness != null && readiness.Failed); } }

    // The PortSession selector may arm only a diagnostic build after the
    // original owner is ready. This observer lives with this process-lifetime
    // owner; it never creates or owns Wwise objects and stores no Unity objects.
    public static void ConfigurePointSoundDiagnostic(bool requested)
    {
        lock (Sync)
        {
            if (pointSoundDiagnosticConfigured)
                throw new InvalidOperationException("Point-sound diagnostic selection is immutable for this process.");
            pointSoundDiagnosticConfigured = true;
            if (!requested) return;
            if (!GameAudioOriginalPointSoundBuildPin.DiagnosticCallsitesPresent)
                throw new InvalidOperationException("Point-sound diagnostic selector requires the instrumented diagnostic game assembly.");
            PointSoundDiagnosticObserver.Configure(true);
        }
    }

    public static string PointSoundDiagnosticBuildRefusal(bool requested) =>
        requested && !GameAudioOriginalPointSoundBuildPin.DiagnosticCallsitesPresent
            ? "Point-sound diagnostic selector requires the instrumented diagnostic game assembly"
            : null;

    public static PointSoundDiagnosticObserver.Snapshot CapturePointSoundDiagnosticSnapshot()
    {
        lock (Sync) return PointSoundDiagnosticObserver.CaptureSnapshot();
    }

    // The diagnostic is scoped to one PortSession run. Capture its last scalar
    // snapshot first, then detach the Unity log observer at terminal report save.
    public static void DisablePointSoundDiagnostic()
    {
        lock (Sync)
        {
            PointSoundDiagnosticObserver.Disable();
        }
    }

    public static void RecordOriginalManagerInitReturned()
    { lock (Sync) originalManagerInitReturned = true; }

    public static void RecordExistingInitializerConflict()
    {
        lock (Sync)
        {
            failure = "original_initializer_already_exists_before_manager_init";
            readiness?.RecordTerminalFailure();
        }
    }

    // WwiseIntegrationManager.Init branches on `if (noAudio) return`; this gate
    // intentionally differs from the public readiness-backed noAudio property.
    public static bool ShouldSkipOriginalManagerInit()
    {
        lock (Sync) return readiness == null || !readiness.StartupSelected;
    }

    public static void RecordOriginalManagerInitException(string exceptionType)
    {
        lock (Sync)
        {
            failure = "original_manager_init_threw:" + (exceptionType ?? "unknown");
            readiness?.RecordTerminalFailure();
        }
    }

    // Preparation rollback is safe before the native Init marker; the concrete
    // bootstrap becomes a no-op after that marker and therefore never tears down
    // or Term's a native owner it does not own.
    public static void AbandonPreparationBeforeOriginalInit()
    {
        IGameAudioOriginalStartupPreparation selected;
        lock (Sync) selected = preparation;
        if (selected != null) AbandonBeforeOriginalInit(selected);
    }

    public static void RecordStartupTimeout()
    {
        lock (Sync)
        {
            failure = "original_audio_readiness_timeout";
            readiness?.RecordTerminalFailure();
        }
    }

    private static void AbandonBeforeOriginalInit(IGameAudioOriginalStartupPreparation selectedPreparation)
    {
        try { selectedPreparation.AbandonBeforeOriginalInit(); }
        catch (Exception error) { lock (Sync) failure = failure ?? "preparation_abandon_threw:" + error.GetType().Name; }
    }

    // Replaces the accepted Android candidate's noAudio getter only after the
    // original no-audio guard transform. The startup exception is intentionally
    // separate: selected startup may instantiate the original prefabs while this
    // remains true, keeping all measured audio consumers closed until ready.
    public static bool NoAudio
    {
        get { lock (Sync) return readiness == null || readiness.NoAudio; }
    }

    public static bool StartupSelected
    {
        get { lock (Sync) return readiness != null && readiness.StartupSelected; }
    }

    public static bool Ready
    {
        get { lock (Sync) return readiness != null && readiness.IsReady; }
    }
    public static int RequestedBankCount
    { get { lock (Sync) return readiness == null ? 0 : readiness.RequestedBankCount; } }
    public static int CompletedBankCount
    { get { lock (Sync) return readiness == null ? 0 : readiness.CompletedBankCount; } }

    public static string Failure
    {
        get { lock (Sync) return failure ?? (readiness == null ? null : readiness.Failed ? "original_audio_readiness_failed" : null); }
    }

    // These are observer-only callbacks inserted around exact original API sites.
    // They preserve result values and never call into the Wwise lifecycle.
    public static void ObserveEngineInit(int result, int successValue) { lock (Sync) readiness?.RecordEngineInit(result, successValue); }
    public static void ObserveInitBank(int result, int successValue, uint bankId) { lock (Sync) readiness?.RecordInitBank(result, successValue, bankId); }
    public static void ObserveInitializeReturn(bool success)
    {
        IGameAudioOriginalStartupPreparation selected;
        lock (Sync)
        {
            readiness?.RecordInitializeReturn(success);
            selected = preparation;
        }
        if (success && selected != null)
        {
            try { selected.PostExactControlMarker(); }
            catch (Exception error) { lock (Sync) failure = "post_exact_control_marker_threw:" + error.GetType().Name; }
        }
    }
    public static void ObserveBankRequest(string name) { lock (Sync) readiness?.RecordBankRequest(name); }
    public static void ObserveBankResult(string name, int result, int successValue, int alreadyLoadedValue,
        uint bankId, bool existingManagedHandleBranch)
    { lock (Sync) readiness?.RecordBankResult(name, result, successValue, alreadyLoadedValue, bankId, existingManagedHandleBranch); }
    public static void ObserveExactPostInitControl(bool nativeCounterAdvanced, bool afterOriginalServiceFrame,
        bool nativeObservationFailed)
    { lock (Sync) readiness?.RecordExactPostInitControl(nativeCounterAdvanced, afterOriginalServiceFrame, nativeObservationFailed); }
    public static void ObserveOriginalServiceFrame(bool postCallbacksReturned, bool renderAudioSucceeded)
    {
        IGameAudioOriginalStartupPreparation selected;
        bool pollControl;
        lock (Sync)
        {
            readiness?.RecordOriginalServiceFrame(postCallbacksReturned, renderAudioSucceeded);
            selected = preparation;
            pollControl = readiness != null && !readiness.ControlObserved;
        }
        if (pollControl && postCallbacksReturned && renderAudioSucceeded && selected != null)
        {
            try { ObserveExactPostInitControl(selected.NativeExactControlObserved(), true, selected.NativeControlObservationFailed); }
            catch (Exception error) { lock (Sync) failure = "observe_exact_control_marker_threw:" + error.GetType().Name; }
        }
    }
    public static void RecordPostCallbacksReturned(int callbackCount)
    { lock (Sync) { postCallbacksResult = callbackCount; postCallbacksSeen = true; } }

    public static void RecordRenderAudioReturned(int result, int successValue)
    {
        int callbacks;
        bool postSeen;
        bool callbacksSucceeded;
        bool renderSucceeded = result == successValue;
        lock (Sync)
        {
            callbacks = postCallbacksResult; postSeen = postCallbacksSeen; postCallbacksSeen = false;
            callbacksSucceeded = postSeen && callbacks >= 0;
            if (callbacksSucceeded && renderSucceeded && successfulOriginalRenderFrames < UInt64.MaxValue)
                successfulOriginalRenderFrames++;
        }
        ObserveOriginalServiceFrame(callbacksSucceeded, renderSucceeded);
    }

    public static void RecordEngineTermReturned()
    {
        IGameAudioOriginalStartupPreparation selected;
        lock (Sync) { engineTermReturns++; selected = preparation; }
        if (selected != null)
        {
            try { selected.ObserveEngineTermReturned(); }
            catch (Exception error) { lock (Sync) failure = "observe_engine_term_threw:" + error.GetType().Name; }
        }
    }

    public static void RecordCallbackManagerTermReturned()
    {
        IGameAudioOriginalStartupPreparation selected;
        lock (Sync)
        {
            if (engineTermReturns <= 0 || callbackManagerTermReturns > 0) return;
            callbackManagerTermReturns++;
            readiness?.RecordOriginalTermsReturned(true, true);
            selected = preparation;
        }
        if (selected != null)
        {
            try { selected.ObserveCallbackManagerTermReturned(); }
            catch (Exception error) { lock (Sync) failure = "observe_callback_manager_term_threw:" + error.GetType().Name; }
        }
    }

    private static void WireOriginalObserver()
    {
        OriginalOwnerProbeObserver.Observer.BeforeEngineInit = () =>
        {
            IGameAudioOriginalStartupPreparation selected;
            lock (Sync) selected = preparation;
            if (selected == null) throw new InvalidOperationException("No selected native monitor preparation.");
            selected.ArmNativeMonitorBeforeInit();
            lock (Sync) nativeInitAttemptObserved = true;
        };
        OriginalOwnerProbeObserver.Observer.InitReturned = result => ObserveEngineInit(result, 1);
        OriginalOwnerProbeObserver.Observer.InitBankReturned = (result, bankId) => ObserveInitBank(result, 1, bankId);
        OriginalOwnerProbeObserver.Observer.InitializeMethodReturned = result => ObserveInitializeReturn(result != 0);
        OriginalOwnerProbeObserver.Observer.EngineTermReturned = RecordEngineTermReturned;
        OriginalOwnerProbeObserver.Observer.CallbackManagerTermReturned = RecordCallbackManagerTermReturned;
        OriginalOwnerProbeObserver.Observer.PostCallbacksReturned = RecordPostCallbacksReturned;
        OriginalOwnerProbeObserver.Observer.RenderAudioReturned = result => RecordRenderAudioReturned(result, 1);
    }

#if GAME_AUDIO_HOST_TEST
    internal static void ResetForHostTest()
    {
        lock (Sync)
        {
            readiness = null; preparation = null; passiveCapture = null; optInRequested = false; configured = false;
            prepareAttempted = false; originalManagerInitClaimed = false; failure = null;
            originalManagerInitReturned = false;
            nativeLibraryLoaded = false;
            nativeInitAttemptObserved = false;
            successfulOriginalRenderFrames = 0; passiveCaptureStopRequested = false;
            postCallbacksResult = 0; postCallbacksSeen = false; engineTermReturns = 0; callbackManagerTermReturns = 0;
            OriginalOwnerProbeObserver.Observer.BeforeEngineInit = null;
            OriginalOwnerProbeObserver.Observer.BeforeEngineTerm = null;
            OriginalOwnerProbeObserver.Observer.InitReturned = null;
            OriginalOwnerProbeObserver.Observer.InitBankReturned = null;
            OriginalOwnerProbeObserver.Observer.InitializeMethodReturned = null;
            OriginalOwnerProbeObserver.Observer.EngineTermReturned = null;
            OriginalOwnerProbeObserver.Observer.CallbackManagerTermReturned = null;
            OriginalOwnerProbeObserver.Observer.PostCallbacksReturned = null;
            OriginalOwnerProbeObserver.Observer.RenderAudioReturned = null;
        }
    }
#endif
}
