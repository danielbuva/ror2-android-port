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

// SDK verification only. No player, game source, scene or phone-generation input.
public static class TargetKeyOracle
{
    [Serializable] public sealed class Request { public int schema; public int[] keys; public string[] names; }
    [Serializable] public sealed class KeyRow { public int key; public string value, error; }
    [Serializable] public sealed class NameRow { public string name; public int value; public bool returned; public string error; }
    [Serializable] public sealed class FileRow { public string path, sha256; }
    [Serializable] public sealed class Report
    {
        public int schema = 1;
        public string profile = "target-key-api-observations-v1", unity, source_commit, phase, failure, request_sha256;
        public bool success, game_inputs, player_built, phone_generation_input, root_generation_qualified;
        public FileRow api_assembly, collector_assembly;
        public KeyRow[] keys;
        public NameRow[] names;
    }
    static string Sha(string path)
    {
        using (var hash = SHA256.Create())
        using (var input = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
    }
    static FileRow AssemblyFile(Assembly assembly)
    {
        return new FileRow { path = Path.GetFullPath(assembly.Location), sha256 = Sha(assembly.Location) };
    }
    public static void Check()
    {
        string attempt = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));
        string output = Environment.GetEnvironmentVariable("ROR2_TARGET_KEY_REPORT");
        string query = Environment.GetEnvironmentVariable("ROR2_TARGET_KEY_REQUEST");
        if (!Application.isBatchMode || Application.unityVersion != "2021.3.45f2" || EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android
            || String.IsNullOrEmpty(output) || Path.GetFullPath(output) != Path.Combine(attempt, "oracle.json") || File.Exists(output)
            || String.IsNullOrEmpty(query) || Path.GetFullPath(query) != Path.Combine(attempt, "queries.json"))
            throw new InvalidOperationException("Fresh exact-SDK query project required");
        var report = new Report { unity = Application.unityVersion, source_commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE"), phase = "request" };
        var keys = new List<KeyRow>();
        var names = new List<NameRow>();
        try
        {
            var request = JsonUtility.FromJson<Request>(File.ReadAllText(query));
            if (request == null || request.schema != 1 || request.keys == null || request.names == null
                || request.keys.Length == 0 || request.keys.Length > 256 || request.names.Length == 0 || request.names.Length > 256
                || request.keys.Any(value => value < -1000000 || value > 1000000) || request.keys.Distinct().Count() != request.keys.Length
                || request.names.Any(value => value == null || value.Length > 128 || !Regex.IsMatch(value, "^[A-Za-z_][A-Za-z0-9_.-]*$"))
                || request.names.Distinct(StringComparer.Ordinal).Count() != request.names.Length)
                throw new InvalidOperationException("Unknown target-key query request");
            report.request_sha256 = Sha(query);
            report.api_assembly = AssemblyFile(typeof(BuildPipeline).Assembly);
            report.collector_assembly = AssemblyFile(typeof(TargetKeyOracle).Assembly);
            MethodInfo reverse = typeof(BuildPipeline).GetMethod("GetBuildTargetByName", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static, null, new[] { typeof(string) }, null);
            if (reverse == null || reverse.ReturnType != typeof(BuildTarget)) throw new InvalidOperationException("Missing exact reverse-name SDK API");
            report.phase = "key-observations";
            foreach (int key in request.keys)
            {
                var row = new KeyRow { key = key };
                try { row.value = BuildPipeline.GetBuildTargetName((BuildTarget)key); }
                catch (Exception error) { row.error = error.GetBaseException().Message; }
                keys.Add(row);
            }
            report.phase = "name-observations";
            foreach (string name in request.names)
            {
                var row = new NameRow { name = name };
                try { row.value = (int)(BuildTarget)reverse.Invoke(null, new object[] { name }); row.returned = true; }
                catch (Exception error) { row.error = error.GetBaseException().Message; }
                names.Add(row);
            }
            report.phase = "complete";
            report.success = true;
        }
        catch (Exception error) { report.failure = error.GetBaseException().Message; report.success = false; }
        finally
        {
            report.keys = keys.ToArray(); report.names = names.ToArray();
            using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
            using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
                writer.Write(JsonUtility.ToJson(report, true) + "\n");
        }
        if (!report.success) throw new InvalidOperationException("Target-key oracle failed; inspect private report");
    }
}
