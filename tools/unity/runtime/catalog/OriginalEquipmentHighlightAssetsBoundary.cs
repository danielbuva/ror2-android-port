// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareOriginalEquipmentHighlightAssets; teardown CleanupOriginalEquipmentHighlightAssets after body/model destruction.
// This loads only the
// three source-owned GameObject slots; it assigns only slots observed empty,
// never reindexes EquipmentCatalog, and never invokes EquipmentCatalog.Init.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceLocations;

[Serializable]
public sealed class OriginalEquipmentHighlightAssetsReport
{
    public string state;
    public string[] requestedFields, assignedFields;
    public bool ready, cleaned;
}

public sealed partial class PortSession
{
    OriginalEquipmentHighlightAssetsSession originalEquipmentHighlightAssetsSession;

    IEnumerator PrepareOriginalEquipmentHighlightAssets()
    {
        if (originalEquipmentHighlightAssetsSession == null)
            originalEquipmentHighlightAssetsSession = new OriginalEquipmentHighlightAssetsSession(this);
        return originalEquipmentHighlightAssetsSession.Prepare();
    }

    void CleanupOriginalEquipmentHighlightAssets(Exception originalFailure = null)
    {
        if (originalEquipmentHighlightAssetsSession == null)
            return;
        try
        {
            Check(!host && !ownedDetachedModel && !worldPlayer,
                  "Equipment-highlight assets must remain owned until original body/model cleanup completes");
        }
        catch (Exception cleanupGuardFailure)
        {
            if (originalFailure != null)
                throw new AggregateException("Preparation and equipment-highlight cleanup guard both failed",
                    originalFailure, cleanupGuardFailure);
            throw;
        }
        originalEquipmentHighlightAssetsSession.Dispose(originalFailure);
    }

    sealed class OriginalEquipmentHighlightAssetsSession : IDisposable
    {
        sealed class SlotLoad
        {
            public FieldInfo field;
            public string addressKey;
            public IResourceLocation location;
            public AsyncOperationHandle<GameObject> handle;
        }

        sealed class SlotSpec
        {
            public string field, addressKey, primaryKey, internalId;
        }

        static readonly SlotSpec[] Rows =
        {
            new SlotSpec { field = "equipmentHighlightPrefab", addressKey = "164a5db278443b1469a210be383c4b0e",
                primaryKey = "RoR2/Base/UI/HighlightEquipment.prefab", internalId = "Assets/WholeGame/RoR2/Base/UI/AR/HighlightEquipment.prefab" },
            new SlotSpec { field = "lunarEquipmentHighlightPrefab", addressKey = "0cb44955b08ec6a4a9c3e04c5f73b815",
                primaryKey = "RoR2/Base/UI/HighlightLunarItem.prefab", internalId = "Assets/WholeGame/RoR2/Base/UI/AR/HighlightLunarItem.prefab" },
            new SlotSpec { field = "bossEquipmentHighlightPrefab", addressKey = "5c3d7eca2b1255148958484c738869d8",
                primaryKey = "RoR2/Base/UI/HighlightBossItem.prefab", internalId = "Assets/WholeGame/RoR2/Base/UI/AR/HighlightBossItem.prefab" }
        };

        readonly PortSession coordinator;
        OriginalEquipmentHighlightAssetsReport report;
        readonly List<AsyncOperationHandle<GameObject>> ownedHandles = new List<AsyncOperationHandle<GameObject>>();
        readonly Dictionary<FieldInfo, AsyncOperationHandle<GameObject>> fieldHandles = new Dictionary<FieldInfo, AsyncOperationHandle<GameObject>>();
        readonly Dictionary<FieldInfo, GameObject> assignedSlots = new Dictionary<FieldInfo, GameObject>();
        readonly List<Exception> cleanupFailureHistory = new List<Exception>();
        bool started, prepared, disposed, cleanupComplete;
        Exception cleanupFailure;
        IResourceLocator capturedLocator;


        public OriginalEquipmentHighlightAssetsSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }

