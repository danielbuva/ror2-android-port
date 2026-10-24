// Subsystem: input/camera. Owner map: docs/ARCHITECTURE.md#ownership.
// NovaInputBridge owns setup, polling and fixed-tick consumption; Neutral/disable releases captures.
using System;
using UnityEngine;

// A pointer producer for the existing original InputBankTest consumer. No motor,
// transform, skill execution, inventory or gameplay clocks are changed here.
public sealed class AndroidTouchInput
{
    public enum Action { Jump, Primary, Secondary, Utility, Special, Equipment, Interact, Sprint }
    [Serializable]
    public sealed class Report
    {
        public bool active, waitingForLift;
        public int frames, begins, cancels, releases, fixedTicks, heldMask;
        public int[] consumedPresses = new int[8];
        public float moveX, moveY, lookX, lookY;
        public float moveRadius;
        public Vector2 moveCenter, lookStart;
        public Vector2[] buttonCenters = new Vector2[8];
    }
    public readonly Report report = new Report();
    readonly int[] fingers = new int[10];
    readonly bool[] seen = new bool[10], held = new bool[8], pending = new bool[8];
    readonly Vector2[] previous = new Vector2[10];
    readonly Rect[] buttons = new Rect[8];
    readonly string[] labels = { "Jump", "Primary", "Secondary", "Utility", "Special", "Equipment", "Interact", "Sprint" };
    Rect safe, moveZone, lookZone;
    Vector2 moveCenter;
    float radius, scale;
    bool waitingForLift = true;
    GUIStyle style;
    // Slots 0/1 are movement/look; slots 2..9 are original bank actions.
    public Vector2 Movement { get; private set; }
    public Vector2 LookDelta { get; private set; }
    public float ViewHeight => safe.height;
    public bool HasInput
    {
        get
        {
            for (int i = 0; i < fingers.Length; i++)
                if (fingers[i] >= 0) return true;
            for (int i = 0; i < pending.Length; i++)
                if (pending[i]) return true;
            return false;
        }
    }
    public AndroidTouchInput()
    {
        ClearCaptures();
    }
    public bool Down(Action action) => held[(int)action];
    public bool Pressed(Action action) => pending[(int)action];
    public bool Request(Action action) => Down(action) || Pressed(action);
    public Rect ButtonRect(Action action) => buttons[(int)action];
    public Vector2 MoveCenter => moveCenter;
    public Rect LookZone => lookZone;

