// Subsystem: input/skill coverage (diagnostic only). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: constructed after the native skill observer; Apply after the world input producer;
// teardown before the owned body/world is released.
using System;
using RoR2;
using RoR2.Skills;
using UnityEngine;

// Supplies short ordinary input pulses for canonical slots that have not yet
// produced both native observer callbacks. It never executes a skill or changes
// any game state directly.
public sealed class SurvivorSkillInputCoverage : IDisposable
{
    public const int MaximumSeconds = 120;
    public const int MaximumRequests = 12;
    public const float RequestIntervalSeconds = 6f;
    public const float PulseSeconds = .25f;
    public const int IsolationMaximumSeconds = 60;
    public const int IsolationMaximumRequests = 10;

    [Serializable]
    public sealed class SlotCoverage
    {
        public string slot;
        public int eligibleSamples, requests, inputBankEdges;
        public int authorityBefore, authorityAfter, serverBefore, serverAfter;
    }

    [Serializable]
    public sealed class Report
    {
        public bool active, completed, cleaned, selectedCallbacksObserved;
        public int requests;
        public float elapsedSeconds;
        public string outcome, mode, isolationSlot, selectedDefinition, selectedActivationState, selectedMachineState;
        public int selectedComponentIndex = -1, selectedFamilyCatalogIndex = -1, selectedVariantIndex = -1,
                   selectedSkillCatalogIndex = -1, runtimeSkillCatalogIndex = -1;
        // False/zero/empty in ordinary checks. This subreport is populated only
        // by the explicit Toolbot offhand selector.
        public bool toolbotOffhandRequested, toolbotOffhandStanceObserved, toolbotOffhandOverrideObserved,
                    toolbotOffhandWeapon2Observed, toolbotOffhandBuzzsawStateObserved;
        public int toolbotOffhandPhase, toolbotOffhandRequests, toolbotOffhandSpecialAuthorityBefore,
                   toolbotOffhandSpecialServerBefore, toolbotOffhandSecondaryAuthorityBefore,
                   toolbotOffhandSecondaryServerBefore, toolbotOffhandBodyDamageEventsBeforeSecondary,
                   toolbotOffhandBodyDamageEventsAtStop, toolbotOffhandDamageFactsBeforeSecondary,
                   toolbotOffhandDamageFactsAtStop;
        public float toolbotOffhandSpecialRequestSeconds, toolbotOffhandSpecialEdgeSeconds,
                     toolbotOffhandStanceSeconds, toolbotOffhandReadySeconds,
                     toolbotOffhandSecondaryRequestSeconds, toolbotOffhandSecondaryEdgeSeconds,
                     toolbotOffhandBuzzsawStateSeconds;
        public string toolbotOffhandOutcome, toolbotOffhandBodyState, toolbotOffhandSpecialDefinition,
                      toolbotOffhandSecondaryDefinition, toolbotOffhandSecondaryActivationMachine,
                      toolbotOffhandWeapon2State;
        public SlotCoverage[] slots;
    }

    static readonly string[] SlotNames = { "primary", "secondary", "utility", "special" };

    CharacterBody body;
    NovaInputBridge bridge;
    SurvivorSkillObserver.Report observed;
    SurvivorCombatOutputObserver.Report combatOutput;
    readonly Report report;
    readonly bool[] producerRequests = new bool[4];
    readonly bool[] lastOverlay = new bool[4];
    float beganAt = float.NaN;
    float pulseUntil;
    float nextRequestAt;
    int target = -1;
    int cursor = -1;
    int pendingSlot = -1;
    int lastEdgeTick = int.MinValue;
    bool pulseActive;
    int isolationTarget = -1;
    int selectedComponentInstanceId;
    readonly bool toolbotOffhandMode;
    GenericSkill[] toolbotSkillComponents;
    float toolbotPhaseBeganAt, toolbotPhaseEnteredAt, toolbotDeadline, toolbotPulseUntil;
    int toolbotPulseStartTick;
    int toolbotSpecialAuthorityBefore, toolbotSpecialServerBefore;
    int toolbotSecondaryAuthorityBefore, toolbotSecondaryServerBefore;
    bool toolbotPulseActive, toolbotSpecialEdgeObserved, toolbotSecondaryEdgeObserved,
         toolbotSpecialPulseStarted, toolbotSecondaryPulseStarted;
    int lastNeutralRevision;
    int requestEdgeCount;
    bool isolationRequestPending;

    public Report reportData => report;

    public static int ParseIsolationSlot(string slot)
    {
        for (int i = 0; i < SlotNames.Length; i++)
            if (string.Equals(slot, SlotNames[i], StringComparison.Ordinal))
                return i;
        throw new ArgumentException("Isolated skill slot must be primary, secondary, utility, or special", nameof(slot));
    }

    public static string IsolationWindowOutcome(float elapsedSeconds, bool selectedCallbacksObserved)
    {
        if (float.IsNaN(elapsedSeconds) || float.IsInfinity(elapsedSeconds) || elapsedSeconds < IsolationMaximumSeconds)
            return null;
        return selectedCallbacksObserved ? "isolated-slot-observation-complete" : "duration-exhausted";
    }

