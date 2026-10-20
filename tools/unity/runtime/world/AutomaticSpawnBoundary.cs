// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup AutomaticSpawnBoundary; teardown —.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

// Original Unity callbacks; the harness only observes and supplies diagnostic input.
public sealed partial class PortSession
{
    internal static void CaptureAutomaticSpawnCleanup(Action action, ref Exception failure)
    {
        try
        {
            action();
        }
        catch (Exception error)
        {
            failure = failure == null ? error : new AggregateException(failure, error);
        }
    }

    internal static void AcquireAutomaticSpawnCallback(Action subscribe, ref bool attempted)
    {
        // Mark before invoking the event add accessor: if an accessor mutates then throws,
        // the finally path still makes a best-effort idempotent unsubscribe.
        attempted = true;
        subscribe();
    }

    internal static void ReleaseAutomaticSpawnCallback(Action unsubscribe, bool attempted, ref Exception failure)
    {
        if (attempted)
            CaptureAutomaticSpawnCleanup(unsubscribe, ref failure);
    }

    internal static EntityStateMachine[] CaptureCanonicalSkillMachines(SkillLocator skills, Action<bool, string> check)
    {
        check(skills && skills.primary && skills.secondary && skills.utility && skills.special,
              "Original playable body is missing a canonical skill slot before spawn callbacks");
        var captured =
            new[] { skills.primary.stateMachine, skills.secondary.stateMachine, skills.utility.stateMachine, skills.special.stateMachine };
        check(captured.Length == 4 && captured.All(stateMachine => stateMachine),
              "Original playable body is missing a canonical skill state machine before spawn callbacks");
        return captured;
    }

    internal static EntityStateMachine[] CaptureCanonicalSkillMachinesForCleanup(SkillLocator skills)
    {
        return CaptureCanonicalSkillMachines(skills, (valid, message) =>
                                                     {
                                                         if (!valid)
                                                             throw new InvalidOperationException(message);
                                                     });
    }

    internal static bool ContainsStateMachineReference(EntityStateMachine[] candidates, EntityStateMachine sought)
    {
        if (candidates == null)
            return false;
        foreach (var candidate in candidates)
            if (ReferenceEquals(candidate, sought))
                return true;
        return false;
    }

    internal static Exception DestroyOwnedPlayableSkillMachines(EntityStateMachine[] captured, EntityStateMachine[] currentCanonical,
                                                                EntityStateMachine[] currentRootMachines, GameObject ownerObject,
                                                                EntityStateMachine bodyMachine, bool ownerAlive,
                                                                bool expectedOwnerDestruction, Action<EntityStateMachine> destroy,
                                                                out int unavailable)
    {
        unavailable = 0;
        // Unity's native body destruction already invokes child OnDestroy callbacks. Treat
        // fake-null children as complete only when the owner recorded its native destruction.
        if (!ownerAlive)
            return expectedOwnerDestruction
                       ? null
                       : new InvalidOperationException("Playable body disappeared without recorded native destruction");
        if (!ownerObject || captured == null || currentCanonical == null || currentRootMachines == null || destroy == null)
        {
            unavailable++;
            return new InvalidOperationException("Playable skill-machine cleanup lease is incomplete for a live body");
        }

        int invalidReferences = 0;
        var merged = new List<EntityStateMachine>();
        Action<EntityStateMachine> include = stateMachine =>
        {
            if (ReferenceEquals(stateMachine, bodyMachine) || ContainsStateMachineReference(merged.ToArray(), stateMachine))
                return;
            if (!stateMachine || stateMachine.gameObject != ownerObject ||
                !ContainsStateMachineReference(currentRootMachines, stateMachine))
            {
                invalidReferences++;
                return;
            }
            merged.Add(stateMachine);
        };
        foreach (var stateMachine in captured)
            include(stateMachine);
        foreach (var stateMachine in currentCanonical)
            include(stateMachine);

        unavailable = invalidReferences;
        Exception failure =
            unavailable == 0
                ? null
                : new InvalidOperationException("Live playable body lost or replaced a root-owned canonical skill state machine");
        foreach (var stateMachine in merged)
        {
            try
            {
                destroy(stateMachine);
            }
            catch (Exception error)
            {
                failure = failure == null ? error : new AggregateException(failure, error);
            }
        }
        return failure;
    }

