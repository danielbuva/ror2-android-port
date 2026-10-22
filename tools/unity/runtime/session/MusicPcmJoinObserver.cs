using System;

// Authored, bounded helper for joining the already-selected original music
// playing ID to snapshots of the existing passive PCM capture. It neither
// posts events nor changes any Wwise state.
internal interface IMusicPcmJoinQuery
{
    float RealtimeSinceStartup { get; }
    ulong CallbackCount { get; }
    ulong FrameCount { get; }
    uint GetEventId(uint playingId);
    int GetSegmentInfo(uint playingId, out int currentPosition, out int activeDuration, out int remainingLookAhead);
    int GetState(uint groupId, out uint stateId);
}

[Serializable]
public sealed class MusicPcmJoinRow
{
    public int sequence;
    public float realtimeBefore, realtimeAfter;
    public bool realtimeBeforeObserved, realtimeAfterObserved;
    public ulong callbacksBefore, callbacksAfter, framesBefore, framesAfter;
    public bool callbacksBeforeObserved, callbacksAfterObserved, framesBeforeObserved, framesAfterObserved;
    public bool playingIdObserved, eventQueryAttempted, eventIdReturned;
    public bool realtimeClockFailure;
    public string realtimeClockFailureReason;
    public uint playingId, eventId;
    public string eventQueryFailure;
    public bool segmentQueryAttempted, segmentResultObserved, segmentValuesObserved;
    public int segmentResult, segmentPositionRaw, segmentActiveDurationRaw, segmentRemainingLookAheadRaw;
    public string segmentQueryFailure;
    public bool musicStateQueryAttempted, musicStateResultObserved, musicStateValueObserved;
    public int musicStateResult;
    public uint musicStateId;
    public string musicStateQueryFailure;
    public bool gameplayStateQueryAttempted, gameplayStateResultObserved, gameplayStateValueObserved;
    public int gameplayStateResult;
    public uint gameplayStateId;
    public string gameplayStateQueryFailure;
}

internal sealed class MusicPcmJoinObserver
{
    internal const float IntervalSeconds = 0.5f;
    internal const int MaximumRows = 24;
    internal const uint MusicSystemGroup = 792781730;
    internal const uint GameplaySongChoiceGroup = 1741660947;

    private readonly MusicPcmJoinRow[] rows = new MusicPcmJoinRow[MaximumRows];
    private float nextSampleAt;
    private float lastObservedRealtime;
    private bool lastObservedRealtimeValid;
    private bool clockFailureObserved;
    private string clockFailure;
    private int count;
    private bool windowStartObserved, windowEndObserved;
    private float windowStartRealtime, windowEndRealtime;
    private ulong windowStartCallbacks, windowStartFrames, windowEndCallbacks, windowEndFrames;

    internal static bool IsExactWindowEligible(bool captureActive, bool engineInitialized, bool musicOutputRequested,
        bool selectorObserved, bool specificOutputSelected, ulong selectedOutputId,
        bool captureOutputIdentityObserved, ulong captureOutputId,
        bool ownedOutputIdentityValid, ulong ownedOutputId,
        bool ownedControllerMatches, bool cleanupStarted)
    {
        return captureActive && engineInitialized && musicOutputRequested && selectorObserved && specificOutputSelected &&
            captureOutputIdentityObserved && ownedOutputIdentityValid && captureOutputId != 0UL &&
            captureOutputId == selectedOutputId && selectedOutputId == ownedOutputId &&
            ownedControllerMatches && !cleanupStarted;
    }

    internal int Count { get { return count; } }
    internal bool ClockFailureObserved { get { return clockFailureObserved; } }
    internal string ClockFailure { get { return clockFailure; } }
    internal bool WindowStartObserved { get { return windowStartObserved; } }
    internal bool WindowEndObserved { get { return windowEndObserved; } }
    internal float WindowStartRealtime { get { return windowStartRealtime; } }
    internal float WindowEndRealtime { get { return windowEndRealtime; } }
    internal ulong WindowStartCallbacks { get { return windowStartCallbacks; } }
    internal ulong WindowStartFrames { get { return windowStartFrames; } }
    internal ulong WindowEndCallbacks { get { return windowEndCallbacks; } }
    internal ulong WindowEndFrames { get { return windowEndFrames; } }

    internal void ObserveWindowStart(IMusicPcmJoinQuery query)
    {
        if (query == null || windowStartObserved) return;
        try
        {
            float realtime = query.RealtimeSinceStartup;
            if (!IsFinite(realtime)) { MarkClockFailure("window_start_non_finite"); return; }
            windowStartCallbacks = query.CallbackCount;
            windowStartFrames = query.FrameCount;
            windowStartRealtime = realtime;
            lastObservedRealtime = realtime;
            lastObservedRealtimeValid = true;
            windowStartObserved = true;
        }
        catch (Exception error) { MarkClockFailure("window_start:" + error.GetType().Name); }
    }

