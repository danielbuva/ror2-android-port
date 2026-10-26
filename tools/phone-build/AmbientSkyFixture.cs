using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Apple;
using UnityEngine.Rendering;

// Authored observation fixture only. An external read-only controller must
// qualify actual native bake observations; this does not produce player data.
public static class AmbientSkyFixture
{
    [Serializable] sealed class Report
    {
        public string unity;
        public string gpu;
        public bool captureCompleted;
        public string failure;
    }

    static string output;
    static bool capturing;
    static bool staged;
    static double started;
    static Report report;

    public static void Begin()
    {
        output = Environment.GetEnvironmentVariable("ROR2_AMBIENT_CAPTURE");
        report = new Report { unity = Application.unityVersion, gpu = SystemInfo.graphicsDeviceType.ToString() };
        try
        {
            Directory.CreateDirectory(output);
            if (Application.unityVersion != "2021.3.45f2") throw new Exception("Exact editor required");
            if (SystemInfo.graphicsDeviceType != GraphicsDeviceType.Metal) throw new Exception("Metal required");
            if (!FrameCapture.IsDestinationSupported(FrameCaptureDestination.GPUTraceDocument))
                throw new Exception("GPU trace unavailable");
            File.WriteAllText(Path.Combine(output, "fixture-started.json"), JsonUtility.ToJson(report, true));
            started = EditorApplication.timeSinceStartup;
            EditorApplication.update += Tick;
        }
        catch (Exception error) { Finish(error); }
    }

    static void StageScene()
    {
        PlayerSettings.colorSpace = ColorSpace.Linear;
        FrameCapture.BeginCaptureToFile(Path.Combine(output, "ambient.gputrace"));
        capturing = true;
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var camera = new GameObject("Lab Camera").AddComponent<Camera>();
        camera.tag = "MainCamera";
        camera.backgroundColor = new Color(.04f, .06f, .09f);
        camera.clearFlags = CameraClearFlags.SolidColor;
        var light = new GameObject("Lab Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.transform.rotation = Quaternion.Euler(35, 40, 0);
        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = "G1 reference cube";
        cube.transform.position = new Vector3(3, 0, 0);
        var material = new Material(Shader.Find("Skybox/Procedural"));
        material.name = "Default-Skybox";
        material.shaderKeywords = new[] { "_SUNDISK_SIMPLE" };
        material.SetFloat("_SunDisk", 1);
        material.SetFloat("_SunSize", .04f);
        material.SetFloat("_SunSizeConvergence", 5);
        material.SetFloat("_AtmosphereThickness", 1);
        material.SetFloat("_Exposure", 1.3f);
        material.SetColor("_SkyTint", new Color(.5f, .5f, .5f, 1));
        material.SetColor("_GroundColor", new Color(.369f, .349f, .341f, 1));
        AssetDatabase.CreateAsset(material, "Assets/OracleSky.mat");
        RenderSettings.skybox = material;
        File.WriteAllText(Path.Combine(output, "scene-configured"), "authored Lab scene and explicit SIMPLE sky\n");
        EditorSceneManager.SaveScene(scene, "Assets/Lab.unity");
        staged = true;
    }

    static void Tick()
    {
        try
        {
            if (!staged && File.Exists(Path.Combine(output, "capture-armed"))) StageScene();
            EditorApplication.QueuePlayerLoopUpdate();
            if (staged && File.Exists(Path.Combine(output, "capture-complete.json")))
            {
                report.captureCompleted = true;
                Finish(null);
            }
            else if (EditorApplication.timeSinceStartup - started > 90)
                Finish(new Exception("No qualified ambient bake capture within 90 seconds"));
        }
        catch (Exception error) { Finish(error); }
    }

    static void Finish(Exception error)
    {
        EditorApplication.update -= Tick;
        try { if (capturing) FrameCapture.EndCapture(); }
        catch (Exception captureError) { if (error == null) error = captureError; }
        report.failure = error == null ? null : error.ToString();
        File.WriteAllText(Environment.GetEnvironmentVariable("ROR2_PHONE_ORACLE_REPORT"), JsonUtility.ToJson(report, true));
        EditorApplication.Exit(error == null ? 0 : 1);
    }
}
