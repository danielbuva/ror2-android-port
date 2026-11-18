using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;
using RoR2;
using RoR2.ContentManagement;
using UnityEngine.AddressableAssets;
using UnityEngine.ResourceManagement.AsyncOperations;

namespace UnityEngine
{
    public static class Time { public static float realtimeSinceStartup; }
    public class Object
    {
        public bool destroyed;
        public static implicit operator bool(Object value) => value != null && !value.destroyed;
        public static void Destroy(Object value) { value.destroyed = true; }
    }
    public class Shader : Object
    {
        public string name;
        public Shader(string value) { name = value; }
    }
    public class Material : Object
    {
        public static int copies;
        public Shader shader;
        public string properties;
        public int srcBlend, dstBlend, zWrite, renderQueue;
        public Material(string name, string values) { shader = new Shader(name); properties = values; }
        public Material(Material source) { copies++; shader = source.shader; properties = source.properties;
            srcBlend = source.srcBlend; dstBlend = source.dstBlend; zWrite = source.zWrite; renderQueue = source.renderQueue; }
    }
    public class Renderer : Object { public Material[] sharedMaterials; }
    public class ParticleSystemRenderer : Renderer { public Material trailMaterial; }
    public class GameObject : Object
    {
        public Object[] components = new Object[0];
        public T[] GetComponentsInChildren<T>(bool includeInactive) where T : Object
            => Array.ConvertAll(Array.FindAll(components, value => value is T), value => (T)value);
    }
}
namespace UnityEngine.ResourceManagement.AsyncOperations
{
    public enum AsyncOperationStatus { None, Succeeded, Failed }
    public class AsyncOperationHandle<T>
    {
        public AsyncOperationStatus Status;
        public bool IsDone => Status != AsyncOperationStatus.None;
        public T Result;
    }
}
namespace UnityEngine.AddressableAssets
{
    public class AssetReference
    {
        public object RuntimeKey;
        public bool RuntimeKeyIsValid() => RuntimeKey != null;
    }
    public static class Addressables
    {
        public static object requestedKey, operation;
        public static AsyncOperationHandle<T> LoadAssetAsync<T>(object key)
        {
            requestedKey = key;
            return (AsyncOperationHandle<T>)operation;
        }
    }
}
namespace EntityStates.Croco
{
    public class Slash
    {
        public class SwingReference
        {
            public AssetReference addressableReference;
            public GameObject directReference;
        }
        public static GameObject configuredNormal;
        public static SwingReference comboFinisherSwingEffectPrefab;
        public GameObject swingEffectPrefab = configuredNormal;
    }
}
namespace EntityStates.Merc
{
    public static class GroundLight { public static GameObject finisherSwingEffectPrefab; }
}
public static class WholeCatalogComposed
{
    public static GameObject mercFinisher;
    public static T LoadOwnedContent<T>(string path) where T : UnityEngine.Object
    {
        if (path != "Assets/WholeGame/RoR2/Base/Characters/Merc/MercSwordFinisherSlash.prefab")
            throw new InvalidOperationException("Unexpected owned swing path: " + path);
        return mercFinisher as T;
    }
}
namespace RoR2
{
    public class DamageTrail : UnityEngine.Object { public GameObject segmentPrefab; }
    public class TeamAreaIndicator : UnityEngine.Object
    {
        public struct TeamMaterialPair { public int teamIndex; public Material sharedMaterial; }
        public TeamMaterialPair[] teamMaterialPairs;
    }
    public class EffectComponent : UnityEngine.Object { }
    public class EffectDef
    {
        readonly AssetOrDirectReference<GameObject> _prefabAssetOrDirectReference;
        public EffectComponent prefabEffectComponent;
        public GameObject prefab => _prefabAssetOrDirectReference.Acquire();
        public EffectDef(AssetOrDirectReference<GameObject> reference) => _prefabAssetOrDirectReference = reference;
    }
    public static class EffectCatalog
    {
        static EffectDef[] entries;
        public static void SetEntries(params EffectDef[] value) => entries = value;
    }
    public static class LegacyResourcesAPI
    {
        public static T Load<T>(string path) where T : UnityEngine.Object => null;
    }
}
namespace RoR2.ContentManagement
{
    public class AssetOrDirectReference<T> where T : UnityEngine.Object
    {
        public T source, result;
        public int acquisitions, subscribers;
        Action<T> discovered;
        public event Action<T> onValidReferenceDiscovered
        {
            add { discovered += value; subscribers++; if (result) value(result); }
            remove { discovered -= value; subscribers--; }
        }
        public T Acquire()
        {
            acquisitions++;
            if (!result)
            {
                result = source;
                discovered?.Invoke(result);
            }
            return result;
        }
    }
}
namespace RoR2.Projectile { public class ProjectileController : UnityEngine.Object { public GameObject ghostPrefab; } }
public static class PortSession
{
    public static FieldInfo RewardField(Type type, string name) => type.GetField(name, BindingFlags.NonPublic | BindingFlags.Static);
}
public partial class SourceSession
{
    readonly HashSet<AssetOrDirectReference<GameObject>> nativeEffectReferences = new HashSet<AssetOrDirectReference<GameObject>>();
    readonly Dictionary<TeamAreaIndicator, TeamAreaIndicator.TeamMaterialPair[]> nativeTeamAreaMaterials =
        new Dictionary<TeamAreaIndicator, TeamAreaIndicator.TeamMaterialPair[]>();
    public readonly List<AsyncOperationHandle<GameObject>> ownedOriginalVisualHandles = new List<AsyncOperationHandle<GameObject>>();
    public SourceSession coordinator => this;
    public SourceSession GetTeleporterWorldSession() => this;
    public readonly List<Material> worldMaterials = new List<Material>();
    public readonly Dictionary<Renderer, Material[]> worldLootSourceMaterials = new Dictionary<Renderer, Material[]>();
    public readonly Dictionary<ParticleSystemRenderer, Material> worldLootSourceTrails = new Dictionary<ParticleSystemRenderer, Material>();
    public class Counts { public int nativeEffectSourceMaterials, nativeEffectSourceRenderers; }
    public class Report { public Counts world; }
    public int nativeEffectSourceMaterials, nativeEffectSourceRenderers;
    public Report r = new Report();
    public GameObject OriginalProjectileGhost(RoR2.Projectile.ProjectileController controller) => controller.ghostPrefab;
    public void Prepare(GameObject root) => PresentNativeEffectSource(root);
    public void Stop() => StopPresentingNativeEffectReferences();
    public IEnumerator PrepareSwings(List<string> unavailable) => PrepareNativeSwingEffects(unavailable);
}
public static partial class AndroidNativeDeferredPresentation
{
    public class Report { public bool available = true; }
    public class Family { public string shader; }
    public class Families { public Family[] families; }
    public static Report report = new Report();
    static Families families = new Families { families = new[] {
        new Family { shader = "Hopoo Games/FX/Cloud Remap" },
        new Family { shader = "Hopoo Games/FX/Opaque Cloud Remap" }
    } };
    public static bool Apply(Material source, Material copy)
    {
        if (!IsSourceFamily(source) || source.properties == "missing-variant") return false;
        copy.shader = new Shader("Recovered/" + source.shader.name);
        return true;
    }
}
public static partial class AndroidMaterialPresentation
{
    class Binding { public Material material; public Shader enhanced, fallback; }
    public class Report { public bool enabled = true; public int surfaces; }
    static readonly List<Binding> bindings = new List<Binding>();
    public static Report report = new Report();
    static readonly Shader fallback = new Shader("Fallback");
    static Shader LoadShader(string name) => fallback;
    public static bool Apply(Material source, Material copy)
    {
        if (source.properties == "missing shader")
            return false;
        copy.shader = new Shader("Recovered/Intersection");
        return true;
    }
}
static class Fixture
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void CheckBakedEffectAdmission(Material original)
    {
        var firstRenderer = new Renderer { sharedMaterials = new[] { original } };
        var loadedRenderer = new Renderer { sharedMaterials = new[] { original } };
        var pendingRenderer = new Renderer { sharedMaterials = new[] { original } };
        var lazy = new AssetOrDirectReference<GameObject> { source = new GameObject { components = new[] { firstRenderer } } };
        var loaded = new AssetOrDirectReference<GameObject> { result = new GameObject { components = new[] { loadedRenderer } } };
        var pending = new AssetOrDirectReference<GameObject> { source = new GameObject { components = new[] { pendingRenderer } } };
        var definition = new EffectDef(lazy);
        EffectCatalog.SetEntries(definition, new EffectDef(loaded), new EffectDef(pending));
        var session = new SourceSession();
        session.PresentRegisteredNativeEffects();
        session.PresentRegisteredNativeEffects();
        Check(lazy.acquisitions == 0 && pending.acquisitions == 0 && loaded.acquisitions == 0, "registration loaded a baked source");
        Check(lazy.subscribers == 1 && loaded.subscribers == 1 && pending.subscribers == 1, "registration subscribed more than once");
        Check(loadedRenderer.sharedMaterials[0].shader.name.StartsWith("Recovered/"), "already loaded source skipped");
        Check(firstRenderer.sharedMaterials[0] == original, "unloaded source was touched early");
        var firstSource = definition.prefab;
        var firstPooledMaterial = firstSource.GetComponentsInChildren<Renderer>(true)[0].sharedMaterials[0];
        Check(firstPooledMaterial.shader.name.StartsWith("Recovered/") && firstPooledMaterial.srcBlend == original.srcBlend &&
            firstPooledMaterial.dstBlend == original.dstBlend, "first native spawn missed original state or recovered shader");
        session.Stop();
        session.Stop();
        pending.Acquire();
        Check(lazy.subscribers == 0 && loaded.subscribers == 0 && pending.subscribers == 0 && pendingRenderer.sharedMaterials[0] == original,
            "late acquisition changed material after teardown");
    }
    static void CheckSwingAdmission(Material original)
    {
        var merc = new Renderer { sharedMaterials = new[] { original } };
        var normal = new Renderer { sharedMaterials = new[] { original } };
        var finisher = new Renderer { sharedMaterials = new[] { original } };
        var fallback = new Renderer { sharedMaterials = new[] { original } };
        WholeCatalogComposed.mercFinisher = new GameObject { components = new[] { merc } };
        EntityStates.Croco.Slash.configuredNormal = new GameObject { components = new[] { normal } };
        EntityStates.Croco.Slash.comboFinisherSwingEffectPrefab = new EntityStates.Croco.Slash.SwingReference {
            addressableReference = new AssetReference { RuntimeKey = "native-finisher" },
            directReference = new GameObject { components = new[] { fallback } }
        };
        var operation = new AsyncOperationHandle<GameObject> { Result = new GameObject { components = new[] { finisher } } };
        Addressables.operation = operation;
        var session = new SourceSession();
        var unavailable = new List<string>();
        var prepare = session.PrepareSwings(unavailable);
        Check(prepare.MoveNext() && normal.sharedMaterials[0] != original && finisher.sharedMaterials[0] == original,
              "normal source should be prepared while native finisher loads");
        Check(!EntityStates.Merc.GroundLight.finisherSwingEffectPrefab &&
              merc.sharedMaterials[0].shader.name.StartsWith("Recovered/") && session.worldLootSourceMaterials[merc][0] == original,
              "owned Merc finisher did not receive presentation before native state configuration");
        operation.Status = AsyncOperationStatus.Succeeded;
        Check(!prepare.MoveNext() && unavailable.Count == 0 && finisher.sharedMaterials[0] != original,
              "native finisher source should be prepared after loading");
        Check((string)Addressables.requestedKey == "native-finisher" && session.ownedOriginalVisualHandles[0] == operation &&
              fallback.sharedMaterials[0] == original && session.worldLootSourceMaterials.Count == 3,
              "native address and source ownership must be preserved");
    }
    static void CheckIntersectionEffectAdmission()
    {
        var source = new Material("Hopoo Games/FX/Cloud Intersection Remap", "source sphere properties") {
            srcBlend = 1, dstBlend = 1, renderQueue = 3000
        };
        var renderer = new ParticleSystemRenderer { sharedMaterials = new[] { source }, trailMaterial = source };
        var root = new GameObject { components = new[] { renderer } };
        var session = new SourceSession();
        Check(AndroidMaterialPresentation.ApplyRecovered(renderer, session.worldMaterials) == 0,
              "actor-only recovery should retain intersection");
        session.Prepare(root);
        session.Prepare(root);
        foreach (var material in new[] { renderer.sharedMaterials[0], renderer.trailMaterial })
            Check(material.shader.name == "Recovered/Intersection" && material.properties == source.properties &&
                  material.srcBlend == 1 && material.dstBlend == 1 && material.renderQueue == 3000,
                  "effect intersection lost its source blend, queue or material properties");
        Check(session.worldMaterials.Count == 2 && session.worldLootSourceMaterials[renderer][0] == source &&
              session.worldLootSourceTrails[renderer] == source && source.shader.name == "Hopoo Games/FX/Cloud Intersection Remap",
              "intersection selection did not retain source slots and trail");
    }
    static void CheckTeamAreaAdmission(Material unrelated)
    {
        const string shader = "Hopoo Games/FX/Cloud Intersection Remap";
        var enemy = new Material(shader, "enemy ramp and fade keyword") { srcBlend = 5, dstBlend = 10, renderQueue = 3000 };
        var unrenderable = new Material(shader, "missing shader");
        var pairs = new[] {
            new TeamAreaIndicator.TeamMaterialPair { teamIndex = 3, sharedMaterial = enemy },
            new TeamAreaIndicator.TeamMaterialPair { teamIndex = 1, sharedMaterial = unrelated },
            new TeamAreaIndicator.TeamMaterialPair { teamIndex = 2, sharedMaterial = unrenderable },
        };
        var indicator = new TeamAreaIndicator { teamMaterialPairs = pairs };
        var root = new GameObject { components = new[] { indicator } };
        var session = new SourceSession();
        session.Prepare(root);
        var prepared = indicator.teamMaterialPairs;
        var selected = prepared[0].sharedMaterial;
        Check(prepared != pairs && prepared[0].teamIndex == pairs[0].teamIndex && pairs[0].sharedMaterial == enemy &&
              prepared[1].sharedMaterial == unrelated && prepared[2].sharedMaterial == unrenderable,
              "native team selection or source table changed");
        Check(session.worldMaterials.Count == 1 && selected == session.worldMaterials[0] &&
              selected.shader.name == "Recovered/Intersection" && selected.properties == enemy.properties &&
              selected.srcBlend == enemy.srcBlend && selected.dstBlend == enemy.dstBlend && selected.renderQueue == enemy.renderQueue,
              "native team selection did not receive a run-owned presentation copy with original properties");
        session.Prepare(root);
        Check(indicator.teamMaterialPairs == prepared && session.worldMaterials.Count == 1, "team table prepared twice");
        session.Stop();
        foreach (var copy in session.worldMaterials) UnityEngine.Object.Destroy(copy);
        Check(indicator.teamMaterialPairs == pairs && enemy && unrelated && unrenderable, "team material source ownership did not unwind");
    }
    static void Main()
    {
        var body = new Material("Hopoo Games/Deferred/Standard", "source tint/textures/queue/keywords");
        var trail = new Material("Hopoo Games/FX/Cloud Remap", "source trail properties");
        var unknown = new Material("Unknown shader", "untouched");
        var renderer = new ParticleSystemRenderer { sharedMaterials = new[] { null, body, unknown }, trailMaterial = trail };
        var owned = new List<Material>();
        Check(AndroidMaterialPresentation.ApplyRecovered(renderer, owned) == 2, "body/trail not recovered");
        Check(renderer.sharedMaterials[0] == null && renderer.sharedMaterials[2] == unknown, "null/unknown replaced");
        Check(renderer.sharedMaterials[1] == owned[0] && renderer.trailMaterial == owned[1], "copies not retained");
        Check(owned[0].shader.name.StartsWith("Recovered/") && owned[1].shader.name.StartsWith("Recovered/"), "shader bypass");
        Check(owned[0].properties == body.properties && owned[1].properties == trail.properties, "source values changed");
        Check(body.shader.name == "Hopoo Games/Deferred/Standard" && trail.shader.name == "Hopoo Games/FX/Cloud Remap", "source mutated");
        int copies = Material.copies;
        Check(AndroidMaterialPresentation.ApplyRecovered(renderer, owned) == 0 && Material.copies == copies, "repeat cloned owned/unknown slots");
        // A native state adds another source slot to the same already-presented renderer.
        var debris = new Material("Hopoo Games/FX/Opaque Cloud Remap", "source debris");
        renderer.sharedMaterials = new[] { owned[0], debris };
        Check(AndroidMaterialPresentation.ApplyRecovered(renderer, owned) == 1, "late slot skipped");
        AndroidMaterialPresentation.SetEnabled(false);
        Check(owned.TrueForAll(material => material.shader.name == "Fallback"), "existing toggle bindings lost");
        var late = new Renderer { sharedMaterials = new[] { body } };
        Check(AndroidMaterialPresentation.ApplyRecovered(late, owned) == 1 && late.sharedMaterials[0].shader.name == "Fallback", "disabled handoff lost");
        AndroidMaterialPresentation.SetEnabled(true);
        Check(owned.TrueForAll(material => material.shader.name.StartsWith("Recovered/")), "reenable lost recovered shaders");
        var missing = new Material("Hopoo Games/FX/Cloud Remap", "missing-variant");
        var refused = new Renderer { sharedMaterials = new[] { missing } };
        int retained = owned.Count;
        Check(AndroidMaterialPresentation.ApplyRecovered(refused, owned) == 0 && refused.sharedMaterials[0] == missing && owned.Count == retained, "unavailable variant replaced");
        AndroidNativeDeferredPresentation.report.available = false;
        copies = Material.copies;
        Check(AndroidMaterialPresentation.ApplyRecovered(refused, owned) == 0 && Material.copies == copies, "unavailable pipeline cloned");
        AndroidNativeDeferredPresentation.report.available = true;
        var fire = new Material("Hopoo Games/FX/Cloud Remap", "fire mask/ramp/keywords") {
            srcBlend = 1, dstBlend = 1, zWrite = 0, renderQueue = 3000 };
        var alpha = new Material("Hopoo Games/FX/Cloud Remap", "alpha mask") {
            srcBlend = 5, dstBlend = 10, zWrite = 0, renderQueue = 3050 };
        CheckBakedEffectAdmission(alpha);
        CheckSwingAdmission(alpha);
        CheckIntersectionEffectAdmission();
        CheckTeamAreaAdmission(unknown);
        var segmentRenderer = new ParticleSystemRenderer { sharedMaterials = new[] { fire }, trailMaterial = alpha };
        var segment = new GameObject { components = new UnityEngine.Object[] { segmentRenderer } };
        var ghostRenderer = new Renderer { sharedMaterials = new[] { alpha } };
        var ghost = new GameObject { components = new UnityEngine.Object[] { ghostRenderer } };
        var root = new GameObject { components = new UnityEngine.Object[] {
            new RoR2.DamageTrail { segmentPrefab = segment },
            new RoR2.Projectile.ProjectileController { ghostPrefab = ghost } } };
        // A cycle and a shared edge must not duplicate source copies or recurse forever.
        segment.components = new UnityEngine.Object[] { segmentRenderer, new RoR2.DamageTrail { segmentPrefab = root } };
        var session = new SourceSession();
        session.Prepare(root);
        Check(session.r.world == null, "objective preparation created a world report");
        Check(session.worldMaterials.Count == 3 && session.nativeEffectSourceMaterials == 3 &&
            session.nativeEffectSourceRenderers == 2, "early objective sources were not counted");
        session.r.world = new SourceSession.Counts();
        session.Prepare(root);
        Check(session.worldMaterials.Count == 3 && session.r.world.nativeEffectSourceMaterials == 3 &&
            session.r.world.nativeEffectSourceRenderers == 2, "world report lost or duplicated early source counts");
        Check(segmentRenderer.sharedMaterials[0].shader.name.StartsWith("Recovered/") && ghostRenderer.sharedMaterials[0].shader.name.StartsWith("Recovered/"), "native pool will inherit dummy shader");
        Check(segmentRenderer.sharedMaterials[0].srcBlend == 1 && segmentRenderer.sharedMaterials[0].dstBlend == 1 && segmentRenderer.sharedMaterials[0].zWrite == 0, "additive source state changed");
        Check(ghostRenderer.sharedMaterials[0].srcBlend == 5 && ghostRenderer.sharedMaterials[0].dstBlend == 10 && ghostRenderer.sharedMaterials[0].renderQueue == 3050, "alpha source state changed");
        foreach (var pair in session.worldLootSourceMaterials) pair.Key.sharedMaterials = pair.Value;
        foreach (var pair in session.worldLootSourceTrails) pair.Key.trailMaterial = pair.Value;
        foreach (var material in session.worldMaterials) UnityEngine.Object.Destroy(material);
        Check(segmentRenderer.sharedMaterials[0] == fire && segmentRenderer.trailMaterial == alpha && ghostRenderer.sharedMaterials[0] == alpha && fire && alpha, "source teardown lost originals");
        foreach (var material in owned) UnityEngine.Object.Destroy(material);
        Check(body && trail && debris && unknown && missing, "teardown destroyed source");
        Console.WriteLine("recovered material handoff passed");
    }
}
