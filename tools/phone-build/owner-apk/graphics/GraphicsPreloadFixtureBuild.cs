// Editor-only owner for the separate authored preload qualification package.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class GraphicsPreloadFixtureBuild
{
    const string Plugin = "Assets/Plugins/Android/arm64-v8a/libGraphicsDriverPreload.so";
    [Serializable] sealed class Result
    {
        public bool success, preloaded, editor_compatible, custom_driver_loaded;
        public string source_commit, failure;
    }

    public static void Build()
    {
        var result = new Result { source_commit = Environment.GetEnvironmentVariable("ROR2_GRAPHICS_PRELOAD_COMMIT") };
        string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        try
        {
            if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException();
            var importer = AssetImporter.GetAtPath(Plugin) as PluginImporter;
            if (importer == null || !importer.isNativePlugin) throw new InvalidOperationException();
            importer.SetCompatibleWithAnyPlatform(false);
            importer.SetCompatibleWithEditor(false);
            importer.SetCompatibleWithPlatform(BuildTarget.Android, true);
            importer.SetPlatformData(BuildTarget.Android, "CPU", "ARM64");
            importer.isPreloaded = true;
            importer.SaveAndReimport();
            importer = AssetImporter.GetAtPath(Plugin) as PluginImporter;
            result.preloaded = importer != null && importer.isPreloaded;
            result.editor_compatible = importer == null || importer.GetCompatibleWithEditor();
            if (!result.preloaded || result.editor_compatible) throw new InvalidOperationException();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Preload fixture camera").AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.gameObject.AddComponent<GraphicsPreloadFixture>();
            EditorSceneManager.SaveScene(scene, "Assets/GraphicsPreloadFixture.unity");
            PlayerSettings.companyName = "LocalLab";
            PlayerSettings.productName = "Graphics preload fixture";
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.ror2lab.graphicspreload");
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel28;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
            EditorUserBuildSettings.buildAppBundle = false;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { "Assets/GraphicsPreloadFixture.unity" },
                locationPathName = Path.Combine(output, "graphics-preload-fixture.apk"),
                target = BuildTarget.Android, options = BuildOptions.Development
            });
            result.success = report.summary.result == BuildResult.Succeeded && report.summary.totalErrors == 0;
            if (!result.success) result.failure = "player-build-failed";
        }
        catch (Exception) { result.failure = "preload-build-contract-failed"; }
        File.WriteAllText(Path.Combine(output, "build-result.json"), JsonUtility.ToJson(result));
    }
}
