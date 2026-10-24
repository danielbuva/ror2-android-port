// Subsystem: input/camera (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup Update, FixedUpdate; teardown —.
using System;
using System.Linq;
using RoR2;
using UnityEngine;

// Temporary, removable Nova input producer. No motor, transform, state or skill execution here.
[DefaultExecutionOrder(-20000)]
public sealed class NovaInputBridge : MonoBehaviour
{
    [Serializable]
    public class Mapping
    {
        public string attempt, observation;
        public int moveX, moveY, aimX, aimY, jump, primary, secondary, utility, special, interact;
        public float moveYSign, aimYSign;
        public bool enableSkills, enableInteraction;
        public void Validate(string expected)
        {
            if (attempt != expected || string.IsNullOrEmpty(observation))
                throw new Exception("Unmeasured or stale Nova mapping");
            var axes = new[] { moveX, moveY, aimX, aimY };
            var buttons = new[] { jump, primary, secondary, utility, special };
            if (axes.Any(x => x < 0 || x >= 16) || axes.Distinct().Count() != 4 || buttons.Any(x => x < 0 || x >= 20) ||
                buttons.Distinct().Count() != 5 || Mathf.Abs(moveYSign) != 1 || Mathf.Abs(aimYSign) != 1)
                throw new Exception("Invalid Nova bindings");
            if (enableInteraction && (interact < 0 || interact >= 20 || buttons.Contains(interact)))
                throw new Exception("Invalid measured interaction binding");
        }
    }
    [Serializable]
    public class Raw
    {
        public float[] axes = new float[16];
        public bool[] buttons = new bool[20];
    }
    // Unity's measured slot-1 exposure is the only accepted mapping. A temporary
    // absence must release every held action, then require a stable neutral sample
    // from that same slot/name before physical input resumes.
    public sealed class ControllerPresence
    {
        public const float ReacquireSeconds = .25f;
        public readonly string expectedName;
        public bool connected { get; private set; }
        public int suspensions { get; private set; }
        public int reconnections { get; private set; }
        bool everConnected;
        float neutralSince = -1;
        public ControllerPresence(string name)
        {
            if (string.IsNullOrEmpty(name))
                throw new ArgumentException("Measured controller name required", nameof(name));
            expectedName = name;
        }
        public bool Matches(string[] names)
        {
            if (names == null || names.Length == 0 || names[0] != expectedName)
                return false;
            for (int i = 1; i < names.Length; i++)
                if (!string.IsNullOrEmpty(names[i]))
                    return false;
            return true;
        }
        public bool Observe(string[] names, bool neutral, float now)
        {
            if (!Matches(names))
            {
                Suspend();
                return false;
            }
            if (connected)
                return true;
            if (!neutral)
            {
                neutralSince = -1;
                return false;
            }
            if (neutralSince < 0)
            {
                neutralSince = now;
                return false;
            }
            if (now - neutralSince < ReacquireSeconds)
                return false;
            connected = true;
            if (everConnected)
                reconnections++;
            everConnected = true;
            return true;
        }
        public void Suspend()
        {
            if (connected)
                suspensions++;
            connected = false;
            neutralSince = -1;
        }
    }
    public InputBankTest bank;
    public Mapping mapping;
    public string error;
    public NovaThirdPersonView thirdPerson;
    public AndroidTouchInput touchControls;
    public bool manualInputAvailable => physicalInputAvailable || touchControls != null;
    bool touchPauseRequested;
    public bool OwnsTouchGuiMouse => !diagnosticInput && (touchPauseRequested || touchControls != null && touchControls.OwnsGuiMouse);
    public bool ConsumeTouchPauseRequest()
    {
        bool requested = touchPauseRequested;
        touchPauseRequested = false;
        return requested;
    }
    public bool diagnosticEquipment, touchEquipment;
    public bool enablePrimary, enableAllSkills, diagnosticInput;
    // Opt-in only for the exact unsupported-model bringup diagnostic owner.
    // Legacy bridge callers default false and retain mapped/null-map behavior.
    public bool automaticDiagnosticOnly;
    public bool physicalInputAvailable => IsPhysicalInputAvailable(automaticDiagnosticOnly, mapping);
    // Owned only by SurvivorSkillInputCoverage; the sink enforces the mode on
    // every FixedUpdate, independent of ordinary producer timing.
    public bool isolatedDiagnosticSkillInput, isolatedDiagnosticSkillPulse;
    // NovaInputSession owns this diagnostic-only sink hold; manual controller and
    // touch-equipment requests retain their independent paths.
    public bool manualMoonAutomaticHold;
    public int manualMoonNeutralFixedTicks;
    public int isolatedDiagnosticSkillSlot = -1;
    public int inputNeutralRevision;
    public bool diagnosticSprint, diagnosticPrimary, diagnosticSecondary, diagnosticUtility, diagnosticSpecial, diagnosticInteract;
    public Vector3 diagnosticAim;
    public bool diagnosticJumpRequest { get; private set; }
    // Toolbot's bounded offhand diagnostic reads these cumulative witnesses
    // because Apply may run several frames after the fixed-tick edge.
    bool diagnosticInputEdgeWitnessEnabled;
    readonly long[] diagnosticInputEdgeCounts = new long[4];

