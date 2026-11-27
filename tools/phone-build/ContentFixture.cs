using System;
using System.Collections;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;

// Isolated authored probe for explicit native content inputs.
public sealed class ContentFixture : MonoBehaviour
{
    public string shaderAddress;
    public string[] computeAddresses;

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
        public bool passed;
        public string failure;
    }

    [Serializable] sealed class ScopeReport
    {
        public string shader;
        public int nonZeroAfterClear;
        public int nonZeroAfterGather;
        public int mismatchedAfterGather;
        public string failure;

        public bool Passed => failure == null && nonZeroAfterClear == 0 && mismatchedAfterGather == 0;
    }

    [Serializable] sealed class ScopesReport
    {
        public string graphics;
        public ScopeReport waveform;
        public ScopeReport vectorscope;
        public bool passed;
        public string failure;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct WaveformBin
    {
        public uint red, green, blue, alpha;
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
        if (!String.IsNullOrEmpty(shaderAddress) || computeAddresses?.Length > 0)
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
        if (computeAddresses?.Length == 2)
        {
            var scopes = new ScopesReport { graphics = graphics };
            try
            {
                foreach (string address in computeAddresses)
                {
                    var shader = LoadComputeShader(bundle, address, loadError);
                    switch (shader.name)
                    {
                        case "Waveform" when scopes.waveform == null:
                            scopes.waveform = CheckScope(shader, true);
                            break;
                        case "Vectorscope" when scopes.vectorscope == null:
                            scopes.vectorscope = CheckScope(shader, false);
                            break;
                        default:
                            throw new Exception("Unexpected scope shader: " + shader.name);
                    }
                }
                scopes.passed = graphics == "Vulkan" && scopes.waveform.Passed && scopes.vectorscope.Passed;
            }
            catch (Exception error) { scopes.failure = error.Message; }
            Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(scopes));
            return;
        }
        if (computeAddresses?.Length == 1)
        {
            var histogram = new HistogramReport { graphics = graphics };
            try
            {
                var shader = LoadComputeShader(bundle, computeAddresses[0], loadError);
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
            DrawAnimateAlpha(shader, report);
        }
        catch (Exception error) { report.failure = error.Message; }
        Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(report));
    }

    static ComputeShader LoadComputeShader(AssetBundle bundle, string address, string loadError)
    {
        if (bundle == null) throw new Exception(loadError ?? "ComputeShader bundle did not load");
        var shader = bundle.LoadAsset<ComputeShader>(address);
        if (shader == null || !SystemInfo.supportsComputeShaders)
            throw new Exception("ComputeShader is unavailable or unsupported: " + address);
        return shader;
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

    const int ScopeWidth = 16;
    const int ScopeBinCount = ScopeWidth * ScopeWidth;

    static ScopeReport CheckScope(ComputeShader shader, bool waveform)
    {
        var report = new ScopeReport { shader = shader.name };
        var source = new Texture2D(ScopeWidth, ScopeWidth, TextureFormat.RGBA32, false, true);
        try
        {
            var red = new Color32[ScopeBinCount];
            for (int i = 0; i < red.Length; ++i) red[i] = new Color32(128, 0, 0, 255);
            source.SetPixels32(red);
            source.Apply();
            if (waveform) DispatchWaveform(shader, source, report);
            else DispatchVectorscope(shader, source, report);
        }
        catch (Exception error) { report.failure = error.Message; }
        finally { Destroy(source); }
        return report;
    }

    static void DispatchScope(ComputeShader shader, Texture source, ComputeBuffer buffer, bool waveform, bool clear)
    {
        int kernel = shader.FindKernel("K" + shader.name + (clear ? "Clear" : "Gather"));
        shader.SetVector("_Params", new Vector4(ScopeWidth, ScopeWidth, waveform ? 0 : ScopeWidth, 0));
        shader.SetBuffer(kernel, "_" + shader.name + "Buffer", buffer);
        if (!clear) shader.SetTexture(kernel, "_Source", source);
        shader.Dispatch(kernel, waveform && !clear ? ScopeWidth : 1, 1, 1);
    }

    static void DispatchVectorscope(ComputeShader shader, Texture source, ScopeReport report)
    {
        var bins = new uint[ScopeBinCount];
        for (int i = 0; i < bins.Length; ++i) bins[i] = 1;
        using (var buffer = new ComputeBuffer(bins.Length, sizeof(uint)))
        {
            buffer.SetData(bins);
            DispatchScope(shader, source, buffer, false, true);
            buffer.GetData(bins);
            report.nonZeroAfterClear = CountNonZero(bins);
            DispatchScope(shader, source, buffer, false, false);
            buffer.GetData(bins);
        }
        report.nonZeroAfterGather = CountNonZero(bins);
        // Mid-red maps to U=6, V=12 on this 16 × 16 grid.
        for (int i = 0; i < bins.Length; ++i)
            if (bins[i] != (i == 12 * ScopeWidth + 6 ? ScopeBinCount : 0))
                ++report.mismatchedAfterGather;
    }

    static void DispatchWaveform(ComputeShader shader, Texture source, ScopeReport report)
    {
        var bins = new WaveformBin[ScopeBinCount];
        for (int i = 0; i < bins.Length; ++i)
            bins[i] = new WaveformBin { red = 1, green = 1, blue = 1, alpha = 1 };
        using (var buffer = new ComputeBuffer(bins.Length, 4 * sizeof(uint)))
        {
            buffer.SetData(bins);
            DispatchScope(shader, source, buffer, true, true);
            buffer.GetData(bins);
            foreach (var bin in bins)
                if ((bin.red | bin.green | bin.blue | bin.alpha) != 0) ++report.nonZeroAfterClear;
            DispatchScope(shader, source, buffer, true, false);
            buffer.GetData(bins);
        }
        for (int i = 0; i < bins.Length; ++i)
        {
            var bin = bins[i];
            if ((bin.red | bin.green | bin.blue | bin.alpha) != 0) ++report.nonZeroAfterGather;
            // Each column has 16 red samples at row 8. The kernel skips absolute bin 0.
            int row = i % ScopeWidth;
            int red = row == 8 ? ScopeWidth : 0;
            int other = row == 0 && i > 0 ? ScopeWidth : 0;
            if (bin.red != red || bin.green != other || bin.blue != other || bin.alpha != 0)
                ++report.mismatchedAfterGather;
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
