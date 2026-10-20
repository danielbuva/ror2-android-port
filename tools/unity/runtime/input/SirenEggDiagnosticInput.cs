// Subsystem: diagnostic input. Owner map: docs/ARCHITECTURE.md#ownership.
// Setup: explicit assisted Siren selection; teardown: integrated world cleanup.
// Original input, skill states and HealthComponents own every gameplay outcome.
using System;
using System.Collections.Generic;
using RoR2;
using UnityEngine;

public interface ISirenEggDiagnosticContext
{
    bool Selected { get; }
    bool Assisted { get; }
    bool ManualTakeover { get; }
    bool SourceSceneActive { get; }
    bool SourceEncounterAttached { get; }
    bool SourceListenerActive { get; }
    bool NativeEncounterStarted { get; }
    bool StageTransporting { get; }
    bool FirstFailure { get; }
    int StageSceneHandle { get; }
    float StageElapsed { get; }
    bool RevalidatedSourceEggs(Vector3 position, List<CharacterBody> destination);
    bool IsCurrentSourceEgg(CharacterBody candidate);
    bool ShouldYieldToExistingWorldCombat(CharacterBody player);
    void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 target, float stopDistance, string targetName,
                            float elapsed);
    Vector3 WorldCombatAimPoint(CharacterBody target, Vector3 origin, out bool visible);
}

// Evidence values are populated from the actual source scene, source body,
// HealthComponent, HurtBoxGroup, NetworkIdentity and server object map. The
// pure predicate is shared with the exact-editor fixture.
public struct SirenEggCandidateEvidence
{
    public bool ownerLive, candidateSceneLoaded;
    public int candidateSceneHandle, ownerSceneHandle, activeSceneHandle;
    public string bodyName;
    public int bodyIndex, expectedBodyIndex;
    public int nativeRegisteredEggCount;
    public bool nativeRegistrationObserved, nativeListeningInstanceMatches, nativeRegisteredListContainsCandidate;
    public bool identityIsServer, hasNonzeroNetworkId, sourceAssetIdMatches, networkMapOwnsExactObject;
    public bool healthExists, healthAlive, hurtBoxGroupExists, mainHurtBoxExists, groupOwnsMainHurtBox;
    public bool mainHurtBoxBullseye, mainHurtBoxEnabled, mainHurtBoxActive, hurtBoxUsesSameHealthComponent;
}

public static class SirenEggSourceContract
{
    public static bool IsExactNativeRegisteredMember(IList<GameObject> nativeEggList, GameObject candidate)
    {
        if (nativeEggList == null || !candidate)
            return false;
        for (int i = 0; i < nativeEggList.Count; i++)
            if (ReferenceEquals(nativeEggList[i], candidate))
                return true;
        return false;
    }

    public static bool IsEligible(SirenEggCandidateEvidence e)
    {
        return e.ownerLive && e.candidateSceneLoaded && e.candidateSceneHandle != 0 && e.candidateSceneHandle == e.ownerSceneHandle &&
               e.activeSceneHandle == e.ownerSceneHandle && !string.IsNullOrEmpty(e.bodyName) &&
               e.bodyName.IndexOf("VultureEgg", StringComparison.Ordinal) >= 0 && e.bodyIndex == e.expectedBodyIndex &&
               e.nativeRegistrationObserved && e.nativeRegisteredEggCount > 0 && e.nativeListeningInstanceMatches &&
               e.nativeRegisteredListContainsCandidate && e.identityIsServer && e.hasNonzeroNetworkId && e.sourceAssetIdMatches &&
               e.networkMapOwnsExactObject && e.healthExists && e.healthAlive && e.hurtBoxGroupExists && e.mainHurtBoxExists &&
               e.groupOwnsMainHurtBox && e.mainHurtBoxBullseye && e.mainHurtBoxEnabled && e.mainHurtBoxActive &&
               e.hurtBoxUsesSameHealthComponent;
    }
}

public static class SirenEggTargetSelectionPolicy
{
    public const int MaximumCandidates = 12;

