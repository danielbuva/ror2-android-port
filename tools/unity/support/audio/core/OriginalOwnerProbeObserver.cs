using System;

namespace OriginalOwnerProbeObserver
{
    // Compatibility adapter for the source-pinned R4 exact-site Cecil transform.
    // All callbacks are observational except the pre-Init latch, which fails closed.
    public static class Observer
    {
        public static bool IsExactOwnedSource(object source, object expected)
        {
            return source != null && expected != null && Object.ReferenceEquals(source, expected);
        }

        public static bool IsExactSelectedTrackSource(bool contextKnown, object source, object currentTrack)
        {
            return contextKnown && IsExactOwnedSource(source, currentTrack);
        }

        public static int IncrementBoundedCount(int value)
        {
            return value >= 1000000 ? 1000000 : (value < 0 ? 0 : value + 1);
        }

        public static Action<int> InitReturned;
        public static Action<int> InitializeMethodReturned;
        public static Action BeforeEngineInit;
        public static Action<int, uint> InitBankReturned;
        public static Action BeforeEngineTerm;
        public static int BeforeEngineTermCalls;
        public static int BeforeEngineTermSuccesses;
        public static int BeforeEngineTermFailure;
        public static string BeforeEngineTermFailureType;
        public static Action EngineTermReturned;
        public static Action CallbackManagerTermReturned;
        public static Action<int> PostCallbacksReturned;
        public static Action<int> RenderAudioReturned;
        // Optional bounded observation of the original MusicController output
        // calls. The receiver must join by exact object identity and retain only
        // scalar results; no Wwise call is made here.
        public static Action<int, object, ulong> MusicAddOutputReturned;
        public static Action<int, object, ulong> MusicRemoveOutputReturned;
        public static Action<uint, object> MusicStartIntroPostEventReturned;
        public static Action<int, object, int> MusicTrackSetStateReturned;

        public static void RecordBeforeEngineInit()
        {
            if (BeforeEngineInit == null) throw new InvalidOperationException("Native pre-Init monitor arm is not configured.");
            BeforeEngineInit();
        }

        // No handler means ordinary default-off operation. When a capture owner
        // installs this callback, a refusal must escape before original Term.
        public static void RecordBeforeEngineTerm()
        {
            BeforeEngineTermCalls++;
            if (BeforeEngineTerm == null) return;
            try
            {
                BeforeEngineTerm();
                BeforeEngineTermSuccesses++;
            }
            catch (Exception e)
            {
                BeforeEngineTermFailure = 1;
                if (string.IsNullOrEmpty(BeforeEngineTermFailureType))
                {
                    string typeName = e.GetType().FullName;
                    BeforeEngineTermFailureType = string.IsNullOrEmpty(typeName) ? "unknown" :
                        (typeName.Length <= 256 ? typeName : typeName.Substring(0, 256));
                }
                throw;
            }
        }

        public static void RecordInitResult(int result) { Safe(() => InitReturned?.Invoke(result)); }
        public static void RecordInitializeMethodReturned(int result) { Safe(() => InitializeMethodReturned?.Invoke(result)); }
        public static void RecordInitBankResult(int result, uint bankId) { Safe(() => InitBankReturned?.Invoke(result, bankId)); }
        public static void RecordInitFailureTermReturned() { Safe(() => EngineTermReturned?.Invoke()); }
        public static void RecordEngineTermReturned() { Safe(() => EngineTermReturned?.Invoke()); }
        public static void RecordCallbackManagerTermReturned() { Safe(() => CallbackManagerTermReturned?.Invoke()); }
        public static void RecordPostCallbacksReturned(int callbackCount) { Safe(() => PostCallbacksReturned?.Invoke(callbackCount)); }
        public static void RecordRenderAudioReturned(int result) { Safe(() => RenderAudioReturned?.Invoke(result)); }

        // These helpers are called only after the original API call returns.
        // Callback exceptions are contained so the observer cannot replace the
        // original return or exception path.
        public static void RecordMusicAddOutputReturned(int result, object sourceOwner, ulong outputId)
        {
            try { MusicAddOutputReturned?.Invoke(result, sourceOwner, outputId); }
            catch { }
        }

        public static void RecordMusicRemoveOutputReturned(int result, object sourceOwner, ulong outputId)
        {
            try { MusicRemoveOutputReturned?.Invoke(result, sourceOwner, outputId); }
            catch { }
        }

        // These are post-return observation hooks for the original discarded
        // values. Their callers leave the original value on the IL stack.
        public static void RecordMusicStartIntroPostEventReturned(uint playingId, object sourceOwner)
        {
            try { MusicStartIntroPostEventReturned?.Invoke(playingId, sourceOwner); }
            catch { }
        }

        // AKRESULT is an Int32-backed enum in the accepted API metadata. The
        // observer receives its unchanged stack representation as an int.
        public static void RecordMusicTrackSetStateReturned(int result, object sourceTrack, int site)
        {
            try { MusicTrackSetStateReturned?.Invoke(result, sourceTrack, site); }
            catch { }
        }

        private static void Safe(Action callback) { try { callback?.Invoke(); } catch { } }
    }
}
