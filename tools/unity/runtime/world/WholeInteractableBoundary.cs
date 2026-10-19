// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PopulateWholeStage (WholeInteractableSession); teardown CleanupWholeStageInteractables, CleanupWholeInteractables (Dispose).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;

// Native SceneDirector owns selection, credits, caps, placement and initial map spawns.
// Android owns inactive templates, explicit no-audio presentation and paired resources.
public sealed partial class PortSession
{
    // Shared with the Gold Shores mission and native stage-context selection.
    SceneDirector wholeSceneDirector;
    JObject wholeStageContext;
    WholeInteractableSession wholeInteractableSession;
    WholeInteractableSession GetWholeInteractableSession()
    {
        if (wholeInteractableSession == null)
            wholeInteractableSession = new WholeInteractableSession(this);
        return wholeInteractableSession;
    }
    GameObject WholeInteractableTemplate(GameObject source)
    {
        return GetWholeInteractableSession().WholeInteractableTemplate(source);
    }
    SpawnCard WholeInteractableCard(SpawnCard source)
    {
        return GetWholeInteractableSession().WholeInteractableCard(source);
    }
    void AdaptWholeInteractableSelection(SceneDirector director, DirectorCardCategorySelection selection)
    {
        GetWholeInteractableSession().AdaptWholeInteractableSelection(director, selection);
    }
    void ObserveWholeInteractable(SceneDirector director, GameObject obj, DirectorCard card)
    {
        GetWholeInteractableSession().ObserveWholeInteractable(director, obj, card);
    }
    IEnumerator PopulateWholeStage()
    {
        return GetWholeInteractableSession().PopulateWholeStage();
    }
    IEnumerator StartNativeWholeStagePopulation()
    {
        return GetWholeInteractableSession().StartNativeWholeStagePopulation();
    }
    void CleanupWholeStageInteractables()
    {
        GetWholeInteractableSession().CleanupWholeStageInteractables();
    }
    internal void AbortNativeWholeStagePopulationBeforeStart(bool nativeQueuesEmpty)
    {
        GetWholeInteractableSession().AbortNativePopulationBeforeStart(nativeQueuesEmpty);
    }
    void CleanupWholeInteractables()
    {
        GetWholeInteractableSession().Dispose();
    }

