using System;
using System.Collections.Generic;

// Generated per-run selection source. The checked-in candidate deliberately
// has no accepted request and therefore stays silent unless a separately
// generated request provider is configured by the reachable PortSession owner
// before the original Wwise manager startup call.
public sealed class GameAudioOriginalRequest
{
    public readonly bool Requested;
    public readonly IEnumerable<string> SourceBankNames;
    public readonly IGameAudioOriginalStartupPreparation Preparation;
    public readonly bool PassivePcmCaptureRequested;
    public readonly IGameAudioOriginalPassivePcmCapture PassivePcmCapture;

    public GameAudioOriginalRequest(bool requested, IEnumerable<string> sourceBankNames,
        IGameAudioOriginalStartupPreparation preparation, bool passivePcmCaptureRequested = false,
        IGameAudioOriginalPassivePcmCapture passivePcmCapture = null)
    {
        if (passivePcmCaptureRequested && (!requested || passivePcmCapture == null))
            throw new ArgumentException("Passive PCM opt-in requires an accepted original-audio request and its bootstrap-owned capture owner.");
        if (!passivePcmCaptureRequested && passivePcmCapture != null)
            throw new ArgumentException("A passive PCM owner cannot be attached when the explicit diagnostic selection is false.");
        Requested = requested;
        SourceBankNames = sourceBankNames;
        Preparation = preparation;
        PassivePcmCaptureRequested = passivePcmCaptureRequested;
        PassivePcmCapture = passivePcmCapture;
    }
}

public static class GameAudioOriginalRequestBootstrap
{
    // Build-generated integration may install a provider only when its request
    // binds the accepted input, staged-bank receipt, adapted Init, and native
    // monitor pins. Null is the intended default-off state.
    // The production request provider is intentionally compiled default-off.
    // A generated request pin can opt in only for this exact accepted build.
    public static Func<GameAudioOriginalRequest> RequestProvider = GameAudioOriginalAcceptedRequestProvider.Create;
    public static bool PassivePcmCaptureRequested { get; private set; }
    // Supplied by the reachable Assembly-CSharp owner. It resolves the original
    // serialized settings asset from the already-owned whole-game content bundle;
    // Bootstrap never creates a Resources duplicate or references RoR2.
    public static Func<AkWwiseInitializationSettings> OriginalSettingsProvider;
    private static bool configured;

    public static bool IsConfigured { get { return configured; } }

    public static void ConfigureBeforeOriginalStartup()
    {
        if (configured) return;
        configured = true;
        GameAudioOriginalRequest request = null;
        try { request = RequestProvider?.Invoke(); }
        catch (Exception error)
        {
            request = new GameAudioOriginalRequest(true, null,
                GameAudioOriginalAcceptedRequestProvider.Refused("request_provider_threw:" + error.GetType().Name));
        }
        if (request == null)
        {
            PassivePcmCaptureRequested = false;
            GameAudioOriginalOwner.Configure(false, null, null);
            return;
        }
        PassivePcmCaptureRequested = request.PassivePcmCaptureRequested;
        if (request.PassivePcmCaptureRequested && (!request.Requested || request.PassivePcmCapture == null))
            throw new InvalidOperationException("Passive PCM opt-in is missing an accepted owner-bound capture instance.");
        GameAudioOriginalOwner.Configure(request.Requested, request.SourceBankNames, request.Preparation, request.PassivePcmCapture, request.PassivePcmCaptureRequested);
    }

#if GAME_AUDIO_HOST_TEST
    internal static void ResetForHostTest()
    {
        configured = false;
        PassivePcmCaptureRequested = false;
        RequestProvider = GameAudioOriginalAcceptedRequestProvider.Create;
    }
#endif
}