    // Shared source policy used by the live sequence and extracted host fixture.
    // Phases: special-ready, special-callback, stance-ready, secondary-ready,
    // secondary-callback, Buzzsaw-state, complete. No phase manufactures an event.
    public static int AdvanceToolbotOffhandPhase(int phase, bool specialPulseStarted, bool specialInputEdge,
        bool specialCallbacks, bool exactDualWieldState, bool effectiveOffhandOverride, bool weapon2Present,
        bool secondaryPulseStarted, bool secondaryInputEdge, bool secondaryCallbacks, bool buzzsawOnWeapon2)
    {
        if (phase == 0 && specialPulseStarted) return 1;
        if (phase == 1 && specialInputEdge && specialCallbacks) return 2;
        if (phase == 2 && exactDualWieldState && effectiveOffhandOverride && weapon2Present) return 3;
        if (phase == 3 && secondaryPulseStarted) return 4;
        if (phase == 4 && secondaryInputEdge && secondaryCallbacks) return 5;
        if (phase == 5 && buzzsawOnWeapon2) return 6;
        return phase;
    }

    public SurvivorSkillInputCoverage(CharacterBody ownedBody, NovaInputBridge ownedBridge,
                                      SurvivorSkillObserver.Report observerReport, string isolatedSlot = null,
                                      bool toolbotOffhand = false, SurvivorCombatOutputObserver.Report combatReport = null)
    {
        if (!ownedBody || !ownedBody.skillLocator || !ownedBridge || observerReport == null || observerReport.slots == null ||
            observerReport.slots.Length != 4)
            throw new ArgumentException("Owned body, input bridge and four-slot observer report are required");
        if (ownedBody.gameObject != ownedBridge.gameObject || !ownedBody.inputBank || ownedBridge.bank != ownedBody.inputBank)
            throw new ArgumentException("The bridge and original input bank must belong to the owned body");

        body = ownedBody;
        bridge = ownedBridge;
        toolbotOffhandMode = toolbotOffhand;
        observed = observerReport;
        combatOutput = combatReport;
        isolationTarget = string.IsNullOrEmpty(isolatedSlot) ? -1 : ParseIsolationSlot(isolatedSlot);
        if (toolbotOffhandMode && isolationTarget >= 0)
            throw new ArgumentException("Toolbot offhand diagnostic cannot be combined with a single-slot isolation selector");
        report = new Report { active = false, outcome = "waiting-for-diagnostic-input",
                              mode = toolbotOffhandMode ? "toolbot-offhand-sequence" : isolationTarget < 0 ? "all-four-slots" : "isolated-slot",
                              isolationSlot = isolationTarget < 0 ? "" : SlotNames[isolationTarget],
                              toolbotOffhandRequested = toolbotOffhandMode,
                              toolbotOffhandOutcome = toolbotOffhandMode ? "waiting-for-owned-live-diagnostic-input" : "",
                              slots = new SlotCoverage[4] };
        for (int i = 0; i < 4; i++)
        {
            if (!ownedBody.skillLocator.GetSkill((SkillSlot)i))
                throw new ArgumentException("Original canonical skill slot missing: " + SlotNames[i], nameof(ownedBody));
            var slot = observerReport.slots[i];
            report.slots[i] = new SlotCoverage { slot = SlotNames[i], authorityBefore = slot.authorityActivations,
                                                 authorityAfter = slot.authorityActivations, serverBefore = slot.serverActivations,
                                                 serverAfter = slot.serverActivations };
        }
        lastNeutralRevision = ownedBridge.inputNeutralRevision;
        if (toolbotOffhandMode)
        {
            CaptureToolbotOffhandIdentity();
            ownedBridge.isolatedDiagnosticSkillInput = true;
            ownedBridge.isolatedDiagnosticSkillSlot = -1;
            ownedBridge.isolatedDiagnosticSkillPulse = false;
        }
        if (isolationTarget >= 0)
        {
            CaptureSelectedIdentity(observerReport, SlotNames[isolationTarget]);
            ownedBridge.isolatedDiagnosticSkillInput = true;
            ownedBridge.isolatedDiagnosticSkillSlot = isolationTarget;
            ownedBridge.isolatedDiagnosticSkillPulse = false;
        }
    }

