// Authored host doubles: no Unity, original assets, game source, or network state.
using System;
using System.Collections.Generic;

public sealed class Report
{
    public bool nativeFirstStageLifecycleDiagnosticAttempt = true;
    public bool sourceStageLifecycleRecoveryRequired;
    public long sourceStageLifecycleRecoveryGeneration;
    public bool cleanup = true;
    public bool success = true;
    public string error = "";
}

public sealed partial class Coordinator
{
    public readonly Report r = new Report();
    public readonly List<string> calls = new List<string>();
    public readonly int baseline = 1;
    public readonly int purchases;
    public int references, finalChecks, attributedReleases, supportReleaseAttempts, supportReleases, saves;
    public bool sourceTablesRestored, commerceChecked;
    public Exception sourceRetirementFailure;
    public readonly TeleporterWorldSession teleporter;

    public Coordinator(int references, int purchases)
    {
        this.references = references;
        this.purchases = purchases;
        teleporter = new TeleporterWorldSession(this);
    }
    public void CleanupDirectorActors() { calls.Add("actors"); }
    public void CleanupWholeStageInteractables() { calls.Add("interactables"); }
    public void ReleaseObjectiveStage() { calls.Add("stage"); }
    public void CleanupStageTransport()
    {
        calls.Add("source-retirement");
        if (sourceRetirementFailure != null)
            throw sourceRetirementFailure;
        sourceTablesRestored = true;
    }
    public void CleanupWorldCommerce(bool final = false)
    {
        calls.Add(final ? "commerce-final" : "commerce-detach");
        if (!final)
            return;
        finalChecks++;
        Require(sourceTablesRestored, "Commerce reconciliation preceded source-table restoration");
        // Independent external contract: one baseline lease plus exactly the
        // attributed native acquisitions. Unexpected ownership is not released.
        int extra = references - baseline;
        if (extra != purchases)
            throw new InvalidOperationException("Strict commerce ownership mismatch");
        Require(!commerceChecked, "Commerce reconciliation repeated");
        commerceChecked = true;
        attributedReleases += extra;
        references -= extra;
    }
    public void CleanupTeleporterWorld() { teleporter.Dispose(); }
    public void CleanupStageBossContent() { calls.Add("boss-content"); }
    public void CleanupMoonMission() { calls.Add("moon-mission"); }
    public void Save() { saves++; }
    public void ReleaseBaseline()
    {
        calls.Add("support-release");
        supportReleaseAttempts++;
        Require(commerceChecked, "Baseline support release preceded strict commerce reconciliation");
        Require(sourceTablesRestored && references == baseline, "Baseline lease is not the only remaining reference");
        supportReleases++;
        references--;
    }
    public static void Require(bool value, string message)
    {
        if (!value)
            throw new InvalidOperationException(message);
    }
}

public sealed partial class TeleporterWorldSession
{
    readonly Coordinator coordinator;
    public TeleporterWorldSession(Coordinator coordinator) { this.coordinator = coordinator; }
    void CleanupNativeObjectivePlacement() { coordinator.calls.Add("objective-placement"); }
    void ObserveObjectiveSupport(bool force = false)
    {
        Coordinator.Require(force, "Support teardown observation lost its force argument");
        coordinator.calls.Add("support-observe");
    }
    void CleanupObjectiveEffects() { coordinator.calls.Add("objective-effects"); }
    void CleanupObjectiveSupport() { coordinator.ReleaseBaseline(); }
}

public sealed partial class IntegratedWorldSession
{
    readonly Coordinator coordinator;
    public IntegratedWorldSession(Coordinator coordinator) { this.coordinator = coordinator; }
    void CleanupWorldTransmutation() { coordinator.calls.Add("transmutation"); }
}

