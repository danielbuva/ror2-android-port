// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareDirectorAssets, SpawnAutomaticEnemy, StartOriginalNavigation (AutomaticDirectorSession); teardown CleanupAutomaticDirector (Dispose), then ReleaseDirectorAssets.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Networking;
using RoR2.Navigation;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Supplies measured source contexts; original enabled callbacks select, fund and place the NPC.
public sealed partial class PortSession
{
    [Serializable]
    public class DirectorReport
    {
        public bool automatic, sourceSettings, playerRegistered, originalTarget, preloaded, creditConserved, placement, stopped, cleaned,
            navigationNext, navigationReachable, nativeSourceContextPrepared;
        public int navigationTicks, navigationAgents, navigationAgentPeak;
        public float navigationTime, navigationPathUpdate;
        public string navigationError;
        public int participatingPlayers, livingPlayers, creditSteps, monsterLimit, masterIndex, selectedCardWeight;
        public float seconds, fixedSeconds, scheduledCreditSeconds, creditPeak, creditAfter, spent, spawnDistance, minDistance, maxDistance;
        public Vector3 position;
        public string scope;
        public int spawnLimit, livePeak;
        public float stoppedAt, totalSpent, totalCreditAfter;
        public bool batchCreditConserved;
        public List<DirectorActorReport> actors = new List<DirectorActorReport>();
        public List<StageCombatDeckReport> stageDecks = new List<StageCombatDeckReport>();
    }
    // Shared with stage transport, population, profile/results and actor observations.
    GameObject automaticDirectorHost;
    DirectorCardCategorySelection automaticDeck;
    PlayerCharacterMasterController directorPlayer;
    CombatDirector sourceSlowDirector;
    float automaticDirectorBegan;
    AutomaticDirectorSession automaticDirectorSession;
    AutomaticDirectorSession GetAutomaticDirectorSession()
    {
        if (automaticDirectorSession == null)
            automaticDirectorSession = new AutomaticDirectorSession(this);
        return automaticDirectorSession;
    }
    GameObject SourceStageDirectorRoot(bool holdSlow)
    {
        return GetAutomaticDirectorSession().SourceStageDirectorRoot(holdSlow);
    }
    bool NativeSourceSceneDirectorWasEnabled => GetAutomaticDirectorSession().NativeSourceSceneDirectorWasEnabled;
    DirectorCardCategorySelection NativeOriginalSourceFastDeck => GetAutomaticDirectorSession().NativeOriginalSourceFastDeck;
    DirectorCardCategorySelection NativeOriginalSourceSlowDeck => GetAutomaticDirectorSession().NativeOriginalSourceSlowDeck;
    void ObserveSourceSlowDirector(CharacterBody player)
    {
        GetAutomaticDirectorSession().ObserveSourceSlowDirector(player);
    }
    List<MasterCatalog.MasterIndex> DirectorPreloadList(string original, string updated)
    {
        return GetAutomaticDirectorSession().DirectorPreloadList(original, updated);
    }
    List<MasterCatalog.MasterIndex> DirectorRequestedMasters()
    {
        return GetAutomaticDirectorSession().DirectorRequestedMasters();
    }
    List<MasterCatalog.MasterIndex> DirectorMessageMasters()
    {
        return GetAutomaticDirectorSession().DirectorMessageMasters();
    }
    void StartOriginalNavigation()
    {
        GetAutomaticDirectorSession().StartOriginalNavigation();
    }
    int NavigationAgentCount()
    {
        return GetAutomaticDirectorSession().NavigationAgentCount();
    }
    void FixedUpdate()
    {
        TickTeamIndicatorQueue();
        GetAutomaticDirectorSession().FixedUpdate();
    }
    void ObserveOriginalNavigation()
    {
        GetAutomaticDirectorSession().ObserveOriginalNavigation();
    }
    IEnumerator PrepareDirectorAssets(SessionConfig cfg, IResourceLocation bundle)
    {
        return GetAutomaticDirectorSession().PrepareDirectorAssets(cfg, bundle);
    }
    IEnumerator SpawnAutomaticEnemy(GameObject template, CharacterBody player, SessionConfig cfg)
    {
        return GetAutomaticDirectorSession().SpawnAutomaticEnemy(template, player, cfg);
    }
    IEnumerator PrepareNativeFirstStageDirectorContext(CharacterBody player, SessionConfig cfg)
    {
        return GetAutomaticDirectorSession().PrepareNativeFirstStageDirectorContext(player, cfg);
    }
    void PrepareNativeFirstStagePlayerContext(CharacterBody player, SessionConfig cfg)
    {
        GetAutomaticDirectorSession().PrepareNativeFirstStagePlayerContext(player, cfg);
    }
    void CleanupAutomaticDirector()
    {
        GetAutomaticDirectorSession().Dispose();
    }
    void ReleaseDirectorAssets()
    {
        GetAutomaticDirectorSession().ReleaseDirectorAssets();
    }

