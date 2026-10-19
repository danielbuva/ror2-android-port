// Subsystem: world/combat (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup constructor after player authority; teardown Dispose before world teardown.
using System;
using System.Collections.Generic;
using RoR2;
using RoR2.Skills;
using UnityEngine;

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
    readonly GenericSkill[] skills;
    readonly SkillDef[] definitions;
    readonly List<SkillComponentEntry> componentEntries = new List<SkillComponentEntry>();
    public readonly Report report;

    public SurvivorSkillObserver(CharacterBody player)
    {
        if (!player || !player.skillLocator)
            throw new ArgumentException("Original player skill locator missing", nameof(player));
        body = player;
        locator = player.skillLocator;
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
        Record(skill, true);
    }
    void ServerActivated(GenericSkill skill)
    {
        Record(skill, false);
    }
    void Record(GenericSkill skill, bool authority)
    {
        if (report.cleaned || !skill)
            return;
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
            return;
        if (authority)
            component.report.authorityActivations++;
        else
            component.report.serverActivations++;
        SampleComponent(component);
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
