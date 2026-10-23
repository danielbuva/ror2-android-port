using System;
using System.Collections;
using UnityEngine;

// Persistent setup/session coordinator for the original game audio owner. This
// component owns no Ak/Wwise lifecycle; the original AkInitializer and
// AudioManager remain the only engine/service/focus/pause/Term owners.
public sealed class PortSessionOriginalAudioOwner : MonoBehaviour
{
    private const float StartupDeadlineSeconds = 180.0f;
    private static readonly object Sync = new object();
    private static PortSessionOriginalAudioOwner instance;
    private static int sessionEntries;
    private static bool pointSoundLogObserverAttached;
    private bool started;
    private bool completed;
    private float elapsed;
    private string coordinatorFailure;
    private string catalogLeaseIdentity;
    private bool catalogLeaseAcquired;

    [Serializable]
    public sealed class Snapshot
    {
        public string phase;
        public string failure;
        public bool requestConfigured;
        public bool managerInitClaimed;
        public bool managerInitReturned;
        public bool ready;
        public bool noAudio;
        public bool nativeApiCallsAvailable;
        public bool nativeInitAttemptObserved;
        public bool originalTermsReturned;
        public bool catalogBundleLeaseHeld;
        public string catalogBundleLeaseIdentity;
        public int requestedBankCount;
        public int completedBankCount;
        public int sessionEntries;
        public float observedStartupSeconds;
        public bool passivePcmCaptureRequested;
        public bool passivePcmMusicOutputRequested;
        public bool passivePcmGameplayArmRequested;
        public float passivePcmWindowStartRealtimeSinceStartup;
        public ulong passivePcmWindowStartServiceFrames;
        public bool passivePcmTerminalStopRequested;
        public string passivePcmState;
        public string passivePcmStopReason;
        public string passivePcmFailure;
        public ulong passivePcmCallbacks, passivePcmFrames, passivePcmSamples, passivePcmFiniteSamples;
        public ulong passivePcmNonzeroFiniteSamples, passivePcmNonfiniteSamples, passivePcmRejectedBuffers, passivePcmCappedBuffers;
        public string passivePcmWaveformReadbackState;
        public string passivePcmWaveformReadbackFailure;
        public bool passivePcmWaveformRawPersisted;
        public ulong passivePcmWaveformGeneration;
        public uint passivePcmWaveformStoredSamples;
        public bool passivePcmOutputIdentityObserved;
        public bool passivePcmCaptureOutputDeviceIdObserved;
        public ulong passivePcmCaptureOutputDeviceId;
        public string passivePcmCaptureOutputDeviceIdDecimal;
        public bool passivePcmCaptureSelectorObserved;
        public string passivePcmCaptureSelectorMode;
        public bool passivePcmCaptureSelectedOutputIdKnown;
        public ulong passivePcmCaptureSelectedOutputId;
        public string passivePcmCaptureSelectedOutputIdDecimal;
        public bool managedDefaultListenerCensusKnown;
        public int managedDefaultListenerCount;
        public OriginalNetworkSoundEventCatalogOwner.Snapshot networkSoundEventCatalog;
        public PortSessionOriginalMusicControllerOwner.Snapshot originalMusicController;
    }

    public static string StartupFailure
    {
        get
        {
            lock (Sync)
                return ReferenceEquals(instance, null) ? null : instance.coordinatorFailure;
        }
    }

    public static IEnumerator EnsureOriginalOwner()
    {
        while (GameAudioOriginalOwner.PassiveCaptureStopRequested && !GameAudioOriginalOwner.OriginalTermsReturned)
            yield return null; // A live/unknown callback retains the process and catalog roots.
        PortSessionOriginalAudioOwner host;
        lock (Sync)
        {
            sessionEntries++;
            if (!instance)
            {
                var gameObject = new GameObject("Original Wwise process owner coordinator");
                UnityEngine.Object.DontDestroyOnLoad(gameObject);
                instance = gameObject.AddComponent<PortSessionOriginalAudioOwner>();
            }
            host = instance;
            if (!host.started)
            {
                host.started = true;
                host.StartCoroutine(host.RunOriginalOwnerOnce());
            }
        }
        while (!host.completed) yield return null;
    }

