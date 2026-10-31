// Authored peers for three extracted production methods. No game code or data.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2.Stats;

class LiveObject
{
    public bool alive = true;
    public object gameObject;
    public static implicit operator bool(LiveObject value) { return value != null && value.alive; }
}
class Stage { public static Action<Stage> onServerStageBegin, onServerStageComplete; }
class Run : LiveObject
{
    public static Run instance;
    public static Action<Run, object> onServerGameOver;
    public static Action<Run, RunReport> onClientGameOverGlobal;
    public object gameOverPrefab;
}
class RunReport { static string runReportsFolder; }
class ContentManager { public static object _gameEndingDefs; }
class GameEndingCatalog { }
class NetworkServer { public static bool active = true; public static void Destroy(object value) { } }
class PlatformSystems { public static object saveSystem; }
class Events { public static Action damage; }
class Report { public bool cleaned; }
class SessionReport { public Report results = new Report(); }
class Coordinator
{
    public readonly object resultsSaveSystem = new object();
    public PlayerStatsComponent resultsStats = new PlayerStatsComponent();
    public SessionReport r = new SessionReport();
    public bool profileAlive = true;
    public void Check(bool pass, string reason) { if (!pass) throw new Exception(reason); }
    public void CleanupAndroidProfile() { profileAlive = false; }
}
namespace RoR2.Stats
{
    class PlayerStatsComponent : LiveObject { public int total; }
    static class StatManager
    {
        // Deliberately tiny synthetic event processor; this is not the game's implementation.
        public struct Event { public PlayerStatsComponent target; public int value; }
        public static readonly Queue<Event> pending = new Queue<Event>();
        public static Coordinator context;
        public static int calls, priorCalls;
        public static bool fail;
        public static void Produce() { pending.Enqueue(new Event { target = context.resultsStats, value = 7 }); }
        public static void Prior() { priorCalls++; }
        public static void Consume()
        {
            calls++;
            Program.Need(context.profileAlive && context.resultsStats && NetworkServer.active &&
                         ReferenceEquals(PlatformSystems.saveSystem, context.resultsSaveSystem), "consumer ran after teardown");
            Program.Need(!Events.damage.GetInvocationList().Contains((Action)Produce), "owned producer still attached");
            if (fail) throw new InvalidOperationException("authored consumer failure");
            while (pending.Count > 0)
            {
                var entry = pending.Dequeue();
                entry.target.total += entry.value;
            }
        }
    }
}
partial class ResultsHarness
{
    readonly Coordinator coordinator;
    readonly Dictionary<FieldInfo, object> resultsEventContext = new Dictionary<FieldInfo, object>();
    Action resultsStatsFixed, resultsStatsProcess;
    Action<Stage> resultsOfflineStageBegin, resultsOfflineStageComplete;
    readonly HashSet<int> resultsVisitedStages = new HashSet<int>(), resultsCompletedStages = new HashSet<int>();
    bool ownsResultsSaveSystem = true, ownsResultsContext = true, ownsResultsStats = true;
    object previousResultsSaveSystem, previousGameOverPrefab, previousEndingContent, previousEndingCatalog;
    string previousReportFolder;
    LiveObject resultsController, resultsTemplate;
    Action<Run, object> resultsServerEvent;
    Action<Run, RunReport> resultsClientEvent;
    public int fixedTicks;
    public ResultsHarness(Coordinator owner, bool partial)
    {
        coordinator = owner;
        StatManager.context = owner;
        PlatformSystems.saveSystem = owner.resultsSaveSystem;
        Events.damage = StatManager.Prior;
        Events.damage += Program.Foreign;
        resultsEventContext[typeof(Events).GetField("damage")] = Events.damage;
        Events.damage += StatManager.Produce;
        resultsStatsFixed = () => fixedTicks++;
        if (!partial) resultsStatsProcess = StatManager.Consume;
        else ownsResultsContext = false;
    }
    void CleanupResultsItemRelationships() { }
    void CleanupResultsItemGroups() { }
    void CleanupResultsKeyItems() { }
    static void Call(PlayerStatsComponent value, string method) { value.alive = false; }
    static void StaticCall(Type type, string method, object[] args) { }
    static void Destroy(object value) { }
}
static class Program
{
    static int foreignCalls;
    public static void Foreign() { foreignCalls++; }
    public static void Need(bool pass, string reason) { if (!pass) throw new Exception(reason); }
    static void Main(string[] args)
    {
        bool partial = args[0] == "partial";
        var coordinator = new Coordinator();
        var owner = new ResultsHarness(coordinator, partial);
        if (!partial) Events.damage(); // Last event arrived after the last scheduled statistics tick.
        if (args[0] == "failure")
        {
            StatManager.fail = true;
            bool threw = false;
            try { owner.Dispose(); } catch (InvalidOperationException) { threw = true; }
            Need(threw && coordinator.profileAlive && coordinator.resultsStats && !coordinator.r.results.cleaned &&
                 StatManager.pending.Count == 1 && coordinator.resultsStats.total == 0, "failed drain lost events or tore down context");
            StatManager.fail = false;
        }
        owner.Dispose();
        Need(coordinator.r.results.cleaned && !coordinator.profileAlive && !coordinator.resultsStats &&
             PlatformSystems.saveSystem == null, "ordinary teardown did not follow final consumer");
        Need(StatManager.pending.Count == 0 && coordinator.resultsStats.total == (partial ? 0 : 7), "pending events were lost or duplicated");
        Need(StatManager.calls == (partial ? 0 : args[0] == "failure" ? 2 : 1), "wrong consumer count");
        if (args[0] == "repeat")
        {
            owner.Dispose();
            Need(StatManager.calls == 1 && coordinator.resultsStats.total == 7, "repeat cleanup reprocessed statistics");
        }
        Need(owner.fixedTicks == 0, "cleanup manufactured a statistics tick");
        int prior = StatManager.priorCalls, foreign = foreignCalls;
        Events.damage();
        Need(StatManager.priorCalls == prior + 1 && foreignCalls == foreign + 1 && StatManager.pending.Count == 0,
             "cleanup removed prior/foreign callbacks or left its own producer");
        Console.WriteLine(args[0] + ": PASS");
    }
}
