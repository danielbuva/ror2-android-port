using System;

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
}
