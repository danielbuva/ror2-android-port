// Authored controlled Unity/RoR2 collaborators; no game implementation or data.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace UnityEngine
{
    public class Object { public static implicit operator bool(Object value) => value != null; }
    public class GameObject : Object { }
    public struct Vector2 { public float x, y; public Vector2(float x, float y) { this.x = x; this.y = y; } public static Vector2 zero => new Vector2(); }
    public struct Vector3 { public Vector3(float x, float y, float z) { } }
    public struct Quaternion { public static Quaternion identity => new Quaternion(); }
    public struct Matrix4x4
    {
        public int marker;
        public static Matrix4x4 TRS(Vector3 position, Quaternion rotation, Vector3 scale) => new Matrix4x4 { marker = 2 };
    }
    public struct Rect
    {
        public float x, y, width, height;
        public Rect(float x, float y, float width, float height) { this.x = x; this.y = y; this.width = width; this.height = height; }
        public float yMax => y + height;
        public Vector2 center => new Vector2(x + width / 2, y + height / 2);
    }
    public static class Mathf
    {
        public static float Min(float a, float b) => Math.Min(a, b);
        public static float Max(float a, float b) => Math.Max(a, b);
        public static float Abs(float value) => Math.Abs(value);
    }
    public class GUIContent { public string text; public GUIContent(string text) { this.text = text; } }
    public class GUIStyle
    {
        public int fontSize;
        public bool wordWrap, richText;
        public GUIStyle() { }
        public GUIStyle(GUIStyle source) { }
        public float CalcHeight(GUIContent content, float width) => 20 * (1 + content.text.Length / 65);
    }
    public class GUISkin { public GUIStyle textArea = new GUIStyle(), button = new GUIStyle(), label = new GUIStyle(), toggle = new GUIStyle(); }
    public static class GUI
    {
        public static GUISkin skin = new GUISkin();
        public static Matrix4x4 matrix = new Matrix4x4 { marker = 1 };
        public static bool enabled = true;
        public static string click, edit;
        public static bool? consent;
        public static List<string> labels = new List<string>();
        public static void Box(Rect rect, string value) { }
        public static void Label(Rect rect, string value, GUIStyle style = null) { labels.Add(value); }
        public static bool Button(Rect rect, string value, GUIStyle style = null)
        {
            if (!enabled || Event.current.type == EventType.Used || click != value) return false;
            click = null;
            return true;
        }
        public static string TextArea(Rect rect, string value, int maxLength, GUIStyle style)
        {
            if (edit == null) return value;
            var next = edit; edit = null; return next;
        }
        public static bool Toggle(Rect rect, bool value, string label, GUIStyle style = null)
        {
            if (!consent.HasValue) return value;
            var next = consent.Value; consent = null; return next;
        }
        public static Vector2 BeginScrollView(Rect rect, Vector2 scroll, Rect view) => scroll;
        public static void EndScrollView() { }
        public static float HorizontalSlider(Rect rect, float value, float min, float max) => value;
    }
    public static class GUIUtility
    {
        static string clipboard = "unrelated prior clipboard";
        public static int keyboardControl, reads, writes;
        public static bool writeFails, readFails, mismatch;
        public static string written;
        public static string systemCopyBuffer
        {
            get { reads++; if (readFails) throw new InvalidOperationException(); return mismatch ? "different" : clipboard; }
            set { writes++; if (writeFails) throw new InvalidOperationException(); clipboard = written = value; }
        }
    }
    public static class Screen { public static int width = 1440, height = 900, sleepTimeout = 15; public static Rect safeArea = new Rect(0, 0, 1440, 900); }
    public static class SleepTimeout { public const int NeverSleep = -1; }
    public enum GraphicsDeviceType { Vulkan }
    public static class SystemInfo { public static GraphicsDeviceType graphicsDeviceType => GraphicsDeviceType.Vulkan; }
    public static class Application
    {
        public static string version = "alpha.1", unityVersion = "2021.3.45f2", buildGUID = "0123456789abcdef0123456789abcdef";
        public static string persistentDataPath = ".";
        public static string url;
        public static bool openFails;
        public static void OpenURL(string value) { if (openFails) throw new InvalidOperationException(); url = value; }
        public static void Quit() { }
    }
    public enum EventType { Repaint, KeyDown, MouseDown, MouseUp, MouseDrag, Used }
    public enum KeyCode { Escape = 27, Joystick1Button0 = 330, Joystick1Button1 = 331 }
    public class Event
    {
        public static Event current = new Event();
        public EventType type = EventType.Repaint;
        public KeyCode keyCode;
        public void Use() { type = EventType.Used; }
    }
    public static class Time { public static float timeScale = .75f; public static int frameCount = 1; }
    public static class Input
    {
        public static HashSet<KeyCode> down = new HashSet<KeyCode>();
        public static bool GetKeyDown(KeyCode key) => down.Contains(key);
    }
}
namespace RoR2
{
    public enum DifficultyIndex { Normal }
    public class PauseStopController : UnityEngine.Object
    {
        public static PauseStopController instance = new PauseStopController();
        public bool isPaused;
        public bool NetworkisPaused { set { isPaused = value; } }
    }
    public class Run : UnityEngine.Object { public static Run instance = new Run(); public float GetRunStopwatch() => 12; }
    public class CharacterBody : UnityEngine.Object
    {
        public class Health { public bool alive = true; }
        public Health healthComponent = new Health();
        public T GetComponent<T>() where T : new() => new T();
    }
}
public class NovaInputBridge : UnityEngine.Object
{
    public static bool ownGuiMouse;
    public bool OwnsTouchGuiMouse => ownGuiMouse;
    public class Mapping { public int moveX, aimX = 1, jump; }
    public struct Raw { public float[] axes; }
    public static Raw raw = new Raw { axes = new float[2] };
    public static Raw ReadRaw() => raw;
    public static int neutrals;
    public void Neutral() { neutrals++; }
}
public static class AndroidTouchInput
{
    public static Rect PauseGuiRect(float width) => new Rect(width - 205, 10, 185, 40);
}
public class AndroidOfflineSettings
{
    public class Values { public float deadzone = .1f, lookSensitivity = 1; public bool invertY; public int offlineDifficulty; }
    public static Values current;
    public Values values = new Values();
    public string recovery = "none";
    public string saveError;
    public bool refuseSave;
    public int saves;
    public AndroidOfflineSettings(string path) { }
    public void Save() { saves++; }
    public bool TrySave()
    {
        saveError = refuseSave ? "Settings save failed. Check storage and try again." : null;
        if (!refuseSave) Save();
        return !refuseSave;
    }
}
public sealed partial class PortSession
{
    public class Mapping { public int jump; }
    public class Report
    {
        public OfflineSettingsReport settings;
        public Report runClock, nova, profile, results, world, primary, combat, enemy;
        public bool freePlay = true, physicalInputAvailable = true, ready, reportGenerated, integratedWorld = true, commandoPrimaryDiagnostic, persisted;
        public string phase = "world";
        public Mapping mapping = new Mapping();
        public int fixedTicks, appliedRuns, kills, shots, stockAfter, secondaryEntries, utilityEntries, specialEntries, headbutts;
        public float damageDealt, healthAfter, health, playerHealth;
        public string aiState;
    }
    public Report r = new Report();
    GameObject worldPause = new GameObject();
    RoR2.CharacterBody worldPlayer = new RoR2.CharacterBody();
    RoR2.DifficultyIndex offlineDifficulty;
    public int saves, underlying, survivorCycles, difficultyCycles, resultMenuRequests, abandonRequests;
    public bool menuObscured;
    void SetRecoveredMenuObscured(bool value) { menuObscured = value; }
    bool offlineStartVisible, offlineStartSelected;
    bool UsesTouchUi() => false;
    bool OfflineUiControllerPresent() => true;
    bool CanAbandonOfflineRun() => true;
    void RequestAbandonOfflineRun() { abandonRequests++; }
    void Save() { saves++; }
    void Check(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    bool DrawOfflineStart() { underlying++; return false; }
    void DrawIntegratedResults() { underlying++; }
    void DrawIntegratedWorld() { underlying++; }
    void DrawItemPickupObservation() { underlying++; }
    public void Prepare()
    {
        r.nova = new Report(); r.profile = new Report(); r.world = new Report { ready = true };
        PrepareOfflineSettings();
    }
    public void Show(bool show) { ShowOfflineSettings(show); }
    public void Render() { OnGUI(); }
    public void Controller() { ObserveOfflineSettingsControllerInput(); }
    public void Dispose() { CleanupOfflineSettingsPause(); }
    public bool Paused => offlineSettingsPaused;
    public bool SettingsVisible => offlineSettingsVisible;
    public int SettingsSaves => offlineSettings.saves;
    public string SettingsError => r.settings.error;
    public bool SettingsPersisted => r.settings.persisted;
    public void RefuseSettingsSave(bool refuse) { offlineSettings.refuseSave = refuse; }
    public bool StartSelected => offlineStartSelected;
    public void StartMenu() { offlineStartVisible = true; worldPause = null; worldPlayer = null; }
    void CycleOrdinarySurvivor(int direction) { survivorCycles++; }
    OfflineApplicationSession applicationInput;
    public void ApplicationController()
    {
        if (applicationInput == null) applicationInput = new OfflineApplicationSession(this);
        applicationInput.ObserveOfflineApplicationInput();
    }
    sealed partial class OfflineApplicationSession
    {
        readonly PortSession coordinator;
        NovaInputBridge.Mapping offlineMenuMapping = new NovaInputBridge.Mapping();
        bool offlineSurvivorStickLatched, offlineDifficultyStickLatched;
        public OfflineApplicationSession(PortSession coordinator) { this.coordinator = coordinator; }
        bool OfflineUiControllerPresent() => coordinator.OfflineUiControllerPresent();
        void CycleOfflineDifficulty(int direction) { coordinator.difficultyCycles++; }
        void RequestResultsMenu() { coordinator.resultMenuRequests++; }
    }
}

public static class AndroidFeedbackHost
{
    static void Check(bool value, string reason) { if (!value) throw new Exception(reason); }
    static void Refuses(Action action)
    {
        try { action(); } catch (InvalidOperationException) { return; }
        throw new Exception("sharing without consent accepted");
    }
    static AndroidFeedbackDraft Reviewed()
    {
        var draft = new AndroidFeedbackDraft(); draft.Edit("Expected movement; observed a freeze.");
        Check(draft.Review(Application.version, Application.unityVersion, Application.buildGUID, "Vulkan"), "review failed");
        return draft;
    }
    static AndroidFeedbackScreen Previewed()
    {
        var screen = new AndroidFeedbackScreen(); screen.Open();
        GUI.edit = "Steps: pause, then resume. Expected movement."; screen.Draw();
        GUI.click = "Preview report"; screen.Draw();
        return screen;
    }
    static bool LabelContains(string value) => GUI.labels.Exists(label => label.Contains(value));
    static void Consent(AndroidFeedbackScreen screen) { GUI.consent = true; screen.Draw(); }
    static void ModelConsent()
    {
        var draft = new AndroidFeedbackDraft(); draft.Consent(true);
        Check(!draft.CanShare, "empty consent accepted"); Refuses(() => draft.SharedText()); Refuses(() => draft.IssueUrl());
        draft = Reviewed(); Refuses(() => draft.SharedText());
        draft.Consent(true); var exact = draft.Preview;
        Check(draft.SharedText() == exact, "share differs from preview");
        var url = new Uri(draft.IssueUrl());
        Check(url.GetLeftPart(UriPartial.Path) == AndroidFeedbackDraft.IssueEndpoint, "foreign endpoint");
        Check(Uri.UnescapeDataString(url.Query.Split(new[] { "&body=" }, StringSplitOptions.None)[1]) == exact, "issue body differs from preview");
        draft.BeginEdit(); Check(draft.Notes.Length > 0 && draft.Preview == "" && !draft.CanShare, "edit failed to retain notes/invalidate consent");
        Refuses(() => draft.IssueUrl()); draft.Review("1", "2", "bad", "Vulkan"); draft.Consent(true);
        draft.Edit("changed"); Check(draft.Preview == "" && !draft.CanShare, "changed notes retained consent");
        draft.Clear(); Check(draft.Notes == "" && draft.Preview == "" && !draft.CanShare, "clear retained draft");
    }
    static void ModelBounds()
    {
        var draft = new AndroidFeedbackDraft(); draft.Edit(new string('x', 1000));
        Check(draft.Notes.Length == 600, "note limit not enforced");
        Check(draft.Review("private/path", new string('a', 65), "not-a-build-guid", "Vulkan\nprivate"), "bounded review failed");
        Check(!draft.Preview.Contains("private") && !draft.Preview.Contains(new string('a', 65)), "unbounded facts leaked");
        Check(draft.Preview.Contains("App version: unknown") && draft.Preview.Contains("Graphics API: unknown"), "bad facts not refused");
        Check(draft.Preview.Contains("Manual notes are not automatically redacted"), "manual-note warning absent");
        draft.Edit("\0\u0001\ud800 \udfff\t "); Check(!draft.Review("1", "2", null, "Vulkan"), "empty normalized description accepted");
        draft.Edit("<b>\r\n[link](https://example.test)\r\ud83d\ude80\ud800");
        Check(draft.Review("1", "2", null, "Vulkan"), "unicode notes rejected");
        Check(draft.Preview.Contains("\\<b\\>\n\\[link\\]\\(https://example\\.test\\)\n\ud83d\ude80"), "manual text encoding/newlines changed");
        draft.Consent(true); Check(draft.IssueUrl().StartsWith(AndroidFeedbackDraft.IssueEndpoint), "normalized text cannot share");
    }
    static void ScreenConsent()
    {
        var screen = Previewed(); GUI.click = "Copy report"; screen.Draw();
        Check(GUIUtility.writes == 0 && GUIUtility.reads == 0, "copy happened before consent");
        GUI.click = "Open GitHub draft"; screen.Draw(); Check(Application.url == null, "browser called before consent");
        GUI.click = null; Consent(screen); GUI.click = "Copy report"; screen.Draw();
        Check(GUIUtility.writes == 1 && GUIUtility.reads == 1 && LabelContains("Report copied."), "copy not verified by readback");
        GUI.click = "Open GitHub draft"; screen.Draw();
        Check(Uri.UnescapeDataString(Application.url.Split(new[] { "&body=" }, StringSplitOptions.None)[1]) == GUIUtility.written,
              "copy and browser text differ");
        Check(LabelContains("Browser handoff requested") && !LabelContains("Opened a draft"), "void browser return claimed opening");
        GUI.click = "Edit report (clears sharing consent)"; screen.Draw();
        GUI.click = "Preview report"; screen.Draw(); GUI.click = "Copy report"; screen.Draw();
        Check(GUIUtility.writes == 1, "edit retained sharing consent");
        GUI.click = "Back to settings"; GUIUtility.keyboardControl = 7; screen.Draw();
        Check(!screen.Visible && GUIUtility.keyboardControl == 0, "back retained screen/focus");
        screen.Open(); GUI.click = "Preview report"; screen.Draw();
        Check(LabelContains("Enter a description first."), "back retained private notes");
    }
    static void ScreenErrors()
    {
        var screen = Previewed(); Consent(screen);
        GUIUtility.writeFails = true; GUI.click = "Copy report"; screen.Draw();
        Check(GUIUtility.reads == 0 && LabelContains("Could not confirm copying"), "write failure read unrelated clipboard or claimed success");
        GUIUtility.writeFails = false; GUIUtility.mismatch = true; GUI.click = "Copy report"; screen.Draw();
        Check(LabelContains("Copy could not be confirmed"), "mismatched readback claimed success");
        GUIUtility.mismatch = false; GUIUtility.readFails = true; GUI.click = "Copy report"; screen.Draw();
        Check(LabelContains("Could not confirm copying"), "read failure claimed success");
        Application.openFails = true; GUI.click = "Open GitHub draft"; screen.Draw();
        Check(Application.url == null && LabelContains("Browser handoff failed"), "browser exception not handled");
        Check(GUI.enabled && GUI.matrix.marker == 1, "GUI state not restored after action failures");
    }
    static void ScreenEscape()
    {
        var screen = Previewed(); Consent(screen);
        Event.current = new Event { type = EventType.KeyDown, keyCode = KeyCode.Escape };
        screen.Draw(); Check(!screen.Visible && Event.current.type == EventType.Used, "Escape not owned/closed");
        Event.current = new Event(); screen.Open(); GUI.click = "Preview report"; screen.Draw();
        Check(LabelContains("Enter a description first."), "Escape retained notes");
        screen.Close(); screen.Close(); Check(!screen.Visible, "close not idempotent");
    }
    static void SettingsLifecycle()
    {
        var session = new PortSession(); session.Prepare(); session.Show(true);
        Check(session.Paused && Time.timeScale == 0 && NovaInputBridge.neutrals == 1, "settings pause not owned");
        session.Render();
        Check(session.menuObscured && session.underlying == 0, "settings left native menu or underlying GUI active");
        GUI.click = "Close settings"; session.Render();
        Check(!session.SettingsVisible && !session.menuObscured && session.underlying == 0,
              "settings closing event reached underlying menu");
        session.Show(true);
        GUI.click = "Send feedback"; session.Render(); Check(session.underlying == 0, "opening feedback drew underlying widgets");
        GUI.edit = "Private draft"; session.Render();
        GUI.click = "Back to settings"; session.Render();
        Check(session.underlying == 0 && session.Paused && session.SettingsVisible, "Back leaked event or released pause");
        GUI.click = "Send feedback"; session.Render(); GUI.click = "Preview report"; session.Render();
        Check(LabelContains("Enter a description first."), "Back failed to clear notes");
        Input.down.Add(KeyCode.Joystick1Button1); Input.down.Add(KeyCode.Joystick1Button0); session.Controller(); Input.down.Clear();
        Check(session.Paused && session.SettingsVisible && session.SettingsSaves == 0, "feedback back bled into controller save/resume");
        GUI.click = "Send feedback"; session.Render(); GUI.edit = "Discard on cleanup"; session.Render();
        session.Dispose(); Check(!session.Paused && !session.SettingsVisible && !session.menuObscured && Time.timeScale == .75f, "cleanup failed to restore owned pause/menu");
        session.Show(true); GUI.click = "Send feedback"; session.Render(); GUI.click = "Preview report"; session.Render();
        Check(LabelContains("Enter a description first."), "cleanup retained private draft");
        session.Dispose(); session.Dispose(); Check(Time.timeScale == .75f, "repeated cleanup changed pause");
    }
    static void StartMenuInput()
    {
        var session = new PortSession(); session.Prepare(); session.StartMenu(); session.Show(true);
        GUI.click = "Send feedback"; session.Render();
        NovaInputBridge.raw.axes[0] = NovaInputBridge.raw.axes[1] = 1;
        Input.down.Add(KeyCode.Joystick1Button0);
        session.ApplicationController();
        Check(!session.StartSelected && session.survivorCycles == 0 && session.difficultyCycles == 0 && session.SettingsSaves == 0,
              "feedback allowed hidden start-menu A/stick actions");
        Input.down.Add(KeyCode.Joystick1Button1);
        session.ApplicationController();
        Check(session.SettingsVisible && !session.StartSelected && session.survivorCycles == 0 && session.difficultyCycles == 0,
              "feedback B missed close or bled into start-menu actions");
        // B closed only the draft; the settings screen remains and owns the next
        // B+A frame too, even though that action closes settings.
        session.ApplicationController();
        Check(!session.SettingsVisible && !session.StartSelected && session.survivorCycles == 0 && session.difficultyCycles == 0,
              "settings-closing frame started gameplay or changed selection");
        Input.down.Remove(KeyCode.Joystick1Button1);
        session.ApplicationController();
        Check(session.StartSelected && session.survivorCycles == 1 && session.difficultyCycles == 1,
              "ordinary closed-menu A/stick routing changed");
    }
    static void SettingsSaveFailure()
    {
        var session = new PortSession(); session.Prepare(); session.Show(true);
        session.RefuseSettingsSave(true); GUI.click = "Save and close"; session.Render();
        Check(session.Paused && session.SettingsVisible && Time.timeScale == 0, "failed save released pause or closed settings");
        Check(session.SettingsSaves == 0 && !session.SettingsPersisted && !string.IsNullOrEmpty(session.SettingsError),
              "failed save claimed persistence or omitted recovery message");
        session.RefuseSettingsSave(false); GUI.click = "Save and close"; session.Render();
        Check(!session.Paused && !session.SettingsVisible && session.SettingsSaves == 1 && session.SettingsPersisted,
              "successful retry did not save and resume");
        Check(string.IsNullOrEmpty(session.SettingsError), "successful retry retained stale error");
    }
    static void TouchGuiOwnership()
    {
        var session = new PortSession(); session.Prepare();
        NovaInputBridge.ownGuiMouse = true;
        Event.current = new Event { type = EventType.MouseDown };
        GUI.click = "Settings / pause"; session.Render();
        Check(Event.current.type == EventType.Used && !session.SettingsVisible, "captured gameplay touch activated native GUI button");
        NovaInputBridge.ownGuiMouse = false;
        Event.current = new Event { type = EventType.MouseDown };
        GUI.click = "Settings / pause"; session.Render();
        Check(session.SettingsVisible && session.Paused, "unclaimed UI touch was swallowed");
        NovaInputBridge.ownGuiMouse = true;
        Event.current = new Event { type = EventType.MouseDown };
        GUI.click = "Close settings"; session.Render();
        Check(Event.current.type == EventType.Used && session.SettingsVisible && session.Paused,
              "opening gameplay pointer toggled the new modal closed");
        NovaInputBridge.ownGuiMouse = false;
        Event.current = new Event { type = EventType.MouseDown };
        GUI.click = "Resume"; session.Render();
        Check(!session.SettingsVisible && !session.Paused, "fresh modal tap was swallowed after the opening pointer lifted");
    }
    static void EndRunConfirmation()
    {
        var session = new PortSession(); session.Prepare(); session.Show(true);
        GUI.click = "End run and return to menu"; session.Render();
        Check(session.abandonRequests == 0 && session.r.settings.endRunConfirmationVisible && session.underlying == 0,
              "opening end-run dialog ended the run or leaked the event");
        GUI.click = "Keep playing"; session.Render();
        Check(session.abandonRequests == 0 && !session.r.settings.endRunConfirmationVisible && session.Paused,
              "cancel ended the run or resumed hidden gameplay");
        GUI.click = "End run and return to menu"; session.Render();
        Input.down.Add(KeyCode.Joystick1Button1); Input.down.Add(KeyCode.Joystick1Button0);
        session.Controller(); Input.down.Clear();
        Check(!session.r.settings.endRunConfirmationVisible && session.Paused && session.SettingsSaves == 0,
              "controller cancel confirmed, saved or resumed the run");
        GUI.click = "End run and return to menu"; session.Render(); session.Dispose();
        Check(!session.r.settings.endRunConfirmationVisible && session.abandonRequests == 0,
              "cleanup retained or accepted a pending confirmation");
        session.Show(true); GUI.click = "End run and return to menu"; session.Render();
        GUI.click = "Confirm end run"; session.Render();
        Check(session.abandonRequests == 1 && !session.r.settings.endRunConfirmationVisible,
              "explicit confirmation did not dispatch exactly once");
        session.Dispose();
    }
    static void ScreenPolicy()
    {
        var session = new PortSession(); session.KeepAwake();
        Check(Screen.sleepTimeout == SleepTimeout.NeverSleep, "loading screen may auto-suspend");
        session.KeepAwake(); session.ReleaseScreen();
        Check(Screen.sleepTimeout == 15, "repeated setup lost original policy");
        session.ReleaseScreen(); Check(Screen.sleepTimeout == 15, "repeated release changed policy");
        session.KeepAwake(); Screen.sleepTimeout = 30; session.ReleaseScreen();
        Check(Screen.sleepTimeout == 30, "cleanup overwrote a foreign policy");
    }
    public static void Main(string[] args)
    {
        switch (args[0])
        {
            case "model-consent": ModelConsent(); break;
            case "model-bounds": ModelBounds(); break;
            case "screen-consent": ScreenConsent(); break;
            case "screen-errors": ScreenErrors(); break;
            case "screen-escape": ScreenEscape(); break;
            case "settings-lifecycle": SettingsLifecycle(); break;
            case "start-menu-input": StartMenuInput(); break;
            case "end-run-confirmation": EndRunConfirmation(); break;
            case "screen-policy": ScreenPolicy(); break;
            case "settings-save-failure": SettingsSaveFailure(); break;
            case "touch-gui-ownership": TouchGuiOwnership(); break;
            default: throw new Exception("unknown case");
        }
        Console.WriteLine(args[0] + ": PASS");
    }
}