    public void SetDiagnosticInputEdgeWitness(bool enabled)
    {
        diagnosticInputEdgeWitnessEnabled = enabled;
    }

    public bool TryGetDiagnosticInputEdgeCount(int slot, out long count)
    {
        count = 0;
        if (!diagnosticInputEdgeWitnessEnabled || slot < 0 || slot >= diagnosticInputEdgeCounts.Length)
            return false;
        count = diagnosticInputEdgeCounts[slot];
        return true;
    }

    // Called immediately after the real InputBankTest.PushState call. Saturation
    // keeps this diagnostic monotonic; saturation then fails closed as no delta.
    public static long AdvanceDiagnosticInputEdgeCount(long count, bool enabled, bool justPressed)
    {
        return enabled && justPressed && count < long.MaxValue ? count + 1 : count;
    }
    public static bool SkillInputRequest(bool diagnosticMode, bool isolate, bool pulse, int selectedSlot,
                                         int buttonSlot, bool diagnosticRequest, bool physicalRequest)
    {
        if (!diagnosticMode)
            return physicalRequest;
        if (!isolate)
            return diagnosticRequest;
        return pulse && selectedSlot == buttonSlot;
    }
    public static bool EquipmentInputRequest(bool diagnosticMode, bool isolate, bool diagnosticRequest, bool touchRequest)
    {
        return (diagnosticMode && diagnosticRequest && !isolate) || touchRequest;
    }
    public static bool ShouldHoldAutomaticDiagnosticInput(bool diagnosticInput, bool requested)
    {
        return diagnosticInput && requested;
    }
    public bool SetManualMoonAutomaticHold(bool requested)
    {
        bool held = ShouldHoldAutomaticDiagnosticInput(diagnosticInput, requested);
        if (manualMoonAutomaticHold && !held)
            ClearAutomaticDiagnosticRequests();
        manualMoonAutomaticHold = held;
        return held;
    }
    void ClearAutomaticDiagnosticRequests()
    {
        movement = aim = Vector2.zero;
        diagnosticAim = Vector3.zero;
        diagnosticJumpRevision++;
        diagnosticJumpRequest = false;
        jumpHeld = jumpLatched = false;
        diagnosticSprint = diagnosticPrimary = diagnosticSecondary = diagnosticUtility = diagnosticSpecial =
            diagnosticInteract = diagnosticEquipment = false;
        isolatedDiagnosticSkillPulse = false;
        // Manual touch-equipment requests have an independent owner and are preserved.
    }
    public struct DiagnosticJumpSnapshot
    {
        internal bool request, held, latched;
        internal int revision, fixedTick;
        public bool Pending => latched;
        public int Revision => revision;
    }
    int diagnosticJumpRevision;
    public DiagnosticJumpSnapshot CaptureDiagnosticJump()
    {
        return new DiagnosticJumpSnapshot { request = diagnosticJumpRequest, held = jumpHeld, latched = jumpLatched,
                                            revision = diagnosticJumpRevision, fixedTick = fixedTicks };
    }
    // Return only a still-owned diagnostic write. Direct field restoration must
    // not generate another jump edge. A fixed tick consumes any baseline latch.
    public bool RestoreDiagnosticJump(DiagnosticJumpSnapshot producer, DiagnosticJumpSnapshot overlay)
    {
        if (!diagnosticInput || overlay.revision == producer.revision || diagnosticJumpRevision != overlay.revision ||
            diagnosticJumpRequest != overlay.request || jumpHeld != overlay.held)
            return false;
        diagnosticJumpRequest = producer.request;
        jumpHeld = producer.held;
        jumpLatched = producer.latched && fixedTicks == producer.fixedTick;
        diagnosticJumpRevision++;
        return true;
    }
    public Vector2 movement, aim;
    public int fixedTicks, jumpPresses, aimTicks;
    bool focused = true, jumpHeld, jumpLatched;
    ControllerPresence presence;
    static string requiredControllerName;
    public bool controllerConnected => presence != null && presence.connected;
    public int controllerSuspensions => presence == null ? 0 : presence.suspensions;
    public int controllerReconnections => presence == null ? 0 : presence.reconnections;
    public static void RequireNova()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        using (var build = new AndroidJavaClass(
                   "android.os.Build")) if (build.GetStatic<string>("MODEL") !=
                                            "Retroid Pocket Nova") throw new Exception("This bridge is authorized only for Nova");
#else
        throw new Exception("Nova physical input requires the Android device");
#endif
        var names = UnityEngine.Input.GetJoystickNames();
        if (names.Length == 0 || string.IsNullOrEmpty(names[0]) || names.Count(x => !string.IsNullOrEmpty(x)) != 1)
            throw new Exception("Require one controller in Unity joystick slot 1");
        requiredControllerName = names[0];
    }
    public static bool IsAutomaticDiagnosticWithoutPhysicalInput(bool diagnosticMode, bool automaticDiagnosticOnly)
    {
        return diagnosticMode && automaticDiagnosticOnly;
    }
    public static bool IsPhysicalInputAvailable(bool automaticDiagnosticOnly, Mapping mapping)
    {
        return !automaticDiagnosticOnly && mapping != null;
    }
    public static bool MissingMappingRequiresNeutral(bool mappingMissing, bool diagnosticMode, bool automaticDiagnosticOnly)
    {
        return mappingMissing && !IsAutomaticDiagnosticWithoutPhysicalInput(diagnosticMode, automaticDiagnosticOnly);
    }
    public static Raw ReadRaw()
    {
        var raw = new Raw();
        for (int i = 0; i < raw.axes.Length; i++)
            raw.axes[i] = UnityEngine.Input.GetAxisRaw("NovaLabAxis" + i);
        for (int i = 0; i < raw.buttons.Length; i++)
            raw.buttons[i] = UnityEngine.Input.GetKey((KeyCode)((int)KeyCode.Joystick1Button0 + i));
        return raw;
    }
    static Vector2 Stick(Raw raw, int x, int y, float sign)
    {
        var v = new Vector2(raw.axes[x], raw.axes[y] * sign);
        float n = v.magnitude;
        return n <= AndroidOfflineSettings.current.deadzone
                   ? Vector2.zero
                   : v / n * Mathf.Min(1, (n - AndroidOfflineSettings.current.deadzone) / (1 - AndroidOfflineSettings.current.deadzone));
    }
    static bool NeutralSample(Raw raw, Mapping map)
    {
        for (int i = 0; i < raw.buttons.Length; i++)
            if (raw.buttons[i])
                return false;
        var limit = AndroidOfflineSettings.current.deadzone;
        return Mathf.Abs(raw.axes[map.moveX]) <= limit && Mathf.Abs(raw.axes[map.moveY]) <= limit &&
               Mathf.Abs(raw.axes[map.aimX]) <= limit && Mathf.Abs(raw.axes[map.aimY]) <= limit;
    }
    void Update()
    {
        try
        {
            if (!bank || !focused)
            {
                presence?.Suspend();
                SetManualMoonAutomaticHold(false);
                Neutral();
                return;
            }
            if (Time.timeScale == 0)
            {
                presence?.Suspend();
                SetManualMoonAutomaticHold(false);
                Neutral();
                return;
            }
            if (touchControls != null && !diagnosticInput)
            {
                touchControls.Poll();
                if (touchControls.Pressed(AndroidTouchInput.Action.Pause))
                {
                    touchControls.report.pauseRequests++;
                    touchPauseRequested = true;
                    Neutral();
                    return;
                }
                if (thirdPerson != null)
                    thirdPerson.LookTouch(touchControls.LookDelta, touchControls.ViewHeight);
                if (touchControls.HasInput || !physicalInputAvailable)
                {
                    movement = touchControls.Movement;
                    aim = Vector2.zero;
                    diagnosticJumpRevision++;
                    jumpHeld = touchControls.Down(AndroidTouchInput.Action.Jump);
                    jumpLatched |= touchControls.Pressed(AndroidTouchInput.Action.Jump);
                    return;
                }
            }
            if (IsAutomaticDiagnosticWithoutPhysicalInput(diagnosticInput, automaticDiagnosticOnly))
            {
                presence?.Suspend();
                SetManualMoonAutomaticHold(false);
                return;
            }
            if (mapping == null)
            {
                presence?.Suspend();
                SetManualMoonAutomaticHold(false);
                Neutral();
                return;
            }
            if (presence == null)
                presence = new ControllerPresence(requiredControllerName);
            var names = UnityEngine.Input.GetJoystickNames();
            // The developer's deterministic input is independent of the physical
            // controller. Keep observing its connection for later manual takeover, but
            // never stall automated source gameplay when Android drops that device.
            if (diagnosticInput)
            {
                if (!presence.Matches(names))
                    presence.Suspend();
                else
                    presence.Observe(names, NeutralSample(ReadRaw(), mapping), Time.realtimeSinceStartup);
                return;
            }
            if (!presence.Matches(names))
            {
                presence.Suspend();
                Neutral();
                return;
            }
            var raw = ReadRaw();
            if (!presence.Observe(names, NeutralSample(raw, mapping), Time.realtimeSinceStartup))
            {
                Neutral();
                return;
            }
            movement = Stick(raw, mapping.moveX, mapping.moveY, mapping.moveYSign);
            aim = Stick(raw, mapping.aimX, mapping.aimY, mapping.aimYSign);
            if (thirdPerson != null)
                thirdPerson.Look(aim);
            bool down = raw.buttons[mapping.jump];
            diagnosticJumpRevision++;
            jumpLatched |= down && !jumpHeld;
            jumpHeld = down;
        }
        catch (Exception e)
        {
            error = e.ToString();
            enabled = false;
            Neutral();
        }
    }
    void FixedUpdate()
    {
        bool noPhysicalDiagnostic = IsAutomaticDiagnosticWithoutPhysicalInput(diagnosticInput, automaticDiagnosticOnly);
        bool touchManual = !diagnosticInput && touchControls != null && (touchControls.HasInput || !physicalInputAvailable);
        if (!bank || !focused || Time.timeScale == 0 || touchPauseRequested ||
            (!touchManual && MissingMappingRequiresNeutral(mapping == null, diagnosticInput, automaticDiagnosticOnly)))
        {
            Neutral();
            return;
        }
        if (!touchManual && !noPhysicalDiagnostic && !diagnosticInput && (presence == null || !presence.connected))
        {
            Neutral();
            return;
        }
        if (!touchManual && !noPhysicalDiagnostic && !diagnosticInput && !presence.Matches(UnityEngine.Input.GetJoystickNames()))
        {
            presence.Suspend();
            Neutral();
            return;
        }
        bool holdAutomatic = ShouldHoldAutomaticDiagnosticInput(diagnosticInput, manualMoonAutomaticHold);
        Vector2 effectiveMovement = holdAutomatic ? Vector2.zero : movement;
        bank.moveVector = thirdPerson != null && !diagnosticInput ? thirdPerson.Movement(movement)
                                                                   : new Vector3(effectiveMovement.x, 0, effectiveMovement.y);
        bank.SetRawMoveStates(effectiveMovement);
        if (holdAutomatic)
            bank.aimDirection = Vector3.zero;
        else if (diagnosticInput && diagnosticAim.sqrMagnitude > 0)
        {
            bank.aimDirection = diagnosticAim;
            aimTicks++;
        }
        else if (thirdPerson != null && !diagnosticInput)
        {
            bank.aimDirection = thirdPerson.Aim();
            aimTicks++;
            thirdPerson.report.maxAimError =
                Mathf.Max(thirdPerson.report.maxAimError, Vector3.Angle(bank.aimDirection, thirdPerson.report.direction));
        }
        else if (!holdAutomatic && aim.sqrMagnitude > 0)
        {
            bank.aimDirection = new Vector3(aim.x, 0, aim.y);
            aimTicks++;
        }
        bank.jump.PushState(!holdAutomatic && (jumpHeld || jumpLatched));
        if (bank.jump.justPressed)
            jumpPresses++;
        jumpLatched = false;
        bool isolatedSkills = diagnosticInput && isolatedDiagnosticSkillInput;
        bank.activateEquipment.PushState(EquipmentInputRequest(diagnosticInput, isolatedDiagnosticSkillInput,
            holdAutomatic ? false : diagnosticEquipment,
            touchEquipment || touchManual && touchControls.Request(AndroidTouchInput.Action.Equipment)));
        touchEquipment = false;
        bank.sprint.PushState(diagnosticInput ? !holdAutomatic && diagnosticSprint
                                             : touchManual && touchControls.Request(AndroidTouchInput.Action.Sprint));
        var raw = diagnosticInput || touchManual ? null : ReadRaw();
        bank.interact.PushState(diagnosticInput ? (!holdAutomatic && diagnosticInteract)
            : touchManual ? touchControls.Request(AndroidTouchInput.Action.Interact)
                          : mapping.enableInteraction && raw.buttons[mapping.interact]);
        bool all = !automaticDiagnosticOnly && mapping != null && mapping.enableSkills || enableAllSkills;
        bank.skill1.PushState(!holdAutomatic && SkillInputRequest(diagnosticInput, isolatedSkills, isolatedDiagnosticSkillPulse,
                                                isolatedDiagnosticSkillSlot, 0, diagnosticPrimary,
                                                !diagnosticInput && (all || enablePrimary) &&
                                                (touchManual ? touchControls.Request(AndroidTouchInput.Action.Primary) : raw.buttons[mapping.primary])));
        diagnosticInputEdgeCounts[0] = AdvanceDiagnosticInputEdgeCount(diagnosticInputEdgeCounts[0],
            diagnosticInputEdgeWitnessEnabled, bank.skill1.justPressed);
        bank.skill2.PushState(!holdAutomatic && SkillInputRequest(diagnosticInput, isolatedSkills, isolatedDiagnosticSkillPulse,
                                                isolatedDiagnosticSkillSlot, 1, diagnosticSecondary,
                                                !diagnosticInput && all &&
                                                (touchManual ? touchControls.Request(AndroidTouchInput.Action.Secondary) : raw.buttons[mapping.secondary])));
        diagnosticInputEdgeCounts[1] = AdvanceDiagnosticInputEdgeCount(diagnosticInputEdgeCounts[1],
            diagnosticInputEdgeWitnessEnabled, bank.skill2.justPressed);
        bank.skill3.PushState(!holdAutomatic && SkillInputRequest(diagnosticInput, isolatedSkills, isolatedDiagnosticSkillPulse,
                                                isolatedDiagnosticSkillSlot, 2, diagnosticUtility,
                                                !diagnosticInput && all &&
                                                (touchManual ? touchControls.Request(AndroidTouchInput.Action.Utility) : raw.buttons[mapping.utility])));
        diagnosticInputEdgeCounts[2] = AdvanceDiagnosticInputEdgeCount(diagnosticInputEdgeCounts[2],
            diagnosticInputEdgeWitnessEnabled, bank.skill3.justPressed);
        bank.skill4.PushState(!holdAutomatic && SkillInputRequest(diagnosticInput, isolatedSkills, isolatedDiagnosticSkillPulse,
                                                isolatedDiagnosticSkillSlot, 3, diagnosticSpecial,
                                                !diagnosticInput && all &&
                                                (touchManual ? touchControls.Request(AndroidTouchInput.Action.Special) : raw.buttons[mapping.special])));
        diagnosticInputEdgeCounts[3] = AdvanceDiagnosticInputEdgeCount(diagnosticInputEdgeCounts[3],
            diagnosticInputEdgeWitnessEnabled, bank.skill4.justPressed);
        fixedTicks++;
        if (touchManual)
        {
            ObserveTouchBank();
            touchControls.ConsumeFixedTick();
        }
        if (holdAutomatic)
            manualMoonNeutralFixedTicks++;
    }
    public void DiagnosticJump(bool down)
    {
        diagnosticJumpRevision++;
        diagnosticJumpRequest = down;
        jumpLatched |= down && !jumpHeld;
        jumpHeld = down;
    }
    void ObserveTouchBank()
    {
        if (touchControls == null || bank == null) return;
        var report = touchControls.report;
        report.manualBankHeldMask = (bank.jump.down ? 1 : 0) | (bank.skill1.down ? 2 : 0) |
            (bank.skill2.down ? 4 : 0) | (bank.skill3.down ? 8 : 0) | (bank.skill4.down ? 16 : 0) |
            (bank.activateEquipment.down ? 32 : 0) | (bank.interact.down ? 64 : 0) | (bank.sprint.down ? 128 : 0);
        if (bank.jump.justPressed) report.bankPresses[0]++;
        if (bank.skill1.justPressed) report.bankPresses[1]++;
        if (bank.skill2.justPressed) report.bankPresses[2]++;
        if (bank.skill3.justPressed) report.bankPresses[3]++;
        if (bank.skill4.justPressed) report.bankPresses[4]++;
        if (bank.activateEquipment.justPressed) report.bankPresses[5]++;
        if (bank.interact.justPressed) report.bankPresses[6]++;
        if (bank.sprint.justPressed) report.bankPresses[7]++;
    }
    public void Neutral()
    {
        touchControls?.Suspend();
        diagnosticJumpRevision++;
        inputNeutralRevision++;
        movement = aim = Vector2.zero;
        diagnosticJumpRequest = false;
        jumpHeld = jumpLatched = false;
        if (!bank)
            return;
        bank.moveVector = Vector3.zero;
        bank.SetRawMoveStates(Vector2.zero);
        bank.jump.PushState(false);
        bank.skill1.PushState(false);
        bank.skill2.PushState(false);
        bank.skill3.PushState(false);
        bank.skill4.PushState(false);
        bank.interact.PushState(false);
        bank.sprint.PushState(false);
        bank.activateEquipment.PushState(false);
        if (touchControls != null)
            touchControls.report.manualBankHeldMask = 0;
        touchEquipment = diagnosticEquipment = false;
        isolatedDiagnosticSkillPulse = false;
    }
    void OnApplicationFocus(bool value)
    {
        focused = value;
        SetManualMoonAutomaticHold(false);
        if (!value)
        {
            touchPauseRequested = false;
            presence?.Suspend();
            Neutral();
        }
    }
    void OnApplicationPause(bool value)
    {
        focused = !value;
        SetManualMoonAutomaticHold(false);
        if (value)
        {
            touchPauseRequested = false;
            presence?.Suspend();
            Neutral();
        }
    }
    void OnDisable()
    {
        touchPauseRequested = false;
        presence?.Suspend();
        SetManualMoonAutomaticHold(false);
        Neutral();
    }
}
