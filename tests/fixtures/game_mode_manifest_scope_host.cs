using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;
using RoR2;
using RoR2.ContentManagement;
using Object = UnityEngine.Object;
public class ResourceAvailability {}
namespace UnityEngine
{
    public class Object { public string name; public static implicit operator bool(Object value) { return value != null; } }
    public class GameObject : Object
    {
        public Run run;
        public GameObject(string name) { this.name = name; run = new Run { gameObject = this }; }
        public T GetComponent<T>() where T : Object { return run as T; }
    }
}
namespace RoR2
{
    public class Run : Object { public static Run instance; public GameObject gameObject; }
    public class UnlockableDef : Object { public string cachedName; }
    public static class UnlockableCatalog { public static UnlockableDef GetUnlockableDef(string name) { return null; } }
    public static class KarmaManager { public static List<UnlockableDef> startingKarmaUnlockables = new List<UnlockableDef>(); }
    public static class ItemCatalog { public static Object[] allItemDefs = new Object[0]; }
    public enum EquipmentIndex { None }
    public static class EquipmentCatalog { public static int equipmentCount; public static Object GetEquipmentDef(EquipmentIndex index) { return null; } }
    public static class DroneCatalog { public static Object[] allDroneDefs = new Object[0]; }
    public static class KeyItemCatalog { public static Object[] allKeyItemDefs = new Object[0]; }
    public static class RuleCatalog { public static int ruleCount; public static object FindRuleDef(string name) { return ruleCount > 0 ? new object() : null; } }
    public static class RuleBook {}
    public static class GameModeCatalog
    {
        public static GameObject[] modes = new GameObject[0];
        public static int gameModeCount { get { return modes.Length; } }
        public static ResourceAvailability availability = new ResourceAvailability();
        public static Run FindGameModePrefabComponent(string name) { return modes.SingleOrDefault(mode => mode.name == name)?.run; }
    }
}
namespace RoR2.ContentManagement
{
    public static class ContentManager { public static GameObject[] _gameModePrefabs; }
    public static class AddressablesLabels { public const string gameMode = "gameMode"; }
}
public static class WholeCatalogComposed
{
    public static JObject expected;
    public static GameObject[] modes;
    public static int calls;
    public static T[] CategoryFamily<T>(JObject manifest, string category, T[] selected, Action<string> trace)
    {
        if (!ReferenceEquals(manifest, expected) || category != "gameMode" || selected.Length != 0)
            throw new Exception("Game-mode snapshot forwarding changed");
        calls++;
        PortSession.events.Add("family");
        trace("manifest-begin");
        return modes.Cast<T>().ToArray();
    }
}
public partial class PortSession
{
    public static readonly List<string> events = new List<string>();
    public class Report { public object liveCatalogs = new object(); }
    public Report r = new Report();
    public bool stageSourceObjects = true;
    public object androidProgression = new object();
    TeleporterWorldSession session;
    TeleporterWorldSession GetTeleporterWorldSession() { return session ?? (session = new TeleporterWorldSession(this)); }
    public void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void TraceStartup(string step) { events.Add(step); }
    public static void StaticCall(Type type, string method, object[] args = null)
    {
        events.Add(type.Name + "." + method);
        if (type == typeof(RuleCatalog)) RuleCatalog.ruleCount = 1;
        if (type == typeof(GameModeCatalog))
        {
            if (method == "LoadGameModes") GameModeCatalog.modes = ContentManager._gameModePrefabs;
            else
            {
                if (((Run[])args[0]).Length != 0) throw new Exception("Unexpected native cleanup input");
                GameModeCatalog.modes = new GameObject[0];
            }
            GameModeCatalog.availability = new ResourceAvailability();
        }
    }
    sealed partial class TeleporterWorldSession
    {
        readonly PortSession coordinator;
        GameObject[] priorGameModeContent;
        ResourceAvailability priorGameModeAvailability;
        bool ownsGameModeCatalog;
        static string objectiveRuleSignature;
        public TeleporterWorldSession(PortSession value) { coordinator = value; }
    }
    static void Assert(bool value) { if (!value) throw new Exception("Game-mode scope contract differs"); }
    public static void Main()
    {
        var owner = new PortSession();
        var manifest = new JObject();
        WholeCatalogComposed.expected = manifest;
        WholeCatalogComposed.modes = new[] { new GameObject("ClassicRun"), new GameObject("OtherRun") };
        var previousContent = new GameObject[0];
        var previousAvailability = GameModeCatalog.availability;
        var previousKarma = KarmaManager.startingKarmaUnlockables;
        ContentManager._gameModePrefabs = previousContent;
        owner.PrepareObjectiveRuleCatalog(manifest);
        Assert(GameModeCatalog.modes.SequenceEqual(WholeCatalogComposed.modes));
        Assert(ReferenceEquals(GameModeCatalog.modes, ContentManager._gameModePrefabs));
        Assert(ReferenceEquals(GameModeCatalog.FindGameModePrefabComponent("ClassicRun"), WholeCatalogComposed.modes[0].run));
        Assert(ReferenceEquals(KarmaManager.startingKarmaUnlockables, previousKarma));
        Assert(events.Where(step => step.Contains(".") || step == "family").SequenceEqual(new[] {
            "KarmaManager.GatherStartingKarmaUnlockables", "RuleCatalog.Init", "RuleBook.Init", "family", "GameModeCatalog.LoadGameModes" }));
        int eventCount = events.Count;
        owner.PrepareObjectiveRuleCatalog(); // Cached native metadata and owned modes do no work.
        Assert(events.Count == eventCount && WholeCatalogComposed.calls == 1);
        owner.GetTeleporterWorldSession().CleanupOriginalGameModes();
        Assert(ReferenceEquals(ContentManager._gameModePrefabs, previousContent));
        Assert(ReferenceEquals(GameModeCatalog.availability, previousAvailability) && GameModeCatalog.gameModeCount == 0);
        WholeCatalogComposed.expected = null;
        owner.PrepareObjectiveRuleCatalog(); // Existing no-snapshot fallback still forwarded.
        Assert(WholeCatalogComposed.calls == 2);
        owner.GetTeleporterWorldSession().CleanupOriginalGameModes();
        owner.stageSourceObjects = false;
        owner.PrepareOriginalGameModes(manifest);
        Assert(WholeCatalogComposed.calls == 2);
        owner.stageSourceObjects = true;
        GameModeCatalog.modes = WholeCatalogComposed.modes;
        bool refused = false;
        try { owner.PrepareOriginalGameModes(manifest); } catch (Exception) { refused = true; }
        Assert(refused);
        Console.WriteLine("game-mode snapshot native order identity restoration PASS");
    }
}
