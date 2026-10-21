using System;
using System.Collections;
using System.Collections.Generic;

internal sealed class PublicHarnessPreparation : IGameAudioOriginalStartupPreparation
{
    internal bool MarkerObserved = true;
    internal int ArmCalls;
    internal int MarkerCalls;
    internal int EngineTermCalls;
    internal int CallbackManagerTermCalls;
    internal int AbandonCalls;
    private bool prepared;

    public bool Prepared { get { return prepared; } }
    public string Refusal { get { return null; } }
    public bool NativeControlObservationFailed { get { return false; } }

    public IEnumerator PrepareBeforeExistingManagerInit()
    {
        yield return null;
        prepared = true;
    }

    public void ArmNativeMonitorBeforeInit() { ArmCalls++; }
    public void PostExactControlMarker() { MarkerCalls++; }
    public bool NativeExactControlObserved() { return MarkerObserved; }
    public void ObserveEngineTermReturned() { EngineTermCalls++; }
    public void ObserveCallbackManagerTermReturned() { CallbackManagerTermCalls++; }
    public void AbandonBeforeOriginalInit() { AbandonCalls++; }
}

internal static class PublicAudioOwnerObserverHarness
{
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static string[] Names()
    {
        var names = new string[153];
        for (int i = 0; i < names.Length; i++) names[i] = "bank_" + i.ToString("000");
        return names;
    }

    private static void Drain(IEnumerator routine)
    {
        while (routine.MoveNext()) { }
    }

    public static int Main()
    {
        GameAudioOriginalOwner.ResetForHostTest();
        GameAudioOriginalOwner.Configure(false, null, null);
        Drain(GameAudioOriginalOwner.PrepareBeforeOriginalManagerInit());
        Check(GameAudioOriginalOwner.NoAudio, "false admission leaves noAudio closed");
        Check(GameAudioOriginalOwner.ShouldSkipOriginalManagerInit(), "false admission skips the original manager");
        Check(!GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "false admission cannot claim manager startup");
        Check(!GameAudioOriginalOwner.NativeApiCallsAvailable, "native query is unavailable before a loader witness");
        Check(GameAudioOriginalOwner.CanReleaseCatalogLease(false, false, false), "pre-init/no-manager lease can release");

        GameAudioOriginalOwner.ResetForHostTest();
        var prep = new PublicHarnessPreparation();
        GameAudioOriginalOwner.Configure(true, Names(), prep);
        Check(!GameAudioOriginalOwner.NativeApiCallsAvailable, "request alone does not enable native queries");
        GameAudioOriginalOwner.RecordNativeLibraryLoaded();
        Check(GameAudioOriginalOwner.NativeApiCallsAvailable, "loader witness enables native query boundary");
        Drain(GameAudioOriginalOwner.PrepareBeforeOriginalManagerInit());
        Check(GameAudioOriginalOwner.StartupSelected, "completed preparation selects startup");
        Check(GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "first manager admission succeeds");
        Check(!GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "manager admission is one-shot");
        GameAudioOriginalOwner.RecordOriginalManagerInitReturned();

        OriginalOwnerProbeObserver.Observer.RecordBeforeEngineInit();
        Check(prep.ArmCalls == 1 && GameAudioOriginalOwner.NativeInitAttemptObserved,
            "original Init observer arms and records the native attempt");
        OriginalOwnerProbeObserver.Observer.RecordInitResult(1);
        OriginalOwnerProbeObserver.Observer.RecordInitBankResult(1, 9);
        OriginalOwnerProbeObserver.Observer.RecordInitializeMethodReturned(1);
        Check(prep.MarkerCalls == 1, "successful original Initialize return posts the control marker");
        foreach (string name in Names())
        {
            GameAudioOriginalOwner.ObserveBankRequest(name);
            GameAudioOriginalOwner.ObserveBankResult(name, 1, 1, 14, 22, false);
        }
        OriginalOwnerProbeObserver.Observer.RecordPostCallbacksReturned(0);
        OriginalOwnerProbeObserver.Observer.RecordRenderAudioReturned(1);
        Check(GameAudioOriginalOwner.Ready && !GameAudioOriginalOwner.NoAudio,
            "observed original callbacks, bank results, service frame and exact control witness open readiness");

        OriginalOwnerProbeObserver.Observer.RecordEngineTermReturned();
        Check(!GameAudioOriginalOwner.OriginalTermsReturned &&
              !GameAudioOriginalOwner.CanReleaseCatalogLease(true, true, GameAudioOriginalOwner.OriginalTermsReturned),
            "engine Term alone cannot release a post-init catalog lease");
        OriginalOwnerProbeObserver.Observer.RecordCallbackManagerTermReturned();
        Check(GameAudioOriginalOwner.OriginalTermsReturned &&
              GameAudioOriginalOwner.CanReleaseCatalogLease(true, true, GameAudioOriginalOwner.OriginalTermsReturned),
            "both original Term return witnesses allow lease release");
        Check(!GameAudioOriginalOwner.Ready && GameAudioOriginalOwner.NoAudio,
            "original Term closes readiness");

        GameAudioOriginalOwner.ResetForHostTest();
        var failedPrep = new PublicHarnessPreparation();
        GameAudioOriginalOwner.Configure(true, Names(), failedPrep);
        GameAudioOriginalOwner.RecordNativeLibraryLoaded();
        Drain(GameAudioOriginalOwner.PrepareBeforeOriginalManagerInit());
        Check(GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "failed-init scenario still uses original manager admission");
        OriginalOwnerProbeObserver.Observer.RecordBeforeEngineInit();
        OriginalOwnerProbeObserver.Observer.RecordInitResult(0);
        Check(GameAudioOriginalOwner.NativeApiCallsAvailable && GameAudioOriginalOwner.NoAudio &&
              !GameAudioOriginalOwner.Ready,
            "native Init failure leaves the safe native-query boundary open while readiness remains closed");
        Check(!GameAudioOriginalOwner.CanReleaseCatalogLease(true, true, false),
            "failed native Init still retains the bundle before both original Term returns");
        OriginalOwnerProbeObserver.Observer.RecordInitFailureTermReturned();
        Check(!GameAudioOriginalOwner.OriginalTermsReturned,
            "engine failure Term alone is not both original Term witnesses");
        OriginalOwnerProbeObserver.Observer.RecordCallbackManagerTermReturned();
        Check(GameAudioOriginalOwner.OriginalTermsReturned &&
              GameAudioOriginalOwner.CanReleaseCatalogLease(true, true, GameAudioOriginalOwner.OriginalTermsReturned),
            "failed native Init can release only after both original Term returns");

        GameAudioOriginalOwner.ResetForHostTest();
        GameAudioOriginalOwner.Configure(true, Names(), new PublicHarnessPreparation());
        GameAudioOriginalOwner.RecordNativeLibraryLoaded();
        GameAudioOriginalOwner.RecordStartupTimeout();
        Check(GameAudioOriginalOwner.NativeApiCallsAvailable && GameAudioOriginalOwner.NoAudio,
            "native API availability survives readiness failure so original shutdown remains callable");

        Console.WriteLine("PASS false admission, native query boundary, one-shot manager admission, observed original callbacks, native Init failure, both-Term lease policy, and native availability after readiness failure");
        return 0;
    }
}
