// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareWorldItemDisplays (WorldItemDisplaySession); teardown CleanupWorldItemDisplays (Dispose).
using System;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using RoR2;
using UnityEngine;

// Source attachment rules and original CharacterModel factories; owned Android lifecycle/materials.
public sealed partial class PortSession
{
    [Serializable]
    public class ItemDisplayObservation
    {
        public string item, parent;
        public int instances;
        public Vector3 localPosition, localScale;
    }
    [Serializable]
    public class WorldItemDisplayReport
    {
        public bool ready, cleaned;
        public int groups, rules, itemInstances, equipmentInstances, updates;
        public string error,
            scope =
                "Original eligible Commando display rules, attachment transforms and native item/equipment factories. Owned inventory callback and Android material copies; no exact PC pose/material parity or stock camera/highlight acceptance.";
        public List<ItemDisplayObservation> objects = new List<ItemDisplayObservation>();
    }
    // Shared with flight equipment and the destroyed-body lifecycle fixture.
    CharacterBody worldDisplayBody;
    CharacterModel worldDisplayModel;
    Action worldDisplayInventoryChanged;
    WorldItemDisplaySession worldItemDisplaySession;
    WorldItemDisplaySession GetWorldItemDisplaySession()
    {
        if (worldItemDisplaySession == null)
            worldItemDisplaySession = new WorldItemDisplaySession(this);
        return worldItemDisplaySession;
    }
    void PrepareWorldItemDisplays(CharacterBody body, SessionConfig cfg)
    {
        GetWorldItemDisplaySession().PrepareWorldItemDisplays(body, cfg);
    }
    void PresentWorldItemDisplays()
    {
        GetWorldItemDisplaySession().PresentWorldItemDisplays();
    }
    void ObserveWorldItemDisplays()
    {
        GetWorldItemDisplaySession().ObserveWorldItemDisplays();
    }
    void CleanupWorldItemDisplays()
    {
        GetWorldItemDisplaySession().Dispose();
    }

