using System;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Skills;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

// Synthetic callbacks exercise observer ownership in the exact editor. No game
// content, skill execution, catalog setup or profile grants are involved.
public static class SurvivorSkillHost
{
    const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }
    static void Set(object target, string property, object value)
    {
        var field = target.GetType().GetField("<" + property + ">k__BackingField", Instance);
        Require(field != null, "Original fixture field changed: " + property);
        field.SetValue(target, value);
    }
    static Delegate Event(CharacterBody body, string name)
    {
        return (Delegate) typeof(CharacterBody).GetField(name, Instance).GetValue(body);
    }
    static int[] LoadoutSlots(GenericSkill[] skills)
    {
        return (int[]) typeof(PortSession)
            .GetMethod("OfflineLoadoutSlotIndices", BindingFlags.Static | BindingFlags.NonPublic)
            .Invoke(null, new object[] { skills });
    }
    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Require idle editor without a gameplay session");
        var scene = EditorSceneManager.NewPreviewScene();
        var root = new GameObject("Owned inactive survivor skill fixture");
        root.SetActive(false);
        SceneManager.MoveGameObjectToScene(root, scene);
        var definitions = new SkillDef[7];
        SurvivorSkillObserver observer = null;
        try
        {
            var body = root.AddComponent<CharacterBody>();
            var locator = root.AddComponent<SkillLocator>();
            Set(body, "skillLocator", locator);
            var skills = Enumerable.Range(0, 4).Select(i => root.AddComponent<GenericSkill>()).ToArray();
            for (int i = 0; i < definitions.Length; i++)
            {
                definitions[i] = ScriptableObject.CreateInstance<SkillDef>();
                ((ScriptableObject)definitions[i]).name = "FixtureSkill" + i;
                if (i < skills.Length)
                    Set(skills[i], "skillDef", definitions[i]);
            }
            var auxiliary = root.AddComponent<GenericSkill>();
            auxiliary.skillName = "FixtureAuxiliary";
            Set(auxiliary, "skillDef", definitions[5]);
            locator.primary = skills[0];
            locator.secondary = skills[1];
            locator.utility = skills[2];
            locator.special = skills[3];
            skills[1].hideInCharacterSelect = true;
            skills[2].hideInLoadoutSelect = true;
            var visibleSlots = LoadoutSlots(skills);
            Require(visibleSlots.SequenceEqual(new[] { 0, 1, 3 }),
                    "Loadout filtering discarded a character-select-only hidden slot or changed native serialized indices");
            var sourceRows = new[] { "Toolbot", "Captain" }
                                 .Select(name =>
                                         {
                                             var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(
                                                 "Assets/WholeGame/RoR2/Base/Characters/" + name + "/" + name + "Body.prefab");
                                             Require(prefab, "Imported source survivor missing: " + name);
                                             var originalSkills = prefab.GetComponents<GenericSkill>();
                                             var indices = LoadoutSlots(originalSkills);
                                             Require(indices.Length == (name == "Toolbot" ? 5 : 6),
                                                     "Source survivor loadout row count changed: " + name);
                                             Require(indices.All(index => originalSkills[index].skillFamily),
                                                     "Source survivor loadout family missing: " + name);
                                             return new { survivor = name, indices };
                                         })
                                 .ToArray();
            int sentinel = 0;
            int authoritySentinel = 0;
            Action<GenericSkill> prior = skill => sentinel++;
            Action<GenericSkill> priorAuthority = skill => authoritySentinel++;
            body.onSkillActivatedServer += prior;
            body.onSkillActivatedAuthority += priorAuthority;
            observer = new SurvivorSkillObserver(body);
            var report = observer.report;
            Require(report.attached && !report.cleaned && report.slots.Length == 4 && report.components.Length == 5 &&
                        report.slots.Select(slot => slot.initialDefinition)
                            .SequenceEqual(definitions.Take(4).Select(def => ((ScriptableObject)def).name)),
                    "Original slot identities missing");
            var auxiliaryReport = report.components.Single(row => row.instanceId == auxiliary.GetInstanceID());
            Require(auxiliaryReport.present && auxiliaryReport.componentIndex == 4 && auxiliaryReport.skillName == "FixtureAuxiliary" &&
                        auxiliaryReport.canonicalSlot == "None" && auxiliaryReport.definition == ((ScriptableObject)definitions[5]).name,
                    "Unbound source GenericSkill was not represented separately from canonical slots");
            body.ForceSkillActivatedAction(skills[0]);
            body.ForceSkillActivatedAction(skills[3]);
            Require(report.slots[0].serverActivations == 1 && report.slots[3].serverActivations == 1 &&
                        report.slots.All(slot => slot.authorityActivations == 0) && sentinel == 2,
                    "Native server callbacks were conflated with authority callbacks");
            body.ForceSkillActivatedAction(auxiliary);
            Require(auxiliaryReport.serverActivations == 1 && auxiliaryReport.authorityActivations == 0 &&
                        report.slots.Sum(slot => slot.serverActivations) == 2,
                    "Unbound component activation was lost or counted as a canonical slot");
            var lateAuxiliary = root.AddComponent<GenericSkill>();
            lateAuxiliary.skillName = "FixtureLateAuxiliary";
            Set(lateAuxiliary, "skillDef", definitions[6]);
            body.ForceSkillActivatedAction(lateAuxiliary);
            var lateReport = report.components.Single(row => row.instanceId == lateAuxiliary.GetInstanceID());
            Require(lateReport.present && lateReport.componentIndex == 5 && lateReport.serverActivations == 1 &&
                        lateReport.canonicalSlot == "None" && report.slots.Sum(slot => slot.serverActivations) == 2,
                    "Owned component activated before the next bounded sample was not reconciled separately");
            var authorityEvent = Event(body, "onSkillActivatedAuthority");
            for (int i = 0; i < skills.Length; i++)
                authorityEvent.DynamicInvoke(skills[i]);
            authorityEvent.DynamicInvoke(auxiliary);
            authorityEvent.DynamicInvoke(lateAuxiliary);
            Require(report.slots.All(slot => slot.authorityActivations == 1) && authoritySentinel == 6 &&
                        auxiliaryReport.authorityActivations == 1 && lateReport.authorityActivations == 1,
                    "Native authority callbacks were not recorded per original slot");
            Set(skills[0], "skillDef", definitions[4]);
            definitions[4].suppressSkillActivation = true;
            observer.Sample();
            Require(report.slots[0].initialDefinition == ((ScriptableObject)definitions[0]).name &&
                        report.slots[0].definition == ((ScriptableObject)definitions[4]).name && report.slots[0].definitionChanges == 1 &&
                        report.slots[0].suppressesActivationEvents,
                    "Source skill override or suppressed callback context lost");
            locator.primary = skills[1];
            body.ForceSkillActivatedAction(skills[1]);
            body.ForceSkillActivatedAction(skills[0]);
            Require(report.slots[0].componentChanges == 1 && report.slots[0].serverActivations == 2 &&
                        report.slots[1].serverActivations == 0 && report.slots[0].definition == ((ScriptableObject)definitions[1]).name &&
                        sentinel == 6 && auxiliaryReport.canonicalSlot == "None" && lateReport.canonicalSlot == "None" &&
                        report.components.Single(row => row.instanceId == skills[1].GetInstanceID()).canonicalSlot == "Primary",
                    "Native slot reassignment, alias precedence or displaced-skill filtering differs");
            observer.Dispose();
            observer.Dispose();
            body.ForceSkillActivatedAction(skills[0]);
            Require(!report.attached && report.cleaned && report.slots[0].serverActivations == 2 && sentinel == 7 &&
                        Event(body, "onSkillActivatedServer").GetInvocationList().SequenceEqual(new Delegate[] { prior }) &&
                        Event(body, "onSkillActivatedAuthority").GetInvocationList().SequenceEqual(new Delegate[] { priorAuthority }),
                    "Observer retained callbacks or removed a foreign listener");
            skills[2] = DestroyImmediateSkillAndSample(body, skills[2], definitions[2]);
            observer = new SurvivorSkillObserver(body);
            body.ForceSkillActivatedAction(body.skillLocator.primary);
            body.ForceSkillActivatedAction(auxiliary);
            UnityEngine.Object.DestroyImmediate(root);
            observer.Dispose();
            Require(Event(body, "onSkillActivatedServer").GetInvocationList().SequenceEqual(new Delegate[] { prior }) &&
                        Event(body, "onSkillActivatedAuthority").GetInvocationList().SequenceEqual(new Delegate[] { priorAuthority }) &&
                        observer.report.cleaned && observer.report.slots[0].serverActivations == 1 &&
                        observer.report.components.Single(row => row.instanceId == auxiliaryReport.instanceId).serverActivations == 1 &&
                        observer.report.slots.All(slot => !slot.enabled && slot.definition == "" && slot.declaredActivationState == "" &&
                            slot.machineState == "" && slot.stock == 0 && slot.maxStock == 0) &&
                        observer.report.components.All(row => !row.present && row.componentIndex == -1 &&
                            row.skillName == "" && row.canonicalSlot == "" && row.definition == "" && row.declaredActivationState == "" &&
                            row.stock == 0 && row.maxStock == 0),
                    "Destroyed native body retained an owned callback");
            return new { success = true,
                         slots = 4,
                         nativeServerCallbacks = 3,
                         nativeAuthorityCallbacks = 4,
                         overrideObserved = true,
                         teardown = true,
                         destroyedBodyTeardown = true,
                         loadoutSlotIndices = visibleSlots,
                         auxiliaryComponentObserved = true,
                         lateAuxiliaryBeforeSample = true,
                         slotReassignment = true,
                         sourceLoadoutRows = sourceRows };
        }
        finally
        {
            observer?.Dispose();
            UnityEngine.Object.DestroyImmediate(root);
            foreach (var definition in definitions)
                if (definition)
                    UnityEngine.Object.DestroyImmediate(definition);
            EditorSceneManager.ClosePreviewScene(scene);
        }
    }

    static GenericSkill DestroyImmediateSkillAndSample(CharacterBody body, GenericSkill skill, SkillDef definition)
    {
        // A separate observer verifies that destroyed Unity wrappers are
        // compared by managed identity and removed slots lose stale state.
        using (var probe = new SurvivorSkillObserver(body))
        {
            int destroyedId = skill.GetInstanceID();
            UnityEngine.Object.DestroyImmediate(skill);
            body.ForceSkillActivatedAction(skill);
            probe.Sample();
            var slot = probe.report.slots[2];
            var removedComponent = probe.report.components.Single(row => row.instanceId == destroyedId);
            Require(slot.componentChanges == 1 && slot.serverActivations == 0 && !slot.enabled && slot.definition == "" && slot.declaredActivationState == "" &&
                        slot.machineState == "" && slot.stock == 0 && slot.maxStock == 0 && !slot.suppressesActivationEvents &&
                        !removedComponent.present && removedComponent.componentIndex == -1 && removedComponent.skillName == "" &&
                        removedComponent.canonicalSlot == "" && removedComponent.definition == "" &&
                        removedComponent.declaredActivationState == "" && removedComponent.stock == 0 && removedComponent.maxStock == 0,
                    "Removed skill slot retained stale snapshot state");
            body.skillLocator.utility = null;
            probe.Sample();
            Require(slot.componentChanges == 1, "Destroyed wrapper to null counted twice");
            var replacement = body.gameObject.AddComponent<GenericSkill>();
            Set(replacement, "skillDef", definition);
            body.skillLocator.utility = replacement;
            probe.Sample();
            var replacementRow = probe.report.components.Single(row => row.instanceId == replacement.GetInstanceID());
            Require(slot.componentChanges == 2 && slot.definition == ((ScriptableObject)definition).name && replacementRow.present &&
                        replacementRow.canonicalSlot == "Utility" && !removedComponent.present,
                    "Replacement after destroyed component was not observed");
            return replacement;
        }
    }
}
