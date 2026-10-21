using System;
using System.Reflection;
using RoR2;
using OriginalOwnerProbeObserver;

internal static class NativeResultOwnerHarness
{
    private static int assertions;
    private static void Check(bool condition, string label)
    {
        assertions++;
        if (!condition) throw new Exception("FAIL: " + label);
    }

    private static object Read(object target, string field) =>
        target.GetType().GetField(field, BindingFlags.Instance | BindingFlags.Public).GetValue(target);

    public static int Main()
    {
        Check(PortSessionOriginalMusicControllerOwner.StartForReadyAudio(null, false) == null &&
            Observer.MusicStartIntroPostEventReturned == null && Observer.MusicTrackSetStateReturned == null,
            "ordinary false request does not create or arm the music owner");
        var controller = new MusicController { enableMusicSystem = true };
        var selected = new MusicTrackDef { cachedName = "selected" };
        controller.SetCurrentTrackForFixture(selected);
        var owner = new PortSessionOriginalMusicControllerOwner();
        typeof(PortSessionOriginalMusicControllerOwner).GetField("ownedController", BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(owner, controller);
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { typeof(MusicController) });

        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("InstallMusicOutputObserver", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        var snapshot = typeof(PortSessionOriginalMusicControllerOwner).GetField("snapshot", BindingFlags.Instance | BindingFlags.NonPublic)
            .GetValue(owner);
        Check((bool)Read(snapshot, "nativeMusicResultObserverInstalled"), "active explicit owner reports callback installation");
        Observer.RecordMusicStartIntroPostEventReturned(0xf1234567u, controller);
        Check((bool)Read(snapshot, "introPostEventReturnObserved"), "owned intro call result recorded");
        Check((uint)Read(snapshot, "introPostEventPlayingId") == 0xf1234567u, "unsigned playing ID preserved");
        Check((int)Read(snapshot, "introPostEventReturnCount") == 1 && (bool)Read(snapshot, "introPostEventSourceMatched"),
            "controller identity and bounded count recorded");

        var unrelatedController = new MusicController();
        Observer.RecordMusicStartIntroPostEventReturned(17u, unrelatedController);
        Check((int)Read(snapshot, "introPostEventReturnCount") == 1 && (bool)Read(snapshot, "nativeMusicCallOwnerMismatchObserved"),
            "other controller result cannot overwrite owned controller sample");

        var observeTrack = typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveTrackSetState", BindingFlags.Instance | BindingFlags.NonPublic);
        observeTrack.Invoke(owner, new object[] { 0x1234567, selected, 2 });
        Check((bool)Read(snapshot, "selectedTrackPlaySetStateReturnObserved") &&
            (bool)Read(snapshot, "selectedTrackPlayContextKnown") && (bool)Read(snapshot, "selectedTrackPlaySourceMatched"),
            "selected current-track source joined by exact object identity");
        Check((int)Read(snapshot, "selectedTrackPlaySetStateResult") == 0x1234567, "raw enum stack value preserved");

        var otherTrack = new MusicTrackDef { cachedName = "same-name-different-object" };
        observeTrack.Invoke(owner, new object[] { 9, otherTrack, 3 });
        Check((bool)Read(snapshot, "selectedTrackStopSetStateReturnObserved") &&
            !(bool)Read(snapshot, "selectedTrackStopSourceMatched") && (bool)Read(snapshot, "nativeMusicCallOwnerMismatchObserved"),
            "same-name or different track does not pass selected-track identity join");

        typeof(PortSessionOriginalMusicControllerOwner).GetField("currentTrackGetter", BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(owner, null);
        observeTrack.Invoke(owner, new object[] { 11, selected, 2 });
        Check(!(bool)Read(snapshot, "selectedTrackPlayContextKnown") && !(bool)Read(snapshot, "selectedTrackPlaySourceMatched"),
            "unavailable current-track getter remains unknown");

        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("DetachMusicOutputObserver", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        Check(Observer.MusicStartIntroPostEventReturned == null && Observer.MusicTrackSetStateReturned == null,
            "owner teardown detaches exact callback fields");
        Check(!(bool)Read(snapshot, "nativeMusicResultObserverInstalled"), "teardown clears installed state");
        int countAfterDetach = (int)Read(snapshot, "introPostEventReturnCount");
        Observer.RecordMusicStartIntroPostEventReturned(19u, controller);
        Check((int)Read(snapshot, "introPostEventReturnCount") == countAfterDetach, "detached observer cannot receive later calls");

        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, new object[] { typeof(MusicController) });
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("InstallMusicOutputObserver", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        typeof(PortSessionOriginalMusicControllerOwner).GetField("awaitingInstantiationAwake", BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(owner, true);
        Observer.RecordMusicStartIntroPostEventReturned(0u, controller);
        Observer.RecordMusicTrackSetStateReturned((int)AKRESULT.AK_Success, selected, 2);
        typeof(PortSessionOriginalMusicControllerOwner).GetField("awaitingInstantiationAwake", BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(owner, false);
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("JoinPendingNativeResultsToOwnedObjects", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        Check((int)Read(snapshot, "introPostEventReturnCount") == 2 && (uint)Read(snapshot, "introPostEventPlayingId") == 0,
            "early instantiation return is joined by exact controller identity and zero remains raw");
        Check((int)Read(snapshot, "selectedTrackPlaySetStateReturnCount") == 3 &&
            (bool)Read(snapshot, "selectedTrackPlayContextKnown") && (bool)Read(snapshot, "selectedTrackPlaySourceMatched"),
            "early selected-track return is joined after source current-track getter binds");
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("DetachMusicOutputObserver", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(owner, null);
        Check(Observer.IncrementBoundedCount(999999) == 1000000 && Observer.IncrementBoundedCount(1000000) == 1000000,
            "per-site count saturates");

        Console.WriteLine("PASS: " + assertions + " owner identity, scalar result, unknown context and teardown assertions");
        return 0;
    }
}
