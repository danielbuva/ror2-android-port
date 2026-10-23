// Pure fail-closed contract for an opt-in, original-prefab view-only camera.
public static class AndroidNativeSourceCameraRigContract
{
    public struct Evidence
    {
        public object expectedTarget, liveTarget, expectedBody, liveBody;
        public object expectedTeam, liveTeam;
        public int activeRigsTargetingBody;
        public bool rigInventoryComplete;
        public bool rigActive, playerBasicMode, sceneCameraReady, sceneCameraComponentMatchesCamera, sceneCameraOwnsRig, cameraOwnedByRig;
        public bool sprintParticleOwnerPresent, viewOnlyNoViewer, noHud, originalControlAllowed, originalHudAllowed;
        public bool audioComponentPolicySatisfied, viewReady, overrideOwned;
    }

    public static bool ShouldCreate(bool explicitlyRequested, bool selectedSourceModel, bool actualModel)
    {
        return explicitlyRequested && selectedSourceModel && actualModel;
    }

    public static bool CanCreateDedicatedRig(bool explicitlyRequested, bool actualSourceModel, bool audioModeCompatible,
                                             bool inventoryComplete, int existingActiveRigsForBody)
    {
        return explicitlyRequested && actualSourceModel && audioModeCompatible && inventoryComplete &&
               existingActiveRigsForBody == 0;
    }

    // Default-off is valid only while the original audio owner has not been
    // selected. Requested audio must have completed its exact readiness gate;
    // pending, failed, or terminated audio must not be mistaken for silence.
    public static bool IsAudioModeCompatible(bool noAudio, bool optInRequested, bool ready,
                                             bool terminalFailure, bool termsReturned)
    {
        if (terminalFailure || termsReturned)
            return false;
        if (ready)
            return optInRequested && !noAudio;
        return !optInRequested && noAudio;
    }

    public static bool IsReady(Evidence e, out string failure)
    {
        failure = null;
        if (e.expectedTarget == null || !ReferenceEquals(e.expectedTarget, e.liveTarget))
            failure = "view-only camera target does not match the selected body object";
        else if (e.expectedBody == null || !ReferenceEquals(e.expectedBody, e.liveBody))
            failure = "view-only camera target body does not match the selected source body";
        else if (e.expectedTeam == null || !Equals(e.expectedTeam, e.liveTeam))
            failure = "view-only camera target team is not current for the selected body";
        else if (!e.rigActive)
            failure = "original prefab view rig is not active";
        else if (!e.playerBasicMode)
            failure = "original PlayerBasic camera mode is unavailable";
        else if (!e.rigInventoryComplete || e.activeRigsTargetingBody != 1)
            failure = "selected body does not have exactly one fully observed active camera rig";
        else if (!e.sceneCameraReady || !e.sceneCameraComponentMatchesCamera || !e.sceneCameraOwnsRig || !e.cameraOwnedByRig)
            failure = "original SceneCamera is not attached to the owned prefab rig";
        else if (!e.sprintParticleOwnerPresent)
            failure = "original prefab rig lacks its SceneCamera callback owner";
        else if (!e.viewOnlyNoViewer || !e.noHud)
            failure = "view-only rig acquired an unowned viewer or HUD";
        else if (!e.originalControlAllowed || !e.originalHudAllowed)
            failure = "view-only provider blocks original control or HUD permission semantics";
        else if (!e.audioComponentPolicySatisfied)
            failure = "diagnostic view rig does not satisfy its exact default-off or preserved-source listener policy";
        else if (!e.overrideOwned)
            failure = "view-only provider does not exclusively own the rig override";
        else if (!e.viewReady)
            failure = "Nova view pose is not configured";
        return failure == null;
    }
}

public enum AndroidNativeAudioContextStep
{
    Wait,
    Ready,
    Retire
}

public enum AndroidNativeAudioCameraStartStep
{
    WaitForOriginalStart,
    Continue,
    Retire
}

public struct AndroidNativeAudioCameraStartObservation
{
    public bool rigActivityObserved, rigActiveAndEnabled, rigActiveInHierarchy;
    public bool cameraModeObserved, cameraModeIsNull, cameraModeIsPlayerBasic;
    public bool originalStartWaitObserved;
    public string gateState;
}

