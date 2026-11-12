using System;
using System.Linq;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

public struct ResourceAvailability
{
    public bool available;
    public void MakeAvailable() { available = true; WholeCatalogComposed.events.Add("available"); }
}
namespace UnityEngine
{
    public class GameObject
    {
        public RoR2.Projectile.ProjectileController controller = new RoR2.Projectile.ProjectileController();
        public T GetComponent<T>() where T : class => controller as T;
    }
}
namespace RoR2.Projectile { public class ProjectileController { public int catalogIndex; } }
namespace RoR2.ContentManagement
{
    public static class AddressablesLabels { public const string projectile = "projectile"; }
}
namespace RoR2
{
    public static class ProjectileCatalog
    {
        static GameObject[] values = new GameObject[0];
        public static ResourceAvailability catalogAvailability;
        public static int projectilePrefabCount => values.Length;
        static void SetProjectilePrefabs(GameObject[] prefabs)
        {
            WholeCatalogComposed.events.Add(prefabs.Length == 0 ? "reset" : "set");
            values = prefabs;
            for (int i = 0; i < values.Length; i++) values[i].controller.catalogIndex = i;
        }
        public static int GetProjectileIndex(GameObject value) => value.controller.catalogIndex;
        public static GameObject GetProjectilePrefab(int index) => values[index];
    }
}
public static partial class WholeCatalogComposed
{
    static Dictionary<RoR2.Projectile.ProjectileController, int> priorProjectileIndices;
    static ResourceAvailability priorProjectileAvailability;
    public static List<string> events = new List<string>();
    static JObject expectedManifest;
    static GameObject[] source = { new GameObject(), new GameObject() };
    static GameObject[] CategoryFamily(JObject manifest, string label, GameObject[] selected, Action<string> trace)
    {
        Check(ReferenceEquals(manifest, expectedManifest) && label == "projectile" && selected.Length == 0);
        events.Add("family");
        trace?.Invoke("manifest-begin");
        trace?.Invoke("manifest-ready-index-begin");
        trace?.Invoke("index-ready-assets-begin");
        trace?.Invoke("assets-ready");
        return source;
    }
    static void Check(bool value) { if (!value) throw new Exception("Projectile contract differs"); }
    static void Run(bool observed, bool publicEntry)
    {
        expectedManifest = publicEntry ? null : new JObject();
        source[0].controller.catalogIndex = -7;
        source[1].controller.catalogIndex = -11;
        var steps = new List<string>();
        events.Clear();
        int count = publicEntry ? PrepareProjectiles() : observed ? PrepareProjectiles(expectedManifest, steps.Add) : PrepareProjectiles(expectedManifest);
        Check(count == 2 && events.SequenceEqual(new[] { "family", "set", "available" }));
        Check(RoR2.ProjectileCatalog.catalogAvailability.available);
        Check(ReferenceEquals(RoR2.ProjectileCatalog.GetProjectilePrefab(0), source[0]));
        Check(ReferenceEquals(RoR2.ProjectileCatalog.GetProjectilePrefab(1), source[1]));
        if (observed) Check(steps.SequenceEqual(new[] {
            "owner-check-begin", "owner-check-ready-family-begin", "family-manifest-begin",
            "family-manifest-ready-index-begin", "family-index-ready-assets-begin", "family-assets-ready",
            "family-ready-index-snapshot-begin", "index-snapshot-ready-native-set-begin",
            "native-set-ready-availability-begin", "availability-ready-validation-begin", "validation-ready" }));
        else Check(steps.Count == 0);
        RestoreProjectiles();
        Check(RoR2.ProjectileCatalog.projectilePrefabCount == 0 && !RoR2.ProjectileCatalog.catalogAvailability.available);
        Check(source[0].controller.catalogIndex == -7 && source[1].controller.catalogIndex == -11);
        Check(events.SequenceEqual(new[] { "family", "set", "available", "reset" }));
    }
    public static void Main()
    {
        Run(false, true);
        Run(false, false);
        Run(true, false);
        Console.WriteLine("projectile observation native order identity restoration PASS");
    }
}