public static class NativeCommerceReleaseOrderHost
{
    static void Check(bool condition, string message) { Coordinator.Require(condition, message); }
    static Exception Capture(Action operation)
    {
        try { operation(); return null; }
        catch (Exception exception) { return exception; }
    }
    static void CheckSuccess(Coordinator owner, int acquisitions)
    {
        var world = new IntegratedWorldSession(owner);
        world.CleanupIntegratedWorld();
        Check(owner.references == 0 && owner.attributedReleases == acquisitions && owner.supportReleases == 1,
              "Attributed references and one baseline must retire exactly once");
        Check(owner.finalChecks == 1 && owner.commerceChecked && owner.sourceTablesRestored,
              "One strict reconciliation must follow source restoration");
        Check(!owner.r.sourceStageLifecycleRecoveryRequired && owner.r.cleanup && owner.r.success && owner.r.error == "",
              "Successful teardown must not latch recovery or an error");
        Check(owner.calls.IndexOf("commerce-detach") < owner.calls.IndexOf("actors") &&
              owner.calls.IndexOf("source-retirement") < owner.calls.IndexOf("commerce-final"),
              "Detach must precede native retirement; reconciliation must follow source restoration");
        Check(owner.calls.IndexOf("support-observe") < owner.calls.IndexOf("objective-effects") &&
              owner.calls.IndexOf("objective-effects") < owner.calls.IndexOf("support-release") &&
              owner.calls.IndexOf("support-release") < owner.calls.IndexOf("transmutation"),
              "Actual support tail must finish inside teleporter cleanup before world cleanup resumes");
    }
    static void NormalPurchase() { CheckSuccess(new Coordinator(2, 1), 1); }
    static void NoPurchase() { CheckSuccess(new Coordinator(1, 0), 0); }
    static void UnexpectedExtra()
    {
        var owner = new Coordinator(3, 1);
        var failure = Capture(() => new IntegratedWorldSession(owner).CleanupIntegratedWorld());
        Check(failure is InvalidOperationException && failure.Message == "Strict commerce ownership mismatch",
              "Unexpected acquisition must preserve the strict ownership failure");
        Check(owner.sourceTablesRestored && owner.references == 3 && owner.attributedReleases == 0,
              "Mismatch must retain all references after source tables restore");
        Check(owner.finalChecks == 1 && !owner.commerceChecked && owner.supportReleaseAttempts == 0 && owner.supportReleases == 0,
              "Mismatch must skip baseline release and the support tail");
        Check(!owner.calls.Contains("support-observe") && !owner.calls.Contains("objective-effects") &&
              !owner.calls.Contains("transmutation"), "Mismatch must not proceed through dependent cleanup");
        Check(owner.r.sourceStageLifecycleRecoveryRequired && !owner.r.cleanup && !owner.r.success &&
              owner.r.error.Contains("Strict commerce ownership mismatch") && owner.saves == 2,
              "Both real owner catch boundaries must retain recovery and failure evidence");
    }
    static void SourceRetirementFailure()
    {
        var owner = new Coordinator(2, 1);
        var primary = new InvalidOperationException("Source retirement refused");
        owner.sourceRetirementFailure = primary;
        var failure = Capture(() => new IntegratedWorldSession(owner).CleanupIntegratedWorld());
        Check(ReferenceEquals(primary, failure), "Native catch boundaries must rethrow the original retirement failure");
        Check(!owner.sourceTablesRestored && owner.finalChecks == 0 && owner.references == 2 &&
              owner.supportReleaseAttempts == 0 && owner.attributedReleases == 0,
              "Source retirement refusal must skip commerce reconciliation and all support release");
        Check(!owner.calls.Contains("support-observe") && !owner.calls.Contains("objective-effects") &&
              !owner.calls.Contains("transmutation"), "Retirement refusal must retain dependent cleanup");
        Check(owner.r.sourceStageLifecycleRecoveryRequired && !owner.r.cleanup && !owner.r.success &&
              owner.r.error.Contains("Source retirement refused") && owner.saves == 2,
              "Retirement failure must retain coherent recovery flags through both owners");
    }
    public static int Main(string[] arguments)
    {
        try
        {
            NormalPurchase();
            if (arguments.Length == 1 && arguments[0] == "normal-purchase")
            {
                Console.WriteLine("PASS normal purchase before baseline release");
                return 0;
            }
            NoPurchase();
            UnexpectedExtra();
            SourceRetirementFailure();
            Console.WriteLine("{\"normal_purchase\":true,\"no_purchase\":true," +
                              "\"unexpected_extra_retained\":true,\"source_retirement_failure_retained\":true}");
            return 0;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine("FAIL: " + exception.Message);
            return 1;
        }
    }
}
