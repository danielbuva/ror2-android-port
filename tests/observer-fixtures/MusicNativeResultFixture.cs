using System;
using OriginalOwnerProbeObserver;

public enum AKRESULT { AK_Fail = 0, AK_Success = 1 }
public sealed class AkOutputSettings { }
public sealed class AkOutput { }

namespace UnityEngine
{
    public sealed class GameObject { }
}

public static class AkSoundEngine
{
    public static int addCalls, removeCalls, postCalls, setStateCalls;
    public static AKRESULT addResult = AKRESULT.AK_Success;
    public static AKRESULT setStateResult = AKRESULT.AK_Success;
    public static uint postEventResult;
    public static bool throwPostEvent, throwSetState;

    public static AKRESULT AddOutput(AkOutputSettings settings, out ulong deviceId, ulong[] devices, uint count)
    {
        addCalls++;
        deviceId = 0x123456789abcdef0UL;
        return addResult;
    }

    public static AKRESULT RemoveOutput(ulong deviceId) { removeCalls++; return AKRESULT.AK_Success; }
    public static uint PostEvent(string eventName, UnityEngine.GameObject gameObject)
    {
        postCalls++;
        if (throwPostEvent) throw new InvalidOperationException("native PostEvent fixture throw");
        return postEventResult;
    }
    public static uint PostEvent(uint eventId, UnityEngine.GameObject gameObject) { postCalls++; return postEventResult; }
    public static AKRESULT SetState(uint group, uint value)
    {
        setStateCalls++;
        if (throwSetState) throw new InvalidOperationException("native SetState fixture throw");
        return setStateResult;
    }
}

namespace RoR2
{
    public sealed class MusicController
    {
        static object keepAliveSink;
        ulong musicListenerId;

        public void Awake()
        {
            object unused = new object();
            AkOutputSettings settings = new AkOutputSettings();
            bool settingsAreValid = settings != null;
            if (Environment.TickCount == -1) keepAliveSink = unused;
            GC.KeepAlive(settings);
            ulong deviceId;
            if (AkSoundEngine.AddOutput(settings, out deviceId, new ulong[0], 1) == AKRESULT.AK_Success)
            {
                if (settingsAreValid)
                    musicListenerId = deviceId;
            }
            GC.KeepAlive(settings);
        }

        public void OnDestroy() { AkSoundEngine.RemoveOutput(musicListenerId); }

        public void StartIntroMusic()
        {
#if CHANGED_POST_EVENT
            AkSoundEngine.PostEvent(42u, new UnityEngine.GameObject());
#else
            AkSoundEngine.PostEvent("intro", new UnityEngine.GameObject());
#endif
#if DUPLICATE_POST_EVENT
            AkSoundEngine.PostEvent("intro-again", new UnityEngine.GameObject());
#endif
        }
    }

    public sealed class MusicTrackDef
    {
        public void Play()
        {
            AkSoundEngine.SetState(10u, 20u);
        }

        public void Stop()
        {
#if !MISSING_STOP
            AkSoundEngine.SetState(10u, 21u);
#endif
        }
    }
}

