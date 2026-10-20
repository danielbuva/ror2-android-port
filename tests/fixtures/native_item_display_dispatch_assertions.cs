using System;

internal static class OwnerDispatchHarness
{
    static int assertions;

    static void Check(bool condition, string message)
    {
        assertions++;
        if (!condition)
            throw new Exception(message);
    }

    static AndroidNativeItemDisplayDispatch.OwnerEvidence Ready(object body, object model, object report)
    {
        var controller = new NamedObject("animHuntress");
        var avatar = new NamedObject("mdlHuntressAvatar");
        return new AndroidNativeItemDisplayDispatch.OwnerEvidence {
            expectedBody = body, ownerBody = body, expectedModel = model, ownerModel = model,
            expectedReport = report, ownerReport = report,
            expectedController = controller, liveController = controller,
            expectedAvatar = avatar, liveAvatar = avatar, expectedSelectedIndex = 4, liveSelectedIndex = 4,
            componentActive = true, modelEnabled = true, modelActive = true, skinControllerEnabled = true,
            reportRequested = true, reportAttached = true, reportNativeOwnersActive = true,
            selectedSkinReady = true, animatorInitialized = true, selectedIndexMatches = true,
            notDeactivatedOrDestroyed = true, noFailure = true
        };
    }

    sealed class NamedObject
    {
        public readonly string name;
        public NamedObject(string value) { name = value; }
    }

    static void EvidenceRejectsMismatches()
    {
        var body = new object();
        var model = new object();
        var report = new object();
        Check(AndroidNativeItemDisplayDispatch.IsExactReadyOwner(Ready(body, model, report)), "exact owner should pass");
        var other = new object();
        var evidence = Ready(body, model, report);
        evidence.ownerBody = other;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "different live body must refuse");
        evidence = Ready(body, model, report);
        evidence.expectedModel = other;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "different expected model must refuse");
        evidence = Ready(body, model, report);
        evidence.ownerReport = other;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "different report must refuse");
        evidence = Ready(body, model, report);
        evidence.componentActive = false;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "inactive owner must refuse");
        evidence = Ready(body, model, report);
        evidence.selectedIndexMatches = false;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "skin index mismatch must refuse");
        evidence = Ready(body, model, report);
        evidence.animatorInitialized = false;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "uninitialized animator must refuse");
        evidence = Ready(body, model, report);
        evidence.liveController = new NamedObject("animHuntress");
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "same-name different controller object must refuse");
        evidence = Ready(body, model, report);
        evidence.liveAvatar = new NamedObject("mdlHuntressAvatar");
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "same-name different avatar object must refuse");
        evidence = Ready(body, model, report);
        evidence.expectedSelectedIndex = 3;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "stale selected-skin snapshot index must refuse");
        evidence = Ready(body, model, report);
        evidence.notDeactivatedOrDestroyed = false;
        Check(!AndroidNativeItemDisplayDispatch.IsExactReadyOwner(evidence), "deactivated/destroyed owner must refuse");
    }

    sealed class SyntheticInventory
    {
        public event Action Changed;
        public void Raise() => Changed?.Invoke();
    }

    static void DefaultModeUsesOneManualNativeWriter()
    {
        var inventory = new SyntheticInventory();
        int nativeWrites = 0, presentations = 0;
        Action native = () => nativeWrites++;
        Action observer = () => AndroidNativeItemDisplayDispatch.Dispatch(false, false, native, () => presentations++);
        inventory.Changed += observer;
        inventory.Raise();
        Check(nativeWrites == 1 && presentations == 1, "default adapter must write natively once and present once");
        inventory.Changed -= observer;
        inventory.Raise();
        Check(nativeWrites == 1 && presentations == 1, "default cleanup must detach adapter observer");
    }

    static void OptInSourceOwnerWritesOnceAndAdapterOnlyPresents()
    {
        var inventory = new SyntheticInventory();
        int nativeWrites = 0, presentations = 0;
        bool ownerActive = true;
        Action native = () => nativeWrites++;
        // CharacterModel subscribes during OnEnable, before WorldItemDisplaySession.
        inventory.Changed += native;
        Action observer = () => AndroidNativeItemDisplayDispatch.Dispatch(true, ownerActive, native, () => presentations++);
        inventory.Changed += observer;
        // Initial native refresh after filtered rules are installed.
        native();
        Check(nativeWrites == 1, "opt-in setup must seed native displays once");
        inventory.Raise();
        Check(nativeWrites == 2 && presentations == 1, "one event must produce one native write and one presentation");
        inventory.Changed -= observer;
        inventory.Raise();
        Check(nativeWrites == 3 && presentations == 1, "observer cleanup leaves native owner sole writer");
        inventory.Changed -= native;
    }

    static void LostOwnershipRefusesWithoutFallback()
    {
        int nativeWrites = 0, presentations = 0;
        bool threw = false;
        try
        {
            AndroidNativeItemDisplayDispatch.Dispatch(true, false, () => nativeWrites++, () => presentations++);
        }
        catch (InvalidOperationException)
        {
            threw = true;
        }
        Check(threw, "lost native owner must throw");
        Check(nativeWrites == 0 && presentations == 0, "lost owner must not fall back or present stale displays");
    }

    public static int Main()
    {
        EvidenceRejectsMismatches();
        DefaultModeUsesOneManualNativeWriter();
        OptInSourceOwnerWritesOnceAndAdapterOnlyPresents();
        LostOwnershipRefusesWithoutFallback();
        Console.WriteLine("PASS " + assertions + " ownership/dispatch assertions");
        return 0;
    }
}
