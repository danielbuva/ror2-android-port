using System;

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



// Last scalar admission sample for the explicitly selected audio-only source
// camera owner. Every value is paired with an observation/known flag where a
// false sample could otherwise be confused with a value that was never read.
// This DTO contains no Unity or game-object references and does not affect gates.
[Serializable]
public sealed class AndroidNativeAudioCameraAdmissionEvidence
{
    public bool startWindowSampleKnown;
    public int startWindowSampleCount;
    public float startWindowFirstRealtime, startWindowLastRealtime;
    public bool startWindowFirstRealtimeValid, startWindowLastRealtimeValid;
    public bool startWindowFirstActivityKnown, startWindowFirstActiveAndEnabled, startWindowFirstActiveInHierarchy;
    public bool startWindowFirstModeKnown, startWindowFirstModeIsNull, startWindowFirstModeIsPlayerBasic;
    public bool startWindowFirstWaitObserved;
    public float startWindowFirstWaitRealtime;
    public bool startWindowFirstWaitRealtimeValid;
    public bool startWindowFirstPlayerBasicObserved;
    public float startWindowFirstPlayerBasicRealtime;
    public bool startWindowFirstPlayerBasicRealtimeValid;
    public bool startWindowLastActivityKnown, startWindowLastActiveAndEnabled, startWindowLastActiveInHierarchy;
    public bool startWindowLastModeKnown, startWindowLastModeIsNull, startWindowLastModeIsPlayerBasic;
    public bool startWindowLastClockKnown, startWindowLastClockValid, startWindowLastDeadlineExpired;
    public bool startWindowLastAdmissionEvaluationObserved;
    public string startWindowLastStep;
    public float activationRealtime, admissionDeadlineRealtime;
    public bool activationRealtimeValid, admissionDeadlineRealtimeValid;

    public bool admissionSampleKnown;
    public int admissionSampleSequence;
    public float admissionSampleRealtime, admissionDeadlineRemainingSeconds;
    public bool admissionSampleRealtimeValid, admissionDeadlineRemainingSecondsValid;
    public bool admissionClockKnown, admissionClockValid, admissionDeadlineExpired;
    public bool noRenderStateKnown, sourceCameraDisabled, poseCameraAbsent, overrideAbsent;
    public bool rigInventoryKnown;
    public int rigInventoryCount;
    public bool soleOwnedRigIndexZeroKnown, soleOwnedRigIndexZero;
    public bool exactRigKnown, exactRig;
    public bool rigActiveKnown, rigActiveAndEnabled, rigActiveInHierarchy;
    public bool playerBasicModeKnown, playerBasicMode;
    public bool viewerNullKnown, viewerNull, localUserViewerNullKnown, localUserViewerNull;
    public bool hudAbsentKnown, hudAbsent;
    public bool nextTargetKnown, nextTargetMatchesBody, rigSceneCameraMatchesViewKnown, rigSceneCameraMatchesView;
    public bool sceneCameraKnown, sceneCameraActive, sceneCameraMatchesView, sceneCameraOwnsRig;
    public bool bodyTeamKnown, bodyTeamPresent, targetTeamMatchesBody;
    public bool targetReadyKnown, targetReady;
    public bool originalContextProbeAvailable, originalContextResultKnown, originalContextReady;
    public bool markerObservationRequested, markerPresentKnown, markerPresent, markerActiveKnown, markerActive;
    public bool markerBindingKnown, markerBoundToRig, markerBoundToTarget, markerBoundToProvider;
    public bool markerDelegateKnown, markerDelegatePresent;
    public bool markerContextLatchKnown, markerContextLatchReady, markerPumpCountKnown;
    public int markerPumpCount;
    public bool markerCaptureErrorObserved;
    public string markerCaptureError;
    public bool providerActiveKnown, providerActive, applicationKnown, applicationPresent;
    public bool applicationActiveKnown, applicationActive, deltaTimeKnown, deltaTimeNonzero;
    public float deltaTime;
    public bool deltaTimeValid;
    public bool cutsceneKnown, cutscene;
    public bool listenerPreservedKnown, listenerPreserved;
    public bool listenerComponentKnown, listenerComponentPresent;
    public bool listenerBehaviourActiveKnown, listenerBehaviourActive;
    public bool listenerActiveKnown, listenerActive;
    public bool listenerMembershipKnown, listenerMembership;
    public bool musicSnapshotKnown, musicSnapshotRefreshObserved;
    public bool musicRequested, musicSourceAudioReady, musicEngineInitialized, musicNoAudio, musicTermsReturned;
    public bool musicStaticInstanceMatches, musicObservationOwnerAlive, musicObservationSucceeded;
    public bool musicTargetCameraInventoryNonempty, musicTargetBodyObserved;
    public float musicObservationRealtime, musicObservationAgeSeconds;
    public bool musicObservationRealtimeValid, musicObservationAgeSecondsValid;
    public bool musicFreshKnown, musicFresh, musicTargetObserved;
    public bool admissionInputsKnown, previousReady;
    public bool admissionEvaluationObserved;
    public string admissionDecision;
    // The outer instance is the last actual admission evaluation. This frozen,
    // bounded nested copy is the first one; it never points back to itself.
    public AndroidNativeAudioCameraAdmissionEvidence firstAdmissionSample;