    // Unity owns this callback boundary, while Core retains a Unity-free
    // bounded observer. Subscribe only for an explicitly selected PortSession.
    public static void ConfigurePointSoundDiagnostic(bool requested)
    {
        GameAudioOriginalOwner.ConfigurePointSoundDiagnostic(requested);
        if (!requested || pointSoundLogObserverAttached) return;
        Application.logMessageReceived += ObservePointSoundLog;
        pointSoundLogObserverAttached = true;
    }

    public static void DisablePointSoundDiagnostic()
    {
        GameAudioOriginalOwner.DisablePointSoundDiagnostic();
        if (!pointSoundLogObserverAttached) return;
        Application.logMessageReceived -= ObservePointSoundLog;
        pointSoundLogObserverAttached = false;
    }

    public static PointSoundDiagnosticObserver.Snapshot CapturePointSoundDiagnosticSnapshot() =>
        GameAudioOriginalOwner.CapturePointSoundDiagnosticSnapshot();

    public static bool PassivePcmCaptureRequested
    { get { return GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested; } }

    public static bool PassivePcmCaptureAfterAuthoritySkillRequested
    { get { return GameAudioOriginalRequestBootstrap.PassivePcmCaptureAfterAuthoritySkillRequested; } }

    public static bool PassivePcmGameplayArmRequested
    { get { return GameAudioOriginalOwner.PassiveCaptureArmRequested; } }

    public static void FinishPassivePcmCaptureGameplayWindow()
    {
        GameAudioOriginalOwner.FinishPassiveCaptureGameplayWindow();
    }

    public static bool ArmPassivePcmCaptureAtGameplayBoundary(bool playableWorldStarted)
    {
        if (!playableWorldStarted || !GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested)
            return false;
        GameAudioOriginalPassivePcmCaptureSelection selection =
            GameAudioOriginalPassivePcmCaptureSelection.MainOutput();
        if (GameAudioOriginalRequestBootstrap.PassivePcmCaptureMusicOutputRequested)
        {
            PortSessionOriginalMusicControllerOwner.Snapshot music =
                PortSessionOriginalMusicControllerOwner.CaptureSnapshot();
            bool currentOwner = music != null && music.requested && music.sourceAudioReady &&
                !music.noAudio && music.engineInitialized && music.staticInstanceMatchesOwnedController &&
                !music.outputObservationOwnerMismatch && !music.ownerCleanupRequested &&
                !music.controllerDestroyedObserved && !music.removeOutputResultObserved;
            if (!GameAudioOriginalPassivePcmCaptureSelection.TrySpecificOutput(currentOwner,
                music != null && music.outputResultObserved && music.outputAccepted,
                music != null && music.outputDeviceIdValid,
                music == null ? 0UL : music.outputDeviceId, out selection))
                return false; // A selected music-output profile never falls back to MainOutput.
        }
        return GameAudioOriginalOwner.ArmPassiveCaptureAtGameplayBoundary(
            GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested, playableWorldStarted, selection);
    }

    private static void ObservePointSoundLog(string condition, string stackTrace, LogType type)
    {
        try { PointSoundDiagnosticObserver.ObserveUnityLog(condition, stackTrace); }
        catch { /* The diagnostic callback never changes Unity's original log path. */ }
    }

