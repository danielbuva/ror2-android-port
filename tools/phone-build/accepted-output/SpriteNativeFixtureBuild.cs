// Editor-only build owner for the separate disposable SDK diagnostic package.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class SpriteNativeFixtureBuild
{
    [Serializable] sealed class Result { public bool success; public string apk, error; }

    [MenuItem("Tools/P1/Build Sprite Android Fixture")]
    public static void Schedule() { EditorApplication.delayCall += Build; }

    static void Build()
    {
        string root = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        var result = new Result { apk = Path.Combine(root, "sprite-fixture.apk") };
        try
        {
            if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException("Exact SDK version required");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Fixture Camera").AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.gameObject.AddComponent<SpriteNativeFixtureRunner>();
            EditorSceneManager.SaveScene(scene, "Assets/SpriteFixture.unity");
            PlayerSettings.companyName = "LocalLab";
            PlayerSettings.productName = "Sprite SDK Fixture";
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.ror2lab.spritefixture");
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
            PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
            PlayerSettings.Android.useCustomKeystore = false;
            EditorUserBuildSettings.buildAppBundle = false;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { "Assets/SpriteFixture.unity" }, locationPathName = result.apk,
                target = BuildTarget.Android, options = BuildOptions.Development
            });
            result.success = report.summary.result == BuildResult.Succeeded;
            if (!result.success) result.error = "Build failed: " + report.summary.result;
        }
        catch (Exception error) { result.error = error.ToString(); }
        File.WriteAllText(Path.Combine(root, "android-build-result.json"), JsonUtility.ToJson(result, true));
    }
}
