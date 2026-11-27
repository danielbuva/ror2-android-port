using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using UnityEditorInternal;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// One-shot exact-editor oracle/fixture; never used by the game build.
public static partial class ContentFixtureBuilder
{
    [Serializable] public sealed class BuildReceipt { public string unity; public string source_commit; public string build_report_guid; }
    static string Output(string name) { return Path.GetFullPath(Path.Combine(Application.dataPath, "../..", name)); }

    [Serializable] public sealed class NativeContentBundle { public string path; public string sha256; }
    [Serializable] public sealed class NativeMaterialTexture { public string property; public string texture; }
    [Serializable] public sealed class NativeMaterialReferences
    {
        public string shader;
        public List<NativeMaterialTexture> textures = new List<NativeMaterialTexture>();
    }
    [Serializable] public sealed class NativeContentAsset
    {
        public string name;
        public string type;
        public string subasset;
        public string loaded_name;
        public string loaded_type;
        public NativeMaterialReferences material;
        public NativeManifestEntry[] manifest;
    }
    [Serializable] public sealed class NativeManifestEntry
    {
        public string name;
        public string hash;
        public string[] dependencies;
    }
    [Serializable] public sealed class NativeContentRequest
    {
        public string path;
        public string sha256;
        public NativeContentBundle[] dependencies;
        public NativeContentAsset[] assets;
    }
    [Serializable] public sealed class NativeContentReceipt
    {
        public string unity;
        public string source_commit;
        public string request_sha256;
        public string path;
        public string sha256;
        public List<NativeContentBundle> dependencies = new List<NativeContentBundle>();
        public List<NativeContentAsset> assets = new List<NativeContentAsset>();
        public int count;
        public bool unloaded;
        public string failure;
    }

