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
using UnityEngine.SceneManagement;

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
    void PrepareNativeSourceInteractableTables(Scene scene, NetworkIdentity[] sourceIdentities, GameObject[] toggleTargets)
    {
        GetWholeInteractableSession().PrepareNativeSourceInteractableTables(scene, sourceIdentities, toggleTargets);
    }
    void RestoreNativeSourceInteractableTables(Scene scene)
    {
        GetWholeInteractableSession().RestoreNativeSourceInteractableTables(scene);
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
        readonly List<NativeSourceDropTableBinding> nativeSourceDropTableBindings = new List<NativeSourceDropTableBinding>();
        bool nativeSourceInteractablePrepareAttempted;
        GameObject priorSpawnPointPrefab;
        AsyncOperationHandle<GameObject> wholeSpawnPointLease;
        bool ownsSpawnPointPrefab;
        public WholeInteractableSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        sealed class NativeSourceDropTableBinding
        {
            public Component component;
            public int componentInstanceId;
            public int gameObjectInstanceId;
            public string bindingName;
            public NativeBorrowedFieldLease<BasicPickupDropTable> lease;
            public Scene scene;
        }
        internal sealed class NativeBorrowedFieldLease<T>
            where T : class
        {
            readonly Func<T> read;
            readonly Action<T> write;
            readonly T original;
            readonly T owned;
            public NativeBorrowedFieldLease(Func<T> read, Action<T> write, T original, T owned)
            {
                this.read = read ?? throw new ArgumentNullException("read");
                this.write = write ?? throw new ArgumentNullException("write");
                this.original = original ?? throw new ArgumentNullException("original");
                this.owned = owned ?? throw new ArgumentNullException("owned");
                if (ReferenceEquals(original, owned))
                    throw new ArgumentException("Borrowed and owned values must differ");
            }
            public void Bind()
            {
                if (!ReferenceEquals(read(), original))
                    throw new InvalidOperationException("Borrowed field changed before bind");
                write(owned);
                if (!ReferenceEquals(read(), owned))
                    throw new InvalidOperationException("Owned field bind did not take effect");
            }
            public void Restore()
            {
                var current = read();
                if (ReferenceEquals(current, owned))
                    write(original);
                else if (!ReferenceEquals(current, original))
                    throw new InvalidOperationException("Foreign replacement blocks borrowed field restore");
                if (!ReferenceEquals(read(), original))
                    throw new InvalidOperationException("Borrowed field restore did not take effect");
            }
        }
        public void PrepareNativeSourceInteractableTables(Scene scene, NetworkIdentity[] sourceIdentities, GameObject[] toggleTargets)
        {
            coordinator.Check(
                coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && scene.IsValid() && scene.isLoaded &&
                    SceneManager.GetActiveScene() == scene && (scene.name == "golemplains" || scene.name == "lakes") &&
                    !nativeSourceInteractablePrepareAttempted && nativeSourceDropTableBindings.Count == 0 && sourceIdentities != null &&
                    sourceIdentities.Length == (scene.name == "lakes" ? 8 : 5) &&
                    sourceIdentities.All(identity => identity && identity.gameObject.scene == scene && !identity.sceneId.IsEmpty()) &&
                    sourceIdentities.Select(identity => identity.sceneId.Value).Distinct().Count() == sourceIdentities.Length &&
                    toggleTargets != null && toggleTargets.Length == (scene.name == "lakes" ? 21 : 3) &&
                    toggleTargets.All(target => target && target.scene == scene) &&
                    toggleTargets.Distinct().Count() == toggleTargets.Length,
                "Native source interactable table preparation is out of scope or was repeated");
            nativeSourceInteractablePrepareAttempted = true;
            var chestConsumers = sourceIdentities.SelectMany(identity => identity.GetComponentsInChildren<ChestBehavior>(true))
                                     .Concat(toggleTargets.SelectMany(target => target.GetComponentsInChildren<ChestBehavior>(true)))
                                     .Where(component => component && component.gameObject.scene == scene)
                                     .Distinct()
                                     .ToArray();
            if (scene.name == "golemplains")
            {
                var wakeConsumers = sourceIdentities.SelectMany(identity => identity.GetComponentsInChildren<WakeController>(true))
                                        .Concat(toggleTargets.SelectMany(target => target.GetComponentsInChildren<WakeController>(true)))
                                        .Where(component => component && component.gameObject.scene == scene)
                                        .Distinct()
                                        .ToArray();
                coordinator.Check(chestConsumers.Length == 0 && wakeConsumers.Length == 0,
                                  "Golemplains source cohort introduced an unsupported chest or Wake reward consumer");
                return;
            }

            var targets = scene.GetRootGameObjects()
                              .SelectMany(root => root.GetComponentsInChildren<Transform>(true))
                              .Where(value => value && value.gameObject.scene == scene && value.name == "Chest2")
                              .Select(value => value.gameObject)
                              .Distinct()
                              .ToArray();
            coordinator.Check(targets.Length == 1 && !targets[0].activeSelf &&
                                  toggleTargets.Any(value => ReferenceEquals(value, targets[0])),
                              "Exact inactive Lakes Chest2 target is missing or ambiguous");
            var chestObject = targets[0];
            var chestIdentity = chestObject.GetComponent<NetworkIdentity>();
            var chests = chestObject.GetComponents<ChestBehavior>();
            coordinator.Check(chestIdentity && chestIdentity.gameObject == chestObject && chestIdentity.sceneId.Value == 1 &&
                                  chests.Length == 1 && chests[0] && chests[0].gameObject == chestObject && chestConsumers.Length == 1 &&
                                  ReferenceEquals(chestConsumers[0], chests[0]),
                              "Lakes source identity cohort contains an unknown ChestBehavior.Roll consumer");
            var chest = chests[0];
            var chestSource = chest.dropTable as BasicPickupDropTable;
            coordinator.Check(chest.dropTable && IsSupportedNativeBasicTable(chestSource, "dtChest2") && Run.instance &&
                                  Run.instance.availableTier1DropList != null && Run.instance.availableTier2DropList != null &&
                                  Run.instance.availableTier3DropList != null,
                              "Lakes Chest2 source table or prepared Run lists changed");
            var wakeRoots =
                sourceIdentities.Where(identity => identity.sceneId.Value == 8 && identity.gameObject.name == "WakeStageEvent").ToArray();
            var wakes = wakeRoots.SelectMany(identity => identity.GetComponentsInChildren<WakeController>(true))
                            .Where(component => component && component.gameObject.scene == scene)
                            .Distinct()
                            .ToArray();
            var allWakeConsumers = sourceIdentities.SelectMany(identity => identity.GetComponentsInChildren<WakeController>(true))
                                       .Concat(toggleTargets.SelectMany(target => target.GetComponentsInChildren<WakeController>(true)))
                                       .Where(component => component && component.gameObject.scene == scene)
                                       .Distinct()
                                       .ToArray();
            coordinator.Check(wakeRoots.Length == 1 && wakes.Length == 1 && allWakeConsumers.Length == 1 &&
                                  ReferenceEquals(wakes[0], allWakeConsumers[0]) && wakes[0].gameObject.name == "WakeAltar" &&
                                  wakes[0].shamanPickupCreator && wakes[0].shamanPickupCreator.gameObject.name == "ShamanPickupCreator" &&
                                  wakes[0].shamanPickupCreator.gameObject.scene == scene &&
                                  wakes[0].shamanPickupCreator.sourceDropTable == null && wakes[0].goldDropTable &&
                                  wakes[0].silverDropTable && wakes[0].bronzeDropTable &&
                                  wakes[0].goldDropTable.GetType() == typeof(BasicPickupDropTable) &&
                                  wakes[0].silverDropTable.GetType() == typeof(BasicPickupDropTable) &&
                                  wakes[0].bronzeDropTable.GetType() == typeof(BasicPickupDropTable) &&
                                  wakes[0].goldDropTable.name == "dtCursedItemTable" && wakes[0].silverDropTable.name == "dtTier2Item" &&
                                  wakes[0].bronzeDropTable.name == "dtTier1Item",
                              "Lakes WakeStageEvent reward source fields differ from the audited cohort");
            var wake = wakes[0];
            var pickers = sourceIdentities.SelectMany(identity => identity.GetComponentsInChildren<PickupPickerController>(true))
                              .Concat(toggleTargets.SelectMany(target => target.GetComponentsInChildren<PickupPickerController>(true)))
                              .Where(component => component && component.gameObject.scene == scene)
                              .Distinct()
                              .ToArray();
            coordinator.Check(
                pickers.Length == 2 &&
                    pickers.Count(component => component.gameObject.name == "Chest2" && !component.excludedItemsDropTable &&
                                               !component.includedItemsDropTable) == 1 &&
                    pickers.Count(component => component.gameObject.name == "Scrapper" && component.excludedItemsDropTable &&
                                               component.excludedItemsDropTable.GetType() == typeof(ExplicitPickupDropTable) &&
                                               component.excludedItemsDropTable.name == "pdtUnscrappableItems" &&
                                               !component.includedItemsDropTable) == 1,
                "Lakes Scrapper/Chest2 picker exclusion-table inventory changed");
            var pickupCreators =
                sourceIdentities.SelectMany(identity => identity.GetComponentsInChildren<CreatePickupsFromDropTable>(true))
                    .Concat(toggleTargets.SelectMany(target => target.GetComponentsInChildren<CreatePickupsFromDropTable>(true)))
                    .Where(component => component && component.gameObject.scene == scene)
                    .Distinct()
                    .ToArray();
            coordinator.Check(pickupCreators.Length == 1 && ReferenceEquals(pickupCreators[0], wake.shamanPickupCreator) &&
                                  pickupCreators[0].sourceDropTable == null,
                              "Lakes Wake reward creator field is not the audited late-bound null slot");
            PrepareNativeBasicTable(scene, chest, chestSource, "dtChest2", "Chest2.ChestBehavior.dropTable",
                                    () => chest.dropTable as BasicPickupDropTable, value => chest.dropTable = value);
            PrepareNativeBasicTable(scene, wake, (BasicPickupDropTable)wake.goldDropTable, "dtCursedItemTable",
                                    "WakeAltar.WakeController.goldDropTable", () => wake.goldDropTable as BasicPickupDropTable,
                                    value => wake.goldDropTable = value);
            PrepareNativeBasicTable(scene, wake, (BasicPickupDropTable)wake.silverDropTable, "dtTier2Item",
                                    "WakeAltar.WakeController.silverDropTable", () => wake.silverDropTable as BasicPickupDropTable,
                                    value => wake.silverDropTable = value);
            PrepareNativeBasicTable(scene, wake, (BasicPickupDropTable)wake.bronzeDropTable, "dtTier1Item",
                                    "WakeAltar.WakeController.bronzeDropTable", () => wake.bronzeDropTable as BasicPickupDropTable,
                                    value => wake.bronzeDropTable = value);
            coordinator.Check(nativeSourceDropTableBindings.Count == 4,
                              "Lakes native Chest2/Wake table ownership did not prepare exactly four bindings");
        }
        void PrepareNativeBasicTable(Scene scene, Component component, BasicPickupDropTable source, string expectedName, string bindingName,
                                     Func<BasicPickupDropTable> read, Action<BasicPickupDropTable> write)
        {
            coordinator.Check(component && component.gameObject.scene == scene && source && ReferenceEquals(read(), source) &&
                                  IsSupportedNativeBasicTable(source, expectedName),
                              "Native source table field changed before cloning");
            string originalConfiguration = JsonUtility.ToJson(source);
            var owned = coordinator.ObjectiveDropTable(source) as BasicPickupDropTable;
            coordinator.Check(owned && !ReferenceEquals(owned, source) && owned.GetType() == typeof(BasicPickupDropTable) &&
                                  owned.name == source.name && JsonUtility.ToJson(owned) == originalConfiguration,
                              "Owned native source table clone did not preserve source configuration");
            int expectedChoices = ExpectedNativeBasicChoices(source, Run.instance);
            coordinator.Check(expectedChoices >= 0 && (expectedName != "dtChest2" || expectedChoices > 0),
                              "Native source table references a missing Run list or Chest2 has no eligible choices");
            owned.RegenerateDropTable(Run.instance);
            coordinator.Check(owned.GetPickupCount() == expectedChoices && JsonUtility.ToJson(source) == originalConfiguration &&
                                  ReferenceEquals(read(), source),
                              "Owned native source table selector differs from current native availability or changed its borrowed source");
            var binding =
                new NativeSourceDropTableBinding { component = component,
                                                   componentInstanceId = component.GetInstanceID(),
                                                   gameObjectInstanceId = component.gameObject.GetInstanceID(),
                                                   bindingName = bindingName,
                                                   scene = scene,
                                                   lease = new NativeBorrowedFieldLease<BasicPickupDropTable>(read, write, source, owned) };
            // Publish the recovery handle before changing the borrowed field.
            nativeSourceDropTableBindings.Add(binding);
            binding.lease.Bind();
        }
        static bool IsSupportedNativeBasicTable(BasicPickupDropTable table, string expectedName)
        {
            if (!table || table.GetType() != typeof(BasicPickupDropTable) || table.name != expectedName || table.IsFilterRequired())
                return false;
            if (expectedName == "dtChest2")
                return table.tier2Weight > 0 && table.tier3Weight > 0;
            if (expectedName == "dtTier1Item")
                return table.tier1Weight > 0;
            if (expectedName == "dtTier2Item")
                return table.tier2Weight > 0;
            if (expectedName == "dtCursedItemTable")
                return table.cursedWeight > 0;
            return false;
        }
        static int ExpectedNativeBasicChoices(BasicPickupDropTable table, Run run)
        {
            if (!table || !run)
                return -1;
            int count = 0;
            if (!AddNativeAvailableChoices(ref count, run.availableTier1DropList, table.tier1Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableTier2DropList, table.tier2Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableTier3DropList, table.tier3Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableBossDropList, table.bossWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableLunarEquipmentDropList, table.lunarEquipmentWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableLunarItemDropList, table.lunarItemWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableLunarCombinedDropList, table.lunarCombinedWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableEquipmentDropList, table.equipmentWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableVoidTier1DropList, table.voidTier1Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableVoidTier2DropList, table.voidTier2Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableVoidTier3DropList, table.voidTier3Weight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableVoidBossDropList, table.voidBossWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableFoodTierDropList, table.foodTierWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availablePowerShapeItemsDropList, table.powerShapesWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableCursedTierDropList, table.cursedWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availableHexTierDropList, table.hexWeight))
                return -1;
            if (!AddNativeAvailableChoices(ref count, run.availablePageTierDropList, table.pageWeight))
                return -1;
            return count;
        }
        static bool AddNativeAvailableChoices(ref int count, List<PickupIndex> list, float weight)
        {
            if (weight <= 0f)
                return true;
            if (list == null)
                return false;
            count += list.Count;
            return true;
        }
        public void RestoreNativeSourceInteractableTables(Scene scene)
        {
            for (int i = nativeSourceDropTableBindings.Count - 1; i >= 0; i--)
            {
                var binding = nativeSourceDropTableBindings[i];
                bool requestedMatchesBound = scene == binding.scene;
                bool requestedSceneValid = scene.IsValid();
                bool requestedSceneLoaded = requestedSceneValid && scene.isLoaded;
                Scene activeScene = SceneManager.GetActiveScene();
                bool activeSceneMatchesRequested = activeScene == scene;
                Component liveComponent = binding.component;
                bool componentAlive = liveComponent;
                GameObject liveOwner = componentAlive ? liveComponent.gameObject : null;
                bool ownerAlive = liveOwner;
                bool ownerSceneMatchesRequested = ownerAlive && liveOwner.scene == scene;
                bool exactOriginalGuard = requestedMatchesBound && requestedSceneValid && requestedSceneLoaded &&
                                          activeSceneMatchesRequested && componentAlive && ownerSceneMatchesRequested;
                int currentComponentId = componentAlive ? liveComponent.GetInstanceID() : 0;
                int currentGameObjectId = ownerAlive ? liveOwner.GetInstanceID() : 0;
                string requestedSceneName = requestedSceneValid ? scene.name : "<invalid>";
                string boundSceneName = binding.scene.IsValid() ? binding.scene.name : "<invalid>";
                string activeSceneName = activeScene.IsValid() ? activeScene.name : "<invalid>";
                string ownerSceneName = ownerAlive && liveOwner.scene.IsValid() ? liveOwner.scene.name : "<unavailable>";
                coordinator.Check(exactOriginalGuard,
                                  NativeSourceBindingWitnessFormatter.Format(
                                      binding.bindingName, binding.componentInstanceId, binding.gameObjectInstanceId, currentComponentId,
                                      currentGameObjectId, requestedMatchesBound, requestedSceneValid, requestedSceneLoaded,
                                      activeSceneMatchesRequested, componentAlive, ownerAlive, ownerSceneMatchesRequested,
                                      requestedSceneName, boundSceneName, activeSceneName, ownerSceneName));
                binding.lease.Restore();
            }
            nativeSourceDropTableBindings.Clear();
            nativeSourceInteractablePrepareAttempted = false;
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

// Pure formatter for the read-only rollback witness. It does not inspect Unity
// objects or alter the lease/restore decision.
internal static class NativeSourceBindingWitnessFormatter
{
    internal static string Format(string bindingName, int boundComponentId, int boundGameObjectId, int currentComponentId,
                                  int currentGameObjectId, bool requestedMatchesBound, bool requestedSceneValid, bool requestedSceneLoaded,
                                  bool activeSceneMatchesRequested, bool componentAlive, bool ownerAlive, bool ownerSceneMatchesRequested,
                                  string requestedSceneName, string boundSceneName, string activeSceneName, string ownerSceneName)
    {
        return string.Format(
            "Borrowed native source table owner lost its exact scene component; binding={0}; " +
                "componentId={1}/{2}; gameObjectId={3}/{4}; requestedMatchesBound={5}; " +
                "requestedSceneValid={6}; requestedSceneLoaded={7}; " +
                "activeSceneMatchesRequested={8}; componentAlive={9}; ownerAlive={10}; " +
                "ownerSceneMatchesRequested={11}; requestedScene={12}; boundScene={13}; " + "activeScene={14}; ownerScene={15}",
            Safe(bindingName), boundComponentId, currentComponentId, boundGameObjectId, currentGameObjectId, requestedMatchesBound,
            requestedSceneValid, requestedSceneLoaded, activeSceneMatchesRequested, componentAlive, ownerAlive, ownerSceneMatchesRequested,
            Safe(requestedSceneName), Safe(boundSceneName), Safe(activeSceneName), Safe(ownerSceneName));
    }

    static string Safe(string value)
    {
        return value ?? "<unavailable>";
    }
}
