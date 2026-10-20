// Subsystem: input/skill coverage (diagnostic only). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: constructed after the native skill observer; Apply after the world input producer;
// teardown before the owned body/world is released.
using System;
using System.Reflection;
using EntityStates;
using UnityEngine.Networking;
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
        // by an explicit diagnostic sequence selector.
        public bool captainSupplyBeaconRequested, captainSupplyBeaconPlacementValid,
                    captainSupplyBeaconCurrentPlacementValid, captainSupplyBeaconSupplyDrop1CanExecute,
                    captainSupplyBeaconDeployableRegistered, captainSupplyBeaconPendingNativeState,
                    captainSupplyBeaconDeployablePresentAtReturn;
        public int captainSupplyBeaconPhase, captainSupplyBeaconRequests,
                   captainSupplyBeaconDeployablesBefore, captainSupplyBeaconDeployablesAfter,
                   captainSpecialAuthorityBefore, captainSpecialAuthorityAfter,
                   captainSpecialServerBefore, captainSpecialServerAfter,
                   captainSupplyAuthorityBefore, captainSupplyAuthorityAfter,
                   captainSupplyServerBefore, captainSupplyServerAfter;
        public string captainSupplyBeaconOutcome, captainSupplyBeaconBodyState,
                      captainSupplyBeaconPlacementObservation, captainSupplyBeaconCurrentPlacementObservation,
                      captainSupplyBeaconNativeOwnership;
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
        // Fixed Toolbot-only diagnostic snapshots. Each is captured at most once;
        // ordinary skill coverage reports leave these fields null.
        public ToolbotReadinessObservation toolbotReadinessBeforeSpecial, toolbotReadinessAfterOverride, toolbotReadinessAtStop,
            toolbotReadinessAtTerminal;
        public SlotCoverage[] slots;
    }

    [Serializable]
    public sealed class ToolbotReadinessMachineObservation
    {
        public string role, availability, customNameStatus, stateStatus, pendingStatus, interruptStatus, enabledStatus, activeSelfStatus,
            activeInHierarchyStatus, transitionOnUpdateStatus, pendingMainStateStatus, pendingTargetTypeStatus, networkerStatus,
            networkIndexStatus, networkAuthorityStatus, configuredMainStateTypeStatus;
        public int instanceId, networkerInstanceId, networkIndex;
        public string customName, stateType, pendingTargetType, configuredMainStateType, networkMembership;
        public bool pendingState, canInterrupt, componentEnabled, activeSelf, activeInHierarchy, transitionOnUpdate, pendingMainState,
            networkAuthority;
    }

    [Serializable]
    public sealed class ToolbotReadinessObservation
    {
        public bool captured;
        public int captureCount, phase, secondaryInstanceId, stock, requiredStock, maxStock,
                   interruptPriority;
        public float elapsedSeconds, rechargeStopwatch, finalRechargeInterval, fixedTime;
        public int frameCount;
        public string outcome, secondaryAvailability, enabledStatus, skillDefStatus, clockStatus, skillDefNameStatus,
            configuredMachineStatus, stockStatus, requiredStockStatus, maxStockStatus, rechargeStopwatchStatus, finalRechargeIntervalStatus,
            interruptPriorityStatus, isReadyStatus, canExecuteStatus, skillDefIsReadyStatus, skillDefCanExecuteStatus;
        public bool enabled, isReady, canExecute, skillDefIsReady, skillDefCanExecute;
        public string skillDefName, configuredMachineName;
        public ToolbotReadinessMachineObservation resolvedMachine, weaponMachine, weapon2Machine;
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
    long toolbotPulseEdgeBaseline;
    int toolbotSpecialAuthorityBefore, toolbotSpecialServerBefore;
    int toolbotSecondaryAuthorityBefore, toolbotSecondaryServerBefore;
    bool toolbotPulseActive, toolbotSpecialEdgeObserved, toolbotSecondaryEdgeObserved,
         toolbotSpecialPulseStarted, toolbotSecondaryPulseStarted;
    int lastNeutralRevision;
    int requestEdgeCount;
    bool isolationRequestPending;
    readonly bool captainSupplyBeaconMode;
    CaptainSupplyBeaconSequence captainSupplyBeaconSequence;
    GenericSkill[] captainSupplyBeaconComponents;
    int[] captainSupplyBeaconComponentIds;
    int captainDeployablesBefore, captainSpecialAuthorityBefore, captainSpecialServerBefore,
        captainSupplyAuthorityBefore, captainSupplyServerBefore;
    CharacterMaster captainSupplyBeaconMaster;
    NetworkInstanceId captainSupplyBeaconMasterNetworkId;
    int captainSupplyBeaconMasterInstanceId;
    GameObject captainSupplyBeaconMasterObject;
    bool captainPulseActive, captainPulseEdgeAccepted, captainSpecialInputEdge, captainSupplyInputEdge;
    int captainPulseStartTick;
    long captainPulseEdgeBaseline;
    float captainPulseUntil, captainBeganAt = float.NaN;
    string captainSpecialDefinition;

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

    public enum DiagnosticInputEdgeStatus { None, Fresh, CounterReset, Multiple }

    // A fresh edge is one cumulative bridge-counter increment after this
    // request's snapshot and a later fixed tick. The request owner advances its
    // baseline after accepting the increment so it cannot count twice.
    public static DiagnosticInputEdgeStatus ClassifyDiagnosticInputEdge(long baseline, long current, bool laterFixedTick,
                                                                      bool observedForPulse = false)
    {
        if (baseline < 0 || current < baseline)
            return DiagnosticInputEdgeStatus.CounterReset;
        if (!laterFixedTick)
            return DiagnosticInputEdgeStatus.None;
        long delta = current - baseline;
        if (delta == 0)
            return DiagnosticInputEdgeStatus.None;
        return delta == 1 && !observedForPulse ? DiagnosticInputEdgeStatus.Fresh : DiagnosticInputEdgeStatus.Multiple;
    }

    public SurvivorSkillInputCoverage(CharacterBody ownedBody, NovaInputBridge ownedBridge,
                                      SurvivorSkillObserver.Report observerReport, string isolatedSlot = null,
                                      bool toolbotOffhand = false, SurvivorCombatOutputObserver.Report combatReport = null,
                                      bool captainSupplyBeacon = false)
    {
        if (!ownedBody || !ownedBody.skillLocator || !ownedBridge || observerReport == null || observerReport.slots == null ||
            observerReport.slots.Length != 4)
            throw new ArgumentException("Owned body, input bridge and four-slot observer report are required");
        if (ownedBody.gameObject != ownedBridge.gameObject || !ownedBody.inputBank || ownedBridge.bank != ownedBody.inputBank)
            throw new ArgumentException("The bridge and original input bank must belong to the owned body");

        body = ownedBody;
        bridge = ownedBridge;
        toolbotOffhandMode = toolbotOffhand;
        captainSupplyBeaconMode = captainSupplyBeacon;
        observed = observerReport;
        combatOutput = combatReport;
        isolationTarget = string.IsNullOrEmpty(isolatedSlot) ? -1 : ParseIsolationSlot(isolatedSlot);
        if (toolbotOffhandMode && isolationTarget >= 0)
            throw new ArgumentException("Toolbot offhand diagnostic cannot be combined with a single-slot isolation selector");
        if (captainSupplyBeaconMode && (toolbotOffhandMode || isolationTarget >= 0))
            throw new ArgumentException("Captain supply-beacon diagnostic cannot be combined with Toolbot offhand or slot isolation");
        report = new Report { active = false, outcome = "waiting-for-diagnostic-input",
                              mode = captainSupplyBeaconMode ? "captain-supply-beacon-sequence" :
                                     toolbotOffhandMode ? "toolbot-offhand-sequence" : isolationTarget < 0 ? "all-four-slots" : "isolated-slot",
                              isolationSlot = isolationTarget < 0 ? "" : SlotNames[isolationTarget],
                              toolbotOffhandRequested = toolbotOffhandMode,
                              captainSupplyBeaconRequested = captainSupplyBeaconMode,
                              captainSupplyBeaconOutcome = captainSupplyBeaconMode ? "waiting-for-owned-live-diagnostic-input" : "",
                              toolbotOffhandOutcome = toolbotOffhandMode ? "waiting-for-owned-live-diagnostic-input" : "",
                              slots = new SlotCoverage[4] };
        if (toolbotOffhandMode)
        {
            report.toolbotReadinessBeforeSpecial = new ToolbotReadinessObservation();
            report.toolbotReadinessAfterOverride = new ToolbotReadinessObservation();
            report.toolbotReadinessAtStop = new ToolbotReadinessObservation();
            report.toolbotReadinessAtTerminal = new ToolbotReadinessObservation();
        }
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
        if (captainSupplyBeaconMode)
        {
            CaptureCaptainSupplyBeaconIdentity();
            captainSupplyBeaconSequence = new CaptainSupplyBeaconSequence();
            ownedBridge.SetDiagnosticInputEdgeWitness(true);
            ownedBridge.isolatedDiagnosticSkillInput = true;
            ownedBridge.isolatedDiagnosticSkillSlot = -1;
            ownedBridge.isolatedDiagnosticSkillPulse = false;
        }
        if (toolbotOffhandMode)
        {
            CaptureToolbotOffhandIdentity();
            ownedBridge.SetDiagnosticInputEdgeWitness(true);
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
        if (captainSupplyBeaconMode)
        {
            ApplyCaptainSupplyBeacon(elapsed);
            return;
        }
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

    public static bool UpdateCaptainPlacementWitness(bool setup, bool currentPlacementValid, Report report)
    {
        if (report == null)
            return false;
        report.captainSupplyBeaconCurrentPlacementValid = setup && currentPlacementValid;
        report.captainSupplyBeaconCurrentPlacementObservation = !setup ? "setup-state-not-current" :
            (currentPlacementValid ? "native-setup-current-placement-valid" : "native-setup-current-placement-not-valid");
        bool positive = setup && currentPlacementValid;
        if (positive)
        {
            report.captainSupplyBeaconPlacementValid = true;
            report.captainSupplyBeaconPlacementObservation = "native-setup-placement-valid";
        }
        else if (!report.captainSupplyBeaconPlacementValid)
        {
            report.captainSupplyBeaconPlacementObservation = setup ?
                "native-setup-placement-not-valid" : "setup-state-not-current";
        }
        return positive;
    }

    public static bool CaptainSupplyDrop1CanExecute(bool primaryRemapped, bool nativeCanExecute)
    {
        return primaryRemapped && nativeCanExecute;
    }

    public static void CaptureCaptainCallbackBaselinesForRequest(int slot, int specialAuthority, int specialServer,
            int supplyAuthority, int supplyServer, Report report)
    {
        if (report == null)
            throw new ArgumentNullException(nameof(report));
        if (slot == 3)
        {
            report.captainSpecialAuthorityBefore = specialAuthority;
            report.captainSpecialServerBefore = specialServer;
        }
        else if (slot == 0)
        {
            report.captainSupplyAuthorityBefore = supplyAuthority;
            report.captainSupplyServerBefore = supplyServer;
        }
        else
            throw new ArgumentOutOfRangeException(nameof(slot), "Captain sequence requests only original special or primary");
    }

    public static bool CaptainMasterIdentityMatches(CharacterBody ownedBody, CharacterMaster originalMaster,
            int originalMasterInstanceId, NetworkInstanceId originalMasterNetworkId, GameObject originalMasterObject)
    {
        return ownedBody && originalMaster && ReferenceEquals(ownedBody.master, originalMaster) &&
            originalMaster.GetInstanceID() == originalMasterInstanceId &&
            originalMaster.netId == originalMasterNetworkId && originalMaster.isServer && originalMaster.hasBody &&
            originalMaster.GetBody() == ownedBody &&
            ReferenceEquals(originalMaster.gameObject, originalMasterObject) &&
            ReferenceEquals(NetworkServer.FindLocalObject(originalMasterNetworkId), originalMasterObject);
    }

    internal bool ObserveCaptainPulseBeforePolicy(float elapsed)
    {
        if (captainPulseActive)
        {
            ObserveCaptainInputBankEdge();
            if (report.completed)
                return false;
            if (elapsed >= captainPulseUntil)
                ReleaseCaptainPulse();
        }
        return !report.completed;
    }

    public static bool CaptainSetupSupplyBeaconIdentityMatches(string activationMachineName,
        string activationStateTypeName)
    {
        return string.Equals(activationMachineName, "Skillswap", StringComparison.Ordinal) &&
            string.Equals(activationStateTypeName, "EntityStates.Captain.Weapon.SetupSupplyDrop", StringComparison.Ordinal);
    }

    void CaptureCaptainSupplyBeaconIdentity()
    {
        if (!body || body.bodyIndex != BodyCatalog.FindBodyIndex("CaptainBody") || !body.master ||
            observed.skillVariantInventory == null || observed.skillVariantInventory.status != "available" ||
            observed.skillVariantInventory.components == null || observed.skillVariantInventory.components.Length != 6)
            throw new ArgumentException("Captain supply-beacon sequence requires the exact six-component native Captain inventory");
        captainSupplyBeaconComponents = body.GetComponents<GenericSkill>();
        if (captainSupplyBeaconComponents == null || captainSupplyBeaconComponents.Length != 6)
            throw new ArgumentException("Captain supply-beacon sequence requires six live GenericSkill components");
        string[] names = { "Primary", "Secondary", "Utility", "Special", "SupplyDrop1", "SupplyDrop2" };
        string[] definitions = { "CaptainShotgun", "CaptainTazer", "PrepAirstrike", "PrepSupplyDrop", "CallSupplyDropHealing", "CallSupplyDropShocking" };
        captainSupplyBeaconComponentIds = new int[6];
        for (int i = 0; i < captainSupplyBeaconComponents.Length; i++)
        {
            var skill = captainSupplyBeaconComponents[i];
            var row = observed.skillVariantInventory.components[i];
            if (!skill || !skill.skillDef || row == null || row.componentIndex != i || row.skillName != names[i] ||
                row.runtimeDefinitionStatus != "matches-selected-native-loadout" ||
                skill.skillName != names[i] || ((ScriptableObject)skill.skillDef).name != definitions[i] ||
                skill.skillDef.skillIndex < 0 || SkillCatalog.GetSkillDef(skill.skillDef.skillIndex) != skill.skillDef)
                throw new ArgumentException("Captain supply-beacon default native identity mismatch at component " + i);
            captainSupplyBeaconComponentIds[i] = skill.GetInstanceID();
        }
        var captainSpecialSkillDef = captainSupplyBeaconComponents[3].skillDef;
        var captainSpecialStateType = captainSpecialSkillDef.activationState.stateType;
        if (!CaptainSetupSupplyBeaconIdentityMatches(captainSpecialSkillDef.activationStateMachineName,
                captainSpecialStateType != null ? captainSpecialStateType.FullName : null) ||
            body.skillLocator.special != captainSupplyBeaconComponents[3] ||
            body.skillLocator.primary != captainSupplyBeaconComponents[0] ||
            body.skillLocator.secondary != captainSupplyBeaconComponents[1])
            throw new ArgumentException("Captain supply-beacon special/default slot identity is not canonical");
        captainSpecialDefinition = ((ScriptableObject)captainSupplyBeaconComponents[3].skillDef).name;
        if (!NetworkServer.active || !body.isServer || body.netId.Value == 0 ||
            !CaptainMasterIdentityMatches(body, body.master, body.master.GetInstanceID(), body.master.netId, body.master.gameObject) ||
            NetworkServer.FindLocalObject(body.netId) != body.gameObject)
            throw new ArgumentException("Captain supply-beacon requires the reciprocal server-owned body/master identity");
        captainSupplyBeaconMaster = body.master;
        captainSupplyBeaconMasterInstanceId = body.master.GetInstanceID();
        captainSupplyBeaconMasterNetworkId = body.master.netId;
        captainSupplyBeaconMasterObject = body.master.gameObject;
        captainDeployablesBefore = captainSupplyBeaconMaster.GetDeployableCount(DeployableSlot.CaptainSupplyDrop);
        report.captainSupplyBeaconDeployablesBefore = captainDeployablesBefore;
    }

    bool CaptainStateIs(string fullName)
    {
        if (!body) return false;
        var machines = body.GetComponents<EntityStateMachine>();
        int matches = 0;
        foreach (var machine in machines)
            if (machine && machine.state != null && machine.state.GetType().FullName == fullName) matches++;
        return matches == 1;
    }

    string CaptainBodyState()
    {
        var machine = body ? EntityStateMachine.FindByCustomName(body.gameObject, "Body") : null;
        return machine && machine.state != null ? machine.state.GetType().FullName : "";
    }

    bool CaptainPlacementIsValid()
    {
        // Read the original SetupSupplyDrop placement struct only. Reflection is
        // deliberate because the shipped field is private and version-specific.
        if (!body) return false;
        var machines = body.GetComponents<EntityStateMachine>();
        object placement = null;
        int matches = 0;
        foreach (var machine in machines)
        {
            if (!machine || machine.state == null || machine.state.GetType().FullName != "EntityStates.Captain.Weapon.SetupSupplyDrop") continue;
            var field = machine.state.GetType().GetField("currentPlacementInfo", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (field == null) continue;
            placement = field.GetValue(machine.state);
            matches++;
        }
        if (matches != 1 || placement == null) return false;
        var type = placement.GetType();
        var okField = type.GetField("ok", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        if (okField != null && okField.FieldType == typeof(bool)) return (bool)okField.GetValue(placement);
        var okProperty = type.GetProperty("ok", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        return okProperty != null && okProperty.PropertyType == typeof(bool) && okProperty.CanRead && (bool)okProperty.GetValue(placement, null);
    }

    bool BeginCaptainPulse(int slot, float elapsed)
    {
        if (slot < 0 || slot > 3 || !bridge.TryGetDiagnosticInputEdgeCount(slot, out captainPulseEdgeBaseline))
        {
            FinishCaptainSupplyBeacon("owned-input-edge-witness-unavailable");
            return false;
        }
        captainPulseStartTick = bridge.fixedTicks;
        captainPulseEdgeAccepted = false;
        if (slot == 3) captainSpecialInputEdge = false;
        if (slot == 0) captainSupplyInputEdge = false;
        target = slot;
        captainPulseActive = true;
        captainPulseUntil = elapsed + PulseSeconds;
        bridge.isolatedDiagnosticSkillInput = true;
        bridge.isolatedDiagnosticSkillSlot = slot;
        bridge.isolatedDiagnosticSkillPulse = true;
        lastEdgeTick = int.MinValue;
        report.captainSupplyBeaconRequests++;
        report.requests++;
        report.slots[slot].requests++;
        return true;
    }

    bool ObserveCaptainInputBankEdge()
    {
        if (!captainPulseActive) return false;
        if (!bridge.TryGetDiagnosticInputEdgeCount(target, out long current))
        {
            FinishCaptainSupplyBeacon("owned-input-edge-witness-unavailable");
            return false;
        }
        var status = ClassifyDiagnosticInputEdge(captainPulseEdgeBaseline, current,
            bridge.fixedTicks > captainPulseStartTick, captainPulseEdgeAccepted);
        if (status == DiagnosticInputEdgeStatus.CounterReset || status == DiagnosticInputEdgeStatus.Multiple)
        {
            FinishCaptainSupplyBeacon(status == DiagnosticInputEdgeStatus.CounterReset ?
                "owned-input-edge-counter-reset" : "multiple-input-edges-for-one-pulse");
            return false;
        }
        if (status != DiagnosticInputEdgeStatus.Fresh) return false;
        captainPulseEdgeBaseline = current;
        captainPulseEdgeAccepted = true;
        report.slots[target].inputBankEdges++;
        if (target == 3) captainSpecialInputEdge = true;
        if (target == 0) captainSupplyInputEdge = true;
        return true;
    }

    void ReleaseCaptainPulse()
    {
        if (bridge)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            bridge.isolatedDiagnosticSkillSlot = -1;
        }
        captainPulseActive = false;
        target = -1;
    }

    void ApplyCaptainSupplyBeacon(float elapsed)
    {
        if (float.IsNaN(elapsed) || float.IsInfinity(elapsed) || elapsed < 0)
        {
            FinishCaptainSupplyBeacon("invalid-elapsed-time"); return;
        }
        if (float.IsNaN(captainBeganAt)) captainBeganAt = elapsed;
        report.elapsedSeconds = Mathf.Max(0, elapsed - captainBeganAt);
        if (!OwnsLiveDiagnosticInput()) { FinishCaptainSupplyBeacon("diagnostic-input-owner-lost"); return; }
        if (bridge.inputNeutralRevision != lastNeutralRevision)
        {
            lastNeutralRevision = bridge.inputNeutralRevision;
            FinishCaptainSupplyBeacon("neutralized-request-cancelled"); return;
        }
        if (captainSupplyBeaconComponents == null || captainSupplyBeaconComponents.Length != 6 ||
            body.GetComponents<GenericSkill>().Length != 6 || !captainSupplyBeaconMaster ||
            !NetworkServer.active || !body.isServer ||
            !CaptainMasterIdentityMatches(body, captainSupplyBeaconMaster, captainSupplyBeaconMasterInstanceId,
                captainSupplyBeaconMasterNetworkId, captainSupplyBeaconMasterObject))
        { FinishCaptainSupplyBeacon("captain-owner-or-skill-inventory-changed"); return; }
        for (int i = 0; i < 6; i++)
            if (!captainSupplyBeaconComponents[i] || captainSupplyBeaconComponents[i].GetInstanceID() != captainSupplyBeaconComponentIds[i])
            { FinishCaptainSupplyBeacon("captain-skill-component-replaced"); return; }

        if (!ObserveCaptainPulseBeforePolicy(elapsed)) return;
        bool setup = CaptainStateIs("EntityStates.Captain.Weapon.SetupSupplyDrop");
        bool call = CaptainStateIs("EntityStates.Captain.Weapon.CallSupplyDropHealing");
        bool primaryRemapped = body.skillLocator.primary == captainSupplyBeaconComponents[4] &&
                               captainSupplyBeaconComponents[4].skillDef &&
                               ((ScriptableObject)captainSupplyBeaconComponents[4].skillDef).name == "CallSupplyDropHealing";
        bool secondaryRemapped = body.skillLocator.secondary == captainSupplyBeaconComponents[5] &&
                                 captainSupplyBeaconComponents[5].skillDef &&
                                 ((ScriptableObject)captainSupplyBeaconComponents[5].skillDef).name == "CallSupplyDropShocking";
        bool specialCallbacks = observed.components[3].authorityActivations > captainSpecialAuthorityBefore &&
                                observed.components[3].serverActivations > captainSpecialServerBefore;
        bool supplyCallbacks = observed.components[4].authorityActivations > captainSupplyAuthorityBefore &&
                               observed.components[4].serverActivations > captainSupplyServerBefore;
        int ownedCount = body.master.GetDeployableCount(DeployableSlot.CaptainSupplyDrop);
        report.captainSupplyBeaconDeployablesAfter = ownedCount;
        report.captainSpecialAuthorityBefore = captainSpecialAuthorityBefore;
        report.captainSpecialAuthorityAfter = observed.components[3].authorityActivations;
        report.captainSpecialServerBefore = captainSpecialServerBefore;
        report.captainSpecialServerAfter = observed.components[3].serverActivations;
        report.captainSupplyAuthorityBefore = captainSupplyAuthorityBefore;
        report.captainSupplyAuthorityAfter = observed.components[4].authorityActivations;
        report.captainSupplyServerBefore = captainSupplyServerBefore;
        report.captainSupplyServerAfter = observed.components[4].serverActivations;
        report.captainSupplyBeaconDeployableRegistered = ownedCount > captainDeployablesBefore;
        report.captainSupplyBeaconBodyState = CaptainBodyState();
        bool currentPlacementValid = setup && CaptainPlacementIsValid();
        UpdateCaptainPlacementWitness(setup, currentPlacementValid, report);
        bool supplyDrop1CanExecute = CaptainSupplyDrop1CanExecute(primaryRemapped,
            captainSupplyBeaconComponents[4].CanExecute());
        report.captainSupplyBeaconSupplyDrop1CanExecute = supplyDrop1CanExecute;
        report.captainSupplyBeaconNativeOwnership = "owned-master-CaptainSupplyDrop-count=" + ownedCount;
        report.captainSupplyBeaconPendingNativeState = setup || call;
        report.captainSupplyBeaconDeployablePresentAtReturn = !setup && !call && ownedCount > captainDeployablesBefore;

        var observation = new CaptainSupplyBeaconSequence.Observation {
            elapsedSeconds = report.elapsedSeconds,
            exactCaptainOwner = body.bodyIndex == BodyCatalog.FindBodyIndex("CaptainBody") && body.master.GetBody() == body,
            exactDefaultSupplySkill = captainSpecialDefinition == "PrepSupplyDrop" &&
                ((ScriptableObject)captainSupplyBeaconComponents[3].skillDef).name == "PrepSupplyDrop" &&
                ((ScriptableObject)captainSupplyBeaconComponents[4].skillDef).name == "CallSupplyDropHealing" &&
                ((ScriptableObject)captainSupplyBeaconComponents[5].skillDef).name == "CallSupplyDropShocking",
            isolatedDiagnosticInputOwned = bridge.diagnosticInput && bridge.isolatedDiagnosticSkillInput,
            neutralRevisionChanged = false,
            specialCanExecute = body.skillLocator.special && body.skillLocator.special.enabled && body.skillLocator.special.CanExecute(),
            specialInputEdge = captainSpecialInputEdge,
            specialAuthorityCallback = specialCallbacks,
            specialServerCallback = specialCallbacks,
            setupSupplyDropState = setup,
            setupPrimaryIsSupplyDrop1 = primaryRemapped,
            setupSecondaryIsSupplyDrop2 = secondaryRemapped,
            nativePlacementValid = currentPlacementValid,
            supplyDrop1CanExecute = supplyDrop1CanExecute,
            supplyDrop1InputEdge = captainSupplyInputEdge,
            supplyDrop1AuthorityCallback = supplyCallbacks,
            supplyDrop1ServerCallback = supplyCallbacks,
            nativeCallSupplyDropHealingState = call,
            ownedCaptainSupplyDropCountIncreased = report.captainSupplyBeaconDeployableRegistered,
            returnedToOrdinaryBodyState = !setup && !call && report.captainSupplyBeaconDeployablePresentAtReturn &&
                                          body.skillLocator.primary == captainSupplyBeaconComponents[0] &&
                                          body.skillLocator.secondary == captainSupplyBeaconComponents[1]
        };
        var decision = captainSupplyBeaconSequence.Step(observation);
        report.captainSupplyBeaconPhase = (int)decision.phase;
        report.captainSupplyBeaconOutcome = decision.outcome;
        if (decision.requestInputSlot >= 0)
        {
            CaptureCaptainCallbackBaselinesForRequest(decision.requestInputSlot,
                observed.components[3].authorityActivations, observed.components[3].serverActivations,
                observed.components[4].authorityActivations, observed.components[4].serverActivations, report);
            if (decision.requestInputSlot == 3)
            {
                captainSpecialAuthorityBefore = observed.components[3].authorityActivations;
                captainSpecialServerBefore = observed.components[3].serverActivations;
            }
            else
            {
                captainSupplyAuthorityBefore = observed.components[4].authorityActivations;
                captainSupplyServerBefore = observed.components[4].serverActivations;
            }
            BeginCaptainPulse(decision.requestInputSlot, elapsed);
        }
        if (decision.completed || decision.refused) FinishCaptainSupplyBeacon(decision.outcome);
    }

    void FinishCaptainSupplyBeacon(string outcome)
    {
        ReleaseCaptainPulse();
        if (bridge)
        {
            bridge.isolatedDiagnosticSkillPulse = false;
            bridge.isolatedDiagnosticSkillSlot = -1;
            bridge.SetDiagnosticInputEdgeWitness(false);
            // Keep isolated input ownership until normal Dispose so no physical
            // button leaks into the unresolved native setup/call state.
            bridge.isolatedDiagnosticSkillInput = true;
        }
        report.captainSupplyBeaconOutcome = outcome;
        report.captainSupplyBeaconPendingNativeState = CaptainStateIs("EntityStates.Captain.Weapon.SetupSupplyDrop") ||
                                                        CaptainStateIs("EntityStates.Captain.Weapon.CallSupplyDropHealing");
        report.captainSupplyBeaconDeployablePresentAtReturn = !report.captainSupplyBeaconPendingNativeState &&
            body && captainSupplyBeaconMaster &&
            captainSupplyBeaconMaster.GetDeployableCount(DeployableSlot.CaptainSupplyDrop) > captainDeployablesBefore;
        report.completed = true;
        report.active = false;
        report.outcome = outcome;
        SyncNativeCallbacks();
        if (observed != null && observed.components != null && observed.components.Length > 4)
        {
            report.captainSpecialAuthorityAfter = observed.components[3].authorityActivations;
            report.captainSpecialServerAfter = observed.components[3].serverActivations;
            report.captainSupplyAuthorityAfter = observed.components[4].authorityActivations;
            report.captainSupplyServerAfter = observed.components[4].serverActivations;
        }
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

    static string ToolbotObservationException(Exception exception)
    {
        return "exception:" + (exception != null ? exception.GetType().FullName : "unknown");
    }

    public static string ToolbotObjectAvailability(bool referenceIsNull, bool unityObjectAlive)
    {
        if (referenceIsNull)
            return "null";
        return unityObjectAlive ? "available" : "destroyed-fake-null";
    }

    public static bool BeginToolbotReadinessCaptureHeader(ToolbotReadinessObservation observation, int phase, float elapsedSeconds,
                                                          string outcome, int frameCount, float fixedTime, string clockStatus)
    {
        if (observation == null || observation.captured)
            return false;
        observation.captured = true;
        observation.captureCount = 1;
        observation.phase = phase;
        observation.elapsedSeconds = elapsedSeconds;
        observation.outcome = outcome;
        observation.frameCount = frameCount;
        observation.fixedTime = fixedTime;
        observation.clockStatus = clockStatus;
        return true;
    }

    void CaptureToolbotReadinessSnapshot(ToolbotReadinessObservation observation, float elapsed, string outcome)
    {
        if (observation == null || observation.captured)
            return;
        int frameCount = 0;
        float fixedTime = 0;
        string clockStatus = "unavailable";
        try
        {
            frameCount = Time.frameCount;
            fixedTime = Time.fixedTime;
            clockStatus = "available";
        }
        catch (Exception exception)
        {
            clockStatus = ToolbotObservationException(exception);
        }
        if (!BeginToolbotReadinessCaptureHeader(observation, report.toolbotOffhandPhase, elapsed, outcome, frameCount, fixedTime,
                                                clockStatus))
            return;
        observation.secondaryAvailability = "unavailable";
        observation.enabledStatus = observation.skillDefStatus = observation.skillDefNameStatus = "unavailable";
        observation.configuredMachineStatus = observation.stockStatus = observation.requiredStockStatus = "unavailable";
        observation.maxStockStatus = observation.rechargeStopwatchStatus = "unavailable";
        observation.finalRechargeIntervalStatus = observation.interruptPriorityStatus = "unavailable";
        observation.isReadyStatus = observation.canExecuteStatus = "unavailable";
        observation.skillDefIsReadyStatus = observation.skillDefCanExecuteStatus = "unavailable";

        GenericSkill secondary = null;
        try
        {
            if (body && body.skillLocator)
                secondary = body.skillLocator.secondary;
            if (secondary)
            {
                observation.secondaryAvailability = "available";
                observation.secondaryInstanceId = secondary.GetInstanceID();
            }
        }
        catch (Exception exception)
        {
            observation.secondaryAvailability = ToolbotObservationException(exception);
        }

        SkillDef skillDef = null;
        if (secondary)
        {
            try
            {
                observation.enabled = secondary.enabled;
                observation.enabledStatus = "available";
            }
            catch (Exception exception)
            {
                observation.enabledStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.stock = secondary.stock;
                observation.stockStatus = "available";
            }
            catch (Exception exception)
            {
                observation.stockStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.maxStock = secondary.maxStock;
                observation.maxStockStatus = "available";
            }
            catch (Exception exception)
            {
                observation.maxStockStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.rechargeStopwatch = secondary.rechargeStopwatch;
                observation.rechargeStopwatchStatus = "available";
            }
            catch (Exception exception)
            {
                observation.rechargeStopwatchStatus = ToolbotObservationException(exception);
            }
            try
            {
                skillDef = secondary.skillDef;
                observation.skillDefStatus = skillDef ? "available" : "unavailable";
            }
            catch (Exception exception)
            {
                observation.skillDefStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.finalRechargeInterval = secondary.CalculateFinalRechargeInterval();
                observation.finalRechargeIntervalStatus = "available";
            }
            catch (Exception exception)
            {
                observation.finalRechargeIntervalStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.isReady = secondary.IsReady();
                observation.isReadyStatus = "available";
            }
            catch (Exception exception)
            {
                observation.isReadyStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.canExecute = secondary.CanExecute();
                observation.canExecuteStatus = "available";
            }
            catch (Exception exception)
            {
                observation.canExecuteStatus = ToolbotObservationException(exception);
            }
        }

        InterruptPriority interruptPriority = InterruptPriority.Any;
        bool interruptPriorityAvailable = false;
        if (skillDef)
        {
            try
            {
                observation.skillDefName = ((ScriptableObject)skillDef).name;
                observation.skillDefNameStatus = "available";
            }
            catch (Exception exception)
            {
                observation.skillDefNameStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.configuredMachineName = skillDef.activationStateMachineName;
                observation.configuredMachineStatus = "available";
            }
            catch (Exception exception)
            {
                observation.configuredMachineStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.requiredStock = skillDef.requiredStock;
                observation.requiredStockStatus = "available";
            }
            catch (Exception exception)
            {
                observation.requiredStockStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.interruptPriority = (int)skillDef.interruptPriority;
                interruptPriority = skillDef.interruptPriority;
                interruptPriorityAvailable = true;
                observation.interruptPriorityStatus = "available";
            }
            catch (Exception exception)
            {
                observation.interruptPriorityStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.skillDefIsReady = skillDef.IsReady(secondary);
                observation.skillDefIsReadyStatus = "available";
            }
            catch (Exception exception)
            {
                observation.skillDefIsReadyStatus = ToolbotObservationException(exception);
            }
            try
            {
                observation.skillDefCanExecute = skillDef.CanExecute(secondary);
                observation.skillDefCanExecuteStatus = "available";
            }
            catch (Exception exception)
            {
                observation.skillDefCanExecuteStatus = ToolbotObservationException(exception);
            }
        }

        try
        {
            EntityStateMachine resolved = ResolveToolbotReadinessMachine(
                secondary ? secondary.stateMachine : null, null);
            observation.resolvedMachine = CaptureToolbotReadinessMachine("resolved", interruptPriority,
                interruptPriorityAvailable, resolved);
        }
        catch (Exception exception)
        {
            observation.resolvedMachine = new ToolbotReadinessMachineObservation {
                role = "resolved", availability = ToolbotObservationException(exception),
                customNameStatus = "unavailable", stateStatus = "unavailable",
                pendingStatus = "unavailable", interruptStatus = "unavailable"
            };
        }
        observation.weaponMachine = CaptureNamedToolbotReadinessMachine("Weapon", "Weapon", interruptPriority,
            interruptPriorityAvailable);
        observation.weapon2Machine = CaptureNamedToolbotReadinessMachine("Weapon2", "Weapon2", interruptPriority,
            interruptPriorityAvailable);
    }

    static EntityStateMachine ResolveToolbotReadinessMachine(EntityStateMachine directReference,
        Func<EntityStateMachine> explicitNameLookup)
    {
        if (directReference)
            return directReference;
        return explicitNameLookup != null ? explicitNameLookup() : null;
    }

    ToolbotReadinessMachineObservation CaptureNamedToolbotReadinessMachine(string role, string customName,
        InterruptPriority interruptPriority, bool interruptPriorityAvailable)
    {
        EntityStateMachine machine;
        try
        {
            machine = ResolveToolbotReadinessMachine(null, delegate {
                return body ? EntityStateMachine.FindByCustomName(body.gameObject, customName) : null;
            });
        }
        catch (Exception exception)
        {
            return new ToolbotReadinessMachineObservation {
                role = role, availability = ToolbotObservationException(exception),
                customNameStatus = "unavailable", stateStatus = "unavailable",
                pendingStatus = "unavailable",
                interruptStatus = interruptPriorityAvailable ? "unavailable" : "unavailable-skill-priority"
            };
        }
        return CaptureToolbotReadinessMachine(role, interruptPriority, interruptPriorityAvailable, machine);
    }

    ToolbotReadinessMachineObservation CaptureToolbotReadinessMachine(string role,
        InterruptPriority interruptPriority, bool interruptPriorityAvailable, EntityStateMachine machine)
    {
        bool networkIndexAvailable = false;
        ToolbotReadinessMachineObservation observation =
            new ToolbotReadinessMachineObservation { role = role,
                                                     availability = ToolbotObjectAvailability(ReferenceEquals(machine, null), machine),
                                                     customNameStatus = "unavailable",
                                                     stateStatus = "unavailable",
                                                     pendingStatus = "unavailable",
                                                     interruptStatus =
                                                         interruptPriorityAvailable ? "unavailable" : "unavailable-skill-priority",
                                                     enabledStatus = "unavailable",
                                                     activeSelfStatus = "unavailable",
                                                     activeInHierarchyStatus = "unavailable",
                                                     transitionOnUpdateStatus = "unavailable",
                                                     pendingMainStateStatus = "unavailable",
                                                     pendingTargetTypeStatus = "unavailable-no-public-api",
                                                     networkerStatus = "unavailable",
                                                     networkIndexStatus = "unavailable",
                                                     networkAuthorityStatus = "unavailable",
                                                     configuredMainStateTypeStatus = "unavailable",
                                                     networkMembership = "unavailable" };
        if (!machine)
            return observation;
        try
        {
            observation.instanceId = machine.GetInstanceID();
        }
        catch (Exception exception)
        {
            observation.availability = ToolbotObservationException(exception);
        }
        try
        {
            observation.componentEnabled = machine.enabled;
            observation.enabledStatus = "available";
        }
        catch (Exception exception)
        {
            observation.enabledStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.activeSelf = machine.gameObject.activeSelf;
            observation.activeSelfStatus = "available";
        }
        catch (Exception exception)
        {
            observation.activeSelfStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.activeInHierarchy = machine.gameObject.activeInHierarchy;
            observation.activeInHierarchyStatus = "available";
        }
        catch (Exception exception)
        {
            observation.activeInHierarchyStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.transitionOnUpdate = machine.ShouldStateTransitionOnUpdate;
            observation.transitionOnUpdateStatus = "available";
        }
        catch (Exception exception)
        {
            observation.transitionOnUpdateStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.pendingMainState = machine.IsPendingMainState();
            observation.pendingMainStateStatus = "available";
        }
        catch (Exception exception)
        {
            observation.pendingMainStateStatus = ToolbotObservationException(exception);
        }
        try
        {
            var configuredMainState = machine.mainStateType.stateType;
            observation.configuredMainStateType = configuredMainState != null ? configuredMainState.FullName : "";
            observation.configuredMainStateTypeStatus = configuredMainState != null ? "available" : "unavailable-main-state-type";
        }
        catch (Exception exception)
        {
            observation.configuredMainStateTypeStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.networkIndex = machine.networkIndex;
            observation.networkIndexStatus = "available";
            networkIndexAvailable = true;
        }
        catch (Exception exception)
        {
            observation.networkIndexStatus = ToolbotObservationException(exception);
        }
        try
        {
            NetworkStateMachine networker = machine.networker;
            observation.networkerStatus = ToolbotObjectAvailability(ReferenceEquals(networker, null), networker);
            observation.networkMembership = !networker                      ? "networker-unavailable"
                                            : !networkIndexAvailable        ? "network-index-unavailable"
                                            : observation.networkIndex >= 0 ? "networker-present-index-assigned"
                                                                            : "networker-present-index-unassigned";
            if (networker)
            {
                observation.networkerInstanceId = networker.GetInstanceID();
                observation.networkAuthority = networker.hasAuthority;
                observation.networkAuthorityStatus = "available";
            }
            else
                observation.networkAuthorityStatus = "unavailable-networker";
        }
        catch (Exception exception)
        {
            observation.networkerStatus = ToolbotObservationException(exception);
            observation.networkAuthorityStatus = ToolbotObservationException(exception);
            observation.networkMembership = "exception";
        }
        try
        {
            observation.customName = machine.customName;
            observation.customNameStatus = "available";
        }
        catch (Exception exception)
        {
            observation.customNameStatus = ToolbotObservationException(exception);
        }
        try
        {
            EntityState currentState = machine.state;
            observation.stateType = currentState != null ? currentState.GetType().FullName : "";
            observation.stateStatus = currentState != null ? "available" : "unavailable-state";
        }
        catch (Exception exception)
        {
            observation.stateStatus = ToolbotObservationException(exception);
        }
        try
        {
            observation.pendingState = machine.HasPendingState();
            observation.pendingStatus = "available";
            observation.pendingTargetTypeStatus = "unavailable-no-public-api";
        }
        catch (Exception exception)
        {
            observation.pendingStatus = ToolbotObservationException(exception);
        }
        if (interruptPriorityAvailable)
        {
            try
            {
                observation.canInterrupt = machine.CanInterruptState(interruptPriority);
                observation.interruptStatus = "available";
            }
            catch (Exception exception)
            {
                observation.interruptStatus = ToolbotObservationException(exception);
            }
        }
        return observation;
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
            if (!ObserveInputBankEdge())
                return;
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
        if (dualWield && effectiveOverride)
            CaptureToolbotReadinessSnapshot(report.toolbotReadinessAfterOverride, report.elapsedSeconds,
                "after-dual-wield-override-observed");

        if (report.toolbotOffhandPhase == 0)
        {
            CaptureToolbotReadinessSnapshot(report.toolbotReadinessBeforeSpecial, report.elapsedSeconds,
                "before-special-readiness-gate");
            var specialSkill = body.skillLocator.special;
            if (specialSkill && specialSkill.enabled && specialSkill.skillDef && specialSkill.CanExecute())
            {
                toolbotSpecialAuthorityBefore = observed.slots[3].authorityActivations;
                toolbotSpecialServerBefore = observed.slots[3].serverActivations;
                report.toolbotOffhandSpecialAuthorityBefore = toolbotSpecialAuthorityBefore;
                report.toolbotOffhandSpecialServerBefore = toolbotSpecialServerBefore;
                if (!BeginToolbotPulse(3, elapsed)) return;
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
                if (!BeginToolbotPulse(1, elapsed)) return;
                toolbotSecondaryPulseStarted = true;
                report.toolbotOffhandSecondaryRequestSeconds = report.elapsedSeconds;
                report.toolbotOffhandPhase = AdvanceToolbotOffhandPhase(3, true, true, true, true,
                    true, true, toolbotSecondaryPulseStarted, false, false, false);
                toolbotPhaseEnteredAt = elapsed;
                report.toolbotOffhandOutcome = "secondary-offhand-pulse-requested";
            }
            else
            {
                CaptureToolbotReadinessSnapshot(report.toolbotReadinessAtStop, report.elapsedSeconds,
                    "phase-3-secondary-native-readiness-refusal");
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

    bool BeginToolbotPulse(int slot, float elapsed)
    {
        if (report.toolbotOffhandRequests >= 2)
        {
            StopToolbotOffhand("toolbot-offhand-request-budget-exhausted");
            return false;
        }
        if (toolbotOffhandMode && !bridge.TryGetDiagnosticInputEdgeCount(slot, out toolbotPulseEdgeBaseline))
        {
            StopToolbotOffhand("toolbot-input-edge-witness-unavailable");
            return false;
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
        return true;
    }

    void SampleToolbotDamageCounts()
    {
        if (combatOutput == null) return;
        report.toolbotOffhandBodyDamageEventsAtStop = combatOutput.bodyDamageEvents;
        report.toolbotOffhandDamageFactsAtStop = combatOutput.damageFactCount;
    }

    void StopToolbotOffhand(string outcome)
    {
        CaptureToolbotReadinessSnapshot(report.toolbotReadinessAtStop, report.elapsedSeconds,
            "offhand-sequence-stop:" + (outcome ?? "unknown"));
        CaptureToolbotReadinessSnapshot(report.toolbotReadinessAtTerminal, report.elapsedSeconds, "terminal:" + (outcome ?? "unknown"));
        SampleToolbotDamageCounts();
        if (bridge)
        {
            bridge.SetDiagnosticInputEdgeWitness(false);
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

    bool ObserveInputBankEdge()
    {
        if (!body || !body.inputBank || !bridge || bridge.fixedTicks == lastEdgeTick || target < 0)
            return true;
        lastEdgeTick = bridge.fixedTicks;
        var bank = body.inputBank;
        bool edge;
        if (toolbotOffhandMode)
        {
            if (!bridge.TryGetDiagnosticInputEdgeCount(target, out long count))
            {
                StopToolbotOffhand("toolbot-input-edge-witness-unavailable");
                return false;
            }
            var status = ClassifyDiagnosticInputEdge(toolbotPulseEdgeBaseline, count,
                                                   bridge.fixedTicks > toolbotPulseStartTick,
                                                   report.slots[target].inputBankEdges != 0);
            if (status == DiagnosticInputEdgeStatus.CounterReset)
            {
                StopToolbotOffhand("toolbot-input-edge-counter-reset");
                return false;
            }
            if (status == DiagnosticInputEdgeStatus.Multiple)
            {
                StopToolbotOffhand("multiple-toolbot-input-edges-for-pulse");
                return false;
            }
            edge = status == DiagnosticInputEdgeStatus.Fresh;
            if (edge)
                toolbotPulseEdgeBaseline = count;
        }
        else
        {
            edge = target == 0   ? bank.skill1.justPressed
                   : target == 1 ? bank.skill2.justPressed
                   : target == 2 ? bank.skill3.justPressed
                                 : bank.skill4.justPressed;
        }
        if (edge)
        {
            if (captainSupplyBeaconMode)
            {
                if (target == 3) captainSpecialInputEdge = true;
                if (target == 0) captainSupplyInputEdge = true;
            }
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
        return true;
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
        if (captainSupplyBeaconMode && bridge)
        {
            // The world owner tears down before its body. If an original setup/
            // call state is still active, keep the skill sink masked through
            // that teardown; the soon-to-be-destroyed body/bridge owns the lease.
            bool unresolvedNativeState = CaptainStateIs("EntityStates.Captain.Weapon.SetupSupplyDrop") ||
                                         CaptainStateIs("EntityStates.Captain.Weapon.CallSupplyDropHealing");
            report.captainSupplyBeaconPendingNativeState = unresolvedNativeState;
            bridge.SetDiagnosticInputEdgeWitness(false);
            bridge.isolatedDiagnosticSkillPulse = false;
            bridge.isolatedDiagnosticSkillSlot = -1;
            if (!unresolvedNativeState)
                bridge.isolatedDiagnosticSkillInput = false;
        }
        if (toolbotOffhandMode && bridge)
        {
            bridge.SetDiagnosticInputEdgeWitness(false);
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
        captainSupplyBeaconComponents = null;
        captainSupplyBeaconComponentIds = null;
        captainSupplyBeaconSequence = null;
    }
}


// Host-testable policy to splice into SurvivorSkillInputCoverage. The runtime
// adapter supplies observations from the existing InputBank, skill observer,
// SetupSupplyDrop state, and CharacterMaster deployable registry.
public sealed class CaptainSupplyBeaconSequence
{
    public enum Phase
    {
        WaitingForNativeReadiness,
        AwaitingSpecialEdgeAndCallbacks,
        AwaitingSetupAndSlotRemap,
        AwaitingValidPlacement,
        AwaitingSupplyEdgeAndCallbacks,
        AwaitingNativeSupplyState,
        AwaitingOwnedDeployableAndReturn,
        Complete,
        Refused
    }

    public sealed class Observation
    {
        public float elapsedSeconds;
        public bool exactCaptainOwner;
        public bool exactDefaultSupplySkill;
        public bool isolatedDiagnosticInputOwned;
        public bool neutralRevisionChanged;
        public bool specialCanExecute;
        public bool specialInputEdge;
        public bool specialAuthorityCallback;
        public bool specialServerCallback;
        public bool setupSupplyDropState;
        public bool setupPrimaryIsSupplyDrop1;
        public bool setupSecondaryIsSupplyDrop2;
        public bool nativePlacementValid;
        public bool supplyDrop1CanExecute;
        public bool supplyDrop1InputEdge;
        public bool supplyDrop1AuthorityCallback;
        public bool supplyDrop1ServerCallback;
        public bool nativeCallSupplyDropHealingState;
        public bool ownedCaptainSupplyDropCountIncreased;
        public bool returnedToOrdinaryBodyState;
    }

    public sealed class Decision
    {
        public Phase phase;
        // -1 means neutral; 3 is the original special button, 0 is primary.
        public int requestInputSlot = -1;
        public string outcome;
        public bool completed;
        public bool refused;
    }

    public const float MaximumSeconds = 30f;
    public const float PhaseTimeoutSeconds = 8f;
    public const int MaximumRequests = 2;

    Phase phase = Phase.WaitingForNativeReadiness;
    float beganAt = float.NaN;
    float phaseBeganAt = float.NaN;
    int requests;
    bool lastPlacementValid;
    bool lastSupplyDrop1CanExecute;

    public Phase CurrentPhase => phase;
    public int Requests => requests;

    // Reused by the CLI/selector fixture: this mode cannot combine with a
    // different survivor, alternate loadout, Toolbot sequence, or slot isolation.
    public static string SelectorRefusal(bool requested, string survivor, bool variantOverride,
                                         string isolatedSlot, bool toolbotOffhand, bool sirenSourceEntry = false)
    {
        if (!requested)
            return null;
        if (!string.Equals(survivor, "Captain", StringComparison.Ordinal))
            return "captain-supply-beacon-requires-Captain";
        if (variantOverride)
            return "captain-supply-beacon-requires-default-loadout";
        if (!string.IsNullOrEmpty(isolatedSlot))
            return "captain-supply-beacon-conflicts-with-slot-isolation";
        if (toolbotOffhand)
            return "captain-supply-beacon-conflicts-with-Toolbot-offhand";
        if (sirenSourceEntry)
            return "captain-supply-beacon-conflicts-with-Siren-source-entry";
        return null;
    }

    public Decision Step(Observation observation)
    {
        if (observation == null)
            return Refuse("missing-observation");
        if (phase == Phase.Complete || phase == Phase.Refused)
            return Snapshot(-1, phase == Phase.Complete ? "captain-supply-beacon-sequence-complete" : "captain-supply-beacon-refused");
        if (float.IsNaN(observation.elapsedSeconds) || float.IsInfinity(observation.elapsedSeconds) || observation.elapsedSeconds < 0)
            return Refuse("invalid-elapsed-time");
        if (float.IsNaN(beganAt))
        {
            beganAt = observation.elapsedSeconds;
            phaseBeganAt = observation.elapsedSeconds;
        }
        if (observation.elapsedSeconds - beganAt >= MaximumSeconds)
            return Refuse("sequence-deadline");
        if (!observation.exactCaptainOwner)
            return Refuse("captain-owner-changed");
        if (!observation.exactDefaultSupplySkill)
            return Refuse("native-default-supply-skill-changed");
        if (!observation.isolatedDiagnosticInputOwned)
            return Refuse("diagnostic-input-owner-lost");
        if (observation.neutralRevisionChanged)
            return Refuse("neutralized-request-cancelled");
        if (phase == Phase.AwaitingValidPlacement)
        {
            lastPlacementValid = observation.nativePlacementValid;
            lastSupplyDrop1CanExecute = observation.supplyDrop1CanExecute;
        }
        if (observation.elapsedSeconds - phaseBeganAt >= PhaseTimeoutSeconds)
            return Refuse(TimeoutOutcome());

        switch (phase)
        {
            case Phase.WaitingForNativeReadiness:
                if (observation.setupSupplyDropState)
                    return Refuse("setup-state-before-owned-special-request");
                if (observation.specialCanExecute)
                {
                    if (requests >= MaximumRequests)
                        return Refuse("request-budget-exhausted");
                    requests++;
                    phase = Phase.AwaitingSpecialEdgeAndCallbacks;
                    phaseBeganAt = observation.elapsedSeconds;
                    return Snapshot(3, "captain-special-pulse-requested");
                }
                return Snapshot(-1, "waiting-for-native-special-readiness");

            case Phase.AwaitingSpecialEdgeAndCallbacks:
                if (observation.specialInputEdge && observation.specialAuthorityCallback && observation.specialServerCallback)
                    Move(Phase.AwaitingSetupAndSlotRemap, observation.elapsedSeconds);
                return Snapshot(-1, observation.setupSupplyDropState ?
                    "setup-observed-waiting-for-special-edge-and-native-callback-pair" :
                    "waiting-for-special-edge-and-native-callback-pair");

            case Phase.AwaitingSetupAndSlotRemap:
                if (observation.setupSupplyDropState && observation.setupPrimaryIsSupplyDrop1 &&
                    observation.setupSecondaryIsSupplyDrop2)
                    Move(Phase.AwaitingValidPlacement, observation.elapsedSeconds);
                return Snapshot(-1, "waiting-for-original-setup-state-and-slot-remap");

            case Phase.AwaitingValidPlacement:
                if (!observation.setupSupplyDropState || !observation.setupPrimaryIsSupplyDrop1 ||
                    !observation.setupSecondaryIsSupplyDrop2)
                    return Refuse("native-setup-or-slot-remap-lost-before-placement");
                if (observation.nativePlacementValid && observation.supplyDrop1CanExecute)
                {
                    if (requests >= MaximumRequests)
                        return Refuse("request-budget-exhausted");
                    requests++;
                    Move(Phase.AwaitingSupplyEdgeAndCallbacks, observation.elapsedSeconds);
                    return Snapshot(0, "captain-supply-drop1-primary-pulse-requested");
                }
                return Snapshot(-1, "waiting-for-original-valid-placement-and-supply-readiness");

            case Phase.AwaitingSupplyEdgeAndCallbacks:
                if (observation.supplyDrop1InputEdge && observation.supplyDrop1AuthorityCallback &&
                    observation.supplyDrop1ServerCallback)
                    Move(Phase.AwaitingNativeSupplyState, observation.elapsedSeconds);
                return Snapshot(-1, observation.nativeCallSupplyDropHealingState ?
                    "call-state-observed-waiting-for-primary-edge-and-supply-callback-pair" :
                    "waiting-for-primary-edge-and-supply-callback-pair");

            case Phase.AwaitingNativeSupplyState:
                if (observation.nativeCallSupplyDropHealingState)
                    Move(Phase.AwaitingOwnedDeployableAndReturn, observation.elapsedSeconds);
                return Snapshot(-1, "waiting-for-original-supply-drop-state");

            case Phase.AwaitingOwnedDeployableAndReturn:
                if (observation.ownedCaptainSupplyDropCountIncreased && observation.returnedToOrdinaryBodyState)
                {
                    phase = Phase.Complete;
                    return Snapshot(-1, "captain-supply-beacon-sequence-complete");
                }
                return Snapshot(-1, "waiting-for-native-deployable-and-normal-state-return");

            default:
                return Refuse("invalid-sequence-phase");
        }
    }

    public Decision Cancel()
    {
        if (phase == Phase.Complete || phase == Phase.Refused)
            return Snapshot(-1, "captain-supply-beacon-sequence-already-terminal");
        return Refuse("sequence-cancelled");
    }

    Decision Snapshot(int slot, string outcome)
    {
        return new Decision { phase = phase, requestInputSlot = slot, outcome = outcome,
                              completed = phase == Phase.Complete, refused = phase == Phase.Refused };
    }

    Decision Refuse(string outcome)
    {
        phase = Phase.Refused;
        return Snapshot(-1, outcome);
    }

    void Move(Phase next, float now)
    {
        phase = next;
        phaseBeganAt = now;
    }

    string TimeoutOutcome()
    {
        switch (phase)
        {
            case Phase.WaitingForNativeReadiness: return "special-not-native-ready";
            case Phase.AwaitingSpecialEdgeAndCallbacks: return "special-edge-or-callback-pair-timeout";
            case Phase.AwaitingSetupAndSlotRemap: return "setup-state-or-slot-remap-timeout";
            case Phase.AwaitingValidPlacement:
                if (!lastPlacementValid && !lastSupplyDrop1CanExecute)
                    return "native-placement-and-supply-drop1-not-ready";
                if (!lastPlacementValid)
                    return "native-placement-not-valid";
                return "native-supply-drop1-not-ready";
            case Phase.AwaitingSupplyEdgeAndCallbacks: return "supply-edge-or-callback-pair-timeout";
            case Phase.AwaitingNativeSupplyState: return "native-supply-state-timeout";
            case Phase.AwaitingOwnedDeployableAndReturn: return "native-deployable-or-state-return-timeout";
            default: return "sequence-phase-timeout";
        }
    }
}
