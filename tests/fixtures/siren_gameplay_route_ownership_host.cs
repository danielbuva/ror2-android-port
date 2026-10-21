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
        recorder.ObserveTrigger(true, true, 398, 167, 60, 0f, rangeStart);
        Require(recorder.ObserveTrigger(true, true, 398, 167, 60, 0f, triggerAt), "valid trigger did not start");
        return recorder;
    }

    public static int Main()
    {
        var progressing = new SirenNavigationObservationRecorder();
        Require(!progressing.ObserveTrigger(true, true, 700, 168.5f, 60f, 0f, 1f),
                "first far sample should establish continuity only");
        Require(progressing.ObserveTrigger(true, true, 700, 168.0f, 60f, 0f, 1.51f),
                "out-of-range approach with zero stall must arm after continuity");
        Require(progressing.report.triggerObjectiveStallAvailable && progressing.report.triggerObjectiveStalledSeconds == 0f,
                "trigger-time zero stall was not preserved");

        var unknownStall = new SirenNavigationObservationRecorder();
        unknownStall.ObserveTrigger(true, true, 701, 100f, 60f, float.NaN, 5f);
        Require(unknownStall.ObserveTrigger(true, true, 701, 100f, 60f, float.NaN, 5.51f),
                "unknown stall must not block the range observer");
        Require(!unknownStall.report.triggerObjectiveStallAvailable,
                "unknown trigger stall was fabricated as available");

        var eggChange = new SirenNavigationObservationRecorder();
        eggChange.ObserveTrigger(true, true, 702, 100f, 60f, 0f, 10f);
        Require(!eggChange.ObserveTrigger(true, true, 703, 100f, 60f, 0f, 10.6f),
                "egg identity change must restart continuity");
        Require(eggChange.ObserveTrigger(true, true, 703, 100f, 60f, 0f, 11.11f),
                "new egg failed after a fresh continuity interval");

        var lostTracker = new SirenNavigationObservationRecorder();
        lostTracker.ObserveTrigger(true, true, 704, 100f, 60f, 0f, 20f);
        Require(!lostTracker.ObserveTrigger(true, false, 704, 100f, 60f, 0f, 20.6f),
                "missing tracker did not reset continuity");
        Require(!lostTracker.ObserveTrigger(true, true, 704, 100f, 60f, 0f, 21.01f),
                "tracker recovery reused old continuity");
        Require(lostTracker.ObserveTrigger(true, true, 704, 100f, 60f, 0f, 21.52f),
                "tracker recovery failed after a fresh interval");

        var invalidTime = new SirenNavigationObservationRecorder();
        Require(!invalidTime.ObserveTrigger(true, true, 705, 100f, 60f, 0f, float.NaN),
                "unknown time armed the observer");
        Require(!invalidTime.ObserveTrigger(true, true, 705, 100f, 60f, 0f, 30f),
                "unknown time left stale continuity armed");

        var lostEgg = new SirenNavigationObservationRecorder();
        lostEgg.ObserveTrigger(true, true, 706, 100f, 60f, 0f, 40f);
        Require(!lostEgg.ObserveTrigger(false, true, 706, 100f, 60f, 0f, 40.6f),
                "unselected/destroyed source egg retained continuity");
        Require(!lostEgg.ObserveTrigger(true, true, 0, 100f, 60f, 0f, 41f),
                "zero source egg identity armed the observer");
        Require(!lostEgg.ObserveTrigger(true, true, 706, 100f, 60f, 0f, 41.51f),
                "revalidated egg armed before its own continuity interval");
        Require(lostEgg.ObserveTrigger(true, true, 706, 100f, 60f, 0f, 42.02f),
                "revalidated egg failed after fresh continuity");

        var legacyStall = new SirenNavigationObservationRecorder();
        legacyStall.ObserveTrigger(true, true, 707, 100f, 60f, 7f, 50f);
        Require(legacyStall.ObserveTrigger(true, true, 707, 100f, 60f, 7f, 50.51f),
                "existing stalled-route case no longer starts");

        Require(SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", 10, .2f, true),
                "real path request was not available");
        Require(!SirenNavigationObservationPolicy.PathRequestAvailable(false, 1, "graph-changed", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 0, "graph-changed", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "", 10, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", float.NaN, .2f, true) &&
                !SirenNavigationObservationPolicy.PathRequestAvailable(true, 1, "graph-changed", 10, .2f, false),
                "absent or malformed path request was marked available");
        Require(!SirenNavigationObservationPolicy.PathRequestAvailable(true, 5, "destination-moved", 12f, -168f, true) &&
                SirenNavigationObservationPolicy.PathRequestAvailable(true, 5, "destination-moved", 12f, .4f, true),
                "run-relative request timestamp was confused with the stage-relative Siren clock");

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
        clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100);
        clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100.2f);
        Require(!clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100.1f), "pre-trigger rollback armed");
        Require(!clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100.2f), "rollback did not restart continuity");
        Require(!clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100.6f), "restarted continuity armed before 0.5 seconds");
        Require(clock.ObserveTrigger(true, true, 398, 167, 60, 0, 100.71f), "restarted continuity did not arm");
        clock.QueueRequest(new UnityEngine.Vector2(1, 0), 8, 0f);
        clock.Maintain(103, true);
        clock.Maintain(102.9f, true);
        Require(clock.report.completed && clock.report.stopReason == "invalid-clock", "post-trigger rollback above start was missed");

        var stale = Start(10, 10.5f);
        stale.QueueRequest(new UnityEngine.Vector2(1, 0), 10, 0f);
        var unavailable = new FakeReader { Available = false };
        Require(!stale.ObservePending(398, 10.6f, true, 11, unavailable), "unavailable reader sampled");
        Require(stale.report.completed && stale.report.stopReason == "observation-dependency-unavailable" && unavailable.Calls == 0,
                "stale request was not terminally cleared on unavailable dependencies");
        var recovered = new FakeReader();
        Require(!stale.ObservePending(398, 10.7f, true, 12, recovered) && recovered.Calls == 0,
                "old request was reused after recovery");

        var identityHandoff = Start(15, 15.5f);
        identityHandoff.QueueRequest(new UnityEngine.Vector2(1, 0), 20, 0f);
        var identityReader = new FakeReader();
        Require(!identityHandoff.ObservePending(404, 15.6f, true, 21, identityReader) &&
                identityHandoff.report.completed && identityHandoff.report.stopReason == "selected-egg-changed" &&
                identityReader.Calls == 0,
                "same-frame egg identity handoff consumed the previous request");
        var bridgeHandoff = Start(17, 17.5f);
        bridgeHandoff.QueueRequest(new UnityEngine.Vector2(1, 0), 30, 0f);
        bridgeHandoff.OnBridgeIdentityChanged();
        var newBridgeReader = new FakeReader();
        Require(!bridgeHandoff.ObservePending(398, 17.6f, true, 1, newBridgeReader) && newBridgeReader.Calls == 0 &&
                bridgeHandoff.report.completed && bridgeHandoff.report.stopReason == "bridge-instance-changed",
                "new bridge fixed-tick sequence consumed the old bridge request");

        var paired = Start(20, 20.5f);
        paired.QueueRequest(new UnityEngine.Vector2(.25f, -.75f), 40, 2.75f);
        var fake = new FakeReader();
        Require(!paired.ObservePending(398, 20.6f, true, 40, fake) && fake.Calls == 0,
                "same fixed tick was sampled");
        Require(paired.ObservePending(398, 20.7f, true, 41, fake), "later fixed tick was not sampled");
        Require(paired.report.samples[0].requestWrittenAfterFixedTick == 40 && paired.report.samples[0].observedAfterFixedTick == 41 &&
                paired.report.samples[0].requestedBridgeMovement.x == .25f && paired.report.samples[0].requestedBridgeMovement.y == -.75f,
                "sample did not preserve exact request/tick pair");
        Require(paired.report.samples[0].navigationObjectiveStallAvailable &&
                paired.report.samples[0].navigationObjectiveStalledSeconds == 2.75f,
                "sample did not preserve objective-stall context");

        var unavailableStallSample = Start(21, 21.5f);
        unavailableStallSample.QueueRequest(new UnityEngine.Vector2(0, 0), 50, float.NaN);
        Require(unavailableStallSample.ObservePending(398, 21.6f, true, 51, new FakeReader()),
                "sample with unavailable stall operand was dropped");
        Require(!unavailableStallSample.report.samples[0].navigationObjectiveStallAvailable &&
                unavailableStallSample.report.samples[0].navigationObjectiveStalledSeconds == 0f,
                "unavailable sample stall was fabricated");

        var cap = Start(30, 30.5f);
        var capReader = new FakeReader();
        for (int i = 0; i < 8; i++) {
            cap.QueueRequest(new UnityEngine.Vector2(i, 0), i * 2, i * 0.25f);
            Require(cap.ObservePending(398, 30.5f + i, true, i * 2 + 1, capReader), "bounded sample rejected");
        }
        Require(cap.report.sampleCount == 8 && cap.report.completed && cap.report.stopReason == "sample-cap" && capReader.Calls == 8,
                "eight-sample cap failed");
        Require(!cap.ObserveTrigger(true, true, 398, 167, 60, 8, 40), "completed trace rearmed");

        var deadline = Start(50, 50.5f);
        deadline.Maintain(58.5f, true);
        Require(deadline.report.completed && deadline.report.stopReason == "window-expired", "deadline depended on a pending request");
        var inactive = Start(60, 60.5f);
        inactive.QueueRequest(new UnityEngine.Vector2(1, 0), 1, 0f);
        Require(!inactive.ObservePending(398, 60.6f, false, 2, new FakeReader()) && inactive.report.completed &&
                inactive.report.stopReason == "owner-inactive", "owner stop did not close recorder");
        foreach (string ownerLoss in new[] { "manual-takeover", "foreign-bridge-or-bank", "source-owner-lost" }) {
            var yielded = Start(65, 65.5f);
            yielded.QueueRequest(new UnityEngine.Vector2(1, 0), 3, 0f);
            var ownerReader = new FakeReader();
            Require(!yielded.ObservePending(398, 65.6f, false, 4, ownerReader) && ownerReader.Calls == 0 &&
                    yielded.report.completed, ownerLoss + " captured without owned diagnostic input");
        }
        var yieldPath = Start(68, 68.5f);
        yieldPath.QueueRequest(new UnityEngine.Vector2(1, 0), 3, 0f);
        yieldPath.Complete("manual-input-takeover");
        Require(yieldPath.report.completed && yieldPath.report.stopReason == "manual-input-takeover",
                "yield after pending request did not close the trace");
        var disposed = Start(70, 70.5f);
        disposed.QueueRequest(new UnityEngine.Vector2(1, 0), 1, 0f);
        disposed.Dispose();
        Require(disposed.report.completed && disposed.report.stopReason == "owner-disposed", "dispose did not close recorder");

        Require(SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, true, false, true, true, true),
                "ready selected Siren owner did not receive the diagnostic input frame");
        Require(!SirenNavigationObservationPolicy.SirenOwnsInputFrame(false, true, true, false, true, true, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, false, true, false, true, true, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, false, false, true, true, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, true, true, true, true, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, true, false, false, true, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, true, false, true, false, true) &&
                !SirenNavigationObservationPolicy.SirenOwnsInputFrame(true, true, true, false, true, true, false),
                "Siren claimed navigation before every source/diagnostic ownership prerequisite");

        // Pairing contract: route state is made current before the prior input
        // request is sampled, and the next request is queued only afterward.
        var afterRouteWrite = Start(80, 80.5f);
        afterRouteWrite.QueueRequest(new UnityEngine.Vector2(.5f, .25f), 100, 0f);
        var routeReader = new FakeReader();
        Require(afterRouteWrite.ObservePending(398, 81f, true, 101, routeReader),
                "same-owner path sample was not accepted after route state was prepared");
        Require(afterRouteWrite.report.samples[0].requestWrittenAfterFixedTick == 100 &&
                afterRouteWrite.report.samples[0].observedAfterFixedTick == 101 && routeReader.Calls == 1,
                "sample lost the prior request/fixed-tick pairing");

        Console.WriteLine("siren-navigation-recorder-state-contract-passed");
        return 0;
    }
}
