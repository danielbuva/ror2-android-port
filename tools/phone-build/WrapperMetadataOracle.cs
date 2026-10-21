using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using UnityEngine;

// Desktop verification only. No player, game project or phone-build consumer.
public static class WrapperMetadataOracle
{
    [Serializable] public sealed class Row
    {
        public int persistentTypeID;
        public string name, nativeNamespace, module, qualifiedName;
        public bool hasParent;
        public int parentID, flags;
        public bool wrapperQueried, wrapperReturnedNull;
        public string wrapperName, skipReason;
    }
    [Serializable] public sealed class AssemblyInput
    {
        public string identity, path, sha256;
    }
    [Serializable] public sealed class Report
    {
        public int schema = 1;
        public string unity, source_commit;
        public bool root_generation_qualified = false;
        public bool game_inputs = false;
        public string queryProfile = "concrete-object-descendants-v1";
        public AssemblyInput[] assemblies;
        public Row[] records;
    }
    const BindingFlags Static = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

    public static Type UniqueType(IEnumerable<Assembly> assemblies, string name)
    {
        var matches = assemblies.Select(a => a.GetType(name, false)).Where(t => t != null).Distinct().ToArray();
        if (matches.Length != 1) throw new InvalidOperationException("Missing or ambiguous SDK API type: " + name);
        return matches[0];
    }
    static object Property(Type type, object node, string name, Type expected)
    {
        var property = type.GetProperty(name, Instance);
        if (property == null || property.PropertyType != expected || property.GetIndexParameters().Length != 0
            || property.GetGetMethod(true) == null || property.GetGetMethod(true).IsStatic)
            throw new InvalidOperationException("SDK API property differs: " + name);
        return property.GetValue(node, null);
    }
    static MethodInfo Method(Type type, string name, Type[] arguments)
    {
        var method = type.GetMethod(name, Static, null, arguments, null);
        if (method == null || method.IsGenericMethod) throw new InvalidOperationException("SDK API method differs: " + name);
        return method;
    }
    public static Row[] Collect(Type nativeType, Type wrapperType)
    {
        var get = Method(nativeType, "GetTypes", Type.EmptyTypes);
        if (!typeof(IEnumerable).IsAssignableFrom(get.ReturnType)) throw new InvalidOperationException("SDK registry is not enumerable");
        var all = ((IEnumerable)get.Invoke(null, null)).Cast<object>().ToArray();
        var count = nativeType.GetProperty("TypeCount", Static);
        if (count == null || count.PropertyType != typeof(uint) || (uint)count.GetValue(null, null) != all.Length || all.Length == 0)
            throw new InvalidOperationException("SDK registry count differs");
        if (all.Any(n => n == null || n.GetType() != nativeType) || all.Distinct().Count() != all.Length)
            throw new InvalidOperationException("SDK registry contains foreign or repeated objects");
        var flags = nativeType.GetProperty("flags", Instance);
        if (flags == null || !flags.PropertyType.IsEnum) throw new InvalidOperationException("SDK flags are not an enum");
        var rows = new Dictionary<object, Row>();
        var parents = new Dictionary<object, object>();
        foreach (var node in all)
        {
            var row = new Row {
                persistentTypeID = (int)Property(nativeType, node, "persistentTypeID", typeof(int)),
                name = (string)Property(nativeType, node, "name", typeof(string)),
                nativeNamespace = (string)Property(nativeType, node, "nativeNamespace", typeof(string)),
                module = (string)Property(nativeType, node, "module", typeof(string)),
                qualifiedName = (string)Property(nativeType, node, "qualifiedName", typeof(string)),
                flags = Convert.ToInt32(Property(nativeType, node, "flags", flags.PropertyType)),
                wrapperName = "", skipReason = ""
            };
            if (String.IsNullOrEmpty(row.name) || row.nativeNamespace == null || String.IsNullOrEmpty(row.module)
                || row.qualifiedName != (row.nativeNamespace.Length == 0 ? "" : row.nativeNamespace + "::") + row.name)
                throw new InvalidOperationException("Incomplete SDK identity");
            parents.Add(node, Property(nativeType, node, "baseClass", nativeType));
            rows.Add(node, row);
        }
        if (rows.Values.Select(r => r.persistentTypeID).Distinct().Count() != rows.Count
            || rows.Values.Select(r => r.qualifiedName).Distinct().Count() != rows.Count)
            throw new InvalidOperationException("Duplicate SDK identity or ID");
        foreach (var node in all)
        {
            var seen = new HashSet<object>();
            for (var current = node; current != null; current = parents[current])
                if (!rows.ContainsKey(current) || !seen.Add(current)) throw new InvalidOperationException("Foreign parent or cycle");
            var parent = parents[node];
            rows[node].hasParent = parent != null;
            if (parent != null) rows[node].parentID = rows[parent].persistentTypeID;
        }
        var roots = all.Where(n => parents[n] == null && rows[n].name == "Object" && rows[n].nativeNamespace == "").ToArray();
        if (roots.Length != 1) throw new InvalidOperationException("Ambiguous native Object root");
        var root = roots[0];
        var query = Method(wrapperType, "ScriptingWrapperTypeNameForNativeID", new[] { typeof(int) });
        if (query.ReturnType != typeof(string)) throw new InvalidOperationException("SDK wrapper return type differs");
        // Validate the complete graph before making any native wrapper query.
        foreach (var node in all)
        {
            var row = rows[node];
            var ancestor = parents[node];
            while (ancestor != null && !System.Object.ReferenceEquals(ancestor, root)) ancestor = parents[ancestor];
            if (System.Object.ReferenceEquals(node, root)) row.skipReason = "native-object-root";
            else if (ancestor == null) row.skipReason = "outside-object-hierarchy";
            else if ((row.flags & 1) != 0) row.skipReason = "abstract";
            else
            {
                var value = (string)query.Invoke(null, new object[] { row.persistentTypeID });
                row.wrapperReturnedNull = value == null;
                row.wrapperName = value ?? "";
                row.wrapperQueried = true;
            }
        }
        return rows.Values.OrderBy(r => r.persistentTypeID).ToArray();
    }
    static AssemblyInput Input(Assembly assembly)
    {
        var path = Path.GetFullPath(assembly.Location);
        using (var hash = SHA256.Create()) using (var stream = File.OpenRead(path))
            return new AssemblyInput { identity = assembly.FullName, path = path,
                sha256 = BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant() };
    }
    public static void Check()
    {
        if (Application.unityVersion != "2021.3.45f2") throw new InvalidOperationException("Exact editor required");
        var output = Environment.GetEnvironmentVariable("ROR2_WRAPPER_ORACLE_REPORT");
        var commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE");
        if (String.IsNullOrEmpty(output) || !Path.IsPathRooted(output) || File.Exists(output)
            || commit == null || !System.Text.RegularExpressions.Regex.IsMatch(commit, "^[0-9a-f]{40}$"))
            throw new InvalidOperationException("Explicit new output and source commit required");
        var loaded = AppDomain.CurrentDomain.GetAssemblies();
        var native = UniqueType(loaded, "UnityEditor.UnityType");
        var wrapper = UniqueType(loaded, "UnityEditor.RuntimeClassMetadataUtils");
        var report = new Report { unity = Application.unityVersion, source_commit = commit,
            records = Collect(native, wrapper), assemblies = new[] { native.Assembly, wrapper.Assembly }.Distinct().Select(Input).ToArray() };
        using (var file = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
        using (var writer = new StreamWriter(file)) writer.WriteLine(JsonUtility.ToJson(report, true));
        Debug.Log("Wrapper metadata oracle completed: " + report.records.Length + " native metadata records");
    }
}
