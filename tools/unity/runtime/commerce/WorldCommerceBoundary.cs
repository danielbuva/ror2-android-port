// Subsystem: commerce/pickups (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareCommerceSupport, PrepareWorldCommerce (WorldCommerceSession); teardown CleanupWorldCommerce(final); Dispose performs final cleanup.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.Networking;
using UnityEngine.AddressableAssets;

// Original purchase/selection/shrine code; owned layout, presentation and observations.
public sealed partial class PortSession
{
    [Serializable]
    public class CommerceObservation
    {
        public string source, item, costType;
        public uint netId;
        public int cost, purchases;
        public bool available, hidden, purchased;
    }
    [Serializable]
    public class CommercePurchase
    {
        public float at, healthAfter, shieldAfter;
        public string source, family, subtype, costType;
        public int cost;
        public uint moneyAfter;
        public bool debugAssisted;
    }
    [Serializable]
    public class CommercePlacement
    {
        public string source, scene;
        public Vector3 position, sourceScale, placedScale;
        public float radius, spawnDistance, requiredDistance;
    }
    [Serializable]
    public class CommerceReport
    {
        public string scope, lastMessage;
        public int shops, chanceShrines, bloodShrines, healingShrines, bossShrines, restackShrines, messages, playerSummons,
            playerSummonBodies;
        public bool cleaned;
        public CommerceObservation[] objects;
        public List<string> repairableTypes = new List<string>();
        public List<CommercePurchase> purchases = new List<CommercePurchase>();
        public List<CommercePlacement> placements = new List<CommercePlacement>();
        public List<HealingWardObservation> healingWards = new List<HealingWardObservation>();
    }
    // Shared with the integrated world, native interactables and proc content.
    readonly List<PurchaseInteraction> commercePurchases = new List<PurchaseInteraction>();
    readonly List<MultiShopController> commerceShops = new List<MultiShopController>();
    readonly List<GameObject> commerceOwned = new List<GameObject>();
    readonly Dictionary<PurchaseInteraction, UnityAction<CostTypeDef.PayCostContext, CostTypeDef.PayCostResults>> commerceListeners =
        new Dictionary<PurchaseInteraction, UnityAction<CostTypeDef.PayCostContext, CostTypeDef.PayCostResults>>();
    readonly Dictionary<PurchaseInteraction, int> commercePurchaseCounts = new Dictionary<PurchaseInteraction, int>();
    int commerceEffectIndex = -1;
    bool ownsCommerceMessages;
    WorldCommerceSession worldCommerceSession;
    WorldCommerceSession GetWorldCommerceSession()
    {
        if (worldCommerceSession == null)
            worldCommerceSession = new WorldCommerceSession(this);
        return worldCommerceSession;
    }
    public static float CommerceRadius(GameObject source)
    {
        return WorldCommerceSession.CommerceRadius(source);
    }
    GameObject PrepareCommerceSupport(SessionConfig cfg)
    {
        return GetWorldCommerceSession().PrepareCommerceSupport(cfg);
    }
    void PresentCommerceModel(Transform root)
    {
        GetWorldCommerceSession().PresentCommerceModel(root);
    }
    void ConfigureCommerceObject(GameObject obj)
    {
        GetWorldCommerceSession().ConfigureCommerceObject(obj);
    }
    void PrepareCommerceSymbols(GameObject obj)
    {
        GetWorldCommerceSession().PrepareCommerceSymbols(obj);
    }
    Material CopyCommerceSymbol(Material source)
    {
        return GetWorldCommerceSession().CopyCommerceSymbol(source);
    }
    string CommerceSweepFamily(PurchaseInteraction purchase)
    {
        return GetWorldCommerceSession().CommerceSweepFamily(purchase);
    }
    string RepairableCommerceType(PurchaseInteraction purchase)
    {
        return GetWorldCommerceSession().RepairableCommerceType(purchase);
    }
    bool CommerceSweepPendingRepairs()
    {
        return GetWorldCommerceSession().CommerceSweepPendingRepairs();
    }
    PurchaseInteraction NextCommerceSweepTarget(CharacterBody player)
    {
        return GetWorldCommerceSession().NextCommerceSweepTarget(player);
    }
    void WatchCommercePurchase(PurchaseInteraction purchase)
    {
        GetWorldCommerceSession().WatchCommercePurchase(purchase);
    }
    void PrepareWorldCommerce(SessionConfig cfg, Vector3 origin)
    {
        GetWorldCommerceSession().PrepareWorldCommerce(cfg, origin);
    }
    void ObserveWorldCommerce()
    {
        GetWorldCommerceSession().ObserveWorldCommerce();
    }
    GameObject AffordableWorldCommerce()
    {
        return GetWorldCommerceSession().AffordableWorldCommerce();
    }
    void CleanupWorldCommerce(bool final = false)
    {
        GetWorldCommerceSession().CleanupWorldCommerce(final);
    }

