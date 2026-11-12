using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Only the editor substitutes AssetDatabase for the Android bundle provider.
public static class WholeCatalogHost
{
    // Current exact-editor inventory; published membership is the native provider policy.
    // This inspects imported assets and resource coverage, never claims Android rendering.
    public static object AuditCombatMaterials(string manifestPath, string outputPath)
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorUtility.scriptCompilationFailed ||
            EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer || stack.Count != 0)
            throw new Exception("Editor busy or source not compiled");
        var manifest = JObject.Parse(File.ReadAllText(manifestPath));
        var locations = manifest["locations"].ToDictionary(row => (int)row["id"]);
        var roots = new JArray();
        var rows = new JArray();
        var errors = new JArray();
        var candidates = new JArray();
        foreach (var category in new[] { "CharacterBody", "Projectile" })
        {
            var groups = WholeCatalogComposed.FamilyLocationGroups(manifest, category);
            for (int provider = 0; provider < groups.Length; provider++)
                foreach (int id in groups[provider])
                {
                    var candidate = (JObject)locations[id].DeepClone();
                    candidate["category"] = category;
                    candidate["provider"] = provider;
                    candidates.Add(candidate);
                }
        }
        // The lab publishes effects from its session config, independently of the
        // catalog's Effect label. Inspect precisely those registered source prefabs.
        var config = Resources.Load<TextAsset>("MovementBatchProbe");
        if (!config)
            throw new Exception("Current lab session config missing");
        foreach (var path in JObject.Parse(config.text)["objectiveEffectAssets"].Values<string>().Distinct())
            candidates.Add(new JObject { ["id"] = -1, ["path"] = path, ["category"] = "RegisteredEffect", ["provider"] = -1 });
        foreach (JObject location in candidates)
        {
            string category = (string)location["category"];
            int provider = (int)location["provider"], id = (int)location["id"];
            string path = (string)location["path"];
            var root = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            roots.Add(new JObject { ["category"] = category, ["provider"] = provider, ["location"] = id, ["path"] = path,
                                    ["loaded"] = (bool)root });
            if (!root)
            {
                errors.Add("Typed prefab missing: " + category + "/" + path);
                continue;
            }
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                var hierarchy = new List<string>();
                for (var node = renderer.transform; node; node = node.parent)
                    hierarchy.Add(node.name + "[" + node.GetSiblingIndex() + "]");
                hierarchy.Reverse();
                var particle = renderer as ParticleSystemRenderer;
                var streams = new List<ParticleSystemVertexStream>();
                if (particle)
                    particle.GetActiveVertexStreams(streams);
                var materials = renderer.sharedMaterials;
                for (int slot = 0; slot < materials.Length; slot++)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", slot,
                                      materials[slot]);
                foreach (var model in root.GetComponentsInChildren<RoR2.CharacterModel>(true))
                    foreach (var info in model.baseRendererInfos.Where(info => info.renderer == renderer))
                    {
                        var row = AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams,
                                                    "CharacterModel.defaultMaterial", 0, info.defaultMaterial);
                        row["materialAddress"] =
                            info.defaultMaterialAddress == null ? null : Convert.ToString(info.defaultMaterialAddress.RuntimeKey);
                    }
                var billboard = renderer as BillboardRenderer;
                if (billboard && billboard.billboard)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "billboard.material", 0,
                                      billboard.billboard.material);
                if (particle && particle.trailMaterial)
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "trailMaterial", 0,
                                      particle.trailMaterial);
                if (materials.Length == 0 && !(billboard && billboard.billboard))
                    AddCombatMaterial(rows, id, category, path, renderer, hierarchy, particle, streams, "sharedMaterials", -1, null);
            }
        }
        var result = new JObject {
            ["scope"] =
                "Native-provider body/projectile candidates before per-provider name deduplication, plus current lab registered effects; resource coverage only; Android rendering and reference comparison remain open",
            ["roots"] = roots, ["slots"] = rows, ["errors"] = errors,
            ["surfaceObservationContract"] = VerifySurfaceMaterialObservation()
        };
        File.WriteAllText(outputPath, result.ToString());
        return new { roots = roots.Count, slots = rows.Count, errors = errors.Count, output = outputPath };
    }
    static JObject VerifySurfaceMaterialObservation()
    {
        // Exercise the actual runtime observer against live Unity material state.
        // No session, catalog, scene or presentation adapter is initialized.
        var type = typeof(PortSession).GetNestedType("TeleporterWorldSession", System.Reflection.BindingFlags.NonPublic);
        var observer = Activator.CreateInstance(type, new object[] { null });
        var method = type.GetMethod("ObserveSurfaceMaterial");
        var material = new Material(Shader.Find("Standard"));
        var texture = new Texture2D(2, 2) { name = "Authored census fixture texture" };
        try
        {
            material.name = "Authored census fixture material";
            material.renderQueue = 3123;
            material.SetTexture("_MainTex", texture);
            material.SetTextureScale("_MainTex", new Vector2(2, 3));
            material.EnableKeyword("_EMISSION");
            var row = (PortSession.SurfaceMaterialObservation)method.Invoke(observer, new object[] { material });
            var main = row.properties.Single(property => property.name == "_MainTex");
            if (row.material != material.name || row.shader != material.shader.name || row.queue != 3123 ||
                row.supported != material.shader.isSupported || !row.keywords.Contains("_EMISSION") ||
                main.textureId != texture.GetInstanceID() || main.width != 2 || main.height != 2 ||
                main.scale != new Vector2(2, 3) || material.GetTexture("_MainTex") != texture || material.renderQueue != 3123 ||
                method.Invoke(observer, new object[] { null }) != null)
                throw new Exception("Live surface material observation contract failed");
            return new JObject { ["liveMaterialState"] = true, ["nullSlot"] = true, ["sourceUnchanged"] = true };
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(material);
            UnityEngine.Object.DestroyImmediate(texture);
        }
    }
    static JObject AddCombatMaterial(JArray rows, int id, string category, string root, Renderer renderer, List<string> hierarchy,
                                     ParticleSystemRenderer particle, List<ParticleSystemVertexStream> streams, string binding, int slot,
                                     Material material)
    {
        var textures = new JArray();
        var meshes = particle ? new Mesh[particle.meshCount] : new Mesh[0];
        if (particle)
            particle.GetMeshes(meshes);
        if (material && material.shader)
            foreach (var name in material.GetTexturePropertyNames())
            {
                var texture = material.GetTexture(name);
                textures.Add(new JObject { ["property"] = name, ["name"] = texture ? texture.name : null,
                                           ["path"] = texture ? AssetDatabase.GetAssetPath(texture) : null });
            }
        var row =
            new JObject { ["location"] = id,
                          ["category"] = category,
                          ["root"] = root,
                          ["renderer"] = string.Join("/", hierarchy),
                          ["kind"] = renderer.GetType().Name,
                          ["component"] = Array.IndexOf(renderer.GetComponents<Renderer>(), renderer),
                          ["binding"] = binding,
                          ["slot"] = slot,
                          ["active"] = renderer.gameObject.activeSelf,
                          ["enabled"] = renderer.enabled,
                          ["material"] = material ? AssetDatabase.GetAssetPath(material) : null,
                          ["shader"] = material && material.shader ? material.shader.name : null,
                          ["keywords"] = new JArray(material ? material.shaderKeywords.OrderBy(key => key, StringComparer.Ordinal).ToArray()
                                                             : new string[0]),
                          ["queue"] = material ? material.renderQueue : -1,
                          ["textures"] = textures,
                          ["particleMode"] = particle ? particle.renderMode.ToString() : null,
                          ["particleMesh"] = particle && particle.mesh ? AssetDatabase.GetAssetPath(particle.mesh) : null,
                          ["particleMeshes"] = new JArray(meshes.Select(mesh => mesh ? AssetDatabase.GetAssetPath(mesh) : null)),
                          ["vertexStreams"] = new JArray(streams.Select(stream => stream.ToString())),
                          ["mapping"] = CombatMaterialMapping(material) };
        rows.Add(row);
        return row;
    }
    static JObject CombatMaterialMapping(Material material)
    {
        if (!material || !material.shader)
            return new JObject { ["outcome"] = "missing-material-or-shader" };
        string shader = material.shader.name;
        var standard = Resources.Load<TextAsset>("AndroidNativeStandardVariants");
        var families = Resources.Load<TextAsset>("AndroidNativeMaterialFamilies");
        JObject family = null;
        if (shader == "Hopoo Games/Deferred/Standard" && standard)
            family = JObject.Parse(standard.text);
        else if (families)
            family = JObject.Parse(families.text)["families"].OfType<JObject>().SingleOrDefault(row => (string)row["shader"] == shader);
        if (family != null)
        {
            var keys = family["features"].Values<string>().Where(key => material.IsKeywordEnabled(key)).OrderBy(key => key).ToArray();
            var variant =
                family["variants"].SingleOrDefault(row => row["keywords"].Values<string>().OrderBy(key => key).SequenceEqual(keys));
            string resource = variant == null ? null : (string)variant["resource"];
            var recovered = resource == null ? null : Resources.Load<Shader>(resource);
            return new JObject { ["outcome"] = recovered ? "recovered-resource-present" : "known-family-missing-resource-or-variant",
                                 ["features"] = new JArray(keys), ["resource"] = resource,
                                 ["editorSupported"] = recovered && recovered.isSupported };
        }
        bool nativeParticle = shader == "Mobile/Particles/Alpha Blended" || shader == "Particles/Standard Unlit" ||
                              shader == "Legacy Shaders/Particles/Additive" || shader == "Legacy Shaders/Particles/Additive (Soft)";
        return new JObject { ["outcome"] = nativeParticle ? "native-unity-particle" : "separate-or-approximate-path",
                             ["editorSupported"] = material.shader.isSupported };
    }
    sealed class ImportedAssetProvider : ResourceProviderBase
    {
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                var asset = AssetDatabase.LoadAssetAtPath(handle.Location.InternalId, handle.Type);
                if (!asset)
                    throw new Exception("Typed import missing: " + handle.Location.InternalId + " [" + handle.Type + "]");
                handle.Complete<UnityEngine.Object>(asset, true, null);
            }
            catch (Exception e)
            {
                WholeCatalogLoader.failures.Add(e.ToString());
                handle.Complete<UnityEngine.Object>(null, false, e);
            }
        }
    }
    static readonly Stack<IEnumerator> stack = new Stack<IEnumerator>();
    static string output;
    static AsyncOperationHandle? waiting;
    static double deadline;
    static void Log(string message, string trace, LogType kind)
    {
        if (kind == LogType.Error || kind == LogType.Exception || kind == LogType.Assert)
            WholeCatalogLoader.failures.Add(message + "\n" + trace);
    }
    static IEnumerator LoadAndInitialize(JObject manifest)
    {
        yield return WholeCatalogLoader.Load(manifest, typeof(ImportedAssetProvider).FullName);
        if (WholeCatalogLoader.failures.Count != 0)
            throw new Exception("Original provider loading reported errors");
        yield return WholeCatalogLoader.InitializeCatalogs();
    }
    public static void Begin(string manifestPath, string outputPath)
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode ||
            UnityEditor.BuildPipeline.isBuildingPlayer || stack.Count != 0)
            throw new Exception("Editor busy");
        output = outputPath;
        deadline = EditorApplication.timeSinceStartup + 240;
        waiting = null;
        var directory = Path.GetDirectoryName(output);
        var catalog = Path.Combine(directory, "host-empty-catalog.json");
        var settings = Path.Combine(directory, "host-settings.json");
        File.WriteAllText(
            catalog,
            "{\"m_LocatorId\":\"whole-host-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
        var settingsData = new ResourceManagerRuntimeData { BuildTarget = "Android", DisableCatalogUpdateOnStartup = true,
                                                            LogResourceManagerExceptions = true };
        settingsData.CatalogLocations.Add(new ResourceLocationData(new[] { ResourceManagerRuntimeData.kCatalogAddress }, catalog,
                                                                   typeof(ContentCatalogProvider), typeof(ContentCatalogData)));
        File.WriteAllText(settings, JsonUtility.ToJson(settingsData));
        string original = Addressables.RuntimePath + "/settings.json";
        Addressables.InternalIdTransformFunc = location => location.InternalId == original ? settings : location.InternalId;
        Addressables.ResourceManager.ResourceProviders.Add(new ImportedAssetProvider());
        stack.Push(LoadAndInitialize(JObject.Parse(File.ReadAllText(manifestPath))));
        Application.logMessageReceived += Log;
        EditorApplication.update += Tick;
    }
    static void Save(bool success, string error = null)
    {
        var text = Newtonsoft.Json.JsonConvert.SerializeObject(
            new { success, finished = stack.Count == 0 || error != null, phase = WholeCatalogLoader.phase,
                  progress = WholeCatalogLoader.progress, error, failures = WholeCatalogLoader.failures,
                  counts = WholeCatalogLoader.Counts() },
            Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(output + ".pending", text);
        if (File.Exists(output))
            File.Replace(output + ".pending", output, null);
        else
            File.Move(output + ".pending", output);
    }
    static void Tick()
    {
        try
        {
            // The preserved package's editor scheduler is internal, unlike newer APIs.
            typeof(UnityEngine.ResourceManagement.ResourceManager)
                .GetMethod("Update", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                .Invoke(Addressables.ResourceManager, new object[] { 0.016f });
            if (EditorApplication.timeSinceStartup > deadline)
                throw new TimeoutException("Original provider phase stalled");
            if (waiting.HasValue)
            {
                if (!waiting.Value.IsDone)
                    return;
                waiting = null;
            }
            for (int i = 0; i < 100 && stack.Count != 0; i++)
            {
                var top = stack.Peek();
                if (!top.MoveNext())
                {
                    stack.Pop();
                    continue;
                }
                var child = top.Current as IEnumerator;
                if (child != null)
                {
                    stack.Push(child);
                    continue;
                }
                if (top.Current is AsyncOperationHandle)
                {
                    waiting = (AsyncOperationHandle)top.Current;
                    break;
                }
                break;
            }
            if (stack.Count == 0)
            {
                Save(WholeCatalogLoader.failures.Count == 0);
                EditorApplication.update -= Tick;
                Application.logMessageReceived -= Log;
            }
            else
                Save(false);
        }
        catch (Exception e)
        {
            Save(false, e.ToString());
            stack.Clear();
            EditorApplication.update -= Tick;
            Application.logMessageReceived -= Log;
            Debug.LogException(e);
        }
    }
}