    // Call after the ordinary world input producer. Only diagnostic bridge
    // requests are overlaid; the bridge's physical-input path is never touched.
    public void Apply(float elapsed)
    {
        if (report.cleaned || report.completed)
            return;
        SyncNativeCallbacks();
        if (toolbotOffhandMode)
        {
            ApplyToolbotOffhand(elapsed);
            return;
        }
        if (float.IsNaN(elapsed) || float.IsInfinity(elapsed) || elapsed < 0)
        {
            Stop("invalid-elapsed-time");
            return;
        }
        if (float.IsNaN(beganAt))
        {
            beganAt = elapsed;
            nextRequestAt = elapsed;
        }
        report.elapsedSeconds = Mathf.Max(0, elapsed - beganAt);

        int durationLimit = isolationTarget >= 0 ? IsolationMaximumSeconds : MaximumSeconds;
        int requestLimit = isolationTarget >= 0 ? IsolationMaximumRequests : MaximumRequests;
        if (report.elapsedSeconds >= durationLimit && isolationTarget < 0)
        {
            Stop("duration-exhausted");
            return;
        }
        if (!OwnsLiveDiagnosticInput())
        {
            if (pulseActive)
                ReleasePulse();
            if (isolationTarget >= 0)
            {
                ReleaseIsolationSink();
                Stop("diagnostic-input-yielded");
                return;
            }
            report.active = false;
            report.outcome = "waiting-for-owned-live-diagnostic-input";
            return;
        }
        report.active = true;

        if (isolationTarget >= 0)
        {
            if (bridge.inputNeutralRevision != lastNeutralRevision)
            {
                lastNeutralRevision = bridge.inputNeutralRevision;
                pulseActive = false;
                target = -1;
                isolationRequestPending = false;
                bridge.isolatedDiagnosticSkillPulse = false;
                report.outcome = "neutralized-request-cancelled";
                nextRequestAt = elapsed;
                return;
            }
            ApplyIsolated(elapsed, requestLimit);
            return;
        }

        if (pulseActive)
        {
            if (elapsed >= pulseUntil)
            {
                ObserveInputBankEdge();
                ReleasePulse(false);
            }
            else
            {
                CaptureFreshProducerRequests();
                ApplyExclusivePulse();
                ObserveInputBankEdge();
            }
            return;
        }

        if (pendingSlot < 0 || !MissingCallback(pendingSlot))
            pendingSlot = FindNextMissingCallbackSlot();
        int pending = pendingSlot;
        if (pending < 0)
        {
            Stop("all-canonical-callbacks-observed");
            return;
        }
        if (report.requests >= requestLimit)
        {
            Stop("request-budget-exhausted");
            return;
        }
        var skill = body.skillLocator.GetSkill((SkillSlot)pending);
        if (!skill || !skill.enabled || !skill.skillDef)
        {
            if (elapsed >= nextRequestAt)
                AdvanceAfterSkippedSlot(pending, elapsed);
            else
                report.outcome = "waiting-for-selected-slot";
            return;
        }
        // This is a read-only native readiness/interrupt check. It does not
        // execute the skill, spend stock or force a state transition.
        bool eligible = skill.CanExecute();
        if (eligible)
            report.slots[pending].eligibleSamples++;
        if (elapsed < nextRequestAt)
        {
            if (!eligible)
                report.outcome = "waiting-for-native-can-execute";
            else
                report.outcome = "waiting-for-next-request-window";
            return;
        }
        if (!eligible)
        {
            AdvanceAfterSkippedSlot(pending, elapsed);
            report.outcome = "waiting-for-native-can-execute";
            return;
        }

        target = pending;
        cursor = pending;
        pendingSlot = -1;
        nextRequestAt = elapsed + RequestIntervalSeconds;
        pulseUntil = elapsed + PulseSeconds;
        report.requests++;
        report.slots[pending].requests++;
        // Only a button edge produced by a later bridge tick belongs to this
        // pulse. A justPressed bit may still describe input from before it.
        lastEdgeTick = bridge.fixedTicks;
        pulseActive = true;
        CaptureProducerRequests();
        ApplyExclusivePulse();
        report.outcome = "pulse-requested";
    }

    void CaptureSelectedIdentity(SurvivorSkillObserver.Report observerReport, string slotName)
    {
        if (observerReport.skillVariantInventory == null || observerReport.skillVariantInventory.status != "available" ||
            observerReport.components == null)
            throw new ArgumentException("Isolated slot requires exact post-spawn native component and loadout inventory");
        var components = Array.FindAll(observerReport.components, row => row != null && row.present &&
            string.Equals(row.canonicalSlot, slotName, StringComparison.OrdinalIgnoreCase));
        if (components.Length != 1)
            throw new ArgumentException("Isolated slot must resolve to exactly one current canonical GenericSkill component");
        int componentIndex = components[0].componentIndex;
        var catalogs = Array.FindAll(observerReport.skillVariantInventory.components ?? new SurvivorSkillObserver.SkillVariantComponentReport[0],
            row => row != null && row.componentIndex == componentIndex);
        if (catalogs.Length != 1)
            throw new ArgumentException("Isolated slot native family/variant identity is missing or ambiguous");
        var catalog = catalogs[0];
        if (catalog.familyCatalogIndex < 0 || catalog.selectedLoadoutVariantIndex < 0 ||
            catalog.selectedLoadoutSkillCatalogIndex < 0 || catalog.runtimeSkillCatalogIndex < 0 ||
            catalog.runtimeDefinitionStatus != "matches-selected-native-loadout" ||
            catalog.runtimeSkillCatalogIndex != catalog.selectedLoadoutSkillCatalogIndex ||
            string.IsNullOrEmpty(components[0].definition) || catalog.variants == null ||
            catalog.selectedLoadoutVariantIndex >= catalog.variants.Length ||
            catalog.variants[catalog.selectedLoadoutVariantIndex] == null ||
            catalog.variants[catalog.selectedLoadoutVariantIndex].variantIndex != catalog.selectedLoadoutVariantIndex ||
            catalog.variants[catalog.selectedLoadoutVariantIndex].skillCatalogIndex != catalog.selectedLoadoutSkillCatalogIndex)
            throw new ArgumentException("Isolated slot runtime skill differs from the selected native family/variant");
        var slotReport = Array.Find(observerReport.slots, row => row != null && row.slot == slotName);
        if (slotReport == null || string.IsNullOrEmpty(slotReport.declaredActivationState) ||
            string.IsNullOrEmpty(slotReport.machineState))
            throw new ArgumentException("Isolated slot native activation and machine state are unavailable");
        report.selectedComponentIndex = componentIndex;
        selectedComponentInstanceId = components[0].instanceId;
        report.selectedFamilyCatalogIndex = catalog.familyCatalogIndex;
        report.selectedVariantIndex = catalog.selectedLoadoutVariantIndex;
        report.selectedSkillCatalogIndex = catalog.selectedLoadoutSkillCatalogIndex;
        report.runtimeSkillCatalogIndex = catalog.runtimeSkillCatalogIndex;
        report.selectedDefinition = slotReport.definition;
        report.selectedActivationState = slotReport.declaredActivationState;
        report.selectedMachineState = slotReport.machineState;
        var current = body.skillLocator.GetSkill((SkillSlot)isolationTarget);
        if (!current || current.GetInstanceID() != selectedComponentInstanceId || !current.skillDef ||
            current.skillDef.skillIndex != report.selectedSkillCatalogIndex ||
            SkillCatalog.GetSkillDef(report.selectedSkillCatalogIndex) != current.skillDef)
            throw new ArgumentException("Isolated slot does not match the exact current post-spawn GenericSkill/loadout identity");
    }