    public void Layout(Rect area)
    {
        if (safe == area) return;
        Suspend();
        safe = area;
        if (area.width <= 0 || area.height <= 0)
        {
            radius = 0;
            return;
        }
        scale = Mathf.Min(area.width / 1920f, area.height / 1080f);
        radius = 125 * scale;
        moveCenter = new Vector2(area.x + 190 * scale, area.y + 200 * scale);
        report.moveCenter = moveCenter;
        report.moveRadius = radius;
        report.lookStart = new Vector2(area.x + area.width * .75f, area.y + area.height * .72f);
        moveZone = new Rect(area.x, area.y, 425 * scale, 425 * scale);
        lookZone = new Rect(area.x + area.width * .5f, area.y, area.width * .5f, area.height - 85 * scale);
        float right = area.xMax, bottom = area.y;
        SetButton(Action.Jump, right - 145 * scale, bottom + 350 * scale);
        SetButton(Action.Primary, right - 145 * scale, bottom + 105 * scale);
        SetButton(Action.Secondary, right - 265 * scale, bottom + 105 * scale);
        SetButton(Action.Utility, right - 145 * scale, bottom + 225 * scale);
        SetButton(Action.Special, right - 265 * scale, bottom + 225 * scale);
        SetButton(Action.Equipment, right - 385 * scale, bottom + 105 * scale);
        SetButton(Action.Interact, right - 385 * scale, bottom + 225 * scale);
        SetButton(Action.Sprint, area.x + 410 * scale, bottom + 95 * scale);
    }
    void SetButton(Action action, float x, float y)
    {
        buttons[(int)action] = new Rect(x - 52 * scale, y - 45 * scale, 104 * scale, 90 * scale);
        report.buttonCenters[(int)action] = buttons[(int)action].center;
    }
    void ClearCaptures()
    {
        for (int i = 0; i < fingers.Length; i++) fingers[i] = -1;
        Array.Clear(held, 0, held.Length);
        Array.Clear(pending, 0, pending.Length);
        Movement = LookDelta = Vector2.zero;
    }
    public void Suspend()
    {
        ClearCaptures();
        waitingForLift = true;
        Publish();
    }
    // The frame/pointer API also lets the host exercise real capture ownership
    // without an Android input device. Runtime uses only Input.GetTouch below.
    public void BeginFrame(int touchCount)
    {
        LookDelta = Vector2.zero;
        Array.Clear(seen, 0, seen.Length);
        if (touchCount == 0) waitingForLift = false;
    }
    public void Pointer(int id, Vector2 position, bool began, bool ended, bool canceled)
    {
        if (waitingForLift || radius <= 0 || id < 0) return;
        int slot = -1;
        for (int i = 0; i < fingers.Length; i++)
            if (fingers[i] == id) { slot = i; break; }
        if (slot < 0 && began && !ended && !canceled)
        {
            for (int i = 0; i < buttons.Length; i++)
                if (buttons[i].Contains(position)) { slot = i + 2; break; }
            if (slot < 0 && moveZone.Contains(position)) slot = 0;
            if (slot < 0 && lookZone.Contains(position)) slot = 1;
            if (slot < 0 || fingers[slot] >= 0) return;
            fingers[slot] = id;
            previous[slot] = position;
            report.begins++;
            if (slot >= 2) pending[slot - 2] = true;
        }
        if (slot < 0) return;
        seen[slot] = true;
        if (ended || canceled)
        {
            Release(slot, canceled);
            return;
        }
        if (slot == 0)
            Movement = Vector2.ClampMagnitude((position - moveCenter) / radius, 1);
        else if (slot == 1)
            LookDelta += position - previous[slot];
        else
            held[slot - 2] = buttons[slot - 2].Contains(position);
        previous[slot] = position;
    }
    void Release(int slot, bool canceled)
    {
        fingers[slot] = -1;
        if (slot == 0) Movement = Vector2.zero;
        else if (slot >= 2) held[slot - 2] = false;
        if (canceled)
        {
            if (slot >= 2) pending[slot - 2] = false;
            report.cancels++;
        }
        else report.releases++;
    }
    public void EndFrame()
    {
        for (int i = 0; i < fingers.Length; i++)
            if (fingers[i] >= 0 && !seen[i]) Release(i, true);
        report.frames++;
        Publish();
    }
    public void Poll()
    {
        Layout(Screen.safeArea);
        int count = Input.touchCount;
        BeginFrame(count);
        for (int i = 0; i < count; i++)
        {
            var touch = Input.GetTouch(i);
            Pointer(touch.fingerId, touch.position, touch.phase == TouchPhase.Began,
                    touch.phase == TouchPhase.Ended, touch.phase == TouchPhase.Canceled);
        }
        EndFrame();
    }
    public void ConsumeFixedTick()
    {
        for (int i = 0; i < pending.Length; i++)
        {
            if (pending[i]) report.consumedPresses[i]++;
            pending[i] = false;
        }
        report.fixedTicks++;
    }
    void Publish()
    {
        report.active = HasInput;
        report.waitingForLift = waitingForLift;
        report.heldMask = 0;
        for (int i = 0; i < held.Length; i++)
            if (held[i]) report.heldMask |= 1 << i;
        report.moveX = Movement.x; report.moveY = Movement.y;
        report.lookX = LookDelta.x; report.lookY = LookDelta.y;
    }
    static Rect GuiRect(Rect rect) => new Rect(rect.x, Screen.height - rect.yMax, rect.width, rect.height);
    public void Draw()
    {
        Layout(Screen.safeArea);
        if (safe.width <= 0 || safe.height <= 0) return;
        var color = GUI.color;
        try
        {
            int fontSize = Mathf.Max(12, Mathf.RoundToInt(20 * scale));
            if (style == null || style.fontSize != fontSize)
                style = new GUIStyle(GUI.skin.box) { fontSize = fontSize, alignment = TextAnchor.MiddleCenter, wordWrap = true };
            GUI.color = new Color(1, 1, 1, .65f);
            GUI.Box(GuiRect(new Rect(moveCenter.x - radius, moveCenter.y - radius, radius * 2, radius * 2)), "Move", style);
            var knob = moveCenter + Movement * radius;
            GUI.Box(GuiRect(new Rect(knob.x - 25 * scale, knob.y - 25 * scale, 50 * scale, 50 * scale)), "");
            for (int i = 0; i < buttons.Length; i++)
            {
                GUI.color = held[i] ? new Color(.6f, 1, .6f, .85f) : new Color(1, 1, 1, .65f);
                GUI.Box(GuiRect(buttons[i]), labels[i], style);
            }
        }
        finally { GUI.color = color; }
    }
}
