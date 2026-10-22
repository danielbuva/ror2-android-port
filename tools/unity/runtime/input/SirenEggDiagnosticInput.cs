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
    bool TryReadNavigationTrigger(CharacterBody player, CharacterBody egg, out float eggDistance, out float trackerMaximumDistance);
    float NavigationObjectiveStalledSeconds { get; }
    ISirenNavigationObservationReader CreateNavigationObservationReader(CharacterBody player, NovaInputBridge bridge);
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
    public int lastTargetSampleFrame;
    public float lastTargetSampleRealtime;
    public bool lastTargetSampleKnown, lastTargetVisible, lastTargetPrimaryRequested;

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
    public int nativeTargetReadErrors;
    public string lastNativeTargetReadErrorType;

    // At most two one-shot snapshots per stage; no per-frame diagnostic history.
    public int eligibilitySnapshotAttempts, eligibilitySnapshotErrors;
    public string lastEligibilitySnapshotErrorType;
    public SirenTargetEligibilitySnapshot firstMismatchEligibilitySnapshot, delayedNullEligibilitySnapshot;
    public SirenNavigationObservationReport navigationObservation = new SirenNavigationObservationReport();
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
    IdentifiedTarget,
    TargetReadError
}

[Serializable]
public struct SirenTargetEligibilitySnapshot
{
    public bool attempted, captured;
    public string kind, samplePhase, errorType;
    public float waitSinceFirstMismatchSeconds, sustainedNullTargetSeconds;
    public uint selectedEggNetworkId, nativeTargetNetworkId;
    public int selectedBodyIndex, selectedBodyTeamIndex, selectedHurtBoxTeamIndex, nativeBodyIndex, nativeBodyTeamIndex,
        nativeHurtBoxTeamIndex;
    public bool selectedBodyAvailable, selectedTeamAvailable, selectedHurtBoxTeamAvailable, nativeBodyAvailable, nativeTeamAvailable,
        nativeHurtBoxTeamAvailable;
    public int selectedHurtBoxLayer, nativeHurtBoxLayer, selectedColliderLayer, nativeColliderLayer;
    public bool selectedHurtBoxAvailable, selectedHurtBoxEnabled, selectedHurtBoxActive, selectedHurtBoxBullseye;
    public bool selectedHurtBoxHealthAvailable, selectedHurtBoxHealthAlive, selectedColliderAvailable, selectedColliderEnabled;
    public bool nativeHurtBoxAvailable, nativeHurtBoxEnabled, nativeHurtBoxActive, nativeHurtBoxBullseye;
    public bool nativeHurtBoxHealthAvailable, nativeHurtBoxHealthAlive, nativeColliderAvailable, nativeColliderEnabled;
    public uint selectedBodyNetworkId;
    public bool selectedRegistryAvailable, selectedRegistryMembershipKnown, selectedInGlobalBullseyeList;
    public bool nativeRegistryAvailable, nativeRegistryMembershipKnown, nativeInGlobalBullseyeList, nativeCacheAgeKnown;
    public bool registryScanTruncated;
    public int registryTotalCount, registryScannedCount;
    public Vector3 aimOrigin, heldAimDirection, selectedHurtBoxPoint, selectedAimRequestPoint, nativeHurtBoxPoint;
    public bool aimOriginAvailable, heldAimDirectionAvailable, selectedPointAvailable, selectedAimRequestPointAvailable,
        nativePointAvailable;
    public float selectedDistance, selectedAimDot, nativeDistance, nativeAimDot;
    public bool selectedGeometryAvailable, nativeGeometryAvailable;
    public float maxTrackingDistance, maxTrackingAngle;
    public bool trackerLimitsAvailable;
    public bool selectedRangeKnown, selectedWithinRange, selectedConeKnown, selectedWithinCone;
    public bool nativeRangeKnown, nativeWithinRange, nativeConeKnown, nativeWithinCone;
    public bool selectedLosKnown, selectedLineOfSight, nativeLosKnown, nativeLineOfSight;
}

public struct SirenBullseyeMembershipEvidence
{
    public bool available, known, present, truncated;
    public int totalCount, scannedCount;
}

public struct SirenNullTargetWitnessWindow
{
    public bool active;
    public uint selectedEggNetworkId;
    public int consecutiveSamples;
    public float firstObservedRealtime;
    public float lastObservedRealtime;
}

