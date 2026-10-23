// Subsystem: progression (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareAndroidProfile (AndroidProfileSession.Prepare), ApplyAndroidProfileLoadoutBeforeSpawn; teardown CleanupAndroidProfile (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates.TimedChest;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.Networking;
using UnityEngine.ResourceManagement.AsyncOperations;
using Zio;

public sealed partial class PortSession
{
    [Serializable]
    public sealed class AndroidProfileReport
    {
        public bool ready, created, roundTrip, cleaned, resultApplied, assistedExcluded, loadoutAppliedBeforeSpawn, loadoutVerified,
            loadoutMenuCommitted, threeStageEligible, threeStageAssistedExcluded, threeStageAwarded;
        public string recovery, scope, error;
        public int saveFields, statFields, survivors, appliedRuns, baselineRuns, reconciledRuns, unlockables, achievements,
            persistentStatAchievements, earnedUnlocks, availableEarnedUnlocks, discoverySlots, discoveredPickups,
            assistedDiscoveriesExcluded, threeStageChargedEvents;
        public uint selectedSkin;
        public int[] selectedSkillVariants;
        public string[] earnedLoot;
        public AndroidProgressionBoundary.AwardReport awards;
        public AndroidProgressionBoundary.DiscoveryReport discovery;
        public AndroidProgressionBoundary.ThreeStageReport threeStageAward;
        public List<AndroidProgressionBoundary.EventAwardReport> eventAwards = new List<AndroidProgressionBoundary.EventAwardReport>();
        public uint earnedCoins;
        public ulong kills, firstTeleporterCompletedStat;
    }
    sealed class AndroidProfileSaveSystem : SaveSystem
    {
        public AndroidOfflineProfile local;
        static Exception Unavailable()
        {
            return new NotSupportedException(
                "Steam identity, cloud/profile import and platform history unavailable; owned Android profile only.");
        }
        protected override void ProcessFileOutputQueue()
        {
            if (local != null && local.profile.saveRequestPending)
                local.Save();
        }
        protected override void StartSave(UserProfile profile, bool blocking)
        {
            if (local == null || !ReferenceEquals(profile, local.profile))
                throw Unavailable();
            local.Save();
            userProfile = local.profile;
        }
        protected override LoadUserProfileOperationResult LoadUserProfileFromDisk(IFileSystem files, UPath path)
        {
            throw Unavailable();
        }
        public override void LoadUserProfiles()
        {
            throw Unavailable();
        }
        public override UserProfile LoadPrimaryProfile()
        {
            return local == null ? null : local.profile;
        }
        public override string GetPlatformUsernameOrDefault(string defaultName)
        {
            return defaultName;
        }
        public override UserProfile CreateProfile(IFileSystem files, string name, ulong platformUserID = 0)
        {
            throw Unavailable();
        }
        public override void SaveHistory(byte[] data, string name)
        {
            throw Unavailable();
        }
        public override Dictionary<string, byte[]> LoadHistory()
        {
            throw Unavailable();
        }
    }
    // Shared with earned run availability and the objective rule catalog.
    AndroidProgressionBoundary androidProgression;
    AndroidProfileSession androidProfileSession;
    // Loadout preview precedes Prepare; cleanup must also reset menu selection
    // when preparation was skipped. Keep the owner across those entry points.
    AndroidProfileSession GetAndroidProfileSession()
    {
        if (androidProfileSession == null)
            androidProfileSession = new AndroidProfileSession(this);
        return androidProfileSession;
    }
    void ApplyAndroidProfileLoadoutBeforeSpawn(CharacterMaster master, GameObject prefab)
    {
        var session = GetAndroidProfileSession();
        session.ApplyLoadoutBeforeSpawn(master, prefab);
        session.ApplyDeveloperSkillVariantOverride(master, prefab);
    }
    bool HasOwnedProfileUnlock(UnlockableDef definition)
    {
        return GetAndroidProfileSession().HasOwnedProfileUnlock(definition);
    }
    void PrepareAndroidProfile(CharacterBody player)
    {
        GetAndroidProfileSession().Prepare(player);
    }
    void PersistAndroidProfileResult(bool assisted)
    {
        GetAndroidProfileSession().PersistResult(assisted || IsRunAssisted());
    }
    void CleanupAndroidProfile()
    {
        GetAndroidProfileSession().Dispose();
    }

