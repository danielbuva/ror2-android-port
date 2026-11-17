// Subsystem: settings/feedback (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Setup: settings Open; teardown: Close on settings exit/session cleanup. No disk state.
using System;
using UnityEngine;

// Owns the complete manual settings -> preview -> clipboard/browser flow.
public sealed class AndroidFeedbackScreen
{
    readonly AndroidFeedbackDraft draft = new AndroidFeedbackDraft();
    Vector2 scroll;
    string status = "";
    GUIStyle text, button, heading, toggle;
    public bool Visible { get; private set; }

    public void Open()
    {
        Close();
        Visible = true;
    }

    public void Close()
    {
        Visible = false;
        draft.Clear();
        scroll = Vector2.zero;
        status = "";
    }

    public void Draw()
    {
        if (!Visible)
            return;
        if (text == null)
        {
            text = new GUIStyle(GUI.skin.textArea) { fontSize = 18, wordWrap = true, richText = false };
            button = new GUIStyle(GUI.skin.button) { fontSize = 18 };
            heading = new GUIStyle(GUI.skin.label) { fontSize = 18, wordWrap = true, richText = false };
            toggle = new GUIStyle(GUI.skin.toggle) { fontSize = 17, wordWrap = true };
        }
        var savedMatrix = GUI.matrix;
        var savedEnabled = GUI.enabled;
        try
        {
            var scale = Mathf.Min(Screen.safeArea.width / 760f, Screen.safeArea.height / 660f);
            if (scale <= 0)
                return;
            // IMGUI uses top-left coordinates; safeArea uses bottom-left.
            GUI.matrix = Matrix4x4.TRS(new Vector3(Screen.safeArea.x, Screen.height - Screen.safeArea.yMax, 0),
                                      Quaternion.identity, new Vector3(scale, scale, 1));
            GUI.Box(new Rect(0, 0, 760, 660), "");
            GUI.Label(new Rect(20, 14, 720, 32), "Send feedback", heading);
            if (GUI.Button(new Rect(550, 12, 190, 38), "Back to settings", button))
            {
                Close();
                return;
            }
            if (draft.Preview.Length == 0)
            {
                GUI.Label(new Rect(20, 62, 720, 62),
                          "Describe what happened, how to reproduce it, and what you expected.\n" +
                          "Your report stays in memory until you choose to share it.", heading);
                draft.Edit(GUI.TextArea(new Rect(20, 132, 720, 290), draft.Notes,
                                        AndroidFeedbackDraft.MaxNotesLength, text));
                GUI.Label(new Rect(20, 430, 720, 62),
                          draft.Notes.Length + "/" + AndroidFeedbackDraft.MaxNotesLength +
                          " characters. No logs or attachments are collected.\n" +
                          "Build facts will be shown before sharing.", heading);
                if (GUI.Button(new Rect(20, 510, 720, 50), "Preview report", button))
                    status = draft.Review(Application.version, Application.unityVersion, Application.buildGUID,
                                          SystemInfo.graphicsDeviceType.ToString()) ? "" : "Enter a description first.";
            }
            else
            {
                GUI.Label(new Rect(20, 62, 720, 50), "Review the entire report, including your own text.", heading);
                scroll = GUI.BeginScrollView(new Rect(20, 114, 720, 286), scroll,
                                             new Rect(0, 0, 685, Mathf.Max(280, text.CalcHeight(new GUIContent(draft.Preview), 680))));
                GUI.Label(new Rect(0, 0, 680, Mathf.Max(280, text.CalcHeight(new GUIContent(draft.Preview), 680))),
                          draft.Preview, text);
                GUI.EndScrollView();
                draft.Consent(GUI.Toggle(new Rect(20, 414, 720, 58), draft.Consented,
                                         "I reviewed this report and agree to share it using the action I choose below.", toggle));
                GUI.enabled = savedEnabled && draft.CanShare;
                if (GUI.Button(new Rect(20, 486, 350, 50), "Copy report", button))
                {
                    try
                    {
                        GUIUtility.systemCopyBuffer = draft.SharedText();
                        status = "Report copied. Paste it where you choose.";
                    }
                    catch (Exception)
                    {
                        status = "Could not copy the report. You can open the issue draft instead.";
                    }
                }
                if (GUI.Button(new Rect(390, 486, 350, 50), "Open GitHub draft", button))
                {
                    try
                    {
                        Application.OpenURL(draft.IssueUrl());
                        status = "Opened a draft in your browser. Review and submit it there.";
                    }
                    catch (Exception)
                    {
                        status = "Could not open a browser. You can copy the report instead.";
                    }
                }
                GUI.enabled = savedEnabled;
                if (GUI.Button(new Rect(20, 548, 720, 42), "Edit report (clears sharing consent)", button))
                {
                    var notes = draft.Notes;
                    draft.Clear();
                    draft.Edit(notes);
                    status = "";
                }
            }
            GUI.Label(new Rect(20, 598, 720, 52), status, heading);
        }
        finally
        {
            GUI.matrix = savedMatrix;
            GUI.enabled = savedEnabled;
        }
    }
}