public static class SirenTargetEligibilityWitnessPolicy
{
    public const int MaximumGlobalBullseyeScanCount = 4096;
    public const float FollowupWaitSeconds = 0.5f;
    public const int MinimumSustainedNullSamples = 2;
    // Require observations to remain continuous at the owner's fixed-sample cadence.
    // A larger pause starts a new window; it is not evidence of a gameplay failure.
    public const float MaximumObservationGapSeconds = 0.25f;

    public static bool ObserveSustainedNullTarget(ref SirenNullTargetWitnessWindow window, bool qualifyingNoTarget,
                                                   uint selectedEggNetworkId, float realtime, out float elapsed)
    {
        elapsed = 0f;
        if (!qualifyingNoTarget || selectedEggNetworkId == 0 || !IsFinite(realtime))
        {
            window = new SirenNullTargetWitnessWindow();
            return false;
        }
        float sampleGap = realtime - window.lastObservedRealtime;
        if (!window.active || window.selectedEggNetworkId != selectedEggNetworkId ||
            !IsFinite(window.firstObservedRealtime) || !IsFinite(window.lastObservedRealtime) ||
            !IsFinite(sampleGap) || sampleGap < 0f || sampleGap > MaximumObservationGapSeconds)
        {
            window = new SirenNullTargetWitnessWindow { active = true, selectedEggNetworkId = selectedEggNetworkId,
                                                        consecutiveSamples = 1, firstObservedRealtime = realtime,
                                                        lastObservedRealtime = realtime };
            return false;
        }
        if (window.consecutiveSamples < int.MaxValue)
            window.consecutiveSamples++;
        window.lastObservedRealtime = realtime;
        elapsed = realtime - window.firstObservedRealtime;
        if (!IsFinite(elapsed))
        {
            window = new SirenNullTargetWitnessWindow();
            elapsed = 0f;
            return false;
        }
        return window.consecutiveSamples >= MinimumSustainedNullSamples && elapsed >= FollowupWaitSeconds;
    }

    public static bool WithinCaptureBudget(int attempts) => attempts >= 0 && attempts < 2;

    public static bool ShouldCaptureFirstMismatch(bool alreadyAttempted, bool visiblePrimary, bool identifiedTarget, uint selectedId,
                                                  uint nativeId)
    {
        return !alreadyAttempted && visiblePrimary && identifiedTarget && selectedId != 0 && nativeId != 0 && nativeId != selectedId;
    }

    public static bool ShouldCaptureDelayedNull(bool nullTarget, bool selectedEggUnchanged, float elapsed)
    {
        return nullTarget && selectedEggUnchanged && IsFinite(elapsed) && elapsed >= FollowupWaitSeconds;
    }

    public static bool TryMeasureRangeAndCone(float distance, float aimDot, float maxDistance, float maxAngle, out bool rangePass,
                                              out bool conePass)
    {
        rangePass = false;
        conePass = false;
        if (!IsFinite(distance) || !IsFinite(aimDot) || !IsFinite(maxDistance) || maxDistance < 0f || !IsFinite(maxAngle) ||
            maxAngle < 0f || maxAngle > 180f)
            return false;
        rangePass = distance <= maxDistance;
        float minDot = Mathf.Cos(maxAngle * (Mathf.PI / 180f));
        conePass = aimDot >= minDot;
        return true;
    }

    public static void ScanMembershipPair<T>(IList<T> list, T firstTarget, T secondTarget, int maximum,
                                             out SirenBullseyeMembershipEvidence first, out SirenBullseyeMembershipEvidence second)
        where T : class
    {
        first = new SirenBullseyeMembershipEvidence();
        second = new SirenBullseyeMembershipEvidence();
        if (list == null || maximum < 0)
            return;
        int total = list.Count;
        int limit = Math.Min(total, maximum);
        bool truncated = limit < total;
        first.available = second.available = true;
        first.totalCount = second.totalCount = total;
        first.truncated = second.truncated = truncated;
        bool firstHasReference = !ReferenceEquals(firstTarget, null);
        bool secondHasReference = !ReferenceEquals(secondTarget, null);
        if (!firstHasReference && !secondHasReference)
            return;
        int scanned = 0;
        for (int i = 0; i < limit; i++)
        {
            scanned++;
            T candidate = list[i];
            if (firstHasReference && !first.present && ReferenceEquals(candidate, firstTarget))
            {
                first.known = true;
                first.present = true;
            }
            if (secondHasReference && !second.present && ReferenceEquals(candidate, secondTarget))
            {
                second.known = true;
                second.present = true;
            }
            if ((!firstHasReference || first.present) && (!secondHasReference || second.present))
                break;
        }
        first.scannedCount = second.scannedCount = scanned;
        if (firstHasReference && !first.present)
            first.known = !truncated;
        if (secondHasReference && !second.present)
            second.known = !truncated;
    }

