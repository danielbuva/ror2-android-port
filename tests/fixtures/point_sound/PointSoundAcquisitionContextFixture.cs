using System;

internal static class PointSoundAcquisitionContextFixture
{
    private static int Main()
    {
        // A fresh default-off process must record neither existing markers nor
        // matching Unity logs, and must not publish a diagnostic snapshot.
        PointSoundDiagnosticObserver.Configure(false);
        PointSoundDiagnosticObserver.Begin(123u);
        PointSoundDiagnosticObserver.Mark(21);
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException",
            "at RoR2.Audio.PointSoundManager.EmitSoundLocal");
        if (PointSoundDiagnosticObserver.CaptureSnapshot() != null ||
            PointSoundDiagnosticObserver.RequestCount != 0 ||
            PointSoundDiagnosticObserver.MatchingNullReferenceCount != 0)
            return 4;

        int[] paths = { 20, 21, 22 };
        uint eventId = 74455154u;
        foreach (int path in paths)
        {
            PointSoundDiagnosticObserver.Configure(true);
            PointSoundDiagnosticObserver.Begin(eventId);
            PointSoundDiagnosticObserver.Mark(path); // existing RequestEmitter branch marker
            PointSoundDiagnosticObserver.Mark(3);    // existing returned-emitter marker
            PointSoundDiagnosticObserver.RecordEmitterAlive(false);
            PointSoundDiagnosticObserver.Mark(4);    // existing pre-transform marker
            PointSoundDiagnosticObserver.ObserveUnityLog(
                "NullReferenceException: Object reference not set to an instance of an object.",
                "at RoR2.Audio.PointSoundManager.EmitSoundLocal (RoR2.Audio.AkEventIdArg akEventId, UnityEngine.Vector3 position)");

            var snapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
            if (snapshot == null || !snapshot.hasFirstNullReference ||
                snapshot.firstNullReferenceStage != 4 ||
                snapshot.firstNullReferenceEventId != eventId ||
                snapshot.firstNullReferenceAcquisitionPath != path ||
                !snapshot.hasFirstNullReferenceEmitterAlive ||
                snapshot.firstNullReferenceEmitterAlive)
                return 1;

            // Later activity must not mutate the first failure's context.
            PointSoundDiagnosticObserver.Begin(eventId + 1);
            PointSoundDiagnosticObserver.Mark(22);
            PointSoundDiagnosticObserver.RecordEmitterAlive(true);
            PointSoundDiagnosticObserver.Mark(4);
            PointSoundDiagnosticObserver.ObserveUnityLog(
                "NullReferenceException",
                "at RoR2.Audio.PointSoundManager.EmitSoundLocal");
            snapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
            if (snapshot.firstNullReferenceEventId != eventId ||
                snapshot.firstNullReferenceAcquisitionPath != path ||
                snapshot.firstNullReferenceEmitterAlive)
                return 2;
            eventId++;
        }

        PointSoundDiagnosticObserver.Configure(true);
        PointSoundDiagnosticObserver.Begin(eventId);
        PointSoundDiagnosticObserver.Mark(3);
        PointSoundDiagnosticObserver.RecordEmitterAlive(false);
        PointSoundDiagnosticObserver.Mark(4);
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException",
            "at RoR2.Audio.PointSoundManager.EmitSoundLocal");
        var noBranchSnapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        if (noBranchSnapshot.firstNullReferenceAcquisitionPath != 0 ||
            !noBranchSnapshot.hasFirstNullReferenceEmitterAlive ||
            noBranchSnapshot.firstNullReferenceEmitterAlive)
            return 3;

        // Stage zero is a valid first observation before any Begin call. It
        // still freezes the first event/path/unknown-emitter state, even after
        // a later acquisition and NRE update the ordinary last-event fields.
        PointSoundDiagnosticObserver.Configure(true);
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException",
            "at RoR2.Audio.PointSoundManager.EmitSoundLocal");
        var stageZeroSnapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        if (stageZeroSnapshot == null || !stageZeroSnapshot.hasFirstNullReference ||
            stageZeroSnapshot.firstNullReferenceStage != 0 ||
            stageZeroSnapshot.firstNullReferenceEventId != 0 ||
            stageZeroSnapshot.firstNullReferenceAcquisitionPath != 0 ||
            stageZeroSnapshot.hasFirstNullReferenceEmitterAlive)
            return 5;

        PointSoundDiagnosticObserver.Begin(9001u);
        PointSoundDiagnosticObserver.Mark(22);
        PointSoundDiagnosticObserver.RecordEmitterAlive(true);
        PointSoundDiagnosticObserver.Mark(4);
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException",
            "at RoR2.Audio.PointSoundManager.EmitSoundLocal");
        stageZeroSnapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        if (stageZeroSnapshot.firstNullReferenceStage != 0 ||
            stageZeroSnapshot.firstNullReferenceEventId != 0 ||
            stageZeroSnapshot.firstNullReferenceAcquisitionPath != 0 ||
            stageZeroSnapshot.hasFirstNullReferenceEmitterAlive ||
            stageZeroSnapshot.matchingNullReferenceCount != 2 ||
            stageZeroSnapshot.lastEventId != 9001u)
            return 6;

        Console.WriteLine("default-off silent; markers 20/21/22 retained; first NRE including stage zero frozen");
        return 0;
    }
}
