// Subsystem: input/skill coverage (diagnostic only). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: constructed after the native skill observer; Apply after the world input producer;
// teardown before the owned body/world is released.
using System;
using RoR2;
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
        public bool active, completed, cleaned;
        public int requests;
        public float elapsedSeconds;
        public string outcome;
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

    public Report reportData => report;

    public SurvivorSkillInputCoverage(CharacterBody ownedBody, NovaInputBridge ownedBridge, SurvivorSkillObserver.Report observerReport)
    {
        if (!ownedBody || !ownedBody.skillLocator || !ownedBridge || observerReport == null || observerReport.slots == null ||
            observerReport.slots.Length != 4)
            throw new ArgumentException("Owned body, input bridge and four-slot observer report are required");
        if (ownedBody.gameObject != ownedBridge.gameObject || !ownedBody.inputBank || ownedBridge.bank != ownedBody.inputBank)
            throw new ArgumentException("The bridge and original input bank must belong to the owned body");

        body = ownedBody;
        bridge = ownedBridge;
        observed = observerReport;
        report = new Report { active = false, outcome = "waiting-for-diagnostic-input", slots = new SlotCoverage[4] };
        for (int i = 0; i < 4; i++)
        {
            if (!ownedBody.skillLocator.GetSkill((SkillSlot)i))
                throw new ArgumentException("Original canonical skill slot missing: " + SlotNames[i], nameof(ownedBody));
            var slot = observerReport.slots[i];
            report.slots[i] = new SlotCoverage { slot = SlotNames[i], authorityBefore = slot.authorityActivations,
                                                 authorityAfter = slot.authorityActivations, serverBefore = slot.serverActivations,
                                                 serverAfter = slot.serverActivations };
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

        if (report.elapsedSeconds >= MaximumSeconds)
        {
            Stop("duration-exhausted");
            return;
        }
        if (!OwnsLiveDiagnosticInput())
        {
            if (pulseActive)
                ReleasePulse();
            report.active = false;
            report.outcome = "waiting-for-owned-live-diagnostic-input";
            return;
        }
        report.active = true;

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
        if (report.requests >= MaximumRequests)
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
        if (pulseActive && restoreIfOwned)
            RestoreOwnedOverlayIfCurrent();
        pulseActive = false;
        target = -1;
    }

    void Stop(string outcome)
    {
        ReleasePulse(true);
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
        report.active = false;
        report.cleaned = true;
        body = null;
        bridge = null;
        observed = null;
    }
}
