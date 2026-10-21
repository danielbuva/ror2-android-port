using System;
using System.Collections.Generic;

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

        Console.WriteLine("PASS: default-off/pre-ready do not read; ready opt-in reports managed count; zero is known; read failure is unknown");
        return 0;
    }
}
