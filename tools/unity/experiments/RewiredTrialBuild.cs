using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class RewiredTrialBuild
{
    [Serializable] public class Result { public bool success; public string apk, result; public int errors; public double seconds; }
    [MenuItem("Porting Lab/Build Rewired Trial Reference")]
    public static void Queue()
    {
        if (BuildPipeline.isBuildingPlayer) throw new InvalidOperationException("A build is already active");
        EditorApplication.update -= StartBuild;
        EditorApplication.update += StartBuild;
    }
    static void StartBuild() { EditorApplication.update -= StartBuild; Build(); }
    static void Build()
    {
        if (!Application.dataPath.EndsWith("/rewired-trial-reference/Assets")) throw new InvalidOperationException("Wrong reference project");
        string output = Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
        var started = DateTime.UtcNow;
        var result = new Result { apk = Path.Combine(output,"rewired-trial-arm64.apk") };
        File.WriteAllText(Path.Combine(output,"trial-build-start.json"),"{\"startedUtc\":\""+started.ToString("o")+"\"}");
        try
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camera = new GameObject("Reference Camera").AddComponent<Camera>(); camera.backgroundColor = Color.black; camera.clearFlags = CameraClearFlags.SolidColor;
            new GameObject("Reference Light").AddComponent<Light>().type = LightType.Directional;
            var source = new SerializedObject(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/ReferenceInput/GameInputManager.prefab").GetComponent<Rewired.InputManager>());
            var go = new GameObject("Trial Input Manager — copied game data"); go.SetActive(false);
            var manager = go.AddComponent<Rewired.InputManager>();
            var destination = new SerializedObject(manager);
            var property = source.GetIterator();
            bool enterChildren = true;
            while (property.Next(enterChildren))
            {
                enterChildren = false;
                if (property.name.StartsWith("_")) destination.CopyFromSerializedProperty(property);
            }
            destination.ApplyModifiedPropertiesWithoutUndo(); destination.Update();
            if (destination.FindProperty("_userData.actions").arraySize != source.FindProperty("_userData.actions").arraySize ||
                destination.FindProperty("_controllerDataFiles").objectReferenceValue == null ||
                destination.FindProperty("_controllerDataFiles").objectReferenceValue != source.FindProperty("_controllerDataFiles").objectReferenceValue)
                throw new InvalidOperationException("Reference scene did not retain the source action data and controller registry");
            go.SetActive(true);
            var probe = new GameObject("Bounded SDK Physical Probe").AddComponent<RewiredTrialControllerProbe>();
            probe.attempt = new DirectoryInfo(output).Name;
            var actions = source.FindProperty("_userData.actions");
            probe.expectedActionIds = Enumerable.Range(0,actions.arraySize).Select(i => actions.GetArrayElementAtIndex(i).FindPropertyRelative("_id").intValue).ToArray();
            EditorSceneManager.SaveScene(scene,"Assets/ReferenceInput/ControllerProbe.unity");
            // Reuse the expressly owned disposable lab identity and installation guards.
            // Host lab source and proprietary input remain untouched; APK rollback retained.
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android,"dev.ror2lab.arm64");
            PlayerSettings.companyName = "PortingLab"; PlayerSettings.productName = "Rewired Trial Reference";
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android,ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel23;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel30;
            PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android,false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android,new[]{GraphicsDeviceType.Vulkan});
            EditorUserBuildSettings.buildAppBundle = false;
            var build = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[]{"Assets/ReferenceInput/ControllerProbe.unity"}, locationPathName = result.apk, target = BuildTarget.Android, options = BuildOptions.Development });
            result.errors = (int)build.summary.totalErrors; result.result = build.summary.result.ToString(); result.success = build.summary.result == BuildResult.Succeeded;
        }
        catch (Exception e) { result.result = e.ToString(); Debug.LogException(e); }
        result.seconds = (DateTime.UtcNow-started).TotalSeconds;
        File.WriteAllText(Path.Combine(output,"trial-build-result.json"),JsonUtility.ToJson(result,true));
        Debug.Log("REWIRED_TRIAL_BUILD_RESULT " + JsonUtility.ToJson(result));
    }
}