    public AndroidNativeAudioCameraAdmissionEvidence Copy()
    {
        var copy = (AndroidNativeAudioCameraAdmissionEvidence)MemberwiseClone();
        if (firstAdmissionSample != null)
        {
            copy.firstAdmissionSample = (AndroidNativeAudioCameraAdmissionEvidence)firstAdmissionSample.MemberwiseClone();
            copy.firstAdmissionSample.SanitizeFloats();
        }
        copy.SanitizeFloats();
        return copy;
    }

    static bool IsFinite(float value)
    {
        return !float.IsNaN(value) && !float.IsInfinity(value);
    }

    static float ProjectFinite(float value, out bool valid)
    {
        valid = IsFinite(value);
        return valid ? value : 0f;
    }

    static float Sanitize(float value, ref bool valid)
    {
        bool finite = IsFinite(value);
        valid = valid && finite;
        return valid ? value : 0f;
    }

    void SanitizeFloats()
    {
        startWindowFirstRealtime = Sanitize(startWindowFirstRealtime, ref startWindowFirstRealtimeValid);
        startWindowLastRealtime = Sanitize(startWindowLastRealtime, ref startWindowLastRealtimeValid);
        startWindowFirstWaitRealtime = Sanitize(startWindowFirstWaitRealtime, ref startWindowFirstWaitRealtimeValid);
        startWindowFirstPlayerBasicRealtime = Sanitize(startWindowFirstPlayerBasicRealtime, ref startWindowFirstPlayerBasicRealtimeValid);
        activationRealtime = Sanitize(activationRealtime, ref activationRealtimeValid);
        admissionDeadlineRealtime = Sanitize(admissionDeadlineRealtime, ref admissionDeadlineRealtimeValid);
        admissionSampleRealtime = Sanitize(admissionSampleRealtime, ref admissionSampleRealtimeValid);
        admissionDeadlineRemainingSeconds = Sanitize(admissionDeadlineRemainingSeconds, ref admissionDeadlineRemainingSecondsValid);
        deltaTime = Sanitize(deltaTime, ref deltaTimeValid);
        musicObservationRealtime = Sanitize(musicObservationRealtime, ref musicObservationRealtimeValid);
        musicObservationAgeSeconds = Sanitize(musicObservationAgeSeconds, ref musicObservationAgeSecondsValid);
    }

