using System;
using System.Collections.Generic;
using UnityEngine;

namespace UnityEngine
{
    enum LogType { Log }
    enum LogOption { NoStacktrace }
    static class Time { public static float realtimeSinceStartup = 10; public static int frameCount = 3; }
    static class Debug
    {
        public static readonly List<string> messages = new List<string>();
        public static void LogFormat(LogType type, LogOption option, object context, string format, string value)
        { messages.Add(value); }
    }
}

sealed class PortSession
{
    public sealed class Results { public string initializationStep; }
    public sealed class Report
    {
        public Results results = new Results();
        public string firstFailure, firstFailurePhase, phase = "integrated-results-context";
        public int assertions;
    }
    public Report r = new Report();
    public int saves;
    public bool failSave;
    public string savedStep, savedFailure;
    public void Save()
    {
        saves++;
        if (failSave) throw new Exception("authored write failure");
        savedStep = r.results.initializationStep;
        savedFailure = r.firstFailure;
    }
    // CHECK
    sealed class ResultsOwner
    {
        readonly PortSession coordinator;
        public ResultsOwner(PortSession coordinator) { this.coordinator = coordinator; }
        // RESULTS_STEP
        public void Step(string value) { ResultsStep(value); }
    }
    static void Need(bool condition, string message) { if (!condition) throw new Exception(message); }
    static void Main()
    {
        var session = new PortSession();
        var owner = new ResultsOwner(session);
        owner.Step("key-item-statistics");
        owner.Step("item-groups");
        owner.Step("run-identity");
        Need(session.saves == 0 && session.r.results.initializationStep == "run-identity", "markers wrote intermediate reports");
        Need(Debug.messages.Count == 3 && Debug.messages[0].Contains("step=key-item-statistics ") &&
             Debug.messages[1].Contains("step=item-groups ") && Debug.messages[2].Contains("step=run-identity "), "step logs changed order");
        session.Save();
        Need(session.saves == 1 && session.savedStep == "run-identity", "completion lost latest step");
        owner.Step("item-relationships");
        try { session.Check(false, "authored catalog refusal"); throw new Exception("predicate accepted"); }
        catch (Exception error) { Need(error.Message == "authored catalog refusal", "predicate changed"); }
        Need(session.saves == 2 && session.savedStep == "item-relationships" &&
             session.savedFailure == "authored catalog refusal" && session.r.firstFailurePhase == session.r.phase, "first failure lost checkpoint");
        var broken = new PortSession { failSave = true };
        new ResultsOwner(broken).Step("ending-catalog");
        try { broken.Check(false, "authored ending refusal"); throw new Exception("predicate accepted"); }
        catch (Exception error) { Need(error.Message == "authored ending refusal", "write failure masked predicate"); }
        Need(broken.saves == 1 && broken.r.results.initializationStep == "ending-catalog" &&
             broken.r.firstFailure == "authored ending refusal", "write failure lost in-memory checkpoint");
        Console.WriteLine("results step persistence PASS");
    }
}
