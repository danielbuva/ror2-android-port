using System;
using System.Collections;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Rendering;

// Isolated authored probe for explicit native content inputs.
public sealed class ContentFixture : MonoBehaviour
{
    public string shaderAddress;
    public bool computeHistogram;

    [Serializable] sealed class HistogramReport
    {
        public string graphics;
        public string shader;
        public uint[] clearThreads;
        public uint[] gatherThreads;
        public int nonZeroAfterClear;
        public int nonZeroAfterGather;
        public uint lastBin;
        public bool passed;
        public string failure;
    }

    [Serializable] sealed class ShaderDrawReport
    {
        public string graphics;
        public string shader;
        public Color32 low;
        public Color32 high;
        public Color32[] outlineSamples;
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
            yield return CheckShader();
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

    IEnumerator CheckShader()
    {
        using (var request = UnityWebRequestAssetBundle.GetAssetBundle(Application.streamingAssetsPath + "/phone-shader.bundle"))
        {
            yield return request.SendWebRequest();
            yield return new WaitForEndOfFrame();
            var bundle = request.result == UnityWebRequest.Result.Success ? DownloadHandlerAssetBundle.GetContent(request) : null;
            try { CheckShaderBundle(bundle, request.error); }
            finally { if (bundle != null) bundle.Unload(true); }
        }
    }

    void CheckShaderBundle(AssetBundle bundle, string loadError)
    {
        string graphics = SystemInfo.graphicsDeviceType.ToString();
        if (computeHistogram)
        {
            var histogram = new HistogramReport { graphics = graphics };
            try
            {
                if (bundle == null) throw new Exception(loadError ?? "ComputeShader bundle did not load");
                var shader = bundle.LoadAsset<ComputeShader>(shaderAddress);
                if (shader == null || !SystemInfo.supportsComputeShaders) throw new Exception("ComputeShader is unavailable or unsupported");
                histogram.shader = shader.name;
                DispatchHistogram(shader, histogram);
            }
            catch (Exception error) { histogram.failure = error.Message; }
            Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(histogram));
            return;
        }

        var report = new ShaderDrawReport { graphics = graphics };
        try
        {
            if (bundle == null) throw new Exception(loadError ?? "Shader bundle did not load");
            var shader = bundle.LoadAsset<Shader>(shaderAddress);
            if (shader == null || !shader.isSupported) throw new Exception("Shader is unavailable or unsupported");
            report.shader = shader.name;
            if (shader.name == "Unlit/OutlineHighlightNew") DrawOutline(shader, report);
            else DrawAnimateAlpha(shader, report);
        }
        catch (Exception error) { report.failure = error.Message; }
        Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(report));
    }

    static uint[] KernelThreads(ComputeShader shader, int kernel)
    {
        shader.GetKernelThreadGroupSizes(kernel, out uint x, out uint y, out uint z);
        return new[] { x, y, z };
    }

    static int CountNonZero(uint[] bins)
    {
        int count = 0;
        foreach (uint bin in bins) if (bin != 0) ++count;
        return count;
    }

    static void DispatchHistogram(ComputeShader shader, HistogramReport report)
    {
        const int width = 16;
        const int binCount = 256;
        int clear = shader.FindKernel("KHistogramClear");
        int gather = shader.FindKernel("KHistogramGather");
        report.clearThreads = KernelThreads(shader, clear);
        report.gatherThreads = KernelThreads(shader, gather);
        if (report.clearThreads[0] != 16 || report.clearThreads[1] != 1 || report.clearThreads[2] != 1 ||
            report.gatherThreads[0] != width || report.gatherThreads[1] != width || report.gatherThreads[2] != 1)
            throw new Exception("Unexpected histogram kernel thread group sizes");

        var source = new Texture2D(width, width, TextureFormat.RGBA32, false, true);
        try
        {
            var red = new Color32[width * width];
            var bins = new uint[binCount];
            for (int i = 0; i < red.Length; ++i) red[i] = new Color32(255, 0, 0, 255);
            for (int i = 0; i < bins.Length; ++i) bins[i] = 1;
            source.SetPixels32(red);
            source.Apply();
            using (var histogram = new ComputeBuffer(binCount, sizeof(uint)))
            {
                histogram.SetData(bins);
                shader.SetBuffer(clear, "_HistogramBuffer", histogram);
                shader.Dispatch(clear, binCount / 16, 1, 1);
                histogram.GetData(bins);
                report.nonZeroAfterClear = CountNonZero(bins);

                shader.SetBuffer(gather, "_HistogramBuffer", histogram);
                shader.SetTexture(gather, "_Source", source);
                shader.SetVector("_Params", new Vector4(width, width, 0, 0));
                shader.Dispatch(gather, 1, 1, 1);
                histogram.GetData(bins);
                report.nonZeroAfterGather = CountNonZero(bins);
                report.lastBin = bins[binCount - 1];
            }
            report.passed = report.graphics == "Vulkan" && report.nonZeroAfterClear == 0 &&
                report.nonZeroAfterGather == 1 && report.lastBin == width * width;
        }
        finally { Destroy(source); }
    }

    static void DrawOutline(Shader shader, ShaderDrawReport report)
    {
        var color = Shader.PropertyToID("_OutlineColor");
        var sobel = Shader.PropertyToID("_SobelTex");
        var previousSobel = Shader.GetGlobalTexture(sobel);
        var plain = new Material(shader);
        var instanced = new Material(shader) { enableInstancing = true };
        var mesh = new Mesh();
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(32, 32, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        try
        {
            using var commands = new CommandBuffer();
            mesh.vertices = new[] {
                new Vector3(-0.15f, -0.2f, 0.5f), new Vector3(-0.15f, 0.2f, 0.5f),
                new Vector3(0.15f, 0.2f, 0.5f), new Vector3(0.15f, -0.2f, 0.5f)
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2 };
            plain.SetColor(color, Color.white);
            var properties = new MaterialPropertyBlock();
            properties.SetVectorArray(color, new Vector4[] { Color.red, Color.green });
            var transforms = new[] {
                Matrix4x4.Translate(new Vector3(-0.6f, 0, 0)), Matrix4x4.Translate(new Vector3(0.6f, 0, 0))
            };
            commands.SetRenderTarget(target);
            commands.ClearRenderTarget(true, true, Color.blue);
            commands.SetViewProjectionMatrices(Matrix4x4.identity, Matrix4x4.identity);
            commands.SetGlobalTexture(sobel, Texture2D.whiteTexture);
            commands.DrawMesh(mesh, Matrix4x4.identity, plain, 0, 0);
            commands.DrawMeshInstanced(mesh, 0, instanced, 0, transforms, transforms.Length, properties);
            Graphics.ExecuteCommandBuffer(commands);

            RenderTexture.active = target;
            pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
            report.outlineSamples = new Color32[] {
                pixels.GetPixel(16, 0), pixels.GetPixel(6, 0), pixels.GetPixel(25, 0), pixels.GetPixel(11, 0)
            };
            var expected = new Color32[] { Color.white, Color.red, Color.green, Color.blue };
            for (int i = 0; i < expected.Length; ++i)
            {
                var sample = report.outlineSamples[i];
                var match = expected[i];
                if (Mathf.Abs(sample.r - match.r) > 5 || Mathf.Abs(sample.g - match.g) > 5 ||
                    Mathf.Abs(sample.b - match.b) > 5)
                    throw new Exception("Outline sample " + i + " did not match the expected RGB");
            }
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            Shader.SetGlobalTexture(sobel, previousSobel);
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(plain);
            Destroy(instanced);
            Destroy(mesh);
            Destroy(pixels);
        }
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
