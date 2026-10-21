using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using UnityEngine;

// Independent SDK-only desktop verification. Never queries the native root or
// outside-hierarchy IDs, and never supplies data to a phone build.
public static class WrapperPopulationOracle
{
    const BindingFlags Static = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    [Serializable] public sealed class Report
    {
        public int schema = 1;
        public string unity, source_commit;
        public string queryProfile = "all-object-descendants-v1";
        public bool game_inputs = false, cache_population_qualified = false, root_generation_qualified = false;
        public WrapperMetadataOracle.Row[] records;
        public WrapperMetadataOracle.AssemblyInput[] assemblies;
        public string[] reverseApiCandidates;
    }
    static WrapperMetadataOracle.AssemblyInput Input(Assembly assembly)
    {
        var path = Path.GetFullPath(assembly.Location);
        using (var hash = SHA256.Create()) using (var stream = File.OpenRead(path))
            return new WrapperMetadataOracle.AssemblyInput {identity = assembly.FullName, path = path,
                sha256 = BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant()};
    }
    public static WrapperMetadataOracle.Row[] Collect(Type native, Type wrapper)
    {
        // The existing collector checks the entire identity/parent graph before
        // its established concrete queries. Preserve its results and exclusions.
        var rows = WrapperMetadataOracle.Collect(native, wrapper);
        var query = wrapper.GetMethod("ScriptingWrapperTypeNameForNativeID", Static, null, new[] {typeof(int)}, null);
        if (query == null || query.ReturnType != typeof(string)) throw new InvalidOperationException("Wrapper query API differs");
        foreach (var row in rows.Where(r => r.skipReason == "abstract"))
        {
            if (!row.hasParent || (row.flags & 1) == 0 || row.wrapperQueried)
                throw new InvalidOperationException("Abstract query precondition differs");
            var value = (string)query.Invoke(null, new object[] {row.persistentTypeID});
            row.wrapperName = value ?? "";
            row.wrapperReturnedNull = value == null;
            row.wrapperQueried = true;
            row.skipReason = "";
        }
        return rows;
    }
    public static void Check()
    {
        if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException("Exact SDK required");
        var output = Environment.GetEnvironmentVariable("ROR2_POPULATION_ORACLE_REPORT");
        var commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE");
        if (String.IsNullOrEmpty(output) || !Path.IsPathRooted(output) || File.Exists(output)
            || commit == null || !System.Text.RegularExpressions.Regex.IsMatch(commit, "^[0-9a-f]{40}$"))
            throw new InvalidOperationException("Explicit new output/source required");
        var loaded = AppDomain.CurrentDomain.GetAssemblies();
        var native = WrapperMetadataOracle.UniqueType(loaded, "UnityEditor.UnityType");
        var wrapper = WrapperMetadataOracle.UniqueType(loaded, "UnityEditor.RuntimeClassMetadataUtils");
        var report = new Report {unity = Application.unityVersion, source_commit = commit, records = Collect(native, wrapper),
            assemblies = new[] {native.Assembly, wrapper.Assembly, typeof(UnityEngine.Object).Assembly}.Distinct().Select(Input).ToArray()};
        // Reflection-only discovery. Candidate methods are never invoked here.
        report.reverseApiCandidates = new[] {native.Assembly, typeof(UnityEngine.Object).Assembly}.Distinct()
            .SelectMany(a => a.GetTypes()).SelectMany(t => t.GetMethods(Static))
            .Where(m => (m.Name.IndexOf("Class", StringComparison.OrdinalIgnoreCase) >= 0
                      || m.Name.IndexOf("NativeType", StringComparison.OrdinalIgnoreCase) >= 0)
                     && m.GetParameters().Any(p => p.ParameterType == typeof(Type)))
            .Select(m => m.DeclaringType.FullName + "." + m).Distinct().OrderBy(s => s, StringComparer.Ordinal).ToArray();
        using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
        using (var writer = new StreamWriter(stream)) writer.WriteLine(JsonUtility.ToJson(report, true));
        Debug.Log("Population oracle completed: " + report.records.Count(r => r.wrapperQueried) + " queries");
    }
}