    internal static int RestoreCapturedEnabledRootStateMachines(EntityStateMachine[] captured, bool integratedWorld)
    {
        if (!integratedWorld || captured == null)
            return 0;
        int restored = 0;
        foreach (var stateMachine in captured)
            if (stateMachine && !stateMachine.enabled)
            {
                stateMachine.enabled = true;
                restored++;
            }
        return restored;
    }

    IEnumerator AutomaticSpawnBoundary(CharacterBody body, SessionConfig cfg)
    {
        if (!ownsStateCatalog)
        {
            var preparation = PrepareSpawnStateCatalog(cfg);
            while (preparation.MoveNext())
                yield return preparation.Current;
        }
        var machine = EntityStateMachine.FindByCustomName(body.gameObject, "Body");
        var motor = body.characterMotor;
        var solver = body.GetComponent<KinematicCharacterMotor>();
        var input = body.inputBank;
        var spawnedMaster = body.master;
        var rootEntityStateMachines = body.GetComponents<EntityStateMachine>();
        var sourceEnabledRootStateMachines = rootEntityStateMachines.Where(stateMachine => stateMachine && stateMachine.enabled).ToArray();
        EntityStateMachine[] playableSkillMachines = null;
        if (IsPlayableSpine())
        {
            playableSkillMachines = CaptureCanonicalSkillMachines(body.skillLocator, Check);
            Check(playableSkillMachines.All(stateMachine => stateMachine.gameObject == body.gameObject &&
                                                            ContainsStateMachineReference(rootEntityStateMachines, stateMachine)),
                  "Original playable skill slots must bind to state machines on their owned body root");
        }
        Exception automaticSpawnCleanupFailure = null;
        bool automaticBody = IsAutomaticBody(), automaticDirection = IsAutomaticDirection(), automaticModel = IsAutomaticModel();
        var direction = body.GetComponent<CharacterDirection>();
        if (automaticDirection)
            Check(direction && !direction.modelAnimator, "Direction Start already ran; refuse automatic scheduling claim");
        bool movingMotor = r.id != "body-state-spawn-state-auto-state", scripted = r.id == "body-state-spawn-state-auto-motion";
        Check(machine && machine.state is Uninitialized && machine.initialStateType.stateType == typeof(SpawnTeleporterState) &&
                  machine.mainStateType.stateType != null && typeof(GenericCharacterMain).IsAssignableFrom(machine.mainStateType.stateType),
              "Original automatic state starting identity");
        Check(motor && solver && motor.Motor == solver && input && !body.gameObject.activeInHierarchy,
              "Automatic fixture motor/input isolation");
        var model = body.modelLocator.modelTransform.GetComponent<CharacterModel>();
        int invisible = model.invisibilityCount;
        var savedGravity = Physics.gravity;
        var savedLayers = solver.CollidableLayers;
        bool savedSolving = (bool)typeof(KinematicCharacterMotor)
                                .GetField("_solveGrounding", BindingFlags.Instance | BindingFlags.NonPublic)
                                .GetValue(solver);
        Action<CharacterBody> observed = b =>
        {
            if (b == body)
                r.motorStartEvents++;
        };
        bool observedSubscriptionAttempted = false, masterSubscriptionAttempted = false, bodySubscriptionAttempted = false,
             statsSubscriptionAttempted = false;
        bool automaticSpawnSetupStarted = false;
        Action<CharacterBody> masterStarted =
                                  b =>
        {
            if (b == body)
                r.masterStartEvents++;
        },
                              bodyStarted =
                                  b =>
        {
            if (b == body)
                r.bodyStartEvents++;
        },
                              stats = b =>
        {
            if (b == body)
                r.automaticBodyStatsEvents++;
        };
        try
        {
            // Enclose acquisition itself so partial subscription setup is always unwound.
            AcquireAutomaticSpawnCallback(() => motor.onMotorStart += observed, ref observedSubscriptionAttempted);
            if (automaticBody)
            {
                AcquireAutomaticSpawnCallback(() => spawnedMaster.onBodyStart += masterStarted, ref masterSubscriptionAttempted);
                AcquireAutomaticSpawnCallback(() => CharacterBody.onBodyStartGlobal += bodyStarted, ref bodySubscriptionAttempted);
                AcquireAutomaticSpawnCallback(() => body.onRecalculateStats += stats, ref statsSubscriptionAttempted);
            }
            automaticSpawnSetupStarted = true;
            // Body-enabled probes use only Unity Start/Update/FixedUpdate; other root callbacks remain inactive.
            foreach (var component in body.GetComponents<MonoBehaviour>())
                component.enabled = false;
            if (automaticModel)
                PrepareAutomaticModel(body);
            machine.enabled = true;
            if (movingMotor)
                motor.enabled = true;
            if (automaticBody)
                body.enabled = true;
            if (automaticDirection)
                direction.enabled = true;
            if (automaticModel)
                body.modelLocator.enabled = true;
            if (IsAutomaticSkill())
                EnableAutomaticSkills(body);
            if (IsPlayableSpine())
            {
                foreach (var skill in cfg.combatSpine ? new[] { body.skillLocator.primary, body.skillLocator.secondary,
                                                                body.skillLocator.utility, body.skillLocator.special }
                                                      : new[] { body.skillLocator.primary })
                {
                    skill.enabled = true;
                    skill.stateMachine.enabled = true;
                }
            }
            int restoredSourceEnabledStateMachines =
                RestoreCapturedEnabledRootStateMachines(sourceEnabledRootStateMachines, cfg.integratedWorld);
            sourceEnabledRootStateMachines = null;
            r.automaticCallbacks = body.GetComponents<MonoBehaviour>().Where(x => x.enabled).Select(x => x.GetType().FullName).ToArray();
            if (!cfg.combatSpine)
                Check(r.automaticCallbacks.Length == (movingMotor ? 2 : 1) + (automaticBody ? 1 : 0) + (automaticDirection ? 1 : 0) +
                                                         (automaticModel ? 1 : 0) + AutomaticSkillCount() + (IsPlayableSpine() ? 2 : 0) +
                                                         restoredSourceEnabledStateMachines,
                      "Unexpected enabled root callback");
            Physics.gravity = Vector3.zero;
            solver.SetGroundSolvingActivation(false);
            input.moveVector = Vector3.zero;
            r.phase = "automatic-spawn-state-start";
            Save();
            body.gameObject.SetActive(true);
            yield return null;
            Check(machine.state is SpawnTeleporterState && body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility) == 1 &&
                      model.invisibilityCount == invisible + 1,
                  "Automatic original spawn Start/buff/model effects");
            r.spawnStateEntries++;
            if (automaticBody)
            {
                r.spawnedHealth = body.healthComponent.health;
                r.spawnedSkinIndex = body.skinIndex;
                r.automaticBodyRegistered = CharacterBody.readOnlyInstancesList.Contains(body);
                Save();
                Check(r.masterStartEvents == 1 && r.bodyStartEvents == 1 && r.automaticBodyStatsEvents >= 1 && r.automaticBodyRegistered &&
                          r.spawnedHealth == body.baseMaxHealth,
                      "Original automatic body Start/events/stats/registration");
            }
            if (movingMotor)
            {
                r.rawAuthority = body.hasAuthority;
                r.effectiveAuthority = RoR2.Util.HasEffectiveAuthority(body.gameObject);
                Check(r.motorStartEvents == 1 && motor.hasEffectiveAuthority && r.effectiveAuthority && !r.rawAuthority && motor.useGravity,
                      "Automatic original motor Start/authority");
                Check(solver.enabled && KinematicCharacterSystem.CharacterMotors_Important.Contains(solver) &&
                          KinematicCharacterSystem.Settings.AutoSimulation,
                      "Original automatic solver registration/settings");
                r.automaticSolverRegistered = true;
                solver.CollidableLayers = 0; // Start rebuilds layers; isolate collisions only after the original callback.
            }
            else
                Check(!solver.enabled && !KinematicCharacterSystem.CharacterMotors_Important.Contains(solver),
                      "State-only probe unexpectedly schedules solver");
            var deadline = Time.realtimeSinceStartup + cfg.sourceSpawnDelay + 3;
            while (machine.state is SpawnTeleporterState && Time.realtimeSinceStartup < deadline)
            {
                ObserveTeleportOverlays(body);
                TemporaryOverlayManager.OverlayUpdate();
                yield return null;
            }
            // The final spawn tick and transition can occur before the coroutine resumes.
            ObserveTeleportOverlays(body);
            r.spawnState = machine.state.GetType().FullName;
            r.hiddenBuffCount = body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);
            r.spawnedStateAge = SpawnedStateAge(machine.state, "age");
            r.spawnedFixedAge = SpawnedStateAge(machine.state, "fixedAge");
            Save();
            Check(machine.state is GenericCharacterMain && model.invisibilityCount == invisible,
                  "Automatic original timed transition/model exit");
            float buffDuration = 0;
            Check(r.hiddenBuffCount == 1 &&
                      body.GetTimedBuffTotalDurationForIndex(RoR2Content.Buffs.HiddenInvincibility.buffIndex, out buffDuration) &&
                      buffDuration > 2.5f && buffDuration <= 3f && (automaticBody || buffDuration == 3f),
                  "Original spawn exit timed hidden buff duration");
            r.spawnExitBuffSeconds = buffDuration;
            Check(r.teleportOverlays == 1, "Original automatic spawn overlay not observed");
            r.spawnState = machine.state.GetType().FullName;
            r.spawnedMoveSpeed = body.moveSpeed;
            r.spawnedAcceleration = body.acceleration;
            Check((cfg.enemySpine ? body.healthComponent.health > 0 && body.maxHealth == body.baseMaxHealth
                                  : body.healthComponent.health == body.baseMaxHealth) &&
                      body.moveSpeed == body.baseMoveSpeed && body.acceleration == body.baseAcceleration &&
                      body.jumpPower == body.baseJumpPower,
                  "Original automatic spawned computed stats");
            if (IsAutomaticHealth())
            {
                if (IsPlayableSpine())
                    body.healthComponent.enabled = true;
                else
                {
                    var healthRoutine = AutomaticHealthBoundary(body, machine);
                    while (healthRoutine.MoveNext())
                        yield return healthRoutine.Current;
                    if (r.sourceStageLifecycleRecoveryRequired)
                        yield break;
                }
            }
            if (IsAutomaticSkill())
                StartAutomaticSkillTiming(body);
            if (IsNovaInput())
            {
                var novaRoutine = NovaInputBoundary(body, machine, cfg);
                while (novaRoutine.MoveNext())
                    yield return novaRoutine.Current;
                if (r.sourceStageLifecycleRecoveryRequired)
                    yield break;
                if (r.sirenSourceEntryDiagnosticAttempt)
                {
                    Check(r.sirenSourceEntryDiagnosticCleanupObserved,
                          "Siren source-entry diagnostic did not complete exact encounter/source cleanup");
                    Save();
                    yield break;
                }
                if (restartRequested)
                {
                    Check(CompletedOfflineAbandon() || CompletedResultsReturn() ||
                              (r.playerDefeat != null && r.playerDefeat.bodyDestroyed && r.playerDefeat.deathEntered && !body),
                          "Restart before owned session exit or original ending completed");
                    yield break;
                }
            }
            else if (automaticDirection)
            {
                var directionRoutine = AutomaticDirectionBoundary(body, machine);
                while (directionRoutine.MoveNext())
                    yield return directionRoutine.Current;
                if (r.sourceStageLifecycleRecoveryRequired)
                    yield break;
            }
            else if (r.id == "body-state-spawn-state-auto-gravity" || IsRecoveredLanding())
            {
                var groundRoutine = AutomaticGroundBoundary(body, machine, cfg);
                while (groundRoutine.MoveNext())
                    yield return groundRoutine.Current;
                if (r.sourceStageLifecycleRecoveryRequired)
                    yield break;
            }
            else
            {
                var state = machine.state;
                float age = SpawnedStateAge(state, "age"), fixedAge = SpawnedStateAge(state, "fixedAge");
                var origin = solver.TransientPosition;
                float began = Time.realtimeSinceStartup;
                bool moved = false, stopped = false;
                Vector3 stopPosition = origin;
                if (scripted)
                {
                    input.moveVector = Vector3.right;
                    input.aimDirection = Vector3.right;
                }
                r.phase = scripted ? "automatic-spawned-scripted-motion" : "automatic-spawned-neutral-hold";
                Save();
                while (Time.realtimeSinceStartup - began < 60)
                {
                    ObserveTeleportOverlays(body);
                    TemporaryOverlayManager.OverlayUpdate();
                    if (r.id == "body-state-spawn-state-auto-barrier")
                        ObserveBarrierEffect(body);
                    float elapsed = Time.realtimeSinceStartup - began;
                    Check(machine.state == state && body.gameObject.activeInHierarchy, "Automatic original main state/root changed");
                    if (scripted && !moved && elapsed >= 1)
                    {
                        r.x = solver.TransientPosition.x - origin.x;
                        r.y = solver.TransientPosition.y - origin.y;
                        Check(r.x > 4 && r.x < 9 && Mathf.Abs(r.y) < .001f && Mathf.Abs(motor.velocity.x - body.moveSpeed) < .001f,
                              "Automatic original state/motor/solver movement");
                        input.moveVector = Vector3.zero;
                        moved = true;
                    }
                    if (scripted && moved && !stopped && elapsed >= 2)
                    {
                        r.z = solver.TransientPosition.x - origin.x;
                        stopPosition = solver.TransientPosition;
                        Check(r.z >= r.x && r.z < r.x + 2 && motor.velocity.sqrMagnitude < .000001f && motor.moveDirection == Vector3.zero,
                              "Automatic original state braking");
                        stopped = true;
                    }
                    if (stopped)
                        Check(Vector3.Distance(solver.TransientPosition, stopPosition) < .001f, "Automatic neutral hold drift");
                    if (!scripted)
                        Check(Vector3.Distance(solver.TransientPosition, origin) < .001f, "Automatic neutral position drift");
                    r.automaticFrames++;
                    yield return null;
                }
                r.automaticSeconds = Time.realtimeSinceStartup - began;
                r.spawnedStateAge = SpawnedStateAge(state, "age") - age;
                r.spawnedFixedAge = SpawnedStateAge(state, "fixedAge") - fixedAge;
                Check(r.automaticSeconds >= 60 && r.automaticFrames > 300 && r.spawnedStateAge > 55 && r.spawnedFixedAge > 55,
                      "Automatic original sustained frame/fixed ages");
                Check(!scripted || (moved && stopped), "Automatic motion sequence incomplete");
                Save();
            }
            if (r.id == "body-state-spawn-state-auto-barrier")
            {
                ObserveBarrierEffect(body);
                Check(r.barrierMaterialCopies > 0 && r.barrierEffectEntries == 1 && r.barrierEffectExited && r.barrierEffectDestroyed &&
                          !BodyBarrier(body),
                      "Original automatic barrier effect entry/exit/destruction");
            }
            if (IsAutomaticHealth())
            {
                var health = body.healthComponent;
                if (cfg.integratedWorld)
                    Check(health.enabled && health.health > 0 && health.health <= health.fullHealth && health.barrier >= 0 &&
                              health.barrier <= health.fullBarrier,
                          "Original integrated health/barrier outside native limits");
                else
                    Check(
                        health.enabled &&
                            (cfg.enemySpine ? health.health > 0 && health.health <= body.maxHealth : health.health == body.baseMaxHealth) &&
                            health.barrier == 0,
                        "Original automatic health sustained full health/barrier expiry");
            }
            if (automaticBody)
            {
                r.hiddenBuffCount = body.GetBuffCount(RoR2Content.Buffs.HiddenInvincibility);
                r.spawnBuffExpired = r.hiddenBuffCount == 0 && !body.GetTimedBuffTotalDurationForIndex(
                                                                   RoR2Content.Buffs.HiddenInvincibility.buffIndex, out buffDuration);
                r.stationarySeconds = (float)typeof(CharacterBody)
                                          .GetField("notMovingStopwatch", BindingFlags.Instance | BindingFlags.NonPublic)
                                          .GetValue(body);
                Save();
                Check(r.spawnBuffExpired && (IsNovaInput() || r.stationarySeconds > 55) && r.automaticBodyStatsEvents >= 2,
                      "Original automatic body buff expiry/update timer/stat recalculation");
                // A continuing integrated run may have original item, buff and state
                // modifiers after several stages; its level-one numeric baseline is no
                // longer an invariant. Keep exact values for the bounded early probes.
                bool integratedStats = body.healthComponent.health > 0 && body.maxHealth >= body.baseMaxHealth &&
                                       !float.IsNaN(body.moveSpeed) && !float.IsInfinity(body.moveSpeed) &&
                                       !float.IsNaN(body.acceleration) && !float.IsInfinity(body.acceleration) &&
                                       !float.IsNaN(body.jumpPower) && !float.IsInfinity(body.jumpPower) &&
                                       !float.IsNaN(body.attackSpeed) && !float.IsInfinity(body.attackSpeed);
                bool earlyStats = (cfg.enemySpine ? body.healthComponent.health > 0 && body.maxHealth == body.baseMaxHealth
                                                  : body.healthComponent.health == body.baseMaxHealth) &&
                                  body.moveSpeed == body.baseMoveSpeed && body.acceleration == body.baseAcceleration &&
                                  body.jumpPower == body.baseJumpPower;
                Check((cfg.integratedWorld ? integratedStats : earlyStats) && r.bodyStartEvents == 1 && r.masterStartEvents == 1,
                      "Original continuing body stats/Start uniqueness: health=" + body.healthComponent.health + ", max=" + body.maxHealth +
                          ", move=" + body.moveSpeed + ", acceleration=" + body.acceleration + ", jump=" + body.jumpPower +
                          ", attack=" + body.attackSpeed + ", bodyStart=" + r.bodyStartEvents + ", masterStart=" + r.masterStartEvents);
            }
        }
        finally
        {
            // These observer leases are always released, including the source-recovery path.
            ReleaseAutomaticSpawnCallback(() => motor.onMotorStart -= observed, observedSubscriptionAttempted,
                                          ref automaticSpawnCleanupFailure);
            if (automaticBody)
            {
                ReleaseAutomaticSpawnCallback(
                    () =>
                    {
                        if (spawnedMaster)
                            spawnedMaster.onBodyStart -= masterStarted;
                    },
                    masterSubscriptionAttempted, ref automaticSpawnCleanupFailure);
                ReleaseAutomaticSpawnCallback(() => CharacterBody.onBodyStartGlobal -= bodyStarted, bodySubscriptionAttempted,
                                              ref automaticSpawnCleanupFailure);
                ReleaseAutomaticSpawnCallback(
                    () =>
                    {
                        if (body)
                            body.onRecalculateStats -= stats;
                    },
                    statsSubscriptionAttempted, ref automaticSpawnCleanupFailure);
            }
            if (!r.sourceStageLifecycleRecoveryRequired && automaticSpawnSetupStarted)
            {
                if (body)
                    CaptureAutomaticSpawnCleanup(() => body.gameObject.SetActive(false), ref automaticSpawnCleanupFailure);
                if (input)
                    CaptureAutomaticSpawnCleanup(() => input.moveVector = Vector3.zero, ref automaticSpawnCleanupFailure);
                // Capture source identities before any yield: cleanup must not rediscover canonical slots
                // through a body whose native lifecycle may already be unwinding.
                if (playableSkillMachines != null)
                {
                    // A completed native body-destruction path owns child callbacks already.
                    // Otherwise inspect the current canonical binding as well as entry identities:
                    // native skill overrides can remap a slot while this coroutine is suspended.
                    bool ownerAlive = body;
                    bool expectedOwnerDestruction = !ownerAlive && r.playerDefeat != null && r.playerDefeat.bodyDestroyed;
                    EntityStateMachine[] currentCanonical = null;
                    EntityStateMachine[] currentRootMachines = null;
                    if (ownerAlive)
                    {
                        CaptureAutomaticSpawnCleanup(
                            () =>
                            {
                                currentRootMachines = body.GetComponents<EntityStateMachine>();
                                currentCanonical = CaptureCanonicalSkillMachinesForCleanup(body.skillLocator);
                            },
                            ref automaticSpawnCleanupFailure);
                    }
                    int unavailable;
                    var skillCleanupError = DestroyOwnedPlayableSkillMachines(
                        playableSkillMachines, currentCanonical, currentRootMachines, body ? body.gameObject : null, machine, ownerAlive,
                        expectedOwnerDestruction, weapon => Call(weapon, "OnDestroy"), out unavailable);
                    if (skillCleanupError != null)
                        CaptureAutomaticSpawnCleanup(() =>
                                                     { throw skillCleanupError; },
                                                     ref automaticSpawnCleanupFailure);
                }
                if (machine)
                    CaptureAutomaticSpawnCleanup(() => Call(machine, "OnDestroy"), ref automaticSpawnCleanupFailure);
                CaptureAutomaticSpawnCleanup(() => Physics.gravity = savedGravity, ref automaticSpawnCleanupFailure);
                if (solver)
                {
                    CaptureAutomaticSpawnCleanup(() => solver.CollidableLayers = savedLayers, ref automaticSpawnCleanupFailure);
                    CaptureAutomaticSpawnCleanup(() => solver.SetGroundSolvingActivation(savedSolving), ref automaticSpawnCleanupFailure);
                }
                if ((restartRequested || (r.playerDefeat != null && r.playerDefeat.bodyDestroyed)) && ownedDetachedModel)
                    CaptureAutomaticSpawnCleanup(() => Destroy(ownedDetachedModel), ref automaticSpawnCleanupFailure);
            }
            if (automaticSpawnCleanupFailure != null)
            {
                RecordAutomaticSpawnCleanupFailure(r, automaticSpawnCleanupFailure);
            }
        }
        if (r.sourceStageLifecycleRecoveryRequired)
            yield break;
        if (automaticSpawnCleanupFailure != null)
            Check(false, "Automatic spawn cleanup failed after preserving the primary iterator failure: " + automaticSpawnCleanupFailure);
        Check(!automaticBody || !CharacterBody.readOnlyInstancesList.Contains(body), "Original automatic body deregistration");
        Check(machine.state == null && !KinematicCharacterSystem.CharacterMotors_Important.Contains(solver),
              "Automatic state exit/solver unregistration");
    }
}