    void CaptureToolbotOffhandIdentity()
    {
        var inventory = observed.skillVariantInventory;
        if (combatOutput == null)
            throw new ArgumentException("Toolbot offhand sequence requires the existing owned combat-output observer report");
        if (!body || body.bodyIndex != BodyCatalog.FindBodyIndex("ToolbotBody") || inventory == null ||
            inventory.status != "available" || inventory.bodyIndex != (int)body.bodyIndex || inventory.components == null ||
            inventory.components.Length != 5)
            throw new ArgumentException("Toolbot offhand requires the exact live five-component native loadout inventory");
        toolbotSkillComponents = body.GetComponents<GenericSkill>();
        if (toolbotSkillComponents == null || toolbotSkillComponents.Length != 5 ||
            toolbotSkillComponents[1] == null || toolbotSkillComponents[2] == null ||
            toolbotSkillComponents[4] == null || body.skillLocator.primary != toolbotSkillComponents[0] ||
            body.skillLocator.secondary != toolbotSkillComponents[2] || body.skillLocator.special != toolbotSkillComponents[4])
            throw new ArgumentException("Toolbot auxiliary primary or native special component is missing or ambiguous");
        bool primarySelected = ToolbotSelectedComponentMatches(
            0, "ToolbotBodyPrimary1", "ToolbotBodyFireNailgun", 141, 0, 195);
        bool buzzsawSelected = ToolbotSelectedComponentMatches(
            1, "ToolbotBodyPrimary2", "ToolbotBodyFireBuzzsaw", 142, 3, 193);
        bool dualWieldSelected = ToolbotSelectedComponentMatches(
            4, "ToolbotBodySpecialFamily", "ToolbotDualWield", 144, 1, 201);
        bool primaryDefinition = toolbotSkillComponents[0].skillDef &&
            ((ScriptableObject)toolbotSkillComponents[0].skillDef).name == "ToolbotBodyFireNailgun";
        bool buzzsawDefinition = toolbotSkillComponents[1].skillDef &&
            ((ScriptableObject)toolbotSkillComponents[1].skillDef).name == "ToolbotBodyFireBuzzsaw";
        bool dualWieldDefinition = toolbotSkillComponents[4].skillDef &&
            ((ScriptableObject)toolbotSkillComponents[4].skillDef).name == "ToolbotDualWield";
        if (!primarySelected || !buzzsawSelected || !dualWieldSelected ||
            !primaryDefinition || !buzzsawDefinition || !dualWieldDefinition)
            throw new ArgumentException("Toolbot offhand selected-identity refusal: " +
                "primarySelected=" + primarySelected + ", buzzsawSelected=" + buzzsawSelected +
                ", dualWieldSelected=" + dualWieldSelected + ", primaryDefinition=" + primaryDefinition +
                ", buzzsawDefinition=" + buzzsawDefinition + ", dualWieldDefinition=" + dualWieldDefinition +
                "; " + DescribeToolbotComponent(0) + "; " + DescribeToolbotComponent(1) +
                "; " + DescribeToolbotComponent(4));
        var primary = toolbotSkillComponents[0];
        if (!primary || !primary.skillDef || ((ScriptableObject)primary.skillDef).name != "ToolbotBodyFireNailgun")
            throw new ArgumentException("Toolbot offhand diagnostic requires the retained Nailgun primary");
        toolbotDeadline = float.NaN;
        toolbotPhaseEnteredAt = float.NaN;
        report.toolbotOffhandPhase = 0;
        report.toolbotOffhandOutcome = "waiting-for-owned-live-diagnostic-input";
    }

    string DescribeToolbotComponent(int componentIndex)
    {
        var skill = toolbotSkillComponents != null && componentIndex >= 0 &&
                    componentIndex < toolbotSkillComponents.Length
            ? toolbotSkillComponents[componentIndex] : null;
        var inventory = observed != null ? observed.skillVariantInventory : null;
        var rows = inventory != null ? inventory.components : null;
        var row = rows != null && componentIndex >= 0 && componentIndex < rows.Length
            ? rows[componentIndex] : null;
        string familyName = skill && skill.skillFamily ? ((ScriptableObject)skill.skillFamily).name : "";
        string familyCatalogIndex = skill && skill.skillFamily ? skill.skillFamily.catalogIndex.ToString() : "missing";
        string definitionName = skill && skill.skillDef ? ((ScriptableObject)skill.skillDef).name : "";
        string definitionIndex = skill && skill.skillDef ? skill.skillDef.skillIndex.ToString() : "missing";
        string serializedSkillName = skill ? (skill.skillName ?? "") : "";
        return "component[" + componentIndex + "]{genericSkillName=" + serializedSkillName +
               ",familyName=" + familyName + ",familyCatalogIndex=" + familyCatalogIndex +
               ",skillDefName=" + definitionName + ",skillDefIndex=" + definitionIndex +
               ",selectedVariant=" + (row != null ? row.selectedLoadoutVariantIndex.ToString() : "missing") +
               ",selectedSkillIndex=" + (row != null ? row.selectedLoadoutSkillCatalogIndex.ToString() : "missing") +
               ",runtimeSkillIndex=" + (row != null ? row.runtimeSkillCatalogIndex.ToString() : "missing") +
               ",runtimeStatus=" + (row != null ? (row.runtimeDefinitionStatus ?? "") : "missing") + "}";
    }

