using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// One-shot exact-editor oracle/fixture; never used by the game build.
public static class ContentFixtureBuilder
{
    static string Output(string name) { return Path.GetFullPath(Path.Combine(Application.dataPath, "../..", name)); }

    public static void Check()
    {
        var report = ContentFixture.Check(Path.Combine(Application.streamingAssetsPath, "phone-fixture.bundle"));
        File.WriteAllText(Output("editor-content-report.json"), JsonUtility.ToJson(report, true));
        if (!report.bundleLoaded || !report.textMatched || !report.unloaded || !String.IsNullOrEmpty(report.failure))
            throw new Exception("Content fixture failed; inspect editor-content-report.json");
    }

    public static void Build()
    {
        if (Application.unityVersion != "2021.3.45f2") throw new Exception("Exact editor required");
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
    }
}
