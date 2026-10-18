// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup Prepare, ConfigureLocations; teardown Release.
using System;
using System.Collections;
using System.IO;
using System.Linq;
using UnityEngine;
using Newtonsoft.Json.Linq;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.ResourceProviders;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.Util;
using System.Collections.Generic;
using System.Reflection;

// The expanded build gives old assets a shared bundle owner. Keep that owner
// loaded before the existing composed game deserializes its body/support assets.
public static class WholeCatalogComposed
{
    static AssetBundle owned;
    static IResourceLocator[] priorLocators;
    static IResourceLocator ownedLocator;
    static HashSet<string> borrowedNames;
    static readonly List<WeakReference> releasedLocators = new List<WeakReference>();
    static readonly List<WeakReference> releasedManifests = new List<WeakReference>();
    static WeakReference currentManifest;
    static int lastDetachedAssetOperations;
    delegate bool ExtractSubObjectKey(object key, out string mainKey, out string subKey);
    static readonly ExtractSubObjectKey originalSubObjectKey = (ExtractSubObjectKey)Delegate.CreateDelegate(
        typeof(ExtractSubObjectKey),
        typeof(ResourceManagerConfig)
            .GetMethod("ExtractKeyAndSubKey", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic));
    public static T LoadOwnedContent<T>(string path)
        where T : UnityEngine.Object
    {
        if (!owned)
            throw new Exception("Shared whole-content owner is not active");
        var asset = owned.LoadAsset<T>(path);
        if (!asset)
            throw new Exception("Accepted shared content asset is missing: " + path);
        return asset;
    }
    sealed class BorrowedBundle : IAssetBundleResource
    {
        readonly string name;
        public BorrowedBundle(string value)
        {
            name = value;
        }
        public AssetBundle GetAssetBundle()
        {
            if (!owned || borrowedNames == null || !borrowedNames.Contains(name))
                throw new Exception("Borrowed bundle outlived its composed owner: " + name);
            var bundle = AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(value => value.name == name);
            if (!bundle)
                throw new Exception("Composed bundle owner released before its consumers: " + name);
            return bundle;
        }
    }
    sealed class BorrowedBundleProvider : ResourceProviderBase
    {
        public override Type GetDefaultType(IResourceLocation location)
        {
            return typeof(IAssetBundleResource);
        }
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                var resource = new BorrowedBundle(handle.Location.PrimaryKey);
                resource.GetAssetBundle();
                handle.Complete<IAssetBundleResource>(resource, true, null);
            }
            catch (Exception error)
            {
                handle.Complete<IAssetBundleResource>(null, false, error);
            }
        }
        // Existing manual/provider leases keep these bundles alive; this bridge owns none.
        public override void Release(IResourceLocation location, object asset)
        {
        }
    }
    sealed class BorrowedAssetProvider : ResourceProviderBase
    {
        static readonly HashSet<string> reportedFailures = new HashSet<string>(StringComparer.Ordinal);
        public static void ResetFailures()
        {
            lock (reportedFailures) reportedFailures.Clear();
        }
        // Match the shipped provider's broad request contract (including Object loads).
        public override Type GetDefaultType(IResourceLocation location)
        {
            return typeof(object);
        }
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                var dependencies = new List<object>();
                handle.GetDependencies(dependencies);
                var declared = handle.Location.Dependencies;
                if (declared == null || declared.Count == 0)
                    throw new Exception("Borrowed asset owner not declared");
                string owner = declared[0].PrimaryKey;
                var resource = dependencies.OfType<IAssetBundleResource>().SingleOrDefault(value => value.GetAssetBundle().name == owner);
                if (resource == null)
                    throw new Exception("Borrowed asset owner absent: " + owner);
                string path = handle.ResourceManager.TransformInternalId(handle.Location);
                if (handle.Type.IsArray)
                    throw new Exception("Unmeasured borrowed array contract: " + path);
                string mainKey, subKey;
                var bundle = resource.GetAssetBundle();
                // Match the shipped provider's exact subobject name/type selection.
                var asset =
                    originalSubObjectKey(path, out mainKey, out subKey)
                        ? bundle.LoadAssetWithSubAssets(mainKey, handle.Type)
                              .FirstOrDefault(value => value && value.name == subKey && handle.Type.IsAssignableFrom(value.GetType()))
                        : bundle.LoadAsset(path, handle.Type);
                if (!asset)
                    throw new Exception("Borrowed typed asset missing: " + path + " / " + handle.Type.FullName);
                handle.Complete<UnityEngine.Object>(asset, true, null);
            }
            catch (Exception error)
            {
                string failure = handle.Location.InternalId + " / " + handle.Type.FullName + " / " + error.Message;
                lock (reportedFailures) if (reportedFailures.Add(failure)) Debug.LogError("Borrowed asset provider failed: " + failure);
                handle.Complete<UnityEngine.Object>(null, false, error);
            }
        }
        public override void Release(IResourceLocation location, object asset)
        {
        }
    }
    public static IEnumerator Prepare()
    {
        if (!Resources.Load<TextAsset>("WholeCatalogBootstrap"))
            yield break;
        if (owned)
            throw new Exception("Shared whole-content dependency already owned");
        string path = Path.Combine(Application.persistentDataPath, "payload", "whole-game-content");
        if (!File.Exists(path))
            throw new Exception("Shared whole-content dependency not synchronized");
        if (AssetBundle.GetAllLoadedAssetBundles().Any(x => x.name == "whole-game-content"))
            throw new Exception("Shared dependency has a foreign owner");
        var load = AssetBundle.LoadFromFileAsync(path);
        yield return load;
        owned = load.assetBundle;
        if (!owned)
            throw new Exception("Shared whole-content dependency failed to load");
    }
    public static void ConfigureLocations()
    {
        if (!owned || ownedLocator != null)
            throw new Exception("Shared content location ownership invalid");
        string payload = Path.Combine(Application.persistentDataPath, "payload");
        var manifest = JObject.Parse(File.ReadAllText(Path.Combine(payload, "whole-catalog.json")));
        currentManifest = new WeakReference(manifest);
        var descriptor = JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
        if ((string)manifest["input_id"] != (string)descriptor["input_id"] || (string)manifest["attempt"] != (string)descriptor["attempt"])
            throw new Exception("Composed APK/catalog generation mismatch");
        priorLocators = Addressables.ResourceLocators.ToArray();
        borrowedNames = new HashSet<string>(AssetBundle.GetAllLoadedAssetBundles().Select(bundle => bundle.name));
        var providers = Addressables.ResourceManager.ResourceProviders;
        if (!providers.Any(provider => provider is BorrowedBundleProvider))
            providers.Add(new BorrowedBundleProvider());
        if (!providers.Any(provider => provider is BorrowedAssetProvider))
            providers.Add(new BorrowedAssetProvider());
        WholeCatalogLoader.RegisterLocations(manifest, typeof(BundledAssetProvider).FullName, payload,
                                             typeof(BorrowedBundleProvider).FullName, borrowedNames,
                                             typeof(BorrowedAssetProvider).FullName);
        ownedLocator = WholeCatalogLoader.locator;
    }
    public static void Release()
    {
        lastDetachedAssetOperations = DetachBorrowedAssetCache();
        if (ownedLocator != null)
        {
            releasedLocators.Add(new WeakReference(ownedLocator));
            releasedManifests.Add(currentManifest);
            currentManifest = null;
            Addressables.RemoveResourceLocator(ownedLocator);
            foreach (var locator in priorLocators)
            {
                Addressables.RemoveResourceLocator(locator);
                Addressables.AddResourceLocator(locator);
            }
            WholeCatalogLoader.locator = null;
            ownedLocator = null;
            priorLocators = null;
        }
        definitionFamilies.Clear();
        BorrowedAssetProvider.ResetFailures();
        borrowedNames = null;
        if (owned)
        {
            owned.Unload(true);
            owned = null;
        }
    }
    // LegacyResourcesAPI.Load keeps successful handles after returning its asset.
    // The session has ended, so remove only completed operations from this owned
    // locator before unloading its bundles. Retained original handles remain valid
    // for their callers; a later session must not reuse their destroyed Unity result.
    static int DetachBorrowedAssetCache()
    {
        if (ownedLocator == null)
            return 0;
        var manager = Addressables.ResourceManager;
        var field = manager.GetType().GetField("m_AssetOperationCache", BindingFlags.Instance | BindingFlags.NonPublic);
        var cache = field == null ? null : field.GetValue(manager) as System.Collections.IDictionary;
        if (cache == null)
            throw new Exception("Original resource operation cache contract changed");
        var stale = new List<System.Collections.DictionaryEntry>();
        foreach (System.Collections.DictionaryEntry entry in cache)
        {
            var key = entry.Key;
            var keyType = key.GetType();
            if (keyType.Name != "LocationCacheKey")
                continue;
            var locationField = keyType.GetField("m_Location", BindingFlags.Instance | BindingFlags.NonPublic);
            var location = locationField == null ? null : locationField.GetValue(key) as IResourceLocation;
            if (location == null || location.ProviderId != typeof(BorrowedAssetProvider).FullName || location.Dependencies == null ||
                location.Dependencies.Count == 0)
                continue;
            var owner = location.Dependencies[0].PrimaryKey;
            if (owner != "whole-game-content" && owner != "commando-prefab-lab" && owner != "objective-support-lab")
                continue;
            var operation = entry.Value;
            var asyncType = operation.GetType().GetInterfaces().SingleOrDefault(
                value => value.FullName == "UnityEngine.ResourceManagement.AsyncOperations.IAsyncOperation");
            var cacheType = operation.GetType().GetInterfaces().SingleOrDefault(
                value => value.FullName == "UnityEngine.ResourceManagement.AsyncOperations.ICachable");
            if (asyncType == null || cacheType == null || !(bool)asyncType.GetProperty("IsDone").GetValue(operation, null) ||
                !ReferenceEquals(cacheType.GetProperty("Key").GetValue(operation, null), key))
                throw new Exception("Owned resource operation is pending or changed");
            stale.Add(entry);
        }
        foreach (var entry in stale)
        {
            var operation = entry.Value;
            var cacheType = operation.GetType().GetInterfaces().Single(value => value.FullName ==
                                                                                "UnityEngine.ResourceManagement.AsyncOperations.ICachable");
            cacheType.GetProperty("Key").SetValue(operation, null, null);
            cache.Remove(entry.Key);
        }
        return stale.Count;
    }
    public static int[] ReleasedCatalogRetention()
    {
        return new[] { releasedLocators.Count, releasedLocators.Count(value => value.IsAlive),
                       releasedManifests.Count(value => value != null && value.IsAlive), Addressables.ResourceLocators.Count(),
                       lastDetachedAssetOperations };
    }
    public static string DiagnoseFireTrail()
    {
        const string path = "Prefabs/FireTrail";
        string guid;
        if (!RoR2.LegacyResourcesAPI.GetGuid(path, out guid))
            return "original legacy alias missing";
        IList<IResourceLocation> locations = null;
        bool located = WholeCatalogLoader.locator != null && WholeCatalogLoader.locator.Locate(guid, typeof(GameObject), out locations);
        var direct = owned ? owned.LoadAsset<GameObject>("Assets/WholeGame/RoR2/Base/Common/DamageTrails/FireTrail.prefab") : null;
        var handle = Addressables.LoadAssetAsync<GameObject>(guid);
        try
        {
            var result = handle.WaitForCompletion();
            return Newtonsoft.Json.JsonConvert.SerializeObject(
                new { located, count = locations == null ? 0 : locations.Count,
                      providers = locations == null ? new string[0] : locations.Select(value => value.ProviderId).ToArray(),
                      direct = direct != null, status = handle.Status.ToString(), result = result != null,
                      error = handle.OperationException == null ? "" : handle.OperationException.GetBaseException().Message });
        }
        finally
        {
            if (handle.IsValid())
                Addressables.Release(handle);
        }
    }
    // Complete definition families share the existing converted owner; no tested-content whitelist.
    static readonly Dictionary<string, UnityEngine.Object[]> definitionFamilies = new Dictionary<string, UnityEngine.Object[]>();
    // Labels alone include Junk content which the original provider does not publish.
    // Resolve each provider using its native category policy and collection ordering.
    public static int[][] FamilyLocationGroups(JObject manifest, string category)
    {
        var keys = manifest["keys"]
                       .Where(row => row["keyType"] == null || (string)row["keyType"] == "System.String")
                       .ToDictionary(row => (string)row["key"], row => new HashSet<int>(row["locations"].Select(value => (int)value)));
        var helper = new RoR2.ContentManagement.AddressablesLoadHelper(new IResourceLocator[0]);
        return manifest["providers"]
            .Select(provider =>
                    {
                        var instance = Activator.CreateInstance(Type.GetType((string)provider["type"], true));
                        var pack =
                            (RoR2.ContentManagement.ContentPack)instance.GetType()
                                .GetField("contentPack", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                                .GetValue(instance);
                        if (!helper.CanLoadType(category, pack))
                            return new int[0];
                        return keys["ContentPack:" + (string)provider["identifier"]].Intersect(keys[category]).ToArray();
                    })
            .ToArray();
    }
    public static T[] CategoryFamily<T>(string category, IEnumerable<T> selected)
        where T : UnityEngine.Object
    {
        if (!owned)
            throw new Exception("Complete category owner unavailable: " + category);
        string key = typeof(T).FullName + ":" + category;
        UnityEngine.Object[] values;
        if (!definitionFamilies.TryGetValue(key, out values))
        {
            var manifest = JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json")));
            var locations = manifest["locations"].ToDictionary(row => (int)row["id"]);
            values = FamilyLocationGroups(manifest, category)
                         .SelectMany(group =>
                                     {
                                         var collection =
                                             new RoR2.ContentManagement.NamedAssetCollection<T>(value => ((UnityEngine.Object)value).name);
                                         collection.Add(
                                             group
                                                 .Select(id =>
                                                         {
                                                             var row = locations[id];
                                                             if (!typeof(T).IsAssignableFrom(Type.GetType((string)row["type"], true)))
                                                                 throw new Exception("Original category type differs: " + category);
                                                             var bundle = AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(
                                                                 value => value.name == (string)row["bundle"]);
                                                             if (!bundle)
                                                                 throw new Exception("Original category owner not loaded: " + category +
                                                                                     "/" + row["bundle"]);
                                                             var asset = bundle.LoadAsset<T>((string)row["path"]);
                                                             if (!asset)
                                                                 throw new Exception("Original category asset missing: " + category + "/" +
                                                                                     row["path"]);
                                                             return asset;
                                                         })
                                                 .ToArray());
                                         return collection.ToArray();
                                     })
                         .Distinct()
                         .Cast<UnityEngine.Object>()
                         .ToArray();
            // Native collections enforce names within each provider, not across packs.
            if (values.Length == 0)
                throw new Exception("Original category is empty: " + category);
            definitionFamilies.Add(key, values);
        }
        if (selected.Any(value => !values.Contains(value)))
            throw new Exception("Selected asset outside original category: " + category);
        return values.Cast<T>().ToArray();
    }
    public static T[] DefinitionFamily<T>(System.Collections.Generic.IEnumerable<T> selected)
        where T : UnityEngine.Object
    {
        if (!owned)
            throw new Exception("Complete definition owner unavailable: " + typeof(T).FullName);
        UnityEngine.Object[] values;
        if (!definitionFamilies.TryGetValue(typeof(T).FullName, out values))
        {
            var manifest = JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json")));
            var roots = new HashSet<int>(manifest["provider_roots"].Select(value => (int)value));
            values =
                manifest["locations"]
                    .Where(row => roots.Contains((int)row["id"]) && typeof(T).IsAssignableFrom(Type.GetType((string)row["type"], true)))
                    .Select(row =>
                            {
                                string owner = (string)row["bundle"];
                                var bundle = AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(value => value.name == owner);
                                if (!bundle)
                                    throw new Exception("Original definition owner not loaded: " + typeof(T).FullName + "/" + owner);
                                return bundle.LoadAsset<T>((string)row["path"]);
                            })
                    .Distinct()
                    .Cast<UnityEngine.Object>()
                    .ToArray();
            if (values.Length == 0 || values.Any(value => !value) || values.Select(value => value.name).Distinct().Count() != values.Length)
                throw new Exception("Complete definition identity missing or ambiguous: " + typeof(T).FullName);
            definitionFamilies.Add(typeof(T).FullName, values);
        }
        if (selected.Any(value => !values.Contains(value)))
            throw new Exception("Selected definition is outside original provider family: " + typeof(T).FullName);
        return values.Cast<T>().ToArray();
    }
    static readonly Dictionary<System.Reflection.FieldInfo, object> priorDefinitionFields =
        new Dictionary<System.Reflection.FieldInfo, object>();
    public static void PopulateDefinitionFields<T>(string family, T[] definitions, string prefix = "")
        where T : UnityEngine.Object
    {
        var manifest = JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json")));
        var byName = definitions.ToDictionary(value => value.name, StringComparer.Ordinal);
        foreach (var provider in manifest["providers"])
        {
            var holder = Type.GetType((string)provider["type"], true).GetNestedType(family);
            if (holder == null)
                continue;
            var fields = holder.GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
            var assets =
                fields
                    .Select(field =>
                            {
                                if (field.FieldType != typeof(T))
                                    throw new Exception("Original definition holder type differs: " + holder.FullName + "/" + field.Name);
                                var target = (RoR2.ContentManagement.TargetAssetNameAttribute)Attribute.GetCustomAttribute(
                                    field, typeof(RoR2.ContentManagement.TargetAssetNameAttribute));
                                string name = target != null ? target.targetAssetName : prefix + field.Name;
                                T value;
                                if (!byName.TryGetValue(name, out value))
                                    throw new Exception("Original definition holder asset absent: " + holder.FullName + "/" + name);
                                if (!priorDefinitionFields.ContainsKey(field))
                                    priorDefinitionFields.Add(field, field.GetValue(null));
                                if (field.GetValue(null) != null && !ReferenceEquals(field.GetValue(null), value))
                                    throw new Exception("Original definition holder identity changed: " + holder.FullName + "/" + name);
                                return value;
                            })
                    .Distinct()
                    .ToArray();
            var collection = new RoR2.ContentManagement.NamedAssetCollection<T>(value => value.name);
            collection.Add(assets);
            RoR2.ContentManagement.ContentLoadHelper.PopulateTypeFields(holder, collection, name => prefix + name);
            foreach (var field in fields)
                if (field.GetValue(null) == null)
                    throw new Exception("Original definition holder unbound: " + holder.FullName + "/" + field.Name);
        }
    }
    public static void PopulateBodyFields(GameObject[] prefabs)
    {
        var byName = prefabs.ToDictionary(value => value.name, StringComparer.Ordinal);
        var manifest = JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json")));
        foreach (var provider in manifest["providers"])
        {
            var holder = Type.GetType((string)provider["type"], true).GetNestedType("BodyPrefabs");
            if (holder == null)
                continue;
            var fields = holder.GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
            var assets =
                fields
                    .Select(field =>
                            {
                                var target = (RoR2.ContentManagement.TargetAssetNameAttribute)Attribute.GetCustomAttribute(
                                    field, typeof(RoR2.ContentManagement.TargetAssetNameAttribute));
                                GameObject value;
                                if (field.FieldType != typeof(RoR2.CharacterBody) ||
                                    !byName.TryGetValue(target != null ? target.targetAssetName : field.Name, out value))
                                    throw new Exception("Original body holder contract absent: " + holder.FullName + "/" + field.Name);
                                if (!priorDefinitionFields.ContainsKey(field))
                                    priorDefinitionFields.Add(field, field.GetValue(null));
                                if (field.GetValue(null) != null &&
                                    !ReferenceEquals(field.GetValue(null), value.GetComponent<RoR2.CharacterBody>()))
                                    throw new Exception("Original body holder has a foreign owner: " + field.Name);
                                return value;
                            })
                    .Distinct()
                    .ToArray();
            var collection = new RoR2.ContentManagement.NamedAssetCollection<GameObject>(value => value.name);
            collection.Add(assets);
            RoR2.ContentManagement.ContentLoadHelper.PopulateTypeFields(holder, collection,
                                                                        (GameObject value) => value.GetComponent<RoR2.CharacterBody>());
        }
    }
    static Dictionary<RoR2.Projectile.ProjectileController, int> priorProjectileIndices;
    static global::ResourceAvailability priorProjectileAvailability;
    public static int PrepareProjectiles()
    {
        if (priorProjectileIndices != null || RoR2.ProjectileCatalog.projectilePrefabCount != 0)
            throw new Exception("Projectile catalog has a foreign owner");
        var values = CategoryFamily(RoR2.ContentManagement.AddressablesLabels.projectile, new GameObject[0]);
        priorProjectileIndices = values.Select(value => value.GetComponent<RoR2.Projectile.ProjectileController>())
                                     .ToDictionary(value => value, value => value.catalogIndex);
        priorProjectileAvailability = RoR2.ProjectileCatalog.catalogAvailability;
        typeof(RoR2.ProjectileCatalog)
            .GetMethod("SetProjectilePrefabs", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)
            .Invoke(null, new object[] { values });
        RoR2.ProjectileCatalog.catalogAvailability.MakeAvailable();
        if (values.Any(value => RoR2.ProjectileCatalog.GetProjectilePrefab(RoR2.ProjectileCatalog.GetProjectileIndex(value)) != value))
            throw new Exception("Original projectile catalog identity differs");
        return values.Length;
    }
    public static void RestoreProjectiles()
    {
        if (priorProjectileIndices == null)
            return;
        typeof(RoR2.ProjectileCatalog)
            .GetMethod("SetProjectilePrefabs", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)
            .Invoke(null, new object[] { new GameObject[0] });
        foreach (var pair in priorProjectileIndices)
            pair.Key.catalogIndex = pair.Value;
        priorProjectileIndices = null;
        RoR2.ProjectileCatalog.catalogAvailability = priorProjectileAvailability;
    }
    static RoR2.ItemTierDef[] priorTierContent;
    static object priorTierDefinitions;
    static global::ResourceAvailability priorTierAvailability;
    static Dictionary<RoR2.ItemTierDef, RoR2.ItemTier> originalTiers;
    public static void PrepareItemTiers()
    {
        if (originalTiers != null)
            throw new Exception("Item tiers already owned");
        var type = typeof(RoR2.ItemTierCatalog);
        var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static;
        var map = (System.Collections.IDictionary)type.GetField("itemTierToDef", flags).GetValue(null);
        if (RoR2.ItemTierCatalog.itemCount != 0 || map.Count != 0)
            throw new Exception("Item tiers have a foreign owner");
        priorTierContent = RoR2.ContentManagement.ContentManager._itemTierDefs;
        priorTierDefinitions = type.GetField("itemTierDefs", flags).GetValue(null);
        priorTierAvailability = RoR2.ItemTierCatalog.availability;
        var values = DefinitionFamily(new RoR2.ItemTierDef[0]);
        originalTiers = values.ToDictionary(value => value, value => value.tier);
        RoR2.ContentManagement.ContentManager._itemTierDefs = values;
        type.GetMethod("Init", flags).Invoke(null, null);
        if (values.Any(value => RoR2.ItemTierCatalog.GetItemTierDef(value.tier) != value))
            throw new Exception("Original item-tier identity differs");
    }
    public static void RestoreItemTiers()
    {
        if (originalTiers == null)
            return;
        var type = typeof(RoR2.ItemTierCatalog);
        var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static;
        ((System.Collections.IDictionary)type.GetField("itemTierToDef", flags).GetValue(null)).Clear();
        type.GetField("itemTierDefs", flags).SetValue(null, priorTierDefinitions);
        RoR2.ContentManagement.ContentManager._itemTierDefs = priorTierContent;
        RoR2.ItemTierCatalog.availability = priorTierAvailability;
        foreach (var pair in originalTiers)
            pair.Key.tier = pair.Value;
        originalTiers = null;
    }
    public static void RestoreDefinitionFields()
    {
        foreach (var pair in priorDefinitionFields)
            pair.Key.SetValue(null, pair.Value);
        priorDefinitionFields.Clear();
    }
    public static RoR2.BuffDef[] BuffDefinitions()
    {
        if (!owned)
            throw new Exception("Shared original buff owner unavailable");
        return owned.LoadAllAssets<RoR2.BuffDef>();
    }
    public static RoR2.ItemDef[] ItemDefinitions()
    {
        if (!owned)
            throw new Exception("Shared original item owner unavailable");
        return owned.LoadAllAssets<RoR2.ItemDef>();
    }
    public static RoR2.EliteDef[] EliteDefinitions()
    {
        return CategoryFamily(RoR2.ContentManagement.AddressablesLabels.eliteDef, new RoR2.EliteDef[0]);
    }
    public static RoR2.KeyItemDef[] KeyItemDefinitions()
    {
        if (!owned)
            throw new Exception("Shared original key-item owner unavailable");
        return owned.LoadAllAssets<RoR2.KeyItemDef>();
    }
    public static RoR2.ItemGroupType[] ItemGroupTypes()
    {
        if (!owned)
            throw new Exception("Shared original item-group owner unavailable");
        return owned.LoadAllAssets<RoR2.ItemGroupType>();
    }
    public static RoR2.ItemGroupProvider[] ItemGroupProviders()
    {
        if (!owned)
            throw new Exception("Shared original item-group provider owner unavailable");
        return owned.LoadAllAssets<RoR2.ItemGroupProvider>();
    }
    public static RoR2.CharacterBody[] BodyComparisons(Type holder)
    {
        if (!owned)
            throw new Exception("Shared original body owner unavailable");
        var manifest = JObject.Parse(File.ReadAllText(Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json")));
        var locations = manifest["locations"]
                            .Where(row => ((string)row["type"]).StartsWith("UnityEngine.GameObject,", StringComparison.Ordinal))
                            .ToLookup(row => Path.GetFileName((string)row["path"]), StringComparer.OrdinalIgnoreCase);
        return holder.GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
            .Select(field =>
                    {
                        var matches = locations[field.Name + ".prefab"].ToArray();
                        if (field.FieldType != typeof(RoR2.CharacterBody) || matches.Length != 1)
                            throw new Exception("Original comparison body owner ambiguous: " + field.Name);
                        string owner = (string)matches[0]["bundle"];
                        var bundle = AssetBundle.GetAllLoadedAssetBundles().SingleOrDefault(value => value.name == owner);
                        if (!bundle)
                            throw new Exception("Original comparison body owner not loaded: " + field.Name + " / " + owner);
                        var prefab = bundle.LoadAsset<GameObject>((string)matches[0]["path"]);
                        var body = prefab ? prefab.GetComponent<RoR2.CharacterBody>() : null;
                        if (!body || prefab.name != field.Name)
                            throw new Exception("Original comparison body identity differs: " + field.Name);
                        return body;
                    })
            .ToArray();
    }
}
