// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldHealingItemSource, ObserveWorldHealingItems (WorldHealingItemsSession); teardown CleanupWorldHealingItems (Dispose).
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;

// Source providers and native callbacks only; no ward, pulse or plant algorithms.
public sealed partial class PortSession
{
    WorldHealingItemsSession worldHealingItemsSession;
    WorldHealingItemsSession GetWorldHealingItemsSession()
    {
        if (worldHealingItemsSession == null)
            worldHealingItemsSession = new WorldHealingItemsSession(this);
        return worldHealingItemsSession;
    }
    bool IsWorldHealingItemSource(string path)
    {
        return GetWorldHealingItemsSession().IsWorldHealingItemSource(path);
    }
    void PrepareWorldHealingItemSource(string path, GameObject source)
    {
        GetWorldHealingItemsSession().PrepareWorldHealingItemSource(path, source);
    }
    void ObserveWorldHealingItems(bool force = false)
    {
        GetWorldHealingItemsSession().ObserveWorldHealingItems(force);
    }
    void ObserveWorldWarbannerEffect(TemporaryVisualEffect effect)
    {
        GetWorldHealingItemsSession().ObserveWorldWarbannerEffect(effect);
    }
    void CleanupWorldHealingItems()
    {
        GetWorldHealingItemsSession().Dispose();
    }

