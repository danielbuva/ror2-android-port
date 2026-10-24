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
    static void Main(string[] args)
    {
        switch (args[0])
        {
            case "multi-pointer": MultiPointer(); break;
            case "short-taps": ShortTaps(); break;
            case "suspension": Suspension(); break;
            case "cancellation": Cancellation(); break;
            case "camera-delta": CameraDelta(); break;
            case "gui-ownership": GuiOwnership(); break;
            case "bank-witness": BankWitness(); break;
            default: throw new Exception("unknown case");
        }
        Console.WriteLine(args[0] + ": PASS");
    }
}
