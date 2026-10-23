using System;

internal static class PassivePcmActivityArmPolicyHarness
{
    static void Check(bool value, string message)
    {
        if (!value) throw new Exception(message);
    }

    public static int Main()
    {
        var off = new GameAudioOriginalPassivePcmActivityArmPolicy(false, false, false);
        Check(!off.ObservePlayableWorld(true), "default-off must not arm");
        Check(!off.ObserveAuthoritySkill(true, true), "default-off callback must not arm");
        Check(!off.ArmAttempted, "default-off must not consume the request");

        // Legacy and MusicController-specific modes still arm on the same
        // existing playable-world save gate.
        var main = new GameAudioOriginalPassivePcmActivityArmPolicy(true, false, false);
        Check(!main.ObservePlayableWorld(false), "invalid world must not arm");
        Check(main.ObservePlayableWorld(true), "legacy MainOutput arms at the world boundary");
        Check(!main.ObservePlayableWorld(true), "legacy MainOutput is one-shot");
        var music = new GameAudioOriginalPassivePcmActivityArmPolicy(true, false, true);
        Check(music.ObservePlayableWorld(true), "MusicController selector keeps existing immediate timing");

        // The selected deferred MainOutput waits through the world boundary and
        // ignores both unrecognized callbacks and a callback outside playable time.
        var deferred = new GameAudioOriginalPassivePcmActivityArmPolicy(true, true, false);
        Check(!deferred.ObservePlayableWorld(true), "deferred mode must not arm early");
        Check(!deferred.ObserveAuthoritySkill(false, true), "unmatched skill is ignored");
        Check(!deferred.ObserveAuthoritySkill(true, false), "pre-playable skill is ignored");
        Check(!deferred.ArmAttempted, "invalid callback must not consume the one-shot");
        Check(deferred.ObserveAuthoritySkill(true, true), "recognized authority activity arms once");
        Check(!deferred.ObserveAuthoritySkill(true, true), "repeated/reentrant activity cannot arm twice");

        var disposed = new GameAudioOriginalPassivePcmActivityArmPolicy(true, true, false);
        disposed.Close();
        Check(!disposed.ObservePlayableWorld(true), "closed owner cannot arm from a later save");
        Check(!disposed.ObserveAuthoritySkill(true, true), "closed owner cannot arm from a late callback");
        Check(!disposed.ArmAttempted, "late callback leaves the closed owner unarmed");

        bool refused = false;
        try { new GameAudioOriginalPassivePcmActivityArmPolicy(true, true, true); }
        catch (ArgumentException) { refused = true; }
        Check(refused, "activity-deferred mode must refuse MusicController output");
        refused = false;
        try { new GameAudioOriginalPassivePcmActivityArmPolicy(false, true, false); }
        catch (ArgumentException) { refused = true; }
        Check(refused, "activity-deferred mode requires explicit PCM capture");

        Console.WriteLine("PASS integrated PCM activity policy: off, legacy/music unchanged, deferred one-shot, cleanup/refusal/reentrancy");
        return 0;
    }
}
