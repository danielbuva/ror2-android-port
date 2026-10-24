using UnityEditor;
using UnityEngine;
using MCPForUnity.Editor.Services;
using System;
using System.IO;
using System.Threading.Tasks;
public static class BootstrapMcp
{
    static bool connecting;
    [UnityEditor.Callbacks.DidReloadScripts(-10000)]
    static void ResumeLane()
    {
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ROR2LAB_MCP_HTTP_URL")))
        {
            SessionState.EraseBool("MCPForUnity.ResumeHttpAfterReload");
            EditorApplication.delayCall += Connect;
        }
    }
    public static async void Connect()
    {
        if (connecting) return;
        connecting = true;
        FileStream lease = null;
        string laneUrl = Environment.GetEnvironmentVariable("ROR2LAB_MCP_HTTP_URL");
        string lockPath = Environment.GetEnvironmentVariable("ROR2LAB_MCP_PREF_LOCK");
        try
        {
            // The pinned MCP captures its endpoint at StartAsync but stores
            // configuration in machine-wide EditorPrefs. Serialize only this
            // short setup, then restore the canonical preference immediately.
            if (!string.IsNullOrEmpty(lockPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(lockPath));
                for (int i = 0; lease == null; i++)
                {
                    try { lease = new FileStream(lockPath, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None); }
                    catch (IOException) { if (i >= 300) throw; await Task.Delay(100); }
                }
            }
            bool hadUrl = EditorPrefs.HasKey("MCPForUnity.HttpUrl");
            string previousUrl = EditorPrefs.GetString("MCPForUnity.HttpUrl", "http://127.0.0.1:8080");
            bool previousHttp = EditorPrefs.GetBool("MCPForUnity.UseHttpTransport", true);
            try
            {
                if (!string.IsNullOrEmpty(laneUrl))
                {
                    SessionState.EraseBool("MCPForUnity.ResumeHttpAfterReload");
                    await MCPServiceLocator.Bridge.StopAsync();
                }
                EditorPrefs.SetBool("MCPForUnity.UseHttpTransport", true);
                EditorPrefs.SetString("MCPForUnity.HttpUrl", string.IsNullOrEmpty(laneUrl) ? "http://127.0.0.1:8080" : laneUrl);
                bool started = await MCPServiceLocator.Bridge.StartAsync();
                Debug.Log("BOOTSTRAP_MCP_CONNECTED=" + started);
            }
            finally
            {
                if (!string.IsNullOrEmpty(laneUrl))
                {
                    if (hadUrl) EditorPrefs.SetString("MCPForUnity.HttpUrl", previousUrl);
                    else EditorPrefs.DeleteKey("MCPForUnity.HttpUrl");
                    EditorPrefs.SetBool("MCPForUnity.UseHttpTransport", previousHttp);
                }
            }
        }
        finally { if (lease != null) lease.Dispose(); connecting = false; }
    }
}
