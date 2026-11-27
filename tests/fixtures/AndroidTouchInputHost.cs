using System;
using UnityEngine;

static class AndroidTouchInputHost
{
    static void Check(bool value, string message)
    {
        if (!value) throw new Exception(message);
    }
    static AndroidTouchInput Ready()
    {
        var input = new AndroidTouchInput();
        input.Layout(new Rect(0, 0, 1920, 1080), new Vector2(1920, 1080));
        input.BeginFrame(0); input.EndFrame();
        return input;
    }
    static void MultiPointer()
    {
        var input = Ready();
        var move = input.MoveCenter + new Vector2(125, 0);
        var look = new Vector2(1400, 800);
        var fire = input.ButtonRect(AndroidTouchInput.Action.Primary).center;
        input.BeginFrame(3);
        input.Pointer(17, move, true, false, false);
        input.Pointer(25, look, true, false, false);
        input.Pointer(80, fire, true, false, false);
        input.EndFrame();
        Check(input.Movement == Vector2.right && input.Down(AndroidTouchInput.Action.Primary), "independent movement and primary");
        input.ConsumeFixedTick();
        input.BeginFrame(3);
        input.Pointer(17, move, false, false, false);
        input.Pointer(25, look + new Vector2(50, 30), false, false, false);
        input.Pointer(80, fire, false, false, false);
        input.EndFrame();
        Check(input.LookDelta == new Vector2(50, 30), "camera delta follows captured finger");
        Check(input.Movement == Vector2.right && input.Down(AndroidTouchInput.Action.Primary), "other fingers stay held");
        input.BeginFrame(2);
        input.Pointer(25, look, false, false, false);
        input.Pointer(80, fire, false, true, false);
        input.EndFrame();
        Check(input.Movement == Vector2.zero && !input.Request(AndroidTouchInput.Action.Primary), "missing movement and released button neutralize");
        Check(input.report.cancels == 1 && input.report.releases == 1, "cancellation and release are distinct");
    }
    static void ShortTaps()
    {
        var input = Ready();
        for (int i = 0; i < 8; i++)
        {
            var action = (AndroidTouchInput.Action)i;
            var point = input.ButtonRect(action).center;
            input.BeginFrame(1); input.Pointer(100 + i, point, true, false, false); input.EndFrame();
            input.BeginFrame(1); input.Pointer(100 + i, point, false, true, false); input.EndFrame();
            Check(!input.Down(action) && input.Request(action), "short tap survives until fixed tick: " + action);
            input.ConsumeFixedTick();
            Check(!input.Request(action) && input.report.consumedPresses[i] == 1, "exactly one pending edge: " + action);
            input.ConsumeFixedTick();
            Check(input.report.consumedPresses[i] == 1, "fixed tick cannot repeat released edge: " + action);
        }
    }
    static void Suspension()
    {
        var input = Ready();
        var jump = input.ButtonRect(AndroidTouchInput.Action.Jump).center;
        input.BeginFrame(1); input.Pointer(1, jump, true, false, false); input.EndFrame();
        input.Suspend();
        Check(!input.HasInput && !input.Request(AndroidTouchInput.Action.Jump), "pause clears held and pending actions");
        input.BeginFrame(1); input.Pointer(1, jump, true, false, false); input.EndFrame();
        Check(!input.HasInput && input.report.waitingForLift, "held pointer cannot reacquire across pause/focus loss");
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(1, jump, true, false, false); input.EndFrame();
        Check(input.Request(AndroidTouchInput.Action.Jump), "fresh touch after lift resumes");
        input.Layout(new Rect(60, 40, 1200, 650), new Vector2(1320, 730));
        Check(!input.HasInput && input.report.waitingForLift, "orientation/safe-area change releases old capture");
    }
    static void Cancellation()
    {
        var input = Ready();
        var point = input.ButtonRect(AndroidTouchInput.Action.Utility).center;
        input.BeginFrame(1); input.Pointer(8, point, false, false, false); input.EndFrame();
        Check(!input.HasInput, "a moved pointer never creates a new action");
        input.BeginFrame(1); input.Pointer(8, point, true, false, false); input.EndFrame();
        input.BeginFrame(1); input.Pointer(8, point, false, false, true); input.EndFrame();
        Check(!input.Request(AndroidTouchInput.Action.Utility), "canceled pending edge cannot fire");
        input.Layout(new Rect(0, 0, 0, 0), Vector2.zero);
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(9, point, true, false, false); input.EndFrame();
        Check(!input.HasInput && input.Movement == Vector2.zero, "zero viewport cannot produce nonfinite movement");
    }
    static void CameraDelta()
    {
        AndroidOfflineSettings.current = new AndroidOfflineSettings.Values { lookSensitivity = 2 };
        var one = new CameraFixture();
        one.LookTouch(Vector2.zero, 1080);
        Check(one.poses == 0, "stationary touch does not move camera");
        one.LookTouch(new Vector2(120, 60), 1080);
        Check(Math.Abs(one.yaw - 40) < .001f && Math.Abs(one.pitch + 20) < .001f, "pixel drag and sensitivity");
        var split = new CameraFixture();
        split.LookTouch(new Vector2(60, 30), 1080); split.LookTouch(new Vector2(60, 30), 1080);
        Check(one.yaw == split.yaw && one.pitch == split.pitch, "frame subdivision cannot change a drag");
        AndroidOfflineSettings.current.lookSensitivity = 1;
        AndroidOfflineSettings.current.invertY = true;
        var inverted = new CameraFixture();
        inverted.LookTouch(new Vector2(120, 60), 540);
        Check(inverted.yaw == one.yaw && inverted.pitch == -one.pitch, "viewport scaling and invert Y");
        inverted.LookTouch(new Vector2(100, 100), 0);
        Check(inverted.report.touchFrames == 1 && inverted.poses == 1, "invalid viewport does not move camera");
    }
    static void CameraAim()
    {
        var view = new CameraFixture();
        view.camera.ray = new Ray(Vector3.back, Vector3.forward);
        view.body.inputBank.aimOrigin = Vector3.up;
        var child = new CameraFixture.Collider();
        child.transform.parent = view.body.transform;
        var detached = new CameraFixture.Collider
        {
            hurtBox = new CameraFixture.HurtBox { healthComponent = view.body.healthComponent },
        };
        var enemy = new CameraFixture.Collider
        {
            hurtBox = new CameraFixture.HurtBox { healthComponent = new CameraFixture.HealthComponent() },
        };
        var farHit = new CameraFixture.RaycastHit(20, 19, new CameraFixture.Collider());
        var enemyHit = new CameraFixture.RaycastHit(10, 9, enemy);
        var childHit = new CameraFixture.RaycastHit(1, 0, child);
        var ownHit = new CameraFixture.RaycastHit(2, 1, detached);
        CameraFixture.Physics.supplied = new[] { farHit, childHit, enemyHit, ownHit };
        Check(view.Aim() == (enemyHit.point - view.body.inputBank.aimOrigin).normalized,
            "aim uses nearest eligible hit from native aim origin");
        Check(view.report.rayAim && view.report.aimPoint == enemyHit.point && view.report.detachedOwnHurtBoxRejections == 1,
            "camera report records selected external point and detached self-hit rejection");
        Check(view.camera.viewport == new Vector3(.5f, .5f, 0) && CameraFixture.Physics.distance == 500 &&
            CameraFixture.Physics.mask == (CameraFixture.LayerIndex.world.mask | CameraFixture.LayerIndex.entityPrecise.mask) &&
            CameraFixture.Physics.triggers == QueryTriggerInteraction.Ignore,
            "aim ray uses the center reticle and existing layer, trigger and range policy");

        CameraFixture.Physics.supplied = new[] { childHit, ownHit };
        var fallback = view.camera.ray.GetPoint(500);
        Check(view.Aim() == (fallback - view.body.inputBank.aimOrigin).normalized && view.report.aimPoint == fallback,
            "self-only hits use the same no-target fallback");
    }
    static void GuiOwnership()
    {
        var input = Ready();
        var move = input.MoveCenter;
        var pause = input.ButtonRect(AndroidTouchInput.Action.Pause).center;
        Check(pause == new Vector2(AndroidTouchInput.PauseGuiRect(1920).center.x, 1050), "pause shares native UI geometry");
        input.BeginFrame(2);
        input.Pointer(4, move, true, false, false, true);
        input.Pointer(8, pause, true, false, false);
        input.EndFrame();
        Check(input.Pressed(AndroidTouchInput.Action.Pause), "secondary finger cannot request pause while movement is held");
        Check(input.OwnsGuiMouse, "gameplay primary touch was not claimed before GUI widgets");
        input.Suspend(); input.BeginFrame(1);
        input.Pointer(4, move, false, false, false, true); input.EndFrame();
        Check(input.OwnsGuiMouse && !input.HasInput, "waiting for lift leaked held pointer to GUI");
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(9, new Vector2(960, 1046), true, false, false, true); input.EndFrame();
        Check(!input.HasInput && !input.OwnsGuiMouse, "reserved native UI strip became gameplay input");
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(1, pause, true, false, false, true); input.EndFrame();
        input.Suspend();
        Check(input.OwnsGuiMouse && !input.HasInput, "opening pause lost the captured GUI pointer");
        input.ObserveSuspendedTouches(1); input.Suspend();
        Check(input.OwnsGuiMouse, "paused neutralization leaked the held opening tap");
        input.ObserveSuspendedTouches(1);
        Check(input.OwnsGuiMouse, "opening tap release leaked into the modal");
        input.ObserveSuspendedTouches(0); input.Suspend();
        input.ObserveSuspendedTouches(1);
        Check(!input.OwnsGuiMouse, "fresh modal tap was captured after the opening pointer lifted");
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(1, pause, true, false, false, true); input.EndFrame();
        input.BeginFrame(1); input.Pointer(1, pause, false, true, false, true); input.EndFrame();
        Check(input.OwnsGuiMouse, "owned release event reached native GUI after touch ended");
    }
    static void BankWitness()
    {
        string[] fields = { "jump", "skill1", "skill2", "skill3", "skill4", "activateEquipment", "interact", "sprint" };
        for (int i = 0; i < fields.Length; i++)
        {
            var fixture = new BankFixture();
            var button = (BankFixture.Button)typeof(BankFixture.Bank).GetField(fields[i]).GetValue(fixture.bank);
            button.down = button.justPressed = true;
            fixture.ObserveTouchBank(true);
            Check(fixture.touchControls.report.manualBankHeldMask == 1 << i, "bank held slot alias: " + fields[i]);
            Check(fixture.touchControls.report.bankPresses[i] == 1, "native edge not observed: " + fields[i]);
            button.justPressed = false; fixture.ObserveTouchBank(true);
            Check(fixture.touchControls.report.bankPresses[i] == 1, "held state invented another native edge");
            button.down = false; fixture.ObserveTouchBank(false);
            Check(fixture.touchControls.report.manualBankHeldMask == 0, "bank release not observed");
            button.down = button.justPressed = true;
            fixture.ObserveTouchBank(false);
            Check(fixture.touchControls.report.manualBankHeldMask == 1 << i, "physical fallback bank state is stale");
            Check(fixture.touchControls.report.bankPresses[i] == 1, "physical fallback invented a touch edge");
            button.down = button.justPressed = false;
            fixture.ObserveTouchBank(false);
            Check(fixture.touchControls.report.manualBankHeldMask == 0, "physical fallback release is stale");
        }
    }
    static void JumpCancelBeforeFixed()
    {
        foreach (bool physical in new[] { false, true })
            foreach (bool missing in new[] { false, true })
            {
                var input = Ready(); var bridge = new TouchJumpFixture { touchControls = input };
                var jump = input.ButtonRect(AndroidTouchInput.Action.Jump).center;
                input.BeginFrame(1); input.Pointer(4, jump, true, false, false); input.EndFrame(); bridge.Update(physical);
                input.BeginFrame(missing ? 0 : 1);
                if (!missing) input.Pointer(4, jump, false, false, true);
                input.EndFrame(); bridge.Update(physical);
                Check(!bridge.Tick(physical), "canceled/missing jump survived until physics; physical=" + physical + " missing=" + missing);
                Check(!bridge.Tick(physical), "canceled jump returned on a later physics tick");
            }
        foreach (bool physical in new[] { false, true })
        {
            var input = Ready(); var bridge = new TouchJumpFixture { touchControls = input };
            var jump = input.ButtonRect(AndroidTouchInput.Action.Jump).center;
            input.BeginFrame(1); input.Pointer(4, jump, true, false, false); input.EndFrame(); bridge.Update(physical);
            input.BeginFrame(1); input.Pointer(4, jump, false, true, false); input.EndFrame(); bridge.Update(physical);
            Check(bridge.Tick(physical), "released short jump was lost before physics");
            bridge.Update(physical); Check(!bridge.Tick(physical), "released short jump repeated");
        }
        var raw = new TouchJumpFixture { touchControls = Ready(), jumpLatched = true };
        raw.Update(true); Check(raw.Tick(true), "untouched physical pending edge was cleared");
        Check(!raw.Tick(true), "physical pending edge repeated");
    }
    static void Main(string[] args)
    {
        switch (args[0])
        {
            case "multi-pointer": MultiPointer(); break;
            case "short-taps": ShortTaps(); break;
            case "suspension": Suspension(); break;
            case "cancellation": Cancellation(); break;
            case "camera-delta": CameraDelta(); break;
            case "camera-aim": CameraAim(); break;
            case "gui-ownership": GuiOwnership(); break;
            case "bank-witness": BankWitness(); break;
            case "jump-cancel-before-fixed": JumpCancelBeforeFixed(); break;
            default: throw new Exception("unknown case");
        }
        Console.WriteLine(args[0] + ": PASS");
    }
}

