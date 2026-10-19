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

    static void SetSkillDefs(SkillDef[] definitions)
    {
        var method = typeof(SkillCatalog).GetMethod("SetSkillDefs", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        Require(method != null, "Skill catalog registration owner changed");
        method.Invoke(null, new object[] { definitions });
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

        for (int selected = 0; selected < 4; selected++)
            for (int button = 0; button < 4; button++)
            {
                bool pulse = NovaInputBridge.SkillInputRequest(true, true, true, selected, button, true, true);
                Require(pulse == (selected == button), "Isolated bridge sink did not route exactly the selected slot");
                Require(!NovaInputBridge.SkillInputRequest(true, true, false, selected, button, true, true),
                        "Isolated bridge sink emitted a skill request outside the owner pulse");
            }
        Require(NovaInputBridge.SkillInputRequest(true, false, false, -1, 2, true, false) &&
                    NovaInputBridge.SkillInputRequest(false, false, false, -1, 2, false, true),
                "Default diagnostic or physical skill input route changed");
        Require(!NovaInputBridge.EquipmentInputRequest(true, true, true, false) &&
                    NovaInputBridge.EquipmentInputRequest(true, false, true, false) &&
                    NovaInputBridge.EquipmentInputRequest(true, true, false, true),
                "Isolated automatic equipment suppression changed default or touch requests");
        Require(SurvivorSkillInputCoverage.ParseIsolationSlot("utility") == 2,
                "Canonical isolated slot parser changed");
        bool invalidIsolationSlotRefused = false;
        try { SurvivorSkillInputCoverage.ParseIsolationSlot("Utility"); }
        catch (ArgumentException) { invalidIsolationSlotRefused = true; }
        Require(invalidIsolationSlotRefused, "Noncanonical isolated slot was accepted");
        Require(SurvivorSkillInputCoverage.IsolationWindowOutcome(
                    SurvivorSkillInputCoverage.IsolationMaximumSeconds - 1, true) == null &&
                    SurvivorSkillInputCoverage.IsolationWindowOutcome(
                        SurvivorSkillInputCoverage.IsolationMaximumSeconds, true) == "isolated-slot-observation-complete" &&
                    SurvivorSkillInputCoverage.IsolationWindowOutcome(
                        SurvivorSkillInputCoverage.IsolationMaximumSeconds, false) == "duration-exhausted",
                "Production isolation window decision did not wait for the full bound or refuse a missing callback pair");
        for (int selected = 0; selected < 4; selected++)
            Require(!NovaInputBridge.SkillInputRequest(true, true, false, selected, selected, true, true),
                    "An attested selected callback must leave the isolated skill-input mask neutral");

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
        SurvivorSkillInputCoverage isolated = null;
        SurvivorSkillInputCoverage isolatedTimeout = null;
        SurvivorSkillInputCoverage isolatedTakeover = null;
        SkillDef[] previousSkillDefs = null;
        bool ownsSyntheticSkillCatalog = false;
        AlwaysReadySkillDef syntheticCatalogSkill = null;
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

            // A rendered-frame Neutral is insufficient: later FixedUpdate must
            // suppress stale automatic producer values at the owned sink.
            bridge.movement = Vector2.right;
            bridge.diagnosticAim = Vector3.right;
            bridge.diagnosticEquipment = true;
            bridge.diagnosticSprint = true;
            bridge.diagnosticInteract = true;
            bridge.DiagnosticJump(true);
            bridge.Neutral();
            bridge.diagnosticPrimary = bridge.diagnosticSecondary = bridge.diagnosticUtility = bridge.diagnosticSpecial = true;
            bridge.movement = Vector2.right;
            bridge.aim = Vector2.right;
            bank.aimDirection = Vector3.up;
            bridge.diagnosticAim = Vector3.right;
            bridge.diagnosticSprint = bridge.diagnosticInteract = bridge.diagnosticEquipment = true;
            bridge.DiagnosticJump(true);
            Require(bridge.SetManualMoonAutomaticHold(true), "Diagnostic manual-boundary hold was not acquired");
            FixedInput(bridge);
            Require(!bank.skill1.down && !bank.skill2.down && !bank.skill3.down && !bank.skill4.down &&
                        !bank.jump.down && !bank.interact.down && !bank.sprint.down && !bank.activateEquipment.down &&
                        bank.moveVector == Vector3.zero && bank.aimDirection == bank.transform.forward &&
                        bridge.manualMoonNeutralFixedTicks == 1 &&
                        bridge.diagnosticPrimary && bridge.diagnosticInteract,
                    "FixedUpdate reasserted stale automatic requests after Neutral while the hold was owned");
            bridge.touchEquipment = true;
            FixedInput(bridge);
            Require(bank.activateEquipment.down && bridge.manualMoonNeutralFixedTicks == 2,
                    "The automatic hold consumed the independent manual touch-equipment request");
            Require(!NovaInputBridge.ShouldHoldAutomaticDiagnosticInput(false, true) &&
                        !NovaInputBridge.ShouldHoldAutomaticDiagnosticInput(true, false),
                    "A non-diagnostic/manual input path was classified as held");
            bridge.touchEquipment = true;
            bank.skill1.PushState(true);
            bridge.diagnosticInput = false;
            Require(!bridge.SetManualMoonAutomaticHold(true) && bank.skill1.down && bridge.touchEquipment &&
                        !bridge.diagnosticPrimary && !bridge.diagnosticInteract,
                    "Releasing the diagnostic hold changed physical bank/touch state or retained held automatic requests");
            bridge.diagnosticInput = true;
            bridge.SetManualMoonAutomaticHold(false);
            bridge.touchEquipment = false;
            bank.skill1.PushState(false);
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

            observer.Dispose();
            observer = null;
            previousSkillDefs = SkillCatalog.allSkillDefs != null
                                    ? SkillCatalog.allSkillDefs.ToArray() : new SkillDef[0];
            syntheticCatalogSkill = ScriptableObject.CreateInstance<AlwaysReadySkillDef>();
            ((ScriptableObject)syntheticCatalogSkill).name = "IsolatedOwnerCatalogSkill";
            ownsSyntheticSkillCatalog = true;
            SetSkillDefs(previousSkillDefs.Concat(new SkillDef[] { syntheticCatalogSkill }).ToArray());
            var nativeDefinition = (SkillDef)syntheticCatalogSkill;
            foreach (var skill in root.GetComponents<GenericSkill>())
            {
                Set(skill, "skillDef", nativeDefinition);
            }
            observer = new SurvivorSkillObserver(body);
            int nativeSkillIndex = nativeDefinition.skillIndex;
            observer.report.skillVariantInventory = new SurvivorSkillObserver.SkillVariantInventoryReport {
                status = "available", selectionSource = "synthetic-host-live-catalog-contract",
                components = observer.report.components.Where(row => row != null && row.present)
                    .Select(row => new SurvivorSkillObserver.SkillVariantComponentReport {
                        componentIndex = row.componentIndex, familyCatalogIndex = 0,
                        selectedLoadoutVariantIndex = 0, selectedLoadoutSkillCatalogIndex = nativeSkillIndex,
                        runtimeSkillCatalogIndex = nativeSkillIndex,
                        runtimeDefinitionStatus = "matches-selected-native-loadout",
                        variants = new[] { new SurvivorSkillObserver.SkillVariantEntryReport {
                            variantIndex = 0, skillCatalogIndex = nativeSkillIndex,
                            skillName = ((ScriptableObject)nativeDefinition).name
                        } }
                    }).ToArray()
            };
            foreach (var slot in observer.report.slots)
            {
                slot.declaredActivationState = "EntityStates.GenericCharacterMain";
                slot.machineState = "EntityStates.GenericCharacterMain";
            }
            bridge.diagnosticInput = true;
            bridge.inputNeutralRevision = 0;
            bank.skill1.PushState(false);
            bank.skill2.PushState(false);
            bank.skill3.PushState(false);
            bank.skill4.PushState(false);
            PublishAllRequests(bridge);
            isolated = new SurvivorSkillInputCoverage(body, bridge, observer.report, "utility");
            FixedInput(bridge);
            isolated.Apply(0f);
            Require(isolated.reportData.requests == 1 && bridge.isolatedDiagnosticSkillPulse,
                    "Isolated owner did not produce its selected native input request");
            FixedInput(bridge);
            isolated.Apply(0.01f);
            isolated.Apply(0.3f);
            Require(isolated.reportData.slots[2].inputBankEdges == 1,
                    "Isolated owner did not observe the later fixed-tick input-bank edge");
            observer.report.slots[2].authorityActivations = 1;
            observer.report.slots[2].serverActivations = 1;
            isolated.Apply(6f);
            Require(isolated.reportData.selectedCallbacksObserved && !bridge.isolatedDiagnosticSkillPulse,
                    "Isolated owner did not match the fresh selected callback pair after its input edge");
            isolated.Apply(SurvivorSkillInputCoverage.IsolationMaximumSeconds);
            Require(isolated.reportData.completed && isolated.reportData.selectedCallbacksObserved &&
                        isolated.reportData.outcome == "isolated-slot-observation-complete" &&
                        bridge.isolatedDiagnosticSkillInput && !bridge.isolatedDiagnosticSkillPulse,
                    "Selected callback pair did not finish the real isolated owner at its bound while preserving the mask");
            for (int selected = 0; selected < 4; selected++)
                Require(!NovaInputBridge.SkillInputRequest(true, true, bridge.isolatedDiagnosticSkillPulse,
                            bridge.isolatedDiagnosticSkillSlot, selected, true, true),
                        "Completed isolated observation leaked a diagnostic skill request");
            isolated.Dispose();
            isolated = null;

            isolatedTimeout = new SurvivorSkillInputCoverage(body, bridge, observer.report, "utility");
            isolatedTimeout.Apply(0f);
            isolatedTimeout.Apply(SurvivorSkillInputCoverage.IsolationMaximumSeconds);
            Require(isolatedTimeout.reportData.completed && !isolatedTimeout.reportData.selectedCallbacksObserved &&
                        isolatedTimeout.reportData.outcome == "duration-exhausted" &&
                        bridge.isolatedDiagnosticSkillInput && !bridge.isolatedDiagnosticSkillPulse,
                    "Isolated timeout did not refuse while keeping the skill-input mask active");
            isolatedTimeout.Dispose();
            isolatedTimeout = null;

            isolatedTakeover = new SurvivorSkillInputCoverage(body, bridge, observer.report, "utility");
            isolatedTakeover.Apply(0f);
            bridge.diagnosticInput = false;
            isolatedTakeover.Apply(0.1f);
            Require(isolatedTakeover.reportData.completed && isolatedTakeover.reportData.outcome == "diagnostic-input-yielded" &&
                        !bridge.isolatedDiagnosticSkillInput && !bridge.isolatedDiagnosticSkillPulse,
                    "Native input takeover did not release the isolated owner mask");
            isolatedTakeover.Dispose();
            isolatedTakeover = null;
            bridge.diagnosticInput = true;

            return new { success = true,
                         isolatedBridgeMask = true,
                         automaticEquipmentSuppressed = true,
                         touchEquipmentPreserved = true,
                         manualMoonFixedUpdateHold = true,
                         defaultInputRoutePreserved = true,
                         invalidSlotRefused = true,
                         exclusiveRouting = true,
                         dynamicCanonicalLookup = true,
                         inputBankEdgeObserved = true,
                         freshProducerPreservedAtExpiry = true,
                         partialReleaseAndForeignStatePreserved = true,
                         completionOnCallbacks = true,
                         isolatedOwnerWindowAndMask = true,
                         isolatedTimeoutRefusal = true,
                         isolatedManualTakeoverRelease = true,
                         requestBudget = SurvivorSkillInputCoverage.MaximumRequests,
                         durationBudgetSeconds = SurvivorSkillInputCoverage.MaximumSeconds,
                         disposedReferencesReleased = true,
                         nativeSkillExecutionTested = false };
        }
        finally
        {
            duration?.Dispose();
            isolated?.Dispose();
            isolatedTimeout?.Dispose();
            isolatedTakeover?.Dispose();
            bounded?.Dispose();
            manual?.Dispose();
            foreign?.Dispose();
            partial?.Dispose();
            coverage?.Dispose();
            observer?.Dispose();
            observer = null;
            if (ownsSyntheticSkillCatalog)
            {
                SetSkillDefs(previousSkillDefs);
                ownsSyntheticSkillCatalog = false;
            }
            UnityEngine.Object.DestroyImmediate(root);
            if (replacementDefinition)
                UnityEngine.Object.DestroyImmediate(replacementDefinition);
            if (syntheticCatalogSkill)
                UnityEngine.Object.DestroyImmediate(syntheticCatalogSkill);
            foreach (var definition in definitions)
                if (definition)
                    UnityEngine.Object.DestroyImmediate(definition);
        }
    }
}