// Shared decisions used by the source owner and exercised by host fixtures.
// Observations themselves remain owned by the Unity-facing source component.
public static class AndroidNativeAudioCameraContextContract
{
    public static bool IsValidStartupClock(float nowRealtime, float activationRealtime, float deadlineRealtime)
    {
        return IsFinite(nowRealtime) && IsFinite(activationRealtime) && IsFinite(deadlineRealtime) &&
            nowRealtime >= activationRealtime && deadlineRealtime >= activationRealtime;
    }

    public static AndroidNativeAudioCameraStartStep EvaluateOriginalStartWindow(
        bool audioContextOnly, bool rigActiveAndEnabled, bool rigActiveInHierarchy,
        bool cameraModeIsNull, bool cameraModeIsPlayerBasic, bool previouslyReady,
        float nowRealtime, float activationRealtime, float deadlineRealtime)
    {
        if (!audioContextOnly)
            return rigActiveAndEnabled && rigActiveInHierarchy && cameraModeIsPlayerBasic
                ? AndroidNativeAudioCameraStartStep.Continue : AndroidNativeAudioCameraStartStep.Retire;
        if (!IsValidStartupClock(nowRealtime, activationRealtime, deadlineRealtime))
            return AndroidNativeAudioCameraStartStep.Retire;
        if (cameraModeIsNull && cameraModeIsPlayerBasic)
            return AndroidNativeAudioCameraStartStep.Retire;
        if (!rigActiveAndEnabled || !rigActiveInHierarchy)
            return AndroidNativeAudioCameraStartStep.Retire;
        if (cameraModeIsPlayerBasic)
            return !previouslyReady && nowRealtime >= deadlineRealtime
                ? AndroidNativeAudioCameraStartStep.Retire : AndroidNativeAudioCameraStartStep.Continue;
        if (!cameraModeIsNull || previouslyReady || nowRealtime >= deadlineRealtime)
            return AndroidNativeAudioCameraStartStep.Retire;
        return AndroidNativeAudioCameraStartStep.WaitForOriginalStart;
    }

    public static AndroidNativeAudioCameraStartObservation CreateStartObservation(
        bool rigActiveAndEnabledObserved, bool rigActiveAndEnabled,
        bool rigActiveInHierarchyObserved, bool rigActiveInHierarchy,
        bool cameraModeObserved, bool cameraModeIsNull, bool cameraModeIsPlayerBasic,
        bool originalStartWaitObserved, string gateState)
    {
        return new AndroidNativeAudioCameraStartObservation {
            rigActivityObserved = rigActiveAndEnabledObserved && rigActiveInHierarchyObserved,
            rigActiveAndEnabled = rigActiveAndEnabled,
            rigActiveInHierarchy = rigActiveInHierarchy,
            cameraModeObserved = cameraModeObserved,
            cameraModeIsNull = cameraModeIsNull,
            cameraModeIsPlayerBasic = cameraModeIsPlayerBasic,
            originalStartWaitObserved = originalStartWaitObserved,
            gateState = gateState,
        };
    }

    static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    public static AndroidNativeAudioContextStep EvaluateObservation(
        bool exactOwnedRig, bool targetContextAndListenerReady, bool freshMusicTarget,
        bool previouslyReady, bool startupDeadlineExpired)
    {
        if (!exactOwnedRig)
            return AndroidNativeAudioContextStep.Retire;
        if (previouslyReady)
            return targetContextAndListenerReady && freshMusicTarget
                ? AndroidNativeAudioContextStep.Ready : AndroidNativeAudioContextStep.Retire;
        if (startupDeadlineExpired)
            return AndroidNativeAudioContextStep.Retire;
        return targetContextAndListenerReady && freshMusicTarget
            ? AndroidNativeAudioContextStep.Ready : AndroidNativeAudioContextStep.Wait;
    }

    public static bool MustRetireOnRefusal(bool audioContextOnly) => audioContextOnly;

    public static string ShortFailureDetail(string message)
    {
        if (string.IsNullOrEmpty(message))
            return string.Empty;
        if (message.IndexOf('/') >= 0 || message.IndexOf('\\') >= 0)
            return "detail_omitted_path_like_text";
        return message.Length <= 180 ? message : message.Substring(0, 180);
    }

    public static bool CanResetAttempt(bool previousAttempted, bool previousOwnerReferenceIsClrNull,
                                       bool previousReportKnown, bool previousCreationReturnedOwner,
                                       bool previousReleasePrepared)
    {
        if (!previousOwnerReferenceIsClrNull)
            return false;
        if (!previousAttempted)
            return true;
        if (!previousReportKnown)
            return false;
        return !previousCreationReturnedOwner || previousReleasePrepared;
    }
}
