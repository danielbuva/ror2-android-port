using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
public static class BootstrapBuild
{
    public static void Build()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var camera = new GameObject("Bootstrap Camera").AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.025f, 0.19f, 0.28f);
        camera.gameObject.AddComponent<BootstrapMarker>();
        EditorSceneManager.SaveScene(camera.gameObject.scene, "Assets/Bootstrap.unity");
        PlayerSettings.companyName = "LocalBootstrap";
        PlayerSettings.productName = "ARM64 Bootstrap Smoke";
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "dev.localbootstrap.arm64smoke");
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
        PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
        PlayerSettings.Android.useCustomKeystore = false;
        EditorUserBuildSettings.buildAppBundle = false;
        string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../builds/bootstrap-arm64.apk"));
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { "Assets/Bootstrap.unity" }, locationPathName = output,
            target = BuildTarget.Android, options = BuildOptions.Development
        });
        if (report.summary.result != BuildResult.Succeeded) throw new Exception("Bootstrap build failed: " + report.summary.result);
        Debug.Log("BOOTSTRAP_BUILD_OK " + output);
    }
}
