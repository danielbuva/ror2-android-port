using System;

internal static class NativeSourceBindingWitnessHost
{
    static void Require(bool value, string message)
    {
        if (!value)
            throw new Exception(message);
    }

    static string Format(bool sceneMatches, bool sceneValid, bool sceneLoaded, bool activeMatches, bool componentAlive, bool ownerAlive,
                         bool ownerSceneMatches, string requested, string bound, string active, string owner)
    {
        return NativeSourceBindingWitnessFormatter.Format("WakeAltar.WakeController.bronzeDropTable", 71, 72, componentAlive ? 71 : 0,
                                                          ownerAlive ? 72 : 0, sceneMatches, sceneValid, sceneLoaded, activeMatches,
                                                          componentAlive, ownerAlive, ownerSceneMatches, requested, bound, active, owner);
    }

    public static int Main()
    {
        string ok = Format(true, true, true, true, true, true, true, "lakes", "lakes", "lakes", "lakes");
        Require(ok.StartsWith("Borrowed native source table owner lost its exact scene component;"), "failure prefix changed");
        Require(ok.Contains("binding=WakeAltar.WakeController.bronzeDropTable") && ok.Contains("componentId=71/71") &&
                    ok.Contains("gameObjectId=72/72"),
                "binding identity missing");
        Require(ok.Contains("requestedMatchesBound=True") && ok.Contains("requestedSceneValid=True") &&
                    ok.Contains("requestedSceneLoaded=True") && ok.Contains("activeSceneMatchesRequested=True") &&
                    ok.Contains("componentAlive=True") && ok.Contains("ownerAlive=True") && ok.Contains("ownerSceneMatchesRequested=True"),
                "healthy predicates missing");

        string missing = Format(true, true, true, true, false, false, false, "lakes", "lakes", "lakes", "<unavailable>");
        Require(missing.Contains("componentId=71/0") && missing.Contains("gameObjectId=72/0") && missing.Contains("componentAlive=False") &&
                    missing.Contains("ownerAlive=False") && missing.Contains("ownerSceneMatchesRequested=False"),
                "fake-null owner is not distinguishable");

        string wrongScene = Format(false, true, true, true, true, true, false, "golemplains", "lakes", "golemplains", "lakes");
        Require(wrongScene.Contains("requestedMatchesBound=False") && wrongScene.Contains("requestedScene=golemplains") &&
                    wrongScene.Contains("boundScene=lakes") && wrongScene.Contains("ownerSceneMatchesRequested=False"),
                "changed requested scene is not distinguishable");

        string invalid = Format(false, false, false, false, true, true, true, "<invalid>", "lakes", "<invalid>", "lakes");
        Require(invalid.Contains("requestedSceneValid=False") && invalid.Contains("requestedSceneLoaded=False") &&
                    invalid.Contains("activeSceneMatchesRequested=False") && invalid.Contains("requestedScene=<invalid>"),
                "invalid/unloaded scene state is not distinguishable");

        string unloaded = Format(true, true, false, true, true, true, true, "lakes", "lakes", "lakes", "lakes");
        Require(unloaded.Contains("requestedSceneValid=True") && unloaded.Contains("requestedSceneLoaded=False"),
                "valid but unloaded scene state is not distinguishable");

        string inactive = Format(true, true, true, false, true, true, true, "lakes", "lakes", "menu", "lakes");
        Require(inactive.Contains("activeSceneMatchesRequested=False") && inactive.Contains("activeScene=menu"),
                "active scene mismatch is not distinguishable");
        Console.WriteLine("PASS native source binding witness formatting");
        return 0;
    }
}
