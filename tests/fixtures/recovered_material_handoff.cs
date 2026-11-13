using System;
using System.Collections.Generic;
using UnityEngine;
using RoR2;

namespace UnityEngine
{
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
namespace RoR2 { public class DamageTrail : UnityEngine.Object { public GameObject segmentPrefab; } }
namespace RoR2.Projectile { public class ProjectileController : UnityEngine.Object { public GameObject ghostPrefab; } }
public partial class SourceSession
{
    public SourceSession coordinator => this;
    public readonly List<Material> worldMaterials = new List<Material>();
    public readonly Dictionary<Renderer, Material[]> worldLootSourceMaterials = new Dictionary<Renderer, Material[]>();
    public readonly Dictionary<ParticleSystemRenderer, Material> worldLootSourceTrails = new Dictionary<ParticleSystemRenderer, Material>();
    public class Counts { public int nativeEffectSourceMaterials, nativeEffectSourceRenderers; }
    public class Report { public Counts world = new Counts(); }
    public Report r = new Report();
    public GameObject OriginalProjectileGhost(RoR2.Projectile.ProjectileController controller) => controller.ghostPrefab;
    public void Prepare(GameObject root) => PresentNativeEffectSource(root);
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
}
static class Fixture
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
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
        session.Prepare(root);
        Check(session.worldMaterials.Count == 3 && session.r.world.nativeEffectSourceRenderers == 2, "referenced native roots skipped or duplicated");
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
