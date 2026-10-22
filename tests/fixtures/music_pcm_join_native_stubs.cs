using System;
using UnityEngine;
public enum GameAudioOriginalPassivePcmCaptureSelectorMode { MainOutput = 0, SpecificOutput = 1 }
public struct GameAudioOriginalPassivePcmCaptureSelection
{
    public GameAudioOriginalPassivePcmCaptureSelectorMode Mode;
    public bool SpecificOutputIdKnown;
    public ulong SpecificOutputId;
}
public enum AKRESULT { AK_Fail = 0, AK_Success = 1 }
public sealed class AkSegmentInfo : IDisposable
{
    public int iCurrentPosition, iActiveDuration, iRemainingLookAheadTime;
    public void Dispose() { }
}
public static class AkSoundEngine
{
    public static bool Fail;
    public static uint GetEventIDFromPlayingID(uint id) { if (Fail) throw new InvalidOperationException(); return 3260968109; }
    public static AKRESULT GetPlayingSegmentInfo(uint id, AkSegmentInfo info)
    { if (Fail) throw new InvalidOperationException(); info.iCurrentPosition = 100; info.iActiveDuration = 200; info.iRemainingLookAheadTime = 3; return AKRESULT.AK_Success; }
    public static AKRESULT GetState(uint group, out uint state)
    { state = group == MusicPcmJoinObserver.MusicSystemGroup ? 89505537u : 1859829901u; return Fail ? AKRESULT.AK_Fail : AKRESULT.AK_Success; }
}
public static class GameAudioOriginalOwner
{
    public static IGameAudioOriginalPassivePcmCapture PassiveCapture;
}
public interface IGameAudioOriginalPassivePcmCapture
{
    ulong CallbackCount { get; }
    ulong FrameCount { get; }
    string State { get; }
    bool CaptureSelectorObserved { get; }
    GameAudioOriginalPassivePcmCaptureSelection CaptureSelection { get; }
    bool CaptureOutputDeviceIdObserved { get; }
    ulong CaptureOutputDeviceId { get; }
}
namespace UnityEngine { public static class Time { public static float realtimeSinceStartup; } }
