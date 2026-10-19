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
        public SlotCoverage[] slots;
    }

    static readonly string[] SlotNames = { "primary", "secondary", "utility", "special" };

    CharacterBody body;
    NovaInputBridge bridge;
    SurvivorSkillObserver.Report observed;
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

    public SurvivorSkillInputCoverage(CharacterBody ownedBody, NovaInputBridge ownedBridge,
                                      SurvivorSkillObserver.Report observerReport, string isolatedSlot = null)
    {
        if (!ownedBody || !ownedBody.skillLocator || !ownedBridge || observerReport == null || observerReport.slots == null ||
            observerReport.slots.Length != 4)
            throw new ArgumentException("Owned body, input bridge and four-slot observer report are required");
        if (ownedBody.gameObject != ownedBridge.gameObject || !ownedBody.inputBank || ownedBridge.bank != ownedBody.inputBank)
            throw new ArgumentException("The bridge and original input bank must belong to the owned body");

        body = ownedBody;
        bridge = ownedBridge;
        observed = observerReport;
        isolationTarget = string.IsNullOrEmpty(isolatedSlot) ? -1 : ParseIsolationSlot(isolatedSlot);
        report = new Report { active = false, outcome = "waiting-for-diagnostic-input",
                              mode = isolationTarget < 0 ? "all-four-slots" : "isolated-slot",
                              isolationSlot = isolationTarget < 0 ? "" : SlotNames[isolationTarget],
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
            report.slots[target].inputBankEdges++;
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
        if (isolationTarget >= 0 && bridge)
            bridge.isolatedDiagnosticSkillPulse = false;
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
        report.active = false;
        report.cleaned = true;
        body = null;
        bridge = null;
        observed = null;
    }
}
