// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldDotSupport (WorldDotSession); teardown CleanupWorldDots (Dispose), then FinishWorldDotCleanup.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Bind shipped DOT content; original catalog, stacks, ticks and damage stay native.
public sealed partial class PortSession
{
    [Serializable]
    public class DotObservation
    {
        public string type;
        public int inflictions, damageEvents;
        public float damage;
    }
    [Serializable]
    public class WorldDotReport
    {
        public bool ready, cleaned;
        public int definitions, daggerSpawns, peakControllers;
        public string scope =
            "Original DOT definitions, damage and six source burn/poison visual families; no expansion or unlock grants. Registration is not proc acceptance; audio unavailable.";
        public string[] effectTypes;
        public List<DotObservation> observations = new List<DotObservation>();
    }
    // Shared with integrated-world cleanup verification.
    bool ownsWorldDots;
    WorldDotSession worldDotSession;
    WorldDotSession GetWorldDotSession()
    {
        if (worldDotSession == null)
            worldDotSession = new WorldDotSession(this);
        return worldDotSession;
    }
    BuffDef[] WorldDotBuffs(SessionConfig cfg)
    {
        return GetWorldDotSession().WorldDotBuffs(cfg);
    }
    DotObservation WorldDotRow(DotController.DotIndex index)
    {
        return GetWorldDotSession().WorldDotRow(index);
    }
    void BindWorldBurnEffect(string fieldName, string materialPath, string prefabPath)
    {
        GetWorldDotSession().BindWorldBurnEffect(fieldName, materialPath, prefabPath);
    }
    GameObject[] PrepareWorldDotSupport(SessionConfig cfg)
    {
        return GetWorldDotSession().PrepareWorldDotSupport(cfg);
    }
    void CleanupWorldDots()
    {
        GetWorldDotSession().Dispose();
    }
    void FinishWorldDotCleanup()
    {
        GetWorldDotSession().FinishWorldDotCleanup();
    }

