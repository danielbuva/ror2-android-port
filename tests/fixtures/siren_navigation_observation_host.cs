public static class HostContract
{
    sealed class FakeReader : ISirenNavigationObservationReader
    {
        public bool Available { get; set; } = true;
        public int Calls;
        public bool TryRead(UnityEngine.Vector2 movement, int writtenTick, int observedTick, float now,
                            out SirenNavigationObservationSample sample)
        {
            Calls++;
            sample = new SirenNavigationObservationSample {
                requestedBridgeMovement = movement,
                requestWrittenAfterFixedTick = writtenTick,
                observedAfterFixedTick = observedTick,
                realtimeSeconds = now
            };
            return true;
        }
    }

    static void Require(bool value, string message)
    {
        if (!value)
            throw new System.Exception(message);
    }

    static SirenNavigationObservationRecorder Start(float rangeStart, float triggerAt)
    {
        var recorder = new SirenNavigationObservationRecorder();
        recorder.ObserveTrigger(true, true, 398, 167, 60, 6.01f, rangeStart);
        Require(recorder.ObserveTrigger(true, true, 398, 167, 60, 6.01f, triggerAt), "valid trigger did not start");
        return recorder;
    }

    public static int Main()
    {
        Require(SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", 10, .2f, true),
                "real path request was not available");
        Require(!SirenNavigationObservationPolicy.PathRequestAvailable(false, 1, "graph-changed", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 0, "graph-changed", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", float.NaN, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", 10, .2f, false),
                "absent or malformed path request was marked available");

        var continuity = new SirenNavigationObservationRecorder();
        continuity.ObserveTrigger(true, true, 398, 167, 60, 7, 1);
        continuity.ResetTriggerContinuity();
        Require(!continuity.ObserveTrigger(true, true, 398, 167, 60, 7, 1.5f),
                "same egg armed across an unobserved frame gap");
        Require(continuity.ObserveTrigger(true, true, 398, 167, 60, 7, 2.01f),
                "same egg did not arm after a fresh continuous interval");
        var disabledTracker = new SirenNavigationObservationRecorder();
        disabledTracker.ObserveTrigger(true, true, 398, 167, 60, 7, 5);
        disabledTracker.ObserveTrigger(true, false, 398, 167, 60, 7, 5.2f);
        Require(!disabledTracker.ObserveTrigger(true, true, 398, 167, 60, 7, 5.6f),
                "disabled tracker interval remained continuous");
        Require(disabledTracker.ObserveTrigger(true, true, 398, 167, 60, 7, 6.11f),
                "active tracker did not establish a new continuous interval");

        var clock = new SirenNavigationObservationRecorder();
        clock.ObserveTrigger(true, true, 398, 167, 60, 5, 100);
        clock.ObserveTrigger(true, true, 398, 167, 60, 5, 102);
        Require(!clock.ObserveTrigger(true, true, 398, 167, 60, 5, 101), "pre-trigger rollback armed");
        Require(!clock.ObserveTrigger(true, true, 398, 167, 60, 5, 102), "rollback did not restart continuity");
        Require(clock.ObserveTrigger(true, true, 398, 167, 60, 7, 102.6f), "restarted continuity did not arm");
        clock.QueueRequest(new UnityEngine.Vector2(1, 0), 8);
        clock.Maintain(103, true);
        clock.Maintain(102.9f, true);
        Require(clock.report.completed && clock.report.stopReason == "invalid-clock", "post-trigger rollback above start was missed");

        var stale = Start(10, 10.5f);
        stale.QueueRequest(new UnityEngine.Vector2(1, 0), 10);
        var unavailable = new FakeReader { Available = false };
        Require(!stale.ObservePending(398, 10.6f, true, 11, unavailable), "unavailable reader sampled");
        Require(stale.report.completed && stale.report.stopReason == "observation-dependency-unavailable" && unavailable.Calls == 0,
                "stale request was not terminally cleared on unavailable dependencies");
        var recovered = new FakeReader();
        Require(!stale.ObservePending(398, 10.7f, true, 12, recovered) && recovered.Calls == 0,
                "old request was reused after recovery");

        var identityHandoff = Start(15, 15.5f);
        identityHandoff.QueueRequest(new UnityEngine.Vector2(1, 0), 20);
        var identityReader = new FakeReader();
        Require(!identityHandoff.ObservePending(404, 15.6f, true, 21, identityReader) &&
                identityHandoff.report.completed && identityHandoff.report.stopReason == "selected-egg-changed" &&
                identityReader.Calls == 0,
                "same-frame egg identity handoff consumed the previous request");
        var bridgeHandoff = Start(17, 17.5f);
        bridgeHandoff.QueueRequest(new UnityEngine.Vector2(1, 0), 30);
        bridgeHandoff.OnBridgeIdentityChanged();
        var newBridgeReader = new FakeReader();
        Require(!bridgeHandoff.ObservePending(398, 17.6f, true, 1, newBridgeReader) && newBridgeReader.Calls == 0 &&
                bridgeHandoff.report.completed && bridgeHandoff.report.stopReason == "bridge-instance-changed",
                "new bridge fixed-tick sequence consumed the old bridge request");

        var paired = Start(20, 20.5f);
        paired.QueueRequest(new UnityEngine.Vector2(.25f, -.75f), 40);
        var fake = new FakeReader();
        Require(!paired.ObservePending(398, 20.6f, true, 40, fake) && fake.Calls == 0,
                "same fixed tick was sampled");
        Require(paired.ObservePending(398, 20.7f, true, 41, fake), "later fixed tick was not sampled");
        Require(paired.report.samples[0].requestWrittenAfterFixedTick == 40 && paired.report.samples[0].observedAfterFixedTick == 41 &&
                paired.report.samples[0].requestedBridgeMovement.x == .25f && paired.report.samples[0].requestedBridgeMovement.y == -.75f,
                "sample did not preserve exact request/tick pair");

        var cap = Start(30, 30.5f);
        var capReader = new FakeReader();
        for (int i = 0; i < 8; i++) {
            cap.QueueRequest(new UnityEngine.Vector2(i, 0), i * 2);
            Require(cap.ObservePending(398, 30.5f + i, true, i * 2 + 1, capReader), "bounded sample rejected");
        }
        Require(cap.report.sampleCount == 8 && cap.report.completed && cap.report.stopReason == "sample-cap" && capReader.Calls == 8,
                "eight-sample cap failed");
        Require(!cap.ObserveTrigger(true, true, 398, 167, 60, 8, 40), "completed trace rearmed");

        var deadline = Start(50, 50.5f);
        deadline.Maintain(58.5f, true);
        Require(deadline.report.completed && deadline.report.stopReason == "window-expired", "deadline depended on a pending request");
        var inactive = Start(60, 60.5f);
        inactive.QueueRequest(new UnityEngine.Vector2(1, 0), 1);
        Require(!inactive.ObservePending(398, 60.6f, false, 2, new FakeReader()) && inactive.report.completed &&
                inactive.report.stopReason == "owner-inactive", "owner stop did not close recorder");
        foreach (string ownerLoss in new[] { "manual-takeover", "foreign-bridge-or-bank", "source-owner-lost" }) {
            var yielded = Start(65, 65.5f);
            yielded.QueueRequest(new UnityEngine.Vector2(1, 0), 3);
            var ownerReader = new FakeReader();
            Require(!yielded.ObservePending(398, 65.6f, false, 4, ownerReader) && ownerReader.Calls == 0 &&
                    yielded.report.completed, ownerLoss + " captured without owned diagnostic input");
        }
        var yieldPath = Start(68, 68.5f);
        yieldPath.QueueRequest(new UnityEngine.Vector2(1, 0), 3);
        yieldPath.Complete("manual-input-takeover");
        Require(yieldPath.report.completed && yieldPath.report.stopReason == "manual-input-takeover",
                "yield after pending request did not close the trace");
        var disposed = Start(70, 70.5f);
        disposed.QueueRequest(new UnityEngine.Vector2(1, 0), 1);
        disposed.Dispose();
        Require(disposed.report.completed && disposed.report.stopReason == "owner-disposed", "dispose did not close recorder");

        Console.WriteLine("siren-navigation-recorder-state-contract-passed");
        return 0;
    }
}
