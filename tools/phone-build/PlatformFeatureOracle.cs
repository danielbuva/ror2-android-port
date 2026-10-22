using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

// Exact-SDK verification only. Never a phone-generation or game-build input.
public static class PlatformFeatureOracle
{
    [Serializable] public sealed class Request { public int schema; public string[] features; }
    [Serializable] public sealed class Row { public string feature; public bool supported; }
    [Serializable] public sealed class FileRow { public string path, sha256; }
    [Serializable] public sealed class Report
    {
        public int schema = 1, target_value;
        public string profile = "android-feature-api-oracle-v1", unity, source_commit, phase, failure, target, platform_define;
        public bool success, game_inputs, player_built, phone_generation_input, root_generation_qualified;
        public string query_sha256;
        public FileRow api_assembly, collector_assembly;
        public Row[] rows;
    }
    static string Sha(string path)
    {
        using (var hash = SHA256.Create())
        using (var input = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
    }
    static FileRow AssemblyFile(Assembly value)
    {
        return new FileRow { path = Path.GetFullPath(value.Location), sha256 = Sha(value.Location) };
    }
    public static void Check()
    {
        string attempt = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        string output = Environment.GetEnvironmentVariable("ROR2_FEATURE_ORACLE_REPORT");
        string query = Environment.GetEnvironmentVariable("ROR2_FEATURE_ORACLE_QUERIES");
        if (!Application.isBatchMode || Application.unityVersion != "2021.3.45f2" || EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android
            || String.IsNullOrEmpty(output) || Path.GetFullPath(output) != Path.Combine(attempt, "oracle.json") || File.Exists(output)
            || String.IsNullOrEmpty(query) || Path.GetFullPath(query) != Path.Combine(attempt, "queries.json"))
            throw new InvalidOperationException("Fresh exact Android SDK query attempt required");
        var report = new Report { unity = Application.unityVersion, source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"), phase = "request" };
        var rows = new List<Row>();
        try
        {
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(query));
            if (request == null || request.schema != 1 || request.features == null || request.features.Length == 0 || request.features.Length > 256
                || request.features.Any(v => v == null || v.Length > 128 || !Regex.IsMatch(v, "^[A-Z_][A-Z0-9_]*$"))
                || request.features.Distinct(StringComparer.Ordinal).Count() != request.features.Length)
                throw new InvalidOperationException("Unknown feature query request");
            report.query_sha256 = Sha(query);
            report.target = BuildTarget.Android.ToString();
            report.target_value = (int)BuildTarget.Android;
            report.api_assembly = AssemblyFile(typeof(BuildPipeline).Assembly);
            report.collector_assembly = AssemblyFile(typeof(PlatformFeatureOracle).Assembly);
            report.phase = "target-discovery-observation";
            Type discovery = typeof(BuildPipeline).Assembly.GetType("UnityEditor.BuildTargetDiscovery", true);
            MethodInfo targets = discovery.GetMethod("GetBuildTargetInfoList", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static, null, Type.EmptyTypes, null);
            if (targets == null) throw new InvalidOperationException("Missing SDK target discovery API");
            int found = 0;
            foreach (object item in (Array)targets.Invoke(null, null))
            {
                Type type = item.GetType();
                var target = (BuildTarget)type.GetField("buildTargetPlatformVal").GetValue(item);
                if (target != BuildTarget.Android) continue;
                report.platform_define = (string)type.GetField("platformDefine").GetValue(item);
                ++found;
            }
            if (found != 1 || String.IsNullOrEmpty(report.platform_define)) throw new InvalidOperationException("Ambiguous SDK Android discovery observation");
            report.phase = "native-feature-api";
            MethodInfo feature = typeof(BuildPipeline).GetMethod("IsFeatureSupported", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static, null, new[] { typeof(string), typeof(BuildTarget) }, null);
            if (feature == null || feature.ReturnType != typeof(bool)) throw new InvalidOperationException("Missing exact SDK feature API");
            foreach (string name in request.features)
                rows.Add(new Row { feature = name, supported = (bool)feature.Invoke(null, new object[] { name, BuildTarget.Android }) });
            report.phase = "complete";
            report.success = true;
        }
        catch (Exception error) { report.failure = error.GetBaseException().Message; report.success = false; }
        finally
        {
            report.rows = rows.ToArray();
            using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
                writer.Write(JsonUtility.ToJson(report, true) + "\n");
        }
        if (!report.success) throw new InvalidOperationException("Feature oracle failed; inspect private report");
    }
}
