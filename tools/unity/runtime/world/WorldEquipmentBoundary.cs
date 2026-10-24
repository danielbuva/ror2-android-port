// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldEquipmentSupport, PrepareWorldEquipment (WorldEquipmentSession); teardown CleanupWorldEquipment (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Supplies eligible shipped equipment content and input/lifecycle scheduling.
// Original grants, activation dispatch, buffs, healing and cooldowns execute unchanged.
public sealed partial class PortSession
{
    [Serializable]
    public class EquipmentActionObservation
    {
        public string equipment;
        public float seconds, health, armor, crit;
        public int stock;
    }
    [Serializable]
    public class WorldEquipmentReport
    {
        public bool ready, cleaned;
        public string equipment, error,
            scope =
                "Original equipment pickup/activation/cooldown; owned input/scheduling, source presentation approximation, no stock profile unlocks.";
        public int definitions, eligible, stock, maxStock, ticks, activations, ammoPacks, sourceBarrels, openedBarrels;
        public float cooldown;
        public List<EquipmentActionObservation> actions = new List<EquipmentActionObservation>();
        public List<FlightEquipmentObservation> flightObjects = new List<FlightEquipmentObservation>();
        public int ownedFlightDeathCallbacksRemoved;
        public bool flightCleaned;
        public ObjectiveRendererObservation[] temporaryEffectViews;
    }
    // Shared with world input, native barrel population and flight equipment.
    readonly List<ChestBehavior> worldEquipmentChests = new List<ChestBehavior>();
    EquipmentSlot worldEquipmentSlot;
    bool worldEquipmentTouch;
    NovaInputBridge worldEquipmentBridge;
    WorldEquipmentSession worldEquipmentSession;
    WorldEquipmentSession GetWorldEquipmentSession()
    {
        if (worldEquipmentSession == null)
            worldEquipmentSession = new WorldEquipmentSession(this);
        return worldEquipmentSession;
    }
    EquipmentDef[] WorldEquipmentDefs(SessionConfig cfg)
    {
        return GetWorldEquipmentSession().WorldEquipmentDefs(cfg);
    }
    BuffDef[] WorldEquipmentBuffs(SessionConfig cfg)
    {
        return GetWorldEquipmentSession().WorldEquipmentBuffs(cfg);
    }
    IEnumerable<EquipmentDef> EligibleWorldEquipment()
    {
        return GetWorldEquipmentSession().EligibleWorldEquipment();
    }
    GameObject[] PrepareWorldEquipmentSupport(SessionConfig cfg)
    {
        return GetWorldEquipmentSession().PrepareWorldEquipmentSupport(cfg);
    }
    void PrepareWorldEquipment(CharacterBody player, SessionConfig cfg)
    {
        GetWorldEquipmentSession().PrepareWorldEquipment(player, cfg);
    }
    void TickWorldEquipment()
    {
        GetWorldEquipmentSession().TickWorldEquipment();
    }
    void ObserveWorldEquipment(bool force = false)
    {
        GetWorldEquipmentSession().ObserveWorldEquipment(force);
    }
    void WorldEquipmentStimulus(NovaInputBridge bridge, float elapsed)
    {
        GetWorldEquipmentSession().WorldEquipmentStimulus(bridge, elapsed);
    }
    void CleanupWorldEquipment()
    {
        GetWorldEquipmentSession().Dispose();
    }
    void AddEquipmentBarrel(SessionConfig cfg, Vector3 origin)
    {
        GetWorldEquipmentSession().AddEquipmentBarrel(cfg, origin);
    }
    ChestBehavior NextAutomaticWorldChest(CharacterBody player)
    {
        return GetWorldEquipmentSession().NextAutomaticWorldChest(player);
    }
    void DrawWorldEquipment()
    {
        GetWorldEquipmentSession().DrawWorldEquipment();
    }

