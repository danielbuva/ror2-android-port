// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup CollectPriorSessionGarbage, ObserveSessionResources; teardown TrackCompletedSessionReferences, ReclaimCompletedSessionResources.
using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Profiling;

// Measurements and reclamation only at an already completed owned session.
// No gameplay pools, live content, process caches or unrelated files are cleared.
public sealed partial class PortSession
{
    [Serializable]
    public class SessionResourceSample
    {
        public string phase;
        public float seconds;
        public long allocated, reserved, managed;
        public long managedTotal;
        public int collections;
        public string gcMode;
        public bool incremental;
        public float collectionSeconds;
        public int trackedCompletedSessions, liveCompletedProbes, liveCompletedReports;
        public int materials, textures, shaders, gameObjects, bundles;
        public string[] bundleNames;
        public int catalogGenerations, catalogLocatorsAlive, catalogManifestsAlive, activeLocators, detachedCatalogOperations;
        public string[] ownedCallbackRoots, callbackRootReadFailures, callbackOwnerScope, statQueueCounts;
        // "Owner.field:subscribers/destroyedTargets" for nonempty scanned static callbacks.
        public string[] staticCallbackCounts;
        // Destroyed-BaseAI depossession entries removed before this sample (J775); -1 if not run.
        public int prunedDestroyedDepossessionSubscribers = -1;
        // "Owner.field:removed/remaining" for pruned original static registries (J787).
        public string[] prunedDestroyedRegistryEntries;
        // Opt-in completed-session root walk (diagnosticCompletedRootWalkSession selector); empty otherwise.
        public bool rootWalkRan, rootWalkTruncated;
        public int rootWalkNodes, rootWalkRoots, rootWalkReadFailures;
        public float rootWalkSeconds;
        public string[] rootWalkPaths, rootWalkFailureSamples, rootWalkCensus, rootWalkRootAttribution;
        // Private diagnostic snapshots at menus 2/4; not ordinary growth/performance samples.
        public bool memorySnapshotRequested, memorySnapshotComplete, memorySnapshotSuccess;
        public string memorySnapshotFile, memorySnapshotError;
    }
    [Serializable]
    class RootWalkSelection
    {
        public string attempt;
        public int diagnosticCompletedRootWalkSession;
        public bool diagnosticCompletedMemorySnapshots;
    }
    const int RootWalkNodeBudget = 2000000;
    // Reads only the launch selector's opt-in session index; the coordinator's own parsing is
    // unchanged. Reading an uninitialized static field runs that type's static constructor, which
    // can register original callbacks (J773), so the walk runs only at the requested final menu.
    RootWalkSelection ReadResourceDiagnostics()
    {
        var path = System.IO.Path.Combine(Application.persistentDataPath, "movement-batch-selection.json");
        if (r == null || !System.IO.File.Exists(path))
            return null;
        try
        {
            var selection = JsonUtility.FromJson<RootWalkSelection>(System.IO.File.ReadAllText(path));
            return selection != null && selection.attempt == r.attempt ? selection : null;
        }
        catch (Exception)
        {
            return null;
        }
    }
    bool CompletedRootWalkRequested()
    {
        var selection = ReadResourceDiagnostics();
        return selection != null && selection.diagnosticCompletedRootWalkSession > 1 &&
               selection.diagnosticCompletedRootWalkSession == sessionIndex;
    }
    void CaptureCompletedMemorySnapshot(SessionResourceSample sample)
    {
        var selection = ReadResourceDiagnostics();
        if (selection == null || !selection.diagnosticCompletedMemorySnapshots || (sessionIndex != 2 && sessionIndex != 4))
            return;
        sample.memorySnapshotRequested = true;
        if (!Debug.isDebugBuild || Run.instance || NetworkServer.active || NetworkClient.active)
        {
            sample.memorySnapshotComplete = true;
            sample.memorySnapshotError = "Snapshot requires an idle development menu.";
            return;
        }
        try
        {
            var directory = System.IO.Path.Combine(Application.persistentDataPath, "diagnostics", "session-memory");
            System.IO.Directory.CreateDirectory(directory);
            sample.memorySnapshotFile = "session-" + sessionIndex + "-" + Guid.NewGuid().ToString("N") + ".snap";
            var path = System.IO.Path.Combine(directory, sample.memorySnapshotFile);
            UnityEngine.Profiling.Memory.Experimental.MemoryProfiler.TakeSnapshot(path, (returned, success) =>
            {
                sample.memorySnapshotComplete = true;
                sample.memorySnapshotSuccess = success && returned == path && System.IO.File.Exists(path) && new System.IO.FileInfo(path).Length > 0;
                if (!sample.memorySnapshotSuccess) sample.memorySnapshotError = "Native snapshot capture failed.";
                // A synchronous callback precedes the startup report's session assignment;
                // its next Save publishes completion without writing a transient session 0.
                if (this && r != null && r.session == sessionIndex) Save();
            }, UnityEngine.Profiling.Memory.Experimental.CaptureFlags.ManagedObjects | UnityEngine.Profiling.Memory.Experimental.CaptureFlags.NativeObjects);
        }
        catch (Exception error)
        {
            sample.memorySnapshotComplete = true;
            sample.memorySnapshotError = error.GetType().Name;
        }
    }
    void WalkCompletedSessionRoots(SessionResourceSample sample)
    {
        var targets = new System.Collections.Generic.List<System.Collections.Generic.KeyValuePair<string, object>>();
        for (int i = 0; i < completedSessionReferences.Count; i++)
        {
            var probe = completedSessionReferences[i][0].Target;
            var report = completedSessionReferences[i][1].Target;
            if (probe != null)
                targets.Add(new System.Collections.Generic.KeyValuePair<string, object>("completed[" + i + "].probe", probe));
            if (report != null)
                targets.Add(new System.Collections.Generic.KeyValuePair<string, object>("completed[" + i + "].report", report));
        }
        // With no retained completed session the same walk still records a reachable-type census.
        if (Run.instance || NetworkServer.active || NetworkClient.active)
            return;
        // Live engine-held managed objects (including this coordinator) are roots too.
        var extra = new System.Collections.Generic.List<System.Collections.Generic.KeyValuePair<string, object>>();
        foreach (var behaviour in Resources.FindObjectsOfTypeAll<MonoBehaviour>())
            extra.Add(new System.Collections.Generic.KeyValuePair<string, object>(
                "live:" + behaviour.GetType().FullName + "@" + (behaviour ? behaviour.gameObject.name : "destroyed"), behaviour));
        foreach (var asset in Resources.FindObjectsOfTypeAll<ScriptableObject>())
            extra.Add(new System.Collections.Generic.KeyValuePair<string, object>("asset:" + asset.GetType().FullName, asset));
        var types = new System.Collections.Generic.List<Type>();
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            try
            {
                types.AddRange(assembly.GetTypes());
            }
            catch (ReflectionTypeLoadException e)
            {
                types.AddRange(e.Types.Where(x => x != null));
            }
        }
        var began = Time.realtimeSinceStartup;
        var result = CompletedSessionRootWalk.Find(types, extra, targets, RootWalkNodeBudget, 16, 60);
        sample.rootWalkRan = true;
        sample.rootWalkSeconds = Time.realtimeSinceStartup - began;
        sample.rootWalkNodes = result.nodes;
        sample.rootWalkRoots = result.roots;
        sample.rootWalkTruncated = result.truncated;
        sample.rootWalkReadFailures = result.readFailures;
        sample.rootWalkPaths = result.paths;
        sample.rootWalkFailureSamples = result.failureSamples;
        sample.rootWalkCensus = result.census;
        sample.rootWalkRootAttribution = result.rootAttribution;
    }
    static readonly System.Collections.Generic.List<WeakReference[]> completedSessionReferences =
        new System.Collections.Generic.List<WeakReference[]>();
    void TrackCompletedSessionReferences()
    {
        completedSessionReferences.RemoveAll(x => !x[0].IsAlive && !x[1].IsAlive);
        if (completedSessionReferences.Count < 128)
            completedSessionReferences.Add(new[] { new WeakReference(this), new WeakReference(r) });
    }
    void CollectPriorSessionGarbage()
    {
        if (completedSessionReferences.Count == 0)
            return;
        Check(!Run.instance && !NetworkServer.active && !NetworkClient.active, "Refuse prior-session collection in live gameplay");
        if (UnityEngine.Scripting.GarbageCollector.GCMode != UnityEngine.Scripting.GarbageCollector.Mode.Disabled)
            GC.Collect();
    }
    void ObserveSessionResources(string phase)
    {
        if (r.sessionResources == null)
            r.sessionResources = new System.Collections.Generic.List<SessionResourceSample>();
        var roots = new System.Collections.Generic.List<string>();
        var callbackCounts = new System.Collections.Generic.List<string>();
        var failures = new System.Collections.Generic.List<string>();
        // Read only already-used gameplay callback owners; never initialize unrelated
        // subsystem types, invoke callbacks or remove original handlers diagnostically.
        var callbackOwners = new[] { typeof(RoR2Application),
                                     typeof(GlobalEventManager),
                                     typeof(Run),
                                     typeof(CharacterBody),
                                     typeof(CharacterMaster),
                                     typeof(SceneCatalog),
                                     typeof(Stage),
                                     typeof(MasterSummon),
                                     typeof(BossGroup),
                                     typeof(SceneExitController),
                                     typeof(TeleporterInteraction),
                                     typeof(Inventory),
                                     typeof(DotController),
                                     typeof(EquipmentSlot),
                                     typeof(VehicleSeat) };
        if (completedSessionReferences.Count > 0)
            foreach (var type in callbackOwners)
                foreach (var field in type.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)
                             .Where(x => typeof(Delegate).IsAssignableFrom(x.FieldType)))
                {
                    Delegate callback;
                    try
                    {
                        callback = field.GetValue(null) as Delegate;
                    }
                    catch (Exception e)
                    {
                        failures.Add(type.FullName + "." + field.Name + ":" + e.GetType().Name);
                        continue;
                    }
                    if (callback == null)
                        continue;
                    // Count subscribers, and those whose target is a destroyed Unity object, to
                    // attribute growth that outlives every completed session (J773). Read only.
                    var entries = callback.GetInvocationList();
                    int destroyed = entries.Count(x => x.Target is UnityEngine.Object && !(UnityEngine.Object)x.Target);
                    callbackCounts.Add(type.Name + "." + field.Name + ":" + entries.Length + "/" + destroyed);
                    foreach (var entry in entries)
                        for (int i = 0; i < completedSessionReferences.Count; i++)
                        {
                            var probe = completedSessionReferences[i][0].Target;
                            var report = completedSessionReferences[i][1].Target;
                            if (probe == null && report == null)
                                continue;
                            var path = FindCompletedCallbackReference(entry.Target, probe, report, 0);
                            if (path != null)
                                roots.Add(type.FullName + "." + field.Name + " -> " + entry.Method.Name + " -> completed[" + i + "]" +
                                          path);
                        }
                }
        // Addressables is already live in this composition. Inspect only delegate fields;
        // do not walk asset graphs, initialize other services or change cached operations.
        if (completedSessionReferences.Count > 0)
        {
            var manager = UnityEngine.AddressableAssets.Addressables.ResourceManager;
            foreach (var field in manager.GetType()
                         .GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                         .Where(x => typeof(Delegate).IsAssignableFrom(x.FieldType)))
            {
                Delegate callback;
                try
                {
                    callback = field.GetValue(manager) as Delegate;
                }
                catch (Exception e)
                {
                    failures.Add(manager.GetType().FullName + "." + field.Name + ":" + e.GetType().Name);
                    continue;
                }
                if (callback == null)
                    continue;
                foreach (var entry in callback.GetInvocationList())
                    for (int i = 0; i < completedSessionReferences.Count; i++)
                    {
                        var path = FindCompletedCallbackReference(entry.Target, completedSessionReferences[i][0].Target,
                                                                  completedSessionReferences[i][1].Target, 0);
                        if (path != null)
                            roots.Add(manager.GetType().FullName + "." + field.Name + " -> " + entry.Method.Name + " -> completed[" + i +
                                      "]" + path);
                    }
            }
        }
        var catalogs = WholeCatalogComposed.ReleasedCatalogRetention();
        r.sessionResources.Add(new SessionResourceSample {
            phase = phase,
            seconds = Time.realtimeSinceStartup,
            ownedCallbackRoots = roots.ToArray(),
            staticCallbackCounts = callbackCounts.ToArray(),
            callbackRootReadFailures = failures.ToArray(),
            callbackOwnerScope = callbackOwners.Select(x => x.FullName)
                                     .Concat(new[] { "UnityEngine.ResourceManagement.ResourceManager (instance delegates)" })
                                     .ToArray(),
            statQueueCounts = ReadStatQueueCounts(),
            trackedCompletedSessions = completedSessionReferences.Count,
            liveCompletedProbes = completedSessionReferences.Count(x => x[0].IsAlive),
            liveCompletedReports = completedSessionReferences.Count(x => x[1].IsAlive),
            catalogGenerations = catalogs[0],
            catalogLocatorsAlive = catalogs[1],
            catalogManifestsAlive = catalogs[2],
            activeLocators = catalogs[3],
            detachedCatalogOperations = catalogs[4],
            allocated = Profiler.GetTotalAllocatedMemoryLong(),
            reserved = Profiler.GetTotalReservedMemoryLong(),
            managed = Profiler.GetMonoUsedSizeLong(),
            managedTotal = GC.GetTotalMemory(false),
            collections = GC.CollectionCount(0),
            gcMode = UnityEngine.Scripting.GarbageCollector.GCMode.ToString(),
            incremental = UnityEngine.Scripting.GarbageCollector.isIncremental,
            materials = Resources.FindObjectsOfTypeAll<Material>().Length,
            textures = Resources.FindObjectsOfTypeAll<Texture>().Length,
            shaders = Resources.FindObjectsOfTypeAll<Shader>().Length,
            gameObjects = Resources.FindObjectsOfTypeAll<GameObject>().Length,
            bundles = AssetBundle.GetAllLoadedAssetBundles().Count(),
            bundleNames = AssetBundle.GetAllLoadedAssetBundles().Select(x => x.name).OrderBy(x => x).ToArray()
        });
        if (phase == "before-presentation" && completedSessionReferences.Count > 0)
        {
            if (CompletedRootWalkRequested()) WalkCompletedSessionRoots(r.sessionResources.Last());
            CaptureCompletedMemorySnapshot(r.sessionResources.Last());
        }
    }
    static string[] ReadStatQueueCounts()
    {
        // Original StatManager owns these event queues. Count only at existing
        // resource samples; never drain events or infer a retaining root from count.
        var type = typeof(RoR2.Stats.PlayerStatsComponent).Assembly.GetType("RoR2.Stats.StatManager", false);
        if (type == null)
            return new[] { "StatManager:unavailable" };
        var names = new[] { "damageEvents",       "deathEvents",           "healingEvents",       "goldCollectedEvents",
                            "purchaseStatEvents", "characterUpdateEvents", "itemCollectedEvents", "itemGainedEvents" };
        var values = new string[names.Length];
        for (int i = 0; i < names.Length; i++)
        {
            var field = type.GetField(names[i], BindingFlags.Static | BindingFlags.NonPublic);
            if (field == null)
            {
                values[i] = names[i] + ":missing";
                continue;
            }
            try
            {
                var queue = field.GetValue(null);
                var count = queue == null ? null : queue.GetType().GetProperty("Count", BindingFlags.Public | BindingFlags.Instance);
                values[i] = names[i] + ":" + (count == null ? "unreadable" : count.GetValue(queue, null).ToString());
            }
            catch (Exception e)
            {
                values[i] = names[i] + ":" + e.GetType().Name;
            }
        }
        return values;
    }
    static string FindCompletedCallbackReference(object value, object probe, object report, int depth)
    {
        if (value == null)
            return null;
        if (ReferenceEquals(value, probe))
            return ":probe";
        if (ReferenceEquals(value, report))
            return ":report";
        if (depth >= 2 || !value.GetType().IsDefined(typeof(System.Runtime.CompilerServices.CompilerGeneratedAttribute), false))
            return null;
        foreach (var field in value.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
        {
            var path = FindCompletedCallbackReference(field.GetValue(value), probe, report, depth + 1);
            if (path != null)
                return "." + field.Name + path;
        }
        return null;
    }
    // Adapted Android lifecycle (J775): original BaseAI.Awake subscribes to the static
    // GlobalEventManager.onCharacterDepossessed and never unsubscribes, so every AI ever
    // spawned, with the graph it references, stays reachable for the process (J773).
    // Remove only entries whose BaseAI Unity has already destroyed, outside any Run;
    // live subscribers and the original handler's behaviour are unchanged.
    int PruneDestroyedDepossessionSubscribers()
    {
        var field = typeof(GlobalEventManager).GetField("onCharacterDepossessed",
                                                        BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        Check(field != null && typeof(Delegate).IsAssignableFrom(field.FieldType),
              "Original depossession event field changed");
        int removed;
        var kept = CompletedSessionRootWalk.RemoveTargets(
            field.GetValue(null) as Delegate,
            target => target is RoR2.CharacterAI.BaseAI && !(UnityEngine.Object)target, out removed);
        if (removed > 0)
            field.SetValue(null, kept);
        return removed;
    }
    // Adapted Android lifecycle (J787): each session reloads the whole-catalog bundle, and
    // the unloaded ItemDisplayRuleSet/PickupDropTable assets never reach the OnDisable that
    // removes them from their original static lists; the original indicator queue is never
    // drained because TeamComponent.Init is not run. Remove only entries Unity has already
    // destroyed, exactly those the original OnDisable or queue processor would drop or skip.
    string[] PruneDestroyedOriginalRegistries()
    {
        var report = new System.Collections.Generic.List<string>();
        foreach (var owner in new[] { typeof(ItemDisplayRuleSet), typeof(PickupDropTable) })
        {
            var field = owner.GetField("instancesList", BindingFlags.Static | BindingFlags.NonPublic);
            var list = field == null ? null : field.GetValue(null) as System.Collections.IList;
            Check(list != null, "Original instance registry changed: " + owner.Name);
            int removed = CompletedSessionRootWalk.RemoveWhere(list, item => !(UnityEngine.Object)item);
            report.Add(owner.Name + ".instancesList:" + removed + "/" + list.Count);
        }
        var queueField = typeof(TeamComponent).GetField("indicatorSetupQueue", BindingFlags.Static | BindingFlags.NonPublic);
        var queue = queueField == null ? null : queueField.GetValue(null) as System.Collections.Generic.Queue<TeamComponent>;
        Check(queue != null, "Original indicator setup queue changed");
        int before = queue.Count;
        var live = queue.Where(component => component).ToArray();
        queue.Clear();
        foreach (var component in live)
            queue.Enqueue(component);
        report.Add("TeamComponent.indicatorSetupQueue:" + (before - queue.Count) + "/" + queue.Count);
        return report.ToArray();
    }
    // Native menu captures identify destroyed cloned cards retained by the original
    // deferred loadout callback. Drop only destroyed targets after world teardown;
    // preserve live callbacks and the ResourceAvailability value-type state.
    int PruneDestroyedSpawnCardCallbacks()
    {
        Check(r.world.cleaned && !Run.instance && !NetworkServer.active && !NetworkClient.active,
              "Refuse spawn-card callback cleanup in a live session");
        var field = typeof(CharacterSpawnCard).GetField("loadoutAvailability", BindingFlags.Static | BindingFlags.NonPublic);
        Check(field != null, "Original spawn-card loadout availability changed");
        var availability = field.GetValue(null);
        var callbacks = field.FieldType.GetField("onAvailable", BindingFlags.Instance | BindingFlags.NonPublic);
        Check(callbacks != null && typeof(Delegate).IsAssignableFrom(callbacks.FieldType),
              "Original loadout availability callback changed");
        int removed;
        var kept = CompletedSessionRootWalk.RemoveTargets(callbacks.GetValue(availability) as Delegate,
            target => target is CharacterSpawnCard && !(UnityEngine.Object)target, out removed);
        if (removed > 0)
        {
            callbacks.SetValue(availability, kept);
            field.SetValue(null, availability);
        }
        return removed;
    }
    // Native menu-4 capture reaches completed player stats through this scratch
    // list. Original Fire clears it before discovery, but leaves its last targets
    // afterwards. Release only destroyed targets at the idle teardown boundary.
    int PruneDestroyedOverlapTargets()
    {
        Check(r.world.cleaned && !Run.instance && !NetworkServer.active && !NetworkClient.active,
              "Refuse overlap-target cleanup in a live session");
        var field = typeof(OverlapAttack).GetField("discoveredHurtboxes", BindingFlags.Static | BindingFlags.NonPublic);
        var targets = field == null ? null : field.GetValue(null) as System.Collections.Generic.List<HurtBox>;
        Check(targets != null, "Original overlap discovery storage changed");
        return targets.RemoveAll(target => !target);
    }
    // The captured J1091 graph identifies the original BulletHitPool as a root
    // for completed actors. Its Reset leaves hitHurtBox assigned. Visit only
    // returned items, after teardown, and release only Unity-destroyed targets.
    int ReleaseDestroyedPooledHitTargets()
    {
        Check(r.world.cleaned && !Run.instance && !NetworkServer.active && !NetworkClient.active,
              "Refuse pooled-hit cleanup in a live session");
        var poolField = typeof(BulletAttack).GetField("bulletHitPool", BindingFlags.Static | BindingFlags.NonPublic);
        var pool = poolField == null ? null : poolField.GetValue(null);
        Check(pool != null, "Original bullet-hit pool changed");
        var itemsField = pool.GetType().BaseType.GetField("items", BindingFlags.Instance | BindingFlags.NonPublic);
        var items = itemsField == null ? null : itemsField.GetValue(pool) as System.Collections.Generic.Stack<BulletAttack.BulletHit>;
        Check(items != null, "Original returned bullet-hit storage changed");
        int released = 0;
        foreach (var hit in items)
        {
            if (!ReferenceEquals(hit.hitHurtBox, null) && !hit.hitHurtBox)
            {
                hit.hitHurtBox = null;
                released++;
            }
        }
        return released;
    }
    IEnumerator ReclaimCompletedSessionResources()
    {
        Check(r.world.cleaned && !Run.instance && !NetworkServer.active && !NetworkClient.active,
              "Refuse resource reclamation in a live session");
        // Let deferred destruction finish before Unity's ordinary unused-asset sweep.
        yield return null;
        int pruned = PruneDestroyedDepossessionSubscribers();
        var registries = PruneDestroyedOriginalRegistries().Concat(new[] {
            "BulletAttack.bulletHitPool.destroyedTargets:" + ReleaseDestroyedPooledHitTargets(),
            "OverlapAttack.discoveredHurtboxes.destroyedTargets:" + PruneDestroyedOverlapTargets(),
            "CharacterSpawnCard.loadoutAvailability.destroyedTargets:" + PruneDestroyedSpawnCardCallbacks()
        }).ToArray();
        ObserveSessionResources("completed-before-reclaim");
        r.sessionResources.Last().prunedDestroyedDepossessionSubscribers = pruned;
        r.sessionResources.Last().prunedDestroyedRegistryEntries = registries;
        yield return Resources.UnloadUnusedAssets();
        ObserveSessionResources("completed-after-reclaim");
        // Attribute remaining managed growth after teardown, without changing GC mode.
        if (UnityEngine.Scripting.GarbageCollector.GCMode != UnityEngine.Scripting.GarbageCollector.Mode.Disabled)
        {
            var began = Time.realtimeSinceStartup;
            GC.Collect();
            var seconds = Time.realtimeSinceStartup - began;
            yield return null;
            ObserveSessionResources("completed-after-managed-collection");
            r.sessionResources.Last().collectionSeconds = seconds;
        }
        Save();
    }
}

// Unity-free bounded reachability walk used only by the opt-in completed-session
// root diagnostic. It reads fields; it never invokes members, clears references or
// changes state. Host contract: tests/test_completed_session_root_walk.py.
public static class CompletedSessionRootWalk
{
    public sealed class Result
    {
        public string[] paths = new string[0];
        public int nodes, roots, readFailures;
        public bool truncated;
        public string[] failureSamples = new string[0];
        // "Type:objects:primitiveArrayBytes", largest first by objects then bytes (census).
        public string[] census = new string[0];
        // "root label (type):objects first reached from it", largest first.
        public string[] rootAttribution = new string[0];
    }
    sealed class Identity : System.Collections.Generic.IEqualityComparer<object>
    {
        public new bool Equals(object x, object y) => ReferenceEquals(x, y);
        public int GetHashCode(object value) => System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(value);
    }
    const BindingFlags InstanceFields = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    const BindingFlags StaticFields = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;
    static readonly System.Collections.Generic.Dictionary<Type, FieldInfo[]> fieldCache =
        new System.Collections.Generic.Dictionary<Type, FieldInfo[]>();

    // Names the first reference path from a static field (or an extra named root)
    // to each target. Targets are expanded too, so a path may pass through another
    // completed session; such hops are labelled with the target's name.
    public static Result Find(System.Collections.Generic.IEnumerable<Type> types,
                              System.Collections.Generic.IList<System.Collections.Generic.KeyValuePair<string, object>> extraRoots,
                              System.Collections.Generic.IList<System.Collections.Generic.KeyValuePair<string, object>> targets,
                              int nodeBudget, int maxPaths, int censusTop = 0)
    {
        var result = new Result();
        var failures = new System.Collections.Generic.List<string>();
        var visited = new System.Collections.Generic.Dictionary<object, int>(new Identity());
        var nodes = new System.Collections.Generic.List<object>();
        var parents = new System.Collections.Generic.List<int>();
        // Edge: root label string, FieldInfo, boxed element index or delegate MethodInfo.
        var edges = new System.Collections.Generic.List<object>();
        var rootOf = new System.Collections.Generic.List<int>();
        var targetNames = new System.Collections.Generic.Dictionary<object, string>(new Identity());
        foreach (var target in targets)
            if (target.Value != null && !targetNames.ContainsKey(target.Value))
                targetNames.Add(target.Value, target.Key);
        var found = new System.Collections.Generic.List<string>();
        var reached = new System.Collections.Generic.HashSet<object>(new Identity());
        Action<object, int, object> enqueue = (value, parent, edge) =>
        {
            if (value == null || visited.ContainsKey(value) || Skip(value.GetType()))
                return;
            if (nodes.Count >= nodeBudget)
            {
                result.truncated = true;
                return;
            }
            visited.Add(value, nodes.Count);
            rootOf.Add(parent < 0 ? nodes.Count : rootOf[parent]);
            nodes.Add(value);
            parents.Add(parent);
            edges.Add(edge);
        };
        foreach (var root in extraRoots)
            enqueue(root.Value, -1, root.Key);
        foreach (var type in types)
        {
            if (type == null || type.IsGenericTypeDefinition || type.ContainsGenericParameters)
                continue;
            FieldInfo[] statics;
            try
            {
                statics = type.GetFields(StaticFields);
            }
            catch (Exception e)
            {
                Fail(result, failures, type.FullName + ":" + e.GetType().Name);
                continue;
            }
            foreach (var field in statics)
            {
                if (field.IsLiteral || Leaf(field.FieldType))
                    continue;
                object value;
                try
                {
                    value = field.GetValue(null);
                }
                catch (Exception e)
                {
                    Fail(result, failures, type.FullName + "." + field.Name + ":" + e.GetType().Name);
                    continue;
                }
                enqueue(value, -1, type.FullName + "." + field.Name);
            }
        }
        result.roots = nodes.Count;
        for (int index = 0; index < nodes.Count && found.Count < maxPaths; index++)
        {
            var value = nodes[index];
            string name;
            if (targetNames.TryGetValue(value, out name) && reached.Add(value))
                found.Add(name + " <= " + Render(nodes, parents, edges, targetNames, index));
            var type = value.GetType();
            var callback = value as Delegate;
            if (callback != null)
            {
                Delegate[] list;
                try
                {
                    list = callback.GetInvocationList();
                }
                catch (Exception e)
                {
                    Fail(result, failures, "delegate:" + e.GetType().Name);
                    continue;
                }
                for (int i = 0; i < list.Length; i++)
                    enqueue(list[i].Target, index, list[i].Method);
                continue;
            }
            var array = value as Array;
            if (array != null)
            {
                if (array.Rank != 1 || Leaf(type.GetElementType()))
                    continue;
                for (int i = 0; i < array.Length; i++)
                {
                    object element;
                    try
                    {
                        element = array.GetValue(i);
                    }
                    catch (Exception e)
                    {
                        Fail(result, failures, type.FullName + "[]:" + e.GetType().Name);
                        break;
                    }
                    enqueue(element, index, i);
                }
                continue;
            }
            foreach (var field in Fields(type))
            {
                object child;
                try
                {
                    child = field.GetValue(value);
                }
                catch (Exception e)
                {
                    Fail(result, failures, type.FullName + "." + field.Name + ":" + e.GetType().Name);
                    continue;
                }
                enqueue(child, index, field);
            }
        }
        result.nodes = nodes.Count;
        result.paths = found.ToArray();
        result.census = Census(nodes, censusTop);
        if (censusTop > 0)
        {
            var perRoot = new System.Collections.Generic.Dictionary<int, int>();
            foreach (var root in rootOf)
                perRoot[root] = perRoot.TryGetValue(root, out var count) ? count + 1 : 1;
            result.rootAttribution = perRoot.OrderByDescending(x => x.Value)
                                         .Take(25)
                                         .Select(x => Edge(edges[x.Key]) + " (" + nodes[x.Key].GetType().Name + "):" + x.Value)
                                         .ToArray();
        }
        result.failureSamples = failures.ToArray();
        return result;
    }
    // Removes matching items in place, preserving order; returns the removed count.
    public static int RemoveWhere(System.Collections.IList list, Func<object, bool> remove)
    {
        int removed = 0;
        for (int i = list.Count - 1; i >= 0; i--)
            if (remove(list[i]))
            {
                list.RemoveAt(i);
                removed++;
            }
        return removed;
    }
    // Removes every invocation entry whose target matches; returns the remaining delegate.
    public static Delegate RemoveTargets(Delegate callback, Func<object, bool> remove, out int removed)
    {
        removed = 0;
        if (callback == null)
            return null;
        var kept = callback;
        foreach (var entry in callback.GetInvocationList())
            if (entry.Target != null && remove(entry.Target))
            {
                kept = Delegate.Remove(kept, entry);
                removed++;
            }
        return kept;
    }
    static string[] Census(System.Collections.Generic.List<object> nodes, int top)
    {
        if (top <= 0)
            return new string[0];
        var counts = new System.Collections.Generic.Dictionary<Type, long[]>();
        foreach (var node in nodes)
        {
            var type = node.GetType();
            long[] row;
            if (!counts.TryGetValue(type, out row))
                counts.Add(type, row = new long[2]);
            row[0]++;
            var array = node as Array;
            if (array != null && type.GetElementType().IsPrimitive)
                row[1] += Buffer.ByteLength(array);
        }
        var rows = new System.Collections.Generic.List<System.Collections.Generic.KeyValuePair<Type, long[]>>(counts);
        rows.Sort((a, b) => a.Value[0] != b.Value[0] ? b.Value[0].CompareTo(a.Value[0]) : b.Value[1].CompareTo(a.Value[1]));
        var byBytes = new System.Collections.Generic.List<System.Collections.Generic.KeyValuePair<Type, long[]>>(counts);
        byBytes.Sort((a, b) => b.Value[1].CompareTo(a.Value[1]));
        var output = new System.Collections.Generic.List<string>();
        var seen = new System.Collections.Generic.HashSet<Type>();
        foreach (var row in rows.Take(top).Concat(byBytes.Take(top / 4)))
            if (seen.Add(row.Key))
                output.Add(row.Key.FullName + ":" + row.Value[0] + ":" + row.Value[1]);
        return output.ToArray();
    }
    static void Fail(Result result, System.Collections.Generic.List<string> failures, string failure)
    {
        result.readFailures++;
        if (failures.Count < 20)
            failures.Add(failure);
    }
    static bool Skip(Type type)
    {
        // Leaves and reflection metadata hold no session state.
        return type == null || type.IsPrimitive || type.IsEnum || type.IsPointer || type == typeof(string) ||
               type == typeof(decimal) || typeof(MemberInfo).IsAssignableFrom(type) || typeof(Assembly).IsAssignableFrom(type) ||
               typeof(Module).IsAssignableFrom(type) || type == typeof(IntPtr) || type == typeof(UIntPtr) ||
               typeof(WeakReference).IsAssignableFrom(type);
    }
    static bool Leaf(Type type)
    {
        return type.IsPrimitive || type.IsEnum || type.IsPointer || type == typeof(string);
    }
    static FieldInfo[] Fields(Type type)
    {
        FieldInfo[] fields;
        if (fieldCache.TryGetValue(type, out fields))
            return fields;
        var list = new System.Collections.Generic.List<FieldInfo>();
        for (var current = type; current != null && current != typeof(object); current = current.BaseType)
            foreach (var field in current.GetFields(InstanceFields | BindingFlags.DeclaredOnly))
                if (!Leaf(field.FieldType))
                    list.Add(field);
        fields = list.ToArray();
        fieldCache.Add(type, fields);
        return fields;
    }
    static string Edge(object edge)
    {
        var field = edge as FieldInfo;
        if (field != null)
            return "." + field.Name;
        var method = edge as MethodInfo;
        if (method != null)
            return "(" + method.DeclaringType?.Name + "." + method.Name + ").Target";
        if (edge is int)
            return "[" + edge + "]";
        return edge as string ?? "?";
    }
    static string Render(System.Collections.Generic.List<object> nodes, System.Collections.Generic.List<int> parents,
                         System.Collections.Generic.List<object> edges, System.Collections.Generic.Dictionary<object, string> targets,
                         int index)
    {
        var parts = new System.Collections.Generic.List<string>();
        for (int i = index; i >= 0; i = parents[i])
        {
            string name;
            var label = Edge(edges[i]) + " (" + nodes[i].GetType().Name + ")";
            if (i != index && targets.TryGetValue(nodes[i], out name))
                label += " [" + name + "]";
            parts.Add(label);
            if (parts.Count > 64)
            {
                parts.Add("...");
                break;
            }
        }
        parts.Reverse();
        return string.Join(" -> ", parts.ToArray());
    }
}
