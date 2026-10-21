// Fail-closed policy for preserving only the source prefab's own Wwise listener.
// This helper does not create, register, unregister, or configure native objects.
[System.Serializable]
public sealed class OriginalWwiseCameraListenerSnapshot
{
    public bool evidenceCaptured;
    public bool sourcePairPreserved;
    public bool gameObjectIdValid;
    public bool listenerActive;
    public bool managedListObservationCaptured;
    public bool managedListContainsExactListener;
    public bool managedListContainsExactListenerBeforeDisableCaptured;
    public bool managedListContainsExactListenerBeforeDisable;
    public bool listenerInactiveAfterDisable;
    public bool managedListContainsExactListenerAfterDisableCaptured;
    public bool managedListContainsExactListenerAfterDisable;
    public bool sourceListenerTeardownObserved;
    public string gameObjectId;
    public string lifecycleState;
    public string nativeAddOutcome;
    public string nativeRemoveOutcome;
}

public interface IOriginalWwiseCameraListenerState
{
    bool ListenerStateEvidenceCaptured { get; }
    bool SourceDefaultListenerPreserved { get; }
    bool SourceDefaultListenerGameObjectIdValid { get; }
    string SourceDefaultListenerGameObjectIdText { get; }
    bool SourceDefaultListenerActive { get; }
    bool ManagedDefaultListenerObservationCaptured { get; }
    bool ManagedDefaultListenerContainsExactReference { get; }
    bool ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured { get; }
    bool ManagedDefaultListenerContainsExactReferenceBeforeDisable { get; }
    bool SourceDefaultListenerInactiveAfterDisable { get; }
    bool ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured { get; }
    bool ManagedDefaultListenerContainsExactReferenceAfterDisable { get; }
    bool SourceDefaultListenerTeardownObserved { get; }
    string SourceDefaultListenerLifecycleState { get; }
    string NativeDefaultListenerAddOutcome { get; }
    string NativeDefaultListenerRemoveOutcome { get; }
}

public static class OriginalWwiseCameraListenerContract
{
    // A listener admitted while the original engine is ready must be retired
    // through its source Unity lifecycle as soon as either readiness gate is
    // lost. This policy never performs a native operation itself.
    public static bool ShouldClosePreservedSourceListener(
        bool sourceListenerPreserved,
        bool originalAudioModeCompatible,
        bool nativeEngineInitialized)
    {
        return sourceListenerPreserved && (!originalAudioModeCompatible || !nativeEngineInitialized);
    }

    public static OriginalWwiseCameraListenerSnapshot CaptureSnapshot(IOriginalWwiseCameraListenerState source)
    {
        var snapshot = new OriginalWwiseCameraListenerSnapshot {
            lifecycleState = "owner_unavailable",
            nativeAddOutcome = "not_observed_original_wrapper_discards_AKRESULT",
            nativeRemoveOutcome = "not_observed_original_wrapper_discards_AKRESULT"
        };
        if (source == null)
            return snapshot;
        snapshot.evidenceCaptured = source.ListenerStateEvidenceCaptured;
        snapshot.sourcePairPreserved = source.SourceDefaultListenerPreserved;
        snapshot.gameObjectIdValid = source.SourceDefaultListenerGameObjectIdValid;
        snapshot.gameObjectId = source.SourceDefaultListenerGameObjectIdText ?? string.Empty;
        snapshot.listenerActive = source.SourceDefaultListenerActive;
        snapshot.managedListObservationCaptured = source.ManagedDefaultListenerObservationCaptured;
        snapshot.managedListContainsExactListener = source.ManagedDefaultListenerContainsExactReference;
        snapshot.managedListContainsExactListenerBeforeDisableCaptured =
            source.ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured;
        snapshot.managedListContainsExactListenerBeforeDisable =
            source.ManagedDefaultListenerContainsExactReferenceBeforeDisable;
        snapshot.listenerInactiveAfterDisable = source.SourceDefaultListenerInactiveAfterDisable;
        snapshot.managedListContainsExactListenerAfterDisableCaptured =
            source.ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured;
        snapshot.managedListContainsExactListenerAfterDisable =
            source.ManagedDefaultListenerContainsExactReferenceAfterDisable;
        snapshot.sourceListenerTeardownObserved = source.SourceDefaultListenerTeardownObserved;
        snapshot.lifecycleState = source.SourceDefaultListenerLifecycleState ?? "state_unavailable";
        snapshot.nativeAddOutcome = source.NativeDefaultListenerAddOutcome ?? "not_observed";
        snapshot.nativeRemoveOutcome = source.NativeDefaultListenerRemoveOutcome ?? "not_observed";
        return snapshot;
    }

    public static bool ShouldPreserveSourceDefaultListener(
        bool explicitAudioRequested,
        bool originalOwnerReady,
        bool noAudio,
        bool termsReturned,
        bool engineInitialized,
        bool sourcePrefabPinned,
        int listenerCount,
        int gameObjectCount,
        bool listenerIsDefault,
        bool listenerAndGameObjectShareCameraObject)
    {
        return explicitAudioRequested && originalOwnerReady && !noAudio && !termsReturned && engineInitialized &&
               sourcePrefabPinned && listenerCount == 1 && gameObjectCount == 1 && listenerIsDefault &&
               listenerAndGameObjectShareCameraObject;
    }

    public static bool ManagedDefaultListenerObserved(
        bool originalOwnerReady,
        bool noAudio,
        bool engineInitialized,
        bool sourceListenerActive,
        bool sourceListenerDefault,
        bool sourceAkGameObjectLive,
        bool validWwiseObjectId,
        bool exactListenerReferenceInOriginalDefaultList)
    {
        return originalOwnerReady && !noAudio && engineInitialized && sourceListenerActive && sourceListenerDefault &&
               sourceAkGameObjectLive && validWwiseObjectId && exactListenerReferenceInOriginalDefaultList;
    }

    // Native success is separate from managed-list membership. The current
    // accepted listener wrapper discards this AddDefaultListener result; until
    // an exact call-result observer is integrated, this gate must stay false.
    public static bool NativeDefaultListenerRegistrationAccepted(
        bool resultObserved,
        string resultName,
        bool resultBelongsToOwnedSourceListener,
        bool duplicateNativeAddOccurred)
    {
        return resultObserved && resultName == "AK_Success" && resultBelongsToOwnedSourceListener &&
               !duplicateNativeAddOccurred;
    }

    public static bool SpatialPcmClaimAllowed(
        bool originalOwnerReady,
        bool noAudio,
        bool managedDefaultListenerObserved,
        bool nativeDefaultListenerRegistrationAccepted,
        bool emitterUsesDefaultListener,
        bool sourceEventCompleted,
        bool passivePcmWindowBoundToSameAttempt,
        bool finiteNonzeroPcmObserved)
    {
        return originalOwnerReady && !noAudio && managedDefaultListenerObserved &&
               nativeDefaultListenerRegistrationAccepted && emitterUsesDefaultListener && sourceEventCompleted &&
               passivePcmWindowBoundToSameAttempt && finiteNonzeroPcmObserved;
    }
}
