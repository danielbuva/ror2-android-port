using System;
using System.Reflection;
using System.Linq;
using UnityEngine.Scripting;

// Process-lifetime owner for the optional diagnostic capture callback only.
// The game assembly binds this type and two members by reflection, so preserve
// only that exact reflected surface through UnityLinker.
// It shares the original bootstrap's NativeWwiseMonitorLease and never creates,
// initializes, services, or terminates a Wwise engine.
[Preserve]
internal sealed class OriginalGameAudioPassivePcmOwner : IGameAudioOriginalPassivePcmCapture
{
    private static readonly object Sync = new object();
    private static OriginalGameAudioPassivePcmOwner processOwner;
    private static bool configured;

    private readonly bool requested;
    private readonly NativeWwiseMonitorLease existingMonitorLease;
    private readonly PassivePcmCaptureWindow window;
    private readonly FieldInfo apiBeforeEngineTermField;
    private readonly Action<string> requestCoordinatorStop;
    private readonly object gate = new object();
    private Action installedBeforeTermGuard;
    private bool gameplayArmRequested;
    private bool started;
    private bool terminalRefusal;
    private string terminalFailure;

    private OriginalGameAudioPassivePcmOwner(GameAudioOriginalAndroidNativeBootstrap bootstrap)
    {
        if (bootstrap == null) throw new ArgumentNullException(nameof(bootstrap));
        requested = true;
        existingMonitorLease = bootstrap.MonitorLease;
        if (existingMonitorLease == null || !bootstrap.OwnsMonitorLease(existingMonitorLease))
            throw new InvalidOperationException("Capture must use the exact live lease owned by the accepted native bootstrap.");
        requestCoordinatorStop = reason => GameAudioOriginalOwner.RequestPassivePcmTerminalStop(reason);
        // The transformed Wwise API and Core compile duplicate observer type
        // names into distinct assemblies. Bind the API assembly's exact static
        // field by assembly identity; a missing/ambiguous helper refuses capture.
        apiBeforeEngineTermField = ResolveApiBeforeEngineTermField();
        window = new PassivePcmCaptureWindow(existingMonitorLease, true,
            InstallBeforeEngineTermGuard,
            ReadBeforeEngineTermGuard, RecordTermRefusal);
    }

    // Called exactly once from the accepted process-lifetime preparation. A
    // generated request must explicitly select capture; false is the default.
    // A second capture owner or a different native lease is never admitted.
    internal static OriginalGameAudioPassivePcmOwner CreateForAcceptedBootstrap(
        GameAudioOriginalAndroidNativeBootstrap bootstrap, bool captureRequested)
    {
        lock (Sync)
        {
            if (configured)
                throw new InvalidOperationException("The passive PCM process selection is immutable and already configured.");
            configured = true;
            if (!captureRequested) return null;
            if (bootstrap == null) throw new ArgumentNullException(nameof(bootstrap));
            processOwner = new OriginalGameAudioPassivePcmOwner(bootstrap);
            return processOwner;
        }
    }

    // The static reference intentionally retains the window, exact delegate,
    // existing native lease, and stop callback through scene/session teardown.
    internal static OriginalGameAudioPassivePcmOwner ProcessLifetimeOwner
    {
        [Preserve]
        get { lock (Sync) return processOwner; }
    }

    // Keep the already-installed passive-capture guard as the single callback
    // owner. The music participant is appended to that owner, never installed
    // over its API/Core delegate.
    [Preserve]
    internal static bool RegisterMusicBeforeTerm(Action handler)
    {
        if (handler == null) throw new ArgumentNullException(nameof(handler));
        lock (Sync)
        {
            if (processOwner == null) return false;
            Action current = processOwner.ReadBeforeEngineTermGuard();
            if (!Object.ReferenceEquals(current, processOwner.installedBeforeTermGuard) || current == null)
                throw new InvalidOperationException("The existing passive pre-Term guard no longer matches its API/Core owner.");
            processOwner.window.RegisterBeforeEngineTermParticipant(handler);
            return true;
        }
    }

#if GAME_AUDIO_HOST_TEST
    internal static void ResetForHostTest()
    { lock (Sync) { processOwner = null; configured = false; } }
#endif