    public static bool IsCandidateCountSupported(int count) => count >= 0 && count <= MaximumCandidates;

    // Selection changes only which already validated original egg receives the
    // ordinary movement/aim request. Visibility wins over proximity; distance
    // breaks ties. When every candidate is occluded, the nearest one remains a
    // navigation target and the caller must keep primary released.
    public static bool Prefer(bool candidateVisible, float candidateDistanceSqr, bool bestExists, bool bestVisible, float bestDistanceSqr)
    {
        if (float.IsNaN(candidateDistanceSqr) || float.IsInfinity(candidateDistanceSqr) || candidateDistanceSqr < 0f)
            return false;
        if (!bestExists)
            return true;
        if (candidateVisible != bestVisible)
            return candidateVisible;
        return candidateDistanceSqr < bestDistanceSqr;
    }
}

public struct SirenCombatThreatEvidence
{
    public bool bodyLive, masterLive, healthAlive, playerTeamKnown, hostileTeam, insideSourceBounds;
    public float distanceSqr;
}

public static class SirenCombatThreatContract
{
    public const float NearbyDistanceSqr = 400f;
    public static bool IsNearbyHostileDirectorThreat(SirenCombatThreatEvidence e)
    {
        return e.bodyLive && e.masterLive && e.healthAlive && e.playerTeamKnown && e.hostileTeam && e.insideSourceBounds &&
               e.distanceSqr < NearbyDistanceSqr;
    }
}

[Serializable]
public sealed class SirenEggInputReport
{
    public bool selected, assisted, active, cleaned, terminal;
    public int targetSamples, primaryRequestedFixedTicks;
    public float elapsedSeconds;
    public string stopReason;
    public uint lastTargetNetworkId;
    public string lastTargetScene, lastTargetBody;

    // Read-only witness of the native HuntressTracker target at the same input
    // owner's sample. These counters intentionally distinguish an absent
    // tracker, an empty/fake-null target and a known target identity.
    public int nativeTrackerWitnessSamples, nativeTrackerUnavailableSamples, nativeTrackerDisabledSamples;
    public int nativeTrackerInactiveSamples, nativeTargetNullSamples;
    public int nativeTargetDestroyedSamples, nativeTargetHealthUnavailableSamples;
    public int nativeTargetIdentityUnavailableSamples, nativeTargetZeroNetworkIdSamples;
    public int nativeTargetIdentifiedSamples, nativeTargetMatchesSelectedSamples, nativeTargetDiffersSelectedSamples;
    public int primaryRequestedSamples, primaryReleasedSamples, primaryRequestedNativeMatchSamples;
    public int primaryRequestedNativeMismatchSamples, primaryRequestedNativeUnknownSamples;
    public uint firstSelectedEggNetworkId, lastSelectedEggNetworkId;
    public uint firstNativeHuntressTargetNetworkId, lastNativeHuntressTargetNetworkId;
    public bool nativeTrackerConfigurationObserved, lastNativeTrackerAvailable, lastNativeTrackerEnabled;
    public bool lastNativeTrackerActiveAndEnabled, lastNativeTrackerActivationObserved, lastNativeTargetAvailable;
    public bool lastNativeTargetIdentityAvailable, lastNativeTargetMatchesSelected, lastNativeTargetHealthAlive;
    public bool lastNativePlayerTeamObserved, lastNativeTargetTeamObserved;
    public int lastNativePlayerTeamIndex, lastNativeTargetTeamIndex;
    public float nativeTrackerMaxTrackingDistance, nativeTrackerMaxTrackingAngle, nativeTrackerUpdateFrequency;
    public float lastNativeTargetCurrentDistance, lastNativeTargetCurrentAimDot;
    public bool lastNativeTargetCurrentDistanceObserved, lastNativeTargetCurrentAimDotObserved;
    public bool lastNativeTargetCurrentGeometryObserved;
    public string lastNativeTargetObservation = "not-sampled";
    public string lastPrimaryRequestReason = "not-sampled";
}