        public IEnumerator Prepare()
        {
            // Reserve before touching the report or issuing a request. A second
            // iterator cannot race the first one while its Addressables loads wait.
            coordinator.Check(!disposed && !started, "Equipment-highlight owner already used or disposed");
            started = true;
            report = coordinator.r.originalEquipmentHighlightAssets;
            if (report == null)
            {
                report = new OriginalEquipmentHighlightAssetsReport();
                coordinator.r.originalEquipmentHighlightAssets = report;
            }
            report.state = "preparing";
            report.ready = false;
            report.cleaned = false;
            coordinator.Save();
            coordinator.Check(WholeCatalogComposed.IsConfigured,
                             "Equipment-highlight loads require the active whole-catalog bundle/locator owner");
            capturedLocator = WholeCatalogLoader.locator;
            coordinator.Check(capturedLocator != null,
                              "Equipment-highlight loads require the captured active whole-catalog locator");

            var pending = new List<SlotLoad>();
            var owner = typeof(EquipmentCatalog);
            foreach (var row in Rows)
            {
                var field = owner.GetField(row.field, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                coordinator.Check(field != null && field.FieldType == typeof(GameObject),
                                 "Original equipment-highlight static slot changed: " + row.field);
                object currentObject = field.GetValue(null);
                // This route supplies SetEquipmentDefs without the original Init.
                // Prepopulated slots belong to another owner; do not adopt them
                // or carry their references across this catalog's later unload.
                coordinator.Check(ReferenceEquals(currentObject, null),
                                  "Unowned original equipment-highlight slot before preparation: " + row.field);
                IList<IResourceLocation> locations;
                coordinator.Check(capturedLocator.Locate(row.addressKey, typeof(GameObject), out locations) &&
                                  locations != null && locations.Count == 1,
                                  "Equipment-highlight address key did not resolve uniquely: " + row.field);
                var location = locations[0];
                coordinator.Check(location != null && location.ResourceType == typeof(GameObject) &&
                                  String.Equals(location.PrimaryKey, row.primaryKey, StringComparison.Ordinal) &&
                                  String.Equals(location.InternalId, row.internalId, StringComparison.Ordinal),
                                  "Equipment-highlight location metadata differs: " + row.field);
                pending.Add(new SlotLoad { field = field, addressKey = row.addressKey, location = location });
            }

            report.requestedFields = pending.Select(slot => slot.field.Name).ToArray();
            report.state = "loading";
            coordinator.Save();
            foreach (var slot in pending)
            {
                EnsureNotDisposed("before Addressables request");
                slot.handle = Addressables.LoadAssetAsync<GameObject>(slot.location);
                ownedHandles.Add(slot.handle);
                fieldHandles.Add(slot.field, slot.handle);
            }
            float deadline = Time.realtimeSinceStartup + 60f;
            while (pending.Any(slot => !slot.handle.IsDone) && Time.realtimeSinceStartup < deadline)
            {
                EnsureNotDisposed("while waiting for Addressables");
                yield return null;
                // Dispose may run while this iterator is suspended. Never inspect
                // released handles or publish their results after cancellation.
                if (disposed)
                {
                    yield break;
                }
            }
            if (disposed)
            {
                yield break;
            }
            if (!pending.All(slot => slot.handle.IsDone))
                throw new TimeoutException("Original equipment-highlight asset load timed out: " +
                                           string.Join(",", pending.Where(slot => !slot.handle.IsDone)
                                                               .Select(slot => slot.field.Name).ToArray()));
            foreach (var slot in pending)
                coordinator.Check(slot.handle.Status == AsyncOperationStatus.Succeeded && slot.handle.Result,
                                  "Original equipment-highlight asset failed: " + slot.field.Name + " key=" + slot.addressKey);
            coordinator.Check(WholeCatalogComposed.IsConfigured && ReferenceEquals(capturedLocator, WholeCatalogLoader.locator),
                              "Active whole-catalog locator changed while equipment-highlight assets loaded");

            // Refuse any competing initializer, even if it published the same
            // asset: its callback/handle lifetime has not been adopted here.
            foreach (var slot in pending)
            {
                object current = slot.field.GetValue(null);
                coordinator.Check(ReferenceEquals(current, null),
                                  "Original equipment-highlight slot changed during load: " + slot.field.Name);
            }

            EnsureNotDisposed("before static slot publication");
            // No yield occurs between the complete-set validation and publication.
            foreach (var slot in pending)
            {
                if (!ReferenceEquals(slot.field.GetValue(null), null))
                    continue;
                assignedSlots.Add(slot.field, slot.handle.Result);
                slot.field.SetValue(null, slot.handle.Result);
            }
            foreach (var row in Rows)
            {
                var field = owner.GetField(row.field, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                coordinator.Check(field != null && field.GetValue(null) is GameObject prefab && prefab,
                                  "Original equipment-highlight slot unavailable after preparation: " + row.field);
            }
            EnsureNotDisposed("before ready publication");
            prepared = true;
            report.assignedFields = assignedSlots.Keys.Select(field => field.Name).ToArray();
            report.ready = true;
            report.state = "ready";
            coordinator.Save();
        }

        void EnsureNotDisposed(string point)
        {
            coordinator.Check(!disposed, "Equipment-highlight preparation cancelled " + point);
        }

        public void Dispose()
        {
            Dispose(null);
        }

        public void Dispose(Exception originalFailure)
        {
            if (cleanupComplete)
            {
                return;
            }
            disposed = true;
            var failures = new List<Exception>();
            foreach (var pair in assignedSlots.ToArray())
            {
                try
                {
                    if (!ReferenceEquals(pair.Key.GetValue(null), pair.Value))
                    {
                        failures.Add(new InvalidOperationException(
                            "Original equipment-highlight slot changed before cleanup: " + pair.Key.Name));
                        continue;
                    }
                    pair.Key.SetValue(null, null);
                    assignedSlots.Remove(pair.Key);
                }
                catch (Exception exception)
                {
                    failures.Add(exception);
                }
            }
            // Refuse catalog retirement if a competing initializer left any
            // source slot populated. It is not ours to clear or unload beneath.
            foreach (var row in Rows)
            {
                try
                {
                    var field = typeof(EquipmentCatalog).GetField(
                        row.field, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                    if (field == null || field.FieldType != typeof(GameObject) || !ReferenceEquals(field.GetValue(null), null))
                        failures.Add(new InvalidOperationException(
                            "Unowned original equipment-highlight slot prevents catalog retirement: " + row.field));
                }
                catch (Exception exception)
                {
                    failures.Add(exception);
                }
            }
            foreach (var handle in ownedHandles.ToArray())
            {
                // Keep a request alive while its result may still occupy one of
                // this owner's static slots. A later Dispose can retry restoring
                // that exact slot before releasing the handle.
                bool slotStillOwned = fieldHandles.Any(pair => pair.Value.Equals(handle) && assignedSlots.ContainsKey(pair.Key));
                if (slotStillOwned)
                    continue;
                try
                {
                    if (handle.IsValid())
                        Addressables.Release(handle);
                    ownedHandles.Remove(handle);
                }
                catch (Exception exception)
                {
                    failures.Add(exception);
                }
            }
            cleanupFailureHistory.AddRange(failures);
            cleanupFailure = cleanupFailureHistory.Count == 0 ? null : new AggregateException(cleanupFailureHistory);
            if (report != null)
            {
                report.cleaned = cleanupFailure == null;
                report.ready = false;
                report.state = cleanupFailure != null ? "cleanup-failed" : (prepared ? "cleaned" : "cancelled-cleaned");
                try
                {
                    coordinator.Save();
                }
                catch (Exception exception)
                {
                    failures.Add(exception);
                    cleanupFailureHistory.Add(exception);
                    cleanupFailure = new AggregateException(cleanupFailureHistory);
                    report.cleaned = false;
                    report.ready = false;
                    report.state = "cleanup-failed";
                }
            }
            cleanupComplete = cleanupFailure == null && ownedHandles.Count == 0 && assignedSlots.Count == 0;
            if (cleanupComplete)
            {
                fieldHandles.Clear();
                capturedLocator = null;
            }
            if (cleanupFailure != null)
            {
                if (originalFailure != null)
                    throw new AggregateException("Preparation and equipment-highlight cleanup both failed",
                        originalFailure, cleanupFailure);
                throw new AggregateException("Original equipment-highlight cleanup failed", cleanupFailure);
            }
        }
    }
}
