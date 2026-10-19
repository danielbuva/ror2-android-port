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
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using System.Runtime.CompilerServices;

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
        public List<string> nativeShrineEffectOperationWitnesses;
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
        string commerceEffectExpectedGuid;
        string commerceEffectOperationBaselineError = string.Empty;
        List<NativeShrineEffectOperationBaseline> commerceEffectOperationBaseline = new List<NativeShrineEffectOperationBaseline>();
        bool commerceEffectOperationBaselineCaptured, commerceEffectOperationDetailCaptured, commerceEffectOperationCleanupCaptured;
        int commerceBloodShrineDetailedPurchaseCallbacks, commerceHealingShrineDetailedPurchaseCallbacks,
            commerceBossShrineDetailedPurchaseCallbacks, commerceRestackShrineDetailedPurchaseCallbacks;
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
            commerceEffectExpectedGuid = coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt
                                             ? (cfg.objectiveSupportKeys != null && cfg.objectiveSupportKeys.Length > coordinator.commerceEffectIndex
                                                    ? cfg.objectiveSupportKeys[coordinator.commerceEffectIndex]
                                                    : null)
                                             : null;
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
                bool bloodShrine = purchase.GetComponent<ShrineBloodBehavior>();
                bool healingShrine = purchase.GetComponent<ShrineHealingBehavior>();
                bool bossShrine = purchase.GetComponent<ShrineBossBehavior>();
                bool restackShrine = purchase.GetComponent<ShrineRestackBehavior>();
                if (bloodShrine || healingShrine || bossShrine || restackShrine)
                    commerceDirectShrineEffectLoads++;
                if (bloodShrine)
                    commerceBloodShrineDetailedPurchaseCallbacks++;
                if (healingShrine)
                    commerceHealingShrineDetailedPurchaseCallbacks++;
                if (bossShrine)
                    commerceBossShrineDetailedPurchaseCallbacks++;
                if (restackShrine)
                    commerceRestackShrineDetailedPurchaseCallbacks++;
                if (bossShrine && coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && !commerceEffectOperationDetailCaptured)
                {
                    commerceEffectOperationDetailCaptured = true;
                    CaptureNativeShrineEffectOperationWitness("boss-detailed-purchase");
                }
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
            if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && !commerceEffectOperationBaselineCaptured)
                CaptureNativeShrineEffectOperationBaselineInert(purchase);
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
                int finalReferenceCount = (int)typeof(UnityEngine.ResourceManagement.AsyncOperations.AsyncOperationHandle<GameObject>)
                                             .GetProperty("ReferenceCount", BindingFlags.Instance | BindingFlags.NonPublic)
                                             .GetValue(lease);
                int extra = finalReferenceCount - commerceEffectBaseline;
                string nativeWitness = coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt && !commerceEffectOperationCleanupCaptured
                                           ? CaptureNativeShrineEffectOperationWitness("cleanup-before-refusal")
                                           : null;
                if (nativeWitness != null)
                    commerceEffectOperationCleanupCaptured = true;
                coordinator.Check(
                    extra == commerceDirectShrineEffectLoads,
                    NativeShrineEffectAttributionWitness.Format(
                        commerceEffectBaseline, finalReferenceCount, commerceDirectShrineEffectLoads,
                        commerceBloodShrineDetailedPurchaseCallbacks, commerceHealingShrineDetailedPurchaseCallbacks,
                        commerceBossShrineDetailedPurchaseCallbacks, commerceRestackShrineDetailedPurchaseCallbacks,
                        nativeWitness));
                for (int i = 0; i < extra; i++)
                    Addressables.Release(lease.Result);
                coordinator.commerceEffectIndex = -1;
            }
        }
        public void Dispose()
        {
            CleanupWorldCommerce(true);
        }
        void CaptureNativeShrineEffectOperationBaselineInert(PurchaseInteraction purchase)
        {
            try
            {
                if (!purchase || !purchase.GetComponent<ShrineBossBehavior>())
                    return;
                commerceEffectOperationBaselineCaptured = true;
                int supportIndex = coordinator.commerceEffectIndex;
                if (supportIndex < 0 || coordinator.objectiveSupportLeases == null ||
                    coordinator.objectiveSupportSources == null || supportIndex >= coordinator.objectiveSupportLeases.Length ||
                    supportIndex >= coordinator.objectiveSupportSources.Length)
                {
                    commerceEffectOperationBaselineError = "baselineSupportIndexUnavailable";
                    return;
                }
                var lease = coordinator.objectiveSupportLeases[supportIndex];
                string currentGuid = LegacyResourcesAPI.GetPathGuidString("Prefabs/Effects/ShrineUseEffect");
                commerceEffectOperationBaseline = NativeShrineEffectOperationSnapshot.CaptureBaseline(
                    lease, commerceEffectExpectedGuid, currentGuid, out commerceEffectOperationBaselineError);
            }
            catch (Exception exception)
            {
                commerceEffectOperationBaselineCaptured = true;
                commerceEffectOperationBaselineError = "baselineError=" + exception.GetType().Name;
                commerceEffectOperationBaseline = new List<NativeShrineEffectOperationBaseline>();
            }
        }
        string CaptureNativeShrineEffectOperationWitness(string reason)
        {
            try
            {
                if (reason == "boss-detailed-purchase" && commerceEffectOperationDetailCaptured == false)
                    commerceEffectOperationDetailCaptured = true;
                if (reason == "cleanup-before-refusal" && commerceEffectOperationCleanupCaptured)
                    return "reason=cleanup-before-refusal; captureSkipped=alreadyCaptured";
                if (reason == "cleanup-before-refusal")
                    commerceEffectOperationCleanupCaptured = true;
                var row = NativeShrineEffectOperationSnapshot.Capture(
                    coordinator.objectiveSupportLeases[coordinator.commerceEffectIndex],
                    coordinator.objectiveSupportSources[coordinator.commerceEffectIndex], commerceEffectExpectedGuid,
                    LegacyResourcesAPI.GetPathGuidString("Prefabs/Effects/ShrineUseEffect"), coordinator.commerceEffectIndex, reason,
                    commerceEffectOperationBaseline, commerceEffectOperationBaselineError);
                if (coordinator.r.commerce != null)
                {
                    if (coordinator.r.commerce.nativeShrineEffectOperationWitnesses == null)
                        coordinator.r.commerce.nativeShrineEffectOperationWitnesses = new List<string>();
                    if (coordinator.r.commerce.nativeShrineEffectOperationWitnesses.Count < 4)
                        coordinator.r.commerce.nativeShrineEffectOperationWitnesses.Add(row);
                }
                return row;
            }
            catch (Exception exception)
            {
                string error = "captureError=" + exception.GetType().Name;
                if (coordinator.r.commerce != null)
                {
                    if (coordinator.r.commerce.nativeShrineEffectOperationWitnesses == null)
                        coordinator.r.commerce.nativeShrineEffectOperationWitnesses = new List<string>();
                    if (coordinator.r.commerce.nativeShrineEffectOperationWitnesses.Count < 4)
                        coordinator.r.commerce.nativeShrineEffectOperationWitnesses.Add("reason=" + reason + "; " + error);
                }
                return "reason=" + reason + "; " + error;
            }
        }
    }
}


