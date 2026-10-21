using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;

// Independently authored API substitutes, not Unity registry data.
namespace UnityEngine
{
    public class Object { }
    public static class Application { public static string unityVersion = "fixture"; }
    public static class JsonUtility { public static string ToJson(object value, bool pretty) { throw new Exception("Not an editor oracle"); } }
    public static class Debug { public static void Log(object value) { } }
}
namespace UnityEditor
{
    [Flags] public enum TestFlags { None = 0, Abstract = 1 }
    public sealed class UnityType
    {
        public string name { get; set; }
        public string nativeNamespace { get { return ""; } }
        public string module { get { return "Authored"; } }
        public int persistentTypeID { get; set; }
        public UnityType baseClass { get; set; }
        public TestFlags flags { get; set; }
        public string qualifiedName { get { return name; } }
        public static List<UnityType> Values = new List<UnityType>();
        public static uint TypeCount { get { return (uint)Values.Count; } }
        public static IEnumerable<UnityType> GetTypes() { return Values; }
    }
    public static class RuntimeClassMetadataUtils
    {
        public static List<int> Calls = new List<int>();
        public static string ScriptingWrapperTypeNameForNativeID(int id)
        {
            Calls.Add(id);
            if (id == 11) return "Authored.Concrete";
            if (id == 13) return "Authored.AncestorWrapper";
            if (id == 16) return null;
            throw new Exception("Unsupported native query executed");
        }
    }
}
public static class OracleHost
{
    static void Check(bool value) { if (!value) throw new Exception("Fixture assertion failed"); }
    static void Refuses(Action action)
    {
        bool refused = false;
        try { action(); } catch (InvalidOperationException) { refused = true; }
        Check(refused);
        Check(UnityEditor.RuntimeClassMetadataUtils.Calls.Count == 0);
    }
    static UnityEditor.UnityType Node(int id, string name, UnityEditor.UnityType parent = null, bool abstractType = false)
    {
        return new UnityEditor.UnityType { persistentTypeID = id, name = name, baseClass = parent,
            flags = abstractType ? UnityEditor.TestFlags.Abstract : UnityEditor.TestFlags.None };
    }
    static List<UnityEditor.UnityType> Reset()
    {
        var root = Node(10, "Object");
        var abstractType = Node(12, "AuthoredAbstract", root, true);
        var otherRoot = Node(14, "OtherRoot");
        UnityEditor.RuntimeClassMetadataUtils.Calls.Clear();
        UnityEditor.UnityType.Values = new List<UnityEditor.UnityType> {
            root, Node(11, "AuthoredConcrete", root), abstractType, Node(13, "AuthoredLeaf", abstractType),
            otherRoot, Node(15, "OtherLeaf", otherRoot), Node(16, "NoWrapper", root)
        };
        return UnityEditor.UnityType.Values;
    }
    static WrapperMetadataOracle.Row[] Collect()
    {
        return WrapperMetadataOracle.Collect(typeof(UnityEditor.UnityType), typeof(UnityEditor.RuntimeClassMetadataUtils));
    }
    static Assembly Api(string assemblyName)
    {
        var assembly = AppDomain.CurrentDomain.DefineDynamicAssembly(new AssemblyName(assemblyName), AssemblyBuilderAccess.Run);
        assembly.DefineDynamicModule(assemblyName).DefineType("Authored.ConflictApi", TypeAttributes.Public).CreateType();
        return assembly;
    }
    public static int Main()
    {
        Reset();
        var rows = Collect();
        Check(rows.Length == 7 && rows.Count(r => r.wrapperQueried) == 3);
        Check(UnityEditor.RuntimeClassMetadataUtils.Calls.SequenceEqual(new[] { 11, 13, 16 }));
        Check(rows.Single(r => r.persistentTypeID == 10).skipReason == "native-object-root");
        Check(rows.Single(r => r.persistentTypeID == 12).skipReason == "abstract");
        Check(rows.Single(r => r.persistentTypeID == 15).skipReason == "outside-object-hierarchy");
        var missing = rows.Single(r => r.persistentTypeID == 16);
        Check(missing.wrapperQueried && missing.wrapperReturnedNull && missing.wrapperName == "");
        Check(rows.Single(r => r.persistentTypeID == 13).parentID == 12);
        var values = Reset(); values[2].baseClass = values[3]; Refuses(() => Collect());
        values = Reset(); values[1].baseClass = Node(99, "Foreign"); Refuses(() => Collect());
        values = Reset(); values[1].persistentTypeID = 10; Refuses(() => Collect());
        values = Reset(); values[1].name = "AuthoredLeaf"; Refuses(() => Collect());
        values = Reset(); values.Add(values[1]); Refuses(() => Collect());
        values = Reset(); values[0].name = "NotObject"; Refuses(() => Collect());
        var own = typeof(UnityEditor.UnityType).Assembly;
        Check(WrapperMetadataOracle.UniqueType(new[] { own, own }, "UnityEditor.UnityType") == typeof(UnityEditor.UnityType));
        Refuses(() => WrapperMetadataOracle.UniqueType(new[] { own }, "Authored.Missing"));
        Refuses(() => WrapperMetadataOracle.UniqueType(new[] { Api("One"), Api("Two") }, "Authored.ConflictApi"));
        Console.WriteLine("PASS: scope, null result, full graph validation, identity and API ambiguity contracts");
        return 0;
    }
}