    public static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
}

public static class SirenNativeTargetWitnessPolicy
{
    // Preserve the native getter's original exception and control flow. The
    // optional witness records only the exception type before rethrowing it.
    public static HurtBox ReadTargetOrThrow(HuntressTracker tracker, SirenEggInputReport report)
    {
        try
        {
            return tracker.GetTrackingTarget();
        }
        catch (Exception error)
        {
            report.nativeTargetReadErrors++;
            report.lastNativeTargetReadErrorType = error.GetType().FullName;
            throw;
        }
    }

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
        case SirenNativeTargetObservation.TargetReadError:
            return "target-read-error";
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
    readonly SirenNavigationObservationRecorder navigationObservation;
    readonly SirenEggInputLease inputLease = new SirenEggInputLease();
    readonly List<CharacterBody> sourceEggCandidates = new List<CharacterBody>();
    NovaInputBridge ownedBridge;
    float beganAt = float.NaN;
    int startedSceneHandle;
    int lastObservedInputTick = int.MinValue;
    bool lastSubmittedPrimary, listenerObserved, started, terminal, disposed;
    bool firstEligibilitySnapshotAttempted, delayedEligibilitySnapshotAttempted, selectedEggChangedAfterMismatch;
    SirenNullTargetWitnessWindow nullTargetWitnessWindow;
    uint firstEligibilitySnapshotSelectedId;
    float firstEligibilitySnapshotRealtime = float.NaN;

    public SirenEggDiagnosticInput(ISirenEggDiagnosticContext context, SirenEggInputReport report)
    {
        this.context = context ?? throw new ArgumentNullException(nameof(context));
        this.report = report ?? throw new ArgumentNullException(nameof(report));
        navigationObservation = new SirenNavigationObservationRecorder(report.navigationObservation);
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
        if (ownedBridge != bridge)
        {
            navigationObservation.OnBridgeIdentityChanged();
            ReleaseIfStillOwned();
            return;
        }
        ObservePreviousRequest(ownedBridge);
        ReleaseIfStillOwned();
    }

    // Called last, after the existing world and earned-feather producers.
    public bool Apply(CharacterBody player, NovaInputBridge bridge, bool producerFrameFresh)
    {
        report.lastTargetSampleKnown = false;
        if (disposed || terminal)
            return false;
        if (ownedBridge && ownedBridge != bridge)
        {
            navigationObservation.OnBridgeIdentityChanged();
            ReleaseIfStillOwned();
        }
        if (bridge && producerFrameFresh)
            inputLease.CaptureProducerValues(bridge, true);
        if (bridge)
            ObservePreviousRequest(bridge);
        float observationRealtime = Time.realtimeSinceStartup;
        navigationObservation.Maintain(observationRealtime, true);
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

        bool visible = hasVisible;
        Vector3 point = visible ? visiblePoint : nearestPoint;
        var identity = egg.GetComponent<UnityEngine.Networking.NetworkIdentity>();
        uint selectedEggNetworkId = identity ? identity.netId.Value : 0;
        float selectedEggDistance, trackerMaximumDistance;
        if (context.TryReadNavigationTrigger(player, egg, out selectedEggDistance, out trackerMaximumDistance))
            navigationObservation.ObserveTrigger(true, true, selectedEggNetworkId, selectedEggDistance, trackerMaximumDistance,
                                                  context.NavigationObjectiveStalledSeconds, Time.realtimeSinceStartup);
        else
            navigationObservation.ResetTriggerContinuity();

        context.NavigateWorldInput(player, bridge, egg.transform.position, StopDistance, "Original Vulture egg", stageElapsed);
        // Read after the selected Siren route has updated the shared PathFollower
        // and request clock. NovaInputBoundary suppresses the competing general
        // route only while this exact native owner holds the diagnostic frame.
        if (navigationObservation.report.started && !navigationObservation.report.completed)
        {
            if (!OwnsDiagnosticInput(player, bridge))
            {
                Yield(context.ManualTakeover ? "manual-input-takeover" : "diagnostic-input-not-owned");
                return false;
            }
            navigationObservation.ObservePending(selectedEggNetworkId, Time.realtimeSinceStartup, OwnsDiagnosticInput(player, bridge),
                                                  bridge.fixedTicks, context.CreateNavigationObservationReader(player, bridge));
        }
        ObserveNativeHuntressTarget(player, egg, selectedEggNetworkId, visible, point);
        Vector3 aim = point - player.inputBank.aimOrigin;
        bridge.aim = new Vector2(aim.x, aim.z).normalized;
        bridge.diagnosticAim = aim.normalized;
        bridge.diagnosticPrimary = visible;
        inputLease.CaptureOwnedOverlay(bridge);
        navigationObservation.QueueRequest(bridge.movement, bridge.fixedTicks, context.NavigationObjectiveStalledSeconds);
        ownedBridge = bridge;
        report.active = true;
        report.targetSamples++;
        report.lastTargetScene = egg.gameObject.scene.name;
        report.lastTargetBody = egg.name;
        report.lastTargetNetworkId = selectedEggNetworkId;
        report.lastTargetSampleFrame = Time.frameCount;
        report.lastTargetSampleRealtime = Time.realtimeSinceStartup;
        report.lastTargetVisible = visible;
        report.lastTargetPrimaryRequested = visible;
        report.lastTargetSampleKnown = true;
        lastSubmittedPrimary = visible;
        report.stopReason = visible ? "ordinary-primary-requested" : "source-aim-occluded";
        return true;
    }

