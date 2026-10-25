using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

public sealed class WholeItemBehaviorPreservation : UnityEditor.Build.IPreprocessBuildWithReport
{
    public int callbackOrder
    {
        get {
            return -100;
        }
    }
    public void OnPreprocessBuild(UnityEditor.Build.Reporting.BuildReport report)
    {
        var types =
            typeof(RoR2.CharacterBody)
                .Assembly.GetTypes()
                .SelectMany(type => type.GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic |
                                                    System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.DeclaredOnly))
                .Where(method => Attribute.IsDefined(method, typeof(RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute)))
                .SelectMany(method =>
                            {
                                var association = (RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute)Attribute.GetCustomAttribute(
                                    method, typeof(RoR2.Items.BaseItemBodyBehavior.ItemDefAssociationAttribute));
                                return new[] { method.DeclaringType, association.behaviorTypeOverride ?? method.DeclaringType };
                            })
                .Distinct()
                .OrderBy(type => type.FullName)
                .ToArray();
        string directory = "Assets/LabLoadingScene/WholeCatalogPreservation";
        if (!Directory.Exists(directory))
            return;
        var root = new System.Xml.Linq.XElement(
            "linker", new System.Xml.Linq.XElement(
                          "assembly", new System.Xml.Linq.XAttribute("fullname", typeof(RoR2.CharacterBody).Assembly.GetName().Name),
                          types.Select(type => new System.Xml.Linq.XElement(
                                           "type", new System.Xml.Linq.XAttribute("fullname", type.FullName.Replace('+', '/')),
                                           new System.Xml.Linq.XAttribute("preserve", "all")))));
        directory = Path.Combine(directory, "item-behaviors");
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, "link.xml");
        File.WriteAllText(path, root.ToString());
        AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
    }
}
public static class WholeCatalogBuild
{
    static JObject catalog;
    static string root;
    static readonly Dictionary<int, string> cameraShaderLocations = new Dictionary<int, string>
    {
        { 16022, "41e90cbc5ad198a438128b019f8d8553" }, // HGOutlineHighlight
        { 16025, "5e246b703e2090148a761d52af19744b" }, // HGVisionLimit
        { 15950, "c14b6abb309b8c246add9e94a6920d7f" }, // RampFog
        { 2537, "e4abd95960ed75f4a9f59cac7c40bd9d" },  // TranslucentImage DownTent
        { 2538, "12e87e7c7fde8e74db9f75172456c5c3" }, // TranslucentImage EfficientBlur
        { 2539, "d996ab4381100014d99e25e68e9aac84" }, // TranslucentImage FillCrop
        { 2540, "b12e02e9a9b684543a286089a03cb04b" }, // TranslucentImage QuickDumbBlur
        { 16024, "780f79b2a62a0df439dedf59c533eee6" }, // SobelBuffer
        { 15952, "7d6541fe01591cd418caf48d3c099e52" }, // SobelOutline
    };
    const string ShaderLocationType = "UnityEngine.Shader, UnityEngine.CoreModule, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null";

    static void ValidateCameraShaderRows(ISet<string> ownerPaths = null, bool requireBuiltBundles = false)
    {
        var locations = catalog["locations"].ToDictionary(row => (int)row["id"]);
        var keys = catalog["keys"].Where(row => (string)row["keyType"] == "System.String")
                         .ToDictionary(row => (string)row["key"], row => row);
        foreach (var expected in cameraShaderLocations)
        {
            if (!locations.TryGetValue(expected.Key, out var row) || (string)row["type"] != ShaderLocationType ||
                row["root"]?.Value<bool>() != true)
                throw new Exception("Original camera shader row missing or changed: " + expected.Key);
            if (!keys.TryGetValue(expected.Value, out var key) || !key["locations"].Any(value => (int)value == expected.Key))
                throw new Exception("Original camera shader address key changed: " + expected.Value);
            string path = (string)row["path"];
            string bundle = (string)row["bundle"];
            if (string.IsNullOrEmpty(path) || string.IsNullOrEmpty(bundle) || ownerPaths != null && !ownerPaths.Contains(path))
                throw new Exception("Original camera shader has no exact bundle owner: " + expected.Key);
            if (requireBuiltBundles && (catalog["bundles"][bundle] == null || !File.Exists(Path.Combine(root, "generated-android-data", bundle))))
                throw new Exception("Original camera shader bundle was not built: " + expected.Key);
        }
    }

