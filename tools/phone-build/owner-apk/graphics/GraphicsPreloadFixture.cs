// Qualification only: ordering is not custom-driver or completed-frame acceptance.
using System;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering;

public sealed class GraphicsPreloadFixture : MonoBehaviour
{
    [DllImport("GraphicsDriverPreload", EntryPoint = "GraphicsDriverPreloadStatus")]
    static extern uint ReadStatus();

    [Serializable] sealed class Result
    {
        public bool success, vulkan, custom_driver_loaded, completed_frame_verified;
        public uint ordering_flags;
        public string classification;
    }

    void Start()
    {
        Application.targetFrameRate = 15;
        var result = new Result { vulkan = SystemInfo.graphicsDeviceType == GraphicsDeviceType.Vulkan };
        try
        {
            result.ordering_flags = ReadStatus();
            result.success = result.vulkan && result.ordering_flags == 0x7f;
            result.classification = result.success ? "preload-order-observed" : "preload-order-not-proven";
        }
        catch (Exception) { result.classification = "preload-status-unavailable"; }
        string json = JsonUtility.ToJson(result);
        File.WriteAllText(Path.Combine(Application.persistentDataPath, "graphics-preload-result.json"), json);
        Debug.Log("GRAPHICS_PRELOAD_RESULT " + json);
    }
}
