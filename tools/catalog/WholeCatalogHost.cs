using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.AddressableAssets;
using UnityEngine.AddressableAssets.Initialization;
using UnityEngine.AddressableAssets.ResourceLocators;
using UnityEngine.AddressableAssets.ResourceProviders;
using UnityEngine.ResourceManagement.AsyncOperations;
using UnityEngine.ResourceManagement.ResourceProviders;

// Only the editor substitutes AssetDatabase for the Android bundle provider.
public static class WholeCatalogHost
{
    sealed class ImportedAssetProvider : ResourceProviderBase
    {
        public override void Provide(ProvideHandle handle)
        {
            try
            {
                var asset = AssetDatabase.LoadAssetAtPath(handle.Location.InternalId, handle.Type);
                if (!asset)
                    throw new Exception("Typed import missing: " + handle.Location.InternalId + " [" + handle.Type + "]");
                handle.Complete<UnityEngine.Object>(asset, true, null);
            }
            catch (Exception e)
            {
                WholeCatalogLoader.failures.Add(e.ToString());
                handle.Complete<UnityEngine.Object>(null, false, e);
            }
        }
    }
    static readonly Stack<IEnumerator> stack = new Stack<IEnumerator>();
    static string output;
    static AsyncOperationHandle? waiting;
    static double deadline;
    static void Log(string message, string trace, LogType kind)
    {
        if (kind == LogType.Error || kind == LogType.Exception || kind == LogType.Assert)
            WholeCatalogLoader.failures.Add(message + "\n" + trace);
    }
    static IEnumerator LoadAndInitialize(JObject manifest)
    {
        yield return WholeCatalogLoader.Load(manifest, typeof(ImportedAssetProvider).FullName);
        if (WholeCatalogLoader.failures.Count != 0)
            throw new Exception("Original provider loading reported errors");
        yield return WholeCatalogLoader.InitializeCatalogs();
    }
    public static void Begin(string manifestPath, string outputPath)
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode ||
            UnityEditor.BuildPipeline.isBuildingPlayer || stack.Count != 0)
            throw new Exception("Editor busy");
        output = outputPath;
        deadline = EditorApplication.timeSinceStartup + 240;
        waiting = null;
        var directory = Path.GetDirectoryName(output);
        var catalog = Path.Combine(directory, "host-empty-catalog.json");
        var settings = Path.Combine(directory, "host-settings.json");
        File.WriteAllText(
            catalog,
            "{\"m_LocatorId\":\"whole-host-init\",\"m_ProviderIds\":[],\"m_InternalIds\":[],\"m_KeyDataString\":\"AAAAAA==\",\"m_BucketDataString\":\"AAAAAA==\",\"m_EntryDataString\":\"AAAAAA==\",\"m_ExtraDataString\":\"\",\"m_resourceTypes\":[]}");
        var settingsData = new ResourceManagerRuntimeData { BuildTarget = "Android", DisableCatalogUpdateOnStartup = true,
                                                            LogResourceManagerExceptions = true };
        settingsData.CatalogLocations.Add(new ResourceLocationData(new[] { ResourceManagerRuntimeData.kCatalogAddress }, catalog,
                                                                   typeof(ContentCatalogProvider), typeof(ContentCatalogData)));
        File.WriteAllText(settings, JsonUtility.ToJson(settingsData));
        string original = Addressables.RuntimePath + "/settings.json";
        Addressables.InternalIdTransformFunc = location => location.InternalId == original ? settings : location.InternalId;
        Addressables.ResourceManager.ResourceProviders.Add(new ImportedAssetProvider());
        stack.Push(LoadAndInitialize(JObject.Parse(File.ReadAllText(manifestPath))));
        Application.logMessageReceived += Log;
        EditorApplication.update += Tick;
    }
    static void Save(bool success, string error = null)
    {
        var text = Newtonsoft.Json.JsonConvert.SerializeObject(
            new { success, finished = stack.Count == 0 || error != null, phase = WholeCatalogLoader.phase,
                  progress = WholeCatalogLoader.progress, error, failures = WholeCatalogLoader.failures,
                  counts = WholeCatalogLoader.Counts() },
            Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(output + ".pending", text);
        if (File.Exists(output))
            File.Replace(output + ".pending", output, null);
        else
            File.Move(output + ".pending", output);
    }
    static void Tick()
    {
        try
        {
            // The preserved package's editor scheduler is internal, unlike newer APIs.
            typeof(UnityEngine.ResourceManagement.ResourceManager)
                .GetMethod("Update", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                .Invoke(Addressables.ResourceManager, new object[] { 0.016f });
            if (EditorApplication.timeSinceStartup > deadline)
                throw new TimeoutException("Original provider phase stalled");
            if (waiting.HasValue)
            {
                if (!waiting.Value.IsDone)
                    return;
                waiting = null;
            }
            for (int i = 0; i < 100 && stack.Count != 0; i++)
            {
                var top = stack.Peek();
                if (!top.MoveNext())
                {
                    stack.Pop();
                    continue;
                }
                var child = top.Current as IEnumerator;
                if (child != null)
                {
                    stack.Push(child);
                    continue;
                }
                if (top.Current is AsyncOperationHandle)
                {
                    waiting = (AsyncOperationHandle)top.Current;
                    break;
                }
                break;
            }
            if (stack.Count == 0)
            {
                Save(WholeCatalogLoader.failures.Count == 0);
                EditorApplication.update -= Tick;
                Application.logMessageReceived -= Log;
            }
            else
                Save(false);
        }
        catch (Exception e)
        {
            Save(false, e.ToString());
            stack.Clear();
            EditorApplication.update -= Tick;
            Application.logMessageReceived -= Log;
            Debug.LogException(e);
        }
    }
}
