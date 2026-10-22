using System;
using System.Collections.Generic;

// Pure policy for the existing SirenEncounterSession observation owner.
// It deliberately contains no Unity calls, state writes, threshold inference, or gameplay action.
[Serializable]
public struct SirenNativeEggSlotSnapshot
{
    public int slot;
    public uint originalNetworkId;
    public bool originalNetworkIdKnown;
    public bool managedReferencePresent;
    public bool unityObjectAlive;
    public bool originalReferenceMatches;
    public bool identityKnown;
    public uint currentNetworkId;
    public bool currentNetworkIdKnown;
    public bool currentNetworkIdMatchesOriginal;
    public bool healthComponentAvailable;
    public bool healthAlive;
    public bool healthValueKnown;
    public float healthValue;
    public int retainedVictimDamageFacts;
    public int latestVictimDamageFrame;
}

[Serializable]
public sealed class SirenNativeListeningSnapshot
{
    public bool sampleAvailable;
    public bool observationAttempted;
    public bool retainedAfterListenerExit;
    public string sampleErrorType;
    public bool nativeListReferenceMatchesBaseline;
    public bool registeredSlotCountKnown;
    public int registeredSlotCount;
    public bool nativeUnityNullSlotCountKnown;
    public int nativeUnityNullSlotCount;
    public bool listeningRegisteredFlagKnown;
    public bool listeningRegisteredFlag;
    public bool previousDestroyedCountKnown;
    public int previousDestroyedCount;
    public bool countdownActiveKnown;
    public bool countdownActive;
    public bool countdownSecondsKnown;
    public float countdownSeconds;
    public bool thresholdKnown;
    public int threshold;
    public bool damageObserverAvailable;
    public int observationFrame;
    public float observationRealtime;
    public int inputObservationFrame;
    public float inputObservationRealtime;
    public bool inputSampleFresh;
    public bool inputTargetKnown;
    public uint inputTargetNetworkId;
    public bool inputTargetVisibleKnown;
    public bool inputTargetVisible;
    public bool inputPrimaryRequested;
    public SirenNativeEggSlotSnapshot[] slots = Array.Empty<SirenNativeEggSlotSnapshot>();
}

public static class SirenNativeListeningSnapshotPolicy
{
    public const int ExpectedSourceEggCount = 12;

    public static bool HasExactInitialCohort(IList<uint> nativeIds, IList<uint> sourceIds)
    {
        if (nativeIds == null || sourceIds == null || nativeIds.Count != ExpectedSourceEggCount ||
            sourceIds.Count != ExpectedSourceEggCount)
            return false;
        var seen = new HashSet<uint>();
        for (int i = 0; i < nativeIds.Count; i++)
        {
            uint id = nativeIds[i];
            if (id == 0 || !seen.Add(id))
                return false;
        }
        if (seen.Count != sourceIds.Count)
            return false;
        var sourceSeen = new HashSet<uint>();
        for (int i = 0; i < sourceIds.Count; i++)
            if (sourceIds[i] == 0 || !seen.Contains(sourceIds[i]) || !sourceSeen.Add(sourceIds[i]))
                return false;
        return true;
    }

    public static bool TryCountUnityNullSlots(IList<bool> unityObjectAlive, bool sameKnownList, out int count)
    {
        count = 0;
        if (!sameKnownList || unityObjectAlive == null || unityObjectAlive.Count != ExpectedSourceEggCount)
            return false;
        for (int i = 0; i < unityObjectAlive.Count; i++)
            if (!unityObjectAlive[i])
                count++;
        return true;
    }

    public static bool IsSlotIdentityConsistent(uint originalId, bool unityObjectAlive, bool identityKnown, uint currentId)
    {
        if (originalId == 0)
            return false;
        return !unityObjectAlive || identityKnown && currentId != 0 && currentId == originalId;
    }

    public static bool IsFiniteHealth(bool healthComponentAvailable, float health)
    {
        return healthComponentAvailable && IsFinite(health);
    }

    static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    public static bool IsFreshInputSample(float now, float sampleTime, float maximumAge)
    {
        float age = now - sampleTime;
        return IsFinite(now) && IsFinite(sampleTime) && IsFinite(maximumAge) &&
               maximumAge >= 0f && age >= 0f && age <= maximumAge;
    }

    public static int CountRetainedVictimDamageFacts(IList<DamageFact> facts, uint victimId, int minimumFrame,
                                                      out int latestFrame)
    {
        latestFrame = -1;
        if (facts == null || victimId == 0)
            return 0;
        int count = 0;
        for (int i = 0; i < facts.Count; i++)
        {
            DamageFact fact = facts[i];
            if (fact.victimNetworkId != victimId || fact.frame < minimumFrame)
                continue;
            count++;
            if (fact.frame > latestFrame)
                latestFrame = fact.frame;
        }
        return count;
    }

    public struct DamageFact
    {
        public int frame;
        public uint victimNetworkId;
    }
}
