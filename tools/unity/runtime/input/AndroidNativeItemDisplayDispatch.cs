using System;

// Pure policy shared by the source-skin owner and item-display session.
public static class AndroidNativeItemDisplayDispatch
{
    public struct OwnerEvidence
    {
        public object expectedBody, ownerBody, expectedModel, ownerModel, expectedReport, ownerReport;
        public object expectedController, liveController, expectedAvatar, liveAvatar;
        public int expectedSelectedIndex, liveSelectedIndex;
        public bool componentActive, modelEnabled, modelActive, skinControllerEnabled;
        public bool reportRequested, reportAttached, reportNativeOwnersActive, selectedSkinReady, animatorInitialized;
        public bool selectedIndexMatches, notDeactivatedOrDestroyed, noFailure;
    }

    public static bool IsExactReadyOwner(OwnerEvidence evidence)
    {
        return evidence.expectedBody != null && ReferenceEquals(evidence.expectedBody, evidence.ownerBody) &&
               evidence.expectedModel != null && ReferenceEquals(evidence.expectedModel, evidence.ownerModel) &&
               evidence.expectedReport != null && ReferenceEquals(evidence.expectedReport, evidence.ownerReport) &&
               evidence.componentActive && evidence.modelEnabled && evidence.modelActive && evidence.skinControllerEnabled &&
               evidence.reportRequested && evidence.reportAttached && evidence.reportNativeOwnersActive &&
               evidence.selectedSkinReady && evidence.animatorInitialized && evidence.selectedIndexMatches &&
               evidence.expectedController != null && ReferenceEquals(evidence.expectedController, evidence.liveController) &&
               evidence.expectedAvatar != null && ReferenceEquals(evidence.expectedAvatar, evidence.liveAvatar) &&
               evidence.expectedSelectedIndex >= 0 && evidence.expectedSelectedIndex == evidence.liveSelectedIndex &&
               evidence.notDeactivatedOrDestroyed && evidence.noFailure;
    }

    // A requested native owner is exclusive. Losing it fails closed; the adapter
    // never takes over native writes after setup.
    public static bool AdapterMustCallNative(bool nativeOwnerRequested, bool exactOwnerActive)
    {
        if (nativeOwnerRequested && !exactOwnerActive)
            throw new InvalidOperationException("Native CharacterModel inventory ownership was lost");
        return !nativeOwnerRequested;
    }

    public static void Dispatch(bool nativeOwnerRequested, bool exactOwnerActive, Action nativeRefresh, Action present)
    {
        if (AdapterMustCallNative(nativeOwnerRequested, exactOwnerActive))
            nativeRefresh();
        present();
    }
}
