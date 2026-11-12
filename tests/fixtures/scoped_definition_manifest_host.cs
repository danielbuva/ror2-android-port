using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using Newtonsoft.Json.Linq;
using UnityEngine;
using RoR2;
using UnityEngine.ResourceManagement.ResourceLocations;
using Object = UnityEngine.Object;
namespace UnityEngine
{
    public class Object { public string name; public static implicit operator bool(Object value) { return value != null; } }
    public class GameObject : Object
    {
        public RoR2.CharacterBody body = new RoR2.CharacterBody();
        public T GetComponent<T>() where T : Object { return body as T; }
    }
    public static class Application { public static string persistentDataPath = "."; }
    public class AssetBundle : Object
    {
        public static AssetBundle owner = new AssetBundle { name = "source" };
        public static Dictionary<string, Object> assets = new Dictionary<string, Object>();
        public static AssetBundle[] loadedOwners;
        public static int enumerations;
        public static Action<string> onLoad;
        public static AssetBundle[] GetAllLoadedAssetBundles() { enumerations++; return loadedOwners ?? new[] { owner }; }
        public static int typedLoads;
        public T LoadAsset<T>(string path) where T : Object { typedLoads++; onLoad?.Invoke(path); return (T)assets[path]; }
        public T[] LoadAllAssets<T>() where T : Object { throw new Exception("Unrelated drop table activated before native Run setup"); }
    }
}
namespace UnityEngine.ResourceManagement.ResourceLocations { public interface IResourceLocator {} }
namespace RoR2 { public class CharacterBody : Object {} public class BuffDef : Object {} public class ItemDef : Object {} public class KeyItemDef : Object {} public class ItemGroupType : Object {} public class ItemGroupProvider : Object {} public class SurvivorDef : Object {} public class UnlockableDef : Object {} }
namespace RoR2.ContentManagement
{
    public static class AddressablesLabels { public const string survivorDef = "survivors", unlockableDef = "unlockables", keyItemDef = "KeyItemDef", itemGroupType = "ItemGroupType", itemGroupProvider = "ItemGroupProvider"; }
    public class ContentPack { public bool allowed; }
    public class AddressablesLoadHelper
    {
        public AddressablesLoadHelper(IResourceLocator[] unused) {}
        public bool CanLoadType(string category, ContentPack pack) { return pack.allowed; }
    }
    public class NamedAssetCollection<T>
    {
        readonly List<T> values = new List<T>();
        public NamedAssetCollection(Func<T, string> getName) {}
        public void Add(T[] assets) { values.AddRange(assets); }
        public T[] ToArray() { return values.ToArray(); }
    }
    public class TargetAssetNameAttribute : Attribute { public string targetAssetName; }
    public static class ContentLoadHelper
    {
        public static void PopulateTypeFields<T>(Type holder, NamedAssetCollection<T> values, Func<T, RoR2.CharacterBody> convert)
            where T : Object
        {
            foreach (var field in holder.GetFields(BindingFlags.Public | BindingFlags.Static))
                field.SetValue(null, convert(values.ToArray().Single(value => value.name == field.Name)));
        }
        public static void PopulateTypeFields<T>(Type holder, NamedAssetCollection<T> values, Func<string, string> convert)
            where T : Object
        {
            foreach (var field in holder.GetFields(BindingFlags.Public | BindingFlags.Static))
                field.SetValue(null, values.ToArray().Single(value => value.name == convert(field.Name)));
        }
    }
}
public class Definition : Object {}
public class SourceProvider
{
    public static bool allowed = true;
    public static int constructions;
    public SourceProvider() { constructions++; }
    readonly RoR2.ContentManagement.ContentPack contentPack = new RoR2.ContentManagement.ContentPack { allowed = allowed };
    public class ItemRelationshipTypes { public static Definition Related; }
    public class BodyPrefabs { public static RoR2.CharacterBody Player; }
}
public class ExcludedProvider
{
    readonly RoR2.ContentManagement.ContentPack contentPack = new RoR2.ContentManagement.ContentPack { allowed = false };
}
public static partial class WholeCatalogComposed
{
    static AssetBundle owned = AssetBundle.owner;
    static WeakReference definitionManifest;
    static readonly Dictionary<string, Object[]> definitionFamilies = new Dictionary<string, Object[]>();
    static readonly Dictionary<FieldInfo, object> priorDefinitionFields = new Dictionary<FieldInfo, object>();
    static void Check(bool value) { if (!value) throw new Exception("Scoped manifest contract differs"); }
    public static void Main(string[] args)
    {
        Directory.CreateDirectory("payload");
        ManifestParseContract();
        ManifestWeakCacheContract();
        ManifestIndexContract();
        var type = new Definition { name = "Related" };
        var provider = new Definition { name = "Provider" };
        var player = new GameObject { name = "Player" };
        AssetBundle.assets.Add("type", type);
        AssetBundle.assets.Add("provider", provider);
        var data = new JObject {
            ["providers"] = new JArray(new JObject { ["type"] = "SourceProvider", ["identifier"] = "source" },
                                       new JObject { ["type"] = "ExcludedProvider", ["identifier"] = "excluded" }),
            ["locations"] = new JArray(new JObject { ["id"] = 1, ["type"] = "Definition", ["bundle"] = "source", ["path"] = "type" },
                                       new JObject { ["id"] = 2, ["type"] = "Definition", ["bundle"] = "source", ["path"] = "provider" }),
            ["keys"] = new JArray(new JObject { ["key"] = "ContentPack:source", ["locations"] = new JArray(1, 2) },
                                  new JObject { ["key"] = "types", ["locations"] = new JArray(1) },
                                  new JObject { ["key"] = "providers", ["locations"] = new JArray(2) }) };
        WriteManifest(data.ToString());
        var survivor = new RoR2.SurvivorDef { name = "Commando" };
        var unlockable = new RoR2.UnlockableDef { name = "Earned" };
        AssetBundle.assets.Add("survivor", survivor);
        AssetBundle.assets.Add("unlockable", unlockable);
        ((JArray)data["locations"]).Add(new JObject { ["id"] = 3, ["type"] = "RoR2.SurvivorDef", ["bundle"] = "source", ["path"] = "survivor" });
        ((JArray)data["locations"]).Add(new JObject { ["id"] = 4, ["type"] = "RoR2.UnlockableDef", ["bundle"] = "source", ["path"] = "unlockable" });
        ((JArray)data["keys"]).Add(new JObject { ["key"] = "survivors", ["locations"] = new JArray(3) });
        ((JArray)data["keys"]).Add(new JObject { ["key"] = "unlockables", ["locations"] = new JArray(4) });
        ((JArray)data["keys"][0]["locations"]).Add(3);
        ((JArray)data["keys"][0]["locations"]).Add(4);
        WriteManifest(data.ToString());
        var snapshot = ReadDefinitionManifest();
        File.Delete("payload/whole-catalog.json"); // All three operations must use the supplied snapshot.
        var profile = new ProfileScope();
        profile.Run(snapshot);
        Check(ReferenceEquals(profile.ruleManifest, snapshot));
        Check(ReferenceEquals(profile.survivors.Single(), survivor) && ReferenceEquals(profile.unlockables.Single(), unlockable));
        Check(profile.trace.Where(value => !value.Contains("assets-costs ")).SequenceEqual(new[] {
            "profile-survivor-family-manifest-begin", "profile-survivor-family-manifest-ready-index-begin",
            "profile-survivor-family-index-ready-assets-begin", "profile-survivor-family-assets-ready",
            "profile-unlockable-family-manifest-begin", "profile-unlockable-family-manifest-ready-index-begin",
            "profile-unlockable-family-index-ready-assets-begin", "profile-unlockable-family-assets-ready" }));
        profile.trace.Clear();
        profile.Run(null); // Warm families use no file and emit no trace.
        Check(profile.trace.Count == 0);
        definitionFamilies.Clear();
        WriteManifest(data.ToString());
        profile.Run(null); // Cold fallback remains supported.
        Check(ReferenceEquals(profile.survivors.Single(), survivor) && ReferenceEquals(profile.unlockables.Single(), unlockable));
        File.Delete("payload/whole-catalog.json");
        var trace = new List<string>();
        var types = CategoryFamily(snapshot, "types", new[] { type }, trace.Add);
        Check(trace.Where(value => !value.StartsWith("assets-costs ")).SequenceEqual(new[] { "manifest-begin", "manifest-ready-index-begin", "index-ready-assets-begin", "assets-ready" }));
        CheckCosts(trace, 1, 1);
        var providers = CategoryFamily(snapshot, "providers", new[] { provider });
        PopulateDefinitionFields(snapshot, "ItemRelationshipTypes", types);
        PopulateBodyFields(snapshot, new[] { player });
        Check(ReferenceEquals(SourceProvider.BodyPrefabs.Player, player.body));
        bool foreignBodyRejected = false;
        try { PopulateBodyFields(snapshot, new[] { new GameObject { name = "Player" } }); }
        catch (Exception) { foreignBodyRejected = true; }
        Check(foreignBodyRejected);
        bool missingBodyRejected = false;
        try { PopulateBodyFields(snapshot, new GameObject[0]); }
        catch (Exception) { missingBodyRejected = true; }
        Check(missingBodyRejected);
        Check(ReferenceEquals(types.Single(), type) && ReferenceEquals(providers.Single(), provider));
        Check(ReferenceEquals(SourceProvider.ItemRelationshipTypes.Related, type));
        // A public cache hit keeps membership validation and needs no parse.
        Check(ReferenceEquals(CategoryFamily("types", new[] { type }).Single(), type));
        trace.Clear();
        Check(ReferenceEquals(CategoryFamily<Definition>(null, "types", new[] { type }, trace.Add).Single(), type));
        Check(trace.Count == 0);
        bool rejected = false;
        try { CategoryFamily(snapshot, "types", new[] { provider }); } catch (Exception) { rejected = true; }
        Check(rejected);
        // Existing teardown can restore the holder; no scope creates another owner.
        foreach (var prior in priorDefinitionFields) prior.Key.SetValue(null, prior.Value);
        priorDefinitionFields.Clear();
        definitionFamilies.Clear();
        Check(SourceProvider.ItemRelationshipTypes.Related == null);
        Check(SourceProvider.BodyPrefabs.Player == null);
        data["locations"][0]["path"] = "provider";
        WriteManifest(data.ToString());
        Check(ReferenceEquals(CategoryFamily("types", new[] { provider }).Single(), provider));
        DefinitionFamilyContract<RoR2.BuffDef>(BuffDefinitions);
        DefinitionFamilyContract<RoR2.ItemDef>(ItemDefinitions);
        LabeledFamilyContract<RoR2.KeyItemDef>(KeyItemDefinitions, "KeyItemDef");
        LabeledFamilyContract<RoR2.ItemGroupType>(ItemGroupTypes, "ItemGroupType", ItemGroupTypes);
        LabeledFamilyContract<RoR2.ItemGroupProvider>(ItemGroupProviders, "ItemGroupProvider", ItemGroupProviders);
        CategoryBundleContract();
        Console.WriteLine("scope identity policy restoration buffs items PASS");
    }
    static void CheckCosts(List<string> trace, int rows, int bundles)
    {
        var values = trace.Single(value => value.StartsWith("assets-costs ")).Split(' ').Skip(1)
                          .Select(value => value.Split('='))
                          .ToDictionary(value => value[0], value => long.Parse(value[1]));
        Check(values["rows"] == rows && values["bundles"] == bundles && values["frequency"] > 0);
        Check(values["typeTicks"] >= 0 && values["ownerTicks"] >= 0 && values["loadTicks"] >= 0 && values["collectionTicks"] >= 0);
        Check(values["totalTicks"] == values["typeTicks"] + values["ownerTicks"] + values["loadTicks"] + values["collectionTicks"]);
    }
    static void CategoryBundleContract()
    {
        var first = new Definition { name = "First" };
        var second = new Definition { name = "Second" };
        AssetBundle.assets["first"] = first;
        AssetBundle.assets["second"] = second;
        var data = new JObject {
            ["providers"] = new JArray(new JObject { ["type"] = "SourceProvider", ["identifier"] = "source" }),
            ["locations"] = new JArray(
                new JObject { ["id"] = 1, ["type"] = "Definition", ["bundle"] = "source", ["path"] = "first" },
                new JObject { ["id"] = 2, ["type"] = "Definition", ["bundle"] = "source", ["path"] = "second" }),
            ["keys"] = new JArray(new JObject { ["key"] = "ContentPack:source", ["locations"] = new JArray(1, 2) },
                                  new JObject { ["key"] = "category", ["locations"] = new JArray(1, 2) }) };
        var unrelated = new AssetBundle { name = "unrelated" };
        AssetBundle.loadedOwners = new[] { AssetBundle.owner, unrelated, unrelated };
        definitionFamilies.Clear();
        int before = AssetBundle.enumerations;
        int loads = AssetBundle.typedLoads;
        var unobserved = CategoryFamily(data, "category", new[] { second });
        Check(unobserved.SequenceEqual(new[] { first, second }));
        Check(AssetBundle.enumerations == before + 1 && AssetBundle.typedLoads == loads + 2);
        definitionFamilies.Clear();
        var trace = new List<string>();
        Check(CategoryFamily(data, "category", new[] { second }, trace.Add).SequenceEqual(unobserved));
        CheckCosts(trace, 2, 1);
        Check(AssetBundle.enumerations == before + 2 && AssetBundle.typedLoads == loads + 4);
        trace.Clear();
        Check(CategoryFamily(data, "category", new[] { first }, trace.Add).SequenceEqual(unobserved));
        Check(trace.Count == 0 && AssetBundle.enumerations == before + 2 && AssetBundle.typedLoads == loads + 4);
        definitionFamilies.Clear();
        AssetBundle.loadedOwners = new[] { AssetBundle.owner, AssetBundle.owner };
        Refuses(() => CategoryFamily(data, "category", new Definition[0]));
        AssetBundle.loadedOwners = new[] { unrelated };
        Refuses(() => CategoryFamily(data, "category", new Definition[0]));
        // First-use resolution preserves a later owner loaded by an asset callback.
        AssetBundle.loadedOwners = new[] { AssetBundle.owner };
        var later = new AssetBundle { name = "later" };
        data["locations"][1]["bundle"] = "later";
        AssetBundle.onLoad = path => { if (path == "first") AssetBundle.loadedOwners = new[] { AssetBundle.owner, later }; };
        before = AssetBundle.enumerations;
        Check(CategoryFamily(data, "category", new Definition[0]).SequenceEqual(new[] { first, second }));
        Check(AssetBundle.enumerations == before + 2);
        AssetBundle.onLoad = null;
        AssetBundle.loadedOwners = null;
        definitionFamilies.Clear();
    }
    static void LabeledFamilyContract<T>(Func<T[]> definitions, string label, Func<Action<string>, T[]> observed = null) where T : Object, new()
    {
        definitionFamilies.Clear();
        var first = new T { name = "First" };
        var second = new T { name = "Second" };
        AssetBundle.assets["first-key"] = first;
        AssetBundle.assets["second-key"] = second;
        var data = new JObject {
            ["providers"] = new JArray(new JObject { ["type"] = "SourceProvider", ["identifier"] = "source" }),
            ["locations"] = new JArray(
                new JObject { ["id"] = 1, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "first-key" },
                new JObject { ["id"] = 2, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "second-key" },
                new JObject { ["id"] = 3, ["type"] = "Definition", ["bundle"] = "source", ["path"] = "unrelated-drop-table" }),
            ["keys"] = new JArray(
                new JObject { ["key"] = "ContentPack:source", ["locations"] = new JArray(1, 2, 3) },
                new JObject { ["key"] = label, ["locations"] = new JArray(1, 2) }) };
        WriteManifest(data.ToString());
        int before = AssetBundle.typedLoads;
        Check(definitions().SequenceEqual(new[] { first, second }));
        Check(AssetBundle.typedLoads == before + 2);
        if (observed != null)
        {
            var trace = new List<string>();
            Check(observed(trace.Add).SequenceEqual(new[] { first, second }) && trace.Count == 0);
            definitionFamilies.Clear();
            Check(observed(trace.Add).SequenceEqual(new[] { first, second }));
            Check(trace.Where(value => !value.StartsWith("assets-costs ")).SequenceEqual(new[] {
                "manifest-begin", "manifest-ready-index-begin", "index-ready-assets-begin", "assets-ready" }));
            CheckCosts(trace, 2, 1);
            before += 2;
        }
        File.Delete("payload/whole-catalog.json");
        Check(definitions().SequenceEqual(new[] { first, second }));
        Check(AssetBundle.typedLoads == before + 2);
        definitionFamilies.Clear(); // A later catalog generation must reload its own definitions.
        WriteManifest(data.ToString());
        AssetBundle.assets["second-key"] = null;
        Refuses(() => definitions());
        AssetBundle.assets["second-key"] = second;
        definitionFamilies.Clear();
    }
    static void ManifestParseContract()
    {
        const string source = @"{
            /* same default comment handling */
            ""nested"": { ""z"": [null, true, false, 42, -2.5e3, ""2026-11-04T12:30:00Z""],
                            ""a"": ""\u03bb\uD83D\uDE80"" },
            ""duplicate"": 1, ""after"": {}, ""duplicate"": 2
        } // trailing comment";
        WriteManifest(source);
        var expected = JObject.Parse(source);
        var actual = ReadDefinitionManifest();
        Check(JToken.DeepEquals(expected, actual));
        var expectedTokens = expected.DescendantsAndSelf().ToArray();
        var actualTokens = actual.DescendantsAndSelf().ToArray();
        Check(expectedTokens.Select(token => token.Type).SequenceEqual(actualTokens.Select(token => token.Type)));
        Check(expectedTokens.Select(token => token.Path).SequenceEqual(actualTokens.Select(token => token.Path)));
        Check(expectedTokens.OfType<JProperty>().Select(property => property.Name)
            .SequenceEqual(actualTokens.OfType<JProperty>().Select(property => property.Name)));
        Check(expectedTokens.Any(token => ((Newtonsoft.Json.IJsonLineInfo)token).HasLineInfo()));
        Check(actualTokens.All(token => !((Newtonsoft.Json.IJsonLineInfo)token).HasLineInfo()));
        foreach (string invalid in new[] { "{\"unfinished\":", "{\"items\":[1,}", "{} {}", "{} trailing" })
        {
            WriteManifest(invalid);
            foreach (Func<JObject> parse in new Func<JObject>[] { () => JObject.Parse(invalid), ReadDefinitionManifest })
            {
                bool refused = false;
                try { parse(); } catch (Newtonsoft.Json.JsonReaderException) { refused = true; }
                Check(refused);
            }
        }
    }
    static void WriteManifest(string content)
    {
        ResetDefinitionManifest();
        File.WriteAllText("payload/whole-catalog.json", content);
    }
    static void ManifestIndexContract()
    {
        var data = new JObject {
            ["providers"] = new JArray(new JObject { ["type"] = "SourceProvider", ["identifier"] = "source" },
                                       new JObject { ["type"] = "ExcludedProvider", ["identifier"] = "excluded" }),
            ["locations"] = new JArray(new JObject { ["id"] = 1 }, new JObject { ["id"] = 2 }),
            ["keys"] = new JArray(new JObject { ["key"] = "ContentPack:source", ["locations"] = new JArray(2, 1, 2) },
                                  new JObject { ["key"] = "category", ["locations"] = new JArray(1, 2) },
                                  new JObject { ["key"] = "category", ["keyType"] = "System.Int32", ["locations"] = new JArray(99) }) };
        WriteManifest(data.ToString());
        var snapshot = ReadDefinitionManifest();
        var index = IndexDefinitionManifest(snapshot);
        Check(ReferenceEquals(index, IndexDefinitionManifest(snapshot)));
        Check(ReferenceEquals(index.Keys(snapshot), IndexDefinitionManifest(snapshot).Keys(snapshot)));
        Check(ReferenceEquals(index.Locations(snapshot), IndexDefinitionManifest(snapshot).Locations(snapshot)));
        int before = SourceProvider.constructions;
        var groups = FamilyLocationGroups(snapshot, "category");
        Check(groups.Length == 2 && groups[0].SequenceEqual(new[] { 2, 1 }) && groups[1].Length == 0);
        SourceProvider.allowed = false;
        Check(FamilyLocationGroups(snapshot, "category").All(group => group.Length == 0));
        Check(SourceProvider.constructions == before + 2);
        SourceProvider.allowed = true;
        ResetDefinitionManifest();
        Check(snapshot.Annotation<DefinitionManifestIndex>() == null);
        Check(!ReferenceEquals(index, IndexDefinitionManifest(snapshot)));
        // Mutable callers keep fresh key/ID validation and original failure order.
        Check(!ReferenceEquals(IndexDefinitionManifest(data), IndexDefinitionManifest(data)));
        data["keys"][0]["locations"] = new JArray(1);
        Check(FamilyLocationGroups(data, "category")[0].SequenceEqual(new[] { 1 }));
        ((JArray)data["locations"]).Add(new JObject { ["id"] = 1 });
        Check(FamilyLocationGroups(data, "category")[0].SequenceEqual(new[] { 1 }));
        Refuses(() => IndexDefinitionManifest(data).Locations(data));
        ((JArray)data["keys"]).Add(new JObject { ["key"] = "category", ["locations"] = new JArray(1) });
        Refuses(() => FamilyLocationGroups(data, "category"));
        ((JArray)data["keys"]).RemoveAt(3);
        ((JArray)data["keys"]).RemoveAt(1);
        Refuses(() => FamilyLocationGroups(data, "category"));
    }
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    static WeakReference ReadLiveSnapshot()
    {
        var first = ReadDefinitionManifest();
        Check(ReferenceEquals(first, ReadDefinitionManifest()));
        var index = IndexDefinitionManifest(first);
        index.Keys(first);
        index.Locations(first);
        return new WeakReference(first);
    }
    static void ManifestWeakCacheContract()
    {
        WriteManifest("{\"generation\":1,\"keys\":[],\"locations\":[{\"id\":1}]}");
        var snapshot = ReadLiveSnapshot();
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
        Check(!snapshot.IsAlive);
        var first = ReadDefinitionManifest();
        Check((int)first["generation"] == 1);
        WriteManifest("{\"generation\":2}");
        var second = ReadDefinitionManifest();
        Check(!ReferenceEquals(first, second) && (int)second["generation"] == 2);
        WriteManifest("{\"unfinished\":");
        Refuses(() => ReadDefinitionManifest());
        WriteManifest("{}");
        Check(ReadDefinitionManifest().Count == 0);
        ResetDefinitionManifest();
    }
    static void Refuses(Action action)
    {
        bool refused = false;
        try { action(); } catch (Exception) { refused = true; }
        Check(refused);
    }
    static void DefinitionFamilyContract<T>(Func<T[]> definitions) where T : Object, new()
    {
        var first = new T { name = "First" };
        var second = new T { name = "Second" };
        var excluded = new T { name = "NotAProviderRoot" };
        AssetBundle.assets["first"] = first;
        AssetBundle.assets["second"] = second;
        AssetBundle.assets["excluded"] = excluded;
        var data = new JObject {
            ["provider_roots"] = new JArray(10, 11, 12),
            ["locations"] = new JArray(
                new JObject { ["id"] = 10, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "first" },
                new JObject { ["id"] = 11, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "second" },
                new JObject { ["id"] = 12, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "first" },
                new JObject { ["id"] = 13, ["type"] = typeof(T).FullName, ["bundle"] = "source", ["path"] = "excluded" }) };
        definitionFamilies.Clear();
        WriteManifest(data.ToString());
        int before = AssetBundle.typedLoads;
        int ownerLookups = AssetBundle.enumerations;
        var buffs = definitions();
        Check(buffs.Length == 2 && ReferenceEquals(buffs[0], first) && ReferenceEquals(buffs[1], second));
        Check(AssetBundle.typedLoads == before + 3); // Alias roots retain one native identity.
        Check(AssetBundle.enumerations == ownerLookups + 1);
        File.Delete("payload/whole-catalog.json");
        Check(definitions().SequenceEqual(buffs) && AssetBundle.typedLoads == before + 3);
        Check(DefinitionFamily(new[] { second }).SequenceEqual(buffs));
        Check(AssetBundle.enumerations == ownerLookups + 1);
        Refuses(() => DefinitionFamily(new[] { excluded }));
        var previousOwner = owned;
        owned = null;
        Refuses(() => definitions());
        owned = previousOwner;
        // Existing release clears this cache; replacement input must be read again.
        definitionFamilies.Clear();
        data["locations"][0]["path"] = "second";
        data["locations"][1]["path"] = "first";
        WriteManifest(data.ToString());
        Check(ReferenceEquals(definitions()[0], second));
        definitionFamilies.Clear();
        second.name = first.name;
        Refuses(() => definitions());
        second.name = "Second";
        AssetBundle.assets["second"] = null;
        Refuses(() => definitions());
        AssetBundle.assets["second"] = second;
        AssetBundle.owner.name = "other";
        Refuses(() => definitions());
        AssetBundle.owner.name = "source";
        AssetBundle.loadedOwners = new[] { AssetBundle.owner, new AssetBundle { name = "source" } };
        Refuses(() => definitions());
        AssetBundle.loadedOwners = null;
        data["provider_roots"] = new JArray();
        WriteManifest(data.ToString());
        Refuses(() => definitions());
        definitionFamilies.Clear();
    }

}

public partial class ProfileScope
{
    public JObject ruleManifest;
    ProfileScope coordinator { get { return this; } }
    void PrepareObjectiveRuleCatalog(JObject manifest) { ruleManifest = manifest; }
    public RoR2.SurvivorDef[] survivors;
    public RoR2.UnlockableDef[] unlockables;
    public readonly List<string> trace = new List<string>();
    ProfileScope GetAndroidProfileSession() { return this; }
    void TraceStartup(string step) { trace.Add(step); }
    public void Run(JObject manifest) { PrepareAndroidProfile(null, manifest); }
}
