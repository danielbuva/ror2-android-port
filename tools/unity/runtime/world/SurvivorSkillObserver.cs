// Subsystem: world/combat (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup constructor after player authority; teardown Dispose before world teardown.
using System;
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
    }

    CharacterBody body;
    SkillLocator locator;
    readonly GenericSkill[] skills;
    readonly SkillDef[] definitions;
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
        // Toolbot can replace the locator's slot components. Use the native
        // lookup at activation time, including its precedence for aliased slots.
        int index = locator ? (int)locator.FindSkillSlot(skill) : -1;
        if (index < 0 || index >= skills.Length)
            return;
        if (authority)
            report.slots[index].authorityActivations++;
        else
            report.slots[index].serverActivations++;
        RefreshSlots();
        SampleSlot(index);
    }

    void RefreshSlots()
    {
        if (!locator)
            return;
        for (int i = 0; i < skills.Length; i++)
        {
            var current = locator.GetSkill((SkillSlot)i);
            if (skills[i] != current)
            {
                report.slots[i].componentChanges++;
                skills[i] = current;
            }
        }
    }

    public void Sample()
    {
        if (report.cleaned)
            return;
        RefreshSlots();
        for (int i = 0; i < skills.Length; i++)
            SampleSlot(i);
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
        report.attached = false;
        report.cleaned = true;
    }
}
