using System;
using System.Collections.Generic;

internal static class GameAudioOriginalReadinessHarness
{
    private static List<string> Banks()
    {
        var values = new List<string>();
        for (int i = 0; i < 153; i++) values.Add("bank_" + i.ToString("000"));
        return values;
    }
    private static GameAudioOriginalReadiness Ready()
    {
        var names = Banks();
        var gate = new GameAudioOriginalReadiness(names);
        if (!gate.NoAudio) throw new Exception("default must remain unavailable");
        gate.SelectAndPrepare(true, true, true, true);
        gate.RecordEngineInit(1, 1);
        gate.RecordInitBank(1, 1, 9);
        gate.RecordInitializeReturn(true);
        gate.RecordOriginalServiceFrame(true, true);
        gate.RecordExactPostInitControl(true, true, false);
        foreach (string bank in names)
        {
            gate.RecordBankRequest(bank);
            gate.RecordBankResult(bank, 1, 1, 14, 22, false);
        }
        return gate;
    }
    public static int Main()
    {
        var names = Banks();
        var off = new GameAudioOriginalReadiness(names);
        off.SelectAndPrepare(false, false, false, false);
        if (!off.NoAudio || off.StartupSelected) throw new Exception("off path changed startup policy");
        bool badCountRejected = false;
        try { new GameAudioOriginalReadiness(names.GetRange(0, 152)); }
        catch (ArgumentException) { badCountRejected = true; }
        if (!badCountRejected) throw new Exception("153-name source contract was not enforced");

        var partial = new GameAudioOriginalReadiness(names);
        partial.SelectAndPrepare(true, true, true, true);
        partial.RecordEngineInit(1, 1); partial.RecordInitBank(1, 1, 5);
        partial.RecordInitializeReturn(true);
        partial.RecordOriginalServiceFrame(true, true); partial.RecordExactPostInitControl(true, true, false);
        foreach (string bank in names)
        {
            partial.RecordBankRequest(bank);
            if (bank != names[152]) partial.RecordBankResult(bank, 1, 1, 14, 4, false);
        }
        if (!partial.NoAudio) throw new Exception("missing one bank result opened readiness");

        var failed = Ready();
        if (!failed.IsReady || failed.NoAudio) throw new Exception("complete source evidence did not open readiness");
        failed.RecordOriginalTermsReturned(true, true);
        if (!failed.NoAudio || failed.IsReady) throw new Exception("Term must close readiness");

        var duplicate = new GameAudioOriginalReadiness(names);
        duplicate.SelectAndPrepare(true, true, true, true);
        duplicate.RecordBankRequest(names[0]); duplicate.RecordBankRequest(names[0]);
        if (!duplicate.NoAudio || !duplicate.Failed) throw new Exception("duplicate request did not fail closed");

        var falseAlreadyLoaded = new GameAudioOriginalReadiness(names);
        falseAlreadyLoaded.SelectAndPrepare(true, true, true, true);
        falseAlreadyLoaded.RecordBankRequest(names[0]);
        falseAlreadyLoaded.RecordBankResult(names[0], 14, 1, 14, 0, false);
        if (!falseAlreadyLoaded.Failed || !falseAlreadyLoaded.NoAudio) throw new Exception("unproven AlreadyLoaded was accepted");

        var pendingManagedHandle = new GameAudioOriginalReadiness(names);
        pendingManagedHandle.SelectAndPrepare(true, true, true, true);
        pendingManagedHandle.RecordBankRequest(names[0]);
        pendingManagedHandle.RecordBankResult(names[0], 14, 1, 14, 0, true);
        if (!pendingManagedHandle.Failed || !pendingManagedHandle.NoAudio)
            throw new Exception("managed dictionary membership must not prove prior native success");

        var delayedControl = new GameAudioOriginalReadiness(names);
        delayedControl.SelectAndPrepare(true, true, true, true);
        delayedControl.RecordEngineInit(1, 1); delayedControl.RecordInitBank(1, 1, 9);
        delayedControl.RecordInitializeReturn(true);
        delayedControl.RecordOriginalServiceFrame(true, true);
        delayedControl.RecordExactPostInitControl(false, true, false);
        if (delayedControl.Failed || !delayedControl.NoAudio)
            throw new Exception("a pending post-init marker poll must keep readiness closed without poisoning it");
        foreach (string bank in names)
        {
            delayedControl.RecordBankRequest(bank);
            delayedControl.RecordBankResult(bank, 1, 1, 14, 22, false);
        }
        delayedControl.RecordOriginalServiceFrame(true, true);
        delayedControl.RecordExactPostInitControl(true, true, false);
        if (!delayedControl.IsReady || delayedControl.NoAudio)
            throw new Exception("a later exact marker after another original service frame did not open readiness");

        var timedOutControl = new GameAudioOriginalReadiness(names);
        timedOutControl.SelectAndPrepare(true, true, true, true);
        timedOutControl.RecordEngineInit(1, 1); timedOutControl.RecordInitBank(1, 1, 9);
        timedOutControl.RecordInitializeReturn(true);
        for (int i = 0; i < GameAudioOriginalReadiness.MaxPostInitControlServiceFrames; i++)
        {
            timedOutControl.RecordOriginalServiceFrame(true, true);
            timedOutControl.RecordExactPostInitControl(false, true, false);
        }
        if (!timedOutControl.Failed || !timedOutControl.NoAudio)
            throw new Exception("bounded post-init marker timeout did not fail closed");

        var terminalControlFailure = new GameAudioOriginalReadiness(names);
        terminalControlFailure.SelectAndPrepare(true, true, true, true);
        terminalControlFailure.RecordEngineInit(1, 1); terminalControlFailure.RecordInitBank(1, 1, 9);
        terminalControlFailure.RecordInitializeReturn(true);
        terminalControlFailure.RecordOriginalServiceFrame(true, true);
        terminalControlFailure.RecordExactPostInitControl(false, true, true);
        if (!terminalControlFailure.Failed || !terminalControlFailure.NoAudio)
            throw new Exception("native terminal lease failure did not fail closed");

        Console.WriteLine("PASS default-off, exact 153-name contract, all-result gate, missing-result refusal, duplicate refusal, fail-closed unproven AlreadyLoaded, delayed exact control, bounded control timeout, terminal monitor failure, and Term closure");
        return 0;
    }
}
