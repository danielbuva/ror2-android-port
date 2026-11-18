using System;

namespace OwnerLayout
{
    // Pointer coordinates are caller-supplied top-left display pixels, editor only.
    public sealed class TouchEditorGesture
    {
        private readonly TouchLayoutEditor editor;
        private readonly double minimumWidth, minimumHeight;
        private int pointer;
        private double startX, startY;
        private LayoutRect startRectangle, safeArea;
        private bool resize;
        public bool Active { get; private set; }
        public TouchEditorGesture(TouchLayoutEditor editor, double minimumWidthPixels, double minimumHeightPixels)
        {
            if (editor == null) throw new ArgumentNullException("editor");
            if (!LayoutRect.Finite(minimumWidthPixels) || !LayoutRect.Finite(minimumHeightPixels) ||
                minimumWidthPixels <= 0 || minimumHeightPixels <= 0) throw new ArgumentException("Positive finite editor minimums required");
            this.editor = editor; minimumWidth = minimumWidthPixels; minimumHeight = minimumHeightPixels;
        }
        private static void RequirePoint(double x, double y, LayoutProjection projection)
        {
            if (projection == null) throw new ArgumentNullException("projection");
            if (!LayoutRect.Finite(x) || !LayoutRect.Finite(y)) throw new ArgumentException("Finite pointer coordinates required");
        }
        public bool Down(int pointerId, double x, double y, LayoutProjection projection, string profile, bool resizeBottomRight)
        {
            if (Active) return false;
            RequirePoint(x, y, projection);
            if (editor.Draft != null) throw new InvalidOperationException("Editor already owns a draft");
            var controls = editor.Document.Find(profile).Controls;
            // Last authored control is topmost. Half-open edges avoid double hits.
            for (int i = controls.Length - 1; i >= 0; i--)
            {
                var pixels = projection.Project(controls[i].Rectangle);
                if (x < pixels.X || y < pixels.Y || x >= pixels.X + pixels.Width || y >= pixels.Y + pixels.Height) continue;
                editor.Begin(profile, controls[i].Id);
                pointer = pointerId; startX = x; startY = y; startRectangle = controls[i].Rectangle;
                safeArea = projection.SafeArea; resize = resizeBottomRight; Active = true; return true;
            }
            return false;
        }
        private bool SameArea(LayoutRect area)
        {
            return area.X == safeArea.X && area.Y == safeArea.Y && area.Width == safeArea.Width && area.Height == safeArea.Height;
        }
        public bool Move(int pointerId, double x, double y, LayoutProjection projection)
        {
            if (!Active || pointerId != pointer) return false;
            RequirePoint(x, y, projection);
            // Rotation/inset/aspect changes invalidate the pixel basis, not saved preferences.
            if (!SameArea(projection.SafeArea)) { Cancel(); return false; }
            double dx = (x - startX) / safeArea.Width, dy = (y - startY) / safeArea.Height;
            if (!LayoutRect.Finite(dx) || !LayoutRect.Finite(dy)) throw new ArgumentException("Pointer delta overflow");
            var r = startRectangle;
            var next = resize
                ? new LayoutRect(r.X, r.Y, Math.Max(minimumWidth / safeArea.Width, r.Width + dx), Math.Max(minimumHeight / safeArea.Height, r.Height + dy))
                : new LayoutRect(r.X + dx, r.Y + dy, r.Width, r.Height);
            editor.DragResize(next, projection, minimumWidth, minimumHeight); return true;
        }
        public bool Up(int pointerId, double x, double y, LayoutProjection projection)
        {
            if (!Move(pointerId, x, y, projection)) return false;
            editor.Confirm(); Active = false; return true;
        }
        public bool CancelPointer(int pointerId)
        {
            if (!Active || pointerId != pointer) return false;
            Cancel(); return true;
        }
        // Focus loss, navigation, teardown or a display change without another pointer event.
        public void Cancel()
        {
            if (Active) editor.Cancel();
            Active = false;
        }
    }
}