    public static Snapshot CaptureSnapshot()
    {
        PortSessionOriginalAudioOwner host;
        int entries;
        lock (Sync) { host = instance; entries = sessionEntries; }
        bool ready = GameAudioOriginalOwner.Ready;
        bool claimed = GameAudioOriginalOwner.OriginalManagerInitClaimed;
        string failure = (host ? host.coordinatorFailure : null) ?? GameAudioOriginalOwner.Failure;
        IGameAudioOriginalPassivePcmCapture pcm = GameAudioOriginalOwner.PassiveCapture;
        bool managedDefaultListenerCensusKnown = false;
        int managedDefaultListenerCount = 0;
        if (ready && GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested)
        {
            try
            {
                // This is the Wwise-managed list only. It performs no native
                // query and does not prove native default-listener registration.
                int count = AkAudioListener.DefaultListeners.ListenerList.Count;
                if (count >= 0)
                {
                    managedDefaultListenerCount = count;
                    managedDefaultListenerCensusKnown = true;
                }
            }
            catch
            {
                // A census read failure remains unknown and cannot break Save.
            }
        }
        return new Snapshot {
            phase = failure != null ? "failed_closed" : (ready ? "ready" : (claimed ? "original_manager_starting" :
                (GameAudioOriginalOwner.StartupSelected ? "prepared" : (host && host.completed ? "disabled_or_refused" : "starting")))),
            failure = failure,
            requestConfigured = GameAudioOriginalRequestBootstrap.IsConfigured,
            managerInitClaimed = claimed,
            managerInitReturned = GameAudioOriginalOwner.OriginalManagerInitReturned,
            ready = ready,
            noAudio = GameAudioOriginalOwner.NoAudio,
            nativeApiCallsAvailable = GameAudioOriginalOwner.NativeApiCallsAvailable,
            nativeInitAttemptObserved = GameAudioOriginalOwner.NativeInitAttemptObserved,
            originalTermsReturned = GameAudioOriginalOwner.OriginalTermsReturned,
            catalogBundleLeaseHeld = WholeCatalogComposed.OriginalAudioLeaseHeld,
            catalogBundleLeaseIdentity = WholeCatalogComposed.OriginalAudioLeaseIdentity,
            requestedBankCount = GameAudioOriginalOwner.RequestedBankCount,
            completedBankCount = GameAudioOriginalOwner.CompletedBankCount,
            sessionEntries = entries,
            observedStartupSeconds = host ? host.elapsed : 0f,
            passivePcmCaptureRequested = GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested,
            passivePcmMusicOutputRequested = GameAudioOriginalRequestBootstrap.PassivePcmCaptureMusicOutputRequested,
            passivePcmGameplayArmRequested = pcm != null && pcm.ArmRequested,
            passivePcmWindowStartRealtimeSinceStartup = pcm == null ? 0f : pcm.WindowStartRealtimeSinceStartup,
            passivePcmWindowStartServiceFrames = pcm == null ? 0UL : pcm.WindowStartServiceFrames,
            passivePcmTerminalStopRequested = GameAudioOriginalOwner.PassiveCaptureStopRequested,
            passivePcmState = pcm == null ? "disabled" : pcm.State,
            passivePcmStopReason = pcm == null ? null : pcm.StopReason,
            passivePcmFailure = pcm == null ? null : pcm.Failure,
            passivePcmCallbacks = pcm == null ? 0 : pcm.CallbackCount,
            passivePcmFrames = pcm == null ? 0 : pcm.FrameCount,
            passivePcmSamples = pcm == null ? 0 : pcm.SampleCount,
            passivePcmFiniteSamples = pcm == null ? 0 : pcm.FiniteSamples,
            passivePcmNonzeroFiniteSamples = pcm == null ? 0 : pcm.NonzeroFiniteSamples,
            passivePcmNonfiniteSamples = pcm == null ? 0 : pcm.NonfiniteSamples,
            passivePcmRejectedBuffers = pcm == null ? 0 : pcm.RejectedBuffers,
            passivePcmCappedBuffers = pcm == null ? 0 : pcm.CappedBuffers,
            passivePcmWaveformReadbackState = pcm == null ? "not_requested" : pcm.WaveformReadbackState,
            passivePcmWaveformReadbackFailure = pcm == null ? null : pcm.WaveformReadbackFailure,
            passivePcmWaveformRawPersisted = pcm != null && pcm.WaveformRawPersisted,
            passivePcmWaveformGeneration = pcm == null ? 0UL : pcm.WaveformGeneration,
            passivePcmWaveformStoredSamples = pcm == null ? 0U : pcm.WaveformStoredSamples,
            passivePcmOutputIdentityObserved = pcm != null && pcm.OutputIdentityObserved,
            passivePcmCaptureOutputDeviceIdObserved = pcm != null && pcm.CaptureOutputDeviceIdObserved,
            passivePcmCaptureOutputDeviceId = pcm == null ? 0UL : pcm.CaptureOutputDeviceId,
            passivePcmCaptureOutputDeviceIdDecimal = pcm != null && pcm.CaptureOutputDeviceIdObserved
                ? GameAudioOriginalPassivePcmIdentity.ToDecimalString(pcm.CaptureOutputDeviceId) : null,
            passivePcmCaptureSelectorObserved = pcm != null && pcm.CaptureSelectorObserved,
            passivePcmCaptureSelectorMode = pcm != null && pcm.CaptureSelectorObserved
                ? (pcm.CaptureSelection.Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.MainOutput ? "main" : "specific") : null,
            passivePcmCaptureSelectedOutputIdKnown = pcm != null && pcm.CaptureSelectorObserved &&
                pcm.CaptureSelection.SpecificOutputIdKnown,
            passivePcmCaptureSelectedOutputId = pcm != null && pcm.CaptureSelectorObserved &&
                pcm.CaptureSelection.SpecificOutputIdKnown ? pcm.CaptureSelection.SpecificOutputId : 0UL,
            passivePcmCaptureSelectedOutputIdDecimal = pcm != null && pcm.CaptureSelectorObserved &&
                pcm.CaptureSelection.SpecificOutputIdKnown
                ? GameAudioOriginalPassivePcmIdentity.ToDecimalString(pcm.CaptureSelection.SpecificOutputId) : null,
            managedDefaultListenerCensusKnown = managedDefaultListenerCensusKnown,
            managedDefaultListenerCount = managedDefaultListenerCount,
            networkSoundEventCatalog = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot(),
            originalMusicController = PortSessionOriginalMusicControllerOwner.CaptureSnapshot()
        };
    }

