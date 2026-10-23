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
    static NetworkSoundEventDef[] FullDefs(bool includeNullName = false)
    {
        var values = new NetworkSoundEventDef[65];
        for (int i = 0; i < values.Length; i++)
            values[i] = new NetworkSoundEventDef { name = "definition-" + i.ToString("D2"), eventName = "event-" + i };
        values[0].eventName = String.Empty;
        values[64].eventName = String.Empty;
        values[32].eventName = "   "; // Every non-null source value must reach the original setter unchanged.
        Array.Reverse(values); // The owner and native setter must agree on ordinal definition-name ordering.
        if (includeNullName) values[32].eventName = null;
        return values;
    }
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
        else if (scenario == "empty-family")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = FullDefs();
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && ready.sourceDefinitionCountObserved && ready.sourceDefinitionCount == 65,
                "the complete 65-entry source family must be observed and admitted");
            Check(ready.emptyEventNameCount == 2 && ready.emptyEventNameIndices.SequenceEqual(new[] { 0, 64 }) &&
                  !ready.emptyEventNameIndicesTruncated,
                "empty-event telemetry must use sorted catalog ordinals and retain both edge entries");
            Check(NetworkSoundEventCatalog.setCalls == 1 && NetworkSoundEventCatalog.mappedEventNameCount == 65,
                "every family member, including empty values, must reach the original setter");
            Check(NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)0).eventName == String.Empty &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)64).eventName == String.Empty &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)32).eventName == "   ",
                "the setter must receive exact empty and whitespace values without rewriting");
            Check(NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)64).name == "definition-64" &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)0).index == (NetworkSoundEventIndex)0 &&
                  NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)64).index == (NetworkSoundEventIndex)64,
                "stable ordinal names and native index assignments must remain unchanged");
        }
        else if (scenario == "empty-truncation")
        {
            NetworkSoundEventCatalog.Reset();
            var values = FullDefs();
            foreach (var definition in values.Where(definition => definition.name.CompareTo("definition-07") <= 0))
                definition.eventName = String.Empty;
            WholeCatalogComposed.Definitions = values;
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && ready.emptyEventNameCount == 9,
                "full count must remain accurate when ordinal details exceed the bounded list");
            Check(ready.emptyEventNameIndices.SequenceEqual(Enumerable.Range(0, 8)) && ready.emptyEventNameIndicesTruncated,
                "bounded empty ordinals must keep the first eight sorted indices and flag truncation");
            Check(NetworkSoundEventCatalog.mappedEventNameCount == 65,
                "truncated telemetry must not truncate definitions passed to the native setter");
        }
        else if (scenario == "null-event-name")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = FullDefs(true);
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "null event name must be refused separately before native mapping");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(rejected.sourceDefinitionCountObserved && rejected.sourceDefinitionCount == 65 &&
                  rejected.nullEventNameCount == 1 && rejected.nullEventNameIndices.SequenceEqual(new[] { 32 }),
                "null-event refusal must report observed family size and sorted null ordinal");
            Check(rejected.failure == "original-definition-event-name-null" && NetworkSoundEventCatalog.setCalls == 0 &&
                  NetworkSoundEventCatalog.mappedEventNameCount == 0,
                "null string cannot be replaced with a fabricated name or sent to native mapping");
            Check(rejected.emptyEventNameCount == 2 && rejected.emptyEventNameIndices.SequenceEqual(new[] { 0, 64 }),
                "empty source strings remain separately counted even when another member refuses the family");
        }
        else if (scenario == "null-definition")
        {
            NetworkSoundEventCatalog.Reset();
            var values = FullDefs();
            values[0] = null;
            WholeCatalogComposed.Definitions = values;
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "null definition must fail before sorting or native calls");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(rejected.sourceDefinitionCountObserved && rejected.sourceDefinitionCount == 65 &&
                  rejected.nullDefinitionCount == 1 && NetworkSoundEventCatalog.setCalls == 0,
                "null definition refusal must be explicit and preserve the observed source count");
        }
        else if (scenario == "null-source")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = null;
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "null family result must refuse");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(!rejected.sourceDefinitionCountObserved && rejected.sourceDefinitionCount == 0,
                "null family has no observed array length and differs from an empty array");
            Check(NetworkSoundEventCatalog.setCalls == 0, "null family must not reach the native setter");
        }
        else if (scenario == "empty-source")
        {
            NetworkSoundEventCatalog.Reset();
            WholeCatalogComposed.Definitions = Array.Empty<NetworkSoundEventDef>();
            Refused(() => OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true),
                "empty family must refuse");
            var rejected = OriginalNetworkSoundEventCatalogOwner.CaptureSnapshot();
            Check(rejected.sourceDefinitionCountObserved && rejected.sourceDefinitionCount == 0,
                "empty family must report an observed zero length");
            Check(NetworkSoundEventCatalog.setCalls == 0, "empty family must not reach the native setter");
        }
        else if (scenario == "preexisting")
        {
            WholeCatalogComposed.Definitions = FullDefs();
            NetworkSoundEventCatalog.Reset();
            NetworkSoundEventCatalog.SetNetworkSoundEvents(WholeCatalogComposed.Definitions.OrderBy(d => d.name, StringComparer.Ordinal).ToArray());
            NetworkSoundEventCatalog.setCalls = 0;
            var ready = OriginalNetworkSoundEventCatalogOwner.InitializeBeforeWorld(true, false, true, false, true, true);
            Check(ready.ready && !ready.initializedByOwner && ready.nativeEntryCountBefore == 65 &&
                  ready.sourceDefinitionCountObserved && ready.sourceDefinitionCount == 65 &&
                  ready.emptyEventNameCount == 2,
                "exact source-matching preexisting catalog is accepted without replacing it");
            Check(NetworkSoundEventCatalog.setCalls == 0 && ready.availabilityMadeAvailable,
                "preexisting catalog is not reassigned and native availability is established");
        }
        else throw new Exception("Unknown fixture scenario");
        Console.WriteLine("PASS " + scenario + " " + checks);
    }
}
