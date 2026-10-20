public static class ObserverScopeHost
{
    static void Need(bool value, string message)
    {
        if (!value)
            throw new System.Exception(message);
    }

    public static void Run()
    {
        var observer = new CommandoPrimaryScopeHarness();
        var commando = new RoR2.CharacterBody { bodyIndex = RoR2.BodyIndex.Commando, primaryMissing = true };
        bool refused = false;
        try
        {
            observer.Update(true, commando);
        }
        catch (System.InvalidOperationException)
        {
            refused = true;
        }
        Need(refused && observer.commandoObserverCalls == 1,
             "Commando still enters the strict primary observer and refuses a missing primary");

        observer = new CommandoPrimaryScopeHarness();
        var toolbot = new RoR2.CharacterBody { bodyIndex = RoR2.BodyIndex.Toolbot, primaryMissing = true };
        observer.Update(true, toolbot);
        Need(observer.commandoObserverCalls == 0 && observer.readinessReads == 0 && observer.hudPrimaryReads == 0,
             "Toolbot spine skips every Commando-only primary observer/readiness/HUD read");
        Need(observer.genericCoverageTicks == 1, "generic survivor skill coverage continues for Toolbot");

        observer = new CommandoPrimaryScopeHarness();
        observer.Update(false, commando);
        Need(observer.commandoObserverCalls == 0 && observer.readinessReads == 0 && observer.hudPrimaryReads == 0,
             "a Commando outside the playable-spine case does not enter this diagnostic");
        System.Console.WriteLine("PASS: Commando primary observer scope");
    }
}
