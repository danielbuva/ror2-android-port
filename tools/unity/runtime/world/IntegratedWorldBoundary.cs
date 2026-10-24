// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareIntegratedWorld (IntegratedWorldSession); teardown CleanupIntegratedWorld (Dispose), VerifyIntegratedWorldCleanup, then RestartWorldAfterCleanup.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HG.Reflection;
using RoR2;
using RoR2.Audio;
using RoR2.Networking;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Persistent local gameplay composition. Original simulation, purchases, loot and rewards
// remain in the preserved assemblies. The shell supplies content/context and unavailable audio UI.
public sealed partial class PortSession
{
    [Serializable]
    public class WorldPickupObservation
    {
        public string item, interactability;
        public Vector3 position, aimTarget;
        public float aimDistance;
        public bool selected, collider, interactableLayer;
    }
    [Serializable]
    public class WorldPickupMessageObservation
    {
        public float at;
        public bool resolvedMaster, playerMaster, knownPickup;
        public uint masterId, quantity;
        public int pickupIndex;
        public string item;
    }
    [Serializable]
    public class WorldItemObservation
    {
        public string item, tier;
        public int count;
    }
    [Serializable]
    public class LightningStakeObservation
    {
        public int frame, instance, projectileCatalogIndex, lastFiniteFrame, stuckHurtBoxIndex;
        public uint networkId, ownerNetworkId, victimNetworkId;
        public float fixedTime, seconds;
        public string sample, networkAssetId, ownerName, ownerBody, position, rotation, scale, networkPosition, networkRotation,
            rigidbodyPosition, velocity, angularVelocity, ownerPosition, victimName, victimPosition, stuckTransformPath,
            stuckTransformPosition, stuckBody, stuckBodyPosition, stuckHurtBox, localPosition, localRotation, colliderRadius,
            colliderCenter, lastFinitePosition, lastFiniteNetworkPosition, lastFiniteRigidbodyPosition, lastFiniteVelocity,
            lastFiniteAngularVelocity;
        public int ownerTeam;
        public bool spawnTimeKnown, networkObjectMatches, isServer, ownerObjectMatches, ownerBlueElite;
        public bool finiteSnapshot, firstNonFiniteTransition, finitePosition, finiteRotation, finiteScale, finiteNetworkPosition,
            finiteNetworkRotation, finiteRigidbodyPosition, finiteVelocity, finiteAngularVelocity, finiteLocalPosition, finiteLocalRotation,
            finiteStuckTransformPosition, finiteVictimPosition, rigidbodyKinematic, rigidbodyGravity, rigidbodyDetectCollisions,
            colliderEnabled, colliderTrigger, stuck;
    }
    [Serializable]
    public class BlueEliteHitObservation
    {
        public int frame;
        public float seconds;
        public string attacker, hit, victim;
        public bool finiteHit;
    }
    [Serializable]
    public class WorldMessageFailure
    {
        public float at;
        public int id;
        public string side, handler, error;
    }
    [Serializable]
    public class NavigationPathPoint
    {
        public Vector3 position;
        public float minimumJumpHeight;
    }
    [Serializable]
    public sealed class ObjectiveCombatInputFailureReport
    {
        // Captured once on the first diagnostic-path NRE. Operand states use
        // 0=unread, 1=CLR null, 2=Unity fake-null, 3=live.
        public string step, exceptionType, exceptionMessage;
        // Bits: input bank 0, player motor 1, SkillLocator 2, actor body 3,
        // actor health 4, actor master 5, player TeamComponent 6, target body 7,
        // primary slot 8, primary definition 9, utility slot 10, boss group 11,
        // CombatSquad 12, membership list 13, KCC motor 14.
        public int observedMask, actorIndex, lastActorSampleIndex;
        public byte playerState, playerTeamComponentState, playerInputBankState, actorBodyState, actorHealthComponentState,
            actorMasterState, targetActorBodyState, bossGroupState, combatSquadState, bossMembersState, playerMotorState, motorState,
            skillLocatorState, primarySlotState, primaryDefinitionState, utilitySlotState;
    }
    [Serializable]
    public class WorldReport
    {
        public int nativeEffectSourceRenderers, nativeEffectSourceMaterials;
        public ObjectiveRendererObservation[] nativeEffectViews;

