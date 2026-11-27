// Subsystem: input/camera. Owned by the offline pause/settings and touch HUD.
using System.IO;
using OwnerLayout;
using UnityEngine;

public sealed partial class PortSession
{
    TouchLayoutSession touchLayoutSession;
    bool touchLayoutSettingsExitPending, touchLayoutPointer, touchLayoutSaved;
    AndroidTouchInput touchLayoutDefaults;
    Rect touchLayoutPointerArea;

    TouchLayoutSession GetTouchLayoutSession()
    {
        if (!UsesTouchUi() || offlineSettings == null) return null;
        if (touchLayoutSession != null) return touchLayoutSession;
        if (touchLayoutDefaults == null) touchLayoutDefaults = new AndroidTouchInput();
        var defaults = touchLayoutDefaults.CreateLayoutDefaults(Screen.safeArea, new Vector2(Screen.width, Screen.height));
        if (defaults == null) return null;
        // A saved layout survives clearing the one-shot editor request.
        touchLayoutSession = new TouchLayoutSession(true, defaults,
            new LayoutPreferenceStore(Path.Combine(offlineSettings.directory, "touch-layout.txt")), touchLayoutDefaults.ValidLayout);
        return touchLayoutSession;
    }

    void ApplyTouchLayout(AndroidTouchInput input)
    {
        if (input == null) return;
        var session = GetTouchLayoutSession();
        if (session != null && (session.StartupState == LayoutLoadState.Loaded || touchLayoutSaved))
            input.SetLayoutProfile(session.Current.Find(AndroidTouchInput.LayoutProfile));
    }

    void CancelTouchLayoutGesture()
    {
        touchLayoutPointer = false;
        touchLayoutSession?.CancelGesture();
    }
    void CloseTouchLayoutEditor()
    {
        CancelTouchLayoutGesture();
        touchLayoutSession?.DiscardAndClose();
        touchLayoutSettingsExitPending = false;
    }

    // Invoked before the settings/world GUI. While visible it owns the whole
    // event, and the existing settings pause suppresses the gameplay input bank.
    bool DrawTouchLayoutEditor()
    {
        if (!UsesTouchUi() || offlineSettings == null || !HasSavedTouchEditorRequest) return false;
        // Do not take over a boot scene, result screen, or an unpausable run.
        if (!offlineSettingsPaused && !offlineStartVisible) return false;
        if (!offlineSettingsVisible) ShowOfflineSettings(true);
        var area = Screen.safeArea;
        var screen = new Vector2(Screen.width, Screen.height);
        var full = AndroidTouchInput.ProjectSafeArea(area, screen);
        if (full == null) { CancelTouchLayoutGesture(); return true; }
        var session = GetTouchLayoutSession();
        if (session == null) return true;
        var space = full.SafeArea;
        float x = (float)space.X, y = (float)space.Y, w = (float)space.Width;
        float toolbar = Mathf.Min(96, area.height * .3f);
        var preview = new LayoutProjection(screen.x, screen.y, x, y + toolbar, screen.x - area.xMax, area.y);
        if (!touchLayoutSettingsExitPending && !session.Editing && session.CanEdit)
            session.OpenEditor(36, 36);
        if (!Application.isFocused) CancelTouchLayoutGesture();

        var pointerArea = new Rect(x, y + toolbar, w, area.height - toolbar);
        if (touchLayoutPointer && touchLayoutPointerArea != pointerArea) CancelTouchLayoutGesture();
        var e = Event.current;
        // Finish an owned drag before toolbar buttons see its release.
        if (touchLayoutPointer && e != null && e.button == 0)
        {
            var pointer = e.mousePosition;
            if (e.type == EventType.MouseDrag)
            {
                session.Move(0, pointer.x, pointer.y, preview);
                e.Use();
            }
            else if (e.type == EventType.MouseUp)
            {
                session.Up(0, pointer.x, pointer.y, preview);
                touchLayoutPointer = false;
                e.Use();
            }
        }
        GUI.Box(new Rect(x, y, w, toolbar), "");
        float width = w / 5, height = toolbar * .52f;
        bool save = GUI.Button(new Rect(x, y, width, height), touchLayoutSettingsExitPending ? "Retry close" : "Save layout");
        bool back = GUI.Button(new Rect(x + width, y, width, height), "Back");
        bool undo = GUI.Button(new Rect(x + width * 2, y, width, height), "Undo");
        bool redo = GUI.Button(new Rect(x + width * 3, y, width, height), "Redo");
        string status = touchLayoutSettingsExitPending ? "Could not clear the editor setting. Retry close."
            : session.SaveFailed ? "Layout save failed. Retry or go back."
            : !session.CanEdit ? "Saved layout unavailable. Defaults in use; original file preserved."
            : "Drag a control to move it. Drag its lower-right corner to resize.";
        GUI.Label(new Rect(x, y + height, w, toolbar - height), status);
        if (save && (touchLayoutSettingsExitPending || session.Editing))
        {
            if (!touchLayoutSettingsExitPending)
            {
                var before = session.Current;
                CancelTouchLayoutGesture();
                if (!session.SaveAndClose()) return true;
                touchLayoutSaved |= !ReferenceEquals(before, session.Current);
                if (worldPlayer != null)
                {
                    var bridge = worldPlayer.GetComponent<NovaInputBridge>();
                    if (bridge != null) ApplyTouchLayout(bridge.touchControls);
                }
            }
            FinishTouchLayoutEditor();
            return true;
        }
        if (back)
        {
            CloseTouchLayoutEditor();
            FinishTouchLayoutEditor();
            return true;
        }
        if (undo) session.Undo();
        if (redo) session.Redo();

        var controls = session.EditorDocument.Find(AndroidTouchInput.LayoutProfile).Controls;
        foreach (var control in controls)
        {
            var draft = session.Draft;
            var active = draft != null && draft.Id == control.Id ? draft : control;
            var rect = PreviewRect(preview, active);
            GUI.Box(rect, active.Id);
            GUI.Box(ResizeHandle(rect), "");
        }
        if (!session.Editing || e == null || !Application.isFocused || e.button != 0) return true;
        var point = e.mousePosition;
        if (e.type == EventType.MouseDown && point.y >= y + toolbar)
        {
            for (int i = controls.Length - 1; i >= 0; i--)
            {
                var rect = PreviewRect(preview, controls[i]);
                if (!rect.Contains(point)) continue;
                touchLayoutPointer = session.Down(0, point.x, point.y, preview, AndroidTouchInput.LayoutProfile, ResizeHandle(rect).Contains(point));
                if (touchLayoutPointer) { touchLayoutPointerArea = pointerArea; e.Use(); }
                break;
            }
        }
        return true;
    }
    static Rect PreviewRect(LayoutProjection projection, TouchControl control)
    {
        var rect = projection.Project(control.Rectangle);
        return new Rect((float)rect.X, (float)rect.Y, (float)rect.Width, (float)rect.Height);
    }
    static Rect ResizeHandle(Rect rect)
    {
        float side = Mathf.Min(22, Mathf.Min(rect.width, rect.height) * .4f);
        return new Rect(rect.xMax - side, rect.yMax - side, side, side);
    }
    void FinishTouchLayoutEditor()
    {
        offlineSettings.values.touchLayoutEditor = false;
        if (SaveOfflineSettings())
        {
            touchLayoutSettingsExitPending = false;
            ShowOfflineSettings(false);
        }
        else
        {
            // Layout and settings are different files. Retry only the settings
            // write after a committed layout, never re-run a durable layout save.
            offlineSettings.values.touchLayoutEditor = true;
            touchLayoutSettingsExitPending = true;
        }
    }
}
