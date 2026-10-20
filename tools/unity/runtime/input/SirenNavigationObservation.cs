using System;
using RoR2;
using UnityEngine;

[Serializable]
public struct SirenNavigationObservationSample
{
    public float realtimeSeconds;
    public uint selectedEggNetworkId;
    public int requestId, requestWrittenAfterFixedTick, observedAfterFixedTick;
    public Vector2 requestedBridgeMovement;
    public Vector3 appliedInputMoveVector, motorVelocity, bodyPosition, footPosition;
    public bool motorGrounded;
    public bool pathWaypointAvailable, pathNodeAvailable, pathRequestAvailable;
    public Vector3 pathWaypoint;
    public string pathNodeIdentity, pathRequestReason, movementState;
    public float pathRequestStageSeconds, pathRequestAgeSeconds;
}

[Serializable]
public sealed class SirenNavigationObservationReport
{
    public const int Capacity = 8;
    public bool started, completed;
    public uint selectedEggNetworkId;
    public float startedRealtimeSeconds, triggerEggDistance, triggerTrackerMaximumDistance;
    public float triggerObjectiveStalledSeconds, triggerSameEggOutOfRangeSeconds;
    public int sampleCount;
    public string stopReason;
    public SirenNavigationObservationSample[] samples = new SirenNavigationObservationSample[Capacity];
}

public static class SirenNavigationObservationPolicy
{
    public const float MinimumOutOfRangeSeconds = .5f;
    public const float MinimumObjectiveStallSeconds = 6f;
    public const float SampleIntervalSeconds = 1f;
    public const float MaximumWindowSeconds = 8f;
    public const int MaximumSamples = 8;
    public static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    public static bool ShouldStart(bool selected, uint eggId, float distance, float maxDistance, float rangeAge, float stall)
    {
        return selected && eggId != 0 && Finite(distance) && Finite(maxDistance) && maxDistance >= 0 && distance > maxDistance &&
               Finite(rangeAge) && rangeAge >= MinimumOutOfRangeSeconds && Finite(stall) && stall > MinimumObjectiveStallSeconds;
    }

    public static bool ShouldComplete(int count, float age) => count >= MaximumSamples || !Finite(age) || age < 0 || age >= MaximumWindowSeconds;

    public static bool PathRequestAvailable(bool requestExists, int requestId, string reason, float stageSeconds, float ageSeconds,
                                            bool pathGraphAvailable)
    {
        return requestExists && requestId > 0 && !string.IsNullOrEmpty(reason) && pathGraphAvailable && Finite(stageSeconds) &&
               stageSeconds >= 0 && Finite(ageSeconds) && ageSeconds >= 0;
    }
}

// The recorder owns only copied values. Production supplies a reader backed by the
// current Siren owner; tests supply a fake. It never retains Unity object references.
public interface ISirenNavigationObservationReader
{
    bool Available { get; }
    bool TryRead(Vector2 requestedMovement, int requestWrittenAfterFixedTick, int observedAfterFixedTick,
                 float realtimeSeconds, out SirenNavigationObservationSample sample);
}

public sealed class SirenNavigationObservationRecorder
{
    public readonly SirenNavigationObservationReport report;
    uint rangeEggId;
    float rangeSince = float.NaN, lastRealtime = float.NaN, lastSampleRealtime = float.NaN;
    Vector2 pendingMovement;
    int pendingWrittenAfterTick;
    bool pending;

    public SirenNavigationObservationRecorder(SirenNavigationObservationReport report = null)
    {
        this.report = report ?? new SirenNavigationObservationReport();
    }