    public void RecordStartWindowSample(float now, bool activeAndEnabled, bool activeInHierarchy,
        bool modeIsNull, bool modeIsPlayerBasic, bool clockValid, bool deadlineExpired,
        AndroidNativeAudioCameraStartStep step, float activation, float deadline)
    {
        if (!startWindowSampleKnown)
        {
            startWindowFirstRealtime = ProjectFinite(now, out startWindowFirstRealtimeValid);
            startWindowFirstActivityKnown = true;
            startWindowFirstActiveAndEnabled = activeAndEnabled;
            startWindowFirstActiveInHierarchy = activeInHierarchy;
            startWindowFirstModeKnown = true;
            startWindowFirstModeIsNull = modeIsNull;
            startWindowFirstModeIsPlayerBasic = modeIsPlayerBasic;
        }
        startWindowSampleKnown = true;
        startWindowSampleCount++;
        startWindowLastRealtime = ProjectFinite(now, out startWindowLastRealtimeValid);
        startWindowLastActivityKnown = true;
        startWindowLastActiveAndEnabled = activeAndEnabled;
        startWindowLastActiveInHierarchy = activeInHierarchy;
        startWindowLastModeKnown = true;
        startWindowLastModeIsNull = modeIsNull;
        startWindowLastModeIsPlayerBasic = modeIsPlayerBasic;
        startWindowLastClockKnown = true;
        startWindowLastClockValid = clockValid;
        startWindowLastDeadlineExpired = deadlineExpired;
        startWindowLastStep = step.ToString();
        startWindowLastAdmissionEvaluationObserved = false;
        activationRealtime = ProjectFinite(activation, out activationRealtimeValid);
        admissionDeadlineRealtime = ProjectFinite(deadline, out admissionDeadlineRealtimeValid);
        if (step == AndroidNativeAudioCameraStartStep.WaitForOriginalStart && !startWindowFirstWaitObserved)
        {
            startWindowFirstWaitObserved = true;
            startWindowFirstWaitRealtime = ProjectFinite(now, out startWindowFirstWaitRealtimeValid);
        }
        if (modeIsPlayerBasic && !startWindowFirstPlayerBasicObserved)
        {
            startWindowFirstPlayerBasicObserved = true;
            startWindowFirstPlayerBasicRealtime = ProjectFinite(now, out startWindowFirstPlayerBasicRealtimeValid);
        }
    }

    public void RecordOriginalContextResult(bool probeAvailable, bool result)
    {
        originalContextProbeAvailable = probeAvailable;
        originalContextResultKnown = probeAvailable;
        originalContextReady = probeAvailable && result;
    }

    public void RecordAdmissionEvaluationTimes(float realtime, float activation, float deadline, float deadlineRemaining)
    {
        admissionSampleRealtime = ProjectFinite(realtime, out admissionSampleRealtimeValid);
        activationRealtime = ProjectFinite(activation, out activationRealtimeValid);
        admissionDeadlineRealtime = ProjectFinite(deadline, out admissionDeadlineRealtimeValid);
        admissionDeadlineRemainingSeconds = ProjectFinite(deadlineRemaining, out admissionDeadlineRemainingSecondsValid);
    }

    public void RecordMusicObservationTimes(float observationRealtime, float observationAge, bool observationKnown)
    {
        musicObservationRealtime = ProjectFinite(observationRealtime, out musicObservationRealtimeValid);
        musicObservationAgeSeconds = ProjectFinite(observationAge, out musicObservationAgeSecondsValid);
        musicObservationRealtimeValid = musicObservationRealtimeValid && observationKnown;
        musicObservationAgeSecondsValid = musicObservationAgeSecondsValid && observationKnown;
        if (!musicObservationRealtimeValid) musicObservationRealtime = 0f;
        if (!musicObservationAgeSecondsValid) musicObservationAgeSeconds = 0f;
    }

    public void RecordMusicSnapshot(bool snapshotKnown, bool refreshed, bool requested,
        bool sourceAudioReady, bool engineInitialized, bool noAudio, bool termsReturned,
        bool staticInstanceMatches, bool observationOwnerAlive, bool observationSucceeded,
        bool targetCameraInventoryNonempty, bool targetBodyObserved,
        float observationRealtime, float observationAge, bool observationTimeKnown)
    {
        musicSnapshotKnown = snapshotKnown;
        musicSnapshotRefreshObserved = refreshed;
        musicRequested = requested;
        musicSourceAudioReady = sourceAudioReady;
        musicEngineInitialized = engineInitialized;
        musicNoAudio = noAudio;
        musicTermsReturned = termsReturned;
        musicStaticInstanceMatches = staticInstanceMatches;
        musicObservationOwnerAlive = observationOwnerAlive;
        musicObservationSucceeded = observationSucceeded;
        musicTargetCameraInventoryNonempty = targetCameraInventoryNonempty;
        musicTargetBodyObserved = targetBodyObserved;
        RecordMusicObservationTimes(observationRealtime, observationAge, observationTimeKnown);
    }

    public void RecordDeltaTime(float value, bool known)
    {
        deltaTimeKnown = known;
        deltaTime = ProjectFinite(value, out deltaTimeValid);
        deltaTimeValid = deltaTimeValid && known;
        if (!deltaTimeValid)
            deltaTime = 0f;
    }