    // Create on first use and retain for partial setup, repeated cleanup and later
    // observations. Dispose keeps flight cleanup before scheduler and callback reset.
    sealed class WorldEquipmentSession : IDisposable
    {
        readonly PortSession coordinator;
        Action worldEquipmentFixed, worldEquipmentInventoryFixed;
        Action<EquipmentSlot, EquipmentIndex> worldEquipmentActivated;
        static readonly FieldInfo[] worldEquipmentEffectFields =
            new[] { "elephantDefenseEffectInstance", "lifestealOnHitEffectInstance", "teamWarCryEffectInstance" }
                .Select(name => typeof(CharacterBody).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic))
                .ToArray();
        EquipmentDef[] worldEquipmentDefinitions;
        float equipmentLastInput = -100;
        public WorldEquipmentSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public EquipmentDef[] WorldEquipmentDefs(SessionConfig cfg)
        {
            if (cfg.worldEquipmentAssets == null || cfg.worldEquipmentAssets.Length == 0)
                return new EquipmentDef[0];
            var names = new[] { "Fruit",          "CritOnUse", "GainArmor", "LifestealOnHit", "GoldGat", "PassiveHealing",
                                "CommandMissile", "Saw",       "Blackhole", "TeamWarCry",     "Jetpack", "FireBallDash" };
            coordinator.Check(cfg.worldEquipmentAssets.Length == names.Length, "Equipment source context differs");
            worldEquipmentDefinitions =
                cfg.worldEquipmentAssets.Select(x => coordinator.artifactBundle.LoadAsset<EquipmentDef>(x)).ToArray();
            for (int i = 0; i < names.Length; i++)
            {
                var def = worldEquipmentDefinitions[i];
                coordinator.Check(def && def.name == names[i], "Original equipment definition missing: " + names[i]);
                coordinator.BindEnemyDefinition(typeof(RoR2Content.Equipment), names[i], def);
                if (i < 4 || i >= 6)
                    coordinator.Check(!def.unlockableDef && !def.requiredExpansion && def.canDrop && !def.isLunar && !def.isBoss,
                                      "Equipment requires unavailable ownership/profile: " + names[i]);
            }
            return worldEquipmentDefinitions;
        }
        public BuffDef[] WorldEquipmentBuffs(SessionConfig cfg)
        {
            if (cfg.worldEquipmentBuffAssets == null || cfg.worldEquipmentBuffAssets.Length == 0)
                return new BuffDef[0];
            var names = new[] { "FullCrit", "ElephantArmorBoost", "LifeSteal", "TeamWarCry" };
            coordinator.Check(cfg.worldEquipmentBuffAssets.Length == names.Length, "Equipment buff context differs");
            var defs = cfg.worldEquipmentBuffAssets.Select(x => coordinator.artifactBundle.LoadAsset<BuffDef>(x)).ToArray();
            for (int i = 0; i < names.Length; i++)
            {
                coordinator.Check(defs[i] && defs[i].name == "bd" + names[i], "Original equipment buff missing");
                coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs), names[i], defs[i]);
            }
            return defs;
        }
        public IEnumerable<EquipmentDef> EligibleWorldEquipment()
        {
            if (Resources.Load<TextAsset>("WholeCatalogBootstrap") && coordinator.r.integratedWorld)
                return EquipmentCatalog.allEquipment.Select(index => EquipmentCatalog.GetEquipmentDef(index))
                    .Where(def => def && def.canDrop && !def.requiredExpansion && coordinator.HasOwnedProfileUnlock(def.unlockableDef));
            return (worldEquipmentDefinitions ?? new EquipmentDef[0]).Where(x => x.name != "GoldGat" && x.name != "PassiveHealing");
        }
        public GameObject[] PrepareWorldEquipmentSupport(SessionConfig cfg)
        {
            if (cfg.worldEquipmentSupportPaths == null || cfg.worldEquipmentSupportPaths.Length == 0)
                return new GameObject[0];
            coordinator.Check(cfg.worldEquipmentSupportPaths.Length == 12, "Equipment/proc provider closure differs");
            var effects = new List<GameObject>();
            foreach (var path in cfg.worldEquipmentSupportPaths)
            {
                int i = Array.IndexOf(cfg.objectiveSupportPaths, path);
                coordinator.Check(i >= 0, "Equipment/proc provider missing: " + path);
                var source = coordinator.objectiveSupportSources[i];
                coordinator.Check(source && source.GetComponentsInChildren<Component>(true).All(x => x),
                                  "Equipment/proc source reference missing: " + path);
                coordinator.worldNativeLootLeaseBaselines.Add(
                    i, (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                           .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                           .GetValue(coordinator.objectiveSupportLeases[i]));
                if (source.GetComponent<EffectComponent>())
                {
                    if (!GameAudioOriginalOwner.Ready)
                        source.GetComponent<EffectComponent>().soundName = null;
                    effects.Add(source);
                }
                else if (source.GetComponent<RoR2.Projectile.ProjectileController>() != null)
                {
                    var ghost = coordinator.OriginalProjectileGhost(source.GetComponent<RoR2.Projectile.ProjectileController>());
                    coordinator.Check(
                        (ghost || (source.name == "GravSphere" && source.GetComponentsInChildren<Renderer>(true).Length > 0)) &&
                            source.GetComponent<UnityEngine.Networking.NetworkIdentity>(),
                        "Original equipment projectile/network contract absent");
                    var roots = new List<GameObject> { source };
                    if (ghost)
                        roots.Add(ghost);
                    foreach (var component in source.GetComponents<Component>())
                        foreach (var field in component.GetType().GetFields(BindingFlags.Public | BindingFlags.Instance))
                        {
                            if (field.FieldType != typeof(GameObject))
                                continue;
                            var effect = field.GetValue(component) as GameObject;
                            if (effect && effect.GetComponent<EffectComponent>())
                            {
                                roots.Add(effect);
                                effects.Add(effect);
                            }
                        }
                    foreach (var root in roots.Distinct())
                    {
                        foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
                        {
                            if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                                continue;
                            coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                            coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                        }
                        coordinator.PresentCommerceModel(root.transform);
                    }
                }
                else if (source.name == "JetpackController" || source.name == "FireballVehicle")
                    coordinator.PrepareFlightEquipmentSource(source, effects);
                else if (source.name == "AmmoPack")
                {
                    var pickup = source.GetComponentInChildren<AmmoPickup>(true);
                    coordinator.Check(pickup && pickup.baseObject == source && pickup.teamFilter &&
                                          source.GetComponent<UnityEngine.Networking.NetworkIdentity>() && pickup.pickupEffect,
                                      "Original ammo pickup linkage missing");
                    effects.Add(pickup.pickupEffect);
                }
                else
                {
                    coordinator.Check(source.GetComponent<TemporaryVisualEffect>(), "Unknown equipment support source: " + path);
                    var field = typeof(CharacterBody)
                                    .GetNestedType("AssetReferences", BindingFlags.NonPublic)
                                    .GetField(source.name == "ElephantDefense"  ? "elephantDefenseEffectPrefab"
                                              : source.name == "TeamWarCryAura" ? "teamWarCryEffectPrefab"
                                                                                : "lifestealOnHitEffectPrefab",
                                              BindingFlags.Public | BindingFlags.Static);
                    coordinator.Check(field != null && field.GetValue(null) == null, "Unowned equipment visual context");
                    coordinator.worldLootEffectSlots.Add(field, null);
                    field.SetValue(null, source);
                    // These prefabs bypass EffectCatalog; bind the same source-driven programs
                    // before original CharacterBody creates their native temporary instances.
                    foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
                    {
                        if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                            continue;
                        coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                        coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                    }
                    coordinator.PresentCommerceModel(source.transform);
                }
            }
            foreach (var source in effects.Distinct())
            {
                coordinator.Check(source.GetComponent<EffectComponent>(), "Equipment/proc effect identity absent");
                if (!GameAudioOriginalOwner.Ready)
                    source.GetComponent<EffectComponent>().soundName = null;
            }
            return effects.Distinct().ToArray();
        }
        public void PrepareWorldEquipment(CharacterBody player, SessionConfig cfg)
        {
            if (worldEquipmentDefinitions == null)
                return;
            coordinator.r.world.equipment =
                new WorldEquipmentReport { definitions = worldEquipmentDefinitions.Length, eligible = EligibleWorldEquipment().Count() };
            coordinator.worldEquipmentSlot = player.equipmentSlot;
            coordinator.Check(coordinator.worldEquipmentSlot && !coordinator.worldEquipmentSlot.enabled &&
                                  coordinator.worldEquipmentSlot.equipmentIndex == EquipmentIndex.None,
                              "Unowned equipment scheduler");
            Call(coordinator.worldEquipmentSlot, "UpdateAuthority");
            coordinator.Check((bool)typeof(EquipmentSlot)
                                  .GetField("hasEffectiveAuthority", BindingFlags.Instance | BindingFlags.NonPublic)
                                  .GetValue(coordinator.worldEquipmentSlot),
                              "Original equipment authority missing");
            worldEquipmentFixed = (Action)Delegate.CreateDelegate(
                typeof(Action), coordinator.worldEquipmentSlot,
                typeof(EquipmentSlot).GetMethod("FixedUpdate", BindingFlags.Instance | BindingFlags.NonPublic));
            if (!player.inventory.isActiveAndEnabled)
                worldEquipmentInventoryFixed = (Action)Delegate.CreateDelegate(
                    typeof(Action), player.inventory,
                    typeof(Inventory).GetMethod("FixedUpdate", BindingFlags.Instance | BindingFlags.NonPublic));
            worldEquipmentActivated = (slot, index) =>
            {
                if (slot != coordinator.worldEquipmentSlot)
                    return;
                var def = EquipmentCatalog.GetEquipmentDef(index);
                coordinator.Check(EligibleWorldEquipment().Contains(def), "Unsupported equipment activated");
                if (def.name == "Jetpack" || def.name == "FireBallDash")
                    coordinator.worldFlightDiscoveryUntil = Time.realtimeSinceStartup + 5;
                coordinator.r.world.equipment.activations++;
                coordinator.r.world.equipment.actions.Add(
                    new EquipmentActionObservation { equipment = def.name, seconds = Run.instance.GetRunStopwatch(), stock = slot.stock,
                                                     health = player.healthComponent.health, armor = player.armor, crit = player.crit });
            };
            EquipmentSlot.onServerEquipmentActivated += worldEquipmentActivated;
            coordinator.r.world.equipment.ready = true;
        }
        public void TickWorldEquipment()
        {
            if (worldEquipmentFixed == null || !coordinator.worldPlayer || !coordinator.worldPlayer.healthComponent.alive)
                return;
            try
            {
                if (worldEquipmentInventoryFixed != null)
                    worldEquipmentInventoryFixed();
                worldEquipmentFixed();
                coordinator.r.world.equipment.ticks++;
            }
            catch (Exception e)
            {
                coordinator.r.world.equipment.error = e.ToString();
                worldEquipmentFixed = null;
                coordinator.Save();
            }
        }
        public void ObserveWorldEquipment(bool force = false)
        {
            var report = coordinator.r.world.equipment;
            if (report == null)
                return;
            long began = System.Diagnostics.Stopwatch.GetTimestamp();
            coordinator.ObserveFlightEquipment();
            coordinator.r.performance.flightMs += PerformanceMs(began);
            coordinator.Check(string.IsNullOrEmpty(report.error), "Original equipment lifecycle failed: " + report.error);
            began = System.Diagnostics.Stopwatch.GetTimestamp();
            var def = EquipmentCatalog.GetEquipmentDef(coordinator.worldEquipmentSlot.equipmentIndex);
            report.equipment = def ? def.name : "";
            report.stock = coordinator.worldEquipmentSlot.stock;
            report.maxStock = coordinator.worldEquipmentSlot.maxStock;
            report.cooldown = coordinator.worldEquipmentSlot.cooldownTimer;
            report.sourceBarrels = coordinator.worldEquipmentChests.Count(x => x);
            report.openedBarrels = coordinator.worldEquipmentChests.Count(x => x && x.NetworkisChestOpened);
            coordinator.r.performance.equipmentStateMs += PerformanceMs(began);
            began = System.Diagnostics.Stopwatch.GetTimestamp();
            foreach (var field in worldEquipmentEffectFields)
            {
                var effect = (TemporaryVisualEffect)field.GetValue(coordinator.worldPlayer);
                if (effect && !coordinator.worldLootTemporaryEffects.Contains(effect.gameObject))
                {
                    coordinator.worldLootTemporaryEffects.Add(effect.gameObject);
                    report.temporaryEffectViews =
                        effect.GetComponentsInChildren<Renderer>(true).Select(coordinator.ObserveOwnedSurface).ToArray();
                }
            }
            coordinator.r.performance.temporaryEffectMs += PerformanceMs(began);
            began = System.Diagnostics.Stopwatch.GetTimestamp();
            var ammo = force ? Resources.FindObjectsOfTypeAll<AmmoPickup>().Where(x => x && x.gameObject.scene.IsValid()).ToArray()
                             : NetworkServer.objects.Values.Where(x => x && x.name == "AmmoPack(Clone)")
                                   .Select(x => x.GetComponentInChildren<AmmoPickup>(true))
                                   .Where(x => x)
                                   .ToArray();
            foreach (var pickup in ammo)
                if (coordinator.worldNativeLootObjects.Add(pickup.baseObject))
                {
                    coordinator.worldObjects.Add(pickup.baseObject);
                    report.ammoPacks++;
                }
            coordinator.r.performance.ammoMs += PerformanceMs(began);
        }
        public void WorldEquipmentStimulus(NovaInputBridge bridge, float elapsed)
        {
            bridge.diagnosticEquipment = false;
            // Isolated skill diagnostics never request the automatic equipment
            // action. Preserve explicit touch/manual requests through the bridge.
            if (bridge.isolatedDiagnosticSkillInput)
                return;
            if (coordinator.r.world.equipment == null)
                return;
            if (coordinator.DeveloperEquipmentStimulus(bridge, elapsed))
                return;
            if (coordinator.worldEquipmentSlot.stock > 0 && coordinator.worldEquipmentSlot.equipmentIndex != EquipmentIndex.None &&
                elapsed - equipmentLastInput > 45)
            {
                bridge.diagnosticEquipment = true;
                equipmentLastInput = elapsed;
            }
        }
        public void Dispose()
        {
            ObserveWorldEquipment(true);
            coordinator.CleanupFlightEquipment();
            worldEquipmentFixed = null;
            worldEquipmentInventoryFixed = null;
            coordinator.worldEquipmentTouch = false;
            coordinator.worldEquipmentChests.Clear();
            equipmentLastInput = -100;
            if (worldEquipmentActivated != null)
                EquipmentSlot.onServerEquipmentActivated -= worldEquipmentActivated;
            worldEquipmentActivated = null;
            worldEquipmentDefinitions = null;
            coordinator.worldEquipmentSlot = null;
            coordinator.worldEquipmentBridge = null;
            if (coordinator.r.world != null && coordinator.r.world.equipment != null)
                coordinator.r.world.equipment.cleaned = true;
        }
        public void AddEquipmentBarrel(SessionConfig cfg, Vector3 origin)
        {
            if (string.IsNullOrEmpty(cfg.worldEquipmentChestAsset))
                return;
            var source = coordinator.artifactBundle.LoadAsset<GameObject>(cfg.worldEquipmentChestAsset);
            coordinator.Check(source && source.name == "EquipmentBarrel", "Original equipment barrel absent");
            var chest = source.GetComponent<ChestBehavior>();
            coordinator.Check(chest && chest.dropTable && Run.instance.availableEquipmentDropList.Count == EligibleWorldEquipment().Count(),
                              "Original equipment loot domain absent");
            var table = chest.dropTable as BasicPickupDropTable;
            coordinator.Check(table, "Equipment source drop table type differs");
            table.RegenerateDropTable(Run.instance);
            coordinator.Check(chest.dropTable.GetPickupCount() == EligibleWorldEquipment().Count(), "Source equipment table mismatch");
            coordinator.OwnChestAnimationSources(source.GetComponent<ModelLocator>().modelTransform, "EquipmentBarrelArmature|Open");
            foreach (var offset in new[] { new Vector3(-8, 0, 4), new Vector3(8, 0, 4) })
            {
                var obj = coordinator.CreateWorldInteractable(source, origin + offset, true);
                if (obj)
                {
                    var owned = obj.GetComponent<ChestBehavior>();
                    coordinator.worldChests.Add(owned);
                    coordinator.worldEquipmentChests.Add(owned);
                }
            }
        }
        public ChestBehavior NextAutomaticWorldChest(CharacterBody player)
        {
            // Diagnostic route chooses a normal purchase; it never grants equipment or bypasses cost.
            if (coordinator.r.liveCatalogs != null)
            {
                // Save earned money for a native EquipmentBarrel while the slot is empty;
                // shopping an ordinary chest first can consume the exact currency needed.
                if (player.inventory.currentEquipmentIndex == EquipmentIndex.None)
                {
                    var equipment = coordinator.worldEquipmentChests
                                        .Where(x =>
                                               {
                                                   if (!x || x.NetworkisChestOpened)
                                                       return false;
                                                   var purchase = x.GetComponent<PurchaseInteraction>();
                                                   return purchase && purchase.available && purchase.costType == CostTypeIndex.Money;
                                               })
                                        .OrderBy(x => Vector3.SqrMagnitude(x.transform.position - player.corePosition))
                                        .FirstOrDefault();
                    if (equipment)
                    {
                        var cost = equipment.GetComponent<PurchaseInteraction>().cost;
                        return player.master.money >= cost ? equipment : null;
                    }
                }
                var affordable = coordinator.worldChests
                                     .Where(x =>
                                            {
                                                if (!x || x.NetworkisChestOpened)
                                                    return false;
                                                var purchase = x.GetComponent<PurchaseInteraction>();
                                                return purchase && purchase.available && purchase.costType == CostTypeIndex.Money &&
                                                       player.master.money >= purchase.cost;
                                            })
                                     .ToArray();
                return affordable.OrderBy(x => Vector3.SqrMagnitude(x.transform.position - player.corePosition)).FirstOrDefault();
            }
            if (player.inventory.currentEquipmentIndex == EquipmentIndex.None)
            {
                var equipment = coordinator.worldEquipmentChests.FirstOrDefault(x => x && !x.NetworkisChestOpened);
                if (equipment)
                    return equipment;
            }
            return coordinator.worldChests.FirstOrDefault(x => x && !x.NetworkisChestOpened &&
                                                               !coordinator.worldEquipmentChests.Contains(x));
        }
        public void DrawWorldEquipment()
        {
            if (coordinator.r.world.equipment == null)
                return;
            if (GUI.Button(new Rect(Screen.width - 205, Screen.height - 180, 185, 45), "Use equipment"))
            {
                if (coordinator.worldEquipmentBridge)
                    coordinator.worldEquipmentBridge.touchEquipment = true;
            }
        }
    }
}