// Failure-only values for the existing fail-closed native effect ownership check.
// These counts describe detailed-purchase callbacks; they do not claim to have
// intercepted LegacyResourcesAPI.Load or identified its caller.
internal static class NativeShrineEffectAttributionWitness
{
    internal static string Format(int baselineReferenceCount, int finalReferenceCount, int attributedPurchaseCallbacks,
                                  int bloodCallbacks, int healingCallbacks, int bossCallbacks, int restackCallbacks,
                                  string operationWitness = null)
    {
        int referenceCountDelta = finalReferenceCount - baselineReferenceCount;
        return string.Format(
            "Unattributed original blood/healing shrine effect loads; " +
                "referenceCountBaseline={0}; referenceCountFinal={1}; referenceCountDelta={2}; " +
                "attributedDetailedPurchaseCallbacks={3}; bloodCallbacks={4}; healingCallbacks={5}; " +
                "bossCallbacks={6}; restackCallbacks={7}{8}",
            baselineReferenceCount, finalReferenceCount, referenceCountDelta, attributedPurchaseCallbacks, bloodCallbacks,
            healingCallbacks, bossCallbacks, restackCallbacks,
            string.IsNullOrEmpty(operationWitness) ? string.Empty : "; nativeEffectOperationWitness=" + operationWitness);
    }
}

