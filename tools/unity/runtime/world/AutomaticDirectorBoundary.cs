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
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Supplies measured source contexts; original enabled callbacks select, fund and place the NPC.
public sealed partial class PortSession
{
    [Serializable]
    public class DirectorReport
    {
        public bool automatic, sourceSettings, playerRegistered, originalTarget, preloaded, creditConserved, placement, stopped, cleaned,
            navigationNext, navigationReachable;
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
        public AutomaticDirectorSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public GameObject SourceStageDirectorRoot(bool holdSlow)
        {
            var roots = coordinator.stageGeometryScene.GetRootGameObjects().Where(root => root.name == "Director").ToArray();
            coordinator.Check(coordinator.stageSourceObjects && roots.Length == 1 && !roots[0].activeSelf,
                              "Original source Director root unavailable");
            var root = roots[0];
            var sceneDirector = root.GetComponent<SceneDirector>();
            var directors = root.GetComponents<CombatDirector>();
            coordinator.Check(sceneDirector && sceneDirector.enabled && directors.Length == 2 && directors.All(x => x.enabled) &&
                                  root.GetComponent<DirectorCore>(),
                              "Original source Director components changed");
            // Teleporter ownership is established later; its original Start is invoked
            // after that boundary. The slow director waits for the complete stage deck.
            sceneDirector.enabled = false;
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
            var adaptedMasters =
                new[] { template }.Concat(coordinator.objectiveTemplates.Where(x => x.GetComponent<CharacterMaster>())).ToArray();
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
            var index = MasterCatalog.FindMasterIndex(template);
            coordinator.Check(MasterCatalog.GetMasterPrefab(index) == template, "Original master catalog identity");
            coordinator.r.director.masterIndex = (int)index;
            coordinator.directorPlayer = player.master.GetComponent<PlayerCharacterMasterController>();
            coordinator.Check(coordinator.directorPlayer && !coordinator.directorPlayer.gameObject.activeInHierarchy &&
                                  !coordinator.directorPlayer.networkUser && PlayerCharacterMasterController.instances.Count == 0,
                              "Measured local player registration scope changed");
            if (!coordinator.directorPlayer.master)
                Call(coordinator.directorPlayer, "Awake");
            coordinator.Check(coordinator.directorPlayer.master == player.master, "Original player controller master binding");
            directorPlayerRegistered = true;
            Call(coordinator.directorPlayer, "OnEnable");
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
