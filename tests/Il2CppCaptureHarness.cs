using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class CaptureHarness
{
    static void Check(bool value, string reason) { if (!value) throw new Exception(reason); }
    static BuildReport Report(string guid, BuildResult result = BuildResult.Unknown)
    {
        return new BuildReport { summary = new BuildSummary { guid = new GUID { value = guid }, platform = BuildTarget.Android, outputPath = "fixture.apk", result = result } };
    }
    static string Arg(string[] args, string flag)
    {
        int i = Array.IndexOf(args, flag);
        return i < 0 || i + 1 >= args.Length ? null : args[i + 1];
    }
    public static int Main(string[] args)
    {
        string mode = args.Length == 0 ? "default-off" : args[0];
        string workArg = Arg(args, "-labWorkRoot");
        string tempRoot = Environment.GetEnvironmentVariable("LAB_HOST_TEMP_ROOT") ?? Path.GetTempPath();
        string scratch = Path.Combine(tempRoot, "il2cpp-capture-host-" + Guid.NewGuid().ToString("N"));
        string project = Path.Combine(scratch, "unity-project");
        string work = Path.GetFullPath(Path.Combine(project, ".."));
        if (workArg != null)
        {
            work = Path.GetFullPath(workArg);
            DirectoryInfo parent = Directory.GetParent(work);
            parent = parent == null ? null : parent.Parent;
            parent = parent == null ? null : parent.Parent;
            project = parent == null ? null : parent.FullName;
            if (project == null) throw new Exception("invalid fixture work-root layout");
            scratch = Directory.GetParent(project).FullName;
        }
        Application.dataPath = Path.Combine(project, "Assets");
        Directory.CreateDirectory(Application.dataPath);
        EditorApplication.timeSinceStartup = 100;
        try
        {
            var capture = new Il2CppInvocationCapture();
            if (mode == "default-off")
            {
                capture.OnPreprocessBuild(Report("guid-default"));
                Check(Application.Subscribers == 0, "ordinary build subscribed to Unity logs");
                Check(!File.Exists(Path.Combine(work, "build-request.json")), "ordinary build read or created a request file");
                Console.WriteLine("ordinary-build early-return host contract passed");
                return 0;
            }
            if (mode == "explicit-off")
            {
                Directory.CreateDirectory(work);
                File.WriteAllText(Path.Combine(work, "build-request.json"), "{\"request_id\":\"host-request-1\",\"captureIl2CppInvocation\":false}");
                SessionState.request = "host-request-1";
                capture.OnPreprocessBuild(Report("guid-off"));
                Check(Application.Subscribers == 0, "explicitly disabled request subscribed to Unity logs");
                Check(!Directory.Exists(Path.Combine(work, "lab-build")), "explicitly disabled request wrote capture output");
                Console.WriteLine("explicit-off host contract passed");
                return 0;
            }
            Directory.CreateDirectory(work);
            Directory.CreateDirectory(Path.Combine(work, "inventory"));
            string id = mode == "wrong-active" ? "different-active-request" : "host-request-1";
            File.WriteAllText(Path.Combine(project, ".port-input.json"), "{\"input_id\":\"" + new string('b', 64) + "\"}");
            File.WriteAllText(Path.Combine(work, "inventory", "files.json"), "{\"input_id\":\"" + new string('b', 64) + "\"}");
            File.WriteAllText(Path.Combine(work, "build-request.json"), "{\"request_id\":\"" + id + "\",\"captureIl2CppInvocation\":true,\"sourceCommit\":\"" + new string('a', 40) + "\",\"inputId\":\"" + new string('b', 64) + "\"}");
            SessionState.request = mode == "wrong-active" ? "host-request-1" : id;
            if (mode == "wrong-active")
            {
                bool refused = false;
                try { capture.OnPreprocessBuild(Report("guid-wrong-active")); }
                catch (InvalidOperationException) { refused = true; }
                Check(refused, "opted-in request with wrong active identity was accepted");
                Check(Application.Subscribers == 0, "wrong active identity installed callback");
                Console.WriteLine("wrong-active-request refusal host contract passed");
                return 0;
            }
            string input = Path.Combine(project, "Temp", "StagingArea", "Data", "Managed");
            Directory.CreateDirectory(input);
            File.WriteAllBytes(Path.Combine(input, "Game.dll"), new byte[] { 1, 2, 3, 4 });
            string guid = "abcdef0123456789abcdef0123456789";
            BuildPipeline.isBuildingPlayer = true;
            capture.OnPreprocessBuild(Report(guid));
            Check(Application.Subscribers == 1, "opted-in request did not subscribe");

            if (mode == "cancel")
            {
                BuildPipeline.isBuildingPlayer = false;
                EditorApplication.timeSinceStartup += 6;
                EditorApplication.Tick();
                Check(Application.Subscribers == 0, "cancel path leaked log listener");
                Check(File.Exists(Path.Combine(work, "lab-build", "player-linker-inputs", id + ".il2cpp-incomplete.json")), "cancel path omitted failure witness");
                Check(!File.Exists(Path.Combine(work, "lab-build", "player-linker-inputs", id + ".il2cpp.json")), "cancel path emitted complete receipt");
                Console.WriteLine("cancel cleanup host contract passed");
                return 0;
            }

            Application.Emit("Invoking il2cpp with arguments: --convert-in-graph --directory=" + input);
            if (mode == "duplicate-directory")
            {
                Application.Emit("Invoking il2cpp with arguments: --directory=" + input + " --directory=" + input);
                BuildPipeline.isBuildingPlayer = false;
                capture.OnPostprocessBuild(Report(guid, BuildResult.Unknown));
                Check(Application.Subscribers == 0, "malformed invocation leaked log listener");
                Check(File.Exists(Path.Combine(work, "lab-build", "player-linker-inputs", id + ".il2cpp-incomplete.json")), "duplicate --directory omitted failure witness");
                Check(!File.Exists(Path.Combine(work, "lab-build", "player-linker-inputs", id + ".il2cpp.json")), "duplicate --directory emitted complete receipt");
                Console.WriteLine("duplicate-directory refusal host contract passed");
                return 0;
            }
            string snapshot = Path.Combine(work, "lab-build", "player-linker-inputs", id, "poststrip", "Game.dll");
            Check(File.Exists(snapshot), "snapshot was not written under distinct work root");
            Check(File.ReadAllBytes(snapshot).SequenceEqual(new byte[] { 1, 2, 3, 4 }), "snapshot bytes differ");
            Check(!Directory.Exists(Path.Combine(project, "lab-build")), "snapshot incorrectly used project as work root");
            BuildPipeline.isBuildingPlayer = false;
            capture.OnPostprocessBuild(Report(guid, BuildResult.Unknown));
            Check(Application.Subscribers == 0, "postprocess leaked log listener");
            string receipt = File.ReadAllText(Path.Combine(work, "lab-build", "player-linker-inputs", id + ".il2cpp.json"));
            Check(receipt.Contains("Temp/ StagingArea") == false, "unexpected path rewrite");
            Check(receipt.Contains("Temp/StagingArea/Data/Managed"), "receipt did not record project-relative input");
            Check(receipt.Contains(guid), "receipt omitted BuildReport GUID");
            Check(receipt.Contains("Unknown"), "probe incorrectly assumed callback result already succeeded");
            Console.WriteLine("distinct project/work-root host contract passed");
            return 0;
        }
        finally { try { Directory.Delete(scratch, true); } catch { } }
    }
}
