using UnityEngine;

// Adapter only: every call goes through accepted 1ced managed Wwise APIs and
// reads the same capture owner's scalar counters. It does not touch PCM bytes.
internal sealed class AkMusicPcmJoinQueryAdapter : IMusicPcmJoinQuery
{
    public float RealtimeSinceStartup { get { return Time.realtimeSinceStartup; } }
    public ulong CallbackCount { get { var pcm = GameAudioOriginalOwner.PassiveCapture; return pcm == null ? 0UL : pcm.CallbackCount; } }
    public ulong FrameCount { get { var pcm = GameAudioOriginalOwner.PassiveCapture; return pcm == null ? 0UL : pcm.FrameCount; } }
    public uint GetEventId(uint playingId) { return AkSoundEngine.GetEventIDFromPlayingID(playingId); }
    public int GetSegmentInfo(uint playingId, out int currentPosition, out int activeDuration, out int remainingLookAhead)
    {
        currentPosition = activeDuration = remainingLookAhead = 0;
        using (var segment = new AkSegmentInfo())
        {
            AKRESULT result = AkSoundEngine.GetPlayingSegmentInfo(playingId, segment);
            if (result == AKRESULT.AK_Success)
            {
                currentPosition = segment.iCurrentPosition;
                activeDuration = segment.iActiveDuration;
                remainingLookAhead = segment.iRemainingLookAheadTime;
            }
            return (int)result;
        }
    }
    public int GetState(uint groupId, out uint stateId)
    {
        AKRESULT result = AkSoundEngine.GetState(groupId, out stateId);
        return (int)result;
    }
}
