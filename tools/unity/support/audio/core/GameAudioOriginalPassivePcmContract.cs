using System;
using System.Globalization;

// Cross-assembly contract: the Core owner can drive/report a bootstrap-owned
// diagnostic callback lease without referencing the bootstrap assembly.
public interface IGameAudioOriginalPassivePcmCapture
{
    bool RequestGameplayArm();
    bool RequestGameplayArm(GameAudioOriginalPassivePcmCaptureSelection selection);
    void FinishGameplayWindow();
    bool ArmRequested { get; }
    float WindowStartRealtimeSinceStartup { get; }
    ulong WindowStartServiceFrames { get; }
    void Tick(float realtimeSinceStartup, bool ownerReady, bool exactControlObserved, ulong successfulOriginalRenderFrames);
    void BeforeOriginalEngineTerm();
    void PersistWaveformAfterOriginalTerms();
    bool TerminalStopRequested { get; }
    string State { get; }
    string StopReason { get; }
    string Failure { get; }
    ulong CallbackCount { get; }
    ulong FrameCount { get; }
    ulong SampleCount { get; }
    ulong FiniteSamples { get; }
    ulong NonzeroFiniteSamples { get; }
    ulong NonfiniteSamples { get; }
    ulong RejectedBuffers { get; }
    ulong CappedBuffers { get; }
    string WaveformReadbackState { get; }
    string WaveformReadbackFailure { get; }
    bool WaveformRawPersisted { get; }
    ulong WaveformGeneration { get; }
    uint WaveformStoredSamples { get; }
    bool OutputIdentityObserved { get; }
    bool CaptureOutputDeviceIdObserved { get; }
    ulong CaptureOutputDeviceId { get; }
    bool CaptureSelectorObserved { get; }
    GameAudioOriginalPassivePcmCaptureSelection CaptureSelection { get; }
}

// Cross-assembly, immutable selector carried from the accepted per-run profile
// through native registration and the matching unregister. MainOutput is the
// default (the pinned SDK's invalid-output selector is numeric zero). A mode
// discriminator is required because zero must never mean both main and an
// exact-output request.
public enum GameAudioOriginalPassivePcmCaptureSelectorMode : int
{
    MainOutput = 0,
    SpecificOutput = 1
}

public struct GameAudioOriginalPassivePcmCaptureSelection
{
    public readonly GameAudioOriginalPassivePcmCaptureSelectorMode Mode;
    public readonly bool SelectionKnown;
    public readonly bool SpecificOutputIdKnown;
    public readonly ulong SpecificOutputId;

    private GameAudioOriginalPassivePcmCaptureSelection(
        GameAudioOriginalPassivePcmCaptureSelectorMode mode, bool selectionKnown, bool known, ulong outputId)
    {
        Mode = mode;
        SelectionKnown = selectionKnown;
        SpecificOutputIdKnown = known;
        SpecificOutputId = outputId;
    }

    public static GameAudioOriginalPassivePcmCaptureSelection MainOutput()
    {
        return new GameAudioOriginalPassivePcmCaptureSelection(
            GameAudioOriginalPassivePcmCaptureSelectorMode.MainOutput, true, false, 0UL);
    }

    public static bool TrySpecificOutput(bool currentOwnedMusicControllerMatches,
        bool outputAccepted, bool outputDeviceIdValid, ulong outputDeviceId,
        out GameAudioOriginalPassivePcmCaptureSelection selection)
    {
        selection = default(GameAudioOriginalPassivePcmCaptureSelection);
        // The SDK reserves zero for the default/main selector. Refuse the
        // maximum sentinel as well; neither value identifies a selectable
        // specific output. Never infer absence from an ID's numeric value.
        if (!currentOwnedMusicControllerMatches || !outputAccepted || !outputDeviceIdValid ||
            outputDeviceId == 0UL || outputDeviceId == ulong.MaxValue)
            return false;
        selection = new GameAudioOriginalPassivePcmCaptureSelection(
            GameAudioOriginalPassivePcmCaptureSelectorMode.SpecificOutput, true, true, outputDeviceId);
        return true;
    }

    public bool IsWellFormed
    {
        get
        {
            if (!SelectionKnown) return false;
            if (Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.MainOutput)
                return !SpecificOutputIdKnown && SpecificOutputId == 0UL;
            return Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.SpecificOutput &&
                SpecificOutputIdKnown && SpecificOutputId != 0UL && SpecificOutputId != ulong.MaxValue;
        }
    }

    public ulong NativeOutputSelector
    {
        get
        {
            if (!IsWellFormed) throw new InvalidOperationException("Capture output selector is malformed.");
            return Mode == GameAudioOriginalPassivePcmCaptureSelectorMode.MainOutput ? 0UL : SpecificOutputId;
        }
    }
}

// JSON number consumers implemented with IEEE-754 doubles cannot preserve all
// AkOutputDeviceID values. Keep the companion representation decimal and exact.
public static class GameAudioOriginalPassivePcmIdentity
{
    public static string ToDecimalString(ulong outputDeviceId)
    {
        return outputDeviceId.ToString(CultureInfo.InvariantCulture);
    }
}


// Pure admission predicate for the passive capture's gameplay-boundary request.
// The results-profile flag is deliberately absent: gameplay is established by the
// existing integrated-world phase and finite positive simulation time.
public static class GameAudioOriginalPassivePcmGameplayGate
{
    public static bool ShouldRequestArm(
        bool captureRequested, bool boundaryAttempted, bool integratedWorld, string phase, float worldSeconds)
    {
        return captureRequested && !boundaryAttempted && integratedWorld &&
            string.Equals(phase, "integrated-world-playing", StringComparison.Ordinal) &&
            !float.IsNaN(worldSeconds) && !float.IsInfinity(worldSeconds) && worldSeconds > 0f;
    }
}