    // Nested to keep shared coordinator state private. Dispose retains the existing
    // partial-prepare and repeated-cleanup behaviour; a later session may Prepare.
    sealed class AndroidProfileSession : IDisposable
    {
        readonly PortSession coordinator;
        public AndroidProfileSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        BodyIndex previewLoadoutBody = BodyIndex.None;
        uint previewLoadoutSkin;
        int[] previewLoadoutSkills;
        int[] appliedLoadoutSkills;
        public void ApplyLoadoutBeforeSpawn(CharacterMaster master, GameObject prefab)
        {
            if (coordinator.r.liveCatalogs == null || !Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                return;
            coordinator.Check(master && master.loadout != null && prefab && SkinCatalog.availability.available,
                              "Original profile loadout requires owned master and skin catalog");
            var body = prefab.GetComponent<CharacterBody>();
            coordinator.Check(body && body.bodyIndex != BodyIndex.None && BodyCatalog.GetBodyPrefab(body.bodyIndex) == prefab,
                              "Selected profile loadout body identity changed");
            var directory = System.IO.Path.Combine(Application.persistentDataPath, "android-profile-v1");
            var unlocked = AndroidOfflineProfile.PreviewUnlockNames(directory);
            var preview = coordinator.offlineLoadoutEdited && coordinator.offlinePendingLoadout != null &&
                                  coordinator.r.developerSkillVariantOverride == null
                              ? coordinator.offlinePendingLoadout
                              : AndroidOfflineProfile.PreviewLoadout(directory);
            uint skinIndex = preview.bodyLoadoutManager.GetSkinIndex(body.bodyIndex);
            coordinator.Check(skinIndex < int.MaxValue && skinIndex < SkinCatalog.GetBodySkinCount(body.bodyIndex),
                              "Saved original skin index unavailable");
            var skin = SkinCatalog.GetBodySkinDef(body.bodyIndex, (int)skinIndex);
            coordinator.Check(
                skin && string.IsNullOrEmpty(skin.unlockableName) &&
                    (!skin.unlockableDef || !skin.unlockableDef.requiredExpansion && unlocked.Contains(skin.unlockableDef.cachedName)),
                "Saved original skin requires an unavailable unlock or expansion");
            var slots = prefab.GetComponents<GenericSkill>();
            var selected = new Loadout();
            var variants = new int[slots.Length];
            selected.bodyLoadoutManager.SetSkinIndex(body.bodyIndex, skinIndex);
            for (int i = 0; i < slots.Length; i++)
            {
                var family = slots[i].skillFamily;
                uint index = preview.bodyLoadoutManager.GetSkillVariant(body.bodyIndex, i);
                coordinator.Check(family && index < family.variants.Length && family.variants[(int)index].skillDef,
                                  "Saved original skill variant unavailable");
                var variant = family.variants[(int)index];
                coordinator.Check(string.IsNullOrEmpty(variant.unlockableName) &&
                                      (!variant.unlockableDef ||
                                       !variant.unlockableDef.requiredExpansion && unlocked.Contains(variant.unlockableDef.cachedName)),
                                  "Saved original skill requires an unavailable unlock or expansion");
                selected.bodyLoadoutManager.SetSkillVariant(body.bodyIndex, i, index);
                variants[i] = (int)index;
            }
            selected.Copy(master.loadout);
            previewLoadoutBody = body.bodyIndex;
            previewLoadoutSkin = skinIndex;
            previewLoadoutSkills = variants;
            appliedLoadoutSkills = (int[])variants.Clone();
            coordinator.Check(master.loadout.bodyLoadoutManager.GetSkinIndex(body.bodyIndex) == skinIndex &&
                                  Enumerable.Range(0, variants.Length)
                                      .All(i => master.loadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex, i) == variants[i]),
                              "Original pre-spawn loadout copy differs");
        }
        public void ApplyDeveloperSkillVariantOverride(CharacterMaster master, GameObject prefab)
        {
            var request = coordinator.r.developerSkillVariantOverride;
            if (request == null)
                return;
            var report = coordinator.r.developerSkillVariantOverrideReport ?? new DeveloperSkillVariantOverrideReport { requested = true };
            coordinator.r.developerSkillVariantOverrideReport = report;
            // Record assistance before any per-run native loadout mutation, including refusal.
            coordinator.MarkDeveloperSkillVariantAssisted("explicit per-run survivor skill variant selection");
            report.status = "applying";
            try
            {
                if (previewLoadoutBody == BodyIndex.None || appliedLoadoutSkills == null)
                    throw new DeveloperSkillVariantSelection.SelectionException(
                        "refused", "Developer skill-variant override requires the native profile/default loadout preview");
                report.skillVariantInventory =
                    SurvivorSkillObserver.CaptureSkillVariantInventory(prefab, master.loadout, "native-master-loadout-pre-spawn");
                if (report.skillVariantInventory.status != "available")
                    throw new DeveloperSkillVariantSelection.SelectionException(
                        "refused", "Developer skill-variant catalog inventory refused: " + report.skillVariantInventory.error);
                appliedLoadoutSkills = DeveloperSkillVariantSelection.Apply(request, master, prefab, coordinator.r.selectedSurvivor);
                report.effectiveSkillVariants = (int[])appliedLoadoutSkills.Clone();
                report.applied = true;
                report.status = "applied";
            }
            catch (DeveloperSkillVariantSelection.SelectionException error)
            {
                report.status = error.outcome;
                report.error = error.Message;
                coordinator.Check(false, "Developer skill-variant override refused: " + error.Message);
            }
            catch (Exception error)
            {
                report.status = "refused";
                report.error = error.Message;
                coordinator.Check(false, "Developer skill-variant override failed safely: " + error.Message);
            }
        }
        void ConfirmAndroidProfileLoadout(CharacterBody player, UserProfile profile)
        {
            if (previewLoadoutBody == BodyIndex.None)
                return;
            coordinator.Check(player && player.master && player.bodyIndex == previewLoadoutBody && profile != null &&
                                  profile.loadout != null,
                              "Original profile loadout verification context missing");
            var spawnedSkills = player.GetComponents<GenericSkill>();
            coordinator.Check(
                player.skinIndex == previewLoadoutSkin && spawnedSkills.Length == appliedLoadoutSkills.Length &&
                    Enumerable.Range(0, spawnedSkills.Length)
                        .All(i => spawnedSkills[i] && spawnedSkills[i].skillFamily &&
                                  spawnedSkills[i].skillDef == spawnedSkills[i].skillFamily.variants[appliedLoadoutSkills[i]].skillDef),
                "Original spawned body differs from selected loadout");
            if (coordinator.offlineLoadoutEdited && coordinator.r.developerSkillVariantOverride == null)
            {
                coordinator.Check(coordinator.resultsSaveSystem.local != null &&
                                      ReferenceEquals(profile, coordinator.resultsSaveSystem.local.profile),
                                  "Selected loadout has no owned profile");
                coordinator.r.profile.loadoutMenuCommitted =
                    coordinator.resultsSaveSystem.local.SelectLoadout(previewLoadoutBody, previewLoadoutSkin, previewLoadoutSkills);
                profile = coordinator.resultsSaveSystem.local.profile;
                coordinator.resultsSaveSystem.userProfile = profile;
            }
            var bodyLoadout = profile.loadout.bodyLoadoutManager;
            coordinator.Check(bodyLoadout.GetSkinIndex(previewLoadoutBody) == previewLoadoutSkin && player.skinIndex == previewLoadoutSkin,
                              "Decoded original profile skin differs from spawned body");
            var skills = spawnedSkills;
            coordinator.Check(skills.Length == previewLoadoutSkills.Length, "Original spawned skill slot count changed");
            for (int i = 0; i < skills.Length; i++)
                coordinator.Check(skills[i] && skills[i].skillFamily &&
                                      bodyLoadout.GetSkillVariant(previewLoadoutBody, i) == previewLoadoutSkills[i],
                                  "Decoded original profile skill index differs from selected profile preview");
            coordinator.r.profile.loadoutAppliedBeforeSpawn = true;
            coordinator.r.profile.loadoutVerified = true;
            coordinator.r.profile.selectedSkin = previewLoadoutSkin;
            coordinator.r.profile.selectedSkillVariants = previewLoadoutSkills;
        }
        public bool HasOwnedProfileUnlock(UnlockableDef definition)
        {
            return !definition || coordinator.resultsSaveSystem != null && coordinator.resultsSaveSystem.local != null &&
                                      coordinator.resultsSaveSystem.local.profile.HasUnlockable(definition);
        }
        AndroidProgressionBoundary.DiscoveryReport pendingDiscovery;
        Action<TeleporterInteraction> profileProgressionCharge, profileTeleporterBegin;
        Action<DamageDealtMessage> profileTeleporterDamage;
        Action<DamageReport> profileEliteDeath;
        Action<BossGroup> profileQuickBoss, profileMountainBoss;
        Action<Stage> profileLoopStage;
        Action<SceneExitController> profileTeleporterExit;
        Action<SceneExitControllerColossusPortal> profileColossusExit;
        Action profileTimedChestOpened;
        Run profileAwardRun;
        CharacterBody profileAwardBody;
        CharacterMaster profileAwardMaster;
        AndroidProfileSaveSystem profileAwardSaveSystem;
        AndroidOfflineProfile profileAwardStore;
        bool profileFirstTeleporterRecorded, profileTeleporterCharging, profileTeleporterHit;
        readonly HashSet<string> profileObservedEvents = new HashSet<string>(StringComparer.Ordinal);
        Inventory discoveryInventory;
        Action<ItemIndex> discoveryItem;
        Action<EquipmentIndex, uint> discoveryEquipment;
        Action<KeyItemIndex> discoveryKeyItem;
        readonly Dictionary<FieldInfo, object> priorProfileCatalog = new Dictionary<FieldInfo, object>();
        readonly Dictionary<SurvivorDef, SurvivorIndex> priorProfileSurvivors = new Dictionary<SurvivorDef, SurvivorIndex>();
        ViewablesCatalog.Node profileViewablesRoot;
        ViewablesCatalog.Node[] priorProfileNodes;
        Dictionary<string, ViewablesCatalog.Node> profileViewablesMap, priorProfileViewables;
        UserProfile priorDefaultProfile;
        object priorProfileRedirects;
        bool ownsProfileContext;
        AsyncOperationHandle<UserProfileRedirectData> profileRedirectLease;
        bool ownsProfileRedirectLease;
        public void Prepare(CharacterBody player)
        {
            if (!Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                return;
            coordinator.r.profile = new AndroidProfileReport {
                scope =
                    "Original UserProfile/default/XML/statistics/loadout on Android only; recoverable local generations. Native persistent-stat, first-teleporter/portal-stat and measured three-stage awards; platform reporting, login, Steam/cloud import and Rewired maps unavailable. Other event-achievement families remain deferred."
            };
            coordinator.Save();
            coordinator.Check(SurvivorCatalog.survivorCount == 0 && UserProfile.defaultProfile == null && priorProfileCatalog.Count == 0,
                              "Foreign survivor/profile context");
            var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            foreach (var field in typeof(SurvivorCatalog).GetFields(flags))
                if (!field.IsLiteral && !field.IsInitOnly &&
                    (field.FieldType.IsArray || field.FieldType == typeof(SurvivorDef) ||
                     field.FieldType == typeof(global::ResourceAvailability)))
                    priorProfileCatalog.Add(field, field.GetValue(null));
            profileViewablesRoot = (ViewablesCatalog.Node)RewardField(typeof(ViewablesCatalog), "rootNode").GetValue(null);
            priorProfileNodes = profileViewablesRoot.children.ToArray();
            profileViewablesMap =
                (Dictionary<string, ViewablesCatalog.Node>)RewardField(typeof(ViewablesCatalog), "fullNameToNodeMap").GetValue(null);
            priorProfileViewables = new Dictionary<string, ViewablesCatalog.Node>(profileViewablesMap);
            priorDefaultProfile = UserProfile.defaultProfile;
            priorProfileRedirects = RewardField(typeof(XmlUtility), "ValueReplacements").GetValue(null);
            coordinator.Check(priorProfileRedirects == null, "Foreign profile redirect owner");
            ownsProfileContext = true;
            var definitions =
                WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef, Array.Empty<SurvivorDef>());
            foreach (var def in definitions)
                priorProfileSurvivors.Add(def, def.survivorIndex);
            StaticCall(typeof(SurvivorCatalog), "SetSurvivorDefs", new object[] { definitions });
            SurvivorCatalog.availability.MakeAvailable();
            coordinator.Check(
                SurvivorCatalog.defaultSurvivor &&
                    definitions.All(def => SurvivorCatalog.GetSurvivorDef(def.survivorIndex) == def &&
                                           SurvivorCatalog.GetBodyIndexFromSurvivorIndex(def.survivorIndex) != BodyIndex.None),
                "Original survivor identity differs");
            coordinator.androidProgression = new AndroidProgressionBoundary();
            var metadata = coordinator.androidProgression.Prepare(
                WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.unlockableDef, Array.Empty<UnlockableDef>()));
            // This original initializer yields only scheduling nulls. Any new asynchronous
            // dependency must be handled explicitly rather than discarded by this drain.
            try
            {
                while (metadata.MoveNext())
                    coordinator.Check(metadata.Current == null, "Native progression metadata acquired an asynchronous dependency");
            }
            finally
            {
                var disposable = metadata as IDisposable;
                if (disposable != null)
                    disposable.Dispose();
            }
            coordinator.r.profile.unlockables = coordinator.androidProgression.unlockables;
            coordinator.r.profile.achievements = coordinator.androidProgression.achievements;
            coordinator.r.profile.persistentStatAchievements = coordinator.androidProgression.persistentStatDefinitions.Length;
            // Native rule choices capture these catalog unlock references, and replaying
            // saved RunReports later requires RuleBook default-value metadata.
            coordinator.PrepareObjectiveRuleCatalog();
            // Pair the source serializer's otherwise unretained redirect-asset load with
            // the existing composed provider owner; no extra bundle or input copy.
            profileRedirectLease = Addressables.LoadAssetAsync<UserProfileRedirectData>("RoR2/Base/Core/UserProfileRedirects.asset");
            ownsProfileRedirectLease = true;
            var redirects = profileRedirectLease.WaitForCompletion();
            coordinator.Check(profileRedirectLease.Status == AsyncOperationStatus.Succeeded && redirects,
                              "Original profile redirect asset unavailable");
            RewardField(typeof(XmlUtility), "ValueReplacements").SetValue(null, redirects);
            if (UserProfile.saveFields == null)
                UserProfile.GenerateSaveFieldFunctions();
            coordinator.Check(PickupCatalog.pickupCount > 0, "Native profile requires complete pickup metadata first");
            UserProfile.LoadDefaultProfile();
            coordinator.Check(!UserProfile.defaultProfile.canSave && !UserProfile.defaultProfile.loggedIn &&
                                  UserProfile.defaultProfile.coins == 0,
                              "Native default profile unexpectedly has platform/currency state");
            var local = new AndroidOfflineProfile(
                System.IO.Path.Combine(Application.persistentDataPath, "android-profile-v1"),
                coordinator.resultsLedger.runs.Select(ProfileRunIdentity),
                candidate =>
                { coordinator.r.profile.awards = coordinator.androidProgression.ApplyPersistentStatCandidate(candidate); },
                (candidate, pickup) =>
                { pendingDiscovery = coordinator.androidProgression.ApplyDiscoveryCandidate(candidate, pickup); });
            coordinator.resultsSaveSystem.local = local;
            coordinator.resultsSaveSystem.userProfile = local.profile;
            coordinator.resultsSaveSystem.isInitialLoadFinished = true;
            coordinator.r.profile.discoverySlots = ((bool[]) typeof(UserProfile)
                                                        .GetField("discoveredPickups", BindingFlags.Instance | BindingFlags.NonPublic)
                                                        .GetValue(local.profile))
                                                       .Length;
            coordinator.Check(coordinator.r.profile.discoverySlots == PickupCatalog.pickupCount,
                              "Native profile discovery capacity differs from catalog");
            ReconcileAndroidProfile(local);
            coordinator.resultsSaveSystem.userProfile = local.profile;
            coordinator.ConfirmSelectedSurvivorUnlock();
            ConfirmAndroidProfileLoadout(player, local.profile);
            coordinator.r.profile.ready = true;
            coordinator.r.profile.created = local.recovery == "new";
            coordinator.r.profile.roundTrip = true;
            coordinator.r.profile.recovery = local.recovery;
            coordinator.r.profile.saveFields = UserProfile.saveFields.Length;
            coordinator.r.profile.statFields = local.profile.statSheet.fields.Length;
            coordinator.r.profile.survivors = SurvivorCatalog.survivorCount;
            ObserveAndroidProfile();
            coordinator.Save();
            profileProgressionCharge = ObserveOfflineTeleporterProgression;
            TeleporterInteraction.onTeleporterChargedGlobal += profileProgressionCharge;
            profileTeleporterBegin = teleporter =>
            {
                if (teleporter == coordinator.worldTeleporter)
                {
                    profileTeleporterCharging = true;
                    profileTeleporterHit = false;
                }
            };
            TeleporterInteraction.onTeleporterBeginChargingGlobal += profileTeleporterBegin;
            profileTeleporterDamage = message =>
            {
                if (profileTeleporterCharging && message != null && coordinator.worldPlayer &&
                    message.victim == coordinator.worldPlayer.gameObject)
                    profileTeleporterHit = true;
            };
            GlobalEventManager.onClientDamageNotified += profileTeleporterDamage;
            profileEliteDeath = damage =>
            {
                if (damage != null && damage.victimIsElite && coordinator.worldPlayer &&
                    damage.attackerMaster == coordinator.worldPlayer.master)
                    RecordOfflineOriginalEvent("KillEliteMonster");
            };
            GlobalEventManager.onDeathProcServer += profileEliteDeath;
            profileQuickBoss = group =>
            {
                if (group && group.fixedTimeSinceEnabled <= 15f && group.GetComponent<TeleporterInteraction>())
                    RecordOfflineOriginalEvent("KillBossQuick");
            };
            BossGroup.onBossGroupDefeatedServer += profileQuickBoss;
            profileMountainBoss = group =>
            {
                if (group && coordinator.worldTeleporter && coordinator.worldPlayer && coordinator.worldPlayer.healthComponent &&
                    coordinator.worldPlayer.healthComponent.alive && coordinator.worldTeleporter.bossDirector &&
                    coordinator.worldTeleporter.bossDirector.combatSquad == group.combatSquad &&
                    coordinator.worldTeleporter.shrineBonusStacks >= 2)
                    RecordOfflineOriginalEvent("CompleteMultiBossShrine");
            };
            BossGroup.onBossGroupDefeatedServer += profileMountainBoss;
            profileLoopStage = stage =>
            {
                var scene = SceneCatalog.GetSceneDefForCurrentScene();
                if (stage && Run.instance && Run.instance.GetType() == typeof(Run) && Run.instance.loopClearCount > 0 && scene &&
                    (scene.sceneType == SceneType.Stage || scene.sceneType == SceneType.UntimedStage) && !scene.isFinalStage &&
                    scene.stageOrder == 1)
                    RecordOfflineOriginalEvent("LoopOnce");
            };
            Stage.onServerStageBegin += profileLoopStage;
            profileTeleporterExit = exit =>
            {
                if (exit && exit.portalUsedAfterTeleporterEventFinish && coordinator.worldPlayer &&
                    coordinator.worldPlayer.healthComponent && coordinator.worldPlayer.healthComponent.alive)
                    RecordOfflineOriginalEvent("CompleteTeleporter");
            };
            SceneExitController.onBeginExit += profileTeleporterExit;
            profileColossusExit = exit =>
            {
                if (exit && coordinator.worldPlayer && coordinator.worldPlayer.healthComponent &&
                    coordinator.worldPlayer.healthComponent.alive)
                    RecordOfflineOriginalEvent("CompleteTeleporter");
            };
            SceneExitControllerColossusPortal.onBeginExit += profileColossusExit;
            var timedChestSaveSystem = coordinator.resultsSaveSystem;
            var timedChestStore = timedChestSaveSystem == null ? null : timedChestSaveSystem.local;
            var timedChestProfile = timedChestStore == null ? null : timedChestStore.profile;
            coordinator.Check(NetworkServer.active && Run.instance && Run.instance.GetType() == typeof(Run) && player &&
                                  coordinator.worldPlayer == player && player.master && player.master.GetBody() == player &&
                                  coordinator.directorPlayer && coordinator.directorPlayer.master == player.master &&
                                  !coordinator.directorPlayer.networkUser && !coordinator.directorPlayer.isConnected &&
                                  timedChestSaveSystem != null && ReferenceEquals(PlatformSystems.saveSystem, timedChestSaveSystem) &&
                                  timedChestStore != null && timedChestProfile != null &&
                                  ReferenceEquals(timedChestSaveSystem.userProfile, timedChestProfile) && timedChestProfile.canSave &&
                                  !timedChestProfile.loggedIn && !timedChestProfile.isClaimed && timedChestProfile.saveID == 0,
                              "Timed-chest observer lacks the exact owned offline profile/run/body/master context");
            profileAwardRun = Run.instance;
            profileAwardBody = player;
            profileAwardMaster = player.master;
            profileAwardSaveSystem = timedChestSaveSystem;
            profileAwardStore = timedChestStore;
            profileTimedChestOpened = () =>
            {
                // The original event is global and carries no chest or player identity.
                // AndroidOfflineProfile swaps its UserProfile on commit, so validate its stable owner and resolve the current profile.
                if (NetworkServer.active && ReferenceEquals(Run.instance, profileAwardRun) && profileAwardRun &&
                    profileAwardRun.GetType() == typeof(Run) && coordinator.worldPlayer == profileAwardBody && profileAwardBody &&
                    profileAwardBody.master == profileAwardMaster && profileAwardMaster &&
                    profileAwardMaster.GetBody() == profileAwardBody && coordinator.directorPlayer &&
                    coordinator.directorPlayer.master == profileAwardMaster && !coordinator.directorPlayer.networkUser &&
                    !coordinator.directorPlayer.isConnected && coordinator.resultsSaveSystem != null &&
                    ReferenceEquals(coordinator.resultsSaveSystem, profileAwardSaveSystem) &&
                    ReferenceEquals(PlatformSystems.saveSystem, profileAwardSaveSystem) && profileAwardStore != null &&
                    ReferenceEquals(profileAwardSaveSystem.local, profileAwardStore))
                {
                    var currentProfile = profileAwardStore.profile;
                    if (currentProfile != null && ReferenceEquals(profileAwardSaveSystem.userProfile, currentProfile) &&
                        currentProfile.canSave && !currentProfile.loggedIn && !currentProfile.isClaimed && currentProfile.saveID == 0)
                        RecordOfflineOriginalEvent("FindTimedChest",
                                                   "EntityStates.TimedChest.Opening.onOpened (global; no sender or chest identity)");
                }
            };
            Opening.onOpened += profileTimedChestOpened;
            coordinator.Check(player && player.master && player.master.inventory && player.master.inventory == player.inventory &&
                                  !coordinator.directorPlayer.networkUser && discoveryInventory == null,
                              "Owned offline player pickup discovery identity missing");
            discoveryInventory = player.inventory;
            discoveryItem = index => RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
            discoveryEquipment = (index, slot) => RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
            discoveryKeyItem = index => RecordProfileDiscovery(PickupCatalog.FindPickupIndex(index));
            discoveryInventory.onItemAddedClient += discoveryItem;
            discoveryInventory.onEquipmentChangedClient += discoveryEquipment;
            discoveryInventory.onKeyItemAddedClient += discoveryKeyItem;
        }
        void RecordProfileDiscovery(PickupIndex pickup)
        {
            if (coordinator.r.profile == null || !coordinator.r.profile.ready || !pickup.isValid)
                return;
            coordinator.Check(discoveryInventory != null && coordinator.resultsSaveSystem.local != null && NetworkClient.active,
                              "Original pickup event has no owned offline player context");
            if ((coordinator.r.nova != null && coordinator.r.nova.diagnosticInput) || coordinator.IsRunAssisted())
            {
                coordinator.r.profile.assistedDiscoveriesExcluded++;
                return;
            }
            pendingDiscovery = null;
            if (coordinator.resultsSaveSystem.local.DiscoverPickup(pickup))
            {
                coordinator.Check(pendingDiscovery != null && pendingDiscovery.discovered,
                                  "Native discovery report missing after profile commit");
                coordinator.r.profile.discovery = pendingDiscovery;
                coordinator.resultsSaveSystem.userProfile = coordinator.resultsSaveSystem.local.profile;
                coordinator.r.profile.discoveredPickups++;
                ObserveAndroidProfile();
                coordinator.Save();
            }
        }
        void ObserveOfflineTeleporterProgression(TeleporterInteraction teleporter)
        {
            if (coordinator.r.profile == null || !coordinator.r.profile.ready || teleporter != coordinator.worldTeleporter)
                return;
            coordinator.Check(coordinator.resultsStats && coordinator.resultsStats.currentStats != null &&
                                  coordinator.resultsSaveSystem.local != null && coordinator.androidProgression != null,
                              "Original charged-stage achievement lacks its offline profile/stat context");
            var scene = SceneCatalog.GetSceneDefForCurrentScene();
            var stats = coordinator.resultsStats.currentStats;
            var body = coordinator.worldPlayer;
            var health = body ? body.healthComponent : null;
            if (scene && scene.sceneType == SceneType.Stage && health && health.alive)
            {
                if (profileTeleporterCharging && !profileTeleporterHit)
                    RecordOfflineOriginalEvent("CompleteTeleporterWithoutInjury");
                if (health.combinedHealthFraction <= 0.1f)
                    RecordOfflineOriginalEvent("ChargeTeleporterWhileNearDeath");
            }
            profileTeleporterCharging = false;
            coordinator.r.profile.threeStageChargedEvents++;
            // The shipped Toolbot server tracker applies this stat on the first charged
            // teleporter. Its NetworkUser is absent in the owned offline session.
            if (!profileFirstTeleporterRecorded && Run.instance && Run.instance.stageClearCount == 0)
            {
                stats.PushStatValue(RoR2.Stats.StatDef.firstTeleporterCompleted, 1uL);
                profileFirstTeleporterRecorded = true;
                coordinator.r.profile.firstTeleporterCompletedStat = stats.GetStatValueULong(RoR2.Stats.StatDef.firstTeleporterCompleted);
            }
            bool eligible = Run.instance && Run.instance.GetType() == typeof(Run) && scene && scene.stageOrder == 3 &&
                            stats.GetStatValueULong(RoR2.Stats.StatDef.totalDeaths) == 0;
            if (!eligible)
            {
                coordinator.Save();
                return;
            }
            coordinator.r.profile.threeStageEligible = true;
            if (coordinator.r.world != null && coordinator.r.world.diagnosticInputEver ||
                coordinator.r.nova != null && coordinator.r.nova.diagnosticInput || coordinator.r.developerSurvivorOverride ||
                coordinator.IsRunAssisted())
            {
                coordinator.r.profile.threeStageAssistedExcluded = true;
                coordinator.Save();
                return;
            }
            var awarded = coordinator.resultsSaveSystem.local.AwardObservedEvent(
                candidate =>
                {
                    coordinator.r.profile.threeStageAward =
                        coordinator.androidProgression.ApplyThreeStageCandidate(candidate, stats, scene);
                    return coordinator.r.profile.threeStageAward.granted;
                });
            coordinator.Check(coordinator.r.profile.threeStageAward != null && awarded == coordinator.r.profile.threeStageAward.granted,
                              "Original third-stage award transaction disagrees with committed profile");
            coordinator.r.profile.threeStageAwarded = awarded;
            coordinator.resultsSaveSystem.userProfile = coordinator.resultsSaveSystem.local.profile;
            ObserveAndroidProfile();
            coordinator.Save();
        }
        void RecordOfflineOriginalEvent(string identifier, string eventSource = null)
        {
            if (coordinator.r.profile == null || !coordinator.r.profile.ready || !NetworkServer.active || !coordinator.worldPlayer ||
                !coordinator.worldPlayer.master || profileObservedEvents.Contains(identifier))
                return;
            coordinator.Check(coordinator.resultsSaveSystem.local != null && coordinator.androidProgression != null,
                              "Original event achievement lacks its offline profile owner");
            profileObservedEvents.Add(identifier);
            bool assisted = coordinator.r.world != null && coordinator.r.world.diagnosticInputEver ||
                            coordinator.r.nova != null && coordinator.r.nova.diagnosticInput || coordinator.r.developerSurvivorOverride ||
                            coordinator.IsRunAssisted();
            AndroidProgressionBoundary.EventAwardReport report;
            if (assisted)
                report =
                    new AndroidProgressionBoundary.EventAwardReport { identifier = identifier, eventSource = eventSource,
                                                                      blocked =
                                                                          "Developer-assisted run excluded from permanent progression" };
            else
            {
                report = null;
                bool awarded;
                try
                {
                    awarded = coordinator.resultsSaveSystem.local.AwardObservedEvent(
                        candidate =>
                        {
                            report = coordinator.androidProgression.ApplyObservedEventCandidate(candidate, identifier);
                            report.eventSource = eventSource;
                            return report.granted;
                        });
                }
                catch
                {
                    // The reservation blocked reentrant callbacks during the transaction.
                    // A failed transaction must allow a later genuine event to retry.
                    profileObservedEvents.Remove(identifier);
                    throw;
                }
                coordinator.Check(report != null && awarded == report.granted,
                                  "Original event award transaction disagrees with committed profile");
                coordinator.resultsSaveSystem.userProfile = coordinator.resultsSaveSystem.local.profile;
                ObserveAndroidProfile();
            }
            coordinator.r.profile.eventAwards.Add(report);
            coordinator.Save();
        }
        Guid ProfileRunIdentity(AndroidRunEntry entry)
        {
            var stem = System.IO.Path.GetFileNameWithoutExtension(entry.file);
            Guid id;
            coordinator.Check(stem.StartsWith("run-") && Guid.TryParseExact(stem.Substring(4), "N", out id) && id != Guid.Empty,
                              "Owned profile result identity invalid");
            return Guid.ParseExact(stem.Substring(4), "N");
        }
        void ReconcileAndroidProfile(AndroidOfflineProfile local)
        {
            // A result is written before its profile delta. Replay only post-birth,
            // unassisted native reports when a crash or backup restore lost that delta.
            foreach (var entry in coordinator.resultsLedger.runs)
            {
                var id = ProfileRunIdentity(entry);
                if (entry.debugAssisted || !local.ShouldApply(id))
                    continue;
                var report = RunReport.Load(System.IO.Path.GetFileNameWithoutExtension(entry.file));
                coordinator.Check(report != null && report.runGuid == id && report.gameEnding &&
                                      report.gameEnding.cachedName == entry.ending && report.gameEnding.isWin == entry.win &&
                                      report.playerInfoCount == 1 && report.GetPlayerInfo(0).statSheet != null,
                                  "Owned native result reconciliation differs");
                if (local.ApplyResult(id, report.GetPlayerInfo(0).statSheet))
                    coordinator.r.profile.reconciledRuns++;
            }
        }
        void ObserveAndroidProfile()
        {
            if (coordinator.r.profile == null || !coordinator.r.profile.ready)
                return;
            coordinator.r.profile.appliedRuns = coordinator.resultsSaveSystem.local.appliedRuns;
            coordinator.r.profile.baselineRuns = coordinator.resultsSaveSystem.local.baselineRuns;
            coordinator.r.profile.kills =
                coordinator.resultsSaveSystem.local.profile.statSheet.GetStatValueULong(RoR2.Stats.StatDef.totalKills);
            coordinator.androidProgression.ValidateProfile(coordinator.resultsSaveSystem.local.profile);
            coordinator.r.profile.earnedUnlocks = coordinator.resultsSaveSystem.local.profile.statSheet.GetUnlockableCount();
            coordinator.r.profile.earnedCoins = coordinator.resultsSaveSystem.local.profile.coins;
        }
        public void PersistResult(bool assisted)
        {
            if (coordinator.r.profile == null || !coordinator.r.profile.ready)
                return;
            coordinator.r.profile.assistedExcluded = assisted;
            if (!assisted)
            {
                coordinator.r.profile.resultApplied = coordinator.resultsSaveSystem.local.ApplyResult(
                    coordinator.resultsRunReport.runGuid, coordinator.resultsRunReport.GetPlayerInfo(0).statSheet);
                coordinator.resultsSaveSystem.userProfile = coordinator.resultsSaveSystem.local.profile;
            }
            ObserveAndroidProfile();
        }
        public void Dispose()
        {
            if (profileProgressionCharge != null)
            {
                TeleporterInteraction.onTeleporterChargedGlobal -= profileProgressionCharge;
                profileProgressionCharge = null;
            }
            profileFirstTeleporterRecorded = false;
            if (profileTeleporterBegin != null)
            {
                TeleporterInteraction.onTeleporterBeginChargingGlobal -= profileTeleporterBegin;
                profileTeleporterBegin = null;
            }
            if (profileTeleporterDamage != null)
            {
                GlobalEventManager.onClientDamageNotified -= profileTeleporterDamage;
                profileTeleporterDamage = null;
            }
            profileTeleporterCharging = false;
            profileTeleporterHit = false;
            if (profileEliteDeath != null)
            {
                GlobalEventManager.onDeathProcServer -= profileEliteDeath;
                profileEliteDeath = null;
            }
            if (profileQuickBoss != null)
            {
                BossGroup.onBossGroupDefeatedServer -= profileQuickBoss;
                profileQuickBoss = null;
            }
            if (profileMountainBoss != null)
            {
                BossGroup.onBossGroupDefeatedServer -= profileMountainBoss;
                profileMountainBoss = null;
            }
            if (profileLoopStage != null)
            {
                Stage.onServerStageBegin -= profileLoopStage;
                profileLoopStage = null;
            }
            if (profileTeleporterExit != null)
            {
                SceneExitController.onBeginExit -= profileTeleporterExit;
                profileTeleporterExit = null;
            }
            if (profileColossusExit != null)
            {
                SceneExitControllerColossusPortal.onBeginExit -= profileColossusExit;
                profileColossusExit = null;
            }
            if (profileTimedChestOpened != null)
            {
                Opening.onOpened -= profileTimedChestOpened;
                profileTimedChestOpened = null;
            }
            profileAwardRun = null;
            profileAwardBody = null;
            profileAwardMaster = null;
            profileAwardSaveSystem = null;
            profileAwardStore = null;
            profileObservedEvents.Clear();
            if (!ownsProfileContext)
            {
                previewLoadoutBody = BodyIndex.None;
                previewLoadoutSkills = null;
                appliedLoadoutSkills = null;
                previewLoadoutSkin = 0;
                coordinator.offlinePendingLoadout = null;
                coordinator.offlineLoadoutEdited = false;
                return;
            }
            if (!ReferenceEquals(discoveryInventory, null))
            {
                discoveryInventory.onItemAddedClient -= discoveryItem;
                discoveryInventory.onEquipmentChangedClient -= discoveryEquipment;
                discoveryInventory.onKeyItemAddedClient -= discoveryKeyItem;
                discoveryInventory = null;
                discoveryItem = null;
                discoveryEquipment = null;
                discoveryKeyItem = null;
            }
            try
            {
                if (coordinator.resultsSaveSystem.local != null && coordinator.resultsSaveSystem.local.profile.saveRequestPending)
                    coordinator.resultsSaveSystem.local.Save();
            }
            catch (Exception error)
            {
                // Preserve the save failure but finish every owned teardown. A failed disk
                // write must not root a previous session's globals or permit its restart.
                if (coordinator.r.profile != null)
                    coordinator.r.profile.error = error.ToString();
                coordinator.r.error += " Android profile save during cleanup: " + error;
                coordinator.r.success = false;
                if (string.IsNullOrEmpty(coordinator.r.firstFailure))
                {
                    coordinator.r.firstFailure = error.GetBaseException().Message;
                    coordinator.r.firstFailurePhase = "android-profile-cleanup-save";
                }
            }
            pendingDiscovery = null;
            if (coordinator.androidProgression != null)
            {
                coordinator.androidProgression.Dispose();
                coordinator.androidProgression = null;
            }
            UserProfile.defaultProfile = priorDefaultProfile;
            RewardField(typeof(XmlUtility), "ValueReplacements").SetValue(null, priorProfileRedirects);
            if (ownsProfileRedirectLease)
            {
                if (profileRedirectLease.IsValid())
                    Addressables.Release(profileRedirectLease);
                ownsProfileRedirectLease = false;
            }
            foreach (var node in profileViewablesRoot.children.ToArray())
                if (!priorProfileNodes.Contains(node))
                    node.SetParent(null);
            foreach (var key in profileViewablesMap.Keys.ToArray())
                if (!priorProfileViewables.ContainsKey(key))
                    profileViewablesMap.Remove(key);
            coordinator.Check(priorProfileViewables.All(pair => profileViewablesMap.ContainsKey(pair.Key) &&
                                                                ReferenceEquals(profileViewablesMap[pair.Key], pair.Value)),
                              "Foreign viewable identity changed");
            foreach (var pair in priorProfileSurvivors)
                pair.Key.survivorIndex = pair.Value;
            foreach (var pair in priorProfileCatalog)
                pair.Key.SetValue(null, pair.Value);
            priorProfileSurvivors.Clear();
            priorProfileCatalog.Clear();
            coordinator.resultsSaveSystem.local = null;
            coordinator.resultsSaveSystem.userProfile = null;
            ownsProfileContext = false;
            if (coordinator.r.profile != null)
                coordinator.r.profile.cleaned = true;
            previewLoadoutBody = BodyIndex.None;
            previewLoadoutSkills = null;
            appliedLoadoutSkills = null;
            previewLoadoutSkin = 0;
            coordinator.offlinePendingLoadout = null;
            coordinator.offlineLoadoutEdited = false;
        }
    }
}