    public static void Append(string work, List<AssetBundleBuild> builds)
    {
        string recipe = Path.Combine(work, "whole-catalog-build.json");
        if (!File.Exists(recipe))
        {
            catalog = null;
            return;
        }
        root = work;
        var config = JObject.Parse(File.ReadAllText(recipe));
        string manifest = Path.GetFullPath((string)config["manifest"]);
        if (!manifest.StartsWith(Path.Combine(work, "experiments/whole-catalog") + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new Exception("Whole catalog recipe outside owned input");
        catalog = JObject.Parse(File.ReadAllText(manifest));
        ValidateSourceCameraPrograms();
        ValidateSourceCollisionPolicy();
        var owners = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var build in builds)
            foreach (string path in build.assetNames)
            {
                if (owners.ContainsKey(path))
                    throw new Exception("Duplicate explicit bundle ownership: " + path);
                owners.Add(path, build.assetBundleName);
            }
        var paths = catalog["locations"]
                        .Select(x => (string)x["path"])
                        .Distinct(StringComparer.OrdinalIgnoreCase)
                        .Where(x => !owners.ContainsKey(x))
                        .ToArray();
        foreach (var path in paths)
            if (!path.StartsWith("Assets/", StringComparison.Ordinal) || !File.Exists(path))
                throw new Exception("Whole catalog input missing: " + path);
        var ordinary = paths.Where(x => !x.EndsWith(".unity", StringComparison.OrdinalIgnoreCase)).ToArray();
        builds.Add(new AssetBundleBuild { assetBundleName = "whole-game-content", assetNames = ordinary });
        foreach (var path in ordinary)
            owners.Add(path, "whole-game-content");
        foreach (string path in paths.Where(x => x.EndsWith(".unity", StringComparison.OrdinalIgnoreCase)))
        {
            string name = "whole-scene-" + Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
            if (builds.Any(x => x.assetBundleName == name))
                throw new Exception("Scene bundle name collision");
            builds.Add(new AssetBundleBuild { assetBundleName = name, assetNames = new[] { path } });
            owners.Add(path, name);
        }
        foreach (var row in catalog["locations"])
            row["bundle"] = owners[(string)row["path"]];
        ValidateCameraShaderRows(new HashSet<string>(owners.Keys, StringComparer.OrdinalIgnoreCase));
    }

    // Compare imported settings with the locally generated original-input receipt.
    public static object ValidateSourceCollisionPolicy()
    {
        var path = Path.Combine(Path.GetDirectoryName(Application.dataPath), ".rebuild/source-collision-policy.json");
        var expected = JObject.Parse(File.ReadAllText(path));
        var rows = expected["rows"].ToObject<uint[]>();
        var layers = expected["layers"].ToObject<string[]>();
        if (rows.Length != 32 || layers.Length != 32)
            throw new Exception("Original collision policy dimensions changed");
        int pairs = 0;
        for (int a = 0; a < 32; a++)
        {
            if (LayerMask.LayerToName(a) != layers[a])
                throw new Exception("Collision policy layer index differs from its accepted source");
            for (int b = a; b < 32; b++)
            {
                bool collides = (rows[a] & (1u << b)) != 0;
                if (Physics.GetIgnoreLayerCollision(a, b) == collides)
                    throw new Exception("Collision policy differs from accepted source at " + a + "/" + b);
                pairs++;
            }
        }
        return new { sourcePolicyVerified = true, unorderedPairs = pairs,
                     projectileSelfIgnored = Physics.GetIgnoreLayerCollision(14, 14),
                     projectileWorldCollides = !Physics.GetIgnoreLayerCollision(14, 11),
                     projectileHurtBoxCollides = !Physics.GetIgnoreLayerCollision(14, 12) };
    }

    // The existing optional source-camera batch owns these Resources assets.
    // Exercise the real editor importer before building.
    public static void ValidateSourceCameraPrograms()
    {
        const string receiptPath = ".rebuild/postprocessing-uber-receipt.json";
        if (!File.Exists(receiptPath))
            return;
        var programs = JObject.Parse(File.ReadAllText(receiptPath))["programs"] as JArray;
        if (programs == null)
            return; // Historical Uber-only receipts remain readable.
        foreach (var program in programs)
        {
            string path = (string)program["target"];
            if (path.EndsWith(".compute", StringComparison.Ordinal))
            {
                var shader = AssetDatabase.LoadAssetAtPath<ComputeShader>(path);
                if (!shader)
                    throw new Exception("Source camera compute import missing: " + path);
                foreach (var message in ShaderUtil.GetComputeShaderMessages(shader))
                    if (message.severity.ToString() == "Error")
                        throw new Exception("Source camera compute compile error: " + path + ": " + message.message);
                var kernels = (JArray)program["kernels"];
                var groups = (JArray)program["kernel_thread_groups"];
                for (int i = 0; i < kernels.Count; i++)
                {
                    string kernel = (string)kernels[i];
                    if (!shader.HasKernel(kernel))
                        throw new Exception("Source camera compute kernel missing: " + kernel);
                    shader.GetKernelThreadGroupSizes(shader.FindKernel(kernel), out uint x, out uint y, out uint z);
                    if (x != (uint)groups[i][0] || y != (uint)groups[i][1] || z != (uint)groups[i][2])
                        throw new Exception("Source camera compute thread group differs: " + kernel);
                }
            }
            else
            {
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(path);
                if (!shader || !shader.isSupported || ShaderUtil.ShaderHasError(shader))
                    throw new Exception("Source camera graphics shader import failed: " + path);
            }
        }
    }
    public static void Complete(AssetBundleManifest manifest)
    {
        if (catalog == null)
            return;
        var bundles = new JObject();
        string output = Path.Combine(root, "generated-android-data");
        foreach (string name in manifest.GetAllAssetBundles())
        {
            string path = Path.Combine(output, name);
            string hash;
            using (var stream = File.OpenRead(path)) using (var sha = System.Security.Cryptography.SHA256.Create()) hash =
                BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
            bundles[name] = JObject.FromObject(
                new { sha256 = hash, bytes = new FileInfo(path).Length, dependencies = manifest.GetAllDependencies(name) });
        }
        catalog["bundles"] = bundles;
        ValidateCameraShaderRows(requireBuiltBundles: true);
        File.WriteAllText(Path.Combine(output, "whole-catalog.json"), catalog.ToString(Newtonsoft.Json.Formatting.None));
    }
}