    // Create on first use and retain for stage turnover, partial setup and later
    // observations. The cleanup forwarder preserves its final flag; Dispose uses
    // that same final cleanup without moving the coordinator's release call sites.
    sealed class WorldCommerceSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly List<GameObject> commerceTemplates = new List<GameObject>();
        readonly HashSet<int> commercePresentedPickupModels = new HashSet<int>();
        static readonly FieldInfo commercePickupModelField =
            typeof(PickupDisplay).GetField("modelObject", BindingFlags.NonPublic | BindingFlags.Instance);
        int commerceEffectBaseline, commerceDirectShrineEffectLoads;
        public WorldCommerceSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public static float CommerceRadius(GameObject source)
        {
            float radius = 0;
            var center = source.transform.position;
            foreach (var renderer in source.GetComponentsInChildren<Renderer>(true))
            {
                var bounds = renderer.bounds;
                var delta = bounds.center - center;
                radius =
                    Mathf.Max(radius, new Vector2(Mathf.Abs(delta.x) + bounds.extents.x, Mathf.Abs(delta.z) + bounds.extents.z).magnitude);
            }
            var shop = source.GetComponent<MultiShopController>();
            if (shop && shop.terminalPrefab)
                foreach (var position in shop.terminalPositions)
                    radius = Mathf.Max(radius, Vector3.ProjectOnPlane(position.position - center, Vector3.up).magnitude +
                                                   CommerceRadius(shop.terminalPrefab));
            if (radius <= 0 || float.IsNaN(radius) || float.IsInfinity(radius))
                throw new InvalidOperationException("Original commerce model footprint invalid: " + source.name);
            return radius;
        }
        public GameObject PrepareCommerceSupport(SessionConfig cfg)
        {
            if (cfg.worldCommerceAssets == null || cfg.worldCommerceAssets.Length == 0)
                return null;
            coordinator.commerceEffectIndex = Array.IndexOf(cfg.objectiveSupportPaths, "Prefabs/Effects/ShrineUseEffect");
            coordinator.Check(coordinator.commerceEffectIndex >= 0, "Original shrine effect provider absent");
            var effect = coordinator.objectiveSupportSources[coordinator.commerceEffectIndex];
            coordinator.Check(effect && effect.GetComponent<EffectComponent>(), "Original shrine effect component missing");
            commerceEffectBaseline = (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                                         .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                         .GetValue(coordinator.objectiveSupportLeases[coordinator.commerceEffectIndex]);
            coordinator.Check(commerceEffectBaseline > 0, "Original shrine effect lease absent");
            foreach (var renderer in effect.GetComponentsInChildren<Renderer>(true))
            {
                coordinator.worldLootSourceMaterials.Add(renderer, renderer.sharedMaterials);
                coordinator.worldLootSourceLayers[renderer.gameObject] = renderer.gameObject.layer;
            }
            PresentCommerceModel(effect.transform);
            return effect;
        }
        public void PresentCommerceModel(Transform root)
        {
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                if (!coordinator.worldPresented.Add(renderer.GetInstanceID()))
                    continue;
                // Native terminal clones inherit the owned template materials. Reusing those
                // copies preserves the first source-driven shader selection and its bindings.
                renderer.sharedMaterials = renderer.sharedMaterials
                                               .Select(source =>
                                                       {
                                                           if (!source)
                                                               return null;
                                                           if (coordinator.worldMaterials.Contains(source))
                                                               return source;
                                                           var copy = new Material(source);
                                                           copy.shader = Resources.Load<Shader>("StageSurfacePreview");
                                                           copy.shaderKeywords = new string[0];
                                                           AndroidMaterialPresentation.Apply(source, copy);
                                                           coordinator.worldMaterials.Add(copy);
                                                           return copy;
                                                       })
                                               .ToArray();
                if (!renderer.GetComponent<Collider>())
                    renderer.gameObject.layer = 30;
            }
        }
        public void ConfigureCommerceObject(GameObject obj)
        {
            var allowed = new[] { typeof(NetworkIdentity),        typeof(MultiShopController),  typeof(ShopTerminalBehavior),
                                  typeof(PurchaseInteraction),    typeof(ShrineChanceBehavior), typeof(ShrineBloodBehavior),
                                  typeof(ShrineHealingBehavior),  typeof(ShrineBossBehavior),   typeof(ShrineRestackBehavior),
                                  typeof(PickupDisplay),          typeof(ModelLocator),         typeof(EntityLocator),
                                  typeof(ChildLocator),           typeof(PingInfoProvider),     typeof(AnimationEvents),
                                  typeof(SpecialObjectAttributes) };
            foreach (var behaviour in obj.GetComponentsInChildren<MonoBehaviour>(true))
                behaviour.enabled = allowed.Contains(behaviour.GetType());
            foreach (var animator in obj.GetComponentsInChildren<Animator>(true))
            {
                animator.enabled = true;
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            }
            PresentCommerceModel(obj.transform);
        }
        public void PrepareCommerceSymbols(GameObject obj)
        {
            var boss = obj.GetComponent<ShrineBossBehavior>();
            if (!boss)
                return;
            // Native FixedUpdate chooses the original symbol material; supply owned copies
            // through that same contract so it does not reinstall a Windows-only shader.
            boss.regularSymbolMaterial = CopyCommerceSymbol(boss.regularSymbolMaterial);
            if (boss.prestigeSymbolMaterial)
                boss.prestigeSymbolMaterial = CopyCommerceSymbol(boss.prestigeSymbolMaterial);
        }
        public Material CopyCommerceSymbol(Material source)
        {
            coordinator.Check(source, "Original shrine symbol material absent");
            var copy = new Material(source);
            copy.shader = Resources.Load<Shader>("StageSurfacePreview");
            copy.shaderKeywords = new string[0];
            AndroidMaterialPresentation.Apply(source, copy);
            coordinator.worldMaterials.Add(copy);
            return copy;
        }
        public string CommerceSweepFamily(PurchaseInteraction purchase)
        {
            if (purchase.GetComponent<ShrineChanceBehavior>())
                return "chance-shrine";
            if (purchase.GetComponent<ShopTerminalBehavior>())
                return "multishop";
            if (purchase.GetComponent<SummonMasterBehavior>())
                return "drone-or-turret";
            if (purchase.GetComponent<ShrineHealingBehavior>())
                return "healing-shrine";
            return null;
        }
        public string RepairableCommerceType(PurchaseInteraction purchase)
        {
            var summon = purchase.GetComponent<SummonMasterBehavior>();
            return summon && summon.masterPrefab ? summon.masterPrefab.name : null;
        }
        public bool CommerceSweepPendingRepairs()
        {
            return coordinator.r.commerce != null &&
                   coordinator.r.commerce.repairableTypes.Any(type => !coordinator.r.commerce.purchases.Any(p => p.subtype == type));
        }
        public PurchaseInteraction NextCommerceSweepTarget(CharacterBody player)
        {
            if (coordinator.r.commerce == null || player == null || player.master == null)
                return null;
            var pending = new HashSet<string>(
                coordinator.r.commerce.repairableTypes.Where(type => !coordinator.r.commerce.purchases.Any(p => p.subtype == type)));
            var interactor = player.GetComponent<Interactor>();
            return coordinator.commercePurchases
                .Where(p => p && p.available && p.costType == CostTypeIndex.Money && coordinator.commercePurchaseCounts[p] == 0 &&
                            pending.Contains(RepairableCommerceType(p)) && p.CanBeAffordedByInteractor(interactor))
                .OrderBy(p => p.cost)
                .ThenBy(p => Vector3.SqrMagnitude(p.transform.position - player.corePosition))
                .FirstOrDefault();
        }
        public void WatchCommercePurchase(PurchaseInteraction purchase)
        {
            coordinator.Check(purchase && !coordinator.commerceListeners.ContainsKey(purchase),
                              "Duplicate or missing original commerce purchase component");
            coordinator.commercePurchases.Add(purchase);
            coordinator.commercePurchaseCounts[purchase] = 0;
            var subtype = RepairableCommerceType(purchase);
            if (subtype != null && !coordinator.r.commerce.repairableTypes.Contains(subtype))
                coordinator.r.commerce.repairableTypes.Add(subtype);
            UnityAction<CostTypeDef.PayCostContext, CostTypeDef.PayCostResults> listener = (context, result) =>
            {
                coordinator.commercePurchaseCounts[purchase]++;
                if ((purchase.GetComponent<ShrineBloodBehavior>() || purchase.GetComponent<ShrineHealingBehavior>() ||
                     purchase.GetComponent<ShrineBossBehavior>() || purchase.GetComponent<ShrineRestackBehavior>()))
                    commerceDirectShrineEffectLoads++;
                coordinator.Check(context.activatorBody == coordinator.worldPlayer && context.purchaseInteraction == purchase,
                                  "Original commerce purchase context changed");
                coordinator.r.commerce.purchases.Add(new CommercePurchase {
                    at = coordinator.r.world.seconds, source = purchase.name, family = CommerceSweepFamily(purchase), subtype = subtype,
                    cost = context.cost, costType = purchase.costType.ToString(), moneyAfter = coordinator.worldPlayer.master.money,
                    healthAfter = coordinator.worldPlayer.healthComponent.health,
                    shieldAfter = coordinator.worldPlayer.healthComponent.shield,
                    debugAssisted = coordinator.r.debugAcceleration != null && coordinator.r.debugAcceleration.everAssisted
                });
                coordinator.Save();
            };
            coordinator.commerceListeners.Add(purchase, listener);
            purchase.onDetailedPurchaseServer.AddListener(listener);
        }
        public void PrepareWorldCommerce(SessionConfig cfg, Vector3 origin)
        {
            if (cfg.worldCommerceAssets == null || cfg.worldCommerceAssets.Length == 0)
                return;
            coordinator.Check(
                (cfg.worldCommerceAssets.Length == 4 || cfg.worldCommerceAssets.Length == 5 || cfg.worldCommerceAssets.Length == 7) &&
                    coordinator.commerceEffectIndex >= 0,
                "Original world commerce contract incomplete");
            coordinator.r.phase = "integrated-world-commerce";
            coordinator.Save();
            if (coordinator.r.commerce == null)
            {
                coordinator.r.commerce = new CommerceReport {
                    scope =
                        "Original multishop terminal generation/choice/closure, chance shrine RNG/failure/refresh/drops, blood shrine health cost/gold/refresh healing shrine native ward/radius/refresh, Mountain boss-stack and Order inventory-restack contracts. Authored near-entry layout/material adapter; no original SceneDirector placement, equipment, platform text-chat or normal health-cost acceptance under invincibility."
                };
                coordinator.Check(!coordinator.activeBodyClient.handlers.ContainsKey(59) ||
                                      coordinator.worldSourceClientHandlerIds.Contains(59),
                                  "Unowned platform chat handler");
                if (!coordinator.activeBodyClient.handlers.ContainsKey(59))
                {
                    coordinator.ownsCommerceMessages = true;
                    coordinator.activeBodyClient.RegisterHandler(
                        59, message =>
                            {
                                var native = ChatMessageBase.Instantiate(message.reader.ReadByte());
                                coordinator.Check(native != null, "Original local gameplay message type missing");
                                native.Deserialize(message.reader);
                                coordinator.r.commerce.messages++;
                                var subject = native as Chat.SubjectFormatChatMessage;
                                var simple = native as Chat.SimpleChatMessage;
                                coordinator.r.commerce.lastMessage =
                                    subject != null ? subject.baseToken : (simple != null ? simple.baseToken : native.GetType().Name);
                            });
                }
            }
            if (coordinator.r.liveCatalogs != null)
            {
                coordinator.r.commerce.scope =
                    "Original complete stage interactable selection/credits/node placement and native purchase behaviors; owned Android activation/audio/presentation and continuous-body/teleporter lifecycle adapters. Registration is not every interactable behavior acceptance.";
                return;
            }
            // Reserve the original camera orbit plus each unscaled source model footprint.
            // The old 8m offsets let tall terminals occupy the initial third-person view.
            var directions = new[] { Vector3.right,
                                     Vector3.left,
                                     Vector3.forward,
                                     Vector3.back,
                                     new Vector3(1, 0, 1).normalized,
                                     new Vector3(-1, 0, 1).normalized,
                                     new Vector3(1, 0, -1).normalized,
                                     new Vector3(-1, 0, -1).normalized };
            int start = 0;
            var placed = new List<CommercePlacement>();
            CharacterCameraParamsData cameraParams;
            coordinator.worldPlayer.GetComponent<CameraTargetParams>().CalcParams(out cameraParams);
            float cameraOrbit = cameraParams.idealLocalCameraPos.value.magnitude;
            foreach (var path in cfg.worldCommerceAssets)
            {
                var source = coordinator.artifactBundle.LoadAsset<GameObject>(path);
                coordinator.Check(source && source.GetComponentsInChildren<Component>(true).All(x => x),
                                  "Original commerce source references missing: " + path);
                RaycastHit ground = default(RaycastHit);
                bool found = false;
                float radius = CommerceRadius(source), required = Mathf.Max(14, cameraOrbit + radius + 2);
                for (int ring = 0; ring < 3 && !found; ring++)
                    for (int i = 0; i < directions.Length; i++)
                    {
                        var candidate = origin + directions[(start + i) % directions.Length] * (required + ring * 4);
                        if (!Physics.Raycast(candidate + Vector3.up * 20, Vector3.down, out ground, 50, LayerIndex.world.mask,
                                             QueryTriggerInteraction.Ignore) ||
                            ground.collider.gameObject.scene != coordinator.stageGeometryScene || ground.normal.y <= .9f ||
                            Mathf.Abs(ground.point.y - origin.y) >= 2 || !coordinator.InsideSourceStageBounds(ground.point))
                            continue;
                        if (placed.Any(x =>
                                           Vector3.ProjectOnPlane(x.position - ground.point, Vector3.up).magnitude < x.radius + radius + 1))
                            continue;
                        found = true;
                        start = (start + i + 1) % directions.Length;
                        break;
                    }
                if (!found)
                    continue;
                var obj = PortSession.Instantiate(source, coordinator.worldStaging.transform);
                obj.name = source.name;
                coordinator.worldObjects.Add(obj);
                coordinator.commerceOwned.Add(obj);
                ConfigureCommerceObject(obj);
                PrepareCommerceSymbols(obj);
                obj.transform.position = ground.point + Vector3.up * .4f;
                var placement =
                    new CommercePlacement { source = source.name,
                                            scene = coordinator.r.stageProgress.current,
                                            position = obj.transform.position,
                                            radius = radius,
                                            spawnDistance = Vector3.ProjectOnPlane(obj.transform.position - origin, Vector3.up).magnitude,
                                            requiredDistance = required,
                                            sourceScale = source.transform.localScale,
                                            placedScale = obj.transform.localScale };
                coordinator.Check(placement.spawnDistance >= required - .1f && placement.sourceScale == placement.placedScale,
                                  "Commerce spawn/camera clearance changed source scale");
                placed.Add(placement);
                coordinator.r.commerce.placements.Add(placement);
                var shop = obj.GetComponent<MultiShopController>();
                if (shop)
                {
                    coordinator.Check(!shop.doEquipmentInstead && !shop.isTripleDroneVendor && shop.terminalPositions.Length == 3,
                                      "Original item-only multishop contract differs");
                    var template = PortSession.Instantiate(shop.terminalPrefab, coordinator.worldStaging.transform);
                    commerceTemplates.Add(template);
                    coordinator.commerceOwned.Add(template);
                    ConfigureCommerceObject(template);
                    var terminal = template.GetComponent<ShopTerminalBehavior>();
                    coordinator.Check(terminal && terminal.selfGeneratePickup && terminal.dropTable is BasicPickupDropTable,
                                      "Original self-generating item terminal contract differs");
                    terminal.dropTable = coordinator.ObjectiveDropTable(terminal.dropTable);
                    ((BasicPickupDropTable)terminal.dropTable).RegenerateDropTable(Run.instance);
                    coordinator.Check(terminal.dropTable.GetPickupCount() > 0, "Original terminal selector empty");
                    shop.terminalPrefab = template;
                }
                var chance = obj.GetComponent<ShrineChanceBehavior>();
                if (chance)
                {
                    coordinator.Check(chance.dropTable, "Original chance shrine drop table absent");
                    coordinator.Check(chance.effectPrefabShrineRewardNormal, "Original chance shrine normal effect absent");
                    chance.dropTable = coordinator.ObjectiveDropTable(chance.dropTable);
                    var table = chance.dropTable as BasicPickupDropTable;
                    coordinator.Check(table, "Original chance shrine table type changed");
                    table.RegenerateDropTable(Run.instance);
                    coordinator.Check(table.GetPickupCount() > 0, "Original chance shrine source selector empty");
                }
                obj.transform.SetParent(null, true);
                obj.SetActive(true);
                NetworkServer.Spawn(obj);
                if (shop)
                {
                    coordinator.commerceShops.Add(shop);
                    foreach (var terminal in shop.terminalGameObjectsList)
                    {
                        coordinator.Check(terminal && terminal.GetComponent<ShopTerminalBehavior>() &&
                                              terminal.GetComponent<NetworkIdentity>().netId.Value != 0,
                                          "Original multishop terminal factory/network identity failed");
                        coordinator.commerceOwned.Add(terminal);
                        coordinator.worldObjects.Add(terminal);
                        PresentCommerceModel(terminal.transform);
                        WatchCommercePurchase(terminal.GetComponent<PurchaseInteraction>());
                    }
                    coordinator.r.commerce.shops++;
                }
                else
                {
                    WatchCommercePurchase(obj.GetComponent<PurchaseInteraction>());
                    if (chance)
                        coordinator.r.commerce.chanceShrines++;
                    else if (obj.GetComponent<ShrineHealingBehavior>())
                    {
                        coordinator.r.commerce.healingShrines++;
                    }
                    else if (obj.GetComponent<ShrineBossBehavior>())
                        coordinator.r.commerce.bossShrines++;
                    else if (obj.GetComponent<ShrineRestackBehavior>())
                        coordinator.r.commerce.restackShrines++;
                    else
                    {
                        coordinator.Check(obj.GetComponent<ShrineBloodBehavior>(), "Unknown original shrine");
                        coordinator.r.commerce.bloodShrines++;
                    }
                }
            }
        }
        public void ObserveWorldCommerce()
        {
            if (coordinator.r.commerce == null)
                return;
            coordinator.ObserveHealingCommerceWards();
            foreach (var purchase in coordinator.commercePurchases)
            {
                if (!purchase)
                    continue;
                var terminal = purchase.GetComponent<ShopTerminalBehavior>();
                if (terminal && terminal.pickupDisplay)
                {
                    var model = (GameObject)commercePickupModelField.GetValue(terminal.pickupDisplay);
                    if (model && commercePresentedPickupModels.Add(model.GetInstanceID()))
                        PresentCommerceModel(model.transform);
                }
            }
            if (Time.frameCount % 30 != 0)
                return;
            coordinator.r.commerce.playerSummons = coordinator.wholePlayerSummons.Count(x => x);
            coordinator.r.commerce.playerSummonBodies = coordinator.wholePlayerSummons.Count(x => x && x.GetBody());
            coordinator.r.commerce.objects =
                coordinator.commercePurchases.Where(x => x)
                    .Select(x =>
                            {
                                var terminal = x.GetComponent<ShopTerminalBehavior>();
                                var pickup = terminal ? PickupCatalog.GetPickupDef(terminal.Networkpickup.pickupIndex) : null;
                                return new CommerceObservation { source = x.name,
                                                                 netId = x.netId.Value,
                                                                 cost = x.cost,
                                                                 costType = x.costType.ToString(),
                                                                 available = x.available,
                                                                 purchases = coordinator.commercePurchaseCounts[x],
                                                                 item = pickup == null ? null : pickup.internalName,
                                                                 hidden = terminal && terminal.Networkhidden,
                                                                 purchased = terminal && terminal.NetworkhasBeenPurchased };
                            })
                    .ToArray();
        }
        public GameObject AffordableWorldCommerce()
        {
            return coordinator.commercePurchases
                .FirstOrDefault(x => x && x.available && (x.costType == CostTypeIndex.None || x.costType == CostTypeIndex.Money) &&
                                     coordinator.commercePurchaseCounts[x] == 0 &&
                                     (x.costType == CostTypeIndex.None || coordinator.worldPlayer.master.money >= x.cost))
                ?.gameObject;
        }
        public void CleanupWorldCommerce(bool final = false)
        {
            coordinator.ObserveWorldChestBreadth();
            coordinator.worldBreadthChests.Clear();
            coordinator.CleanupHealingCommerceWards();
            foreach (var pair in coordinator.commerceListeners)
                if (pair.Key)
                    pair.Key.onDetailedPurchaseServer.RemoveListener(pair.Value);
            coordinator.commerceListeners.Clear();
            coordinator.commercePurchases.Clear();
            coordinator.commercePurchaseCounts.Clear();
            coordinator.commerceShops.Clear();
            commercePresentedPickupModels.Clear();
            foreach (var template in commerceTemplates)
                if (template)
                    PortSession.Destroy(template);
            commerceTemplates.Clear();
            if (!final)
                return;
            if (coordinator.ownsCommerceMessages && coordinator.activeBodyClient != null)
            {
                coordinator.activeBodyClient.UnregisterHandler(59);
                coordinator.ownsCommerceMessages = false;
            }
            if (coordinator.commerceEffectIndex >= 0)
            {
                var lease = coordinator.objectiveSupportLeases[coordinator.commerceEffectIndex];
                int extra = (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                                .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                .GetValue(lease) -
                            commerceEffectBaseline;
                coordinator.Check(extra == commerceDirectShrineEffectLoads, "Unattributed original blood/healing shrine effect loads");
                for (int i = 0; i < extra; i++)
                    Addressables.Release(lease.Result);
                coordinator.commerceEffectIndex = -1;
            }
        }
        public void Dispose()
        {
            CleanupWorldCommerce(true);
        }
    }
}