public static class MusicNativeResultFixture
{
    public static int Main()
    {
        int postCallbacks = 0, playCallbacks = 0, stopCallbacks = 0;
        uint seenPlayingId = 0;
        int seenPlayResult = 0, seenStopResult = 0;
        object seenController = null, seenPlayTrack = null, seenStopTrack = null;
        Observer.MusicStartIntroPostEventReturned = (value, source) =>
        {
            postCallbacks++;
            seenPlayingId = value;
            seenController = source;
        };
        Observer.MusicTrackSetStateReturned = (value, source, site) =>
        {
            if (site == 2) { playCallbacks++; seenPlayResult = value; seenPlayTrack = source; }
            else if (site == 3) { stopCallbacks++; seenStopResult = value; seenStopTrack = source; }
            else throw new Exception("unexpected observer site");
        };

        var controller = new RoR2.MusicController();
        var track = new RoR2.MusicTrackDef();
        AkSoundEngine.postEventResult = 0xf1234567u;
        AkSoundEngine.setStateResult = (AKRESULT)0x1234567;
        controller.Awake();
        controller.StartIntroMusic();
        track.Play();
        track.Stop();
        controller.OnDestroy();
        if (AkSoundEngine.addCalls != 1 || AkSoundEngine.postCalls != 1 || AkSoundEngine.setStateCalls != 2 ||
            AkSoundEngine.removeCalls != 1 || postCallbacks != 1 || playCallbacks != 1 || stopCallbacks != 1 ||
            seenPlayingId != 0xf1234567u || seenPlayResult != 0x1234567 || seenStopResult != 0x1234567 ||
            !ReferenceEquals(seenController, controller) || !ReferenceEquals(seenPlayTrack, track) ||
            !ReferenceEquals(seenStopTrack, track))
            throw new Exception("native call count/result/source changed through observer instrumentation");

        if (!Observer.IsExactOwnedSource(controller, controller) || Observer.IsExactOwnedSource(new object(), controller) ||
            Observer.IsExactSelectedTrackSource(false, track, track) ||
            Observer.IsExactSelectedTrackSource(true, new object(), track) ||
            !Observer.IsExactSelectedTrackSource(true, track, track) ||
            Observer.IncrementBoundedCount(999999) != 1000000 || Observer.IncrementBoundedCount(1000000) != 1000000)
            throw new Exception("owner identity/unknown selection/saturating counter contract changed");

        Observer.MusicStartIntroPostEventReturned = null;
        Observer.MusicTrackSetStateReturned = null;
        controller.StartIntroMusic();
        track.Play();
        if (AkSoundEngine.postCalls != 2 || AkSoundEngine.setStateCalls != 3)
            throw new Exception("null observer changed the original calls");

        Observer.MusicStartIntroPostEventReturned = (_, _) => throw new InvalidOperationException("observer exception");
        Observer.MusicTrackSetStateReturned = (_, _, _) => throw new InvalidOperationException("observer exception");
        controller.StartIntroMusic();
        track.Stop();
        if (AkSoundEngine.postCalls != 3 || AkSoundEngine.setStateCalls != 4)
            throw new Exception("observer exception replaced the original call path");

        Observer.MusicStartIntroPostEventReturned = (value, _) => { postCallbacks++; seenPlayingId = value; };
        AkSoundEngine.postEventResult = 0;
        controller.StartIntroMusic();
        if (postCallbacks != 2 || seenPlayingId != 0 || AkSoundEngine.postCalls != 4)
            throw new Exception("zero playing ID was not preserved as an observed raw return");

        Observer.MusicStartIntroPostEventReturned = (_, _) => postCallbacks++;
        AkSoundEngine.throwPostEvent = true;
        try { controller.StartIntroMusic(); throw new Exception("native PostEvent fixture did not throw"); }
        catch (InvalidOperationException error) when (error.Message == "native PostEvent fixture did not throw") { throw; }
        catch (InvalidOperationException) { }
        AkSoundEngine.throwPostEvent = false;
        Observer.MusicTrackSetStateReturned = (_, _, _) => playCallbacks++;
        AkSoundEngine.throwSetState = true;
        try { track.Play(); throw new Exception("native SetState fixture did not throw"); }
        catch (InvalidOperationException error) when (error.Message == "native SetState fixture did not throw") { throw; }
        catch (InvalidOperationException) { }
        AkSoundEngine.throwSetState = false;
        if (postCallbacks != 2 || playCallbacks != 1 || AkSoundEngine.postCalls != 5 || AkSoundEngine.setStateCalls != 5)
            throw new Exception("throwing native call produced a return observation or changed call counts");
        Console.WriteLine("native return observer preserved original calls, uint/int values, sources and safe callback behavior");
        return 0;
    }
}
