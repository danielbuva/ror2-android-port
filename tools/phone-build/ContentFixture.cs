using System;
using System.Collections;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;

// Isolated authored probe for explicit native content inputs.
public sealed class ContentFixture : MonoBehaviour
{
    public string shaderAddress;

    [Serializable] sealed class ShaderDrawReport
    {
        public string graphics;
        public string shader;
        public Color32 low;
        public Color32 high;
        public bool passed;
        public string failure;
    }

    [Serializable] public sealed class Report
    {
        public string unity;
        public string graphics;
        public bool bundleLoaded;
        public bool textMatched;
        public bool unloaded;
        public string source;
        public string bundleSha256;
        public int successfulCycles;
        public string failure;
    }

    [Serializable] sealed class Selection { public string sha256; }
    [Serializable] sealed class Paths
    {
        public string persistentDataPath;
        public string filesDir;
        public string externalFilesDir;
    }

    static string Sha256(byte[] data)
    {
        using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
    }

    public static Report Check(string path)
    {
        var report = new Report { unity = Application.unityVersion, graphics = SystemInfo.graphicsDeviceType.ToString() };
        AssetBundle bundle = null;
        TextAsset text = null;
        try
        {
            bundle = AssetBundle.LoadFromFile(path);
            report.bundleLoaded = bundle != null;
            if (!report.bundleLoaded) throw new Exception("AssetBundle.LoadFromFile returned null");
            text = bundle.LoadAsset<TextAsset>("assets/phone-fixture.txt");
            report.textMatched = text != null && text.text == "phone-owned-content-fixture-v1\n";
            if (!report.textMatched) throw new Exception("TextAsset deserialization/payload mismatch");
        }
        catch (Exception error) { report.failure = error.GetType().Name + ": " + error.Message; }
        finally
        {
            if (bundle != null) { bundle.Unload(true); report.unloaded = text == null; }
        }
        return report;
    }