    internal bool TerminalRefusal { get { return terminalRefusal; } }
    public bool TerminalStopRequested { get { return terminalRefusal; } }
    public bool ArmRequested { get { lock (gate) return gameplayArmRequested; } }
    public float WindowStartRealtimeSinceStartup { get { lock (gate) return window.WindowStartRealtimeSinceStartup; } }
    public ulong WindowStartServiceFrames { get { lock (gate) return window.WindowStartServiceFrames; } }
    public string State { get { lock (gate) return window.State; } }
    public string StopReason { get { lock (gate) return window.StopReason; } }
    public string Failure { get { lock (gate) return terminalFailure ?? window.Failure; } }
    private PassivePcmCaptureReport CurrentReport { get { lock (gate) return window.Report; } }
    public ulong CallbackCount { get { return CurrentReport.CallbackCount; } }
    public ulong FrameCount { get { return CurrentReport.FrameCount; } }
    public ulong SampleCount { get { return CurrentReport.SampleCount; } }
    public ulong FiniteSamples { get { return CurrentReport.FiniteSamples; } }
    public ulong NonzeroFiniteSamples { get { return CurrentReport.NonzeroFiniteSamples; } }
    public ulong NonfiniteSamples { get { return CurrentReport.NonfiniteSamples; } }
    public ulong RejectedBuffers { get { return CurrentReport.RejectedBuffers; } }
    public ulong CappedBuffers { get { return CurrentReport.CappedBuffers; } }
    public bool OutputIdentityObserved { get { return CurrentReport.OutputIdentityObserved; } }
    public bool CaptureOutputDeviceIdObserved { get { return CurrentReport.CaptureOutputDeviceIdObserved; } }
    public ulong CaptureOutputDeviceId { get { return CurrentReport.CaptureOutputDeviceId; } }
    internal string TerminalFailure { get { return terminalFailure; } }
    internal string CaptureState { get { return window.State; } }
    internal PassivePcmCaptureReport Report { get { return window.Report; } }

    // The coordinator calls this only after the selected playable world has
    // spawned its original body. Engine readiness alone never starts capture.
    public bool RequestGameplayArm()
    {
        lock (gate)
        {
            if (!requested || terminalRefusal || gameplayArmRequested) return gameplayArmRequested;
            gameplayArmRequested = window.RequestGameplayArm();
            return gameplayArmRequested;
        }
    }

    public void FinishGameplayWindow()
    {
        lock (gate)
        {
            if (!requested || !gameplayArmRequested || terminalRefusal) return;
            window.FinishGameplayWindow();
            if (window.Failure != null && !existingMonitorLease.CaptureSafeBeforeEngineTerm)
            {
                terminalFailure = "passive_capture_session_end_outcome_unknown";
                terminalRefusal = true;
                try { requestCoordinatorStop?.Invoke(terminalFailure); } catch { }
            }
        }
    }

    // Called from the existing PortSession owner's persistent Update after the
    // original API's PostCallbacks/RenderAudio return observers have advanced.
    public void Tick(float realtimeSinceStartup, bool ownerReady, bool exactControlObserved,
        ulong successfulOriginalRenderFrames)
    {
        lock (gate)
        {
        if (!requested || !gameplayArmRequested || terminalRefusal) return;
        if (!started)
        {
            // Require the actual original owner readiness and at least one
            // successful original service frame before capture registration.
            if (!ownerReady || !exactControlObserved || successfulOriginalRenderFrames == 0) return;
            started = window.Start(realtimeSinceStartup, ownerReady, exactControlObserved,
                true, successfulOriginalRenderFrames);
            if (!started && window.Failure != null &&
                !existingMonitorLease.CaptureSafeBeforeEngineTerm)
            {
                terminalFailure = "passive_capture_registration_outcome_unknown";
                terminalRefusal = true;
                try { requestCoordinatorStop?.Invoke(terminalFailure); } catch { }
            }
            return;
        }
        window.Tick(realtimeSinceStartup, ownerReady, exactControlObserved,
            successfulOriginalRenderFrames);
        // A failed snapshot after known registration leaves the callback live
        // while the lease outcome is unknown. Stop the original session's
        // lifecycle work now; the pre-Term gate may make the single cleanup-only
        // unregister attempt later. Do not infer ownership or clear the process
        // root here.
        if (window.Failure != null &&
            !existingMonitorLease.CaptureSafeBeforeEngineTerm)
        {
            terminalFailure = "passive_capture_tick_outcome_unknown";
            terminalRefusal = true;
            try { requestCoordinatorStop?.Invoke(terminalFailure); } catch { }
        }
        }
    }