// Native-diagnostic-only, read-only snapshot of cached operations for the exact
// ShrineUseEffect GUID/type lookup. It creates no Addressables operations and
// retains no handles or Unity objects after Capture returns.
internal static class NativeShrineEffectOperationSnapshot
{
    const int MaxCacheEntries = 8192, MaxLocators = 32, MaxRawLocations = 128, MaxLocations = 32, MaxMatches = 8,
              MaxSerializedChars = 4096, MaxIdentityStringChars = 1024;
    static readonly BindingFlags InstanceFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    static readonly FieldInfo CacheField = typeof(ResourceManager).GetField("m_AssetOperationCache", BindingFlags.Instance | BindingFlags.NonPublic);
    static readonly FieldInfo LocationField = typeof(AsyncOperationHandle<GameObject>).GetField("m_InternalOp", BindingFlags.Instance | BindingFlags.NonPublic);

    internal static List<NativeShrineEffectOperationBaseline> CaptureBaseline(AsyncOperationHandle<GameObject> lease,
                                                                               string expectedGuid, string currentGuid,
                                                                               out string error)
    {
        error = string.Empty;
        try
        {
            var output = new List<NativeShrineEffectOperationBaseline>();
            int locatorsVisited, rawLocationsVisited;
            bool locatorTruncated, rawLocationTruncated, uniqueLocationTruncated, expectedGuidInvalid, currentGuidInvalid;
            var locations = CandidateLocations(expectedGuid, currentGuid, out locatorsVisited, out rawLocationsVisited,
                                               out locatorTruncated, out rawLocationTruncated, out uniqueLocationTruncated,
                                               out expectedGuidInvalid, out currentGuidInvalid);
            if (locatorTruncated || rawLocationTruncated || uniqueLocationTruncated || expectedGuidInvalid || currentGuidInvalid)
                error = "baselineLocatorScanCappedOrInvalid";
            var cache = CacheField == null ? null : CacheField.GetValue(Addressables.ResourceManager) as System.Collections.IDictionary;
            if (cache == null)
            {
                error = "cacheUnavailable";
                return output;
            }
            int visited = 0;
            foreach (System.Collections.DictionaryEntry entry in cache)
            {
                if (++visited > MaxCacheEntries)
                {
                    error = "baselineScanTruncated";
                    break;
                }
                object operation;
                var location = CacheLocation(entry, out operation);
                if (operation == null || location == null || !MatchesAny(location, locations) || !CacheTypeIsGameObject(entry.Key))
                    continue;
                if (output.Count >= MaxMatches)
                {
                    error = "baselineMatchCapReached";
                    break;
                }
                output.Add(new NativeShrineEffectOperationBaseline(operation, ReadInt(operation, "Version"),
                                                                    ReadInt(operation, "ReferenceCount")));
            }
            return output;
        }
        catch (Exception exception)
        {
            error = exception.GetType().Name;
            return new List<NativeShrineEffectOperationBaseline>();
        }
    }