public enum SirenNativeTargetObservation
{
    TrackerUnavailable,
    TrackerDisabled,
    TrackerInactive,
    NoTarget,
    DestroyedTarget,
    HealthUnavailable,
    IdentityUnavailable,
    ZeroNetworkId,
    IdentifiedTarget
}

public static class SirenNativeTargetWitnessPolicy
{
    static int Increment(int value) => value < int.MaxValue ? value + 1 : value;

    public static bool IsTrackerReadEligible(bool componentPresent, bool enabled, bool activeAndEnabled)
    {
        return componentPresent && enabled && activeAndEnabled;
    }

    static string Name(SirenNativeTargetObservation observation)
    {
        switch (observation)
        {
        case SirenNativeTargetObservation.TrackerUnavailable:
            return "tracker-unavailable";
        case SirenNativeTargetObservation.TrackerDisabled:
            return "tracker-disabled";
        case SirenNativeTargetObservation.TrackerInactive:
            return "tracker-inactive";
        case SirenNativeTargetObservation.NoTarget:
            return "no-target";
        case SirenNativeTargetObservation.DestroyedTarget:
            return "destroyed-target";
        case SirenNativeTargetObservation.HealthUnavailable:
            return "health-unavailable";
        case SirenNativeTargetObservation.IdentityUnavailable:
            return "identity-unavailable";
        case SirenNativeTargetObservation.ZeroNetworkId:
            return "zero-network-id";
        case SirenNativeTargetObservation.IdentifiedTarget:
            return "identified-target";
        default:
            return "unknown-observation";
        }
    }

    // A fixed set of scalar first/last values and saturating counters keeps
    // instrumentation bounded and allocation-free on the normal input path.
    public static void Record(SirenEggInputReport report, SirenNativeTargetObservation observation, uint selectedEggNetworkId,
                              uint nativeTargetNetworkId, bool primaryRequested)
    {
        if (report == null)
            return;
        report.nativeTrackerWitnessSamples = Increment(report.nativeTrackerWitnessSamples);
        report.lastNativeTargetObservation = Name(observation);
        report.lastPrimaryRequestReason = primaryRequested ? "visible-egg-requested-primary" : "no-visible-egg-primary-released";
        report.lastNativeHuntressTargetNetworkId = 0;
        report.lastNativeTargetAvailable = observation == SirenNativeTargetObservation.IdentifiedTarget;
        report.lastNativeTargetIdentityAvailable = report.lastNativeTargetAvailable;
        report.lastNativeTargetMatchesSelected =
            report.lastNativeTargetAvailable && selectedEggNetworkId != 0 && nativeTargetNetworkId == selectedEggNetworkId;
        if (selectedEggNetworkId != 0)
        {
            if (report.firstSelectedEggNetworkId == 0)
                report.firstSelectedEggNetworkId = selectedEggNetworkId;
            report.lastSelectedEggNetworkId = selectedEggNetworkId;
        }

        switch (observation)
        {
        case SirenNativeTargetObservation.TrackerUnavailable:
            report.nativeTrackerUnavailableSamples = Increment(report.nativeTrackerUnavailableSamples);
            break;
        case SirenNativeTargetObservation.TrackerDisabled:
            report.nativeTrackerDisabledSamples = Increment(report.nativeTrackerDisabledSamples);
            break;
        case SirenNativeTargetObservation.TrackerInactive:
            report.nativeTrackerInactiveSamples = Increment(report.nativeTrackerInactiveSamples);
            break;
        case SirenNativeTargetObservation.NoTarget:
            report.nativeTargetNullSamples = Increment(report.nativeTargetNullSamples);
            break;
        case SirenNativeTargetObservation.DestroyedTarget:
            report.nativeTargetDestroyedSamples = Increment(report.nativeTargetDestroyedSamples);
            break;
        case SirenNativeTargetObservation.HealthUnavailable:
            report.nativeTargetHealthUnavailableSamples = Increment(report.nativeTargetHealthUnavailableSamples);
            break;
        case SirenNativeTargetObservation.IdentityUnavailable:
            report.nativeTargetIdentityUnavailableSamples = Increment(report.nativeTargetIdentityUnavailableSamples);
            break;
        case SirenNativeTargetObservation.ZeroNetworkId:
            report.nativeTargetZeroNetworkIdSamples = Increment(report.nativeTargetZeroNetworkIdSamples);
            break;
        case SirenNativeTargetObservation.IdentifiedTarget:
            report.nativeTargetIdentifiedSamples = Increment(report.nativeTargetIdentifiedSamples);
            if (report.lastNativeTargetMatchesSelected)
                report.nativeTargetMatchesSelectedSamples = Increment(report.nativeTargetMatchesSelectedSamples);
            else
                report.nativeTargetDiffersSelectedSamples = Increment(report.nativeTargetDiffersSelectedSamples);
            if (report.firstNativeHuntressTargetNetworkId == 0)
                report.firstNativeHuntressTargetNetworkId = nativeTargetNetworkId;
            report.lastNativeHuntressTargetNetworkId = nativeTargetNetworkId;
            break;
        }

        if (primaryRequested)
        {
            report.primaryRequestedSamples = Increment(report.primaryRequestedSamples);
            if (observation == SirenNativeTargetObservation.IdentifiedTarget)
            {
                if (report.lastNativeTargetMatchesSelected)
                    report.primaryRequestedNativeMatchSamples = Increment(report.primaryRequestedNativeMatchSamples);
                else
                    report.primaryRequestedNativeMismatchSamples = Increment(report.primaryRequestedNativeMismatchSamples);
            }
            else
                report.primaryRequestedNativeUnknownSamples = Increment(report.primaryRequestedNativeUnknownSamples);
        }
        else
            report.primaryReleasedSamples = Increment(report.primaryReleasedSamples);
    }
}

