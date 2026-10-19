#if UNITY_EDITOR
// API/input contracts create no gameplay object. The unawakened-prefab contract
// reads an already loaded asset and changes only a temporary local Loadout.
using System;
using System.Reflection;
using RoR2;
using RoR2.Skills;
using UnityEngine;

public static class DeveloperSkillVariantSelectionFixture
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    public static object RunNativeApiContract()
    {
        Require(typeof(Loadout.BodyLoadoutManager).GetMethod("GetSkillVariant", new[] { typeof(BodyIndex), typeof(int) }) != null &&
                    typeof(Loadout.BodyLoadoutManager).GetMethod("SetSkillVariant", new[] { typeof(BodyIndex), typeof(int), typeof(uint) }) != null,
                "Accepted native per-body Loadout skill-variant API changed");
        Require(typeof(CharacterMaster).GetMethod("SetLoadoutServer", new[] { typeof(Loadout) }) != null &&
                    typeof(SkillLocator).GetMethod("ApplyLoadoutServer", new[] { typeof(Loadout), typeof(BodyIndex) }) != null,
                "Accepted server loadout application API changed");
        Require(typeof(SkillCatalog).GetMethod("GetSkillFamily", new[] { typeof(int) }) != null &&
                    typeof(SkillCatalog).GetMethod("GetSkillDef", new[] { typeof(int) }) != null &&
                    typeof(SkillFamily).GetField("catalogIndex") == null &&
                    typeof(SkillFamily).GetProperty("catalogIndex") != null &&
                    typeof(SkillDef).GetProperty("skillIndex") != null,
                "Accepted family/definition catalog identity API changed");
        return new { bodyLoadoutVariantReadWrite = true, serverApplication = true,
                     exactFamilyAndDefinitionIndexes = true, noNativeStateCreated = true };
    }

    public static object RunStrictInputContract()
    {
        const string valid = "{\"attempt\":\"fixture\",\"developerSkillVariantOverride\":{" +
            "\"survivor\":\"Toolbot\",\"entries\":[{\"componentIndex\":4,\"familyCatalogIndex\":31," +
            "\"variantIndex\":1,\"skillCatalogIndex\":86}]}}";
        var request = DeveloperSkillVariantSelection.ParseSessionReport(valid);
        Require(request != null && request.survivor == "Toolbot" && request.entries.Length == 1 &&
                    request.entries[0].componentIndex == 4 && request.entries[0].familyCatalogIndex == 31 &&
                    request.entries[0].variantIndex == 1 && request.entries[0].skillCatalogIndex == 86,
                "Strict per-run selection did not preserve exact requested identities");
        Require(DeveloperSkillVariantSelection.ParseSessionReport("{\"attempt\":\"fixture\"}") == null,
                "Missing override must preserve native/profile default selection");
        bool refused = false;
        try { DeveloperSkillVariantSelection.ParseSessionReport(valid.Replace("\"familyCatalogIndex\":31,", "\"familyCatalogIndex\":31,\"extra\":true,")); }
        catch (DeveloperSkillVariantSelection.SelectionException) { refused = true; }
        Require(refused, "Unknown selector properties must be refused");
        return new { exactIndexesPreserved = true, absentSelectionMeansNoOverride = true,
                     unknownPropertiesRefused = true, noProfileOrNativeStateWritten = true };
    }

    // Pass an already-loaded base-body prefab asset from the editor catalog. This
    // reads its unawakened GenericSkill components and mutates only a local Loadout.
    public static object RunUnawakenedPrefabInventoryContract(GameObject bodyPrefab)
    {
        Require(bodyPrefab && !bodyPrefab.activeInHierarchy,
                "Fixture requires an inactive native body prefab asset; do not instantiate or activate it");
        var body = bodyPrefab.GetComponent<CharacterBody>();
        Require(body && body.bodyIndex != BodyIndex.None && BodyCatalog.GetBodyPrefab(body.bodyIndex) == bodyPrefab,
                "Fixture target must be the exact accepted body catalog prefab");
        var skills = bodyPrefab.GetComponents<GenericSkill>();
        Require(skills.Length > 0 && skills.Length <= 6, "Fixture body component count is outside the bounded base range");
        var selectedLoadout = new Loadout();
        for (int i = 0; i < skills.Length; i++)
        {
            Require(skills[i] && skills[i].skillFamily && !skills[i].skillDef,
                    "Fixture requires unawakened GenericSkill components with catalog family but no runtime skillDef");
            selectedLoadout.bodyLoadoutManager.SetSkillVariant(body.bodyIndex, i, 0);
        }
        var inventory = SurvivorSkillObserver.CaptureSkillVariantInventory(
            bodyPrefab, selectedLoadout, "native-master-loadout-pre-spawn");
        Require(inventory.status == "available" && inventory.components.Length == skills.Length,
                "Static prefab family metadata must enumerate without a runtime skillDef");
        for (int i = 0; i < inventory.components.Length; i++)
        {
            Require(inventory.components[i].componentIndex == i &&
                        inventory.components[i].selectedLoadoutVariantIndex == 0 &&
                        inventory.components[i].runtimeDefinitionStatus == "uninitialized-or-unassigned",
                    "Prefab inventory must distinguish native selected loadout from the uninitialized runtime definition");
        }
        return new { inactivePrefab = true, awakeInvoked = false, globalCatalogsChanged = false,
                     localLoadoutOnly = true, runtimeSkillDefRequired = false,
                     componentCount = skills.Length, selectedLoadoutVariantIndexes = true };
    }
}
#endif
