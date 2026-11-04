using System;
using System.IO;
using System.Collections;
using UnityEngine;
using UnityEngine.Profiling;

namespace UnityEngine
{
    public static class Time { public static float realtimeSinceStartup = 10; }
    public sealed class WaitForEndOfFrame {}
}
partial class Monitor
{
    public sealed class World { public float seconds; }
    public sealed class Report { public string phase, firstFailure, error; public World world; }
    public Report r;
    public LoadingProfileCapture loadingProfile;
    public int saves;
    void Save() { saves++; }
    public IEnumerator Observe() { return ObserveLoadingProfile(); }
}
namespace UnityEngine.Profiling
{
    public enum ProfilerArea { CPU, Memory }
    public static class Profiler
    {
        public static bool enabled = true, enableBinaryLog = true, enableAllocationCallstacks = true;
        public static string logFile = "previous.raw";
        public static bool cpu, memory;
        public static bool failEnable;
        public static bool GetAreaEnabled(ProfilerArea area) { return area == ProfilerArea.CPU ? cpu : memory; }
        public static void SetAreaEnabled(ProfilerArea area, bool value)
        {
            if (failEnable && value) { failEnable = false; throw new Exception("native setup failed"); }
            if (area == ProfilerArea.CPU) cpu = value; else memory = value;
        }
    }
}

public static class Harness
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void Restored()
    {
        Check(Profiler.enabled && Profiler.enableBinaryLog && Profiler.enableAllocationCallstacks &&
              Profiler.logFile == "previous.raw" && !Profiler.cpu && !Profiler.memory, "previous profiler state lost");
    }
    public static void Main()
    {
        string root = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Check(LoadingProfileCapture.Begin(root) == null, "unrequested capture");
            Restored();
            string request = Path.Combine(root, "loading-profiler.request");
            File.WriteAllText(request, "");
            var capture = LoadingProfileCapture.Begin(root);
            Check(!File.Exists(request) && capture.active && Profiler.enabled && Profiler.enableBinaryLog &&
                  Profiler.cpu && Profiler.memory && !Profiler.enableAllocationCallstacks, "capture setup failed");
            Check(capture.path == Path.Combine(root, "diagnostics", "loading-profile.raw"), "unowned output path");
            File.WriteAllBytes(capture.path, new byte[] { 1, 2, 3, 4 });
            Time.realtimeSinceStartup = 20;
            capture.Stop("first-playable-frame");
            Check(capture.completed && !capture.active && capture.bytes == 4 && capture.stopReason == "first-playable-frame" &&
                  capture.startedAt == 10 && capture.stoppedAt == 20, "closure facts missing");
            capture.Dispose();
            Check(capture.stopReason == "first-playable-frame", "duplicate disposal rewrote closure");
            Restored();
            File.Delete(capture.path);
            File.WriteAllText(request, "");
            var empty = LoadingProfileCapture.Begin(root);
            empty.Stop("failure");
            Check(!empty.completed && empty.bytes == 0 && empty.stopReason == "failure", "empty capture accepted");
            Restored();
            File.WriteAllText(request, "");
            Profiler.failEnable = true;
            var failed = LoadingProfileCapture.Begin(root);
            Check(!failed.active && !failed.completed && failed.error.Contains("native setup failed") &&
                  failed.stopReason == "setup-failed", "setup failure hidden");
            Restored();
            File.WriteAllText(request, "");
            var destroyed = LoadingProfileCapture.Begin(root);
            destroyed.Dispose();
            Check(!destroyed.active && destroyed.stopReason == "destroyed", "destruction left capture open");
            Restored();
            File.WriteAllText(request, "");
            var monitor = new Monitor { loadingProfile = LoadingProfileCapture.Begin(root), r = new Monitor.Report {
                phase = "integrated-world-playing", world = new Monitor.World() } };
            var observer = monitor.Observe();
            Check(observer.MoveNext() && observer.Current is WaitForEndOfFrame, "not waiting for rendered frame");
            Check(observer.MoveNext() && monitor.loadingProfile.active, "phase alone closed capture");
            monitor.r.world.seconds = 0.1f;
            Check(!observer.MoveNext() && monitor.saves == 1 && monitor.loadingProfile.stopReason == "first-playable-frame",
                  "positive playable frame did not close and save");
            Restored();
            File.WriteAllText(request, "");
            monitor.loadingProfile = LoadingProfileCapture.Begin(root);
            monitor.r.firstFailure = "native failure";
            observer = monitor.Observe(); observer.MoveNext();
            Check(!observer.MoveNext() && monitor.loadingProfile.stopReason == "failure", "failure capture left open");
            Restored();
            File.WriteAllText(request, "");
            monitor.loadingProfile = LoadingProfileCapture.Begin(root);
            monitor.r = null;
            observer = monitor.Observe(); observer.MoveNext();
            Time.realtimeSinceStartup += 240;
            Check(!observer.MoveNext() && monitor.loadingProfile.stopReason == "deadline", "deadline capture left open");
            Restored();
            Console.WriteLine("loading profile opt-in closure restoration PASS");
        }
        finally { Directory.Delete(root, true); }
    }
}