// A value-type exact-value lease. `CaptureProducerValues(..., true)` is called
// after the ordinary frame producers; disposal never claims a fresh frame.
public sealed class SirenEggInputLease
{
    struct Snapshot
    {
        public Vector2 movement, aim;
        public Vector3 diagnosticAim;
        public bool sprint, primary;
        public NovaInputBridge.DiagnosticJumpSnapshot jump;
        public static Snapshot Read(NovaInputBridge b) => new Snapshot {
            movement = b.movement,           aim = b.aim,
            diagnosticAim = b.diagnosticAim, sprint = b.diagnosticSprint,
            primary = b.diagnosticPrimary,   jump = b.CaptureDiagnosticJump()
        };
        public void CaptureChanged(NovaInputBridge b, ref Snapshot producer)
        {
            if (b.movement != movement)
                producer.movement = b.movement;
            if (b.aim != aim)
                producer.aim = b.aim;
            if (b.diagnosticAim != diagnosticAim)
                producer.diagnosticAim = b.diagnosticAim;
            if (b.diagnosticSprint != sprint)
                producer.sprint = b.diagnosticSprint;
            if (b.diagnosticPrimary != primary)
                producer.primary = b.diagnosticPrimary;
            if (b.CaptureDiagnosticJump().Revision != jump.Revision)
                producer.jump = b.CaptureDiagnosticJump();
        }
    }