    static string FileHash(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static Type NativeContentType(string name)
    {
        switch (name)
        {
            case "LightingSettings": return typeof(LightingSettings);
            case "Mesh": return typeof(Mesh);
            case "Avatar": return typeof(Avatar);
            case "AnimationClip": return typeof(AnimationClip);
            case "Material": return typeof(Material);
            case "Shader": return typeof(Shader);
            case "Texture2D": return typeof(Texture2D);
            case "Cubemap": return typeof(Cubemap);
            case "Sprite": return typeof(Sprite);
            case "GameObject": return typeof(GameObject);
            case "AvatarMask": return typeof(AvatarMask);
            case "PhysicMaterial": return typeof(PhysicMaterial);
            case "SpeedTreeWindAsset": return typeof(Terrain).Assembly.GetType("UnityEngine.SpeedTreeWindAsset", throwOnError: true);
            case "AnimatorOverrideController": return typeof(AnimatorOverrideController);
            case "AssetBundleManifest": return typeof(AssetBundleManifest);
            default: throw new Exception("Unsupported native-content type: " + name);
        }
    }

    static NativeMaterialReferences ObserveMaterial(Material material)
    {
        var references = new NativeMaterialReferences { shader = material.shader == null ? "" : material.shader.name };
        using (var serialized = new SerializedObject(material))
        {
            var textures = serialized.FindProperty("m_SavedProperties.m_TexEnvs");
            if (textures == null || !textures.isArray)
                throw new Exception("Native Material saved texture array unavailable");
            for (int i = 0; i < textures.arraySize; i++)
            {
                var pair = textures.GetArrayElementAtIndex(i);
                var value = pair.FindPropertyRelative("second").FindPropertyRelative("m_Texture").objectReferenceValue;
                if (value != null)
                    references.textures.Add(new NativeMaterialTexture {
                        property = pair.FindPropertyRelative("first").stringValue, texture = value.name
                    });
            }
        }
        return references;
    }

    static NativeManifestEntry[] ObserveManifest(AssetBundleManifest manifest)
    {
        return Array.ConvertAll(manifest.GetAllAssetBundles(), name => new NativeManifestEntry {
            name = name,
            hash = manifest.GetAssetBundleHash(name).ToString(),
            dependencies = manifest.GetDirectDependencies(name)
        });
    }

    static void CheckNativeContent(string oracle)
    {
        string requestPath = Environment.GetEnvironmentVariable("ROR2_PHONE_NATIVE_CONTENT_CHECK");
        if (String.IsNullOrEmpty(requestPath)) return;
        var receipt = new NativeContentReceipt {
            unity = Application.unityVersion,
            source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE")
        };
        var bundles = new List<AssetBundle>();
        var loaded = new List<UnityEngine.Object>();
        try
        {
            if (!Path.IsPathRooted(requestPath)) throw new Exception("Absolute native-content request required");
            receipt.request_sha256 = FileHash(requestPath);
            var request = JsonUtility.FromJson<NativeContentRequest>(File.ReadAllText(requestPath));
            if (request == null || String.IsNullOrEmpty(request.path) || !Path.IsPathRooted(request.path)
                || request.assets == null || request.assets.Length == 0)
                throw new Exception("Native-content request needs absolute bundle path and typed assets");
            receipt.path = Path.GetFullPath(request.path);
            receipt.sha256 = FileHash(receipt.path);
            if (receipt.sha256 != request.sha256) throw new Exception("Native-content bundle SHA-256 mismatch");
            var assets = new HashSet<(string, string, string)>();
            foreach (var asset in request.assets)
                if (asset == null || String.IsNullOrEmpty(asset.name) || String.IsNullOrEmpty(asset.type)
                    || !assets.Add((asset.name, asset.type, asset.subasset ?? "")))
                    throw new Exception("Native-content asset name/type absent, duplicated or unsupported");
            foreach (var dependency in request.dependencies ?? Array.Empty<NativeContentBundle>())
            {
                if (!Path.IsPathRooted(dependency.path) || FileHash(dependency.path) != dependency.sha256)
                    throw new Exception("Native-content dependency path or SHA-256 mismatch");
                var dependencyBundle = AssetBundle.LoadFromFile(dependency.path);
                if (dependencyBundle == null) throw new Exception("Native-content dependency failed to load: " + dependency.path);
                bundles.Add(dependencyBundle);
                receipt.dependencies.Add(new NativeContentBundle {
                    path = Path.GetFullPath(dependency.path), sha256 = dependency.sha256
                });
            }
            var bundle = AssetBundle.LoadFromFile(receipt.path);
            if (bundle == null) throw new Exception("Native-content bundle failed to load");
            bundles.Add(bundle);
            foreach (var asset in request.assets)
            {
                var type = NativeContentType(asset.type);
                var value = String.IsNullOrEmpty(asset.subasset) ? bundle.LoadAsset(asset.name, type)
                    : Array.Find(bundle.LoadAssetWithSubAssets(asset.name, type), item => item.name == asset.subasset);
                if (value == null || value.GetType() != type)
                    throw new Exception("Native-content typed load failed: " + asset.name + " as " + type.FullName);
                loaded.Add(value);
                receipt.assets.Add(new NativeContentAsset {
                    name = asset.name, type = asset.type, subasset = asset.subasset, loaded_name = value.name, loaded_type = value.GetType().FullName,
                    material = asset.material != null && value is Material material ? ObserveMaterial(material) : null,
                    manifest = asset.manifest != null && value is AssetBundleManifest manifest ? ObserveManifest(manifest) : null
                });
                receipt.count = loaded.Count;
            }
            if (FileHash(receipt.path) != receipt.sha256) throw new Exception("Native-content bundle changed during load");
            foreach (var dependency in receipt.dependencies)
                if (FileHash(dependency.path) != dependency.sha256)
                    throw new Exception("Native-content dependency changed during load: " + dependency.path);
        }
        catch (Exception error) { receipt.failure = error.ToString(); throw; }
        finally
        {
            try
            {
                if (bundles.Count != 0)
                {
                    for (int i = bundles.Count - 1; i >= 0; i--)
                        bundles[i].Unload(true);
                    receipt.unloaded = bundles.TrueForAll(value => value == null) && loaded.TrueForAll(value => value == null);
                    if (!receipt.unloaded) throw new Exception("Native-content objects survived unload");
                }
            }
            catch (Exception error) { receipt.failure = error.ToString(); throw; }
            finally
            {
                File.WriteAllText(Path.Combine(Path.GetDirectoryName(oracle), "native-content-check.json"), JsonUtility.ToJson(receipt, true));
            }
        }
    }

    [Serializable] public sealed class NativeScriptReceipt
    {
        public string unity;
        public string source_commit;
        public string class_name;
        public string properties_hash;
        public string serialized_file;
        public long serialized_bytes;
        public string serialized_sha256;
        public string failure;
    }

    static void CheckNativeScript(string oracle)
    {
        string attempt = Path.GetDirectoryName(oracle);
        var receipt = new NativeScriptReceipt {
            unity = Application.unityVersion,
            source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"),
            serialized_file = "native-script-schema.assets"
        };
        GameObject instance = null;
        try
        {
            instance = new GameObject("NativeScriptSchemaFixture");
            var fixture = instance.AddComponent<NativeScriptSchemaFixture>();
            fixture.control = 7;
            fixture.propertyName = new PropertyName("authored-native-field");
            fixture.exposedReference = new ExposedReference<GameObject> {
                exposedName = new PropertyName("authored-native-reference"), defaultValue = instance
            };
            fixture.vector2Int = new Vector2Int(1, 2);
            fixture.vector2IntArray = new[] { new Vector2Int(3, 4) };
            fixture.vector2IntList = new List<Vector2Int> { new Vector2Int(5, 6) };
            fixture.vector3Int = new Vector3Int(7, 8, 9);
            var script = MonoScript.FromMonoBehaviour(fixture);
            if (script == null || script.GetClass() != typeof(NativeScriptSchemaFixture))
                throw new Exception("Native fixture MonoScript class association failed");
            receipt.class_name = script.GetClass().FullName;
            var method = typeof(MonoScript).GetMethod("GetPropertiesHashString",
                BindingFlags.Instance | BindingFlags.NonPublic, null, Type.EmptyTypes, null);
            if (method == null) throw new Exception("Native MonoScript hash API unavailable");
            receipt.properties_hash = (string)method.Invoke(script, null);
            if (String.IsNullOrEmpty(receipt.properties_hash)) throw new Exception("Native MonoScript hash empty");
            string path = Path.Combine(attempt, receipt.serialized_file);
            // The imported MonoScript is persistent; this API saves only the
            // temporary authored objects, retaining their script reference.
            InternalEditorUtility.SaveToSerializedFileAndForget(
                new UnityEngine.Object[] { instance, instance.transform, fixture }, path, false);
            byte[] data = File.ReadAllBytes(path);
            receipt.serialized_bytes = data.LongLength;
            if (data.Length == 0) throw new Exception("Native fixture serialized file empty");
            using (var hash = SHA256.Create())
                receipt.serialized_sha256 = BitConverter.ToString(hash.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
            // Binary output is evidence, not a claim that the native save retains type trees.
            // The host must inspect its actual metadata before using any schema as a hash operand.
        }
        catch (Exception error) { receipt.failure = error.ToString(); throw; }
        finally
        {
            if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
            File.WriteAllText(Path.Combine(attempt, "native-script-schema.json"), JsonUtility.ToJson(receipt, true));
        }
    }

    public static void Check()
    {
        if (Application.unityVersion != "2021.3.45f2") throw new Exception("Exact editor required");
        var report = ContentFixture.Check(Path.Combine(Application.streamingAssetsPath, "phone-fixture.bundle"));
        var oracle = Environment.GetEnvironmentVariable("ROR2_PHONE_ORACLE_REPORT");
        if (String.IsNullOrEmpty(oracle)) throw new Exception("Explicit oracle report required");
        File.WriteAllText(oracle, JsonUtility.ToJson(report, true));
        if (!report.bundleLoaded || !report.textMatched || !report.unloaded || !String.IsNullOrEmpty(report.failure))
            throw new Exception("Content fixture failed; inspect the explicit oracle report");
        CheckNativeScript(oracle);
        CheckNativeContent(oracle);
    }

    public static void Build()
    {
        Check();
        PlayerSettings.companyName = "Porting Laboratory";
        PlayerSettings.productName = "Phone Content Fixture";
        PlayerSettings.bundleVersion = "0.0.2";
        PlayerSettings.Android.bundleVersionCode = 2;
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.ror2lab.phonecontentfixture");
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
        PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
        PlayerSettings.Android.useCustomKeystore = false;
        EditorUserBuildSettings.buildAppBundle = false;
        PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
        PlayerSettings.stripEngineCode = false;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
        new GameObject("PhoneContentFixture").AddComponent<ContentFixture>();
        EditorSceneManager.SaveScene(scene, "Assets/Fixture.unity");
        var report = BuildPipeline.BuildPlayer(new[] { "Assets/Fixture.unity" }, Output("phone-content-fixture.apk"), BuildTarget.Android, BuildOptions.Development);
        if (report.summary.result != BuildResult.Succeeded) throw new Exception("Fixture build failed: " + report.summary.result);
        var receipt = new BuildReceipt { unity = Application.unityVersion, source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"), build_report_guid = report.summary.guid.ToString() };
        string attempt = Path.GetDirectoryName(Environment.GetEnvironmentVariable("ROR2_PHONE_ORACLE_REPORT"));
        File.WriteAllText(Path.Combine(attempt, "player-build.json"), JsonUtility.ToJson(receipt, true));
    }
}
