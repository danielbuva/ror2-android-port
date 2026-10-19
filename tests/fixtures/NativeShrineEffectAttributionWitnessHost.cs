using System;

static class NativeShrineEffectAttributionWitnessHost
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    public static int Main()
    {
        string excess = NativeShrineEffectAttributionWitness.Format(12, 15, 2, 1, 0, 1, 0);
        Require(excess.Contains("referenceCountBaseline=12") && excess.Contains("referenceCountFinal=15") &&
                    excess.Contains("referenceCountDelta=3") && excess.Contains("attributedDetailedPurchaseCallbacks=2") &&
                    excess.Contains("bloodCallbacks=1") && excess.Contains("healingCallbacks=0") &&
                    excess.Contains("bossCallbacks=1") && excess.Contains("restackCallbacks=0"),
                "excess mismatch witness omitted one of the operands or bounded component counters");

        string deficit = NativeShrineEffectAttributionWitness.Format(15, 12, 4, 2, 1, 1, 0);
        Require(deficit.Contains("referenceCountDelta=-3") && deficit.Contains("attributedDetailedPurchaseCallbacks=4"),
                "negative delta was hidden or normalized");

        string operation = "reason=fixture; captureError=UnavailableFixtureMember";
        string extended = NativeShrineEffectAttributionWitness.Format(12, 15, 2, 1, 0, 1, 0, operation);
        Require(extended == excess + "; nativeEffectOperationWitness=" + operation,
                "diagnostic evidence replaced or reordered the original attribution failure");
        Require(NativeShrineEffectAttributionWitness.Format(12, 15, 2, 1, 0, 1, 0, null) == excess,
                "absent diagnostic evidence changed the ordinary attribution failure");

        Console.WriteLine("PASS shrine effect mismatch values and callback attribution formatting");
        return 0;
    }
}
