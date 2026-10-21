using System;

sealed class FakeListenerState : IOriginalWwiseCameraListenerState
{
    public bool ListenerStateEvidenceCaptured => true;
    public bool SourceDefaultListenerPreserved => true;
    public bool SourceDefaultListenerGameObjectIdValid => true;
    public string SourceDefaultListenerGameObjectIdText { get; set; } = "123456789";
    public bool SourceDefaultListenerActive { get; set; }
    public bool ManagedDefaultListenerObservationCaptured { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReference { get; set; }
    public bool ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReferenceBeforeDisable { get; set; } = true;
    public bool SourceDefaultListenerInactiveAfterDisable { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReferenceAfterDisable { get; set; }
    public bool SourceDefaultListenerTeardownObserved { get; set; }
    public string SourceDefaultListenerLifecycleState { get; set; } = "deactivation_not_observed";
    public string NativeDefaultListenerAddOutcome => "not_observed_original_wrapper_discards_AKRESULT";
    public string NativeDefaultListenerRemoveOutcome => "not_observed_original_wrapper_discards_AKRESULT";
}

sealed class FakeSourceListenerLifecycle
{
    public bool preserved = true, audioModeCompatible = true, nativeInitialized = true;
    public bool stagingActive = true, listenerActive = true, exactManagedEntry = true;
    public bool beforeCaptured, beforePresent, afterCaptured, afterPresent, teardownObserved;

    public bool Poll()
    {
        if (!OriginalWwiseCameraListenerContract.ShouldClosePreservedSourceListener(
            preserved, audioModeCompatible, nativeInitialized))
            return false;
        beforeCaptured = true;
        beforePresent = exactManagedEntry;
        stagingActive = false;
        listenerActive = false;
        // Model the accepted AkAudioListener.OnDisable managed-list removal.
        exactManagedEntry = false;
        afterCaptured = true;
        afterPresent = exactManagedEntry;
        teardownObserved = !stagingActive && !listenerActive;
        return true;
    }

    public OriginalWwiseCameraListenerSnapshot Snapshot()
    {
        return OriginalWwiseCameraListenerContract.CaptureSnapshot(new FakeListenerState {
            SourceDefaultListenerActive = listenerActive,
            ManagedDefaultListenerContainsExactReference = exactManagedEntry,
            ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured = beforeCaptured,
            ManagedDefaultListenerContainsExactReferenceBeforeDisable = beforePresent,
            SourceDefaultListenerInactiveAfterDisable = !listenerActive,
            ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured = afterCaptured,
            ManagedDefaultListenerContainsExactReferenceAfterDisable = afterPresent,
            SourceDefaultListenerTeardownObserved = teardownObserved,
            SourceDefaultListenerLifecycleState = teardownObserved
                ? afterPresent ? "deactivated_managed_entry_retained" : "deactivated_managed_entry_removed"
                : "preserved_active_managed_list_member",
        });
    }
}

public static class ListenerContractHarness
{
    static int assertions;

    static void Check(bool value, string name)
    {
        assertions++;
        if (!value) throw new Exception("FAIL: " + name);
    }

    public static int Main()
    {
        var initiallyReady = new FakeSourceListenerLifecycle();
        Check(!initiallyReady.Poll() && initiallyReady.stagingActive && initiallyReady.listenerActive,
            "ready and initialized preserved listener stays active");
        var defaultOff = new FakeSourceListenerLifecycle { preserved = false, audioModeCompatible = true, nativeInitialized = false };
        Check(!defaultOff.Poll() && defaultOff.stagingActive,
            "default-off owner does not enter the preserved-listener teardown gate");
        var ownerLost = new FakeSourceListenerLifecycle { audioModeCompatible = false };
        Check(ownerLost.Poll() && !ownerLost.stagingActive && !ownerLost.listenerActive,
            "owner readiness loss deactivates source lifecycle");
        var ownerLostSnapshot = ownerLost.Snapshot();
        Check(ownerLostSnapshot.gameObjectId == "123456789" &&
              ownerLostSnapshot.managedListContainsExactListenerBeforeDisableCaptured &&
              ownerLostSnapshot.managedListContainsExactListenerBeforeDisable &&
              ownerLostSnapshot.listenerInactiveAfterDisable &&
              ownerLostSnapshot.managedListContainsExactListenerAfterDisableCaptured &&
              !ownerLostSnapshot.managedListContainsExactListenerAfterDisable &&
              ownerLostSnapshot.sourceListenerTeardownObserved &&
              ownerLostSnapshot.nativeRemoveOutcome.Contains("not_observed"),
            "owner-loss teardown snapshots exact managed removal without inventing native success");
        var nativeLost = new FakeSourceListenerLifecycle { nativeInitialized = false };
        Check(nativeLost.Poll() && !nativeLost.stagingActive && !nativeLost.listenerActive,
            "native initialized loss deactivates source lifecycle");
        var nativeLostSnapshot = nativeLost.Snapshot();
        Check(nativeLostSnapshot.managedListContainsExactListenerBeforeDisable &&
              !nativeLostSnapshot.managedListContainsExactListenerAfterDisable &&
              nativeLostSnapshot.nativeAddOutcome.Contains("not_observed") &&
              nativeLostSnapshot.nativeRemoveOutcome.Contains("not_observed"),
            "native-loss teardown preserves before/after observation and unknown native outcomes");
        var unavailable = OriginalWwiseCameraListenerContract.CaptureSnapshot(null);
        Check(!unavailable.evidenceCaptured && unavailable.lifecycleState == "owner_unavailable",
            "missing owner is represented as unknown");
        Check(unavailable.nativeAddOutcome.Contains("not_observed") && unavailable.nativeRemoveOutcome.Contains("not_observed"),
            "native registration outcomes remain unobserved without an observer");
        var removed = new FakeListenerState { ManagedDefaultListenerContainsExactReference = false,
            ManagedDefaultListenerContainsExactReferenceAfterDisable = false, SourceDefaultListenerTeardownObserved = true,
            SourceDefaultListenerLifecycleState = "deactivated_managed_entry_removed" };
        var removedSnapshot = OriginalWwiseCameraListenerContract.CaptureSnapshot(removed);
        Check(removedSnapshot.gameObjectId == "123456789" && removedSnapshot.gameObjectIdValid,
            "teardown retains the previously observed Wwise object ID");
        Check(removedSnapshot.managedListContainsExactListenerBeforeDisableCaptured &&
              removedSnapshot.managedListContainsExactListenerBeforeDisable &&
              removedSnapshot.listenerInactiveAfterDisable &&
              removedSnapshot.managedListContainsExactListenerAfterDisableCaptured &&
              !removedSnapshot.managedListContainsExactListenerAfterDisable &&
              removedSnapshot.sourceListenerTeardownObserved,
            "snapshot reports before/after managed membership and inactive state");
        Check(removedSnapshot.nativeRemoveOutcome.Contains("not_observed"),
            "managed removal is not promoted to native removal success");
        var retained = new FakeListenerState { ManagedDefaultListenerContainsExactReference = true,
            ManagedDefaultListenerContainsExactReferenceAfterDisable = true, SourceDefaultListenerTeardownObserved = true,
            SourceDefaultListenerLifecycleState = "deactivated_managed_entry_retained" };
        var retainedSnapshot = OriginalWwiseCameraListenerContract.CaptureSnapshot(retained);
        Check(retainedSnapshot.sourceListenerTeardownObserved && retainedSnapshot.managedListContainsExactListenerAfterDisable,
            "a retained managed entry is reported as a cleanup anomaly");
        var unknown = new FakeListenerState { ManagedDefaultListenerContainsExactReference = false,
            ManagedDefaultListenerContainsExactReferenceAfterDisable = false, SourceDefaultListenerTeardownObserved = false,
            SourceDefaultListenerLifecycleState = "deactivation_not_observed" };
        var unknownSnapshot = OriginalWwiseCameraListenerContract.CaptureSnapshot(unknown);
        Check(!unknownSnapshot.sourceListenerTeardownObserved && unknownSnapshot.lifecycleState == "deactivation_not_observed",
            "failed teardown observation remains unknown rather than cleared");
        var unavailableList = new FakeListenerState { ManagedDefaultListenerObservationCaptured = false,
            ManagedDefaultListenerContainsExactReference = false,
            ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured = false,
            ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured = false,
            SourceDefaultListenerTeardownObserved = false, SourceDefaultListenerLifecycleState = "deactivation_not_observed" };
        var unavailableListSnapshot = OriginalWwiseCameraListenerContract.CaptureSnapshot(unavailableList);
        Check(!unavailableListSnapshot.managedListObservationCaptured &&
              !unavailableListSnapshot.managedListContainsExactListenerBeforeDisableCaptured &&
              !unavailableListSnapshot.managedListContainsExactListenerAfterDisableCaptured,
            "failed list queries remain unknown instead of reporting absence");
        Check(OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, true, 1, 1, true, true), "preserve exact source pair when ready");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            false, true, false, false, true, true, 1, 1, true, true), "default-off does not preserve");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, false, false, false, true, true, 1, 1, true, true), "owner not ready refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, true, false, true, true, 1, 1, true, true), "no-audio state refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, true, true, true, 1, 1, true, true), "terms returned refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, false, true, 1, 1, true, true), "engine not initialized refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, false, 1, 1, true, true), "unbound prefab refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, true, 2, 1, true, true), "duplicate listeners refuse");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, true, 1, 2, true, true), "duplicate game objects refuse");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, true, 1, 1, false, true), "nondefault source listener refuses");
        Check(!OriginalWwiseCameraListenerContract.ShouldPreserveSourceDefaultListener(
            true, true, false, false, true, true, 1, 1, true, false), "misplaced listener pair refuses");

        Check(OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            true, false, true, true, true, true, true, true), "exact managed listener membership observed");
        Check(!OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            true, false, true, true, true, true, true, false), "missing list reference refuses");
        Check(!OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            true, false, true, true, true, true, false, true), "invalid object id refuses");
        Check(!OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            true, false, true, true, true, false, true, true), "missing AkGameObj refuses");
        Check(!OriginalWwiseCameraListenerContract.ManagedDefaultListenerObserved(
            true, true, true, true, true, true, true, true), "no-audio listener is not reported");

        Check(!OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            false, "AK_Success", true, false), "unobserved native result remains closed");
        Check(OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            true, "AK_Success", true, false), "exact observed native success accepted");
        Check(!OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            true, "AK_Fail", true, false), "native failure refuses");
        Check(!OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            true, "ak_success", true, false), "result names compare exactly");
        Check(!OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            true, "AK_Success", false, false), "other listener result refuses");
        Check(!OriginalWwiseCameraListenerContract.NativeDefaultListenerRegistrationAccepted(
            true, "AK_Success", true, true), "second native add refuses");

        Check(OriginalWwiseCameraListenerContract.SpatialPcmClaimAllowed(
            true, false, true, true, true, true, true, true), "all same-attempt spatial PCM gates pass");
        for (int missing = 0; missing < 6; missing++)
        {
            bool[] gates = { true, true, true, true, true, true };
            gates[missing] = false;
            Check(!OriginalWwiseCameraListenerContract.SpatialPcmClaimAllowed(
                true, false, gates[0], gates[1], gates[2], gates[3], gates[4], gates[5]),
                "spatial gate " + missing + " refuses when absent");
        }
        Check(!OriginalWwiseCameraListenerContract.SpatialPcmClaimAllowed(
            true, true, true, true, true, true, true, true), "no-audio state blocks spatial claim");
        Console.WriteLine("PASS: " + assertions + " listener lifecycle and evidence assertions");
        return 0;
    }
}