    bool ToolbotSelectedComponentMatches(int componentIndex, string familyName, string skillName,
                                        int familyIndex, int variantIndex, int skillIndex)
    {
        var skill = toolbotSkillComponents[componentIndex];
        var row = observed.skillVariantInventory.components[componentIndex];
        var expectedDefinition = SkillCatalog.GetSkillDef(skillIndex);
        // During Dual Wield the native special slot legitimately returns its
        // contextual Cancel SkillDef; compare the selected loadout row/family,
        // not GenericSkill.skillDef, after initial live-identity validation.
        return skill && skill.skillFamily && ((ScriptableObject)skill.skillFamily).name == familyName && expectedDefinition &&
               ((ScriptableObject)expectedDefinition).name == skillName && row != null && row.componentIndex == componentIndex &&
               row.familyCatalogIndex == familyIndex && row.selectedLoadoutVariantIndex == variantIndex &&
               row.selectedLoadoutSkillCatalogIndex == skillIndex && row.runtimeSkillCatalogIndex == skillIndex &&
               row.runtimeDefinitionStatus == "matches-selected-native-loadout" && row.variants != null &&
               variantIndex < row.variants.Length && row.variants[variantIndex] != null &&
               row.variants[variantIndex].skillCatalogIndex == skillIndex && row.variants[variantIndex].skillName == skillName;
    }

