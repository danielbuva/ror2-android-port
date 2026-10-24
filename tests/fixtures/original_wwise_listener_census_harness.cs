using System;
using System.Collections.Generic;
using System.Reflection;

internal static class ListenerCensusHarness
{
    private static int Main()
    {
        var listeners = AkAudioListener.DefaultListeners.ListenerList;
        listeners.Clear();
        AkAudioListener.GetterReads = 0;

        GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested = false;
        GameAudioOriginalOwner.Ready = true;
        var snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (snapshot.managedDefaultListenerCensusKnown || snapshot.managedDefaultListenerCount != 0 ||
            AkAudioListener.GetterReads != 0)
            return 1;

        GameAudioOriginalRequestBootstrap.PassivePcmCaptureRequested = true;
        GameAudioOriginalOwner.Ready = false;
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (snapshot.managedDefaultListenerCensusKnown || snapshot.managedDefaultListenerCount != 0 ||
            AkAudioListener.GetterReads != 0)
            return 2;

        GameAudioOriginalOwner.Ready = true;
        listeners.Add(new AkAudioListener());
        listeners.Add(new AkAudioListener());
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (!snapshot.managedDefaultListenerCensusKnown || snapshot.managedDefaultListenerCount != 2 ||
            AkAudioListener.GetterReads != 1)
            return 3;

        listeners.Clear();
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (!snapshot.managedDefaultListenerCensusKnown || snapshot.managedDefaultListenerCount != 0 ||
            AkAudioListener.GetterReads != 2)
            return 4;

        AkAudioListener.ThrowOnRead = true;
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (snapshot.managedDefaultListenerCensusKnown || snapshot.managedDefaultListenerCount != 0 ||
            AkAudioListener.GetterReads != 3)
            return 5;

        // Exercise the actual process owner's termination-delegate extension.
        var owner = new PortSessionOriginalAudioOwner();
        typeof(PortSessionOriginalAudioOwner).GetField("instance", BindingFlags.NonPublic | BindingFlags.Static).SetValue(null, owner);
        Action<string> invoke = name => typeof(PortSessionOriginalAudioOwner).GetMethod(name,
            BindingFlags.NonPublic | BindingFlags.Instance).Invoke(owner, null);
        var initialization = AkSoundEngineInitialization.Current;
        int beforeCalls = 0, afterCalls = 0;
        initialization.terminationDelegate = () => beforeCalls++;
        GameAudioOriginalOwner.OptInRequested = true;
        GameAudioOriginalOwner.NativeApiCallsAvailable = true;
        GameAudioOriginalOwner.Ready = false;
        invoke("AttachOriginalBankReleaseWakeup");
        GameAudioOriginalOwner.Ready = true;
        GameAudioOriginalOwner.OptInRequested = false;
        invoke("AttachOriginalBankReleaseWakeup");
        GameAudioOriginalOwner.OptInRequested = true;
        GameAudioOriginalOwner.NativeApiCallsAvailable = false;
        invoke("AttachOriginalBankReleaseWakeup");
        GameAudioOriginalOwner.NativeApiCallsAvailable = true;
        RoR2.WwiseIntegrationManager.noAudio = true;
        invoke("AttachOriginalBankReleaseWakeup");
        if (AkSoundEngineInitialization.GetterReads != 0) return 10;
        RoR2.WwiseIntegrationManager.noAudio = false;
        invoke("AttachOriginalBankReleaseWakeup");
        invoke("AttachOriginalBankReleaseWakeup");
        initialization.terminationDelegate += () => afterCalls++;
        if (AkSoundEngineInitialization.GetterReads != 1 || initialization.terminationDelegate.GetInvocationList().Length != 3) return 11;

        GameAudioOriginalOwner.NativeApiCallsAvailable = false;
        initialization.terminationDelegate();
        GameAudioOriginalOwner.NativeApiCallsAvailable = true;
        AkSoundEngine.Initialized = false;
        initialization.terminationDelegate();
        if (AkSoundEngine.WakeupCalls != 0 || beforeCalls != 2 || afterCalls != 2) return 12;
        AkSoundEngine.Initialized = true;
        // A consumer no-audio/ready flag cannot block the still-initialized
        // original engine's own bank-release callback.
        GameAudioOriginalOwner.Ready = false;
        RoR2.WwiseIntegrationManager.noAudio = true;
        initialization.terminationDelegate();
        GameAudioOriginalOwner.Ready = true;
        RoR2.WwiseIntegrationManager.noAudio = false;
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (AkSoundEngine.WakeupCalls != 1 || !snapshot.bankReleaseWakeupAttached ||
            UnityEngine.Debug.LastLog != "Original audio bank-release wakeup returned AK_Success") return 13;
        AkSoundEngine.WakeupResult = AKRESULT.AK_Fail;
        initialization.terminationDelegate();
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (AkSoundEngine.WakeupCalls != 2 ||
            UnityEngine.Debug.LastLog != "Original audio bank-release wakeup returned AK_Fail") return 14;
        AkSoundEngine.ThrowOnWakeup = true;
        initialization.terminationDelegate();
        snapshot = PortSessionOriginalAudioOwner.CaptureSnapshot();
        if (AkSoundEngine.WakeupCalls != 3 ||
            UnityEngine.Debug.LastWarning != "Original audio bank-release wakeup failed: InvalidOperationException" ||
            beforeCalls != 5 || afterCalls != 5) return 15;
        invoke("OnDestroy");
        invoke("DetachOriginalBankReleaseWakeup");
        initialization.terminationDelegate();
        if (AkSoundEngine.WakeupCalls != 3 || beforeCalls != 6 || afterCalls != 6 ||
            PortSessionOriginalAudioOwner.CaptureSnapshot().bankReleaseWakeupAttached) return 16;
        GameAudioOriginalOwner.OriginalTermsReturned = true;
        invoke("AttachOriginalBankReleaseWakeup");
        if (AkSoundEngineInitialization.GetterReads != 1) return 17;
        Console.WriteLine("PASS: original termination wakeup admission, single subscription, native failures and owned delegate removal");
        Console.WriteLine("PASS: default-off/pre-ready do not read; ready opt-in reports managed count; zero is known; read failure is unknown");
        return 0;
    }
}
