using System;
using System.Collections.Generic;

public static class MusicControllerContractHarness
{
    static int assertions;
    static void Check(bool value, string name)
    {
        assertions++;
        if (!value) throw new Exception("FAIL: " + name);
    }

    public static int Main()
    {
        Check(OriginalMusicControllerContract.MayStart(true, true, false, false, true, false, true),
            "explicit ready original audio can request the exact source controller");
        Check(!OriginalMusicControllerContract.MayStart(false, true, false, false, true, false, true), "default-off refuses");
        Check(!OriginalMusicControllerContract.MayStart(true, false, false, false, true, false, true), "pending audio refuses");
        Check(!OriginalMusicControllerContract.MayStart(true, true, true, false, true, false, true), "noAudio refuses");
        Check(!OriginalMusicControllerContract.MayStart(true, true, false, true, true, false, true), "terms returned refuses");
        Check(!OriginalMusicControllerContract.MayStart(true, true, false, false, false, false, true), "engine uninitialized refuses");
        Check(!OriginalMusicControllerContract.MayStart(true, true, false, false, true, true, true), "existing singleton refuses duplicate");
        Check(!OriginalMusicControllerContract.MayStart(true, true, false, false, true, false, false), "wrong resource key refuses");

        Check(OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, false, true, true, true, true),
            "same owner accepts timely exact successful load");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(false, false, true, false, false, true, true, true, true), "dead owner refuses callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, true, true, false, false, true, true, true, true), "shutdown request refuses callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, false, false, false, true, true, true, true), "audio readiness loss refuses callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, true, false, true, true, true, true), "noAudio refuses callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, true, true, true, true, true), "original terms refuse callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, false, false, true, true, true), "native engine loss refuses callback");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, false, true, false, true, true), "failed load refuses");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, false, true, true, false, true), "late load refuses");
        Check(!OriginalMusicControllerContract.MayAcceptLoadCompletion(true, false, true, false, false, true, true, true, false), "changed source prefab graph refuses");

        Check(OriginalMusicControllerContract.MayReportPreloaded(true, true, true, true), "source instance and Preload identity can be reported");
        Check(!OriginalMusicControllerContract.MayReportPreloaded(false, true, true, true), "foreign static instance refuses");
        Check(!OriginalMusicControllerContract.MayReportPreloaded(true, false, true, true), "missing Preload refuses");
        Check(!OriginalMusicControllerContract.MayReportPreloaded(true, true, false, true), "inactive source prefab refuses");

        Check(OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, false, false),
            "main-thread cleanup with no pending load and no source delegate is safe to continue");
        Check(OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, true, true),
            "source scene callback must retire before Term cleanup");
        Check(!OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, true, false),
            "Term-first while source callback is live refuses output removal");
        Check(!OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, true, false, false),
            "pending async prefab load refuses Term");
        Check(!OriginalMusicControllerContract.MayRunBeforeTermCleanup(false, false, false, false),
            "off-thread Term refuses Unity destruction");
        Check(!OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, false, false, true),
            "partial Preload failure keeps callback retirement unknown and refuses Term");
        Check(!OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, true, true, true),
            "observing a later event cannot turn partial Preload failure into a source-retirement claim");

        bool sourceCallbackRetired = false;
        bool controllerDestroyed = false;
        int removeOutputCalls = 0;
        var order = new List<string>();
        Action beforeTerm = () => {
            if (!OriginalMusicControllerContract.MayRunBeforeTermCleanup(true, false, true, sourceCallbackRetired))
                throw new InvalidOperationException("source callback still live");
            if (!controllerDestroyed)
            {
                controllerDestroyed = true;
                removeOutputCalls++; // Represents original OnDestroy; no direct output API call.
                order.Add("original_OnDestroy_RemoveOutput");
            }
        };
        bool TermAttempt()
        {
            try { beforeTerm(); order.Add("original_Term"); return true; }
            catch (InvalidOperationException) { return false; }
        }
        Check(!TermAttempt(), "Term-first refuses while original source callback is live");
        Check(removeOutputCalls == 0 && order.Count == 0, "refusal preserves source output and prevents Term");
        sourceCallbackRetired = true;
        Check(TermAttempt(), "retired source callback permits ordered cleanup then Term");
        Check(order.Count == 2 && order[0] == "original_OnDestroy_RemoveOutput" && order[1] == "original_Term",
            "original OnDestroy/RemoveOutput precedes exactly one Term call");
        Check(TermAttempt(), "repeat observer call remains idempotent");
        Check(removeOutputCalls == 1, "repeat pre-Term observer never duplicates source OnDestroy");

        Check(!OriginalMusicControllerContract.NativeOutputAccepted(false, "AK_Success", true, false), "unobserved AddOutput result stays closed");
        Check(OriginalMusicControllerContract.NativeOutputAccepted(true, "AK_Success", true, false), "exact observed owned output result passes contract");
        Check(!OriginalMusicControllerContract.NativeOutputAccepted(true, "AK_Fail", true, false), "native output failure refuses");
        Check(!OriginalMusicControllerContract.NativeOutputAccepted(true, "AK_Success", false, false), "different controller result refuses");
        Check(!OriginalMusicControllerContract.NativeOutputAccepted(true, "AK_Success", true, true), "duplicate output refuses");

        Check(OriginalMusicControllerContract.MayClaimTrackPlayback(true, true, true, true, true, true), "all separate playback witnesses pass");
        for (int missing = 0; missing < 6; missing++)
        {
            bool[] gates = { true, true, true, true, true, true };
            gates[missing] = false;
            Check(!OriginalMusicControllerContract.MayClaimTrackPlayback(gates[0], gates[1], gates[2], gates[3], gates[4], gates[5]),
                "playback evidence gate " + missing + " refuses");
        }
        Console.WriteLine("PASS: " + assertions + " original music owner contract assertions");
        return 0;
    }
}