    public bool ObserveTrigger(bool selected, bool trackerAvailable, uint eggId, float distance, float maxDistance,
                              float stallSeconds, float realtimeSeconds)
    {
        if (report.started || report.completed)
            return false;
        if (!ObserveClock(realtimeSeconds))
        {
            rangeEggId = 0;
            rangeSince = float.NaN;
            return false;
        }
        if (!selected || !trackerAvailable || eggId == 0 || !SirenNavigationObservationPolicy.Finite(distance) ||
            !SirenNavigationObservationPolicy.Finite(maxDistance) || maxDistance < 0 || distance <= maxDistance)
        {
            rangeEggId = 0;
            rangeSince = float.NaN;
            return false;
        }
        if (rangeEggId != eggId || !SirenNavigationObservationPolicy.Finite(rangeSince))
        {
            rangeEggId = eggId;
            rangeSince = realtimeSeconds;
            return false;
        }
        float rangeAge = realtimeSeconds - rangeSince;
        if (!SirenNavigationObservationPolicy.ShouldStart(selected, eggId, distance, maxDistance, rangeAge, stallSeconds))
            return false;
        report.started = true;
        report.selectedEggNetworkId = eggId;
        report.startedRealtimeSeconds = realtimeSeconds;
        report.triggerEggDistance = distance;
        report.triggerTrackerMaximumDistance = maxDistance;
        report.triggerObjectiveStalledSeconds = stallSeconds;
        report.triggerSameEggOutOfRangeSeconds = rangeAge;
        return true;
    }

    public void QueueRequest(Vector2 movement, int bridgeFixedTicks)
    {
        if (!report.started || report.completed)
            return;
        pendingMovement = movement;
        pendingWrittenAfterTick = bridgeFixedTicks;
        pending = true;
    }

    public void ResetTriggerContinuity()
    {
        if (report.started || report.completed)
            return;
        rangeEggId = 0;
        rangeSince = float.NaN;
    }

    public void OnBridgeIdentityChanged()
    {
        ResetTriggerContinuity();
        Complete("bridge-instance-changed");
    }

    // Call at the beginning of every Siren Apply frame, before NavigateWorldInput
    // can overwrite the bridge request. A missing owner/dependency closes the
    // trace; an old request is never retained across an unavailable gap.
    public bool ObservePending(uint currentEggId, float realtimeSeconds, bool ownerActive, int bridgeFixedTicks,
                              ISirenNavigationObservationReader reader)
    {
        if (!report.started || report.completed)
            return false;
        if (!ObserveClock(realtimeSeconds))
        {
            Complete("invalid-clock");
            return false;
        }
        float age = realtimeSeconds - report.startedRealtimeSeconds;
        if (SirenNavigationObservationPolicy.ShouldComplete(report.sampleCount, age))
        {
            Complete(report.sampleCount >= SirenNavigationObservationReport.Capacity ? "sample-cap" : "window-expired");
            return false;
        }
        if (!ownerActive)
        {
            Complete("owner-inactive");
            return false;
        }
        if (currentEggId != report.selectedEggNetworkId)
        {
            Complete("selected-egg-changed");
            return false;
        }
        if (!pending)
            return false;
        if (reader == null || !reader.Available)
        {
            ClearPending();
            Complete("observation-dependency-unavailable");
            return false;
        }
        if (bridgeFixedTicks <= pendingWrittenAfterTick)
            return false;
        float sinceLastSample = report.sampleCount == 0 ? 0 : realtimeSeconds - lastSampleRealtime;
        if (report.sampleCount > 0 && sinceLastSample < SirenNavigationObservationPolicy.SampleIntervalSeconds)
            return false;
        SirenNavigationObservationSample sample;
        if (!reader.TryRead(pendingMovement, pendingWrittenAfterTick, bridgeFixedTicks, realtimeSeconds, out sample))
        {
            ClearPending();
            Complete("observation-read-unavailable");
            return false;
        }
        if (sample.requestWrittenAfterFixedTick != pendingWrittenAfterTick || sample.observedAfterFixedTick <= pendingWrittenAfterTick)
        {
            ClearPending();
            Complete("observation-tick-contract-invalid");
            return false;
        }
        sample.selectedEggNetworkId = currentEggId;
        report.samples[report.sampleCount++] = sample;
        lastSampleRealtime = realtimeSeconds;
        ClearPending();
        if (report.sampleCount >= SirenNavigationObservationReport.Capacity)
            Complete("sample-cap");
        return true;
    }

    public void Maintain(float realtimeSeconds, bool ownerActive)
    {
        if (!report.started || report.completed)
            return;
        if (!ObserveClock(realtimeSeconds))
        {
            Complete("invalid-clock");
            return;
        }
        float age = realtimeSeconds - report.startedRealtimeSeconds;
        if (SirenNavigationObservationPolicy.ShouldComplete(report.sampleCount, age))
        {
            Complete(report.sampleCount >= SirenNavigationObservationReport.Capacity ? "sample-cap" : "window-expired");
            return;
        }
        if (!ownerActive)
            Complete("owner-inactive");
    }

