using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using OwnerConversion;

// Exact-editor diagnostic builder, never a public converter input provider.
// Stage this file under Assets/Editor and the runtime files under Assets.
public static class RuntimeEnvironmentFixture
{
    [Serializable] sealed class Receipt
    {
        public bool success;
        public string unity_version, apk, bundle, error;
    }

    [MenuItem("Tools/P1/Build Runtime Environment Fixture")]
    public static void Build()
    {
        string output = Directory.GetParent(Directory.GetParent(Application.dataPath).FullName).FullName;
        var receipt = new Receipt { unity_version = Application.unityVersion };
        try
        {
            if (Application.unityVersion != "2021.3.45f2") throw new Exception("Exact SDK required");
            PlayerSettings.companyName = "Porting Laboratory";
            PlayerSettings.productName = "Owner Environment Fixture";
            PlayerSettings.bundleVersion = "0.0.1";
            PlayerSettings.Android.bundleVersionCode = 1;
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.ror2lab.environmentfixture");
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
            PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Low);
            PlayerSettings.stripEngineCode = false;
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
            EditorUserBuildSettings.buildAppBundle = false;
            var sky = new Material(Shader.Find("Skybox/Procedural"));
            AssetDatabase.CreateAsset(sky, "Assets/SourceSky.mat");
            AssetDatabase.SaveAssets();
            string built = Path.Combine(output, "built");
            Directory.CreateDirectory(built);
            var manifest = BuildPipeline.BuildAssetBundles(built, new[] {
                new AssetBundleBuild { assetBundleName = "source-sky", assetNames = new[] { "Assets/SourceSky.mat" } }
            }, BuildAssetBundleOptions.ChunkBasedCompression, BuildTarget.Android);
            if (!manifest) throw new Exception("SDK source sky bundle failed");
            receipt.bundle = Path.Combine(built, "source-sky");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Color.black;
            var owner = new GameObject("Owner environment tool");
            owner.AddComponent<RuntimeEnvironmentProducer>();
            owner.AddComponent<RuntimeEnvironmentTool>();
            EditorSceneManager.SaveScene(scene, "Assets/Environment.unity");
            receipt.apk = Path.Combine(output, "environment-fixture.apk");
            var report = BuildPipeline.BuildPlayer(new[] { "Assets/Environment.unity" }, receipt.apk,
                BuildTarget.Android, BuildOptions.Development);
            if (report.summary.result != BuildResult.Succeeded) throw new Exception("Tool player build failed: " + report.summary.result);
            receipt.success = true;
        }
        catch (Exception error) { receipt.error = error.ToString(); }
        File.WriteAllText(Path.Combine(output, "android-build-result.json"), JsonUtility.ToJson(receipt, true));
    }
}
