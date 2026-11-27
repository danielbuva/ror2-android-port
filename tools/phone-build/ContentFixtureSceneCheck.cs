using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static partial class ContentFixtureBuilder
{
    [Serializable] sealed class SceneCheckRequest
    {
        public string path;
        public string sha256;
        public NativeContentBundle[] dependencies;
        public string scene;
        public string loadMode;
    }

    [Serializable] sealed class SceneCheckReport
    {
        public string unity;
        public string sourceCommit;
        public string bundleSha256;
        public string scenePath;
        public string loadMode;
        public int roots;
        public int meshRenderers;
        public bool occlusionDataResolved;
        public int umbraBeforeLoad;
        public int umbraBeforeActivation;
        public int umbraAfterActivation;
        public bool unloaded;
        public string failure;
    }

    static SceneCheckRequest sceneRequest;
    static SceneCheckReport sceneReport;
    static readonly List<AssetBundle> sceneBundles = new List<AssetBundle>();
    static Scene hostScene;
    static Scene streamedScene;
    static LoadSceneMode sceneLoadMode;
    static AsyncOperation sceneOperation;
    static bool unloadingScene;
    static double sceneCheckDeadline;

    public static void BeginSceneCheck()
    {
        sceneReport = new SceneCheckReport {
            unity = Application.unityVersion,
            sourceCommit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"),
        };
        try
        {
            if (Application.unityVersion != "2021.3.45f2")
                throw new Exception("Exact editor required");
            sceneRequest = JsonUtility.FromJson<SceneCheckRequest>(File.ReadAllText(
                Environment.GetEnvironmentVariable("ROR2_PHONE_NATIVE_CONTENT_CHECK")));
            sceneLoadMode = sceneRequest.loadMode == "Single" ? LoadSceneMode.Single : LoadSceneMode.Additive;
            sceneReport.loadMode = sceneLoadMode.ToString();
            var blank = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            if (!EditorSceneManager.SaveScene(blank, "Assets/SceneCheckHost.unity"))
                throw new Exception("Could not save the empty fixture scene");
            EditorSettings.enterPlayModeOptionsEnabled = true;
            EditorSettings.enterPlayModeOptions = EnterPlayModeOptions.DisableDomainReload;
            sceneCheckDeadline = EditorApplication.timeSinceStartup + 180;
            EditorApplication.update += TickSceneCheck;
            EditorApplication.EnterPlaymode();
        }
        catch (Exception error) { FinishSceneCheck(error); }
    }

    static AssetBundle LoadSceneCheckBundle(string path, string expectedHash)
    {
        if (FileHash(path) != expectedHash)
            throw new Exception("Native scene bundle SHA-256 changed");
        var bundle = AssetBundle.LoadFromFile(path);
        if (!bundle) throw new Exception("Unity failed to load native scene input " + path);
        sceneBundles.Add(bundle);
        return bundle;
    }

    static void TickSceneCheck()
    {
        try
        {
            if (EditorApplication.timeSinceStartup > sceneCheckDeadline)
                throw new Exception("Timed out loading or unloading the streamed scene");
            if (!EditorApplication.isPlaying) return;
            if (sceneOperation == null)
            {
                hostScene = SceneManager.GetActiveScene();
                foreach (var dependency in sceneRequest.dependencies ?? Array.Empty<NativeContentBundle>())
                    LoadSceneCheckBundle(dependency.path, dependency.sha256);
                var bundle = LoadSceneCheckBundle(sceneRequest.path, sceneRequest.sha256);
                sceneReport.bundleSha256 = sceneRequest.sha256;
                var path = sceneRequest.scene;
                if (!bundle.isStreamedSceneAssetBundle || Array.IndexOf(bundle.GetAllScenePaths(), path) < 0)
                    throw new Exception("Pinned scene path is absent from the streamed bundle: " + path);
                sceneReport.umbraBeforeLoad = StaticOcclusionCulling.umbraDataSize;
                sceneOperation = SceneManager.LoadSceneAsync(path, sceneLoadMode);
                if (sceneOperation == null) throw new Exception("Unity did not start the streamed scene load");
                return;
            }
            if (!sceneOperation.isDone) return;
            if (unloadingScene)
            {
                sceneReport.unloaded = !SceneManager.GetSceneByPath(sceneRequest.scene).isLoaded;
                FinishSceneCheck(null);
                return;
            }

            ObserveStreamedScene();
            if (sceneLoadMode == LoadSceneMode.Single)
                hostScene = SceneManager.CreateScene("SceneCheckCleanup");
            if (!SceneManager.SetActiveScene(hostScene))
                throw new Exception("Could not restore the fixture scene");
            sceneOperation = SceneManager.UnloadSceneAsync(streamedScene);
            if (sceneOperation == null) throw new Exception("Unity did not start the streamed scene unload");
            unloadingScene = true;
        }
        catch (Exception error) { FinishSceneCheck(error); }
    }

    static void ObserveStreamedScene()
    {
        streamedScene = SceneManager.GetSceneByPath(sceneRequest.scene);
        if (!streamedScene.isLoaded)
            throw new Exception("Unity did not load the pinned scene");
        sceneReport.scenePath = streamedScene.path;
        var roots = streamedScene.GetRootGameObjects();
        sceneReport.roots = roots.Length;
        foreach (var root in roots)
            sceneReport.meshRenderers += root.GetComponentsInChildren<MeshRenderer>(true).Length;
        sceneReport.umbraBeforeActivation = StaticOcclusionCulling.umbraDataSize;
        if (SceneManager.GetActiveScene() != streamedScene && !SceneManager.SetActiveScene(streamedScene))
            throw new Exception("Unity could not activate the pinned scene");
        sceneReport.umbraAfterActivation = StaticOcclusionCulling.umbraDataSize;

        // The editor's class 29 view exposes the data reference. The release
        // renderer table is checked separately in the serialized scene.
        var getter = typeof(StaticOcclusionCulling).GetProperty("occlusionCullingSettings",
            BindingFlags.NonPublic | BindingFlags.Static);
        var settings = getter?.GetValue(null) as UnityEngine.Object;
        if (!settings) throw new Exception("Active scene has no native occlusion settings");
        using (var serialized = new SerializedObject(settings))
            sceneReport.occlusionDataResolved =
                serialized.FindProperty("m_OcclusionCullingData")?.objectReferenceValue != null;
    }

    static void FinishSceneCheck(Exception error)
    {
        EditorApplication.update -= TickSceneCheck;
        try
        {
            for (var i = sceneBundles.Count - 1; i >= 0; i--) sceneBundles[i].Unload(true);
            sceneReport.unloaded &= sceneBundles.TrueForAll(bundle => !bundle);
        }
        catch (Exception unloadError) { if (error == null) error = unloadError; }
        sceneReport.failure = error?.ToString();
        File.WriteAllText(Environment.GetEnvironmentVariable("ROR2_PHONE_ORACLE_REPORT"),
            JsonUtility.ToJson(sceneReport, true));
        EditorApplication.Exit(error == null ? 0 : 1);
    }
}
