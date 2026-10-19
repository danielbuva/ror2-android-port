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
        var definitions = new SkillDef[5];
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
            Action<GenericSkill> prior = skill => sentinel++;
            body.onSkillActivatedServer += prior;
            observer = new SurvivorSkillObserver(body);
            var report = observer.report;
            Require(report.attached && !report.cleaned && report.slots.Length == 4 &&
                        report.slots.Select(slot => slot.initialDefinition)
                            .SequenceEqual(definitions.Take(4).Select(def => ((ScriptableObject)def).name)),
                    "Original slot identities missing");
            body.ForceSkillActivatedAction(skills[0]);
            body.ForceSkillActivatedAction(skills[3]);
            Require(report.slots[0].serverActivations == 1 && report.slots[3].serverActivations == 1 &&
                        report.slots.All(slot => slot.authorityActivations == 0) && sentinel == 2,
                    "Native server callbacks were conflated with authority callbacks");
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
                        sentinel == 4,
                    "Native slot reassignment, alias precedence or displaced-skill filtering differs");
            observer.Dispose();
            observer.Dispose();
            body.ForceSkillActivatedAction(skills[0]);
            Require(!report.attached && report.cleaned && report.slots[0].serverActivations == 2 && sentinel == 5 &&
                        Event(body, "onSkillActivatedServer").GetInvocationList().SequenceEqual(new Delegate[] { prior }) &&
                        Event(body, "onSkillActivatedAuthority") == null,
                    "Observer retained callbacks or removed a foreign listener");
            observer = new SurvivorSkillObserver(body);
            UnityEngine.Object.DestroyImmediate(root);
            observer.Dispose();
            Require(Event(body, "onSkillActivatedServer").GetInvocationList().SequenceEqual(new Delegate[] { prior }) &&
                        Event(body, "onSkillActivatedAuthority") == null,
                    "Destroyed native body retained an owned callback");
            return new { success = true,
                         slots = 4,
                         nativeServerCallbacks = 3,
                         overrideObserved = true,
                         teardown = true,
                         destroyedBodyTeardown = true,
                         loadoutSlotIndices = visibleSlots,
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
}
