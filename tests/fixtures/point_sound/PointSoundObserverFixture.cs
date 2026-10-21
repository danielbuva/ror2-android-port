using System;

internal static class PointSoundObserverFixture
{
    private static void Require(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }

    private static int Main()
    {
        Require(PointSoundDiagnosticObserver.CaptureSnapshot() == null, "observer must start default-off");
        Require(PointSoundDiagnosticObserver.RouteRefusal(false, false) == null &&
            PointSoundDiagnosticObserver.OwnerRefusal(false, false, false) == null,
            "absent selector must leave ordinary runs unaffected");
        Require(PointSoundDiagnosticObserver.RouteRefusal(true, false) != null,
            "diagnostic must reject a non-integrated route");
        Require(PointSoundDiagnosticObserver.OwnerRefusal(true, false, true) != null &&
            PointSoundDiagnosticObserver.OwnerRefusal(true, true, false) != null &&
            PointSoundDiagnosticObserver.OwnerRefusal(true, true, true) == null,
            "diagnostic must require the selected ready original-audio owner");
        Require(GameAudioOriginalOwner.PointSoundDiagnosticBuildRefusal(false) == null &&
            GameAudioOriginalOwner.PointSoundDiagnosticBuildRefusal(true) == null,
            "diagnostic build pin must admit the explicitly instrumented fixture variant");
        PointSoundDiagnosticObserver.Configure(true);
        PointSoundDiagnosticObserver.Begin(0x1234u);
        PointSoundDiagnosticObserver.Mark(6);
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException: synthetic original failure",
            "at RoR2.Audio.PointSoundManager.EmitSoundLocal (RoR2.Audio.AkEventIdArg eventId, UnityEngine.Vector3 position)");
        PointSoundDiagnosticObserver.ObserveUnityLog(
            "NullReferenceException: unrelated",
            "at RoR2.Other.Owner.Run ()");
        var snapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        Require(snapshot != null && snapshot.requested && snapshot.enabled, "explicit diagnostic opt-in missing");
        Require(snapshot.requestCount == 1 && snapshot.lastEventId == 0x1234u && snapshot.lastStage == 6,
            "event boundary fields not captured");
        Require(snapshot.hasFirstNullReference && snapshot.firstNullReferenceStage == 6 &&
            snapshot.firstNullReferenceEventId == 0x1234u && snapshot.matchingNullReferenceCount == 1,
            "dotted Unity method stack was not classified");

        PointSoundDiagnosticObserver.Reset();
        PointSoundDiagnosticObserver.Begin(0x5678u);
        PointSoundDiagnosticObserver.ObserveUnityLog("NullReferenceException", "PointSoundManager:EmitSoundLocal");
        snapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        Require(snapshot.hasFirstNullReference && snapshot.firstNullReferenceEventId == 0x5678u,
            "legacy colon stack format was not retained");
        var requestCountBeforeDisable = snapshot.requestCount;
        var matchCountBeforeDisable = snapshot.matchingNullReferenceCount;
        PointSoundDiagnosticObserver.Disable();
        PointSoundDiagnosticObserver.Begin(0x9999u);
        PointSoundDiagnosticObserver.ObserveUnityLog("NullReferenceException", "PointSoundManager:EmitSoundLocal");
        snapshot = PointSoundDiagnosticObserver.CaptureSnapshot();
        Require(snapshot.requested && !snapshot.enabled && snapshot.requestCount == requestCountBeforeDisable &&
            snapshot.matchingNullReferenceCount == matchCountBeforeDisable,
            "terminal teardown must retain the final opt-in report while disabling subsequent observations");
        Console.WriteLine("default-off, request gate, dotted and legacy stack matching, bounded first-failure retention, teardown passed");
        return 0;
    }
}
