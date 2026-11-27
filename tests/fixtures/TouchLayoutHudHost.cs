// Portable platform/UI peers. The tested HUD, input and layout classes below
// are the production sources; this does not verify Unity's event delivery.
using System;
using System.IO;
using OwnerLayout;
using UnityEngine;
namespace UnityEngine
{
    public struct Vector2
    {
        public float x, y;
        public Vector2(float x, float y) { this.x = x; this.y = y; }
        public static Vector2 zero => new Vector2();
        public static bool operator ==(Vector2 a, Vector2 b) => a.Equals(b);
        public static bool operator !=(Vector2 a, Vector2 b) => !a.Equals(b);
        public override bool Equals(object obj) => obj is Vector2 v && x == v.x && y == v.y;
        public override int GetHashCode() => x.GetHashCode();
        public static Vector2 operator +(Vector2 a, Vector2 b) => new Vector2(a.x + b.x, a.y + b.y);
        public static Vector2 operator -(Vector2 a, Vector2 b) => new Vector2(a.x - b.x, a.y - b.y);
        public static Vector2 operator *(Vector2 a, float k) => new Vector2(a.x * k, a.y * k);
        public static Vector2 operator /(Vector2 a, float k) => new Vector2(a.x / k, a.y / k);
        public static Vector2 ClampMagnitude(Vector2 a, float n) => a;
    }
    public struct Rect
    {
        public float x, y, width, height;
        public Rect(float x, float y, float width, float height)
        { this.x = x; this.y = y; this.width = width; this.height = height; }
        public float xMax => x + width;
        public float yMax => y + height;
        public Vector2 center => new Vector2(x + width / 2, y + height / 2);
        public bool Contains(Vector2 p) => p.x >= x && p.y >= y && p.x < xMax && p.y < yMax;
        public static bool operator ==(Rect a, Rect b) => a.Equals(b);
        public static bool operator !=(Rect a, Rect b) => !a.Equals(b);
        public override bool Equals(object obj) => obj is Rect r && x == r.x && y == r.y && width == r.width && height == r.height;
        public override int GetHashCode() => x.GetHashCode();
    }
    public static class Mathf
    {
        public static float Min(float a, float b) => Math.Min(a, b);
        public static int Max(int a, int b) => Math.Max(a, b);
        public static int RoundToInt(float a) => (int)Math.Round(a);
    }
    public struct Color { public Color(float a, float b, float c, float d) {} }
    public enum TextAnchor { MiddleCenter }
    public sealed class GUIStyle
    {
        public GUIStyle(GUIStyle other) {}
        public int fontSize;
        public TextAnchor alignment;
        public bool wordWrap;
    }
    public sealed class Skin { public GUIStyle box; }
    public static class GUI
    {
        public static Color color;
        public static Skin skin = new Skin();
        public static string click, status;
        public static void Box(Rect r, string s, GUIStyle style = null) {}
        public static void Label(Rect r, string s) { status = s; }
        public static bool Button(Rect r, string s)
        {
            if (click != s) return false;
            click = null;
            return true;
        }
    }
    public static class Screen
    {
        public static int width = 1920, height = 1080;
        public static Rect safeArea = new Rect(0, 0, width, height);
    }
    public static class Application { public static bool isFocused = true; }
    public enum EventType { Repaint, MouseDown, MouseDrag, MouseUp, Used }
    public sealed class Event
    {
        public static Event current = new Event();
        public EventType type;
        public int button;
        public Vector2 mousePosition;
        public void Use() { type = EventType.Used; }
    }
    public enum TouchPhase { Began, Ended, Canceled }
    public struct Touch { public int fingerId; public Vector2 position; public TouchPhase phase; }
    public static class Input { public static int touchCount => 0; public static Touch GetTouch(int i) => default; }
}
public sealed class AndroidOfflineSettings
{
    public readonly string directory;
    public readonly Values values = new Values();
    public sealed class Values { public bool touchLayoutEditor; }
    public AndroidOfflineSettings(string path) { directory = path; }
}
public sealed class NovaInputBridge { public AndroidTouchInput touchControls = new AndroidTouchInput(); }
public sealed class WorldPlayer
{
    public NovaInputBridge Bridge = new NovaInputBridge();
    public T GetComponent<T>() where T : class => Bridge as T;
}
public sealed partial class PortSession
{
    AndroidOfflineSettings offlineSettings;
    bool offlineSettingsPaused, offlineStartVisible, offlineSettingsVisible, wantsEditor, touchUi;
    WorldPlayer worldPlayer = new WorldPlayer();
    bool HasSavedTouchEditorRequest => wantsEditor;
    bool UsesTouchUi() => touchUi;
    bool canSaveSettings = true;
    void ShowOfflineSettings(bool show) { offlineSettingsVisible = show; }
    bool SaveOfflineSettings()
    {
        if (!canSaveSettings) return false;
        wantsEditor = offlineSettings.values.touchLayoutEditor;
        return true;
    }
    static void Check(bool ok, string problem) { if (!ok) throw new Exception(problem); }
    void EventAt(EventType type, float x, float y)
    {
        Event.current = new Event { type = type, mousePosition = new Vector2(x, y) };
        Check(DrawTouchLayoutEditor(), "editor must consume the GUI when active");
    }
    void Click(string label)
    {
        GUI.click = label;
        EventAt(EventType.Repaint, 0, 0);
        Check(GUI.click == null, "expected editor button " + label);
    }
    static void Main()
    {
        var path = Path.Combine(Path.GetTempPath(), "touch-hud-fixture-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(path);
        try { Exercise(path); }
        finally { Directory.Delete(path, true); }
        Console.WriteLine("touch-hud: PASS");
    }
    static void Exercise(string path)
    {
        var file = Path.Combine(path, "touch-layout.txt");
        var app = new PortSession { offlineSettings = new AndroidOfflineSettings(path), offlineStartVisible = true };
        Check(!app.DrawTouchLayoutEditor(), "disabled editor opened");
        app.wantsEditor = app.offlineSettings.values.touchLayoutEditor = true;
        Check(!app.DrawTouchLayoutEditor(), "non-touch UI opened");
        app.touchUi = true;
        app.EventAt(EventType.Repaint, 0, 0);
        Check(app.offlineSettingsVisible && !File.Exists(file), "startup must open without writing");
        float x = 1775, y = 96f + (1080f - 350f) * (984f / 1080f);
        app.EventAt(EventType.MouseDown, x, y);
        app.EventAt(EventType.MouseDrag, x - 250, y);
        Application.isFocused = false;
        app.EventAt(EventType.Repaint, 0, 0);
        Application.isFocused = true;
        app.EventAt(EventType.MouseUp, x - 250, y);
        Check(!File.Exists(file), "focus loss wrote a draft");
        app.EventAt(EventType.MouseDown, x, y);
        Check(Event.current.type == EventType.Used, "editor did not capture pointer");
        app.EventAt(EventType.MouseDrag, x - 200, y);
        app.EventAt(EventType.MouseUp, x - 200, y);
        Check(!File.Exists(file), "gesture wrote disk before Save");
        app.canSaveSettings = false;
        app.Click("Save layout");
        Check(File.Exists(file) && app.wantsEditor && app.offlineSettingsVisible, "failed settings write hid the editor");
        var saved = File.ReadAllText(file);
        app.canSaveSettings = true;
        app.Click("Retry close");
        Check(!app.wantsEditor && !app.offlineSettingsVisible && saved == File.ReadAllText(file), "retry rewrote layout or kept editor open");

        var cold = new PortSession { offlineSettings = new AndroidOfflineSettings(path), touchUi = true };
        var input = cold.worldPlayer.Bridge.touchControls;
        cold.ApplyTouchLayout(input);
        input.Layout(Screen.safeArea, new Vector2(Screen.width, Screen.height));
        var newJump = input.ButtonRect(AndroidTouchInput.Action.Jump).center;
        Check(Math.Abs(newJump.x - (x - 200)) < .01f && Math.Abs(newJump.y - 350) < .01f, "cold startup did not apply edited geometry");
        input.BeginFrame(0); input.EndFrame();
        input.BeginFrame(1); input.Pointer(1, newJump, true, false, false); input.EndFrame();
        Check(input.Request(AndroidTouchInput.Action.Jump), "new geometry not used by gameplay capture");

        File.WriteAllText(file, "not a layout");
        var damaged = new PortSession { offlineSettings = new AndroidOfflineSettings(path), touchUi = true, offlineSettingsPaused = true, wantsEditor = true };
        damaged.EventAt(EventType.Repaint, 0, 0);
        Check(GUI.status.Contains("original file preserved"), "corrupt fallback not reported");
        damaged.Click("Save layout");
        Check(damaged.wantsEditor && File.ReadAllText(file) == "not a layout", "corrupt file was overwritten");
        damaged.Click("Back");
        Check(!damaged.wantsEditor && File.ReadAllText(file) == "not a layout", "back did not preserve corrupt file");
    }
}
