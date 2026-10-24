// Subsystem: input/camera (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup NovaRawBoundary, NovaInputBoundary (NovaInputSession); teardown input iterator finally; Dispose retains trace state.
using System.Linq;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using EntityStates;
using KinematicCharacterController;
using RoR2;
using UnityEngine;

public static class InputSessionPolicy
{
    public enum Mode { RefuseUnmeasuredPhysicalInput, MeasuredNovaPhysicalInput, AutomaticDiagnosticWithoutPhysicalInput }
    public const string NovaModel = "Retroid Pocket Nova";
    public const string ThorModel = "AYN Thor";
    public static Mode Resolve(string model, bool explicitBringup)
    {
        if (string.Equals(model, NovaModel, StringComparison.Ordinal))
            return Mode.MeasuredNovaPhysicalInput;
        return explicitBringup && string.Equals(model, ThorModel, StringComparison.Ordinal)
                   ? Mode.AutomaticDiagnosticWithoutPhysicalInput
                   : Mode.RefuseUnmeasuredPhysicalInput;
    }
}

public sealed partial class PortSession
{
    static string cachedInputDeviceModel;
    static string CurrentDeviceModel()
    {
        if (!string.IsNullOrEmpty(cachedInputDeviceModel))
            return cachedInputDeviceModel;
#if UNITY_ANDROID && !UNITY_EDITOR
        using (var build = new AndroidJavaClass("android.os.Build")) cachedInputDeviceModel = build.GetStatic<string>("MODEL");
#else
        cachedInputDeviceModel = SystemInfo.deviceModel;
#endif
        return cachedInputDeviceModel;
    }
    bool UsesDiagnosticWithoutPhysicalInput()
    {
        return r != null && InputSessionPolicy.Resolve(CurrentDeviceModel(), r.id != null && r.id.EndsWith("-bringup", StringComparison.Ordinal)) ==
                               InputSessionPolicy.Mode.AutomaticDiagnosticWithoutPhysicalInput;
    }
    [Serializable]
    public class PerformanceReport
    {
        public int frames, fixedTicks, targetFrameRate, requestedFrameRate, vSyncCount, displayRefreshRate, sampledAllocationFrames;
        public long ownLoopAllocatedBytes, worldAllocatedBytes, stimulusAllocatedBytes, saveAllocatedBytes;
        public double ownLoopMs, observersMs, preObserversMs, primaryMs, combatMs, enemyMs, clockMs, worldMs, clientUpdateMs, stimulusMs,
            presentationMs, saveMs, objectiveMs, teleporterMs, moonMs, lootMs, pickupMs, commerceHudMs, lootSupportMs, equipmentMs,
            equipmentStateMs, temporaryEffectMs, flightMs, ammoMs, itemBehaviorsMs, healingMs, bossMs, legendaryMs, itemDisplayMs;
    }
    static double PerformanceMs(long began)
    {
        return (System.Diagnostics.Stopwatch.GetTimestamp() - began) * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
    }
    [Serializable]
    public class NovaSample
    {
        public float seconds;
        public NovaInputBridge.Raw raw;
        public Vector3 input, aim, stateAim, velocity, position;
        public bool grounded, jump;
        public int jumpCount;
    }
    [Serializable]
    public class NovaReport
    {
        public bool originalAimAnimator, characterMatteApproximation;
        public float aimPitchCycle, aimYawCycle;
        public Vector3 modelForward;
        public bool novaOnly, originalInputConsumer, stopped, aimConsumed, rendersOriginalModel, diagnosticInput;
        public bool commandoPrimaryDiagnostic;
        public AndroidNativeSourceSkinLifecycle.Report nativeSourceSkinLifecycle;
        public string inputSource;
        public bool physicalInputAvailable, mappingAvailable;
        public bool automaticDiagnosticInputHeldAtBoundary;
        public int automaticDiagnosticHoldFixedTicks, automaticDiagnosticHoldTransitions;
        public string automaticDiagnosticHoldStage, automaticDiagnosticHoldScope;
        public int samples, fixedTicks, jumpPresses, localJumpCallbacks, jumpTransitions, landings;
        public float seconds, pathLength, planarPathLength, maxRise, diagnosticReturnFireAt;
        public uint spawnedBodyId, masterId;
        public NovaInputBridge.Mapping mapping;
        public List<NovaSample> observations = new List<NovaSample>();
    }
    [Serializable]
    public class NovaTraceChunk
    {
        public string attempt, id;
        public int pid, session, firstSample;
        public NovaSample[] observations;
    }
    NovaInputSession novaInputSession;
    NovaInputSession GetNovaInputSession()
    {
        if (novaInputSession == null)
            novaInputSession = new NovaInputSession(this);
        return novaInputSession;
    }
    void FlushNovaTrace()
    {
        GetNovaInputSession().FlushNovaTrace();
    }
    IEnumerator NovaRawBoundary()
    {
        return GetNovaInputSession().NovaRawBoundary();
    }
    IEnumerator NovaInputBoundary(CharacterBody body, EntityStateMachine machine, SessionConfig cfg)
    {
        return GetNovaInputSession().NovaInputBoundary(body, machine, cfg);
    }
    void OnGUI()
    {
        if (DrawOfflineSettings())
            return;
        if (DrawOfflineStart())
            return;
        if (r != null && r.results != null && r.results.reportGenerated)
        {
            DrawIntegratedResults();
            return;
        }
        if (r != null && r.integratedWorld && r.world != null && r.world.ready)
        {
            DrawIntegratedWorld();
            return;
        }
        if (r != null)
            DrawItemPickupObservation();
        if (r != null && r.phase == "commando-defeated")
        {
            GUI.Label(new Rect(20, 70, 800, 40), "Commando defeated. Close the test, then open Porting Lab again to retry.");
            if (GUI.Button(new Rect(20, 115, 200, 40), "Close test"))
                Application.Quit();
            return;
        }
        if (r != null && r.nova != null && r.nova.commandoPrimaryDiagnostic && r.primary != null)
            GUI.Label(
                new Rect(20, 70, 850, 100),
                "Commando | A: jump | X: primary | Y: secondary | LB: roll | RB: barrage | audio unavailable\nOriginal primary entries: " +
                    r.primary.shots + " | stock: " + r.primary.stockAfter +
                    (r.combat == null ? ""
                                      : "\nTarget HP: " + r.combat.healthAfter.ToString("F1") +
                                            " | damage: " + r.combat.damageDealt.ToString("F1") + " | secondary/roll/barrage: " +
                                            r.combat.secondaryEntries + "/" + r.combat.utilityEntries + "/" + r.combat.specialEntries) +
                    (r.enemy == null
                         ? ""
                         : "\nBeetle HP: " + r.enemy.health.ToString("F1") + " | player HP: " + r.enemy.playerHealth.ToString("F1") +
                               " | AI: " + r.enemy.aiState + " | attacks: " + r.enemy.headbutts));
    }
    bool IsNovaInput()
    {
        return IsPlayableSpine() || r.id == "body-state-spawn-state-auto-nova-controls";
    }

