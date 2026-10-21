using System;
using System.Reflection;
using RoR2;
using UnityEngine;

internal static class MusicObservationHarness
{
    private static int assertions;
    private static void Check(bool condition, string label)
    {
        assertions++;
        if (!condition) throw new Exception("FAIL: " + label);
    }
    private static object Read(object target, string name) =>
        target.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public).GetValue(target);

    private static PortSessionOriginalMusicControllerOwner NewOwner(MusicController controller)
    {
        var owner = new PortSessionOriginalMusicControllerOwner();
        typeof(PortSessionOriginalMusicControllerOwner).GetField("ownedController", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(owner, controller);
        typeof(PortSessionOriginalMusicControllerOwner).GetField("ownedControllerRoot", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(owner, new GameObject("owned-music"));
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, new object[] { typeof(MusicController) });
        return owner;
    }

    private static object Snapshot(PortSessionOriginalMusicControllerOwner owner) =>
        typeof(PortSessionOriginalMusicControllerOwner).GetField("snapshot", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(owner);

    public static int Main()
    {
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(false, true, false, false, true, true) == "music_disabled", "disabled system has no scene candidate");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, false, true, false, true, true) == "scene_missing", "missing scene has no candidate");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, true, false, false, true, true) == "main_track", "absent teleporter selects main candidate");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, true, true, true, true, true) == "main_track", "idle teleporter selects main candidate");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, true, true, false, true, true) == "boss_track", "active teleporter with boss track selects boss candidate");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, true, true, false, false, true) == "main_track", "missing boss track falls back to main");
        Check(PortSessionOriginalMusicControllerOwner.ClassifySceneTrackCandidate(true, true, true, false, false, false) == "no_scene_track", "scene with no tracks remains empty");

        Check(PortSessionOriginalMusicControllerOwner.IsSuccessfulGlobalRtpcRead(AKRESULT.AK_Success, 80f, (int)AkQueryRTPCValue.RTPCValue_Global), "successful finite global query is observed");
        Check(!PortSessionOriginalMusicControllerOwner.IsSuccessfulGlobalRtpcRead(AKRESULT.AK_Fail, 80f, (int)AkQueryRTPCValue.RTPCValue_Global), "failed query is unknown");
        Check(!PortSessionOriginalMusicControllerOwner.IsSuccessfulGlobalRtpcRead(AKRESULT.AK_Success, float.NaN, (int)AkQueryRTPCValue.RTPCValue_Global), "non-finite query is unknown");
        Check(!PortSessionOriginalMusicControllerOwner.IsSuccessfulGlobalRtpcRead(AKRESULT.AK_Success, 80f, (int)AkQueryRTPCValue.RTPCValue_GameObject), "non-global resolved type is not reported as global");

        var main = new MusicTrackDef { cachedName = "main-track" };
        var boss = new MusicTrackDef { cachedName = "boss-track" };
        SceneCatalog.mostRecentSceneDef = new SceneDef { name = "test-scene", cachedName = "test-scene", mainTrack = main, bossTrack = boss };
        TeleporterInteraction.instance = new TeleporterInteraction { isIdle = false };
        var controller = new MusicController { name = "source-controller", enableMusicSystem = true };
        controller.SetCurrentTrackForFixture(boss);
        var owner = NewOwner(controller);
        Time.realtimeSinceStartup = 1f;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("SampleSourceMusicContextSafely", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, null);
        var snapshot = Snapshot(owner);
        Check((bool)Read(snapshot, "currentTrackGetterAvailable"), "exact private source getter bound");
        Check((bool)Read(snapshot, "currentTrackObserved"), "private currentTrack read observed");
        Check((string)Read(snapshot, "currentTrackName") == "boss-track", "selected current track name captured");
        Check((string)Read(snapshot, "sceneTrackCandidateKind") == "boss_track", "scene/teleporter gate captured");
        Check((bool)Read(snapshot, "teleporterIdleObserved") && !(bool)Read(snapshot, "teleporterIdle"), "teleporter active gate captured");
        Check((bool)Read(snapshot, "sceneTrackHookObservationKnown"), "hook presence reflection surface resolved");
        var sourceParameters = (PortSessionOriginalMusicControllerOwner.Snapshot.SourceMusicParameterObservation[])Read(snapshot, "sourceMusicParameters");
        Check(sourceParameters.Length == 5 && sourceParameters[0].valueObserved, "managed source RTPC setter values captured as scalars");
        Check(!(bool)Read(snapshot, "ownedListenerMembershipObserved"), "missing listener stays unknown");

        var ownedRoot = (GameObject)typeof(PortSessionOriginalMusicControllerOwner).GetField("ownedControllerRoot", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(owner);
        var listener = ownedRoot.AddComponent<AkAudioListener>();
        listener.isDefaultListener = true;
        AkAudioListener.DefaultListeners.ListenerList.Add(listener);
        Time.realtimeSinceStartup = 2f;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("SampleSourceMusicContextSafely", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, null);
        Check((bool)Read(snapshot, "ownedListenerObserved") && (bool)Read(snapshot, "ownedListenerEnabled"), "owned listener component activity captured");
        Check((bool)Read(snapshot, "ownedListenerDefault") && (bool)Read(snapshot, "ownedListenerMembershipObserved"), "default-list membership is explicitly observed");
        Check((bool)Read(snapshot, "ownedListenerInManagedDefaultList") && (int)Read(snapshot, "managedDefaultListenerCount") == 1, "exact owned listener membership and managed count captured");

        SceneCatalog.ThrowOnRead = true;
        Time.realtimeSinceStartup = 3f;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("SampleSourceMusicContextSafely", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, null);
        Check((bool)Read(snapshot, "musicObservationAttempted") && !(bool)Read(snapshot, "musicObservationSucceeded"), "context read exception is contained as failed observation");
        Check((string)Read(snapshot, "musicObservationFailure") == "sample_failed:InvalidOperationException", "sample failure reason is scalar and explicit");
        Check(!(bool)Read(snapshot, "currentTrackObserved") && Read(snapshot, "currentTrackName") == null && !(bool)Read(snapshot, "sceneTrackGateObserved"), "failed sample clears stale track and scene values");
        Check(!((PortSessionOriginalMusicControllerOwner.Snapshot.SourceMusicParameterObservation[])Read(snapshot, "sourceMusicParameters"))[0].valueObserved, "failed sample clears stale source RTPC values");
        SceneCatalog.ThrowOnRead = false;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, new object[] { null });
        Check(!(bool)Read(snapshot, "currentTrackGetterAvailable") && (string)Read(snapshot, "musicObservationFailure") == "binding_failed:ArgumentNullException", "optional reflection binding failure stays non-fatal and unknown");
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, new object[] { typeof(MusicController) });
        Time.realtimeSinceStartup = 4f;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("SampleSourceMusicContextSafely", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(owner, null);
        Check((bool)Read(snapshot, "musicObservationSucceeded") && (string)Read(snapshot, "currentTrackName") == "boss-track", "later healthy sample recovers after contained diagnostic failure");
        typeof(PortSessionOriginalMusicControllerOwner).GetField("instance", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, owner);
        var capturedWhileLive = PortSessionOriginalMusicControllerOwner.CaptureSnapshot();
        Check(capturedWhileLive.musicObservationOwnerAlive && capturedWhileLive.currentTrackObserved,
            "report capture preserves valid context while the owned controller exists");
        int queryCountBeforeCapture = AkSoundEngine.QueryCalls;
        typeof(PortSessionOriginalMusicControllerOwner).GetField("ownedController", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(owner, null);
        PortSessionOriginalMusicControllerOwner.CaptureSnapshot();
        Check(AkSoundEngine.QueryCalls == queryCountBeforeCapture,
            "same-frame report invalidation makes no new native query");
        Check(!(bool)Read(snapshot, "musicObservationOwnerAlive") && !(bool)Read(snapshot, "currentTrackObserved") && Read(snapshot, "currentTrackName") == null, "destroyed owned controller invalidates the previous sample");
        Check((string)Read(snapshot, "musicObservationFailure") == "source_controller_missing_or_destroyed", "destroyed owner is explicit instead of stale success");

        var globalSnapshot = newOwnerForGlobalQuery();
        var globalOwner = (PortSessionOriginalMusicControllerOwner)globalSnapshot.Item1;
        var globalState = globalSnapshot.Item2;
        var engineInitialized = globalState.GetType().GetField("engineInitialized", BindingFlags.Instance | BindingFlags.Public);
        engineInitialized.SetValue(globalState, true);
        AkSoundEngine.Initialized = true;
        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryReturnedTypes = new[] {
            (int)AkQueryRTPCValue.RTPCValue_Global,
            (int)AkQueryRTPCValue.RTPCValue_Global,
            (int)AkQueryRTPCValue.RTPCValue_Global
        };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 2f });
        var rtpcs = (PortSessionOriginalMusicControllerOwner.Snapshot.RtpcObservation[])Read(globalState, "globalRtpcs");
        Check(AkSoundEngine.QueryCalls == 3, "one read-only query per exact global volume RTPC");
        Check(AkSoundEngine.LastGameObject == ulong.MaxValue && AkSoundEngine.LastPlayingId == 0, "global query uses exact invalid object/playing IDs");
        Check(rtpcs[0].name == "Volume_Master" && rtpcs[0].valueObserved && rtpcs[0].value == 100f, "master global value recorded only on success");
        Check(rtpcs[1].name == "Volume_MSX" && rtpcs[1].valueObserved && rtpcs[1].value == 80f, "music global value recorded only on success");
        Check(rtpcs[2].name == "Parent_Volume_MSX" && rtpcs[2].valueObserved && rtpcs[2].value == 65f, "parent music global value recorded only on success");
        Check(rtpcs[0].resolvedValueObserved && rtpcs[0].resolvedValue == 100f && rtpcs[0].returnedValueType == 1, "global result is also available with explicit resolved scope");

        globalOwner.GetType().GetField("ownedController", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(globalOwner, controller);
        globalOwner.GetType().GetField("ownedControllerRoot", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(globalOwner, new GameObject("owned-global-music"));
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("TryBindMusicObservationMembers", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { typeof(MusicController) });
        globalOwner.GetType().GetField("nextGlobalRtpcObservationAt", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(globalOwner, 3f);
        AkSoundEngine.ResetQueryControls();
        Time.realtimeSinceStartup = 2.5f;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("SampleSourceMusicContextSafely", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, null);
        Check(AkSoundEngine.QueryCalls == 0 && (bool)Read(globalState, "musicObservationSucceeded"), "intermediate source sample does not repeat throttled native queries");
        Check(rtpcs[0].valueObserved && rtpcs[0].resolvedValueObserved && rtpcs[0].sampleRealtime == 2f, "throttled global/resolved results retain their original sample time");

        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryReturnedTypes = new[] {
            (int)AkQueryRTPCValue.RTPCValue_Default,
            (int)AkQueryRTPCValue.RTPCValue_Global,
            (int)AkQueryRTPCValue.RTPCValue_GameObject
        };
        AkSoundEngine.QueryValues = new[] { 43f, 81f, 27f };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 3f });
        Check(!rtpcs[0].valueObserved && rtpcs[0].value == 0f && rtpcs[0].resolvedValueObserved && rtpcs[0].resolvedValue == 43f && rtpcs[0].returnedValueType == 0,
            "default-scope value is separate and never labeled global");
        Check(rtpcs[1].valueObserved && rtpcs[1].value == 81f && rtpcs[1].resolvedValueObserved, "global value retains both existing and resolved representations");
        Check(!rtpcs[2].valueObserved && rtpcs[2].resolvedValueObserved && rtpcs[2].resolvedValue == 27f && rtpcs[2].returnedValueType == 2,
            "game-object fallback keeps explicit scope without global classification");

        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryReturnedTypes = new[] {
            (int)AkQueryRTPCValue.RTPCValue_PlayingID,
            (int)AkQueryRTPCValue.RTPCValue_Unavailable,
            99
        };
        AkSoundEngine.QueryValues = new[] { 12f, 22f, 33f };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 4f });
        Check(rtpcs[0].resolvedValueObserved && rtpcs[0].resolvedValue == 12f && rtpcs[0].returnedValueType == 3,
            "playing-ID scope is retained as a known resolved scope");
        Check(!rtpcs[1].resolvedValueObserved && rtpcs[1].resolvedValue == 0f && rtpcs[1].returnedValueType == 4,
            "unavailable scope is not a resolved value");
        Check(!rtpcs[2].resolvedValueObserved && rtpcs[2].resolvedValue == 0f && rtpcs[2].returnedValueType == 99,
            "unknown enum value is not a resolved value");

        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryResults = new[] { AKRESULT.AK_IDNotFound, AKRESULT.AK_Success, AKRESULT.AK_Fail };
        AkSoundEngine.QueryReturnedTypes = new[] {
            (int)AkQueryRTPCValue.RTPCValue_Unavailable,
            (int)AkQueryRTPCValue.RTPCValue_Default,
            (int)AkQueryRTPCValue.RTPCValue_Global
        };
        AkSoundEngine.QueryValues = new[] { 77f, float.NaN, 88f };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 5f });
        Check(rtpcs[0].resultObserved && rtpcs[0].resultCode == (int)AKRESULT.AK_IDNotFound && !rtpcs[0].resolvedValueObserved,
            "IDNotFound remains a known failure with no value");
        Check(rtpcs[1].resultObserved && !rtpcs[1].resolvedValueObserved && rtpcs[1].resolvedValue == 0f,
            "non-finite successful native output is unknown");
        Check(rtpcs[2].resultObserved && rtpcs[2].resultCode == (int)AKRESULT.AK_Fail && !rtpcs[2].resolvedValueObserved,
            "failed query is not retained as a value");

        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.ThrowOnQuery = true;
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 6f });
        Check(AkSoundEngine.QueryCalls == 3 && !rtpcs[0].resultObserved && !rtpcs[0].resolvedValueObserved && rtpcs[0].returnedValueType == -1,
            "thrown native wrapper clears both value representations and returned scope");

        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryReturnedTypes = new[] { (int)AkQueryRTPCValue.RTPCValue_Default };
        AkSoundEngine.QueryValues = new[] { 54f };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 7f });
        Check(rtpcs[0].resolvedValueObserved && rtpcs[0].resolvedValue == 54f, "known default-scope value can recover after wrapper failure");

        engineInitialized.SetValue(globalState, false);
        AkSoundEngine.ResetQueryControls();
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 8f });
        Check(AkSoundEngine.QueryCalls == 0 && !rtpcs[0].queryAttempted && !rtpcs[0].valueObserved && !rtpcs[0].resolvedValueObserved,
            "uninitialized engine produces unknown without native queries");

        engineInitialized.SetValue(globalState, true);
        AkSoundEngine.Initialized = true;
        AkSoundEngine.ResetQueryControls();
        AkSoundEngine.QueryReturnedTypes = new[] { (int)AkQueryRTPCValue.RTPCValue_Default };
        AkSoundEngine.QueryValues = new[] { 54f };
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ObserveGlobalRtpcs", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, new object[] { 9f });
        Check(rtpcs[0].resolvedValueObserved, "pre-destruction result exists for cleanup check");
        globalOwner.GetType().GetField("ownedController", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(globalOwner, null);
        typeof(PortSessionOriginalMusicControllerOwner).GetMethod("ExpireMusicObservationIfOwnerMissing", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(globalOwner, null);
        Check(!rtpcs[0].valueObserved && !rtpcs[0].resolvedValueObserved && rtpcs[0].resolvedValue == 0f && rtpcs[0].returnedValueType == -1,
            "controller destruction clears global and resolved values and scope");

        Console.WriteLine("PASS: " + assertions + " music-context and read-only RTPC assertions");
        return 0;
    }

    private static Tuple<object, object> newOwnerForGlobalQuery()
    {
        var owner = new PortSessionOriginalMusicControllerOwner();
        return Tuple.Create((object)owner, Snapshot(owner));
    }
}
