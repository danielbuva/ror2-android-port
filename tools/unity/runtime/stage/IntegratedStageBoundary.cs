// Subsystem: stage transport (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareStageTransport, BeginOriginalStage, TransportIntegratedStage (IntegratedStageSession); teardown ReleaseObjectiveStage, CleanupStageTransport (Dispose).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using LabPort.SourceStageLifecycle;
using RoR2;
using RoR2.Navigation;
using RoR2.ContentManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// The user's configured manual boundary is a refusal policy, not a destination selector.
// Keep the production decision pure so the exact-editor fixture exercises the same gate.
public static class ManualMoonBoundary
{
    public const int CompletedTransitions = 4;
    public const float ObservationSeconds = 30f;
    public const string MoonDestination = "moon2";

    public static bool HoldAutomaticProgression(bool enabled, int completedTransitions)
    {
        return enabled && completedTransitions >= CompletedTransitions;
    }

    public static bool RefuseTransport(bool enabled, int completedTransitions, string requestedDestination)
    {
        return enabled && (completedTransitions >= CompletedTransitions ||
                           string.Equals(requestedDestination, MoonDestination, StringComparison.Ordinal));
    }

    public static bool FinishObservation(bool held, float stageElapsed)
    {
        return held && stageElapsed > ObservationSeconds;
    }
}

// Additive converted-stage transport, with a declared continuous-body entry adapter.
// No synthetic stage count, reward, kill, authority, ownership or platform identity.
public sealed partial class PortSession
{
    [Serializable]
    public class IntegratedStageSpec
    {
        public bool moonMission;
        public string[] activeRoots;
        public int missionComponents;
        public string name, bundle, scene, groundGraph, airGraph;
        public int previewCallbacks, mapZoneCount, mapZoneNetworkObjects;
        public string[] mapZoneActiveNames;
        public string[] previewNames, emptyMeshPaths, emptyColliderPaths;
    }
    [Serializable]
    public class StageProgressReport
    {
        public string current, requested, error, scope, actualScene, actualSceneDef;
        public bool transporting, cleaned, activeSceneVerified, goldPortalEntry;
        public int transitions, stageClearCount, countedStages, completedBarrels, completedChests, effectLoansReturned,
            playerSummonsRemoved, retiredActorObservers, retiredModelObservers, retiredCommerceObservers, originalStageBegins;
        public float enteredAt, experienceSettlementSeconds;
        public uint bodyId, masterId, moneyBefore, moneyAfter;
        public ulong experienceBefore, experienceAfter, experienceAtExit, pendingExperienceAtExit;
        public int pendingExperienceAwardsAtExit;
        public int itemsBefore, itemsAfter;
        public List<string> completed = new List<string>();
        public List<ObjectiveReport> completedObjectives = new List<ObjectiveReport>();
        public List<SirenEncounterReport> sirenEncounters = new List<SirenEncounterReport>();
        public List<SirenSourceEntryReport> sirenSourceEntries = new List<SirenSourceEntryReport>();
        public List<StageEntryObservation> entryObservations = new List<StageEntryObservation>();
        public string sirenTransportOperation, sirenTransportPhase, sirenTransportException;
    }
    [Serializable]
    public class SirenSourceEntryReport
    {
        public string scene, status, sourceSceneSha256, error, cleanupError;
        public bool selected, nativeAwakeObserved, controllerSpawned, fullMulticastDispatched, nativeToggleQueueDrained,
            nativeSpawnQueueDrained, exactEggBijection, cleanupDisposed, controllerUnspawned, controllerOriginalInactiveRestored,
            nativeToggleTargetsRestored;
        public uint controllerSceneId, controllerNetworkId;
        public int sourceEggSpawnerCount, nativeActivationChoiceCount, selectedNestCount, observedSpawnerDisableCount,
            mappedEggCount, retiredEggCount, multicastSubscriberCount, nativeToggleTargetCount;
        public uint[] mappedEggNetworkIds;
        public int[] mappedSpawnerInstanceIds;
    }
    [Serializable]
    public class StageEntryObservation
    {
        public float at;
        public Vector3 position, velocity, queuedPositionTarget, bodyPosition, footPosition, corePosition;
        public bool sourceBounds, stable, groundCollider, groundEnabled, motorEnabled, solverEnabled, queuedPosition;
        public string tag, colliderPath, colliderScene;
        public int colliderLayer;
        public string[] mapZones;
    }
    // Shared with the other runtime boundaries.
    string pendingStage;
    int stagePickupBaseline;
    float stageEnteredAt;
    HashSet<GameObject> stageStaticRoots = new HashSet<GameObject>();
    IntegratedStageSession integratedStageSession;
    IntegratedStageSession GetIntegratedStageSession()
    {
        if (integratedStageSession == null)
            integratedStageSession = new IntegratedStageSession(this);
        return integratedStageSession;
    }
    void ObserveStageEntry(CharacterMotor motor, string tag = "settling")
    {
        GetIntegratedStageSession().ObserveStageEntry(motor, tag);
    }
    void PrepareOriginalSurfaceCatalog()
    {
        GetIntegratedStageSession().PrepareOriginalSurfaceCatalog();
    }
    void CleanupOriginalSurfaceCatalog()
    {
        GetIntegratedStageSession().CleanupOriginalSurfaceCatalog();
    }
    void PrepareOriginalDamageMacros()
    {
        GetIntegratedStageSession().PrepareOriginalDamageMacros();
    }
    void PrepareCraftableCatalog()
    {
        GetIntegratedStageSession().PrepareCraftableCatalog();
    }
    void CleanupCraftableCatalog()
    {
        GetIntegratedStageSession().CleanupCraftableCatalog();
    }
    void PrepareStageSpellCatalog()
    {
        GetIntegratedStageSession().PrepareStageSpellCatalog();
    }
    void CleanupStageSpellCatalog()
    {
        GetIntegratedStageSession().CleanupStageSpellCatalog();
    }
    void PrepareStageTransport(SessionConfig cfg)
    {
        GetIntegratedStageSession().PrepareStageTransport(cfg);
    }
    IEnumerator BeginOriginalStage()
    {
        return GetIntegratedStageSession().BeginOriginalStage();
    }
    void ReleaseObjectiveStage()
    {
        GetIntegratedStageSession().ReleaseObjectiveStage();
    }
    internal void BeginNativeFirstStageBoundary()
    {
        GetIntegratedStageSession().BeginNativeStageBoundary();
    }
    internal bool CaptureNativeFirstStage(Stage stage)
    {
        return GetIntegratedStageSession().CaptureNativeStage(stage);
    }
    void TickOriginalStage()
    {
        GetIntegratedStageSession().TickOriginalStage();
    }
    int IntegratedInventoryCount()
    {
        return GetIntegratedStageSession().IntegratedInventoryCount();
    }
    ulong PendingStagePlayerExperience(out int count)
    {
        return GetIntegratedStageSession().PendingStagePlayerExperience(out count);
    }
    IEnumerator TransportIntegratedStage(NovaInputBridge bridge, float simulationBegan)
    {
        return GetIntegratedStageSession().TransportIntegratedStage(bridge, simulationBegan);
    }
    void ReturnIntegratedStageEffects()
    {
        GetIntegratedStageSession().ReturnIntegratedStageEffects();
    }
    IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks()
    {
        return GetIntegratedStageSession().ReturnIntegratedStageEffectsAfterNativeCallbacks();
    }
    void CleanupStageTransport()
    {
        GetIntegratedStageSession().Dispose();
    }
    public int SirenDiagnosticSceneHandle => GetIntegratedStageSession().SirenDiagnosticSceneHandle;
    public bool SirenDiagnosticSceneActive => GetIntegratedStageSession().SirenDiagnosticSceneActive;
    public bool SirenDiagnosticOwnerAttached => GetIntegratedStageSession().SirenDiagnosticOwnerAttached;
    public bool SirenDiagnosticListenerActive => GetIntegratedStageSession().SirenDiagnosticListenerActive;
    public bool SirenNativeEncounterStarted => GetIntegratedStageSession().SirenNativeEncounterStarted;
    public bool SirenDiagnosticStageTransporting => GetIntegratedStageSession().SirenDiagnosticStageTransporting;
    public CharacterBody NearestSirenDiagnosticEgg(Vector3 position) => GetIntegratedStageSession().NearestSirenDiagnosticEgg(position);
    public bool IsCurrentSirenDiagnosticEgg(CharacterBody body) => GetIntegratedStageSession().IsCurrentSirenDiagnosticEgg(body);

