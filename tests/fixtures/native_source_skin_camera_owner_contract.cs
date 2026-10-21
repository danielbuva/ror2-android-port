// Synthetic Unity-facing seam for the skin owner's bounded camera report.
// The full production camera owner is compiled by the exact-editor overlay
// contract; this fixture verifies that the existing lifecycle can consume its
// stable report surface without importing game/editor assemblies.
public sealed class AndroidNativeSourceCameraRigOwner : UnityEngine.MonoBehaviour, IOriginalWwiseCameraListenerState
{
    public bool ready { get; set; }
    public string status { get; set; }
    public bool ListenerStateEvidenceCaptured { get; set; } = true;
    public bool SourceDefaultListenerPreserved { get; set; } = true;
    public bool SourceDefaultListenerGameObjectIdValid { get; set; } = true;
    public string SourceDefaultListenerGameObjectIdText { get; set; } = "987654321";
    public bool throwListenerActiveRead;
    private bool listenerActive = true;
    public bool SourceDefaultListenerActive
    {
        get
        {
            if (throwListenerActiveRead)
                throw new System.InvalidOperationException("synthetic listener read failure");
            return listenerActive;
        }
        set { listenerActive = value; }
    }
    public bool ManagedDefaultListenerObservationCaptured { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReference { get; set; } = true;
    public bool ManagedDefaultListenerContainsExactReferenceBeforeDisableCaptured { get; set; }
    public bool ManagedDefaultListenerContainsExactReferenceBeforeDisable { get; set; }
    public bool SourceDefaultListenerInactiveAfterDisable { get; set; }
    public bool ManagedDefaultListenerContainsExactReferenceAfterDisableCaptured { get; set; }
    public bool ManagedDefaultListenerContainsExactReferenceAfterDisable { get; set; }
    public bool SourceDefaultListenerTeardownObserved { get; set; }
    public string SourceDefaultListenerLifecycleState { get; set; } = "preserved_active_managed_list_member";
    public string NativeDefaultListenerAddOutcome { get; set; } = "not_observed_original_wrapper_discards_AKRESULT";
    public string NativeDefaultListenerRemoveOutcome { get; set; } = "not_observed_original_wrapper_discards_AKRESULT";
}
