using System;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Passive snapshot reader for the existing SirenEncounterSession partial.
// Call CaptureNativeListeningSnapshot from its current 0.5 s Observe cadence.
public sealed partial class SirenEncounterSession
{
    static readonly FieldInfo ListeningPreviousDestroyedEggCountField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening)
            .GetField("previousDestroyedEggCount", BindingFlags.Instance | BindingFlags.NonPublic);
    static readonly FieldInfo ListeningBeginEncounterCountdownField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening)
            .GetField("beginEncounterCountdown", BindingFlags.Instance | BindingFlags.NonPublic);
    static readonly FieldInfo ListeningEncounterCountdownField =
        typeof(EntityStates.Missions.SuperRoboBallEncounter.Listening)
            .GetField("encounterCountdown", BindingFlags.Instance | BindingFlags.NonPublic);

    List<GameObject> snapshotBaselineList;
    GameObject[] snapshotBaselineObjects;
    uint[] snapshotBaselineIds;

    void ResetNativeListeningSnapshotBaseline()
    {
        ReleaseNativeListeningSnapshotBaseline();
        if (Report != null)
            Report.nativeListeningSnapshot = new SirenNativeListeningSnapshot();
    }

    void ObserveNativeListeningStateChange(EntityStates.Missions.SuperRoboBallEncounter.Listening current)
    {
        if (current != null)
        {
            // A new exact Listening instance starts a distinct observation
            // context; it must not inherit the prior listener's scalars.
            ResetNativeListeningSnapshotBaseline();
            return;
        }

        ReleaseNativeListeningSnapshotBaseline();
        SirenNativeListeningSnapshot snapshot = Report != null ? Report.nativeListeningSnapshot : null;
        if (snapshot != null && snapshot.observationAttempted)
            snapshot.retainedAfterListenerExit = true;
    }

    void ReleaseNativeListeningSnapshotBaseline()
    {
        snapshotBaselineList = null;
        snapshotBaselineObjects = null;
        snapshotBaselineIds = null;
    }

    void CaptureNativeListeningSnapshot(SirenEggInputReport input, SurvivorCombatOutputObserver.Report combat)
    {
        if (Report.nativeListeningSnapshot == null)
            Report.nativeListeningSnapshot = new SirenNativeListeningSnapshot();
        SirenNativeListeningSnapshot snapshot = Report.nativeListeningSnapshot;
        var current = stateMachine ? stateMachine.state as EntityStates.Missions.SuperRoboBallEncounter.Listening : null;
        if (current == null)
        {
            // Do not clear or refresh the last listener sample on ordinary
            // polls after the native state has exited. The original frame/time
            // fields identify when the preserved values were observed.
            ReleaseNativeListeningSnapshotBaseline();
            if (snapshot.observationAttempted)
                snapshot.retainedAfterListenerExit = true;
            return;
        }
        snapshot.observationAttempted = true;
        snapshot.retainedAfterListenerExit = false;
        snapshot.sampleErrorType = null;
        try
        {
            CaptureNativeListeningSnapshotCore(input, combat, snapshot);
        }
        catch (Exception error)
        {
            // A failed read is an aborted sample, not a partly valid update.
            // Do not publish stale threshold values or rows collected before the
            // exception. The input join is independent of this native sample.
            ClearListeningSample(snapshot, discardSlots: true);
            snapshot.sampleErrorType = error.GetType().Name;
        }
    }

    void CaptureNativeListeningSnapshotCore(SirenEggInputReport input, SurvivorCombatOutputObserver.Report combat,
                                            SirenNativeListeningSnapshot snapshot)
    {
        ClearListeningSample(snapshot, discardSlots: false);
        snapshot.observationFrame = Time.frameCount;
        snapshot.observationRealtime = Time.realtimeSinceStartup;
        snapshot.thresholdKnown = false;
        snapshot.damageObserverAvailable = combat != null && combat.attached && !combat.cleaned && !combat.inert &&
                                           combat.damageFacts != null &&
                                           combat.damageFacts.Length == SurvivorCombatOutputObserver.DamageHistoryCapacity;
        snapshot.inputObservationFrame = input != null ? input.lastTargetSampleFrame : 0;
        snapshot.inputObservationRealtime = input != null ? input.lastTargetSampleRealtime : 0f;
        snapshot.inputSampleFresh = input != null && input.lastTargetSampleKnown &&
                                    SirenNativeListeningSnapshotPolicy.IsFreshInputSample(
                                        Time.realtimeSinceStartup, input.lastTargetSampleRealtime, 1f);
        snapshot.inputTargetKnown = snapshot.inputSampleFresh && input.lastTargetNetworkId != 0;
        snapshot.inputTargetNetworkId = snapshot.inputTargetKnown ? input.lastTargetNetworkId : 0;
        snapshot.inputTargetVisibleKnown = snapshot.inputSampleFresh;
        snapshot.inputTargetVisible = snapshot.inputTargetVisibleKnown && input.lastTargetVisible;
        snapshot.inputPrimaryRequested = snapshot.inputSampleFresh && input.lastTargetPrimaryRequested;

        var current = stateMachine ? stateMachine.state as EntityStates.Missions.SuperRoboBallEncounter.Listening : null;
        if (current == null || !ReferenceEquals(current, observedNativeListeningState) || !NativeEggRegistrationObserved ||
            observedNativeEggList == null || !IsLiveNetworkOwner() || NativeEncounterStarted)
            return;
        snapshot.threshold = EntityStates.Missions.SuperRoboBallEncounter.Listening.eggsDestroyedToTriggerEncounter;
        snapshot.thresholdKnown = true;

        List<GameObject> registered = observedNativeEggList;
        if (registered.Count != SirenNativeListeningSnapshotPolicy.ExpectedSourceEggCount)
            return;
        if (snapshotBaselineList == null)
        {
            if (!Report.nativeEggRegistrationMatchesSourceEntry || Report.sourceEntryEggNetworkIds == null)
                return;
            var ids = new uint[registered.Count];
            var objects = new GameObject[registered.Count];
            for (int i = 0; i < registered.Count; i++)
            {
                GameObject gameObject = registered[i];
                if (!gameObject)
                    return;
                NetworkIdentity identity = gameObject.GetComponent<NetworkIdentity>();
                if (!identity || !identity.isServer || identity.netId.Value == 0 ||
                    !ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), gameObject))
                    return;
                ids[i] = identity.netId.Value;
                objects[i] = gameObject;
            }
            if (!SirenNativeListeningSnapshotPolicy.HasExactInitialCohort(ids, Report.sourceEntryEggNetworkIds))
                return;
            snapshotBaselineList = registered;
            snapshotBaselineObjects = objects;
            snapshotBaselineIds = ids;
        }

        if (!ReferenceEquals(registered, snapshotBaselineList) || snapshotBaselineObjects == null || snapshotBaselineIds == null ||
            registered.Count != snapshotBaselineIds.Length)
            return;

        snapshot.nativeListReferenceMatchesBaseline = true;
        snapshot.registeredSlotCountKnown = true;
        snapshot.registeredSlotCount = registered.Count;
        snapshot.nativeUnityNullSlotCountKnown = true;
        snapshot.nativeUnityNullSlotCount = 0;
        bool allOriginalSlotReferencesMatch = true;
        if (snapshot.slots == null || snapshot.slots.Length != registered.Count)
            snapshot.slots = new SirenNativeEggSlotSnapshot[registered.Count];

        bool registeredFlagRead = TryReadListeningField(current, ListeningHasRegisteredEggsField, typeof(bool),
                                                        out object registeredValue, out string fieldReadError);
        snapshot.listeningRegisteredFlagKnown = registeredFlagRead;
        snapshot.listeningRegisteredFlag = registeredFlagRead && (bool)registeredValue;
        if (fieldReadError != null)
            snapshot.sampleErrorType = fieldReadError;
        snapshot.previousDestroyedCountKnown = TryReadListeningField(current, ListeningPreviousDestroyedEggCountField, typeof(int),
                                                                     out object destroyedCount, out fieldReadError);
        snapshot.previousDestroyedCount = snapshot.previousDestroyedCountKnown ? (int)destroyedCount : 0;
        if (fieldReadError != null && snapshot.sampleErrorType == null)
            snapshot.sampleErrorType = fieldReadError;
        snapshot.countdownActiveKnown = TryReadListeningField(current, ListeningBeginEncounterCountdownField, typeof(bool),
                                                              out object countdownActive, out fieldReadError);
        snapshot.countdownActive = snapshot.countdownActiveKnown && (bool)countdownActive;
        if (fieldReadError != null && snapshot.sampleErrorType == null)
            snapshot.sampleErrorType = fieldReadError;
        bool countdownRead = TryReadListeningField(current, ListeningEncounterCountdownField, typeof(float), out object countdown,
                                                    out fieldReadError);
        if (fieldReadError != null && snapshot.sampleErrorType == null)
            snapshot.sampleErrorType = fieldReadError;
        snapshot.countdownSeconds = countdownRead ? (float)countdown : 0f;
        snapshot.countdownSecondsKnown = countdownRead && !float.IsNaN(snapshot.countdownSeconds) &&
                                         !float.IsInfinity(snapshot.countdownSeconds);

        for (int i = 0; i < registered.Count; i++)
        {
            GameObject gameObject = registered[i];
            bool managedReferencePresent = !ReferenceEquals(gameObject, null);
            bool unityAlive = gameObject;
            if (!unityAlive)
                snapshot.nativeUnityNullSlotCount++;
            bool sameOriginalReference = ReferenceEquals(gameObject, snapshotBaselineObjects[i]);
            if (!sameOriginalReference)
                allOriginalSlotReferencesMatch = false;
            NetworkIdentity identity = unityAlive ? gameObject.GetComponent<NetworkIdentity>() : null;
            bool identityKnown = identity;
            uint currentId = identityKnown ? identity.netId.Value : 0;
            bool slotConsistent = sameOriginalReference && SirenNativeListeningSnapshotPolicy.IsSlotIdentityConsistent(
                snapshotBaselineIds[i], unityAlive, identityKnown, currentId);
            HealthComponent health = unityAlive ? gameObject.GetComponent<HealthComponent>() : null;
            bool healthAvailable = health;
            bool healthValueKnown = healthAvailable && SirenNativeListeningSnapshotPolicy.IsFiniteHealth(true, health.health);
            SirenNativeEggSlotSnapshot slot = new SirenNativeEggSlotSnapshot {
                slot = i,
                originalNetworkId = snapshotBaselineIds[i],
                originalNetworkIdKnown = snapshotBaselineIds[i] != 0,
                managedReferencePresent = managedReferencePresent,
                unityObjectAlive = unityAlive,
                originalReferenceMatches = sameOriginalReference,
                identityKnown = identityKnown,
                currentNetworkId = currentId,
                currentNetworkIdKnown = identityKnown && currentId != 0,
                currentNetworkIdMatchesOriginal = slotConsistent && currentId == snapshotBaselineIds[i],
                healthComponentAvailable = healthAvailable,
                healthAlive = healthAvailable && health.alive,
                healthValueKnown = healthValueKnown,
                healthValue = healthValueKnown ? health.health : 0f,
                retainedVictimDamageFacts = 0,
                latestVictimDamageFrame = -1
            };
            if (snapshot.damageObserverAvailable)
            {
                int count = 0, latest = -1;
                int minimumFrame = Time.frameCount - 600;
                for (int factIndex = 0; factIndex < combat.damageFacts.Length; factIndex++)
                {
                    SurvivorCombatOutputObserver.DamageFact fact = combat.damageFacts[factIndex];
                    if (fact.victimNetworkId != slot.originalNetworkId || fact.frame < minimumFrame)
                        continue;
                    count++;
                    if (fact.frame > latest)
                        latest = fact.frame;
                }
                slot.retainedVictimDamageFacts = count;
                slot.latestVictimDamageFrame = latest;
            }
            snapshot.slots[i] = slot;
        }
        if (!allOriginalSlotReferencesMatch)
        {
            snapshot.nativeUnityNullSlotCountKnown = false;
            snapshot.nativeUnityNullSlotCount = 0;
        }
        snapshot.sampleAvailable = true;
    }

    static void ClearListeningSample(SirenNativeListeningSnapshot snapshot, bool discardSlots)
    {
        snapshot.sampleAvailable = false;
        snapshot.sampleErrorType = null;
        snapshot.nativeListReferenceMatchesBaseline = false;
        snapshot.registeredSlotCountKnown = false;
        snapshot.registeredSlotCount = 0;
        snapshot.nativeUnityNullSlotCountKnown = false;
        snapshot.nativeUnityNullSlotCount = 0;
        snapshot.listeningRegisteredFlagKnown = false;
        snapshot.listeningRegisteredFlag = false;
        snapshot.previousDestroyedCountKnown = false;
        snapshot.previousDestroyedCount = 0;
        snapshot.countdownActiveKnown = false;
        snapshot.countdownActive = false;
        snapshot.countdownSecondsKnown = false;
        snapshot.countdownSeconds = 0f;
        snapshot.thresholdKnown = false;
        snapshot.threshold = 0;
        snapshot.damageObserverAvailable = false;
        if (discardSlots)
        {
            snapshot.slots = Array.Empty<SirenNativeEggSlotSnapshot>();
        }
        else if (snapshot.slots != null)
        {
            // Keep the successful-path array allocation reusable, but never
            // leave the previous sample's row values visible while recapturing.
            for (int i = 0; i < snapshot.slots.Length; i++)
                snapshot.slots[i] = default(SirenNativeEggSlotSnapshot);
        }
    }

    static bool TryReadListeningField(EntityStates.Missions.SuperRoboBallEncounter.Listening state, FieldInfo field,
                                      Type expectedType, out object value, out string errorType)
    {
        value = null;
        errorType = null;
        if (state == null || field == null || !field.IsPrivate || field.IsStatic || field.FieldType != expectedType)
            return false;
        try
        {
            value = field.GetValue(state);
            return value != null && value.GetType() == expectedType;
        }
        catch (Exception error)
        {
            value = null;
            errorType = error.GetType().Name;
            return false;
        }
    }
}
