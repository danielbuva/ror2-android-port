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
    public bool diagnosticEquipment, touchEquipment;
    public bool enablePrimary, enableAllSkills, diagnosticInput;
    public bool diagnosticSprint, diagnosticPrimary, diagnosticSecondary, diagnosticUtility, diagnosticSpecial, diagnosticInteract;
    public Vector3 diagnosticAim;
    public bool diagnosticJumpRequest { get; private set; }
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
            if (!bank || mapping == null || !focused)
            {
                presence?.Suspend();
                Neutral();
                return;
            }
            if (presence == null)
                presence = new ControllerPresence(requiredControllerName);
            if (Time.timeScale == 0)
            {
                presence.Suspend();
                Neutral();
                return;
            }
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
        if (!bank || mapping == null || !focused || Time.timeScale == 0)
        {
            Neutral();
            return;
        }
        if (!diagnosticInput && (presence == null || !presence.connected))
        {
            Neutral();
            return;
        }
        if (!diagnosticInput && !presence.Matches(UnityEngine.Input.GetJoystickNames()))
        {
            presence.Suspend();
            Neutral();
            return;
        }
        bank.moveVector = thirdPerson != null && !diagnosticInput ? thirdPerson.Movement(movement) : new Vector3(movement.x, 0, movement.y);
        bank.SetRawMoveStates(movement);
        if (diagnosticInput && diagnosticAim.sqrMagnitude > 0)
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
        else if (aim.sqrMagnitude > 0)
        {
            bank.aimDirection = new Vector3(aim.x, 0, aim.y);
            aimTicks++;
        }
        bank.jump.PushState(jumpHeld || jumpLatched);
        if (bank.jump.justPressed)
            jumpPresses++;
        jumpLatched = false;
        bank.activateEquipment.PushState((diagnosticInput && diagnosticEquipment) || touchEquipment);
        touchEquipment = false;
        bank.sprint.PushState(diagnosticInput && diagnosticSprint);
        var raw = diagnosticInput ? null : ReadRaw();
        bank.interact.PushState(diagnosticInput ? diagnosticInteract : mapping.enableInteraction && raw.buttons[mapping.interact]);
        bool all = mapping.enableSkills || enableAllSkills;
        bank.skill1.PushState(diagnosticInput ? diagnosticPrimary : (all || enablePrimary) && raw.buttons[mapping.primary]);
        bank.skill2.PushState(diagnosticInput ? diagnosticSecondary : all && raw.buttons[mapping.secondary]);
        bank.skill3.PushState(diagnosticInput ? diagnosticUtility : all && raw.buttons[mapping.utility]);
        bank.skill4.PushState(diagnosticInput ? diagnosticSpecial : all && raw.buttons[mapping.special]);
        fixedTicks++;
    }
    public void DiagnosticJump(bool down)
    {
        diagnosticJumpRevision++;
        diagnosticJumpRequest = down;
        jumpLatched |= down && !jumpHeld;
        jumpHeld = down;
    }
    public void Neutral()
    {
        diagnosticJumpRevision++;
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
        touchEquipment = diagnosticEquipment = false;
    }
    void OnApplicationFocus(bool value)
    {
        focused = value;
        if (!value)
        {
            presence?.Suspend();
            Neutral();
        }
    }
    void OnApplicationPause(bool value)
    {
        focused = !value;
        if (value)
        {
            presence?.Suspend();
            Neutral();
        }
    }
    void OnDisable()
    {
        presence?.Suspend();
        Neutral();
    }
}