    // Retain after Dispose: native stacks and bindings are released first; pool
    // cleanup stays at its later coordinator call site after the original yields.
    sealed class WorldDotSession : IDisposable
    {
        readonly PortSession coordinator;
        object previousWorldDotDefs;
        readonly Dictionary<FieldInfo, BurnEffectController.EffectParams> previousWorldBurnEffects =
            new Dictionary<FieldInfo, BurnEffectController.EffectParams>();
        DotController.OnDotInflictedServerGlobalDelegate worldDotInflicted;
        Action<DamageReport> worldDotDamage;
        readonly List<GameObject> worldDotPoolSources = new List<GameObject>();
        public WorldDotSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public BuffDef[] WorldDotBuffs(SessionConfig cfg)
        {
            if (cfg.worldDotBuffAssets == null || cfg.worldDotBuffAssets.Length == 0)
                return new BuffDef[0];
            var names = new[] { "Bleeding",     "OnFire",   "Poisoned",  "Blight", "SuperBleed",
                                "StrongerBurn", "Fracture", "lunarruin", "Frost",  "Electrocuted" };
            var owners = new[] { typeof(RoR2Content.Buffs), typeof(RoR2Content.Buffs), typeof(RoR2Content.Buffs), typeof(RoR2Content.Buffs),
                                 typeof(RoR2Content.Buffs), typeof(DLC1Content.Buffs), typeof(DLC1Content.Buffs), typeof(DLC2Content.Buffs),
                                 typeof(DLC2Content.Buffs), typeof(DLC3Content.Buffs) };
            coordinator.Check(cfg.worldDotBuffAssets.Length == names.Length, "Original DOT comparison closure differs");
            return cfg.worldDotBuffAssets
                .Select((path, i) =>
                        {
                            var def = coordinator.artifactBundle.LoadAsset<BuffDef>(path);
                            coordinator.Check(def && def.name == "bd" + names[i], "Original DOT buff missing: " + names[i]);
                            coordinator.BindEnemyDefinition(owners[i], names[i], def);
                            return def;
                        })
                .ToArray();
        }
        public DotObservation WorldDotRow(DotController.DotIndex index)
        {
            var name = index.ToString();
            var row = coordinator.r.dots.observations.FirstOrDefault(x => x.type == name);
            if (row == null)
            {
                row = new DotObservation { type = name };
                coordinator.r.dots.observations.Add(row);
            }
            return row;
        }
        public void BindWorldBurnEffect(string fieldName, string materialPath, string prefabPath)
        {
            var field = typeof(BurnEffectController).GetField(fieldName, BindingFlags.Static | BindingFlags.Public);
            coordinator.Check(field != null && field.FieldType == typeof(BurnEffectController.EffectParams) && field.GetValue(null) == null,
                              "Foreign original DOT effect: " + fieldName);
            var material = WholeCatalogComposed.LoadOwnedContent<Material>(materialPath);
            var prefab = WholeCatalogComposed.LoadOwnedContent<GameObject>(prefabPath);
            coordinator.Check(material && prefab && prefab.GetComponent<BurnEffectControllerHelper>(),
                              "Original DOT effect source differs: " + fieldName);
            var copy = new Material(material);
            AndroidMaterialPresentation.Apply(material, copy);
            coordinator.worldMaterials.Add(copy);
            foreach (var renderer in prefab.GetComponentsInChildren<Renderer>(true))
                if (!coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                {
                    coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                    coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                }
            coordinator.PresentCommerceModel(prefab.transform);
            worldDotPoolSources.Add(prefab);
            previousWorldBurnEffects.Add(field, null);
            field.SetValue(null, new BurnEffectController.EffectParams { overlayMaterial = copy, fireEffectPrefab = prefab });
        }
        public GameObject[] PrepareWorldDotSupport(SessionConfig cfg)
        {
            if (cfg.worldDotBuffAssets == null || cfg.worldDotBuffAssets.Length == 0)
                return new GameObject[0];
            var field = typeof(DotController).GetField("dotDefs", BindingFlags.Static | BindingFlags.NonPublic);
            previousWorldDotDefs = field.GetValue(null);
            var burnFields =
                new[] { "normalEffect", "helfireEffect", "poisonEffect", "blightEffect", "strongerBurnEffect", "lynxPoisonEffect" }
                    .Select(name => typeof(BurnEffectController).GetField(name, BindingFlags.Static | BindingFlags.Public))
                    .ToArray();
            coordinator.Check(previousWorldDotDefs == null && DotController.readOnlyInstancesList.Count == 0 &&
                                  burnFields.All(field => field != null && field.FieldType == typeof(BurnEffectController.EffectParams) &&
                                                          field.GetValue(null) == null),
                              "Unowned original DOT context");
            coordinator.ownsWorldDots = true;
            StaticCall(typeof(DotController), "InitDotCatalog");
            var defs = (Array)field.GetValue(null);
            coordinator.Check(defs != null && defs.Length == (int)DotController.DotIndex.Count,
                              "Original DOT catalog initialization differs");
            foreach (DotController.DotIndex index in Enum.GetValues(typeof(DotController.DotIndex)))
            {
                if (index < DotController.DotIndex.Bleed || index >= DotController.DotIndex.Count)
                    continue;
                var def = DotController.GetDotDef(index);
                coordinator.Check(def != null && def.interval > 0 &&
                                      (!def.associatedBuff || BuffCatalog.GetBuffDef(def.associatedBuff.buffIndex) == def.associatedBuff),
                                  "Original DOT definition/buff not indexed: " + index);
            }
            var effects = new List<GameObject>();
            var paths = new[] { "Prefabs/NetworkedObjects/DotController", "Prefabs/BleedEffect", "Prefabs/FireEffect",
                                "Prefabs/Effects/ImpactEffects/IgniteExplosionVFX", "Prefabs/Projectiles/DaggerProjectile" };
            foreach (var path in paths)
            {
                int i = Array.IndexOf(cfg.objectiveSupportPaths, path);
                coordinator.Check(i >= 0, "Original DOT provider absent: " + path);
                var source = coordinator.objectiveSupportSources[i];
                coordinator.Check(source && source.GetComponentsInChildren<Component>(true).All(x => x),
                                  "Original DOT source references absent: " + path);
                var roots = new List<GameObject> { source };
                if (source.name == "DotController")
                {
                    coordinator.Check(source.GetComponent<DotController>() && source.GetComponent<NetworkIdentity>(),
                                      "Original DOT network prefab absent");
                    var slot = typeof(DotController).GetField("DotControllerPrefab");
                    coordinator.Check(slot.GetValue(null) == null, "Unowned DOT prefab");
                    coordinator.worldLootEffectSlots.Add(slot, null);
                    slot.SetValue(null, source);
                }
                else if (source.name == "DaggerProjectile")
                {
                    var slot = typeof(GlobalEventManager.CommonAssets).GetField("daggerPrefab");
                    coordinator.Check(slot.GetValue(null) == null, "Unowned original dagger binding");
                    coordinator.worldLootEffectSlots.Add(slot, null);
                    slot.SetValue(null, source);
                    var ghost = coordinator.OriginalProjectileGhost(source.GetComponent<RoR2.Projectile.ProjectileController>());
                    coordinator.Check(ghost && source.GetComponent<NetworkIdentity>(), "Original dagger projectile/ghost absent");
                    roots.Add(ghost);
                    foreach (var component in source.GetComponents<Component>())
                        foreach (var value in component.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public))
                        {
                            if (value.FieldType != typeof(GameObject))
                                continue;
                            var effect = value.GetValue(component) as GameObject;
                            if (effect && effect.GetComponent<EffectComponent>())
                            {
                                roots.Add(effect);
                                effects.Add(effect);
                            }
                        }
                }
                else if (source.name == "IgniteExplosionVFX")
                {
                    var slot = typeof(GlobalEventManager.CommonAssets).GetField("igniteOnKillExplosionEffectPrefab");
                    coordinator.Check(slot.GetValue(null) == null, "Unowned original ignite binding");
                    coordinator.worldLootEffectSlots.Add(slot, null);
                    slot.SetValue(null, source);
                    coordinator.Check(source.GetComponent<EffectComponent>(), "Original ignite effect absent");
                    effects.Add(source);
                }
                else
                {
                    worldDotPoolSources.Add(source);
                    coordinator.Check((source.name == "BleedEffect" || source.GetComponent<BurnEffectControllerHelper>()),
                                      "Original DOT pooled effect contract absent");
                    coordinator.worldNativeLootLeaseBaselines.Add(
                        i, (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                               .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                               .GetValue(coordinator.objectiveSupportLeases[i]));
                }
                foreach (var renderer in roots.Distinct().SelectMany(x => x.GetComponentsInChildren<Renderer>(true)).Distinct())
                {
                    if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                        continue;
                    coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                    coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                }
                foreach (var root in roots.Distinct())
                    coordinator.PresentCommerceModel(root.transform);
            }
            var overlay = coordinator.artifactBundle.LoadAsset<Material>(cfg.worldDotBurnMaterialAsset);
            coordinator.Check(overlay && overlay.name == "matOnFire", "Original burn overlay absent");
            var copy = new Material(overlay);
            AndroidMaterialPresentation.Apply(overlay, copy);
            coordinator.worldMaterials.Add(copy);
            var normal = typeof(BurnEffectController).GetField("normalEffect", BindingFlags.Static | BindingFlags.Public);
            previousWorldBurnEffects.Add(normal, null);
            BurnEffectController.normalEffect = new BurnEffectController.EffectParams {
                startSound = "Play_item_proc_igniteOnKill_Loop", stopSound = "Stop_item_proc_igniteOnKill_Loop", overlayMaterial = copy,
                fireEffectPrefab = coordinator.objectiveSupportSources[Array.IndexOf(cfg.objectiveSupportPaths, "Prefabs/FireEffect")]
            };
            BindWorldBurnEffect("helfireEffect", "Assets/WholeGame/RoR2/Base/Equipment/BurnNearby/matOnHelfire.mat",
                                "Assets/WholeGame/RoR2/Base/Equipment/BurnNearby/HelfireEffect.prefab");
            BurnEffectController.helfireEffect.startSound = "Play_item_proc_igniteOnKill_Loop";
            BurnEffectController.helfireEffect.stopSound = "Stop_item_proc_igniteOnKill_Loop";
            BindWorldBurnEffect("poisonEffect", "Assets/WholeGame/RoR2/Base/Characters/Croco/matPoisoned.mat",
                                "Assets/WholeGame/RoR2/Base/Characters/Croco/PoisonEffect.prefab");
            BindWorldBurnEffect("blightEffect", "Assets/WholeGame/RoR2/Base/Characters/Croco/matBlighted.mat",
                                "Assets/WholeGame/RoR2/Base/Characters/Croco/BlightEffect.prefab");
            BindWorldBurnEffect("strongerBurnEffect", "Assets/WholeGame/RoR2/DLC1/Items/StrengthenBurn/matStrongerBurn.mat",
                                "Assets/WholeGame/RoR2/DLC1/Items/StrengthenBurn/StrongerBurnEffect.prefab");
            // This source binding does not make DLC4 content available to a run.
            BindWorldBurnEffect("lynxPoisonEffect", "Assets/WholeGame/RoR2/DLC4/Common/Buffs/bdLynxPoison/matLynxPoisoned.mat",
                                "Assets/WholeGame/RoR2/DLC4/Common/Buffs/bdLynxPoison/LynxPoisonEffect.prefab");
            coordinator.r.dots =
                new WorldDotReport { ready = true, definitions = defs.Length,
                                     effectTypes =
                                         previousWorldBurnEffects.Keys.Select(field => field.Name).OrderBy(name => name).ToArray() };
            worldDotInflicted = (DotController controller, ref InflictDotInfo info) =>
            {
                coordinator.Check(controller && controller.victimObject == info.victimObject && controller.netId.Value != 0,
                                  "Native DOT victim/network binding differs");
                WorldDotRow(info.dotIndex).inflictions++;
                coordinator.r.dots.peakControllers =
                    Mathf.Max(coordinator.r.dots.peakControllers, DotController.readOnlyInstancesList.Count);
            };
            worldDotDamage = report =>
            {
                if (report.damageInfo.dotIndex == DotController.DotIndex.None)
                    return;
                var row = WorldDotRow(report.damageInfo.dotIndex);
                row.damageEvents++;
                row.damage += report.damageDealt;
            };
            DotController.onDotInflictedServerGlobal += worldDotInflicted;
            GlobalEventManager.onServerDamageDealt += worldDotDamage;
            return effects.Distinct().ToArray();
        }
        public void Dispose()
        {
            if (!coordinator.ownsWorldDots)
                return;
            if (worldDotInflicted != null)
                DotController.onDotInflictedServerGlobal -= worldDotInflicted;
            if (worldDotDamage != null)
                GlobalEventManager.onServerDamageDealt -= worldDotDamage;
            worldDotInflicted = null;
            worldDotDamage = null;
            // Empty native stacks while their victim/buff/server context is still valid.
            foreach (var controller in DotController.readOnlyInstancesList.ToArray())
                if (controller)
                {
                    controller.enabled = false;
                    var stacks = (IList) typeof(DotController)
                                     .GetField("dotStackList", BindingFlags.Instance | BindingFlags.NonPublic)
                                     .GetValue(controller);
                    if (NetworkServer.active && stacks != null)
                        while (stacks.Count > 0)
                            Call(controller, "RemoveDotStackAtServer", stacks.Count - 1);
                    Call(controller, "HandleDestroy");
                }
            typeof(DotController).GetField("dotDefs", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, previousWorldDotDefs);
            foreach (var entry in previousWorldBurnEffects)
                entry.Key.SetValue(null, entry.Value);
            previousWorldBurnEffects.Clear();
            coordinator.ownsWorldDots = false;
        }
        public void FinishWorldDotCleanup()
        {
            if (coordinator.r.dots == null)
                return;
            coordinator.Check(!coordinator.ownsWorldDots && DotController.readOnlyInstancesList.Count == 0,
                              "Native DOT instances survived owned teardown");
            var pools = (Dictionary<GameObject, EffectPool>)RewardField(typeof(EffectManager), "_EffectPrefabMap").GetValue(null);
            var cache = (IDictionary)RewardField(typeof(EffectManager), "_ShouldUsePooledEffectMap").GetValue(null);
            foreach (var source in worldDotPoolSources)
            {
                EffectPool pool;
                if (pools.TryGetValue(source, out pool))
                {
                    foreach (var effect in pool.InUse.ToArray())
                        pool.ReturnObject(effect);
                    EffectManager.ClearPool(source);
                    pool.Kill();
                }
                cache.Remove(source);
            }
            worldDotPoolSources.Clear();
            coordinator.r.dots.cleaned = true;
        }
    }
}
