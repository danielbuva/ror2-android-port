// Per-run developer-only selection. Mutates only the selected master Loadout;
// never edits UserProfile, native SkillFamily assets, entitlement or unlock state.
using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using RoR2;
using RoR2.Skills;
using UnityEngine;
using UnityEngine.Networking;

public static class DeveloperSkillVariantSelection
{
    static readonly string[] BaseSurvivorKeys = {
        "Commando", "Huntress", "Bandit2", "Toolbot", "Engi", "Mage", "Merc", "Treebot", "Loader", "Croco", "Captain"
    };

    public sealed class SelectionException : Exception
    {
        public readonly string outcome;
        public SelectionException(string outcome, string message) : base(message) { this.outcome = outcome; }
    }

    static void Require(bool condition, string outcome, string message)
    {
        if (!condition) throw new SelectionException(outcome, message);
    }

    static int ReadIndex(JObject item, string name)
    {
        JToken token = item[name];
        Require(token != null && token.Type == JTokenType.Integer, "refused", "Variant selector field must be an integer: " + name);
        long value = token.Value<long>();
        Require(value >= 0 && value <= int.MaxValue, "refused", "Variant selector index is outside Int32 range: " + name);
        return (int)value;
    }

    static void RequireExactProperties(JObject value, params string[] expected)
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (JProperty property in value.Properties())
        {
            Require(Array.IndexOf(expected, property.Name) >= 0, "refused", "Unknown variant selector property: " + property.Name);
            Require(seen.Add(property.Name), "ambiguous", "Duplicate variant selector property: " + property.Name);
        }
        foreach (string name in expected)
            Require(seen.Contains(name), "refused", "Missing variant selector property: " + name);
    }

    public static PortSession.DeveloperSkillVariantOverrideRequest ParseSessionReport(string json)
    {
        JObject root;
        using (var reader = new JsonTextReader(new StringReader(json)))
            root = JObject.Load(reader, new JsonLoadSettings { DuplicatePropertyNameHandling = DuplicatePropertyNameHandling.Error });
        JToken token = root["developerSkillVariantOverride"];
        if (token == null || token.Type == JTokenType.Null)
            return null;
        Require(token.Type == JTokenType.Object, "refused", "Developer skill-variant selection must be an object");
        var value = (JObject)token;
        RequireExactProperties(value, "survivor", "entries");
        JToken survivorToken = value["survivor"];
        Require(survivorToken.Type == JTokenType.String, "refused", "Variant selection survivor must be a catalog key");
        string survivor = survivorToken.Value<string>();
        Require(Array.IndexOf(BaseSurvivorKeys, survivor) >= 0, "unknown", "Variant selection is limited to base survivor catalog keys");
        JToken entriesToken = value["entries"];
        Require(entriesToken.Type == JTokenType.Array, "refused", "Variant selection entries must be an array");
        var entries = (JArray)entriesToken;
        Require(entries.Count > 0 && entries.Count <= 6, "refused", "Variant selection must contain 1 to 6 component entries");
        var result = new PortSession.DeveloperSkillVariantOverrideRequest {
            survivor = survivor,
            entries = new PortSession.DeveloperSkillVariantOverrideEntry[entries.Count]
        };
        var components = new HashSet<int>();
        for (int i = 0; i < entries.Count; i++)
        {
            Require(entries[i].Type == JTokenType.Object, "refused", "Variant selection entry must be an object");
            var entry = (JObject)entries[i];
            RequireExactProperties(entry, "componentIndex", "familyCatalogIndex", "variantIndex", "skillCatalogIndex");
            int component = ReadIndex(entry, "componentIndex");
            Require(components.Add(component), "ambiguous", "Multiple variant selections target one GenericSkill component");
            result.entries[i] = new PortSession.DeveloperSkillVariantOverrideEntry {
                componentIndex = component,
                familyCatalogIndex = ReadIndex(entry, "familyCatalogIndex"),
                variantIndex = ReadIndex(entry, "variantIndex"),
                skillCatalogIndex = ReadIndex(entry, "skillCatalogIndex")
            };
        }
        return result;
    }

    static bool IsExpansionGated(SkillFamily.Variant variant)
    {
        if (variant.unlockableDef)
            return variant.unlockableDef.requiredExpansion;
        if (string.IsNullOrEmpty(variant.unlockableName))
            return false;
        var legacyUnlock = UnlockableCatalog.GetUnlockableDef(variant.unlockableName);
        Require(legacyUnlock, "unknown", "Legacy skill unlock name is not present in the accepted catalog");
        return legacyUnlock.requiredExpansion;
    }

    public static int[] Apply(PortSession.DeveloperSkillVariantOverrideRequest request,
                              CharacterMaster master, GameObject bodyPrefab, string selectedSurvivor)
    {
        Require(NetworkServer.active, "refused", "Developer skill-variant override requires native server authority");
        Require(request != null && request.entries != null, "refused", "Developer skill-variant request is incomplete");
        Require(request.entries.Length > 0 && request.entries.Length <= 6, "refused", "Developer skill-variant request count is invalid");
        Require(request.survivor == selectedSurvivor && Array.IndexOf(BaseSurvivorKeys, selectedSurvivor) >= 0,
                "unknown", "Variant selector survivor differs from the selected base survivor");
        Require(master && master.loadout != null && bodyPrefab && master.bodyPrefab == bodyPrefab,
                "refused", "Variant selector requires the exact pre-spawn master/body prefab");
        var body = bodyPrefab.GetComponent<CharacterBody>();
        Require(body && body.bodyIndex != BodyIndex.None && BodyCatalog.GetBodyPrefab(body.bodyIndex) == bodyPrefab,
                "unknown", "Variant selector body catalog identity differs");
        GenericSkill[] slots = bodyPrefab.GetComponents<GenericSkill>();
        Require(slots.Length > 0 && slots.Length <= 6,
                "refused", "Variant selector body exceeds the bounded base-component range");
        var selectedSkills = new SkillDef[request.entries.Length];
        var selectedComponents = new HashSet<int>();
        for (int i = 0; i < request.entries.Length; i++)
        {
            var entry = request.entries[i];
            Require(selectedComponents.Add(entry.componentIndex), "ambiguous", "Multiple variant selections target one GenericSkill component");
            Require(entry.componentIndex >= 0 && entry.componentIndex < slots.Length && slots[entry.componentIndex],
                    "unknown", "Variant selector component index is unavailable on selected body");
            var family = slots[entry.componentIndex].skillFamily;
            Require(family && family.catalogIndex == entry.familyCatalogIndex &&
                        SkillCatalog.GetSkillFamily(entry.familyCatalogIndex) == family,
                    "unknown", "Variant selector family identity differs from selected body component");
            Require(family.variants != null && family.variants.Length > 0 && family.variants.Length <= 16,
                    "refused", "Variant selector family exceeds the bounded variant catalog range");
            Require(entry.variantIndex >= 0 && entry.variantIndex < family.variants.Length,
                    "unknown", "Variant selector index is outside the selected skill family");
            var definition = family.variants[entry.variantIndex].skillDef;
            Require(definition && definition.skillIndex == entry.skillCatalogIndex &&
                        SkillCatalog.GetSkillDef(entry.skillCatalogIndex) == definition,
                    "unknown", "Variant selector SkillDef identity differs from the selected family variant");
            Require(!IsExpansionGated(family.variants[entry.variantIndex]), "refused",
                    "Developer selector cannot use an expansion-gated skill variant");
            selectedSkills[i] = definition;
        }

        var perRunLoadout = new Loadout();
        master.loadout.Copy(perRunLoadout);
        foreach (var entry in request.entries)
            perRunLoadout.bodyLoadoutManager.SetSkillVariant(body.bodyIndex, entry.componentIndex, (uint)entry.variantIndex);
        master.SetLoadoutServer(perRunLoadout);

        var applied = new int[slots.Length];
        for (int i = 0; i < slots.Length; i++)
            applied[i] = (int)master.loadout.bodyLoadoutManager.GetSkillVariant(body.bodyIndex, i);
        for (int i = 0; i < request.entries.Length; i++)
        {
            var entry = request.entries[i];
            Require(slots[entry.componentIndex].skillFamily.variants[applied[entry.componentIndex]].skillDef == selectedSkills[i],
                    "refused", "Native per-run Loadout did not retain the requested skill definition");
        }
        return applied;
    }
}