    private IEnumerator RunOriginalOwnerOnce()
    {
        float startedAt = Time.realtimeSinceStartup;
        try
        {
            // This route enters RegisterBodyCatalog before AwaitOfflineRunStart;
            // the original settings asset is already in that owned content bundle.
            // The closure is only invoked for an explicit request and obtains the
            // same GUID-bound object referenced by the original WwiseGlobal prefab.
            GameAudioOriginalRequestBootstrap.OriginalSettingsProvider = () =>
                WholeCatalogComposed.LoadOwnedContent<AkWwiseInitializationSettings>(
                    "Assets/WholeGame/Wwise/ScriptableObjects/AkWwiseInitializationSettings.asset");
            Exception setupError = null;
            try { GameAudioOriginalRequestBootstrap.ConfigureBeforeOriginalStartup(); }
            catch (Exception error) { setupError = error; }
            if (setupError != null)
            {
                coordinatorFailure = "original_audio_configuration_threw:" + setupError.GetType().Name;
                yield break;
            }

            if (GameAudioOriginalOwner.OptInRequested)
            {
                try
                {
                    if (!WholeCatalogComposed.IsConfigured)
                        throw new InvalidOperationException("The current PortSession route did not prepare the shared whole-catalog owner.");
                    catalogLeaseIdentity = WholeCatalogComposed.RetainForOriginalAudioOwner(
                        "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88");
                    catalogLeaseAcquired = true;
                }
                catch (Exception error)
                {
                    coordinatorFailure = "original_audio_catalog_lease_refused:" + error.GetType().Name;
                    yield break;
                }
            }

            IEnumerator preparation = null;
            try { preparation = GameAudioOriginalOwner.PrepareBeforeOriginalManagerInit(); }
            catch (Exception error)
            {
                GameAudioOriginalOwner.RecordOriginalManagerInitException(error.GetType().Name);
                GameAudioOriginalOwner.AbandonPreparationBeforeOriginalInit();
            }
            if (preparation != null)
            {
                bool keepPreparing = true;
                while (keepPreparing)
                {
                    bool moved = false;
                    object current = null;
                    try { moved = preparation.MoveNext(); current = moved ? preparation.Current : null; }
                    catch (Exception error)
                    {
                        coordinatorFailure = "original_audio_preparation_owner_threw:" + error.GetType().Name;
                        GameAudioOriginalOwner.RecordOriginalManagerInitException(error.GetType().Name);
                        GameAudioOriginalOwner.AbandonPreparationBeforeOriginalInit();
                        keepPreparing = false;
                    }
                    if (!keepPreparing || !moved) break;
                    yield return current;
                }
            }
            if (!GameAudioOriginalOwner.StartupSelected) yield break;

            if (UnityEngine.Object.FindObjectOfType<AkInitializer>())
            {
                GameAudioOriginalOwner.RecordExistingInitializerConflict();
                GameAudioOriginalOwner.AbandonPreparationBeforeOriginalInit();
                yield break;
            }
            if (GameAudioOriginalOwner.TryBeginOriginalManagerInit())
            {
                Exception managerError = null;
                try
                {
                    // Exact accepted static manager call; its unchanged body issues
                    // both LegacyResourcesAPI requests and preserves their callbacks.
                    RoR2.WwiseIntegrationManager.Init();
                    GameAudioOriginalOwner.RecordOriginalManagerInitReturned();
                }
                catch (Exception error) { managerError = error; }
                if (managerError != null)
                {
                    GameAudioOriginalOwner.RecordOriginalManagerInitException(managerError.GetType().Name);
                    GameAudioOriginalOwner.AbandonPreparationBeforeOriginalInit();
                    yield break;
                }
            }

            while (!GameAudioOriginalOwner.Ready && !GameAudioOriginalOwner.HasTerminalFailure &&
                   Time.realtimeSinceStartup - startedAt < StartupDeadlineSeconds)
            {
                elapsed = Time.realtimeSinceStartup - startedAt;
                yield return null;
            }
            if (!GameAudioOriginalOwner.Ready && !GameAudioOriginalOwner.HasTerminalFailure)
            {
                GameAudioOriginalOwner.RecordStartupTimeout();
                GameAudioOriginalOwner.AbandonPreparationBeforeOriginalInit();
            }
            if (GameAudioOriginalOwner.Ready && GameAudioOriginalOwner.OptInRequested)
            {
                if (!RoR2.WwiseIntegrationManager.noAudio)
                {
                    try
                    {
                        OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(
                            explicitlyRequested: true,
                            noAudio: RoR2.WwiseIntegrationManager.noAudio,
                            originalAudioReady: GameAudioOriginalOwner.Ready,
                            originalTermsReturned: GameAudioOriginalOwner.OriginalTermsReturned,
                            nativeEngineInitialized: AkSoundEngine.IsInitialized(),
                            originalCatalogLeaseHeld: WholeCatalogComposed.OriginalAudioLeaseHeld);
                    }
                    catch
                    {
                        var catalog = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
                        coordinatorFailure = "original_network_sound_catalog_refused:" +
                            (catalog.failure ?? "initializer-threw");
                        throw; // Preserve the exception; PortSession records the explicit startup refusal.
                    }
                }
                PortSessionOriginalMusicControllerOwner.StartForReadyAudio(this, explicitlyRequested: true);
            }
        }
        finally
        {
            elapsed = Time.realtimeSinceStartup - startedAt;
            // If the request was refused before the original manager was
            // admitted, no Wwise prefab/initializer owns this bundle yet and
            // the normal catalog cleanup may unload it. Once manager startup
            // was claimed, retain it until the exact original Term witnesses.
            if (catalogLeaseAcquired && !GameAudioOriginalOwner.OriginalManagerInitClaimed &&
                !GameAudioOriginalOwner.OriginalTermsReturned)
                ReleaseCatalogLease();
            completed = true;
        }
    }