    void ApplyToolbotOffhand(float elapsed)
    {
        if (float.IsNaN(elapsed) || float.IsInfinity(elapsed) || elapsed < 0)
        {
            StopToolbotOffhand("invalid-elapsed-time");
            return;
        }
        if (float.IsNaN(toolbotDeadline))
        {
            toolbotPhaseBeganAt = elapsed;
            toolbotPhaseEnteredAt = elapsed;
            toolbotDeadline = elapsed + IsolationMaximumSeconds;
        }
        report.elapsedSeconds = Mathf.Max(0, elapsed - toolbotPhaseBeganAt);
        SampleToolbotDamageCounts();
        if (!OwnsLiveDiagnosticInput())
        {
            StopToolbotOffhand("diagnostic-input-yielded");
            return;
        }
        if (elapsed >= toolbotDeadline)
        {
            StopToolbotOffhand("toolbot-offhand-deadline");
            return;
        }
        if (bridge.inputNeutralRevision != lastNeutralRevision)
        {
            lastNeutralRevision = bridge.inputNeutralRevision;
            StopToolbotOffhand("neutralized-request-cancelled");
            return;
        }
        if (body.skillLocator.primary != toolbotSkillComponents[0] ||
            body.skillLocator.secondary != toolbotSkillComponents[2] ||
            body.skillLocator.special != toolbotSkillComponents[4] ||
            !ToolbotSelectedComponentMatches(0, "ToolbotBodyPrimary1", "ToolbotBodyFireNailgun", 141, 0, 195) ||
            !ToolbotSelectedComponentMatches(1, "ToolbotBodyPrimary2", "ToolbotBodyFireBuzzsaw", 142, 3, 193) ||
            !ToolbotSelectedComponentMatches(4, "ToolbotBodySpecialFamily", "ToolbotDualWield", 144, 1, 201))
        {
            StopToolbotOffhand("selected-native-identity-changed");
            return;
        }
        report.active = true;
        bridge.isolatedDiagnosticSkillInput = true;

        if (report.toolbotOffhandPhase < 6 && elapsed - toolbotPhaseEnteredAt >=
            (report.toolbotOffhandPhase == 5 ? 4f : 8f))
        {
            string timeout = report.toolbotOffhandPhase == 0 ? "special-not-native-ready" :
                report.toolbotOffhandPhase == 1 ? "special-input-without-callback-pair" :
                report.toolbotOffhandPhase == 2 ? "dual-wield-state-or-offhand-override-not-observed" :
                report.toolbotOffhandPhase == 3 ? "offhand-secondary-not-native-ready" :
                report.toolbotOffhandPhase == 4 ? "secondary-edge-without-callback-pair" :
                "offhand-callback-without-weapon2-buzzsaw-state";
            StopToolbotOffhand(timeout);
            return;
        }
        if (toolbotPulseActive)
        {
            ObserveInputBankEdge();
            if (elapsed >= toolbotPulseUntil)
            {
                bridge.isolatedDiagnosticSkillPulse = false;
                toolbotPulseActive = false;
                target = -1;
            }
            else
            {
                bridge.isolatedDiagnosticSkillPulse = true;
                return;
            }
        }

        bool specialCallbacks = observed.slots[3].authorityActivations > toolbotSpecialAuthorityBefore &&
                               observed.slots[3].serverActivations > toolbotSpecialServerBefore;
        bool secondaryCallbacks = observed.slots[1].authorityActivations > toolbotSecondaryAuthorityBefore &&
                                 observed.slots[1].serverActivations > toolbotSecondaryServerBefore;
        var bodyMachine = EntityStateMachine.FindByCustomName(body.gameObject, "Body");
        var weapon2 = EntityStateMachine.FindByCustomName(body.gameObject, "Weapon2");
        string bodyState = bodyMachine && bodyMachine.state != null ? bodyMachine.state.GetType().FullName : "";
        string weapon2State = weapon2 && weapon2.state != null ? weapon2.state.GetType().FullName : "";
        bool dualWield = bodyState == "EntityStates.Toolbot.ToolbotDualWield";
        var secondary = body.skillLocator.secondary;
        var offhand = toolbotSkillComponents[1];
        bool effectiveOverride = secondary && offhand && secondary.skillDef == offhand.skillDef &&
                                 secondary.skillDef && offhand.skillDef.skillIndex == 193 &&
                                 ((ScriptableObject)offhand.skillDef).name == "ToolbotBodyFireBuzzsaw" &&
                                 secondary.skillDef.activationStateMachineName == "Weapon";
        bool sawState = weapon2 && weapon2.state != null && weapon2.state.GetType().FullName == "EntityStates.Toolbot.FireBuzzsaw";
        if (dualWield && !report.toolbotOffhandStanceObserved)
            report.toolbotOffhandStanceSeconds = report.elapsedSeconds;
        report.toolbotOffhandStanceObserved |= dualWield;
        report.toolbotOffhandOverrideObserved |= effectiveOverride;
        report.toolbotOffhandWeapon2Observed |= (bool)weapon2;
        report.toolbotOffhandBuzzsawStateObserved |= sawState;
        report.toolbotOffhandBodyState = bodyState;
        var special = body.skillLocator.special;
        report.toolbotOffhandSpecialDefinition = special && special.skillDef
            ? ((ScriptableObject)special.skillDef).name : "";
        report.toolbotOffhandSecondaryDefinition = secondary && secondary.skillDef
            ? ((ScriptableObject)secondary.skillDef).name : "";
        report.toolbotOffhandSecondaryActivationMachine = secondary && secondary.skillDef
            ? secondary.skillDef.activationStateMachineName : "";
        report.toolbotOffhandWeapon2State = weapon2State;

        if (report.toolbotOffhandPhase == 0)
        {
            var specialSkill = body.skillLocator.special;
            if (specialSkill && specialSkill.enabled && specialSkill.skillDef && specialSkill.CanExecute())
            {
                toolbotSpecialAuthorityBefore = observed.slots[3].authorityActivations;
                toolbotSpecialServerBefore = observed.slots[3].serverActivations;
                report.toolbotOffhandSpecialAuthorityBefore = toolbotSpecialAuthorityBefore;
                report.toolbotOffhandSpecialServerBefore = toolbotSpecialServerBefore;
                BeginToolbotPulse(3, elapsed);
                toolbotSpecialPulseStarted = true;
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandSpecialRequestSeconds = report.elapsedSeconds;
                report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(0, true, false, false, false, false,
                    false, false, false, false, false);
                report.toolbotOffhandOutcome = "special-pulse-requested";
            }
            return;
        }
        if (report.toolbotOffhandPhase == 1)
        {
            report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(1, toolbotSpecialPulseStarted,
                toolbotSpecialEdgeObserved, specialCallbacks, false, false, false, false,
                false, false, false);
            if (report.toolbotOffhandPhase == 2)
            {
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandOutcome = "waiting-for-dual-wield-state-and-offhand-override";
            }
            return;
        }
        if (report.toolbotOffhandPhase == 2)
        {
            report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(2, true, true, true, dualWield,
                effectiveOverride, weapon2, false, false, false, false);
            if (report.toolbotOffhandPhase == 3)
            {
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandReadySeconds = report.elapsedSeconds;
                report.toolbotOffhandOutcome = "offhand-ready";
            }
            return;
        }
        if (report.toolbotOffhandPhase == 3)
        {
            if (!dualWield || !effectiveOverride || !weapon2)
            {
                StopToolbotOffhand("dual-wield-offhand-contract-lost-before-secondary-pulse");
                return;
            }
            if (secondary && secondary.enabled && secondary.skillDef && secondary.CanExecute())
            {
                toolbotSecondaryAuthorityBefore = observed.slots[1].authorityActivations;
                toolbotSecondaryServerBefore = observed.slots[1].serverActivations;
                report.toolbotOffhandSecondaryAuthorityBefore = toolbotSecondaryAuthorityBefore;
                report.toolbotOffhandSecondaryServerBefore = toolbotSecondaryServerBefore;
                report.toolbotOffhandBodyDamageEventsBeforeSecondary = combatOutput.bodyDamageEvents;
                report.toolbotOffhandDamageFactsBeforeSecondary = combatOutput.damageFactCount;
                BeginToolbotPulse(1, elapsed);
                toolbotSecondaryPulseStarted = true;
                report.toolbotOffhandSecondaryRequestSeconds = report.elapsedSeconds;
                report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(3, true, true, true, true,
                    true, true, toolbotSecondaryPulseStarted, false, false, false);
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandOutcome = "secondary-offhand-pulse-requested";
            }
            return;
        }
        if (report.toolbotOffhandPhase == 4)
        {
            report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(4, toolbotSpecialPulseStarted,
                toolbotSpecialEdgeObserved, specialCallbacks, dualWield, effectiveOverride, weapon2,
                toolbotSecondaryPulseStarted, toolbotSecondaryEdgeObserved, secondaryCallbacks, false);
            if (report.toolbotOffhandPhase == 5)
            {
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandOutcome = "offhand-callback-observed-waiting-for-weapon2-state";
            }
            return;
        }
        if (report.toolbotOffhandPhase == 5)
        {
            report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(5, toolbotSpecialPulseStarted,
                toolbotSpecialEdgeObserved, specialCallbacks, dualWield, effectiveOverride, weapon2,
                toolbotSecondaryPulseStarted, toolbotSecondaryEdgeObserved, secondaryCallbacks,
                report.toolbotOffhandBuzzsawStateObserved);
            if (report.toolbotOffhandPhase == 6)
            {
                report.toolbotOffhandBuzzsawStateSeconds = report.elapsedSeconds;
                StopToolbotOffhand("toolbot-offhand-activation-observed");
            }
        }
    }

