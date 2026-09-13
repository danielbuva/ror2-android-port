using UnityEditor;
using UnityEngine;
using MCPForUnity.Editor.Services;
public static class BootstrapMcp
{
    public static async void Connect()
    {
        EditorPrefs.SetBool("MCPForUnity.UseHttpTransport", true);
        EditorPrefs.SetString("MCPForUnity.HttpUrl", "http://127.0.0.1:8080");
        bool started = await MCPServiceLocator.Bridge.StartAsync();
        Debug.Log("BOOTSTRAP_MCP_CONNECTED=" + started);
    }
}