    internal static string Capture(AsyncOperationHandle<GameObject> lease, GameObject ownedEffect, string expectedGuid,
                                   string currentGuid, int supportIndex, string reason,
                                   List<NativeShrineEffectOperationBaseline> baseline, string baselineError)
    {
        var leaseOp = LocationField == null ? null : LocationField.GetValue(lease);
        var leaseLocation = OperationLocation(leaseOp);
        int visitedLocators, visitedLocations;
        bool locatorTruncated, rawLocationTruncated, uniqueLocationTruncated, expectedGuidInvalid, currentGuidInvalid;
        var candidateLocations = CandidateLocations(expectedGuid, currentGuid, out visitedLocators, out visitedLocations,
                                                     out locatorTruncated, out rawLocationTruncated, out uniqueLocationTruncated,
                                                     out expectedGuidInvalid, out currentGuidInvalid);
        int effectCatalogIndex = (int)EffectCatalog.FindEffectIndexFromPrefab(ownedEffect);
        var manager = Addressables.ResourceManager;
        var cache = CacheField == null ? null : CacheField.GetValue(manager) as System.Collections.IDictionary;
        if (cache == null)
                return BoundSerialized(Header(reason, expectedGuid, currentGuid, supportIndex, effectCatalogIndex,
                                              lease, leaseOp, leaseLocation, candidateLocations.Count, visitedLocators,
                                              visitedLocations, locatorTruncated, rawLocationTruncated, uniqueLocationTruncated,
                                              expectedGuidInvalid, currentGuidInvalid, -1, false, true) +
                              "; cacheUnavailable=true; baselineError=" + (baselineError ?? string.Empty));

        int visited = 0, matched = 0;
        bool truncated = false;
        var rows = new List<string>();
        foreach (System.Collections.DictionaryEntry entry in cache)
        {
            if (++visited > MaxCacheEntries)
            {
                truncated = true;
                break;
            }
            object operation;
            var location = CacheLocation(entry, out operation);
            if (operation == null || location == null || !MatchesAny(location, candidateLocations) || !CacheTypeIsGameObject(entry.Key))
                continue;

            matched++;
            object result = OperationResult(operation);
            if (rows.Count < MaxMatches)
            {
                int version = ReadInt(operation, "Version"), count = ReadInt(operation, "ReferenceCount");
                var previous = baseline == null ? null : baseline.FirstOrDefault(item => item.Matches(operation, version));
                rows.Add(string.Format("op={0},owned={1},prior={2},beforeRc={3},afterRc={4},delta={5},version={6},status={7},done={8},resultOwned={9},pk={10},provider={11},internal={12}",
                    RuntimeHelpers.GetHashCode(operation), ReferenceEquals(operation, leaseOp), previous != null,
                    previous == null ? -1 : previous.ReferenceCount, count,
                    previous == null ? -1 : count - previous.ReferenceCount, version, ReadText(operation, "Status"), ReadBool(operation, "IsDone"),
                    ReferenceEquals(result, ownedEffect), Hash(location.PrimaryKey), Hash(location.ProviderId), Hash(location.InternalId)));
            }
        }
        string header = Header(reason, expectedGuid, currentGuid, supportIndex, effectCatalogIndex, lease, leaseOp, leaseLocation,
                               candidateLocations.Count, visitedLocators, visitedLocations, locatorTruncated, rawLocationTruncated,
                               uniqueLocationTruncated, expectedGuidInvalid, currentGuidInvalid, matched, matched > MaxMatches, truncated);
        return BoundSerialized(header + "; baselineEntries=" + (baseline == null ? 0 : baseline.Count) + "; baselineError=" +
               (baselineError ?? string.Empty) + (rows.Count == 0 ? string.Empty : "; entries=[" + string.Join("|", rows.ToArray()) + "]"));
    }

