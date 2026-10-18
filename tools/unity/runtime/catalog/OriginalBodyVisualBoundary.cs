// Subsystem: catalog/resources (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareOriginalBodyVisualReferences (OriginalBodyVisualSession); teardown CleanupOriginalBodyVisualReferences (Dispose).
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

// Bind the original CharacterBody and HealthComponent visual references from
// their exact shipped initializer field/path pairs. Handles stay session-owned.
public sealed partial class PortSession
{
    OriginalBodyVisualSession originalBodyVisualSession;
    OriginalBodyVisualSession GetOriginalBodyVisualSession()
    {
        if (originalBodyVisualSession == null)
            originalBodyVisualSession = new OriginalBodyVisualSession(this);
        return originalBodyVisualSession;
    }
    IEnumerator PrepareOriginalBodyVisualReferences()
    {
        return GetOriginalBodyVisualSession().PrepareOriginalBodyVisualReferences();
    }
    void CleanupOriginalBodyVisualReferences()
    {
        GetOriginalBodyVisualSession().Dispose();
    }

    // Retain the owner after Dispose so partial setup, repeated cleanup and cleanup
    // without setup keep the original slot, handle and report behavior.
    sealed class OriginalBodyVisualSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly Dictionary<FieldInfo, GameObject> priorOriginalVisualSlots = new Dictionary<FieldInfo, GameObject>();
        readonly List<AsyncOperationHandle<GameObject>> ownedOriginalVisualHandles = new List<AsyncOperationHandle<GameObject>>();
        public OriginalBodyVisualSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public IEnumerator PrepareOriginalBodyVisualReferences()
        {
            var descriptor = JObject.Parse(Resources.Load<TextAsset>("WholeCatalogBootstrap").text);
            var input = (string)descriptor["input_id"];
            coordinator.Check(OriginalBodyVisualMap.InputId == input && OriginalHealthVisualMap.InputId == input,
                              "Original visual maps belong to another input");
            var pending = new List<Tuple<FieldInfo, AsyncOperationHandle<GameObject>, bool>>();
            var bodyUnavailable = new List<string>();
            var healthUnavailable = new List<string>();
            foreach (var family in new[] { new { type = typeof(CharacterBody), rows = OriginalBodyVisualMap.Rows },
                                           new { type = typeof(HealthComponent), rows = OriginalHealthVisualMap.Rows } })
            {
                var owner = family.type.GetNestedType("AssetReferences", BindingFlags.NonPublic);
                coordinator.Check(owner != null, "Original visual-reference owner changed: " + family.type.Name);
                bool health = family.type == typeof(HealthComponent);
                foreach (var row in family.rows)
                {
                    coordinator.Check(row.Length == 3, "Original visual mapping changed: " + family.type.Name);
                    var field = owner.GetField(row[2], BindingFlags.Public | BindingFlags.Static);
                    coordinator.Check(field != null && field.FieldType == typeof(GameObject),
                                      "Original visual slot changed: " + family.type.Name + "." + row[2]);
                    // Existing owned adapters retain their original bindings.
                    if ((GameObject)field.GetValue(null))
                        continue;
                    string key;
                    if (row[0] == "LegacyResourcesAPI")
                    {
                        if (!LegacyResourcesAPI.GetGuid(row[1], out key))
                        {
                            (health ? healthUnavailable : bodyUnavailable).Add(row[2] + ": legacy alias absent");
                            continue;
                        }
                    }
                    else
                        coordinator.Check(row[0] == "Addressables", "Unknown original visual loader");
                    var handle = row[0] == "LegacyResourcesAPI" ? LegacyResourcesAPI.LoadAsync<GameObject>(row[1])
                                                                : Addressables.LoadAssetAsync<GameObject>(row[1]);
                    ownedOriginalVisualHandles.Add(handle);
                    pending.Add(Tuple.Create(field, handle, health));
                }
            }
            var deadline = Time.realtimeSinceStartup + 45f;
            while (pending.Any(entry => !entry.Item2.IsDone) && Time.realtimeSinceStartup < deadline)
                yield return null;
            coordinator.Check(pending.All(entry => entry.Item2.IsDone), "Original visual-reference load timed out");
            foreach (var entry in pending)
            {
                var handle = entry.Item2;
                if (handle.Status != AsyncOperationStatus.Succeeded || !handle.Result)
                {
                    (entry.Item3 ? healthUnavailable : bodyUnavailable).Add(entry.Item1.Name + ": original asset load failed");
                    continue;
                }
                coordinator.Check(!((GameObject)entry.Item1.GetValue(null)), "Original visual slot changed during load");
                priorOriginalVisualSlots.Add(entry.Item1, null);
                entry.Item1.SetValue(null, handle.Result);
            }
            var exposed = typeof(CharacterBody)
                              .GetNestedType("AssetReferences", BindingFlags.NonPublic)
                              .GetField("mercExposeEffectPrefab", BindingFlags.Public | BindingFlags.Static);
            coordinator.Check(exposed != null && (GameObject)exposed.GetValue(null),
                              "Original Merc expose visual missing after source reference load");
            coordinator.Check(healthUnavailable.Count == 0,
                              "Original HealthComponent visual-reference closure failed: " + string.Join(",", healthUnavailable.ToArray()));
            coordinator.r.world.bodyVisualSlots =
                priorOriginalVisualSlots.Keys.Count(field => field.DeclaringType.DeclaringType == typeof(CharacterBody));
            coordinator.r.world.healthVisualSlots =
                priorOriginalVisualSlots.Keys.Count(field => field.DeclaringType.DeclaringType == typeof(HealthComponent));
            coordinator.r.world.bodyVisualUnavailable = bodyUnavailable.ToArray();
            coordinator.r.world.healthVisualUnavailable = healthUnavailable.ToArray();
            coordinator.Save();
        }
        public void Dispose()
        {
            foreach (var entry in priorOriginalVisualSlots)
                entry.Key.SetValue(null, entry.Value);
            priorOriginalVisualSlots.Clear();
            foreach (var handle in ownedOriginalVisualHandles)
                if (handle.IsValid())
                    Addressables.Release(handle);
            ownedOriginalVisualHandles.Clear();
            if (coordinator.r.world != null)
                coordinator.r.world.bodyVisualCleaned = true;
        }
    }
}
