using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using RoR2;

namespace RoR2
{
    public enum ArtifactIndex { First }
    public class ArtifactDef { }
    public class ItemDef { }
    public class EquipmentDef { }
    public class GameObject { }
    public static class ArtifactCatalog
    {
        public static ArtifactDef[] values = { new ArtifactDef() };
        public static int artifactCount => values.Length;
        public static ArtifactDef GetArtifactDef(ArtifactIndex index) => values[(int)index];
    }
    public static class ItemCatalog { public static ItemDef[] allItemDefs = { new ItemDef() }; }
    public static class EquipmentCatalog
    {
        public static int[] allEquipment = { 0 };
        public static EquipmentDef value = new EquipmentDef();
        public static EquipmentDef GetEquipmentDef(int index) => value;
    }
    public static class BodyCatalog { public static GameObject[] allBodyPrefabs = { new GameObject() }; }
    public static class RunArtifactManager { }
}
namespace RoR2.ContentManagement
{
    public static class AddressablesLabels { public const string artifactDef = "ArtifactDef"; }
}
public static class WholeCatalogComposed
{
    public static readonly List<string> events = new List<string>();
    public static readonly ArtifactDef[] artifacts = { ArtifactCatalog.values[0], new ArtifactDef() };
    static JObject snapshot;
    public static JObject ReadDefinitionManifest()
    {
        if (snapshot != null) throw new Exception("Duplicate source read");
        events.Add("read");
        return snapshot = new JObject();
    }
    public static ArtifactDef[] CategoryFamily(JObject manifest, string category, IEnumerable<ArtifactDef> selected)
    {
        Check(ReferenceEquals(manifest, snapshot) && category == "ArtifactDef");
        Check(selected.SequenceEqual(ArtifactCatalog.values));
        events.Add("family");
        return artifacts;
    }
    public static void PopulateDefinitionFields<T>(JObject manifest, string family, T[] values)
    {
        Check(ReferenceEquals(manifest, snapshot));
        if (family == "Artifacts") Check(ReferenceEquals(values, artifacts));
        else if (family == "Items") Check(values.Cast<ItemDef>().SequenceEqual(ItemCatalog.allItemDefs));
        else if (family == "Equipment") Check(ReferenceEquals(values.Single(), EquipmentCatalog.value));
        else throw new Exception("Unexpected holder");
        events.Add(family);
    }
    public static void PopulateBodyFields(JObject manifest, GameObject[] values)
    {
        Check(ReferenceEquals(manifest, snapshot) && values.SequenceEqual(BodyCatalog.allBodyPrefabs));
        events.Add("bodies");
    }
    public static void Check(bool value) { if (!value) throw new Exception("Artifact/holder contract differs"); }
}
public static partial class PortSession
{
    static void TraceStartup(string step) => WholeCatalogComposed.events.Add(step);
    static void StaticCall(Type type, string method, object[] args = null)
    {
        if (type == typeof(ArtifactCatalog) && method == "SetArtifactDefs")
        {
            ArtifactCatalog.values = (ArtifactDef[])args.Single();
            WholeCatalogComposed.events.Add("register");
        }
        else
        {
            WholeCatalogComposed.Check(type == typeof(RunArtifactManager) && method == "Init");
            WholeCatalogComposed.Check(ReferenceEquals(ArtifactCatalog.values, WholeCatalogComposed.artifacts));
            WholeCatalogComposed.events.Add("init");
        }
    }
    public static void Main()
    {
        Prepare();
        WholeCatalogComposed.Check(WholeCatalogComposed.events.SequenceEqual(new[] {
            "artifact-family-begin", "read", "family", "register", "definition-holders-begin",
            "Artifacts", "init", "Items", "Equipment", "bodies" }));
        Console.WriteLine("artifact holder snapshot order identity PASS");
    }
}
