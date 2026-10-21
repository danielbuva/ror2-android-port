using System;

public static class OriginalMusicStartupTriggerContractHarness
{
    static int assertions;

    static bool Gate(bool request = true, bool owner = true, bool audio = true,
        bool noAudio = false, bool engine = true, bool terms = false,
        bool stopped = false, bool failed = false, bool cleanup = false,
        bool preload = true, bool singleton = true, bool controllerActive = true,
        bool addExpected = true, bool resultSeen = true, bool accepted = true,
        int result = 1, int success = 1, bool deviceValid = true,
        bool mismatch = false, bool sameOutputOwner = true, bool attempted = false)
    {
        return OriginalMusicControllerContract.MayActivate(request, owner,
            audio, noAudio, engine, terms, stopped, failed, cleanup, preload,
            singleton, controllerActive, addExpected, resultSeen, accepted,
            result, success, deviceValid, mismatch, sameOutputOwner, attempted);
    }

    static void Check(bool condition, string label)
    {
        assertions++;
        if (!condition)
            throw new Exception("FAIL: " + label);
    }

    public static int Main()
    {
        Check(Gate(), "all exact owner-scoped prerequisites permit one activation");
        Check(!Gate(request: false), "explicit request defaults off");
        Check(!Gate(owner: false), "owner must be the active process owner");
        Check(!Gate(audio: false), "source audio readiness required");
        Check(!Gate(noAudio: true), "noAudio refuses activation");
        Check(!Gate(engine: false), "native engine must remain initialized");
        Check(!Gate(terms: true), "returned Terms refuses activation");
        Check(!Gate(stopped: true), "stop request refuses activation");
        Check(!Gate(failed: true), "owner failure refuses activation");
        Check(!Gate(cleanup: true), "cleanup request refuses activation");
        Check(!Gate(preload: false), "source preload must return");
        Check(!Gate(singleton: false), "same source singleton required");
        Check(!Gate(controllerActive: false), "source controller must stay active");
        Check(!Gate(addExpected: false), "source AddOutput lifecycle must be expected");
        Check(!Gate(resultSeen: false), "unknown AddOutput result refuses activation");
        Check(!Gate(accepted: false), "failed AddOutput refuses activation");
        Check(!Gate(result: 2), "result code must equal native AK_Success");
        Check(!Gate(deviceValid: false), "accepted output device identity required");
        Check(!Gate(mismatch: true), "observer owner ambiguity refuses activation");
        Check(!Gate(sameOutputOwner: false), "AddOutput result must join exact controller");
        Check(!Gate(attempted: true), "prior process activation refuses another dispatch");

        bool claimed = false;
        int originalComponentOnEnableCalls = 0;
        Check(OriginalMusicControllerContract.TryClaimActivation(ref claimed, Gate()),
            "first qualified process activation claims the one-shot");
        if (claimed)
            originalComponentOnEnableCalls++; // Mock exact original OnEnable seam.
        Check(claimed && originalComponentOnEnableCalls == 1,
            "one activation dispatches one original component callback");
        Check(!OriginalMusicControllerContract.TryClaimActivation(ref claimed, Gate()),
            "same-process re-entry does not claim again");
        Check(originalComponentOnEnableCalls == 1,
            "re-entry does not dispatch duplicate callback");

        bool refusedClaim = false;
        Check(!OriginalMusicControllerContract.TryClaimActivation(
                ref refusedClaim, Gate(resultSeen: false)),
            "unknown output leaves activation unclaimed");
        Check(!refusedClaim, "refused gate does not consume the one-shot claim");
        Console.WriteLine("PASS: " + assertions + " adapted original music startup gate assertions");
        return 0;
    }
}