    // Retain the owner across stage turnover and repeated/partial cleanup.
    // Stage teardown keeps the spawn-point lease until the full Dispose boundary.
    sealed class WholeInteractableSession : IDisposable
    {
        readonly PortSession coordinator;
        WholeStagePopulationObservation nativePopulationObservation;
        bool nativePopulationStarted, nativePopulationCompleted, nativeTeleporterPlaced;
        bool nativePopulationSafeAborted;
        readonly Dictionary<GameObject, GameObject> wholeInteractableTemplates = new Dictionary<GameObject, GameObject>();
        readonly Dictionary<SpawnCard, SpawnCard> wholeInteractableCards = new Dictionary<SpawnCard, SpawnCard>();
        readonly List<GameObject> wholePlayerSpawnPoints = new List<GameObject>();
        GameObject priorSpawnPointPrefab;
        AsyncOperationHandle<GameObject> wholeSpawnPointLease;
        bool ownsSpawnPointPrefab;
        public WholeInteractableSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public GameObject WholeInteractableTemplate(GameObject source)
        {
            GameObject owned;
            if (wholeInteractableTemplates.TryGetValue(source, out owned))
                return owned;
            coordinator.Check(source && coordinator.worldStaging && !coordinator.worldStaging.activeInHierarchy,
                              "Original interactable staging unavailable");
            owned = PortSession.Instantiate(source, coordinator.worldStaging.transform);
            owned.name = source.name;
            owned.SetActive(true);
            wholeInteractableTemplates.Add(source, owned);
            coordinator.Check(owned.GetComponentsInChildren<Component>(true).All(value => value),
                              "Original interactable has a missing component: " + source.name);
            foreach (var behaviour in owned.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (behaviour.GetType().Name.StartsWith("Ak", StringComparison.Ordinal))
                {
                    PortSession.DestroyImmediate(behaviour);
                    continue;
                }
                foreach (var field in behaviour.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                {
                    if (field.IsInitOnly || (!field.IsPublic && !Attribute.IsDefined(field, typeof(SerializeField))))
                        continue;
                    var table = field.GetValue(behaviour) as PickupDropTable;
                    if (table)
                    {
                        var copy = coordinator.ObjectiveDropTable(table);
                        coordinator.Check(copy, "Original interactable drop table unavailable: " + table.name);
                        field.SetValue(behaviour, copy);
                    }
                    if (field.FieldType == typeof(GameObject))
                    {
                        var target = field.GetValue(behaviour) as GameObject;
                        GameObject master;
                        if (target && target.GetComponent<CharacterMaster>() &&
                            coordinator.wholeMasterTemplates.TryGetValue(target.name, out master))
                            field.SetValue(behaviour, master);
                    }
                }
            }
            foreach (var sfx in owned.GetComponentsInChildren<SfxLocator>(true))
                foreach (var field in typeof(SfxLocator).GetFields(BindingFlags.Instance | BindingFlags.Public))
                    if (field.FieldType == typeof(string))
                        field.SetValue(sfx, null);
            var shop = owned.GetComponent<MultiShopController>();
            if (shop && shop.terminalPrefab)
                shop.terminalPrefab = WholeInteractableTemplate(shop.terminalPrefab);
            coordinator.PrepareCommerceSymbols(owned);
            coordinator.PresentCommerceModel(owned.transform);
            return owned;
        }
        public SpawnCard WholeInteractableCard(SpawnCard source)
        {
            SpawnCard owned;
            if (wholeInteractableCards.TryGetValue(source, out owned))
                return owned;
            coordinator.Check(source is InteractableSpawnCard && source.prefab, "Original stage has an invalid interactable spawn card");
            owned = PortSession.Instantiate(source);
            owned.name = source.name;
            owned.prefab = WholeInteractableTemplate(source.prefab);
            wholeInteractableCards.Add(source, owned);
            return owned;
        }
        public void AdaptWholeInteractableSelection(SceneDirector director, DirectorCardCategorySelection selection)
        {
            if (director != coordinator.wholeSceneDirector)
                return;
            // Native CopyFrom clones arrays but shares DirectorCard instances with source pools.
            // Unity's serialized clone separates those instances before Android substitutions.
            var owned = PortSession.Instantiate(selection);
            try
            {
                foreach (var card in owned.categories.SelectMany(category => category.cards))
                {
                    card.spawnCard = WholeInteractableCard(card.GetSpawnCard());
                    card.spawnCardReference = new AssetReferenceT<SpawnCard>("");
                }
                selection.categories = owned.categories;
            }
            finally
            {
                PortSession.DestroyImmediate(owned);
            }
        }
        public void ObserveWholeInteractable(SceneDirector director, GameObject obj, DirectorCard card)
        {
            if (director != coordinator.wholeSceneDirector)
                return;
            coordinator.Check(obj && card.GetSpawnCard() && wholeInteractableCards.Values.Contains(card.GetSpawnCard()),
                              "Native interactable has no owned source card");
            coordinator.worldObjects.Add(obj);
            coordinator.commerceOwned.Add(obj);
            var barrel = obj.GetComponent<BarrelInteraction>();
            if (barrel)
            {
                coordinator.worldBarrels.Add(barrel);
                coordinator.worldBarrelConsumers++;
            }
            var chest = obj.GetComponent<ChestBehavior>();
            if (chest)
            {
                coordinator.worldChests.Add(chest);
                if (card.GetSpawnCard().name == "iscEquipmentBarrel")
                    coordinator.worldEquipmentChests.Add(chest);
            }
            var shop = obj.GetComponent<MultiShopController>();
            if (shop)
            {
                coordinator.commerceShops.Add(shop);
                coordinator.r.commerce.shops++;
                foreach (var terminal in shop.terminalGameObjectsList)
                {
                    coordinator.worldObjects.Add(terminal);
                    coordinator.commerceOwned.Add(terminal);
                    coordinator.WatchCommercePurchase(terminal.GetComponent<PurchaseInteraction>());
                }
            }
            var purchase = obj.GetComponent<PurchaseInteraction>();
            if (purchase)
                coordinator.WatchCommercePurchase(purchase);
            if (obj.GetComponent<ShrineChanceBehavior>())
                coordinator.r.commerce.chanceShrines++;
            if (obj.GetComponent<ShrineBloodBehavior>())
                coordinator.r.commerce.bloodShrines++;
            if (obj.GetComponent<ShrineHealingBehavior>())
                coordinator.r.commerce.healingShrines++;
            if (obj.GetComponent<ShrineBossBehavior>())
                coordinator.r.commerce.bossShrines++;
            if (obj.GetComponent<ShrineRestackBehavior>())
                coordinator.r.commerce.restackShrines++;
            coordinator.currentStageCombatDeck.placedInteractables.Add(card.GetSpawnCard().name);
        }
        public IEnumerator PopulateWholeStage()
        {
            if (coordinator.r.liveCatalogs == null)
                yield break;
            bool nativeFirstStage = coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt;
            coordinator.Check(coordinator.wholeStageInfo && ClassicStageInfo.instance == coordinator.wholeStageInfo &&
                                  coordinator.wholeStageContext != null &&
                                  (nativeFirstStage ? !coordinator.objectiveStage : coordinator.objectiveStage && DirectorCore.instance) &&
                                  (nativeFirstStage || coordinator.worldTeleporter || coordinator.stageGeometryScene.name == "goldshores"),
                              "Native stage population context incomplete");
            if (!ownsSpawnPointPrefab)
            {
                var field = typeof(SpawnPoint).GetField("prefab", BindingFlags.Static | BindingFlags.NonPublic);
                priorSpawnPointPrefab = (GameObject)field.GetValue(null);
                coordinator.Check(!priorSpawnPointPrefab, "Foreign player-spawn prefab owner");
                wholeSpawnPointLease = LegacyResourcesAPI.LoadAsync<GameObject>("Prefabs/SpawnPoint");
                ownsSpawnPointPrefab = true;
                yield return wholeSpawnPointLease;
                coordinator.Check(wholeSpawnPointLease.Status == AsyncOperationStatus.Succeeded && wholeSpawnPointLease.Result,
                                  "Original player-spawn prefab unavailable");
                field.SetValue(null, wholeSpawnPointLease.Result);
            }
            if (coordinator.stageSourceObjects)
            {
                var roots = coordinator.stageGeometryScene.GetRootGameObjects().Where(root => root.name == "Director").ToArray();
                bool rootState = roots.Length == 1 && roots[0].scene == coordinator.stageGeometryScene &&
                                 (nativeFirstStage ? !roots[0].activeSelf : roots[0].activeSelf);
                coordinator.Check(rootState && (nativeFirstStage || roots[0] == coordinator.automaticDirectorHost),
                                  "Original source Director owner differs from expected lifecycle state");
                coordinator.wholeSceneDirector = roots[0].GetComponent<SceneDirector>();
                var mapDirectors = roots[0].GetComponents<CombatDirector>();
                coordinator.Check(coordinator.wholeSceneDirector && !coordinator.wholeSceneDirector.enabled && mapDirectors.Length == 2 &&
                                      (nativeFirstStage ||
                                       mapDirectors[0] == coordinator.rewardDirector && mapDirectors[1] == coordinator.sourceSlowDirector),
                                  "Original source Director component contract changed");
                if (nativeFirstStage)
                {
                    coordinator.automaticDirectorHost = roots[0];
                    coordinator.rewardDirector = mapDirectors[0];
                    coordinator.sourceSlowDirector = mapDirectors[1];
                }
                foreach (var property in ((JObject)coordinator.wholeStageContext["director_fields"]).Properties())
                {
                    var field = typeof(SceneDirector).GetField(property.Name, BindingFlags.Public | BindingFlags.Instance);
                    coordinator.Check(field != null && PortSession.Equals(field.GetValue(coordinator.wholeSceneDirector),
                                                                          property.Value.ToObject(field.FieldType)),
                                      "Original source Director field drift: " + property.Name);
                }
                coordinator.Check(nativeFirstStage ? !DirectorCore.instance && !CombatDirector.instancesList.Contains(mapDirectors[0]) &&
                                                         !CombatDirector.instancesList.Contains(mapDirectors[1])
                                                   : DirectorCore.instance == roots[0].GetComponent<DirectorCore>() &&
                                                         CombatDirector.instancesList.Contains(mapDirectors[0]) &&
                                                         CombatDirector.instancesList.Contains(mapDirectors[1]),
                                  "Original source continuous director lifecycle state changed");
                coordinator.Check(coordinator.sourceGameManagerRoot &&
                                      GlobalEventManager.instance == coordinator.sourceGameManagerRoot.GetComponent<GlobalEventManager>(),
                                  "Original source stage event owner is not running");
                coordinator.currentStageCombatDeck.sourceSceneDirector = true;
                coordinator.currentStageCombatDeck.sourceContinuousDirectors = 2;
                coordinator.currentStageCombatDeck.sourceGameManager = true;
            }
            else
            {
                coordinator.wholeSceneDirector = coordinator.automaticDirectorHost.AddComponent<SceneDirector>();
                coordinator.wholeSceneDirector.enabled = false;
                foreach (var property in ((JObject)coordinator.wholeStageContext["director_fields"]).Properties())
                {
                    var field = typeof(SceneDirector).GetField(property.Name, BindingFlags.Public | BindingFlags.Instance);
                    coordinator.Check(field != null, "Original scene director field unavailable: " + property.Name);
                    field.SetValue(coordinator.wholeSceneDirector, property.Value.ToObject(field.FieldType));
                }
            }
            // Ordinary stages reuse the accepted native teleporter; Gold Shores has none.
            if (nativeFirstStage)
            {
                var preparedTemplateTeleporter =
                    coordinator.objectiveHost ? coordinator.objectiveHost.GetComponent<TeleporterInteraction>() : null;
                coordinator.Check(preparedTemplateTeleporter && coordinator.objectiveHost && !coordinator.objectiveHost.activeInHierarchy &&
                                      coordinator.r.objective != null && !coordinator.r.objective.ready,
                                  "Prepared native teleporter template is missing before SceneDirector configuration");
                coordinator.Check(!coordinator.wholeSceneDirector.teleporterInstance &&
                                      coordinator.wholeSceneDirector.teleporterSpawnCard &&
                                      ReferenceEquals(coordinator.wholeSceneDirector.teleporterSpawnCard.prefab, coordinator.objectiveHost),
                                  "Native objective owner did not prepare the exact source teleporter SpawnCard");
            }
            else
                coordinator.wholeSceneDirector.teleporterInstance =
                    coordinator.worldTeleporter ? coordinator.worldTeleporter.gameObject : null;
            var sourceBonuses =
                ((JArray)coordinator.wholeStageContext["bonus_credits"])
                    .Select(row =>
                            {
                                var matches = coordinator.stageGeometryScene.GetRootGameObjects()
                                                  .SelectMany(root => root.GetComponentsInChildren<Transform>(true))
                                                  .Where(value => PortSession.StageObjectPath(value) == (string)row["path"])
                                                  .ToArray();
                                coordinator.Check(matches.Length == 1, "Original stage bonus-credit object is ambiguous: " + row["path"]);
                                return new ClassicStageInfo.BonusInteractibleCreditObject { objectThatGrantsPointsIfEnabled =
                                                                                                matches[0].gameObject,
                                                                                            points = (int)row["points"] };
                            })
                    .ToArray();
            if (coordinator.stageSourceObjects)
            {
                var serialized =
                    coordinator.wholeStageInfo.bonusInteractibleCreditObjects ?? new ClassicStageInfo.BonusInteractibleCreditObject[0];
                coordinator.Check(serialized.Length == sourceBonuses.Length &&
                                      serialized
                                          .Zip(sourceBonuses, (actual, expected) => actual.objectThatGrantsPointsIfEnabled ==
                                                                                        expected.objectThatGrantsPointsIfEnabled &&
                                                                                    actual.points == expected.points)
                                          .All(x => x),
                                  "Original source bonus-credit references differ");
            }
            else
                coordinator.wholeStageInfo.bonusInteractibleCreditObjects = sourceBonuses;
            int credits = coordinator.wholeStageInfo.sceneDirectorInteractibleCredits;
            foreach (var bonus in coordinator.wholeStageInfo.bonusInteractibleCreditObjects)
                if (bonus.objectThatGrantsPointsIfEnabled.activeSelf)
                    credits += bonus.points;
            coordinator.currentStageCombatDeck.initialInteractableCredits = credits;
            coordinator.currentStageCombatDeck.droneDefinitions = DroneCatalog.droneCount;
            coordinator.currentStageCombatDeck.availableDrones =
                DroneCatalog.allDroneDefs.Count(def => Run.instance.IsDroneAvailable(def.droneIndex));
            coordinator.currentStageCombatDeck.pickupDefinitions = PickupCatalog.pickupCount;
            coordinator.currentStageCombatDeck.lunarLoot = Run.instance.availableLunarCombinedDropList.Count;
            if (nativeFirstStage)
            {
                coordinator.Check(nativePopulationObservation == null && !nativePopulationStarted && coordinator.wholeSceneDirector &&
                                      !coordinator.wholeSceneDirector.enabled,
                                  "Native SceneDirector population observer already owned or source director was enabled early");
                nativePopulationObservation = new WholeStagePopulationObservation(this);
                nativePopulationObservation.ArmBeforeNativeStart();
                yield break;
            }
            var populationObservation = new WholeStagePopulationObservation(this);
            populationObservation.ArmBeforeNativeStart();
            try
            {
                PortSession.Call(coordinator.wholeSceneDirector, "Start");
                populationObservation.ObserveNativeStart();
            }
            finally
            {
                populationObservation.Dispose();
            }
            coordinator.currentStageCombatDeck.playerSpawnPoints = wholePlayerSpawnPoints.Count;
            coordinator.r.world.barrels = coordinator.worldBarrels.Count;
            coordinator.r.world.chests = coordinator.worldChests.Count;
            coordinator.Save();
            yield return null;
        }
        public IEnumerator StartNativeWholeStagePopulation()
        {
            coordinator.Check(coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && nativePopulationObservation != null &&
                                  !nativePopulationStarted && coordinator.wholeSceneDirector && !coordinator.wholeSceneDirector.enabled &&
                                  coordinator.objectiveStage && Stage.instance == coordinator.objectiveStage &&
                                  coordinator.objectiveStage.isServer &&
                                  coordinator.objectiveStage.gameObject.scene == coordinator.stageGeometryScene,
                              "Native SceneDirector start requires the real source Stage and an armed observation owner");
            nativePopulationStarted = true;
            bool completed = false;
            try
            {
                coordinator.wholeSceneDirector.enabled = true;
                float deadline = Time.realtimeSinceStartup + 30;
                while (!nativePopulationCompleted && Time.realtimeSinceStartup < deadline)
                    yield return null;
                // onPostPopulateSceneServer runs inside SceneDirector.Start. Defer
                // teleporter readiness checks until Unity has run Teleporter.Start.
                var teleporterStart = coordinator.CompleteNativeTeleporterPlacement(coordinator.wholeSceneDirector);
                while (teleporterStart.MoveNext())
                    yield return teleporterStart.Current;
                var teleporter = coordinator.worldTeleporter;
                coordinator.Check(
                    nativePopulationCompleted && nativeTeleporterPlaced && teleporter && coordinator.objectiveHost &&
                        teleporter.holdoutZoneController && teleporter.bossGroup && Run.instance.nextStageScene && teleporter.isIdle &&
                        teleporter.GetInteractability(coordinator.worldPlayer.GetComponent<Interactor>()) == Interactability.Available &&
                        coordinator.wholeSceneDirector.enabled &&
                        coordinator.wholeSceneDirector.teleporterInstance == coordinator.objectiveHost,
                    "Native SceneDirector did not complete exact teleporter and population callbacks");
                coordinator.r.objective.sourceDuration = teleporter.holdoutZoneController.baseChargeDuration;
                coordinator.r.objective.sourceRadius = teleporter.holdoutZoneController.baseRadius;
                coordinator.r.objective.position = coordinator.objectiveHost.transform.position;
                coordinator.r.objective.ready = true;
                coordinator.Save();
                nativePopulationObservation.Dispose();
                nativePopulationObservation = null;
                coordinator.currentStageCombatDeck.playerSpawnPoints = wholePlayerSpawnPoints.Count;
                coordinator.r.world.barrels = coordinator.worldBarrels.Count;
                coordinator.r.world.chests = coordinator.worldChests.Count;
                coordinator.r.world.ready = coordinator.r.world.authority && coordinator.r.world.lootReady &&
                                            coordinator.r.world.interactionReady && coordinator.r.objective.ready &&
                                            nativePopulationCompleted;
                coordinator.Save();
                completed = true;
            }
            finally
            {
                if (!completed)
                {
                    coordinator.r.sourceStageLifecycleRecoveryRequired = true;
                    coordinator.r.cleanup = false;
                    coordinator.r.success = false;
                    coordinator.r.error += " Native SceneDirector transaction retained for recovery.";
                    coordinator.Save();
                }
            }
        }
        sealed class WholeStagePopulationObservation : IDisposable
        {
            readonly WholeInteractableSession owner;
            HashSet<SpawnPoint> priorSpawnPoints;
            Action<SceneDirector, DirectorCardCategorySelection> onGenerateInteractableCardSelection;
            Action<SceneDirector, GameObject, DirectorCard> onSpawnInteractableServer;
            Action<SceneDirector> onPostPopulateSceneServer;

            public WholeStagePopulationObservation(WholeInteractableSession owner)
            {
                this.owner = owner;
            }

            public void ArmBeforeNativeStart()
            {
                priorSpawnPoints = new HashSet<SpawnPoint>(SpawnPoint.readOnlyInstancesList);
                onGenerateInteractableCardSelection = owner.AdaptWholeInteractableSelection;
                onSpawnInteractableServer = owner.ObserveWholeInteractable;
                SceneDirector.onGenerateInteractableCardSelection += onGenerateInteractableCardSelection;
                SceneDirector.onSpawnInteractableServer += onSpawnInteractableServer;
                if (owner.coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)
                {
                    onPostPopulateSceneServer = ObserveNativePostPopulation;
                    SceneDirector.onPostPopulateSceneServer += onPostPopulateSceneServer;
                }
            }
            void ObserveNativePostPopulation(SceneDirector director)
            {
                owner.coordinator.Check(owner.nativePopulationStarted && ReferenceEquals(director, owner.coordinator.wholeSceneDirector),
                                        "Native post-population event does not belong to the prepared source Director");
                owner.coordinator.Check(owner.coordinator.objectiveHost && director.teleporterInstance == owner.coordinator.objectiveHost &&
                                            owner.coordinator.worldTeleporter ==
                                                owner.coordinator.objectiveHost.GetComponent<TeleporterInteraction>(),
                                        "Native teleporter owner did not adopt the exact placed host before population completed");
                owner.nativeTeleporterPlaced = true;
                owner.nativePopulationCompleted = true;
                owner.coordinator.currentStageCombatDeck.nativeScenePopulation = true;
                owner.coordinator.currentStageCombatDeck.remainingInteractableCredits = director.interactableCredit;
            }
            public void ObserveNativeStart()
            {
                owner.coordinator.currentStageCombatDeck.nativeScenePopulation = true;
                owner.coordinator.currentStageCombatDeck.remainingInteractableCredits =
                    owner.coordinator.wholeSceneDirector.interactableCredit;
            }

            public void Dispose()
            {
                SceneDirector.onGenerateInteractableCardSelection -= onGenerateInteractableCardSelection;
                SceneDirector.onSpawnInteractableServer -= onSpawnInteractableServer;
                if (onPostPopulateSceneServer != null)
                    SceneDirector.onPostPopulateSceneServer -= onPostPopulateSceneServer;
                foreach (var point in SpawnPoint.readOnlyInstancesList)
                    if (!priorSpawnPoints.Contains(point))
                        owner.wholePlayerSpawnPoints.Add(point.gameObject);
            }
        }

        public void AbortNativePopulationBeforeStart(bool nativeQueuesEmpty)
        {
            coordinator.Check(coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && nativePopulationObservation != null &&
                                  LabPort.SourceStageLifecycle.FirstStageDiagnosticGate.MayDisarmPopulationObserver(
                                      nativePopulationStarted, nativePopulationCompleted, true, nativeQueuesEmpty) &&
                                  coordinator.wholeSceneDirector && !coordinator.wholeSceneDirector.enabled,
                              "Only an exact successful pre-boundary rollback may disarm an unstarted population observer");
            nativePopulationObservation.Dispose();
            nativePopulationObservation = null;
            nativePopulationSafeAborted = true;
        }

        public void CleanupWholeStageInteractables()
        {
            if (nativePopulationObservation != null && !nativePopulationCompleted &&
                !(!nativePopulationStarted && nativePopulationSafeAborted))
            {
                coordinator.r.sourceStageLifecycleRecoveryRequired = true;
                coordinator.r.cleanup = false;
                coordinator.r.success = false;
                coordinator.r.error += " Native SceneDirector population did not complete; retaining source owners and dependencies.";
                coordinator.Save();
                throw new InvalidOperationException("Native source SceneDirector owner retained until population recovery completes");
            }
            if (coordinator.wholeSceneDirector)
            {
                if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && nativePopulationCompleted)
                {
                    coordinator.Check(coordinator.wholeSceneDirector.teleporterSpawnCard &&
                                          ReferenceEquals(coordinator.wholeSceneDirector.teleporterInstance, coordinator.objectiveHost),
                                      "Native objective owner lost its exact placed teleporter");
                }
                else if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && !nativePopulationSafeAborted)
                    throw new InvalidOperationException(
                        "Native objective cleanup requires a completed placement or proven pre-start abort");
                else if (coordinator.stageSourceObjects)
                    coordinator.wholeSceneDirector.teleporterInstance = null;
                else
                    PortSession.Destroy(coordinator.wholeSceneDirector);
            }
            coordinator.wholeSceneDirector = null;
            foreach (var point in wholePlayerSpawnPoints)
                if (point)
                    PortSession.Destroy(point);
            wholePlayerSpawnPoints.Clear();
            foreach (var card in wholeInteractableCards.Values)
                if (card)
                    PortSession.Destroy(card);
            wholeInteractableCards.Clear();
            foreach (var template in wholeInteractableTemplates.Values)
                if (template)
                    PortSession.Destroy(template);
            wholeInteractableTemplates.Clear();
        }
        public void Dispose()
        {
            CleanupWholeStageInteractables();
            if (ownsSpawnPointPrefab)
            {
                typeof(SpawnPoint).GetField("prefab", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, priorSpawnPointPrefab);
                if (wholeSpawnPointLease.IsValid())
                    Addressables.Release(wholeSpawnPointLease);
                ownsSpawnPointPrefab = false;
            }
        }
    }
}
