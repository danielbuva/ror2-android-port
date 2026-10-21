using System;

namespace OriginalOwnerProbeObserver
{
    // Compatibility adapter for the source-pinned R4 exact-site Cecil transform.
    // All callbacks are observational except the pre-Init latch, which fails closed.
    public static class Observer
    {
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

        private static void Safe(Action callback) { try { callback?.Invoke(); } catch { } }
    }
}