    void ObserveNativeHuntressTarget(CharacterBody player, CharacterBody selectedEgg, uint selectedEggNetworkId, bool primaryRequested,
                                     Vector3 selectedAimPoint)
    {
        SirenNativeTargetObservation observation = SirenNativeTargetObservation.TrackerUnavailable;
        uint nativeTargetNetworkId = 0;
        HurtBox nativeTarget = null;
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

                nativeTarget = SirenNativeTargetWitnessPolicy.ReadTargetOrThrow(tracker, report);
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
        TryCaptureEligibilitySnapshot(player, selectedEgg, selectedEggNetworkId, selectedAimPoint, primaryRequested, observation,
                                      nativeTarget, nativeTargetNetworkId);
    }

    void TryCaptureEligibilitySnapshot(CharacterBody player, CharacterBody selectedEgg, uint selectedEggNetworkId, Vector3 selectedAimPoint,
                                       bool primaryRequested, SirenNativeTargetObservation observation, HurtBox nativeTarget,
                                       uint nativeTargetNetworkId)
    {
        bool sustainedNullEligible = !firstEligibilitySnapshotAttempted && !report.delayedNullEligibilitySnapshot.attempted &&
                                     SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(report.eligibilitySnapshotAttempts) &&
                                     primaryRequested && selectedEggNetworkId != 0 && selectedEgg &&
                                     observation == SirenNativeTargetObservation.NoTarget;
        float sustainedNullElapsed;
        bool sustainedNull = SirenTargetEligibilityWitnessPolicy.ObserveSustainedNullTarget(
            ref nullTargetWitnessWindow, sustainedNullEligible, selectedEggNetworkId,
            sustainedNullEligible ? Time.realtimeSinceStartup : 0f, out sustainedNullElapsed);
        if (firstEligibilitySnapshotAttempted && selectedEggNetworkId != firstEligibilitySnapshotSelectedId)
            selectedEggChangedAfterMismatch = true;
        if (!primaryRequested || selectedEggNetworkId == 0 || !selectedEgg ||
            !SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(report.eligibilitySnapshotAttempts))
            return;
        bool firstMismatch = SirenTargetEligibilityWitnessPolicy.ShouldCaptureFirstMismatch(
            firstEligibilitySnapshotAttempted, primaryRequested, observation == SirenNativeTargetObservation.IdentifiedTarget,
            selectedEggNetworkId, nativeTargetNetworkId);
        if (firstMismatch)
        {
            firstEligibilitySnapshotAttempted = true;
            delayedEligibilitySnapshotAttempted = report.delayedNullEligibilitySnapshot.attempted;
            selectedEggChangedAfterMismatch = false;
            firstEligibilitySnapshotSelectedId = selectedEggNetworkId;
            firstEligibilitySnapshotRealtime = Time.realtimeSinceStartup;
            CaptureEligibilitySnapshot(ref report.firstMismatchEligibilitySnapshot, "first-visible-primary-mismatch", 0f, player,
                                       selectedEgg, selectedEggNetworkId, selectedAimPoint, nativeTarget, nativeTargetNetworkId);
            return;
        }
        if (firstEligibilitySnapshotAttempted && !delayedEligibilitySnapshotAttempted &&
            selectedEggNetworkId == firstEligibilitySnapshotSelectedId)
        {
            float wait = Time.realtimeSinceStartup - firstEligibilitySnapshotRealtime;
            if (SirenTargetEligibilityWitnessPolicy.ShouldCaptureDelayedNull(observation == SirenNativeTargetObservation.NoTarget,
                                                                             !selectedEggChangedAfterMismatch, wait))
            {
                delayedEligibilitySnapshotAttempted = true;
                CaptureEligibilitySnapshot(ref report.delayedNullEligibilitySnapshot, "delayed-null-same-selected-egg", wait, player,
                                           selectedEgg, selectedEggNetworkId, selectedAimPoint, null, 0);
            }
            return;
        }
        if (!firstEligibilitySnapshotAttempted && !delayedEligibilitySnapshotAttempted && sustainedNull &&
            !report.delayedNullEligibilitySnapshot.attempted &&
            SirenTargetEligibilityWitnessPolicy.WithinCaptureBudget(report.eligibilitySnapshotAttempts))
        {
            delayedEligibilitySnapshotAttempted = true;
            CaptureEligibilitySnapshot(ref report.delayedNullEligibilitySnapshot, "first-sustained-null-primary-same-selected-egg",
                                       0f, player, selectedEgg, selectedEggNetworkId, selectedAimPoint, null, 0);
            report.delayedNullEligibilitySnapshot.sustainedNullTargetSeconds = sustainedNullElapsed;
        }
    }

