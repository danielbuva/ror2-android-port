using System;

internal static class PassivePcmGameplayGateHarness
{
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    public static int Main()
    {
        bool integratedResults = false; // Results profile is not a gameplay-start witness.
        Check(!integratedResults, "fixture must reproduce the observed report shape");
        Check(GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "integrated-world-playing", 35.324f),
            "real integrated world must arm even while results profile is false");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            false, false, true, "integrated-world-playing", 35.324f),
            "default-off selection must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, true, true, "integrated-world-playing", 35.324f),
            "attempted boundary must be one-shot");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, false, "integrated-world-playing", 35.324f),
            "non-integrated run must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "body-spawned", 35.324f),
            "pre-world phase must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "integrated-world-playing", 0f),
            "zero world time must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "integrated-world-playing", -1f),
            "negative world time must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "integrated-world-playing", float.NaN),
            "NaN world time must not arm");
        Check(!GameAudioOriginalPassivePcmGameplayGate.ShouldRequestArm(
            true, false, true, "integrated-world-playing", float.PositiveInfinity),
            "infinite world time must not arm");
        Console.WriteLine("PASS PCM gameplay gate: authoritative phase/time, false-results report, off, one-shot, invalid-world refusals");
        return 0;
    }
}