    Snapshot producer, overlay;
    bool hasProducer, hasOverlay;
    public bool HasOutstandingLease => hasProducer && hasOverlay;
    public void CaptureProducerValues(NovaInputBridge b, bool fresh = false)
    {
        if (!b)
            return;
        if (fresh || !hasOverlay || !hasProducer)
        {
            producer = Snapshot.Read(b);
            hasProducer = true;
        }
        else
            overlay.CaptureChanged(b, ref producer);
    }
    public void CaptureOwnedOverlay(NovaInputBridge b)
    {
        if (!b)
            return;
        if (!hasProducer)
        {
            producer = Snapshot.Read(b);
            hasProducer = true;
        }
        overlay = Snapshot.Read(b);
        hasOverlay = true;
    }
    public void Release(NovaInputBridge b)
    {
        if (b && b.diagnosticInput && hasProducer && hasOverlay)
        {
            if (b.movement == overlay.movement)
                b.movement = producer.movement;
            if (b.aim == overlay.aim)
                b.aim = producer.aim;
            if (b.diagnosticAim == overlay.diagnosticAim)
                b.diagnosticAim = producer.diagnosticAim;
            if (b.diagnosticSprint == overlay.sprint)
                b.diagnosticSprint = producer.sprint;
            if (b.diagnosticPrimary == overlay.primary)
                b.diagnosticPrimary = producer.primary;
            b.RestoreDiagnosticJump(producer.jump, overlay.jump);
        }
        producer = default(Snapshot);
        overlay = default(Snapshot);
        hasProducer = hasOverlay = false;
    }
}

public sealed class SirenEggDiagnosticInput : IDisposable
{
    public const float MaximumStageSeconds = 180f;
    public const float ListenerStartupGraceSeconds = 5f;
    public const float StopDistance = 1.5f;

    readonly ISirenEggDiagnosticContext context;
    readonly SirenEggInputReport report;
    readonly SirenEggInputLease inputLease = new SirenEggInputLease();
    readonly List<CharacterBody> sourceEggCandidates = new List<CharacterBody>();
    NovaInputBridge ownedBridge;
    float beganAt = float.NaN;
    int startedSceneHandle;
    int lastObservedInputTick = int.MinValue;
    bool lastSubmittedPrimary, listenerObserved, started, terminal, disposed;

    public SirenEggDiagnosticInput(ISirenEggDiagnosticContext context, SirenEggInputReport report)
    {
        this.context = context ?? throw new ArgumentNullException(nameof(context));
        this.report = report ?? throw new ArgumentNullException(nameof(report));
    }

    public bool HasOutstandingInputLease => ownedBridge && inputLease.HasOutstandingLease;

    // Releasing before the ordinary producers gives the next Apply a genuine
    // fresh baseline. Default-off remains a no-op unless this exact owner still
    // holds an overlay from an earlier selected frame, in which case the
    // transition frame must return that lease before producers run.
    public static void PrepareProducerFrameForSelection(bool selected, SirenEggDiagnosticInput owner, NovaInputBridge bridge)
    {
        if (owner != null && (selected || owner.HasOutstandingInputLease))
            owner.PrepareProducerFrame(bridge);
    }

    public void PrepareProducerFrame(NovaInputBridge bridge)
    {
        if (disposed || terminal || !ownedBridge)
            return;
        ObservePreviousRequest(ownedBridge);
        ReleaseIfStillOwned();
    }

