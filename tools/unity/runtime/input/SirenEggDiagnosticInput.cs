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
    CharacterBody NearestRevalidatedSourceEgg(Vector3 position);
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

        CharacterBody egg = context.NearestRevalidatedSourceEgg(player.corePosition);
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
        Vector3 point = context.WorldCombatAimPoint(egg, player.inputBank.aimOrigin, out bool visible);
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
        var identity = egg.GetComponent<UnityEngine.Networking.NetworkIdentity>();
        report.lastTargetNetworkId = identity ? identity.netId.Value : 0;
        lastSubmittedPrimary = visible;
        report.stopReason = visible ? "ordinary-primary-requested" : "source-aim-occluded";
        return true;
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