    static List<IResourceLocation> CandidateLocations(string expectedGuid, string currentGuid, out int locatorsVisited,
                                                       out int rawLocationsVisited, out bool locatorTruncated,
                                                       out bool rawLocationTruncated, out bool uniqueLocationTruncated,
                                                       out bool expectedGuidInvalid, out bool currentGuidInvalid)
    {
        var output = new List<IResourceLocation>();
        locatorsVisited = 0;
        rawLocationsVisited = 0;
        locatorTruncated = rawLocationTruncated = uniqueLocationTruncated = false;
        expectedGuidInvalid = !IsGuid(expectedGuid);
        currentGuidInvalid = !IsGuid(currentGuid);
        if (!expectedGuidInvalid)
            AddLocations(expectedGuid, output, ref locatorsVisited, ref rawLocationsVisited,
                         ref locatorTruncated, ref rawLocationTruncated, ref uniqueLocationTruncated);
        if (!currentGuidInvalid && currentGuid != expectedGuid && !locatorTruncated && !rawLocationTruncated && !uniqueLocationTruncated)
            AddLocations(currentGuid, output, ref locatorsVisited, ref rawLocationsVisited,
                         ref locatorTruncated, ref rawLocationTruncated, ref uniqueLocationTruncated);
        return output;
    }
    static void AddLocations(string key, List<IResourceLocation> output, ref int locatorsVisited, ref int rawLocationsVisited,
                             ref bool locatorTruncated, ref bool rawLocationTruncated, ref bool uniqueLocationTruncated)
    {
        foreach (var locator in Addressables.ResourceLocators)
        {
            if (locatorsVisited >= MaxLocators) { locatorTruncated = true; return; }
            locatorsVisited++;
            IList<IResourceLocation> locations;
            if (!locator.Locate(key, typeof(GameObject), out locations) || locations == null)
                continue;
            foreach (var location in locations)
            {
                if (rawLocationsVisited >= MaxRawLocations) { rawLocationTruncated = true; return; }
                rawLocationsVisited++;
                if (location == null)
                    continue;
                if (output.Any(existing => LocationEquals(existing, location)))
                    continue;
                if (output.Count >= MaxLocations) { uniqueLocationTruncated = true; return; }
                output.Add(location);
            }
        }
    }
    static bool IsGuid(string value)
    {
        if (value == null || value.Length != 32) return false;
        for (int i = 0; i < value.Length; i++)
        {
            char c = value[i];
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return false;
        }
        return true;
    }
    static string SafeGuid(string value) { return IsGuid(value) ? value : "<invalid>"; }
    static string BoundSerialized(string value)
    {
        if (value == null || value.Length <= MaxSerializedChars) return value;
        return value.Substring(0, MaxSerializedChars - 32) + ";serializedCapped=true";
    }

    static IResourceLocation CacheLocation(System.Collections.DictionaryEntry entry, out object operation)
    {
        operation = entry.Value;
        var key = entry.Key;
        if (key == null || operation == null)
            return null;
        var field = key.GetType().GetField("m_Location", InstanceFlags);
        return field == null ? null : field.GetValue(key) as IResourceLocation;
    }
    static bool CacheTypeIsGameObject(object key)
    {
        if (key == null)
            return false;
        var field = key.GetType().GetField("m_DesiredType", InstanceFlags);
        return field != null && (field.GetValue(key) as Type) == typeof(GameObject);
    }