    void BeginToolbotPulse(int slot, float elapsed)
    {
        if (report.toolbotOffhandRequests >= 2)
        {
            StopToolbotOffhand("toolbot-offhand-request-budget-exhausted");
            return;
        }
        pulseActive = toolbotPulseActive = true;
        target = slot;
        lastEdgeTick = bridge.fixedTicks;
        toolbotPulseStartTick = bridge.fixedTicks;
        toolbotPulseUntil = elapsed + PulseSeconds;
        bridge.isolatedDiagnosticSkillSlot = slot;
        bridge.isolatedDiagnosticSkillPulse = true;
        report.requests++;
        report.toolbotOffhandRequests++;
        report.slots[slot].requests++;
        report.slots[slot].eligibleSamples++;
    }

    void SampleToolbotDamageCounts()
    {
        if (combatOutput == null) return;
        report.toolbotOffhandBodyDamageEventsAtStop = combatOutput.bodyDamageEvents;
        report.toolbotOffhandDamageFactsAtStop = combatOutput.damageFactCount;
    }

    void StopToolbotOffhand(string outcome)
    {
        SampleToolbotDamageCounts();
        if (bridge)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            bridge.isolatedDiagnosticSkillSlot = -1;
        }
        pulseActive = toolbotPulseActive = false;
        target = -1;
        SyncNativeCallbacks();
        report.completed = true;
        report.active = false;
        report.outcome = outcome;
        report.toolbotOffhandOutcome = outcome;
    }

    void ApplyIsolated(float elapsed, int requestLimit)
    {
        bridge.isolatedDiagnosticSkillInput = true;
        bridge.isolatedDiagnosticSkillSlot = isolationTarget;
        if (!RefreshSelectedState())
        {
            Stop("selected-native-identity-changed");
            return;
        }
        if (isolationRequestPending && report.slots[isolationTarget].inputBankEdges > requestEdgeCount &&
            report.slots[isolationTarget].authorityAfter > report.slots[isolationTarget].authorityBefore &&
            report.slots[isolationTarget].serverAfter > report.slots[isolationTarget].serverBefore)
        {
            report.selectedCallbacksObserved = true;
            isolationRequestPending = false;
            pulseActive = false;
            target = -1;
            bridge.isolatedDiagnosticSkillPulse = false;
            report.outcome = "isolated-slot-callbacks-observed";
        }
        string windowOutcome = IsolationWindowOutcome(report.elapsedSeconds, report.selectedCallbacksObserved);
        if (windowOutcome != null)
        {
            Stop(windowOutcome);
            return;
        }
        if (report.selectedCallbacksObserved)
        {
            pulseActive = false;
            target = -1;
            bridge.isolatedDiagnosticSkillPulse = false;
            return;
        }
        if (pulseActive)
        {
            if (elapsed >= pulseUntil)
            {
                ObserveInputBankEdge();
                pulseActive = false;
                target = -1;
                bridge.isolatedDiagnosticSkillPulse = false;
            }
            else
            {
                bridge.isolatedDiagnosticSkillPulse = true;
                ObserveInputBankEdge();
            }
            return;
        }
        if (elapsed < nextRequestAt)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            report.outcome = isolationRequestPending ? "waiting-for-native-callbacks" : "waiting-for-request-window";
            return;
        }
        if (report.requests >= requestLimit)
        {
            Stop("request-budget-exhausted");
            return;
        }
        var skill = body.skillLocator.GetSkill((SkillSlot)isolationTarget);
        if (!skill || !skill.enabled || !skill.skillDef || !skill.CanExecute())
        {
            report.outcome = "waiting-for-native-can-execute";
            nextRequestAt = elapsed + RequestIntervalSeconds;
            return;
        }
        var slot = report.slots[isolationTarget];
        slot.eligibleSamples++;
        slot.authorityBefore = observed.slots[isolationTarget].authorityActivations;
        slot.serverBefore = observed.slots[isolationTarget].serverActivations;
        slot.authorityAfter = slot.authorityBefore;
        slot.serverAfter = slot.serverBefore;
        requestEdgeCount = slot.inputBankEdges;
        isolationRequestPending = true;
        target = isolationTarget;
        lastEdgeTick = bridge.fixedTicks;
        pulseUntil = elapsed + PulseSeconds;
        nextRequestAt = elapsed + RequestIntervalSeconds;
        report.requests++;
        slot.requests++;
        pulseActive = true;
        bridge.isolatedDiagnosticSkillPulse = true;
        report.outcome = "isolated-slot-pulse-requested";
    }

    bool RefreshSelectedState()
    {
        var skill = body && body.skillLocator ? body.skillLocator.GetSkill((SkillSlot)isolationTarget) : null;
        if (!skill || skill.GetInstanceID() != selectedComponentInstanceId || !skill.skillDef ||
            skill.skillDef.skillIndex != report.selectedSkillCatalogIndex ||
            SkillCatalog.GetSkillDef(report.selectedSkillCatalogIndex) != skill.skillDef ||
            ((ScriptableObject)skill.skillDef).name != report.selectedDefinition)
            return false;
        report.selectedActivationState = skill.skillDef.activationState.typeName;
        report.selectedMachineState = skill.stateMachine && skill.stateMachine.state != null
                                          ? skill.stateMachine.state.GetType().FullName : "";
        return true;
    }

    void ReleaseIsolationSink()
    {
        if (!bridge)
            return;
        bridge.isolatedDiagnosticSkillPulse = false;
        bridge.isolatedDiagnosticSkillInput = false;
        bridge.isolatedDiagnosticSkillSlot = -1;
    }

    bool OwnsLiveDiagnosticInput()
    {
        return body && bridge && body.gameObject == bridge.gameObject && body.healthComponent && body.healthComponent.alive &&
               body.skillLocator && body.inputBank && bridge.bank == body.inputBank && bridge.diagnosticInput;
    }

    int FindNextMissingCallbackSlot()
    {
        for (int offset = 1; offset <= 4; offset++)
        {
            int index = (cursor + offset) % 4;
            var slot = observed.slots[index];
            if (slot.authorityActivations == 0 || slot.serverActivations == 0)
                return index;
        }
        return -1;
    }

    bool MissingCallback(int index)
    {
        var slot = observed.slots[index];
        return slot.authorityActivations == 0 || slot.serverActivations == 0;
    }

    void AdvanceAfterSkippedSlot(int index, float elapsed)
    {
        cursor = index;
        pendingSlot = -1;
        nextRequestAt = elapsed + RequestIntervalSeconds;
    }

    void CaptureProducerRequests()
    {
        producerRequests[0] = bridge.diagnosticPrimary;
        producerRequests[1] = bridge.diagnosticSecondary;
        producerRequests[2] = bridge.diagnosticUtility;
        producerRequests[3] = bridge.diagnosticSpecial;
    }

    void CaptureFreshProducerRequests()
    {
        // When the caller did not run its producer between Apply calls, leave
        // the last real producer snapshot intact instead of saving our overlay.
        if (CurrentMatchesOverlay())
            return;
        CaptureProducerRequests();
    }

    void ApplyExclusivePulse()
    {
        if (!bridge)
            return;
        lastOverlay[0] = bridge.diagnosticPrimary = target == 0;
        lastOverlay[1] = bridge.diagnosticSecondary = target == 1;
        lastOverlay[2] = bridge.diagnosticUtility = target == 2;
        lastOverlay[3] = bridge.diagnosticSpecial = target == 3;
    }

    void ObserveInputBankEdge()
    {
        if (!body || !body.inputBank || !bridge || bridge.fixedTicks == lastEdgeTick || target < 0)
            return;
        lastEdgeTick = bridge.fixedTicks;
        var bank = body.inputBank;
        bool edge = target == 0   ? bank.skill1.justPressed
                    : target == 1 ? bank.skill2.justPressed
                    : target == 2 ? bank.skill3.justPressed
                                  : bank.skill4.justPressed;
        if (edge)
        {
            report.slots[target].inputBankEdges++;
            if (toolbotOffhandMode && bridge.fixedTicks > toolbotPulseStartTick)
            {
                if (target == 3)
                {
                    toolbotSpecialEdgeObserved = true;
                    report.toolbotOffhandSpecialEdgeSeconds = report.elapsedSeconds;
                }
                else if (target == 1)
                {
                    toolbotSecondaryEdgeObserved = true;
                    report.toolbotOffhandSecondaryEdgeSeconds = report.elapsedSeconds;
                }
            }
        }
    }

    void SyncNativeCallbacks()
    {
        if (observed == null || observed.slots == null)
            return;
        for (int i = 0; i < report.slots.Length; i++)
        {
            report.slots[i].authorityAfter = observed.slots[i].authorityActivations;
            report.slots[i].serverAfter = observed.slots[i].serverActivations;
        }
    }

    bool CurrentMatchesOverlay()
    {
        return bridge && bridge.diagnosticPrimary == lastOverlay[0] && bridge.diagnosticSecondary == lastOverlay[1] &&
               bridge.diagnosticUtility == lastOverlay[2] && bridge.diagnosticSpecial == lastOverlay[3];
    }

    void RestoreOwnedOverlayIfCurrent()
    {
        if (!bridge || !bridge.diagnosticInput || !CurrentMatchesOverlay())
            return;
        bridge.diagnosticPrimary = producerRequests[0];
        bridge.diagnosticSecondary = producerRequests[1];
        bridge.diagnosticUtility = producerRequests[2];
        bridge.diagnosticSpecial = producerRequests[3];
    }

    void ReleasePulse(bool restoreIfOwned = true)
    {
        if (pulseActive && restoreIfOwned && isolationTarget < 0)
            RestoreOwnedOverlayIfCurrent();
        pulseActive = false;
        target = -1;
    }

    void Stop(string outcome)
    {
        ReleasePulse(true);
        if ((isolationTarget >= 0 || toolbotOffhandMode) && bridge)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            if (toolbotOffhandMode) bridge.isolatedDiagnosticSkillSlot = -1;
        }
        SyncNativeCallbacks();
        report.completed = true;
        report.active = false;
        report.outcome = outcome;
    }

    public void ReleaseAll()
    {
        ReleasePulse(true);
        SyncNativeCallbacks();
    }

    public void Dispose()
    {
        if (report.cleaned)
            return;
        ReleaseAll();
        if (isolationTarget >= 0)
            ReleaseIsolationSink();
        if (toolbotOffhandMode && bridge)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            bridge.isolatedDiagnosticSkillInput = false;
            bridge.isolatedDiagnosticSkillSlot = -1;
        }
        report.active = false;
        report.cleaned = true;
        body = null;
        bridge = null;
        observed = null;
        combatOutput = null;
    }
}
