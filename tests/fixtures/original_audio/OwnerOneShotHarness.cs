using System;
using System.Collections;
using System.Collections.Generic;

internal sealed class HarnessPreparation : IGameAudioOriginalStartupPreparation
{
    public bool Prepared { get; private set; }
    public string Refusal { get; private set; }
    public bool NativeControlObservationFailed => false;
    public int abandonCount;
    public IEnumerator PrepareBeforeExistingManagerInit()
    {
        yield return null;
        Prepared = true;
    }
    public void ArmNativeMonitorBeforeInit() { }
    public void PostExactControlMarker() { }
    public bool NativeExactControlObserved() => false;
    public void ObserveEngineTermReturned() { }
    public void ObserveCallbackManagerTermReturned() { }
    public void AbandonBeforeOriginalInit() { abandonCount++; }
}

internal static class OwnerOneShotHarness
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
        Check(GameAudioOriginalOwner.NoAudio, "default-off stays silent");
        Check(GameAudioOriginalOwner.ShouldSkipOriginalManagerInit(), "default-off skips original manager");
        Check(!GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "default-off cannot claim manager");
        Check(!GameAudioOriginalOwner.NativeApiCallsAvailable,
            "default-off preserves WwiseUnavailable's false IsInitialized boundary before native load");
        Check(GameAudioOriginalOwner.CanReleaseCatalogLease(false, false, false),
            "pre-manager refusal can release the bundle without nonexistent Term witnesses");
        Check(!GameAudioOriginalOwner.CanReleaseCatalogLease(true, false, false),
            "manager admission retains the bundle until both original Term witnesses return");
        Check(!GameAudioOriginalOwner.CanReleaseCatalogLease(false, true, false),
            "an actual engine Init attempt retains the bundle until both original Term witnesses return");
        Check(GameAudioOriginalOwner.CanReleaseCatalogLease(true, false, true),
            "post-start release is allowed only after both original Term witnesses return");

        GameAudioOriginalOwner.ResetForHostTest();
        var prep = new HarnessPreparation();
        GameAudioOriginalOwner.Configure(true, Names(), prep);
        Check(!GameAudioOriginalOwner.NativeApiCallsAvailable,
            "explicit selection alone cannot enable pre-library Wwise P/Invokes");
        GameAudioOriginalOwner.RecordNativeLibraryLoaded();
        Check(GameAudioOriginalOwner.NativeApiCallsAvailable,
            "native query becomes available only after the loader-return witness");
        var start = GameAudioOriginalOwner.PrepareBeforeOriginalManagerInit();
        Check(start.MoveNext(), "preparation remains asynchronous");
        Check(!GameAudioOriginalOwner.StartupSelected, "manager unavailable before prep completes");
        Check(!start.MoveNext(), "prep completes after one yield");
        Check(GameAudioOriginalOwner.StartupSelected, "original owner selected only after prep");
        Check(GameAudioOriginalOwner.NoAudio, "audio stays closed until original witnesses complete");
        Check(!GameAudioOriginalOwner.ShouldSkipOriginalManagerInit(), "selected prep admits original manager");
        Check(GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "first PortSession claims original manager");
        Check(!GameAudioOriginalOwner.TryBeginOriginalManagerInit(), "later PortSession reuses one-shot manager claim");
        GameAudioOriginalOwner.RecordOriginalManagerInitReturned();
        Check(GameAudioOriginalOwner.OriginalManagerInitReturned, "manager return is reported");
        bool refusedReconfigure = false;
        try { GameAudioOriginalOwner.Configure(true, Names(), prep); }
        catch (InvalidOperationException) { refusedReconfigure = true; }
        Check(refusedReconfigure, "process owner cannot be configured twice");
        GameAudioOriginalOwner.RecordStartupTimeout();
        Check(GameAudioOriginalOwner.HasTerminalFailure && GameAudioOriginalOwner.NoAudio,
            "bounded failure closes readiness and preserves noAudio");
        Check(GameAudioOriginalOwner.NativeApiCallsAvailable && GameAudioOriginalOwner.NoAudio,
            "truthful native query remains available after a readiness failure so original Term can run");

        Console.WriteLine("PASS default-off admission, prepare-before-manager, process one-shot reuse, readiness closure");
        return 0;
    }
}
