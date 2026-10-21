using System;
using System.Globalization;

// Cross-assembly contract: the Core owner can drive/report a bootstrap-owned
// diagnostic callback lease without referencing the bootstrap assembly.
public interface IGameAudioOriginalPassivePcmCapture
{
    bool RequestGameplayArm();
    void FinishGameplayWindow();
    bool ArmRequested { get; }
    float WindowStartRealtimeSinceStartup { get; }
    ulong WindowStartServiceFrames { get; }
    void Tick(float realtimeSinceStartup, bool ownerReady, bool exactControlObserved, ulong successfulOriginalRenderFrames);
    void BeforeOriginalEngineTerm();
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
    bool OutputIdentityObserved { get; }
    bool CaptureOutputDeviceIdObserved { get; }
    ulong CaptureOutputDeviceId { get; }
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
