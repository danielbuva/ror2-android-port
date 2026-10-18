using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Path = System.IO.Path;
using System.Linq;
using System.Reflection;
using Assets.RoR2.Scripts.Platform;
using Newtonsoft.Json.Linq;
using RoR2;
using RoR2.ContentManagement;
using RoR2.EntitlementManagement;
using RoR2.ExpansionManagement;
using RoR2.Stats;
using UnityEditor;
using UnityEngine;

// Native achievement/storage checks with complete source definition families.
// Synthetic thresholds and rewards exist only in this ignored host fixture.
public static class AndroidProgressionHost
{
    const BindingFlags Flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    static void Check(bool value, string message)
    {
        if (!value)
            throw new InvalidOperationException(message);
    }
    static FieldInfo Field(Type type, string name)
    {
        var field = type.GetField(name, Flags);
        Check(field != null, "Missing original host field: " + type.Name + "." + name);
        return field;
    }
    static void Set(Type type, string name, object value)
    {
        Field(type, name).SetValue(null, value);
    }
    static void NativeSet(Type type, string name, object values)
    {
        type.GetMethod(name, Flags).Invoke(null, new[] { values });
    }
    static DictionaryEntry[] Entries(IDictionary map)
    {
        var result = new List<DictionaryEntry>();
        foreach (DictionaryEntry entry in map)
            result.Add(entry);
        return result.ToArray();
    }
    static UserProfile Clone(UserProfile profile)
    {
        var result = UserProfile.FromXml(UserProfile.ToXml(profile));
        result.canSave = false;
        return result;
    }
    sealed class Fixture : IDisposable
    {
        readonly List<Action> restore = new List<Action>();
        readonly List<UnityEngine.Object> owned = new List<UnityEngine.Object>();
        readonly List<Action> checkSources = new List<Action>();
        public SurvivorDef Survivor(SurvivorDef source)
        {
            string serialized = EditorJsonUtility.ToJson(source);
            bool dirty = EditorUtility.IsDirty(source);
            string name = source.cachedName;
            checkSources.Add(() => Check(EditorUtility.IsDirty(source) == dirty && EditorJsonUtility.ToJson(source) == serialized &&
                                             source.cachedName == name,
                                         "Host fixture mutated imported survivor data"));
            var clone = UnityEngine.Object.Instantiate(source);
            owned.Add(clone);
            clone.hideFlags = HideFlags.HideAndDontSave;
            clone.cachedName = name;
            return clone;
        }
        public void Remember(Type type, string name)
        {
            var field = Field(type, name);
            var value = field.GetValue(null);
            restore.Add(() => field.SetValue(null, value));
        }
        public void Remember(Action action)
        {
            restore.Add(action);
        }
        public void Catalog(Type type)
        {
            foreach (var field in type.GetFields(Flags).Where(value => !value.IsLiteral))
            {
                object original = field.GetValue(null);
                var map = original as IDictionary;
                var list = original as IList;
                if (map != null)
                {
                    var entries = Entries(map);
                    restore.Add(() =>
                                {
                                    map.Clear();
                                    foreach (var pair in entries)
                                        map.Add(pair.Key, pair.Value);
                                });
                }
                else if (list != null && !(original is Array))
                {
                    var values = list.Cast<object>().ToArray();
                    restore.Add(() =>
                                {
                                    list.Clear();
                                    foreach (var value in values)
                                        list.Add(value);
                                });
                }
                else if (original != null && original.GetType().IsGenericType &&
                         original.GetType().GetGenericTypeDefinition() == typeof(Stack<>))
                {
                    var values = ((IEnumerable)original).Cast<object>().Reverse().ToArray();
                    restore.Add(() =>
                                {
                                    original.GetType().GetMethod("Clear").Invoke(original, null);
                                    foreach (var value in values)
                                        original.GetType().GetMethod("Push").Invoke(original, new[] { value });
                                });
                }
                if (!field.IsInitOnly)
                {
                    restore.Add(() => field.SetValue(null, original));
                    if (original is Array)
                        field.SetValue(null, ((Array)original).Clone());
                }
            }
        }
        public void Dispose()
        {
            try
            {
                for (int i = restore.Count - 1; i >= 0; i--)
                    restore[i]();
                restore.Clear();
            }
            finally
            {
                foreach (var asset in owned)
                    if (asset)
                        UnityEngine.Object.DestroyImmediate(asset);
                owned.Clear();
                foreach (var check in checkSources)
                    check();
                checkSources.Clear();
            }
        }
    }
    static T[] Family<T>(JObject manifest, string category)
        where T : UnityEngine.Object
    {
        // Reuse the composed provider/category policy, including original pack order.
        var groups = WholeCatalogComposed.FamilyLocationGroups(manifest, category);
        var locations = manifest["locations"].ToDictionary(row => (int)row["id"]);
        return groups
            .SelectMany(group =>
                        {
                            var collection = new NamedAssetCollection<T>(value => ((UnityEngine.Object)value).name);
                            collection.Add(group
                                               .Select(id =>
                                                       {
                                                           var row = locations[id];
                                                           Check(typeof(T).IsAssignableFrom(Type.GetType((string)row["type"], true)),
                                                                 "Host source category type differs");
                                                           var asset = AssetDatabase.LoadAssetAtPath<T>((string)row["path"]);
                                                           Check(asset, "Host source asset absent: " + row["path"]);
                                                           return asset;
                                                       })
                                               .ToArray());
                            return collection.ToArray();
                        })
            .Distinct()
            .ToArray();
    }
    public static object Run(string directory)
    {
        Check(!EditorApplication.isPlayingOrWillChangePlaymode && !EditorApplication.isCompiling && !EditorApplication.isUpdating &&
                  !BuildPipeline.isBuildingPlayer,
              "Require idle editor");
        string work = Directory.GetParent(Application.dataPath).Parent.FullName,
               allowed = Path.Combine(work, "experiments/whole-catalog/gameplay") + Path.DirectorySeparatorChar;
        directory = Path.GetFullPath(directory);
        Check(directory.StartsWith(allowed, StringComparison.Ordinal) && !Directory.Exists(directory),
              "Require a new ignored progression fixture directory");
        Check(BodyCatalog.bodyCount == 0 && ItemCatalog.itemCount == 0 && EquipmentCatalog.equipmentCount == 0 &&
                  ArtifactCatalog.artifactCount == 0 && SurvivorCatalog.survivorCount == 0,
              "Host fixture would replace live catalogs");
        var recipe = JObject.Parse(File.ReadAllText(Path.Combine(work, "whole-catalog-build.json")));
        var manifest = JObject.Parse(File.ReadAllText((string)recipe["manifest"]));
        using (var fixture = new Fixture()) using (var owner = new AndroidProgressionBoundary())
        {
            foreach (var type in new[] { typeof(ItemCatalog), typeof(EquipmentCatalog), typeof(ArtifactCatalog), typeof(BodyCatalog),
                                         typeof(SurvivorCatalog), typeof(PickupCatalog) })
                fixture.Catalog(type);
            fixture.Remember(typeof(ContentManager), "_itemDefs");
            fixture.Remember(typeof(StatSheet), "fieldsTemplate");
            fixture.Remember(typeof(StatSheet), "nonDefaultFieldsBuffer");
            fixture.Remember(typeof(XmlUtility), "ValueReplacements");
            var oldDefault = UserProfile.defaultProfile;
            fixture.Remember(() => UserProfile.defaultProfile = oldDefault);
            var viewRoot = (ViewablesCatalog.Node)Field(typeof(ViewablesCatalog), "rootNode").GetValue(null);
            var oldNodes = viewRoot.children.ToArray();
            var viewMap = (IDictionary)Field(typeof(ViewablesCatalog), "fullNameToNodeMap").GetValue(null);
            var oldMap = Entries(viewMap);
            fixture.Remember(() =>
                             {
                                 foreach (var node in viewRoot.children.ToArray())
                                     if (!oldNodes.Contains(node))
                                         node.SetParent(null);
                                 viewMap.Clear();
                                 foreach (var pair in oldMap)
                                     viewMap.Add(pair.Key, pair.Value);
                             });
            var items = Family<ItemDef>(manifest, AddressablesLabels.itemDef);
            var equipment = Family<EquipmentDef>(manifest, AddressablesLabels.equipmentDef);
            var artifacts = Family<ArtifactDef>(manifest, AddressablesLabels.artifactDef);
            var survivors = Family<SurvivorDef>(manifest, AddressablesLabels.survivorDef).Select(fixture.Survivor).ToArray();
            var bodies =
                Family<GameObject>(manifest, AddressablesLabels.characterBody).OrderBy(body => body.name, StringComparer.Ordinal).ToArray();
            var unlocks = Family<UnlockableDef>(manifest, AddressablesLabels.unlockableDef);
            // Native index getters attempt repair and log errors before registration.
            var itemIndexField = typeof(ItemDef).GetField("_itemIndex", BindingFlags.Instance | BindingFlags.NonPublic);
            var equipmentIndexField = typeof(EquipmentDef).GetField("_equipmentIndex", BindingFlags.Instance | BindingFlags.NonPublic);
            Check(itemIndexField != null && equipmentIndexField != null, "Original index backing fields absent");
            foreach (var def in items)
            {
                var index = itemIndexField.GetValue(def);
                fixture.Remember(() => itemIndexField.SetValue(def, index));
            }
            foreach (var def in equipment)
            {
                var index = equipmentIndexField.GetValue(def);
                fixture.Remember(() => equipmentIndexField.SetValue(def, index));
            }
            foreach (var def in artifacts)
            {
                var index = def.artifactIndex;
                fixture.Remember(() => def.artifactIndex = index);
            }
            // Survivor cachedName writes Unity Object.name and dirties assets even when
            // restoring the same value. Native registration uses transient owned clones;
            // their original body/unlock references are retained without asset mutation.
            // BodyCatalog's native setter queues asynchronous portrait loads. This purely
            // synchronous metadata fixture supplies only its source body/skill inputs;
            // native live body initialization remains covered by the composed game.
            for (int i = 0; i < bodies.Length; i++)
            {
                var body = bodies[i].GetComponent<CharacterBody>();
                Check(body, "Source body component absent");
                var index = body.bodyIndex;
                fixture.Remember(() => body.bodyIndex = index);
                body.bodyIndex = (BodyIndex)i;
            }
            Set(typeof(BodyCatalog), "bodyPrefabs", bodies);
            Set(typeof(BodyCatalog), "bodyPrefabBodyComponents", bodies.Select(body => body.GetComponent<CharacterBody>()).ToArray());
            Set(typeof(BodyCatalog), "bodyNames", bodies.Select(body => body.name).ToArray());
            Set(typeof(BodyCatalog), "skillSlots", bodies.Select(body => body.GetComponents<GenericSkill>()).ToArray());
            Set(typeof(BodyCatalog), "<bodyCount>k__BackingField", bodies.Length);
            // ContentManager normally creates the empty item array before native registration.
            if (Field(typeof(ContentManager), "_itemDefs").GetValue(null) == null)
                Set(typeof(ContentManager), "_itemDefs", Array.Empty<ItemDef>());
            NativeSet(typeof(ItemCatalog), "SetItemDefs", items);
            NativeSet(typeof(EquipmentCatalog), "SetEquipmentDefs", equipment);
            NativeSet(typeof(ArtifactCatalog), "SetArtifactDefs", artifacts);
            NativeSet(typeof(SurvivorCatalog), "SetSurvivorDefs", survivors);
            PickupCatalog.SetEntries(
                items.Select(def => def.CreatePickupDef()).Concat(equipment.Select(def => def.CreatePickupDef())).ToArray());
            var routine = owner.Prepare(unlocks);
            try
            {
                while (routine.MoveNext())
                    Check(routine.Current == null, "Unexpected asynchronous native metadata dependency");
            }
            finally
            {
                (routine as IDisposable)?.Dispose();
            }
            var stats = StatDef.allStatDefs.Select(def => new StatField { statDef = def }).ToArray();
            Set(typeof(StatSheet), "fieldsTemplate", stats);
            Set(typeof(StatSheet), "nonDefaultFieldsBuffer", new bool[stats.Length]);
            var redirects =
                AssetDatabase.LoadAssetAtPath<UserProfileRedirectData>("Assets/WholeGame/RoR2/Base/Core/UserProfileRedirects.asset");
            Check(redirects, "Source redirect data absent");
            Set(typeof(XmlUtility), "ValueReplacements", redirects);
            if (UserProfile.saveFields == null)
                UserProfile.GenerateSaveFieldFunctions();
            UserProfile.LoadDefaultProfile();
            var empty = Clone(UserProfile.defaultProfile);
            var thresholds = Run(owner, empty);
            var persistence = CheckPersistence(owner, directory);
            var discovery = AndroidDiscoveryHost.Run(owner, empty, Path.Combine(directory, "discovery"));
            return new { success = true,
                         thresholds,
                         persistence,
                         discovery,
                         bodies = bodies.Length,
                         items = items.Length,
                         equipment = equipment.Length,
                         artifacts = artifacts.Length,
                         survivors = survivors.Length,
                         unlockables = owner.unlockables,
                         duplicateNames = owner.duplicateUnlockNames,
                         achievements = owner.achievements,
                         fixtureStatFields = stats.Length,
                         syntheticHostDataOnly = true,
                         sourceSurvivorAssetsUnchanged = true,
                         bodyPortraitInitializationTested = false };
        }
    }
    public static object Run(AndroidProgressionBoundary owner, UserProfile emptyFixture)
    {
        Check(!EditorApplication.isPlaying && !EditorApplication.isCompiling && owner != null && owner.ready,
              "Require idle editor and owned original progression metadata");
        owner.ValidateProfile(emptyFixture);
        var saved = (ICollection) typeof(UserProfile)
                        .GetField("achievementsList", BindingFlags.Instance | BindingFlags.NonPublic)
                        .GetValue(emptyFixture);
        Check(!emptyFixture.canSave && emptyFixture.statSheet.GetUnlockableCount() == 0 && saved.Count == 0,
              "Require an unsaveable empty host fixture");
        string unchanged = UserProfile.ToXml(emptyFixture).ToString();
        var rows = new List<object>();
        int prerequisites = 0;
        foreach (var definition in owner.persistentStatDefinitions)
        {
            var stat = AndroidProgressionBoundary.GetPersistentStat(definition);
            ulong threshold = AndroidProgressionBoundary.GetPersistentRequirement(definition);
            Check(threshold > 0, "Zero native threshold needs review");
            var below = Clone(emptyFixture);
            below.statSheet.SetStatValueFromString(stat, (threshold - 1).ToString(CultureInfo.InvariantCulture));
            var at = Clone(emptyFixture);
            at.statSheet.SetStatValueFromString(stat, threshold.ToString(CultureInfo.InvariantCulture));
            var low = owner.InspectPersistentStatCandidate(below, definition);
            var high = owner.InspectPersistentStatCandidate(at, definition);
            Check(string.IsNullOrEmpty(low.blocked) && string.IsNullOrEmpty(high.blocked) && !low.wouldGrant && high.wouldGrant &&
                      at.statSheet.GetUnlockableCount() == 0 && !at.HasAchievement(definition.identifier),
                  "Native threshold boundary differs: " + definition.identifier);
            if (!string.IsNullOrEmpty(definition.prerequisiteAchievementIdentifier))
            {
                Check(!at.CanSeeAchievement(definition.identifier), "Native prerequisite visibility differs");
                prerequisites++;
            }
            var eligible = owner.InspectPersistentStatCandidate(at).Where(value => value.wouldGrant).ToArray();
            uint reward = checked((uint)eligible.Sum(value => (long)value.lunarReward));
            var grant = owner.ApplyPersistentStatCandidate(at);
            Check(grant.awarded.Contains(definition.identifier) && grant.awarded.Length == eligible.Length && at.coins == reward &&
                      at.totalCollectedCoins == reward && at.onStatsReceived == null && PlatformSystems.activityManager == null,
                  "Native local award/currency differs");
            foreach (var row in eligible)
            {
                var def = UnlockableCatalog.GetUnlockableDef(row.reward);
                AndroidProgressionBoundary.RequireDefinition(def);
                Check(at.HasAchievement(row.identifier) && at.statSheet.HasUnlockable(def), "Native unlock reward missing");
            }
            string awarded = UserProfile.ToXml(at).ToString();
            Check(owner.ApplyPersistentStatCandidate(at).awarded.Length == 0 && UserProfile.ToXml(at).ToString() == awarded,
                  "Native local award duplicated");
            rows.Add(new { identifier = definition.identifier, stat = stat.name, requirement = threshold, belowGrants = low.wouldGrant,
                           atGrants = high.wouldGrant, awarded = grant.awarded, lunarReward = reward });
        }
        var target = owner.persistentStatDefinitions.Single(value => value.identifier == "Die5Times");
        var denied = Clone(emptyFixture);
        denied.statSheet.SetStatValueFromString(AndroidProgressionBoundary.GetPersistentStat(target), "5");
        var rewardDef = UnlockableCatalog.GetUnlockableDef(target.unlockableRewardIdentifier);
        var expansions = (IDictionary)Field(typeof(UnlockableCatalog), "unlockableToExpansionTable").GetValue(null);
        bool had = expansions.Contains(rewardDef.index);
        object old = expansions[rewardDef.index];
        var entitlement = ScriptableObject.CreateInstance<EntitlementDef>();
        var expansion = ScriptableObject.CreateInstance<ExpansionDef>();
        expansion.requiredEntitlement = entitlement;
        try
        {
            expansions[rewardDef.index] = expansion;
            var report = owner.ApplyPersistentStatCandidate(denied);
            Check(report.awarded.Length == 0 && report.observations.Single(row => row.identifier == target.identifier).blocked != null &&
                      denied.coins == 0 && denied.statSheet.GetUnlockableCount() == 0,
                  "Missing entitlement was bypassed");
        }
        finally
        {
            if (had)
                expansions[rewardDef.index] = old;
            else
                expansions.Remove(rewardDef.index);
            UnityEngine.Object.DestroyImmediate(expansion);
            UnityEngine.Object.DestroyImmediate(entitlement);
        }
        var saturated = Clone(emptyFixture);
        saturated.coins = uint.MaxValue;
        saturated.totalCollectedCoins = uint.MaxValue;
        saturated.statSheet.SetStatValueFromString(StatDef.totalDeaths, "5");
        Check(owner.ApplyPersistentStatCandidate(saturated).awarded.Length == 1 && saturated.coins == uint.MaxValue &&
                  saturated.totalCollectedCoins == uint.MaxValue,
              "Native currency saturation differs");
        bool nullRejected = false, noneRejected = false;
        try
        {
            AndroidProgressionBoundary.RequireDefinition(null);
        }
        catch (InvalidOperationException)
        {
            nullRejected = true;
        }
        var invalid = ScriptableObject.CreateInstance<UnlockableDef>();
        try
        {
            invalid.index = UnlockableIndex.None;
            try
            {
                AndroidProgressionBoundary.RequireDefinition(invalid);
            }
            catch (InvalidOperationException)
            {
                noneRejected = true;
            }
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(invalid);
        }
        Check(nullRejected && noneRejected && UserProfile.ToXml(emptyFixture).ToString() == unchanged &&
                  LocalUserManager.readOnlyLocalUsersList.Count == 0 && PlatformSystems.activityManager == null,
              "Host fixture changed source profile or retained platform context");
        return new { success = true,
                     nativeThresholds = rows.Count,
                     checks = rows,
                     prerequisiteVisibilityCases = prerequisites,
                     entitlementRejected = true,
                     nullAndNoneRejected = true,
                     currencySaturated = true,
                     awardsDeduplicated = true,
                     callbacksReleased = true,
                     originalMetadata = true,
                     sourceProfileUnchanged = true,
                     externalServicesUnavailable = true,
                     deviceProgressAwarded = false };
    }
    static object CheckPersistence(AndroidProgressionBoundary owner, string directory)
    {
        int callbacks = 0;
        Action<UserProfile> progression = profile =>
        {
            callbacks++;
            owner.ApplyPersistentStatCandidate(profile);
        };
        var baseline = Guid.NewGuid();
        var id = Guid.NewGuid();
        var store = new AndroidOfflineProfile(directory, new[] { baseline }, progression);
        var delta = StatSheet.New();
        delta.PushStatValue(StatDef.totalDeaths, 5UL);
        Check(callbacks == 0 && !store.ApplyResult(baseline, delta) && callbacks == 0, "Historical/initial load awarded progression");
        Check(store.ApplyResult(id, delta) && !store.ApplyResult(id, delta) && callbacks == 1, "Award transaction deduplication differs");
        var reward = UnlockableCatalog.GetUnlockableDef("Items.Bear");
        AndroidProgressionBoundary.RequireDefinition(reward);
        Check(store.profile.HasAchievement("Die5Times") && store.profile.statSheet.HasUnlockable(reward) && store.profile.coins == 1 &&
                  store.profile.totalCollectedCoins == 1,
              "Native awarded transaction incomplete");
        var loaded = new AndroidOfflineProfile(directory, null, progression);
        Check(callbacks == 1 && loaded.profile.HasAchievement("Die5Times") && loaded.profile.statSheet.HasUnlockable(reward) &&
                  loaded.profile.coins == 1 && !loaded.ApplyResult(id, delta) && callbacks == 1,
              "Earned profile cold reload differs");
        string path = Path.Combine(directory, "profile.json"), accepted = File.ReadAllText(path);
        File.WriteAllText(path, "interrupted host reward generation");
        var replay = new AndroidOfflineProfile(directory, null, progression);
        Check(replay.recovery == "validated-backup" && replay.ShouldApply(id) && replay.ApplyResult(id, delta) &&
                  !replay.ApplyResult(id, delta) && callbacks == 2 && File.ReadAllText(path) == accepted,
              "Native earned reward replay differs");
        return new { success = true,    allRewardFieldsAtomic = true, baselineSkipped = true, resultDeduplicated = true,
                     coldReload = true, backupReplayExact = true };
    }
}
