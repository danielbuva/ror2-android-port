using System;

public static class PhaseHost
{
    static void Need(bool ok, string message) { if (!ok) throw new Exception(message); }
    static CaptainSupplyBeaconSequence.Observation Ready(float t)
    {
        return new CaptainSupplyBeaconSequence.Observation { elapsedSeconds = t, exactCaptainOwner = true,
            exactDefaultSupplySkill = true, isolatedDiagnosticInputOwned = true };
    }
    static void Main()
    {
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", false, true) ==
                "captain-supply-beacon-conflicts-with-Siren-source-entry", "combined source-entry selector must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(false, "Commando", true, "primary", true) == null,
            "default-off selector must not inspect unused options");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", false) == null,
            "exact Captain default mode should be accepted");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Commando", false, "", false) ==
                "captain-supply-beacon-requires-Captain", "wrong target must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", true, "", false) ==
                "captain-supply-beacon-requires-default-loadout", "variant override must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "special", false) ==
                "captain-supply-beacon-conflicts-with-slot-isolation", "slot isolation must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", true) ==
                "captain-supply-beacon-conflicts-with-Toolbot-offhand", "Toolbot mode must refuse");

        var s = new CaptainSupplyBeaconSequence();
        var o = Ready(0); o.specialCanExecute = true;
        var d = s.Step(o);
        Need(d.phase == CaptainSupplyBeaconSequence.Phase.AwaitingSpecialEdgeAndCallbacks && d.requestInputSlot == 3 && s.Requests == 1,
            "native-ready special must request exactly slot 3");
        o = Ready(.3f); o.specialInputEdge = true; o.specialAuthorityCallback = true; o.specialServerCallback = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingSetupAndSlotRemap,
            "special needs input-bank edge and both native callbacks");
        o = Ready(.4f); o.setupSupplyDropState = true; o.setupPrimaryIsSupplyDrop1 = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingSetupAndSlotRemap,
            "partial slot remap must not advance");
        o.setupSecondaryIsSupplyDrop2 = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingValidPlacement,
            "exact original setup state and both auxiliary slot remaps are required");
        o = Ready(.5f); o.setupSupplyDropState = true; o.setupPrimaryIsSupplyDrop1 = true; o.setupSecondaryIsSupplyDrop2 = true;
        o.nativePlacementValid = true; o.supplyDrop1CanExecute = true;
        d = s.Step(o);
        Need(d.phase == CaptainSupplyBeaconSequence.Phase.AwaitingSupplyEdgeAndCallbacks && d.requestInputSlot == 0 && s.Requests == 2,
            "valid placement must request only the original primary edge");
        o = Ready(.8f); o.supplyDrop1InputEdge = true; o.supplyDrop1AuthorityCallback = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingSupplyEdgeAndCallbacks,
            "primary edge without server callback must not advance");
        o.supplyDrop1ServerCallback = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingNativeSupplyState,
            "supply requires primary edge and both native callbacks");
        o = Ready(1f); o.nativeCallSupplyDropHealingState = true;
        Need(s.Step(o).phase == CaptainSupplyBeaconSequence.Phase.AwaitingOwnedDeployableAndReturn,
            "native CallSupplyDropHealing state required");
        o = Ready(2f); o.nativeCallSupplyDropHealingState = true; o.ownedCaptainSupplyDropCountIncreased = true;
        Need(!s.Step(o).completed, "spawn registration without normal state return is not complete");
        o.returnedToOrdinaryBodyState = true;
        d = s.Step(o);
        Need(d.completed && d.phase == CaptainSupplyBeaconSequence.Phase.Complete && s.Requests == 2,
            "completion requires deployable registration and ordinary state return");

        Refuse("missing Captain owner", x => x.exactCaptainOwner = false, "captain-owner-changed");
        Refuse("loadout override", x => x.exactDefaultSupplySkill = false, "native-default-supply-skill-changed");
        Refuse("lost input owner", x => x.isolatedDiagnosticInputOwned = false, "diagnostic-input-owner-lost");
        Refuse("neutral cancellation", x => x.neutralRevisionChanged = true, "neutralized-request-cancelled");
        var delayed = new CaptainSupplyBeaconSequence();
        var delayedObservation = Ready(0); delayedObservation.specialCanExecute = true;
        delayed.Step(delayedObservation);
        delayedObservation = Ready(.3f); delayedObservation.setupSupplyDropState = true;
        Need(!delayed.Step(delayedObservation).refused, "native setup may be observed before the counters are sampled");
        delayedObservation = Ready(.4f); delayedObservation.specialInputEdge = true;
        delayedObservation.specialAuthorityCallback = true; delayedObservation.specialServerCallback = true;
        Need(delayed.Step(delayedObservation).phase == CaptainSupplyBeaconSequence.Phase.AwaitingSetupAndSlotRemap,
            "latched edge and callback pair advance after the original state is already visible");
        Timeout();
        Console.WriteLine("Captain supply beacon phase and refusal contracts passed");
    }

    static void Timeout()
    {
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(false, "Commando", true, "primary", true) == null,
            "default-off selector must not inspect unused options");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", false) == null,
            "exact Captain default mode should be accepted");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Commando", false, "", false) ==
                "captain-supply-beacon-requires-Captain", "wrong target must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", true, "", false) ==
                "captain-supply-beacon-requires-default-loadout", "variant override must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "special", false) ==
                "captain-supply-beacon-conflicts-with-slot-isolation", "slot isolation must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", true) ==
                "captain-supply-beacon-conflicts-with-Toolbot-offhand", "Toolbot mode must refuse");

        var s = new CaptainSupplyBeaconSequence();
        Need(!s.Step(Ready(0)).refused, "initial wait should not time out");
        var d = s.Step(Ready(8));
        Need(d.refused && d.outcome == "special-not-native-ready", "native readiness timeout must refuse");
    }

    static void Refuse(string label, Action<CaptainSupplyBeaconSequence.Observation> change, string expected)
    {
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(false, "Commando", true, "primary", true) == null,
            "default-off selector must not inspect unused options");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", false) == null,
            "exact Captain default mode should be accepted");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Commando", false, "", false) ==
                "captain-supply-beacon-requires-Captain", "wrong target must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", true, "", false) ==
                "captain-supply-beacon-requires-default-loadout", "variant override must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "special", false) ==
                "captain-supply-beacon-conflicts-with-slot-isolation", "slot isolation must refuse");
        Need(CaptainSupplyBeaconSequence.SelectorRefusal(true, "Captain", false, "", true) ==
                "captain-supply-beacon-conflicts-with-Toolbot-offhand", "Toolbot mode must refuse");

        var s = new CaptainSupplyBeaconSequence();
        var o = Ready(0); change(o);
        var d = s.Step(o);
        Need(d.refused && d.requestInputSlot == -1 && d.outcome == expected, label + " refusal changed: " + d.outcome);
    }
}
