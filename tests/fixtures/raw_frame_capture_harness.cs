using System;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;
using UnityEngine;

// Only unrelated presentation dependencies are stubbed. The actual camera,
// admission/counters, bounded recorder and file writer are compiled unchanged.
public static class AndroidMaterialPresentation
{
    public sealed class Report { public bool enabled; }
    public static Report report = new Report();
    public static Shader LoadShader(string name) { return null; }
}
public static class AndroidNativeDeferredPresentation
{
    public static void Configure(Camera camera) { }
}
public static class RawFrameCaptureHarness
{
    static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }
    static void Field(object camera, string name, object value)
    {
        typeof(AndroidPresentationCamera).GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).SetValue(camera, value);
    }
    static void Observe(object camera, float ms)
    {
        typeof(AndroidPresentationCamera).GetMethod("ObserveFrameTiming", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(camera, new object[] { ms });
    }
    public static int Main(string[] args)
    {
        var camera = (AndroidPresentationCamera)FormatterServices.GetUninitializedObject(typeof(AndroidPresentationCamera));
        var report = new AndroidPresentationCamera.Report();
        var capture = new AndroidPresentationCamera.RawFrameCapture(1);
        Field(camera, "report", report);
        Field(camera, "rawFrames", capture);
        Observe(camera, 16.5f);
        Field(camera, "measurementPaused", true);
        Observe(camera, 10000f);
        Field(camera, "measurementPaused", false);
        Field(camera, "discardResumeFrame", true);
        Observe(camera, 10000f);
        Observe(camera, 33.334f);
        Observe(camera, 51.25f);
        Check(report.frames == 3 && capture.count == 3, "capture must use identical active-frame admission");
        Check(report.resumeFramesSkipped == 1, "exactly one resumed interval excluded");
        Check(report.over33ms == 1 && report.over50ms == 1 && report.maxMs == 51.25f, "strict thresholds and genuine hitch preserved");
        Check(report.totalMs == (double)16.5f + 33.334f + 51.25f, "exact cumulative float durations");
        capture.Write(Path.Combine(args[0], "capture.bin"));
        var overflow = new AndroidPresentationCamera.RawFrameCapture(8, 2);
        overflow.Observe(10); overflow.Observe(60); overflow.Observe(100);
        Check(overflow.count == 2 && overflow.dropped == 1, "bounded overflow must not overwrite retained frames");
        overflow.Write(Path.Combine(args[0], "overflow.bin"));
        Check(new FileInfo(Path.Combine(args[0], "overflow.bin")).Length == 32, "header plus exact retained float payload");
        Console.WriteLine("PASS raw frame admission, counters, exact sidecar and overflow");
        return 0;
    }
}
