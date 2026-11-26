using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace OwnerLayout
{
    public sealed class TouchControl
    {
        public string Id { get; private set; }
        public LayoutRect Rectangle { get; private set; }
        public double Scale { get; private set; }
        public double Opacity { get; private set; }
        public TouchControl(string id, LayoutRect rectangle, double scale, double opacity)
        {
            TouchLayoutDocument.RequireId(id);
            LayoutProjection.RequireNormalized(rectangle);
            if (!LayoutRect.Finite(scale) || scale < .25 || scale > 4 ||
                !LayoutRect.Finite(opacity) || opacity < 0 || opacity > 1)
                throw new ArgumentException("Scale must be .25..4 and opacity 0..1");
            Id = id; Rectangle = rectangle; Scale = scale; Opacity = opacity;
        }
    }

    public sealed class TouchProfile
    {
        private readonly TouchControl[] controls;
        public string Name { get; private set; }
        public TouchControl[] Controls { get { return (TouchControl[])controls.Clone(); } }
        public TouchProfile(string name, TouchControl[] controls)
        {
            TouchLayoutDocument.RequireId(name);
            if (controls == null || controls.Length < 1 || controls.Length > 128)
                throw new ArgumentException("Profile requires 1..128 controls");
            var ids = new HashSet<string>(StringComparer.Ordinal);
            foreach (var control in controls)
                if (control == null || !ids.Add(control.Id)) throw new ArgumentException("Duplicate or null control");
            Name = name; this.controls = (TouchControl[])controls.Clone();
        }
        public TouchControl Find(string id)
        {
            foreach (var control in controls) if (control.Id == id) return control;
            throw new ArgumentException("Unknown control");
        }
        internal TouchProfile With(TouchControl replacement)
        {
            Find(replacement.Id);
            var copy = Controls;
            for (int i = 0; i < copy.Length; i++) if (copy[i].Id == replacement.Id) copy[i] = replacement;
            return new TouchProfile(Name, copy);
        }
    }

    public sealed class TouchLayoutDocument
    {
        public const int Schema = 1;
        public const int MaximumTextLength = 1048576;
        private readonly TouchProfile[] profiles;
        public TouchProfile[] Profiles { get { return (TouchProfile[])profiles.Clone(); } }
        public TouchLayoutDocument(TouchProfile[] profiles)
        {
            if (profiles == null || profiles.Length < 1 || profiles.Length > 16)
                throw new ArgumentException("Document requires 1..16 profiles");
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var profile in profiles)
                if (profile == null || !names.Add(profile.Name)) throw new ArgumentException("Duplicate or null profile");
            this.profiles = (TouchProfile[])profiles.Clone();
        }
        internal static void RequireId(string id)
        {
            if (string.IsNullOrEmpty(id) || id.Length > 64) throw new ArgumentException("Identifier length must be 1..64");
            foreach (char c in id)
                if (!(c >= 'a' && c <= 'z') && !(c >= 'A' && c <= 'Z') && !(c >= '0' && c <= '9') && c != '_' && c != '-')
                    throw new ArgumentException("Identifiers use ASCII letters, digits, underscore or hyphen");
        }
        public TouchProfile Find(string name)
        {
            foreach (var profile in profiles) if (profile.Name == name) return profile;
            throw new ArgumentException("Unknown profile");
        }
        internal TouchLayoutDocument With(TouchProfile replacement)
        {
            Find(replacement.Name);
            var copy = Profiles;
            for (int i = 0; i < copy.Length; i++) if (copy[i].Name == replacement.Name) copy[i] = replacement;
            return new TouchLayoutDocument(copy);
        }
        private static string Number(double value) { return value.ToString("R", CultureInfo.InvariantCulture); }
        public string Export()
        {
            var text = new StringBuilder("touch-layout\t1\n");
            foreach (var profile in profiles)
            {
                text.Append("P\t").Append(profile.Name).Append('\n');
                foreach (var control in profile.Controls)
                {
                    var r = control.Rectangle;
                    text.Append("C\t").Append(control.Id);
                    foreach (double value in new[] { r.X, r.Y, r.Width, r.Height, control.Scale, control.Opacity })
                        text.Append('\t').Append(Number(value));
                    text.Append('\n');
                }
            }
            if (text.Length > MaximumTextLength) throw new ArgumentException("Export exceeds text limit");
            return text.ToString();
        }
        private static double ParseNumber(string text)
        {
            double value;
            if (text.Length == 0 || text.Length > 32 || !double.TryParse(text,
                NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint | NumberStyles.AllowExponent,
                CultureInfo.InvariantCulture, out value) || !LayoutRect.Finite(value))
                throw new ArgumentException("Invalid finite number");
            return value;
        }
        public static TouchLayoutDocument Import(string text)
        {
            if (text == null || text.Length > MaximumTextLength || !text.EndsWith("\n", StringComparison.Ordinal))
                throw new ArgumentException("Invalid or oversized document");
            var lines = text.Split('\n');
            if (lines[0] != "touch-layout\t1") throw new ArgumentException("Unknown layout format/version");
            var result = new List<TouchProfile>();
            var controls = new List<TouchControl>();
            string name = null;
            for (int i = 1; i < lines.Length - 1; i++)
            {
                var fields = lines[i].Split('\t');
                if (fields.Length == 2 && fields[0] == "P")
                {
                    if (name != null) result.Add(new TouchProfile(name, controls.ToArray()));
                    if (result.Count >= 16) throw new ArgumentException("Too many profiles");
                    RequireId(fields[1]); name = fields[1]; controls.Clear();
                }
                else if (fields.Length == 8 && fields[0] == "C" && name != null)
                {
                    if (controls.Count >= 128) throw new ArgumentException("Too many controls");
                    controls.Add(new TouchControl(fields[1], new LayoutRect(ParseNumber(fields[2]), ParseNumber(fields[3]),
                        ParseNumber(fields[4]), ParseNumber(fields[5])), ParseNumber(fields[6]), ParseNumber(fields[7])));
                }
                else throw new ArgumentException("Unknown layout record");
            }
            if (name != null) result.Add(new TouchProfile(name, controls.ToArray()));
            return new TouchLayoutDocument(result.ToArray());
        }
    }

    // In-memory transactions only. The caller owns file I/O and durable save errors.
    public sealed class TouchLayoutEditor
    {
        private readonly TouchLayoutDocument defaults;
        private readonly List<TouchLayoutDocument> undo = new List<TouchLayoutDocument>();
        private readonly List<TouchLayoutDocument> redo = new List<TouchLayoutDocument>();
        public TouchLayoutDocument Document { get; private set; }
        public string SelectedProfile { get; private set; }
        public TouchControl Draft { get; private set; }
        public TouchLayoutEditor(TouchLayoutDocument defaults)
        {
            if (defaults == null) throw new ArgumentNullException("defaults");
            this.defaults = defaults; Document = defaults;
        }
        private void RequireIdle() { if (Draft != null) throw new InvalidOperationException("Confirm or cancel active draft first"); }
        public void Begin(string profile, string control)
        {
            RequireIdle();
            var selected = Document.Find(profile).Find(control);
            SelectedProfile = profile; Draft = selected;
        }
        public void SetDraft(LayoutRect rectangle, double scale, double opacity)
        {
            if (Draft == null) throw new InvalidOperationException("No selected draft");
            Draft = new TouchControl(Draft.Id, rectangle, scale, opacity);
        }
        public void DragResize(LayoutRect rectangle, LayoutProjection projection, double minimumWidth, double minimumHeight)
        {
            if (projection == null) throw new ArgumentNullException("projection");
            if (Draft == null) throw new InvalidOperationException("No selected draft");
            SetDraft(projection.Clamp(rectangle, minimumWidth, minimumHeight), Draft.Scale, Draft.Opacity);
        }
        private static void Push(List<TouchLayoutDocument> stack, TouchLayoutDocument document)
        {
            if (stack.Count == 32) stack.RemoveAt(0);
            stack.Add(document);
        }
        private void Commit(TouchLayoutDocument next)
        {
            Push(undo, Document); Document = next; redo.Clear();
        }
        public void Confirm()
        {
            if (Draft == null) throw new InvalidOperationException("No selected draft");
            Commit(Document.With(Document.Find(SelectedProfile).With(Draft))); Cancel();
        }
        public void Cancel() { Draft = null; SelectedProfile = null; }
        public void Reset(string profile)
        {
            RequireIdle(); Commit(Document.With(defaults.Find(profile)));
        }
        public void Import(string text)
        {
            RequireIdle(); var next = TouchLayoutDocument.Import(text); Commit(next);
        }
        private bool Restore(List<TouchLayoutDocument> source, List<TouchLayoutDocument> destination)
        {
            RequireIdle(); if (source.Count == 0) return false;
            Push(destination, Document); Document = source[source.Count - 1]; source.RemoveAt(source.Count - 1); return true;
        }
        public bool Undo() { return Restore(undo, redo); }
        public bool Redo() { return Restore(redo, undo); }
    }
}