    static bool MatchesAny(IResourceLocation target, List<IResourceLocation> candidates)
    {
        return candidates.Any(candidate => LocationEquals(target, candidate));
    }
    static bool LocationEquals(IResourceLocation left, IResourceLocation right)
    {
        if (left == null || right == null) return false;
        string leftId = left.InternalId, rightId = right.InternalId;
        string leftProvider = left.ProviderId, rightProvider = right.ProviderId;
        return leftId != null && rightId != null && leftProvider != null && rightProvider != null &&
               leftId.Length <= MaxIdentityStringChars && rightId.Length <= MaxIdentityStringChars &&
               leftProvider.Length <= MaxIdentityStringChars && rightProvider.Length <= MaxIdentityStringChars &&
               leftId == rightId && leftProvider == rightProvider && left.ResourceType == right.ResourceType;
    }
    static IResourceLocation OperationLocation(object operation)
    {
        if (operation == null)
            return null;
        var iface = operation.GetType().GetInterfaces().FirstOrDefault(type => type.Name == "IGenericProviderOperation");
        var property = iface == null ? null : iface.GetProperty("Location");
        return property == null ? null : property.GetValue(operation, null) as IResourceLocation;
    }
    static object OperationResult(object operation)
    {
        var iface = operation == null ? null : operation.GetType().GetInterfaces().FirstOrDefault(type => type.Name == "IAsyncOperation");
        var method = iface == null ? null : iface.GetMethod("GetResultAsObject");
        return method == null ? null : method.Invoke(operation, null);
    }
    static int ReadInt(object target, string name)
    {
        var property = FindProperty(target, name);
        return property == null ? -1 : Convert.ToInt32(property.GetValue(target, null));
    }
    static bool ReadBool(object target, string name)
    {
        var property = FindProperty(target, name);
        return property != null && Convert.ToBoolean(property.GetValue(target, null));
    }
    static string ReadText(object target, string name)
    {
        var property = FindProperty(target, name);
        return property == null ? "missing" : Convert.ToString(property.GetValue(target, null));
    }
    static PropertyInfo FindProperty(object target, string name)
    {
        if (target == null)
            return null;
        var property = target.GetType().GetProperty(name, InstanceFlags);
        if (property != null)
            return property;
        foreach (var iface in target.GetType().GetInterfaces())
        {
            property = iface.GetProperty(name);
            if (property != null)
                return property;
        }
        return null;
    }
    static string Hash(string value)
    {
        if (value == null)
            return "null";
        unchecked
        {
            uint hash = 2166136261;
            int count = Math.Min(value.Length, MaxIdentityStringChars);
            for (int i = 0; i < count; i++)
                hash = (hash ^ value[i]) * 16777619;
            return hash.ToString("x8") + (value.Length > count ? "capped" : string.Empty);
        }
    }
    static string Header(string reason, string expectedGuid, string currentGuid, int supportIndex, int effectCatalogIndex,
                         AsyncOperationHandle<GameObject> lease, object leaseOp, IResourceLocation leaseLocation,
                         int candidateLocations, int locatorsVisited, int rawLocationsVisited, bool locatorTruncated,
                         bool rawLocationTruncated, bool uniqueLocationTruncated, bool expectedGuidInvalid,
                         bool currentGuidInvalid, int matched, bool matchRowsCapped, bool scanTruncated)
    {
        return string.Format("reason={0},expectedGuid={1},currentGuid={2},mapMatch={3},supportIndex={4},effectCatalogIndex={5},leaseValid={6}," +
                             "leaseRc={7},leaseVersion={8},leaseStatus={9},leaseOp={10},leasePk={11},leaseProvider={12}," +
                             "leaseInternal={13},candidateLocations={14},locatorsVisited={15},rawLocationsVisited={16}," +
                             "locatorScanTruncated={17},rawLocationScanTruncated={18},uniqueLocationScanTruncated={19}," +
                             "expectedGuidInvalid={20},currentGuidInvalid={21},cacheMatches={22},matchRowsCapped={23},scanTruncated={24}",
            reason, SafeGuid(expectedGuid), SafeGuid(currentGuid), IsGuid(expectedGuid) && expectedGuid == currentGuid,
            supportIndex, effectCatalogIndex, lease.IsValid(), ReadInt(leaseOp, "ReferenceCount"), ReadInt(leaseOp, "Version"),
            ReadText(leaseOp, "Status"), leaseOp == null ? "null" : RuntimeHelpers.GetHashCode(leaseOp).ToString(),
            Hash(leaseLocation == null ? null : leaseLocation.PrimaryKey), Hash(leaseLocation == null ? null : leaseLocation.ProviderId),
            Hash(leaseLocation == null ? null : leaseLocation.InternalId), candidateLocations, locatorsVisited, rawLocationsVisited,
            locatorTruncated, rawLocationTruncated, uniqueLocationTruncated, expectedGuidInvalid, currentGuidInvalid,
            matched, matchRowsCapped, scanTruncated);
    }

}

// Weak references let the native-only observer compare cache operations across
// the purchase without keeping a released Addressables operation alive.
internal sealed class NativeShrineEffectOperationBaseline
{
    readonly WeakReference operation;
    internal readonly int Version, ReferenceCount;
    internal NativeShrineEffectOperationBaseline(object operation, int version, int referenceCount)
    {
        this.operation = new WeakReference(operation);
        Version = version;
        ReferenceCount = referenceCount;
    }
    internal bool Matches(object candidate, int version)
    {
        return Version == version && ReferenceEquals(operation.Target, candidate);
    }
}
