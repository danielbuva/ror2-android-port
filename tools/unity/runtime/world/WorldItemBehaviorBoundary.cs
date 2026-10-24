// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWholeItemBehaviorSupport, PrepareWorldItemBehaviorSupport, PrepareWorldItemBehaviors (WorldItemBehaviorSession); teardown CleanupWorldItemBehaviors (Dispose).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Items;
using RoR2.Orbs;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

// Scoped startup adapter; component assignment, stack refresh and simulation are native.
public sealed partial class PortSession
{
    [Serializable]
    public class ItemBehaviorReport
    {
        public bool ready, cleaned, sourceSupport;
        public int bodies, assignments, refreshes, mushroomWards, cloakObservations, whipBuffSamples, nearbyIndicators, wispOrbsPeak;
        public string[] definitions, normalLoot, bossRewards, requestedDeveloperGrants;
        public float whipPeakMoveSpeed;
        public List<LegendaryItemObservation> legendaryInstances = new List<LegendaryItemObservation>();
        public string scope =
            "Original item associations and effects with adapted provider leases and read-only observations. Normal loot, source boss rewards and requested developer grants are distinct; effect registration alone is not behavior acceptance.";
    }
    WorldItemBehaviorSession worldItemBehaviorSession;
    WorldItemBehaviorSession GetWorldItemBehaviorSession()
    {
        if (worldItemBehaviorSession == null)
            worldItemBehaviorSession = new WorldItemBehaviorSession(this);
        return worldItemBehaviorSession;
    }
    static FieldInfo MushroomPrefabField()
    {
        return WorldItemBehaviorSession.MushroomPrefabField();
    }
    BuffDef[] WorldItemBehaviorBuffs(SessionConfig cfg)
    {
        return GetWorldItemBehaviorSession().WorldItemBehaviorBuffs(cfg);
    }
    GameObject[] PrepareWorldItemBehaviorSupport(SessionConfig cfg)
    {
        return GetWorldItemBehaviorSession().PrepareWorldItemBehaviorSupport(cfg);
    }
    IEnumerator PrepareWholeItemBehaviorSupport(SessionConfig cfg)
    {
        return GetWorldItemBehaviorSession().PrepareWholeItemBehaviorSupport(cfg);
    }
    GameObject[] WholeItemBehaviorEffects()
    {
        return GetWorldItemBehaviorSession().WholeItemBehaviorEffects();
    }
    void PrepareWorldItemBehaviors(SessionConfig cfg)
    {
        GetWorldItemBehaviorSession().PrepareWorldItemBehaviors(cfg);
    }
    void RefreshWorldItemBehaviors(CharacterBody body)
    {
        GetWorldItemBehaviorSession().RefreshWorldItemBehaviors(body);
    }
    void RemoveWorldItemBehaviors(CharacterBody body)
    {
        GetWorldItemBehaviorSession().RemoveWorldItemBehaviors(body);
    }
    void ObserveWorldItemBehaviors()
    {
        GetWorldItemBehaviorSession().ObserveWorldItemBehaviors();
    }
    void CleanupWorldItemBehaviors()
    {
        GetWorldItemBehaviorSession().Dispose();
    }

