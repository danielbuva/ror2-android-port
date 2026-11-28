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
    public string[] shaderAddresses;
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
        public Color32[] outlineSamples;
        public Color32[] intersectionSamples;
        public Color32[] cloudRemapSamples;
        public Color32[] terrainDetailOutside;
        public Color32[] clothDeferredSamples;
        public Color32[] clothShadowSamples;
        public Color32[] triplanarSamples;
        public Color32[] wireframeSamples;
        public bool passed;
        public string failure;
    }

    [Serializable] sealed class ShaderDrawBatchReport
    {
        public string graphics;
        public ShaderDrawReport[] draws;
        public bool passed;
    }

    [Serializable] sealed class TriplanarDrawReport
    {
        public string shader;
        public Color32[] triplanarSamples;
        public bool passed;
    }

    [Serializable] sealed class TriplanarDrawBatchReport
    {
        public string graphics;
        public TriplanarDrawReport[] draws;
        public bool passed;
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

    [Serializable] sealed class DownsampleReport
    {
        public string graphics;
        public int regularComponents;
        public int msaaComponents;
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
        if (shaderAddresses?.Length > 0 || computeAddresses?.Length > 0)
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
                if (shader.name == "MultiScaleVODownsample2")
                {
                    CheckDownsample2(shader, graphics);
                    return;
                }
                histogram.shader = shader.name;
                DispatchHistogram(shader, histogram);
            }
            catch (Exception error) { histogram.failure = error.Message; }
            Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(histogram));
            return;
        }

        var firstDraw = CheckShaderDraw(bundle, loadError, graphics, shaderAddresses[0]);
        if (shaderAddresses.Length == 1)
        {
            Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(firstDraw));
            return;
        }

        var draws = new ShaderDrawReport[shaderAddresses.Length];
        draws[0] = firstDraw;
        for (int i = 1; i < draws.Length; ++i)
            draws[i] = CheckShaderDraw(bundle, loadError, graphics, shaderAddresses[i]);
        bool passed = Array.TrueForAll(draws, draw => draw.passed);
        if (draws.Length == 3 && Array.TrueForAll(shaderAddresses, address => address.Contains("/triplanar-")))
        {
            // Keep the three triplanar samples in one Android log entry.
            foreach (var draw in draws)
                if (!string.IsNullOrEmpty(draw.failure)) Debug.LogWarning(draw.failure);
            var compact = new TriplanarDrawBatchReport {
                graphics = graphics, passed = passed,
                draws = Array.ConvertAll(draws, draw => new TriplanarDrawReport {
                    shader = draw.shader, triplanarSamples = draw.triplanarSamples, passed = draw.passed
                })
            };
            Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(compact));
            return;
        }
        var batch = new ShaderDrawBatchReport {
            graphics = graphics, draws = draws, passed = passed
        };
        Debug.Log("PHONE_SHADER_DRAW " + JsonUtility.ToJson(batch));
    }

    static ShaderDrawReport CheckShaderDraw(AssetBundle bundle, string loadError, string graphics, string address)
    {
        var report = new ShaderDrawReport { graphics = graphics };
        try
        {
            if (bundle == null) throw new Exception(loadError ?? "Shader bundle did not load");
            var shader = bundle.LoadAsset<Shader>(address);
            if (shader == null || !shader.isSupported) throw new Exception("Shader is unavailable or unsupported: " + address);
            report.shader = shader.name;
            if (shader.name == "Unlit/OutlineHighlightNew") DrawOutline(shader, report);
            else if (shader.name == "Hopoo Games/FX/Cloud Intersection Remap") DrawIntersection(shader, report);
            else if (shader.name == "Hidden/TerrainEngine/TerrainLayerUtils") DrawTerrainLayers(shader, report);
            else if (shader.name == "Hopoo Games/FX/Cloud Remap") DrawCloudRemap(shader, report);
            else if (shader.name == "Hidden/TerrainEngine/Details/WavingDoublePass") DrawTerrainDetail(shader, report, false);
            else if (shader.name == "Hidden/TerrainEngine/Details/BillboardWavingDoublePass") DrawTerrainDetail(shader, report, true);
            else if (shader.name == "Hopoo Games/Deferred/Wavy Cloth") DrawWavyCloth(shader, report);
            else if (shader.name == "Hopoo Games/Deferred/Triplanar Terrain Blend" ||
                shader.name == "Hopoo Games/Deferred/Triplanar Terrain Blend Emissive")
                DrawTriplanar(shader, report, new[] { "_RedChannelSideTex", "_RedChannelTopTex", "_GreenChannelTex", "_BlueChannelTex" });
            else if (shader.name == "Hopoo Games/Deferred/Standard Triplanar Splat")
                DrawTriplanar(shader, report, new[] { "_MainTex", "_RedSplatTex" });
            else if (shader.name == "Hopoo Games/Transparent/Texture Scrolling Wireframe") DrawWireframe(shader, report);
            else DrawAnimateAlpha(shader, report);
        }
        catch (Exception error) { report.failure = error.Message; }
        return report;
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

    const int DownsampleInputSize = 16;

    static float DownsampleDepth(int x, int y, int channel)
    {
        float depth = (1 + x + DownsampleInputSize * y) / 512f;
        return channel == 0 ? depth : 1f - depth;
    }

    static void CheckDownsample2(ComputeShader shader, string graphics)
    {
        var report = new DownsampleReport { graphics = graphics };
        try
        {
            report.regularComponents = DispatchDownsample2(shader, false);
            report.msaaComponents = DispatchDownsample2(shader, true);
            report.passed = graphics == "Vulkan" && report.regularComponents == 160 && report.msaaComponents == 320;
        }
        catch (Exception error) { report.failure = error.Message; }
        Debug.Log("PHONE_SHADER_COMPUTE " + JsonUtility.ToJson(report));
    }

    static int DispatchDownsample2(ComputeShader shader, bool msaa)
    {
        // Post Processing 2.3.0 passes a single-sample DS4x plane with one or two depth channels.
        int channels = msaa ? 2 : 1;
        string kernelName = msaa ? "MultiScaleVODownsample2_MSAA" : "MultiScaleVODownsample2";
        int kernel = shader.FindKernel(kernelName);
        var threads = KernelThreads(shader, kernel);
        if (threads[0] != 8 || threads[1] != 8 || threads[2] != 1)
            throw new Exception("Unexpected downsample workgroup dimensions: " + kernelName);

        string[] names = { "DS8x", "DS8xAtlas", "DS16x", "DS16xAtlas" };
        var outputs = new RenderTexture[names.Length];
        var source = new Texture2D(DownsampleInputSize, DownsampleInputSize,
            msaa ? TextureFormat.RGFloat : TextureFormat.RFloat, false, true);
        try
        {
            var pixels = new float[DownsampleInputSize * DownsampleInputSize * channels];
            for (int y = 0, i = 0; y < DownsampleInputSize; ++y)
                for (int x = 0; x < DownsampleInputSize; ++x)
                    for (int channel = 0; channel < channels; ++channel)
                        pixels[i++] = DownsampleDepth(x, y, channel);
            source.SetPixelData(pixels, 0);
            source.Apply();
            shader.SetTexture(kernel, "DS4x", source);

            for (int i = 0; i < outputs.Length; ++i)
            {
                bool atlas = (i & 1) != 0;
                int size = (i < 2 ? 8 : 4) / (atlas ? 4 : 1);
                var format = atlas ? (msaa ? RenderTextureFormat.RGHalf : RenderTextureFormat.RHalf)
                    : (msaa ? RenderTextureFormat.RGFloat : RenderTextureFormat.RFloat);
                var output = new RenderTexture(new RenderTextureDescriptor(size, size, format, 0) {
                    dimension = atlas ? TextureDimension.Tex2DArray : TextureDimension.Tex2D,
                    volumeDepth = atlas ? 16 : 1, enableRandomWrite = true, sRGB = false
                });
                outputs[i] = output;
                if (!output.Create()) throw new Exception("Downsample target allocation failed: " + names[i]);
                shader.SetTexture(kernel, names[i], output);
            }
            shader.Dispatch(kernel, 1, 1, 1);

            int components = 0;
            for (int i = 0; i < outputs.Length; ++i)
                components += CheckDownsampleOutput(outputs[i], names[i], i < 2 ? 2 : 4, channels);
            return components;
        }
        finally
        {
            foreach (var output in outputs)
                if (output != null) { output.Release(); Destroy(output); }
            Destroy(source);
        }
    }

    static int CheckDownsampleOutput(RenderTexture output, string name, int scale, int channels)
    {
        var readback = AsyncGPUReadback.Request(output, 0);
        readback.WaitForCompletion();
        bool atlas = output.dimension == TextureDimension.Tex2DArray;
        int components = output.width * output.height * channels;
        if (readback.hasError || readback.layerCount != output.volumeDepth ||
            readback.layerDataSize != components * (atlas ? sizeof(ushort) : sizeof(float)))
            throw new Exception("Unexpected downsample readback shape or status: " + name);

        // Each atlas layer selects one pixel from every 4 by 4 tile of the plane.
        for (int layer = 0; layer < readback.layerCount; ++layer)
        {
            var halves = atlas ? readback.GetData<ushort>(layer) : default;
            var singles = atlas ? default : readback.GetData<float>(layer);
            for (int y = 0, i = 0; y < output.height; ++y)
                for (int x = 0; x < output.width; ++x)
                    for (int channel = 0; channel < channels; ++channel, ++i)
                    {
                        int sourceX = scale * (atlas ? 4 * x + (layer & 3) : x);
                        int sourceY = scale * (atlas ? 4 * y + (layer >> 2) : y);
                        float expected = DownsampleDepth(sourceX, sourceY, channel);
                        bool matches = atlas ? halves[i] == Mathf.FloatToHalf(expected) : singles[i] == expected;
                        if (!matches)
                            throw new Exception($"Downsample mismatch: {name}, layer {layer}, ({x}, {y}), channel {channel}");
                    }
        }
        return components * readback.layerCount;
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

    static void DrawWireframe(Shader shader, ShaderDrawReport report)
    {
        const int size = 64;
        var material = new Material(shader);
        var mesh = new Mesh();
        var pixels = new Texture2D(size, size, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(size, size, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        try
        {
            // Keep the triangle below the center so the upper sample also detects a clip-space Y inversion.
            mesh.vertices = new[] {
                new Vector3(-0.75f, -0.6875f, 0.5f), new Vector3(0.625f, -0.6875f, 0.5f),
                new Vector3(-0.40625f, -0.09375f, 0.5f)
            };
            mesh.triangles = new[] { 0, 1, 2 };
            var uv = new[] { Vector2.zero, Vector2.right, Vector2.up };
            mesh.uv = uv;
            mesh.uv2 = uv;
            mesh.colors = new[] { Color.white, Color.white, Color.white };

            material.SetTexture("_MainTex", Texture2D.whiteTexture);
            material.SetTexture("_EmTex", Texture2D.whiteTexture);
            material.SetTexture("_ScrollTex", Texture2D.whiteTexture);
            material.SetTexture("_RemapTex", Texture2D.blackTexture);
            material.SetColor("_Color", Color.blue);
            material.SetColor("_EmColor", Color.black);
            material.SetColor("_WireframeColor", Color.red);
            material.SetColor("_VertColor", Color.red);
            material.SetFloat("_EmBoost", 1);
            material.SetFloat("_EmPower", 1);
            material.SetFloat("_WireframeThickness", 0.1f);
            material.SetFloat("_WireframeSmoothing", 1);
            material.SetFloat("_Cull", (float)CullMode.Off);
            material.SetFloat("_ZTest", (float)CompareFunction.Always);
            material.SetFloat("_SrcBlend", (float)BlendMode.One);
            material.SetFloat("_DstBlend", (float)BlendMode.Zero);

            using var commands = new CommandBuffer();
            commands.SetRenderTarget(target);
            commands.ClearRenderTarget(true, true, Color.green);
            commands.SetViewProjectionMatrices(Matrix4x4.identity, Matrix4x4.identity);
            // The first source pass writes depth only.
            commands.DrawMesh(mesh, Matrix4x4.identity, material, 0, 1);
            Graphics.ExecuteCommandBuffer(commands);
            RenderTexture.active = target;
            pixels.ReadPixels(new Rect(0, 0, size, size), 0, 0, false);
            report.wireframeSamples = new Color32[] {
                pixels.GetPixel(23, 10), pixels.GetPixel(23, 17), pixels.GetPixel(23, 53)
            };
            var expected = new Color32[] { Color.magenta, Color.blue, Color.green };
            for (int i = 0; i < expected.Length; ++i)
            {
                var sample = report.wireframeSamples[i];
                var match = expected[i];
                if (Mathf.Abs(sample.r - match.r) > 5 || Mathf.Abs(sample.g - match.g) > 5 ||
                    Mathf.Abs(sample.b - match.b) > 5)
                    throw new Exception("Wireframe sample " + i + " did not match the expected RGB");
            }
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(material);
            Destroy(mesh);
            Destroy(pixels);
        }
    }

    static void DrawIntersection(Shader shader, ShaderDrawReport report)
    {
        const string directional = "DIRECTIONAL";
        int cameraPosition = Shader.PropertyToID("_WorldSpaceCameraPos");
        var previousCameraPosition = Shader.GetGlobalVector(cameraPosition);
        bool previousDirectional = Shader.IsKeywordEnabled(directional);
        var mainMask = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var ramp = new Texture2D(2, 1, TextureFormat.RGBA32, false, true) {
            filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp
        };
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(32, 32, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        var plain = new Material(shader);
        var mesh = new Mesh();
        Material instanced = null;
        try
        {
            using var commands = new CommandBuffer();
            mainMask.SetPixel(0, 0, Color.clear);
            mainMask.Apply();
            ramp.SetPixels(new[] { Color.red, Color.green });
            ramp.Apply();
            plain.SetTexture("_MainTex", mainMask);
            plain.SetTexture("_Cloud1Tex", Texture2D.whiteTexture);
            plain.SetTexture("_Cloud2Tex", Texture2D.whiteTexture);
            plain.SetTexture("_RemapTex", ramp);
            plain.SetColor("_TintColor", Color.white);
            plain.SetInt("_SrcBlendFloat", (int)BlendMode.One);
            plain.SetInt("_DstBlendFloat", (int)BlendMode.Zero);
            plain.SetInt("_Cull", (int)CullMode.Off);
            foreach (string property in new[] { "_Boost", "_ExternalAlpha", "_AlphaBoost",
                "_IntersectionStrength", "_RimPower", "_RimStrength" })
                plain.SetFloat(property, 1);
            plain.SetFloat("_InvFade", 0);
            instanced = new Material(plain) { enableInstancing = true };
            instanced.SetTexture("_MainTex", Texture2D.whiteTexture);

            mesh.vertices = new[] {
                new Vector3(-0.15f, -0.2f, 0.5f), new Vector3(-0.15f, 0.2f, 0.5f),
                new Vector3(0.15f, 0.2f, 0.5f), new Vector3(0.15f, -0.2f, 0.5f)
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            mesh.uv = new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right };
            mesh.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            mesh.colors = new[] { Color.white, Color.white, Color.white, Color.white };
            var transforms = new[] {
                Matrix4x4.Translate(new Vector3(-0.6f, 0, 0)), Matrix4x4.Translate(new Vector3(0.6f, 0, 0))
            };
            commands.SetRenderTarget(target);
            commands.ClearRenderTarget(true, true, Color.blue);
            commands.SetViewProjectionMatrices(Matrix4x4.identity, Matrix4x4.identity);
            commands.SetGlobalVector(cameraPosition, new Vector4(0, 0, 2, 1));
            commands.EnableShaderKeyword(directional);
            commands.DrawMesh(mesh, Matrix4x4.identity, plain, 0, 0);
            commands.DrawMeshInstanced(mesh, 0, instanced, 0, transforms, transforms.Length, null);
            Graphics.ExecuteCommandBuffer(commands);

            RenderTexture.active = target;
            pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
            report.intersectionSamples = new Color32[] {
                pixels.GetPixel(16, 0), pixels.GetPixel(6, 0), pixels.GetPixel(25, 0), pixels.GetPixel(11, 0)
            };
            // With depth fade disabled, the camera-facing rim drives opaque masks
            // to the high ramp endpoint. The transparent mask stays at the low end.
            var expected = new Color32[] { Color.red, Color.green, Color.green, Color.blue };
            for (int i = 0; i < expected.Length; ++i)
            {
                var sample = report.intersectionSamples[i];
                var match = expected[i];
                if (Mathf.Abs(sample.r - match.r) > 5 || Mathf.Abs(sample.g - match.g) > 5 ||
                    Mathf.Abs(sample.b - match.b) > 5)
                    throw new Exception("Cloud Intersection sample " + i + " did not match the expected RGB");
            }
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            if (!previousDirectional) Shader.DisableKeyword(directional);
            Shader.SetGlobalVector(cameraPosition, previousCameraPosition);
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(plain);
            Destroy(instanced);
            Destroy(mesh);
            Destroy(mainMask);
            Destroy(ramp);
            Destroy(pixels);
        }
    }

    static void DrawCloudRemap(Shader shader, ShaderDrawReport report)
    {
        const string directional = "DIRECTIONAL";
        bool previousDirectional = Shader.IsKeywordEnabled(directional);
        var material = new Material(shader);
        var transparent = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var ramp = new Texture2D(2, 1, TextureFormat.RGBA32, false, true) {
            filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp
        };
        var mesh = new Mesh();
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(32, 32, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        try
        {
            transparent.SetPixel(0, 0, Color.clear);
            transparent.Apply();
            ramp.SetPixels(new[] { Color.red, Color.green });
            ramp.Apply();
            material.SetTexture("_RemapTex", ramp);
            material.SetColor("_TintColor", Color.white);
            material.SetInt("_SrcBlend", (int)BlendMode.One);
            material.SetInt("_DstBlend", (int)BlendMode.Zero);
            material.SetInt("_Cull", (int)CullMode.Off);
            material.SetInt("_ZTest", (int)CompareFunction.Always);
            foreach (string property in new[] { "_Boost", "_ExternalAlpha", "_AlphaBoost", "_Fade" })
                material.SetFloat(property, 1);
            material.SetFloat("_AlphaBias", 0);

            mesh.vertices = new[] {
                new Vector3(-0.15f, -0.2f, 0.5f), new Vector3(-0.15f, 0.2f, 0.5f),
                new Vector3(0.15f, 0.2f, 0.5f), new Vector3(0.15f, -0.2f, 0.5f)
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            mesh.uv = new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right };
            mesh.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            mesh.colors = new[] { Color.white, Color.white, Color.white, Color.white };
            var low = new MaterialPropertyBlock();
            var high = new MaterialPropertyBlock();
            low.SetTexture("_MainTex", transparent);
            high.SetTexture("_MainTex", Texture2D.whiteTexture);
            using var commands = new CommandBuffer();
            commands.SetRenderTarget(target);
            commands.ClearRenderTarget(true, true, Color.blue);
            commands.SetViewProjectionMatrices(Matrix4x4.identity, Matrix4x4.identity);
            commands.EnableShaderKeyword(directional);
            commands.DrawMesh(mesh, Matrix4x4.Translate(new Vector3(-0.6f, 0, 0)), material, 0, 0, low);
            commands.DrawMesh(mesh, Matrix4x4.Translate(new Vector3(0.6f, 0, 0)), material, 0, 0, high);
            Graphics.ExecuteCommandBuffer(commands);

            RenderTexture.active = target;
            pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
            report.cloudRemapSamples = new Color32[] { pixels.GetPixel(6, 0), pixels.GetPixel(25, 0), pixels.GetPixel(16, 0) };
            var expected = new Color32[] { Color.red, Color.green, Color.blue };
            for (int i = 0; i < expected.Length; ++i)
            {
                if (!report.cloudRemapSamples[i].Equals(expected[i]))
                    throw new Exception("Cloud Remap sample " + i + " did not match the expected RGBA");
            }
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            if (!previousDirectional) Shader.DisableKeyword(directional);
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(material);
            Destroy(transparent);
            Destroy(ramp);
            Destroy(mesh);
            Destroy(pixels);
        }
    }

    static void DrawWavyCloth(Shader shader, ShaderDrawReport report)
    {
        const string shadowKeyword = "SHADOWS_DEPTH";
        int lightDirection = Shader.PropertyToID("_WorldSpaceLightPos0");
        int shadowBias = Shader.PropertyToID("unity_LightShadowBias");
        var previousDirection = Shader.GetGlobalVector(lightDirection);
        var previousBias = Shader.GetGlobalVector(shadowBias);
        bool previousShadowKeyword = Shader.IsKeywordEnabled(shadowKeyword);
        var previousTarget = RenderTexture.active;
        var mesh = new Mesh();
        var material = new Material(shader);
        var transparent = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var normal = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var color = new RenderTexture[4];
        try
        {
            int deferred = material.FindPass("DEFERRED");
            int shadowCaster = material.FindPass("ShadowCaster");
            if (deferred < 0 || shadowCaster < 0)
                throw new Exception("Wavy Cloth Deferred or ShadowCaster pass is missing");

            var targets = new RenderTargetIdentifier[color.Length];
            for (int i = 0; i < color.Length; ++i)
            {
                color[i] = RenderTexture.GetTemporary(32, 32, i == 0 ? 24 : 0,
                    RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
                targets[i] = color[i];
            }
            mesh.vertices = new[] {
                new Vector3(-0.16f, -0.2f, 0), new Vector3(-0.16f, 0.2f, 0),
                new Vector3(0.16f, 0.2f, 0), new Vector3(0.16f, -0.2f, 0)
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            mesh.normals = new[] { Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward };
            var tangent = new Vector4(1, 0, 0, 1);
            mesh.tangents = new[] { tangent, tangent, tangent, tangent };
            mesh.colors = new[] { Color.white, Color.white, Color.white, Color.white };
            var uv = new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right };
            mesh.uv = uv;
            mesh.uv2 = uv;
            mesh.uv3 = uv;
            mesh.uv4 = uv;

            transparent.SetPixel(0, 0, Color.clear);
            transparent.Apply();
            normal.SetPixel(0, 0, new Color(0.5f, 0.5f, 1, 0.5f));
            normal.Apply();
            material.SetTexture("_MainTex", Texture2D.whiteTexture);
            material.SetTexture("_ScrollingNormalMap", normal);
            material.SetColor("_Color", Color.green);
            material.SetFloat("_Cutoff", 0.5f);
            material.SetFloat("_VertexOffsetStrength", 0);
            material.SetFloat("_NormalStrength", 0);
            material.SetInt("_EnableVertexColorDistortion", 0);
            material.SetVector("_WindVector", Vector4.zero);
            material.SetVector("_Scroll", Vector4.zero);
            var cutout = new MaterialPropertyBlock();
            cutout.SetTexture("_MainTex", transparent);

            var nearLeft = Matrix4x4.Translate(new Vector3(-0.6f, 0, -1));
            var nearRight = Matrix4x4.Translate(new Vector3(0.6f, 0, -1));
            var farLeft = Matrix4x4.Translate(new Vector3(-0.6f, 0, -2));
            var farRight = Matrix4x4.Translate(new Vector3(0.6f, 0, -2));
            var projection = Matrix4x4.Ortho(-1, 1, -1, 1, 0.1f, 10);
            using var commands = new CommandBuffer();

            Color32[] ReadPair()
            {
                Graphics.ExecuteCommandBuffer(commands);
                commands.Clear();
                RenderTexture.active = color[0];
                pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
                return new Color32[] { pixels.GetPixel(6, 0), pixels.GetPixel(25, 0) };
            }

            void BeginPair()
            {
                commands.SetRenderTarget(targets, targets[0]);
                commands.ClearRenderTarget(true, true, Color.blue);
                commands.SetViewProjectionMatrices(Matrix4x4.identity, projection);
                commands.DisableShaderKeyword(shadowKeyword);
            }

            BeginPair();
            commands.DrawMesh(mesh, farLeft, material, 0, deferred);
            commands.DrawMesh(mesh, farRight, material, 0, deferred);
            var baseline = ReadPair();
            if (!baseline[0].Equals((Color32)Color.green) || !baseline[1].Equals((Color32)Color.green))
                throw new Exception("Wavy Cloth Deferred baseline did not cover both samples");

            BeginPair();
            commands.DrawMesh(mesh, farLeft, material, 0, deferred);
            commands.DrawMesh(mesh, farRight, material, 0, deferred, cutout);
            report.clothDeferredSamples = ReadPair();
            if (!report.clothDeferredSamples[0].Equals((Color32)Color.green) ||
                !report.clothDeferredSamples[1].Equals((Color32)Color.blue))
                throw new Exception("Wavy Cloth Deferred alpha-cutout samples differ");

            BeginPair();
            commands.SetGlobalVector(lightDirection, new Vector4(0, 0, 1, 0));
            commands.SetGlobalVector(shadowBias, Vector4.zero);
            commands.EnableShaderKeyword(shadowKeyword);
            commands.DrawMesh(mesh, nearLeft, material, 0, shadowCaster);
            commands.DrawMesh(mesh, nearRight, material, 0, shadowCaster, cutout);
            commands.ClearRenderTarget(false, true, Color.blue);
            commands.DisableShaderKeyword(shadowKeyword);
            commands.DrawMesh(mesh, farLeft, material, 0, deferred);
            commands.DrawMesh(mesh, farRight, material, 0, deferred);
            report.clothShadowSamples = ReadPair();
            if (!report.clothShadowSamples[0].Equals((Color32)Color.blue) ||
                !report.clothShadowSamples[1].Equals((Color32)Color.green))
                throw new Exception("Wavy Cloth ShadowCaster depth samples differ");
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            if (previousShadowKeyword) Shader.EnableKeyword(shadowKeyword);
            else Shader.DisableKeyword(shadowKeyword);
            Shader.SetGlobalVector(lightDirection, previousDirection);
            Shader.SetGlobalVector(shadowBias, previousBias);
            RenderTexture.active = previousTarget;
            foreach (var target in color)
                if (target != null) RenderTexture.ReleaseTemporary(target);
            Destroy(mesh);
            Destroy(material);
            Destroy(transparent);
            Destroy(normal);
            Destroy(pixels);
        }
    }

    static void DrawTriplanar(Shader shader, ShaderDrawReport report, string[] albedoProperties)
    {
        var previous = RenderTexture.active;
        var material = new Material(shader);
        var mesh = new Mesh();
        var red = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var green = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var normal = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var color = new RenderTexture[4];
        try
        {
            int deferred = material.FindPass("DEFERRED");
            if (deferred < 0) throw new Exception("Triplanar Deferred pass is missing");
            var targets = new RenderTargetIdentifier[color.Length];
            for (int i = 0; i < color.Length; ++i)
            {
                color[i] = RenderTexture.GetTemporary(32, 32, i == 0 ? 24 : 0,
                    RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
                targets[i] = color[i];
            }

            mesh.vertices = new[] {
                new Vector3(-0.16f, -0.2f, 0), new Vector3(-0.16f, 0.2f, 0),
                new Vector3(0.16f, 0.2f, 0), new Vector3(0.16f, -0.2f, 0)
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            mesh.normals = new[] { Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward };
            var tangent = new Vector4(1, 0, 0, 1);
            mesh.tangents = new[] { tangent, tangent, tangent, tangent };
            mesh.colors = new[] { Color.white, Color.white, Color.white, Color.white };
            var uv = new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right };
            mesh.uv = uv;
            mesh.uv2 = uv;
            mesh.uv3 = uv;
            mesh.uv4 = uv;

            material.SetFloat("_Cull", (float)CullMode.Off);
            material.SetColor("_Color", Color.white);
            red.SetPixel(0, 0, Color.red);
            red.Apply();
            green.SetPixel(0, 0, Color.green);
            green.Apply();
            normal.SetPixel(0, 0, new Color(0.5f, 0.5f, 1, 0.5f));
            normal.Apply();
            material.SetTexture("_SplatmapTex", red);
            material.SetTexture("_NormalTex", normal);
            foreach (var property in new[] { "_overallColor", "_RedTint", "_RColor", "_GColor", "_BColor" })
                if (material.HasProperty(property)) material.SetColor(property, Color.white);
            var redAlbedo = new MaterialPropertyBlock();
            var greenAlbedo = new MaterialPropertyBlock();
            foreach (var property in albedoProperties)
            {
                redAlbedo.SetTexture(property, red);
                greenAlbedo.SetTexture(property, green);
            }

            using var commands = new CommandBuffer();
            commands.SetRenderTarget(targets, targets[0]);
            commands.ClearRenderTarget(true, true, Color.blue);
            commands.SetViewProjectionMatrices(Matrix4x4.identity, Matrix4x4.Ortho(-1, 1, -1, 1, 0.1f, 10));
            commands.DrawMesh(mesh, Matrix4x4.Translate(new Vector3(-0.6f, 0, -1)), material, 0, deferred, redAlbedo);
            commands.DrawMesh(mesh, Matrix4x4.Translate(new Vector3(0.6f, 0, -1)), material, 0, deferred, greenAlbedo);
            Graphics.ExecuteCommandBuffer(commands);
            RenderTexture.active = color[0];
            pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
            Color32 left = pixels.GetPixel(6, 0);
            Color32 middle = pixels.GetPixel(16, 0);
            Color32 right = pixels.GetPixel(25, 0);
            report.triplanarSamples = new[] { left, middle, right };
            if (left.r <= 64 || left.g != 0 || left.b != 0 || !middle.Equals((Color32)Color.blue) ||
                right.g <= 64 || right.r != 0 || right.b != 0)
                throw new Exception("Triplanar Deferred albedo or clear samples differ");
            report.passed = report.graphics == "Vulkan";
        }
        finally
        {
            RenderTexture.active = previous;
            foreach (var target in color)
                if (target != null) RenderTexture.ReleaseTemporary(target);
            Destroy(mesh);
            Destroy(material);
            Destroy(red);
            Destroy(green);
            Destroy(normal);
            Destroy(pixels);
        }
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
            report.low = DrawPassSample(material, pixels, Texture2D.blackTexture, 0);
            report.high = DrawPassSample(material, pixels, Texture2D.whiteTexture, 0);
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

    static void DrawTerrainLayers(Shader shader, ShaderDrawReport report)
    {
        var material = new Material(shader);
        var source = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var pixels = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(16, 16, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        GL.PushMatrix();
        try
        {
            var texel = new Color32(17, 109, 223, 255);
            source.SetPixels32(new[] { texel });
            source.Apply();
            material.SetVector("_LayerMask", new Vector4(0, 1, 0, 0));
            material.SetTextureScale("_MainTex", Vector2.one);
            material.SetTextureOffset("_MainTex", Vector2.zero);
            RenderTexture.active = target;
            GL.LoadOrtho();
            if (material.passCount != 3) throw new Exception("Terrain Layer Utils did not expose three passes");
            report.low = DrawPassSample(material, pixels, source, 0);
            report.high = DrawPassSample(material, pixels, source, 2);
            // Pass 0 replicates the masked channel and uses Max blending over the blue clear.
            var maskedOverBlue = new Color32(texel.g, texel.g, byte.MaxValue, byte.MaxValue);
            report.passed = report.graphics == "Vulkan" &&
                report.low.Equals(maskedOverBlue) && report.high.Equals(texel);
        }
        finally
        {
            GL.PopMatrix();
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Destroy(material);
            Destroy(source);
            Destroy(pixels);
        }
    }

    static Color32 DrawPassSample(Material material, Texture2D pixels, Texture texture, int pass)
    {
        GL.Clear(true, true, Color.blue);
        material.SetTexture("_MainTex", texture);
        if (!material.SetPass(pass)) throw new Exception("Shader pass " + pass + " could not bind");
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

    static void DrawTerrainDetail(Shader shader, ShaderDrawReport report, bool billboard)
    {
        const int layer = 30;
        int mask = 1 << layer;
        var cameraGlobals = new[] { "_CameraPosition", "_CameraRight", "_CameraUp" };
        var previousGlobals = Array.ConvertAll(cameraGlobals, Shader.GetGlobalVector);
        int previousPixelLights = QualitySettings.pixelLightCount;
        var camera = new GameObject("Terrain detail camera").AddComponent<Camera>();
        var geometry = new GameObject("Terrain detail geometry") { layer = layer };
        var sun = new GameObject("Terrain detail directional light").AddComponent<Light>();
        var point = new GameObject("Terrain detail point light").AddComponent<Light>();
        var material = new Material(shader);
        var mesh = new Mesh();
        var pixels = new Texture2D(32, 1, TextureFormat.RGBA32, false, true);
        var target = RenderTexture.GetTemporary(32, 32, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
        var previousTarget = RenderTexture.active;
        try
        {
            if (material.GetPassName(0) != "FORWARD") throw new Exception("Terrain detail base pass unavailable");
            material.SetTexture("_MainTex", Texture2D.whiteTexture);
            material.SetFloat("_Cutoff", 0.25f);
            // The shader's Material distance default clips the entire fixture.
            material.SetVector("_WaveAndDistance", new Vector4(0, 0, 0, 16));
            material.SetColor("_WavingTint", Color.white);

            camera.enabled = false;
            camera.transform.SetPositionAndRotation(new Vector3(0, 0, 2), Quaternion.Euler(0, 180, 0));
            camera.renderingPath = RenderingPath.Forward;
            camera.orthographic = true;
            camera.orthographicSize = 0.5f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.blue;
            camera.cullingMask = mask;
            camera.allowHDR = false;
            camera.allowMSAA = false;
            camera.targetTexture = target;
            Shader.SetGlobalVector(cameraGlobals[0], new Vector4(0, 0, 2, 1));
            Shader.SetGlobalVector(cameraGlobals[1], camera.transform.right);
            Shader.SetGlobalVector(cameraGlobals[2], camera.transform.up);

            QualitySettings.pixelLightCount = 1;
            sun.type = LightType.Directional;
            sun.transform.rotation = camera.transform.rotation;
            sun.intensity = 0.25f;
            sun.renderMode = LightRenderMode.ForcePixel;
            sun.cullingMask = mask;
            sun.shadows = LightShadows.None;
            point.type = LightType.Point;
            point.transform.position = new Vector3(0, 0, 1.35f);
            point.range = 3;
            point.color = Color.red;
            point.renderMode = LightRenderMode.ForceVertex;
            point.cullingMask = mask;
            point.shadows = LightShadows.None;

            var center = new Vector3(0, 0, 0.5f);
            var corners = new[] {
                new Vector2(-0.25f, -0.25f), new Vector2(-0.25f, 0.25f),
                new Vector2(0.25f, 0.25f), new Vector2(0.25f, -0.25f)
            };
            // A billboard can only cover the sample after its vertex program expands it.
            mesh.vertices = Array.ConvertAll(corners, corner => billboard ? center : center + (Vector3)corner);
            mesh.tangents = Array.ConvertAll(corners, corner => billboard
                ? new Vector4(corner.x, corner.y, 0, 1) : new Vector4(1, 0, 0, 1));
            mesh.normals = Array.ConvertAll(corners, _ => Vector3.forward);
            mesh.colors32 = Array.ConvertAll(corners, _ => (Color32)Color.white);
            var uv = new[] { Vector2.zero, Vector2.up, Vector2.one, Vector2.right };
            mesh.uv = mesh.uv2 = mesh.uv3 = mesh.uv4 = uv;
            // The billboard expands in camera axes while the mesh uses world axes.
            mesh.triangles = billboard ? new[] { 0, 1, 2, 0, 2, 3 } : new[] { 0, 2, 1, 0, 3, 2 };
            mesh.bounds = new Bounds(center, new Vector3(0.5f, 0.5f, 0.1f));
            geometry.AddComponent<MeshFilter>().sharedMesh = mesh;
            var renderer = geometry.AddComponent<MeshRenderer>();
            renderer.sharedMaterial = material;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;

            var inside = new Color32[2];
            report.terrainDetailOutside = new Color32[inside.Length];
            for (int i = 0; i < inside.Length; ++i)
            {
                point.enabled = i != 0;
                camera.Render();
                RenderTexture.active = target;
                pixels.ReadPixels(new Rect(0, 16, 32, 1), 0, 0, false);
                inside[i] = pixels.GetPixel(15, 0);
                report.terrainDetailOutside[i] = pixels.GetPixel(2, 0);
            }

            report.low = inside[0];
            report.high = inside[1];
            var clear = (Color32)Color.blue;
            report.passed = report.graphics == "Vulkan" && report.low.a == 255 && report.high.a == 255 &&
                report.low.g >= 16 && Mathf.Abs(report.low.r - report.low.g) <= 4 &&
                Mathf.Abs(report.low.b - report.low.g) <= 4 && report.high.r >= report.low.r + 16 &&
                Mathf.Abs(report.high.g - report.low.g) <= 4 && Mathf.Abs(report.high.b - report.low.b) <= 4 &&
                Array.TrueForAll(report.terrainDetailOutside, sample => sample.Equals(clear));
            if (!report.passed) throw new Exception("Terrain detail failed its vertex light readback");
        }
        finally
        {
            for (int i = 0; i < cameraGlobals.Length; ++i) Shader.SetGlobalVector(cameraGlobals[i], previousGlobals[i]);
            QualitySettings.pixelLightCount = previousPixelLights;
            camera.targetTexture = null;
            geometry.SetActive(false);
            sun.enabled = false;
            point.enabled = false;
            RenderTexture.active = previousTarget;
            RenderTexture.ReleaseTemporary(target);
            Destroy(camera.gameObject);
            Destroy(geometry);
            Destroy(sun.gameObject);
            Destroy(point.gameObject);
            Destroy(material);
            Destroy(mesh);
            Destroy(pixels);
        }
    }
}