    // Create on first use, including Unity ticks before setup, and retain after
    // Dispose: director cleanup precedes the separate asset release at its call site.
    sealed class AutomaticDirectorSession : IDisposable
    {
        readonly PortSession coordinator;
        bool directorPlayerRegistered;
        GameObject[] directorTeamEffects;
        object priorDirectorEliteTiers;
        readonly Dictionary<FieldInfo, object> directorMasterFields = new Dictionary<FieldInfo, object>();
        IDictionary directorMasterMap;
        float automaticDirectorFixedBegan;
        Action ownedNavigationTick;
        BroadNavigationSystem navigationSystem;
        GameObject nativeSourceDirectorRoot;
        bool nativeSourceSceneDirectorWasEnabled;
        DirectorCardCategorySelection nativeOriginalSourceFastDeck, nativeOriginalSourceSlowDeck;
        public AutomaticDirectorSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public bool NativeSourceSceneDirectorWasEnabled => nativeSourceDirectorRoot && nativeSourceSceneDirectorWasEnabled;
        public DirectorCardCategorySelection NativeOriginalSourceFastDeck => nativeOriginalSourceFastDeck;
        public DirectorCardCategorySelection NativeOriginalSourceSlowDeck => nativeOriginalSourceSlowDeck;
        public GameObject SourceStageDirectorRoot(bool holdSlow)
        {
            var roots = coordinator.stageGeometryScene.GetRootGameObjects().Where(root => root.name == "Director").ToArray();
            coordinator.Check(coordinator.stageSourceObjects && roots.Length == 1 && !roots[0].activeSelf,
                              "Original source Director root unavailable");
            var root = roots[0];
            var sceneDirector = root.GetComponent<SceneDirector>();
            var directors = root.GetComponents<CombatDirector>();
            coordinator.Check(sceneDirector && directors.Length == 2 && directors.All(x => x) && root.GetComponent<DirectorCore>(),
                              "Original source Director components changed");
            if (!sceneDirector.enabled)
            {
                coordinator.Check(ReferenceEquals(nativeSourceDirectorRoot, root) && coordinator.sourceSlowDirector == directors[1],
                                  "Disabled source SceneDirector was not suspended by this session");
                if (holdSlow)
                    coordinator.sourceSlowDirector.enabled = false;
                return root;
            }
            coordinator.Check(directors.All(x => x.enabled), "Original source CombatDirector was disabled before ownership");
            // Teleporter ownership is established later; its original Start is invoked
            // after that boundary. The slow director waits for the complete stage deck.
            nativeOriginalSourceFastDeck = directors[0].monsterCards;
            nativeOriginalSourceSlowDeck = directors[1].monsterCards;
            nativeSourceSceneDirectorWasEnabled = sceneDirector.enabled;
            sceneDirector.enabled = false;
            nativeSourceDirectorRoot = root;
            coordinator.sourceSlowDirector = directors[1];
            if (holdSlow)
                coordinator.sourceSlowDirector.enabled = false;
            return root;
        }
        public void ObserveSourceSlowDirector(CharacterBody player)
        {
            var director = coordinator.sourceSlowDirector;
            coordinator.Check(director && director.onSpawnedServer != null, "Original source slow director event unavailable");
            director.onSpawnedServer.AddListener(obj =>
                                                 {
                                                     coordinator.RecordRewardSpawn(obj);
                                                     if (coordinator.currentStageCombatDeck != null)
                                                         coordinator.RecordStageCombatSpawn(obj, player, director);
                                                     else
                                                         coordinator.RecordDirectorActor(obj, player);
                                                 });
        }
        // The update separates server bookkeeping from the client preload cache. Read
        // the measured server lists in either input; never substitute client readiness.
        public List<MasterCatalog.MasterIndex> DirectorPreloadList(string original, string updated)
        {
            var flags = BindingFlags.Public | BindingFlags.Static;
            var type = typeof(NetworkPreloadManager);
            var field = type.GetField(original, flags) ?? type.GetField(updated, flags);
            coordinator.Check(field != null && field.FieldType == typeof(List<MasterCatalog.MasterIndex>),
                              "Original server preload-list contract missing: " + original + " / " + updated);
            var value = (List<MasterCatalog.MasterIndex>)field.GetValue(null);
            coordinator.Check(value != null, "Original server preload list is null");
            return value;
        }
        public List<MasterCatalog.MasterIndex> DirectorRequestedMasters()
        {
            return DirectorPreloadList("previouslyRequestedMasters", "previouslyRequestedMastersServer");
        }
        public List<MasterCatalog.MasterIndex> DirectorMessageMasters()
        {
            return DirectorPreloadList("requestMasterList", "masterListForMessageGeneration");
        }
        public void StartOriginalNavigation()
        {
            coordinator.Check(!RoR2Application.instance || !RoR2Application.instance.isActiveAndEnabled,
                              "Original application already schedules navigation");
            navigationSystem = RoR2.CharacterAI.BaseAI.nodeGraphNavigationSystem;
            var systems = (IList)RewardField(typeof(BroadNavigationSystem), "instancesList").GetValue(null);
            coordinator.Check(systems.Count == 1 && ReferenceEquals(systems[0], navigationSystem) && NavigationAgentCount() == 0,
                              "Unexpected pre-existing navigation agents/system");
            ownedNavigationTick = (Action)Delegate.CreateDelegate(
                typeof(Action), typeof(BroadNavigationSystem).GetMethod("StaticUpdate", BindingFlags.NonPublic | BindingFlags.Static));
        }
        public int NavigationAgentCount()
        {
            return navigationSystem == null ? 0
                                            : (int)typeof(BroadNavigationSystem)
                                                  .GetProperty("agentCount", BindingFlags.NonPublic | BindingFlags.Instance)
                                                  .GetValue(navigationSystem, null);
        }
        public void FixedUpdate()
        {
            coordinator.TickOriginalRunClock();
            coordinator.TickWorldEquipment();
            coordinator.TickIntegratedResults();
            if (ownedNavigationTick == null)
                return;
            try
            {
                ownedNavigationTick();
                coordinator.r.director.navigationTicks++;
            }
            catch (Exception e)
            {
                coordinator.r.director.navigationError = e.ToString();
                ownedNavigationTick = null;
                coordinator.Save();
            }
        }
        public void ObserveOriginalNavigation()
        {
            if (coordinator.r.director == null || navigationSystem == null)
                return;
            coordinator.r.director.navigationAgents = NavigationAgentCount();
            coordinator.r.director.navigationAgentPeak =
                Math.Max(coordinator.r.director.navigationAgentPeak, coordinator.r.director.navigationAgents);
            coordinator.r.director.navigationTime = (float)typeof(BroadNavigationSystem)
                                                        .GetField("localTime", BindingFlags.NonPublic | BindingFlags.Instance)
                                                        .GetValue(navigationSystem);
            coordinator.Check(string.IsNullOrEmpty(coordinator.r.director.navigationError),
                              "Original navigation scheduler failed: " + coordinator.r.director.navigationError);
            if (coordinator.enemyAI)
            {
                var output = coordinator.enemyAI.broadNavigationAgent.output;
                coordinator.r.director.navigationNext |= output.nextPosition.HasValue;
                coordinator.r.director.navigationReachable |= output.targetReachable;
                coordinator.r.director.navigationPathUpdate = output.lastPathUpdate;
            }
        }
        public IEnumerator PrepareDirectorAssets(SessionConfig cfg, IResourceLocation bundle)
        {
            coordinator.Check(cfg.enemyDirectorTeamKeys.Length == 2 && cfg.enemyDirectorTeamAssets.Length == 2,
                              "Measured director team asset count");
            var names = new[] { "Prefabs/Effects/LevelUpEffect", "Prefabs/Effects/LevelUpEffectEnemy" };
            for (int i = 0; i < 2; i++)
            {
                string key;
                coordinator.Check(LegacyResourcesAPI.GetGuid(names[i], out key) && key == cfg.enemyDirectorTeamKeys[i],
                                  "Original team effect legacy identity");
                coordinator.rewardLocator.Add(key,
                                              new ResourceLocationBase(key, cfg.enemyDirectorTeamAssets[i],
                                                                       typeof(BundledAssetProvider).FullName, typeof(GameObject), bundle));
            }
            // Natural TeamCatalog constructor retains its real limit, effect and sound contracts.
            var player = TeamCatalog.GetTeamDef(TeamIndex.Player);
            var monster = TeamCatalog.GetTeamDef(TeamIndex.Monster);
            // The static constructor runs only once. Owned teardown releases and clears its
            // original provider leases; a restarted session must acquire those exact assets again.
            if (coordinator.r.session > 1)
            {
                var teams = Enum.GetValues(typeof(TeamIndex))
                                .Cast<TeamIndex>()
                                .Where(team => team >= TeamIndex.Player && team < TeamIndex.Count)
                                .ToArray();
                coordinator.Check(teams.All(x => !TeamCatalog.GetTeamDef(x).levelUpEffect),
                                  "Previous session retained team effect ownership");
                foreach (var team in teams)
                    TeamCatalog.GetTeamDef(team).levelUpEffect =
                        LegacyResourcesAPI.Load<GameObject>(names[team == TeamIndex.Player ? 0 : 1]);
            }
            directorTeamEffects = new[] { player.levelUpEffect, monster.levelUpEffect };
            coordinator.Check(directorTeamEffects.All(x => x) && directorTeamEffects[0].name == "LevelUpEffect" &&
                                  directorTeamEffects[1].name == "LevelUpEffectEnemy" && monster.softCharacterLimit == 40,
                              "Original team limit/effect contracts missing");
            yield return null;
        }
        // Native global initialization is kept separate from fixture deck/host activation.
        // This preserves the accepted CombatDirector.Init and async elite-tier wait order.
        IEnumerator PrepareNativeDirectorEliteTiers()
        {
            priorDirectorEliteTiers = RewardField(typeof(CombatDirector), "eliteTiers").GetValue(null);
            coordinator.Check(priorDirectorEliteTiers == null, "Existing original elite tiers");
            StaticCall(typeof(CombatDirector), "Init");
            // Current original Init fills tier entries through asynchronous asset collections.
            float eliteDeadline = Time.realtimeSinceStartup + 20;
            while (((Array)RewardField(typeof(CombatDirector), "eliteTiers").GetValue(null)).Cast<object>().Any(tier => tier == null) &&
                   Time.realtimeSinceStartup < eliteDeadline)
                yield return null;
            coordinator.Check(
                ((Array)RewardField(typeof(CombatDirector), "eliteTiers").GetValue(null)).Cast<object>().All(tier => tier != null),
                "Original elite tier initialization incomplete");
            yield break;
        }