    public void BeginAdmissionObservation(int sequence, float realtime, float activation, float deadline)
    {
        admissionSampleKnown = true;
        admissionSampleSequence = sequence;
        admissionSampleRealtime = ProjectFinite(realtime, out admissionSampleRealtimeValid);
        activationRealtime = ProjectFinite(activation, out activationRealtimeValid);
        admissionDeadlineRealtime = ProjectFinite(deadline, out admissionDeadlineRealtimeValid);
        admissionDeadlineRemainingSeconds = ProjectFinite(deadline - realtime, out admissionDeadlineRemainingSecondsValid);
        deltaTimeKnown = false;
        deltaTimeNonzero = false;
        deltaTime = 0f;
        deltaTimeValid = false;
        admissionClockKnown = false;
        admissionClockValid = false;
        admissionDeadlineExpired = false;
        startWindowLastAdmissionEvaluationObserved = false;
        noRenderStateKnown = false;
        sourceCameraDisabled = false;
        poseCameraAbsent = false;
        overrideAbsent = false;
        rigInventoryKnown = false;
        rigInventoryCount = -1;
        soleOwnedRigIndexZeroKnown = false;
        soleOwnedRigIndexZero = false;
        exactRigKnown = false;
        exactRig = false;
        rigActiveKnown = false;
        rigActiveAndEnabled = false;
        rigActiveInHierarchy = false;
        playerBasicModeKnown = false;
        playerBasicMode = false;
        viewerNullKnown = false;
        viewerNull = false;
        localUserViewerNullKnown = false;
        localUserViewerNull = false;
        hudAbsentKnown = false;
        hudAbsent = false;
        nextTargetKnown = false;
        nextTargetMatchesBody = false;
        rigSceneCameraMatchesViewKnown = false;
        rigSceneCameraMatchesView = false;
        sceneCameraKnown = false;
        sceneCameraActive = false;
        sceneCameraMatchesView = false;
        sceneCameraOwnsRig = false;
        bodyTeamKnown = false;
        bodyTeamPresent = false;
        targetTeamMatchesBody = false;
        targetReadyKnown = false;
        targetReady = false;
        originalContextProbeAvailable = false;
        originalContextResultKnown = false;
        originalContextReady = false;
        markerObservationRequested = false;
        markerPresentKnown = markerActiveKnown = false;
        markerPresent = markerActive = false;
        markerBindingKnown = markerBoundToRig = markerBoundToTarget = markerBoundToProvider = false;
        providerActiveKnown = providerActive = false;
        applicationKnown = applicationPresent = applicationActiveKnown = applicationActive = false;
        deltaTimeKnown = deltaTimeNonzero = cutsceneKnown = cutscene = false;
        deltaTime = 0f;
        deltaTimeValid = false;
        markerDelegateKnown = false;
        markerDelegatePresent = false;
        markerContextLatchKnown = false;
        markerContextLatchReady = false;
        markerPumpCountKnown = false;
        markerPumpCount = 0;
        markerCaptureErrorObserved = false;
        markerCaptureError = null;
        listenerPreservedKnown = listenerComponentKnown = listenerBehaviourActiveKnown = false;
        listenerPreserved = listenerComponentPresent = listenerBehaviourActive = false;
        listenerActiveKnown = false;
        listenerActive = false;
        listenerMembershipKnown = false;
        listenerMembership = false;
        musicSnapshotKnown = false;
        musicSnapshotRefreshObserved = false;
        musicRequested = musicSourceAudioReady = musicEngineInitialized = musicNoAudio = musicTermsReturned = false;
        musicStaticInstanceMatches = musicObservationOwnerAlive = musicObservationSucceeded = false;
        musicTargetCameraInventoryNonempty = musicTargetBodyObserved = false;
        musicObservationRealtime = 0f;
        musicObservationRealtimeValid = false;
        musicFreshKnown = false;
        musicFresh = false;
        musicObservationAgeSeconds = 0f;
        musicObservationAgeSecondsValid = false;
        musicTargetObserved = false;
        admissionInputsKnown = false;
        previousReady = false;
        admissionEvaluationObserved = false;
        admissionDecision = "not_evaluated";
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