    // Called last, after the existing world and earned-feather producers.
    public bool Apply(CharacterBody player, NovaInputBridge bridge, bool producerFrameFresh)
    {
        if (disposed || terminal)
            return false;
        if (ownedBridge && ownedBridge != bridge)
            ReleaseIfStillOwned();
        if (bridge && producerFrameFresh)
            inputLease.CaptureProducerValues(bridge, true);
        if (bridge)
            ObservePreviousRequest(bridge);
        if (!context.Selected)
        {
            if (started)
                Stop("selection-disabled");
            else
                ReleaseIfStillOwned();
            return false;
        }
        report.selected = true;
        report.assisted = context.Assisted;
        if (context.FirstFailure)
        {
            Stop("first-failure");
            return false;
        }

        if (!started)
        {
            if (!context.SourceSceneActive || !context.SourceEncounterAttached)
            {
                Yield("awaiting-original-shipgraveyard-owner");
                return false;
            }
            started = true;
            startedSceneHandle = context.StageSceneHandle;
            beganAt = context.StageElapsed;
        }
        if (context.StageTransporting)
        {
            Stop("stage-transport");
            return false;
        }
        if (!context.SourceSceneActive || !context.SourceEncounterAttached || context.StageSceneHandle != startedSceneHandle)
        {
            Stop(context.StageSceneHandle != startedSceneHandle ? "stage-changed" : "source-owner-unavailable");
            return false;
        }
        // The gate reads ScriptedCombatEncounter.hasSpawnedServer and the actual
        // source FSM directly, never the last 0.5-second report sample.
        if (context.NativeEncounterStarted)
        {
            Stop("native-encounter-started");
            return false;
        }
        float stageElapsed = context.StageElapsed;
        if (float.IsNaN(stageElapsed) || float.IsInfinity(stageElapsed) || stageElapsed < beganAt)
        {
            Stop("invalid-stage-time");
            return false;
        }
        report.elapsedSeconds = stageElapsed - beganAt;
        if (report.elapsedSeconds >= MaximumStageSeconds)
        {
            Stop("stage-time-budget-exhausted");
            return false;
        }
        if (context.SourceListenerActive)
            listenerObserved = true;
        else if (listenerObserved)
        {
            Stop("native-listener-lost-before-encounter-start");
            return false;
        }
        else if (report.elapsedSeconds >= ListenerStartupGraceSeconds)
        {
            Stop("native-listener-startup-not-observed");
            return false;
        }
        else
        {
            Yield("waiting-for-native-listener-initialization");
            return false;
        }

        if (!OwnsDiagnosticInput(player, bridge))
        {
            Yield(context.ManualTakeover ? "manual-input-takeover" : "diagnostic-input-not-owned");
            return false;
        }
        if (context.ShouldYieldToExistingWorldCombat(player))
        {
            Yield("yielded-to-existing-world-combat");
            return false;
        }

        if (!context.RevalidatedSourceEggs(player.corePosition, sourceEggCandidates))
        {
            Yield("native-source-egg-candidate-limit-exceeded");
            return false;
        }
        CharacterBody nearestEgg = null, visibleEgg = null;
        Vector3 nearestPoint = Vector3.zero, visiblePoint = Vector3.zero;
        float nearestDistanceSqr = float.PositiveInfinity, visibleDistanceSqr = float.PositiveInfinity;
        bool hasNearest = false, hasVisible = false;
        for (int i = 0; i < sourceEggCandidates.Count; i++)
        {
            CharacterBody candidate = sourceEggCandidates[i];
            if (!candidate || !context.IsCurrentSourceEgg(candidate))
                continue;
            float distanceSqr = (candidate.corePosition - player.corePosition).sqrMagnitude;
            Vector3 candidatePoint = context.WorldCombatAimPoint(candidate, player.inputBank.aimOrigin, out bool candidateVisible);
            if (SirenEggTargetSelectionPolicy.Prefer(false, distanceSqr, hasNearest, false, nearestDistanceSqr))
            {
                nearestEgg = candidate;
                nearestPoint = candidatePoint;
                nearestDistanceSqr = distanceSqr;
                hasNearest = true;
            }
            if (candidateVisible && SirenEggTargetSelectionPolicy.Prefer(true, distanceSqr, hasVisible, true, visibleDistanceSqr))
            {
                visibleEgg = candidate;
                visiblePoint = candidatePoint;
                visibleDistanceSqr = distanceSqr;
                hasVisible = true;
            }
        }
        CharacterBody egg = hasVisible ? visibleEgg : nearestEgg;
        if (!egg || !context.IsCurrentSourceEgg(egg))
        {
            Yield("no-current-source-egg-target");
            return false;
        }
        // Recheck the live owner/start boundary immediately before writing the
        // ordinary bridge requests. The candidate itself was revalidated above.
        if (context.FirstFailure)
        {
            Stop("first-failure");
            return false;
        }
        if (context.StageTransporting)
        {
            Stop("stage-transport");
            return false;
        }
        if (!context.SourceSceneActive || !context.SourceEncounterAttached || context.StageSceneHandle != startedSceneHandle)
        {
            Stop("source-owner-or-stage-changed");
            return false;
        }
        if (context.NativeEncounterStarted)
        {
            Stop("native-encounter-started");
            return false;
        }
        if (!context.SourceListenerActive)
        {
            Stop("native-listener-lost-before-encounter-start");
            return false;
        }

        context.NavigateWorldInput(player, bridge, egg.transform.position, StopDistance, "Original Vulture egg", stageElapsed);
        bool visible = hasVisible;
        Vector3 point = visible ? visiblePoint : nearestPoint;
        var identity = egg.GetComponent<UnityEngine.Networking.NetworkIdentity>();
        uint selectedEggNetworkId = identity ? identity.netId.Value : 0;
        ObserveNativeHuntressTarget(player, selectedEggNetworkId, visible);
        Vector3 aim = point - player.inputBank.aimOrigin;
        bridge.aim = new Vector2(aim.x, aim.z).normalized;
        bridge.diagnosticAim = aim.normalized;
        bridge.diagnosticPrimary = visible;
        inputLease.CaptureOwnedOverlay(bridge);
        ownedBridge = bridge;
        report.active = true;
        report.targetSamples++;
        report.lastTargetScene = egg.gameObject.scene.name;
        report.lastTargetBody = egg.name;
        report.lastTargetNetworkId = selectedEggNetworkId;
        lastSubmittedPrimary = visible;
        report.stopReason = visible ? "ordinary-primary-requested" : "source-aim-occluded";
        return true;
    }

