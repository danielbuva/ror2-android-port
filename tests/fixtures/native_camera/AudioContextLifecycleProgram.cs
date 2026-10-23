using System;
static class Assertions
{
    static int checks;
    static void Check(bool value, string name) { checks++; if (!value) throw new Exception(name); }
    static void Step(AndroidNativeAudioContextStep expected, bool rig, bool context, bool music,
                     bool previouslyReady, bool expired, string name)
    {
        Check(AndroidNativeAudioCameraContextContract.EvaluateObservation(
            rig, context, music, previouslyReady, expired) == expected, name);
    }
    static void Reset(bool expected, bool attempted, bool nullRef, bool reportKnown, bool created, bool released, string name)
    {
        Check(AndroidNativeAudioCameraContextContract.CanResetAttempt(
            attempted, nullRef, reportKnown, created, released) == expected, name);
    }
    public static int Main()
    {
        Step(AndroidNativeAudioContextStep.Retire, false, true, true, false, false, "invalid source rig retires immediately");
        Step(AndroidNativeAudioContextStep.Wait, true, false, false, false, false, "startup waits for target/listener/context");
        Step(AndroidNativeAudioContextStep.Wait, true, true, false, false, false, "startup waits for fresh music observation");
        Step(AndroidNativeAudioContextStep.Ready, true, true, true, false, false, "exact context and fresh music admit");
        Step(AndroidNativeAudioContextStep.Retire, true, false, true, true, false, "lost context after admission retires");
        Step(AndroidNativeAudioContextStep.Retire, true, true, false, true, false, "lost music evidence after admission retires");
        Step(AndroidNativeAudioContextStep.Retire, true, false, false, false, true, "incomplete startup past deadline retires");
        Step(AndroidNativeAudioContextStep.Wait, true, true, false, false, false, "pre-deadline absence is not treated as failure");
        Check(AndroidNativeAudioCameraContextContract.MustRetireOnRefusal(true), "context refusal retires owned source rig");
        Check(!AndroidNativeAudioCameraContextContract.MustRetireOnRefusal(false), "visual owner keeps legacy refusal path");
        Reset(true, false, true, false, false, false, "first world starts with no attempt");
        Reset(true, true, true, true, false, false, "refused creation can retry after prior owner was never returned");
        Reset(true, true, true, true, true, true, "created owner resets only after prepared release");
        Reset(false, true, true, true, true, false, "created owner without verified release blocks reset");
        Reset(false, true, false, true, true, true, "live or fake-null managed owner reference blocks reset");
        Reset(false, false, false, false, false, false, "stale owner reference blocks even first attempt");
        Reset(false, true, true, false, false, false, "attempt without prior report blocks reset");
        Check(AndroidNativeAudioCameraContextContract.ShortFailureDetail("accepted source rig unavailable") ==
            "accepted source rig unavailable", "authored failure reason is preserved");
        Check(AndroidNativeAudioCameraContextContract.ShortFailureDetail("private/path/detail") ==
            "detail_omitted_path_like_text", "path-like failure detail is omitted");
        Check(AndroidNativeAudioCameraContextContract.ShortFailureDetail(new string('x', 220)).Length == 180,
            "failure detail is bounded");
        ReleaseChecks.Run();
        Console.WriteLine("PASS: " + checks + " production audio-context lifecycle decisions and production release checks");
        return 0;
    }
}

static class ReleaseChecks
{
    static void Check(bool value, string label) { if (!value) throw new Exception(label); }
    public static void Run()
    {
        var owner = new ProductionRelease();
        owner.ReleaseAudioContext();
        Check(!owner.audioContextReady, "release retained stale readiness");
        Check(owner.disposeCalls == 1 && owner.destroyRequests == 1, "release must deactivate once and request exact owned destroy");
        Check(owner.audioContextReleasePreparedForDestroy, "coherent inactive/listener removal evidence should qualify preparation");
        Check(owner.stagingRoot != null, "a deferred destroy request must not claim actual destruction");
        owner.ReleaseAudioContext();
        Check(owner.disposeCalls == 1 && owner.destroyRequests == 1, "release is not idempotent");
        var retired = new ProductionRelease { terminallyRetired = true };
        retired.ReleaseAudioContext();
        Check(!retired.audioContextReady && retired.disposeCalls == 0, "retired owner release must clear readiness without another disposal");
        var listenerStillPresent = new ProductionRelease { membershipPresent = true };
        listenerStillPresent.ReleaseAudioContext();
        Check(!listenerStillPresent.audioContextReleasePreparedForDestroy, "listener still present must not qualify release preparation");
        var unobserved = new ProductionRelease { membershipKnown = false };
        unobserved.ReleaseAudioContext();
        Check(!unobserved.audioContextReleasePreparedForDestroy, "unknown membership must not qualify release preparation");
        var pointer = new ProductionRelease { capturedGlobalSceneCamera = true };
        pointer.ReleaseAudioContext();
        Check(!pointer.audioContextReleasePreparedForDestroy, "unrestored scene pointer must not qualify release preparation");
        var otherMode = new ProductionRelease { audioContextOnly = false };
        bool refused = false;
        try { otherMode.ReleaseAudioContext(); } catch (InvalidOperationException) { refused = true; }
        Check(refused && otherMode.disposeCalls == 0 && otherMode.destroyRequests == 0, "visual mode must not enter context release");
    }
}