    bool ObserveClock(float now)
    {
        if (!SirenNavigationObservationPolicy.Finite(now) ||
            SirenNavigationObservationPolicy.Finite(lastRealtime) && now < lastRealtime)
            return false;
        lastRealtime = now;
        return true;
    }

    void ClearPending()
    {
        pending = false;
        pendingMovement = Vector2.zero;
        pendingWrittenAfterTick = 0;
    }

    public void Complete(string reason)
    {
        if (!report.started || report.completed)
            return;
        report.completed = true;
        report.stopReason = string.IsNullOrEmpty(reason) ? "owner-ended" : reason;
        ClearPending();
    }

    public void Dispose() => Complete("owner-disposed");
}

public sealed class SirenNavigationObservationApi : ISirenNavigationObservationReader
{
    readonly CharacterBody player;
    readonly NovaInputBridge bridge;
    readonly PathFollower pathFollower;
    readonly int requestId;
    readonly bool requestExists;
    readonly float requestStageSeconds, requestAgeSeconds;
    readonly string requestReason, movementState;

    public SirenNavigationObservationApi(CharacterBody player, NovaInputBridge bridge, PathFollower pathFollower,
                                        int requestId, bool requestExists, float requestStageSeconds, float requestAgeSeconds,
                                        string requestReason, string movementState)
    {
        this.player = player;
        this.bridge = bridge;
        this.pathFollower = pathFollower;
        this.requestId = requestId;
        this.requestExists = requestExists;
        this.requestStageSeconds = requestStageSeconds;
        this.requestAgeSeconds = requestAgeSeconds;
        this.requestReason = requestReason;
        this.movementState = movementState;
    }

    public bool Available => player && bridge && player.inputBank && player.characterMotor && bridge.isActiveAndEnabled;
    static string Label(string value) => string.IsNullOrEmpty(value) ? "unavailable" : value.Length <= 64 ? value : value.Substring(0, 64);

    public bool TryRead(Vector2 movement, int writtenTick, int observedTick, float now, out SirenNavigationObservationSample sample)
    {
        sample = default(SirenNavigationObservationSample);
        if (!Available || observedTick <= writtenTick)
            return false;
        bool pathAvailable = SirenNavigationObservationPolicy.PathRequestAvailable(requestExists, requestId, requestReason,
                                                                                    requestStageSeconds, requestAgeSeconds,
                                                                                    pathFollower != null && pathFollower.nodeGraph != null);
        Vector3? waypoint = pathFollower == null ? (Vector3?)null : pathFollower.GetNextPosition();
        sample = new SirenNavigationObservationSample {
            realtimeSeconds = now,
            requestId = pathAvailable ? requestId : 0,
            requestWrittenAfterFixedTick = writtenTick,
            observedAfterFixedTick = observedTick,
            requestedBridgeMovement = movement,
            appliedInputMoveVector = player.inputBank.moveVector,
            motorVelocity = player.characterMotor.velocity,
            motorGrounded = player.characterMotor.isGrounded,
            bodyPosition = player.transform.position,
            footPosition = player.temporaryPathfindingFootpositionDoNotUseWillBePatchedOut,
            pathWaypointAvailable = waypoint.HasValue,
            pathWaypoint = waypoint.GetValueOrDefault(),
            pathNodeAvailable = pathFollower != null && pathFollower.nextNode != RoR2.Navigation.NodeGraph.NodeIndex.invalid,
            pathNodeIdentity = pathFollower == null ? "unavailable" : Label(pathFollower.nextNode.ToString()),
            pathRequestAvailable = pathAvailable,
            pathRequestStageSeconds = pathAvailable ? requestStageSeconds : 0,
            pathRequestAgeSeconds = pathAvailable ? requestAgeSeconds : 0,
            pathRequestReason = pathAvailable ? Label(requestReason) : "unavailable",
            movementState = Label(movementState)
        };
        return true;
    }
}
