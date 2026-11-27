using System;
using System.IO;

namespace OwnerLayout
{
    // App-lifetime owner to be called by the touch HUD. The caller owns the
    // feature gate, private directory and event routing; no Unity/device calls here.
    public sealed class TouchLayoutSession
    {
        private readonly LayoutPreferenceStore store;
        private TouchLayoutEditor editor;
        private TouchEditorGesture gesture;
        public LayoutLoadState? StartupState { get; private set; }
        public TouchLayoutDocument Current { get; private set; }
        public bool CanEdit => StartupState == LayoutLoadState.Loaded || StartupState == LayoutLoadState.Missing;
        public bool Editing => editor != null;
        public bool SaveFailed { get; private set; }
        public TouchLayoutDocument EditorDocument => editor == null ? Current : editor.Document;
        public TouchControl Draft => editor == null ? null : editor.Draft;

        public TouchLayoutSession(bool enabled, TouchLayoutDocument defaults, LayoutPreferenceStore store, Func<TouchLayoutDocument, bool> acceptLoaded = null)
        {
            Current = defaults ?? throw new ArgumentNullException(nameof(defaults));
            if (!enabled) return;
            this.store = store ?? throw new ArgumentNullException(nameof(store));
            var load = store.LoadTouch(defaults);
            StartupState = load.State;
            // Invalid/unavailable is a read-only fallback, not permission to overwrite.
            if (load.State == LayoutLoadState.Loaded)
            {
                if (acceptLoaded != null && !acceptLoaded(load.Value)) StartupState = LayoutLoadState.Invalid;
                else Current = load.Value;
            }
        }

        public bool OpenEditor(double minimumWidthPixels, double minimumHeightPixels)
        {
            if (!CanEdit || Editing) return false;
            var opened = new TouchLayoutEditor(Current);
            gesture = new TouchEditorGesture(opened, minimumWidthPixels, minimumHeightPixels);
            editor = opened;
            return true;
        }

        public bool Down(int pointer, double x, double y, LayoutProjection projection, string profile, bool resize)
            => Editing && gesture.Down(pointer, x, y, projection, profile, resize);
        public bool Move(int pointer, double x, double y, LayoutProjection projection)
            => Editing && gesture.Move(pointer, x, y, projection);
        public bool Up(int pointer, double x, double y, LayoutProjection projection)
            => Editing && gesture.Up(pointer, x, y, projection);
        public bool CancelPointer(int pointer) => Editing && gesture.CancelPointer(pointer);
        public void CancelGesture() { if (Editing) gesture.Cancel(); }
        public bool Undo() => Editing && !gesture.Active && editor.Undo();
        public bool Redo() => Editing && !gesture.Active && editor.Redo();

        // Explicit editor exit is the only write boundary. A failed save leaves
        // gameplay using Current and preserves the editor for Retry or Discard.
        public bool SaveAndClose()
        {
            if (!Editing) return false;
            gesture.Cancel();
            var next = editor.Document;
            if (!ReferenceEquals(Current, next) && !string.Equals(Current.Export(), next.Export(), StringComparison.Ordinal))
            {
                try { store.SaveTouch(next); }
                catch (InvalidDataException) { SaveFailed = true; return false; }
                catch (IOException) { SaveFailed = true; return false; }
                catch (UnauthorizedAccessException) { SaveFailed = true; return false; }
                Current = next;
            }
            DiscardAndClose();
            return true;
        }

        // Also used for teardown: destruction never substitutes for Save.
        public void DiscardAndClose()
        {
            CancelGesture();
            editor = null;
            gesture = null;
            SaveFailed = false;
        }
    }
}
