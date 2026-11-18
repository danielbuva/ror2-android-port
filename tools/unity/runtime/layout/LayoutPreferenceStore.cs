using System;
using System.IO;
using System.Text;

namespace OwnerLayout
{
    public enum LayoutLoadState { Missing, Loaded, Invalid, Unavailable }
    public sealed class LayoutLoadResult<T> where T : class
    {
        public LayoutLoadState State { get; private set; }
        public T Value { get; private set; }
        public string Error { get; private set; }
        internal LayoutLoadResult(LayoutLoadState state, T value, string error)
        { State = state; Value = value; Error = error; }
    }

    // Internal seam for authored host fault tests; production always uses real files.
    internal class LayoutFileOperations
    {
        internal virtual string Read(string path)
        {
            const int maximum = 1048576;
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                var bytes = new byte[maximum + 1]; int count = 0;
                while (count < bytes.Length)
                {
                    int read = stream.Read(bytes, count, bytes.Length - count);
                    if (read == 0) break;
                    count += read;
                }
                if (count > maximum) throw new InvalidDataException("Layout file exceeds 1 MiB");
                return new UTF8Encoding(false, true).GetString(bytes, 0, count);
            }
        }
        internal virtual void Write(string path, string text)
        {
            byte[] bytes = new UTF8Encoding(false, true).GetBytes(text);
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            { stream.Write(bytes, 0, bytes.Length); stream.Flush(true); }
        }
        internal virtual void Publish(string temporary, string destination, bool replace)
        {
            // Refuse unsupported atomic replacement; never delete the previous file first.
            if (replace) File.Replace(temporary, destination, null);
            else File.Move(temporary, destination);
        }
        internal virtual void DeleteTemporary(string path) { File.Delete(path); }
    }

    // One caller-owned regular file in an existing private directory; no runtime wiring.
    // A caller must serialize writers across instances/processes and own path security.
    public sealed class LayoutPreferenceStore
    {
        private readonly string path;
        private readonly LayoutFileOperations files;
        private readonly object gate = new object();
        public LayoutPreferenceStore(string path) : this(path, new LayoutFileOperations()) { }
        internal LayoutPreferenceStore(string path, LayoutFileOperations files)
        {
            if (string.IsNullOrEmpty(path)) throw new ArgumentException("Caller-owned path required");
            if (files == null) throw new ArgumentNullException("files");
            this.path = Path.GetFullPath(path); this.files = files;
        }
        private LayoutLoadResult<T> Load<T>(T defaults, Func<string, T> parse) where T : class
        {
            if (defaults == null) throw new ArgumentNullException("defaults");
            try { return new LayoutLoadResult<T>(LayoutLoadState.Loaded, parse(files.Read(path)), null); }
            catch (FileNotFoundException) { return new LayoutLoadResult<T>(LayoutLoadState.Missing, defaults, null); }
            catch (DirectoryNotFoundException e) { return new LayoutLoadResult<T>(LayoutLoadState.Unavailable, null, e.Message); }
            catch (InvalidDataException e) { return new LayoutLoadResult<T>(LayoutLoadState.Invalid, null, e.Message); }
            catch (ArgumentException e) { return new LayoutLoadResult<T>(LayoutLoadState.Invalid, null, e.Message); }
            catch (IOException e) { return new LayoutLoadResult<T>(LayoutLoadState.Unavailable, null, e.Message); }
            catch (UnauthorizedAccessException e) { return new LayoutLoadResult<T>(LayoutLoadState.Unavailable, null, e.Message); }
        }
        public LayoutLoadResult<TouchLayoutDocument> LoadTouch(TouchLayoutDocument defaults)
        { lock (gate) return Load(defaults, TouchLayoutDocument.Import); }
        public LayoutLoadResult<HudLayoutModel> LoadHud(HudLayoutModel defaults)
        {
            if (defaults == null) throw new ArgumentNullException("defaults");
            lock (gate) return Load(defaults, text => HudLayoutModel.Import(defaults.Defaults, text));
        }
        private void Save<T>(T model, string text, Func<string, T> parse) where T : class
        {
            // Validate existing state without File.Exists (which hides access failures).
            var previous = Load(model, parse);
            if (previous.State == LayoutLoadState.Invalid) throw new InvalidDataException("Existing layout is invalid; preserve it for explicit recovery");
            if (previous.State == LayoutLoadState.Unavailable) throw new IOException("Existing layout is unavailable: " + previous.Error);
            string temporary = Path.Combine(Path.GetDirectoryName(path), ".layout-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                files.Write(temporary, text);
                files.Publish(temporary, path, previous.State == LayoutLoadState.Loaded);
            }
            finally
            {
                // Cleanup is best effort and cannot turn a published save into a reported failure.
                try { files.DeleteTemporary(temporary); }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
        }
        public void SaveTouch(TouchLayoutDocument model)
        {
            if (model == null) throw new ArgumentNullException("model");
            lock (gate) Save(model, model.Export(), TouchLayoutDocument.Import);
        }
        public void SaveHud(HudLayoutModel model)
        {
            if (model == null) throw new ArgumentNullException("model");
            lock (gate) Save(model, model.Export(), text => HudLayoutModel.Import(model.Defaults, text));
        }
    }
}
