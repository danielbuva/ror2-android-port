using System;

internal sealed class FakeQuery : IMusicPcmJoinQuery
{
    public float RealtimeSinceStartup { get; set; }
    public ulong CallbackCount { get; set; }
    public ulong FrameCount { get; set; }
    public bool ThrowQueries;
    public uint GetEventId(uint playingId) { if (ThrowQueries) throw new InvalidOperationException(); return 3260968109; }
    public int GetSegmentInfo(uint playingId, out int position, out int duration, out int lookAhead)
    { if (ThrowQueries) throw new InvalidOperationException(); position = 101; duration = 202; lookAhead = 3; return 1; }
    public int GetState(uint groupId, out uint stateId)
    { if (ThrowQueries) throw new InvalidOperationException(); stateId = groupId == MusicPcmJoinObserver.MusicSystemGroup ? 89505537u : 1859829901u; return 1; }
}

internal static class MusicPcmJoinObserverHarness
{
    private static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    public static int Main()
    {
        var observer = new MusicPcmJoinObserver();
        var q = new FakeQuery { RealtimeSinceStartup = 10f, CallbackCount = 5, FrameCount = 20 };
        Require(!MusicPcmJoinObserver.IsExactWindowEligible(false, true, true, true, true, 4, true, 4, true, 4, true, false), "inactive capture refused");
        Require(!MusicPcmJoinObserver.IsExactWindowEligible(true, true, false, true, true, 4, true, 4, true, 4, true, false), "non-music capture refused");
        Require(!MusicPcmJoinObserver.IsExactWindowEligible(true, true, true, true, true, 4, true, 4, true, 5, true, false), "wrong output refused");
        Require(!MusicPcmJoinObserver.IsExactWindowEligible(true, true, true, true, true, 4, true, 4, true, 4, false, false), "owner mismatch refused");
        bool eligible = MusicPcmJoinObserver.IsExactWindowEligible(true, true, true, true, true, 4, true, 4, true, 4, true, false);
        Require(observer.TrySample(eligible, true, 7, q), "sample admitted");
        Require(!observer.TrySample(eligible, true, 7, q), "0.5s cadence enforced");
        q.RealtimeSinceStartup = 10.5f; q.CallbackCount = 6; q.FrameCount = 24; q.ThrowQueries = true;
        Require(observer.TrySample(eligible, true, 7, q), "query failure retained as row");
        var rows = observer.Rows;
        Require(rows.Length == 2 && rows[0].eventIdReturned && rows[0].segmentResultObserved, "native values retained");
        Require(rows[1].eventQueryAttempted && !rows[1].eventIdReturned && rows[1].eventQueryFailure == "InvalidOperationException" && !rows[1].segmentResultObserved, "failed native queries unknown");
        foreach (var field in typeof(MusicPcmJoinRow).GetFields())
            Require(field.FieldType.IsValueType || field.FieldType == typeof(string), "row contains scalar only: " + field.Name);
        Require(rows[0].callbacksBefore == 5 && rows[0].callbacksAfter == 5 && rows[0].framesBefore == 20, "counter brackets recorded");
        Require(!observer.TrySample(eligible, true, 7, null), "missing query refused");
        for (int i = 2; i < MusicPcmJoinObserver.MaximumRows; i++)
        { q.ThrowQueries = false; q.RealtimeSinceStartup = 10.5f + (i - 1) * .5f; Require(observer.TrySample(eligible, false, 0, q), "bounded row admitted"); }
        q.RealtimeSinceStartup = 30f;
        Require(!observer.TrySample(eligible, true, 7, q) && observer.Count == 24, "row cap enforced");
        Require(!observer.TrySample(eligible, true, 7, q), "no work after cap");
        var malformedClock = new MusicPcmJoinObserver();
        q.ThrowQueries = false;
        q.RealtimeSinceStartup = float.NaN;
        Require(!malformedClock.TrySample(eligible, true, 7, q) && malformedClock.Count == 0 && malformedClock.ClockFailureObserved,
            "NaN cannot bypass cadence or consume a row");
        q.RealtimeSinceStartup = float.PositiveInfinity;
        var infiniteClock = new MusicPcmJoinObserver();
        Require(!infiniteClock.TrySample(eligible, true, 7, q) && infiniteClock.Count == 0 && infiniteClock.ClockFailureObserved,
            "infinite time refused");
        var backwardClock = new MusicPcmJoinObserver();
        q.RealtimeSinceStartup = 8f;
        backwardClock.ObserveWindowStart(q);
        q.RealtimeSinceStartup = 7f;
        Require(!backwardClock.TrySample(eligible, true, 7, q) && backwardClock.Count == 0 && backwardClock.ClockFailureObserved,
            "pre-window/backward time refused");
        var repeatedClock = new MusicPcmJoinObserver();
        q.RealtimeSinceStartup = 8f;
        repeatedClock.ObserveWindowStart(q);
        Require(repeatedClock.TrySample(eligible, true, 7, q), "first finite timestamp admitted");
        q.RealtimeSinceStartup = 7f;
        Require(!repeatedClock.TrySample(eligible, true, 7, q) && repeatedClock.Count == 1 && repeatedClock.ClockFailureObserved,
            "backwards timestamp after a valid row refused");
        var unrepresentableCadence = new MusicPcmJoinObserver();
        q.RealtimeSinceStartup = 16777216f;
        Require(!unrepresentableCadence.TrySample(eligible, true, 7, q) && unrepresentableCadence.Count == 0 &&
            unrepresentableCadence.ClockFailureObserved, "cadence that cannot represent half a second refused");
        var endClock = new MusicPcmJoinObserver();
        q.RealtimeSinceStartup = 8f;
        endClock.ObserveWindowStart(q);
        q.RealtimeSinceStartup = float.NegativeInfinity;
        endClock.ObserveWindowEnd(q);
        Require(!endClock.WindowEndObserved && endClock.ClockFailureObserved, "non-finite end bracket remains unknown");
        UnityEngine.Time.realtimeSinceStartup = 40f;
        var adapter = new AkMusicPcmJoinQueryAdapter();
        Require(adapter.GetEventId(7) == 3260968109, "accepted API event-ID wrapper");
        int position, duration, lookAhead;
        Require(adapter.GetSegmentInfo(7, out position, out duration, out lookAhead) == 1 && position == 100 && duration == 200, "segment wrapper and raw outputs");
        AkSoundEngine.Fail = true;
        Require(adapter.GetState(MusicPcmJoinObserver.MusicSystemGroup, out var state) == 0, "native failure result retained");
        Console.WriteLine("PASS bounded cadence, exact capture/output gates, scalar brackets, clock refusals, unknown query failures and 24-row cap");
        return 0;
    }
}