public sealed class AndroidOfflineSettings
{
    public sealed class Values { public float lookSensitivity = 1; public bool invertY; }
    public static Values current = new Values();
}

public sealed partial class CameraFixture
{
    public sealed class Report
    {
        public int touchFrames, lookFrames, detachedOwnHurtBoxRejections;
        public bool rayAim;
        public Vector3 direction, aimPoint;
    }
    public sealed class Camera
    {
        public Ray ray;
        public Vector3 viewport;
        public Ray ViewportPointToRay(Vector3 point) { viewport = point; return ray; }
    }
    public sealed class Transform
    {
        public Transform parent;
        public bool IsChildOf(Transform owner) => this == owner || (parent != null && parent.IsChildOf(owner));
    }
    public sealed class HealthComponent
    {
        public static implicit operator bool(HealthComponent value) => value != null;
    }
    public sealed class CharacterBody
    {
        public readonly Transform transform = new Transform();
        public readonly HealthComponent healthComponent = new HealthComponent();
        public readonly InputBank inputBank = new InputBank();
    }
    public sealed class InputBank { public Vector3 aimOrigin; }
    public sealed class HurtBox { public HealthComponent healthComponent; }
    public sealed class Collider
    {
        public readonly Transform transform = new Transform();
        public HurtBox hurtBox;
        public static implicit operator bool(Collider value) => value != null;
        public bool TryGetComponent<T>(out T component) where T : class
        {
            component = hurtBox as T;
            return component != null;
        }
    }
    public struct RaycastHit
    {
        public readonly Collider collider;
        public readonly float distance;
        public readonly Vector3 point;
        public RaycastHit(float distance, float z, Collider collider)
        {
            this.distance = distance;
            this.collider = collider;
            point = Vector3.forward * z;
        }
    }
    public sealed class LayerIndex
    {
        public static readonly LayerIndex world = new LayerIndex { mask = 4 };
        public static readonly LayerIndex entityPrecise = new LayerIndex { mask = 128 };
        public int mask;
    }
    public static class Physics
    {
        public static RaycastHit[] supplied;
        public static float distance;
        public static int mask;
        public static QueryTriggerInteraction triggers;
        public static int RaycastNonAlloc(Ray ray, RaycastHit[] hits, float range, int layers, QueryTriggerInteraction query)
        {
            distance = range;
            mask = layers;
            triggers = query;
            supplied.CopyTo(hits, 0);
            return supplied.Length;
        }
    }
    public readonly Camera camera = new Camera();
    public readonly CharacterBody body = new CharacterBody();
    public readonly Report report = new Report();
    readonly RaycastHit[] hits = new RaycastHit[64];
    public float yaw, pitch;
    public int poses;
    void Place() { poses++; }
}
