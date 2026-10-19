public static class TransientProjectileWindowHost
{
    static void Require(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }

    static int DriveWindow(TransientProjectileWindowSchedule policy, float start, bool baselineAtStart = false)
    {
        Require(policy.Request(start, true), "Expected bounded window acceptance");
        int scans = 0;
        // Integer ticks avoid test-only clock accumulation drift.
        for (int tick = 1; tick <= 20; tick++)
        {
            float now = start + tick * .05f;
            bool extra;
            if (policy.TryTakeScan(now, baselineAtStart && tick == 1, out extra)) scans++;
        }
        return scans;
    }

    public static int Main()
    {
        var invalid = new TransientProjectileWindowSchedule();
        Require(!invalid.Request(float.NaN, true) && !invalid.Request(float.PositiveInfinity, true) &&
                    !invalid.Request(-1, true) && !invalid.Request(0, false),
                "Invalid clocks and unavailable observer must refuse window arming");
        Require(invalid.requests == 4 && invalid.droppedRequests == 4 && invalid.accepted == 0,
                "Refused window requests must remain explicit and bounded");
        bool ignoredExtra;
        Require(!invalid.TryTakeScan(float.NaN, false, out ignoredExtra), "Invalid sample time must not scan");

        var expiry = new TransientProjectileWindowSchedule();
        Require(expiry.Request(1f, true), "Expiry setup failed");
        Require(!expiry.TryTakeScan(2.1f, false, out ignoredExtra) && expiry.expiredWindows == 1,
                "A delayed update must expire a burst without catch-up scans");
        Require(!expiry.TryTakeScan(2.1f, false, out ignoredExtra) && expiry.expiredWindows == 1,
                "Repeated same-time call must not rescan or double-expire");

        var cadence = new TransientProjectileWindowSchedule();
        Require(cadence.Request(10, true), "Cadence setup failed");
        Require(!cadence.TryTakeScan(10.049f, false, out ignoredExtra), "Window scanned before its cadence");
        Require(cadence.TryTakeScan(10.05f, false, out ignoredExtra) && ignoredExtra, "First extra sample was not admitted");
        Require(!cadence.TryTakeScan(10.05f, false, out ignoredExtra), "Same world timestamp caused a duplicate scan");
        Require(cadence.TryTakeScan(10.10f, false, out ignoredExtra), "Next cadence sample was not admitted");
        Require(Math.Abs(cadence.maximumGapWorldSeconds - .05f) < .0001f,
                "Maximum inter-sample gap should use world-clock seconds");

        var budget = new TransientProjectileWindowSchedule();
        int totalScans = DriveWindow(budget, 0);
        totalScans += DriveWindow(budget, 10, true);
        totalScans += DriveWindow(budget, 20);
        Require(!budget.Request(30, true), "Fourth request should be dropped after three accepted windows");
        Require(budget.requests == 4 && budget.accepted == 3 && budget.droppedRequests == 1,
                "Request/accepted/drop counters should be distinct");
        Require(totalScans == 60 && budget.scans == 60 && budget.extraScans == 59 &&
                    budget.extraScans <= TransientProjectileWindowSchedule.MaximumExtraScans,
                "Three one-second windows must stay within sixty extra scans; baseline overlap is not extra: " +
                    totalScans + "/" + budget.scans + "/" + budget.extraScans);
        Require(budget.completedWindows == 3 && budget.scanBudgetDrops == 0,
                "Normal windows should complete without exhausting the defensive scan cap");

        var baseline = new TransientProjectileWindowSchedule();
        Require(baseline.Request(0, true), "Baseline-overlap setup failed");
        Require(baseline.TryTakeScan(.05f, true, out ignoredExtra) && !ignoredExtra &&
                    baseline.scans == 1 && baseline.extraScans == 0,
                "A baseline scan overlapping the window must not count as an extra scan");

        var betweenCadence = new TransientProjectileWindowSchedule();
        Require(betweenCadence.Request(.99f, true), "Between-cadence window setup failed");
        Require(betweenCadence.TryTakeScan(1f, true, out ignoredExtra) && !ignoredExtra &&
                    betweenCadence.scans == 1 && betweenCadence.extraScans == 0,
                "A baseline scan before the .05 deadline must still count as an in-window scan");
        Require(!betweenCadence.TryTakeScan(1f, true, out ignoredExtra) &&
                    !betweenCadence.TryTakeScan(1.02f, false, out ignoredExtra) &&
                    betweenCadence.scans == 1,
                "Baseline overlap must retain same-time and next-cadence guards");
        Console.WriteLine("PASS: transient projectile window policy contracts");
        return 0;
    }
}