    // Create on first use and retain for partial setup, repeated cleanup and later
    // observations. Dispose keeps native callback removal before instance teardown.
    sealed class WorldHealingItemsSession : IDisposable
    {
        readonly PortSession coordinator;
        static readonly string[] worldHealingItemNames = { "WarbannerWard", "InterstellarDeskPlant", "DeskplantWard",
                                                           "TeleporterHealNovaGenerator", "TeleporterHealNovaPulse" };
        static readonly FieldInfo worldWarbannerEffectField =
            typeof(CharacterBody).GetField("warbannerEffectInstance", BindingFlags.NonPublic | BindingFlags.Instance);
        readonly HashSet<GameObject> worldHealingItemInstances = new HashSet<GameObject>();
        Action<CharacterBody> worldWarbannerLevel;
        public WorldHealingItemsSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public bool IsWorldHealingItemSource(string path)
        {
            return path == "Prefabs/TemporaryVisualEffects/WarbannerBuffEffect" ||
                   worldHealingItemNames.Any(name => path == "Prefabs/NetworkedObjects/" + name);
        }
        public void PrepareWorldHealingItemSource(string path, GameObject source)
        {
            if (path == "Prefabs/TemporaryVisualEffects/WarbannerBuffEffect")
            {
                var effect = source.GetComponent<TemporaryVisualEffect>();
                coordinator.Check(effect && effect.visualTransform, "Original Warbanner temporary effect linkage absent");
                var field = typeof(CharacterBody)
                                .GetNestedType("AssetReferences", BindingFlags.NonPublic)
                                .GetField("warbannerEffectPrefab", BindingFlags.Public | BindingFlags.Static);
                coordinator.Check(field != null && field.GetValue(null) == null, "Unowned Warbanner temporary effect source");
                coordinator.worldLootEffectSlots.Add(field, null);
                field.SetValue(null, source);
                foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
                {
                    if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                        continue;
                    coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                    coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                }
                coordinator.PresentCommerceModel(source.transform);
                return;
            }
            coordinator.Check(path == "Prefabs/NetworkedObjects/" + source.name && source.GetComponent<NetworkIdentity>() &&
                                  source.GetComponent<TeamFilter>(),
                              "Original healing-item source/network/team identity differs");
            if (source.name == "WarbannerWard")
            {
                coordinator.Check(source.GetComponent<BuffWard>() && source.GetComponent<BuffWard>().buffDef == RoR2Content.Buffs.Warbanner,
                                  "Original Warbanner buff contract differs");
                var owner = typeof(RoR2.Items.WardOnLevelManager);
                var field = owner.GetField("wardPrefab", BindingFlags.NonPublic | BindingFlags.Static);
                coordinator.Check(field != null && field.GetValue(null) == null && worldWarbannerLevel == null,
                                  "Unowned native Warbanner callback/provider");
                coordinator.worldLootEffectSlots.Add(field, null);
                field.SetValue(null, source);
                worldWarbannerLevel = RoR2.Items.WardOnLevelManager.OnCharacterLevelUp;
                GlobalEventManager.onCharacterLevelUp += worldWarbannerLevel;
            }
            else if (source.name == "InterstellarDeskPlant")
            {
                var plant = source.GetComponent<DeskPlantController>();
                coordinator.Check(plant && plant.plantObject && plant.seedObject && source.GetComponent<EntityStateMachine>(),
                                  "Original Desk Plant state/presentation contract differs");
            }
            else if (source.name == "DeskplantWard")
                coordinator.Check(source.GetComponent<HealingWard>(), "Original Desk Plant healing ward missing");
            else
                coordinator.Check(source.GetComponent<EntityStateMachine>(), "Original teleporter healing state machine missing");
            foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
            {
                if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                    continue;
                coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
            }
            coordinator.PresentCommerceModel(source.transform);
        }
        public void ObserveWorldHealingItems(bool force = false)
        {
            if (coordinator.r.procContent == null || (!force && Time.frameCount % 30 != 0))
                return;
            if (force)
                foreach (var effect in Resources.FindObjectsOfTypeAll<TemporaryVisualEffect>())
                    ObserveWorldWarbannerEffect(effect);
            else
            {
                // CharacterBody owns the exact temporary visual instance. Read that source
                // field from live bodies instead of searching the entire loaded catalog.
                coordinator.Check(worldWarbannerEffectField != null, "Original Warbanner effect owner field absent");
                if (coordinator.worldPlayer)
                    ObserveWorldWarbannerEffect((TemporaryVisualEffect)worldWarbannerEffectField.GetValue(coordinator.worldPlayer));
                foreach (var actor in coordinator.directorActors)
                    if (actor.body)
                        ObserveWorldWarbannerEffect((TemporaryVisualEffect)worldWarbannerEffectField.GetValue(actor.body));
            }
            var instances = force ? Resources.FindObjectsOfTypeAll<GameObject>()
                                  : NetworkServer.objects.Values.Where(x => x).Select(x => x.gameObject).ToArray();
            foreach (var obj in instances.Where(x => x && x.scene.IsValid() &&
                                                     worldHealingItemNames.Any(name => x.name == name + "(Clone)")))
            {
                if (!worldHealingItemInstances.Add(obj))
                    continue;
                var identity = obj.GetComponent<NetworkIdentity>();
                coordinator.Check(identity && identity.netId.Value != 0 && NetworkServer.FindLocalObject(identity.netId) == obj,
                                  "Original healing-item local network ownership differs");
                coordinator.worldObjects.Add(obj);
                switch (obj.name)
                {
                case "WarbannerWard(Clone)":
                    coordinator.r.procContent.warbannerWards++;
                    break;
                case "InterstellarDeskPlant(Clone)":
                    coordinator.r.procContent.deskPlants++;
                    break;
                case "DeskplantWard(Clone)":
                    coordinator.r.procContent.deskplantWards++;
                    break;
                case "TeleporterHealNovaGenerator(Clone)":
                    coordinator.r.procContent.healNovaGenerators++;
                    break;
                case "TeleporterHealNovaPulse(Clone)":
                    coordinator.r.procContent.healNovaPulses++;
                    break;
                }
            }
        }
        public void ObserveWorldWarbannerEffect(TemporaryVisualEffect effect)
        {
            if (!effect || !effect.gameObject.scene.IsValid() || effect.name != "WarbannerBuffEffect(Clone)" ||
                coordinator.worldLootTemporaryEffects.Contains(effect.gameObject))
                return;
            coordinator.Check(effect.healthComponent &&
                                  effect.parentTransform == effect.healthComponent.GetComponent<CharacterBody>().coreTransform,
                              "Original Warbanner buff effect body linkage differs");
            coordinator.worldLootTemporaryEffects.Add(effect.gameObject);
            coordinator.r.procContent.warbannerBuffEffects++;
        }
        public void Dispose()
        {
            ObserveWorldHealingItems(true);
            if (worldWarbannerLevel != null)
            {
                GlobalEventManager.onCharacterLevelUp -= worldWarbannerLevel;
                worldWarbannerLevel = null;
            }
            foreach (var obj in worldHealingItemInstances)
                if (obj)
                    NetworkServer.Destroy(obj);
            worldHealingItemInstances.Clear();
        }
    }
}
