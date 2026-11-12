using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
class Asset { public string name; public static implicit operator bool(Asset value) { return value != null; } }
class TextAsset : Asset { }
class ItemGroupType : Asset { }
class Group { public object[] items; }
class ItemGroupProvider : Asset { public ItemGroupType groupType; public Group[] groups; }
static class DLC4Content { public static class ItemGroupTypes { public static ItemGroupType Alpha, Beta; } }
static class Resources {
    public static bool available = true;
    public static T Load<T>(string key) where T : Asset, new() { return available ? new T() : null; }
}
static class ItemCatalog {
    public static Hashtable itemGroups = new Hashtable();
    public static Group[] GetItemGroupsForGroupType(ItemGroupType type) {
        return WholeCatalogComposed.providers.Where(p => p.groupType == type).SelectMany(p => p.groups)
            .Where(g => g.items.Length > 0).ToArray();
    }
}
static class WholeCatalogComposed {
    public static ItemGroupType[] types = { new ItemGroupType { name = "Alpha" }, new ItemGroupType { name = "Beta" } };
    public static ItemGroupProvider[] providers = {
        new ItemGroupProvider { groupType = types[0], groups = new[] { new Group { items = new object[] { null } }, new Group { items = new object[0] } } },
        new ItemGroupProvider { groupType = types[1], groups = new[] { new Group { items = new[] { new object() } } } }
    };
    public static ItemGroupType[] ItemGroupTypes() { Host.calls.Add("types"); return types; }
    public static ItemGroupProvider[] ItemGroupProviders() { Host.calls.Add("providers"); return providers; }
}
class Counts { public int itemGroupTypes, itemGroupProviders, itemGroups; }
class Report { public Counts results = new Counts(); }
class Coordinator {
    public Report r = new Report();
    public void Check(bool value, string message) { if (!value) throw new Exception(message); }
    public void BindEnemyDefinition(Type owner, string name, ItemGroupType value) {
        Host.calls.Add("bind:" + name); owner.GetField(name).SetValue(null, value);
    }
}
public class Host {
    public static List<string> calls = new List<string>(), traces = new List<string>();
    Coordinator coordinator = new Coordinator(); bool ownsResultsItemGroups;
    static FieldInfo RewardField(Type owner, string name) { return owner.GetField(name); }
    static void TraceStartup(string step) { traces.Add(step); }
    static void StaticCall(Type owner, string name, object[] args) {
        var values = (ItemGroupProvider[])args[0];
        calls.Add(values.Length == 0 ? "clear" : "set");
        if (values.Length != 0 && !ReferenceEquals(values, WholeCatalogComposed.providers)) throw new Exception("provider identity");
        ItemCatalog.itemGroups.Clear();
        foreach (var value in values) ItemCatalog.itemGroups[value] = value;
    }
    // OWNER_METHODS
    static void Need(bool value, string message) { if (!value) throw new Exception(message); }
    public static void Main() {
        var host = new Host();
        Resources.available = false; host.PrepareResultsItemGroups();
        Need(calls.Count == 0 && traces.Count == 0, "absent bootstrap");
        Resources.available = true; host.PrepareResultsItemGroups();
        Need(String.Join(",", calls) == "types,providers,bind:Alpha,bind:Beta,set", "native order");
        Need(DLC4Content.ItemGroupTypes.Alpha == WholeCatalogComposed.types[0] && DLC4Content.ItemGroupTypes.Beta == WholeCatalogComposed.types[1], "holder identities");
        Need(host.coordinator.r.results.itemGroupTypes == 2 && host.coordinator.r.results.itemGroupProviders == 2 && host.coordinator.r.results.itemGroups == 3, "native counts incl empty slot");
        Need(WholeCatalogComposed.providers[0].groups[0].items[0] == null, "source null membership");
        Need(String.Join(",", traces.Select(s => s.Replace("results-item-groups-", ""))) ==
            "owner-check-begin,owner-check-ready-types-begin,types-ready-providers-begin,providers-ready-metadata-begin,metadata-ready-bindings-begin,bindings-ready-native-set-begin,native-set-ready-validation-begin,validation-ready", "ordered seams");
        int before = calls.Count;
        try { host.PrepareResultsItemGroups(); throw new Exception("foreign owner admitted"); }
        catch (Exception e) { Need(e.Message == "Unowned item-group catalog", "ownership failure"); }
        Need(calls.Count == before, "failure before mutation");
        host.CleanupResultsItemGroups(); host.CleanupResultsItemGroups();
        Need(calls.Last() == "clear" && calls.Count == before + 1 && ItemCatalog.itemGroups.Count == 0 && !host.ownsResultsItemGroups, "owned cleanup once");
        Console.WriteLine("item-group attribution order identity cleanup PASS");
    }
}
