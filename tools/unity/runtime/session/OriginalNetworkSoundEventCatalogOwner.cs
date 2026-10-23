using System;
using System.Linq;
using RoR2;
using RoR2.Audio;

// Process-scoped admission for the original native catalog. The game's public
// setter remains responsible for sorting, index assignment, and Wwise ID lookup.
public static class OriginalNetworkSoundEventCatalogOwner
{
    [Serializable]
    public sealed class Snapshot
    {
        public bool attempted;
        public bool ready;
        public bool initializedByOwner;
        public bool preCountObserved;
        public int nativeEntryCountBefore;
        public bool postCountObserved;
        public int nativeEntryCountAfter;
        public int sourceDefinitionCount;
        public bool availabilityMadeAvailable;
        // Nonzero GetIDFromString results prove only a mapped nonzero hash;
        // they do not prove that an event exists in a bank or is audible.
        public bool nativeIdMappingReady;
        public int zeroNativeIdCount;
        public int[] zeroNativeIdIndices = Array.Empty<int>();
        public bool zeroNativeIdIndicesTruncated;
        public string failure;
    }

    static bool attempted;
    static NetworkSoundEventDef[] retainedDefinitions = Array.Empty<NetworkSoundEventDef>();
    static readonly Snapshot snapshot = new Snapshot();

    public static Snapshot CaptureSnapshot()
    {
        return new Snapshot
        {
            attempted = snapshot.attempted,
            ready = snapshot.ready,
            initializedByOwner = snapshot.initializedByOwner,
            preCountObserved = snapshot.preCountObserved,
            nativeEntryCountBefore = snapshot.nativeEntryCountBefore,
            postCountObserved = snapshot.postCountObserved,
            nativeEntryCountAfter = snapshot.nativeEntryCountAfter,
            sourceDefinitionCount = snapshot.sourceDefinitionCount,
            availabilityMadeAvailable = snapshot.availabilityMadeAvailable,
            nativeIdMappingReady = snapshot.nativeIdMappingReady,
            zeroNativeIdCount = snapshot.zeroNativeIdCount,
            zeroNativeIdIndices = (int[])snapshot.zeroNativeIdIndices.Clone(),
            zeroNativeIdIndicesTruncated = snapshot.zeroNativeIdIndicesTruncated,
            failure = snapshot.failure
        };
    }

    // Invoke once from the process-lifetime original-audio owner after native
    // audio readiness and before selected body/world producers are activated.
    // Do not call in no-audio mode: J474's explicit decoder remains the owner.
    public static Snapshot InitializeBeforeWorld(bool explicitlyRequested, bool noAudio,
        bool originalAudioReady, bool originalTermsReturned, bool nativeEngineInitialized,
        bool originalCatalogLeaseHeld)
    {
        if (attempted)
            return Refuse("process-scoped-admission-already-attempted");
        attempted = true;
        snapshot.attempted = true;

        if (!explicitlyRequested || noAudio || !originalAudioReady || originalTermsReturned ||
            !nativeEngineInitialized || !originalCatalogLeaseHeld)
            return Refuse("native-audio-readiness-or-lease-not-proven");

        ObservePreCount();
        var source = WholeCatalogComposed.DefinitionFamily(Array.Empty<NetworkSoundEventDef>());
        if (source == null || source.Length == 0 || source.Any(definition => !definition) ||
            source.Any(definition => String.IsNullOrWhiteSpace(definition.name) ||
                                     String.IsNullOrWhiteSpace(definition.eventName)) ||
            source.Select(definition => definition.name).Distinct(StringComparer.Ordinal).Count() != source.Length)
            return Refuse("complete-original-definition-family-invalid");

        // Keep source references alive while the native static index mapping is in use.
        retainedDefinitions = source.OrderBy(definition => definition.name, StringComparer.Ordinal).ToArray();
        snapshot.sourceDefinitionCount = retainedDefinitions.Length;

        if (snapshot.nativeEntryCountBefore == 0)
        {
            try
            {
                NetworkSoundEventCatalog.SetNetworkSoundEvents(retainedDefinitions);
                snapshot.initializedByOwner = true;
            }
            catch (Exception error)
            {
                snapshot.failure = "native-setter-threw:" + error.GetType().Name;
                ObservePostCount();
                throw; // Keep the original exception visible to the existing startup route.
            }
            ObservePostCount();
        }
        else
        {
            ObservePostCount();
            if (!MatchesExactSortedFamily(snapshot.nativeEntryCountAfter))
                return Refuse("preexisting-native-catalog-does-not-match-source-family");
        }

        if (!MatchesExactSortedFamily(snapshot.nativeEntryCountAfter))
            return Refuse("native-catalog-setter-did-not-produce-exact-source-family");

        ObserveZeroAkIds();
        snapshot.nativeIdMappingReady = snapshot.zeroNativeIdCount == 0;
        if (!snapshot.nativeIdMappingReady)
            return Refuse("native-id-mapping-incomplete");

        // Only publish availability after the source table and all nonzero
        // native name hashes have passed this owner's admission checks.
        NetworkSoundEventCatalog.availability.MakeAvailable();
        snapshot.availabilityMadeAvailable = NetworkSoundEventCatalog.availability.available;
        if (!snapshot.availabilityMadeAvailable)
            return Refuse("native-catalog-availability-not-established");

        snapshot.ready = true;
        return CaptureSnapshot();
    }

    static void ObservePreCount()
    {
        snapshot.nativeEntryCountBefore = NetworkSoundEventCatalog.networkSoundCount;
        snapshot.preCountObserved = true;
    }

    static void ObservePostCount()
    {
        snapshot.nativeEntryCountAfter = NetworkSoundEventCatalog.networkSoundCount;
        snapshot.postCountObserved = true;
    }

    static bool MatchesExactSortedFamily(int count)
    {
        if (count != retainedDefinitions.Length)
            return false;
        for (int i = 0; i < count; i++)
        {
            var nativeDefinition = NetworkSoundEventCatalog.GetNetworkSoundEventDef((NetworkSoundEventIndex)i);
            if (!nativeDefinition || !ReferenceEquals(nativeDefinition, retainedDefinitions[i]) ||
                (int)nativeDefinition.index != i)
                return false;
        }
        return true;
    }

    static void ObserveZeroAkIds()
    {
        var missing = retainedDefinitions.Select((definition, index) => new { definition, index })
            .Where(item => item.definition.akId == 0u).ToArray();
        snapshot.zeroNativeIdCount = missing.Length;
        snapshot.zeroNativeIdIndicesTruncated = missing.Length > 8;
        snapshot.zeroNativeIdIndices = missing.Take(8).Select(item => item.index).ToArray();
    }

    static Snapshot Refuse(string reason)
    {
        if (snapshot.preCountObserved && !snapshot.postCountObserved)
            ObservePostCount();
        snapshot.ready = false;
        snapshot.failure = reason;
        throw new InvalidOperationException("Original network-sound catalog admission refused: " + reason);
    }

    // PortSession uses this directly after awaiting the persistent owner, before
    // running any selected probe/player activation. The no-audio decoder remains valid.
    public static bool MayEnterSelectedProbe(bool originalAudioRequested, bool noAudio, string startupFailure,
        bool catalogAdmissionAttempted, bool catalogAdmissionReady)
    {
        if (catalogAdmissionAttempted && !catalogAdmissionReady)
            return false;
        if (!originalAudioRequested || noAudio)
            return true;
        return catalogAdmissionAttempted && catalogAdmissionReady && String.IsNullOrEmpty(startupFailure);
    }
}
