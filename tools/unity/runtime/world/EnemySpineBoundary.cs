// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareEnemyConfigs, PrepareEnemy (EnemySpineSession); teardown CleanupEnemy, then VerifyEnemyCleanup (awaited in Start), then CleanupEnemyConfigs (Dispose via spawn-config cleanup).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using EntityStates;
using RoR2;
using RoR2.CharacterAI;
using RoR2.Navigation;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Original actor/AI/input/state/physics. Only owned audio/visual binding and diagnostic placement.
public sealed partial class PortSession
{
    [Serializable]
    public class EnemyReport
    {
        public bool graphReady, spawned, linked, authority, targetFound, dead, cleaned, naturalBodyDestroyed, naturalMasterDestroyed,
            preservedCorpseObserved;
        public int groundNodes, airNodes, aiFrames, headbutts, enemyDamageEvents, playerDamageEvents, groundedFrames, groundedBeforeDamage,
            collisionMask, stableMask, deathGlobalEvents, playerKillsBefore, playerKillsAfter;
        public float pathLength, planarPathLength, planarBeforeDamage, maxFall, maxFallBeforeDamage, maxIncomingForce, health, playerHealth,
            damageToEnemy, damageToPlayer;
        public string aiState, bodyState;
        public Vector3 position, spawnPosition, velocity;
        public string[] excludedCallbacks;
    }
    // Shared with rewards, stage transport, director actors and population setup.
    GameObject enemyTemplates, enemyMasterHost, enemySceneHost;
    CharacterMaster enemyMaster;
    CharacterBody enemyBody, enemyPlayer;
    BaseAI enemyAI;
    EnemySpineSession enemySpineSession;
    EnemySpineSession GetEnemySpineSession()
    {
        if (enemySpineSession == null)
            enemySpineSession = new EnemySpineSession(this);
        return enemySpineSession;
    }
    void BindEnemyDefinition(Type holder, string name, UnityEngine.Object value)
    {
        GetEnemySpineSession().BindEnemyDefinition(holder, name, value);
    }
    ArtifactDef[] EnemyArtifacts(SessionConfig cfg, ArtifactDef fall)
    {
        return GetEnemySpineSession().EnemyArtifacts(cfg, fall);
    }
    void PrepareEnemyElites(SessionConfig cfg)
    {
        GetEnemySpineSession().PrepareEnemyElites(cfg);
    }
    EliteDef[] ComposedEliteDefinitions(SessionConfig cfg)
    {
        return GetEnemySpineSession().ComposedEliteDefinitions(cfg);
    }
    EquipmentDef[] ComposedEliteEquipment(SessionConfig cfg)
    {
        return GetEnemySpineSession().ComposedEliteEquipment(cfg);
    }
    BuffDef[] ComposedEliteBuffs(SessionConfig cfg)
    {
        return GetEnemySpineSession().ComposedEliteBuffs(cfg);
    }
    BuffDef[] EnemyDeathBuffs(SessionConfig cfg)
    {
        return GetEnemySpineSession().EnemyDeathBuffs(cfg);
    }
    EquipmentDef[] EnemyDeathEquipment(SessionConfig cfg)
    {
        return GetEnemySpineSession().EnemyDeathEquipment(cfg);
    }
    Type[] EnemyTypes()
    {
        return GetEnemySpineSession().EnemyTypes();
    }
    EntityStateConfiguration[] PrepareEnemyConfigs(SessionConfig cfg)
    {
        return GetEnemySpineSession().PrepareEnemyConfigs(cfg);
    }
    void EnemyExclusions()
    {
        GetEnemySpineSession().EnemyExclusions();
    }
    IEnumerator PrepareEnemy(CharacterBody player, SessionConfig cfg)
    {
        return GetEnemySpineSession().PrepareEnemy(player, cfg);
    }
    void EnemyDamage(DamageReport report)
    {
        GetEnemySpineSession().EnemyDamage(report);
    }
    void EnemyDeath(DamageReport report)
    {
        GetEnemySpineSession().EnemyDeath(report);
    }
    void ObserveEnemy()
    {
        GetEnemySpineSession().ObserveEnemy();
    }
    void CleanupEnemy()
    {
        GetEnemySpineSession().CleanupEnemy();
    }
    IEnumerator VerifyEnemyCleanup()
    {
        return GetEnemySpineSession().VerifyEnemyCleanup();
    }
    void CleanupEnemyConfigs()
    {
        GetEnemySpineSession().Dispose();
    }