    void CaptureEligibilitySnapshot(ref SirenTargetEligibilitySnapshot snapshot, string kind, float wait, CharacterBody player,
                                    CharacterBody selectedEgg, uint selectedEggNetworkId, Vector3 selectedAimPoint, HurtBox nativeTarget,
                                    uint nativeTargetNetworkId)
    {
        snapshot = new SirenTargetEligibilitySnapshot { attempted = true,
                                                        kind = kind,
                                                        samplePhase = "before-current-frame-diagnostic-aim-write;cached-target-age-unknown",
                                                        waitSinceFirstMismatchSeconds = wait,
                                                        selectedEggNetworkId = selectedEggNetworkId,
                                                        selectedBodyNetworkId = selectedEggNetworkId,
                                                        nativeTargetNetworkId = nativeTargetNetworkId };
        report.eligibilitySnapshotAttempts++;
        try
        {
            InputBankTest input = player ? player.inputBank : null;
            if (!input || !selectedEgg)
                return;

            snapshot.aimOrigin = input.aimOrigin;
            snapshot.heldAimDirection = input.aimDirection;
            snapshot.selectedAimRequestPoint = selectedAimPoint;
            snapshot.aimOriginAvailable = IsFinite(snapshot.aimOrigin);
            snapshot.heldAimDirectionAvailable = IsFinite(snapshot.heldAimDirection);
            snapshot.selectedAimRequestPointAvailable = IsFinite(snapshot.selectedAimRequestPoint);
            snapshot.selectedBodyAvailable = true;
            snapshot.selectedBodyIndex = (int)selectedEgg.bodyIndex;
            if (selectedEgg.teamComponent)
            {
                snapshot.selectedTeamAvailable = true;
                snapshot.selectedBodyTeamIndex = (int)selectedEgg.teamComponent.teamIndex;
            }

            HurtBox selectedHurtBox = selectedEgg.mainHurtBox;
            if (selectedHurtBox)
            {
                snapshot.selectedHurtBoxAvailable = true;
                snapshot.selectedHurtBoxEnabled = selectedHurtBox.enabled;
                snapshot.selectedHurtBoxActive = selectedHurtBox.gameObject.activeInHierarchy;
                snapshot.selectedHurtBoxBullseye = selectedHurtBox.isBullseye;
                snapshot.selectedHurtBoxLayer = selectedHurtBox.gameObject.layer;
                snapshot.selectedHurtBoxTeamIndex = (int)selectedHurtBox.teamIndex;
                snapshot.selectedHurtBoxTeamAvailable = true;
                snapshot.selectedHurtBoxPoint = selectedHurtBox.transform.position;
                snapshot.selectedPointAvailable = IsFinite(snapshot.selectedHurtBoxPoint);
                HealthComponent hurtBoxHealth = selectedHurtBox.healthComponent;
                if (hurtBoxHealth)
                {
                    snapshot.selectedHurtBoxHealthAvailable = true;
                    snapshot.selectedHurtBoxHealthAlive = hurtBoxHealth.alive;
                }
                if (selectedHurtBox.collider)
                {
                    snapshot.selectedColliderAvailable = true;
                    snapshot.selectedColliderEnabled = selectedHurtBox.collider.enabled;
                    snapshot.selectedColliderLayer = selectedHurtBox.collider.gameObject.layer;
                }
            }

            HuntressTracker tracker = player.GetComponent<HuntressTracker>();
            if (tracker)
            {
                snapshot.maxTrackingDistance = tracker.maxTrackingDistance;
                snapshot.maxTrackingAngle = tracker.maxTrackingAngle;
                snapshot.trackerLimitsAvailable = SirenTargetEligibilityWitnessPolicy.IsFinite(snapshot.maxTrackingDistance) &&
                                                  SirenTargetEligibilityWitnessPolicy.IsFinite(snapshot.maxTrackingAngle) &&
                                                  snapshot.maxTrackingDistance >= 0f && snapshot.maxTrackingAngle >= 0f &&
                                                  snapshot.maxTrackingAngle <= 180f;
            }

            SirenBullseyeMembershipEvidence selectedMembership, nativeMembership;
            SirenTargetEligibilityWitnessPolicy.ScanMembershipPair(HurtBox.readOnlyBullseyesList, selectedHurtBox, nativeTarget,
                                                                   SirenTargetEligibilityWitnessPolicy.MaximumGlobalBullseyeScanCount,
                                                                   out selectedMembership, out nativeMembership);
            snapshot.selectedRegistryAvailable = selectedMembership.available;
            snapshot.selectedRegistryMembershipKnown = selectedMembership.known;
            snapshot.selectedInGlobalBullseyeList = selectedMembership.present;
            snapshot.nativeRegistryAvailable = nativeMembership.available;
            snapshot.nativeRegistryMembershipKnown = nativeMembership.known;
            snapshot.nativeInGlobalBullseyeList = nativeMembership.present;
            snapshot.registryScanTruncated = selectedMembership.truncated || nativeMembership.truncated;
            snapshot.registryTotalCount = selectedMembership.totalCount;
            snapshot.registryScannedCount = selectedMembership.scannedCount;

            MeasureEligibilityGeometry(snapshot.aimOrigin, snapshot.heldAimDirection, snapshot.selectedHurtBoxPoint,
                                       snapshot.aimOriginAvailable, snapshot.heldAimDirectionAvailable, snapshot.selectedPointAvailable,
                                       snapshot.trackerLimitsAvailable, snapshot.maxTrackingDistance, snapshot.maxTrackingAngle,
                                       out snapshot.selectedGeometryAvailable, out snapshot.selectedDistance, out snapshot.selectedAimDot,
                                       out snapshot.selectedRangeKnown, out snapshot.selectedWithinRange, out snapshot.selectedConeKnown,
                                       out snapshot.selectedWithinCone, out snapshot.selectedLosKnown, out snapshot.selectedLineOfSight);

            if (nativeTarget)
            {
                snapshot.nativeHurtBoxAvailable = true;
                snapshot.nativeHurtBoxEnabled = nativeTarget.enabled;
                snapshot.nativeHurtBoxActive = nativeTarget.gameObject.activeInHierarchy;
                snapshot.nativeHurtBoxBullseye = nativeTarget.isBullseye;
                snapshot.nativeHurtBoxLayer = nativeTarget.gameObject.layer;
                snapshot.nativeHurtBoxTeamIndex = (int)nativeTarget.teamIndex;
                snapshot.nativeHurtBoxTeamAvailable = true;
                snapshot.nativeHurtBoxPoint = nativeTarget.transform.position;
                snapshot.nativePointAvailable = IsFinite(snapshot.nativeHurtBoxPoint);
                HealthComponent targetHealth = nativeTarget.healthComponent;
                if (targetHealth)
                {
                    snapshot.nativeHurtBoxHealthAvailable = true;
                    snapshot.nativeHurtBoxHealthAlive = targetHealth.alive;
                    CharacterBody nativeBody = targetHealth.body;
                    if (nativeBody)
                    {
                        snapshot.nativeBodyAvailable = true;
                        snapshot.nativeBodyIndex = (int)nativeBody.bodyIndex;
                        if (nativeBody.teamComponent)
                        {
                            snapshot.nativeTeamAvailable = true;
                            snapshot.nativeBodyTeamIndex = (int)nativeBody.teamComponent.teamIndex;
                        }
                    }
                }
                if (nativeTarget.collider)
                {
                    snapshot.nativeColliderAvailable = true;
                    snapshot.nativeColliderEnabled = nativeTarget.collider.enabled;
                    snapshot.nativeColliderLayer = nativeTarget.collider.gameObject.layer;
                }
                MeasureEligibilityGeometry(snapshot.aimOrigin, snapshot.heldAimDirection, snapshot.nativeHurtBoxPoint,
                                           snapshot.aimOriginAvailable, snapshot.heldAimDirectionAvailable, snapshot.nativePointAvailable,
                                           snapshot.trackerLimitsAvailable, snapshot.maxTrackingDistance, snapshot.maxTrackingAngle,
                                           out snapshot.nativeGeometryAvailable, out snapshot.nativeDistance, out snapshot.nativeAimDot,
                                           out snapshot.nativeRangeKnown, out snapshot.nativeWithinRange, out snapshot.nativeConeKnown,
                                           out snapshot.nativeWithinCone, out snapshot.nativeLosKnown, out snapshot.nativeLineOfSight);
            }
            snapshot.captured = true;
        }
        catch (Exception error)
        {
            report.eligibilitySnapshotErrors++;
            snapshot.errorType = error.GetType().FullName;
            report.lastEligibilitySnapshotErrorType = snapshot.errorType;
            snapshot.captured = false;
        }
    }