    private void Update()
    {
        GameAudioOriginalOwner.TickPassiveCapture(Time.realtimeSinceStartup);
        if (GameAudioOriginalOwner.OriginalTermsReturned)
        {
            try { GameAudioOriginalOwner.PassiveCapture?.PersistWaveformAfterOriginalTerms(); }
            catch { /* optional waveform evidence cannot become an audio lifecycle failure */ }
        }
        if (catalogLeaseAcquired && GameAudioOriginalOwner.OriginalTermsReturned)
        {
            var music = GetComponent<PortSessionOriginalMusicControllerOwner>();
            if (music)
            {
                music.NotifyOriginalTermsReturned();
                if (!music.MayReleaseOriginalAudioCatalogLease)
                    return; // Retain track banks while source callbacks/controller ownership remain live.
            }
            ReleaseCatalogLease();
        }
    }

    private void ReleaseCatalogLease()
    {
        if (!catalogLeaseAcquired) return;
        try
        {
            WholeCatalogComposed.ReleaseOriginalAudioOwnerLease(catalogLeaseIdentity);
            catalogLeaseAcquired = false;
            catalogLeaseIdentity = null;
        }
        catch (Exception error)
        {
            coordinatorFailure = coordinatorFailure ?? "original_audio_catalog_lease_release_failed:" + error.GetType().Name;
        }
    }
}