        public NovaThirdPersonView.Report camera;
        public WorldEquipmentReport equipment;
        public bool lunarDefinition, lunarCurrencyAvailable;
        public bool engiShieldGuardPrepared, engiShieldGuardReleased;
        public EngineerNativeOutputObserver.Report engiNativeOutputs;
        public SurvivorCombatOutputObserver.Report survivorCombatOutputs;
        public bool ready, authority, lootReady, interactionReady, cleaned, diagnosticInput, diagnosticInputEver;
        public bool originalAudioCameraContextRequested, originalAudioCameraContextReady;
        public AndroidNativeAudioCameraAdmissionEvidence originalAudioCameraContextLastAdmissionEvidence;
        public bool originalAudioCameraContextCreated, originalAudioCameraContextReleaseVerified;
        public bool originalAudioCameraContextDestroyRequested, originalAudioCameraContextDestroyObservationCaptured,
            originalAudioCameraContextDestroyObserved;
        public bool originalAudioCameraContextDeferredForVisualDiagnostic;
        public bool originalAudioCameraContextRenderCameraDisabled, originalAudioCameraContextOverrideAbsent;
        public bool originalAudioCameraContextSourceRigAtIndexZero, originalAudioCameraContextManagedListenerObserved;
        public bool originalAudioCameraContextManagedListenerRemovalObserved;
        public bool originalAudioCameraContextRigActivityObserved;
        public bool originalAudioCameraContextRigActiveAndEnabledObserved,
            originalAudioCameraContextRigActiveInHierarchyObserved;
        public bool originalAudioCameraContextRigActiveAndEnabled, originalAudioCameraContextRigActiveInHierarchy;
        public bool originalAudioCameraContextCameraModeObserved, originalAudioCameraContextCameraModeIsNull,
            originalAudioCameraContextCameraModeIsPlayerBasic, originalAudioCameraContextOriginalStartWaitObserved;
        public bool originalAudioCameraContextStartupClockObserved,
            originalAudioCameraContextStartupClockValid, originalAudioCameraContextStartupDeadlineExpired;
        public bool originalAudioCameraContextDamageNumberManagerBeforeCaptured, originalAudioCameraContextDamageNumberManagerBefore;
        public bool originalAudioCameraContextDamageNumberManagerAfterCaptured, originalAudioCameraContextDamageNumberManagerAfter;
        public int originalAudioCameraContextRigIndex = -1;
        public string originalAudioCameraContextState, originalAudioCameraContextScope,
            originalAudioCameraContextAdmissionFailure, originalAudioCameraContextAdmissionFailureDetail,
            originalAudioCameraContextCameraStartGateState;
        public ObjectiveCombatInputFailureReport objectiveCombatInputFailure;
        public int tableLoadedCount, barrels, chests, openedBarrels, openedChests, pickups, droplets, pickupMessages, coinMessages,
            xpMessages, frames, kills, liveEnemies;
        public int lootDomain, syringe, lightning, glasses, slug, drink, steak, secondary, roll, barrage;
        public uint money;
        public ulong experience;
        public int lootTier1, lootTier2, lootTier3, transmutationGroups, transmutationMapped;
        public bool transmutationCleaned;
        public float shield, maxShield, armor;
        public WorldItemObservation[] itemStacks;
        public int featherJumps, featherEffectLoads;
        public bool featherEffectCleaned, featherInputAttempted;
        public string featherInputOutcome;
        public int nativeLootProviderLoads, healthPacks, moneyPacks, stunImpactLoads, slowedEnemiesPeak;
        public bool nativeLootProvidersCleaned;
        public int stickyBombLoads, stickyBombSpawns, wispDelaySpawns, barrierEffects;
        public float barrier;
        public string fireTrailDiagnostic;
        public List<BlueEliteHitObservation> blueEliteHits = new List<BlueEliteHitObservation>();
        public List<LightningStakeObservation> lightningStakes = new List<LightningStakeObservation>();
        public string lightningStakeObserverStatus;
        public PortSession.LightningStakeSourceCallReport lightningStakeSourceCall;
        public int lightningStakeIdentitiesObserved;
        public int earlyHurtCaches;
        public List<string> earlyHurtBodies = new List<string>();
        public float simulationSeconds, seconds, health, maxHealth, level, attackSpeed, crit, regen, moveSpeed, difficulty, distance;
        public string scope, objective, target, lastPickup, feedbackCapability;
        public Vector3 start, position;
        public float interactionDistance;
        public WorldPickupObservation[] pickupObservations;
        public string pickupRegistryStatus;
        public List<WorldPickupMessageObservation> pickupMessageObservations = new List<WorldPickupMessageObservation>();
        public int unresolvedPickupMessages, otherPickupMessages, zeroCountPickupMessages;
        public List<WorldMessageFailure> messageFailures = new List<WorldMessageFailure>();
        public int messageFailureCount;
        public int sourceServerMessageHandlers, sourceClientMessageHandlers, offlineChatPackets, offlinePointSoundPackets,
            offlineEffectSoundPackets;
        public bool sourceConstructTurretHandler, offlineChatBoundary, offlinePointSoundBoundary, offlineEffectSoundBoundary;
        public string offlineChatLastToken, offlinePointSoundLastEvent, offlineEffectSoundLastEvent;
        public Vector3 offlinePointSoundLastPosition;
        public int bodyVisualSlots, healthVisualSlots, globalCommonAssetSlots;
        public string[] bodyVisualUnavailable, healthVisualUnavailable, globalCommonAssetUnavailable;
        public bool bodyVisualCleaned, globalCommonAssetCleaned;
        public string navigationTarget;
        public bool navigationReachable, navigationJump, navigationElevatedApproachAttempted, navigationElevatedApproachFound,
            navigationElevatedApproachActive;
        public int navigationWaypoints;
        public Vector3 navigationDestination, navigationWaypoint;
        public int navigationRecoveries, navigationRecoveryJumpFrames;
        public float navigationStalledSeconds, navigationProgressDistance, navigationObjectiveStalledSeconds,
            navigationObjectiveProgressDistance;
        public bool navigationRecoveryJump;
        public Vector3 navigationReference, navigationLocalMovement;
        public bool navigationLocalObstructed, navigationAllowWalkOffCliff;
        public float navigationLocalJumpSpeed;
        public NavigationPathPoint[] navigationPath;
        public bool navigationTerrainFallback, navigationTerrainNoCandidate, navigationSprint;
        public int navigationTerrainFrames, navigationTerrainBlocked, navigationObjectiveRecoveryFrames;
        public Vector3 navigationTerrainTarget;
        public int navigationTerrainLowerChoices, navigationTerrainRayOverflow;
        public bool navigationPartial;
        public int navigationPartialCandidates, navigationPartialNode = -1;
        public float navigationPartialSeconds;
        public Vector3 navigationPartialDestination;
        public string navigationHull, navigationJumpHeight;
        public int navigationGraphNodes, navigationStartNode = -1, navigationNearestNode = -1, navigationApproachBoundsRejected,
                                         navigationApproachTooShort, navigationApproachUnreachable;
        public float navigationMaxSpeed, navigationMaxSlope, navigationGravityY;
        public Vector3 navigationStartPosition;
        public bool motorGrounded, motorStable, jumpDown, jumpPressed, jumpClaimed;
        public int motorJumpCount, motorMaxJumpCount;
        public Vector3 motorVelocity, motorGroundPoint;
        public string motorGroundCollider, movementState;
        public bool manualTakeover, inputBridgeEnabled, inputBridgeActive, inputControllerConnected, playerObjectActive, playerMotorEnabled,
            pauseControllerPaused;
        public int inputControllerSuspensions, inputControllerReconnections;
        public float liveTimeScale, liveFixedDeltaTime;
        public int combatMotionSamples, combatMotionBlocked, combatCandidates, combatBoundsRejected, travelDefenseFrames;
        public string combatTarget, travelDefenseTarget;
        public Vector3 combatGround, combatDestination;
        public Vector2 combatMotion;
        public int combatVisibleCandidates, combatOccludedCandidates, combatApproachFrames, combatHoldoutReturnFrames;
        public bool combatLineOfSight, combatTargetBoss, combatHoldoutConstrained, combatPrimaryRequested;
        public float combatTargetDistance, combatThreatDistance, combatHoldoutReturnDistance;
        public Vector3 combatAimOrigin, combatAimTarget;
        public bool combatMeleePrimary;
        public float combatEngagementRange;
        public Vector3 combatTargetPhysicsPosition, combatTargetCorePosition;
    }
    readonly List<GameObject> worldObjects = new List<GameObject>();
    readonly List<Transform> worldModels = new List<Transform>();
    readonly List<Material> worldMaterials = new List<Material>();
    readonly HashSet<int> worldPresented = new HashSet<int>();
    readonly List<BarrelInteraction> worldBarrels = new List<BarrelInteraction>();
    readonly List<ChestBehavior> worldChests = new List<ChestBehavior>();
    GameObject worldStaging, worldPause;
    InteractionDriver worldDriver;
    CharacterBody worldPlayer;
    BasicPickupDropTable worldChestTable;
    int worldBarrelConsumers;
    bool ownsIntegratedPools;
    readonly List<short> worldSourceClientHandlerIds = new List<short>();
    int worldObjective;
    float worldLastPress = -1;
    RoR2.PathFollower worldPathFollower = new RoR2.PathFollower();
    LocalNavigator worldLocalNavigator = new LocalNavigator();
    CharacterBody worldNavigationBody;
    float worldTerrainSelectedAt = -100, worldTerrainRecoveryUntil = -100;
    readonly List<Vector3> worldTerrainRecent = new List<Vector3>();
    NovaThirdPersonView worldView;
    bool restartRequested, worldManualTakeover;
    public int sessionIndex = 1;
    ItemDef[] worldLootDefinitions;
    ItemMask worldAvailableItems;
    EquipmentMask worldAvailableEquipment;
    readonly Dictionary<FieldInfo, GameObject> worldLootEffectSlots = new Dictionary<FieldInfo, GameObject>();
    readonly List<GameObject> worldLootTemporaryEffects = new List<GameObject>();
    readonly Dictionary<Renderer, Material[]> worldLootSourceMaterials = new Dictionary<Renderer, Material[]>();
    readonly Dictionary<GameObject, int> worldLootSourceLayers = new Dictionary<GameObject, int>();
    readonly Dictionary<int, int> worldNativeLootLeaseBaselines = new Dictionary<int, int>();
    readonly HashSet<GameObject> worldNativeLootObjects = new HashSet<GameObject>();
    IntegratedWorldSession integratedWorldSession;
    IntegratedWorldSession GetIntegratedWorldSession()
    {
        if (integratedWorldSession == null)
            integratedWorldSession = new IntegratedWorldSession(this);
        return integratedWorldSession;
    }
    public bool HasNearbyHostileDirectorThreat(CharacterBody player)
    {
        return GetIntegratedWorldSession().HasNearbyHostileDirectorThreat(player);
    }
    void PrepareEarlyHurtCache(CharacterBody body)
    {
        GetIntegratedWorldSession().PrepareEarlyHurtCache(body);
    }
    void PrepareEarlyHurtCaches(CharacterBody player)
    {
        GetIntegratedWorldSession().PrepareEarlyHurtCaches(player);
    }
    static bool Finite(float value)
    {
        return IntegratedWorldSession.Finite(value);
    }
    static bool Finite(Vector3 value)
    {
        return IntegratedWorldSession.Finite(value);
    }
    static bool Finite(Quaternion value)
    {
        return IntegratedWorldSession.Finite(value);
    }
    static string Number(float value)
    {
        return IntegratedWorldSession.Number(value);
    }
    static string Position(Vector3 value)
    {
        return IntegratedWorldSession.Position(value);
    }
    static string Rotation(Quaternion value)
    {
        return IntegratedWorldSession.Rotation(value);
    }
    void ObserveLightningStakes()
    {
        GetIntegratedWorldSession().ObserveLightningStakes();
    }
    ItemDef[] WorldTierOneLoot(SessionConfig cfg)
    {
        return GetIntegratedWorldSession().WorldTierOneLoot(cfg);
    }
    ItemDef[] WorldLoot(SessionConfig cfg)
    {
        return GetIntegratedWorldSession().WorldLoot(cfg);
    }
    BuffDef[] WorldLootBuffs(SessionConfig cfg)
    {
        return GetIntegratedWorldSession().WorldLootBuffs(cfg);
    }
    void PrepareSourceTemporaryVisuals()
    {
        GetIntegratedWorldSession().PrepareSourceTemporaryVisuals();
    }
    GameObject OriginalProjectileGhost(RoR2.Projectile.ProjectileController controller)
    {
        return GetIntegratedWorldSession().OriginalProjectileGhost(controller);
    }
    GameObject[] PrepareWorldLootSupport(SessionConfig cfg)
    {
        return GetIntegratedWorldSession().PrepareWorldLootSupport(cfg);
    }
    void ObserveWorldLootSupport(CharacterBody body, bool force = false)
    {
        GetIntegratedWorldSession().ObserveWorldLootSupport(body, force);
    }
    void CleanupWorldLootSupport()
    {
        GetIntegratedWorldSession().CleanupWorldLootSupport();
    }
    IEnumerator PrepareIntegratedWorld(CharacterBody player, SessionConfig cfg)
    {
        return GetIntegratedWorldSession().PrepareIntegratedWorld(player, cfg);
    }
    IEnumerator PrepareWorldTransmutation()
    {
        return GetIntegratedWorldSession().PrepareWorldTransmutation();
    }
    void CleanupWorldTransmutation()
    {
        GetIntegratedWorldSession().CleanupWorldTransmutation();
    }
    void PrepareUnavailableWorldPresentation(CharacterBody player)
    {
        GetIntegratedWorldSession().PrepareUnavailableWorldPresentation(player);
    }
    void PrepareWorldMessages()
    {
        GetIntegratedWorldSession().PrepareWorldMessages();
    }
    void RegisterMissingOriginalWorldMessages()
    {
        GetIntegratedWorldSession().RegisterMissingOriginalWorldMessages();
    }
    void ObserveUnavailablePlatformChat(NetworkMessage message)
    {
        GetIntegratedWorldSession().ObserveUnavailablePlatformChat(message);
    }
    void ObserveUnavailablePointSound(NetworkMessage message)
    {
        GetIntegratedWorldSession().ObserveUnavailablePointSound(message);
    }
    void ObserveUnavailableEffectSound(NetworkMessage message, Type packetType)
    {
        GetIntegratedWorldSession().ObserveUnavailableEffectSound(message, packetType);
    }
    void ObserveWorldHandlers(bool server)
    {
        GetIntegratedWorldSession().ObserveWorldHandlers(server);
    }
    void RestoreWorldHandlers(bool server)
    {
        GetIntegratedWorldSession().RestoreWorldHandlers(server);
    }
    GameObject CreateWorldInteractable(GameObject source, Vector3 candidate, bool chest, PickupDropTable dropOverride = null)
    {
        return GetIntegratedWorldSession().CreateWorldInteractable(source, candidate, chest, dropOverride);
    }
    void PresentWorldModel(Transform model, bool sourceView, bool optionalObjectiveSlots = false)
    {
        GetIntegratedWorldSession().PresentWorldModel(model, sourceView, optionalObjectiveSlots);
    }
    void ObserveIntegratedWorld(CharacterBody player, float elapsed)
    {
        GetIntegratedWorldSession().ObserveIntegratedWorld(player, elapsed);
    }
    void IntegratedWorldStimulus(CharacterBody player, NovaInputBridge bridge, float elapsed)
    {
        var session = GetIntegratedWorldSession();
        session.IntegratedWorldStimulus(player, bridge, elapsed);
        session.ApplySurvivorSkillCoverage(player, bridge, elapsed);
    }
    void EarnedFeatherInput(CharacterBody player, NovaInputBridge bridge, float elapsed)
    {
        GetIntegratedWorldSession().EarnedFeatherInput(player, bridge, elapsed);
    }
    void PrepareSirenEggDiagnosticInputFrame(CharacterBody player, NovaInputBridge bridge)
    {
        GetIntegratedWorldSession().PrepareSirenEggDiagnosticInputFrame(player, bridge);
    }
    void ApplySirenEggDiagnosticInput(CharacterBody player, NovaInputBridge bridge)
    {
        GetIntegratedWorldSession().ApplySirenEggDiagnosticInput(player, bridge);
    }
    void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination, float stopDistance, string target,
                            float elapsed)
    {
        GetIntegratedWorldSession().NavigateWorldInput(player, bridge, destination, stopDistance, target, elapsed);
    }
    bool FindSourceWorldApproach(CharacterBody player, RoR2.Navigation.NodeGraph graph, RoR2.Path path, Vector3 position,
                                 Vector3 destination, bool elevated = false)
    {
        return GetIntegratedWorldSession().FindSourceWorldApproach(player, graph, path, position, destination, elevated);
    }
    Vector3 TerrainTravelWaypoint(CharacterBody player, Vector3 position, Vector3 destination, float elapsed)
    {
        return GetIntegratedWorldSession().TerrainTravelWaypoint(player, position, destination, elapsed);
    }
    IEnumerator VerifyIntegratedWorldCleanup()
    {
        return GetIntegratedWorldSession().VerifyIntegratedWorldCleanup();
    }
    void DrawIntegratedWorld()
    {
        GetIntegratedWorldSession().DrawIntegratedWorld();
    }
    void RequestWorldRestart()
    {
        GetIntegratedWorldSession().RequestWorldRestart();
    }
    void ObserveWorldRestartInput()
    {
        GetIntegratedWorldSession().ObserveWorldRestartInput();
    }
    void RestartWorldAfterCleanup()
    {
        GetIntegratedWorldSession().RestartWorldAfterCleanup();
    }
    void CleanupIntegratedWorld()
    {
        GetIntegratedWorldSession().Dispose();
    }

    // Create on first use and retain after Dispose. World teardown stays separate
    // from catalog release, deferred verification and the coordinator restart.
    sealed class IntegratedWorldSession : IDisposable
    {
        readonly PortSession coordinator;
        SurvivorSkillObserver survivorSkills;
        SurvivorCombatOutputObserver survivorCombatOutputs;
        SirenEggDiagnosticInput sirenEggDiagnosticInput;
        EngineerNativeOutputObserver engiNativeOutputs;
        SurvivorSkillInputCoverage skillInputCoverage;
        EngiShieldHitGuardTemplateLease engiShieldGuard;
        AndroidNativeSourceCameraRigOwner originalAudioCameraContext;
        bool originalAudioCameraContextAttempted;
        readonly OriginalAudioCameraContextCreationSchedule originalAudioCameraContextCreationSchedule =
            new OriginalAudioCameraContextCreationSchedule();
        float nextSurvivorSkillSample;
        int lastTransientWindowRequestCount;
        public IntegratedWorldSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }

        // The finite source-camera admission window must start only after this
        // session is servicing the actual integrated-world playing loop.
        // This policy performs no Unity or native work and consumes a queued
        // creation exactly once at that lifecycle boundary.
        internal sealed class OriginalAudioCameraContextCreationSchedule
        {
            internal enum BeginResult { NotPending, Deferred, Begin, Refused }
            bool pending;
            public bool IsPending => pending;
            public void Schedule() { pending = true; }
            public void Reset() { pending = false; }
            public bool CancelPending()
            {
                bool wasPending = pending;
                pending = false;
                return wasPending;
            }
            public BeginResult Begin(bool integratedWorldPlaying, object updatePlayer, object ownedWorldPlayer, bool alreadyAttempted)
            {
                if (!pending) return BeginResult.NotPending;
                if (!integratedWorldPlaying) return BeginResult.Deferred;
                pending = false;
                return !alreadyAttempted && updatePlayer != null && ReferenceEquals(updatePlayer, ownedWorldPlayer)
                    ? BeginResult.Begin : BeginResult.Refused;
            }
        }

        float nextWorldPickupSnapshot;
        string worldPickupRegistryStage;
        bool worldPickupRegistryFallback;
        bool fireTrailDiagnosisRecorded;
        Action worldClientUpdate;
        ResourceLocationMap worldDropletLocator;
        GameObject worldDropletSource;
        FieldInfo worldDropletField;
        object priorWorldDroplet;
        bool ownsWorldDroplet, ownsWorldLists;
        RoR2.ConVar.IntConVar worldVfxOption;
        string priorWorldVfx, priorWorldXp;
        AsyncOperationHandle<GameObject> worldCoinLease;
        bool ownsWorldCoinLease;
        int worldCoinBaseline;
        Action<Interactor, IInteractable, GameObject> worldInteraction;
        bool ownsWorldTeleportHandler;
        readonly Dictionary<short, NetworkMessageDelegate> worldClientHandlers = new Dictionary<short, NetworkMessageDelegate>(),
                                                           worldServerHandlers = new Dictionary<short, NetworkMessageDelegate>(),
                                                           worldClientObservers = new Dictionary<short, NetworkMessageDelegate>(),
                                                           worldServerObservers = new Dictionary<short, NetworkMessageDelegate>();
        readonly List<short> worldSourceServerHandlerIds = new List<short>();
        NetworkSoundEventDef[] worldOfflineNetworkSoundDefs;
        Vector3 worldPathTarget;
        float worldPathRequested = -100;
        int worldPathRequestId;
        string worldPathRequestReason = "unavailable";
        RoR2.Navigation.NodeGraph worldElevatedApproachGraph;
        Vector3 worldElevatedApproachObjective, worldElevatedApproachDestination;
        bool worldElevatedApproachActive;
        float worldNavigationUpdatedAt;
        Vector3 worldNavigationProgressWaypoint, worldNavigationProgressDestination;
        float worldNavigationProgressDistance, worldNavigationProgressAt, worldNavigationRecoveryUntil = -1;
        bool worldNavigationHasProgress;
        Vector3 worldNavigationObjective;
        float worldNavigationObjectiveDistance, worldNavigationObjectiveProgressAt;
        bool worldNavigationHasObjectiveProgress;
        Vector3 worldTerrainTarget, worldTerrainGoal;
        readonly RaycastHit[] worldTerrainHits = new RaycastHit[64];
        bool ownsWorldMisc;
        MiscPickupDef[] previousWorldMiscContent;
        object previousWorldMiscCatalog;
        readonly Dictionary<MiscPickupDef, MiscPickupIndex> priorWholeMiscIndices = new Dictionary<MiscPickupDef, MiscPickupIndex>();
        ResourceAvailability previousWorldMiscAvailability;
        LunarCoinDef worldLunarCoin;
        Action<TeamIndex> unavailableTeamLevelSound;
        Action<Run> unavailableAmbientSound;
        Action<CharacterBody> unavailableLevelEffect;
        Action<ItemIndex> unavailableItemHighlight;
        bool ownsWorldPresentation;
        ItemMask previousWorldAvailableItems;
        EquipmentMask previousWorldAvailableEquipment;
        int worldFeatherEffectIndex = -1, worldFeatherReferenceBaseline;
        CharacterBody.JumpDelegate worldFeatherJumped;
        bool worldWispEffectEligible;
        LightningStakeDiagnosticObserver lightningStakeObserver;
        LightningStakeSourceCallObserver lightningStakeSourceCallObserver;
        int savedLightningStakeSourceCallCount;
        Action<CharacterBody> earlyHurtCacheHandler;
        static readonly FieldInfo hurtDurationCache =
            typeof(SetStateOnHurt).GetField("buffDurationControllers", BindingFlags.Instance | BindingFlags.NonPublic);
        public void PrepareEarlyHurtCache(CharacterBody body)
        {
            if (!body || !body.gameObject.scene.IsValid())
                return;
            coordinator.Check(hurtDurationCache != null && hurtDurationCache.FieldType == typeof(AlterBuffDuration[]),
                              "Original hurt-duration cache contract changed");
            foreach (var hurt in body.GetComponents<SetStateOnHurt>())
            {
                if (hurtDurationCache.GetValue(hurt) != null)
                    continue;
                // The native Start method fills this cache, but a same-frame blast can hit
                // a newly spawned body before Start. Populate exactly that source value.
                hurtDurationCache.SetValue(hurt, body.GetComponents<AlterBuffDuration>());
                coordinator.r.world.earlyHurtCaches++;
                if (coordinator.r.world.earlyHurtBodies.Count < 8)
                    coordinator.r.world.earlyHurtBodies.Add(body.name);
            }
        }
        public void PrepareEarlyHurtCaches(CharacterBody player)
        {
            coordinator.Check(earlyHurtCacheHandler == null, "Duplicate early hurt-cache owner");
            earlyHurtCacheHandler = PrepareEarlyHurtCache;
            CharacterBody.onBodyAwakeGlobal += earlyHurtCacheHandler;
            foreach (var body in CharacterBody.readOnlyInstancesList.ToArray())
                PrepareEarlyHurtCache(body);
            PrepareEarlyHurtCache(player);
        }
        void ResetOriginalAudioCameraContextAttemptForWorld()
        {
            var previousReport = coordinator.r?.world;
            bool previousCreated = previousReport != null && previousReport.originalAudioCameraContextCreated;
            bool previousReleasePrepared = previousReport != null && previousReport.originalAudioCameraContextReleaseVerified;
            bool ownerReferenceIsClrNull = ReferenceEquals(originalAudioCameraContext, null);
            coordinator.Check(AndroidNativeAudioCameraContextContract.CanResetAttempt(
                    originalAudioCameraContextAttempted, ownerReferenceIsClrNull, previousReport != null,
                    previousCreated, previousReleasePrepared),
                "Previous original audio camera-context owner was not released before preparing another world");
            originalAudioCameraContextAttempted = false;
            originalAudioCameraContextCreationSchedule.Reset();
            originalAudioCameraContext = null;
        }

        void PrepareOriginalAudioCameraContext(CharacterBody player, bool createAtIntegratedWorldUpdate = false)
        {
            var report = coordinator.r.world;
            if (report == null)
                return;
            report.originalAudioCameraContextScope =
                "When explicitly selected original Wwise audio is Ready, this mode activates the accepted source CameraRigController and its exact default listener with the selected body at index zero, but leaves the source Camera disabled and installs no view override. The source rig joins global camera membership/events and makes its target spectated to original queries; source Start may load/instantiate the global DamageNumberManager if absent. These are intentional native source effects, not an inert audio helper. Native listener registration, event routing, PCM attribution, and physical audibility remain unobserved.";
            if (!GameAudioOriginalOwner.OptInRequested)
            {
                report.originalAudioCameraContextState = "original_audio_not_requested_default_off";
                return;
            }
            report.originalAudioCameraContextRequested = true;
            if (coordinator.r.nativeSourceSkinLifecycleDiagnosticRequested)
            {
                report.originalAudioCameraContextDeferredForVisualDiagnostic = true;
                report.originalAudioCameraContextState = "deferred_existing_visual_source_camera_diagnostic_owns_source_rig";
                return;
            }
            if (originalAudioCameraContextAttempted)
            {
                report.originalAudioCameraContextState = "duplicate_world_context_creation_refused";
                return;
            }
            if (!createAtIntegratedWorldUpdate)
            {
                originalAudioCameraContextCreationSchedule.Schedule();
                report.originalAudioCameraContextState = "deferred_until_first_integrated_world_update";
                return;
            }
            originalAudioCameraContextAttempted = true;
            try
            {
                originalAudioCameraContext = AndroidNativeSourceCameraRigOwner.CreateAudioContextOnly(
                    coordinator.transform, player);
                report.originalAudioCameraContextCreated = true;
                report.originalAudioCameraContextState = "staged_waiting_for_native_source_context";
                ObserveOriginalAudioCameraContext();
            }
            catch (Exception error)
            {
                var cause = error.GetBaseException();
                report.originalAudioCameraContextState = "refused_closed: " + cause.GetType().Name;
                report.originalAudioCameraContextAdmissionFailure = cause.GetType().Name;
                report.originalAudioCameraContextAdmissionFailureDetail = AndroidNativeAudioCameraContextContract.ShortFailureDetail(cause.Message);
            }
        }
        void ObserveOriginalAudioCameraContext()
        {
            var report = coordinator.r?.world;
            if (report == null)
                return;
            if (!originalAudioCameraContext)
            {
                if (originalAudioCameraContextAttempted && report.originalAudioCameraContextReady)
                {
                    report.originalAudioCameraContextReady = false;
                    report.originalAudioCameraContextState = "source_context_owner_destroyed_after_admission";
                }
                return;
            }
            report.originalAudioCameraContextReady = originalAudioCameraContext.audioContextReady;
            var admissionEvidence = originalAudioCameraContext.audioContextAdmissionEvidence;
            report.originalAudioCameraContextLastAdmissionEvidence = admissionEvidence == null
                ? null : admissionEvidence.Copy();
            report.originalAudioCameraContextRigIndex = originalAudioCameraContext.audioContextRigIndex;
            report.originalAudioCameraContextSourceRigAtIndexZero =
                originalAudioCameraContext.audioContextReady && originalAudioCameraContext.audioContextRigIndex == 0;
            report.originalAudioCameraContextRenderCameraDisabled =
                originalAudioCameraContext.viewCamera && !originalAudioCameraContext.viewCamera.enabled;
            report.originalAudioCameraContextOverrideAbsent =
                originalAudioCameraContext.cameraRig && !originalAudioCameraContext.cameraRig.hasOverride;
            report.originalAudioCameraContextManagedListenerObserved =
                originalAudioCameraContext.managedSourceDefaultListenerObserved;
            report.originalAudioCameraContextManagedListenerRemovalObserved =
                originalAudioCameraContext.managedSourceDefaultListenerPresentAfterDisableCaptured &&
                !originalAudioCameraContext.managedSourceDefaultListenerPresentAfterDisable;
            var startObservation = AndroidNativeAudioCameraContextContract.CreateStartObservation(
                originalAudioCameraContext.audioContextRigActiveAndEnabledObserved,
                originalAudioCameraContext.audioContextRigActiveAndEnabled,
                originalAudioCameraContext.audioContextRigActiveInHierarchyObserved,
                originalAudioCameraContext.audioContextRigActiveInHierarchy,
                originalAudioCameraContext.audioContextCameraModeObserved,
                originalAudioCameraContext.audioContextCameraModeIsNull,
                originalAudioCameraContext.audioContextCameraModeIsPlayerBasic,
                originalAudioCameraContext.audioContextOriginalStartWaitObserved,
                originalAudioCameraContext.audioContextCameraStartGateState);
            report.originalAudioCameraContextRigActivityObserved = startObservation.rigActivityObserved;
            report.originalAudioCameraContextRigActiveAndEnabledObserved =
                originalAudioCameraContext.audioContextRigActiveAndEnabledObserved;
            report.originalAudioCameraContextRigActiveInHierarchyObserved =
                originalAudioCameraContext.audioContextRigActiveInHierarchyObserved;
            report.originalAudioCameraContextRigActiveAndEnabled = startObservation.rigActiveAndEnabled;
            report.originalAudioCameraContextRigActiveInHierarchy = startObservation.rigActiveInHierarchy;
            report.originalAudioCameraContextCameraModeObserved = startObservation.cameraModeObserved;
            report.originalAudioCameraContextCameraModeIsNull = startObservation.cameraModeIsNull;
            report.originalAudioCameraContextCameraModeIsPlayerBasic = startObservation.cameraModeIsPlayerBasic;
            report.originalAudioCameraContextOriginalStartWaitObserved = startObservation.originalStartWaitObserved;
            report.originalAudioCameraContextCameraStartGateState = startObservation.gateState;
            report.originalAudioCameraContextStartupClockObserved =
                originalAudioCameraContext.audioContextStartupClockObserved;
            report.originalAudioCameraContextStartupClockValid =
                originalAudioCameraContext.audioContextStartupClockValid;
            report.originalAudioCameraContextStartupDeadlineExpired =
                originalAudioCameraContext.audioContextStartupDeadlineExpired;
            report.originalAudioCameraContextDamageNumberManagerBeforeCaptured =
                originalAudioCameraContext.damageNumberManagerPreActivationObserved;
            report.originalAudioCameraContextDamageNumberManagerBefore =
                originalAudioCameraContext.damageNumberManagerPresentBeforeActivation;
            report.originalAudioCameraContextDamageNumberManagerAfterCaptured =
                originalAudioCameraContext.damageNumberManagerPostActivationObserved;
            report.originalAudioCameraContextDamageNumberManagerAfter =
                originalAudioCameraContext.damageNumberManagerPresentAfterActivation;
            report.originalAudioCameraContextState = originalAudioCameraContext.status;
        }
        void ReleaseOriginalAudioCameraContext()
        {
            var report = coordinator.r?.world;
            if (!originalAudioCameraContext)
            {
                if (report != null && report.originalAudioCameraContextCreated &&
                    !report.originalAudioCameraContextReleaseVerified)
                    FailOriginalAudioCameraContextCleanup(report);
                return;
            }
            if (report != null)
                report.originalAudioCameraContextReady = false;
            try
            {
                var admissionEvidence = originalAudioCameraContext.audioContextAdmissionEvidence;
                if (report != null && admissionEvidence != null)
                    report.originalAudioCameraContextLastAdmissionEvidence = admissionEvidence.Copy();
                originalAudioCameraContext.ReleaseAudioContext();
                if (report != null)
                {
                    report.originalAudioCameraContextReady = false;
                    admissionEvidence = originalAudioCameraContext.audioContextAdmissionEvidence;
                    if (admissionEvidence != null)
                        report.originalAudioCameraContextLastAdmissionEvidence = admissionEvidence.Copy();
                    report.originalAudioCameraContextRenderCameraDisabled =
                        originalAudioCameraContext.viewCamera && !originalAudioCameraContext.viewCamera.enabled;
                    report.originalAudioCameraContextOverrideAbsent =
                        !originalAudioCameraContext.cameraRig || !originalAudioCameraContext.cameraRig.hasOverride;
                    report.originalAudioCameraContextManagedListenerObserved =
                        originalAudioCameraContext.managedSourceDefaultListenerPresentAfterDisableCaptured &&
                        !originalAudioCameraContext.managedSourceDefaultListenerPresentAfterDisable;
                    report.originalAudioCameraContextManagedListenerRemovalObserved =
                        report.originalAudioCameraContextManagedListenerObserved;
                    report.originalAudioCameraContextReleaseVerified =
                        originalAudioCameraContext.audioContextReleasePreparedForDestroy;
                    report.originalAudioCameraContextDestroyRequested =
                        originalAudioCameraContext.audioContextDestroyRequested;
                    report.originalAudioCameraContextDestroyObservationCaptured = false;
                    report.originalAudioCameraContextDestroyObserved = false;
                    report.originalAudioCameraContextState =
                        originalAudioCameraContext.audioContextReleasePreparedForDestroy
                            ? "owned_root_inactive_source_listener_deactivated_exact_managed_membership_removed_destroy_requested_not_observed"
                            : "release_incomplete_source_listener_teardown_unobserved";
                    report.originalAudioCameraContextDamageNumberManagerAfterCaptured =
                        originalAudioCameraContext.damageNumberManagerPostActivationObserved;
                    report.originalAudioCameraContextDamageNumberManagerAfter =
                        originalAudioCameraContext.damageNumberManagerPresentAfterActivation;
                }
                if (report != null && !originalAudioCameraContext.audioContextReleasePreparedForDestroy)
                    FailOriginalAudioCameraContextCleanup(report);
                originalAudioCameraContext = null;
            }
            catch (Exception error)
            {
                if (report != null)
                    report.originalAudioCameraContextState = "release-error: " + error.GetBaseException().GetType().Name;
                FailOriginalAudioCameraContextCleanup(report);
            }
        }
        void FailOriginalAudioCameraContextCleanup(WorldReport report)
        {
            coordinator.r.success = false;
            coordinator.r.cleanup = false;
            if (report != null)
                report.originalAudioCameraContextReleaseVerified = false;
            if (string.IsNullOrEmpty(coordinator.r.firstFailure))
            {
                coordinator.r.firstFailure = "Original audio camera-context cleanup was not verified";
                coordinator.r.firstFailurePhase = "integrated-world-cleanup";
            }
        }
        public static bool Finite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }
        public static bool Finite(Vector3 value)
        {
            return Finite(value.x) && Finite(value.y) && Finite(value.z);
        }
        public static bool Finite(Quaternion value)
        {
            return Finite(value.x) && Finite(value.y) && Finite(value.z) && Finite(value.w);
        }
        public static string Number(float value)
        {
            return value.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
        }
        public static string Position(Vector3 value)
        {
            return Number(value.x) + "," + Number(value.y) + "," + Number(value.z);
        }
        public static string Rotation(Quaternion value)
        {
            return Number(value.x) + "," + Number(value.y) + "," + Number(value.z) + "," + Number(value.w);
        }
        public void ObserveLightningStakes()
        {
            if (coordinator.r.world == null)
                return;
            bool changed = false;
            if (lightningStakeObserver != null)
            {
                changed = lightningStakeObserver.Observe(coordinator.r.world.seconds);
                string status = lightningStakeObserver.SetupStatus;
                bool statusChanged = coordinator.r.world.lightningStakeObserverStatus != status;
                coordinator.r.world.lightningStakeObserverStatus = status;
                coordinator.r.world.lightningStakeIdentitiesObserved =
                    Math.Max(coordinator.r.world.lightningStakeIdentitiesObserved, lightningStakeObserver.DiscoveredCount);
                changed |= statusChanged;
            }
            if (lightningStakeSourceCallObserver != null && coordinator.r.world.lightningStakeSourceCall != null &&
                savedLightningStakeSourceCallCount != coordinator.r.world.lightningStakeSourceCall.sourceCallCount)
            {
                savedLightningStakeSourceCallCount = coordinator.r.world.lightningStakeSourceCall.sourceCallCount;
                changed = true;
            }
            if (changed)
                coordinator.Save();
        }
        static readonly PropertyInfo worldNativeLootReferenceCount =
            typeof(AsyncOperationHandle<GameObject>).GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic);
        static readonly FieldInfo[] worldBarrierEffectFields =
            new[] { "bucklerShieldTempEffectInstance", "barrierTempEffectInstance" }
                .Select(name => typeof(CharacterBody).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic))
                .ToArray();
        public ItemDef[] WorldTierOneLoot(SessionConfig cfg)
        {
            return WorldLoot(cfg).Where(x => x.tier == ItemTier.Tier1).ToArray();
        }
        public ItemDef[] WorldLoot(SessionConfig cfg)
        {
            if (cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                return ItemCatalog.allItemDefs
                    .Where(item => item && !item.requiredExpansion && coordinator.HasOwnedProfileUnlock(item.unlockableDef) &&
                                   !item.hidden &&
                                   (item.tier == ItemTier.Tier1 || item.tier == ItemTier.Tier2 || item.tier == ItemTier.Tier3) &&
                                   item.DoesNotContainTag(ItemTag.IgnoreForDropList) && item.DoesNotContainTag(ItemTag.WorldUnique))
                    .ToArray();
            var loot = new List<ItemDef> { RoR2Content.Items.Syringe, RoR2Content.Items.CritGlasses, RoR2Content.Items.HealWhileSafe };
            // Receipted additions only. Older accepted configurations retain their original pool.
            if (cfg.teleporterLoop && cfg.objectiveItemNames != null)
            {
                if (cfg.objectiveItemNames.Contains("SprintBonus"))
                    loot.Add(RoR2Content.Items.SprintBonus);
                if (cfg.objectiveItemNames.Contains("FlatHealth"))
                    loot.Add(RoR2Content.Items.FlatHealth);
            }
            loot.Add(RoR2Content.Items.ChainLightning);
            if (cfg.worldAdditionalLootItems != null)
                foreach (var name in cfg.worldAdditionalLootItems)
                {
                    var def = ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(name));
                    coordinator.Check(def && def.name == name && !def.requiredExpansion && !def.unlockableDef && !def.hidden,
                                      "Core loot identity/requirement unavailable: " + name);
                    loot.Add(def);
                }
            coordinator.Check(loot.All(x => x) && loot.Distinct().Count() == loot.Count, "Duplicate or absent composed loot definition");
            return loot.ToArray();
        }
        public BuffDef[] WorldLootBuffs(SessionConfig cfg)
        {
            if (cfg.worldAdditionalLootItems == null || !cfg.worldAdditionalLootItems.Contains("SlowOnHit"))
                return new BuffDef[0];
            var def = coordinator.artifactBundle.LoadAsset<BuffDef>(cfg.worldLootSlowBuffAsset);
            coordinator.Check(def && def.name == "bdSlow60", "Original loot slow buff missing");
            coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs), "Slow60", def);
            return new[] { def };
        }
        readonly Dictionary<string, AsyncOperationHandle<GameObject>> worldProjectileGhostLeases =
            new Dictionary<string, AsyncOperationHandle<GameObject>>();
        public void PrepareSourceTemporaryVisuals()
        {
            // Treebot's original states can apply Weak and Fruiting immediately. In
            // this offline composition CharacterBody's legacy async preload does not
            // populate those slots, so lease the shipped prefabs from the owned catalog.
            var type = typeof(CharacterBody).GetNestedType("AssetReferences", BindingFlags.NonPublic);
            var entries =
                new[] { (field: "weakTempEffectPrefab", path: "Assets/WholeGame/RoR2/Base/Characters/Treebot/WeakEffect.prefab"),
                        (field: "fruitingEffectPrefab", path: "Assets/WholeGame/RoR2/Base/Characters/Treebot/FruitingEffect.prefab") };
            foreach (var entry in entries)
            {
                var source = WholeCatalogComposed.LoadOwnedContent<GameObject>(entry.path);
                var field = type.GetField(entry.field, BindingFlags.Public | BindingFlags.Static);
                coordinator.Check(source && source.GetComponent<TemporaryVisualEffect>() && field != null &&
                                      field.FieldType == typeof(GameObject) && !((GameObject)field.GetValue(null)),
                                  "Original temporary visual binding unavailable: " + entry.field);
                coordinator.worldLootEffectSlots.Add(field, null);
                field.SetValue(null, source);
            }
        }
        public GameObject OriginalProjectileGhost(RoR2.Projectile.ProjectileController controller)
        {
            coordinator.Check(controller, "Original projectile controller absent");
            // Match the shipped controller's address-first selection without filling its obsolete direct field.
            if (controller.ghostPrefabAddress == null || !controller.ghostPrefabAddress.RuntimeKeyIsValid())
                return controller.ghostPrefab;
            var key = controller.ghostPrefabAddress.RuntimeKey.ToString();
            AsyncOperationHandle<GameObject> lease;
            if (!worldProjectileGhostLeases.TryGetValue(key, out lease))
            {
                lease = Addressables.LoadAssetAsync<GameObject>(controller.ghostPrefabAddress);
                worldProjectileGhostLeases.Add(key, lease);
                lease.WaitForCompletion();
            }
            coordinator.Check(lease.Status == AsyncOperationStatus.Succeeded && lease.Result &&
                                  lease.Result.GetComponent<RoR2.Projectile.ProjectileGhostController>() &&
                                  lease.Result.GetComponentsInChildren<Component>(true).All(component => component),
                              "Original projectile ghost address contract failed: " + controller.name);
            return lease.Result;
        }
        public GameObject[] PrepareWorldLootSupport(SessionConfig cfg)
        {
            if (cfg.worldLootSupportPaths == null || cfg.worldLootSupportPaths.Length == 0)
                return new GameObject[0];
            coordinator.Check(cfg.worldLootSupportPaths.Length == 2 || cfg.worldLootSupportPaths.Length == 3 ||
                                  cfg.worldLootSupportPaths.Length == 6 || cfg.worldLootSupportPaths.Length == 7 ||
                                  cfg.worldLootSupportPaths.Length == 9 || cfg.worldLootSupportPaths.Length == 10 ||
                                  cfg.worldLootSupportPaths.Length == 11,
                              "Core loot support contract length changed");
            coordinator.r.phase = "integrated-core-loot-support";
            coordinator.Save();
            var effects = new List<GameObject>();
            foreach (var path in cfg.worldLootSupportPaths)
            {
                int effectStart = effects.Count;
                var presentationRoots = new List<GameObject>();
                int index = Array.IndexOf(cfg.objectiveSupportPaths, path);
                coordinator.Check(index >= 0, "Core loot provider location absent: " + path);
                var source = coordinator.objectiveSupportSources[index];
                bool shield = path == "Prefabs/Effects/ShieldBreakEffect", feather = path == "Prefabs/Effects/FeatherEffect",
                     slow = path == "Prefabs/TemporaryVisualEffects/SlowDownTime", healthPack = path == "Prefabs/NetworkedObjects/HealPack",
                     moneyPack = path == "Prefabs/NetworkedObjects/BonusMoneyPack";
                bool stun = path == "Prefabs/Effects/ImpactEffects/ImpactStunGrenade",
                     diamond = path == "Prefabs/Effects/ImpactEffects/DiamondDamageBonusEffect";
                bool sticky = path == "Prefabs/Projectiles/StickyBomb", wisp = path == "Prefabs/NetworkedObjects/WilloWispDelay",
                     barrier = path == "Prefabs/TemporaryVisualEffects/BarrierEffect";
                coordinator.Check(shield || feather || slow || healthPack || moneyPack || stun || sticky || wisp || diamond || barrier ||
                                      path == "Prefabs/TemporaryVisualEffects/BucklerDefense",
                                  "Unknown core loot support: " + path);
                coordinator.Check(source && source.name == (shield       ? "ShieldBreakEffect"
                                                            : feather    ? "FeatherEffect"
                                                            : slow       ? "SlowDownTime"
                                                            : healthPack ? "HealPack"
                                                            : moneyPack  ? "BonusMoneyPack"
                                                            : stun       ? "ImpactStunGrenade"
                                                            : diamond    ? "DiamondDamageBonusEffect"
                                                            : sticky     ? "StickyBomb"
                                                            : wisp       ? "WilloWispDelay"
                                                            : barrier    ? "BarrierEffect"
                                                                         : "BucklerDefense"),
                                  "Core loot source prefab identity changed: " + path);
                if (slow || healthPack || moneyPack || stun || sticky)
                    coordinator.worldNativeLootLeaseBaselines.Add(
                        index, (int)typeof(AsyncOperationHandle<GameObject>)
                                   .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                   .GetValue(coordinator.objectiveSupportLeases[index]));
                if (feather)
                {
                    // Original ProcessJump loads this provider asset on each bonus jump.
                    // Observe those real calls and release their owned leases on teardown.
                    coordinator.Check(coordinator.worldPlayer && coordinator.r.world != null && worldFeatherEffectIndex < 0,
                                      "Unowned Feather effect observation");
                    worldFeatherEffectIndex = index;
                    worldFeatherReferenceBaseline = (int)typeof(AsyncOperationHandle<GameObject>)
                                                        .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                                        .GetValue(coordinator.objectiveSupportLeases[index]);
                    worldFeatherJumped = () =>
                    {
                        if (coordinator.worldPlayer.characterMotor.jumpCount > coordinator.worldPlayer.baseJumpCount)
                            coordinator.r.world.featherJumps++;
                    };
                    coordinator.worldPlayer.onJump += worldFeatherJumped;
                }
                else if (!healthPack && !moneyPack && !stun && !sticky)
                {
                    var type = wisp ? typeof(GlobalEventManager).GetNestedType("CommonAssets", BindingFlags.Public)
                                    : (shield || diamond ? typeof(HealthComponent) : typeof(CharacterBody))
                                          .GetNestedType("AssetReferences", BindingFlags.NonPublic);
                    var field = type.GetField(wisp      ? "explodeOnDeathPrefab"
                                              : shield  ? "shieldBreakEffectPrefab"
                                              : diamond ? "diamondDamageBonusImpactEffectPrefab"
                                              : slow    ? "slowDownTimeTempEffectPrefab"
                                              : barrier ? "barrierTempEffectPrefab"
                                                        : "bucklerShieldTempEffectPrefab",
                                              BindingFlags.Public | BindingFlags.Static);
                    coordinator.Check(field != null && field.FieldType == typeof(GameObject) && !((GameObject)field.GetValue(null)),
                                      "Unowned core loot effect slot: " + path);
                    coordinator.worldLootEffectSlots.Add(field, (GameObject)field.GetValue(null));
                    field.SetValue(null, source);
                    coordinator.Check((GameObject)field.GetValue(null) == source, "Core loot source binding failed: " + path);
                }
                if (shield || feather || stun || diamond)
                {
                    coordinator.Check(source.GetComponent<EffectComponent>(), "Original core loot EffectComponent missing: " + path);
                    effects.Add(source);
                }
                else if (healthPack)
                {
                    var pickup = source.GetComponentInChildren<HealthPickup>(true);
                    coordinator.Check(pickup && pickup.baseObject == source && pickup.teamFilter &&
                                          source.GetComponent<NetworkIdentity>() && pickup.pickupEffect &&
                                          pickup.pickupEffect.GetComponent<EffectComponent>(),
                                      "Original heal pack linkage missing");
                    effects.Add(pickup.pickupEffect);
                }
                else if (moneyPack)
                {
                    var pickup = source.GetComponentInChildren<MoneyPickup>(true);
                    coordinator.Check(pickup && pickup.baseObject == source && pickup.teamFilter && source.GetComponent<NetworkIdentity>(),
                                      "Original money pack linkage missing");
                    if (pickup.pickupEffectPrefab)
                    {
                        coordinator.Check(pickup.pickupEffectPrefab.GetComponent<EffectComponent>(),
                                          "Original money effect linkage missing");
                        effects.Add(pickup.pickupEffectPrefab);
                    }
                }
                else if (sticky)
                {
                    var ghost = OriginalProjectileGhost(source.GetComponent<RoR2.Projectile.ProjectileController>());
                    var explosion = source.GetComponent<RoR2.Projectile.ProjectileImpactExplosion>();
                    coordinator.Check(ghost && explosion && explosion.impactEffect && source.GetComponent<NetworkIdentity>(),
                                      "Original sticky projectile/ghost/blast contract missing");
                    effects.Add(explosion.impactEffect);
                    presentationRoots.Add(ghost);
                }
                else if (wisp)
                {
                    var blast = source.GetComponent<DelayBlast>();
                    coordinator.Check(blast && blast.explosionEffect && source.GetComponent<TeamFilter>() &&
                                          source.GetComponent<NetworkIdentity>(),
                                      "Original on-kill delay/blast contract missing");
                    if (blast.delayEffect)
                        effects.Add(blast.delayEffect);
                    effects.Add(blast.explosionEffect);
                }
                else
                    coordinator.Check(source.GetComponent<TemporaryVisualEffect>() &&
                                          source.GetComponent<TemporaryVisualEffect>().visualTransform,
                                      "Original temporary effect linkage missing: " + path);
                foreach (var renderer in presentationRoots.Concat(new[] { source })
                             .Concat(effects.Skip(effectStart))
                             .Distinct()
                             .SelectMany(x => x.GetComponentsInChildren<Renderer>(true))
                             .Distinct())
                {
                    if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                        continue;
                    coordinator.Check(!renderer.GetComponent<Collider>(),
                                      "Core loot renderer shares a collider; preserve its layer before adapting visibility");
                    coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                    coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                    renderer.sharedMaterials = renderer.sharedMaterials
                                                   .Select(original =>
                                                           {
                                                               if (!original)
                                                                   return null;
                                                               var copy = new Material(original);
                                                               copy.shader = Resources.Load<Shader>("StageSurfacePreview");
                                                               copy.shaderKeywords = new string[0];
                                                               AndroidMaterialPresentation.Apply(original, copy);
                                                               coordinator.worldMaterials.Add(copy);
                                                               return copy;
                                                           })
                                                   .ToArray();
                    renderer.gameObject.layer = 30;
                }
            }
            return effects.Distinct().ToArray();
        }
        public void ObserveWorldLootSupport(CharacterBody body, bool force = false)
        {
            int loads = 0;
            foreach (var pair in coordinator.worldNativeLootLeaseBaselines)
            {
                int count = (int)worldNativeLootReferenceCount.GetValue(coordinator.objectiveSupportLeases[pair.Key]) - pair.Value;
                loads += count;
                var name = coordinator.objectiveSupportSources[pair.Key].name;
                if (name == "ImpactStunGrenade")
                    coordinator.r.world.stunImpactLoads = count;
                else if (name == "StickyBomb")
                    coordinator.r.world.stickyBombLoads = count;
            }
            coordinator.r.world.nativeLootProviderLoads = loads;
            if (force || Time.frameCount % 10 == 0)
            {
                if (!worldWispEffectEligible)
                    worldWispEffectEligible =
                        (body && body.inventory && body.inventory.GetItemCount(RoR2Content.Items.ExplodeOnDeath) > 0) ||
                        coordinator.directorActors.Any(x => x.body && x.body.inventory &&
                                                            x.body.inventory.GetItemCount(RoR2Content.Items.ExplodeOnDeath) > 0);
                if (worldWispEffectEligible)
                    foreach (var blast in UnityEngine.Object.FindObjectsOfType<DelayBlast>().Where(x => x.gameObject.scene.IsValid() &&
                                                                                                        x.name == "WilloWispDelay(Clone)"))
                        if (coordinator.worldNativeLootObjects.Add(blast.gameObject))
                        {
                            coordinator.worldObjects.Add(blast.gameObject);
                            coordinator.r.world.wispDelaySpawns++;
                        }
                foreach (var identity in NetworkServer.objects.Values)
                {
                    if (!identity || !identity.gameObject.scene.IsValid())
                        continue;
                    var bomb = identity.GetComponent<RoR2.Projectile.ProjectileController>();
                    if (!bomb ||
                        !(bomb.name == "StickyBomb(Clone)" || bomb.name == "MissileProjectile(Clone)" || bomb.name == "Sawmerang(Clone)" ||
                          bomb.name == "GravSphere(Clone)" || bomb.name == "DaggerProjectile(Clone)"))
                        continue;
                    if (coordinator.worldNativeLootObjects.Add(bomb.gameObject))
                    {
                        coordinator.worldObjects.Add(bomb.gameObject);
                        if (bomb.name == "StickyBomb(Clone)")
                            coordinator.r.world.stickyBombSpawns++;
                        if (bomb.name == "DaggerProjectile(Clone)" && coordinator.r.dots != null)
                            coordinator.r.dots.daggerSpawns++;
                    }
                }
            }
            if (RoR2Content.Buffs.Slow60)
                coordinator.r.world.slowedEnemiesPeak = Mathf.Max(
                    coordinator.r.world.slowedEnemiesPeak, coordinator.directorActors.Count(x => x.body && x.body.healthComponent.alive &&
                                                                                                 x.body.HasBuff(RoR2Content.Buffs.Slow60)));
            if (coordinator.worldNativeLootLeaseBaselines.Count > 0 && (force || Time.frameCount % 30 == 0))
            {
                var packs = force ? Resources.FindObjectsOfTypeAll<GameObject>()
                                  : NetworkServer.objects.Values.Where(x => x).Select(x => x.gameObject).ToArray();
                foreach (var obj in packs.Where(x => x && x.scene.IsValid() &&
                                                     (x.name == "HealPack(Clone)" || x.name == "BonusMoneyPack(Clone)")))
                    if (coordinator.worldNativeLootObjects.Add(obj))
                    {
                        coordinator.worldObjects.Add(obj);
                        if (obj.name == "HealPack(Clone)")
                            coordinator.r.world.healthPacks++;
                        else
                            coordinator.r.world.moneyPacks++;
                    }
            }
            if (worldFeatherEffectIndex >= 0)
            {
                coordinator.r.world.featherEffectLoads =
                    (int)worldNativeLootReferenceCount.GetValue(coordinator.objectiveSupportLeases[worldFeatherEffectIndex]) -
                    worldFeatherReferenceBaseline;
                coordinator.Check(coordinator.r.world.featherEffectLoads == coordinator.r.world.featherJumps,
                                  "Original Feather loads differ from observed bonus jumps");
            }
            if (coordinator.worldLootEffectSlots.Count == 0 || !body)
                return;
            coordinator.r.world.barrier = body.healthComponent.barrier;
            foreach (var field in worldBarrierEffectFields)
            {
                var effect = (TemporaryVisualEffect)field.GetValue(body);
                if (effect && !coordinator.worldLootTemporaryEffects.Contains(effect.gameObject))
                {
                    coordinator.worldLootTemporaryEffects.Add(effect.gameObject);
                    if (field.Name == "barrierTempEffectInstance")
                    {
                        coordinator.Check(effect.healthComponent == body.healthComponent && effect.parentTransform == body.coreTransform,
                                          "Original barrier effect body linkage differs");
                        coordinator.r.world.barrierEffects++;
                    }
                }
            }
        }
        public void CleanupWorldLootSupport()
        {
            coordinator.CleanupWorldProcContent();
            coordinator.CleanupOfflineSettingsPause();
            coordinator.CleanupWorldEquipment();
            coordinator.CleanupWorldItemDisplays();
            if (coordinator.r.world != null)
                ObserveWorldLootSupport(coordinator.worldPlayer, true);
            foreach (var pair in coordinator.worldNativeLootLeaseBaselines)
            {
                int extra = (int)typeof(AsyncOperationHandle<GameObject>)
                                .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                .GetValue(coordinator.objectiveSupportLeases[pair.Key]) -
                            pair.Value;
                coordinator.Check(extra >= 0, "Original native loot provider ownership changed");
                for (int i = 0; i < extra; i++)
                    Addressables.Release(coordinator.objectiveSupportSources[pair.Key]);
            }
            coordinator.worldNativeLootLeaseBaselines.Clear();
            coordinator.worldNativeLootObjects.Clear();
            worldWispEffectEligible = false;
            if (coordinator.r.world != null)
                coordinator.r.world.nativeLootProvidersCleaned = true;
            if (worldFeatherJumped != null)
            {
                if (!ReferenceEquals(coordinator.worldPlayer, null))
                    coordinator.worldPlayer.onJump -= worldFeatherJumped;
                worldFeatherJumped = null;
            }
            if (worldFeatherEffectIndex >= 0)
            {
                for (int i = 0; i < coordinator.r.world.featherEffectLoads; i++)
                    Addressables.Release(coordinator.objectiveSupportSources[worldFeatherEffectIndex]);
                worldFeatherEffectIndex = -1;
                coordinator.r.world.featherEffectCleaned = true;
            }
            foreach (var effect in coordinator.worldLootTemporaryEffects)
                if (effect)
                    PortSession.Destroy(effect);
            foreach (var pair in coordinator.worldLootEffectSlots)
                pair.Key.SetValue(null, pair.Value);
            coordinator.worldLootEffectSlots.Clear();
            foreach (var pair in coordinator.worldLootSourceMaterials)
                if (pair.Key)
                    pair.Key.sharedMaterials = pair.Value;
            coordinator.worldLootSourceMaterials.Clear();
            foreach (var pair in coordinator.worldLootSourceLayers)
                if (pair.Key)
                    pair.Key.layer = pair.Value;
            coordinator.worldLootSourceLayers.Clear();
            foreach (var lease in worldProjectileGhostLeases.Values)
                if (lease.IsValid())
                    Addressables.Release(lease);
            worldProjectileGhostLeases.Clear();
        }
        public IEnumerator PrepareIntegratedWorld(CharacterBody player, SessionConfig cfg)
        {
            ResetOriginalAudioCameraContextAttemptForWorld();
            survivorCombatOutputs?.Dispose();
            if (survivorCombatOutputs != null && survivorCombatOutputs.report.cleaned)
                survivorCombatOutputs = null;
            worldFeatherInputAt = -1;
            lastTransientWindowRequestCount = 0;
            coordinator.Check(
                ((Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap").GetValue(null))
                        .Count == 0,
                "Unowned effect pools before integrated world");
            coordinator.ownsIntegratedPools = true;
            coordinator.r.world = new WorldReport {
                scope =
                    "Persistent original Commando/default skills, recovered golemplains collision/navigation, continuous original one-card director, local HLAPI client/authority, original Money purchases/chest animation/droplet/default pickup/server grants/gold/XP/stats. Authored layout/HUD/input/materials and explicit audio-unavailable pickup presentation. Original Run clock only: stock startup/menu/profile/route/victory remain unavailable; composed original teleporter is observed separately; no NetworkUser, LocalUser or entitlement grant.",
                feedbackCapability = "Authored pickup HUD; original native-audio notification handler unavailable."
            };
            if (survivorCombatOutputs != null)
                coordinator.r.world.survivorCombatOutputs = survivorCombatOutputs.report;
            try
            {
                lightningStakeObserver = new LightningStakeDiagnosticObserver();
                coordinator.r.world.lightningStakeObserverStatus = lightningStakeObserver.SetupStatus;
                coordinator.r.world.lightningStakes = lightningStakeObserver.Observations;
            }
            catch (Exception observerError)
            {
                coordinator.r.world.lightningStakeObserverStatus = "setup-error: " + observerError.GetBaseException().Message;
                lightningStakeObserver = null;
            }
            if (coordinator.r.lightningStakeSourceCallDiagnosticRequested)
            {
                coordinator.r.world.lightningStakeSourceCall = new PortSession.LightningStakeSourceCallReport { status = "requested" };
                try
                {
                    lightningStakeSourceCallObserver = new LightningStakeSourceCallObserver(coordinator.r.world.lightningStakeSourceCall);
                }
                catch (Exception sourceObserverError)
                {
                    coordinator.r.world.lightningStakeSourceCall.status = "setup-error";
                    coordinator.r.world.lightningStakeSourceCall.firstCaptureFailureType =
                        sourceObserverError.GetBaseException().GetType().FullName;
                    lightningStakeSourceCallObserver = null;
                }
            }
            coordinator.worldPlayer = player;
            PrepareOriginalAudioCameraContext(player);
            if (coordinator.r.selectedSurvivor == "Engi")
            {
                // Population setup may replace a catalog template with its
                // owned adaptation after the player has spawned. Native body
                // index and reciprocal master linkage survive that replacement.
                var engiIndex = BodyCatalog.FindBodyIndex("EngiBody");
                coordinator.Check(engiShieldGuard == null && engiIndex != BodyIndex.None && player.bodyIndex == engiIndex &&
                                      player.master && player.master.GetBody() == player,
                                  "Engineer shield compatibility requires the selected original body");
                var template = WholeCatalogComposed.LoadOwnedContent<GameObject>(
                    "Assets/WholeGame/RoR2/Base/Characters/Engi/Projectiles/EngiBubbleShield/EngiBubbleShield.prefab");
                coordinator.Check(template && !template.scene.IsValid(), "Engineer shield source must be the owned catalog template");
                engiShieldGuard = EngiShieldHitGuardTemplateLease.Acquire(template);
                coordinator.r.world.engiShieldGuardPrepared = true;
            }
            PrepareEarlyHurtCaches(player);
            PrepareUnavailableWorldPresentation(player);
            coordinator.r.phase = "integrated-world-client";
            coordinator.Save();
            var connect = coordinator.ConnectActiveBodyClient(player);
            while (connect.MoveNext())
                yield return connect.Current;
            coordinator.r.world.authority =
                player.networkIdentity.hasAuthority && coordinator.activeBodyClient.isConnected && coordinator.activeBodyOwner.isReady;
            coordinator.Check(coordinator.r.world.authority, "Integrated local authority missing");
            Action skillActivity = PortSessionOriginalAudioOwner.PassivePcmCaptureAfterAuthoritySkillRequested
                ? new Action(coordinator.OnRecognizedAuthoritySkillForPassivePcm) : null;
            survivorSkills = new SurvivorSkillObserver(player, skillActivity);
            if (coordinator.r.diagnosticSkillCoverage || coordinator.r.developerSkillVariantOverride != null)
                survivorSkills.report.skillVariantInventory = SurvivorSkillObserver.CaptureSkillVariantInventory(
                    player.gameObject, player.master.loadout, "native-master-loadout-live");
            coordinator.r.survivorSkills = survivorSkills.report;
            if (survivorCombatOutputs == null)
                survivorCombatOutputs = new SurvivorCombatOutputObserver(player);
            coordinator.r.world.survivorCombatOutputs = survivorCombatOutputs.report;
            if (coordinator.r.selectedSurvivor == "Engi")
            {
                engiNativeOutputs = new EngineerNativeOutputObserver(player);
                coordinator.r.world.engiNativeOutputs = engiNativeOutputs.report;
            }
            coordinator.PrepareWholeRunAvailability();
            var displayRules = coordinator.PrepareWholeModelDisplayRules();
            while (displayRules.MoveNext())
                yield return displayRules.Current;
            // Source catalogs persist for the session, rather than being rebuilt around each interaction.
            var flags = BindingFlags.Static | BindingFlags.NonPublic;
            coordinator.Check(!coordinator.ownsPickupCatalog && PickupCatalog.pickupCount == 0, "Unowned integrated pickup catalog");
            foreach (var name in new[] { "entries", "itemIndexToPickupIndex", "equipmentIndexToPickupIndex", "artifactIndexToPickupIndex",
                                         "miscPickupIndexToPickupIndex", "droneIndexToPickupIndex", "keyItemIndexToPickupIndex",
                                         "<pickupCount>k__BackingField" })
            {
                var field = typeof(PickupCatalog).GetField(name, flags);
                coordinator.Check(field != null, "Integrated pickup field absent: " + name);
                coordinator.priorPickupFields[field] = field.GetValue(null);
            }
            coordinator.pickupNameMap = (IDictionary) typeof(PickupCatalog).GetField("nameToPickupIndex", flags).GetValue(null);
            coordinator.pickupTierMap = (IDictionary) typeof(PickupCatalog).GetField("itemTierToPickupIndex", flags).GetValue(null);
            coordinator.Check(coordinator.pickupNameMap.Count == 0 && coordinator.pickupTierMap.Count == 0,
                              "Unowned integrated pickup maps");
            coordinator.priorPickupAvailability = PickupCatalog.availability;
            coordinator.ownsPickupCatalog = true;
            coordinator.Check(MiscPickupCatalog.pickupCount == 0 && !RoR2Content.MiscPickups.LunarCoin, "Unowned integrated misc catalog");
            worldLunarCoin = coordinator.artifactBundle.LoadAsset<LunarCoinDef>(cfg.worldLunarCoinAsset);
            coordinator.Check(worldLunarCoin && worldLunarCoin.name == "LunarCoin" && worldLunarCoin.coinValue == 1 &&
                                  (worldLunarCoin.displayPrefab || worldLunarCoin.pickupModelReference != null &&
                                                                       worldLunarCoin.pickupModelReference.RuntimeKeyIsValid()) &&
                                  worldLunarCoin.dropletDisplayPrefab,
                              "Original lunar coin definition/display missing");
            previousWorldMiscContent = RoR2.ContentManagement.ContentManager._miscPickupDefs;
            previousWorldMiscCatalog = PortSession.RewardField(typeof(MiscPickupCatalog), "_miscPickupDefs").GetValue(null);
            previousWorldMiscAvailability = MiscPickupCatalog.availability;
            ownsWorldMisc = true;
            var miscDefinitions = coordinator.r.liveCatalogs != null
                                      ? WholeCatalogComposed.DefinitionFamily<MiscPickupDef>(new[] { worldLunarCoin })
                                      : new MiscPickupDef[] { worldLunarCoin };
            if (coordinator.r.liveCatalogs != null)
                foreach (var def in miscDefinitions)
                    priorWholeMiscIndices.Add(def, def.miscPickupIndex);
            RoR2.ContentManagement.ContentManager._miscPickupDefs = miscDefinitions;
            if (coordinator.r.liveCatalogs == null)
                RoR2Content.MiscPickups.LunarCoin = worldLunarCoin;
            PortSession.StaticCall(typeof(MiscPickupCatalog), "Init");
            if (coordinator.r.liveCatalogs != null)
                WholeCatalogComposed.PopulateDefinitionFields("MiscPickups", miscDefinitions);
            var lunarPickup = worldLunarCoin.CreatePickupDef();
            var moonEquipmentPickups = cfg.moonMission ? new[] { RoR2Content.Equipment.AffixLunar.CreatePickupDef() } : new PickupDef[0];
            if (coordinator.r.liveCatalogs != null)
            {
                var pickups = coordinator.PrepareWholePickups();
                while (pickups.MoveNext())
                    yield return pickups.Current;
                lunarPickup = PickupCatalog.GetPickupDef(PickupCatalog.FindPickupIndex(worldLunarCoin.miscPickupIndex));
                coordinator.Check(lunarPickup != null, "Native Lunar pickup metadata missing");
            }
            else
                PickupCatalog.SetEntries(ItemCatalog.allItemDefs.Select(x => x.CreatePickupDef())
                                             .Concat(moonEquipmentPickups)
                                             .Concat(coordinator.EligibleWorldEquipment().Select(x => x.CreatePickupDef()))
                                             .Concat(new[] { lunarPickup })
                                             .ToArray());
            // Native profiles size discovery storage from this complete pickup catalog.
            // Load earned state before native rules and the first stage choose loot.
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                coordinator.PrepareNativeFirstStagePlayerContext(player, cfg);
            coordinator.PrepareIntegratedResults(player, cfg);
            if (cfg.moonMission)
                coordinator.Check(PickupCatalog.GetPickupDef(PickupCatalog.FindPickupIndex(RoR2Content.Equipment.AffixLunar.equipmentIndex))
                                          .equipmentIndex == RoR2Content.Equipment.AffixLunar.equipmentIndex,
                                  "Original Lunar equipment pickup metadata missing");
            coordinator.r.world.lunarDefinition =
                MiscPickupCatalog.GetMiscDef(worldLunarCoin.miscPickupIndex) == worldLunarCoin &&
                PickupCatalog.FindPickupIndex(worldLunarCoin.miscPickupIndex) == lunarPickup.pickupIndex &&
                lunarPickup.attemptGrant.Method.DeclaringType == typeof(LunarCoinDef);
            coordinator.Check(coordinator.r.world.lunarDefinition && !Util.LookUpBodyNetworkUser(player),
                              "Original lunar definition or unavailable currency contract changed");
            coordinator.r.world.lunarCurrencyAvailable = false;
            coordinator.Check(Run.instance.availableTier1DropList.Count == 0 && Run.instance.availableTier2DropList.Count == 0 &&
                                  Run.instance.availableTier3DropList.Count == 0,
                              "Unowned integrated loot lists");
            ownsWorldLists = true;
            coordinator.worldLootDefinitions = WorldLoot(cfg);
            coordinator.r.world.itemStacks =
                coordinator.worldLootDefinitions.Select(x => new WorldItemObservation { item = x.name, tier = x.tier.ToString() })
                    .ToArray();
            foreach (var item in coordinator.worldLootDefinitions)
                coordinator.Check(!Run.instance.IsItemExpansionLocked(item.itemIndex) && !item.requiredExpansion &&
                                      coordinator.HasOwnedProfileUnlock(item.unlockableDef) && !item.hidden &&
                                      item.DoesNotContainTag(ItemTag.IgnoreForDropList) && item.DoesNotContainTag(ItemTag.WorldUnique),
                                  "Integrated base item unavailable: " + item.name);
            if (cfg.worldAdditionalLootItems != null && cfg.worldAdditionalLootItems.Length > 0)
            {
                previousWorldAvailableItems = Run.instance.availableItems;
                previousWorldAvailableEquipment = Run.instance.availableEquipment;
                coordinator.worldAvailableItems = ItemMask.Rent();
                coordinator.worldAvailableEquipment = EquipmentMask.Rent();
                Run.instance.availableItems = coordinator.worldAvailableItems;
                Run.instance.availableEquipment = coordinator.worldAvailableEquipment;
                foreach (var item in coordinator.worldLootDefinitions)
                    coordinator.worldAvailableItems.Add(item.itemIndex);
                foreach (var def in coordinator.EligibleWorldEquipment())
                    coordinator.worldAvailableEquipment.Add(def.equipmentIndex);
                if (cfg.teleporterLoop)
                {
                    // Current explicit tables honor Run availability. Include their indexed base boss rewards,
                    // preserving their original tables/weights and all expansion/unlock restrictions.
                    foreach (var item in coordinator.ComposedBaseBossRewards(cfg))
                    {
                        coordinator.Check(!Run.instance.IsItemExpansionLocked(item.itemIndex),
                                          "Owned base boss reward mask differs: " + item.name);
                        coordinator.worldAvailableItems.Add(item.itemIndex);
                    }
                }
                Run.instance.BuildDropTable();
            }
            else
            {
                foreach (var item in coordinator.worldLootDefinitions)
                    if (item.tier == ItemTier.Tier1)
                        Run.instance.availableTier1DropList.Add(PickupCatalog.FindPickupIndex(item.itemIndex));
                    else if (item.tier == ItemTier.Tier2)
                        Run.instance.availableTier2DropList.Add(PickupCatalog.FindPickupIndex(item.itemIndex));
            }
            coordinator.r.world.lootTier1 = Run.instance.availableTier1DropList.Count;
            coordinator.r.world.lootTier2 = Run.instance.availableTier2DropList.Count;
            coordinator.r.world.lootTier3 = Run.instance.availableTier3DropList.Count;
            coordinator.Check(coordinator.r.world.lootTier1 + coordinator.r.world.lootTier2 + coordinator.r.world.lootTier3 ==
                                  coordinator.worldLootDefinitions.Length,
                              "Original composed drop lists differ from eligible item domain");
            coordinator.moneyCatalogField = typeof(CostTypeCatalog).GetField("costTypeDefs", flags);
            coordinator.priorMoneyCatalog = coordinator.moneyCatalogField.GetValue(null);
            coordinator.Check((coordinator.priorMoneyCatalog == null || ((Array)coordinator.priorMoneyCatalog).Length == 0) &&
                                  !coordinator.ownsMoneyCatalog,
                              "Unowned integrated cost catalog");
            coordinator.ownsMoneyCatalog = true;
            PortSession.StaticCall(typeof(CostTypeCatalog), "Init");
            coordinator.Check(CostTypeCatalog.costTypeCount == (int)CostTypeIndex.Count &&
                                  CostTypeCatalog.GetCostTypeDef(CostTypeIndex.Money).name == "Money",
                              "Original integrated cost catalog initialization differs");
            var generic = coordinator.PrepareOriginalDefaultPickup(cfg);
            while (generic.MoveNext())
                yield return generic.Current;
            coordinator.r.phase = "integrated-world-loot";
            coordinator.Save();
            worldDropletField = PortSession.RewardField(typeof(PickupDropletController), "pickupDropletPrefab");
            priorWorldDroplet = worldDropletField.GetValue(null);
            coordinator.Check(priorWorldDroplet == null, "Unowned integrated droplet source");
            var bundle = new ResourceLocationBase("pickup-droplet-lab",
                                                  System.IO.Path.Combine(Application.persistentDataPath, "payload", "pickup-droplet-lab"),
                                                  typeof(AssetBundleProvider).FullName, typeof(IAssetBundleResource));
            bundle.Data = new AssetBundleRequestOptions { BundleName = "pickup-droplet-lab" };
            worldDropletLocator = new ResourceLocationMap("integrated-world-droplet");
            worldDropletLocator.Add(cfg.pickupDropletKey,
                                    new ResourceLocationBase(cfg.pickupDropletKey, cfg.pickupDropletAsset,
                                                             typeof(BundledAssetProvider).FullName, typeof(GameObject), bundle));
            Addressables.AddResourceLocator(worldDropletLocator);
            PortSession.StaticCall(typeof(PickupDropletController), "Init");
            float deadline = Time.realtimeSinceStartup + 8;
            while (worldDropletField.GetValue(null) == null && Time.realtimeSinceStartup < deadline)
                yield return null;
            worldDropletSource = (GameObject)worldDropletField.GetValue(null);
            ownsWorldDroplet = worldDropletSource;
            coordinator.Check(worldDropletSource && worldDropletSource.name == "PickupDroplet" && LegacyResourcesAPI.ActiveCount == 0,
                              "Integrated original droplet Init failed");
            coordinator.worldChestTable = coordinator.artifactBundle.LoadAsset<BasicPickupDropTable>(cfg.chestDropTableAsset);
            coordinator.Check(coordinator.worldChestTable && coordinator.worldChestTable.name == "dtChest1" &&
                                  coordinator.worldChestTable.canDropBeReplaced,
                              "Integrated source drop table identity/policy differs");
            coordinator.r.world.tableLoadedCount = coordinator.worldChestTable.GetPickupCount();
            coordinator.worldChestTable.RegenerateDropTable(Run.instance);
            coordinator.r.world.lootDomain = coordinator.worldChestTable.GetPickupCount();
            coordinator.Check(coordinator.r.world.lootDomain == coordinator.worldLootDefinitions.Length,
                              "Integrated source chest loot domain missing");
            PrepareWorldMessages();
            worldCoinLease = LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/Effects/CoinEmitter");
            ownsWorldCoinLease = true;
            yield return worldCoinLease;
            coordinator.Check(worldCoinLease.Result == coordinator.rewardPrefabs[0], "Integrated coin source witness differs");
            worldCoinBaseline = (int)typeof(AsyncOperationHandle<GameObject>)
                                    .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                    .GetValue(worldCoinLease);
            coordinator.worldPause = new GameObject("Offline gameplay pause context");
            coordinator.worldPause.SetActive(false);
            coordinator.worldPause.AddComponent<NetworkIdentity>();
            coordinator.worldPause.AddComponent<PauseStopController>();
            coordinator.worldPause.SetActive(true);
            yield return null;
            coordinator.Check(PauseStopController.instance && !PauseStopController.instance.isPaused,
                              "Integrated unpaused context missing");
            coordinator.worldDriver = player.GetComponent<InteractionDriver>();
            coordinator.Check(coordinator.worldDriver && (!coordinator.worldDriver || !coordinator.worldDriver.enabled) &&
                                  !coordinator.worldDriver.interactableOverride,
                              "Unowned integrated interaction driver");
            if (!player.equipmentSlot.characterBody)
                PortSession.Call(player.equipmentSlot, "Start");
            PortSession.Call(player.equipmentSlot, "UpdateInventory");
            coordinator.Check(player.equipmentSlot.equipmentIndex == EquipmentIndex.None && !player.equipmentSlot.enabled,
                              "Integrated equipment must start empty/ungranted");
            coordinator.PrepareWorldEquipment(player, cfg);
            coordinator.PrepareWorldItemDisplays(player, cfg);
            if (PortSession.DriverField(coordinator.worldDriver, "networkIdentity") == null)
                PortSession.Call(coordinator.worldDriver, "Awake");
            coordinator.worldStaging = new GameObject("Inactive offline content staging");
            coordinator.worldStaging.SetActive(false);
            var chestSource = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.chestAsset);
            coordinator.OwnChestAnimationSources(chestSource.GetComponent<ModelLocator>().modelTransform);
            var origin = player.characterMotor.Motor.TransientPosition;
            if (coordinator.r.liveCatalogs == null)
            {
                // Measured near-spawn layout; placement is an Android adapter, not original SceneDirector placement.
                var barrelOffsets = new[] { new Vector3(2, 0, 0), new Vector3(-2, 0, 0), new Vector3(0, 0, 3),
                                            new Vector3(4, 0, 3), new Vector3(-4, 0, 3), new Vector3(0, 0, -3) };
                foreach (var offset in barrelOffsets)
                {
                    var obj =
                        CreateWorldInteractable(coordinator.artifactBundle.LoadAsset<GameObject>(cfg.barrelAsset), origin + offset, false);
                    if (obj)
                        coordinator.worldBarrels.Add(obj.GetComponent<BarrelInteraction>());
                }
                foreach (var offset in new[] { new Vector3(5, 0, 0), new Vector3(-5, 0, 0), new Vector3(0, 0, 6), new Vector3(6, 0, 6) })
                {
                    var obj = CreateWorldInteractable(chestSource, origin + offset, true);
                    if (obj)
                        coordinator.worldChests.Add(obj.GetComponent<ChestBehavior>());
                }
                coordinator.AddEquipmentBarrel(cfg, origin);
                coordinator.AddWorldChestBreadth(cfg, origin);
                coordinator.Check(coordinator.worldBarrels.Count >= 3 && coordinator.worldChests.Count >= 2,
                                  "Integrated layout has insufficient walkable source interactables");
            }
            coordinator.r.world.barrels = coordinator.worldBarrels.Count;
            coordinator.r.world.chests = coordinator.worldChests.Count;
            coordinator.r.world.lootReady = true;
            worldInteraction = (actor, component, obj) =>
            {
                if (actor != coordinator.worldDriver.interactor)
                    return;
                if (coordinator.worldObjects.Contains(obj))
                    coordinator.r.world.target = obj.name;
            };
            GlobalEventManager.OnInteractionsGlobal += worldInteraction;
            coordinator.worldDriver.enabled = true;
            yield return null;
            PortSession.Call(coordinator.activeBodyClient, "Update");
            coordinator.r.world.interactionReady =
                coordinator.worldDriver.enabled &&
                ReferenceEquals(PortSession.DriverField(coordinator.worldDriver, "inputBank"), player.inputBank);
            coordinator.r.world.start = origin;
            coordinator.r.world.ready = !coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && coordinator.r.world.authority &&
                                        coordinator.r.world.lootReady && coordinator.r.world.interactionReady &&
                                        coordinator.rewardDirector && coordinator.rewardDirector.enabled;
            if (cfg.teleporterLoop)
            {
                if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                {
                    var nativeDirector = coordinator.PrepareNativeFirstStageDirectorContext(player, cfg);
                    while (nativeDirector.MoveNext())
                        yield return nativeDirector.Current;
                }
                IEnumerator objective;
                if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                {
                    var directorRoots = coordinator.stageGeometryScene.GetRootGameObjects()
                                            .Where(root => root.name == "Director" && root.scene == coordinator.stageGeometryScene)
                                            .ToArray();
                    coordinator.Check(directorRoots.Length == 1 && !directorRoots[0].activeSelf,
                                      "Native objective preparation requires the exact inactive source Director root");
                    coordinator.wholeSceneDirector = directorRoots[0].GetComponent<SceneDirector>();
                    coordinator.Check(coordinator.wholeSceneDirector && !coordinator.wholeSceneDirector.enabled,
                                      "Native objective preparation requires the exact disabled source SceneDirector");
                    objective = coordinator.PrepareNativeTeleporterWorld(cfg, coordinator.wholeSceneDirector);
                }
                else
                    objective = coordinator.PrepareTeleporterWorld(cfg);
                while (objective.MoveNext())
                    yield return objective.Current;
            }
            if (coordinator.r.liveCatalogs != null)
            {
                var visuals = coordinator.PrepareOriginalBodyVisualReferences();
                while (visuals.MoveNext())
                    yield return visuals.Current;
                var common = coordinator.PrepareOriginalGlobalCommonAssets();
                while (common.MoveNext())
                    yield return common.Current;
            }
            if (coordinator.r.liveCatalogs != null && cfg.teleporterLoop)
            {
                var transmutation = PrepareWorldTransmutation();
                while (transmutation.MoveNext())
                    yield return transmutation.Current;
            }
            coordinator.PrepareWorldItemBehaviors(cfg);
            coordinator.PrepareWorldCommerce(cfg, origin);
            var population = coordinator.PopulateWholeStage();
            while (population.MoveNext())
                yield return population.Current;
            var stage = coordinator.BeginOriginalStage();
            while (stage.MoveNext())
                yield return stage.Current;
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
            {
                var nativePopulation = coordinator.StartNativeWholeStagePopulation();
                while (nativePopulation.MoveNext())
                    yield return nativePopulation.Current;
            }
            coordinator.PlaceGoldshoresDiagnosticShrine();
            coordinator.PrepareRecoveredHud();
            coordinator.Check(coordinator.r.world.ready, "Integrated session setup incomplete");
            coordinator.r.phase = "integrated-world-playing";
            coordinator.Save();
        }
        readonly Dictionary<FieldInfo, object> priorWorldTransmutationFields = new Dictionary<FieldInfo, object>();
        Action<Run> worldTransmutationRunStart;
        bool ownsWorldTransmutation;
        public IEnumerator PrepareWorldTransmutation()
        {
            coordinator.Check(!ownsWorldTransmutation && Run.instance && PickupCatalog.pickupCount > 0,
                              "Original transmutation requires owned Run and pickup catalog");
            var type = typeof(PickupTransmutationManager);
            var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            var fields = type.GetFields(flags).Where(field => field.FieldType.IsArray && !field.IsInitOnly).ToArray();
            var groups = type.GetField("pickupGroups", flags);
            var groupMap = type.GetField("pickupGroupMap", flags);
            var available = type.GetField("availablePickupGroupMap", flags);
            coordinator.Check(groups != null && groupMap != null && available != null && fields.Length >= 20 &&
                                  ((Array)groups.GetValue(null)).Length == 0 && ((Array)groupMap.GetValue(null)).Length == 0 &&
                                  ((Array)available.GetValue(null)).Length == 0,
                              "Unowned original transmutation tables");
            foreach (var field in fields)
                priorWorldTransmutationFields.Add(field, field.GetValue(null));
            var callback = type.GetMethod("RebuildAvailablePickupGroups", BindingFlags.Static | BindingFlags.NonPublic);
            var runEvent = typeof(Run).GetField("onRunStartGlobal", flags);
            coordinator.Check(callback != null && runEvent != null, "Original transmutation Run callback missing");
            worldTransmutationRunStart = (Action<Run>)Delegate.CreateDelegate(typeof(Action<Run>), callback);
            var listeners = (Delegate)runEvent.GetValue(null);
            coordinator.Check(listeners == null || !listeners.GetInvocationList().Contains(worldTransmutationRunStart),
                              "Unowned original transmutation callback");
            ownsWorldTransmutation = true;
            coordinator.r.phase = "original-pickup-transmutation";
            coordinator.Save();
            var init = PickupTransmutationManager.Init();
            while (init.MoveNext())
                yield return init.Current;
            PortSession.StaticCall(type, "RebuildAvailablePickupGroups", Run.instance);
            var sourceGroups = (PickupIndex[][])groups.GetValue(null);
            var sourceMap = (PickupIndex[][])groupMap.GetValue(null);
            coordinator.Check(sourceGroups.Length == 16 && sourceMap.Length == PickupCatalog.pickupCount,
                              "Original transmutation group shape differs");
            int mapped = 0;
            for (int index = 0; index < PickupCatalog.pickupCount; index++)
            {
                var pickup = new PickupIndex(index);
                var original = PickupTransmutationManager.GetGroupFromPickupIndex(pickup);
                if (original == null || !original.Contains(pickup))
                    continue;
                var eligible = PickupTransmutationManager.GetAvailableGroupFromPickupIndex(pickup);
                coordinator.Check(eligible != null && eligible.SequenceEqual(original.Where(Run.instance.IsPickupAvailable)),
                                  "Original transmutation availability differs: " + index);
                mapped++;
            }
            coordinator.Check(
                mapped > 100 &&
                    ((Delegate)runEvent.GetValue(null)).GetInvocationList().Count(value => value.Equals(worldTransmutationRunStart)) == 1,
                "Original transmutation coverage or Run callback missing");
            coordinator.r.world.transmutationGroups = sourceGroups.Length;
            coordinator.r.world.transmutationMapped = mapped;
            coordinator.Save();
        }
        public void CleanupWorldTransmutation()
        {
            if (!ownsWorldTransmutation)
                return;
            Run.onRunStartGlobal -= worldTransmutationRunStart;
            foreach (var pair in priorWorldTransmutationFields)
                pair.Key.SetValue(null, pair.Value);
            priorWorldTransmutationFields.Clear();
            ownsWorldTransmutation = false;
            worldTransmutationRunStart = null;
            var flags = BindingFlags.Static | BindingFlags.NonPublic;
            var type = typeof(PickupTransmutationManager);
            coordinator.r.world.transmutationCleaned = ((Array)type.GetField("pickupGroups", flags).GetValue(null)).Length == 0 &&
                                                       ((Array)type.GetField("availablePickupGroupMap", flags).GetValue(null)).Length == 0;
            coordinator.Check(coordinator.r.world.transmutationCleaned, "Original transmutation tables outlived the pickup catalog");
        }
        public void PrepareUnavailableWorldPresentation(CharacterBody player)
        {
            // Optional presentation requires stock application/native audio/item-display contexts.
            // Remove only these measured original listeners; all original XP/level/inventory events remain.
            var flags = BindingFlags.Static | BindingFlags.NonPublic;
            var type = typeof(LevelUpEffectManager);
            unavailableTeamLevelSound =
                (Action<TeamIndex>)Delegate.CreateDelegate(typeof(Action<TeamIndex>), type.GetMethod("OnTeamLevelUp", flags));
            unavailableAmbientSound =
                (Action<Run>)Delegate.CreateDelegate(typeof(Action<Run>), type.GetMethod("OnRunAmbientLevelUp", flags));
            unavailableLevelEffect =
                (Action<CharacterBody>)Delegate.CreateDelegate(typeof(Action<CharacterBody>), type.GetMethod("OnCharacterLevelUp", flags));
            unavailableItemHighlight = (Action<ItemIndex>)Delegate.CreateDelegate(
                typeof(Action<ItemIndex>), player.master,
                typeof(CharacterMaster).GetMethod("OnItemAddedClient", BindingFlags.Instance | BindingFlags.NonPublic));
            var teamListeners = (Delegate)PortSession.RewardField(typeof(GlobalEventManager), "onTeamLevelUp").GetValue(null);
            var ambientListeners = (Delegate)PortSession.RewardField(typeof(Run), "onRunAmbientLevelUp").GetValue(null);
            var effectListeners = (Delegate)PortSession.RewardField(typeof(GlobalEventManager), "onCharacterLevelUp").GetValue(null);
            var highlightListeners =
                (Delegate) typeof(Inventory)
                    .GetField("onItemAddedClient", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                    .GetValue(player.inventory);
            coordinator.Check(teamListeners != null && ambientListeners != null && effectListeners != null && highlightListeners != null &&
                                  teamListeners.GetInvocationList().Count(x => x.Equals(unavailableTeamLevelSound)) == 1 &&
                                  ambientListeners.GetInvocationList().Count(x => x.Equals(unavailableAmbientSound)) == 1 &&
                                  effectListeners.GetInvocationList().Count(x => x.Equals(unavailableLevelEffect)) == 1 &&
                                  highlightListeners.GetInvocationList().Count(x => x.Equals(unavailableItemHighlight)) == 1,
                              "Original optional presentation listener ownership changed");
            GlobalEventManager.onTeamLevelUp -= unavailableTeamLevelSound;
            Run.onRunAmbientLevelUp -= unavailableAmbientSound;
            GlobalEventManager.onCharacterLevelUp -= unavailableLevelEffect;
            player.inventory.onItemAddedClient -= unavailableItemHighlight;
            ownsWorldPresentation = true;
            coordinator.r.world.feedbackCapability +=
                " Original level-up sound/effect and item-display highlight unavailable; original levels/stats/grants retained.";
        }
        public void PrepareWorldMessages()
        {
            coordinator.Check(!coordinator.activeBodyClient.handlers.ContainsKey(52) &&
                                  !coordinator.activeBodyClient.handlers.ContainsKey(55) &&
                                  !coordinator.activeBodyClient.handlers.ContainsKey(57) &&
                                  !coordinator.activeBodyClient.handlers.ContainsKey(68) && !NetworkServer.handlers.ContainsKey(68),
                              "Unowned integrated presentation/teleport handlers");
            worldVfxOption =
                (RoR2.ConVar.IntConVar)PortSession.RewardField(typeof(VFXBudget), "mediumPriorityCostThreshold").GetValue(null);
            priorWorldVfx = worldVfxOption.GetString();
            worldVfxOption.AttemptSetString(worldVfxOption.defaultValue);
            priorWorldXp = SettingsConVars.cvExpAndMoneyEffects.GetString();
            SettingsConVars.cvExpAndMoneyEffects.AttemptSetString("0");
            var effects = (NetworkMessageDelegate)Delegate.CreateDelegate(
                typeof(NetworkMessageDelegate),
                typeof(EffectManager).GetMethod("HandleEffectClient", BindingFlags.Static | BindingFlags.NonPublic));
            var xp = (NetworkMessageDelegate)Delegate.CreateDelegate(
                typeof(NetworkMessageDelegate),
                typeof(ExperienceManager).GetMethod("HandleCreateExpEffect", BindingFlags.Static | BindingFlags.NonPublic));
            var teleport = (NetworkMessageDelegate)Delegate.CreateDelegate(
                typeof(NetworkMessageDelegate),
                typeof(TeleportHelper).GetMethod("HandleTeleport", BindingFlags.Static | BindingFlags.NonPublic));
            ownsWorldTeleportHandler = true;
            coordinator.activeBodyClient.RegisterHandler(68, teleport);
            NetworkServer.RegisterHandler(68, teleport);
            if (WwiseIntegrationManager.noAudio)
            {
                var effectPacketType = typeof(EffectManager).GetNestedType("EffectMessage", BindingFlags.NonPublic);
                coordinator.Check(effectPacketType != null && typeof(MessageBase).IsAssignableFrom(effectPacketType) &&
                                      effectPacketType.GetField("effectIndex") != null && effectPacketType.GetField("effectData") != null,
                                  "Original effect packet contract changed");
                coordinator.activeBodyClient.RegisterHandler(52, msg =>
                                                                 {
                                                                     coordinator.r.world.coinMessages++;
                                                                     ObserveUnavailableEffectSound(msg, effectPacketType);
                                                                 });
                coordinator.r.world.offlineEffectSoundBoundary = true;
            }
            else
                coordinator.activeBodyClient.RegisterHandler(52, msg =>
                                                                 {
                                                                     coordinator.r.world.coinMessages++;
                                                                     effects(msg);
                                                                 });
            coordinator.activeBodyClient.RegisterHandler(55, msg =>
                                                             {
                                                                 coordinator.r.world.xpMessages++;
                                                                 xp(msg);
                                                             });
            // Decode with the original MessageBase. Do not call the original native-audio UI handler
            // or fabricate its completion/profile discovery. Server grant, quantity and identity stay original.
            var type = typeof(GenericPickupController).GetNestedType("PickupMessage", BindingFlags.NonPublic);
            coordinator.Check(type != null && typeof(MessageBase).IsAssignableFrom(type), "Original pickup message contract missing");
            coordinator.activeBodyClient.RegisterHandler(
                57, msg =>
                    {
                        var message = (MessageBase)Activator.CreateInstance(type, true);
                        msg.ReadMessage(message);
                        var master = (GameObject)type.GetField("masterGameObject").GetValue(message);
                        var pickup = (UniquePickup)type.GetField("pickupState").GetValue(message);
                        var quantity = (uint)type.GetField("pickupQuantity").GetValue(message);
                        var characterMaster = master ? master.GetComponent<CharacterMaster>() : null;
                        var definition = PickupCatalog.GetPickupDef(pickup.pickupIndex);
                        var item = ItemCatalog.GetItemDef(definition != null ? definition.itemIndex : ItemIndex.None);
                        var observation =
                            new WorldPickupMessageObservation { at = coordinator.r.world.seconds,
                                                                resolvedMaster = characterMaster,
                                                                playerMaster = characterMaster && coordinator.worldPlayer &&
                                                                               characterMaster == coordinator.worldPlayer.master,
                                                                knownPickup = definition != null,
                                                                masterId = characterMaster ? characterMaster.netId.Value : 0,
                                                                quantity = quantity,
                                                                pickupIndex = pickup.pickupIndex.value,
                                                                item = item                 ? item.name
                                                                       : definition != null ? definition.internalName
                                                                                            : "unavailable" };
                        if (coordinator.r.world.pickupMessageObservations.Count == 64)
                            coordinator.r.world.pickupMessageObservations.RemoveAt(0);
                        coordinator.r.world.pickupMessageObservations.Add(observation);
                        // Original notification handling tolerates missing masters and zero effective stacks.
                        // Record those packets without claiming a connected player grant.
                        if (!characterMaster)
                            coordinator.r.world.unresolvedPickupMessages++;
                        else if (!observation.playerMaster)
                            coordinator.r.world.otherPickupMessages++;
                        else if (quantity == 0)
                            coordinator.r.world.zeroCountPickupMessages++;
                        if (observation.playerMaster && definition != null && quantity > 0)
                        {
                            coordinator.r.world.pickupMessages++;
                            coordinator.r.world.lastPickup = observation.item + " x" + quantity;
                            if (coordinator.recoveredHud)
                                coordinator.recoveredHud.QueuePickup(characterMaster, pickup);
                        }
                        coordinator.Save();
                    });
            RegisterMissingOriginalWorldMessages();
            ObserveWorldHandlers(false);
            ObserveWorldHandlers(true);
        }
        public void RegisterMissingOriginalWorldMessages()
        {
            // Stock NetworkManagerSystem registers these searched source methods during
            // OnStartServer/OnStartClient. The owned offline loopback has neither manager.
            SearchableAttribute.ScanAssembly(typeof(CharacterBody).Assembly);
            var attributes = SearchableAttribute.GetInstances<NetworkMessageHandlerAttribute>();
            coordinator.Check(attributes != null, "Original network-message attributes were not discovered");
            var source = attributes.Cast<NetworkMessageHandlerAttribute>().Where(x => x.server || x.client).ToArray();
            coordinator.Check(source.All(x => x.target is MethodInfo && ((MethodInfo)x.target).IsStatic),
                              "Original network-message method contract changed");
            coordinator.Check(source.Where(x => x.server).Select(x => x.msgType).Distinct().Count() == source.Count(x => x.server) &&
                                  source.Where(x => x.client).Select(x => x.msgType).Distinct().Count() == source.Count(x => x.client),
                              "Original network-message IDs are ambiguous");
            foreach (var attribute in source)
            {
                var handler = (NetworkMessageDelegate)Delegate.CreateDelegate(typeof(NetworkMessageDelegate), (MethodInfo)attribute.target);
                if (attribute.server && !NetworkServer.handlers.ContainsKey(attribute.msgType))
                {
                    NetworkServer.RegisterHandler(attribute.msgType, handler);
                    worldSourceServerHandlerIds.Add(attribute.msgType);
                }
                if (attribute.client && !coordinator.activeBodyClient.handlers.ContainsKey(attribute.msgType))
                {
                    // The shipped Chat receiver asks the platform user manager whether text
                    // chat is allowed. An absent offline user cannot answer that question.
                    if (attribute.msgType == 59 && PlatformSystems.userManager == null)
                    {
                        handler = ObserveUnavailablePlatformChat;
                        coordinator.r.world.offlineChatBoundary = true;
                    }
                    // The shipped point-sound receiver maps the index to a Wwise event, then
                    // emits it. Decode the original packet when the audio engine is absent.
                    if (attribute.msgType == 72 && WwiseIntegrationManager.noAudio)
                    {
                        var definitions = WholeCatalogComposed.DefinitionFamily(Array.Empty<NetworkSoundEventDef>());
                        coordinator.Check(definitions != null && definitions.Length > 0 && definitions.All(def => def),
                                          "Original network-sound definitions are unavailable");
                        worldOfflineNetworkSoundDefs = definitions.OrderBy(def => def.name, StringComparer.Ordinal).ToArray();
                        handler = ObserveUnavailablePointSound;
                        coordinator.r.world.offlinePointSoundBoundary = true;
                    }
                    coordinator.activeBodyClient.RegisterHandler(attribute.msgType, handler);
                    coordinator.worldSourceClientHandlerIds.Add(attribute.msgType);
                }
            }
            NetworkMessageDelegate turret;
            coordinator.r.world.sourceConstructTurretHandler = NetworkServer.handlers.TryGetValue(UmsgType.ConstructTurret, out turret) &&
                                                               turret.Method.DeclaringType == typeof(CharacterBody) &&
                                                               turret.Method.Name == "HandleConstructTurret";
            coordinator.r.world.sourceServerMessageHandlers = worldSourceServerHandlerIds.Count;
            coordinator.r.world.sourceClientMessageHandlers = coordinator.worldSourceClientHandlerIds.Count;
            coordinator.Check(coordinator.r.world.sourceConstructTurretHandler && coordinator.r.world.sourceServerMessageHandlers > 0,
                              "Original local server gameplay messages did not register");
        }
        public void ObserveUnavailablePlatformChat(NetworkMessage message)
        {
            var native = ChatMessageBase.Instantiate(message.reader.ReadByte());
            if (native == null)
                return;
            native.Deserialize(message.reader);
            coordinator.r.world.offlineChatPackets++;
            var subject = native as Chat.SubjectFormatChatMessage;
            var simple = native as Chat.SimpleChatMessage;
            coordinator.r.world.offlineChatLastToken =
                subject != null ? subject.baseToken : (simple != null ? simple.baseToken : native.GetType().Name);
            if (coordinator.r.commerce != null)
            {
                coordinator.r.commerce.messages++;
                coordinator.r.commerce.lastMessage = coordinator.r.world.offlineChatLastToken;
            }
        }
        public void ObserveUnavailablePointSound(NetworkMessage message)
        {
            var index = message.reader.ReadNetworkSoundEventIndex();
            var position = message.reader.ReadVector3();
            coordinator.Check(worldOfflineNetworkSoundDefs != null, "Owned network-sound decoder was not prepared");
            coordinator.Check(index == NetworkSoundEventIndex.Invalid ||
                                  (int)index >= 0 && (int)index < worldOfflineNetworkSoundDefs.Length,
                              "Original point-sound index is outside the source catalog");
            coordinator.r.world.offlinePointSoundPackets++;
            coordinator.r.world.offlinePointSoundLastEvent =
                index == NetworkSoundEventIndex.Invalid ? "invalid" : worldOfflineNetworkSoundDefs[(int)index].eventName;
            coordinator.r.world.offlinePointSoundLastPosition = position;
        }
        public void ObserveUnavailableEffectSound(NetworkMessage message, Type packetType)
        {
            // The shipped client handler decodes this MessageBase and calls SpawnEffect.
            // Only its Wwise event is unavailable: preserve the effect index/data and
            // original visual spawn, while recording the removed sound request.
            var packet = (MessageBase)Activator.CreateInstance(packetType, true);
            message.ReadMessage(packet);
            var index = (EffectIndex)packetType.GetField("effectIndex").GetValue(packet);
            var data = (EffectData)packetType.GetField("effectData").GetValue(packet);
            coordinator.Check(data != null, "Original effect packet data missing");
            var sound = data.networkSoundEventIndex;
            if (sound != NetworkSoundEventIndex.Invalid)
            {
                coordinator.Check(worldOfflineNetworkSoundDefs != null && (int)sound >= 0 &&
                                      (int)sound < worldOfflineNetworkSoundDefs.Length,
                                  "Original effect sound index is outside the source catalog");
                coordinator.r.world.offlineEffectSoundPackets++;
                coordinator.r.world.offlineEffectSoundLastEvent = worldOfflineNetworkSoundDefs[(int)sound].eventName;
                data.networkSoundEventIndex = NetworkSoundEventIndex.Invalid;
            }
            EffectManager.SpawnEffect(index, data, false);
        }
        public void ObserveWorldHandlers(bool server)
        {
            var handlers = server ? NetworkServer.handlers : coordinator.activeBodyClient.handlers;
            var originals = server ? worldServerHandlers : worldClientHandlers;
            var observers = server ? worldServerObservers : worldClientObservers;
            coordinator.Check(originals.Count == 0 && observers.Count == 0, "Unowned integrated handler observation");
            foreach (var pair in handlers.ToArray())
            {
                short id = pair.Key;
                var original = pair.Value;
                NetworkMessageDelegate observer = msg =>
                {
                    try
                    {
                        original(msg);
                    }
                    catch (Exception error)
                    {
                        var failure =
                            new WorldMessageFailure { at = coordinator.r.world.seconds, id = id, side = server ? "server" : "client",
                                                      handler = original.Method.DeclaringType.FullName + "." + original.Method.Name,
                                                      error = error.GetBaseException().ToString() };
                        coordinator.r.world.messageFailureCount++;
                        if (coordinator.r.world.messageFailures.Count < 16)
                            coordinator.r.world.messageFailures.Add(failure);
                        coordinator.Save();
                        Debug.LogError("Integrated message failure " + failure.side + "/" + id + ": " + failure.error);
                        throw;
                    }
                };
                originals.Add(id, original);
                observers.Add(id, observer);
                if (server)
                    NetworkServer.RegisterHandler(id, observer);
                else
                    coordinator.activeBodyClient.RegisterHandler(id, observer);
            }
        }
        public void RestoreWorldHandlers(bool server)
        {
            var originals = server ? worldServerHandlers : worldClientHandlers;
            var observers = server ? worldServerObservers : worldClientObservers;
            if ((server && NetworkServer.active) || (!server && coordinator.activeBodyClient != null))
            {
                var handlers = server ? NetworkServer.handlers : coordinator.activeBodyClient.handlers;
                foreach (var pair in originals)
                {
                    NetworkMessageDelegate current;
                    if (handlers.TryGetValue(pair.Key, out current) && current == observers[pair.Key])
                    {
                        if (server)
                            NetworkServer.RegisterHandler(pair.Key, pair.Value);
                        else
                            coordinator.activeBodyClient.RegisterHandler(pair.Key, pair.Value);
                    }
                }
            }
            originals.Clear();
            observers.Clear();
        }
        public GameObject CreateWorldInteractable(GameObject source, Vector3 candidate, bool chest, PickupDropTable dropOverride = null)
        {
            RaycastHit hit;
            if (!Physics.Raycast(candidate + Vector3.up * 20, Vector3.down, out hit, 50, LayerIndex.world.mask,
                                 QueryTriggerInteraction.Ignore) ||
                hit.normal.y < .9f || Mathf.Abs(hit.point.y - coordinator.worldPlayer.characterMotor.Motor.TransientPosition.y) > 2)
                return null;
            coordinator.Check(source && source.GetComponentsInChildren<Component>(true).All(x => x),
                              "Integrated source interactable reference missing");
            var obj = PortSession.Instantiate(source, coordinator.worldStaging.transform);
            obj.name = source.name;
            coordinator.worldObjects.Add(obj);
            var allowed =
                new[] { typeof(NetworkIdentity), typeof(NetworkStateMachine), typeof(EntityStateMachine),      typeof(BarrelInteraction),
                        typeof(ChestBehavior),   typeof(PurchaseInteraction), typeof(DelusionChestController), typeof(ModelLocator),
                        typeof(EntityLocator),   typeof(ChildLocator),        typeof(PingInfoProvider),        typeof(AnimationEvents) };
            foreach (var behaviour in obj.GetComponentsInChildren<MonoBehaviour>(true))
                behaviour.enabled = allowed.Contains(behaviour.GetType());
            var sound = obj.GetComponent<SfxLocator>();
            if (sound)
                PortSession.DestroyImmediate(sound);
            foreach (var animator in obj.GetComponentsInChildren<Animator>(true))
            {
                animator.enabled = chest;
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            }
            var model = obj.GetComponent<ModelLocator>().modelTransform;
            coordinator.worldModels.Add(model);
            PresentWorldModel(model, true);
            foreach (var collider in obj.GetComponentsInChildren<Collider>(true))
                collider.enabled = true;
            if (dropOverride)
                obj.GetComponent<ChestBehavior>().dropTable = dropOverride;
            obj.transform.position = hit.point + Vector3.up * .4f;
            obj.transform.SetParent(null, true);
            obj.SetActive(true);
            NetworkServer.Spawn(obj);
            if (!chest)
                coordinator.worldBarrelConsumers++;
            return obj;
        }
        public void PresentWorldModel(Transform model, bool sourceView, bool optionalObjectiveSlots = false)
        {
            var shader = Resources.Load<Shader>("StageSurfacePreview");
            coordinator.Check(shader && shader.isSupported, "Integrated preview material unavailable");
            foreach (var renderer in model.GetComponentsInChildren<Renderer>(true))
            {
                if (!coordinator.worldPresented.Add(renderer.GetInstanceID()))
                    continue;
                renderer.sharedMaterials =
                    renderer.sharedMaterials
                        .Select(original =>
                                {
                                    if (!original && optionalObjectiveSlots && renderer is ParticleSystemRenderer)
                                    {
                                        coordinator.r.objective.unusedParticleMaterialSlots++;
                                        return null;
                                    }
                                    coordinator.Check(original || optionalObjectiveSlots, "Integrated source material absent");
                                    var material = original ? new Material(original) : new Material(shader);
                                    material.shader = shader;
                                    if (original)
                                        AndroidMaterialPresentation.Apply(original, material);
                                    if (!original)
                                    {
                                        coordinator.r.objective.previewMaterialSlots++;
                                        material.SetColor("_Color", new Color(.3f, .65f, .9f, 1));
                                    }
                                    coordinator.worldMaterials.Add(material);
                                    return material;
                                })
                        .ToArray();
                if (sourceView && renderer is SkinnedMeshRenderer)
                {
                    var skin = (SkinnedMeshRenderer)renderer;
                    var view = new GameObject("Offline source renderer view");
                    view.layer = 30;
                    view.transform.SetParent(renderer.transform, false);
                    var copy = view.AddComponent<SkinnedMeshRenderer>();
                    copy.sharedMesh = skin.sharedMesh;
                    copy.sharedMaterials = skin.sharedMaterials;
                    copy.bones = skin.bones;
                    copy.rootBone = skin.rootBone;
                    copy.localBounds = skin.localBounds;
                    copy.updateWhenOffscreen = true;
                    coordinator.worldPresented.Add(copy.GetInstanceID());
                }
                else if (!sourceView && !(optionalObjectiveSlots && renderer.GetComponent<Collider>()))
                    renderer.gameObject.layer = 30;
            }
        }
        public void ObserveIntegratedWorld(CharacterBody player, float elapsed)
        {
            var cameraCreation = originalAudioCameraContextCreationSchedule.Begin(
                true, player, coordinator.worldPlayer, originalAudioCameraContextAttempted);
            if (cameraCreation == OriginalAudioCameraContextCreationSchedule.BeginResult.Begin)
                PrepareOriginalAudioCameraContext(player, createAtIntegratedWorldUpdate: true);
            else if (cameraCreation == OriginalAudioCameraContextCreationSchedule.BeginResult.Refused)
            {
                originalAudioCameraContextAttempted = true;
                var report = coordinator.r?.world;
                if (report != null)
                {
                    report.originalAudioCameraContextState = "refused_closed: world_player_lifecycle_mismatch";
                    report.originalAudioCameraContextAdmissionFailure = "world_player_lifecycle_mismatch";
                }
            }
            else
                ObserveOriginalAudioCameraContext();
            coordinator.ObserveSourceAnimationEvents(player, elapsed);
            if (elapsed >= nextSurvivorSkillSample)
            {
                nextSurvivorSkillSample = elapsed + 1;
                survivorSkills?.Sample();
                engiNativeOutputs?.Sample();
            }
            // The observer retains its one-second baseline internally; calling
            // the owner each world update only services explicitly armed windows.
            survivorCombatOutputs?.Sample(elapsed);
            long performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            if (worldClientUpdate == null)
                worldClientUpdate = (Action)Delegate.CreateDelegate(
                    typeof(Action), coordinator.activeBodyClient,
                    coordinator.activeBodyClient.GetType().GetMethod("Update", BindingFlags.NonPublic | BindingFlags.Instance));
            worldClientUpdate();
            coordinator.r.performance.clientUpdateMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.Check(coordinator.activeBodyClient.isConnected && player.networkIdentity.hasAuthority &&
                                  player.networkIdentity.clientAuthorityOwner == coordinator.activeBodyOwner &&
                                  LocalUserManager.readOnlyLocalUsersList.Count == 0 &&
                                  !player.master.playerCharacterMasterController.networkUser,
                              "Integrated authority/unavailable-user scope changed");
            long objectiveStart = performancePart;
            coordinator.ObserveTeleporterWorld();
            coordinator.r.performance.teleporterMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveMoonMission();
            coordinator.ObserveGoldshoresMission();
            coordinator.r.performance.moonMs += PortSession.PerformanceMs(performancePart);
            coordinator.r.performance.objectiveMs += PortSession.PerformanceMs(objectiveStart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            var world = coordinator.r.world;
            world.frames++;
            world.seconds = elapsed;
            world.position = player.characterMotor.Motor.TransientPosition;
            world.distance = Vector3.Distance(world.start, world.position);
            world.health = player.healthComponent.health;
            world.maxHealth = player.maxHealth;
            world.level = player.level;
            world.attackSpeed = player.attackSpeed;
            world.money = player.master.money;
            world.experience = TeamManager.instance.GetTeamExperience(TeamIndex.Player);
            world.kills = player.killCountServer;
            world.difficulty = Run.instance.difficultyCoefficient;
            if (!fireTrailDiagnosisRecorded && !string.IsNullOrEmpty(coordinator.r.runSeedOverride) && Time.frameCount % 30 == 0 &&
                NetworkServer.objects.Values.Any(identity =>
                                                 {
                                                     var body = identity ? identity.GetComponent<CharacterBody>() : null;
                                                     return body && body.HasBuff(RoR2Content.Buffs.AffixRed);
                                                 }))
            {
                fireTrailDiagnosisRecorded = true;
                try
                {
                    world.fireTrailDiagnostic = WholeCatalogComposed.DiagnoseFireTrail();
                }
                catch (Exception error)
                {
                    world.fireTrailDiagnostic = error.GetBaseException().ToString();
                }
                coordinator.Save();
            }
            var motor = player.characterMotor;
            var grounding = motor.Motor.GroundingStatus;
            world.motorGrounded = motor.isGrounded;
            world.motorStable = grounding.IsStableOnGround;
            world.motorGroundPoint = grounding.GroundPoint;
            world.motorGroundCollider = grounding.GroundCollider ? PortSession.StageObjectPath(grounding.GroundCollider.transform) : "";
            world.motorVelocity = motor.velocity;
            world.motorJumpCount = motor.jumpCount;
            world.motorMaxJumpCount = player.maxJumpCount;
            world.jumpDown = player.inputBank.jump.down;
            world.jumpPressed = player.inputBank.jump.justPressed;
            world.jumpClaimed = player.inputBank.jump.hasPressBeenClaimed;
            var bodyMachine = player.GetComponents<EntityStateMachine>().FirstOrDefault(x => x.customName == "Body");
            world.movementState = bodyMachine && bodyMachine.state != null ? bodyMachine.state.GetType().FullName : "unavailable";
            world.syringe = player.inventory.GetItemCountPermanent(RoR2Content.Items.Syringe);
            world.lightning = player.inventory.GetItemCountPermanent(RoR2Content.Items.ChainLightning);
            world.glasses = player.inventory.GetItemCountPermanent(RoR2Content.Items.CritGlasses);
            world.slug = player.inventory.GetItemCountPermanent(RoR2Content.Items.HealWhileSafe);
            world.crit = player.crit;
            world.regen = player.regen;
            world.moveSpeed = player.moveSpeed;
            long lootStart = performancePart;
            world.shield = player.healthComponent.shield;
            world.maxShield = player.maxShield;
            world.armor = player.armor;
            for (int i = 0; i < coordinator.worldLootDefinitions.Length; i++)
                world.itemStacks[i].count = player.inventory.GetItemCountPermanent(coordinator.worldLootDefinitions[i]);
            if (Time.frameCount % 6 == 0)
                ObserveWorldLootSupport(player);
            // Known stake identities receive a cheap finite/stuck check every frame;
            // the diagnostic owner scans the server registry only at its own 6-frame cadence.
            ObserveLightningStakes();
            coordinator.r.performance.lootSupportMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveWorldEquipment();
            coordinator.r.performance.equipmentMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveWorldItemBehaviors();
            coordinator.r.performance.itemBehaviorsMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveWorldHealingItems();
            coordinator.r.performance.healingMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveStageBossContent();
            coordinator.r.performance.bossMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveWorldLegendaryItems();
            coordinator.r.performance.legendaryMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveWorldItemDisplays();
            coordinator.r.performance.itemDisplayMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.r.performance.lootMs += PortSession.PerformanceMs(lootStart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            if (world.lootDomain > 4)
            {
                world.drink = player.inventory.GetItemCountPermanent(RoR2Content.Items.SprintBonus);
                world.steak = player.inventory.GetItemCountPermanent(RoR2Content.Items.FlatHealth);
            }
            world.openedBarrels = coordinator.worldBarrels.Count(x => x && x.Networkopened);
            world.openedChests = coordinator.worldChests.Count(x => x && x.NetworkisChestOpened);
            world.liveEnemies =
                coordinator.directorActors.Count(x => x.body && x.body.healthComponent.alive && x.master.teamIndex != TeamIndex.Player);
            coordinator.ObserveWorldChestBreadth();
            // These are live-world observations. The broad Resources API also walks the
            // complete loaded catalog and its inactive source prefabs every rendered frame.
            if (elapsed >= nextWorldPickupSnapshot)
            {
                // The snapshot is diagnostic state; native pickup creation, collision and
                // interaction still run every frame through their original callbacks.
                nextWorldPickupSnapshot = elapsed + 1f;
                var identities = NetworkServer.objects.Values.Where(x => x && x.gameObject.scene.IsValid()).ToArray();
                var registeredPickups = identities.Select(x => x.GetComponent<GenericPickupController>()).Where(x => x).ToArray();
                var registeredDroplets = identities.Select(x => x.GetComponent<PickupDropletController>()).Where(x => x).ToArray();
                var currentStage = coordinator.r.stageProgress == null ? "" : coordinator.r.stageProgress.current;
                if (currentStage != worldPickupRegistryStage && elapsed - coordinator.stageEnteredAt > 5)
                {
                    var allPickups =
                        UnityEngine.Object.FindObjectsOfType<GenericPickupController>().Where(x => x.gameObject.scene.IsValid()).ToArray();
                    var allDroplets =
                        UnityEngine.Object.FindObjectsOfType<PickupDropletController>().Where(x => x.gameObject.scene.IsValid()).ToArray();
                    worldPickupRegistryFallback =
                        allPickups.Length != registeredPickups.Length || allDroplets.Length != registeredDroplets.Length ||
                        allPickups.Any(x => !registeredPickups.Contains(x)) || allDroplets.Any(x => !registeredDroplets.Contains(x));
                    worldPickupRegistryStage = currentStage;
                    world.pickupRegistryStatus = worldPickupRegistryFallback
                                                     ? "Original network registry incomplete; broad observation retained"
                                                     : "Original network registry matches live pickups and droplets";
                }
                var pickups =
                    worldPickupRegistryFallback
                        ? UnityEngine.Object.FindObjectsOfType<GenericPickupController>().Where(x => x.gameObject.scene.IsValid()).ToArray()
                        : registeredPickups;
                world.pickups = pickups.Length;
                world.droplets =
                    worldPickupRegistryFallback
                        ? UnityEngine.Object.FindObjectsOfType<PickupDropletController>().Count(x => x.gameObject.scene.IsValid())
                        : registeredDroplets.Length;
                var interactor = player.GetComponent<Interactor>();
                world.interactionDistance = interactor.maxInteractionDistance;
                world.pickupObservations =
                    pickups
                        .Select(x =>
                                {
                                    var collider = x.GetComponentsInChildren<Collider>(true).FirstOrDefault(
                                        c => c.enabled && (LayerIndex.CommonMasks.interactable.value & (1 << c.gameObject.layer)) != 0);
                                    var aim = collider ? collider.bounds.center : x.transform.position;
                                    var def = PickupCatalog.GetPickupDef(x.pickup.pickupIndex);
                                    return new WorldPickupObservation { item = def == null ? "invalid" : def.internalName,
                                                                        interactability = x.GetInteractability(interactor).ToString(),
                                                                        position = x.transform.position,
                                                                        aimTarget = aim,
                                                                        aimDistance = Vector3.Distance(player.inputBank.aimOrigin, aim),
                                                                        selected =
                                                                            coordinator.worldDriver.currentInteractable == x.gameObject,
                                                                        collider = collider,
                                                                        interactableLayer = collider };
                                })
                        .ToArray();
                foreach (var pickup in pickups)
                {
                    if (!pickup.pickupDisplay)
                        continue;
                    var model = (GameObject) typeof(PickupDisplay)
                                    .GetField("modelObject", BindingFlags.Instance | BindingFlags.NonPublic)
                                    .GetValue(pickup.pickupDisplay);
                    if (model)
                        PresentWorldModel(model.transform, false);
                }
            }
            world.secondary = coordinator.r.combat.secondaryEntries;
            world.roll = coordinator.r.combat.utilityEntries;
            world.barrage = coordinator.r.combat.specialEntries;
            coordinator.r.performance.pickupMs += PortSession.PerformanceMs(performancePart);
            performancePart = System.Diagnostics.Stopwatch.GetTimestamp();
            world.target = coordinator.worldDriver.currentInteractable ? coordinator.worldDriver.currentInteractable.name : "";
            coordinator.ObserveWorldCommerce();
            coordinator.ObserveRecoveredHud();
            coordinator.r.performance.commerceHudMs += PortSession.PerformanceMs(performancePart);
        }
        SirenEggDiagnosticInput EnsureSirenEggInputOwner()
        {
            if (sirenEggDiagnosticInput == null && coordinator.SirenEggInputSelected && coordinator.r.sirenEggInput != null)
                sirenEggDiagnosticInput =
                    new SirenEggDiagnosticInput(new IntegratedWorldSirenContext(coordinator, this), coordinator.r.sirenEggInput);
            return sirenEggDiagnosticInput;
        }
        public void PrepareSirenEggDiagnosticInputFrame(CharacterBody player, NovaInputBridge bridge)
        {
            bool selected = coordinator.SirenEggInputSelected && coordinator.r.sirenEggInput != null;
            if (selected)
                EnsureSirenEggInputOwner();
            SirenEggDiagnosticInput.PrepareProducerFrameForSelection(selected, sirenEggDiagnosticInput, bridge);
        }
        public void ApplySirenEggDiagnosticInput(CharacterBody player, NovaInputBridge bridge)
        {
            bool selected = coordinator.SirenEggInputSelected && coordinator.r.sirenEggInput != null;
            var owner = selected ? EnsureSirenEggInputOwner() : sirenEggDiagnosticInput;
            owner?.Apply(player, bridge, true);
        }
        sealed class IntegratedWorldSirenContext : ISirenEggDiagnosticContext
        {
            readonly PortSession coordinator;
            readonly IntegratedWorldSession session;
            public IntegratedWorldSirenContext(PortSession owner, IntegratedWorldSession session)
            {
                coordinator = owner;
                this.session = session;
            }
            public bool Selected => coordinator.SirenEggInputSelected;
            public bool Assisted => coordinator.IsRunAssisted();
            public bool ManualTakeover => coordinator.worldManualTakeover;
            public bool SourceSceneActive => coordinator.SirenDiagnosticSceneActive;
            public bool SourceEncounterAttached => coordinator.SirenDiagnosticOwnerAttached;
            public bool SourceListenerActive => coordinator.SirenDiagnosticListenerActive;
            public bool NativeEncounterStarted => coordinator.SirenNativeEncounterStarted;
            public bool StageTransporting => coordinator.SirenDiagnosticStageTransporting;
            public bool FirstFailure => !string.IsNullOrEmpty(coordinator.r.firstFailure) || !string.IsNullOrEmpty(coordinator.r.error) ||
                                        coordinator.r.stageProgress != null && !string.IsNullOrEmpty(coordinator.r.stageProgress.error);
            public int StageSceneHandle => coordinator.SirenDiagnosticSceneHandle;
            public float StageElapsed
            {
                get {
                    float stageElapsed;
                    return SirenNativeEncounterContinuationContract.TryGetWorldStageElapsedSeconds(
                               coordinator.r.world == null ? float.NaN : coordinator.r.world.seconds, coordinator.stageEnteredAt,
                               out stageElapsed)
                               ? stageElapsed
                               : float.NaN;
                }
            }
            public float NavigationObjectiveStalledSeconds =>
                coordinator.r.world == null ? float.NaN : coordinator.r.world.navigationObjectiveStalledSeconds;
            public bool TryReadNavigationTrigger(CharacterBody player, CharacterBody egg, out float eggDistance,
                                                 out float trackerMaximumDistance)
            {
                eggDistance = trackerMaximumDistance = float.NaN;
                if (!player || !egg || !player.inputBank)
                    return false;
                var tracker = player.GetComponent<HuntressTracker>();
                if (!tracker || !tracker.isActiveAndEnabled)
                    return false;
                // Match HuntressTracker's search origin and its actual target
                // point, rather than body centers or pathfinding foot position.
                if (!egg.mainHurtBox)
                    return false;
                eggDistance = Vector3.Distance(player.inputBank.aimOrigin, egg.mainHurtBox.transform.position);
                trackerMaximumDistance = tracker.maxTrackingDistance;
                return IntegratedWorldSession.Finite(eggDistance) && IntegratedWorldSession.Finite(trackerMaximumDistance) &&
                       trackerMaximumDistance >= 0;
            }
            public ISirenNavigationObservationReader CreateNavigationObservationReader(CharacterBody player, NovaInputBridge bridge)
            {
                float stageSeconds = StageElapsed;
                float requestAge = stageSeconds - session.worldPathRequested;
                bool requestExists = session.worldPathRequestId > 0 && session.worldPathRequested >= 0 &&
                                     !string.IsNullOrEmpty(session.worldPathRequestReason) &&
                                     coordinator.worldPathFollower.nodeGraph != null &&
                                     IntegratedWorldSession.Finite(stageSeconds) && IntegratedWorldSession.Finite(requestAge) && requestAge >= 0;
                return new SirenNavigationObservationApi(player, bridge, coordinator.worldPathFollower,
                    session.worldPathRequestId, requestExists, session.worldPathRequested, requestAge,
                    session.worldPathRequestReason, coordinator.r.world == null ? null : coordinator.r.world.movementState);
            }
            public bool RevalidatedSourceEggs(Vector3 position,
                                              List<CharacterBody> destination) => coordinator.RevalidatedSirenDiagnosticEggs(position,
                                                                                                                             destination);
            public bool IsCurrentSourceEgg(CharacterBody candidate) => coordinator.IsCurrentSirenDiagnosticEgg(candidate);
            public bool ShouldYieldToExistingWorldCombat(CharacterBody player) => coordinator.r.combatPerformanceFocus
                                                                                  || coordinator.HasNearbyHostileDirectorThreat(player);
            public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 target, float stopDistance,
                                           string targetName, float elapsed) => coordinator.NavigateWorldInput(player, bridge, target,
                                                                                                               stopDistance, targetName,
                                                                                                               elapsed);
            public Vector3 WorldCombatAimPoint(CharacterBody target, Vector3 origin,
                                               out bool visible) => coordinator.WorldCombatAimPoint(target, origin, out visible);
        }
        // Read-only companion to DefendWorldApproach's live actor, stage-bounds,
        // and <20 m checks. It never calls ObjectiveCombatInput, so the normal
        // producer remains the only combat-input writer for this frame.
        public bool HasNearbyHostileDirectorThreat(CharacterBody player)
        {
            if (!player || !player.teamComponent)
                return false;
            Vector3 playerPosition = player.corePosition;
            TeamIndex playerTeam = player.teamComponent.teamIndex;
            foreach (var actor in coordinator.directorActors)
            {
                CharacterBody body = actor.body;
                CharacterMaster master = actor.master;
                HealthComponent health = body ? body.healthComponent : null;
                SirenCombatThreatEvidence evidence = new SirenCombatThreatEvidence {
                    bodyLive = body,
                    masterLive = master,
                    healthAlive = health && health.alive,
                    playerTeamKnown = true,
                    hostileTeam = master && master.teamIndex != playerTeam,
                    insideSourceBounds = body && coordinator.InsideSourceStageBounds(coordinator.DirectorPhysicsPosition(body)),
                    distanceSqr = body ? (body.corePosition - playerPosition).sqrMagnitude : float.PositiveInfinity
                };
                if (SirenCombatThreatContract.IsNearbyHostileDirectorThreat(evidence))
                    return true;
            }
            return false;
        }
        public void IntegratedWorldStimulus(CharacterBody player, NovaInputBridge bridge, float elapsed)
        {
            // Explicit automation for integrated validation only; direct app launches use physical controls.
            bridge.touchEquipment |= coordinator.worldEquipmentTouch;
            coordinator.worldEquipmentTouch = false;
            if (!bridge.manualInputAvailable)
                coordinator.worldManualTakeover = false;
            bridge.diagnosticInput = !coordinator.worldManualTakeover;
            coordinator.r.world.manualTakeover = coordinator.worldManualTakeover;
            if (coordinator.worldManualTakeover)
            {
                coordinator.r.world.diagnosticInput = false;
                return;
            }
            if (!string.IsNullOrEmpty(coordinator.r.diagnosticSkillIsolationSlot))
            {
                bridge.isolatedDiagnosticSkillInput = true;
                bridge.isolatedDiagnosticSkillSlot = SurvivorSkillInputCoverage.ParseIsolationSlot(
                    coordinator.r.diagnosticSkillIsolationSlot);
            }
            if (!coordinator.r.world.diagnosticInputEver)
            {
                coordinator.Check(coordinator.r.debugAcceleration != null, "Unattended input has no owned diagnostic evidence");
                coordinator.DebugToggle("diagnosticInput", true, "unattended route");
            }
            coordinator.r.world.diagnosticInput = true;
            coordinator.r.world.diagnosticInputEver = true;
            coordinator.WorldEquipmentStimulus(bridge, elapsed);
            bridge.diagnosticSprint = false;
            GameObject target = null;
            bridge.diagnosticInteract = false;
            bridge.diagnosticPrimary = false;
            bridge.diagnosticSecondary = false;
            bridge.diagnosticUtility = false;
            bridge.diagnosticSpecial = false;
            bridge.DiagnosticJump(false);
            // Measurement-only input: keep the whole director/combat simulation active
            // without spending the frame budget on the unattended shopping/path route.
            if (coordinator.r.combatPerformanceFocus)
            {
                bridge.movement = Vector2.zero;
                coordinator.r.world.objective = "Measure original combat with stationary input";
                var origin = player.inputBank.aimOrigin;
                CharacterBody visibleBody = null;
                Vector3 visiblePoint = Vector3.zero;
                float nearest = float.PositiveInfinity;
                foreach (var actor in coordinator.directorActors)
                {
                    if (!actor.body || !actor.body.healthComponent.alive || actor.master.teamIndex == player.teamComponent.teamIndex)
                        continue;
                    bool visible;
                    var point = coordinator.WorldCombatAimPoint(actor.body, origin, out visible);
                    if (!visible)
                        continue;
                    var distance = (point - origin).sqrMagnitude;
                    if (distance >= nearest)
                        continue;
                    nearest = distance;
                    visibleBody = actor.body;
                    visiblePoint = point;
                }
                if (visibleBody)
                {
                    var aim = visiblePoint - origin;
                    bridge.aim = new Vector2(aim.x, aim.z).normalized;
                    bridge.diagnosticAim = aim.normalized;
                    bridge.diagnosticPrimary = true;
                    coordinator.r.world.combatTarget = visibleBody.name;
                    coordinator.r.world.combatTargetDistance = Mathf.Sqrt(nearest);
                    coordinator.r.world.combatLineOfSight = true;
                }
                return;
            }
            if (coordinator.r.moon != null && coordinator.r.moon.loaded && coordinator.MoonWorldStimulus(player, bridge, elapsed))
                return;
            if (coordinator.GoldshoresRouteStimulus(player, bridge, elapsed))
                return;
            // Assisted dependency scan of the source repairable ally types in one
            // composed stage. Only the existing player input/earned Money path purchases;
            // ordinary runs and source selection remain untouched.
            if (coordinator.r.commerceSweep && coordinator.r.stageProgress != null && coordinator.r.stageProgress.transitions == 0 &&
                elapsed - coordinator.stageEnteredAt < 420 && coordinator.CommerceSweepPendingRepairs())
            {
                coordinator.Check(coordinator.IsRunAssisted(), "Commerce sweep must be marked assisted");
                var purchase = coordinator.NextCommerceSweepTarget(player);
                if (purchase)
                {
                    target = purchase.gameObject;
                    coordinator.r.world.objective = "Purchase original " + coordinator.CommerceSweepFamily(purchase);
                    if (coordinator.DefendWorldApproach(player, bridge, target, elapsed))
                        return;
                    NavigateWorldInput(player, bridge, target.transform.position, .4f, target.name, elapsed);
                    var collider = target.GetComponentsInChildren<Collider>(true).FirstOrDefault(x => x.enabled && !x.isTrigger);
                    var aim = (collider ? collider.bounds.center : target.transform.position) - player.inputBank.aimOrigin;
                    bridge.aim = new Vector2(aim.x, aim.z).normalized;
                    bridge.diagnosticAim = aim.normalized;
                    var selected = coordinator.worldDriver.currentInteractable
                                       ? coordinator.worldDriver.currentInteractable.GetComponent<PurchaseInteraction>()
                                       : null;
                    if (selected && selected.available &&
                        coordinator.CommerceSweepFamily(selected) == coordinator.CommerceSweepFamily(purchase) &&
                        selected.CanBeAffordedByInteractor(player.GetComponent<Interactor>()) && elapsed - coordinator.worldLastPress > .5f)
                    {
                        bridge.diagnosticInteract = true;
                        coordinator.worldLastPress = elapsed;
                    }
                }
                else
                {
                    coordinator.r.world.objective = "Earn currency for original interactables";
                    coordinator.ObjectiveCombatInput(player, bridge, elapsed, Vector2.zero, false);
                }
                return;
            }
            // Native placement spreads barrels across the map. Diagnostic input can shop
            // as soon as earned money permits; clearing every barrel is not a game rule.
            if (coordinator.r.liveCatalogs != null && coordinator.worldObjective == 0)
            {
                var chest = coordinator.NextAutomaticWorldChest(player);
                if (chest)
                    coordinator.worldObjective = 1;
            }
            // On some original layouts the teleporter is beside the entry point. An
            // unattended shopping route can strand itself across a disconnected graph
            // before ever selecting it; take the nearby native objective first.
            if (coordinator.r.teleporterLoop && coordinator.worldTeleporter && coordinator.worldTeleporter.isIdle &&
                coordinator.objectiveHost && Vector3.Distance(player.corePosition, coordinator.objectiveHost.transform.position) < 20f &&
                coordinator.ObjectiveWorldStimulus(player, bridge, elapsed))
                return;
            if (coordinator.worldObjective == 0)
            {
                var barrel = coordinator.worldBarrels.Where(x => x && !x.Networkopened)
                                 .OrderBy(x => Vector3.SqrMagnitude(x.transform.position - player.corePosition))
                                 .FirstOrDefault();
                if (barrel)
                    target = barrel.gameObject;
                else
                    coordinator.worldObjective = 1;
            }
            if (coordinator.worldObjective == 3 && elapsed - coordinator.stageEnteredAt < 160 &&
                coordinator.NextAutomaticWorldChest(player) &&
                player.master.money >= coordinator.NextAutomaticWorldChest(player).GetComponent<PurchaseInteraction>().cost)
                coordinator.worldObjective = 1;
            if (coordinator.worldObjective == 1)
            {
                var chest = coordinator.NextAutomaticWorldChest(player);
                if (coordinator.r.world.openedChests > coordinator.r.world.pickupMessages - coordinator.stagePickupBaseline)
                    coordinator.worldObjective = 2;
                else if (chest && player.master.money >= chest.GetComponent<PurchaseInteraction>().cost)
                    target = chest.gameObject;
                else
                    coordinator.worldObjective = 3;
            }
            if (coordinator.worldObjective > 0 && coordinator.GrantableWorldPickups(player, true).Any())
                coordinator.worldObjective = 2;
            if (coordinator.worldObjective == 2)
            {
                var pickup = coordinator.GrantableWorldPickups(player, true)
                                 .OrderBy(x => Vector3.Distance(x.transform.position, player.corePosition))
                                 .FirstOrDefault();
                if (pickup)
                    target = pickup.gameObject;
                else if (coordinator.r.world.pickupMessages - coordinator.stagePickupBaseline >= coordinator.r.world.openedChests)
                    coordinator.worldObjective = 3;
            }
            if (coordinator.worldObjective == 3 && elapsed - coordinator.stageEnteredAt < 65)
            {
                var commerce = coordinator.AffordableWorldCommerce();
                if (commerce)
                    target = commerce;
            }
            coordinator.r.world.objective = coordinator.worldObjective == 0   ? "Collect original barrel rewards"
                                            : coordinator.worldObjective == 1 ? "Purchase original chest"
                                            : coordinator.worldObjective == 2 ? "Collect naturally ejected item"
                                                                              : "Survive original director combat";
            // Keep diagnostic combat/shopping active briefly when the original stage
            // actually spawned an equipment barrel. The native purchase still requires
            // earned money and the normal drop/acquisition path.
            bool shoppingForNativeEquipment = coordinator.worldEquipmentChests.Any(x => x && !x.NetworkisChestOpened) &&
                                              player.inventory.currentEquipmentIndex == EquipmentIndex.None &&
                                              elapsed - coordinator.stageEnteredAt < 160;
            if (coordinator.r.teleporterLoop && elapsed - coordinator.stageEnteredAt > 65 && !shoppingForNativeEquipment)
            {
                if (coordinator.ObjectiveWorldStimulus(player, bridge, elapsed))
                    return;
            }
            bridge.movement = Vector2.zero;
            if (target)
            {
                if (coordinator.r.teleporterLoop && coordinator.DefendWorldApproach(player, bridge, target, elapsed))
                    return;
                NavigateWorldInput(player, bridge, target.transform.position, target.GetComponent<GenericPickupController>() ? .6f : 1.6f,
                                   target.name, elapsed);
                var collider = target.GetComponentsInChildren<Collider>(true).FirstOrDefault(x => x.enabled && !x.isTrigger);
                var aim = (collider ? collider.bounds.center : target.transform.position) - player.inputBank.aimOrigin;
                bridge.aim = new Vector2(aim.x, aim.z).normalized;
                // The original input producer consumes a 3D ray; use the measured target elevation as well.
                bridge.diagnosticAim = aim.normalized;
                if (coordinator.worldDriver.currentInteractable == target && elapsed - coordinator.worldLastPress > .5f)
                {
                    bridge.diagnosticInteract = true;
                    coordinator.worldLastPress = elapsed;
                }
            }
            else
            {
                if (coordinator.r.teleporterLoop)
                {
                    coordinator.ObjectiveCombatInput(player, bridge, elapsed, Vector2.zero, false);
                    return;
                }
                bridge.diagnosticAim = Vector3.zero;
                var enemy = coordinator.directorActors.Where(x => x.body && x.body.healthComponent.alive)
                                .OrderBy(x => Vector3.Distance(x.body.corePosition, player.corePosition))
                                .FirstOrDefault();
                if (enemy != null)
                {
                    var aim = enemy.body.corePosition - player.inputBank.aimOrigin;
                    bridge.aim = new Vector2(aim.x, aim.z).normalized;
                    bridge.diagnosticAim = aim.normalized;
                    bridge.diagnosticPrimary = true;
                    bridge.diagnosticSecondary = elapsed % 12 < .2f;
                    bridge.diagnosticSpecial = elapsed % 20 < .2f;
                    bridge.diagnosticUtility = elapsed % 16 < .2f;
                }
                bridge.DiagnosticJump(elapsed % 18 < .2f);
            }
        }
        float worldFeatherInputAt = -1;
        public void ApplySurvivorSkillCoverage(CharacterBody player, NovaInputBridge bridge, float elapsed)
        {
            if (!coordinator.r.diagnosticSkillCoverage || coordinator.r.phase != "integrated-world-playing")
                return;
            coordinator.Check(player && player == coordinator.worldPlayer && coordinator.r.world.authority,
                              "Diagnostic skill coverage requires the owned authoritative player");
            if (skillInputCoverage == null)
            {
                if (!bridge || !bridge.diagnosticInput)
                    return;
                coordinator.Check(survivorSkills != null && coordinator.r.debugAcceleration != null,
                                  "Diagnostic skill coverage requires prepared observation and assist tracking");
                skillInputCoverage = new SurvivorSkillInputCoverage(player, bridge, survivorSkills.report,
                    coordinator.r.diagnosticSkillIsolationSlot, coordinator.r.diagnosticToolbotOffhand,
                    survivorCombatOutputs != null ? survivorCombatOutputs.report : null,
                    coordinator.r.diagnosticCaptainSupplyBeacon);
                coordinator.r.skillInputCoverage = skillInputCoverage.reportData;
                coordinator.DebugToggle("diagnosticSkillCoverage", true, "explicit launch selection");
                if (skillInputCoverage.reportData.mode == "isolated-slot" ||
                    skillInputCoverage.reportData.mode == "toolbot-offhand-sequence" ||
                    skillInputCoverage.reportData.mode == "captain-supply-beacon-sequence")
                {
                    coordinator.Check(coordinator.r.developerSkillIsolationAssisted,
                                      "Isolated skill-input assistance was not validated before native setup");
                    coordinator.DebugToggle("diagnosticSkillIsolation", true,
                        skillInputCoverage.reportData.mode == "toolbot-offhand-sequence" ?
                            "explicit Toolbot offhand selector" : skillInputCoverage.reportData.mode == "captain-supply-beacon-sequence" ?
                            "explicit Captain supply-beacon selector" : "explicit launch selector");
                }
            }
            skillInputCoverage.Apply(elapsed);
            var coverage = skillInputCoverage.reportData;
            if (coverage.mode == "isolated-slot")
            {
                while (lastTransientWindowRequestCount < coverage.requests)
                {
                    survivorCombatOutputs?.RequestTransientProjectileWindow(elapsed);
                    lastTransientWindowRequestCount++;
                }
            }
            else
            {
                lastTransientWindowRequestCount = coverage.requests;
            }
        }
        public void EarnedFeatherInput(CharacterBody player, NovaInputBridge bridge, float elapsed)
        {
            // Whole-game diagnostic input only. Do not grant inventory, change jump limits,
            // move the body, or claim a controller/normal jump-height acceptance.
            if (coordinator.r.world.featherJumps > 0)
            {
                if (coordinator.r.world.featherInputAttempted)
                    coordinator.r.world.featherInputOutcome = "Original bonus jump and effect observed";
                return;
            }
            if (!bridge.diagnosticInput || coordinator.worldManualTakeover || coordinator.r.moon != null && coordinator.r.moon.loaded)
                return;
            var motor = player.characterMotor;
            if (worldFeatherInputAt < 0)
            {
                if (coordinator.r.world.featherInputAttempted || !coordinator.r.objective.charging ||
                    coordinator.r.objective.charge > .5f || !motor.isGrounded ||
                    player.inventory.GetItemCount(RoR2Content.Items.Feather) <= 0 || player.maxJumpCount <= player.baseJumpCount)
                    return;
                if (Vector3.Distance(motor.Motor.TransientPosition, coordinator.r.objective.position) >
                    coordinator.r.objective.radius * .5f)
                    return;
                worldFeatherInputAt = elapsed;
                coordinator.r.world.featherInputAttempted = true;
                coordinator.r.world.featherInputOutcome = "Original grounded press, release, then airborne second press";
            }
            float age = elapsed - worldFeatherInputAt;
            if (age > 1.5f)
            {
                coordinator.r.world.featherInputOutcome = "No bonus jump observed during input sequence";
                worldFeatherInputAt = -1;
                return;
            }
            bridge.movement = Vector2.zero;
            bridge.diagnosticSprint = false;
            bool first = age < .1f, second = age > .35f && age < .55f && !motor.isGrounded && motor.jumpCount == 1;
            bridge.DiagnosticJump(first || second);
        }
        public void NavigateWorldInput(CharacterBody player, NovaInputBridge bridge, Vector3 destination, float stopDistance, string target,
                                       float elapsed)
        {
            // Match the exact shipped BaseAI navigation reference for this pinned input.
            var position = player.temporaryPathfindingFootpositionDoNotUseWillBePatchedOut;
            var delta = destination - position;
            var planar = new Vector2(delta.x, delta.z);
            coordinator.r.world.navigationReference = position;
            var graph = SceneInfo.instance ? SceneInfo.instance.groundNodes : null;
            var waypoint = destination;
            bool moon = coordinator.r.moon != null && coordinator.r.moon.loaded;
            if (worldElevatedApproachActive &&
                (moon || graph != worldElevatedApproachGraph || Vector3.Distance(destination, worldElevatedApproachObjective) > 2 ||
                 Vector3.Distance(position, worldElevatedApproachDestination) < 3))
                worldElevatedApproachActive = false;
            var routeDestination = worldElevatedApproachActive ? worldElevatedApproachDestination : destination;
            coordinator.r.world.navigationElevatedApproachActive = worldElevatedApproachActive;
            // Players may sprint while travelling. Let original input/stat callbacks supply
            // the actual speed used by the next source path request, including earned items.
            if (moon || elapsed < coordinator.worldTerrainRecoveryUntil)
                bridge.diagnosticSprint = planar.magnitude > 8;
            coordinator.r.world.navigationSprint = bridge.diagnosticSprint;
            coordinator.r.world.navigationTerrainFallback = false;
            coordinator.r.world.navigationTerrainNoCandidate = false;
            coordinator.r.world.navigationTarget = target;
            coordinator.r.world.navigationDestination = destination;
            coordinator.r.world.navigationJump = false;
            // Replay follows the recovered graph through the normal input boundary. Original
            // motor limits, graph gates, physics, interaction range and item positions remain authoritative.
            RaycastHit obstacle;
            bool needsRoute = Mathf.Abs(delta.y) > 2 || planar.magnitude > 15 ||
                              Physics.Linecast(position + Vector3.up, destination + Vector3.up, out obstacle, LayerIndex.world.mask,
                                               QueryTriggerInteraction.Ignore);
            if (graph && needsRoute)
            {
                bool pathGraphChanged = coordinator.worldPathFollower.nodeGraph != graph;
                bool pathDestinationMoved = Vector3.Distance(routeDestination, worldPathTarget) > 2;
                bool pathIntervalExpired = elapsed - worldPathRequested > 8;
                if (pathGraphChanged || pathDestinationMoved || pathIntervalExpired)
                {
                    string requestReason = worldPathRequestId > 0 && worldPathRequested < 0
                                               ? "recovery-invalidated"
                                               : pathGraphChanged ? "graph-changed"
                                               : pathDestinationMoved ? "destination-moved" : "interval-expired";
                    coordinator.r.world.navigationHull = player.hullClassification.ToString();
                    coordinator.r.world.navigationJumpHeight =
                        player.maxJumpHeight.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
                    coordinator.r.world.navigationMaxSpeed = player.moveSpeed;
                    coordinator.r.world.navigationMaxSlope = player.characterMotor.Motor.MaxStableSlopeAngle;
                    coordinator.r.world.navigationGravityY = Physics.gravity.y;
                    coordinator.r.world.navigationGraphNodes = graph.GetNodeCount();
                    coordinator.r.world.navigationNearestNode = graph.FindClosestNode(position, player.hullClassification).nodeIndex;
                    var startNode = graph.FindClosestNodeWithRaycast(position, player.hullClassification, 100, 2);
                    coordinator.r.world.navigationStartNode = startNode.nodeIndex;
                    Vector3 startPosition;
                    coordinator.r.world.navigationStartPosition =
                        graph.GetNodePosition(startNode, out startPosition) ? startPosition : Vector3.zero;
                    coordinator.r.world.navigationApproachBoundsRejected = coordinator.r.world.navigationApproachTooShort =
                        coordinator.r.world.navigationApproachUnreachable = 0;
                    using (var path = new RoR2.Path(graph))
                    {
                        var task = graph.ComputePath(new RoR2.Navigation.NodeGraph.PathRequest {
                            path = path, startPos = position, endPos = routeDestination, hullClassification = player.hullClassification,
                            maxSlope = player.characterMotor.Motor.MaxStableSlopeAngle, maxJumpHeight = player.maxJumpHeight,
                            maxSpeed = player.moveSpeed
                        });
                        coordinator.Check(task.status == RoR2.Navigation.PathTask.TaskStatus.Complete,
                                          "Original stage path did not complete");
                        coordinator.r.world.navigationReachable = task.wasReachable;
                        coordinator.r.world.navigationPartial = false;
                        coordinator.r.world.navigationPartialCandidates = 0;
                        coordinator.r.world.navigationPartialNode = -1;
                        coordinator.r.world.navigationPartialSeconds = 0;
                        // A stage graph can report its nearest target node reachable while returning
                        // no traversal to an objective on a higher platform. Once direct movement
                        // stalls, ask that same source graph for a reachable upper approach.
                        bool elevatedStall = !moon && !worldElevatedApproachActive && task.wasReachable && path.waypointsCount < 2 &&
                                             delta.y > player.maxJumpHeight && worldNavigationHasObjectiveProgress &&
                                             elapsed - worldNavigationObjectiveProgressAt > 6;
                        if (elevatedStall)
                            coordinator.r.world.navigationElevatedApproachAttempted = true;
                        if (moon && !task.wasReachable || elevatedStall)
                        {
                            coordinator.r.world.navigationPartial =
                                FindSourceWorldApproach(player, graph, path, position, destination, elevatedStall);
                            if (elevatedStall && coordinator.r.world.navigationPartial)
                            {
                                coordinator.r.world.navigationElevatedApproachFound = true;
                                worldElevatedApproachActive = true;
                                worldElevatedApproachGraph = graph;
                                worldElevatedApproachObjective = destination;
                                worldElevatedApproachDestination = coordinator.r.world.navigationPartialDestination;
                                coordinator.r.world.navigationElevatedApproachActive = true;
                                routeDestination = worldElevatedApproachDestination;
                            }
                        }
                        coordinator.r.world.navigationWaypoints = path.waypointsCount;
                        coordinator.worldPathFollower.SetPath(path);
                        var observed = new List<NavigationPathPoint>();
                        for (int i = 0; i < path.waypointsCount; i++)
                        {
                            Vector3 node;
                            coordinator.Check(graph.GetNodePosition(path[i].nodeIndex, out node),
                                              "Original path node position unavailable");
                            observed.Add(new NavigationPathPoint { position = node, minimumJumpHeight = path[i].minJumpHeight });
                        }
                        coordinator.r.world.navigationPath = observed.ToArray();
                    }
                    worldPathTarget = routeDestination;
                    worldPathRequested = elapsed;
                    worldPathRequestId++;
                    worldPathRequestReason = requestReason;
                }
                coordinator.worldPathFollower.UpdatePosition(position);
                var next = coordinator.worldPathFollower.GetNextPosition();
                if (next.HasValue)
                    waypoint = next.Value;
                coordinator.r.world.navigationJump = coordinator.worldPathFollower.nextWaypointNeedsJump;
            }
            else
            {
                coordinator.worldPathFollower.Reset();
                coordinator.r.world.navigationReachable = true;
                coordinator.r.world.navigationPartial = false;
                coordinator.r.world.navigationWaypoints = 0;
                coordinator.r.world.navigationPath = new NavigationPathPoint[0];
            }
            bool stalled = worldNavigationHasProgress && elapsed - worldNavigationProgressAt > 3 &&
                           Vector3.Distance(waypoint, worldNavigationProgressWaypoint) < .5f &&
                           Vector3.Distance(destination, worldNavigationProgressDestination) < 2;
            bool sourceApproach = coordinator.r.world.navigationPartial && !coordinator.worldPathFollower.isFinished;
            // A refreshed source path can keep changing its local waypoint while the
            // player circles the same obstacle. Compare progress to the real objective.
            bool objectiveStalled = worldNavigationHasObjectiveProgress &&
                                    Vector3.Distance(routeDestination, worldNavigationObjective) < 2 &&
                                    elapsed - worldNavigationObjectiveProgressAt > 6;
            bool followingElevatedSourcePath = worldElevatedApproachActive && coordinator.r.world.navigationReachable &&
                                               !coordinator.worldPathFollower.isFinished && coordinator.r.world.navigationWaypoints > 2;
            if (needsRoute && ((graph && !coordinator.r.world.navigationReachable && !sourceApproach) || stalled ||
                               objectiveStalled && !followingElevatedSourcePath))
                coordinator.worldTerrainRecoveryUntil = elapsed + 4;
            if (needsRoute && elapsed < coordinator.worldTerrainRecoveryUntil)
            {
                // The source graph can be disconnected or reach a waypoint the current
                // approach cannot traverse. Retain its result; steer normal input over ground.
                // Do not open gates, edit links, invent extra jumps or move the body directly.
                waypoint = TerrainTravelWaypoint(player, position, waypoint, elapsed);
                if (objectiveStalled)
                    coordinator.r.world.navigationObjectiveRecoveryFrames++;
                coordinator.r.world.navigationTerrainFallback = true;
                coordinator.r.world.navigationTerrainFrames++;
                coordinator.r.world.navigationTerrainTarget = waypoint;
            }
            coordinator.r.world.navigationWaypoint = waypoint;
            var direction = waypoint - position;
            var movement = new Vector2(direction.x, direction.z);
            if (coordinator.worldNavigationBody != player)
            {
                coordinator.worldLocalNavigator.SetBody(player);
                coordinator.worldNavigationBody = player;
                worldNavigationUpdatedAt = elapsed;
                worldNavigationHasProgress = false;
                worldNavigationHasObjectiveProgress = false;
            }
            // Original graph traversal can include jumps. Terrain fallback has no such
            // link contract: retain the source cliff guard for its local steering too.
            // Gold Shores' shipped out-of-bounds volume is inactive in the recovered
            // scene. The unattended driver must not follow a graph edge over an exposed
            // drop while pursuing currency targets; source player physics remains intact.
            coordinator.worldLocalNavigator.targetPosition = waypoint + (player.transform.position - position);
            coordinator.worldLocalNavigator.allowWalkOffCliff =
                !coordinator.r.world.navigationTerrainFallback && coordinator.stageGeometryScene.name != "goldshores";
            coordinator.worldLocalNavigator.Update(Mathf.Clamp(elapsed - worldNavigationUpdatedAt, .001f, .1f));
            worldNavigationUpdatedAt = elapsed;
            coordinator.r.world.navigationAllowWalkOffCliff = coordinator.worldLocalNavigator.allowWalkOffCliff;
            coordinator.r.world.navigationLocalMovement = coordinator.worldLocalNavigator.moveVector;
            coordinator.r.world.navigationLocalObstructed = coordinator.worldLocalNavigator.wasObstructedLastUpdate;
            coordinator.r.world.navigationLocalJumpSpeed = coordinator.worldLocalNavigator.jumpSpeed;
            // The requested stopping distance belongs to the final objective, not the
            // next graph waypoint. A broad holdout radius can exceed a nearby waypoint
            // while the player is still far outside the real charge zone.
            bridge.movement = Vector3.Distance(position, destination) > stopDistance
                                  ? new Vector2(coordinator.worldLocalNavigator.moveVector.x, coordinator.worldLocalNavigator.moveVector.z)
                                  : Vector2.zero;
            // Walking in a circle is not progress toward the source waypoint. The real
            // Wetland return capture does this at full speed, so source frustration stays
            // zero. Recovery requests a normal player jump; source physics owns the result.
            var remaining = Vector3.Distance(position, waypoint);
            if (!worldNavigationHasProgress || Vector3.Distance(waypoint, worldNavigationProgressWaypoint) > .5f ||
                Vector3.Distance(destination, worldNavigationProgressDestination) > 2 || remaining < worldNavigationProgressDistance - .5f)
            {
                worldNavigationHasProgress = true;
                worldNavigationProgressWaypoint = waypoint;
                worldNavigationProgressDestination = destination;
                worldNavigationProgressDistance = remaining;
                worldNavigationProgressAt = elapsed;
            }
            coordinator.r.world.navigationStalledSeconds = elapsed - worldNavigationProgressAt;
            // Terrain replanning changes the local waypoint even while circling the same
            // obstacle. Track the actual objective separately so it cannot hide that stall.
            float objectiveDistance = Vector3.Distance(position, routeDestination);
            if (!worldNavigationHasObjectiveProgress || Vector3.Distance(routeDestination, worldNavigationObjective) > 2 ||
                objectiveDistance < worldNavigationObjectiveDistance - .5f)
            {
                worldNavigationHasObjectiveProgress = true;
                worldNavigationObjective = routeDestination;
                worldNavigationObjectiveDistance = objectiveDistance;
                worldNavigationObjectiveProgressAt = elapsed;
            }
            coordinator.r.world.navigationObjectiveStalledSeconds = elapsed - worldNavigationObjectiveProgressAt;
            coordinator.r.world.navigationObjectiveProgressDistance = worldNavigationObjectiveDistance;
            coordinator.r.world.navigationProgressDistance = worldNavigationProgressDistance;
            coordinator.r.world.navigationRecoveryJump =
                remaining > Mathf.Max(1, stopDistance) &&
                (coordinator.r.world.navigationStalledSeconds > 3 ||
                 (coordinator.r.world.navigationTerrainFallback && coordinator.r.world.navigationObjectiveStalledSeconds > 3));
            bool jump = (coordinator.r.world.navigationJump || coordinator.worldLocalNavigator.jumpSpeed > 0 ||
                         coordinator.r.world.navigationRecoveryJump) &&
                        player.characterMotor.isGrounded && elapsed % 1.5f < .25f;
            bridge.DiagnosticJump(jump);
            if (jump && coordinator.r.world.navigationRecoveryJump)
                coordinator.r.world.navigationRecoveryJumpFrames++;
            if (coordinator.r.world.navigationRecoveryJump && elapsed > worldNavigationRecoveryUntil)
            {
                worldNavigationRecoveryUntil = elapsed + 3;
                coordinator.r.world.navigationRecoveries++;
                worldPathRequested = -100;
                worldPathRequestReason = "recovery-invalidated";
            }
        }
        public bool FindSourceWorldApproach(CharacterBody player, RoR2.Navigation.NodeGraph graph, RoR2.Path path, Vector3 position,
                                            Vector3 destination, bool elevated = false)
        {
            var began = Time.realtimeSinceStartup;
            float currentDistance = Vector3.Distance(position, destination);
            var candidates = new List<KeyValuePair<float, RoR2.Navigation.NodeGraph.NodeIndex>>();
            foreach (var index in graph.GetActiveNodesForHullMask((HullMask)(1 << (int)player.hullClassification)))
            {
                Vector3 node;
                coordinator.Check(graph.GetNodePosition(index, out node), "Original approach node unavailable");
                float distance = Vector3.Distance(node, destination);
                if (elevated)
                {
                    // The ramp's first useful node may be farther from the objective than the
                    // stranded footpoint. Its source elevation, bounds and computed path must
                    // agree; proximity alone never authorizes a jump or teleport.
                    // This source teleporter platform lies between lower and upper graph
                    // surfaces. Reach the upper connected surface,
                    // then let the original motor traverse down to the placed objective.
                    float height = node.y - destination.y;
                    if (height < -player.maxJumpHeight || height > Mathf.Max(12f, player.maxJumpHeight * 4f) ||
                        distance > currentDistance + 8)
                        continue;
                }
                else if (distance >= currentDistance - 8)
                    continue;
                if (!coordinator.InsideSourceStageBounds(node))
                {
                    coordinator.r.world.navigationApproachBoundsRejected++;
                    continue;
                }
                candidates.Add(new KeyValuePair<float, RoR2.Navigation.NodeGraph.NodeIndex>(distance, index));
            }
            candidates.Sort((a, b) => a.Key.CompareTo(b.Key));
            foreach (var candidate in candidates)
            {
                coordinator.r.world.navigationPartialCandidates++;
                var task = graph.ComputePath(
                    new RoR2.Navigation.NodeGraph.PathRequest { path = path, startPos = position, endPos = candidate.Value,
                                                                hullClassification = player.hullClassification,
                                                                maxSlope = player.characterMotor.Motor.MaxStableSlopeAngle,
                                                                maxJumpHeight = player.maxJumpHeight, maxSpeed = player.moveSpeed });
                coordinator.Check(task.status == RoR2.Navigation.PathTask.TaskStatus.Complete, "Original approach path did not complete");
                if (!task.wasReachable)
                {
                    coordinator.r.world.navigationApproachUnreachable++;
                    continue;
                }
                if (path.waypointsCount < 2)
                {
                    coordinator.r.world.navigationApproachTooShort++;
                    continue;
                }
                coordinator.r.world.navigationPartialNode = candidate.Value.nodeIndex;
                coordinator.Check(graph.GetNodePosition(candidate.Value, out coordinator.r.world.navigationPartialDestination),
                                  "Original approach destination unavailable");
                coordinator.r.world.navigationPartialSeconds = Time.realtimeSinceStartup - began;
                return true;
            }
            coordinator.r.world.navigationPartialSeconds = Time.realtimeSinceStartup - began;
            path.Clear();
            return false;
        }
        public Vector3 TerrainTravelWaypoint(CharacterBody player, Vector3 position, Vector3 destination, float elapsed)
        {
            coordinator.r.world.navigationTerrainNoCandidate = false;
            if (coordinator.worldNavigationBody != player || Vector3.Distance(destination, worldTerrainGoal) > 2)
            {
                coordinator.worldTerrainRecent.Clear();
                coordinator.worldTerrainSelectedAt = -100;
                worldTerrainGoal = destination;
            }
            if (elapsed - coordinator.worldTerrainSelectedAt < 1 && Vector3.Distance(position, worldTerrainTarget) > 1)
                return worldTerrainTarget;
            coordinator.worldTerrainSelectedAt = elapsed;
            var desired = destination - position;
            desired.y = 0;
            desired.Normalize();
            float best = float.NegativeInfinity;
            Vector3 selected = position;
            // Reuse the full game's ground-to-ground avoidance contract. Short candidates
            // handle local obstacles; longer ones keep the driver on recovered bridges.
            for (int i = 0; i < 16; i++)
                foreach (float length in new[] { 4f, 8f, 16f })
                {
                    var direction = Quaternion.AngleAxis(i * 22.5f, Vector3.up) * desired;
                    Vector3 prior = position, groundPoint = position;
                    bool valid = true;
                    int steps = Mathf.CeilToInt(length / 1.5f);
                    for (int step = 1; step <= steps; step++)
                    {
                        var sample = position + direction * (length * step / steps);
                        sample.y = prior.y;
                        RaycastHit ground = default(RaycastHit);
                        int hits = Physics.RaycastNonAlloc(sample + Vector3.up * 4, Vector3.down, worldTerrainHits, 9,
                                                           LayerIndex.world.mask, QueryTriggerInteraction.Ignore);
                        if (hits == worldTerrainHits.Length)
                        {
                            coordinator.r.world.navigationTerrainRayOverflow++;
                            valid = false;
                            break;
                        }
                        // Overlapping floors must not turn a ceiling into the walking surface.
                        float nearest = float.PositiveInfinity, highest = float.NegativeInfinity;
                        for (int hitIndex = 0; hitIndex < hits; hitIndex++)
                        {
                            var hit = worldTerrainHits[hitIndex];
                            float change = Mathf.Abs(hit.point.y - prior.y);
                            if (hit.collider.gameObject.scene != coordinator.stageGeometryScene ||
                                Vector3.Angle(hit.normal, Vector3.up) > player.characterMotor.Motor.MaxStableSlopeAngle ||
                                change > player.maxJumpHeight || !coordinator.InsideSourceStageBounds(hit.point))
                                continue;
                            highest = Mathf.Max(highest, hit.point.y);
                            if (change < nearest)
                            {
                                nearest = change;
                                ground = hit;
                            }
                        }
                        if (!ground.collider)
                        {
                            valid = false;
                            break;
                        }
                        if (highest - ground.point.y > .1f)
                            coordinator.r.world.navigationTerrainLowerChoices++;
                        // A clear center ray can still send the actual body into an adjacent wall.
                        // Sweep its measured torso width; original KCC remains the movement solver.
                        var segment = ground.point - prior;
                        RaycastHit clearance;
                        if (segment.sqrMagnitude > .0001f &&
                            Physics.SphereCast(prior + Vector3.up, player.characterMotor.Motor.Capsule.radius * .9f, segment.normalized,
                                               out clearance, segment.magnitude, LayerIndex.world.mask, QueryTriggerInteraction.Ignore))
                        {
                            valid = false;
                            break;
                        }
                        prior = groundPoint = ground.point;
                    }
                    if (!valid)
                        continue;
                    float score = Vector3.Distance(position, destination) - Vector3.Distance(groundPoint, destination);
                    // A blocked slope may require moving sideways or away. Recent ground samples
                    // penalize repeating the same circle without changing any simulation values.
                    foreach (var recent in coordinator.worldTerrainRecent)
                        score -= Mathf.Max(0, 8 - Vector3.Distance(recent, groundPoint));
                    if (score <= best)
                        continue;
                    best = score;
                    selected = groundPoint;
                }
            // Rejection must not bypass the ground/torso/bounds checks by steering toward
            // an unchecked distant goal. Neutral input lets original physics settle.
            if (selected == position)
            {
                coordinator.r.world.navigationTerrainBlocked++;
                coordinator.r.world.navigationTerrainNoCandidate = true;
                worldTerrainTarget = position;
                return position;
            }
            worldTerrainTarget = selected;
            if (coordinator.worldTerrainRecent.Count == 0 ||
                Vector3.Distance(position, coordinator.worldTerrainRecent[coordinator.worldTerrainRecent.Count - 1]) > 3)
            {
                coordinator.worldTerrainRecent.Add(position);
                if (coordinator.worldTerrainRecent.Count > 40)
                    coordinator.worldTerrainRecent.RemoveAt(0);
            }
            return selected;
        }
        public IEnumerator VerifyIntegratedWorldCleanup()
        {
            if (coordinator.r.world == null)
                yield break;
            yield return null;
            yield return null;
            if (engiShieldGuard != null)
            {
                engiShieldGuard.ReleaseAfterWorldCleanup();
                engiShieldGuard = null;
                coordinator.r.world.engiShieldGuardReleased = true;
            }
            coordinator.FinishWorldDotCleanup();
            coordinator.VerifyFlightEquipmentCleanup();
            var stageHandlers = typeof(Stage)
                                    .GetField("onServerStageBegin", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                                    .GetValue(null) as Delegate;
            coordinator.Check(stageHandlers == null ||
                                  !stageHandlers.GetInvocationList().Any(
                                      handler => handler.Target is CharacterMaster ||
                                                 handler.Method.DeclaringType ==
                                                     typeof(RoR2.Stats.PlayerStatsComponent).Assembly.GetType("RoR2.Stats.StatManager")),
                              "A completed run retained original master/statistics stage callbacks");
            if (coordinator.r.objective != null)
            {
                coordinator.r.objective.cleaned = !coordinator.objectiveHost && !coordinator.objectiveStageHost &&
                                                  !coordinator.objectiveBossDeck && coordinator.objectiveResources.All(x => !x) &&
                                                  coordinator.objectiveCards.All(x => !x) && coordinator.objectiveTemplates.All(x => !x) &&
                                                  !coordinator.ownsObjectiveIndicator && coordinator.objectiveLocator == null &&
                                                  !coordinator.objectiveSubscribed && !TeleporterInteraction.instance && !Stage.instance;
                coordinator.Check(coordinator.r.objective.cleaned, "Owned teleporter/actor/context/provider cleanup incomplete");
            }
            coordinator.r.world.cleaned =
                coordinator.worldObjects.All(x => !x) && coordinator.worldModels.All(x => !x) && coordinator.worldMaterials.All(x => !x) &&
                !coordinator.worldStaging && !coordinator.worldPause && (!coordinator.worldDriver || !coordinator.worldDriver.enabled) &&
                !PauseStopController.instance && !coordinator.EjectionPickups().Any() && !coordinator.EjectionDroplets().Any() &&
                !ownsWorldDroplet && !ownsWorldCoinLease && worldDropletLocator == null && !coordinator.ownsPickupCatalog &&
                !coordinator.ownsMoneyCatalog && !ownsWorldLists && !ownsWorldPresentation && !ownsWorldMisc &&
                coordinator.worldLootEffectSlots.Count == 0 && coordinator.worldLootSourceMaterials.Count == 0 &&
                coordinator.worldLootSourceLayers.Count == 0 && coordinator.worldLootTemporaryEffects.All(x => !x) &&
                worldFeatherEffectIndex < 0 && worldFeatherJumped == null && coordinator.worldAvailableItems == null &&
                coordinator.worldAvailableEquipment == null;
            coordinator.r.world.cleaned &=
                coordinator.worldNativeLootLeaseBaselines.Count == 0 && coordinator.worldNativeLootObjects.Count == 0 &&
                worldProjectileGhostLeases.Count == 0 && !coordinator.ownsWorldDots &&
                (coordinator.r.dots == null || (coordinator.r.dots.cleaned && DotController.readOnlyInstancesList.Count == 0)) &&
                !ownsWorldTransmutation && (coordinator.r.world.transmutationGroups == 0 || coordinator.r.world.transmutationCleaned);
            if (coordinator.r.hud != null)
            {
                coordinator.r.hud.cleaned = !coordinator.recoveredHud && !coordinator.recoveredMenu;
                coordinator.r.world.cleaned &= coordinator.r.hud.cleaned;
            }
            if (coordinator.r.commerce != null)
            {
                coordinator.r.commerce.cleaned = coordinator.commerceOwned.All(x => !x) && coordinator.commerceListeners.Count == 0 &&
                                                 coordinator.commercePurchases.Count == 0 && !coordinator.ownsCommerceMessages &&
                                                 coordinator.commerceEffectIndex < 0;
                coordinator.r.world.cleaned &= coordinator.r.commerce.cleaned;
            }
            coordinator.Check(coordinator.r.world.cleaned, "Integrated content/input/loot/source/catalog cleanup incomplete");
            coordinator.Save();
        }
        public void DrawIntegratedWorld()
        {
            coordinator.DrawWorldEquipment();
            var world = coordinator.r.world;
            if (world == null || !world.ready)
                return;
            coordinator.DrawDebugAcceleration();
            coordinator.DrawMoonPillarMarkers();
            if (coordinator.r.enhancedPresentation && (!coordinator.recoveredHud || coordinator.debugPanel) &&
                GUI.Button(new Rect(coordinator.recoveredHud ? 20 : Screen.width - 270, 555, 250, 42),
                           AndroidMaterialPresentation.report.enabled ? "Graphics: approximation" : "Graphics: legacy preview"))
                AndroidMaterialPresentation.SetEnabled(!AndroidMaterialPresentation.report.enabled);
            var inputBridge = coordinator.worldPlayer ? coordinator.worldPlayer.GetComponent<NovaInputBridge>() : null;
            if (inputBridge && !inputBridge.diagnosticInput && world.health > 0)
                inputBridge.touchControls?.Draw();
            if (coordinator.r.id.EndsWith("-bringup") && world.health > 0 && inputBridge && inputBridge.manualInputAvailable &&
                GUI.Button(new Rect(Screen.width * .5f - 95, 10, 190, 48),
                           coordinator.worldManualTakeover ? "Resume auto route" : "Take control"))
            {
                var bridge = coordinator.worldPlayer ? coordinator.worldPlayer.GetComponent<NovaInputBridge>() : null;
                if (bridge)
                {
                    bridge.Neutral();
                    coordinator.worldManualTakeover = !coordinator.worldManualTakeover;
                    bridge.touchEquipment |= coordinator.worldEquipmentTouch;
                    coordinator.worldEquipmentTouch = false;
                    bridge.diagnosticInput = !coordinator.worldManualTakeover;
                    world.manualTakeover = coordinator.worldManualTakeover;
                    world.diagnosticInput = !coordinator.worldManualTakeover;
                    coordinator.Save();
                }
            }
            if (coordinator.r.id.EndsWith("-bringup") && world.health > 0 && (!inputBridge || !inputBridge.manualInputAvailable))
                GUI.Label(new Rect(20, Screen.height - 60, Screen.width - 40, 28), "Automatic diagnostic input · physical controller unavailable");
            var style = new GUIStyle(GUI.skin.label) { fontSize = 22 };
            var shadow = new GUIStyle(style);
            shadow.normal.textColor = Color.black;
            if (coordinator.recoveredHud && world.health > 0)
            {
                GUI.Label(new Rect(20, Screen.height - 30, Screen.width - 40, 26),
                          "Offline play");
                return;
            }
            string text = "Offline gameplay lab — " +
                          (coordinator.r.stageProgress != null ? coordinator.r.stageProgress.current : "Titanic Plains") + "\nHP " +
                          Mathf.Max(0, world.health).ToString("F0") + " / " + world.maxHealth.ToString("F0") + "    Lv " +
                          world.level.ToString("F0") + "    $" + world.money + "    " + world.seconds.ToString("F0") + "s\nKills " +
                          world.kills + "    Enemies " + world.liveEnemies + "    Chests " + world.openedChests + " / " + world.chests +
                          "\nSyringe " + world.syringe + " · Glasses " + world.glasses + " · Slug " + world.slug + " · Ukulele " +
                          world.lightning + "\n" + world.lastPickup + "    Crit " + world.crit.ToString("F0") + "% · Regen " +
                          world.regen.ToString("F1") +
                          (inputBridge && inputBridge.automaticDiagnosticOnly
                               ? "\nAutomatic diagnostic route · physical controller unavailable\n" +
                                     (string.IsNullOrEmpty(world.target) ? "Explore, fight and earn money" : "Target: " + world.target)
                               : "\nA jump · B interact · X primary · Y secondary · LB roll · RB barrage\n" +
                                     (string.IsNullOrEmpty(world.target) ? "Explore, fight and earn money" : "B: " + world.target)) +
                          "\nAudio, stock startup and profiles unavailable";
            if (world.lootDomain > 4)
                text += "\nEnergy Drink " + world.drink + " · Steak " + world.steak + " · Move speed " + world.moveSpeed.ToString("F1");
            if (world.lootTier3 > 0)
                text += "\nShield " + world.shield.ToString("F0") + " / " + world.maxShield.ToString("F0") + " · Jumps " +
                        world.motorMaxJumpCount;
            if (coordinator.r.moon != null && coordinator.r.moon.loaded)
                text += "\nMoon batteries " + coordinator.r.moon.charged + " / " + coordinator.r.moon.required + " · Encounter enemies " +
                        coordinator.r.moon.livingEncounterMembers + "\n" + world.objective;
            else if (coordinator.r.objective != null && coordinator.r.objective.ready)
                text += "\nTeleporter " + coordinator.r.objective.state + " — " + (coordinator.r.objective.charge * 100).ToString("F0") +
                        "% | " +
                        (coordinator.r.objective.bossDefeated ? "Boss defeated"
                                                              : "Boss HP " + coordinator.r.objective.bossHealth.ToString("F0") + " / " +
                                                                    coordinator.r.objective.bossMaxHealth.ToString("F0"));
            if (world.health <= 0)
            {
                text += inputBridge && inputBridge.automaticDiagnosticOnly
                            ? "\nCommando defeated. Start a fresh run from the touch button."
                            : "\nCommando defeated. Press A to restart a fresh run.";
                if (GUI.Button(new Rect(20, 420, 240, 48), inputBridge && inputBridge.automaticDiagnosticOnly ? "Restart run" : "Restart run (A)"))
                    RequestWorldRestart();
                if (GUI.Button(new Rect(280, 420, 180, 48), "Close session"))
                    Application.Quit();
            }
            else if (coordinator.worldView != null)
                coordinator.worldView.DrawReticle();
            GUI.Label(new Rect(21, 61, 1100, 350), text, shadow);
            GUI.Label(new Rect(20, 60, 1100, 350), text, style);
        }
        public void RequestWorldRestart()
        {
            if (coordinator.r != null && coordinator.r.freePlay && coordinator.r.integratedWorld &&
                coordinator.r.phase == "commando-defeated" && coordinator.r.playerDefeat.bodyDestroyed)
            {
                coordinator.restartRequested = true;
                coordinator.r.phase = "restarting-world";
                coordinator.Save();
            }
        }
        public void ObserveWorldRestartInput()
        {
            if (coordinator.r == null || !coordinator.r.freePlay || !coordinator.r.integratedWorld ||
                coordinator.r.phase != "commando-defeated" || coordinator.r.nova == null)
                return;
            if (coordinator.r.nova.mapping != null && coordinator.r.nova.physicalInputAvailable &&
                UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0 + coordinator.r.nova.mapping.jump)))
                RequestWorldRestart();
        }
        public void RestartWorldAfterCleanup()
        {
            if (!coordinator.restartRequested)
                return;
            coordinator.Check(coordinator.r.success && coordinator.r.cleanup && coordinator.r.world.cleaned &&
                                  coordinator.r.modelDestroyed && !Run.instance && !SceneInfo.instance && !NetworkServer.active &&
                                  !NetworkClient.active,
                              "Defeated world not clean enough to restart");
            System.IO.File.WriteAllText(
                System.IO.Path.Combine(Application.persistentDataPath, "movement-completed-session-" + coordinator.sessionIndex + ".json"),
                JsonUtility.ToJson(coordinator.r, true));
            coordinator.TrackCompletedSessionReferences();
            var next = new GameObject("Persistent offline gameplay session").AddComponent<PortSession>();
            next.sessionIndex = coordinator.sessionIndex + 1;
            next.skipOfflineMenu = !coordinator.returnToOfflineMenu;
            PortSession.Destroy(coordinator.gameObject);
        }
        void CancelPendingOriginalAudioCameraContextCreationForCleanup()
        {
            bool cancelled = originalAudioCameraContextCreationSchedule.CancelPending();
            var report = coordinator.r?.world;
            if (cancelled && report != null && !report.originalAudioCameraContextCreated)
                report.originalAudioCameraContextState = "deferred_creation_cancelled_by_world_cleanup";
        }

        public void CleanupIntegratedWorld()
        {
            // Close the one-shot scheduling policy before any cleanup branch
            // can return early for source-stage recovery. The observer may be
            // intentionally retained across that recovery, but it must not arm
            // a gameplay capture after world teardown has begun.
            coordinator.ClosePassivePcmActivityArmPolicy();
            CancelPendingOriginalAudioCameraContextCreationForCleanup();
            ReleaseOriginalAudioCameraContext();
            if (lightningStakeSourceCallObserver != null)
            {
                try
                {
                    lightningStakeSourceCallObserver.Dispose();
                    lightningStakeSourceCallObserver = null;
                }
                catch (Exception error)
                {
                    var report = coordinator.r?.world?.lightningStakeSourceCall;
                    if (report != null)
                    {
                        report.status = "teardown-error";
                        if (String.IsNullOrEmpty(report.firstCaptureFailureType))
                            report.firstCaptureFailureType = error.GetBaseException().GetType().FullName;
                    }
                    if (coordinator.r != null)
                    {
                        coordinator.r.success = false;
                        if (String.IsNullOrEmpty(coordinator.r.firstFailure))
                        {
                            coordinator.r.firstFailure = "LightningStake source-call observer did not detach its exact owned callback";
                            coordinator.r.firstFailurePhase = "integrated-world-cleanup";
                        }
                    }
                }
                coordinator.Save();
            }
            if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                return;
            sirenEggDiagnosticInput?.Dispose();
            sirenEggDiagnosticInput = null;
            skillInputCoverage?.Dispose();
            skillInputCoverage = null;
            lastTransientWindowRequestCount = 0;
            engiNativeOutputs?.Dispose();
            engiNativeOutputs = null;
            survivorCombatOutputs?.Dispose();
            if (survivorCombatOutputs != null && survivorCombatOutputs.report.cleaned)
                survivorCombatOutputs = null;
            survivorSkills?.Dispose();
            survivorSkills = null;
            coordinator.ClosePassivePcmActivityArmPolicy();
            nextSurvivorSkillSample = 0;
            coordinator.CleanupRecoveredHud();
            coordinator.CleanupIntegratedResults();
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
            {
                try
                {
                    // Detach per-object commerce listeners first, but keep provider
                    // leases and Run/catalog context until ordered native teardown completes.
                    coordinator.CleanupWorldCommerce(false);
                    coordinator.CleanupTeleporterWorld();
                    if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                        return;
                    CleanupWorldTransmutation();
                }
                catch (Exception primary)
                {
                    coordinator.MarkSourceStageLifecycleRecovery(true);
                    coordinator.r.cleanup = false;
                    coordinator.r.success = false;
                    coordinator.r.error += " Native source teardown retained providers and Run context: " + primary;
                    coordinator.Save();
                    throw;
                }
            }
            else
            {
                coordinator.CleanupWorldCommerce(true);
                CleanupWorldTransmutation();
                coordinator.CleanupTeleporterWorld();
            }
            coordinator.CleanupOriginalGlobalCommonAssets();
            coordinator.CleanupOriginalBodyVisualReferences();
            if (earlyHurtCacheHandler != null)
            {
                CharacterBody.onBodyAwakeGlobal -= earlyHurtCacheHandler;
                earlyHurtCacheHandler = null;
            }
            worldClientUpdate = null;
            nextWorldPickupSnapshot = 0;
            worldPickupRegistryStage = null;
            worldPickupRegistryFallback = false;
            fireTrailDiagnosisRecorded = false;
            lightningStakeObserver?.Dispose();
            lightningStakeObserver = null;
            coordinator.worldPathFollower.Reset();
            worldElevatedApproachActive = false;
            worldElevatedApproachGraph = null;
            coordinator.worldLocalNavigator.SetBody(null);
            coordinator.worldNavigationBody = null;
            coordinator.worldTerrainRecent.Clear();
            coordinator.worldTerrainSelectedAt = coordinator.worldTerrainRecoveryUntil = -100;
            if (coordinator.r.world == null)
                return;
            if (ownsWorldPresentation)
            {
                GlobalEventManager.onTeamLevelUp += unavailableTeamLevelSound;
                Run.onRunAmbientLevelUp += unavailableAmbientSound;
                GlobalEventManager.onCharacterLevelUp += unavailableLevelEffect;
                if (coordinator.worldPlayer && coordinator.worldPlayer.inventory)
                    coordinator.worldPlayer.inventory.onItemAddedClient += unavailableItemHighlight;
                ownsWorldPresentation = false;
            }
            if (worldInteraction != null)
                GlobalEventManager.OnInteractionsGlobal -= worldInteraction;
            if (coordinator.worldDriver)
                coordinator.worldDriver.enabled = false;
            if (coordinator.worldPlayer)
                coordinator.worldPlayer.inputBank.interact.PushState(false);
            foreach (var pickup in coordinator.EjectionPickups().ToArray())
                NetworkServer.Destroy(pickup.gameObject);
            foreach (var droplet in coordinator.EjectionDroplets().ToArray())
                NetworkServer.Destroy(droplet.gameObject);
            foreach (var obj in coordinator.worldObjects)
                if (obj)
                    NetworkServer.Destroy(obj);
            if (coordinator.worldStaging)
                PortSession.Destroy(coordinator.worldStaging);
            if (coordinator.worldPause)
                NetworkServer.Destroy(coordinator.worldPause);
            coordinator.CleanupChestEjection();
            if (coordinator.rewardPrefabs != null)
            {
                var prefab = coordinator.rewardPrefabs[0];
                var pools =
                    (Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap").GetValue(null);
                EffectPool pool;
                if (pools.TryGetValue(prefab, out pool))
                {
                    foreach (var effect in pool.InUse.ToArray())
                        pool.ReturnObject(effect);
                    EffectManager.ClearPool(prefab);
                    pool.Kill();
                }
                ((IDictionary)PortSession.RewardField(typeof(EffectManager), "_ShouldUsePooledEffectMap").GetValue(null)).Remove(prefab);
            }
            if (ownsWorldCoinLease && worldCoinLease.IsValid())
            {
                int extra = (int)typeof(AsyncOperationHandle<GameObject>)
                                .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                .GetValue(worldCoinLease) -
                            worldCoinBaseline;
                coordinator.Check(extra >= 0 && extra <= coordinator.worldBarrelConsumers, "Unattributed integrated barrel coin leases");
                for (int i = 0; i < extra; i++)
                    Addressables.Release(worldCoinLease.Result);
                Addressables.Release(worldCoinLease);
                ownsWorldCoinLease = false;
            }
            RestoreWorldHandlers(false);
            RestoreWorldHandlers(true);
            if (coordinator.activeBodyClient != null)
                foreach (short id in new short[] { 52, 55, 57 })
                    coordinator.activeBodyClient.UnregisterHandler(id);
            if (ownsWorldTeleportHandler)
            {
                if (coordinator.activeBodyClient != null)
                    coordinator.activeBodyClient.UnregisterHandler(68);
                if (NetworkServer.active)
                    NetworkServer.UnregisterHandler(68);
                ownsWorldTeleportHandler = false;
            }
            if (coordinator.activeBodyClient != null)
                foreach (var id in coordinator.worldSourceClientHandlerIds)
                    coordinator.activeBodyClient.UnregisterHandler(id);
            coordinator.worldSourceClientHandlerIds.Clear();
            if (NetworkServer.active)
                foreach (var id in worldSourceServerHandlerIds)
                    NetworkServer.UnregisterHandler(id);
            worldSourceServerHandlerIds.Clear();
            worldOfflineNetworkSoundDefs = null;
            if (worldVfxOption != null)
                worldVfxOption.AttemptSetString(priorWorldVfx);
            if (priorWorldXp != null)
                SettingsConVars.cvExpAndMoneyEffects.AttemptSetString(priorWorldXp);
            if (ownsWorldLists && Run.instance)
            {
                if (coordinator.worldAvailableItems != null)
                {
                    coordinator.worldAvailableItems.Clear();
                    coordinator.worldAvailableEquipment.Clear();
                    Run.instance.BuildDropTable();
                    Run.instance.availableItems = previousWorldAvailableItems;
                    Run.instance.availableEquipment = previousWorldAvailableEquipment;
                    ItemMask.Return(coordinator.worldAvailableItems);
                    EquipmentMask.Return(coordinator.worldAvailableEquipment);
                    coordinator.worldAvailableItems = null;
                    coordinator.worldAvailableEquipment = null;
                }
                else
                {
                    Run.instance.availableTier1DropList.Clear();
                    Run.instance.availableTier2DropList.Clear();
                    Run.instance.availableTier3DropList.Clear();
                }
                if (coordinator.worldChestTable)
                    coordinator.worldChestTable.RegenerateDropTable(Run.instance);
                coordinator.Check(Run.instance.availableTier1DropList.Count == 0 && Run.instance.availableTier2DropList.Count == 0 &&
                                      Run.instance.availableTier3DropList.Count == 0 &&
                                      (!coordinator.worldChestTable || coordinator.worldChestTable.GetPickupCount() == 0),
                                  "Integrated loot list/table restore failed");
                ownsWorldLists = false;
            }
            if (ownsWorldMisc)
            {
                RoR2Content.MiscPickups.LunarCoin = null;
                worldLunarCoin.miscPickupIndex = MiscPickupIndex.None;
                foreach (var entry in priorWholeMiscIndices)
                    entry.Key.miscPickupIndex = entry.Value;
                priorWholeMiscIndices.Clear();
                RoR2.ContentManagement.ContentManager._miscPickupDefs = previousWorldMiscContent;
                PortSession.RewardField(typeof(MiscPickupCatalog), "_miscPickupDefs").SetValue(null, previousWorldMiscCatalog);
                MiscPickupCatalog.availability = previousWorldMiscAvailability;
                ownsWorldMisc = false;
                coordinator.Check(MiscPickupCatalog.pickupCount == 0 && !RoR2Content.MiscPickups.LunarCoin,
                                  "Owned lunar definition/catalog restore failed");
            }
            if (worldDropletField != null)
                worldDropletField.SetValue(null, priorWorldDroplet);
            if (ownsWorldDroplet && worldDropletSource)
            {
                Addressables.Release(worldDropletSource);
                ownsWorldDroplet = false;
            }
            if (worldDropletLocator != null)
            {
                Addressables.RemoveResourceLocator(worldDropletLocator);
                worldDropletLocator = null;
            }
            foreach (var material in coordinator.worldMaterials)
                if (material)
                    PortSession.Destroy(material);
            coordinator.Save();
        }
        public void Dispose()
        {
            CleanupIntegratedWorld();
        }
    }
}
