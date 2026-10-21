using System;
using System.Reflection;

internal static class ProviderValidationHarness
{
    private static int Main(string[] args)
    {
        string expected = args.Length == 0 ? "<null>" : args[0];
        MethodInfo validator = typeof(GameAudioOriginalAcceptedRequestProvider).GetMethod(
            "ValidateGeneratedPins", BindingFlags.NonPublic | BindingFlags.Static);
        if (validator == null) return 2;
        string actual = (string)validator.Invoke(null, null);
        if (!String.Equals(actual ?? "<null>", expected, StringComparison.Ordinal))
        {
            Console.Error.WriteLine("expected=" + expected + "; actual=" + (actual ?? "<null>"));
            return 1;
        }
        Console.WriteLine(actual ?? "PASS: generated accepted pins validated");
        return 0;
    }
}
