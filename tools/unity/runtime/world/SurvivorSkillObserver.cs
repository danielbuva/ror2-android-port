// Subsystem: world/combat (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup constructor after player authority; teardown Dispose before world teardown.
using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Skills;
using UnityEngine;
using UnityEngine.Networking;

// Observes the player's original callbacks. Counts prove activation, not damage,
// placement, targeting, animation or the complete semantics of an ability.
public sealed class SurvivorSkillObserver : IDisposable
{
    [Serializable]
    public sealed class SlotReport
    {
        public string slot, initialDefinition, definition, declaredActivationState, machineState;
        public int authorityActivations, serverActivations, definitionChanges, componentChanges, stock, maxStock;
        public bool enabled, suppressesActivationEvents;
    }
    [Serializable]
    public sealed class Report
    {
        public string body;
        public bool attached, cleaned;
        public SlotReport[] slots;
        public SkillComponentReport[] components;
        public SkillVariantInventoryReport skillVariantInventory;
    }
    [Serializable]
    public sealed class SkillVariantInventoryReport
    {
        public string status, error, selectionSource;
        public int bodyIndex;
        public SkillVariantComponentReport[] components;
    }
    [Serializable]
    public sealed class SkillVariantComponentReport
    {
        public int componentIndex, familyCatalogIndex, selectedLoadoutVariantIndex, selectedLoadoutSkillCatalogIndex;
        public int runtimeSkillCatalogIndex;
        public string runtimeDefinitionStatus;
        public string skillName;
        public SkillVariantEntryReport[] variants;
    }
    [Serializable]
    public sealed class SkillVariantEntryReport
    {
        public int variantIndex, skillCatalogIndex;
        public string skillName, unlockableName;
        public bool expansionGated;
    }
    [Serializable]
    public sealed class SkillComponentReport
    {
        public int componentIndex, instanceId, authorityActivations, serverActivations, definitionChanges, stock, maxStock;
        public string skillName, canonicalSlot, definition, declaredActivationState;
        public bool present, enabled, suppressesActivationEvents;
    }

    sealed class SkillComponentEntry
    {
        public GenericSkill skill;
        public SkillDef definition;
        public SkillComponentReport report;
    }

    CharacterBody body;
    SkillLocator locator;
    Action onRecognizedAuthoritySkill;
    readonly GenericSkill[] skills;
    readonly SkillDef[] definitions;
    readonly List<SkillComponentEntry> componentEntries = new List<SkillComponentEntry>();
    public readonly Report report;

