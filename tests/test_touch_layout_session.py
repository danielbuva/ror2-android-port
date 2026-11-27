"""Exercise the authored HUD layout lifecycle without Unity or a phone."""

import unittest

from tests.layout_csharp import run_csharp


HARNESS = r"""
using System;
using System.IO;
using OwnerLayout;

sealed class StoreProbe : LayoutFileOperations {
    internal int Reads, Publishes;
    internal bool FailPublish;
    internal override string Read(string path) { Reads++; return base.Read(path); }
    internal override void Publish(string temporary, string destination, bool replace) {
        Publishes++;
        if (FailPublish) throw new IOException("synthetic publication failure");
        base.Publish(temporary, destination, replace);
    }
}

class Harness {
    static void Check(bool value, string label) {
        if (!value) throw new Exception(label);
    }
    static void Main() {
        string root = Path.Combine(Path.GetTempPath(), "touch-session-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try {
            string path = Path.Combine(root, "layout.txt");
            var defaults = new TouchLayoutDocument(new[] { new TouchProfile("main",
                new[] { new TouchControl("generic", new LayoutRect(.1, .1, .2, .2), 1, 1) }) });
            var probe = new StoreProbe();
            var store = new LayoutPreferenceStore(path, probe);
            var projection = new LayoutProjection(1000, 600, 0, 0, 0, 0);
            var disabled = new TouchLayoutSession(false, defaults, store);
            Check(disabled.StartupState == null && disabled.Current == defaults &&
                !disabled.OpenEditor(40, 40) && !disabled.SaveAndClose() && probe.Reads == 0, "disabled is inert");

            var session = new TouchLayoutSession(true, defaults, store);
            Check(session.StartupState == LayoutLoadState.Missing && session.CanEdit &&
                session.Current == defaults && !session.Editing, "first startup uses defaults");
            Check(session.OpenEditor(40, 40) && session.Down(1, 140, 85, projection, "main", false) &&
                session.Move(1, 340, 205, projection) && session.Draft != null, "preview capture");
            Check(session.SaveAndClose() && !File.Exists(path), "exit discards an unfinished draft");

            Check(session.OpenEditor(40, 40) && session.Down(1, 140, 85, projection, "main", false) &&
                session.Up(1, 340, 205, projection), "commit edit");
            Check(session.Current == defaults && session.EditorDocument != defaults && !File.Exists(path),
                "unpublished edit is not the running layout");
            Check(session.SaveAndClose() && File.Exists(path) && !session.Editing && probe.Publishes == 1, "save on explicit exit");
            string saved = File.ReadAllText(path);
            session = new TouchLayoutSession(true, defaults, store);
            Check(session.StartupState == LayoutLoadState.Loaded && session.Current.Export() == saved, "load on restart");
            Check(session.OpenEditor(40, 40) && session.SaveAndClose() && probe.Publishes == 1, "unchanged exit does not write");

            Check(session.OpenEditor(40, 40) && session.Down(2, 340, 205, projection, "main", true) &&
                session.Up(2, 400, 250, projection), "resize in editor");
            Check(session.Undo() && session.Redo(), "undo/redo delegates to editor");
            probe.FailPublish = true;
            Check(!session.SaveAndClose() && session.SaveFailed && session.Editing && File.ReadAllText(path) == saved &&
                session.Current.Export() == saved && session.EditorDocument.Export() != saved, "failed write remains retryable");
            probe.FailPublish = false;
            Check(session.SaveAndClose() && !session.SaveFailed && File.ReadAllText(path) != saved, "retry publishes existing edit");

            Check(session.OpenEditor(40, 40) && session.Down(3, 340, 205, projection, "main", false) &&
                session.Up(3, 450, 275, projection), "edit before teardown");
            saved = File.ReadAllText(path);
            session.DiscardAndClose();
            Check(!session.Editing && session.Current.Export() == saved && File.ReadAllText(path) == saved,
                "teardown never saves silently");

            File.WriteAllText(path, "synthetic corrupt layout");
            var corrupt = new TouchLayoutSession(true, defaults, store);
            Check(corrupt.StartupState == LayoutLoadState.Invalid && corrupt.Current == defaults && !corrupt.CanEdit &&
                !corrupt.OpenEditor(40, 40) && !corrupt.SaveAndClose() && File.ReadAllText(path) == "synthetic corrupt layout",
                "corrupt file remains intact with read-only defaults");
            var unavailable = new TouchLayoutSession(true, defaults,
                new LayoutPreferenceStore(Path.Combine(root, "missing-directory", "layout.txt")));
            Check(unavailable.StartupState == LayoutLoadState.Unavailable && unavailable.Current == defaults &&
                !unavailable.CanEdit, "unavailable is not a missing file");
            Console.WriteLine("touch layout session PASS");
        } finally {
            Directory.Delete(root, true);
        }
    }
}
"""


class TouchLayoutSessionTests(unittest.TestCase):
    def test_actual_layout_session_start_exit_restart_and_fallback(self):
        self.assertIn(
            "touch layout session PASS",
            run_csharp(
                HARNESS,
                [
                    "LayoutProjection.cs",
                    "TouchLayoutDocument.cs",
                    "HudLayoutModel.cs",
                    "LayoutPreferenceStore.cs",
                    "TouchEditorGesture.cs",
                    "TouchLayoutSession.cs",
                ],
            ),
        )