        // Own the full master table, local participant registration, and run clock setup.
        // The current catalog builder requires its authored template as an input; this helper
        // deliberately does not select a one-card deck, activate a director, or spawn actors.
        MasterCatalog.MasterIndex PrepareNativeDirectorCatalogAndPlayerContext(GameObject template, CharacterBody player, SessionConfig cfg)
        {
            foreach (var name in new[] { "masterPrefabs", "masterPrefabMasterComponents", "aiMasterPrefabs", "masterNames" })
            {
                var field = RewardField(typeof(MasterCatalog), name);
                var old = field.GetValue(null);
                coordinator.Check(old == null || ((Array)old).Length == 0, "Existing master catalog " + name);
                directorMasterFields[field] = old;
            }
            directorMasterMap = (IDictionary)RewardField(typeof(MasterCatalog), "nameToIndexMap").GetValue(null);
            coordinator.Check(directorMasterMap.Count == 0 && DirectorRequestedMasters().Count == 0 && DirectorMessageMasters().Count == 0,
                              "Existing preload/catalog state");
            if (cfg.teleporterLoop)
                coordinator.PrepareObjectiveActorTemplates(cfg);
            var adaptedMasters = (template ? new[] { template } : Array.Empty<GameObject>())
                                     .Concat(coordinator.objectiveTemplates.Where(x => x.GetComponent<CharacterMaster>()))
                                     .ToArray();
            var masters = adaptedMasters;
            if (coordinator.r.liveCatalogs != null)
            {
                var originals =
                    WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.characterMaster, new GameObject[0]);
                var byName = adaptedMasters.ToDictionary(value => value.name, StringComparer.Ordinal);
                coordinator.Check(byName.Keys.All(name => originals.Any(value => value.name == name)),
                                  "Owned adapted master absent from original provider category");
                masters = coordinator.PrepareWholeMasterTemplates(originals, adaptedMasters);
                coordinator.r.liveCatalogs.masters = masters.Length;
                coordinator.r.liveCatalogs.adaptedMasters =
                    masters.Count(value => coordinator.objectiveTemplates.Contains(value) || adaptedMasters.Contains(value));
            }
            StaticCall(typeof(MasterCatalog), "SetEntries", new object[] { masters });
            var catalogTemplate = template;
            if (!catalogTemplate)
            {
                var source = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyMasterAsset);
                coordinator.Check(source && coordinator.wholeMasterTemplates.TryGetValue(source.name, out catalogTemplate) &&
                                      catalogTemplate,
                                  "Owned source master adaptation missing from native catalog");
            }
            var index = MasterCatalog.FindMasterIndex(catalogTemplate);
            coordinator.Check(MasterCatalog.GetMasterPrefab(index) == catalogTemplate, "Original master catalog identity");
            coordinator.r.director.masterIndex = (int)index;
            PrepareDirectorPlayerContext(player);
            coordinator.r.director.playerRegistered = PlayerCharacterMasterController.instances.Count == 1 &&
                                                      PlayerCharacterMasterController.instances[0] == coordinator.directorPlayer;
            coordinator.Check(coordinator.r.director.playerRegistered, "Original player registration missing");
            coordinator.r.director.participatingPlayers = Run.instance.participatingPlayerCount;
            coordinator.r.director.livingPlayers = Run.instance.livingPlayerCount;
            coordinator.Check(coordinator.r.director.participatingPlayers == PlayerCharacterMasterController.instances.Count &&
                                  coordinator.r.director.participatingPlayers == 1 &&
                                  coordinator.r.director.livingPlayers == PlayerCharacterMasterController.GetPlayersWithBodiesCount() &&
                                  coordinator.r.director.livingPlayers == 1 && !coordinator.directorPlayer.isConnected &&
                                  !coordinator.directorPlayer.networkUser,
                              "Original participant/body counts or unavailable user contract changed");
            coordinator.StartOriginalRunClock();
            return index;
        }

        // Results need this original controller before their own PlayerStatsComponent.Awake.
        // Native first-stage setup borrows only this mandatory context early; catalogs,
        // elite initialization, director activation and the Run clock keep their existing order.
        public void PrepareNativeFirstStagePlayerContext(CharacterBody player, SessionConfig cfg)
        {
            var master = player ? player.master : null;
            coordinator.Check(
                coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && cfg.integratedWorld && cfg.teleporterLoop &&
                    coordinator.stageSourceObjects && coordinator.stageGeometryScene.IsValid() &&
                    (coordinator.stageGeometryScene.name == "golemplains" || coordinator.stageGeometryScene.name == "lakes") &&
                    NetworkServer.active && Run.instance && player && master && player.isServer && master.isServer &&
                    player.netId.Value != 0 && master.netId.Value != 0 && master.hasBody && master.GetBody() == player &&
                    ReferenceEquals(NetworkServer.FindLocalObject(player.netId), player.gameObject) &&
                    ReferenceEquals(NetworkServer.FindLocalObject(master.netId), master.gameObject),
                "Native first-stage player context requires the exact live server body and master");
            PrepareDirectorPlayerContext(player);
        }

        void PrepareDirectorPlayerContext(CharacterBody player)
        {
            var master = player ? player.master : null;
            var controller = master ? master.GetComponent<PlayerCharacterMasterController>() : null;
            coordinator.Check(controller && !controller.gameObject.activeInHierarchy && !controller.networkUser,
                              "Measured inactive local player controller scope changed");
            if (directorPlayerRegistered)
            {
                // The early native results prerequisite and later full catalog setup
                // must share one exact registration and its native subscriptions.
                coordinator.Check(ReferenceEquals(coordinator.directorPlayer, controller) && controller.master == master &&
                                      PlayerCharacterMasterController.instances.Count == 1 &&
                                      ReferenceEquals(PlayerCharacterMasterController.instances[0], controller),
                                  "Owned player controller registration changed before adoption");
                return;
            }
            coordinator.Check((!coordinator.directorPlayer || ReferenceEquals(coordinator.directorPlayer, controller)) &&
                                  PlayerCharacterMasterController.instances.Count == 0,
                              "Unowned local player controller registration");
            coordinator.directorPlayer = controller;
            if (!controller.master)
                Call(controller, "Awake");
            coordinator.Check(controller.master == master, "Original player controller master binding");
            // OnEnable can throw after adding the instance; keep its exact owner for cleanup.
            directorPlayerRegistered = true;
            Call(controller, "OnEnable");
            coordinator.Check(PlayerCharacterMasterController.instances.Count == 1 &&
                                  ReferenceEquals(PlayerCharacterMasterController.instances[0], controller),
                              "Original player registration missing or duplicated");
        }

        public IEnumerator PrepareNativeFirstStageDirectorContext(CharacterBody player, SessionConfig cfg)
        {
            coordinator.Check(
                coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && cfg.integratedWorld && cfg.teleporterLoop &&
                    coordinator.stageSourceObjects && coordinator.stageGeometryScene.IsValid() &&
                    (coordinator.stageGeometryScene.name == "golemplains" || coordinator.stageGeometryScene.name == "lakes") &&
                    !coordinator.automaticDirectorHost && !coordinator.rewardDirectorHost && !coordinator.rewardCard,
                "Native first-stage director context requires a clean supported source attempt");
            // Suspend this exact source SceneDirector before objective setup can
            // activate scene-owned objects. The later lifecycle owner adopts the
            // same suspension rather than disabling or starting it again.
            var borrowedRoot = SourceStageDirectorRoot(false);
            coordinator.Check(borrowedRoot && !borrowedRoot.activeSelf && !borrowedRoot.GetComponent<SceneDirector>().enabled,
                              "Exact source SceneDirector was not suspended before native preparation");
            coordinator.r.director = new DirectorReport {
                automatic = true, spawnLimit = int.MaxValue, monsterLimit = TeamCatalog.GetTeamDef(TeamIndex.Monster).softCharacterLimit,
                scope =
                    "Native source-stage directors and complete accepted stage pool; no early diagnostic actor spawn or Beetle assertions."
            };
            var tiers = PrepareNativeDirectorEliteTiers();
            while (tiers.MoveNext())
                yield return tiers.Current;
            // Prepare whole catalog masters through the owned template mapping. Passing
            // the raw Beetle prefab here would mark it pre-adapted and skip rebinding.
            var sourceMaster = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyMasterAsset);
            coordinator.Check(sourceMaster && sourceMaster.GetComponent<CharacterMaster>() && !sourceMaster.activeSelf,
                              "Original catalog source master missing or active");
            StartOriginalNavigation();
            coordinator.automaticDirectorBegan = Time.realtimeSinceStartup;
            automaticDirectorFixedBegan = Run.instance.fixedTime;
            var sourceIndex = PrepareNativeDirectorCatalogAndPlayerContext(null, player, cfg);
            GameObject adaptedBeetle;
            coordinator.Check(MasterCatalog.GetMasterPrefab(sourceIndex) &&
                                  coordinator.wholeMasterTemplates.TryGetValue(sourceMaster.name, out adaptedBeetle) && adaptedBeetle &&
                                  ReferenceEquals(MasterCatalog.GetMasterPrefab(sourceIndex), adaptedBeetle),
                              "Owned adapted Beetle master is missing from the native master catalog");
            var sourceCard = coordinator.artifactBundle.LoadAsset<CharacterSpawnCard>(cfg.enemySpawnCardAsset);
            coordinator.Check(sourceCard && sourceCard.name == "cscBeetle" && sourceCard.prefab &&
                                  coordinator.wholeMasterTemplates.ContainsKey(sourceCard.prefab.name),
                              "Original source spawn card/master unavailable for world-item attribution");
            coordinator.rewardCard = Instantiate(sourceCard);
            coordinator.rewardCard.name = sourceCard.name;
            coordinator.rewardCard.prefab = coordinator.wholeMasterTemplates[sourceCard.prefab.name];
            coordinator.Check(coordinator.rewardCard.prefab && coordinator.rewardCard.prefab.GetComponent<CharacterMaster>(),
                              "Owned source master template missing for source-card attribution");
            coordinator.r.director.masterIndex = (int)MasterCatalog.FindMasterIndex(coordinator.rewardCard.prefab);
            coordinator.r.director.nativeSourceContextPrepared = true;
            coordinator.r.director.playerRegistered = coordinator.directorPlayer && PlayerCharacterMasterController.instances.Count == 1 &&
                                                      PlayerCharacterMasterController.instances[0] == coordinator.directorPlayer;
            coordinator.Save();
        }

        public IEnumerator SpawnAutomaticEnemy(GameObject template, CharacterBody player, SessionConfig cfg)
        {
            int limit = cfg.integratedWorld ? int.MaxValue : cfg.directorSpawnLimit == 0 ? 1 : cfg.directorSpawnLimit;
            coordinator.Check(cfg.integratedWorld || limit == 1 || limit == 3, "Unmeasured director batch limit");
            coordinator.r.director = new DirectorReport {
                automatic = true, spawnLimit = limit, monsterLimit = TeamCatalog.GetTeamDef(TeamIndex.Monster).softCharacterLimit,
                scope =
                    "Original enabled fast director; source timing/credits/target/team limit/approximate placement, one base Beetle card, bounded " +
                    limit + " spawns; no connected user, full stage, elite or full wave acceptance"
            };
            if (cfg.integratedWorld)
                coordinator.r.director.scope =
                    "Continuous original enabled fast director, one original base Beetle card and real team limit/credits/placement; no artificial spawn cutoff. Original Run clock with unavailable stock startup/user/profile/progression.";
            coordinator.r.phase = "automatic-director-context";
            coordinator.Save();
            coordinator.Check(RunArtifactManager.instance &&
                                  !RunArtifactManager.instance.IsArtifactEnabled(RoR2Content.Artifacts.eliteOnlyArtifactDef),
                              "Original disabled Honor artifact missing");
            var elitePreparation = PrepareNativeDirectorEliteTiers();
            while (elitePreparation.MoveNext())
                yield return elitePreparation.Current;
            MasterCatalog.MasterIndex index = PrepareNativeDirectorCatalogAndPlayerContext(template, player, cfg);
            coordinator.automaticDeck =
                Instantiate(coordinator.artifactBundle.LoadAsset<DirectorCardCategorySelection>(cfg.enemyDirectorDeckAsset));
            coordinator.Check(coordinator.automaticDeck, "Original initial director deck missing");
            var categories = coordinator.automaticDeck.categories
                                 .Where(sourceCategory => sourceCategory.cards.Any(
                                            candidate => candidate.spawnCard && candidate.spawnCard.name == coordinator.rewardCard.name))
                                 .ToArray();
            coordinator.Check(categories.Length == 1, "Original initial actor category ambiguous");
            var category = categories[0];
            category.cards =
                category.cards.Where(candidate => candidate.spawnCard && candidate.spawnCard.name == coordinator.rewardCard.name).ToArray();
            coordinator.automaticDeck.categories = new[] { category };
            coordinator.Check(category.cards.Length == 1, "Original initial actor card ambiguous");
            var card = coordinator.automaticDeck.categories[0].cards[0];
            coordinator.Check(card.spawnCard.name == coordinator.rewardCard.name && card.selectionWeight == 2 &&
                                  card.spawnDistance == DirectorCore.MonsterSpawnDistance.Standard && !card.preventOverhead &&
                                  card.minimumStageCompletions == 0 && !card.requiredUnlockableDef && !card.forbiddenUnlockableDef &&
                                  string.IsNullOrEmpty(card.requiredUnlockable) && string.IsNullOrEmpty(card.forbiddenUnlockable),
                              "Source Beetle card metadata changed");
            card.spawnCard = coordinator.rewardCard;
            coordinator.r.director.selectedCardWeight = card.selectionWeight;
            coordinator.Check(card.IsAvailable(), "Original base card availability failed");
            coordinator.automaticDirectorHost = coordinator.stageSourceObjects
                                                    ? SourceStageDirectorRoot(true)
                                                    : Instantiate(coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyDirectorAsset));
            coordinator.Check(coordinator.automaticDirectorHost && !coordinator.automaticDirectorHost.activeSelf,
                              "Source director root isolation missing");
            coordinator.rewardDirector = coordinator.automaticDirectorHost.GetComponent<CombatDirector>();
            coordinator.Check(
                coordinator.rewardDirector && coordinator.rewardDirector.enabled &&
                    (coordinator.stageSourceObjects || coordinator.automaticDirectorHost.GetComponents<MonoBehaviour>().Length == 1),
                "Source fast director component scope changed");
            coordinator.r.director.sourceSettings =
                coordinator.rewardDirector.monsterCredit == 0 && coordinator.rewardDirector.creditMultiplier == .75f &&
                coordinator.rewardDirector.moneyWaveIntervals.Length == 1 && coordinator.rewardDirector.moneyWaveIntervals[0].min == 1 &&
                coordinator.rewardDirector.moneyWaveIntervals[0].max == 1 && coordinator.rewardDirector.minRerollSpawnInterval == 4.5f &&
                coordinator.rewardDirector.maxRerollSpawnInterval == 9 && coordinator.rewardDirector.targetPlayers &&
                !coordinator.rewardDirector.ignoreTeamSizeLimit && coordinator.rewardDirector.maximumNumberToSpawnBeforeSkipping == 6 &&
                coordinator.rewardDirector.spawnDistanceMultiplier == 1 && coordinator.rewardDirector.minSpawnRange == 0 &&
                !coordinator.rewardDirector.shouldSpawnOneWave;
            coordinator.Check(coordinator.r.director.sourceSettings, "Original fast director settings changed");
            coordinator.rewardDirector.monsterCards = coordinator.automaticDeck;
            var spawningDirector = coordinator.rewardDirector;
            spawningDirector.onSpawnedServer.AddListener(
                obj =>
                {
                    coordinator.RecordRewardSpawn(obj);
                    if (coordinator.currentStageCombatDeck != null)
                        coordinator.RecordStageCombatSpawn(obj, player, spawningDirector);
                    else
                        coordinator.RecordDirectorActor(obj, player);
                    if (coordinator.r.rewards.spawnEvents == 1)
                    {
                        coordinator.r.director.position = coordinator.enemyBody.transform.position;
                        coordinator.r.director.spawnDistance =
                            Vector3.Distance(player.transform.position, coordinator.enemyBody.transform.position);
                        coordinator.r.director.originalTarget = coordinator.rewardDirector.currentSpawnTarget == player.gameObject;
                    }
                    if (coordinator.r.director.actors.Count == limit)
                    {
                        coordinator.rewardDirector.enabled = false;
                        coordinator.r.director.stopped = true;
                        coordinator.r.director.stoppedAt = Time.realtimeSinceStartup - coordinator.automaticDirectorBegan;
                    }
                });
            if (cfg.teleporterLoop)
            {
                // Original charging disables CombatDirectors attached to DirectorCore, not descendants.
                var core = coordinator.rewardDirectorHost.GetComponent<DirectorCore>();
                coordinator.Check(core && DirectorCore.instance == core, "Owned original director core missing");
                core.enabled = false;
                if (coordinator.stageSourceObjects)
                {
                    coordinator.sourceSlowDirector.monsterCards = coordinator.automaticDeck;
                    ObserveSourceSlowDirector(player);
                }
                else
                    coordinator.automaticDirectorHost.AddComponent<DirectorCore>();
            }
            StartOriginalNavigation();
            coordinator.automaticDirectorBegan = Time.realtimeSinceStartup;
            automaticDirectorFixedBegan = Run.instance.fixedTime;
            coordinator.automaticDirectorHost.SetActive(true);
            coordinator.Check(CombatDirector.instancesList.Contains(coordinator.rewardDirector),
                              "Original natural director registration missing");
            float previous = 0;
            try
            {
                while (!coordinator.enemyBody && Time.realtimeSinceStartup - coordinator.automaticDirectorBegan < 55)
                {
                    yield return new WaitForEndOfFrame();
                    coordinator.r.director.seconds = Time.realtimeSinceStartup - coordinator.automaticDirectorBegan;
                    var credit = coordinator.rewardDirector.monsterCredit;
                    if (credit > previous)
                        coordinator.r.director.creditSteps++;
                    previous = credit;
                    coordinator.r.director.creditPeak = Mathf.Max(coordinator.r.director.creditPeak, credit);
                    coordinator.r.director.originalTarget |= coordinator.rewardDirector.currentSpawnTarget == player.gameObject;
                    if (Time.frameCount % 30 == 0)
                        coordinator.Save();
                }
            }
            finally
            {
                coordinator.CaptureRewardSummons(template.GetComponent<CharacterMaster>().bodyPrefab, template);
            }
            coordinator.Check(coordinator.enemyBody && coordinator.r.rewards.spawnEvents == 1 && coordinator.r.rewards.summonEvents == 1,
                              "Original scheduled spawn timed out");
            yield return null;
            coordinator.r.director.creditAfter = coordinator.rewardDirector.monsterCredit;
            coordinator.r.director.spent = coordinator.rewardDirector.totalCreditsSpent;
            coordinator.r.director.preloaded = DirectorRequestedMasters().Count == 1 && DirectorRequestedMasters() [0].Equals(index);
            // Original participant/body getters count the real registered master, without a NetworkUser.
            var waves = (Array) typeof(CombatDirector)
                            .GetField("moneyWaves", BindingFlags.Instance | BindingFlags.NonPublic)
                            .GetValue(coordinator.rewardDirector);
            var wave = waves.GetValue(0);
            var wt = wave.GetType();
            float timer = (float)wt.GetField("timer").GetValue(wave),
                  fraction = (float)wt.GetField("accumulatedAward", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(wave);
            float rate = coordinator.rewardDirector.creditMultiplier * (1 + .4f * Run.instance.compensatedDifficultyCoefficient) *
                         (.5f + .5f * Run.instance.participatingPlayerCount);
            float earned = coordinator.r.director.creditAfter + coordinator.r.director.spent + fraction, scheduled = earned / rate + timer;
            // Original money waves consume fixedDeltaTime, including catch-up ticks. Their
            // conservation clock must be original simulation time, not device wall time.
            coordinator.r.director.fixedSeconds = Run.instance.fixedTime - automaticDirectorFixedBegan;
            coordinator.r.director.scheduledCreditSeconds = scheduled;
            coordinator.r.director.creditConserved = coordinator.r.director.spent == 8 && coordinator.r.director.creditAfter >= 0 &&
                                                     coordinator.r.director.creditSteps >= 7 &&
                                                     Mathf.Abs(scheduled - coordinator.r.director.fixedSeconds) < .15f;
            DirectorCore.GetMonsterSpawnDistance(card.spawnDistance, out coordinator.r.director.minDistance,
                                                 out coordinator.r.director.maxDistance);
            coordinator.r.director.placement = coordinator.r.director.spawnDistance >= coordinator.r.director.minDistance - .1f &&
                                               coordinator.r.director.spawnDistance <= coordinator.r.director.maxDistance + .1f;
            coordinator.Check(
                coordinator.r.director.originalTarget && coordinator.r.director.preloaded && coordinator.r.director.creditConserved &&
                    coordinator.r.director.placement &&
                    (cfg.integratedWorld || limit == 3 ? coordinator.rewardDirector.enabled : !coordinator.rewardDirector.enabled),
                "Original targeting/preload/credit/placement assertions failed");
            coordinator.Save();
        }
        public void Dispose()
        {
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && nativeSourceDirectorRoot)
            {
                var directors = nativeSourceDirectorRoot.GetComponents<CombatDirector>();
                coordinator.Check(directors.Length == 2 && directors.All(candidate => candidate),
                                  "Borrowed source directors disappeared before deck restoration");
                var selected = coordinator.automaticDeck;
                coordinator.Check(ReferenceEquals(directors[0].monsterCards, nativeOriginalSourceFastDeck) ||
                                      ReferenceEquals(directors[0].monsterCards, selected),
                                  "Foreign fast source deck replacement during cleanup");
                coordinator.Check(ReferenceEquals(directors[1].monsterCards, nativeOriginalSourceSlowDeck) ||
                                      ReferenceEquals(directors[1].monsterCards, selected),
                                  "Foreign slow source deck replacement during cleanup");
                if (ReferenceEquals(directors[0].monsterCards, selected))
                    directors[0].monsterCards = nativeOriginalSourceFastDeck;
                if (ReferenceEquals(directors[1].monsterCards, selected))
                    directors[1].monsterCards = nativeOriginalSourceSlowDeck;
            }
            coordinator.CleanupStageCombatDecks();
            coordinator.CleanupWholePopulation();
            ownedNavigationTick = null;
            if (directorPlayerRegistered && coordinator.directorPlayer)
            {
                Call(coordinator.directorPlayer, "OnDisable");
                directorPlayerRegistered = false;
            }
            if (coordinator.automaticDirectorHost)
                Destroy(coordinator.automaticDirectorHost);
            coordinator.sourceSlowDirector = null;
            if (coordinator.automaticDeck)
                Destroy(coordinator.automaticDeck);
            if (directorMasterMap != null)
            {
                directorMasterMap.Clear();
                foreach (var entry in directorMasterFields)
                    entry.Key.SetValue(null, entry.Value);
                directorMasterFields.Clear();
                DirectorRequestedMasters().Clear();
                DirectorMessageMasters().Clear();
                RewardField(typeof(CombatDirector), "eliteTiers").SetValue(null, priorDirectorEliteTiers);
            }
        }
        public void ReleaseDirectorAssets()
        {
            if (directorTeamEffects == null)
                return;
            foreach (var team in Enum.GetValues(typeof(TeamIndex))
                         .Cast<TeamIndex>()
                         .Where(team => team >= TeamIndex.Player && team < TeamIndex.Count))
            {
                var def = TeamCatalog.GetTeamDef(team);
                var effect = def.levelUpEffect;
                coordinator.Check(effect == directorTeamEffects[team == TeamIndex.Player ? 0 : 1],
                                  "Owned team effect reference changed before release");
                def.levelUpEffect = null;
                Addressables.Release(effect);
            }
            directorTeamEffects = null;
            int agents = NavigationAgentCount();
            bool cleaned = !coordinator.automaticDirectorHost && !coordinator.automaticDeck && !directorPlayerRegistered &&
                           PlayerCharacterMasterController.instances.Count == 0 &&
                           (directorMasterMap == null || directorMasterMap.Count == 0) && agents == 0;
            if (coordinator.r.director != null)
            {
                coordinator.r.director.navigationAgents = agents;
                coordinator.r.director.cleaned = cleaned;
            }
            coordinator.Check(cleaned, "Automatic director owned teardown incomplete");
        }
    }
}
