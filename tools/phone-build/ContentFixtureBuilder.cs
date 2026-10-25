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
public static class ContentFixtureBuilder
{
    [Serializable] public sealed class BuildReceipt { public string unity; public string source_commit; public string build_report_guid; }
    static string Output(string name) { return Path.GetFullPath(Path.Combine(Application.dataPath, "../..", name)); }

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
