using System;

__PRODUCTION_SCHEDULE__

sealed class WorldReport
{
    public bool originalAudioCameraContextCreated;
    public string originalAudioCameraContextState;
}

sealed class RunReport { public WorldReport world; }
sealed class Coordinator { public RunReport r; }

sealed class ProductionCleanupProjection
{
    readonly OriginalAudioCameraContextCreationSchedule originalAudioCameraContextCreationSchedule =
        new OriginalAudioCameraContextCreationSchedule();
    readonly Coordinator coordinator = new Coordinator();

__PRODUCTION_CLEANUP_HELPER__

    public void Queue() => originalAudioCameraContextCreationSchedule.Schedule();
    public void Reset() => originalAudioCameraContextCreationSchedule.Reset();
    public bool IsPending => originalAudioCameraContextCreationSchedule.IsPending;
    public void SetReport(WorldReport report) => coordinator.r = new RunReport { world = report };
    public OriginalAudioCameraContextCreationSchedule.BeginResult Begin(
        bool playing, object updateBody, object ownedBody, bool alreadyAttempted) =>
        originalAudioCameraContextCreationSchedule.Begin(playing, updateBody, ownedBody, alreadyAttempted);
    public void Cleanup() => CancelPendingOriginalAudioCameraContextCreationForCleanup();
}

static class DeferredAudioCameraCreationProgram
{
    static void Expect(bool value, string reason)
    {
        if (!value) throw new Exception("failed: " + reason);
    }

    public static int Main()
    {
        var schedule = new ProductionCleanupProjection();
        var ownedBody = new object();
        var foreignBody = new object();
        Expect(schedule.Begin(true, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.NotPending, "default is not pending");
        schedule.Queue();
        Expect(schedule.Begin(false, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Deferred, "non-playing phase defers");
        Expect(schedule.IsPending, "deferred request remains queued");
        Expect(schedule.Begin(true, foreignBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Refused, "foreign body refused");
        Expect(!schedule.IsPending, "foreign-body refusal consumes request");
        schedule.Queue();
        Expect(schedule.Begin(true, null, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Refused, "missing update body refused");
        schedule.Queue();
        Expect(schedule.Begin(true, ownedBody, null, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Refused, "missing owned body refused");
        schedule.Queue();
        Expect(schedule.Begin(true, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Begin, "exact owned body admitted once");
        Expect(schedule.Begin(true, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.NotPending, "second Begin cannot repeat");
        schedule.Queue();
        Expect(schedule.Begin(true, ownedBody, ownedBody, true) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.Refused, "prior attempt refuses duplicate");
        schedule.Queue();
        schedule.Reset();
        Expect(!schedule.IsPending && schedule.Begin(true, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.NotPending, "world reset clears request");

        var pending = new ProductionCleanupProjection();
        var pendingReport = new WorldReport
        {
            originalAudioCameraContextState = "deferred_until_first_integrated_world_update"
        };
        pending.SetReport(pendingReport);
        pending.Queue();
        pending.Cleanup();
        Expect(!pending.IsPending, "cleanup cancels queued creation");
        Expect(pending.Begin(true, ownedBody, ownedBody, false) ==
            OriginalAudioCameraContextCreationSchedule.BeginResult.NotPending, "cleanup then Begin cannot create an owner");
        Expect(!pendingReport.originalAudioCameraContextCreated, "no owner is reported created");
        Expect(pendingReport.originalAudioCameraContextState == "deferred_creation_cancelled_by_world_cleanup",
            "cancellation state is explicit");

        var alreadyCreated = new ProductionCleanupProjection();
        var createdReport = new WorldReport
        {
            originalAudioCameraContextCreated = true,
            originalAudioCameraContextState = "ready"
        };
        alreadyCreated.SetReport(createdReport);
        alreadyCreated.Queue();
        alreadyCreated.Cleanup();
        Expect(!alreadyCreated.IsPending, "cleanup clears pending flag for created context too");
        Expect(createdReport.originalAudioCameraContextCreated && createdReport.originalAudioCameraContextState == "ready",
            "cancel helper preserves created-context status");

        Console.WriteLine("PASS: production deferred-camera lifecycle and cleanup contract");
        return 0;
    }
}
