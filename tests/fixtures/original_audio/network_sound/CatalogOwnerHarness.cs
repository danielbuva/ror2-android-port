using System;
using System.Linq;
using RoR2;
using RoR2.Audio;
class CatalogOwnerHarness
{
    static int checks;
    static void Check(bool ok, string message) { checks++; if (!ok) throw new Exception(message); }
    static NetworkSoundEventDef[] Defs() => new[] {
        new NetworkSoundEventDef { name = "zeta", eventName = "event-zeta" },
        new NetworkSoundEventDef { name = "alpha", eventName = "event-alpha" }
    };
    static NetworkSoundEventDef[] AliasedDefs() => new[] {
        new NetworkSoundEventDef { name = "alias-a", eventName = "shared-event" },
        new NetworkSoundEventDef { name = "alias-b", eventName = "shared-event" }
    };
    static bool Refused(Action action, string message)
    {
        try { action(); } catch (InvalidOperationException) { return true; }
        throw new Exception(message);
    }
    static void Main(string[] args)
    {
        string scenario = args.Length == 0 ? "success" : args[0];
        if (scenario == "success")
        {
            WholeCatalogComposed.Definitions = Defs();
            NetworkSoundEventCatalog.Reset();
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && ready.initializedByOwner, "empty catalog must be initialized by native setter");
            Check(ready.preCountObserved && ready.nativeEntryCountBefore == 0 && ready.postCountObserved && ready.nativeEntryCountAfter == 2,
                "both entry-count reads must be explicitly observed");
            Check(ready.sourceDefinitionCount == 2 && ready.nativeIdMappingReady && ready.zeroNativeIdCount == 0,
                "full source family has nonzero native ID hashes");
            Check(NetworkSoundEventCatalog.setCalls == 1, "setter exactly once");
            Check(NetworkSoundEventCatalog.availability.available && ready.availabilityMadeAvailable,
                "original catalog availability transition must be preserved");
            Check(NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)0).name == "alpha" &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)1).name == "zeta",
                "native ordinal sorting owns indices");
            Check(Attribute.IsDefined(typeof(OriginalNetworkSoundEventCatalogOwner.Snapshot), typeof(SerializableAttribute)),
                "nested report DTO must be serializable");
        }
        else if (scenario == "no-audio")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = Array.Empty<NetworkSoundEventDef>();
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, true, true, false, true, true),
                "no-audio route must refuse native owner");
            Check(NetworkSoundEventCatalog.setCalls == 0, "no-audio decoder path must not mutate native catalog");
            Check(OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, true, "catalog failure", false, false),
                "no-audio path remains allowed to use its existing decoder");
        }
        else if (scenario == "foreign")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = Defs();
            var foreign = Defs().OrderBy(d => d.name, StringComparer.Ordinal).ToArray();
            for (int i = 0; i < foreign.Length; i++) foreign[i].index = (NetworkSoundEventIndex)i;
            NetworkSoundEventCatalog.Reset(foreign);
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "nonmatching nonempty catalog must refuse");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(rejected.preCountObserved && rejected.postCountObserved && rejected.nativeEntryCountAfter == 2,
                "mismatch refusal must retain observed counts");
            Check(NetworkSoundEventCatalog.setCalls == 0, "foreign nonempty catalog must not be overwritten");
        }
        else if (scenario == "zero-id")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = Defs();
            NetworkSoundEventCatalog.zeroEventName = "event-alpha";
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "zero native ID must fail usable mapping readiness");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(!rejected.ready && !rejected.nativeIdMappingReady && rejected.zeroNativeIdCount == 1 &&
                  rejected.zeroNativeIdIndices.SequenceEqual(new[] { 0 }), "zero-ID diagnostic must identify the ordinal only");
            Check(!rejected.availabilityMadeAvailable && !NetworkSoundEventCatalog.availability.available,
                "zero-ID refusal does not publish catalog availability");
        }
        else if (scenario == "setter-throws")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = Defs();
            NetworkSoundEventCatalog.throwAfterSet = true;
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "native setter exception must remain visible");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(rejected.postCountObserved && rejected.nativeEntryCountAfter == 2,
                "post-set count must be sampled even when native setter throws");
            Check(rejected.failure == "native-setter-threw:InvalidOperationException", "setter failure type must be reported");
        }
        else if (scenario == "startup-gate")
        {
            Check(!OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, false, "refused", false, false),
                "native audio refusal must stop before selected probe");
            Check(OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(false, false, "refused", false, false),
                "unrequested audio does not block the route");
            Check(OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, true, "refused", false, false),
                "no-audio path remains independent");
            Check(!OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, true, "refused", true, false),
                "a failed catalog attempt cannot be bypassed by a later no-audio flag");
            Check(!OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, false, null, false, false),
                "requested native audio requires an observed catalog admission even without a failure string");
            Check(OriginalNetworkSoundEventCatalogOwner.MayEnterSelectedProbe(true, false, null, true, true),
                "successful observed admission permits selected world entry");
        }
        else if (scenario == "aliases")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = AliasedDefs();
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && ready.nativeIdMappingReady && ready.zeroNativeIdCount == 0,
                "distinct definition names may alias one native event name");
            Check(NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)0).eventName == "shared-event" &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)1).eventName == "shared-event",
                "alias entries retain their independently assigned definition indices");
            Check(NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)0).akId ==
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)1).akId,
                "event-name aliases may resolve to the same mapping hash");
        }
        else if (scenario == "preexisting")
        {
            WholeCatalogComposed.Definitions = Defs();
            NetworkSoundEventCatalog.Reset();
            NetworkSoundEventCatalog.SetNetworkSoundEvents(WholeCatalogComposed.Definitions.OrderBy(d => d.name, StringComparer.Ordinal).ToArray());
            NetworkSoundEventCatalog.setCalls = 0;
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && !ready.initializedByOwner && ready.nativeEntryCountBefore == 2,
                "exact source-matching preexisting catalog is accepted without replacing it");
            Check(NetworkSoundEventCatalog.setCalls == 0 && ready.availabilityMadeAvailable,
                "preexisting catalog is not reassigned and native availability is established");
        }
        else throw new Exception("Unknown fixture scenario");
        Console.WriteLine("PASS " + scenario + " " + checks);
    }
}