    static void MeasureEligibilityGeometry(Vector3 origin, Vector3 aimDirection, Vector3 point, bool originAvailable, bool aimAvailable,
                                           bool pointAvailable, bool limitsAvailable, float maxDistance, float maxAngle,
                                           out bool geometryAvailable, out float distance, out float aimDot, out bool rangeKnown,
                                           out bool withinRange, out bool coneKnown, out bool withinCone, out bool losKnown,
                                           out bool lineOfSight)
    {
        geometryAvailable = rangeKnown = coneKnown = losKnown = false;
        distance = aimDot = 0f;
        withinRange = withinCone = lineOfSight = false;
        Vector3 direction = point - origin;
        if (!originAvailable || !pointAvailable || !IsFinite(direction) || !(direction.sqrMagnitude > 0f))
            return;
        distance = direction.magnitude;
        RaycastHit hit;
        lineOfSight =
            !Physics.Raycast(origin, direction, out hit, direction.magnitude, LayerIndex.world.mask, QueryTriggerInteraction.UseGlobal);
        losKnown = true;
        if (!aimAvailable)
            return;
        aimDot = Vector3.Dot(aimDirection, direction.normalized);
        geometryAvailable = SirenTargetEligibilityWitnessPolicy.IsFinite(distance) && SirenTargetEligibilityWitnessPolicy.IsFinite(aimDot);
        if (geometryAvailable && limitsAvailable)
        {
            rangeKnown = coneKnown = SirenTargetEligibilityWitnessPolicy.TryMeasureRangeAndCone(distance, aimDot, maxDistance, maxAngle,
                                                                                                out withinRange, out withinCone);
        }
    }

    static bool IsFinite(Vector3 value) => SirenTargetEligibilityWitnessPolicy.IsFinite(value.x) &&
                                           SirenTargetEligibilityWitnessPolicy.IsFinite(value.y) &&
                                           SirenTargetEligibilityWitnessPolicy.IsFinite(value.z);

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
        navigationObservation.ResetTriggerContinuity();
        navigationObservation.Complete(reason);
        ReleaseIfStillOwned();
        report.stopReason = reason;
    }

    void Stop(string reason)
    {
        if (terminal)
            return;
        navigationObservation.Complete(reason);
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
        navigationObservation.Dispose();
        ReleaseIfStillOwned();
        report.cleaned = true;
        disposed = true;
        ownedBridge = null;
    }
}