    void ObserveNativeHuntressTarget(CharacterBody player, uint selectedEggNetworkId, bool primaryRequested)
    {
        SirenNativeTargetObservation observation;
        uint nativeTargetNetworkId = 0;
        report.lastNativeTrackerAvailable = false;
        report.lastNativeTrackerEnabled = false;
        report.lastNativeTrackerActiveAndEnabled = false;
        report.lastNativeTrackerActivationObserved = false;
        report.lastNativeTargetAvailable = false;
        report.lastNativeTargetIdentityAvailable = false;
        report.lastNativeTargetMatchesSelected = false;
        report.lastNativeTargetHealthAlive = false;
        report.lastNativeTargetCurrentDistanceObserved = false;
        report.lastNativeTargetCurrentAimDotObserved = false;
        report.lastNativeTargetCurrentGeometryObserved = false;
        report.lastNativePlayerTeamObserved = false;
        report.lastNativeTargetTeamObserved = false;
        report.lastNativePlayerTeamIndex = -1;
        report.lastNativeTargetTeamIndex = -1;

        HuntressTracker tracker = player.GetComponent<HuntressTracker>();
        if (!tracker)
        {
            observation = SirenNativeTargetObservation.TrackerUnavailable;
        }
        else
        {
            report.lastNativeTrackerAvailable = true;
            report.lastNativeTrackerEnabled = tracker.enabled;
            report.lastNativeTrackerActiveAndEnabled = tracker.isActiveAndEnabled;
            report.lastNativeTrackerActivationObserved = true;
            if (!SirenNativeTargetWitnessPolicy.IsTrackerReadEligible(true, tracker.enabled, tracker.isActiveAndEnabled))
            {
                observation =
                    !tracker.enabled ? SirenNativeTargetObservation.TrackerDisabled : SirenNativeTargetObservation.TrackerInactive;
            }
            else
            {
                report.nativeTrackerConfigurationObserved = true;
                report.nativeTrackerMaxTrackingDistance = tracker.maxTrackingDistance;
                report.nativeTrackerMaxTrackingAngle = tracker.maxTrackingAngle;
                report.nativeTrackerUpdateFrequency = tracker.trackerUpdateFrequency;
                if (player.teamComponent)
                {
                    report.lastNativePlayerTeamIndex = (int)player.teamComponent.teamIndex;
                    report.lastNativePlayerTeamObserved = true;
                }

                HurtBox nativeTarget = tracker.GetTrackingTarget();
                if (ReferenceEquals(nativeTarget, null))
                {
                    observation = SirenNativeTargetObservation.NoTarget;
                }
                else if (!nativeTarget)
                {
                    observation = SirenNativeTargetObservation.DestroyedTarget;
                }
                else
                {
                    report.lastNativeTargetTeamIndex = (int)nativeTarget.teamIndex;
                    report.lastNativeTargetTeamObserved = true;
                    HealthComponent targetHealth = nativeTarget.healthComponent;
                    if (!targetHealth)
                    {
                        observation = SirenNativeTargetObservation.HealthUnavailable;
                    }
                    else
                    {
                        report.lastNativeTargetHealthAlive = targetHealth.alive;
                        UnityEngine.Networking.NetworkIdentity targetIdentity =
                            targetHealth.gameObject.GetComponent<UnityEngine.Networking.NetworkIdentity>();
                        if (!targetIdentity)
                        {
                            observation = SirenNativeTargetObservation.IdentityUnavailable;
                        }
                        else if (targetIdentity.netId.Value == 0)
                        {
                            observation = SirenNativeTargetObservation.ZeroNetworkId;
                        }
                        else
                        {
                            observation = SirenNativeTargetObservation.IdentifiedTarget;
                            nativeTargetNetworkId = targetIdentity.netId.Value;
                            Vector3 toTarget = nativeTarget.transform.position - player.inputBank.aimOrigin;
                            float distanceSqr = toTarget.sqrMagnitude;
                            Vector3 aimDirection = player.inputBank.aimDirection;
                            if (distanceSqr > 0f && !float.IsNaN(distanceSqr) && !float.IsInfinity(distanceSqr))
                            {
                                report.lastNativeTargetCurrentDistance = Mathf.Sqrt(distanceSqr);
                                report.lastNativeTargetCurrentDistanceObserved = true;
                                float aimSqr = aimDirection.sqrMagnitude;
                                if (!float.IsNaN(aimSqr) && !float.IsInfinity(aimSqr))
                                {
                                    float aimDot = Vector3.Dot(aimDirection, toTarget / Mathf.Sqrt(distanceSqr));
                                    if (!float.IsNaN(aimDot) && !float.IsInfinity(aimDot))
                                    {
                                        report.lastNativeTargetCurrentAimDot = aimDot;
                                        report.lastNativeTargetCurrentAimDotObserved = true;
                                        report.lastNativeTargetCurrentGeometryObserved = true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        SirenNativeTargetWitnessPolicy.Record(report, observation, selectedEggNetworkId, nativeTargetNetworkId, primaryRequested);
    }

    bool OwnsDiagnosticInput(CharacterBody player, NovaInputBridge bridge)
    {
        return context.Assisted && !context.ManualTakeover && player && bridge && bridge.diagnosticInput &&
               player.gameObject == bridge.gameObject && player.inputBank && bridge.bank == player.inputBank;
    }

    void ObservePreviousRequest(NovaInputBridge bridge)
    {
        if (lastObservedInputTick == int.MinValue)
            lastObservedInputTick = bridge.fixedTicks;
        int elapsedTicks = bridge.fixedTicks - lastObservedInputTick;
        if (elapsedTicks > 0 && lastSubmittedPrimary)
            report.primaryRequestedFixedTicks += elapsedTicks;
        if (elapsedTicks > 0)
            lastObservedInputTick = bridge.fixedTicks;
    }

    void Yield(string reason)
    {
        ReleaseIfStillOwned();
        report.stopReason = reason;
    }

    void Stop(string reason)
    {
        if (terminal)
            return;
        ReleaseIfStillOwned();
        terminal = true;
        report.terminal = true;
        report.stopReason = reason;
    }

    void ReleaseIfStillOwned()
    {
        inputLease.Release(ownedBridge);
        ownedBridge = null;
        lastSubmittedPrimary = false;
        lastObservedInputTick = int.MinValue;
        report.active = false;
    }

    public void Dispose()
    {
        if (disposed)
            return;
        ReleaseIfStillOwned();
        report.cleaned = true;
        disposed = true;
        ownedBridge = null;
    }
}
