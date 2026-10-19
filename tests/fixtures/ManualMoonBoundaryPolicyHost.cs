using System;

internal static class ManualMoonBoundaryPolicyHost
{
    static void Require(bool value, string message)
    {
        if (!value)
            throw new InvalidOperationException(message);
    }

    static int Main()
    {
        Require(!ManualMoonBoundary.HoldAutomaticProgression(false, -1), "Disabled gate must remain open");
        Require(!ManualMoonBoundary.HoldAutomaticProgression(false, int.MaxValue), "Disabled gate must remain open at large counts");
        Require(!ManualMoonBoundary.HoldAutomaticProgression(true, -1), "Negative count must not hold");
        Require(!ManualMoonBoundary.HoldAutomaticProgression(true, 0), "Zero transitions must not hold");
        Require(!ManualMoonBoundary.HoldAutomaticProgression(true, 3), "Gate must remain open below four transitions");
        Require(ManualMoonBoundary.HoldAutomaticProgression(true, 4), "Gate must hold at four transitions");
        Require(ManualMoonBoundary.HoldAutomaticProgression(true, int.MaxValue), "Gate must remain held above four transitions");

        Require(!ManualMoonBoundary.RefuseTransport(false, 4, "moon2"), "Disabled policy must preserve prior Moon transport");
        Require(!ManualMoonBoundary.RefuseTransport(true, 3, "skymeadow"), "Unrelated route below boundary must pass");
        Require(ManualMoonBoundary.RefuseTransport(true, 3, "moon2"), "Exact Moon destination must refuse early");
        Require(ManualMoonBoundary.RefuseTransport(true, 4, "skymeadow"), "Any destination must refuse at boundary");
        Require(ManualMoonBoundary.RefuseTransport(true, int.MaxValue, "other-stage"), "Any destination must refuse above boundary");
        Require(!ManualMoonBoundary.RefuseTransport(true, 3, "moon2-alt"), "Policy must not guess from a Moon-like name");
        Require(!ManualMoonBoundary.RefuseTransport(true, 3, "Moon2"), "Policy must match the exact native destination key");
        Require(!ManualMoonBoundary.RefuseTransport(true, 3, null), "Missing destination must not be guessed");
        Require(!ManualMoonBoundary.RefuseTransport(true, 3, string.Empty), "Empty destination must not be guessed");

        Require(!ManualMoonBoundary.FinishObservation(false, float.PositiveInfinity), "Disabled observation must not finish");
        Require(!ManualMoonBoundary.FinishObservation(true, 0f), "Observation must not finish at entry");
        Require(!ManualMoonBoundary.FinishObservation(true, 30f), "Observation boundary is exclusive");
        Require(ManualMoonBoundary.FinishObservation(true, 30.001f), "Observation must finish after thirty seconds");
        Require(!ManualMoonBoundary.FinishObservation(true, float.NaN), "NaN elapsed time must not finish");

        Console.WriteLine("PASS exact production ManualMoonBoundary policy cases");
        return 0;
    }
}
