// Authored collaborators model failures before/after a commit. This fixture
// executes the extracted production event owner, not native eligibility or IO.
using System;
using System.Collections.Generic;
using System.IO;

class LiveObject
{
    public static implicit operator bool(LiveObject value) { return value != null; }
}
class CharacterBody : LiveObject { public LiveObject master = new LiveObject(); }
static class NetworkServer { public static bool active = true; }
class UserProfile
{
    public bool earned;
    public int rewards;
    public UserProfile Clone() { return (UserProfile)MemberwiseClone(); }
}
class AndroidProgressionBoundary
{
    public sealed class EventAwardReport
    {
        public string identifier, eventSource, blocked;
        public bool granted;
    }
    public Exception failure;
    public bool refuse;
    public int calls;
    public EventAwardReport ApplyObservedEventCandidate(UserProfile candidate, string identifier)
    {
        calls++;
        if (failure != null) throw failure;
        var report = new EventAwardReport { identifier = identifier };
        if (refuse) { report.blocked = "Unavailable entitlement"; return report; }
        if (candidate.earned) return report;
        candidate.earned = true;
        candidate.rewards++;
        report.granted = true;
        return report;
    }
}
class AndroidOfflineProfile
{
    public UserProfile profile = new UserProfile();
    public Exception commitFailure;
    public Action beforeCommit;
    public int calls, commits;
    public bool AwardObservedEvent(Func<UserProfile, bool> award)
    {
        calls++;
        var candidate = profile.Clone();
        if (!award(candidate)) return false;
        beforeCommit?.Invoke();
        if (commitFailure != null) throw commitFailure;
        profile = candidate;
        commits++;
        return true;
    }
}
class SaveSystem
{
    public AndroidOfflineProfile local = new AndroidOfflineProfile();
    public UserProfile userProfile;
}
class ProfileReport
{
    public bool ready = true;
    public List<AndroidProgressionBoundary.EventAwardReport> eventAwards = new List<AndroidProgressionBoundary.EventAwardReport>();
}
class WorldReport { public bool diagnosticInputEver; }
class NovaReport { public bool diagnosticInput; }
class RuntimeReport
{
    public ProfileReport profile = new ProfileReport();
    public WorldReport world = new WorldReport();
    public NovaReport nova = new NovaReport();
    public bool developerSurvivorOverride;
}
class Coordinator
{
    public RuntimeReport r = new RuntimeReport();
    public CharacterBody worldPlayer = new CharacterBody();
    public SaveSystem resultsSaveSystem = new SaveSystem();
    public AndroidProgressionBoundary androidProgression = new AndroidProgressionBoundary();
    public bool assisted;
    public Exception reportFailure;
    public int saves;
    public bool IsRunAssisted() { return assisted; }
    public void Check(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    public void Save() { saves++; if (reportFailure != null) throw reportFailure; }
}
partial class AndroidProfileSession
{
    public readonly Coordinator coordinator = new Coordinator();
    readonly HashSet<string> profileObservedEvents = new HashSet<string>(StringComparer.Ordinal);
    public Exception observationFailure;
    public int observations;
    void ObserveAndroidProfile()
    {
        observations++;
        if (observationFailure != null) throw observationFailure;
    }
    public void GenuineEvent() { RecordOfflineOriginalEvent("KillEliteMonster", "authored event fixture"); }
}
class OfflineAchievementEventRetryHost
{
    static void Need(bool value, string message) { if (!value) throw new Exception(message); }
    static void ThrowsSame(AndroidProfileSession session, Exception expected)
    {
        Exception observed = null;
        try { session.GenuineEvent(); }
        catch (Exception error) { observed = error; }
        Need(ReferenceEquals(observed, expected), "original exception identity must be preserved");
    }
    static void AssertSingleCommitAndDedup(AndroidProfileSession session)
    {
        var owner = session.coordinator;
        var store = owner.resultsSaveSystem.local;
        session.GenuineEvent();
        Need(store.calls == 2 && store.commits == 1 && store.profile.earned && store.profile.rewards == 1,
             "same genuine event must retry the failed transaction and commit one reward");
        Need(ReferenceEquals(owner.resultsSaveSystem.userProfile, store.profile), "save system must use committed profile");
        Need(owner.r.profile.eventAwards.Count == 1 && owner.r.profile.eventAwards[0].granted &&
             owner.r.profile.eventAwards[0].eventSource == "authored event fixture", "committed report must retain event provenance");
        session.GenuineEvent();
        Need(store.calls == 2 && store.commits == 1 && store.profile.rewards == 1 && owner.saves == 1,
             "successful retry must deduplicate later identical events");
    }
    static void Retry(string scenario)
    {
        var session = new AndroidProfileSession();
        var owner = session.coordinator;
        var store = owner.resultsSaveSystem.local;
        var before = store.profile;
        var failure = new IOException("injected precommit failure");
        if (scenario == "candidate-failure") owner.androidProgression.failure = failure;
        else store.commitFailure = failure;
        ThrowsSame(session, failure);
        Need(failure.StackTrace.Contains("AndroidOfflineProfile.AwardObservedEvent"),
             "original transaction failure stack must be preserved");
        Need(ReferenceEquals(before, store.profile) && !before.earned && before.rewards == 0 && store.commits == 0 &&
             owner.r.profile.eventAwards.Count == 0 && session.observations == 0 && owner.saves == 0,
             "failed transaction must leave profile and completed observations unchanged");
        owner.androidProgression.failure = null;
        store.commitFailure = null;
        AssertSingleCommitAndDedup(session);
    }
    static void Reentrant()
    {
        var session = new AndroidProfileSession();
        var store = session.coordinator.resultsSaveSystem.local;
        store.beforeCommit = session.GenuineEvent;
        session.GenuineEvent();
        session.GenuineEvent();
        Need(store.calls == 1 && store.commits == 1 && store.profile.rewards == 1,
             "in-flight and completed events must both deduplicate");
    }
    static void Assisted()
    {
        // Each existing assistance source must refuse before reaching the store.
        for (int gate = 0; gate < 4; gate++)
        {
            var session = new AndroidProfileSession();
            var owner = session.coordinator;
            if (gate == 0) owner.r.world.diagnosticInputEver = true;
            if (gate == 1) owner.r.nova.diagnosticInput = true;
            if (gate == 2) owner.r.developerSurvivorOverride = true;
            if (gate == 3) owner.assisted = true;
            session.GenuineEvent();
            session.GenuineEvent();
            Need(owner.resultsSaveSystem.local.calls == 0 && owner.androidProgression.calls == 0 &&
                 !owner.resultsSaveSystem.local.profile.earned && owner.r.profile.eventAwards.Count == 1 &&
                 !owner.r.profile.eventAwards[0].granted && owner.r.profile.eventAwards[0].blocked != null && owner.saves == 1,
                 "assisted event must refuse and deduplicate without a reward transaction");
        }
    }
    static void Refused()
    {
        var session = new AndroidProfileSession();
        var owner = session.coordinator;
        owner.androidProgression.refuse = true;
        session.GenuineEvent();
        session.GenuineEvent();
        Need(owner.resultsSaveSystem.local.calls == 1 && owner.resultsSaveSystem.local.commits == 0 &&
             !owner.resultsSaveSystem.local.profile.earned && owner.r.profile.eventAwards.Count == 1 &&
             owner.r.profile.eventAwards[0].blocked != null && owner.saves == 1,
             "a successful refusal decision must remain deduplicated");
    }
    static void AfterCommit(string scenario)
    {
        var session = new AndroidProfileSession();
        var owner = session.coordinator;
        var store = owner.resultsSaveSystem.local;
        var failure = new IOException("injected postcommit failure");
        if (scenario == "observation-failure") session.observationFailure = failure;
        else owner.reportFailure = failure;
        ThrowsSame(session, failure);
        Need(store.commits == 1 && store.profile.earned && store.profile.rewards == 1 &&
             ReferenceEquals(owner.resultsSaveSystem.userProfile, store.profile), "reward must already be committed");
        session.observationFailure = null;
        owner.reportFailure = null;
        session.GenuineEvent();
        Need(store.calls == 1 && store.commits == 1 && store.profile.rewards == 1 && session.observations == 1 &&
             owner.saves == (scenario == "report-failure" ? 1 : 0),
             "postcommit observation/report failure must retain event reservation");
    }
    public static int Main(string[] args)
    {
        string scenario = args[0];
        switch (scenario)
        {
            case "candidate-failure": case "commit-failure": Retry(scenario); break;
            case "reentrant": Reentrant(); break;
            case "assisted": Assisted(); break;
            case "refused": Refused(); break;
            case "observation-failure": case "report-failure": AfterCommit(scenario); break;
            default: throw new Exception("Unknown fixture scenario");
        }
        Console.WriteLine("PASS: " + scenario);
        return 0;
    }
}
