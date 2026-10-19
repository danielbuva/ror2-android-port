// Pure, default-off gate for the narrowly scoped source-stage diagnostic attempt.
namespace LabPort.SourceStageLifecycle
{
internal static class FirstStageDiagnosticGate
{
    internal static bool Requested(bool integratedWorld, bool explicitAttempt)
    {
        return integratedWorld && explicitAttempt;
    }

    internal static bool Enabled(bool integratedWorld, bool explicitAttempt, string stageName)
    {
        return Requested(integratedWorld, explicitAttempt) && IsSupportedStage(stageName);
    }

    internal static bool RefuseUnsupported(bool integratedWorld, bool explicitAttempt, string stageName)
    {
        return Requested(integratedWorld, explicitAttempt) && !IsSupportedStage(stageName);
    }

    internal static bool HasExactStageCapture(bool callbackAccepted, bool exactStage, bool exactHost, bool serverIdentity, uint capturedId,
                                              uint currentId, bool exactServerMap)
    {
        return callbackAccepted && exactStage && exactHost && serverIdentity && capturedId != 0 && capturedId == currentId &&
               exactServerMap;
    }

    internal static bool MayDisarmPopulationObserver(bool nativeStartObserved, bool populationCompleted, bool exactAbortCompleted,
                                                     bool nativeQueuesEmpty)
    {
        return !nativeStartObserved && !populationCompleted && exactAbortCompleted && nativeQueuesEmpty;
    }

    internal static bool IsAssisted(bool nativeFirstStageLifecycleDiagnostic, bool developerVariantAssisted, bool debugEverAssisted)
    {
        return nativeFirstStageLifecycleDiagnostic || developerVariantAssisted || debugEverAssisted;
    }

    internal static bool NormalAcceptanceEligible(bool nativeFirstStageLifecycleDiagnostic, bool developerVariantAssisted,
                                                  bool debugEverAssisted)
    {
        return !IsAssisted(nativeFirstStageLifecycleDiagnostic, developerVariantAssisted, debugEverAssisted);
    }

    static bool IsSupportedStage(string stageName)
    {
        return stageName == "golemplains" || stageName == "lakes";
    }
}
}
