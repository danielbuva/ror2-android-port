// Subsystem: input/camera (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup Awake, OnEnable; teardown OnDestroy.
using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.SceneManagement;
using Unity.Profiling;

// Camera-only presentation pass and bounded measurements; source grading remains pending.
public sealed class AndroidPresentationCamera : MonoBehaviour
{
    [Serializable]
    public class Sample
    {
        public string scene, skybox, sun;
        public bool fog, sourceCubemap, fallbackLight;
        public int fogMode;
        public Color fogColor, ambientLight;
        public float fogStart, fogEnd, fogDensity, ambientIntensity;
        public float seconds, activeSeconds, meanMs, maxMs;
        public double sampledCpuMs, sampledGpuMs, sampledMainActiveMs, sampledRenderActiveMs, sampledDrawCalls, sampledSetPassCalls,
            sampledVertices, sampledGcAllocBytes;
        public int frameTimingSamples, gpuTimingSamples, mainTimingSamples, renderTimingSamples, renderCounterSamples, gcAllocSamples;
        public long allocatedBytes, reservedBytes, managedBytes;
        public int frames, over33ms, over50ms, gcCollections;
    }
    [Serializable]
    public class Report
    {
        public int frames, colorPasses, over33ms, over50ms, pauses, resumeFramesSkipped;
        public double totalMs;
        public string rawFrameTrace, rawFrameTraceError;
        public int rawFrameTraceFirstFrame, rawFrameTraceFrames, rawFrameTraceDropped;
        public bool rawFrameTraceClosed;
        public float meanMs, maxMs, backgroundSeconds;
        public bool sourceCubemap, sourceSun, cameraHdrAllowed, halfFloatSupported;
        public string colorTargetFormat, colorGraphicsFormat, gBuffer3Format, skybox, sun, skyboxStatus, error;
        public List<Sample> samples = new List<Sample>();
    }
    public Light fallbackLight;
    public readonly Report report = new Report();
    // Primitive, bounded storage only. No per-frame allocation or file I/O.
    public sealed class RawFrameCapture
    {
        public const int Capacity = 262144;
        public readonly int firstFrame;
        public int count, dropped;
        readonly float[] durations;
        public RawFrameCapture(int firstFrame, int capacity = Capacity)
        {
            this.firstFrame = firstFrame;
            durations = new float[capacity];
        }
        public void Observe(float ms)
        {
            if (count < durations.Length)
                durations[count++] = ms;
            else
                dropped++;
        }
        public void Write(string path)
        {
            using (var writer = new BinaryWriter(File.Open(path, FileMode.CreateNew, FileAccess.Write)))
            {
                // Little-endian header: magic, first ordinal, retained count,
                // final admitted ordinal, dropped count; then IEEE float32 ms.
                writer.Write(System.Text.Encoding.ASCII.GetBytes("ROR2FRAM"));
                writer.Write(firstFrame);
                writer.Write(count);
                writer.Write(firstFrame + count + dropped - 1);
                writer.Write(dropped);
                for (int i = 0; i < count; i++)
                    writer.Write(durations[i]);
            }
        }
    }
    RawFrameCapture rawFrames;
    public void BeginRawFrameCapture()
    {
        if (report.rawFrameTrace != null)
            return;
        rawFrames = new RawFrameCapture(report.frames + 1);
        report.rawFrameTraceFirstFrame = rawFrames.firstFrame;
        report.rawFrameTrace = "frame-times-" + Guid.NewGuid().ToString("N") + ".bin";
    }
    public void FinishRawFrameCapture()
    {
        if (rawFrames == null)
            return;
        report.rawFrameTraceFrames = rawFrames.count;
        report.rawFrameTraceDropped = rawFrames.dropped;
        try
        {
            rawFrames.Write(Path.Combine(Application.persistentDataPath, report.rawFrameTrace));
            report.rawFrameTraceClosed = true;
        }
        catch (Exception error)
        {
            report.rawFrameTraceError = error.GetType().Name + ": " + error.Message;
        }
        finally
        {
            rawFrames = null;
        }
    }
    Material grade;
    Camera view;
    double sum, timingCpu, timingGpu, timingMain, timingRender, drawCalls, setPassCalls, vertices, gcAllocBytes;
    int timingCount, timingGpuCount, timingMainCount, timingRenderCount, renderCounterCount, gcAllocCount;
    ProfilerRecorder mainThreadRecorder, renderThreadRecorder, drawCallsRecorder, setPassRecorder, verticesRecorder, gcAllocRecorder;
    readonly FrameTiming[] latestTiming = new FrameTiming[1];
    float next, began, backgroundBegan;
    int lightingScene = -1;
    bool sourceDirectional, measurementPaused, discardResumeFrame;
    void Awake()
    {
        view = GetComponent<Camera>();
        view.depthTextureMode |= DepthTextureMode.Depth;
        began = Time.realtimeSinceStartup;
        var shader = AndroidMaterialPresentation.LoadShader("AndroidColorGrade");
        if (shader && shader.isSupported)
            grade = new Material(shader);
        else
            report.error = "Android camera presentation pass unavailable";
    }
    void OnEnable()
    {
        mainThreadRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Internal, "Main Thread", 64);
        renderThreadRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Internal, "Render Thread", 64);
        drawCallsRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Draw Calls Count", 64);
        setPassRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "SetPass Calls Count", 64);
        verticesRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Render, "Vertices Count", 64);
        gcAllocRecorder = ProfilerRecorder.StartNew(ProfilerCategory.Memory, "GC Allocated In Frame", 64);
    }
    void OnApplicationPause(bool paused)
    {
        if (paused)
        {
            if (!measurementPaused)
            {
                measurementPaused = true;
                backgroundBegan = Time.realtimeSinceStartup;
                report.pauses++;
            }
        }
        else if (measurementPaused)
        {
            measurementPaused = false;
            report.backgroundSeconds += Mathf.Max(0, Time.realtimeSinceStartup - backgroundBegan);
            discardResumeFrame = true;
        }
    }
    void ObserveFrameTiming(float ms)
    {
        if (measurementPaused)
            return;
        // Android includes suspension in the first resumed unscaledDeltaTime. Exclude
        // only that lifecycle interval; genuine active-frame hitches still count.
        if (discardResumeFrame)
        {
            discardResumeFrame = false;
            report.resumeFramesSkipped++;
            return;
        }
        report.frames++;
        sum += ms;
        report.totalMs = sum;
        rawFrames?.Observe(ms);
        report.meanMs = (float)(sum / report.frames);
        report.maxMs = Mathf.Max(report.maxMs, ms);
        if (ms > 33.334f)
            report.over33ms++;
        if (ms > 50)
            report.over50ms++;
    }
    void ObserveRenderCounters()
    {
        if (drawCallsRecorder.Valid && setPassRecorder.Valid && verticesRecorder.Valid && drawCallsRecorder.Count > 0 &&
            setPassRecorder.Count > 0 && verticesRecorder.Count > 0)
        {
            renderCounterCount++;
            drawCalls += drawCallsRecorder.LastValue;
            setPassCalls += setPassRecorder.LastValue;
            vertices += verticesRecorder.LastValue;
        }
        if (gcAllocRecorder.Valid && gcAllocRecorder.Count > 0)
        {
            gcAllocCount++;
            gcAllocBytes += gcAllocRecorder.LastValue;
        }
    }
    void LateUpdate()
    {
        if (measurementPaused)
            return;
        AndroidNativeDeferredPresentation.Configure(view);
        // Four measured base-stage skies use Unity's original built-in cubemap shader.
        // Preserve their recovered cubemap, tint, exposure and rotation unchanged.
        var sky = RenderSettings.skybox;
        report.skybox = sky ? sky.name : null;
        report.sourceCubemap = sky && sky.shader && sky.shader.name == "Skybox/Cubemap" && sky.shader.isSupported;
        view.clearFlags = report.sourceCubemap ? CameraClearFlags.Skybox : CameraClearFlags.SolidColor;
        report.skyboxStatus =
            report.sourceCubemap ? "Original Unity cubemap material" : "Source sky unavailable or unverified; no replacement sky";
        var sun = RenderSettings.sun;
        report.sun = sun ? sun.name : null;
        report.sourceSun = sun && sun.isActiveAndEnabled;
        // A null sun reference does not mean that the source scene has no directional light.
        var scene = SceneManager.GetActiveScene();
        if (lightingScene != scene.handle || Time.realtimeSinceStartup >= next)
        {
            lightingScene = scene.handle;
            sourceDirectional = report.sourceSun;
            if (!sourceDirectional && scene.IsValid() && scene.isLoaded)
                foreach (var root in scene.GetRootGameObjects())
                    foreach (var light in root.GetComponentsInChildren<Light>(false))
                        if (light != fallbackLight && light.isActiveAndEnabled && light.type == LightType.Directional)
                        {
                            sourceDirectional = true;
                            break;
                        }
        }
        if (fallbackLight)
            fallbackLight.enabled = !sourceDirectional;
        ObserveFrameTiming(Time.unscaledDeltaTime * 1000);
        if (report.frames % 10 == 0)
            ObserveRenderCounters();
        if (report.frames % 30 == 0)
        {
            FrameTimingManager.CaptureFrameTimings();
            if (FrameTimingManager.GetLatestTimings(1, latestTiming) > 0)
            {
                var timing = latestTiming[0];
                timingCount++;
                timingCpu += timing.cpuFrameTime;
                if (timing.gpuFrameTime > 0)
                {
                    timingGpuCount++;
                    timingGpu += timing.gpuFrameTime;
                }
            }
            if (mainThreadRecorder.Valid && mainThreadRecorder.Count > 0)
            {
                timingMainCount++;
                timingMain += mainThreadRecorder.LastValue * 1e-6;
            }
            if (renderThreadRecorder.Valid && renderThreadRecorder.Count > 0)
            {
                timingRenderCount++;
                timingRender += renderThreadRecorder.LastValue * 1e-6;
            }
        }
        if (Time.realtimeSinceStartup >= next)
        {
            next = Time.realtimeSinceStartup + 30;
            if (report.samples.Count >= 120)
                report.samples.RemoveAt(0);
            report.samples.Add(new Sample { scene = scene.name,
                                            skybox = report.skybox,
                                            sun = report.sun,
                                            sourceCubemap = report.sourceCubemap,
                                            fallbackLight = fallbackLight && fallbackLight.enabled,
                                            fog = RenderSettings.fog,
                                            fogMode = (int)RenderSettings.fogMode,
                                            fogColor = RenderSettings.fogColor,
                                            fogStart = RenderSettings.fogStartDistance,
                                            fogEnd = RenderSettings.fogEndDistance,
                                            fogDensity = RenderSettings.fogDensity,
                                            ambientLight = RenderSettings.ambientLight,
                                            ambientIntensity = RenderSettings.ambientIntensity,
                                            seconds = Time.realtimeSinceStartup - began,
                                            activeSeconds = Mathf.Max(0, Time.realtimeSinceStartup - began - report.backgroundSeconds),
                                            meanMs = report.meanMs,
                                            maxMs = report.maxMs,
                                            frames = report.frames,
                                            over33ms = report.over33ms,
                                            over50ms = report.over50ms,
                                            frameTimingSamples = timingCount,
                                            gpuTimingSamples = timingGpuCount,
                                            mainTimingSamples = timingMainCount,
                                            renderTimingSamples = timingRenderCount,
                                            renderCounterSamples = renderCounterCount,
                                            gcAllocSamples = gcAllocCount,
                                            sampledCpuMs = timingCount > 0 ? timingCpu / timingCount : 0,
                                            sampledGpuMs = timingGpuCount > 0 ? timingGpu / timingGpuCount : 0,
                                            sampledMainActiveMs = timingMainCount > 0 ? timingMain / timingMainCount : 0,
                                            sampledRenderActiveMs = timingRenderCount > 0 ? timingRender / timingRenderCount : 0,
                                            sampledDrawCalls = renderCounterCount > 0 ? drawCalls / renderCounterCount : 0,
                                            sampledSetPassCalls = renderCounterCount > 0 ? setPassCalls / renderCounterCount : 0,
                                            sampledVertices = renderCounterCount > 0 ? vertices / renderCounterCount : 0,
                                            sampledGcAllocBytes = gcAllocCount > 0 ? gcAllocBytes / gcAllocCount : 0,
                                            allocatedBytes = Profiler.GetTotalAllocatedMemoryLong(),
                                            reservedBytes = Profiler.GetTotalReservedMemoryLong(),
                                            managedBytes = Profiler.GetMonoUsedSizeLong(),
                                            gcCollections = GC.CollectionCount(0) });
            timingCount = timingGpuCount = timingMainCount = timingRenderCount = renderCounterCount = gcAllocCount = 0;
            timingCpu = timingGpu = timingMain = timingRender = drawCalls = setPassCalls = vertices = gcAllocBytes = 0;
        }
    }
    void OnRenderImage(RenderTexture source, RenderTexture destination)
    {
        report.cameraHdrAllowed = view.allowHDR;
        report.halfFloatSupported = SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGBHalf);
        report.colorTargetFormat = source.format.ToString();
        report.colorGraphicsFormat = source.graphicsFormat.ToString();
        var gbuffer = Shader.GetGlobalTexture("_CameraGBufferTexture3") as RenderTexture;
        report.gBuffer3Format = gbuffer ? gbuffer.format.ToString() : "unavailable";
        if (grade && AndroidMaterialPresentation.report.enabled)
        {
            Graphics.Blit(source, destination, grade);
            report.colorPasses++;
        }
        else
            Graphics.Blit(source, destination);
    }
    void OnDestroy()
    {
        FinishRawFrameCapture();
        mainThreadRecorder.Dispose();
        renderThreadRecorder.Dispose();
        drawCallsRecorder.Dispose();
        setPassRecorder.Dispose();
        verticesRecorder.Dispose();
        gcAllocRecorder.Dispose();
        if (grade)
            Destroy(grade);
    }
}
