using System;
using System.Collections;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Rendering;

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
        public uint clampedSampleCount;
        public uint blendedSampleCount;
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

    [Serializable] sealed class AutoExposureReport
    {
        public string graphics;
        public float fixedExposure;
        public float risingExposure;
        public float fallingExposure;
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

    [Serializable] sealed class VolumeKernelReport
    {
        public string kernel;
        public int components;
        public int mismatches;
        public string failure;

        public bool Passed => failure == null && mismatches == 0;
    }

    [Serializable] sealed class VolumeReport
    {
        public string graphics;
        public VolumeKernelReport[] original;
        public VolumeKernelReport[] sdk;
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
                var first = LoadComputeShader(bundle, computeAddresses[0], loadError);
                var second = LoadComputeShader(bundle, computeAddresses[1], loadError);
                if (first.name == "Texture3DLerp" && second.name == first.name)
                {
                    CheckVolumePair(first, second, graphics);
                    return;
                }
                foreach (var shader in new[] { first, second })
                {
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
                if (shader.name == "AutoExposure")
                {
                    CheckAutoExposure(shader, graphics);
                    return;
                }
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

    static void CheckAutoExposure(ComputeShader shader, string graphics)
    {
        var report = new AutoExposureReport { graphics = graphics };
        Texture2D previous = null;
        RenderTexture destination = null;
        try
        {
            previous = new Texture2D(1, 1, TextureFormat.RFloat, false, true);
            destination = new RenderTexture(1, 1, 0, RenderTextureFormat.RFloat, RenderTextureReadWrite.Linear) {
                enableRandomWrite = true
            };
            if (!destination.Create()) throw new Exception("RFloat exposure target allocation failed");
            var bins = new uint[128];
            bins[32] = 4;
            bins[64] = 8;
            bins[96] = 4;
            using (var histogram = new ComputeBuffer(bins.Length, sizeof(uint)))
            {
                histogram.SetData(bins);
                shader.SetVector("_Params1", new Vector4(0.125f, 0.875f, 0.125f, 8f));
                shader.SetVector("_Params2", new Vector4(1f, 2f, 1.625f, 1f));
                shader.SetVector("_ScaleOffsetRes", new Vector4(0.25f, 0.5f, 0f, 0f));
                int fixedKernel = shader.FindKernel("KAutoExposureAvgLuminance_fixed");
                int progressive = shader.FindKernel("KAutoExposureAvgLuminance_progressive");
                foreach (int kernel in new[] { fixedKernel, progressive })
                {
                    var threads = KernelThreads(shader, kernel);
                    if (threads[0] != 16 || threads[1] != 8 || threads[2] != 1)
                        throw new Exception("Unexpected exposure workgroup dimensions");
                    shader.SetBuffer(kernel, "_HistogramBuffer", histogram);
                    shader.SetTexture(kernel, "_Destination", destination);
                }

                report.fixedExposure = DispatchExposure(shader, fixedKernel, destination);
                previous.SetPixelData(new[] { 0.25f }, 0);
                previous.Apply();
                shader.SetTexture(progressive, "_Source", previous);
                report.risingExposure = DispatchExposure(shader, progressive, destination);
                previous.SetPixelData(new[] { 2f }, 0);
                previous.Apply();
                report.fallingExposure = DispatchExposure(shader, progressive, destination);
            }
            // The 12.5% and 87.5% cut points leave counts 2, 8 and 2.
            // The luminances 0.5, 1 and 2 give a weighted mean of 13/12.
            // Compensation 13/8 gives 1.5. The rising and falling steps cover 1/2 and 3/4 of the delta.
            const float tolerance = 0.00001f;
            report.passed = graphics == "Vulkan" &&
                Mathf.Abs(report.fixedExposure - 1.5f) <= tolerance &&
                Mathf.Abs(report.risingExposure - 0.875f) <= tolerance &&
                Mathf.Abs(report.fallingExposure - 1.625f) <= tolerance;
        }
        catch (Exception error) { report.failure = error.Message; }
        finally
        {
            if (destination != null) { destination.Release(); Destroy(destination); }
            Destroy(previous);
        }
        Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(report));
    }

    static float DispatchExposure(ComputeShader shader, int kernel, RenderTexture destination)
    {
        shader.Dispatch(kernel, 1, 1, 1);
        var readback = AsyncGPUReadback.Request(destination, 0);
        readback.WaitForCompletion();
        if (readback.hasError || readback.layerCount != 1 || readback.layerDataSize != sizeof(float))
            throw new Exception("Unexpected RFloat exposure readback shape or status");
        return readback.GetData<float>()[0];
    }

    static void DispatchHistogram(ComputeShader shader, HistogramReport report)
    {
        const int threads = 16;
        bool exposure = shader.name == "ExposureHistogram";
        int width = exposure ? 4 : threads;
        int binCount = exposure ? 128 : 256;
        int clear = shader.FindKernel(exposure ? "KEyeHistogramClear" : "KHistogramClear");
        int gather = shader.FindKernel(exposure ? "KEyeHistogram" : "KHistogramGather");
        report.clearThreads = KernelThreads(shader, clear);
        report.gatherThreads = KernelThreads(shader, gather);
        if (report.clearThreads[0] != threads || report.clearThreads[1] != 1 || report.clearThreads[2] != 1 ||
            report.gatherThreads[0] != threads || report.gatherThreads[1] != threads || report.gatherThreads[2] != 1)
            throw new Exception("Unexpected histogram kernel thread group sizes");

        var format = exposure ? TextureFormat.RGBAFloat : TextureFormat.RGBA32;
        var source = new Texture2D(width, width, format, false, true);
        try
        {
            if (exposure)
            {
                var pixels = new Color[width * width];
                for (int i = 0; i < pixels.Length; ++i)
                    pixels[i] = i % 2 == 0 ? new Color(0.25f, 0.25f, 0.25f, 1) : Color.white;
                source.filterMode = FilterMode.Point;
                source.SetPixelData(pixels, 0);
            }
            else
            {
                var red = new Color32[width * width];
                for (int i = 0; i < red.Length; ++i) red[i] = new Color32(255, 0, 0, 255);
                source.SetPixels32(red);
            }
            var bins = new uint[binCount];
            for (int i = 0; i < bins.Length; ++i) bins[i] = 1;
            source.Apply();
            using (var histogram = new ComputeBuffer(binCount, sizeof(uint)))
            {
                histogram.SetData(bins);
                shader.SetBuffer(clear, "_HistogramBuffer", histogram);
                shader.Dispatch(clear, binCount / threads, 1, 1);
                histogram.GetData(bins);
                report.nonZeroAfterClear = CountNonZero(bins);

                shader.SetBuffer(gather, "_HistogramBuffer", histogram);
                shader.SetTexture(gather, "_Source", source);
                if (exposure) shader.SetVector("_ScaleOffsetRes", new Vector4(0.2f, 0.5f, width, width));
                else shader.SetVector("_Params", new Vector4(width, width, 0, 0));
                shader.Dispatch(gather, 1, 1, 1);
                histogram.GetData(bins);
                report.nonZeroAfterGather = CountNonZero(bins);
                report.lastBin = bins[binCount - 1];
            }
            // LinearClamp reads .25 at the edge and .625 between adjacent columns.
            report.clampedSampleCount = exposure ? bins[12] : 0;
            report.blendedSampleCount = exposure ? bins[46] : 0;
            // Each axis steps by two texels. The four samples at (0,0), (0,2),
            // (2,0), (2,2) have radial weights 16, 36, 36 and 64.
            bool gatherMatches = exposure
                ? report.nonZeroAfterGather == 2 && report.clampedSampleCount == 52 && report.blendedSampleCount == 100
                : report.nonZeroAfterGather == 1 && report.lastBin == width * width;
            report.passed = report.graphics == "Vulkan" && report.nonZeroAfterClear == 0 && gatherMatches;
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

    const int VolumeSize = 4;

    static ushort[] VolumePixels(bool second)
    {
        var pixels = new ushort[4 * VolumeSize * VolumeSize * VolumeSize];
        for (int z = 0, i = 0; z < VolumeSize; ++z)
            for (int y = 0; y < VolumeSize; ++y)
                for (int x = 0; x < VolumeSize; ++x)
                {
                    var value = second ? new Vector4(1 - z / 4f, 1 - x / 4f, 1 - y / 4f, 0)
                        : new Vector4(x / 4f, y / 4f, z / 4f, 1);
                    for (int channel = 0; channel < 4; ++channel)
                        pixels[i++] = Mathf.FloatToHalf(value[channel]);
                }
        return pixels;
    }

    static void CheckVolumePair(ComputeShader first, ComputeShader second, string graphics)
    {
        var report = new VolumeReport { graphics = graphics };
        Texture3D from = null, to = null;
        try
        {
            var fromPixels = VolumePixels(false);
            var toPixels = VolumePixels(true);
            from = new Texture3D(VolumeSize, VolumeSize, VolumeSize, TextureFormat.RGBAHalf, false);
            to = new Texture3D(VolumeSize, VolumeSize, VolumeSize, TextureFormat.RGBAHalf, false);
            from.SetPixelData(fromPixels, 0);
            to.SetPixelData(toPixels, 0);
            from.Apply();
            to.Apply();
            var targetColor = new Vector4(1, 0.5f, 0, 0.5f);
            VolumeKernelReport[] Compare(ComputeShader shader) => new[] {
                DispatchVolume(shader, from, to, fromPixels, toPixels, targetColor, false),
                DispatchVolume(shader, from, to, fromPixels, toPixels, targetColor, true)
            };
            report.original = Compare(first);
            report.sdk = Compare(second);
            report.passed = graphics == "Vulkan" && Array.TrueForAll(report.original, row => row.Passed) &&
                Array.TrueForAll(report.sdk, row => row.Passed);
        }
        catch (Exception error) { report.failure = error.Message; }
        finally
        {
            if (to != null) Destroy(to);
            if (from != null) Destroy(from);
        }
        Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(report));
    }

    static VolumeKernelReport DispatchVolume(ComputeShader shader, Texture3D from, Texture3D to,
        ushort[] fromPixels, ushort[] toPixels, Vector4 targetColor, bool toColor)
    {
        var report = new VolumeKernelReport { kernel = toColor ? "KTexture3DLerpToColor" : "KTexture3DLerp" };
        var output = new RenderTexture(new RenderTextureDescriptor(VolumeSize, VolumeSize, RenderTextureFormat.ARGBHalf, 0) {
            dimension = TextureDimension.Tex3D, volumeDepth = VolumeSize, enableRandomWrite = true, sRGB = false
        });
        try
        {
            if (!output.Create()) throw new Exception("ARGBHalf volume allocation failed");
            int kernel = shader.FindKernel(report.kernel);
            var threads = KernelThreads(shader, kernel);
            if (threads[0] != VolumeSize || threads[1] != VolumeSize || threads[2] != VolumeSize)
                throw new Exception("Unexpected volume workgroup dimensions");
            shader.SetVector("_DimensionsAndLerp", new Vector4(VolumeSize, VolumeSize, VolumeSize, 0.5f));
            shader.SetTexture(kernel, "_From", from);
            shader.SetTexture(kernel, "_Output", output);
            if (toColor) shader.SetVector("_TargetColor", targetColor);
            else shader.SetTexture(kernel, "_To", to);
            shader.Dispatch(kernel, 1, 1, 1);

            var readback = AsyncGPUReadback.Request(output, 0);
            readback.WaitForCompletion();
            if (readback.hasError || readback.layerCount * readback.layerDataSize != fromPixels.Length * sizeof(ushort))
                throw new Exception("Unexpected ARGBHalf readback shape or status");
            for (int layer = 0; layer < readback.layerCount; ++layer)
                foreach (ushort actual in readback.GetData<ushort>(layer))
                {
                    int i = report.components++;
                    float right = toColor ? targetColor[i % 4] : Mathf.HalfToFloat(toPixels[i]);
                    ushort expected = Mathf.FloatToHalf((Mathf.HalfToFloat(fromPixels[i]) + right) * 0.5f);
                    if (actual != expected) ++report.mismatches;
                }
            if (report.components != fromPixels.Length) throw new Exception("Incomplete ARGBHalf readback");
        }
        catch (Exception error) { report.failure = error.Message; }
        finally
        {
            output.Release();
            Destroy(output);
        }
        return report;
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
