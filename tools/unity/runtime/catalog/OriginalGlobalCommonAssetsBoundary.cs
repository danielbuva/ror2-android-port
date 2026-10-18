// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareOriginalGlobalCommonAssets (OriginalGlobalCommonAssetsSession); teardown CleanupOriginalGlobalCommonAssets (Dispose).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

// Retain the shipped GlobalEventManager's common proc dependencies while the
// Android session owns its imported catalog. The source initializer is the
// field/path/type authority; generated rows are tied to the accepted input.
public sealed partial class PortSession
{
    OriginalGlobalCommonAssetsSession originalGlobalCommonAssetsSession;
    OriginalGlobalCommonAssetsSession GetOriginalGlobalCommonAssetsSession()
    {
        if (originalGlobalCommonAssetsSession == null)
            originalGlobalCommonAssetsSession = new OriginalGlobalCommonAssetsSession(this);
        return originalGlobalCommonAssetsSession;
    }
    IEnumerator PrepareOriginalGlobalCommonAssets()
    {
        return GetOriginalGlobalCommonAssetsSession().PrepareOriginalGlobalCommonAssets();
    }
    void CleanupOriginalGlobalCommonAssets()
    {
        GetOriginalGlobalCommonAssetsSession().Dispose();
    }

    // Retain the owner after Dispose so partial setup, repeated cleanup and cleanup
    // without setup keep the original slot, handle and report behavior.
    sealed class OriginalGlobalCommonAssetsSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly Dictionary<FieldInfo, object> priorGlobalCommonAssets = new Dictionary<FieldInfo, object>();
        readonly List<AsyncOperationHandle> ownedGlobalCommonHandles = new List<AsyncOperationHandle>();
        public OriginalGlobalCommonAssetsSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public IEnumerator PrepareOriginalGlobalCommonAssets()
        {
            var descriptor = JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
            coordinator.Check(OriginalGlobalCommonAssetMap.InputId == (string)descriptor["input_id"],
                              "Original global common assets belong to another input");
            var owner = typeof(GlobalEventManager.CommonAssets);
            var pending = new List<Tuple<FieldInfo, AsyncOperationHandle, string>>();
            var unavailable = new List<string>();
            foreach (var row in OriginalGlobalCommonAssetMap.Rows)
            {
                coordinator.Check(row.Length == 6, "Original global common-asset mapping changed");
                var field = owner.GetField(row[2], BindingFlags.Static | BindingFlags.Public);
                var fieldType = row[4] == "GameObject"        ? typeof(GameObject)
                                : row[4] == "CharacterMaster" ? typeof(CharacterMaster)
                                : row[4] == "PickupDropTable" ? typeof(PickupDropTable)
                                                              : null;
                coordinator.Check(field != null && fieldType != null && field.FieldType == fieldType,
                                  "Original global common-asset slot changed: " + row[2]);
                if (row[5] == "0")
                {
                    unavailable.Add(row[2] + ": absent from accepted input");
                    continue;
                }
                coordinator.Check(row[5] == "1", "Original global common-asset availability changed");
                if (field.GetValue(null) != null)
                    continue;
                AsyncOperationHandle handle;
                if (row[3] == "GameObject")
                    handle = row[0] == "LegacyResourcesAPI" ? LegacyResourcesAPI.LoadAsync<GameObject>(row[1])
                                                            : Addressables.LoadAssetAsync<GameObject>(row[1]);
                else if (row[3] == "PickupDropTable")
                    handle = row[0] == "Addressables" ? Addressables.LoadAssetAsync<PickupDropTable>(row[1])
                                                      : LegacyResourcesAPI.LoadAsync<PickupDropTable>(row[1]);
                else
                    throw new Exception("Original global common-asset source type changed: " + row[2]);
                ownedGlobalCommonHandles.Add(handle);
                pending.Add(Tuple.Create(field, handle, row[3]));
            }
            var deadline = Time.realtimeSinceStartup + 60f;
            while (pending.Any(entry => !entry.Item2.IsDone) && Time.realtimeSinceStartup < deadline)
                yield return null;
            coordinator.Check(pending.All(entry => entry.Item2.IsDone), "Original global common-asset load timed out");
            foreach (var entry in pending)
            {
                var handle = entry.Item2;
                coordinator.Check(handle.Status == AsyncOperationStatus.Succeeded && handle.Result is UnityEngine.Object,
                                  "Original global common asset failed: " + entry.Item1.Name);
                object value = handle.Result;
                if (entry.Item1.FieldType == typeof(CharacterMaster))
                {
                    var prefab = value as GameObject;
                    value = prefab ? prefab.GetComponent<CharacterMaster>() : null;
                    coordinator.Check(value != null, "Original global common master component absent: " + entry.Item1.Name);
                }
                coordinator.Check(entry.Item1.FieldType.IsInstanceOfType(value) && entry.Item1.GetValue(null) == null,
                                  "Original global common-asset type/owner changed: " + entry.Item1.Name);
                priorGlobalCommonAssets.Add(entry.Item1, null);
                entry.Item1.SetValue(null, value);
            }
            coordinator.r.world.globalCommonAssetSlots = priorGlobalCommonAssets.Count;
            coordinator.r.world.globalCommonAssetUnavailable = unavailable.ToArray();
            coordinator.Save();
        }
        public void Dispose()
        {
            foreach (var entry in priorGlobalCommonAssets)
                entry.Key.SetValue(null, entry.Value);
            priorGlobalCommonAssets.Clear();
            foreach (var handle in ownedGlobalCommonHandles)
                if (handle.IsValid())
                    Addressables.Release(handle);
            ownedGlobalCommonHandles.Clear();
            if (coordinator.r.world != null)
                coordinator.r.world.globalCommonAssetCleaned = true;
        }
    }
}