    // The window calls this while preparing to rethrow. Do not release or clear
    // this process owner, the original monitor lease, or the coordinator's
    // whole-catalog lease on refusal.
    public void BeforeOriginalEngineTerm()
    {
        lock (gate) window.BeforeOriginalEngineTerm();
    }

    private static FieldInfo ResolveApiBeforeEngineTermField()
    {
        const string apiAssemblyName = "AK.Wwise.Unity.API";
        const string observerAssemblyName = "OriginalOwnerProbeObserver";
        const string typeName = "OriginalOwnerProbeObserver.Observer";
        Assembly apiAssembly = Assembly.Load(new AssemblyName(apiAssemblyName));
        var references = apiAssembly.GetReferencedAssemblies()
            .Where(reference => String.Equals(reference.Name, observerAssemblyName, StringComparison.Ordinal))
            .ToArray();
        if (references.Length != 1)
            throw new InvalidOperationException("The transformed Wwise API does not reference exactly one pinned observer assembly.");

        var matches = AppDomain.CurrentDomain.GetAssemblies()
            .Where(assembly => String.Equals(assembly.FullName, references[0].FullName, StringComparison.Ordinal))
            .ToArray();
        if (matches.Length > 1)
            throw new InvalidOperationException("The transformed Wwise API observer identity is loaded more than once.");
        Assembly assembly = matches.Length == 1 ? matches[0] : Assembly.Load(references[0]);
        if (!String.Equals(assembly.FullName, references[0].FullName, StringComparison.Ordinal))
            throw new InvalidOperationException("The loaded observer assembly identity differs from the transformed Wwise API reference.");
        Type observerType = assembly.GetType(typeName, false, false);
        if (observerType == null)
            throw new InvalidOperationException("The transformed Wwise API observer type is unavailable.");
        FieldInfo field = observerType.GetField("BeforeEngineTerm", BindingFlags.Public | BindingFlags.Static);
        MethodInfo method = observerType.GetMethod("RecordBeforeEngineTerm", BindingFlags.Public | BindingFlags.Static);
        if (field == null || field.FieldType != typeof(Action) || !field.IsStatic || method == null ||
            method.ReturnType != typeof(void) || method.GetParameters().Length != 0 || !method.IsStatic)
            throw new InvalidOperationException("The transformed Wwise API observer has no exact Action BeforeEngineTerm field.");
        return field;
    }

    private void InstallBeforeEngineTermGuard(Action handler)
    {
        if (handler == null) throw new ArgumentNullException(nameof(handler));
        Action coreExisting = OriginalOwnerProbeObserver.Observer.BeforeEngineTerm;
        Action apiExisting = apiBeforeEngineTermField.GetValue(null) as Action;
        if (coreExisting != null || apiExisting != null)
            throw new InvalidOperationException("A pre-Term observer is already installed; refusing to replace it.");
        try
        {
            apiBeforeEngineTermField.SetValue(null, handler);
            OriginalOwnerProbeObserver.Observer.BeforeEngineTerm = handler;
            installedBeforeTermGuard = handler;
        }
        catch
        {
            apiBeforeEngineTermField.SetValue(null, null);
            OriginalOwnerProbeObserver.Observer.BeforeEngineTerm = null;
            installedBeforeTermGuard = null;
            throw;
        }
    }

    private Action ReadBeforeEngineTermGuard()
    {
        Action coreHandler = OriginalOwnerProbeObserver.Observer.BeforeEngineTerm;
        Action apiHandler = apiBeforeEngineTermField.GetValue(null) as Action;
        if (!Object.ReferenceEquals(coreHandler, apiHandler))
            throw new InvalidOperationException("The Core and transformed Wwise API do not share the exact pre-Term guard.");
        return coreHandler;
    }

    private void RecordTermRefusal(Exception error)
    {
        terminalRefusal = true;
        terminalFailure = "passive_capture_term_refused:" + error.GetType().Name;
        try { requestCoordinatorStop?.Invoke(terminalFailure); }
        catch { /* preserve the window's original fail-closed exception */ }
    }
}
