using System;
using System.Reflection;

internal static class PreservedBootstrapReflectionHarness
{
    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static bool HasPreserve(MemberInfo member)
    {
        foreach (object attribute in member.GetCustomAttributes(false))
            if (attribute.GetType().FullName == "UnityEngine.Scripting.PreserveAttribute")
                return true;
        return false;
    }

    public static int Main(string[] args)
    {
        if (args.Length != 1) throw new ArgumentException("expected bootstrap overlay assembly path");
        var assembly = Assembly.LoadFrom(args[0]);
        var owner = assembly.GetType("OriginalGameAudioPassivePcmOwner", true, false);
        var property = owner.GetProperty("ProcessLifetimeOwner", BindingFlags.NonPublic | BindingFlags.Static);
        var register = owner.GetMethod("RegisterMusicBeforeTerm", BindingFlags.NonPublic | BindingFlags.Static);
        var unrelated = owner.GetMethod("CreateForAcceptedBootstrap", BindingFlags.NonPublic | BindingFlags.Static);
        Require(HasPreserve(owner), "reflection-bound bootstrap owner type is not preserved");
        Require(property != null, "reflection-bound owner property is missing");
        Require(property.GetMethod != null && HasPreserve(property.GetMethod), "reflection-bound getter is not preserved");
        Require(register != null && HasPreserve(register), "reflection-bound registration method is not preserved");
        Require(unrelated != null && !HasPreserve(unrelated), "preservation scope expanded to an unrelated method");
        Console.WriteLine("PASS: exact reflection-bound bootstrap members carry Unity Preserve metadata");
        return 0;
    }
}
