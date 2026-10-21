using System;
using System.Collections.Generic;

// A readiness gate only. It never calls Init, LoadBank, PostCallbacks, RenderAudio,
// pause/focus APIs, or Term. Those remain owned by the original Wwise components.
internal sealed class GameAudioOriginalReadiness
{
    internal const int MaxPostInitControlServiceFrames = 600;
    private readonly object sync = new object();
    private readonly HashSet<string> expected;
    private readonly HashSet<string> requested = new HashSet<string>(StringComparer.Ordinal);
    private readonly Dictionary<string, BankOutcome> completed = new Dictionary<string, BankOutcome>(StringComparer.Ordinal);
    private bool selected, prepared, initSeen, initSuccess, initBankSeen, initBankSuccess;
    private bool initializeReturnSeen, initializeReturnSuccess, controlObserved, terminated, failed;
    private int initCount, initBankCount, initializeReturnCount, postServiceCount, renderServiceCount, controlPollFrames;

    private struct BankOutcome
    {
        internal readonly int Result;
        internal readonly uint Id;
        internal readonly bool ExistingManagedHandle;
        internal BankOutcome(int result, uint id, bool existingManagedHandle)
        { Result = result; Id = id; ExistingManagedHandle = existingManagedHandle; }
    }

    internal GameAudioOriginalReadiness(IEnumerable<string> expectedBankNames)
    {
        if (expectedBankNames == null) throw new ArgumentNullException(nameof(expectedBankNames));
        expected = new HashSet<string>(StringComparer.Ordinal);
        foreach (string name in expectedBankNames)
        {
            if (String.IsNullOrEmpty(name) || name.IndexOfAny(new[] { '/', '\\' }) >= 0 || !expected.Add(name))
                throw new ArgumentException("Expected bank names must be nonempty, unique file leaves.", nameof(expectedBankNames));
        }
        if (expected.Count != 153) throw new ArgumentException("The current WwiseGlobal source contract requires 153 names.", nameof(expectedBankNames));
    }

    internal bool StartupSelected { get { lock (sync) return selected && prepared && !failed && !terminated; } }
    internal bool IsReady { get { lock (sync) return ComputeReady(); } }
    internal bool NoAudio { get { lock (sync) return !ComputeReady(); } }
    internal bool Failed { get { lock (sync) return failed; } }
    internal bool ControlObserved { get { lock (sync) return controlObserved; } }
    internal int ExpectedBankCount { get { return expected.Count; } }
    internal int RequestedBankCount { get { lock (sync) return requested.Count; } }
    internal int CompletedBankCount { get { lock (sync) return completed.Count; } }

    // Called only after accepted receipts, app-private payload copy, Android resolver,
    // and native-library load are all checked. The bootstrap must not call engine Init.
    internal void SelectAndPrepare(bool userOptIn, bool receiptsAndPayloadReady, bool libraryLoaded, bool androidResolverInstalled)
    {
        lock (sync)
        {
            if (selected || prepared || initCount != 0 || terminated)
                throw new InvalidOperationException("Original audio startup selection is one-shot and must precede the manager call.");
            if (!userOptIn) return;
            selected = true;
            if (!receiptsAndPayloadReady || !libraryLoaded || !androidResolverInstalled)
            {
                failed = true;
                return;
            }
            prepared = true;
        }
    }

    internal void RecordEngineInit(int result, int successValue)
    {
        lock (sync)
        {
            if (!StartupSelected || initSeen) { failed = true; return; }
            initSeen = true; initCount++;
            initSuccess = result == successValue;
            if (!initSuccess) failed = true;
        }
    }

    internal void RecordInitBank(int result, int successValue, uint bankId)
    {
        lock (sync)
        {
            if (!StartupSelected || initBankSeen) { failed = true; return; }
            initBankSeen = true; initBankCount++;
            initBankSuccess = result == successValue && bankId != 0;
            if (!initBankSuccess) failed = true;
        }
    }

    internal void RecordInitializeReturn(bool success)
    {
        lock (sync)
        {
            initializeReturnCount++;
            if (!StartupSelected || initializeReturnSeen || !success) { failed = true; return; }
            initializeReturnSeen = true; initializeReturnSuccess = true;
        }
    }

    internal void RecordOriginalServiceFrame(bool postCallbacksReturned, bool renderAudioSucceeded)
    {
        lock (sync)
        {
            if (!StartupSelected || terminated) return;
            if (postCallbacksReturned) postServiceCount++;
            if (renderAudioSucceeded) renderServiceCount++;
            if (postCallbacksReturned && !renderAudioSucceeded) failed = true;
        }
    }

    internal void RecordExactPostInitControl(bool nativeCounterAdvanced, bool afterOriginalServiceFrame,
        bool nativeObservationFailed)
    {
        lock (sync)
        {
            if (!StartupSelected || controlObserved || postServiceCount == 0 || renderServiceCount == 0)
            { failed = true; return; }
            if (!afterOriginalServiceFrame || nativeObservationFailed)
            { failed = true; return; }
            if (nativeCounterAdvanced)
            {
                controlObserved = true;
                return;
            }
            controlPollFrames++;
            if (controlPollFrames >= MaxPostInitControlServiceFrames) failed = true;
        }
    }

    internal void RecordBankRequest(string name)
    {
        lock (sync)
        {
            if (!StartupSelected || String.IsNullOrEmpty(name) || !expected.Contains(name) || !requested.Add(name))
                failed = true;
        }
    }

    // The exact existing-handle branch is observed, but its dictionary entry can
    // represent a pending async load or a synchronous load whose native success
    // this observer did not witness. Fail closed on AlreadyLoaded until a prior
    // native success for this exact name is independently tracked.
    internal void RecordBankResult(string name, int result, int successValue, int alreadyLoadedValue,
        uint bankId, bool existingManagedHandle)
    {
        lock (sync)
        {
            if (!StartupSelected || String.IsNullOrEmpty(name) || !requested.Contains(name) || completed.ContainsKey(name))
            { failed = true; return; }
            bool success = result == successValue && bankId != 0;
            if (result == alreadyLoadedValue)
            {
                failed = true;
                return;
            }
            if (!success) { failed = true; return; }
            completed.Add(name, new BankOutcome(result, bankId, existingManagedHandle));
        }
    }

    // Called only from an observer after the original engine and callback-manager
    // Term calls return. It does not invoke or retry either call.
    internal void RecordOriginalTermsReturned(bool engineTermReturned, bool callbackManagerTermReturned)
    {
        lock (sync)
        {
            if (!engineTermReturned || !callbackManagerTermReturned) { failed = true; return; }
            terminated = true;
        }
    }

    internal void RecordTerminalFailure()
    {
        lock (sync) failed = true;
    }

    private bool ComputeReady()
    {
        if (failed || terminated || !selected || !prepared || !initSeen || !initSuccess || !initBankSeen ||
            !initBankSuccess || !initializeReturnSeen || !initializeReturnSuccess || !controlObserved ||
            initCount != 1 || initBankCount != 1 || initializeReturnCount != 1 ||
            requested.Count != expected.Count || completed.Count != expected.Count)
            return false;
        foreach (string bank in expected)
            if (!requested.Contains(bank) || !completed.ContainsKey(bank)) return false;
        return true;
    }
}