    public static SkillVariantInventoryReport CaptureSkillVariantInventory(GameObject bodyPrefab, Loadout selectedLoadout,
                                                                           string selectionSource)
    {
        const int maxBodyComponents = 6;
        const int maxVariantsPerFamily = 16;
        var inventory = new SkillVariantInventoryReport {
            status = "refused", bodyIndex = (int)BodyIndex.None, selectionSource = selectionSource ?? ""
        };
        var body = bodyPrefab ? bodyPrefab.GetComponent<CharacterBody>() : null;
        var catalogPrefab = body && body.bodyIndex != BodyIndex.None ? BodyCatalog.GetBodyPrefab(body.bodyIndex) : null;
        // A live body's configured master prefab is not its ownership contract.
        // Use the reciprocal native body/master link and exact server mappings.
        var master = body ? body.master : null;
        bool mappedLiveBody = body && master && master.hasBody && master.GetBody() == body &&
                              NetworkServer.active && body.isServer && master.isServer &&
                              body.netId.Value != 0 && master.netId.Value != 0 &&
                              NetworkServer.FindLocalObject(body.netId) == body.gameObject &&
                              NetworkServer.FindLocalObject(master.netId) == master.gameObject;
        bool exactBody = body && catalogPrefab &&
                         (catalogPrefab == bodyPrefab || mappedLiveBody);
        if (!exactBody)
        {
            inventory.error = "Selected body prefab has no exact body catalog identity";
            return inventory;
        }
        if (selectedLoadout == null || string.IsNullOrEmpty(selectionSource))
        {
            inventory.error = "Skill variant inventory requires an explicit native Loadout selection source";
            return inventory;
        }
        inventory.bodyIndex = (int)body.bodyIndex;
        var skills = bodyPrefab.GetComponents<GenericSkill>();
        var catalogSkills = catalogPrefab.GetComponents<GenericSkill>();
        if (skills.Length < 1 || skills.Length > maxBodyComponents)
        {
            inventory.error = "Skill variant inventory component count is outside the bounded base-body range";
            return inventory;
        }
        if (catalogSkills.Length != skills.Length)
        {
            inventory.error = "Live body skill component count differs from its exact catalog prefab";
            return inventory;
        }
        var components = new SkillVariantComponentReport[skills.Length];
        for (int componentIndex = 0; componentIndex < skills.Length; componentIndex++)
        {
            var skill = skills[componentIndex];
            var family = skill ? skill.skillFamily : null;
            if (!catalogSkills[componentIndex] || catalogSkills[componentIndex].skillFamily != family)
            {
                inventory.error = "Body skill family differs from its catalog component at index " + componentIndex;
                return inventory;
            }
            if (!family || family.catalogIndex < 0 || SkillCatalog.GetSkillFamily(family.catalogIndex) != family ||
                family.variants == null || family.variants.Length < 1 || family.variants.Length > maxVariantsPerFamily)
            {
                inventory.error = "Skill variant family is unavailable, mismatched, empty, or exceeds the bounded inventory size at component " + componentIndex;
                return inventory;
            }
            var variants = new SkillVariantEntryReport[family.variants.Length];
            for (int variantIndex = 0; variantIndex < family.variants.Length; variantIndex++)
            {
                var variant = family.variants[variantIndex];
                var definition = variant.skillDef;
                if (!definition || definition.skillIndex < 0 || SkillCatalog.GetSkillDef(definition.skillIndex) != definition)
                {
                    inventory.error = "Skill variant definition lacks exact catalog identity at component " + componentIndex + ", variant " + variantIndex;
                    return inventory;
                }
                var unlockable = variant.unlockableDef;
                var unlockableName = unlockable ? unlockable.cachedName : (variant.unlockableName ?? "");
                bool expansionGated = unlockable && unlockable.requiredExpansion;
                if (!unlockable && !string.IsNullOrEmpty(variant.unlockableName))
                {
                    unlockable = UnlockableCatalog.GetUnlockableDef(variant.unlockableName);
                    if (!unlockable)
                    {
                        inventory.error = "Skill variant legacy unlock identity is unavailable at component " + componentIndex + ", variant " + variantIndex;
                        return inventory;
                    }
                    expansionGated = unlockable.requiredExpansion;
                }
                variants[variantIndex] = new SkillVariantEntryReport {
                    variantIndex = variantIndex,
                    skillCatalogIndex = definition.skillIndex,
                    skillName = ((ScriptableObject)definition).name,
                    unlockableName = unlockableName,
                    expansionGated = expansionGated
                };
            }
            uint selectedVariant = selectedLoadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex, componentIndex);
            if (selectedVariant >= family.variants.Length)
            {
                inventory.error = "Native Loadout selected an unavailable family variant at component " + componentIndex;
                return inventory;
            }
            var selectedDefinition = family.variants[(int)selectedVariant].skillDef;
            if (!selectedDefinition || selectedDefinition.skillIndex < 0 ||
                SkillCatalog.GetSkillDef(selectedDefinition.skillIndex) != selectedDefinition)
            {
                inventory.error = "Selected native Loadout variant lacks exact SkillDef catalog identity at component " + componentIndex;
                return inventory;
            }
            var runtimeDefinition = skill.skillDef;
            string runtimeStatus;
            int runtimeIndex = -1;
            if (!runtimeDefinition)
                runtimeStatus = "uninitialized-or-unassigned";
            else if (runtimeDefinition.skillIndex < 0 || SkillCatalog.GetSkillDef(runtimeDefinition.skillIndex) != runtimeDefinition)
                runtimeStatus = "runtime-override-or-unmapped";
            else
            {
                runtimeIndex = runtimeDefinition.skillIndex;
                runtimeStatus = runtimeDefinition == selectedDefinition ? "matches-selected-native-loadout" : "differs-from-selected-native-loadout";
            }
            components[componentIndex] = new SkillVariantComponentReport {
                componentIndex = componentIndex,
                familyCatalogIndex = family.catalogIndex,
                selectedLoadoutVariantIndex = (int)selectedVariant,
                selectedLoadoutSkillCatalogIndex = selectedDefinition.skillIndex,
                runtimeSkillCatalogIndex = runtimeIndex,
                runtimeDefinitionStatus = runtimeStatus,
                skillName = skill.skillName ?? "",
                variants = variants
            };
        }
        inventory.status = "available";
        inventory.components = components;
        return inventory;
    }

    public SurvivorSkillObserver(CharacterBody player, Action onRecognizedAuthoritySkill = null)
    {
        if (!player || !player.skillLocator)
            throw new ArgumentException("Original player skill locator missing", nameof(player));
        body = player;
        locator = player.skillLocator;
        this.onRecognizedAuthoritySkill = onRecognizedAuthoritySkill;
        skills = new[] { locator.primary, locator.secondary, locator.utility, locator.special };
        definitions = new SkillDef[skills.Length];
        var names = new[] { "primary", "secondary", "utility", "special" };
        report = new Report { body = player.name, slots = new SlotReport[skills.Length] };
        for (int i = 0; i < skills.Length; i++)
        {
            if (!skills[i] || !skills[i].skillDef)
                throw new ArgumentException("Original player skill slot missing: " + names[i], nameof(player));
            report.slots[i] = new SlotReport { slot = names[i], initialDefinition = ((ScriptableObject)skills[i].skillDef).name };
        }
        Sample();
        body.onSkillActivatedAuthority += AuthorityActivated;
        body.onSkillActivatedServer += ServerActivated;
        report.attached = true;
    }

    void AuthorityActivated(GenericSkill skill)
    {
        if (Record(skill, true) && body && body.networkIdentity && body.networkIdentity.hasAuthority)
            onRecognizedAuthoritySkill?.Invoke();
    }
    void ServerActivated(GenericSkill skill)
    {
        Record(skill, false);
    }
    bool Record(GenericSkill skill, bool authority)
    {
        if (report.cleaned || !skill)
            return false;
        // Toolbot can replace the locator's slot components. Use the native
        // lookup at activation time, including its precedence for aliased slots.
        int index = locator ? (int)locator.FindSkillSlot(skill) : -1;
        if (index >= 0 && index < skills.Length)
        {
            if (authority)
                report.slots[index].authorityActivations++;
            else
                report.slots[index].serverActivations++;
            RefreshSlots();
            SampleSlot(index);
        }
        // The original loadout can contain GenericSkill components which are
        // not one of SkillLocator's four named slots. Keep those observations
        // separate from the canonical counters, and attribute only by the
        // exact managed component reference cached at the bounded sample.
        var component = FindComponent(skill);
        if (component == null && skill && body && skill.gameObject == body.gameObject)
        {
            // A GenericSkill may be attached and activated between bounded
            // samples. Reconcile only this owned callback miss; never scan a
            // different body's component list.
            ReconcileComponents();
            component = FindComponent(skill);
        }
        if (component == null)
            return index >= 0 && index < skills.Length;
        if (authority)
            component.report.authorityActivations++;
        else
            component.report.serverActivations++;
        SampleComponent(component);
        return true;
    }

    void RefreshSlots()
    {
        if (!locator)
        {
            ClearSlotSnapshots();
            return;
        }
        for (int i = 0; i < skills.Length; i++)
        {
            var source = locator.GetSkill((SkillSlot)i);
            // Canonicalize Unity's destroyed wrapper to a real managed null.
            var current = source ? source : null;
            // Unity's overloaded equality treats a destroyed native wrapper as
            // null. Compare managed identity so a destroyed component replaced
            // by an empty slot is still recorded as a change.
            if (!ReferenceEquals(skills[i], current))
            {
                report.slots[i].componentChanges++;
                skills[i] = current;
                if (!current)
                {
                    definitions[i] = null;
                    ResetSlotSnapshot(report.slots[i]);
                }
            }
        }
    }

    static void ResetSlotSnapshot(SlotReport slot)
    {
        slot.definition = "";
        slot.declaredActivationState = "";
        slot.machineState = "";
        slot.enabled = false;
        slot.suppressesActivationEvents = false;
        slot.stock = 0;
        slot.maxStock = 0;
    }

    void ClearSlotSnapshots()
    {
        for (int i = 0; i < skills.Length; i++)
        {
            skills[i] = null;
            definitions[i] = null;
            ResetSlotSnapshot(report.slots[i]);
        }
    }

    public void Sample()
    {
        if (report.cleaned)
            return;
        RefreshSlots();
        ReconcileComponents();
        for (int i = 0; i < skills.Length; i++)
            SampleSlot(i);
    }

    void ReconcileComponents()
    {
        if (!body)
        {
            foreach (var entry in componentEntries)
            {
                ClearComponent(entry.report);
                entry.skill = null;
                entry.definition = null;
            }
            PublishComponentReports();
            return;
        }
        var current = body.GetComponents<GenericSkill>();
        foreach (var entry in componentEntries)
        {
            entry.report.present = false;
            entry.report.componentIndex = -1;
        }
        for (int index = 0; index < current.Length; index++)
        {
            var skill = current[index];
            if (!skill)
                continue;
            var entry = FindComponent(skill);
            if (entry == null)
            {
                entry = new SkillComponentEntry {
                    skill = skill,
                    report = new SkillComponentReport {
                        instanceId = skill.GetInstanceID(),
                        skillName = skill.skillName ?? ""
                    }
                };
                componentEntries.Add(entry);
            }
            entry.report.present = true;
            entry.report.componentIndex = index;
            SampleComponent(entry);
        }
        for (int i = 0; i < componentEntries.Count; i++)
        {
            var entry = componentEntries[i];
            if (entry.report.present)
                continue;
            ClearComponent(entry.report);
            entry.skill = null;
            entry.definition = null;
        }
        PublishComponentReports();
    }

    void PublishComponentReports()
    {
        var rows = new SkillComponentReport[componentEntries.Count];
        for (int i = 0; i < rows.Length; i++)
            rows[i] = componentEntries[i].report;
        report.components = rows;
    }

    string CanonicalSlot(GenericSkill skill)
    {
        if (!locator)
            return "None";
        switch (locator.FindSkillSlot(skill))
        {
            case SkillSlot.Primary: return "Primary";
            case SkillSlot.Secondary: return "Secondary";
            case SkillSlot.Utility: return "Utility";
            case SkillSlot.Special: return "Special";
            default: return "None";
        }
    }

    SkillComponentEntry FindComponent(GenericSkill skill)
    {
        for (int i = 0; i < componentEntries.Count; i++)
            if (ReferenceEquals(componentEntries[i].skill, skill))
                return componentEntries[i];
        return null;
    }

    void SampleComponent(SkillComponentEntry entry)
    {
        var skill = entry.skill;
        var row = entry.report;
        if (!skill)
        {
            ClearComponent(row);
            return;
        }
        row.present = true;
        row.canonicalSlot = CanonicalSlot(skill);
        row.enabled = skill.enabled;
        var definition = skill.skillDef;
        if (row.definition == null || entry.definition != definition)
        {
            if (row.definition != null)
                row.definitionChanges++;
            row.definition = definition ? ((ScriptableObject)definition).name : "";
            entry.definition = definition;
        }
        row.declaredActivationState = definition ? definition.activationState.typeName : "";
        row.suppressesActivationEvents = definition && definition.suppressSkillActivation;
        row.stock = skill.stock;
        row.maxStock = skill.maxStock;
    }

    static void ClearComponent(SkillComponentReport row)
    {
        row.present = false;
        row.componentIndex = -1;
        row.skillName = "";
        row.canonicalSlot = "";
        row.definition = "";
        row.declaredActivationState = "";
        row.enabled = false;
        row.suppressesActivationEvents = false;
        row.stock = 0;
        row.maxStock = 0;
    }
    void SampleSlot(int index)
    {
        var skill = skills[index];
        var slot = report.slots[index];
        slot.enabled = skill && skill.enabled;
        if (!skill)
            return;
        var definition = skill.skillDef;
        if (slot.definition == null || definitions[index] != definition)
        {
            if (slot.definition != null)
                slot.definitionChanges++;
            // Native Object.name allocates; read it only when the definition
            // changes, never once for every primary-fire callback.
            slot.definition = definition ? ((ScriptableObject)definition).name : "";
            definitions[index] = definition;
        }
        slot.declaredActivationState = definition ? definition.activationState.typeName : "";
        slot.suppressesActivationEvents = definition && definition.suppressSkillActivation;
        slot.stock = skill.stock;
        slot.maxStock = skill.maxStock;
        slot.machineState = skill.stateMachine && skill.stateMachine.state != null ? skill.stateMachine.state.GetType().FullName : "";
    }

    public void Dispose()
    {
        if (report.cleaned)
            return;
        Sample();
        // These are managed events and remain accessible after Unity destroys the
        // native body. Release the delegate even for a destroyed Unity wrapper.
        if (!ReferenceEquals(body, null))
        {
            body.onSkillActivatedAuthority -= AuthorityActivated;
            body.onSkillActivatedServer -= ServerActivated;
        }
        body = null;
        locator = null;
        onRecognizedAuthoritySkill = null;
        Array.Clear(skills, 0, skills.Length);
        Array.Clear(definitions, 0, definitions.Length);
        foreach (var entry in componentEntries)
        {
            ClearComponent(entry.report);
            entry.skill = null;
            entry.definition = null;
        }
        PublishComponentReports();
        componentEntries.Clear();
        report.attached = false;
        report.cleaned = true;
    }
}
