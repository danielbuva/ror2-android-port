using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public bool destroyed;
        public static implicit operator bool(Object value) => value != null && !value.destroyed;
    }
    public sealed class GameObject : Object { }
    public static class Time { public static float realtimeSinceStartup; }
}

namespace UnityEngine.ResourceManagement.AsyncOperations
{
    public enum AsyncOperationStatus { None, Succeeded, Failed }
    public struct AsyncOperationHandle<T>
    {
        internal TestOperation<T> operation;
        public bool IsDone => operation.done;
        public AsyncOperationStatus Status => operation.status;
        public T Result => operation.result;
        public bool IsValid() => operation != null && operation.valid;
    }
    public sealed class TestOperation<T>
    {
        public bool done, valid = true;
        public AsyncOperationStatus status;
        public T result;
        public int releases;
        public bool throwOnRelease;
    }
}

namespace UnityEngine.ResourceManagement.ResourceLocations
{
    using System;
    using System.Collections.Generic;
    public interface IResourceLocation
    {
        Type ResourceType { get; }
        string PrimaryKey { get; }
        string InternalId { get; }
    }
    public sealed class TestResourceLocation : IResourceLocation
    {
        public Type ResourceType { get; set; }
        public string PrimaryKey { get; set; }
        public string InternalId { get; set; }
    }
}

namespace UnityEngine.AddressableAssets.ResourceLocators
{
    using System;
    using System.Collections.Generic;
    using UnityEngine.ResourceManagement.ResourceLocations;
    public interface IResourceLocator
    {
        bool Locate(object key, Type type, out IList<IResourceLocation> locations);
    }
    public sealed class ResourceLocationMap : IResourceLocator
    {
        readonly Dictionary<string, List<IResourceLocation>> locations = new Dictionary<string, List<IResourceLocation>>();
        public void Add(string key, IResourceLocation location)
        {
            if (!locations.ContainsKey(key)) locations.Add(key, new List<IResourceLocation>());
            locations[key].Add(location);
        }
        public void Remove(string key) { locations.Remove(key); }
        public bool Locate(object key, Type type, out IList<IResourceLocation> result)
        {
            List<IResourceLocation> found;
            if (key is string name && locations.TryGetValue(name, out found))
            {
                result = found;
                return true;
            }
            result = null;
            return false;
        }
    }
}

namespace UnityEngine.AddressableAssets
{
    using UnityEngine.ResourceManagement.AsyncOperations;
    using UnityEngine.ResourceManagement.ResourceLocations;
    using UnityEngine.AddressableAssets.ResourceLocators;
    public static class Addressables
    {
        public static readonly List<TestOperation<UnityEngine.GameObject>> operations = new List<TestOperation<UnityEngine.GameObject>>();
        public static readonly List<IResourceLocation> requestedLocations = new List<IResourceLocation>();
        public static Func<string, TestOperation<UnityEngine.GameObject>> create;
        public static string throwOnKey;
        public static AsyncOperationHandle<T> LoadAssetAsync<T>(IResourceLocation location)
        {
            if (location.PrimaryKey == throwOnKey) throw new InvalidOperationException("synthetic Addressables request failure");
            requestedLocations.Add(location);
            var operation = create(location.PrimaryKey);
            operations.Add(operation);
            return new AsyncOperationHandle<T> { operation = (TestOperation<T>)(object)operation };
        }
        public static void Release<T>(AsyncOperationHandle<T> handle)
        {
            if (handle.operation.throwOnRelease) throw new InvalidOperationException("synthetic release failure");
            handle.operation.releases++;
            handle.operation.valid = false;
        }
        public static void Reset()
        {
            operations.Clear();
            requestedLocations.Clear();
            create = null;
            throwOnKey = null;
            UnityEngine.Time.realtimeSinceStartup = 0;
        }
    }
}

namespace RoR2
{
    public sealed class EquipmentDef { }
    public static class EquipmentCatalog
    {
        static UnityEngine.GameObject equipmentHighlightPrefab;
        static UnityEngine.GameObject lunarEquipmentHighlightPrefab;
        static UnityEngine.GameObject bossEquipmentHighlightPrefab;
        static string wrongTypeField;
    }
    public static class WholeCatalogComposed { public static bool IsConfigured = true; }
}

public sealed partial class PortSession
{
    public sealed class TestReport { public OriginalEquipmentHighlightAssetsReport originalEquipmentHighlightAssets; }
    public TestReport r = new TestReport();
    public int saves;
    public UnityEngine.GameObject host, ownedDetachedModel, worldPlayer;
    public void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
    public void Save() { saves++; }
}

public static class WholeCatalogLoader
{
    public static UnityEngine.AddressableAssets.ResourceLocators.ResourceLocationMap locator;
}
