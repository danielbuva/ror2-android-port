// Authored lifetime doubles. No game source, assets, native engine or device state.
using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;
using UnityEngine.ResourceManagement.ResourceProviders;
using RoR2;

namespace UnityEngine
{
    public class Object
    {
        public string name;
        public bool destroyed;
        public static implicit operator bool(Object value) { return value != null && !value.destroyed; }
    }
    public class Component : Object { }
    public class Transform : Component
    {
        public T[] GetComponents<T>() { return new T[0]; }
    }
    public class GameObject : Object
    {
        public T[] GetComponentsInChildren<T>(bool includeInactive) { return new T[0]; }
    }
    public class TextAsset : Object { public string text; }
    public static class Application { public static string persistentDataPath = Directory.GetCurrentDirectory(); }
    public static class Resources
    {
        public static string descriptor;
        public static T Load<T>(string key) where T : Object
        {
            return new TextAsset { text = key == "WholeCatalogBootstrap" ? descriptor : "{}" } as T;
        }
    }
    public static class JsonUtility
    {
        public static T FromJson<T>(string text) where T : new() { return new T(); }
    }
    public class AssetBundleCreateRequest { public AssetBundle assetBundle; }
    public class AssetBundle : Object
    {
        public static readonly List<AssetBundle> all = new List<AssetBundle>();
        public static int bodyLoads;
        public int unloads;
        public readonly List<Object> assets = new List<Object>();
        public AssetBundle(string name) { this.name = name; all.Add(this); }
        public T LoadAsset<T>(string path) where T : Object { return assets.OfType<T>().First(); }
        public static IEnumerable<AssetBundle> GetAllLoadedAssetBundles() { return all.Where(bundle => bundle); }
        public static AssetBundle LoadFromFile(string path)
        {
            string name = Path.GetFileName(path);
            if (all.Any(bundle => bundle && bundle.name == name)) throw new Exception("Duplicate native bundle load");
            var value = new AssetBundle(name);
            if (name == "commando-prefab-lab")
            {
                bodyLoads++;
                value.assets.Add(new GameObject { name = "body" });
            }
            return value;
        }
        public static AssetBundleCreateRequest LoadFromFileAsync(string path)
        {
            return new AssetBundleCreateRequest { assetBundle = LoadFromFile(path) };
        }
        public void Unload(bool destroyAssets)
        {
            if (!this || !destroyAssets) throw new Exception("Unexpected unload");
            unloads++;
            destroyed = true;
            foreach (var asset in assets) asset.destroyed = true;
        }
    }
}
namespace UnityEngine.ResourceManagement.ResourceLocations
{
    public class ResourceLocationBase
    {
        public string PrimaryKey;
        public object Data;
        public ResourceLocationBase(string key, string path, string provider, Type type) { PrimaryKey = key; }
    }
}
namespace UnityEngine.ResourceManagement.ResourceProviders
{
    public interface IAssetBundleResource { AssetBundle GetAssetBundle(); }
    public class AssetBundleProvider { }
    public class AssetBundleRequestOptions { public string BundleName; }
    public class BundleResource : IAssetBundleResource
    {
        public AssetBundle bundle;
        public AssetBundle GetAssetBundle() { return bundle; }
    }
}
namespace UnityEngine.ResourceManagement.AsyncOperations
{
    public enum AsyncOperationStatus { Failed, Succeeded }
    public class Operation<T>
    {
        public T result;
        public int references = 1;
        public AsyncOperationStatus status = AsyncOperationStatus.Succeeded;
    }
    public struct AsyncOperationHandle<T>
    {
        public Operation<T> operation;
        public bool IsValid() { return operation != null && operation.references > 0; }
        public AsyncOperationStatus Status { get { return operation.status; } }
        public T Result { get { return operation.result; } }
    }
}
namespace UnityEngine.AddressableAssets.ResourceLocators { public interface IResourceLocator { } }
namespace UnityEngine.AddressableAssets
{
    public sealed class Manager
    {
        public readonly List<object> ResourceProviders = new List<object>();
        public int loads, releases;
        public AsyncOperationHandle<T> ProvideResource<T>(ResourceLocationBase location)
        {
            loads++;
            var bundle = AssetBundle.LoadFromFile(location.PrimaryKey);
            bundle.assets.Add(new GameObject { name = "ward" });
            return new AsyncOperationHandle<T> { operation = new Operation<T> { result = (T)(object)new BundleResource { bundle = bundle } } };
        }
    }
    public static class Addressables
    {
        public static readonly Manager ResourceManager = new Manager();
        public static void Release(AsyncOperationHandle<IAssetBundleResource> handle)
        {
            if (!handle.IsValid()) throw new Exception("Double provider release");
            ResourceManager.releases++;
            handle.operation.references--;
            if (handle.operation.references == 0) handle.Result.GetAssetBundle().Unload(true);
        }
        public static void RemoveResourceLocator(IResourceLocator locator) { }
        public static void AddResourceLocator(IResourceLocator locator) { }
    }
}
namespace RoR2
{
    public class UnlockableDef : UnityEngine.Object { public string cachedName; }
    public class SurvivorDef : UnityEngine.Object
    {
        public GameObject bodyPrefab;
        public bool hidden, expansion, entitlement;
        public string cachedName, unlockableName;
        public UnlockableDef unlockableDef;
        public bool GetRequiredExpansion() { return expansion; }
        public bool GetRequiredEntitlement() { return entitlement; }
    }
    public static class BodyCatalog { public static int bodyCount; public static object availability; }
    public static class SkillCatalog { public static int skillCount, skillFamilyCount; }
    public static class LegacyResourcesAPI { public static int ActiveCount; }
}
namespace RoR2.ContentManagement
{
    public static class AddressablesLabels { public const string survivorDef = "survivors"; }
}
public static class AndroidOfflineProfile
{
    public static HashSet<string> PreviewUnlockNames(string path) { return new HashSet<string>(); }
}
public class SessionConfig { public string[] objectiveSupportAssets = { "unused", "ward" }; }
public static partial class GameAudioOriginalOwner
{
    public static bool OriginalManagerInitClaimed, NativeInitAttemptObserved, OriginalTermsReturned;
}
public static class WholeCatalogLoader { public static IResourceLocator locator; }
public static partial class WholeCatalogComposed
{
    static AssetBundle owned;
    static IResourceLocator ownedLocator;
    static IResourceLocator[] priorLocators;
    static WeakReference currentManifest;
    static string activeInputId, activeAttempt, activeManifestSha256;
    static int lastDetachedAssetOperations;
    static HashSet<string> borrowedNames;
    static readonly List<WeakReference> releasedLocators = new List<WeakReference>(), releasedManifests = new List<WeakReference>();
    static readonly Dictionary<string, UnityEngine.Object[]> definitionFamilies = new Dictionary<string, UnityEngine.Object[]>();
    static class BorrowedAssetProvider { public static void ResetFailures() { } }
    sealed class Locator : IResourceLocator { }
    static int DetachBorrowedAssetCache() { return 0; }
    public static SurvivorDef[] survivors;
    public static T[] CategoryFamily<T>(string category, IEnumerable<T> selected) where T : UnityEngine.Object { return survivors.Cast<T>().ToArray(); }
    public static void ConfigureForHost(string manifest)
    {
        activeInputId = "authored-input";
        activeAttempt = "authored-attempt";
        using (var sha = System.Security.Cryptography.SHA256.Create())
            activeManifestSha256 = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(manifest))).Replace("-", "").ToLowerInvariant();
        ownedLocator = new Locator();
        currentManifest = new WeakReference(new object());
        priorLocators = new IResourceLocator[0];
    }
    public static void CheckGraph(string root, IDictionary<string, string[]> graph, IEnumerable<AssetBundle> loaded)
    {
        new RetainedDependencyOwners(root, graph, loaded);
    }
}
public sealed partial class PortSession
{
    public AssetBundle artifactBundle;
    public ResourceLocationBase objectiveBundleLocation;
    public AsyncOperationHandle<IAssetBundleResource> objectiveBundlePreload;
    bool ownsBodyAvailability, ownsBodyCatalog;
    object priorBodyAvailability;
    HashSet<string> offlineUnlockPreview;
    public class CatalogReport { public bool bodySkillCleanup; }
    public class Report { public CatalogReport liveCatalogs = new CatalogReport(); }
    public readonly Report r = new Report();
    public readonly TeleporterWorldSession teleporter;
    public PortSession() { teleporter = new TeleporterWorldSession(this); }
    void CleanupOriginalSkins() { }
    void CleanupLoadoutTables() { }
    void RestoreCatalogBodyTemplates() { }
    void CleanupRecoveredText() { }
    void RestoreBodySettingsTransform() { }
    void StaticCall(Type type, string method, object value) { BodyCatalog.bodyCount = 0; }
    void ReleaseObjectiveBundlePreload() { teleporter.ReleaseObjectiveBundlePreload(); }
    public void Cleanup() { CleanupBodyCatalog(); }
    public string[] Choices() { return OrdinarySurvivorChoices().Select(value => value.cachedName).ToArray(); }
    public void Check(bool value, string message) { if (!value) throw new Exception(message); }
    public sealed partial class TeleporterWorldSession
    {
        readonly PortSession coordinator;
        bool ownsObjectiveBundlePreload;
        public TeleporterWorldSession(PortSession value) { coordinator = value; }
    }
}
public static class RetainedCatalogHost
{
    const string Root = "whole-game-content", Body = "commando-prefab-lab", Objective = "objective-support-lab";
    static Dictionary<string, string[]> Graph()
    {
        return new Dictionary<string, string[]> { { Root, new[] { Body, Objective } }, { Body, new[] { Root, Objective } }, { Objective, new[] { Root, Body } } };
    }
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void Run(IEnumerator steps) { while (steps.MoveNext()) { } }
    static string manifestPath;
    static int refusals;
    static PortSession Begin(bool audio)
    {
        Run(WholeCatalogComposed.Prepare());
        var session = new PortSession();
        session.AcquireBody();
        Run(session.teleporter.PreloadObjectiveBundle());
        WholeCatalogComposed.ConfigureForHost(manifestPath);
        if (WholeCatalogComposed.survivors == null)
        {
            var root = AssetBundle.GetAllLoadedAssetBundles().Single(value => value.name == Root);
            var huntressBody = new GameObject { name = "huntress-body" };
            root.assets.Add(huntressBody);
            WholeCatalogComposed.survivors = new[] {
                new SurvivorDef { cachedName = "Commando", bodyPrefab = session.artifactBundle.assets.OfType<GameObject>().Single() },
                new SurvivorDef { cachedName = "Huntress", bodyPrefab = huntressBody },
                new SurvivorDef { cachedName = "Locked", bodyPrefab = huntressBody, unlockableName = "unearned" },
                new SurvivorDef { cachedName = "Expansion", bodyPrefab = huntressBody, expansion = true },
                new SurvivorDef { cachedName = "Entitled", bodyPrefab = huntressBody, entitlement = true },
                new SurvivorDef { cachedName = "Hidden", bodyPrefab = huntressBody, hidden = true }
            };
        }
        Check(session.Choices().SequenceEqual(new[] { "Commando", "Huntress" }), "Availability guards changed");
        if (audio) WholeCatalogComposed.RetainForOriginalAudioOwner("authored-input");
        return session;
    }
    static void ReleaseLease()
    {
        GameAudioOriginalOwner.OriginalTermsReturned = true;
        WholeCatalogComposed.ReleaseOriginalAudioOwnerLease("authored-input:authored-attempt:" + Hash(manifestPath));
    }
    static string Hash(string path)
    {
        using (var sha = System.Security.Cryptography.SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
    }
    static void Refuses(Action action)
    {
        try { action(); }
        catch (Exception) { refusals++; return; }
        throw new Exception("Expected ownership refusal");
    }
    static void NoUnload()
    {
        Check(AssetBundle.all.All(value => value && value.unloads == 0), "Dependency destroyed before original Term/session closure");
        Check(Addressables.ResourceManager.releases == 0, "Provider handle released while retained");
    }
    static void Finished()
    {
        Check(AssetBundle.all.All(value => !value && value.unloads == 1), "Each owner must unload exactly once");
        Check(Addressables.ResourceManager.releases == 1, "Provider release must occur exactly once");
    }
    static void Restart()
    {
        var first = Begin(true);
        var body = first.artifactBundle;
        var location = first.objectiveBundleLocation;
        var operation = first.objectiveBundlePreload.operation;
        GameAudioOriginalOwner.OriginalManagerInitClaimed = GameAudioOriginalOwner.NativeInitAttemptObserved = true;
        first.Cleanup();
        for (int next = 0; next < 2; next++)
        {
            // Validate selection first: the unload mutant must fail with the
            // same production failure as R10, rather than an incidental assertion.
            var session = Begin(true);
            NoUnload();
            Check(ReferenceEquals(body, session.artifactBundle), "Manual owner was replaced");
            Check(ReferenceEquals(location, session.objectiveBundleLocation), "Provider location was replaced");
            Check(ReferenceEquals(operation, session.objectiveBundlePreload.operation) && operation.references == 1, "Provider ownership was duplicated");
            session.Cleanup();
        }
        NoUnload();
        ReleaseLease();
        Finished();
        Console.WriteLine("{\"sessions\":3,\"body_loads\":" + AssetBundle.bodyLoads + ",\"provider_loads\":" + Addressables.ResourceManager.loads + ",\"releases\":" + Addressables.ResourceManager.releases + "}");
    }
    static void Termination()
    {
        var session = Begin(true);
        GameAudioOriginalOwner.OriginalManagerInitClaimed = GameAudioOriginalOwner.NativeInitAttemptObserved = true;
        Refuses(() => WholeCatalogComposed.ReleaseOriginalAudioOwnerLease("authored-input:authored-attempt:" + Hash(manifestPath)));
        NoUnload();
        ReleaseLease(); // Term while the session is still active must defer.
        NoUnload();
        session.Cleanup();
        Finished();
        // Start fresh with no audio lease: normal teardown must remain immediate.
        AssetBundle.all.Clear();
        WholeCatalogComposed.survivors = null;
        Addressables.ResourceManager.releases = 0;
        session = Begin(false);
        session.Cleanup();
        Finished();
        Console.WriteLine("{\"active_term\":true,\"early_refusal\":true,\"default_off\":true}");
    }
    static void Refusals()
    {
        var session = Begin(true);
        var loaded = AssetBundle.GetAllLoadedAssetBundles().ToArray();
        var graph = Graph();
        graph.Remove(Body);
        Refuses(() => WholeCatalogComposed.CheckGraph(Root, graph, loaded));
        graph = Graph(); graph[Body] = new[] { Root, Root };
        Refuses(() => WholeCatalogComposed.CheckGraph(Root, graph, loaded));
        Refuses(() => WholeCatalogComposed.CheckGraph(Root, Graph(), loaded.Where(value => value.name != Body)));
        Refuses(() => WholeCatalogComposed.CheckGraph(Root, Graph(), loaded.Concat(new[] { session.artifactBundle })));
        Refuses(() => WholeCatalogComposed.RetainForOriginalAudioOwner("other-input"));
        Refuses(() => WholeCatalogComposed.ReleaseOriginalAudioOwnerLease("other-lease"));
        Refuses(() => Run(WholeCatalogComposed.Prepare()));
        var body = session.artifactBundle;
        var location = session.objectiveBundleLocation;
        var handle = session.objectiveBundlePreload;
        session.Cleanup();
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(body));
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(Objective, location, handle));
        AssetBundle manual;
        Refuses(() => WholeCatalogComposed.TakeRetainedDependency(Objective, out manual));
        ResourceLocationBase parkedLocation;
        AsyncOperationHandle<IAssetBundleResource> parkedHandle;
        Refuses(() => WholeCatalogComposed.TakeRetainedDependency(Body, out parkedLocation, out parkedHandle));
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(Objective, location, default(AsyncOperationHandle<IAssetBundleResource>)));
        body.name = "foreign-name";
        Refuses(() => WholeCatalogComposed.TakeRetainedDependency(Body, out manual));
        body.name = Body;
        WholeCatalogComposed.TakeRetainedDependency(Objective, out parkedLocation, out parkedHandle);
        var foreignLocation = new ResourceLocationBase("foreign-key", "", "", typeof(IAssetBundleResource));
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(Objective, foreignLocation, handle));
        var resource = (BundleResource)handle.Result;
        var originalBundle = resource.bundle;
        resource.bundle = body;
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(Objective, location, handle));
        resource.bundle = originalBundle;
        WholeCatalogComposed.ParkRetainedDependency(Objective, location, handle);
        var foreignBody = new AssetBundle(Body);
        AssetBundle.all.Remove(foreignBody);
        Refuses(() => WholeCatalogComposed.ParkRetainedDependency(foreignBody));
        handle.operation.status = AsyncOperationStatus.Failed;
        Refuses(() => WholeCatalogComposed.ReleaseOriginalAudioOwnerLease("authored-input:authored-attempt:" + Hash(manifestPath)));
        NoUnload();
        handle.operation.status = AsyncOperationStatus.Succeeded;
        string savedManifest = File.ReadAllText(manifestPath);
        File.AppendAllText(manifestPath, " ");
        Refuses(() => Run(WholeCatalogComposed.Prepare()));
        File.WriteAllText(manifestPath, savedManifest);
        // The failed release must leave the identity/held flag retryable.
        ReleaseLease();
        Finished();
        Console.WriteLine("{\"checks\":" + refusals + "}");
    }
    public static int Main(string[] arguments)
    {
        try
        {
            Directory.CreateDirectory(Path.Combine(Application.persistentDataPath, "payload"));
            manifestPath = Path.Combine(Application.persistentDataPath, "payload", "whole-catalog.json");
            Resources.descriptor = "{\"input_id\":\"authored-input\",\"attempt\":\"authored-attempt\"}";
            var bundles = new JObject();
            foreach (var pair in Graph()) bundles[pair.Key] = new JObject { ["dependencies"] = new JArray(pair.Value) };
            var manifest = JObject.Parse(Resources.descriptor);
            manifest["bundles"] = bundles;
            File.WriteAllText(manifestPath, manifest.ToString());
            File.WriteAllText(Path.Combine(Application.persistentDataPath, "payload", Root), "authored-placeholder");
            if (arguments.Single() == "restart") Restart();
            else if (arguments.Single() == "termination") Termination();
            else Refusals();
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
