using System;
using System.Linq;
using System.Reflection;
using RoR2;
using RoR2.Skills;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Exact-editor fixture for routing and ownership only. Synthetic input and
// readiness do not prove native skill execution, authority callbacks, or gameplay.
public static class SurvivorSkillInputHost
{
    static readonly BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

    sealed class AlwaysReadySkillDef : SkillDef
    {
        public int checks;
        public override bool CanExecute(GenericSkill skillSlot)
        {
            checks++;
            return true;
        }
    }

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    static void Set(object target, string property, object value)
    {
        var field = target.GetType().GetField("<" + property + ">k__BackingField", Instance);
        Require(field != null, "Original fixture field changed: " + property);
        field.SetValue(target, value);
    }

    static void FixedInput(NovaInputBridge bridge)
    {
        var method = typeof(NovaInputBridge).GetMethod("FixedUpdate", Instance);
        Require(method != null, "Nova bridge fixed input method missing");
        method.Invoke(bridge, null);
    }

    static void PublishAllRequests(NovaInputBridge bridge)
    {
        bridge.diagnosticPrimary = bridge.diagnosticSecondary = bridge.diagnosticUtility = bridge.diagnosticSpecial = true;
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Require idle editor without a gameplay session");

        var root = new GameObject("Owned survivor skill input coverage fixture");
        root.SetActive(false);
        var definitions = new SkillDef[4];
        AlwaysReadySkillDef replacementDefinition = null;
        SurvivorSkillObserver observer = null;
        SurvivorSkillInputCoverage coverage = null;
        SurvivorSkillInputCoverage partial = null;
        SurvivorSkillInputCoverage foreign = null;
        SurvivorSkillInputCoverage manual = null;
        SurvivorSkillInputCoverage bounded = null;
        SurvivorSkillInputCoverage duration = null;
        try
        {
            var body = root.AddComponent<CharacterBody>();
            var bank = root.AddComponent<InputBankTest>();
            var health = root.AddComponent<HealthComponent>();
            var locator = root.AddComponent<SkillLocator>();
            var bridge = root.AddComponent<NovaInputBridge>();
            Set(body, "inputBank", bank);
            Set(body, "healthComponent", health);
            Set(body, "skillLocator", locator);
            health.health = 100;
            bridge.bank = bank;
            bridge.mapping = new NovaInputBridge.Mapping();
            bridge.diagnosticInput = true;
            PublishAllRequests(bridge);

            var skills = Enumerable.Range(0, 4)
                             .Select(
                                 _ => root.AddComponent<GenericSkill>())
                             .ToArray();
            for (int i = 0; i < skills.Length; i++)
            {
                definitions[i] = ScriptableObject.CreateInstance<AlwaysReadySkillDef>();
                ((ScriptableObject)definitions[i]).name = "CoverageFixtureSkill" + i;
                Set(skills[i], "skillDef", definitions[i]);
            }
            locator.primary = skills[0];
            locator.secondary = skills[1];
            locator.utility = skills[2];
            locator.special = skills[3];
            observer = new SurvivorSkillObserver(body);

            // Reassign the canonical primary after observer setup. The owner
            // must resolve the current locator component when it requests input.
            var replacementPrimary = root.AddComponent<GenericSkill>();
            replacementDefinition = ScriptableObject.CreateInstance<AlwaysReadySkillDef>();
            ((ScriptableObject)replacementDefinition).name = "CoverageFixtureReplacementPrimary";
            Set(replacementPrimary, "skillDef", replacementDefinition);
            locator.primary = replacementPrimary;

            coverage = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            // This edge predates the pulse and must not be attributed to it.
            bank.skill1.PushState(true);
            coverage.Apply(10f);
            Require(coverage.reportData.requests == 1 && coverage.reportData.slots[0].eligibleSamples == 1 &&
                        coverage.reportData.slots[0].requests == 1 && bridge.diagnosticPrimary && !bridge.diagnosticSecondary &&
                        !bridge.diagnosticUtility && !bridge.diagnosticSpecial && replacementDefinition.checks == 1 &&
                        ((AlwaysReadySkillDef)definitions[0]).checks == 0,
                    "Coverage pulse did not resolve and isolate the current eligible canonical slot");

            coverage.Apply(10.01f);
            Require(bank.skill1.justPressed && coverage.reportData.slots[0].inputBankEdges == 0,
                    "Preexisting button edge was attributed before a new bridge fixed tick");
            bank.skill1.PushState(false);
            FixedInput(bridge);
            Require(bank.skill1.justPressed && !bank.skill2.down && !bank.skill3.down && !bank.skill4.down,
                    "Ordinary input bridge did not route the exclusive diagnostic pulse");
            PublishAllRequests(bridge);
            coverage.Apply(10.02f);
            Require(coverage.reportData.slots[0].inputBankEdges == 1, "Observed input-bank edge was not attributed exactly once");
            PublishAllRequests(bridge);
            coverage.Apply(10.3f);
            Require(coverage.reportData.active && coverage.reportData.requests == 1 && bridge.diagnosticPrimary &&
                        bridge.diagnosticSecondary && bridge.diagnosticUtility && bridge.diagnosticSpecial,
                    "Pulse expiry did not preserve fresh ordinary producer values");

            partial = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            partial.Apply(11f);
            Require(partial.reportData.requests == 1 && bridge.diagnosticPrimary && !bridge.diagnosticSecondary &&
                        !bridge.diagnosticUtility && !bridge.diagnosticSpecial,
                    "Partial-cleanup fixture did not acquire its exclusive pulse");
            bank.skill2.PushState(true);
            partial.ReleaseAll();
            Require(bank.skill2.down && bridge.diagnosticPrimary && bridge.diagnosticSecondary && bridge.diagnosticUtility &&
                        bridge.diagnosticSpecial,
                    "Partial release changed input-bank state or failed to restore the matching producer snapshot");
            partial.Dispose();
            partial = null;

            foreign = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            PublishAllRequests(bridge);
            foreign.Apply(18f);
            bridge.diagnosticPrimary = false;
            bridge.diagnosticSecondary = false;
            bridge.diagnosticUtility = true;
            bridge.diagnosticSpecial = false;
            foreign.ReleaseAll();
            Require(!bridge.diagnosticPrimary && !bridge.diagnosticSecondary && bridge.diagnosticUtility && !bridge.diagnosticSpecial &&
                        bank.skill2.down,
                    "Release overwrote foreign producer changes or touched input-bank state");
            foreign.Dispose();
            foreign = null;

            manual = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            PublishAllRequests(bridge);
            manual.Apply(24f);
            bridge.diagnosticInput = false;
            bridge.diagnosticSecondary = false;
            manual.ReleaseAll();
            Require(!bridge.diagnosticSecondary && bank.skill2.down, "Manual takeover release overwrote a foreign request or bank state");
            manual.Dispose();
            manual = null;
            bridge.diagnosticInput = true;

            // Synthetic observer counts check that the owner terminates honestly;
            // this fixture does not invoke ForceSkillActivatedAction or a state.
            foreach (var slot in observer.report.slots)
            {
                slot.authorityActivations = 1;
                slot.serverActivations = 1;
            }
            coverage.Apply(10.4f);
            Require(coverage.reportData.completed && coverage.reportData.outcome == "all-canonical-callbacks-observed",
                    "Coverage did not stop when all canonical callback evidence appeared");
            coverage.Dispose();
            coverage.Dispose();
            Require(coverage.reportData.cleaned &&
                        typeof(SurvivorSkillInputCoverage).GetField("body", Instance).GetValue(coverage) == null &&
                        typeof(SurvivorSkillInputCoverage).GetField("bridge", Instance).GetValue(coverage) == null &&
                        typeof(SurvivorSkillInputCoverage).GetField("observed", Instance).GetValue(coverage) == null,
                    "Coverage owner retained live body, bridge, or observer references after disposal");

            foreach (var slot in observer.report.slots)
                slot.authorityActivations = slot.serverActivations = 0;
            bounded = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            bounded.Apply(100f);
            for (int request = 1; request < SurvivorSkillInputCoverage.MaximumRequests; request++)
            {
                PublishAllRequests(bridge);
                bounded.Apply(100f + (request - 1) * SurvivorSkillInputCoverage.RequestIntervalSeconds + .3f);
                PublishAllRequests(bridge);
                bounded.Apply(100f + request * SurvivorSkillInputCoverage.RequestIntervalSeconds);
            }
            PublishAllRequests(bridge);
            bounded.Apply(100f + (SurvivorSkillInputCoverage.MaximumRequests - 1) * SurvivorSkillInputCoverage.RequestIntervalSeconds +
                          .3f);
            PublishAllRequests(bridge);
            bounded.Apply(100f + SurvivorSkillInputCoverage.MaximumRequests * SurvivorSkillInputCoverage.RequestIntervalSeconds);
            Require(bounded.reportData.requests == SurvivorSkillInputCoverage.MaximumRequests && bounded.reportData.completed &&
                        bounded.reportData.outcome == "request-budget-exhausted",
                    "Coverage exceeded or misreported the pulse request budget");
            bounded.Dispose();
            bounded = null;

            duration = new SurvivorSkillInputCoverage(body, bridge, observer.report);
            PublishAllRequests(bridge);
            duration.Apply(200f);
            PublishAllRequests(bridge);
            duration.Apply(200f + SurvivorSkillInputCoverage.MaximumSeconds);
            Require(duration.reportData.requests == 1 && duration.reportData.completed &&
                        duration.reportData.outcome == "duration-exhausted" &&
                        duration.reportData.elapsedSeconds == SurvivorSkillInputCoverage.MaximumSeconds,
                    "Coverage exceeded or misreported its enabled-time bound");
            duration.Dispose();
            duration = null;

            return new { success = true,
                         exclusiveRouting = true,
                         dynamicCanonicalLookup = true,
                         inputBankEdgeObserved = true,
                         freshProducerPreservedAtExpiry = true,
                         partialReleaseAndForeignStatePreserved = true,
                         completionOnCallbacks = true,
                         requestBudget = SurvivorSkillInputCoverage.MaximumRequests,
                         durationBudgetSeconds = SurvivorSkillInputCoverage.MaximumSeconds,
                         disposedReferencesReleased = true,
                         nativeSkillExecutionTested = false };
        }
        finally
        {
            duration?.Dispose();
            bounded?.Dispose();
            manual?.Dispose();
            foreign?.Dispose();
            partial?.Dispose();
            coverage?.Dispose();
            observer?.Dispose();
            UnityEngine.Object.DestroyImmediate(root);
            if (replacementDefinition)
                UnityEngine.Object.DestroyImmediate(replacementDefinition);
            foreach (var definition in definitions)
                if (definition)
                    UnityEngine.Object.DestroyImmediate(definition);
        }
    }
}
