using System;

namespace OwnerLayout
{
    // Schema 1 convention: top-left origin, x right, y down. Normalized rectangles
    // are relative to the safe rectangle, not the full display or Unity coordinates.
    public struct LayoutRect
    {
        public readonly double X, Y, Width, Height;
        public LayoutRect(double x, double y, double width, double height)
        {
            if (!Finite(x) || !Finite(y) || !Finite(width) || !Finite(height) ||
                width <= 0 || height <= 0 || !Finite(x + width) || !Finite(y + height))
                throw new ArgumentException("Finite coordinates and positive extents required");
            X = x; Y = y; Width = width; Height = height;
        }
        internal static bool Finite(double value) { return !double.IsNaN(value) && !double.IsInfinity(value); }
        internal void Validate() { new LayoutRect(X, Y, Width, Height); }
    }

    public sealed class LayoutProjection
    {
        public const int Schema = 1;
        public LayoutRect SafeArea { get; private set; }
        public LayoutProjection(double width, double height, double left, double top, double right, double bottom)
        {
            new LayoutRect(0, 0, width, height);
            foreach (double inset in new[] { left, top, right, bottom })
                if (!LayoutRect.Finite(inset) || inset < 0) throw new ArgumentException("Finite nonnegative insets required");
            if (left >= width || right >= width - left || top >= height || bottom >= height - top)
                throw new ArgumentException("Insets must leave a positive safe area");
            SafeArea = new LayoutRect(left, top, width - left - right, height - top - bottom);
        }
        public static void RequireNormalized(LayoutRect rectangle)
        {
            rectangle.Validate();
            if (rectangle.X < 0 || rectangle.Y < 0 || rectangle.X + rectangle.Width > 1 || rectangle.Y + rectangle.Height > 1)
                throw new ArgumentException("Rectangle must fit the normalized safe area");
        }
        public LayoutRect Project(LayoutRect normalized)
        {
            RequireNormalized(normalized);
            return new LayoutRect(SafeArea.X + normalized.X * SafeArea.Width, SafeArea.Y + normalized.Y * SafeArea.Height,
                normalized.Width * SafeArea.Width, normalized.Height * SafeArea.Height);
        }
        public LayoutRect Unproject(LayoutRect pixels)
        {
            pixels.Validate();
            // Permit only floating-point boundary roundoff (one trillionth of
            // the safe span), not arbitrary out-of-bounds imported geometry.
            const double epsilon = 1e-12;
            double x = (pixels.X - SafeArea.X) / SafeArea.Width, y = (pixels.Y - SafeArea.Y) / SafeArea.Height;
            double width = pixels.Width / SafeArea.Width, height = pixels.Height / SafeArea.Height;
            if (x < -epsilon || y < -epsilon || x + width > 1 + epsilon || y + height > 1 + epsilon)
                throw new ArgumentException("Pixel rectangle must fit the safe area");
            x = Math.Max(0, x); y = Math.Max(0, y);
            return new LayoutRect(x, y, Math.Min(width, 1 - x), Math.Min(height, 1 - y));
        }
        public LayoutRect Clamp(LayoutRect draft, double minimumWidthPixels, double minimumHeightPixels)
        {
            draft.Validate();
            if (!LayoutRect.Finite(minimumWidthPixels) || !LayoutRect.Finite(minimumHeightPixels) || minimumWidthPixels < 0 || minimumHeightPixels < 0)
                throw new ArgumentException("Finite nonnegative minimum dimensions required");
            // A minimum larger than the display saturates to its available extent.
            double width = Math.Min(1, Math.Max(draft.Width, minimumWidthPixels / SafeArea.Width));
            double height = Math.Min(1, Math.Max(draft.Height, minimumHeightPixels / SafeArea.Height));
            return new LayoutRect(Math.Max(0, Math.Min(draft.X, 1 - width)), Math.Max(0, Math.Min(draft.Y, 1 - height)), width, height);
        }
        public static LayoutRect RotateClockwise(LayoutRect normalized)
        {
            RequireNormalized(normalized);
            return new LayoutRect(1 - (normalized.Y + normalized.Height), normalized.X, normalized.Height, normalized.Width);
        }
    }
}