    // Create on first use, including fixture cleanup before setup. Retain after
    // Dispose for partial setup, repeated cleanup and later calls.
    sealed class WorldItemDisplaySession : IDisposable
    {
        readonly PortSession coordinator;
        ItemDisplayRuleSet worldDisplayRules, worldDisplayPriorRules;
        readonly HashSet<GameObject> worldDisplayInstances = new HashSet<GameObject>();
        public WorldItemDisplaySession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public void PrepareWorldItemDisplays(CharacterBody body, SessionConfig cfg)
        {
            if (!cfg.worldItemDisplays)
                return;
            coordinator.Check(!coordinator.worldDisplayModel && !worldDisplayRules && coordinator.worldDisplayInventoryChanged == null,
                              "Existing owned item display context");
            coordinator.worldDisplayBody = body;
            coordinator.worldDisplayModel = body.modelLocator.modelTransform.GetComponent<CharacterModel>();
            var displayModel = coordinator.worldDisplayModel;
            bool nativeOwnerRequested = coordinator.r.nativeSourceSkinLifecycleDiagnosticRequested;
            var nativeSkinOwner = displayModel ? displayModel.GetComponent<AndroidNativeSourceSkinLifecycle>() : null;
            var nativeSkinReport = coordinator.r.nova != null ? coordinator.r.nova.nativeSourceSkinLifecycle : null;
            bool nativeOwnerActive = nativeOwnerRequested && nativeSkinOwner &&
                                     nativeSkinOwner.IsActiveInventoryDisplayOwner(body, displayModel, nativeSkinReport);
            bool modelStateValid = displayModel &&
                                   (nativeOwnerRequested ? nativeOwnerActive : !displayModel.enabled);
            coordinator.Check(modelStateValid && displayModel.body == body && displayModel.itemDisplayRuleSet,
                              nativeOwnerRequested ? "Exact native source-skin item-display owner is not active"
                                                   : "Original disabled model/display rule context absent");
            worldDisplayPriorRules = coordinator.worldDisplayModel.itemDisplayRuleSet;
            worldDisplayRules = Instantiate(worldDisplayPriorRules);
            var eligible = coordinator.worldLootDefinitions.Cast<UnityEngine.Object>()
                               .Concat(coordinator.EligibleWorldEquipment().Cast<UnityEngine.Object>())
                               .ToArray();
            worldDisplayRules.keyAssetRuleGroups =
                worldDisplayRules.keyAssetRuleGroups.Where(group => eligible.Contains(group.keyAsset)).ToArray();
            coordinator.Check(worldDisplayRules.keyAssetRuleGroups.Length == eligible.Length &&
                                  worldDisplayRules.keyAssetRuleGroups.Select(group => group.keyAsset).Distinct().Count() ==
                                      eligible.Length,
                              "Original eligible display identity/coverage differs from measured source contract");
            foreach (var group in worldDisplayRules.keyAssetRuleGroups)
            {
                coordinator.Check(group.keyAsset && (!(group.keyAssetAddress?.RuntimeKeyIsValid() ?? false)),
                                  "Unresolved display key address");
                foreach (var rule in group.displayRuleGroup.rules ?? new ItemDisplayRule[0])
                    if (rule.ruleType == ItemDisplayRuleType.ParentedPrefab)
                        coordinator.Check((rule.followerPrefab || (rule.followerPrefabAddress?.RuntimeKeyIsValid() ?? false)) &&
                                              coordinator.worldDisplayModel.GetComponent<ChildLocator>().FindChild(rule.childName),
                                          "Original display prefab/address/parent contract absent: " + group.keyAsset.name + " / " +
                                              rule.childName);
            }
            var generation = worldDisplayRules.GenerateRuntimeValuesAsync();
            coordinator.Check(!generation.MoveNext(), "Direct source display rules yielded an unresolved request");
            coordinator.worldDisplayModel.itemDisplayRuleSet = worldDisplayRules;
            coordinator.r.itemDisplays = new WorldItemDisplayReport {
                groups = worldDisplayRules.keyAssetRuleGroups.Length,
                rules = worldDisplayRules.keyAssetRuleGroups.Sum(group => (group.displayRuleGroup.rules ?? new ItemDisplayRule[0]).Length)
            };
            var native = (Action)Delegate.CreateDelegate(
                typeof(Action), coordinator.worldDisplayModel,
                typeof(CharacterModel).GetMethod("OnInventoryChanged", BindingFlags.NonPublic | BindingFlags.Instance));
            coordinator.worldDisplayInventoryChanged = () =>
            {
                try
                {
                    bool ownerStillActive = nativeOwnerRequested && nativeSkinOwner &&
                                            nativeSkinOwner.IsActiveInventoryDisplayOwner(body, displayModel, nativeSkinReport);
                    AndroidNativeItemDisplayDispatch.Dispatch(nativeOwnerRequested, ownerStillActive, native,
                                                              PresentWorldItemDisplays);
                    coordinator.r.itemDisplays.updates++;
                }
                catch (Exception error)
                {
                    coordinator.r.itemDisplays.error = error.ToString();
                    coordinator.Save();
                }
            };
            // The source model already subscribed during OnEnable. Seed its native
            // factories once after installing the filtered rules; later events are
            // handled by that source owner and this session only presents results.
            if (nativeOwnerRequested)
                native();
            body.onInventoryChanged += coordinator.worldDisplayInventoryChanged;
            coordinator.worldDisplayInventoryChanged();
            coordinator.Check(string.IsNullOrEmpty(coordinator.r.itemDisplays.error),
                              "Original item display initialization failed: " + coordinator.r.itemDisplays.error);
            coordinator.r.itemDisplays.ready = true;
        }
        public void PresentWorldItemDisplays()
        {
            var rows = new List<ItemDisplayObservation>();
            int items = 0, equipment = 0;
            foreach (var group in worldDisplayRules.keyAssetRuleGroups)
            {
                var item = group.keyAsset as ItemDef;
                var equip = group.keyAsset as EquipmentDef;
                var instances = item ? coordinator.worldDisplayModel.GetItemDisplayObjects(item.itemIndex)
                                     : coordinator.worldDisplayModel.GetEquipmentDisplayObjects(equip.equipmentIndex);
                if (item)
                    items += instances.Count;
                else
                    equipment += instances.Count;
                foreach (var obj in instances)
                {
                    coordinator.Check(obj && obj.GetComponent<ItemDisplay>(), "Original display factory produced missing ItemDisplay");
                    if (worldDisplayInstances.Add(obj))
                    {
                        coordinator.PresentCommerceModel(obj.transform);
                        var display = obj.GetComponent<ItemDisplay>();
                        for (int i = 0; i < display.rendererInfos.Length; i++)
                        {
                            var renderer = display.rendererInfos[i].renderer;
                            if (renderer)
                                display.rendererInfos[i].defaultMaterial = renderer.sharedMaterial;
                        }
                    }
                    rows.Add(new ItemDisplayObservation { item = group.keyAsset.name, instances = instances.Count,
                                                          parent = obj.transform.parent.name, localPosition = obj.transform.localPosition,
                                                          localScale = obj.transform.localScale });
                }
            }
            coordinator.r.itemDisplays.itemInstances = items;
            coordinator.r.itemDisplays.equipmentInstances = equipment;
            coordinator.r.itemDisplays.objects = rows;
        }
        public void ObserveWorldItemDisplays()
        {
            if (coordinator.r.itemDisplays == null)
                return;
            coordinator.Check(string.IsNullOrEmpty(coordinator.r.itemDisplays.error),
                              "Original item display callback failed: " + coordinator.r.itemDisplays.error);
        }
        public void Dispose()
        {
            // Native death destroys the Unity object before this managed subscription ends.
            if (!ReferenceEquals(coordinator.worldDisplayBody, null) && coordinator.worldDisplayInventoryChanged != null)
                coordinator.worldDisplayBody.onInventoryChanged -= coordinator.worldDisplayInventoryChanged;
            coordinator.worldDisplayInventoryChanged = null;
            if (coordinator.worldDisplayModel)
            {
                coordinator.worldDisplayModel.DisableAllItemDisplays();
                Call(coordinator.worldDisplayModel, "SetEquipmentDisplay", EquipmentIndex.None);
                coordinator.worldDisplayModel.itemDisplayRuleSet = worldDisplayPriorRules;
            }
            if (worldDisplayRules)
                Destroy(worldDisplayRules);
            worldDisplayRules = null;
            worldDisplayPriorRules = null;
            coordinator.worldDisplayModel = null;
            coordinator.worldDisplayBody = null;
            if (coordinator.r.itemDisplays != null)
                coordinator.r.itemDisplays.cleaned = true;
            worldDisplayInstances.Clear();
        }
    }
}