    IEnumerator Start()
    {
        if (!String.IsNullOrEmpty(shaderAddress))
        {
            yield return CheckShaderDraw();
            yield break;
        }
        using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
        using (var activity = player.GetStatic<AndroidJavaObject>("currentActivity"))
        using (var files = activity.Call<AndroidJavaObject>("getFilesDir"))
        using (var external = activity.Call<AndroidJavaObject>("getExternalFilesDir", new object[] { null }))
        {
            var paths = new Paths {
                persistentDataPath = Application.persistentDataPath,
                filesDir = files.Call<string>("getCanonicalPath"),
                externalFilesDir = external.Call<string>("getCanonicalPath")
            };
            File.WriteAllText(Path.Combine(paths.filesDir, "phone-content-paths.json"), JsonUtility.ToJson(paths));
        }
        var path = Path.Combine(Application.persistentDataPath, "phone-fixture.bundle");
        var report = new Report { unity = Application.unityVersion };
        var selector = Path.Combine(Application.persistentDataPath, "phone-fixture-selection.json");
        string source = "embedded";
        string digest = "";
        bool ready = false;
        if (File.Exists(selector))
        {
            try
            {
                var selection = JsonUtility.FromJson<Selection>(File.ReadAllText(selector));
                path = Path.Combine(Application.persistentDataPath, "phone-candidate.bundle");
                digest = Sha256(File.ReadAllBytes(path));
                if (selection == null || selection.sha256 == null || selection.sha256.Length != 64 || digest != selection.sha256)
                    throw new Exception("Candidate hash mismatch");
                source = "external-candidate";
                ready = true;
            }
            catch (Exception error) { report.failure = "candidate: " + error.Message; }
        }
        else using (var request = UnityWebRequest.Get(Application.streamingAssetsPath + "/phone-fixture.bundle"))
        {
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success) report.failure = "fixture copy: " + request.error;
            else { File.WriteAllBytes(path, request.downloadHandler.data); digest = Sha256(request.downloadHandler.data); ready = true; }
        }
        if (ready)
        {
            int cycles = 0;
            for (int i = 0; i < 2; ++i)
            {
                report = Check(path);
                if (!report.bundleLoaded || !report.textMatched || !report.unloaded || !String.IsNullOrEmpty(report.failure)) break;
                ++cycles;
                yield return null;
            }
            report.successfulCycles = cycles;
        }
        report.source = source;
        report.bundleSha256 = digest;
        File.WriteAllText(Path.Combine(Application.persistentDataPath, "phone-content-report.json"), JsonUtility.ToJson(report, true));
        Debug.Log("PHONE_CONTENT_FIXTURE " + JsonUtility.ToJson(report));
    }

    IEnumerator CheckShaderDraw()
    {
        var report = new ShaderDrawReport { graphics = SystemInfo.graphicsDeviceType.ToString() };
        using (var request = UnityWebRequestAssetBundle.GetAssetBundle(Application.streamingAssetsPath + "/phone-shader.bundle"))
        {
            yield return request.SendWebRequest();
            yield return new WaitForEndOfFrame();
            AssetBundle bundle = null;
            try
            {
                if (request.result != UnityWebRequest.Result.Success) throw new Exception(request.error);
                bundle = DownloadHandlerAssetBundle.GetContent(request);
                var shader = bundle.LoadAsset<Shader>(shaderAddress);
                if (shader == null || !shader.isSupported) throw new Exception("Shader is unavailable or unsupported");
                report.shader = shader.name;
                DrawAnimateAlpha(shader, report);
            }
            catch (Exception error) { report.failure = error.Message; }
            finally { if (bundle != null) bundle.Unload(true); }
        }
        Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(report));
    }

    static void DrawAnimateAlpha(Shader shader, ShaderDrawReport report)
    {
        var material = new Material(shader);
        var ramp = new Texture2D(2, 1, TextureFormat.RGBA32, false, true) {
            filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp
        };
        var pixels = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(16, 16, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        GL.PushMatrix();
        try
        {
            ramp.SetPixels(new[] { Color.red, Color.green });
            ramp.Apply();
            material.SetColor("_Color", Color.white);
            material.SetFloat("_AlphaBoost", 1);
            material.SetFloat("_TrueAlpha", 1);
            material.SetFloat("_PatternPixelSize", 1);
            material.SetFloat("_PatternStrength", 0);
            // Let the main texture drive the ramp coordinate at full alpha.
            material.SetFloat("_ExternalAlpha", 1);
            material.SetFloat("_LightenFactor", 0);
            material.SetVector("_TextureSampleAdd", Vector4.zero);
            material.SetTexture("_OverlayTex", Texture2D.whiteTexture);
            material.SetTexture("_RemapRamp", ramp);

            RenderTexture.active = target;
            GL.LoadOrtho();
            report.low = DrawRampSample(material, pixels, Texture2D.blackTexture);
            report.high = DrawRampSample(material, pixels, Texture2D.whiteTexture);
            report.passed = report.graphics == "Vulkan" &&
                report.low.r >= 250 && report.low.g <= 5 && report.low.b <= 5 &&
                report.high.r <= 5 && report.high.g >= 250 && report.high.b <= 5;
        }
        finally
        {
            GL.PopMatrix();
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(material);
            Destroy(ramp);
            Destroy(pixels);
        }
    }

    static Color32 DrawRampSample(Material material, Texture2D pixels, Texture texture)
    {
        GL.Clear(true, true, Color.blue);
        material.SetTexture("_MainTex", texture);
        if (!material.SetPass(0)) throw new Exception("Shader pass 0 could not bind");
        GL.Begin(GL.QUADS);
        GL.Color(Color.white);
        GL.TexCoord2(0, 0); GL.Vertex3(0, 0, 0.5f);
        GL.TexCoord2(0, 1); GL.Vertex3(0, 1, 0.5f);
        GL.TexCoord2(1, 1); GL.Vertex3(1, 1, 0.5f);
        GL.TexCoord2(1, 0); GL.Vertex3(1, 0, 0.5f);
        GL.End();
        pixels.ReadPixels(new Rect(8, 8, 1, 1), 0, 0, false);
        return pixels.GetPixel(0, 0);
    }
}