    // Create on first use and retain after Dispose for partial support setup,
    // repeated cleanup and later calls. Static provider paths and keys stay static.
    sealed class WorldItemBehaviorSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly Dictionary<CharacterBody, BaseItemBodyBehavior[]> worldItemBehaviors =
            new Dictionary<CharacterBody, BaseItemBodyBehavior[]>();
        readonly HashSet<GameObject> worldMushroomWards = new HashSet<GameObject>();
        readonly HashSet<GameObject> worldNearbyIndicators = new HashSet<GameObject>();
        readonly Dictionary<string, AsyncOperationHandle<GameObject>> worldItemSupportLeases =
            new Dictionary<string, AsyncOperationHandle<GameObject>>();
        readonly Dictionary<string, int> worldItemSupportBaselines = new Dictionary<string, int>();
        static readonly string[] wholeItemSupportPaths = { "Prefabs/NetworkedObjects/NearbyDamageBonusIndicator",
                                                           "Prefabs/Effects/SprintActivate", "Prefabs/Effects/OrbEffects/WispOrbEffect" };
        static readonly string[] wholeItemSupportKeys = { "5ba295c0a3919a544939e6efe1ff17b3", "dce12bd0bdcbe9b4ea19ca0511cf8f72",
                                                          "7e6c65661679e0440a67d4a33fe2dcc3" };
        int worldNearbyBehaviorIndex = -1;
        FieldInfo worldNearbyIndicatorField, worldTravelingOrbsField;
        Type[] worldItemBehaviorTypes = { typeof(MushroomBodyBehavior), typeof(PhasingBodyBehavior) };
        ItemDef[] worldItemBehaviorDefinitions;
        bool ownsWorldItemBehaviors, ownsWorldMushroomBinding;
        object previousWorldMushroom;
        public WorldItemBehaviorSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public static FieldInfo MushroomPrefabField()
        {
            return typeof(MushroomBodyBehavior).GetField("mushroomWardPrefab", BindingFlags.NonPublic | BindingFlags.Static);
        }
        public BuffDef[] WorldItemBehaviorBuffs(SessionConfig cfg)
        {
            if (cfg.worldItemBehaviorBuffAssets == null)
                return new BuffDef[0];
            var names = new[] { "Cloak", "CloakSpeed" };
            if (cfg.worldAdditionalLootItems != null && cfg.worldAdditionalLootItems.Contains("LaserTurbine"))
                names = names.Concat(new[] { "LaserTurbineKillCharge" }).ToArray();
            coordinator.Check(cfg.worldItemBehaviorBuffAssets.Length == names.Length, "Original item-behavior buff closure differs");
            return cfg.worldItemBehaviorBuffAssets
                .Select((path, i) =>
                        {
                            var def = coordinator.artifactBundle.LoadAsset<BuffDef>(path);
                            coordinator.Check(def && def.name == "bd" + names[i], "Original stealth buff missing");
                            coordinator.BindEnemyDefinition(typeof(RoR2Content.Buffs), names[i], def);
                            return def;
                        })
                .ToArray();
        }
        public GameObject[] PrepareWorldItemBehaviorSupport(SessionConfig cfg)
        {
            if (cfg.worldItemBehaviorBuffAssets == null)
                return new GameObject[0];
            var effects = new List<GameObject>();
            foreach (var path in new[] { "Prefabs/NetworkedObjects/MushroomWard", "Prefabs/Effects/ProcStealthkit" })
            {
                int i = Array.IndexOf(cfg.objectiveSupportPaths, path);
                coordinator.Check(i >= 0, "Original item-behavior provider absent: " + path);
                var source = coordinator.objectiveSupportSources[i];
                coordinator.Check(source && source.GetComponentsInChildren<Component>(true).All(x => x),
                                  "Original item-behavior references absent");
                if (source.name == "MushroomWard")
                {
                    coordinator.Check(source.GetComponent<HealingWard>() && source.GetComponent<TeamFilter>() &&
                                          source.GetComponent<NetworkIdentity>(),
                                      "Original Mushroom ward contract absent");
                    previousWorldMushroom = MushroomPrefabField().GetValue(null);
                    coordinator.Check(previousWorldMushroom == null, "Unowned original Mushroom binding");
                    ownsWorldMushroomBinding = true;
                    MushroomPrefabField().SetValue(null, source);
                }
                else
                {
                    coordinator.Check(source.name == "ProcStealthkit" && source.GetComponent<EffectComponent>(),
                                      "Original stealth effect absent");
                    effects.Add(source);
                    coordinator.worldNativeLootLeaseBaselines.Add(
                        i, (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                               .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                               .GetValue(coordinator.objectiveSupportLeases[i]));
                }
                foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
                {
                    if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                        continue;
                    coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                    coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                }
                coordinator.PresentCommerceModel(source.transform);
            }
            return effects.ToArray();
        }
        // These roots are already present in the accepted whole-content manifest. Own
        // their original LegacyResourcesAPI leases before native behavior execution;
        // no asset is copied into authored source or enabled by a synthetic grant.
        public IEnumerator PrepareWholeItemBehaviorSupport(SessionConfig cfg)
        {
            if (!cfg.integratedWorld || !Resources.Load<TextAsset>("WholeCatalogBootstrap"))
                yield break;
            coordinator.Check(worldItemSupportLeases.Count == 0 && RoR2Content.Buffs.WhipBoost && RoR2Content.Items.SprintOutOfCombat &&
                                  RoR2Content.Items.NearbyDamageBonus && RoR2Content.Items.SprintWisp,
                              "Original whole-item source definitions absent");
            for (int i = 0; i < wholeItemSupportPaths.Length; i++)
            {
                var path = wholeItemSupportPaths[i];
                string key;
                coordinator.Check(LegacyResourcesAPI.GetGuid(path, out key) && key == wholeItemSupportKeys[i],
                                  "Original whole-item legacy key changed: " + path);
                var lease = LegacyResourcesAPI.LoadAsync<GameObject>(path);
                worldItemSupportLeases.Add(path, lease);
                yield return lease;
                var source = lease.Result;
                coordinator.Check(lease.Status == AsyncOperationStatus.Succeeded && source &&
                                      source.name == path.Substring(path.LastIndexOf('/') + 1) &&
                                      source.GetComponentsInChildren<Component>(true).All(component => component),
                                  "Original whole-item source graph absent: " + path);
                if (i == 0)
                {
                    coordinator.Check(source.GetComponent<NetworkIdentity>() && source.GetComponent<NetworkedBodyAttachment>(),
                                      "Original nearby indicator attachment contract absent");
                    foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
                    {
                        if (coordinator.worldLootSourceMaterials.ContainsKey(renderer))
                            continue;
                        coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                        coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
                    }
                    coordinator.PresentCommerceModel(source.transform);
                }
                else
                {
                    coordinator.Check(source.GetComponent<EffectComponent>(), "Original whole-item effect component absent: " + path);
                    if (!GameAudioOriginalOwner.Ready)
                        source.GetComponent<EffectComponent>().soundName = null;
                }
                worldItemSupportBaselines.Add(path, (int)typeof(AsyncOperationHandle<GameObject>)
                                                        .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                                        .GetValue(lease));
            }
        }
        public GameObject[] WholeItemBehaviorEffects()
        {
            if (worldItemSupportLeases.Count == 0)
                return new GameObject[0];
            return wholeItemSupportPaths.Skip(1).Select(path => worldItemSupportLeases[path].Result).ToArray();
        }
        public void PrepareWorldItemBehaviors(SessionConfig cfg)
        {
            if (cfg.worldItemBehaviorBuffAssets == null)
                return;
            coordinator.Check(NetworkServer.active, "Original item-behavior adapter requires active original server");
            var nativeBodies = (System.Collections.IDictionary) typeof(BaseItemBodyBehavior)
                                   .GetField("bodyToItemBehaviors", BindingFlags.NonPublic | BindingFlags.Static)
                                   .GetValue(null);
            var context = typeof(BaseItemBodyBehavior).GetField("server", BindingFlags.NonPublic | BindingFlags.Static).GetValue(null);
            coordinator.Check(nativeBodies.Count == 0 && context.GetType().GetField("itemTypePairs").GetValue(context) == null,
                              "Native item-behavior lifecycle already initialized; refuse duplicate adapter");
            coordinator.Check(MushroomPrefabField().GetValue(null) != null && RoR2Content.Items.Mushroom && RoR2Content.Items.Phasing,
                              "Original item behavior inputs absent");
            var types = new List<Type> { typeof(MushroomBodyBehavior), typeof(PhasingBodyBehavior) };
            var defs = new List<ItemDef> { RoR2Content.Items.Mushroom, RoR2Content.Items.Phasing };
            var names = new[] { "FallBoots", "Icicle", "LaserTurbine" };
            var nativeTypes = new[] { typeof(HeadstomperBodyBehavior), typeof(IcicleBodyBehavior), typeof(LaserTurbineBodyBehavior) };
            for (int i = 0; i < names.Length; i++)
                if (cfg.worldAdditionalLootItems != null && cfg.worldAdditionalLootItems.Contains(names[i]))
                {
                    var def = ItemCatalog.GetItemDef(ItemCatalog.FindItemIndex(names[i]));
                    coordinator.Check(def && !def.unlockableDef && !def.requiredExpansion,
                                      "Original legendary item unavailable: " + names[i]);
                    types.Add(nativeTypes[i]);
                    defs.Add(def);
                }
            if (cfg.stagePopulationFamilies != null && cfg.stagePopulationFamilies.Contains("Vagrant"))
            {
                var def = RoR2Content.Items.NovaOnLowHealth;
                coordinator.Check(def && !def.unlockableDef && !def.requiredExpansion && def.tier == ItemTier.Boss,
                                  "Original Vagrant boss item unavailable");
                types.Add(typeof(NovaOnLowHealthBodyBehavior));
                defs.Add(def);
            }
            if (cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            {
                types.Clear();
                defs.Clear();
                foreach (var method in typeof(CharacterBody)
                             .Assembly.GetTypes()
                             .SelectMany(type => type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static |
                                                                 BindingFlags.DeclaredOnly)))
                {
                    var association = (BaseItemBodyBehavior.ItemDefAssociationAttribute)Attribute.GetCustomAttribute(
                        method, typeof(BaseItemBodyBehavior.ItemDefAssociationAttribute));
                    if (association == null ||
                        !(NetworkServer.active && association.useOnServer || NetworkClient.active && association.useOnClient))
                        continue;
                    var type = association.behaviorTypeOverride ?? method.DeclaringType;
                    coordinator.Check(typeof(BaseItemBodyBehavior).IsAssignableFrom(type) && !type.IsAbstract &&
                                          method.GetParameters().Length == 0 && !method.IsGenericMethod &&
                                          method.ReturnType == typeof(ItemDef),
                                      "Original item-behavior association signature differs: " + method.Name);
                    var def = (ItemDef)method.Invoke(null, null);
                    coordinator.Check(def && def.itemIndex != ItemIndex.None && ItemCatalog.GetItemDef(def.itemIndex) == def,
                                      "Original item-behavior association is unregistered: " + type.FullName);
                    types.Add(type);
                    defs.Add(def);
                }
                coordinator.Check(types.Count > 0 && types.Distinct().Count() == types.Count,
                                  "Original item-behavior association family ambiguous");
            }
            if (cfg.integratedWorld && Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            {
                foreach (var pair in new[] { new[] { "RoR2.Items.RedWhipBodyBehavior", "SprintOutOfCombat" },
                                             new[] { "RoR2.Items.NearbyDamageBonusBodyBehavior", "NearbyDamageBonus" },
                                             new[] { "RoR2.Items.SprintWispBodyBehavior", "SprintWisp" } })
                {
                    var found = Array.FindIndex(types.ToArray(), type => type.FullName == pair[0]);
                    coordinator.Check(found >= 0 && defs[found].name == pair[1], "Original whole-item association missing: " + pair[1]);
                }
                coordinator.Check(worldItemSupportLeases.Count == wholeItemSupportPaths.Length &&
                                      worldItemSupportBaselines.Count == wholeItemSupportPaths.Length,
                                  "Original whole-item support not owned before behavior activation");
                worldNearbyBehaviorIndex = types.FindIndex(type => type.FullName == "RoR2.Items.NearbyDamageBonusBodyBehavior");
                worldNearbyIndicatorField =
                    types[worldNearbyBehaviorIndex].GetField("nearbyDamageBonusIndicator", BindingFlags.NonPublic | BindingFlags.Instance);
                worldTravelingOrbsField = typeof(OrbManager).GetField("travelingOrbs", BindingFlags.Instance | BindingFlags.NonPublic);
                coordinator.Check(worldNearbyIndicatorField != null && worldNearbyIndicatorField.FieldType == typeof(GameObject) &&
                                      worldTravelingOrbsField != null,
                                  "Original whole-item observation fields changed");
            }
            var bossRewardItems = coordinator.ComposedBaseBossRewards(cfg);
            worldItemBehaviorTypes = types.ToArray();
            worldItemBehaviorDefinitions = defs.ToArray();
            coordinator.r.itemBehaviors = new ItemBehaviorReport {
                ready = true,
                sourceSupport = worldItemSupportLeases.Count == wholeItemSupportPaths.Length,
                definitions = defs.Select(x => x.name).ToArray(),
                normalLoot = defs.Where(def => coordinator.worldLootDefinitions.Contains(def)).Select(x => x.name).ToArray(),
                bossRewards = defs.Where(def => bossRewardItems.Contains(def)).Select(x => x.name).ToArray(),
                requestedDeveloperGrants =
                    (coordinator.r.developerItemGrants ?? new string[0]).Where(name => defs.Any(def => def.name == name)).ToArray()
            };
            ownsWorldItemBehaviors = true;
            CharacterBody.onBodyInventoryChangedGlobal += RefreshWorldItemBehaviors;
            CharacterBody.onBodyDestroyGlobal += RemoveWorldItemBehaviors;
            foreach (var body in CharacterBody.readOnlyInstancesList.ToArray())
                if (body && body.gameObject.activeInHierarchy)
                    RefreshWorldItemBehaviors(body);
        }
        public void RefreshWorldItemBehaviors(CharacterBody body)
        {
            if (!ownsWorldItemBehaviors || !body || !body.gameObject.activeInHierarchy)
                return;
            BaseItemBodyBehavior[] entries;
            if (!worldItemBehaviors.TryGetValue(body, out entries))
            {
                entries = new BaseItemBodyBehavior[worldItemBehaviorTypes.Length];
                worldItemBehaviors.Add(body, entries);
                coordinator.r.itemBehaviors.bodies++;
            }
            var defs = worldItemBehaviorDefinitions;
            var setter = typeof(BaseItemBodyBehavior).GetMethod("SetItemStack", BindingFlags.NonPublic | BindingFlags.Static);
            for (int i = 0; i < entries.Length; i++)
            {
                var before = entries[i];
                var args = new object[] { body, entries[i], worldItemBehaviorTypes[i],
                                          body.inventory ? body.inventory.GetItemCountEffective(defs[i]) : 0 };
                setter.Invoke(null, args);
                entries[i] = (BaseItemBodyBehavior)args[1];
                if (!before && entries[i])
                    coordinator.r.itemBehaviors.assignments++;
                coordinator.Check(!entries[i] || entries[i].body == body, "Original item-behavior body assignment differs");
            }
            coordinator.r.itemBehaviors.refreshes++;
        }
        public void RemoveWorldItemBehaviors(CharacterBody body)
        {
            BaseItemBodyBehavior[] entries;
            if (!worldItemBehaviors.TryGetValue(body, out entries))
                return;
            foreach (var entry in entries)
                if (entry)
                    Destroy(entry);
            worldItemBehaviors.Remove(body);
        }
        public void ObserveWorldItemBehaviors()
        {
            if (!ownsWorldItemBehaviors)
                return;
            foreach (var pair in worldItemBehaviors.ToArray())
            {
                if (!pair.Key)
                {
                    worldItemBehaviors.Remove(pair.Key);
                    continue;
                }
                if (pair.Key.HasBuff(RoR2Content.Buffs.Cloak))
                    coordinator.r.itemBehaviors.cloakObservations++;
                if (worldItemSupportLeases.Count == wholeItemSupportPaths.Length)
                {
                    if (pair.Key.HasBuff(RoR2Content.Buffs.WhipBoost))
                    {
                        coordinator.r.itemBehaviors.whipBuffSamples++;
                        coordinator.r.itemBehaviors.whipPeakMoveSpeed =
                            Mathf.Max(coordinator.r.itemBehaviors.whipPeakMoveSpeed, pair.Key.moveSpeed);
                    }
                    if (worldNearbyBehaviorIndex >= 0 && pair.Value[worldNearbyBehaviorIndex])
                    {
                        var indicator = (GameObject)worldNearbyIndicatorField.GetValue(pair.Value[worldNearbyBehaviorIndex]);
                        if (indicator && worldNearbyIndicators.Add(indicator))
                        {
                            var attachment = indicator.GetComponent<NetworkedBodyAttachment>();
                            var identity = indicator.GetComponent<NetworkIdentity>();
                            coordinator.Check(attachment && attachment.attachedBody == pair.Key && identity && identity.netId.Value != 0 &&
                                                  NetworkServer.FindLocalObject(identity.netId) == indicator,
                                              "Original nearby indicator authority/body linkage differs");
                            coordinator.r.itemBehaviors.nearbyIndicators++;
                        }
                    }
                }
                int mushroom = Array.IndexOf(worldItemBehaviorTypes, typeof(MushroomBodyBehavior));
                var behavior = mushroom < 0 ? null : pair.Value[mushroom];
                if (!behavior)
                    continue;
                var obj = (GameObject) typeof(MushroomBodyBehavior)
                              .GetField("mushroomWardGameObject", BindingFlags.NonPublic | BindingFlags.Instance)
                              .GetValue(behavior);
                if (obj && worldMushroomWards.Add(obj))
                {
                    var ward = obj.GetComponent<HealingWard>();
                    coordinator.Check(ward && ward.netId.Value != 0 &&
                                          obj.GetComponent<TeamFilter>().teamIndex == pair.Key.teamComponent.teamIndex,
                                      "Native Mushroom ward authority/team differs");
                    coordinator.r.itemBehaviors.mushroomWards++;
                    coordinator.worldObjects.Add(obj);
                }
            }
            if (worldItemSupportLeases.Count == wholeItemSupportPaths.Length && OrbManager.instance)
            {
                int count = 0;
                foreach (var orb in (IEnumerable<Orb>)worldTravelingOrbsField.GetValue(OrbManager.instance))
                {
                    var wisp = orb as DevilOrb;
                    var attacker = wisp != null && wisp.attacker ? wisp.attacker.GetComponent<CharacterBody>() : null;
                    if (wisp != null && wisp.effectType == DevilOrb.EffectType.Wisp && attacker && worldItemBehaviors.ContainsKey(attacker))
                        count++;
                }
                coordinator.r.itemBehaviors.wispOrbsPeak = Math.Max(coordinator.r.itemBehaviors.wispOrbsPeak, count);
            }
        }
        public void Dispose()
        {
            if (ownsWorldItemBehaviors)
            {
                CharacterBody.onBodyInventoryChangedGlobal -= RefreshWorldItemBehaviors;
                CharacterBody.onBodyDestroyGlobal -= RemoveWorldItemBehaviors;
                ownsWorldItemBehaviors = false;
                foreach (var body in worldItemBehaviors.Keys.ToArray())
                    RemoveWorldItemBehaviors(body);
                foreach (var ward in worldMushroomWards)
                    if (ward)
                        NetworkServer.Destroy(ward);
                worldMushroomWards.Clear();
                coordinator.r.itemBehaviors.cleaned = true;
            }
            if (ownsWorldMushroomBinding)
            {
                MushroomPrefabField().SetValue(null, previousWorldMushroom);
                ownsWorldMushroomBinding = false;
            }
            if (worldItemSupportLeases.Count > 0)
            {
                var cache = (System.Collections.IDictionary) typeof(OrbStorageUtility)
                                .GetField("_orbDictionary", BindingFlags.Static | BindingFlags.NonPublic)
                                .GetValue(null);
                var orbPath = wholeItemSupportPaths[2];
                if (cache.Contains(orbPath))
                    cache.Remove(orbPath);
                foreach (var pair in worldItemSupportLeases)
                {
                    if (!pair.Value.IsValid())
                        continue;
                    int baseline;
                    if (worldItemSupportBaselines.TryGetValue(pair.Key, out baseline))
                    {
                        var count = (int)typeof(AsyncOperationHandle<GameObject>)
                                        .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                        .GetValue(pair.Value) -
                                    baseline;
                        coordinator.Check(count >= 0, "Original whole-item provider ownership changed: " + pair.Key);
                        for (int i = 0; i < count; i++)
                            Addressables.Release(pair.Value.Result);
                    }
                    Addressables.Release(pair.Value);
                }
                worldItemSupportLeases.Clear();
                worldItemSupportBaselines.Clear();
                worldNearbyIndicators.Clear();
                worldNearbyBehaviorIndex = -1;
                worldNearbyIndicatorField = null;
                worldTravelingOrbsField = null;
            }
        }
    }
}