    // Retain the owner for partial setup, repeated cleanup and later verification.
    // Actor destruction and awaited verification stay separate; Dispose restores configs.
    sealed class EnemySpineSession : IDisposable
    {
        readonly PortSession coordinator;
        Material enemyMaterial;
        SurfaceDef enemySurface;
        EntityState priorEnemyState;
        Vector3 priorEnemyPosition;
        GameObject enemyDetachedModel;
        readonly List<EntityStateConfiguration> enemyConfigs = new List<EntityStateConfiguration>();
        readonly Dictionary<FieldInfo, object> enemyStaticFields = new Dictionary<FieldInfo, object>();
        EliteDef[] priorEnemyElites;
        EliteIndex[] priorEnemyEliteList;
        bool ownsEnemyElites;
        public EnemySpineSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public void BindEnemyDefinition(Type holder, string name, UnityEngine.Object value)
        {
            var field = holder.GetField(name);
            coordinator.Check(field != null && field.GetValue(null) == null && value, "Existing or missing enemy death definition " + name);
            enemyStaticFields[field] = null;
            field.SetValue(null, value);
        }
        public ArtifactDef[] EnemyArtifacts(SessionConfig cfg, ArtifactDef fall)
        {
            if (!cfg.enemySpine)
                return new[] { fall };
            var wisp = coordinator.artifactBundle.LoadAsset<ArtifactDef>(cfg.enemyWispArtifactAsset);
            coordinator.Check(wisp && wisp.cachedName == "WispOnDeath", "Original death artifact missing");
            BindEnemyDefinition(typeof(RoR2Content.Artifacts), "WispOnDeath", wisp);
            if (!cfg.automaticDirector)
                return new[] { fall, wisp };
            var honor = coordinator.artifactBundle.LoadAsset<ArtifactDef>(cfg.enemyHonorArtifactAsset);
            coordinator.Check(honor && honor.cachedName == "EliteOnly", "Original Honor artifact missing");
            BindEnemyDefinition(typeof(RoR2Content.Artifacts), "EliteOnly", honor);
            return new[] { fall, wisp, honor };
        }
        public void PrepareEnemyElites(SessionConfig cfg)
        {
            var field = typeof(EliteCatalog).GetField("eliteDefs", BindingFlags.NonPublic | BindingFlags.Static);
            priorEnemyElites = (EliteDef[])field.GetValue(null);
            priorEnemyEliteList = EliteCatalog.eliteList.ToArray();
            coordinator.Check((priorEnemyElites == null || priorEnemyElites.Length == 0) && priorEnemyEliteList.Length == 0,
                              "Existing elite catalog");
            var names = new[] { "Poison", "Haunted", "Lunar", "Void" };
            var defs = cfg.enemyEliteAssets.Select(x => coordinator.artifactBundle.LoadAsset<EliteDef>(x)).ToArray();
            coordinator.Check(defs.Length == 4, "Measured death elite definitions missing");
            for (int i = 0; i < 4; i++)
            {
                coordinator.Check(defs[i] && defs[i].name == "ed" + names[i], "Original elite identity");
                BindEnemyDefinition(i == 3 ? typeof(DLC1Content.Elites) : typeof(RoR2Content.Elites), names[i], defs[i]);
            }
            var all = ComposedEliteDefinitions(cfg);
            ownsEnemyElites = true;
            PortSession.StaticCall(typeof(EliteCatalog), "SetEliteDefs", new object[] { all });
            foreach (var def in all)
                coordinator.Check(def.eliteIndex != EliteIndex.None && EliteCatalog.GetEliteDef(def.eliteIndex) == def,
                                  "Original elite catalog identity");
            if (coordinator.r.liveCatalogs != null)
                WholeCatalogComposed.PopulateDefinitionFields("Elites", all, "ed");
        }
        public EliteDef[] ComposedEliteDefinitions(SessionConfig cfg)
        {
            var definitions = cfg.enemyEliteAssets.Select(path => coordinator.artifactBundle.LoadAsset<EliteDef>(path));
            if (cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                definitions = definitions.Concat(WholeCatalogComposed.EliteDefinitions());
            var result = definitions.Distinct().ToArray();
            coordinator.Check(result.All(def => def) && result.Select(def => def.name).Distinct().Count() == result.Length,
                              "Original elite definition identity ambiguous");
            return result;
        }
        public EquipmentDef[] ComposedEliteEquipment(SessionConfig cfg)
        {
            return cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap")
                       ? ComposedEliteDefinitions(cfg).Select(def => def.eliteEquipmentDef).Where(def => def).Distinct().ToArray()
                       : new EquipmentDef[0];
        }
        public BuffDef[] ComposedEliteBuffs(SessionConfig cfg)
        {
            return ComposedEliteEquipment(cfg).Select(def => def.passiveBuffDef).Where(def => def).Distinct().ToArray();
        }
        public BuffDef[] EnemyDeathBuffs(SessionConfig cfg)
        {
            if (!cfg.enemySpine)
                return new BuffDef[0];
            var def = coordinator.artifactBundle.LoadAsset<BuffDef>(cfg.enemyDeathBuffAsset);
            coordinator.Check(def && def.name == "bdExtraLifeBuff", "Original death buff missing");
            BindEnemyDefinition(typeof(DLC2Content.Buffs), "ExtraLifeBuff", def);
            return new[] { def };
        }
        public EquipmentDef[] EnemyDeathEquipment(SessionConfig cfg)
        {
            if (!cfg.enemySpine)
                return new EquipmentDef[0];
            var names = new[] { "HealAndRevive", "HealAndReviveConsumed" };
            var defs = cfg.enemyDeathEquipment.Select(x => coordinator.artifactBundle.LoadAsset<EquipmentDef>(x)).ToArray();
            for (int i = 0; i < 2; i++)
            {
                coordinator.Check(defs[i] && defs[i].name == names[i], "Original death equipment missing");
                BindEnemyDefinition(typeof(DLC2Content.Equipment), names[i], defs[i]);
            }
            if (cfg.originalMoneyCost)
            {
                var card = coordinator.artifactBundle.LoadAsset<EquipmentDef>(cfg.multiShopCardAsset);
                coordinator.Check(card && card.name == "MultiShopCard", "Original money-cost comparison equipment missing");
                BindEnemyDefinition(typeof(DLC1Content.Equipment), "MultiShopCard", card);
                return defs.Concat(new[] { card }).ToArray();
            }
            return defs;
        }
        public Type[] EnemyTypes()
        {
            return new[] { typeof(EntityStates.BeetleMonster.SpawnState),
                           typeof(EntityStates.BeetleMonster.HeadbuttState),
                           typeof(EntityStates.AI.Walker.Wander),
                           typeof(EntityStates.AI.Walker.Combat),
                           typeof(EntityStates.AI.Walker.LookBusy),
                           typeof(EntityStates.AI.Walker.Guard),
                           typeof(GenericCharacterDeath),
                           typeof(HurtState),
                           typeof(HurtStateFlyer),
                           typeof(StunState),
                           typeof(SleepState),
                           typeof(EntityStates.Emote.SurpriseState),
                           typeof(EntityStates.EmotePoint) };
        }
        public EntityStateConfiguration[] PrepareEnemyConfigs(SessionConfig cfg)
        {
            coordinator.r.enemy = new EnemyReport();
            foreach (var type in EnemyTypes())
                foreach (var field in type.GetFields(BindingFlags.Public | BindingFlags.Static | BindingFlags.DeclaredOnly))
                    if (!field.IsInitOnly && !field.IsLiteral)
                        enemyStaticFields[field] = field.GetValue(null);
            foreach (var path in new[] { cfg.enemySpawnConfigAsset, cfg.enemyAttackConfigAsset, cfg.enemySleepConfigAsset })
            {
                var original = coordinator.artifactBundle.LoadAsset<EntityStateConfiguration>(path);
                coordinator.Check(original, "Original enemy state configuration missing");
                var copy = Instantiate(original);
                copy.serializedFieldsCollection.serializedFields = original.serializedFieldsCollection.serializedFields.ToArray();
                for (int i = 0; i < copy.serializedFieldsCollection.serializedFields.Length; i++)
                {
                    var field = copy.serializedFieldsCollection.serializedFields[i];
                    var member = ((Type)copy.targetType).GetField(field.fieldName);
                    if (member != null && member.FieldType == typeof(string) &&
                        field.fieldName.IndexOf("sound", StringComparison.OrdinalIgnoreCase) >= 0)
                        copy.serializedFieldsCollection.serializedFields[i].fieldValue.stringValue = "";
                    if (field.fieldName.IndexOf("effect", StringComparison.OrdinalIgnoreCase) >= 0)
                        copy.serializedFieldsCollection.serializedFields[i].fieldValue.objectValue = null;
                }
                enemyConfigs.Add(copy);
            }
            return enemyConfigs.ToArray();
        }
        public void EnemyExclusions()
        {
            EntityStates.BeetleMonster.HeadbuttState.attackSoundString = "";
            EntityStates.BeetleMonster.HeadbuttState.hitEffectPrefab = null;
            StunState.stunVfxPrefab = null;
        }
        public IEnumerator PrepareEnemy(CharacterBody player, SessionConfig cfg)
        {
            coordinator.enemyPlayer = player;
            PrepareEnemyElites(cfg);
            if (cfg.enemyRewards)
            {
                var rewards = coordinator.PrepareEnemyRewards(player, cfg);
                while (rewards.MoveNext())
                    yield return rewards.Current;
            }
            coordinator.Check(RunArtifactManager.instance && RoR2Content.Artifacts.WispOnDeath,
                              "Original enemy death artifact context missing");
            coordinator.Check(!RunArtifactManager.instance.IsArtifactEnabled(RoR2Content.Artifacts.WispOnDeath),
                              "Enemy fixture requires original disabled death artifact");
            coordinator.r.phase = "enemy-navigation-context";
            coordinator.Save();
            coordinator.Check(!SceneInfo.instance, "Existing original SceneInfo context");
            SceneInfo sceneInfo;
            if (coordinator.stageSourceObjects)
                sceneInfo = coordinator.ActivateSourceSceneInfo();
            else
            {
                coordinator.enemySceneHost = new GameObject("Owned original SceneInfo");
                coordinator.enemySceneHost.SetActive(false);
                SceneManager.MoveGameObjectToScene(coordinator.enemySceneHost, coordinator.stageGeometryScene);
                sceneInfo = coordinator.enemySceneHost.AddComponent<SceneInfo>();
                var groundGraphAsset =
                    coordinator.firstStageSpec == null ? cfg.enemyGroundGraphAsset : coordinator.firstStageSpec.groundGraph;
                var airGraphAsset = coordinator.firstStageSpec == null ? cfg.enemyAirGraphAsset : coordinator.firstStageSpec.airGraph;
                typeof(SceneInfo)
                    .GetField("groundNodesAsset", BindingFlags.NonPublic | BindingFlags.Instance)
                    .SetValue(sceneInfo, coordinator.artifactBundle.LoadAsset<NodeGraph>(groundGraphAsset));
                typeof(SceneInfo)
                    .GetField("airNodesAsset", BindingFlags.NonPublic | BindingFlags.Instance)
                    .SetValue(sceneInfo, coordinator.artifactBundle.LoadAsset<NodeGraph>(airGraphAsset));
                coordinator.enemySceneHost.SetActive(true);
            }
            yield return null;
            coordinator.r.enemy.groundNodes = sceneInfo.groundNodes.GetNodeCount();
            coordinator.r.enemy.airNodes = sceneInfo.airNodes.GetNodeCount();
            coordinator.r.enemy.graphReady =
                SceneInfo.instance == sceneInfo && coordinator.r.enemy.groundNodes > 0 && coordinator.r.enemy.airNodes > 0;
            coordinator.Check(coordinator.r.enemy.graphReady, "Original navigation context missing");
            if (coordinator.stageSourceObjects)
            {
                coordinator.r.stage.sourceSceneInfoActive = coordinator.r.enemy.graphReady;
                coordinator.r.stage.sourceStagePopulationActive =
                    ClassicStageInfo.instance == coordinator.sourceSceneInfoRoot.GetComponent<ClassicStageInfo>() &&
                    ClassicStageInfo.instance.monsterSelection != null;
                coordinator.Check(coordinator.r.stage.sourceStagePopulationActive, "Original source stage population did not initialize");
            }
            coordinator.enemyTemplates = new GameObject("Owned inactive enemy templates");
            coordinator.enemyTemplates.SetActive(false);
            var originalBody = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyBodyAsset);
            var bodyTemplate = Instantiate(originalBody, coordinator.enemyTemplates.transform);
            bodyTemplate.name = originalBody.name;
            bodyTemplate.SetActive(true);
            coordinator.r.phase = "enemy-template-binding";
            coordinator.Save();
            var templateBody = bodyTemplate.GetComponent<CharacterBody>();
            var locator = bodyTemplate.GetComponent<ModelLocator>();
            coordinator.Check(templateBody && locator && locator.modelTransform, "Original enemy template components missing");
            var model = locator.modelTransform;
            var animator = model.GetComponent<Animator>();
            coordinator.Check(animator, "Original enemy animator missing");
            animator.avatar = coordinator.artifactBundle.LoadAsset<Avatar>(cfg.enemyAvatarAsset);
            animator.runtimeAnimatorController = coordinator.artifactBundle.LoadAsset<RuntimeAnimatorController>(cfg.enemyControllerAsset);
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            coordinator.Check(animator.avatar && animator.runtimeAnimatorController, "Original enemy avatar/controller missing");
            foreach (var component in bodyTemplate.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (component.GetType().Name.StartsWith("Ak", StringComparison.Ordinal))
                {
                    DestroyImmediate(component);
                    continue;
                }
                if (component is DeathRewards)
                {
                    if (cfg.enemyRewards)
                        ((DeathRewards)component).logUnlockableDef = null;
                    else
                    {
                        DestroyImmediate(component);
                        continue;
                    }
                } // Reward/XP/drop producers are the next integration, not this empty-inventory actor fixture.
                // Same limited empty-inventory/local-server scope as the accepted player. These measured
                // callbacks require unprovided platform-clock, pause or equipment catalog contracts.
                if (component is RoR2.Networking.CharacterNetworkTransform || component is InteractionDriver || component is EquipmentSlot)
                    component.enabled = false;
                // Root gameplay callbacks remain original; inactive visual observers must not initiate new loaders.
                if (component.transform != bodyTemplate.transform)
                    component.enabled = component is HurtBox || component is HurtBoxGroup || component is HitBox ||
                                        component is HitBoxGroup || component is RootMotionAccumulator;
            }
            var sfx = templateBody.GetComponent<SfxLocator>();
            foreach (var field in typeof(SfxLocator).GetFields(BindingFlags.Public | BindingFlags.Instance))
                if (field.FieldType == typeof(string))
                    field.SetValue(sfx, null);
            var sourceMaterial = coordinator.artifactBundle.LoadAsset<Material>(cfg.enemyMaterialAsset);
            enemyMaterial = new Material(sourceMaterial);
            enemyMaterial.shader = Resources.Load<Shader>("CommandoMaterialPreview");
            enemyMaterial.shaderKeywords = new string[0];
            enemyMaterial.SetTexture("_MainTex", sourceMaterial.GetTexture("_MainTex"));
            enemyMaterial.SetColor("_Color", sourceMaterial.GetColor("_Color") * 2);
            enemyMaterial.SetFloat("_EmissionEnabled", 0); // Opaque diagnostic preview; source alpha is not a cutout contract.
            foreach (var renderer in model.GetComponentsInChildren<Renderer>(true))
            {
                renderer.gameObject.layer = 30;
                renderer.sharedMaterial = enemyMaterial;
                var skin = renderer as SkinnedMeshRenderer;
                if (skin)
                {
                    coordinator.Check(skin.sharedMesh && skin.sharedMesh.vertexCount > 0 &&
                                          (skin.bones.Length > 0 || (!animator.hasTransformHierarchy && animator.avatar.isValid &&
                                                                     skin.sharedMesh.bindposes.Length > 0)),
                                      "Original enemy skin/optimized-avatar contract missing");
                    skin.updateWhenOffscreen = true;
                }
            }
            var characterModel = model.GetComponent<CharacterModel>();
            characterModel.visibility =
                VisibilityLevel
                    .Invisible; // Its camera/overlay Start is excluded; original OnDeath may hide owned preview renderers without uninitialized/native RTPC work.
            for (int i = 0; i < characterModel.baseRendererInfos.Length; i++)
                characterModel.baseRendererInfos[i].defaultMaterial = enemyMaterial;
            var surfaces = bodyTemplate.GetComponentsInChildren<SurfaceDefProvider>(true);
            coordinator.Check(surfaces.Length > 0 && surfaces.All(x => x.surfaceDef == surfaces[0].surfaceDef),
                              "Original enemy impact surface identity missing");
            enemySurface = Instantiate(surfaces[0].surfaceDef);
            enemySurface.impactEffectPrefab = null;
            if (cfg.integratedWorld)
                enemySurface.impactSoundString = null;
            foreach (var surface in surfaces)
                surface.surfaceDef = enemySurface;
            GlobalEventManager.onServerDamageDealt += EnemyDamage;
            GlobalEventManager.onCharacterDeathServer += EnemyDeath;
            coordinator.r.enemy.playerKillsBefore = player.killCountServer;
            coordinator.r.enemy.excludedCallbacks =
                new[] { "CharacterNetworkTransform platform snapshot clock", "InteractionDriver pause/interaction context",
                        "EquipmentSlot targeting catalogs",
                        cfg.enemyRewards ? "Inventory automatic equipment refresh (only original UseAmbientLevel)"
                                         : "Inventory automatic equipment refresh (empty inventory only)",
                        cfg.enemyRewards ? "Optional logbook/profile drop" : "DeathRewards gold/XP/drop producers" };
            var position = player.transform.position + Vector3.forward * 9;
            RaycastHit ground;
            coordinator.Check(Physics.Raycast(position + Vector3.up * 20, Vector3.down, out ground, 50, LayerIndex.world.mask,
                                              QueryTriggerInteraction.Ignore),
                              "Original terrain enemy spawn floor missing");
            position = ground.point + Vector3.up * 2;
            // Updated original SpawnBody resolves through BodyCatalog, not master.bodyPrefab.
            coordinator.BindCatalogBodyTemplate(bodyTemplate);
            coordinator.r.phase = "original-enemy-master-spawn";
            coordinator.Save();
            if (cfg.enemyRewards)
            {
                var spawning = coordinator.SpawnRewardEnemy(bodyTemplate, position, player, cfg);
                while (spawning.MoveNext())
                    yield return spawning.Current;
            }
            else
            {
                coordinator.enemyMasterHost = Instantiate(coordinator.artifactBundle.LoadAsset<GameObject>(cfg.enemyMasterAsset));
                coordinator.enemyMasterHost.GetComponent<Inventory>().enabled = false;
                coordinator.enemyMasterHost.SetActive(true);
                coordinator.enemyMaster = coordinator.enemyMasterHost.GetComponent<CharacterMaster>();
                coordinator.Check(coordinator.enemyMaster.inventory.itemAcquisitionOrder.Count == 0 &&
                                      coordinator.enemyMaster.inventory.currentEquipmentIndex == EquipmentIndex.None,
                                  "Enemy callback exclusion requires original empty inventory");
                coordinator.enemyMaster.teamIndex = TeamIndex.Monster;
                NetworkServer.Spawn(coordinator.enemyMasterHost);
                coordinator.enemyMaster.bodyPrefab = bodyTemplate;
                coordinator.enemyBody =
                    coordinator.enemyMaster.SpawnBody(position, Quaternion.LookRotation(player.transform.position - position));
            }
            coordinator.Check(coordinator.enemyBody, "Original enemy spawn failed");
            coordinator.enemyAI = coordinator.enemyMasterHost.GetComponent<BaseAI>();
            priorEnemyPosition = coordinator.enemyBody.transform.position;
            coordinator.r.enemy.spawned = true;
            coordinator.r.enemy.linked =
                coordinator.enemyMaster.GetBody() == coordinator.enemyBody && coordinator.enemyBody.master == coordinator.enemyMaster;
            coordinator.Check(coordinator.r.enemy.linked, "Original enemy master/body linkage failure");
            coordinator.r.phase = "enemy-await-original-start";
            coordinator.Save();
            yield return null;
            coordinator.r.enemy.authority = coordinator.enemyBody.isServer && coordinator.enemyBody.hasEffectiveAuthority;
            coordinator.Check(coordinator.r.enemy.authority, "Original enemy authority after Start missing");
            coordinator.Check(coordinator.enemyAI.body == coordinator.enemyBody, "Original AI OnBodyStart did not adopt body");
            if (cfg.enemyRewards)
            {
                coordinator.r.rewards.spawnLevelAfterStart = coordinator.enemyBody.level;
                coordinator.Check(coordinator.enemyBody.level == 1, "Original directed enemy stats after Start failed");
            }
            // The lab collision matrix is not the original project's matrix. Use the accepted
            // recovered-world-only collision scope, including both actors' own hurtbox exclusions.
            var solver = coordinator.enemyBody.characterMotor.Motor;
            solver.CollidableLayers = LayerIndex.world.mask;
            solver.StableGroundLayers = LayerIndex.world.mask;
            solver.SetGroundSolvingActivation(true);
            coordinator.r.enemy.collisionMask = solver.CollidableLayers;
            coordinator.r.enemy.stableMask = solver.StableGroundLayers;
            coordinator.r.enemy.spawnPosition = coordinator.enemyBody.transform.position;
            enemyDetachedModel = coordinator.enemyBody.modelLocator.modelTransform.gameObject;
            coordinator.r.phase = "enemy-active";
            coordinator.Save();
        }
        public void EnemyDamage(DamageReport report)
        {
            coordinator.ObserveDirectorDamage(report);
            if (report.victimBody == coordinator.enemyBody)
            {
                coordinator.r.enemy.enemyDamageEvents++;
                coordinator.r.enemy.damageToEnemy += report.damageDealt;
                coordinator.r.enemy.maxIncomingForce = Mathf.Max(coordinator.r.enemy.maxIncomingForce, report.damageInfo.force.magnitude);
            }
            if (report.victimBody == coordinator.enemyPlayer)
            {
                coordinator.r.enemy.playerDamageEvents++;
                coordinator.r.enemy.damageToPlayer += report.damageDealt;
            }
        }
        public void EnemyDeath(DamageReport report)
        {
            coordinator.ObserveDirectorDeath(report);
            if (report.victimBody == coordinator.enemyBody)
                coordinator.r.enemy.deathGlobalEvents++;
        }
        public void ObserveEnemy()
        {
            coordinator.ObserveEnemyRewards();
            coordinator.ObserveOriginalNavigation();
            coordinator.ObserveDirectorActors();
            if (coordinator.enemyAI)
            {
                coordinator.r.enemy.aiFrames++;
                coordinator.r.enemy.targetFound |= coordinator.enemyAI.currentEnemy.characterBody == coordinator.enemyPlayer;
                if (coordinator.enemyAI.stateMachine.state != null)
                    coordinator.r.enemy.aiState = coordinator.enemyAI.stateMachine.state.GetType().FullName;
            }
            if (coordinator.enemyBody)
            {
                var state = EntityStateMachine.FindByCustomName(coordinator.enemyBody.gameObject, "Body").state;
                if (state != priorEnemyState && state is EntityStates.BeetleMonster.HeadbuttState)
                    coordinator.r.enemy.headbutts++;
                priorEnemyState = state;
                coordinator.r.enemy.bodyState = state == null ? "null" : state.GetType().FullName;
                coordinator.r.enemy.position = coordinator.enemyBody.transform.position;
                var delta = coordinator.r.enemy.position - priorEnemyPosition;
                coordinator.r.enemy.pathLength += delta.magnitude;
                delta.y = 0;
                coordinator.r.enemy.planarPathLength += delta.magnitude;
                coordinator.r.enemy.maxFall =
                    Mathf.Max(coordinator.r.enemy.maxFall, coordinator.r.enemy.spawnPosition.y - coordinator.r.enemy.position.y);
                coordinator.r.enemy.velocity = coordinator.enemyBody.characterMotor.velocity;
                if (coordinator.enemyBody.characterMotor.isGrounded)
                    coordinator.r.enemy.groundedFrames++;
                if (coordinator.r.enemy.enemyDamageEvents == 0)
                {
                    coordinator.r.enemy.planarBeforeDamage += delta.magnitude;
                    coordinator.r.enemy.maxFallBeforeDamage = coordinator.r.enemy.maxFall;
                    if (coordinator.enemyBody.characterMotor.isGrounded)
                        coordinator.r.enemy.groundedBeforeDamage++;
                }
                priorEnemyPosition = coordinator.r.enemy.position;
                coordinator.r.enemy.health = coordinator.enemyBody.healthComponent.health;
                coordinator.r.enemy.dead |= !coordinator.enemyBody.healthComponent.alive;
            }
            if (coordinator.enemyPlayer)
            {
                coordinator.r.enemy.playerHealth = coordinator.enemyPlayer.healthComponent.health;
                coordinator.r.enemy.playerKillsAfter = coordinator.enemyPlayer.killCountServer;
            }
            if (coordinator.r.enemy.dead)
            {
                coordinator.r.enemy.naturalBodyDestroyed = !coordinator.enemyBody;
                coordinator.r.enemy.naturalMasterDestroyed = !coordinator.enemyMasterHost;
                coordinator.r.enemy.preservedCorpseObserved |=
                    !coordinator.enemyBody && enemyDetachedModel && enemyDetachedModel.GetComponent<Corpse>();
            }
        }
        public void CleanupEnemy()
        {
            GlobalEventManager.onServerDamageDealt -= EnemyDamage;
            GlobalEventManager.onCharacterDeathServer -= EnemyDeath;
            if (coordinator.enemyMasterHost)
                NetworkServer.Destroy(coordinator.enemyMasterHost);
            if (coordinator.enemyBody)
                NetworkServer.Destroy(coordinator.enemyBody.gameObject);
            if (enemyDetachedModel)
                Destroy(
                    enemyDetachedModel); // Original ModelLocator relinquishes a corpse on death; the bounded fixture still owns that detached object.
            coordinator.CleanupDirectorActors();
            coordinator.CleanupRewardHosts();
            coordinator.RestoreCatalogBodyTemplates();
            if (coordinator.sourceSceneInfoRoot)
                coordinator.DeactivateSourceSceneInfo();
            if (coordinator.enemySceneHost)
                Destroy(coordinator.enemySceneHost);
            if (coordinator.enemyTemplates)
                Destroy(coordinator.enemyTemplates);
            if (enemyMaterial)
                Destroy(enemyMaterial);
            if (enemySurface)
                Destroy(enemySurface);
        }
        public IEnumerator VerifyEnemyCleanup()
        {
            if (coordinator.r.enemy == null)
                yield break;
            for (int i = 0; i < 3; i++)
                yield return null;
            var remaining = new[] { coordinator.enemyMasterHost ? "master" : null,
                                    coordinator.enemyBody ? "body" : null,
                                    enemyDetachedModel ? "model/corpse" : null,
                                    coordinator.enemySceneHost ? "scene context" : null,
                                    coordinator.enemyTemplates ? "templates" : null,
                                    enemyMaterial ? "material" : null,
                                    enemySurface ? "surface" : null,
                                    SceneInfo.instance ? "SceneInfo singleton" : null }
                                .Where(x => x != null)
                                .ToArray();
            coordinator.r.enemy.cleaned = remaining.Length == 0;
            coordinator.Check(coordinator.r.enemy.cleaned,
                              "Owned enemy destruction before provider release: " + string.Join(",", remaining));
            coordinator.VerifyDirectorActorCleanup();
            coordinator.Save();
        }
        public void Dispose()
        {
            if (ownsEnemyElites)
            {
                typeof(EliteCatalog).GetField("eliteDefs", BindingFlags.NonPublic | BindingFlags.Static).SetValue(null, priorEnemyElites);
                EliteCatalog.eliteList.Clear();
                EliteCatalog.eliteList.AddRange(priorEnemyEliteList);
                ownsEnemyElites = false;
            }
            foreach (var entry in enemyStaticFields)
                entry.Key.SetValue(null, entry.Value);
            enemyStaticFields.Clear();
            foreach (var cfg in enemyConfigs)
                if (cfg)
                    Destroy(cfg);
            enemyConfigs.Clear();
        }
    }
}
