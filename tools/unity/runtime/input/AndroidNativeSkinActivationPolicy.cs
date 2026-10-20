// Pure selection contract for the opt-in; used by runtime owner and host tests.
public static class AndroidNativeSkinActivationPolicy
{
    public static bool ShouldActivate(bool optedIn, bool selectedSourceModel, bool noAudioBoundary,
                                      bool characterModelAuthoredEnabled, bool skinControllerAuthoredEnabled)
    {
        return optedIn && selectedSourceModel && noAudioBoundary && characterModelAuthoredEnabled &&
               skinControllerAuthoredEnabled;
    }
}
