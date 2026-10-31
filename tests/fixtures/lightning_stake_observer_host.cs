public static class LightningStakeRollingObserverHostContracts
{
    static void Require(bool condition, string label)
    {
        if (!condition) throw new Exception("failed: " + label);
    }

    sealed class SyntheticRetirementOwner
    {
        public sealed class TrackedStake { public uint netId; }
        readonly System.Collections.Generic.List<TrackedStake> tracked = new System.Collections.Generic.List<TrackedStake>();
        readonly LightningStakeSamplingPolicy samplingPolicy = new LightningStakeSamplingPolicy();

        public void Add(uint netId)
        {
            if (samplingPolicy.TryTrack(netId)) tracked.Add(new TrackedStake { netId = netId });
        }
        public int ActiveCount => samplingPolicy.IdentityCount;
        public int TrackedCount => tracked.Count;
        public void RunRetirement(int index) { RetireTrackedAt(index); }

        // Production RetireTrackedAt is inserted here by the extraction runner.
        __EXTRACTED_RETIREMENT_METHOD__
    }

    sealed class PauseCoordinator
    {
        public bool offlineSettingsPaused;
        public int observations;
        public void ObserveLightningStakes() { observations++; }
    }
    sealed class PauseBridge
    {
        public int neutralCalls;
        public void Neutral() { neutralCalls++; }
    }
    sealed class PauseConfig { public bool integratedWorld; }

    static void CheckPause(bool paused, bool integrated, int expectedObservations, int expectedSimulation)
    {
        var coordinator = new PauseCoordinator { offlineSettingsPaused = paused };
        var bridge = new PauseBridge();
        var cfg = new PauseConfig { integratedWorld = integrated };
        int simulation = 0;
        for (int frame = 0; frame < 3; frame++)
        {
            __EXTRACTED_PAUSED_BRANCH__
            simulation++;
        }
        Require(coordinator.observations == expectedObservations, "paused observation follows integrated owner selection");
        Require(bridge.neutralCalls == (paused ? 3 : 0), "pause keeps input neutral each frame");
        Require(simulation == expectedSimulation, "paused diagnostic never resumes simulation");
    }

    public static int Main()
    {
        CheckPause(true, true, 3, 0);
        CheckPause(true, false, 0, 0);
        CheckPause(false, true, 0, 3);
        var policy = new LightningStakeSamplingPolicy();
        Require(policy.TryTrack(1) && policy.TryTrack(2) && policy.TryTrack(3), "three active identities fit");
        Require(!policy.TryTrack(4) && policy.IdentityCount == 3, "active identity budget refuses fourth");
        Require(policy.Untrack(2) && policy.IdentityCount == 2, "vacated identity releases active slot");
        Require(!policy.Untrack(2) && policy.TryTrack(4), "retirement is idempotent and slot recycles");
        Require(policy.TotalIdentitiesObserved == 4, "identity count is cumulative across turnover");
        Require(!policy.Untrack(0) && !policy.TryTrack(0), "zero network id is refused");

        var owner = new SyntheticRetirementOwner();
        owner.Add(25);
        Require(owner.ActiveCount == 1 && owner.TrackedCount == 1, "synthetic observer setup owns active identity");
        owner.RunRetirement(0);
        Require(owner.ActiveCount == 0 && owner.TrackedCount == 0, "extracted production retirement releases exact slot and row");
        owner.Add(26);
        Require(owner.ActiveCount == 1 && owner.TrackedCount == 1, "retired production slot is reusable");

        int replace;
        Require(policy.TryReserveRecord(10, false, 35, -1, out replace) && replace == -1,
                "ordinary sample allowed below total cap");
        Require(!policy.TryReserveRecord(11, false, 35, -1, out replace),
                "per-identity final slot stays reserved for transition");
        Require(policy.TryReserveRecord(11, true, 35, -1, out replace),
                "finite-to-invalid transition consumes reserved identity slot");
        Require(!policy.TryReserveRecord(12, true, 35, -1, out replace), "per-identity history remains capped");

        Require(!policy.TryReserveRecord(2, false, 36, 0, out replace), "full history refuses ordinary growth");
        Require(policy.TryReserveRecord(2, true, 36, 4, out replace) && replace == 4,
                "full history preserves transition by replacing oldest ordinary row");
        Require(!policy.TryReserveRecord(2, true, 36, -1, out replace),
                "all-transition history refuses further growth without evicting transition evidence");
        Require(!policy.TryReserveRecord(2, true, 37, 4, out replace), "invalid over-cap count refuses record");

        Require(LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, false),
                "first finite-to-invalid edge is detected");
        Require(!LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, false, false, false) &&
                !LightningStakeSamplingPolicy.IsFirstNonFiniteTransition(true, true, false, true),
                "already-invalid and already-recorded cases are not duplicate transitions");

        policy.Dispose();
        Require(policy.IsDisposed && policy.IdentityCount == 0 && policy.TotalIdentitiesObserved == 4,
                "cleanup releases active IDs but retains scalar report count");
        Require(!policy.TryTrack(5) && !policy.Untrack(4) &&
                !policy.TryReserveRecord(0, true, 0, -1, out replace), "disposed policy is inert");
        Console.WriteLine("PASS: rolling observer policy contracts");
        return 0;
    }
}