    // Create on first use and retain for partial setup, repeated cleanup and stage
    // transport. Dispose preserves transport/catalog cleanup only; objective-stage
    // release and every transport yield remain at their existing call sites.
    sealed partial class IntegratedStageSession : IDisposable
    {
        readonly PortSession coordinator;
        AndroidStageTransport worldTransport;
        GameObject worldTransportHost;
        SessionConfig integratedStageConfig;
        bool transportingStage;
        CursedBookSpellDef[] priorStageSpells;
        string[] priorStageSpellNames;
        ResourceAvailability priorStageSpellAvailability;
        bool ownsStageSpells;
        CraftableDef[] priorCraftableContent;
        object priorCraftableDefs, priorCraftableRecipes, priorIngredientTypes;
        ResourceAvailability priorCraftableAvailability, priorIngredientAvailability;
        bool ownsCraftableCatalog;
        SurfaceDef[] priorSurfaceContent;
        bool ownsSurfaceCatalog;
        static bool originalDamageMacrosReady;
        bool ownsOriginalStage;
        NetworkInstanceId capturedOriginalStageId;
        SourceStageIdentityLifecycle firstStageIdentityLifecycle;
        FirstStageSourceOwners firstStageIdentityOwners;
        SirenEncounterSession sirenEncounter;
        SirenSourceEntrySession sirenSourceEntry;
        bool sirenCleanupRecoveryRequired;
        bool sirenCleanupMayClearRecovery;
        long sirenCleanupRecoveryGeneration;
        public IntegratedStageSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public int SirenDiagnosticSceneHandle => sirenEncounter != null ? sirenEncounter.DiagnosticSceneHandle : 0;
        public bool SirenDiagnosticSceneActive =>
            sirenEncounter != null && sirenEncounter.DiagnosticSceneActive && (coordinator.r.moon == null || !coordinator.r.moon.loaded);
        public bool SirenDiagnosticOwnerAttached => sirenEncounter != null && sirenEncounter.DiagnosticOwnerAttached;
        public bool SirenDiagnosticListenerActive => sirenEncounter != null && sirenEncounter.DiagnosticListenerActive;
        public bool SirenNativeEncounterStarted => sirenEncounter != null && sirenEncounter.NativeEncounterStarted;
        public bool SirenDiagnosticStageTransporting =>
            transportingStage || coordinator.r.stageProgress != null && coordinator.r.stageProgress.transporting;
        public CharacterBody NearestSirenDiagnosticEgg(Vector3 position) => sirenEncounter != null
                                                                                ? sirenEncounter.NearestRevalidatedDiagnosticEgg(position)
                                                                                : null;
        public bool IsCurrentSirenDiagnosticEgg(CharacterBody body) => sirenEncounter != null
                                                                       && sirenEncounter.IsCurrentDiagnosticSourceEgg(body);
        public void ObserveStageEntry(CharacterMotor motor, string tag = "settling")
        {
            var solver = motor.Motor;
            var collider = solver.GroundingStatus.GroundCollider;
            var point = solver.TransientPosition;
            coordinator.r.stageProgress.entryObservations.Add(new StageEntryObservation {
                tag = tag, at = Time.realtimeSinceStartup, sourceBounds = Util.IsPositionWithinMapBounds(point), position = point,
                velocity = motor.velocity,
                queuedPosition =
                    (bool)solver.GetType().GetField("_movePositionDirty", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(solver),
                queuedPositionTarget = (Vector3)solver.GetType()
                                           .GetField("_movePositionTarget", BindingFlags.NonPublic | BindingFlags.Instance)
                                           .GetValue(solver),
                bodyPosition = coordinator.worldPlayer.transform.position, footPosition = coordinator.worldPlayer.footPosition,
                corePosition = coordinator.worldPlayer.corePosition, stable = solver.GroundingStatus.IsStableOnGround,
                groundCollider = collider, groundEnabled = collider && collider.enabled, motorEnabled = motor.enabled,
                solverEnabled = solver.enabled, colliderPath = collider ? PortSession.StageObjectPath(collider.transform) : "none",
                colliderScene = collider ? collider.gameObject.scene.name : "none",
                colliderLayer = collider ? collider.gameObject.layer : -1,
                mapZones = coordinator.stageGeometryScene.GetRootGameObjects()
                               .SelectMany(x => x.GetComponentsInChildren<MapZone>(true))
                               .Where(x => x.gameObject.activeInHierarchy)
                               .Select(x => x.name + "|" + x.triggerType + "|" + x.zoneType + "|layer=" + x.gameObject.layer +
                                            "|inside=" + x.IsPointInsideMapZone(point))
                               .ToArray()
            });
            coordinator.Save();
        }
        public void PrepareOriginalSurfaceCatalog()
        {
            if (coordinator.r.liveCatalogs == null || !coordinator.stageSourceObjects)
                return;
            coordinator.Check(!ownsSurfaceCatalog && SurfaceDefCatalog.surfaceCount == 0, "Unowned original surface definitions");
            var definitions = WholeCatalogComposed.CategoryFamily(AddressablesLabels.surfaceDef, Array.Empty<SurfaceDef>());
            // The Junk provider advertises four extra assets but its source ContentPack
            // deliberately loads only item/equipment/buff/elite labels in an unmodded run.
            coordinator.Check(definitions.Length == 72 && definitions.All(def => def) &&
                                  definitions.Select(def => def.name).Distinct().Count() == definitions.Length,
                              "Original surface-definition family differs from accepted input");
            priorSurfaceContent = ContentManager._surfaceDefs;
            coordinator.Check(priorSurfaceContent == null || priorSurfaceContent.Length == 0, "Unowned surface-definition content array");
            ContentManager._surfaceDefs = definitions;
            ownsSurfaceCatalog = true;
            PortSession.StaticCall(typeof(SurfaceDefCatalog), "Init");
            coordinator.Check(SurfaceDefCatalog.surfaceCount == definitions.Length &&
                                  definitions.All(def => def.surfaceDefIndex != SurfaceDefIndex.Invalid &&
                                                         SurfaceDefCatalog.GetSurfaceDef(def.surfaceDefIndex) == def),
                              "Original surface-definition indices differ");
        }
        public void CleanupOriginalSurfaceCatalog()
        {
            if (!ownsSurfaceCatalog)
                return;
            PortSession.StaticCall(typeof(SurfaceDefCatalog), "SetSurfaceDefs", new object[] { Array.Empty<SurfaceDef>() });
            ContentManager._surfaceDefs = priorSurfaceContent;
            ownsSurfaceCatalog = false;
            coordinator.Check(SurfaceDefCatalog.surfaceCount == 0, "Original surface-definition catalog outlived its owned bundle");
        }
        public void PrepareOriginalDamageMacros()
        {
            if (coordinator.r.liveCatalogs == null || !coordinator.stageSourceObjects)
                return;
            var expected = new[] { "MidasTouch",    "ChefFireDamage",     "ChefBoostedFireDamage", "ChefBoostedIceDamage",
                                   "ChefIceDamage", "VultureHunterLaser", "EngiHealMechanical" };
            if (!originalDamageMacrosReady)
            {
                coordinator.Check(DamageMacroCatalog.macroNameToIndexReadOnly.Count == 0, "Unowned original damage-macro catalog");
                // Original startup scans opted-in assemblies before SystemInitializer runs.
                HG.Reflection.SearchableAttribute.ScanAssembly(typeof(DamageMacroCatalog).Assembly);
                HG.Reflection.SearchableAttribute.ScanAssembly(typeof(EntityStates.Chef.Sear).Assembly);
                var methods = HG.Reflection.SearchableAttribute.GetInstances<DamageMacroMethodAttribute>();
                coordinator.Check(methods != null && methods.Count == expected.Length &&
                                      methods.Cast<DamageMacroMethodAttribute>().All(method => method.target is MethodInfo &&
                                                                                               expected.Contains(method.searchableName)),
                                  "Original damage-macro searchable methods differ from accepted input");
                PortSession.StaticCall(typeof(DamageMacroCatalog), "Initialize");
                originalDamageMacrosReady = true;
            }
            coordinator.Check(DamageMacroCatalog.macroNameToIndexReadOnly.Count == expected.Length &&
                                  expected.All(name => DamageMacroCatalog.macroNameToIndexReadOnly.ContainsKey(name)),
                              "Original damage-macro registration differs");
        }
        public void PrepareCraftableCatalog()
        {
            if (coordinator.r.liveCatalogs == null || !coordinator.stageSourceObjects)
                return;
            coordinator.Check(!ownsCraftableCatalog && PickupCatalog.pickupCount > 0 && IngredientTypeCatalog.ingredientTypeCount == 0 &&
                                  CraftableCatalog.recipeCount == 0 && CraftableCatalog.pickupToIngredientSearchTable.Count == 0 &&
                                  CraftableCatalog.resultToRecipeSearchTable.Count == 0,
                              "Original crafting dependencies have unexpected owners");
            var definitions = WholeCatalogComposed.DefinitionFamily(Array.Empty<CraftableDef>());
            coordinator.Check(definitions.Length > 0 && definitions.All(def => def && def.recipes != null) &&
                                  definitions.Select(def => def.name).Distinct().Count() == definitions.Length,
                              "Original craftable definition closure is incomplete");
            priorCraftableContent = ContentManager._craftableDefs;
            priorCraftableDefs = PortSession.RewardField(typeof(CraftableCatalog), "craftableDefs").GetValue(null);
            priorCraftableRecipes = PortSession.RewardField(typeof(CraftableCatalog), "allRecipes").GetValue(null);
            priorIngredientTypes = PortSession.RewardField(typeof(IngredientTypeCatalog), "ingredientTypeDefs").GetValue(null);
            priorCraftableAvailability = CraftableCatalog.availability;
            priorIngredientAvailability = IngredientTypeCatalog.availability;
            ownsCraftableCatalog = true;
            PortSession.StaticCall(typeof(IngredientTypeCatalog), "Init");
            coordinator.Check(IngredientTypeCatalog.ingredientTypeCount == 5, "Original ingredient type initialization differs");
            ContentManager._craftableDefs = definitions;
            PortSession.StaticCall(typeof(CraftableCatalog), "Init");
            var recipes = (IList)PortSession.RewardField(typeof(CraftableCatalog), "allRecipes").GetValue(null);
            coordinator.Check(CraftableCatalog.recipeCount == definitions.Length &&
                                  recipes.Count == definitions.Sum(def => def.recipes.Length),
                              "Original craftable recipe registration differs");
        }
        public void CleanupCraftableCatalog()
        {
            if (!ownsCraftableCatalog)
                return;
            CraftableCatalog.pickupToIngredientSearchTable.Clear();
            CraftableCatalog.resultToRecipeSearchTable.Clear();
            PortSession.RewardField(typeof(CraftableCatalog), "craftableDefs").SetValue(null, priorCraftableDefs);
            PortSession.RewardField(typeof(CraftableCatalog), "allRecipes").SetValue(null, priorCraftableRecipes);
            ContentManager._craftableDefs = priorCraftableContent;
            CraftableCatalog.availability = priorCraftableAvailability;
            PortSession.RewardField(typeof(IngredientTypeCatalog), "ingredientTypeDefs").SetValue(null, priorIngredientTypes);
            IngredientTypeCatalog.availability = priorIngredientAvailability;
            ownsCraftableCatalog = false;
        }
        public void PrepareStageSpellCatalog()
        {
            if (coordinator.r.liveCatalogs == null || !coordinator.stageSourceObjects)
                return;
            coordinator.Check(!ownsStageSpells && CursedBookSpellCatalog.spellCount == 0, "Unowned original Cursed Book spell catalog");
            var definitions = WholeCatalogComposed.DefinitionFamily(Array.Empty<CursedBookSpellDef>());
            coordinator.Check(definitions.Length > 0 && definitions.All(spell => spell && spell.itemDef && spell.consumedItemDef) &&
                                  definitions.Select(spell => spell.name).Distinct().Count() == definitions.Length,
                              "Original Cursed Book spell closure is incomplete");
            priorStageSpells = ContentManager._cursedBookSpellDefs;
            priorStageSpellNames = CursedBookSpellCatalog.spellNames;
            priorStageSpellAvailability = CursedBookSpellCatalog.availability;
            ContentManager._cursedBookSpellDefs = Array.Empty<CursedBookSpellDef>();
            ownsStageSpells = true;
            PortSession.StaticCall(typeof(CursedBookSpellCatalog), "SetCursedBookSpellDefs", new object[] { definitions });
            CursedBookSpellCatalog.availability.MakeAvailable();
            coordinator.Check(
                CursedBookSpellCatalog.spellCount == definitions.Length &&
                    CursedBookSpellCatalog.allCursedBookSpellDefs.All(spell => spell.itemDef.itemIndex != ItemIndex.None &&
                                                                               spell.consumedItemDef.itemIndex != ItemIndex.None),
                "Original Cursed Book spell registration differs");
        }
        public void CleanupStageSpellCatalog()
        {
            if (!ownsStageSpells)
                return;
            PortSession.StaticCall(typeof(CursedBookSpellCatalog), "SetCursedBookSpellDefs",
                                   new object[] { Array.Empty<CursedBookSpellDef>() });
            ContentManager._cursedBookSpellDefs = priorStageSpells;
            CursedBookSpellCatalog.spellNames = priorStageSpellNames;
            CursedBookSpellCatalog.availability = priorStageSpellAvailability;
            ownsStageSpells = false;
        }
        public void PrepareStageTransport(SessionConfig cfg)
        {
            coordinator.Check(!NetworkManager.singleton && cfg.integratedStages != null && cfg.integratedStages.Length > 0,
                              "Unowned scene transport or missing converted stages");
            integratedStageConfig = cfg;
            coordinator.r.stageProgress = new StageProgressReport {
                current = coordinator.stageGeometryScene.name, bodyId = coordinator.worldPlayer.netId.Value,
                masterId = coordinator.worldPlayer.master.netId.Value,
                scope =
                    "Original Stage.Update, SceneExit and Run.AdvanceStage accounting; additive recovered scene/graph transport. Temporary continuous live-body/master/inventory adapter instead of stock network-user respawn. Stock startup, profiles, unsupported destinations and victory remain unavailable."
            };
            PrepareStageSpellCatalog();
            PrepareCraftableCatalog();
            PrepareOriginalSurfaceCatalog();
            PrepareOriginalDamageMacros();
            worldTransportHost = new GameObject("Owned Android additive scene transport");
            worldTransport = worldTransportHost.AddComponent<AndroidStageTransport>();
            worldTransport.enabled = false;
            coordinator.Check(NetworkManager.singleton == worldTransport, "Original NetworkManager singleton registration missing");
            var online = worldTransport.CanPlayOnline();
            coordinator.Check(online.MoveNext() && online.Current == RoR2.Networking.NetworkManagerSystem.CanPlayOnlineState.No,
                              "Android transport must report online capability unavailable");
            worldTransport.requested = name =>
            {
                coordinator.Check(string.IsNullOrEmpty(coordinator.pendingStage) && !transportingStage,
                                  "Overlapping original stage requests");
                coordinator.pendingStage = name;
                coordinator.r.stageProgress.requested = name;
                coordinator.r.stageProgress.stageClearCount = Run.instance.stageClearCount;
                coordinator.Save();
            };
        }
        public IEnumerator BeginOriginalStage()
        {
            if (coordinator.r.liveCatalogs == null || !coordinator.stageSourceObjects)
                yield break;
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
            {
                var native = BeginNativeFirstStage();
                while (native.MoveNext())
                    yield return native.Current;
                yield break;
            }
            coordinator.Check(coordinator.objectiveStage && !coordinator.objectiveStageHost.activeInHierarchy &&
                                  Stage.instance == coordinator.objectiveStage && NetworkServer.active && Run.instance,
                              "Temporary stage context missing before original handoff");
            var spells = ContentManager.cursedBookSpellDefs;
            coordinator.Check(spells != null, "Original Cursed Book spell array absent before Stage.Start");
            foreach (var spell in spells)
                coordinator.Check(
                    spell && spell.itemDef && spell.consumedItemDef,
                    "Original Cursed Book spell item references missing before Stage.Start: " + (spell ? spell.name : "null spell") +
                        " / item=" + (spell && (bool)spell.itemDef) + " / consumed=" + (spell && (bool)spell.consumedItemDef));
            var source = WholeCatalogComposed.LoadOwnedContent<GameObject>("Assets/WholeGame/RoR2/Base/Core/Network/Stage.prefab");
            var sourceIdentity = source.GetComponent<NetworkIdentity>();
            coordinator.Check(source.name == "Stage" && sourceIdentity && source.GetComponent<Stage>() &&
                                  source.GetComponents<Component>().Length == 3,
                              "Original Stage prefab contract changed");
            if (coordinator.r.sirenSourceEntryDiagnosticAttempt && coordinator.stageGeometryScene.name == SirenEncounterContract.SceneName)
            {
                coordinator.Check(sirenSourceEntry == null && sirenEncounter == null && coordinator.stageSourceObjects &&
                                      !coordinator.r.diagnosticSirenEggInput,
                                  "Siren source-entry attempt requires a fresh source owner and Siren egg input OFF");
                // Both owner preflight and ID-11 activation require the exact current
                // temporary Stage. Retain the owner before its native mutations; this
                // still precedes the one original Run scene callback.
                coordinator.Check(ReferenceEquals(Stage.instance, coordinator.objectiveStage),
                                  "Siren source preflight requires the exact temporary Stage owner");
                sirenSourceEntry = SirenSourceEntrySession.Prepare(
                    coordinator.stageGeometryScene, selected => coordinator.r.stageProgress.sirenSourceEntries.Add(selected));
                coordinator.RetainNativeLifecycleObject(sirenSourceEntry);
                coordinator.Check(ReferenceEquals(Stage.instance, coordinator.objectiveStage),
                                  "Siren source activation requires the exact temporary Stage owner");
                sirenSourceEntry.ActivateAndSpawnController();
            }
            var prior = coordinator.objectiveStageHost;
            PortSession.Call(coordinator.objectiveStage, "OnDisable");
            coordinator.Check(!Stage.instance, "Temporary Stage singleton survived original handoff");
            PortSession.Destroy(prior);
            int begins = 0;
            Action<Stage> onBegin = stage =>
            {
                if (stage == coordinator.objectiveStage)
                    begins++;
            };
            Stage.onServerStageBegin += onBegin;
            try
            {
                Run.instance.OnServerSceneChanged(coordinator.stageGeometryScene.name);
                coordinator.objectiveStage = Stage.instance;
                coordinator.objectiveStageHost = coordinator.objectiveStage ? coordinator.objectiveStage.gameObject : null;
                var identity = coordinator.objectiveStageHost ? coordinator.objectiveStageHost.GetComponent<NetworkIdentity>() : null;
                coordinator.Check(coordinator.objectiveStageHost && coordinator.objectiveStageHost.activeInHierarchy && identity &&
                                      identity.netId.Value != 0 && identity.assetId.Equals(sourceIdentity.assetId),
                                  "Original Run did not spawn the source Stage prefab");
                ownsOriginalStage = true;
                if (sirenSourceEntry != null)
                    sirenSourceEntry.DispatchAfterNativeRunCallback(coordinator.objectiveStage);
                yield return null;
                coordinator.Check(begins == 1 && coordinator.objectiveStage &&
                                      coordinator.objectiveStage.sceneDef == SceneCatalog.GetSceneDefForCurrentScene(),
                                  "Original Stage.Start or server-begin callback did not complete");
                if (sirenSourceEntry != null)
                    sirenSourceEntry.CompleteAfterNaturalSpawnerStart();
                AttachSirenEncounterIfPresent();
                coordinator.r.stageProgress.originalStageBegins++;
                coordinator.Save();
            }
            finally
            {
                Stage.onServerStageBegin -= onBegin;
            }
        }
        IEnumerator BeginNativeFirstStage()
        {
            // Persist the selector as assisted provenance before any native stage
            // events or progression callbacks can observe this run.
            coordinator.IsRunAssisted();
            coordinator.Check(
                coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt &&
                    (coordinator.stageGeometryScene.name == "golemplains" || coordinator.stageGeometryScene.name == "lakes") &&
                    !coordinator.objectiveStage && !Stage.instance && NetworkServer.active && Run.instance &&
                    coordinator.currentStageCombatDeck != null && coordinator.currentStageCombatDeck.nativePool &&
                    coordinator.automaticDeck && coordinator.wholeSceneDirector && !coordinator.wholeSceneDirector.enabled &&
                    coordinator.objectiveHost && !coordinator.r.objective.ready && !coordinator.r.sourceStageLifecycleRecoveryRequired,
                "Native first-stage transaction preconditions changed before identity activation");
            var spells = ContentManager.cursedBookSpellDefs;
            coordinator.Check(spells != null, "Original Cursed Book spell array absent before Stage.Start");
            foreach (var spell in spells)
                coordinator.Check(spell && spell.itemDef && spell.consumedItemDef,
                                  "Original Cursed Book spell item references missing before Stage.Start");
            firstStageIdentityOwners = new FirstStageSourceOwners(coordinator, coordinator.stageGeometryScene);
            SourceStageIdentityLifecycle.PreflightBeforeStageRelease(coordinator.stageGeometryScene, firstStageIdentityOwners);
            firstStageIdentityLifecycle = SourceStageIdentityLifecycle.Create(coordinator.stageGeometryScene, firstStageIdentityOwners);
            bool completed = false;
            int begins = 0;
            Action<Stage> onBegin = stage =>
            {
                if (firstStageIdentityLifecycle != null && firstStageIdentityLifecycle.HasCapturedNativeStage &&
                    ReferenceEquals(stage, firstStageIdentityLifecycle.CapturedNativeStage) &&
                    ReferenceEquals(Stage.instance, firstStageIdentityLifecycle.CapturedNativeStage) &&
                    ReferenceEquals(stage.gameObject, firstStageIdentityLifecycle.CapturedNativeStageHost) &&
                    stage.gameObject.scene == coordinator.stageGeometryScene)
                    begins++;
            };
            try
            {
                firstStageIdentityLifecycle.Prepare();
                Stage.onServerStageBegin += onBegin;
                firstStageIdentityLifecycle.CompleteAtBeginOriginalStage();
                coordinator.Check(
                    firstStageIdentityLifecycle.HasCapturedNativeStage &&
                        ReferenceEquals(coordinator.objectiveStage, firstStageIdentityLifecycle.CapturedNativeStage) &&
                        ReferenceEquals(coordinator.objectiveStageHost, firstStageIdentityLifecycle.CapturedNativeStageHost) &&
                        ownsOriginalStage && capturedOriginalStageId == firstStageIdentityLifecycle.CapturedNativeStageId,
                    "Native Stage capture did not retain the exact proved Stage host and registration ID");
                yield return null;
                coordinator.Check(
                    begins == 1 && coordinator.objectiveStage &&
                        ReferenceEquals(coordinator.objectiveStage, firstStageIdentityLifecycle.CapturedNativeStage) &&
                        coordinator.objectiveStage.isServer && coordinator.objectiveStage.netId == capturedOriginalStageId &&
                        ReferenceEquals(NetworkServer.FindLocalObject(capturedOriginalStageId), coordinator.objectiveStageHost) &&
                        coordinator.objectiveStage.gameObject.scene == coordinator.stageGeometryScene &&
                        coordinator.objectiveStage.sceneDef == SceneCatalog.GetSceneDefForCurrentScene(),
                    "The genuine server Stage-begin callback did not fire exactly once for the spawned source Stage");
                firstStageIdentityLifecycle.ObserveServerStageBegin();
                coordinator.MarkSourceStageLifecycleRecovery(false);
                coordinator.r.stageProgress.originalStageBegins++;
                coordinator.Save();
                completed = true;
            }
            finally
            {
                Stage.onServerStageBegin -= onBegin;
                if (!completed)
                {
                    if (firstStageIdentityLifecycle != null && Stage.instance && ownsOriginalStage)
                    {
                        // Preserve all owning objects if the real Stage or a native
                        // activation queue cannot be retired synchronously.
                        coordinator.MarkSourceStageLifecycleRecovery(true);
                        coordinator.r.cleanup = false;
                        coordinator.r.success = false;
                        coordinator.Save();
                    }
                    else if (firstStageIdentityLifecycle != null && !firstStageIdentityLifecycle.HasCapturedNativeStage && !Stage.instance)
                    {
                        try
                        {
                            firstStageIdentityLifecycle.AbortBeforeBoundary();
                            coordinator.MarkSourceStageLifecycleRecovery(false);
                            firstStageIdentityLifecycle = null;
                            firstStageIdentityOwners = null;
                        }
                        catch
                        {
                            coordinator.MarkSourceStageLifecycleRecovery(true);
                            coordinator.r.cleanup = false;
                            coordinator.r.success = false;
                            coordinator.Save();
                        }
                    }
                    else if (firstStageIdentityLifecycle != null)
                    {
                        // Any partially acquired Stage, including one whose exact
                        // server-map capture failed, remains owned by the recovery gate.
                        coordinator.MarkSourceStageLifecycleRecovery(true);
                        coordinator.r.cleanup = false;
                        coordinator.r.success = false;
                        coordinator.Save();
                    }
                }
            }
        }
        void DisposeNativeFirstStageLifecycle()
        {
            if (firstStageIdentityLifecycle == null)
                return;
            try
            {
                firstStageIdentityLifecycle.Dispose();
                coordinator.Check(firstStageIdentityLifecycle.IsSafeToUnload, "Native first-stage identities were not fully retired");
                firstStageIdentityLifecycle = null;
                firstStageIdentityOwners = null;
            }
            catch (Exception primary)
            {
                coordinator.MarkSourceStageLifecycleRecovery(true);
                coordinator.r.cleanup = false;
                coordinator.r.success = false;
                coordinator.r.error += " Native source lifecycle retained for recovery: " + primary;
                coordinator.Save();
                throw;
            }
        }
        internal void BeginNativeStageBoundary()
        {
            // Run.BeginStage installs Stage.instance before registering its identity.
            // Retain the full session context before crossing that partial-acquisition boundary.
            coordinator.MarkSourceStageLifecycleRecovery(true);
            coordinator.r.cleanup = false;
            coordinator.r.success = false;
        }
        internal bool CaptureNativeStage(Stage stage)
        {
            if (!stage || coordinator.objectiveStage || ownsOriginalStage || !stage.isServer || stage.netId.Value == 0 ||
                stage.gameObject.scene != coordinator.stageGeometryScene ||
                !ReferenceEquals(NetworkServer.FindLocalObject(stage.netId), stage.gameObject))
                return false;
            var identity = stage.GetComponent<NetworkIdentity>();
            if (!identity || identity.netId.Value == 0 || !ReferenceEquals(NetworkServer.FindLocalObject(identity.netId), stage.gameObject))
                return false;
            coordinator.objectiveStage = stage;
            coordinator.objectiveStageHost = stage.gameObject;
            capturedOriginalStageId = identity.netId;
            ownsOriginalStage = true;
            return true;
        }
        public void ReleaseObjectiveStage()
        {
            if (!coordinator.objectiveStage)
                return;
            if (ownsOriginalStage)
            {
                try
                {
                    coordinator.Check(NetworkServer.active && coordinator.objectiveStageHost &&
                                          ReferenceEquals(coordinator.objectiveStage.gameObject, coordinator.objectiveStageHost),
                                      "Original Stage requires its exact live server host for teardown");
                    if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                    {
                        coordinator.Check(capturedOriginalStageId.Value != 0,
                                          "Native Stage teardown requires its captured registration ID");
                        var stage = coordinator.objectiveStage;
                        var host = coordinator.objectiveStageHost;
                        var identity = host.GetComponent<NetworkIdentity>();
                        coordinator.Check(identity && identity.isServer && identity.netId == capturedOriginalStageId &&
                                              ReferenceEquals(NetworkServer.FindLocalObject(capturedOriginalStageId), host),
                                          "Refusing to retire an unowned or replaced native Stage registration");
                        var networkId = capturedOriginalStageId;
                        NetworkServer.UnSpawn(host);
                        coordinator.Check(NetworkServer.active && ReferenceEquals(NetworkServer.FindLocalObject(networkId), null),
                                          "Native Stage identity remained registered after UnSpawn");
                        DestroyImmediate(host);
                        coordinator.Check(!stage && !Stage.instance && !coordinator.objectiveStage,
                                          "Native Stage OnDisable did not synchronously release its singleton");
                    }
                    else
                        NetworkServer.Destroy(coordinator.objectiveStageHost);
                    ownsOriginalStage = false;
                }
                catch (Exception e)
                {
                    if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                    {
                        coordinator.MarkSourceStageLifecycleRecovery(true);
                        coordinator.r.cleanup = false;
                        coordinator.r.success = false;
                        coordinator.r.error += " Native Stage retirement retained for recovery: " + e;
                        coordinator.Save();
                    }
                    throw;
                }
            }
            else
            {
                PortSession.Call(coordinator.objectiveStage, "OnDisable");
                PortSession.Destroy(coordinator.objectiveStageHost);
            }
            coordinator.objectiveStage = null;
            coordinator.objectiveStageHost = null;
        }
        public void TickOriginalStage()
        {
            if (!transportingStage)
                sirenEncounter?.Observe();
            if (ownsOriginalStage)
                return; // Active source prefab receives Unity's own Update.
            if (coordinator.r == null || !coordinator.r.teleporterLoop || !coordinator.objectiveStage || transportingStage ||
                coordinator.r.stageProgress == null || !string.IsNullOrEmpty(coordinator.r.stageProgress.error))
                return;
            try
            {
                PortSession.Call(coordinator.objectiveStage, "Update");
            }
            catch (Exception e)
            {
                coordinator.r.stageProgress.error = e.ToString();
                if (Run.instance)
                    coordinator.r.stageProgress.stageClearCount = Run.instance.stageClearCount;
                coordinator.Save();
            }
        }
        public int IntegratedInventoryCount()
        {
            return ItemCatalog.allItemDefs.Sum(x => coordinator.worldPlayer.inventory.GetItemCountPermanent(x.itemIndex));
        }
        public ulong PendingStagePlayerExperience(out int count)
        {
            coordinator.Check(coordinator.rewardExperience && ExperienceManager.instance == coordinator.rewardExperience,
                              "Original XP manager ownership changed before transport");
            var field = typeof(ExperienceManager).GetField("pendingAwards", BindingFlags.NonPublic | BindingFlags.Instance);
            coordinator.Check(field != null, "Original timed XP queue field unavailable");
            var pending = (IList)field.GetValue(coordinator.rewardExperience);
            coordinator.Check(pending != null, "Original timed XP queue unavailable");
            ulong amount = 0;
            count = 0;
            foreach (var award in pending)
            {
                var type = award.GetType();
                var recipient = type.GetField("recipient", BindingFlags.Public | BindingFlags.Instance);
                var value = type.GetField("awardAmount", BindingFlags.Public | BindingFlags.Instance);
                coordinator.Check(recipient != null && value != null, "Original timed XP award contract changed");
                if ((TeamIndex)recipient.GetValue(award) != TeamIndex.Player)
                    continue;
                amount = checked(amount + (ulong)value.GetValue(award));
                count++;
            }
            return amount;
        }
        public IEnumerator TransportIntegratedStage(NovaInputBridge bridge, float simulationBegan)
        {
            coordinator.Check(!coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt,
                              "The native source-lifecycle diagnostic owns only its first stage; transport turnover is not implemented");
            if (string.IsNullOrEmpty(coordinator.pendingStage))
                yield break;
            coordinator.Check(!ManualMoonBoundary.RefuseTransport(coordinator.r.pauseBeforeMoon,
                                                                    coordinator.r.stageProgress.transitions,
                                                                    coordinator.pendingStage),
                              "Configured manual Moon boundary refused further original stage transport");
            var next = integratedStageConfig.integratedStages.SingleOrDefault(x => x.name == coordinator.pendingStage);
            coordinator.Check(next != null, "Original next destination has no accepted converted content: " + coordinator.pendingStage);
            var report = coordinator.r.stageProgress;
            var run = Run.instance;
            var body = coordinator.worldPlayer;
            var master = body.master;
            var leaving = SceneCatalog.GetSceneDefForCurrentScene();
            coordinator.Check(leaving && leaving.cachedName == coordinator.stageGeometryScene.name,
                              "Original departing scene definition changed");
            bool leavingGold = leaving.cachedName == "goldshores";
            if (leavingGold)
                coordinator.Check(coordinator.r.goldshores != null && coordinator.r.goldshores.exitFinished &&
                                      coordinator.objectiveStage.completed,
                                  "Original Gold Shores mission exit/completion missing before scene transport");
            else
                coordinator.Check(coordinator.r.objective.bossDefeated && coordinator.r.objective.charged &&
                                      coordinator.r.objective.exitFinished && coordinator.objectiveStage.completed,
                                  "Original stage boss/charge/exit/completion missing before scene transport");
            if ((leaving.sceneType == SceneType.Stage || leaving.sceneType == SceneType.UntimedStage) &&
                !leaving.preventStageAdvanceCounter)
                report.countedStages++;
            report.completedBarrels += coordinator.r.world.openedBarrels;
            report.completedChests += coordinator.r.world.openedChests;
            report.completed.Add(leavingGold
                                     ? "goldshores|original-beacons|original-boss|original-exit"
                                     : coordinator.stageGeometryScene.name + "|boss-defeated|natural-charge|" +
                                           (coordinator.r.objective.rewardCollected ? "post-boss-pickup-collected" : "reward-uncollected") +
                                           "|original-exit");
            report.completedObjectives.Add(coordinator.r.objective);
            report.moneyBefore = master.money;
            report.experienceBefore = TeamManager.instance.GetTeamExperience(TeamIndex.Player);
            report.itemsBefore = IntegratedInventoryCount();
            transportingStage = true;
            report.transporting = true;
            coordinator.r.phase = "integrated-stage-transition";
            coordinator.Save();
            bridge.enabled = false;
            body.inputBank.moveVector = Vector3.zero;
            var beetleGland = body.GetComponent<RoR2.Items.BeetleGlandBodyBehavior>();
            bool resumeBeetleGland = beetleGland && beetleGland.enabled;
            if (resumeBeetleGland)
                beetleGland.enabled = false;
            if (coordinator.sourceSlowDirector)
                coordinator.sourceSlowDirector.enabled = false;
            if (coordinator.rewardDirector)
                coordinator.rewardDirector.enabled = false;
            coordinator.PauseStageMapZones();
            var motor = body.characterMotor;
            var solver = motor.Motor;
            solver.enabled = false;
            motor.velocity = Vector3.zero;
            CleanupSirenEncounter();
            coordinator.CleanupStageBossInstances();
            // The native item can summon a player-owned ally outside the stage director.
            // Retire its body/master before replacing the source navigation graph; its
            // original item behavior may naturally resummon after the new stage loads.
            report.playerSummonsRemoved += coordinator.DestroyWholePlayerSummons();
            // Old actors must release their original navigation agents before replacing source graphs.
            coordinator.CleanupDirectorActors();
            foreach (var projectile in PortSession.FindObjectsOfType<RoR2.Projectile.ProjectileController>())
                NetworkServer.Destroy(projectile.gameObject);
            foreach (var instance in coordinator.objectiveSupportInstances)
                if (instance)
                    NetworkServer.Destroy(instance);
            coordinator.objectiveSupportInstances.Clear();
            foreach (var pickup in coordinator.EjectionPickups().ToArray())
                NetworkServer.Destroy(pickup.gameObject);
            foreach (var droplet in coordinator.EjectionDroplets().ToArray())
                NetworkServer.Destroy(droplet.gameObject);
            coordinator.CleanupWholeStageInteractables();
            coordinator.CleanupWorldCommerce();
            foreach (var obj in coordinator.worldObjects)
                if (obj)
                    NetworkServer.Destroy(obj);
            coordinator.worldObjects.Clear();
            coordinator.worldBarrels.Clear();
            coordinator.worldChests.Clear();
            coordinator.CleanupWholeStagePool();
            if (coordinator.objectiveHost)
                NetworkServer.Destroy(coordinator.objectiveHost);
            if (coordinator.objectiveBossDeck)
                PortSession.Destroy(coordinator.objectiveBossDeck);
            ReleaseObjectiveStage();
            DisposeNativeFirstStageLifecycle();
            if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                yield break;
            if (coordinator.sourceSceneInfoRoot)
                coordinator.DeactivateSourceSceneInfo();
            if (coordinator.enemySceneHost)
                PortSession.Destroy(coordinator.enemySceneHost);
            yield return null;
            yield return null;
            // Keep historical values in the plain report, but stop the persistent probe
            // from retaining actor/component wrappers from every completed stage.
            coordinator.Check(coordinator.directorActors.All(actor => !actor.body && !actor.master && !actor.model),
                              "Old stage actor observer retained a live source object");
            foreach (var actor in coordinator.directorActors)
                actor.report.cleaned = true;
            report.retiredActorObservers += coordinator.directorActors.Count;
            coordinator.directorActors.Clear();
            report.retiredModelObservers += coordinator.worldModels.RemoveAll(model => !model);
            report.retiredCommerceObservers += coordinator.commerceOwned.RemoveAll(obj => !obj);
            coordinator.Check(!SceneInfo.instance && !ClassicStageInfo.instance && !Stage.instance && !TeleporterInteraction.instance &&
                                  coordinator.NavigationAgentCount() == 0,
                              "Old original scene context survived transition: scene=" + (bool)SceneInfo.instance +
                                  ", stageInfo=" + (bool)ClassicStageInfo.instance + ", stage=" + (bool)Stage.instance + ", teleporter=" +
                                  (bool)TeleporterInteraction.instance + ", agents=" + coordinator.NavigationAgentCount());
            // Earned XP can still be in the original timed queue after the exit. Let its
            // normal FixedUpdate settle it before taking the strict transport baseline.
            coordinator.r.phase = "integrated-stage-xp-settlement";
            report.experienceAtExit = TeamManager.instance.GetTeamExperience(TeamIndex.Player);
            int pendingCount;
            report.pendingExperienceAtExit = PendingStagePlayerExperience(out pendingCount);
            report.pendingExperienceAwardsAtExit = pendingCount;
            float settlementBegan = Time.realtimeSinceStartup,
                  settlementDeadline = settlementBegan + ExperienceManager.maxOrbTravelTime + 1;
            while (pendingCount > 0 && Time.realtimeSinceStartup < settlementDeadline)
            {
                yield return null;
                PendingStagePlayerExperience(out pendingCount);
            }
            report.experienceSettlementSeconds = Time.realtimeSinceStartup - settlementBegan;
            coordinator.Check(pendingCount == 0, "Original queued XP did not settle before transport");
            report.experienceBefore = TeamManager.instance.GetTeamExperience(TeamIndex.Player);
            coordinator.Check(report.experienceBefore == checked(report.experienceAtExit + report.pendingExperienceAtExit),
                              "Original queued XP settlement accounting failed");
            coordinator.Save();
            var old = coordinator.stageGeometryScene;
            // Native capacity returns use deferred Unity destruction. Finish those
            // actual callbacks before sceneUnloaded synchronously kills the pools.
            var effectReturns = ReturnIntegratedStageEffectsAfterNativeCallbacks();
            while (effectReturns.MoveNext())
                yield return effectReturns.Current;
            coordinator.ReleaseObjectiveOrbCache(); // Original sceneUnloaded clears its map without releasing leases.
            foreach (var root in old.GetRootGameObjects())
                if (!coordinator.stageStaticRoots.Contains(root))
                    SceneManager.MoveGameObjectToScene(root, coordinator.priorClockScene);
            coordinator.Check(SceneManager.SetActiveScene(coordinator.priorClockScene), "Persistent adapter scene missing");
            yield return SceneManager.UnloadSceneAsync(old);
            foreach (var mat in coordinator.stageGeometryMaterials)
                if (mat)
                    PortSession.Destroy(mat);
            coordinator.stageGeometryMaterials.Clear();
            if (coordinator.stageGeometryBundle)
            {
                coordinator.stageGeometryBundle.Unload(true);
                coordinator.stageGeometryBundle = null;
            }
            var geometry = coordinator.LoadStageGeometry(next.bundle, next.previewCallbacks, next);
            while (geometry.MoveNext())
                yield return geometry.Current;
            // Moon activates its original scene objects while loading, after selecting its
            // scene. Unity returns false when reselecting the scene that is already active.
            if (SceneManager.GetActiveScene() != coordinator.stageGeometryScene)
                coordinator.Check(SceneManager.SetActiveScene(coordinator.stageGeometryScene), "Actual next active scene selection failed");
            var actualSceneDef = SceneCatalog.GetSceneDefForCurrentScene();
            report.actualScene = SceneManager.GetActiveScene().name;
            report.actualSceneDef = actualSceneDef ? actualSceneDef.cachedName : "unavailable";
            report.activeSceneVerified = SceneManager.GetActiveScene() == coordinator.stageGeometryScene;
            coordinator.Save();
            coordinator.Check(report.activeSceneVerified && actualSceneDef && actualSceneDef.cachedName == next.name,
                              "Actual next scene catalog/name mismatch");
            SceneInfo info;
            if (next.moonMission)
                info = SceneInfo.instance;
            else if (coordinator.stageSourceObjects)
                info = coordinator.ActivateSourceSceneInfo();
            else
            {
                coordinator.enemySceneHost = new GameObject("Owned original next-stage SceneInfo");
                coordinator.enemySceneHost.SetActive(false);
                SceneManager.MoveGameObjectToScene(coordinator.enemySceneHost, coordinator.stageGeometryScene);
                info = coordinator.enemySceneHost.AddComponent<SceneInfo>();
                typeof(SceneInfo)
                    .GetField("groundNodesAsset", BindingFlags.Instance | BindingFlags.NonPublic)
                    .SetValue(info, coordinator.artifactBundle.LoadAsset<NodeGraph>(next.groundGraph));
                typeof(SceneInfo)
                    .GetField("airNodesAsset", BindingFlags.Instance | BindingFlags.NonPublic)
                    .SetValue(info, coordinator.artifactBundle.LoadAsset<NodeGraph>(next.airGraph));
                coordinator.enemySceneHost.SetActive(true);
            }
            yield return null;
            coordinator.Check(SceneInfo.instance == info && info.groundNodes.GetNodeCount() > 0 && info.airNodes.GetNodeCount() > 0,
                              "Recovered next-stage navigation missing");
            if (coordinator.stageSourceObjects)
            {
                coordinator.r.stage.sourceSceneInfoActive = true;
                coordinator.r.stage.sourceStagePopulationActive =
                    ClassicStageInfo.instance == coordinator.sourceSceneInfoRoot.GetComponent<ClassicStageInfo>() &&
                    ClassicStageInfo.instance.monsterSelection != null;
                coordinator.Check(coordinator.r.stage.sourceStagePopulationActive,
                                  "Original source next-stage population did not initialize");
            }
            // Explicit temporary entry placement; movement afterward is original motor/state/solver.
            report.entryObservations.Clear();
            ObserveStageEntry(motor, "before-original-teleport");
            TeleportHelper.TeleportGameObject(body.gameObject, coordinator.r.stage.spawnPosition);
            solver.CollidableLayers = LayerIndex.world.mask;
            solver.StableGroundLayers = LayerIndex.world.mask;
            solver.SetGroundSolvingActivation(true);
            solver.ForceUnground();
            solver.enabled = true;
            Physics.SyncTransforms();
            ObserveStageEntry(motor, "after-original-teleport");
            coordinator.EnableStageMapZones();
            yield return new WaitForFixedUpdate();
            yield return null;
            float deadline = Time.realtimeSinceStartup + 5, observedAt = Time.realtimeSinceStartup;
            while ((!solver.GroundingStatus.IsStableOnGround || !solver.GroundingStatus.GroundCollider ||
                    solver.GroundingStatus.GroundCollider.gameObject.scene != coordinator.stageGeometryScene) &&
                   Time.realtimeSinceStartup < deadline)
            {
                if (Time.realtimeSinceStartup - observedAt >= .25f)
                {
                    ObserveStageEntry(motor);
                    observedAt = Time.realtimeSinceStartup;
                }
                yield return null;
            }
            ObserveStageEntry(motor, "settled-or-failed");
            coordinator.Check(solver.GroundingStatus.IsStableOnGround && solver.GroundingStatus.GroundCollider &&
                                  solver.GroundingStatus.GroundCollider.gameObject.scene == coordinator.stageGeometryScene,
                              "Next-stage entry does not land on recovered geometry");
            coordinator.Check(Util.IsPositionWithinMapBounds(solver.TransientPosition),
                              "Original source bounds reject grounded next-stage entry");
            coordinator.worldPathFollower.Reset();
            coordinator.worldLocalNavigator.SetBody(null);
            coordinator.worldNavigationBody = null;
            coordinator.worldTerrainRecent.Clear();
            coordinator.worldTerrainSelectedAt = coordinator.worldTerrainRecoveryUntil = -100;
            if (coordinator.automaticDirectorHost)
                PortSession.Destroy(coordinator.automaticDirectorHost);
            yield return null;
            coordinator.sourceSlowDirector = null;
            coordinator.SelectStageCombatDeck(integratedStageConfig, next.name);
            coordinator.automaticDirectorHost =
                coordinator.stageSourceObjects
                    ? coordinator.SourceStageDirectorRoot(false)
                    : PortSession.Instantiate(coordinator.artifactBundle.LoadAsset<GameObject>(integratedStageConfig.enemyDirectorAsset));
            coordinator.rewardDirector = coordinator.automaticDirectorHost.GetComponent<CombatDirector>();
            coordinator.rewardDirector.monsterCards = coordinator.automaticDeck;
            if (coordinator.stageSourceObjects)
            {
                coordinator.sourceSlowDirector.monsterCards = coordinator.automaticDeck;
                coordinator.ObserveSourceSlowDirector(coordinator.worldPlayer);
            }
            else
                coordinator.automaticDirectorHost.AddComponent<DirectorCore>();
            var spawningDirector = coordinator.rewardDirector;
            spawningDirector.onSpawnedServer.AddListener(obj =>
                                                         {
                                                             coordinator.RecordRewardSpawn(obj);
                                                             if (coordinator.currentStageCombatDeck != null)
                                                                 coordinator.RecordStageCombatSpawn(obj, coordinator.worldPlayer,
                                                                                                    spawningDirector);
                                                             else
                                                                 coordinator.RecordDirectorActor(obj, coordinator.worldPlayer);
                                                         });
            coordinator.automaticDirectorHost.SetActive(true);
            coordinator.Check(
                DirectorCore.instance == coordinator.automaticDirectorHost.GetComponent<DirectorCore>() &&
                    coordinator.rewardDirector.enabled && CombatDirector.instancesList.Contains(coordinator.rewardDirector) &&
                    (!coordinator.stageSourceObjects || CombatDirector.instancesList.Contains(coordinator.sourceSlowDirector)),
                "Next-stage original director missing");
            coordinator.worldObjective = 0;
            coordinator.stagePickupBaseline = coordinator.r.world.pickupMessages;
            coordinator.worldLastPress = -1;
            var origin = solver.TransientPosition;
            var chestSource = coordinator.artifactBundle.LoadAsset<GameObject>(integratedStageConfig.chestAsset);
            if (coordinator.r.liveCatalogs == null || next.moonMission)
            {
                foreach (var offset in new[] { new Vector3(2, 0, 0), new Vector3(-2, 0, 0), new Vector3(0, 0, 3), new Vector3(4, 0, 3),
                                               new Vector3(-4, 0, 3), new Vector3(0, 0, -3) })
                {
                    var obj = coordinator.CreateWorldInteractable(
                        coordinator.artifactBundle.LoadAsset<GameObject>(integratedStageConfig.barrelAsset), origin + offset, false);
                    if (obj)
                        coordinator.worldBarrels.Add(obj.GetComponent<BarrelInteraction>());
                }
                foreach (var offset in new[] { new Vector3(5, 0, 0), new Vector3(-5, 0, 0), new Vector3(0, 0, 6), new Vector3(6, 0, 6) })
                {
                    var obj = coordinator.CreateWorldInteractable(chestSource, origin + offset, true);
                    if (obj)
                        coordinator.worldChests.Add(obj.GetComponent<ChestBehavior>());
                }
                coordinator.AddEquipmentBarrel(integratedStageConfig, origin);
                if (!next.moonMission)
                    coordinator.AddWorldChestBreadth(integratedStageConfig, origin);
                coordinator.Check(coordinator.worldBarrels.Count >= 3 && coordinator.worldChests.Count >= 2,
                                  "Recovered next-stage layout lacks walkable interactables");
                coordinator.r.world.barrels = coordinator.worldBarrels.Count;
                coordinator.r.world.chests = coordinator.worldChests.Count;
            }
            if (next.moonMission)
            {
                coordinator.rewardDirector.enabled = false;
                var mission = coordinator.PrepareMoonWorld();
                while (mission.MoveNext())
                    yield return mission.Current;
                coordinator.objectiveStageHost = new GameObject("Owned Moon stage coordinator");
                coordinator.objectiveStageHost.SetActive(false);
                coordinator.objectiveStageHost.AddComponent<NetworkIdentity>();
                coordinator.objectiveStage = coordinator.objectiveStageHost.AddComponent<Stage>();
                typeof(Stage).GetProperty("sceneDef").SetValue(coordinator.objectiveStage, SceneCatalog.GetSceneDefForCurrentScene());
                PortSession.Call(coordinator.objectiveStage, "OnEnable");
            }
            else
            {
                bool gold = next.name == "goldshores";
                if (gold)
                    coordinator.PrepareGoldshoresStage();
                else
                {
                    var objective = coordinator.SpawnStageObjective(integratedStageConfig);
                    while (objective.MoveNext())
                        yield return objective.Current;
                    coordinator.PrepareWorldCommerce(integratedStageConfig, origin);
                }
                bool observeSirenTransport = coordinator.r.sirenSourceEntryDiagnosticAttempt &&
                                             next.name == SirenEncounterContract.SceneName;
                var population = coordinator.PopulateWholeStage();
                if (observeSirenTransport)
                    population = ObserveSirenTransportRoutine("PopulateWholeStage", population);
                while (population.MoveNext())
                    yield return population.Current;
                var stage = BeginOriginalStage();
                if (observeSirenTransport)
                    stage = ObserveSirenTransportRoutine("BeginOriginalStage", stage);
                while (stage.MoveNext())
                    yield return stage.Current;
                if (gold)
                {
                    var goldMission = coordinator.BeginGoldshoresMission();
                    while (goldMission.MoveNext())
                        yield return goldMission.Current;
                }
                else
                    coordinator.PlaceGoldshoresDiagnosticShrine();
            }
            report.moneyAfter = master.money;
            report.experienceAfter = TeamManager.instance.GetTeamExperience(TeamIndex.Player);
            report.itemsAfter = IntegratedInventoryCount();
            coordinator.Check(Run.instance == run && coordinator.worldPlayer == body && body.master == master && master.GetBody() == body &&
                                  body.netId.Value == report.bodyId && master.netId.Value == report.masterId &&
                                  body.hasEffectiveAuthority && report.itemsAfter == report.itemsBefore &&
                                  report.experienceAfter == report.experienceBefore && report.moneyAfter == report.moneyBefore &&
                                  run.stageClearCount == report.countedStages,
                              "Original run/master/authority/inventory/XP/count continuity failed");
            coordinator.stageEnteredAt = Time.realtimeSinceStartup - simulationBegan;
            report.current = next.name;
            report.transitions++;
            report.stageClearCount = run.stageClearCount;
            report.enteredAt = coordinator.stageEnteredAt;
            report.transporting = false;
            coordinator.pendingStage = null;
            transportingStage = false;
            if (resumeBeetleGland && beetleGland)
                beetleGland.enabled = true;
            bridge.enabled = true;
            coordinator.r.phase = "integrated-world-playing";
            coordinator.Save();
        }
        // Retained across a coroutine suspension or refusal. Never reissue a native
        // return from an interrupted/failed batch or discard its exact pool/loan refs.
        sealed class EffectLoanReturnBatch
        {
            public Dictionary<GameObject, EffectPool> map;
            public KeyValuePair<GameObject, EffectPool>[] pools;
            public EffectManagerHelper[][] loans;
            public int count, issuedFrame;
            public bool issued, completed;
        }
        EffectLoanReturnBatch pendingEffectLoanReturns;

        void CheckEffectLoanPoolOwnership(EffectLoanReturnBatch batch)
        {
            var current = (Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap").GetValue(null);
            coordinator.Check(coordinator.ownsIntegratedPools && ReferenceEquals(current, batch.map) && current.Count == batch.pools.Length,
                              "Owned stage effect pool map changed during original return callbacks");
            foreach (var entry in batch.pools)
            {
                EffectPool currentPool;
                coordinator.Check(current.TryGetValue(entry.Key, out currentPool) && ReferenceEquals(currentPool, entry.Value),
                                  "Owned stage effect pool identity changed during original return callbacks");
            }
        }
        EffectLoanReturnBatch BeginIntegratedStageEffectReturns()
        {
            coordinator.Check(coordinator.ownsIntegratedPools, "Stage effect pools have no integrated ownership baseline");
            if (pendingEffectLoanReturns != null)
            {
                CheckEffectLoanPoolOwnership(pendingEffectLoanReturns);
                coordinator.Check(pendingEffectLoanReturns.issued, "Prior owned stage effect return batch did not finish issuing callbacks");
                return pendingEffectLoanReturns;
            }
            var map = (Dictionary<GameObject, EffectPool>)PortSession.RewardField(typeof(EffectManager), "_EffectPrefabMap").GetValue(null);
            var entries = map.ToArray();
            var batch = new EffectLoanReturnBatch { map = map, pools = entries,
                loans = entries.Select(entry => entry.Value.InUse.ToArray()).ToArray(), issuedFrame = Time.frameCount };
            var helpers = new HashSet<EffectManagerHelper>();
            for (int i = 0; i < entries.Length; i++)
                foreach (var effect in batch.loans[i])
                {
                    coordinator.Check(effect && ReferenceEquals(effect.OwningPool, entries[i].Value) && helpers.Add(effect),
                                      "Owned stage effect return snapshot contains an unowned or duplicate loan");
                    batch.count++;
                }
            pendingEffectLoanReturns = batch;
            for (int i = 0; i < entries.Length; i++)
                foreach (var effect in batch.loans[i])
                {
                    CheckEffectLoanPoolOwnership(batch);
                    coordinator.Check(effect && ReferenceEquals(effect.OwningPool, entries[i].Value) && entries[i].Value.InUse.Contains(effect),
                                      "Owned stage effect loan changed before its original return callback");
                    entries[i].Value.ReturnObject(effect);
                }
            batch.issued = true;
            return batch;
        }
        void CompleteIntegratedStageEffectReturns(EffectLoanReturnBatch batch)
        {
            if (batch.completed)
                return;
            CheckEffectLoanPoolOwnership(batch);
            coordinator.Check(batch.issued, "Owned stage effect return callbacks were not fully issued");
            coordinator.Check(batch.map.Values.All(x => x.InUseCount() == 0), "Owned stage effect loans survived original return callbacks");
            for (int i = 0; i < batch.pools.Length; i++)
                foreach (var effect in batch.loans[i])
                    coordinator.Check(!effect || (ReferenceEquals(effect.OwningPool, batch.pools[i].Value) &&
                                                  batch.pools[i].Value.IsObjectInPool(effect) && !effect.gameObject.activeSelf),
                                      "Owned stage effect loan has no original inactive-pool or destroyed retirement witness");
            if (coordinator.r.stageProgress != null)
                coordinator.r.stageProgress.effectLoansReturned += batch.count;
            batch.completed = true;
            pendingEffectLoanReturns = null;
        }
        public void ReturnIntegratedStageEffects()
        {
            // The genuine synchronous onFinishExit listener keeps its existing
            // invocation order and strict immediate empty-pool requirement.
            CompleteIntegratedStageEffectReturns(BeginIntegratedStageEffectReturns());
        }
        public IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks()
        {
            var batch = BeginIntegratedStageEffectReturns();
            if (batch.map.Values.Any(pool => pool.InUseCount() != 0) && Time.frameCount <= batch.issuedFrame)
            {
                // Object.Destroy retires after this Update; yield null resumes on
                // the next actual frame. No repeated returns or arbitrary timeout.
                yield return null;
                coordinator.Check(Time.frameCount > batch.issuedFrame, "Owned stage effect return fence did not cross a Unity frame");
            }
            CompleteIntegratedStageEffectReturns(batch);
        }
        IEnumerator ObserveSirenTransportRoutine(string operation, IEnumerator routine)
        {
            return new SirenSourceEntryObservedRoutine(
                routine, operation,
                (name, phase) =>
                {
                    if (coordinator.r.stageProgress == null)
                        return;
                    coordinator.r.stageProgress.sirenTransportOperation = name;
                    coordinator.r.stageProgress.sirenTransportPhase = phase;
                    try { coordinator.Save(); }
                    catch (Exception) { /* The report witness must not alter the native stage path. */ }
                },
                ReportSirenTransportException);
        }
        void ReportSirenTransportException(string operation, Exception error)
        {
            var report = coordinator.r.stageProgress;
            if (report != null && string.IsNullOrEmpty(report.sirenTransportException))
            {
                report.sirenTransportOperation = operation;
                report.sirenTransportPhase = "exception";
                report.sirenTransportException = error.ToString();
            }
            if (string.IsNullOrEmpty(coordinator.r.error))
                coordinator.r.error = error.ToString();
            var message = "Siren source transport " + operation + " threw: " + error.GetBaseException().Message;
            SirenSourceEntryFailureClassification.PreserveFirstFailure(
                ref coordinator.r.firstFailure, ref coordinator.r.firstFailurePhase, message, "siren-transport-" + operation);
            coordinator.r.success = false;
            try { coordinator.Save(); }
            catch (Exception) { /* Keep the source operation's original exception authoritative. */ }
        }

        void AttachSirenEncounterIfPresent()
        {
            if (coordinator.stageGeometryScene.name != SirenEncounterContract.SceneName)
                return;
            coordinator.Check(sirenEncounter == null && coordinator.stageSourceObjects,
                              "Siren encounter needs its original source scene and a fresh owner");
            if (coordinator.r.sirenSourceEntryDiagnosticAttempt)
                coordinator.Check(sirenSourceEntry != null &&
                                      sirenSourceEntry.CanAdmitOriginalEncounter(coordinator.r.diagnosticSirenEggInput),
                                  "Siren source-entry diagnostic refuses ID-10 admission until exact eggs map, queues drain, and egg input is off");
            sirenEncounter = SirenEncounterSession.Attach(coordinator.stageGeometryScene,
                                                          selected => coordinator.r.stageProgress.sirenEncounters.Add(selected),
                                                          retained => sirenEncounter = retained,
                                                          cleanupFailure =>
                                                          {
                                                              MarkSirenCleanupRecoveryRequired();
                                                          },
                                                          sirenSourceEntry != null ? sirenSourceEntry.CapturedEggIdentities.ToArray() : null);
        }
        void CleanupSirenEncounter()
        {
            try
            {
                SirenEncounterContract.DisposeOwned(ref sirenEncounter, owner => owner.Dispose());
                SirenEncounterContract.DisposeOwned(ref sirenSourceEntry, owner => owner.Dispose());
                if (sirenCleanupRecoveryRequired)
                {
                    SirenEncounterContract.CompleteOwnedRecovery(
                        ref coordinator.r.sourceStageLifecycleRecoveryRequired,
                        coordinator.r.sourceStageLifecycleRecoveryGeneration,
                        sirenCleanupRecoveryGeneration,
                        sirenCleanupMayClearRecovery,
                        HasOtherSourceLifecycleRecoveryOwner());
                    sirenCleanupRecoveryRequired = false;
                    sirenCleanupMayClearRecovery = false;
                }
            }
            catch
            {
                MarkSirenCleanupRecoveryRequired();
                throw;
            }
        }
        void MarkSirenCleanupRecoveryRequired()
        {
            if (!sirenCleanupRecoveryRequired)
                sirenCleanupMayClearRecovery = !coordinator.r.sourceStageLifecycleRecoveryRequired;
            else if (coordinator.r.sourceStageLifecycleRecoveryGeneration != sirenCleanupRecoveryGeneration)
                sirenCleanupMayClearRecovery = false;
            sirenCleanupRecoveryRequired = true;
            sirenCleanupRecoveryGeneration = coordinator.MarkSourceStageLifecycleRecovery(true);
            coordinator.r.cleanup = false;
            coordinator.r.success = false;
        }
        bool HasOtherSourceLifecycleRecoveryOwner()
        {
            return firstStageIdentityLifecycle != null || firstStageIdentityOwners != null ||
                   coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && (Stage.instance || coordinator.objectiveStage);
        }
        public void Dispose()
        {
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && (Stage.instance || coordinator.objectiveStage))
                throw new InvalidOperationException("Native first-stage recovery owner must retire Stage before source identities");
            if (coordinator.r.sourceStageLifecycleRecoveryRequired)
            {
                if (sirenCleanupRecoveryRequired && !HasOtherSourceLifecycleRecoveryOwner())
                    CleanupSirenEncounter();
                if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                    return;
            }
            DisposeNativeFirstStageLifecycle();
            if (coordinator.r.sourceStageLifecycleRecoveryRequired)
                return;
            CleanupSirenEncounter();
            coordinator.PauseStageMapZones();
            coordinator.StopStageMapZoneObservations();
            if (coordinator.sourceSceneInfoRoot)
                coordinator.DeactivateSourceSceneInfo();
            if (worldTransport)
                worldTransport.requested = null;
            if (NetworkManager.singleton == worldTransport)
                NetworkManager.singleton = null;
            if (worldTransportHost)
                PortSession.Destroy(worldTransportHost);
            coordinator.CleanupOriginalGameModes();
            CleanupOriginalSurfaceCatalog();
            CleanupCraftableCatalog();
            CleanupStageSpellCatalog();
            coordinator.pendingStage = null;
            transportingStage = false;
            if (coordinator.r.stageProgress != null)
                coordinator.r.stageProgress.cleaned = true;
        }
    }
}
