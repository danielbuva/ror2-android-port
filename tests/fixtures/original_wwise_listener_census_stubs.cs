using System;
using System.Collections;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public static implicit operator bool(Object value) => value != null;
        public static bool operator !(Object value) => value == null;
        public static void DontDestroyOnLoad(Object value) { }
        public static T FindObjectOfType<T>() where T : Object => null;
    }
    public class Component : Object { }
    public class MonoBehaviour : Component
    {
        protected void StartCoroutine(IEnumerator routine) { }
        protected T GetComponent<T>() where T : Component => null;
    }
    public sealed class GameObject : Object
    {
        public GameObject(string name) { }
        public T AddComponent<T>() where T : Component, new() => new T();
    }
    public enum LogType { Error }
    public static class Application
    {
        public static event Action<string, string, LogType> logMessageReceived;
    }
    public static class Time
    {
        public static float realtimeSinceStartup;
    }
}


// The listener-census fixture compiles only the audio owner; its unrelated
// snapshot member is represented by this shape-only stub. The music owner has
// its own compiled lifecycle fixture.
public sealed class PortSessionOriginalMusicControllerOwner : UnityEngine.Component
{
    public sealed class Snapshot
    {
        public bool requested, sourceAudioReady, noAudio, engineInitialized;
        public bool staticInstanceMatchesOwnedController, outputObservationOwnerMismatch;
        public bool ownerCleanupRequested, controllerDestroyedObserved, removeOutputResultObserved;
        public bool outputResultObserved, outputAccepted, outputDeviceIdValid;
        public ulong outputDeviceId;
    }
    public static Snapshot CaptureSnapshot() => null;
    public static void StartForReadyAudio(UnityEngine.MonoBehaviour owner, bool explicitlyRequested) { }
    public void NotifyOriginalTermsReturned() { }
    public bool MayReleaseOriginalAudioCatalogLease => false;
}

public sealed class AkWwiseInitializationSettings { }
public sealed class AkInitializer : UnityEngine.Object { }

public sealed class AkAudioListener
{
    private static readonly DefaultListenerList listeners = new DefaultListenerList();
    public static int GetterReads;
    public static bool ThrowOnRead;
    public static DefaultListenerList DefaultListeners
    {
        get
        {
            GetterReads++;
            if (ThrowOnRead) throw new InvalidOperationException("synthetic census read failure");
            return listeners;
        }
    }
    public sealed class DefaultListenerList
    {
        public readonly List<AkAudioListener> ListenerList = new List<AkAudioListener>();
    }
}

public static class GameAudioOriginalRequestBootstrap
{
    public static bool PassivePcmCaptureRequested;
    public static bool PassivePcmCaptureMusicOutputRequested;
    public static bool PassivePcmCaptureAfterAuthoritySkillRequested;
    public static bool IsConfigured;
    public static Func<AkWwiseInitializationSettings> OriginalSettingsProvider;
    public static void ConfigureBeforeOriginalStartup() { }
}

public static class GameAudioOriginalOwner
{
    public static bool PassiveCaptureStopRequested;
    public static bool OriginalTermsReturned;
    public static bool Ready;
    public static bool OriginalManagerInitClaimed;
    public static string Failure;
    public static bool StartupSelected;
    public static bool OptInRequested;
    public static IGameAudioOriginalPassivePcmCapture PassiveCapture;
    public static bool PassiveCaptureArmRequested;
    public static bool NoAudio;
    public static bool NativeApiCallsAvailable;
    public static bool NativeInitAttemptObserved;
    public static bool OriginalManagerInitReturned;
    public static int RequestedBankCount;
    public static int CompletedBankCount;
    public static void ConfigurePointSoundDiagnostic(bool requested) { }
    public static void DisablePointSoundDiagnostic() { }
    public static PointSoundDiagnosticObserver.Snapshot CapturePointSoundDiagnosticSnapshot() => null;
    public static void FinishPassiveCaptureGameplayWindow() { }
    public static bool ArmPassiveCaptureAtGameplayBoundary(bool requested, bool playableWorldStarted, GameAudioOriginalPassivePcmCaptureSelection selection) => false;
    public static IEnumerator PrepareBeforeOriginalManagerInit() => null;
    public static void RecordOriginalManagerInitException(string type) { }
    public static void AbandonPreparationBeforeOriginalInit() { }
    public static void RecordExistingInitializerConflict() { }
    public static bool TryBeginOriginalManagerInit() => false;
    public static void RecordOriginalManagerInitReturned() { }
    public static bool HasTerminalFailure;
    public static void RecordStartupTimeout() { }
    public static void TickPassiveCapture(float realtimeSinceStartup) { }
}

public static class WholeCatalogComposed
{
    public static bool OriginalAudioLeaseHeld;
    public static string OriginalAudioLeaseIdentity;
    public static bool IsConfigured;
    public static string RetainForOriginalAudioOwner(string expectedInputId) => "lease";
    public static T LoadOwnedContent<T>(string path) => default(T);
    public static void ReleaseOriginalAudioOwnerLease(string expectedIdentity) { }
}

public static class PointSoundDiagnosticObserver
{
    public sealed class Snapshot
    {
        public bool requested, sourceAudioReady, noAudio, engineInitialized;
        public bool staticInstanceMatchesOwnedController, outputObservationOwnerMismatch;
        public bool ownerCleanupRequested, controllerDestroyedObserved, removeOutputResultObserved;
        public bool outputResultObserved, outputAccepted, outputDeviceIdValid;
        public ulong outputDeviceId;
    }
    public static void ObserveUnityLog(string condition, string stackTrace) { }
}

namespace RoR2
{
    public static class WwiseIntegrationManager
    {
        public static bool noAudio;
        public static void Init() { }
    }
}

namespace UnityEngine
{
    public static class Debug
    {
        public static string LastLog, LastWarning;
        public static void Log(object value) { LastLog = value.ToString(); }
        public static void LogWarning(object value) { LastWarning = value.ToString(); }
    }
}
public enum AKRESULT { AK_Success = 1, AK_Fail = 2 }
public static class AkSoundEngine
{
    public static bool Initialized;
    public static bool ThrowOnWakeup;
    public static int WakeupCalls;
    public static AKRESULT WakeupResult = AKRESULT.AK_Success;
    public static bool IsInitialized() => Initialized;
    public static AKRESULT WakeupFromSuspend()
    {
        WakeupCalls++;
        if (ThrowOnWakeup) throw new InvalidOperationException("synthetic wakeup failure");
        return WakeupResult;
    }
}
public sealed class AkSoundEngineInitialization
{
    public delegate void TerminationDelegate();
    public static readonly AkSoundEngineInitialization Current = new AkSoundEngineInitialization();
    public static int GetterReads;
    public static AkSoundEngineInitialization Instance { get { GetterReads++; return Current; } }
    public TerminationDelegate terminationDelegate;
}
public static class OriginalNetworkSoundEventCatalogOwner
{
    public sealed class Snapshot { public string failure; }
    public static Snapshot CaptureSnapshot() => new Snapshot();
    public static void InitializeBeforeWorld(bool explicitlyRequested, bool noAudio, bool originalAudioReady,
        bool originalTermsReturned, bool nativeEngineInitialized, bool originalCatalogLeaseHeld) { }
}
