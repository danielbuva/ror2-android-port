using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace OwnerLayout
{
    public enum HudAnchor { TopLeft, TopRight, BottomLeft, BottomRight, Center }

    public sealed class HudGroup
    {
        public string Id { get; private set; }
        public LayoutRect Rectangle { get; private set; }
        public HudAnchor Anchor { get; private set; }
        internal static void RequireId(string value)
        {
            if (string.IsNullOrEmpty(value) || value.Length > 64) throw new ArgumentException("Identifier length must be 1..64");
            foreach (char c in value)
                if (!(c >= 'a' && c <= 'z') && !(c >= 'A' && c <= 'Z') && !(c >= '0' && c <= '9') && c != '_' && c != '-')
                    throw new ArgumentException("Identifier must use ASCII letters, digits, underscore or hyphen");
        }
        public HudGroup(string id, LayoutRect rectangle, HudAnchor anchor)
        {
            RequireId(id); LayoutProjection.RequireNormalized(rectangle);
            if (!Enum.IsDefined(typeof(HudAnchor), anchor)) throw new ArgumentException("Unknown anchor");
            Id = id; Rectangle = rectangle; Anchor = anchor;
        }
        public LayoutRect Project(LayoutProjection projection, double scale)
        {
            if (projection == null) throw new ArgumentNullException("projection");
            HudProfile.RequireScale(scale);
            var r = Rectangle;
            double width = Math.Min(1, r.Width * scale), height = Math.Min(1, r.Height * scale);
            double x = r.X, y = r.Y;
            if (Anchor == HudAnchor.TopRight || Anchor == HudAnchor.BottomRight) x += r.Width - width;
            if (Anchor == HudAnchor.BottomLeft || Anchor == HudAnchor.BottomRight) y += r.Height - height;
            if (Anchor == HudAnchor.Center) { x += (r.Width - width) / 2; y += (r.Height - height) / 2; }
            return projection.Project(projection.Clamp(new LayoutRect(x, y, width, height), 0, 0));
        }
    }

    public sealed class HudProfile
    {
        private readonly HudGroup[] overrides;
        public string Name { get; private set; }
        public double Scale { get; private set; }
        public HudGroup[] Overrides { get { return (HudGroup[])overrides.Clone(); } }
        internal static void RequireScale(double scale)
        {
            if (!LayoutRect.Finite(scale) || scale < .5 || scale > 2) throw new ArgumentException("HUD scale must be .5..2");
        }
        public HudProfile(string name, double scale, HudGroup[] overrides)
        {
            HudGroup.RequireId(name); RequireScale(scale);
            if (overrides == null || overrides.Length > 128) throw new ArgumentException("At most 128 overrides allowed");
            var ids = new HashSet<string>(StringComparer.Ordinal);
            foreach (var group in overrides)
                if (group == null || !ids.Add(group.Id)) throw new ArgumentException("Duplicate or null override");
            Name = name; Scale = scale; this.overrides = (HudGroup[])overrides.Clone();
        }
        internal HudProfile With(HudGroup group)
        {
            var copy = new List<HudGroup>(overrides);
            for (int i = 0; i < copy.Count; i++)
                if (copy[i].Id == group.Id) { copy[i] = group; return new HudProfile(Name, Scale, copy.ToArray()); }
            copy.Add(group); return new HudProfile(Name, Scale, copy.ToArray());
        }
    }

    public sealed class HudLayoutModel
    {
        public const int Schema = 1;
        public const int MaximumTextLength = 1048576;
        private readonly HudGroup[] defaults;
        private readonly HudProfile[] profiles;
        public HudGroup[] Defaults { get { return (HudGroup[])defaults.Clone(); } }
        public HudProfile[] Profiles { get { return (HudProfile[])profiles.Clone(); } }
        public HudLayoutModel(HudGroup[] defaults, HudProfile[] profiles)
        {
            if (defaults == null || defaults.Length < 1 || defaults.Length > 128 ||
                profiles == null || profiles.Length < 1 || profiles.Length > 16) throw new ArgumentException("Invalid layout counts");
            var ids = new HashSet<string>(StringComparer.Ordinal);
            foreach (var group in defaults)
                if (group == null || !ids.Add(group.Id)) throw new ArgumentException("Duplicate or null default group");
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var profile in profiles)
            {
                if (profile == null || !names.Add(profile.Name)) throw new ArgumentException("Duplicate or null profile");
                foreach (var group in profile.Overrides)
                    if (!ids.Contains(group.Id)) throw new ArgumentException("Override names unknown default group");
            }
            this.defaults = (HudGroup[])defaults.Clone(); this.profiles = (HudProfile[])profiles.Clone();
        }
        public HudProfile Find(string profile)
        {
            foreach (var value in profiles) if (value.Name == profile) return value;
            throw new ArgumentException("Unknown profile");
        }
        public HudGroup Resolve(string profile, string group)
        {
            foreach (var value in Find(profile).Overrides) if (value.Id == group) return value;
            foreach (var value in defaults) if (value.Id == group) return value;
            throw new ArgumentException("Unknown group");
        }
        public LayoutRect Project(string profile, string group, LayoutProjection projection)
        {
            return Resolve(profile, group).Project(projection, Find(profile).Scale);
        }
        internal HudLayoutModel With(HudProfile replacement)
        {
            Find(replacement.Name); var copy = Profiles;
            for (int i = 0; i < copy.Length; i++) if (copy[i].Name == replacement.Name) copy[i] = replacement;
            return new HudLayoutModel(defaults, copy);
        }
        private static string Number(double value) { return value.ToString("R", CultureInfo.InvariantCulture); }
        public string Export()
        {
            var text = new StringBuilder("hud-layout\t1\n");
            foreach (var profile in profiles)
            {
                text.Append("P\t").Append(profile.Name).Append('\t').Append(Number(profile.Scale)).Append('\n');
                foreach (var group in profile.Overrides)
                {
                    var r = group.Rectangle;
                    text.Append("G\t").Append(group.Id).Append('\t').Append((int)group.Anchor);
                    foreach (double value in new[] { r.X, r.Y, r.Width, r.Height }) text.Append('\t').Append(Number(value));
                    text.Append('\n');
                }
            }
            return text.ToString();
        }
        private static double ParseNumber(string text)
        {
            double value;
            if (text.Length == 0 || text.Length > 32 || !double.TryParse(text,
                NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint | NumberStyles.AllowExponent,
                CultureInfo.InvariantCulture, out value) || !LayoutRect.Finite(value)) throw new ArgumentException("Invalid finite number");
            return value;
        }
        public static HudLayoutModel Import(HudGroup[] defaults, string text)
        {
            if (text == null || text.Length > MaximumTextLength || !text.EndsWith("\n", StringComparison.Ordinal))
                throw new ArgumentException("Invalid or oversized document");
            var lines = text.Split('\n');
            if (lines[0] != "hud-layout\t1") throw new ArgumentException("Unknown HUD format/version");
            var result = new List<HudProfile>(); var groups = new List<HudGroup>();
            string name = null; double scale = 1;
            for (int i = 1; i < lines.Length - 1; i++)
            {
                var fields = lines[i].Split('\t');
                if (fields.Length == 3 && fields[0] == "P")
                {
                    if (name != null) result.Add(new HudProfile(name, scale, groups.ToArray()));
                    if (result.Count >= 16) throw new ArgumentException("Too many profiles");
                    name = fields[1]; scale = ParseNumber(fields[2]); groups.Clear();
                }
                else if (fields.Length == 7 && fields[0] == "G" && name != null)
                {
                    if (groups.Count >= 128 || fields[2].Length != 1 || fields[2][0] < '0' || fields[2][0] > '4')
                        throw new ArgumentException("Invalid group count or anchor");
                    groups.Add(new HudGroup(fields[1], new LayoutRect(ParseNumber(fields[3]), ParseNumber(fields[4]),
                        ParseNumber(fields[5]), ParseNumber(fields[6])), (HudAnchor)(fields[2][0] - '0')));
                }
                else throw new ArgumentException("Unknown HUD record");
            }
            if (name != null) result.Add(new HudProfile(name, scale, groups.ToArray()));
            return new HudLayoutModel(defaults, result.ToArray());
        }
    }

    public sealed class HudLayoutEditor
    {
        public HudLayoutModel Model { get; private set; }
        public HudProfile Draft { get; private set; }
        public HudLayoutEditor(HudLayoutModel model)
        {
            if (model == null) throw new ArgumentNullException("model"); Model = model;
        }
        private void RequireDraft() { if (Draft == null) throw new InvalidOperationException("No profile draft"); }
        private void RequireIdle() { if (Draft != null) throw new InvalidOperationException("Confirm or cancel draft first"); }
        public void Begin(string profile) { RequireIdle(); Draft = Model.Find(profile); }
        public void SetScale(double scale) { RequireDraft(); Draft = new HudProfile(Draft.Name, scale, Draft.Overrides); }
        public void SetGroup(HudGroup group)
        {
            RequireDraft(); if (group == null) throw new ArgumentNullException("group");
            Model.Resolve(Draft.Name, group.Id); Draft = Draft.With(group);
        }
        public LayoutRect Preview(string group, LayoutProjection projection)
        {
            RequireDraft(); return Model.With(Draft).Project(Draft.Name, group, projection);
        }
        public void Confirm() { RequireDraft(); Model = Model.With(Draft); Cancel(); }
        public void Cancel() { Draft = null; }
        public void Reset(string profile) { RequireIdle(); Model = Model.With(new HudProfile(profile, 1, new HudGroup[0])); }
        public void Import(string text) { RequireIdle(); Model = HudLayoutModel.Import(Model.Defaults, text); }
    }
}
