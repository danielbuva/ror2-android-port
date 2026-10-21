// Fail-closed lifecycle policy for the accepted original MusicController prefab.
// It does not report track playback, output success, or audibility.
public static class OriginalMusicControllerContract
{
    public const string PrefabPath = "Prefabs/MusicController";
    public const string AcceptedLegacyKey = "f5a901d12172cea45ae283b8c359bff4";
    public const string OutputShareSet = "Music_Audio_Device";

    public static bool MayStart(bool explicitlyRequested, bool originalAudioReady, bool noAudio,
        bool termsReturned, bool nativeEngineInitialized, bool existingController,
        bool exactResourceKeyVerified)
    {
        return explicitlyRequested && originalAudioReady && !noAudio && !termsReturned &&
            nativeEngineInitialized && !existingController && exactResourceKeyVerified;
    }

    public static bool MayAcceptLoadCompletion(bool ownerAlive, bool stopRequested,
        bool originalAudioReady, bool noAudio, bool termsReturned, bool nativeEngineInitialized,
        bool loadSucceeded, bool withinDeadline,
        bool exactPrefabAndListenerPair)
    {
        return ownerAlive && !stopRequested && originalAudioReady && !noAudio && !termsReturned && nativeEngineInitialized &&
            loadSucceeded && withinDeadline && exactPrefabAndListenerPair;
    }

    public static bool MayReportPreloaded(bool instanceMatchesOwner, bool preloadCalled,
        bool sourceControllerActive, bool sourceControllerEnabled)
    {
        return instanceMatchesOwner && preloadCalled && sourceControllerActive && sourceControllerEnabled;
    }

    public static bool MayRunBeforeTermCleanup(bool onOwningUnityThread,
        bool asyncLoadPending, bool sourceCallbackObserverAttached,
        bool sourceCallbackRetired)
    {
        return MayRunBeforeTermCleanup(onOwningUnityThread, asyncLoadPending,
            sourceCallbackObserverAttached, sourceCallbackRetired, sourceCallbackRetirementUnknown: false);
    }

    public static bool MayRunBeforeTermCleanup(bool onOwningUnityThread,
        bool asyncLoadPending, bool sourceCallbackObserverAttached,
        bool sourceCallbackRetired, bool sourceCallbackRetirementUnknown)
    {
        return onOwningUnityThread && !asyncLoadPending && !sourceCallbackRetirementUnknown &&
            (!sourceCallbackObserverAttached || sourceCallbackRetired);
    }

    // MusicController exposes no result/identity for its private AddOutput call.
    // Never turn the prefab or controller lifecycle into output acceptance.
    public static bool NativeOutputAccepted(bool exactResultObserved, string result,
        bool sameOwnedMusicController, bool duplicateOutputAttempt)
    {
        return exactResultObserved && result == "AK_Success" && sameOwnedMusicController && !duplicateOutputAttempt;
    }

    public static bool MayClaimTrackPlayback(bool controllerReady, bool sceneTrackResolved,
        bool trackPlayResultObserved, bool relevantNativeEventObserved, bool outputAccepted,
        bool matchingRuntimeAudioCaptured)
    {
        return controllerReady && sceneTrackResolved && trackPlayResultObserved &&
            relevantNativeEventObserved && outputAccepted && matchingRuntimeAudioCaptured;
    }
    // Adapted original TriggerIntroMusicStart lifecycle gate. A successful
    // AddOutput result means the source request was queued; it does not establish
    // native output activation, event completion, playback, or audibility.
    public static bool MayActivate(bool explicitlyRequested, bool ownerAlive,
        bool sourceAudioReady, bool noAudio, bool engineInitialized,
        bool termsReturned, bool stopRequested, bool ownerFailed,
        bool ownerCleanupRequested, bool sourcePreloadReturned,
        bool sameOwnedControllerIsSingleton, bool sourceControllerActive,
        bool sourceAddOutputExpected, bool outputResultObserved,
        bool outputAccepted, int outputResultCode, int successResultCode,
        bool outputDeviceIdValid, bool outputObservationOwnerMismatch,
        bool outputBelongsToSameOwnedController, bool activationAlreadyAttempted)
    {
        return explicitlyRequested && ownerAlive && sourceAudioReady && !noAudio &&
            engineInitialized && !termsReturned && !stopRequested && !ownerFailed &&
            !ownerCleanupRequested && sourcePreloadReturned &&
            sameOwnedControllerIsSingleton && sourceControllerActive &&
            sourceAddOutputExpected && outputResultObserved && outputAccepted &&
            outputResultCode == successResultCode && outputDeviceIdValid &&
            !outputObservationOwnerMismatch && outputBelongsToSameOwnedController &&
            !activationAlreadyAttempted;
    }

    // The process-lifetime claim is latched before touching Unity lifecycle,
    // so re-entry or an exception cannot dispatch a second source trigger.
    public static bool TryClaimActivation(ref bool activationAttempted, bool gatesPass)
    {
        if (activationAttempted || !gatesPass)
            return false;
        activationAttempted = true;
        return true;
    }
}