    // Create on first use: Save flushes traces before input setup and after teardown.
    // Keep iterator-local mapping, landing and camera state with the unchanged loop;
    // its finally owns cleanup. Retain trace state after Dispose for the final Save.
    sealed class NovaInputSession : IDisposable
    {
        readonly PortSession coordinator;
        public NovaInputSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        NovaReport novaTraceOwner;
        int novaTraceNextSample;
        float novaTraceNextWrite;
        public void FlushNovaTrace()
        {
            if (coordinator.r == null || !coordinator.r.integratedWorld || coordinator.r.nova == null)
                return;
            if (!ReferenceEquals(novaTraceOwner, coordinator.r.nova))
            {
                novaTraceOwner = coordinator.r.nova;
                novaTraceNextSample = 0;
                novaTraceNextWrite = 0;
            }
            if (coordinator.r.nova.samples <= novaTraceNextSample)
                return;
            bool urgent = !string.IsNullOrEmpty(coordinator.r.firstFailure) || !string.IsNullOrEmpty(coordinator.r.error) ||
                          coordinator.r.phase == "complete";
            if (!urgent && Time.realtimeSinceStartup < novaTraceNextWrite)
                return;
            int first = coordinator.r.nova.samples - coordinator.r.nova.observations.Count;
            if (novaTraceNextSample < first)
            {
                coordinator.r.firstFailure = "Nova input trace lost an unflushed sample";
                coordinator.r.firstFailurePhase = coordinator.r.phase;
                throw new Exception(coordinator.r.firstFailure);
            }
            var samples = coordinator.r.nova.observations.Skip(novaTraceNextSample - first).ToArray();
            var chunk = new NovaTraceChunk { attempt = coordinator.r.attempt,   id = coordinator.r.id,
                                             pid = coordinator.r.pid,           session = coordinator.r.session,
                                             firstSample = novaTraceNextSample, observations = samples };
            var path =
                System.IO.Path.Combine(Application.persistentDataPath, "movement-batch-" + coordinator.r.id + "-" + coordinator.r.pid +
                                                                           "-" + coordinator.r.session + "-input.jsonl");
            File.AppendAllText(path, JsonUtility.ToJson(chunk, false) + "\n");
            novaTraceNextSample = coordinator.r.nova.samples;
            novaTraceNextWrite = Time.realtimeSinceStartup + 5;
        }
        public IEnumerator NovaRawBoundary()
        {
            NovaInputBridge.RequireNova();
            coordinator.r.nova = new NovaReport { novaOnly = true };
            coordinator.r.phase = "nova-raw-ready";
            coordinator.Save();
            float began = Time.realtimeSinceStartup, next = 0;
            while (Time.realtimeSinceStartup - began < 120)
            {
                float elapsed = Time.realtimeSinceStartup - began;
                if (elapsed >= next)
                {
                    coordinator.r.nova.observations.Add(new NovaSample { seconds = elapsed, raw = NovaInputBridge.ReadRaw() });
                    coordinator.r.nova.samples++;
                    coordinator.r.nova.seconds = elapsed;
                    next = elapsed + .05f;
                }
                if (Time.frameCount % 30 == 0)
                    coordinator.Save();
                yield return null;
            }
            coordinator.Check(coordinator.r.nova.samples > 300, "Nova Unity raw capture incomplete");
            coordinator.Save();
        }
        void ObserveManualMoonHold(NovaInputBridge bridge)
        {
            if (!bridge || bridge.manualMoonNeutralFixedTicks <= 0)
                return;
            var report = coordinator.r.nova;
            if (!report.automaticDiagnosticInputHeldAtBoundary)
            {
                report.automaticDiagnosticHoldStage = coordinator.r.stageProgress == null
                                                         ? string.Empty : coordinator.r.stageProgress.current;
                report.automaticDiagnosticHoldTransitions = coordinator.r.stageProgress == null
                                                               ? 0 : coordinator.r.stageProgress.transitions;
                report.automaticDiagnosticHoldScope =
                    "automatic-diagnostic-input-only; touch-equipment preserved; physical route unchanged when diagnosticInput=false";
            }
            report.automaticDiagnosticInputHeldAtBoundary = true;
            report.automaticDiagnosticHoldFixedTicks = bridge.manualMoonNeutralFixedTicks;
        }
        public IEnumerator NovaInputBoundary(CharacterBody body, EntityStateMachine machine, SessionConfig cfg)
        {
            bool spine = coordinator.IsPlayableSpine(), bringup = coordinator.r.id.EndsWith("-bringup", StringComparison.Ordinal);
            bool commandoPrimaryDiagnostic = spine && IsCommandoPrimaryDiagnosticBody(body);
            coordinator.r.integratedWorld = cfg.integratedWorld;
            coordinator.r.teleporterLoop = cfg.teleporterLoop;
            var inputMode = InputSessionPolicy.Resolve(CurrentDeviceModel(), bringup);
            coordinator.Check(inputMode != InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput,
                              "Unmeasured physical input is unavailable outside an explicit bringup diagnostic");
            bool physicalInputAvailable = inputMode == InputSessionPolicy.Mode.MeasuredNovaPhysicalInput;
            bool automaticDiagnosticOnly = inputMode == InputSessionPolicy.Mode.AutomaticDiagnosticWithoutPhysicalInput;
            if (physicalInputAvailable)
                NovaInputBridge.RequireNova();
            coordinator.r.nova = new NovaReport { rendersOriginalModel = spine,
                                                  commandoPrimaryDiagnostic = commandoPrimaryDiagnostic,
                                                  diagnosticInput = bringup || automaticDiagnosticOnly,
                                                  novaOnly = physicalInputAvailable,
                                                  inputSource = physicalInputAvailable ? "measured-nova" : "automatic-diagnostic",
                                                  physicalInputAvailable = physicalInputAvailable,
                                                  spawnedBodyId = body.netId.Value,
                                                  masterId = body.master.netId.Value };
            bool nativeSourceSkinRequested = coordinator.r.nativeSourceSkinLifecycleDiagnosticRequested;
            if (nativeSourceSkinRequested)
            {
                coordinator.r.nova.nativeSourceSkinLifecycle =
                    new AndroidNativeSourceSkinLifecycle.Report { requested = true };
                coordinator.Check(spine && cfg.integratedWorld && coordinator.SelectedSourceSurvivor(),
                                  "Native source skin lifecycle request requires an integrated run and an actual source-selected player model");
            }
            NovaInputBridge.Mapping mapping = null;
            if (physicalInputAvailable)
            {
                var mappingPath = System.IO.Path.Combine(Application.persistentDataPath, "nova-input-mapping.json");
                coordinator.Check(File.Exists(mappingPath), "Measured Nova mapping required before physical Commando test");
                mapping = JsonUtility.FromJson<NovaInputBridge.Mapping>(File.ReadAllText(mappingPath));
                mapping.Validate(coordinator.r.attempt);
                coordinator.Check(!mapping.enableSkills, "Ability execution is a separate probe");
                coordinator.r.nova.mapping = mapping;
                coordinator.r.nova.mappingAvailable = true;
            }
            var motor = body.characterMotor;
            var solver = motor.Motor;
            var state = machine.state;
            var bank = body.inputBank;
            coordinator.Check(state is GenericCharacterMain && body.master.GetBody() == body && body.isServer &&
                                  motor.hasEffectiveAuthority,
                              "Original spawned Commando input/authority contract");
            coordinator.Check(RoR2Content.Items.JumpBoost && DLC3Content.Items.JumpDamageStrike && DLC1Content.Items.GummyCloneIdentifier &&
                                  string.IsNullOrEmpty(body.GetComponent<SfxLocator>().jumpSound),
                              "Combined original empty inventory/jump contract");
            var priorTriggerQueries = Physics.queriesHitTriggers;
            var gravity = Physics.gravity;
            var layers = solver.CollidableLayers;
            var stable = solver.StableGroundLayers;
            NovaInputBridge bridge = null;
            NovaDiagnosticDisplay display = null;
            int sleepTimeout = Screen.sleepTimeout, priorTargetFrameRate = Application.targetFrameRate;
            bool ownsScreenSleepTimeout = !coordinator.IsPlayableSpine();
            if (ownsScreenSleepTimeout)
                Screen.sleepTimeout = SleepTimeout.NeverSleep;
            CharacterBody.JumpDelegate jumped = () =>
            { coordinator.r.nova.localJumpCallbacks++; };
            CharacterMotor.HitGroundDelegate landed = (ref CharacterMotor.HitGroundInfo hit) =>
            { coordinator.r.nova.landings++; };
            body.onJump += jumped;
            motor.onHitGroundAuthority += landed;
            try
            {
                if (cfg.automaticDirector)
                {
                    coordinator.Check(!cfg.sourceQueriesHitTriggers, "Source placement trigger-query flag changed");
                    Physics.queriesHitTriggers = cfg.sourceQueriesHitTriggers;
                }
                if (!cfg.stageGeometry)
                {
                    coordinator.obstacle = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    coordinator.obstacle.name = "Owned Nova floor";
                    coordinator.obstacle.layer = 30;
                    coordinator.obstacle.transform.position = new Vector3(0, 9, 0);
                    coordinator.obstacle.transform.localScale = new Vector3(200, 1, 200);
                }
                solver.StableGroundLayers = cfg.stageGeometry ? (int)LayerIndex.world.mask : 1 << 30;
                solver.CollidableLayers = solver.StableGroundLayers;
                solver.SetGroundSolvingActivation(true);
                Physics.SyncTransforms();
                Physics.gravity = new Vector3(0, cfg.sourceGravity, 0);
                var deadline = Time.realtimeSinceStartup + 3;
                while (!solver.GroundingStatus.IsStableOnGround && Time.realtimeSinceStartup < deadline)
                {
                    yield return new WaitForEndOfFrame();
                    coordinator.ObserveAutomaticModelFollow(body);
                }
                coordinator.Check(solver.GroundingStatus.IsStableOnGround && coordinator.r.nova.landings == 1 &&
                                      body.healthComponent.health == body.maxHealth,
                                  "Original spawned body landing before physical input");
                // Diagnostic aim stance only; original state/direction still choose and turn toward bank aim.
                body.SetAimTimer(130);
                display = new NovaDiagnosticDisplay(body.modelLocator.modelTransform, coordinator.artifactBundle, cfg.displayAssets,
                                                    coordinator.obstacle, spine, cfg.originalAimPresentation ? body : null,
                                                    coordinator.SelectedSourceSurvivor() ? coordinator.r.selectedSurvivor : null,
                                                    nativeSourceSkinRequested, body, coordinator.r.nova.nativeSourceSkinLifecycle);
                if (nativeSourceSkinRequested)
                {
                    float assetDeadline = Time.realtimeSinceStartup + 15f;
                    while (!display.NativeSourceSkinAssetsReady && Time.realtimeSinceStartup < assetDeadline)
                        yield return null;
                    display.CaptureNativeSourceSkinReport();
                    bool skinReady = display.NativeSourceSkinAssetsReady;
                    if (!skinReady)
                        coordinator.r.nova.nativeSourceSkinLifecycle.Fail("Native selected-skin controller/avatar/renderer readiness is not yet established");
                    coordinator.Check(skinReady,
                                      "Original native selected skin did not provide matching controller/avatar/renderer records within 15 seconds");
                    display.EnableNativeSourceAnimatorAfterSkinReady();
                    float animatorDeadline = Time.realtimeSinceStartup + 3f;
                    while (!display.NativeSourceSkinAnimatorReady && Time.realtimeSinceStartup < animatorDeadline)
                        yield return null;
                    display.CaptureNativeSourceSkinReport();
                    bool animatorReady = display.NativeSourceSkinAnimatorReady;
                    if (!animatorReady)
                        coordinator.r.nova.nativeSourceSkinLifecycle.Fail("Original Animator initialization was not observed after native controller/avatar readiness");
                    coordinator.Check(animatorReady,
                                      "Original Animator did not initialize after native selected controller/avatar readiness");
                    display.EnableNativeAimAfterAnimatorReady();
                }
                coordinator.r.framePacing = display.presentationCameraReport;
                if (cfg.stageGeometry && !display.UsesOriginalLocalCamera)
                    display.camera.cullingMask |= LayerIndex.world.mask;
                if (cfg.combatSpine)
                    coordinator.PrepareCombatScene(body, cfg);
                if (cfg.originalRunClock)
                {
                    var sceneContext = coordinator.PrepareRunSceneContext(cfg);
                    while (sceneContext.MoveNext())
                        yield return sceneContext.Current;
                }
                if (!string.IsNullOrEmpty(cfg.playerDeathEffectAsset))
                {
                    var defeatSetup = coordinator.PreparePlayerDefeat(body, cfg);
                    while (defeatSetup.MoveNext())
                        yield return defeatSetup.Current;
                }
                if (cfg.enemySpine)
                {
                    bool nativeFirstStageAttempt = coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt;
                    if (nativeFirstStageAttempt)
                        coordinator.Check(
                            cfg.integratedWorld && cfg.teleporterLoop && coordinator.stageGeometryScene.IsValid() &&
                                (coordinator.stageGeometryScene.name == "golemplains" || coordinator.stageGeometryScene.name == "lakes"),
                            "Native first-stage lifecycle diagnostic is limited to integrated Golemplains/Lakes attempts");
                    foreach (var hurt in body.hurtBoxGroup.hurtBoxes)
                    {
                        hurt.enabled = true;
                        hurt.GetComponent<Collider>().enabled = true;
                    }
                    // The opt-in keeps Run/reward/navigation/source-context preparation but
                    // does not execute the historical early Beetle/CombatDirector fixture.
                    var enemyRoutine =
                        nativeFirstStageAttempt ? coordinator.PrepareEnemyContext(body, cfg) : coordinator.PrepareEnemy(body, cfg);
                    while (enemyRoutine.MoveNext())
                        yield return enemyRoutine.Current;
                }
                if (cfg.integratedWorld)
                {
                    var world = coordinator.PrepareIntegratedWorld(body, cfg);
                    while (world.MoveNext())
                        yield return world.Current;
                }
                if (!cfg.integratedWorld)
                    coordinator.PrepareIntegratedResults(body, cfg);
                if (cfg.teleporterLoop)
                    display.camera.cullingMask |= LayerIndex.defaultLayer.mask;
                if (cfg.integratedWorld)
                {
                    display.ConfigureThirdPerson(body);
                    coordinator.worldView = display.thirdPerson;
                    coordinator.r.world.camera = coordinator.worldView.report;
                }
                bridge = body.gameObject.AddComponent<NovaInputBridge>();
                bridge.bank = bank;
                bridge.mapping = mapping;
                bridge.automaticDiagnosticOnly = automaticDiagnosticOnly;
                if (!physicalInputAvailable)
                {
                    coordinator.worldManualTakeover = false;
                    if (coordinator.r.world != null)
                    {
                        coordinator.r.world.manualTakeover = false;
                        coordinator.r.world.diagnosticInput = true;
                    }
                }
                bridge.enablePrimary = spine;
                bridge.enableAllSkills = cfg.combatSpine;
                bridge.diagnosticInput = bringup;
                if (!string.IsNullOrEmpty(coordinator.r.diagnosticSkillIsolationSlot))
                {
                    bridge.isolatedDiagnosticSkillInput = true;
                    bridge.isolatedDiagnosticSkillSlot = SurvivorSkillInputCoverage.ParseIsolationSlot(
                        coordinator.r.diagnosticSkillIsolationSlot);
                }
                bridge.thirdPerson = display.thirdPerson;
                coordinator.r.nova.originalInputConsumer = true;
                coordinator.worldEquipmentBridge = bridge;
                if (cfg.integratedWorld)
                    coordinator.PrepareDebugAcceleration(body);
                // Android's -1 default is 30 FPS, and the display can change from 60 to 120 Hz after startup.
                // A high request removes the lab's 60 FPS limit; mobile presentation remains display-limited.
                coordinator.r.phase = cfg.integratedWorld ? "integrated-world-playing"
                                      : bringup           ? "nova-spine-bringup"
                                                          : "nova-commando-ready";
                if (cfg.integratedWorld)
                {
                    Application.targetFrameRate = 300;
                    coordinator.r.performance =
                        new PerformanceReport { targetFrameRate = priorTargetFrameRate, requestedFrameRate = Application.targetFrameRate,
                                                vSyncCount = QualitySettings.vSyncCount,
                                                displayRefreshRate = Screen.currentResolution.refreshRate };
                }
                coordinator.Save();
                float began = Time.realtimeSinceStartup, next = 0, nextReportSave = Time.realtimeSinceStartup + 5,
                      restingY = solver.TransientPosition.y, combatBegan = -1;
                var previous = solver.TransientPosition;
                int priorJumpCount = motor.jumpCount;
                float initialAge = SpawnedStateAge(state, "age"), initialFixed = SpawnedStateAge(state, "fixedAge");
                var aimField = typeof(GenericCharacterMain).GetField("aimDirection", BindingFlags.NonPublic | BindingFlags.Instance);
                while (coordinator.r.freePlay ||
                       Time.realtimeSinceStartup - began <
                           (cfg.integratedWorld
                                ? (cfg.teleporterLoop ? (cfg.integratedRuntimeSeconds > 0 ? cfg.integratedRuntimeSeconds : 360) : 120)
                            : bringup ? (cfg.automaticDirector ? 60
                                         : cfg.enemySpine      ? 30
                                                               : 20)
                                      : 90))
                {
                    yield return new WaitForEndOfFrame();
                    long performanceFrame = cfg.integratedWorld ? System.Diagnostics.Stopwatch.GetTimestamp() : 0,
                         performancePart = performanceFrame;
                    long allocatedFrameStart =
                        cfg.integratedWorld && Time.frameCount % 30 == 0 ? GC.GetAllocatedBytesForCurrentThread() : -1;
                    if (coordinator.CompletedResultsReturn() || coordinator.CompletedOfflineAbandon())
                        yield break;
                    bool pauseBeforeMoonBoundary = cfg.pauseBeforeMoon && cfg.teleporterLoop &&
                                                   coordinator.r.stageProgress != null &&
                                                   ManualMoonBoundary.HoldAutomaticProgression(
                                                       cfg.pauseBeforeMoon, coordinator.r.stageProgress.transitions);
                    bridge.SetManualMoonAutomaticHold(pauseBeforeMoonBoundary);
                    ObserveManualMoonHold(bridge);
                    if ((coordinator.r.freePlay || cfg.integratedWorld) && body && !body.healthComponent.alive)
                    {
                        var defeat = coordinator.ObservePlayerDefeat(body, machine, bridge);
                        while (defeat.MoveNext())
                            yield return defeat.Current;
                        if (coordinator.restartRequested)
                            yield break;
                        coordinator.Check(false, "Integrated diagnostic run ended by original player death before objective completion");
                    }
                    if (cfg.integratedWorld)
                        coordinator.Check(string.IsNullOrEmpty(coordinator.r.debugAcceleration.error),
                                          "Debug acceleration failure: " + coordinator.r.debugAcceleration.error);
                    if (coordinator.r.sirenSourceEntryDiagnosticAttempt &&
                        SirenSourceEntryRuntimeContract.NativeListeningRegistrationMatchesSourceEntry(coordinator.r.stageProgress))
                    {
                        coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved = true;
                        if (coordinator.r.sirenNativeEncounterContinuationRequested &&
                            coordinator.r.sirenNativeEncounterContinuationRegistrationObservedAt <= 0)
                            coordinator.r.sirenNativeEncounterContinuationRegistrationObservedAt = Time.realtimeSinceStartup;
                        if (!coordinator.r.sirenNativeEncounterContinuationRequested)
                            break;
                        bool shouldArm =
                            !coordinator.r.sirenNativeEncounterContinuationArmed &&
                            SirenNativeEncounterContinuationContract.MayArm(
                                coordinator.r.sirenNativeEncounterContinuationRequested, coordinator.r.sirenSourceEntryDiagnosticAttempt,
                                true, coordinator.SirenDiagnosticOwnerAttached, coordinator.SirenDiagnosticListenerActive,
                                coordinator.r.diagnosticSirenEggInput, coordinator.SirenNativeEncounterStarted);
                        if (shouldArm)
                        {
                            coordinator.r.sirenNativeEncounterContinuationArmed = true;
                            coordinator.r.sirenNativeEncounterContinuationWasArmed = true;
                            coordinator.r.phase = "siren-native-encounter-continuation-armed";
                            coordinator.Save();
                        }
                    }
                    if (coordinator.r.sirenNativeEncounterContinuationRequested &&
                        coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved &&
                        !coordinator.r.sirenNativeEncounterContinuationArmed &&
                        (coordinator.SirenNativeEncounterStarted ||
                         Time.realtimeSinceStartup - coordinator.r.sirenNativeEncounterContinuationRegistrationObservedAt >=
                             SirenNativeEncounterContinuationContract.SourceReadinessWaitSeconds))
                    {
                        string readinessFailure =
                            coordinator.SirenNativeEncounterStarted
                                ? "Native Siren encounter started before the exact source registration armed controlled input"
                                : "Native Siren source registration did not reach live owner and Listening readiness within the bounded wait";
                        SirenSourceEntryFailureClassification.PreserveFirstFailure(ref coordinator.r.firstFailure,
                                                                                   ref coordinator.r.firstFailurePhase, readinessFailure,
                                                                                   "siren-native-encounter-continuation-readiness");
                        coordinator.r.phase = "siren-native-encounter-continuation-readiness-refused";
                        coordinator.r.success = false;
                        coordinator.Save();
                        break;
                    }
                    float continuationStageElapsed;
                    bool continuationStageClockValid = SirenNativeEncounterContinuationContract.TryGetStageElapsedSeconds(
                        Time.realtimeSinceStartup, began, coordinator.stageEnteredAt, out continuationStageElapsed);
                    if (coordinator.r.sirenNativeEncounterContinuationRequested && coordinator.r.sirenNativeEncounterContinuationArmed &&
                        (!continuationStageClockValid || continuationStageElapsed >= SirenEggDiagnosticInput.MaximumStageSeconds))
                    {
                        SirenSourceEntryFailureClassification.PreserveFirstFailure(
                            ref coordinator.r.firstFailure, ref coordinator.r.firstFailurePhase,
                            "Native Siren encounter start and exact boss identity were not both observed inside the existing 180-second source-stage input budget",
                            "siren-native-encounter-continuation-timeout");
                        coordinator.r.phase = "siren-native-encounter-continuation-timeout";
                        coordinator.r.success = false;
                        coordinator.Save();
                        break;
                    }
                    if (coordinator.r.sirenNativeEncounterContinuationRequested &&
                        SirenNativeEncounterContinuationContract.IsTerminal(
                            coordinator.r.sirenNativeEncounterContinuationRequested, coordinator.r.sirenNativeEncounterContinuationArmed,
                            coordinator.SirenNativeEncounterStarted, coordinator.SirenNativeEncounterBossIdentityObserved))
                    {
                        coordinator.r.sirenNativeEncounterContinuationCompleted = true;
                        coordinator.r.sirenNativeEncounterStartedObserved = true;
                        coordinator.r.sirenNativeBossIdentityObserved = true;
                        coordinator.r.sirenNativeBossMasterNetworkIds = coordinator.SirenNativeEncounterBossNetworkIds;
                        coordinator.r.phase = "siren-native-encounter-and-exact-boss-observed";
                        coordinator.r.success = true;
                        coordinator.Save();
                        break;
                    }
                    if (cfg.teleporterLoop && !(coordinator.r.sirenNativeEncounterContinuationRequested &&
                                                coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved))
                    {
                        coordinator.Check(coordinator.r.stageProgress != null && string.IsNullOrEmpty(coordinator.r.stageProgress.error),
                                          "Original stage callback failed: " +
                                              (coordinator.r.stageProgress == null ? "missing" : coordinator.r.stageProgress.error));
                        if (!pauseBeforeMoonBoundary && !string.IsNullOrEmpty(coordinator.pendingStage))
                        {
                            var transition = coordinator.TransportIntegratedStage(bridge, began);
                            while (transition.MoveNext())
                                yield return transition.Current;
                            previous = solver.TransientPosition;
                            // The fourth transport completes inside this coroutine. Recheck before
                            // any later producer in this same frame, not only on the next frame.
                            pauseBeforeMoonBoundary = cfg.pauseBeforeMoon && cfg.teleporterLoop &&
                                                      ManualMoonBoundary.HoldAutomaticProgression(
                                                          cfg.pauseBeforeMoon, coordinator.r.stageProgress.transitions);
                            bridge.SetManualMoonAutomaticHold(pauseBeforeMoonBoundary);
                            ObserveManualMoonHold(bridge);
                        }
                    }
                    if (coordinator.offlineSettingsPaused)
                    {
                        bridge.Neutral();
                        continue;
                    }
                    coordinator.ObserveAutomaticModelFollow(body);
                    display.ObserveNativeAim(coordinator.r.nova);
                    TemporaryOverlayManager.OverlayUpdate();
                    coordinator.Check(string.IsNullOrEmpty(bridge.error), "Nova bridge input failure: " + bridge.error);
                    coordinator.Check((cfg.combatSpine || machine.state == state) && body.gameObject.activeInHierarchy &&
                                          body.master.GetBody() == body && motor.hasEffectiveAuthority,
                                      "Original physical simulation state/link/authority changed");
                    float elapsed = Time.realtimeSinceStartup - began;
                    var position = solver.TransientPosition;
                    coordinator.r.nova.pathLength += Vector3.Distance(position, previous);
                    var delta = position - previous;
                    delta.y = 0;
                    coordinator.r.nova.planarPathLength += delta.magnitude;
                    previous = position;
                    if (motor.jumpCount > priorJumpCount)
                        coordinator.r.nova.jumpTransitions += motor.jumpCount - priorJumpCount;
                    priorJumpCount = motor.jumpCount;
                    coordinator.r.nova.maxRise = Mathf.Max(coordinator.r.nova.maxRise, position.y - restingY);
                    var stateAim = machine.state is GenericCharacterMain ? (Vector3)aimField.GetValue(machine.state) : Vector3.zero;
                    if (bridge.aim.sqrMagnitude > .1f && Vector3.Distance(stateAim, bank.aimDirection) < .001f)
                        coordinator.r.nova.aimConsumed = true;
                    if (coordinator.r.nova.planarPathLength > 3 && elapsed > 15 && bank.moveVector == Vector3.zero &&
                        motor.velocity.sqrMagnitude < .0001f && solver.GroundingStatus.IsStableOnGround)
                        coordinator.r.nova.stopped = true;
                    long observerPart = System.Diagnostics.Stopwatch.GetTimestamp();
                    if (cfg.integratedWorld)
                        coordinator.r.performance.preObserversMs += PerformanceMs(performancePart);
                    if (commandoPrimaryDiagnostic)
                        coordinator.ObserveSpinePrimary(body);
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.primaryMs += PerformanceMs(observerPart);
                        observerPart = System.Diagnostics.Stopwatch.GetTimestamp();
                    }
                    if (cfg.combatSpine)
                        coordinator.ObserveCombat(body, machine);
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.combatMs += PerformanceMs(observerPart);
                        observerPart = System.Diagnostics.Stopwatch.GetTimestamp();
                    }
                    if (cfg.enemySpine)
                        coordinator.ObserveEnemy();
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.enemyMs += PerformanceMs(observerPart);
                        observerPart = System.Diagnostics.Stopwatch.GetTimestamp();
                    }
                    coordinator.ObserveOriginalRunClock();
                    if (cfg.integratedWorld)
                        coordinator.r.performance.clockMs += PerformanceMs(observerPart);
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.observersMs += PerformanceMs(performancePart);
                        performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
                        long allocatedPart = allocatedFrameStart >= 0 ? GC.GetAllocatedBytesForCurrentThread() : 0;
                        coordinator.ObserveIntegratedWorld(body, elapsed);
                        coordinator.ObserveIntegratedResults();
                        if (allocatedFrameStart >= 0)
                            coordinator.r.performance.worldAllocatedBytes += GC.GetAllocatedBytesForCurrentThread() - allocatedPart;
                        coordinator.r.performance.worldMs += PerformanceMs(performancePart);
                        performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
                        allocatedPart = allocatedFrameStart >= 0 ? GC.GetAllocatedBytesForCurrentThread() : 0;
                        if (bringup && !pauseBeforeMoonBoundary &&
                            !(coordinator.r.results != null && coordinator.r.results.persisted))
                        {
                            coordinator.PrepareSirenEggDiagnosticInputFrame(body, bridge);
                            bool sirenOwnsWorldInput = SirenNavigationObservationPolicy.SirenOwnsInputFrame(
                                coordinator.SirenEggInputSelected, bridge.diagnosticInput, coordinator.IsRunAssisted(),
                                coordinator.worldManualTakeover, coordinator.SirenDiagnosticSceneActive,
                                coordinator.SirenDiagnosticOwnerAttached, coordinator.SirenDiagnosticListenerActive) &&
                                !coordinator.HasNearbyHostileDirectorThreat(body);
                            if (sirenOwnsWorldInput)
                            {
                                if (!coordinator.r.world.diagnosticInputEver)
                                {
                                    coordinator.Check(coordinator.r.debugAcceleration != null,
                                                     "Unattended input has no owned diagnostic evidence");
                                    coordinator.DebugToggle("diagnosticInput", true, "unattended route");
                                }
                                coordinator.r.world.diagnosticInput = true;
                                coordinator.r.world.diagnosticInputEver = true;
                            }
                            else
                                coordinator.IntegratedWorldStimulus(body, bridge, elapsed);
                            coordinator.EarnedFeatherInput(body, bridge, elapsed);
                            coordinator.ApplySirenEggDiagnosticInput(body, bridge);
                        }
                        if (allocatedFrameStart >= 0)
                            coordinator.r.performance.stimulusAllocatedBytes += GC.GetAllocatedBytesForCurrentThread() - allocatedPart;
                        coordinator.r.performance.stimulusMs += PerformanceMs(performancePart);
                        performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
                    }
                    if (bringup && !cfg.integratedWorld && !pauseBeforeMoonBoundary)
                    {
                        bridge.movement = elapsed < 3 ? Vector2.right : elapsed < 6 ? Vector2.left : Vector2.zero;
                        bridge.aim = elapsed < 6 ? Vector2.right : cfg.combatSpine ? coordinator.CombatAim(body) : Vector2.up;
                        bridge.DiagnosticJump(elapsed > 7 && elapsed < 7.2f);
                        // Observe real melee before diagnostic return fire; wall-clock timing can knock the enemy away before contact.
                        if (cfg.enemySpine && combatBegan < 0 && elapsed >= 9 && coordinator.r.enemy.playerDamageEvents > 0 &&
                            (!coordinator.DirectorBatch() || coordinator.r.director.actors.Count >= 2))
                        {
                            combatBegan = elapsed;
                            coordinator.r.nova.diagnosticReturnFireAt = elapsed;
                        }
                        float fireAge = cfg.enemySpine ? (combatBegan < 0 ? -1 : elapsed - combatBegan + 9) : elapsed;
                        if (cfg.automaticDirector && coordinator.enemyBody && fireAge > 9 && fireAge < 12)
                        {
                            var enemyAimDelta = coordinator.enemyBody.corePosition - body.inputBank.aimOrigin;
                            bridge.aim = new Vector2(enemyAimDelta.x, enemyAimDelta.z).normalized;
                        }
                        bridge.diagnosticPrimary = fireAge > 9 && fireAge < 12;
                        bridge.diagnosticSecondary = cfg.combatSpine && fireAge > 12.3f && fireAge < 12.5f;
                        bridge.diagnosticUtility = cfg.combatSpine && fireAge > 14 && fireAge < 14.2f;
                        bridge.diagnosticSpecial = cfg.combatSpine && fireAge > 16 && fireAge < 16.2f;
                        if (coordinator.DirectorBatch() && fireAge > 18.5f)
                        {
                            var target = coordinator.DirectorReturnFireTarget();
                            bridge.diagnosticPrimary = target;
                            if (target)
                            {
                                var batchAim = target.corePosition - body.inputBank.aimOrigin;
                                bridge.aim = new Vector2(batchAim.x, batchAim.z).normalized;
                            }
                        }
                    }
                    if (bringup && coordinator.worldView != null && bridge.diagnosticInput)
                    {
                        var cameraDirection = bank.aimDirection;
                        coordinator.r.visualCaptureActive = false;
                        // A capture-only camera target never changes the original aim/input bank.
                        // Physical takeover disables this path with diagnosticInput.
                        if (cfg.integratedWorld && coordinator.r.stageProgress != null &&
                            coordinator.r.stageProgress.current == cfg.visualCaptureStage && coordinator.objectiveHost &&
                            !string.IsNullOrEmpty(cfg.visualCaptureRenderer))
                        {
                            var views = coordinator.objectiveHost.GetComponentsInChildren<Renderer>(true)
                                            .Where(x => x.enabled && x.gameObject.activeInHierarchy && x.name == cfg.visualCaptureRenderer)
                                            .ToArray();
                            if (views.Length == 1)
                            {
                                var view = views[0];
                                cameraDirection = view.bounds.center - bank.aimOrigin;
                                coordinator.r.visualCaptureActive = true;
                                coordinator.r.visualCapturePath = StageObjectPath(view.transform);
                                coordinator.r.visualCaptureCenter = view.bounds.center;
                            }
                        }
                        coordinator.worldView.DiagnosticDirection(cameraDirection);
                    }
                    display.Observe(position, bank.aimDirection);
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.presentationMs += PerformanceMs(performancePart);
                        performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
                    }
                    if (elapsed >= next)
                    {
                        if ((coordinator.r.freePlay || cfg.integratedWorld) && coordinator.r.nova.observations.Count >= 900)
                            coordinator.r.nova.observations.RemoveAt(0);
                        coordinator.r.nova.observations.Add(
                            new NovaSample { seconds = elapsed, raw = physicalInputAvailable ? NovaInputBridge.ReadRaw() : null, input = bank.moveVector,
                                             aim = bank.aimDirection, stateAim = stateAim, velocity = motor.velocity, position = position,
                                             grounded = solver.GroundingStatus.IsStableOnGround, jump = bank.jump.down,
                                             jumpCount = motor.jumpCount });
                        coordinator.r.nova.samples++;
                        next = elapsed + .1f;
                    }
                    if (pauseBeforeMoonBoundary &&
                        ManualMoonBoundary.FinishObservation(
                            true, elapsed - coordinator.r.stageProgress.enteredAt))
                    {
                        coordinator.r.nova.seconds = elapsed;
                        break;
                    }
                    if (cfg.teleporterLoop && coordinator.r.stageProgress.transitions >= Mathf.Max(1, cfg.integratedTransitionTarget) &&
                        elapsed - coordinator.r.stageProgress.enteredAt > 30 &&
                        (!cfg.moonMission ||
                         (coordinator.r.moon != null && coordinator.r.moon.gameOver &&
                          (!cfg.integratedResults || (coordinator.r.results != null && coordinator.r.results.persisted)))))
                    {
                        coordinator.r.nova.seconds = elapsed;
                        break;
                    }
                    coordinator.r.nova.seconds = elapsed;
                    coordinator.r.nova.fixedTicks = bridge.fixedTicks;
                    coordinator.r.nova.jumpPresses = bridge.jumpPresses;
                    coordinator.r.automaticFrames++;
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.frames++;
                        coordinator.r.performance.fixedTicks = bridge.fixedTicks;
                        coordinator.r.world.inputBridgeEnabled = bridge.enabled;
                        coordinator.r.world.inputBridgeActive = bridge.isActiveAndEnabled;
                        coordinator.r.world.inputControllerConnected = bridge.controllerConnected;
                        coordinator.r.world.inputControllerSuspensions = bridge.controllerSuspensions;
                        coordinator.r.world.inputControllerReconnections = bridge.controllerReconnections;
                        coordinator.r.world.playerObjectActive = body.gameObject.activeInHierarchy;
                        coordinator.r.world.playerMotorEnabled = motor.enabled;
                        coordinator.r.world.liveTimeScale = Time.timeScale;
                        coordinator.r.world.liveFixedDeltaTime = Time.fixedDeltaTime;
                        coordinator.r.world.pauseControllerPaused = PauseStopController.instance && PauseStopController.instance.isPaused;
                    }
                    if (cfg.integratedWorld ? Time.realtimeSinceStartup >= nextReportSave : Time.frameCount % 30 == 0)
                    {
                        long saveStarted = System.Diagnostics.Stopwatch.GetTimestamp(),
                             saveAllocatedStart = allocatedFrameStart >= 0 ? GC.GetAllocatedBytesForCurrentThread() : 0;
                        if (cfg.integratedWorld)
                        {
                            coordinator.r.performance.requestedFrameRate = Application.targetFrameRate;
                            coordinator.r.performance.displayRefreshRate = Screen.currentResolution.refreshRate;
                            if (nativeSourceSkinRequested && display != null)
                                display.CaptureNativeSourceSkinReport();
                        }
                        coordinator.Save();
                        if (cfg.integratedWorld)
                        {
                            nextReportSave = Time.realtimeSinceStartup + 5;
                            coordinator.r.performance.saveMs += PerformanceMs(saveStarted);
                            if (allocatedFrameStart >= 0)
                                coordinator.r.performance.saveAllocatedBytes += GC.GetAllocatedBytesForCurrentThread() - saveAllocatedStart;
                        }
                    }
                    if (cfg.integratedWorld)
                    {
                        coordinator.r.performance.ownLoopMs += PerformanceMs(performanceFrame);
                        if (allocatedFrameStart >= 0)
                        {
                            coordinator.r.performance.sampledAllocationFrames++;
                            coordinator.r.performance.ownLoopAllocatedBytes += GC.GetAllocatedBytesForCurrentThread() - allocatedFrameStart;
                        }
                    }
                }
                coordinator.r.automaticSeconds = Time.realtimeSinceStartup - began;
                coordinator.r.spawnedStateAge = SpawnedStateAge(state, "age") - initialAge;
                coordinator.r.spawnedFixedAge = SpawnedStateAge(state, "fixedAge") - initialFixed;
                bridge.enabled = false;
                yield return new WaitForSeconds(.5f);
                if (coordinator.r.sirenSourceEntryDiagnosticAttempt)
                {
                    coordinator.Check(coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved,
                                      "Native Listening registration was not proven against the exact source egg bijection");
                    if (coordinator.r.sirenNativeEncounterContinuationRequested)
                    {
                        coordinator.Check(
                            coordinator.r.sirenNativeEncounterContinuationCompleted &&
                                SirenNativeEncounterContinuationContract.IsTerminal(coordinator.r.sirenNativeEncounterContinuationRequested,
                                                                                    coordinator.r.sirenNativeEncounterContinuationArmed,
                                                                                    coordinator.SirenNativeEncounterStarted,
                                                                                    coordinator.SirenNativeEncounterBossIdentityObserved),
                            "Native Siren encounter start and exact captured boss identity were not both observed");
                    }
                    else
                    {
                        coordinator.Check(
                            SirenSourceEntryRuntimeContract.NativeListeningRegistrationMatchesSourceEntry(coordinator.r.stageProgress),
                            "Native Listening registration no longer matches the exact source egg bijection");
                    }
                    coordinator.r.success = true;
                    coordinator.Save();
                    yield break;
                }
                if (cfg.integratedWorld)
                {
                    coordinator.r.world.simulationSeconds = coordinator.r.automaticSeconds;
                    coordinator.Check(coordinator.r.world.ready && coordinator.r.world.simulationSeconds >= 120 &&
                                          coordinator.r.world.frames > 1000,
                                      "Integrated world simulation incomplete");
                    if (!cfg.moonMission)
                        coordinator.Check(
                            coordinator.r.world.openedBarrels +
                                        (coordinator.r.stageProgress == null ? 0 : coordinator.r.stageProgress.completedBarrels) >=
                                    3 &&
                                coordinator.r.world.lootDomain == 4 &&
                                coordinator.r.world.openedChests +
                                        (coordinator.r.stageProgress == null ? 0 : coordinator.r.stageProgress.completedChests) >=
                                    2 &&
                                coordinator.r.world.pickupMessages >= 2 &&
                                coordinator.r.world.syringe + coordinator.r.world.lightning + coordinator.r.world.glasses +
                                        coordinator.r.world.slug >=
                                    2 &&
                                coordinator.r.world.kills > 0 && coordinator.r.world.coinMessages > 0 && coordinator.r.world.xpMessages > 0,
                            "Integrated world gameplay loop incomplete");
                    coordinator.Check(coordinator.r.world.authority && body.healthComponent.alive &&
                                          (cfg.teleporterLoop || coordinator.rewardDirector.enabled) &&
                                          coordinator.r.director.actors.Count > 3,
                                      "Integrated continuous combat/authority/survival incomplete");
                    if (cfg.teleporterLoop)
                        coordinator.Check(coordinator.r.stageProgress.transitions >= Mathf.Max(1, cfg.integratedTransitionTarget) &&
                                              coordinator.r.stageProgress.stageClearCount >= Mathf.Max(1, cfg.integratedTransitionTarget),
                                          "Integrated original teleporter/boss/charge loop incomplete");
                    if (cfg.moonMission && !cfg.pauseBeforeMoon)
                        coordinator.Check(
                            coordinator.r.moon != null && coordinator.r.moon.gameOver &&
                                coordinator.moonEscape.mainStateMachine.state is EscapeSequenceController.EscapeSequenceSuccessState,
                            "Original Moon mission/escape/ending remains incomplete");
                    if (cfg.integratedResults && !cfg.pauseBeforeMoon)
                        coordinator.Check(coordinator.r.results != null && coordinator.r.results.reportGenerated &&
                                              coordinator.r.results.clientEnding && coordinator.r.results.reportReloaded &&
                                              coordinator.r.results.persisted,
                                          "Original ending report/persistence incomplete");
                    coordinator.Save();
                    yield break;
                }
                coordinator.Check(coordinator.r.automaticSeconds >= (bringup ? 20 : 90) &&
                                      coordinator.r.nova.fixedTicks > (bringup ? 300 : 1000) &&
                                      coordinator.r.nova.samples > (bringup ? 100 : 300),
                                  "Physical Commando sustained callbacks");
                coordinator.Check(coordinator.r.nova.planarPathLength > 5 && coordinator.r.nova.stopped,
                                  "Physical movement and original stopping not observed");
                coordinator.Check(coordinator.r.nova.aimConsumed && (bringup || bridge.aimTicks > 10),
                                  "Physical right-stick aim not consumed by original state");
                if (commandoPrimaryDiagnostic)
                    coordinator.Check(coordinator.r.primary.shots > 0 &&
                                          (cfg.combatSpine ? body.skillLocator.primary.CanExecute() : body.skillLocator.primary.stock == 1),
                                      "Original primary firing/readiness not observed");
                coordinator.Check(coordinator.r.nova.jumpTransitions > 0 &&
                                      coordinator.r.nova.jumpPresses >= coordinator.r.nova.jumpTransitions &&
                                      coordinator.r.nova.maxRise > .5f && coordinator.r.nova.landings >= 2 &&
                                      solver.GroundingStatus.IsStableOnGround && motor.jumpCount == 0,
                                  "Physical jump/original landing incomplete");
                coordinator.Save();
                if (cfg.combatSpine)
                    coordinator.Check(coordinator.r.combat.secondaryEntries > 0 && coordinator.r.combat.utilityEntries > 0 &&
                                          coordinator.r.combat.specialEntries > 0 && coordinator.r.combat.projectiles > 0 &&
                                          coordinator.r.combat.damageEvents > 0 &&
                                          coordinator.r.combat.healthAfter < coordinator.r.combat.healthBefore,
                                      "Integrated original skills/projectile/target damage incomplete");
                if (cfg.enemySpine)
                    coordinator.Check(coordinator.r.enemy.graphReady && coordinator.r.enemy.linked && coordinator.r.enemy.authority &&
                                          coordinator.r.enemy.targetFound && coordinator.r.enemy.planarBeforeDamage > 4 &&
                                          coordinator.r.enemy.groundedBeforeDamage > 100 && coordinator.r.enemy.maxFallBeforeDamage < 10,
                                      "Original grounded enemy chase before incoming damage not observed");
                if (cfg.enemySpine && bringup)
                    coordinator.Check(coordinator.r.enemy.headbutts > 0 && coordinator.r.enemy.playerDamageEvents > 0 &&
                                          coordinator.r.enemy.enemyDamageEvents > 0 && coordinator.r.enemy.dead,
                                      "Original enemy melee, return damage and death not observed");
                if (cfg.enemySpine && bringup)
                    coordinator.Check(coordinator.r.enemy.deathGlobalEvents == 1 &&
                                          coordinator.r.enemy.playerKillsAfter ==
                                              coordinator.r.enemy.playerKillsBefore + (coordinator.DirectorBatch() ? 3 : 1) &&
                                          coordinator.r.enemy.naturalBodyDestroyed && coordinator.r.enemy.naturalMasterDestroyed,
                                      "Original enemy death event/kill count/natural teardown incomplete");
                if (cfg.automaticDirector && bringup)
                    coordinator.Check(coordinator.r.director.navigationTicks > 500 && coordinator.r.director.navigationNext &&
                                          coordinator.r.director.navigationReachable && coordinator.r.director.navigationPathUpdate > 0 &&
                                          (coordinator.DirectorBatch() ? coordinator.r.director.navigationAgentPeak >= 2
                                                                       : coordinator.r.director.navigationAgentPeak == 1),
                                      "Original broad route output/scheduling not observed");
                if (cfg.enemyRewards && bringup)
                {
                    if (coordinator.DirectorBatch())
                        coordinator.VerifyDirectorBatch();
                    else
                        coordinator.VerifyEnemyRewardDelivery();
                }
                if (cfg.originalRunClock && bringup)
                    coordinator.VerifyOriginalRunClock();
                if (cfg.barrelInteraction && bringup)
                {
                    var interaction = coordinator.ProbeOriginalBarrel(body, cfg);
                    while (interaction.MoveNext())
                        yield return interaction.Current;
                }
                if (cfg.originalDefaultPickup && bringup)
                {
                    var generic = coordinator.PrepareOriginalDefaultPickup(cfg);
                    while (generic.MoveNext())
                        yield return generic.Current;
                }
                if (cfg.originalItemPickup && bringup)
                {
                    var pickup = coordinator.ProbeOriginalItemPickup(body, cfg);
                    while (pickup.MoveNext())
                        yield return pickup.Current;
                }
                if (cfg.originalMoneyCost && bringup)
                {
                    var cost = coordinator.ProbeOriginalMoneyCost(body, cfg);
                    while (cost.MoveNext())
                        yield return cost.Current;
                }
                if (cfg.originalActiveClient && bringup)
                {
                    var client = coordinator.ProbeActiveBodyClient(body, cfg);
                    while (client.MoveNext())
                        yield return client.Current;
                }
            }
            finally
            {
                if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                {
                    // Preserve the input/physics owners and service graph while the
                    // native Stage/cohort recovery transaction is still live.
                    coordinator.r.cleanup = false;
                    coordinator.r.success = false;
                }
                else
                {
                    if (cfg.integratedWorld && !coordinator.r.sourceStageLifecycleRecoveryRequired)
                    {
                        coordinator.CleanupDebugAcceleration();
                        coordinator.CleanupIntegratedWorld();
                        if (coordinator.r.sirenSourceEntryDiagnosticAttempt)
                        {
                            bool cleanupObserved = coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved &&
                                SirenSourceEntryRuntimeContract.SourceEntryAndEncounterCleanupObserved(coordinator.r.stageProgress);
                            if (coordinator.r.sirenNativeEncounterContinuationRequested &&
                                coordinator.r.sirenNativeEncounterContinuationWasArmed)
                                cleanupObserved &= coordinator.r.sirenEggInput != null && coordinator.r.sirenEggInput.cleaned &&
                                                   !coordinator.r.sirenEggInput.active;
                            coordinator.r.sirenSourceEntryDiagnosticCleanupObserved = cleanupObserved;
                            if (coordinator.r.sirenNativeEncounterContinuationRequested)
                                coordinator.r.sirenNativeEncounterContinuationCleanupObserved = cleanupObserved;
                            coordinator.r.sirenNativeEncounterContinuationArmed = false;
                            coordinator.r.sirenNativeEncounterContinuationDisarmed = cleanupObserved;
                            string failureMessage = SirenSourceEntryFailureClassification.FailureMessage(
                                coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved, cleanupObserved);
                            if (failureMessage == null)
                                coordinator.r.phase = coordinator.r.sirenNativeEncounterContinuationRequested
                                                          ? "siren-native-encounter-boss-and-cleanup-observed"
                                                          : "siren-source-entry-listening-registration-and-cleanup-observed";
                            else
                            {
                                coordinator.r.success = false;
                                SirenSourceEntryFailureClassification.PreserveFirstFailure(
                                    ref coordinator.r.firstFailure, ref coordinator.r.firstFailurePhase, failureMessage,
                                    SirenSourceEntryFailureClassification.FailurePhase(
                                        coordinator.r.sirenSourceEntryDiagnosticRegistrationObserved, cleanupObserved));
                            }
                            coordinator.Save();
                        }
                    }
                    if (!coordinator.r.sourceStageLifecycleRecoveryRequired)
                    {
                        coordinator.CleanupActiveBodyClient();
                        coordinator.CleanupOriginalMoneyCost();
                        coordinator.CleanupOriginalItemPickup();
                        if (cfg.originalDefaultPickup && (bringup || cfg.integratedWorld))
                            coordinator.CleanupOriginalDefaultPickup();
                        coordinator.CleanupOriginalBarrel();
                        coordinator.CleanupRunClock();
                    }
                    if (cfg.enemySpine)
                        coordinator.CleanupEnemy();
                    if (bridge)
                    {
                        bridge.SetManualMoonAutomaticHold(false);
                        bridge.enabled = false;
                        Destroy(bridge);
                    }
                    if (cfg.combatSpine)
                        coordinator.CleanupCombatScene();
                    if (display != null)
                        display.Dispose();
                    if (!ReferenceEquals(body, null))
                        body.onJump -= jumped;
                    if (!ReferenceEquals(motor, null))
                        motor.onHitGroundAuthority -= landed;
                    Physics.gravity = gravity;
                    Physics.queriesHitTriggers = priorTriggerQueries;
                    if (solver)
                    {
                        solver.CollidableLayers = layers;
                        solver.StableGroundLayers = stable;
                        solver.SetGroundSolvingActivation(false);
                    }
                    coordinator.worldView = null;
                    Application.targetFrameRate = priorTargetFrameRate;
                    if (ownsScreenSleepTimeout)
                        Screen.sleepTimeout = sleepTimeout;
                }
            }
        }
        // The input iterator's finally releases its resources in the original order.
        // Trace cursors must survive that cleanup; there is no additional release here.
        public void Dispose()
        {
        }
    }
}