    internal void ObserveWindowEnd(IMusicPcmJoinQuery query)
    {
        if (query == null || !windowStartObserved || windowEndObserved) return;
        try
        {
            float realtime = query.RealtimeSinceStartup;
            if (!IsFinite(realtime) || realtime < windowStartRealtime ||
                (lastObservedRealtimeValid && realtime < lastObservedRealtime))
            { MarkClockFailure("window_end_non_finite_or_backwards"); return; }
            windowEndCallbacks = query.CallbackCount;
            windowEndFrames = query.FrameCount;
            windowEndRealtime = realtime;
            lastObservedRealtime = realtime;
            lastObservedRealtimeValid = true;
            windowEndObserved = true;
        }
        catch (Exception error) { MarkClockFailure("window_end:" + error.GetType().Name); }
    }
    internal MusicPcmJoinRow[] Rows
    {
        get
        {
            var copy = new MusicPcmJoinRow[count];
            Array.Copy(rows, copy, count);
            return copy;
        }
    }

    // The caller must establish that capture is in its exact "capturing" state,
    // that this is the selected music output, and that the native owner still
    // matches. Those facts are checked again here as explicit gates. A query
    // exception is represented as an unavailable result, never success.
    internal bool TrySample(bool exactWindowEligible, bool playingIdObserved, uint playingId,
        IMusicPcmJoinQuery query)
    {
        if (!exactWindowEligible || query == null || count >= MaximumRows)
            return false;
        float before;
        try { before = query.RealtimeSinceStartup; }
        catch (Exception error) { MarkClockFailure("sample_start:" + error.GetType().Name); return false; }
        if (!IsFinite(before) || (lastObservedRealtimeValid && before < lastObservedRealtime))
        { MarkClockFailure("sample_start_non_finite_or_backwards"); return false; }
        if (windowStartObserved && before < windowStartRealtime)
        { MarkClockFailure("sample_before_window_start"); return false; }
        if (before < nextSampleAt) return false;
        nextSampleAt = before + IntervalSeconds;
        if (!IsFinite(nextSampleAt) || nextSampleAt <= before || nextSampleAt - before < IntervalSeconds)
        { MarkClockFailure("cadence_deadline_not_representable"); return false; }

        var row = new MusicPcmJoinRow {
            sequence = count,
            realtimeBefore = before,
            realtimeBeforeObserved = true,
            callbacksBeforeObserved = TryCallbacks(query, out ulong callbacksBefore),
            callbacksBefore = callbacksBefore,
            framesBeforeObserved = TryFrames(query, out ulong framesBefore),
            framesBefore = framesBefore,
            playingIdObserved = playingIdObserved,
            playingId = playingIdObserved ? playingId : 0
        };
        if (playingIdObserved && playingId != 0)
        {
            row.eventQueryAttempted = true;
            try { row.eventId = query.GetEventId(playingId); row.eventIdReturned = true; }
            catch (Exception error) { row.eventQueryFailure = error.GetType().Name; }
            row.segmentQueryAttempted = true;
            try
            {
                row.segmentResult = query.GetSegmentInfo(playingId, out row.segmentPositionRaw,
                    out row.segmentActiveDurationRaw, out row.segmentRemainingLookAheadRaw);
                row.segmentResultObserved = true;
                row.segmentValuesObserved = row.segmentResult == 1;
            }
            catch (Exception error) { row.segmentQueryFailure = error.GetType().Name; }
        }
        row.musicStateQueryAttempted = true;
        try
        {
            row.musicStateResult = query.GetState(MusicSystemGroup, out row.musicStateId);
            row.musicStateResultObserved = true;
            row.musicStateValueObserved = row.musicStateResult == 1;
        }
        catch (Exception error) { row.musicStateQueryFailure = error.GetType().Name; }
        row.gameplayStateQueryAttempted = true;
        try
        {
            row.gameplayStateResult = query.GetState(GameplaySongChoiceGroup, out row.gameplayStateId);
            row.gameplayStateResultObserved = true;
            row.gameplayStateValueObserved = row.gameplayStateResult == 1;
        }
        catch (Exception error) { row.gameplayStateQueryFailure = error.GetType().Name; }
        row.callbacksAfterObserved = TryCallbacks(query, out row.callbacksAfter);
        row.framesAfterObserved = TryFrames(query, out row.framesAfter);
        try
        {
            float after = query.RealtimeSinceStartup;
            if (IsFinite(after) && after >= before)
            {
                row.realtimeAfter = after;
                row.realtimeAfterObserved = true;
                lastObservedRealtime = after;
                lastObservedRealtimeValid = true;
            }
            else
            {
                row.realtimeClockFailure = true;
                row.realtimeClockFailureReason = "sample_end_non_finite_or_backwards";
                MarkClockFailure(row.realtimeClockFailureReason);
            }
        }
        catch (Exception error)
        {
            row.realtimeClockFailure = true;
            row.realtimeClockFailureReason = "sample_end:" + error.GetType().Name;
            MarkClockFailure(row.realtimeClockFailureReason);
        }
        rows[count++] = row;
        return true;
    }

    private static bool IsFinite(float value) { return !Single.IsNaN(value) && !Single.IsInfinity(value); }
    private void MarkClockFailure(string reason)
    {
        clockFailureObserved = true;
        if (clockFailure == null) clockFailure = reason;
    }

    private static bool TryCallbacks(IMusicPcmJoinQuery query, out ulong value)
    { try { value = query.CallbackCount; return true; } catch { value = 0; return false; } }
    private static bool TryFrames(IMusicPcmJoinQuery query, out ulong value)
    { try { value = query.FrameCount; return true; } catch { value = 0; return false; } }
}
