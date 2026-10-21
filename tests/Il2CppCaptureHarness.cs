using System;
using System.IO;
using System.Diagnostics;
using UnityEditor;
using UnityEditor.Build.Reporting;

public static class CaptureHarness
{
    static void Check(bool value, string reason) { if (!value) throw new Exception(reason); }
    static BuildReport Report(string guid, BuildResult result, string output)
    {
        return new BuildReport { summary = new BuildSummary { guid = new GUID { value = guid }, platform = BuildTarget.Android, outputPath = output, result = result, totalErrors = 0 } };
    }
    static void Write(string path, string text) { Directory.CreateDirectory(Path.GetDirectoryName(path)); File.WriteAllText(path, text); }
    static void Fixture(string scratch, string project, string work, bool opted)
    {
        Directory.CreateDirectory(Path.Combine(project, "Assets"));
        Directory.CreateDirectory(Path.Combine(work, "inventory"));
        Directory.CreateDirectory(Path.Combine(work, "editor"));
        Write(Path.Combine(project, ".port-input.json"), "{\"input_id\":\"" + new string('b', 64) + "\"}");
        Write(Path.Combine(work, "inventory/files.json"), "{\"input_id\":\"" + new string('b', 64) + "\"}");
        Write(Path.Combine(work, "build-request.json"), "{\"request_id\":\"host-request-1\",\"captureIl2CppInvocation\":" + (opted ? "true" : "false") + ",\"sourceCommit\":\"" + new string('a', 40) + "\",\"inputId\":\"" + new string('b', 64) + "\"}");
        Write(Path.Combine(work, "Editor.log"), "old editor log prefix\n");
        Write(Path.Combine(work, "editor/lab-process.json"), "{\"log\":\"" + Path.Combine(work, "Editor.log").Replace("\\", "\\\\") + "\",\"pid\":" + Process.GetCurrentProcess().Id + "}");
        Directory.CreateDirectory(Path.Combine(project, "Library/Bee/artifacts"));
        Write(Path.Combine(project, "Library/Bee/artifacts/il2cpp_conv_current.traceevents"), "old trace\n");
        Write(Path.Combine(project, "Library/Bee/PlayerCurrent.dag"), "old graph\n");
        Write(Path.Combine(project, "Library/Bee/PlayerCurrent.dag.json"), "{}\n");
    }
    public static int Main(string[] args)
    {
        string mode = args.Length == 0 ? "default-off" : args[0];
        string scratch = Path.Combine(Environment.GetEnvironmentVariable("LAB_HOST_TEMP_ROOT") ?? Path.GetTempPath(), "bee-capture-host-" + Guid.NewGuid().ToString("N"));
        string project = Path.Combine(scratch, "unity-project");
        string work = Path.GetFullPath(Path.Combine(project, ".."));
        string output = Path.Combine(project, "verified.apk");
        try
        {
            UnityEngine.Application.dataPath = Path.Combine(project, "Assets");
            var capture = new Il2CppInvocationCapture();
            if (mode == "default-off")
            {
                UnityEditor.SessionState.request = null;
                // Even a malformed isolated-work-root switch must be ignored when
                // no lab build session owns this Editor callback.
                capture.OnPreprocessBuild(Report("guid-default", BuildResult.Unknown, output));
                Check(!File.Exists(Path.Combine(work, "build-request.json")), "ordinary build accessed the request");
                Check(!Directory.Exists(Path.Combine(work, "lab-build")), "ordinary build created capture output");
                Console.WriteLine("ordinary build returned before request/path access");
                return 0;
            }
            if (mode == "active-off")
            {
                Fixture(scratch, project, work, false);
                UnityEditor.SessionState.request = "host-request-1";
                capture.OnPreprocessBuild(Report("guid-off", BuildResult.Unknown, output));
                Check(!Directory.Exists(Path.Combine(work, "lab-build")), "off request created capture output");
                Check(!File.Exists(Path.Combine(work, "lab-build/player-linker-inputs/host-request-1.bee-pre.json")), "off request wrote pre receipt");
                Console.WriteLine("active explicitly disabled request returned without capture");
                return 0;
            }
            if (mode != "roundtrip" && mode != "post-unknown" && mode != "post-guid-mismatch" && mode != "post-errors" && mode != "post-target")
                throw new Exception("unknown host mode");
            Fixture(scratch, project, work, true);
            UnityEditor.SessionState.request = "host-request-1";
            string guid = "0123456789abcdef0123456789abcdef";
            capture.OnPreprocessBuild(Report(guid, BuildResult.Unknown, output));
            Check(File.Exists(Path.Combine(work, "lab-build/player-linker-inputs/host-request-1.bee-pre.json")), "opted-in pre receipt missing");
            if (mode != "roundtrip")
            {
                BuildReport rejected = mode == "post-unknown" ? Report(guid, BuildResult.Unknown, output) :
                    mode == "post-guid-mismatch" ? Report("fedcba9876543210fedcba9876543210", BuildResult.Succeeded, output) :
                    Report(guid, BuildResult.Succeeded, output);
                BuildSummary summary = rejected.summary;
                if (mode == "post-errors") summary.totalErrors = 2;
                if (mode == "post-target") summary.platform = BuildTarget.StandaloneOSX;
                rejected.summary = summary;
                capture.OnPostprocessBuild(rejected);
                Check(!File.Exists(Path.Combine(work, "lab-build/player-linker-inputs/host-request-1.bee-post.json")), "mismatched BuildReport wrote a postprocess receipt");
                Console.WriteLine("REJECTED=" + mode);
                return 0;
            }
            string logSlice = "Starting: /Unity/bee_backend --profile=\"Library/Bee/backend_profiler0.traceevents\" --stdin-canary --dagfile=\"Library/Bee/Player123.dag\" --continue-on-failure Player\n" +
                "WorkingDir: " + project + "\nExitCode: 0 Duration: 0s476ms\n";
            File.AppendAllText(Path.Combine(work, "Editor.log"), logSlice);
            File.WriteAllBytes(output, new byte[] { 1, 2, 3, 4 });
            capture.OnPostprocessBuild(Report(guid, BuildResult.Succeeded, output));
            Check(File.Exists(Path.Combine(work, "lab-build/player-linker-inputs/host-request-1.bee-post.json")), "opted-in post receipt missing");
            Console.WriteLine("PROJECT=" + project);
            Console.WriteLine("WORK=" + work);
            Console.WriteLine("APK=" + output);
            Console.WriteLine("GUID=" + guid);
            Console.WriteLine("C# receipt bridge produced pre/post JSON");
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}
