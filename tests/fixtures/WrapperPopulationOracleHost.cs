using System;
using System.Collections.Generic;
using System.Linq;
namespace UnityEngine
{
    public class Object { }
    public static class Application {public static string unityVersion = "fixture";}
    public static class JsonUtility {public static string ToJson(object value, bool pretty) {throw new Exception("Not an SDK batch");}}
    public static class Debug {public static void Log(object value) {}}
}
namespace PopulationFixture
{
    [Flags] public enum Flags {None = 0, Abstract = 1}
    public sealed class Node
    {
        public string name {get; set;}
        public string nativeNamespace {get {return "";}}
        public string module {get {return "Authored";}}
        public string qualifiedName {get {return name;}}
        public int persistentTypeID {get; set;}
        public Flags flags {get; set;}
        public Node baseClass {get; set;}
        public static Node[] Values;
        public static uint TypeCount {get {return (uint)Values.Length;}}
        public static IEnumerable<Node> GetTypes() {return Values;}
    }
    public static class Queries
    {
        public static List<int> Calls = new List<int>();
        public static string ScriptingWrapperTypeNameForNativeID(int id)
        {
            Calls.Add(id);
            if (id == 201) return "Authored.Concrete";
            if (id == 202) return "Authored.Abstract";
            throw new Exception("Unsafe native ID queried");
        }
    }
}
public static class PopulationHost
{
    public static int Main()
    {
        var root = new PopulationFixture.Node {name = "Object", persistentTypeID = 200};
        var concrete = new PopulationFixture.Node {name = "Concrete", persistentTypeID = 201, baseClass = root};
        var abstractType = new PopulationFixture.Node {name = "Abstract", persistentTypeID = 202, baseClass = root, flags = PopulationFixture.Flags.Abstract};
        var outside = new PopulationFixture.Node {name = "Outside", persistentTypeID = 203};
        PopulationFixture.Node.Values = new[] {root, concrete, abstractType, outside};
        var rows = WrapperPopulationOracle.Collect(typeof(PopulationFixture.Node), typeof(PopulationFixture.Queries));
        if (!PopulationFixture.Queries.Calls.SequenceEqual(new[] {201, 202})
            || rows.Count(r => r.wrapperQueried) != 2 || rows.Single(r => r.persistentTypeID == 202).skipReason != "")
            throw new Exception("Population coverage differs");
        PopulationFixture.Queries.Calls.Clear();
        abstractType.baseClass = abstractType;
        try {WrapperPopulationOracle.Collect(typeof(PopulationFixture.Node), typeof(PopulationFixture.Queries)); throw new Exception("Cycle accepted");}
        catch (InvalidOperationException) {}
        if (PopulationFixture.Queries.Calls.Count != 0) throw new Exception("Cycle queried before refusal");
        Console.WriteLine("PASS: abstract, exclusions and graph-before-query");
        return 0;
    }
}
