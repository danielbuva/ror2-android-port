using System;

namespace OriginalOwnerProbeObserver
{
    // Fixture-only return-site witness. Handlers must be configured before Init;
    // handler failures are contained so observation cannot change original flow.
    public static class Observer
    {
        public static Action<int> InitReturned;
        public static Action<int> InitializeMethodReturned;
        public static Action BeforeEngineInit;
        public static int BeforeEngineInitCalls;
        public static int BeforeEngineInitSuccesses;
        public static int BeforeEngineInitFailure;
        public static string BeforeEngineInitFailureType;
        public static Action<int, uint> InitBankReturned;
        public static Action BeforeEngineTerm;
        public static int BeforeEngineTermCalls;
        public static int BeforeEngineTermSuccesses;
        public static int BeforeEngineTermFailure;
        public static string BeforeEngineTermFailureType;
        public static Action EngineTermReturned;
        public static Action CallbackManagerTermReturned;

        public static int HasInitResult;
        public static int InitResult;
        public static int InitializeReturnCount;
        public static int InitializeMethodReturnValue;
        public static int HasInitBankResult;
        public static int InitBankResult;
        public static uint InitBankId;
        public static int EngineTermReturns;
        public static int CallbackManagerTermReturns;
        public static int FirstFailurePhase;
        public static int FirstFailureAkResult;
        public static int ObserverCallbackFailures;
        public static int PostCallbacksCallCount;
        public static int PostCallbacksLastReturnedCount;
        public static int RenderAudioCallCount;
        public static int RenderAudioLastResult;

        public static void Reset()
        {
            InitReturned = null;
            InitializeMethodReturned = null;
            BeforeEngineInit = null;
            BeforeEngineInitCalls = 0;
            BeforeEngineInitSuccesses = 0;
            BeforeEngineInitFailure = 0;
            BeforeEngineInitFailureType = string.Empty;
            InitBankReturned = null;
            BeforeEngineTerm = null;
            BeforeEngineTermCalls = 0;
            BeforeEngineTermSuccesses = 0;
            BeforeEngineTermFailure = 0;
            BeforeEngineTermFailureType = string.Empty;
            EngineTermReturned = null;
            CallbackManagerTermReturned = null;
            HasInitResult = 0;
            InitResult = 0;
            InitializeReturnCount = 0;
            InitializeMethodReturnValue = 0;
            HasInitBankResult = 0;
            InitBankResult = 0;
            InitBankId = 0;
            EngineTermReturns = 0;
            CallbackManagerTermReturns = 0;
            FirstFailurePhase = 0;
            FirstFailureAkResult = 0;
            ObserverCallbackFailures = 0;
            PostCallbacksCallCount = 0;
            PostCallbacksLastReturnedCount = 0;
            RenderAudioCallCount = 0;
            RenderAudioLastResult = 0;
        }

        public static void RecordInitializeMethodReturned(int result)
        {
            InitializeReturnCount++;
            InitializeMethodReturnValue = result;
            try { InitializeMethodReturned?.Invoke(result); }
            catch { ObserverCallbackFailures++; }
        }

        // Called immediately before the original Init call with its argument
        // still on the evaluation stack. Failure is fail-closed: the SDK Init
        // must not run unless the native pre-Init latch succeeded.
        public static void RecordBeforeEngineInit()
        {
            BeforeEngineInitCalls++;
            if (BeforeEngineInit == null)
            {
                RecordBeforeEngineInitFailure(typeof(InvalidOperationException).FullName);
                throw new InvalidOperationException("Fixture pre-Init diagnostic latch is not configured.");
            }
            try
            {
                BeforeEngineInit();
                BeforeEngineInitSuccesses++;
            }
            catch (Exception e)
            {
                RecordBeforeEngineInitFailure(e.GetType().FullName);
                throw;
            }
        }

        private static void RecordBeforeEngineInitFailure(string typeName)
        {
            BeforeEngineInitFailure = 1;
            if (string.IsNullOrEmpty(BeforeEngineInitFailureType))
                BeforeEngineInitFailureType = string.IsNullOrEmpty(typeName) ? "unknown" :
                    (typeName.Length <= 256 ? typeName : typeName.Substring(0, 256));
        }

        public static void RecordInitResult(int result)
        {
            HasInitResult = 1;
            InitResult = result;
            if (result != 1 && FirstFailurePhase == 0)
            {
                FirstFailurePhase = 1;
                FirstFailureAkResult = result;
            }
            try { InitReturned?.Invoke(result); }
            catch { ObserverCallbackFailures++; }
        }

        public static void RecordInitFailureTermReturned()
        {
            EngineTermReturns++;
            try { EngineTermReturned?.Invoke(); }
            catch { ObserverCallbackFailures++; }
        }

        public static void RecordInitBankResult(int result, uint bankId)
        {
            HasInitBankResult = 1;
            InitBankResult = result;
            InitBankId = bankId;
            if (result != 1 && FirstFailurePhase == 0)
            {
                FirstFailurePhase = 2;
                FirstFailureAkResult = result;
            }
            try { InitBankReturned?.Invoke(result, bankId); }
            catch { ObserverCallbackFailures++; }
        }

        // Called only by the transformed accepted API at the common teardown
        // entry reached by both admitted Term branches. The default-off path is
        // inert; a configured passive capture guard must prove native callback
        // removal before any original teardown mutation, or its exception escapes.
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
                    string name = e.GetType().FullName;
                    BeforeEngineTermFailureType = string.IsNullOrEmpty(name) ? "unknown" :
                        (name.Length <= 256 ? name : name.Substring(0, 256));
                }
                throw;
            }
        }

        public static void RecordEngineTermReturned()
        {
            EngineTermReturns++;
            try { EngineTermReturned?.Invoke(); }
            catch { ObserverCallbackFailures++; }
        }

        public static void RecordCallbackManagerTermReturned()
        {
            CallbackManagerTermReturns++;
            try { CallbackManagerTermReturned?.Invoke(); }
            catch { ObserverCallbackFailures++; }
        }

        public static void RecordPostCallbacksReturned(int callbackCount)
        {
            PostCallbacksCallCount++;
            PostCallbacksLastReturnedCount = callbackCount;
        }

        public static void RecordRenderAudioReturned(int result)
        {
            RenderAudioCallCount++;
            RenderAudioLastResult = result;
        }
    }
}
