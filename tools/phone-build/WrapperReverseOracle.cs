using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

// Read-only verification inside a fresh SDK-only desktop process. No private
// SDK functions, external process attachment, runtime initialization or writes.
public static class WrapperReverseOracle
{
    [Serializable] public sealed class Range {public ulong start, size, file_size;}
    [Serializable] public sealed class Layout
    {
        public int schema, begin_offset, end_offset, stride, native_id_offset, forward_offset, forward_count_offset;
        public ulong manager_slot;
        public Range[] ranges;
    }
    [Serializable] public sealed class Name
    {
        public string name, assembly_identity, image_path, image_sha256;
    }
    [Serializable] public sealed class Row {public int persistentTypeID; public Name managed;}
    [Serializable] public sealed class Report
    {
        public int schema = 1;
        public string unity, source_commit, layout_sha256, mono_path, mono_sha256;
        public string queryProfile = "all-object-descendants-v1";
        public bool game_inputs = false, cache_population_qualified = false, root_generation_qualified = false;
        public bool self_process_only = true, existing_runtime_only = true, stable_snapshot;
        public WrapperMetadataOracle.Row[] records;
        public WrapperMetadataOracle.AssemblyInput[] assemblies;
        public Row[] reverse;
        public Row[] forward;
    }
    const string SystemLibrary = "/usr/lib/libSystem.B.dylib";
    [DllImport(SystemLibrary)] static extern uint _dyld_image_count();
    [DllImport(SystemLibrary)] static extern IntPtr _dyld_get_image_name(uint index);
    [DllImport(SystemLibrary)] static extern long _dyld_get_image_vmaddr_slide(uint index);
    [DllImport(SystemLibrary)] static extern IntPtr dlopen(string path, int mode);
    [DllImport(SystemLibrary)] static extern IntPtr dlsym(IntPtr handle, string name);
    [DllImport(SystemLibrary)] static extern int mach_vm_read_overwrite(uint task, ulong address, ulong size, ulong destination, out ulong actual);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Accessor(IntPtr value);
    static string Hash(string path)
    {
        using (var hash = SHA256.Create()) using (var stream = File.OpenRead(path))
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
    static ulong Address(ulong value, long slide) {return checked((ulong)checked((long)value + slide));}
    static bool Contains(Layout layout, long slide, ulong address, int size)
    {
        return size > 0 && layout.ranges.Count(r => address >= Address(r.start, slide)
            && address <= checked(Address(r.start, slide) + r.size - (ulong)size)) == 1;
    }
    static void Pointer(ulong value)
    {
        if (value == 0 || value % 8 != 0) throw new InvalidOperationException("Null or unaligned cache pointer");
    }
    // The host fixture supplies independent memory and metadata callbacks. The
    // actual observer supplies only self-task VM reads and public Mono accessors.
    public static Row[] ReadTable(Layout layout, long slide, Func<ulong, int, byte[]> read, Func<ulong, Name> identify)
    {
        if (!BitConverter.IsLittleEndian || layout.schema != 1 || layout.stride != 16
            || layout.begin_offset < 0 || layout.end_offset != layout.begin_offset + 8
            || layout.native_id_offset != 40 || layout.ranges == null || layout.ranges.Length == 0)
            throw new InvalidOperationException("Unsupported reverse layout");
        var slot = Address(layout.manager_slot, slide);
        if (!Contains(layout, slide, slot, 8)) throw new InvalidOperationException("Manager slot outside SDK VM");
        var manager = BitConverter.ToUInt64(read(slot, 8), 0);
        Pointer(manager);
        var boundsAddress = checked(manager + (ulong)layout.begin_offset);
        var bounds = read(boundsAddress, 16);
        var begin = BitConverter.ToUInt64(bounds, 0);
        var end = BitConverter.ToUInt64(bounds, 8);
        Pointer(begin);
        if (end <= begin || (end - begin) % 16 != 0 || (end - begin) / 16 > 4096)
            throw new InvalidOperationException("Invalid or excessive reverse vector bounds");
        var bytes = read(begin, checked((int)(end - begin)));
        var rows = new List<Row>();
        var identities = new HashSet<string>(StringComparer.Ordinal);
        ulong previous = 0;
        for (int offset = 0; offset < bytes.Length; offset += 16)
        {
            var managed = BitConverter.ToUInt64(bytes, offset);
            var native = BitConverter.ToUInt64(bytes, offset + 8);
            Pointer(managed); Pointer(native);
            if (managed <= previous) throw new InvalidOperationException("Reverse class keys are not unique and ordered");
            previous = managed;
            if (!Contains(layout, slide, native, layout.native_id_offset + 4))
                throw new InvalidOperationException("Native type pointer outside SDK VM");
            var name = identify(managed);
            if (name == null || String.IsNullOrEmpty(name.name) || String.IsNullOrEmpty(name.assembly_identity)
                || !identities.Add(name.assembly_identity + "\n" + name.name))
                throw new InvalidOperationException("Incomplete or duplicate reverse managed identity");
            rows.Add(new Row {persistentTypeID = BitConverter.ToInt32(read(native + (ulong)layout.native_id_offset, 4), 0), managed = name});
        }
        if (!bounds.SequenceEqual(read(boundsAddress, 16)) || !bytes.SequenceEqual(read(begin, bytes.Length))
            || manager != BitConverter.ToUInt64(read(slot, 8), 0))
            throw new InvalidOperationException("Reverse cache changed during observation");
        return rows.ToArray();
    }
    public static Row[] ReadForward(Layout layout, long slide, int[] nativeIDs, Func<ulong, int, byte[]> read, Func<ulong, Name> identify)
    {
        if (layout.forward_offset < 0 || layout.forward_count_offset != layout.forward_offset + 24
            || nativeIDs == null || nativeIDs.Length == 0 || nativeIDs.Length > 4096 || nativeIDs.Distinct().Count() != nativeIDs.Length)
            throw new InvalidOperationException("Unsupported forward vector identity/layout");
        var slot = Address(layout.manager_slot, slide);
        if (!Contains(layout, slide, slot, 8)) throw new InvalidOperationException("Manager slot outside SDK VM");
        var manager = BitConverter.ToUInt64(read(slot, 8), 0);
        Pointer(manager);
        var pointerAddress = checked(manager + (ulong)layout.forward_offset);
        var countAddress = checked(manager + (ulong)layout.forward_count_offset);
        var pointer = BitConverter.ToUInt64(read(pointerAddress, 8), 0);
        Pointer(pointer);
        var count = BitConverter.ToUInt64(read(countAddress, 8), 0);
        if (count != (ulong)nativeIDs.Length) throw new InvalidOperationException("Forward vector differs from native registry coverage");
        var bytes = read(pointer, checked(nativeIDs.Length * 8));
        var rows = new List<Row>();
        for (int i = 0; i < nativeIDs.Length; i++) {
            ulong value = BitConverter.ToUInt64(bytes, i * 8);
            if (value == 0) continue;
            Pointer(value);
            var name = identify(value);
            if (name == null || String.IsNullOrEmpty(name.name) || String.IsNullOrEmpty(name.assembly_identity))
                throw new InvalidOperationException("Incomplete forward identity");
            rows.Add(new Row {persistentTypeID = nativeIDs[i], managed = name});
        }
        if (pointer != BitConverter.ToUInt64(read(pointerAddress, 8), 0) || count != BitConverter.ToUInt64(read(countAddress, 8), 0)
            || !bytes.SequenceEqual(read(pointer, bytes.Length)) || manager != BitConverter.ToUInt64(read(slot, 8), 0))
            throw new InvalidOperationException("Forward cache changed during observation");
        return rows.ToArray();
    }
    static Accessor Api(IntPtr handle, string symbol)
    {
        var value = dlsym(handle, symbol);
        if (value == IntPtr.Zero) throw new InvalidOperationException("Missing existing-runtime metadata accessor");
        return (Accessor)Marshal.GetDelegateForFunctionPointer(value, typeof(Accessor));
    }
    public static void Check()
    {
        if (Application.unityVersion != "2021.3.45f2" || IntPtr.Size != 8)
            throw new InvalidOperationException("Exact 64-bit SDK required");
        var output = Environment.GetEnvironmentVariable("ROR2_POPULATION_ORACLE_REPORT");
        var commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE");
        var layoutPath = Environment.GetEnvironmentVariable("ROR2_REVERSE_ORACLE_LAYOUT");
        var editor = Environment.GetEnvironmentVariable("ROR2_REVERSE_ORACLE_EDITOR");
        var mono = Environment.GetEnvironmentVariable("ROR2_REVERSE_ORACLE_MONO");
        if (String.IsNullOrEmpty(output) || !Path.IsPathRooted(output) || File.Exists(output)
            || commit == null || !System.Text.RegularExpressions.Regex.IsMatch(commit, "^[0-9a-f]{40}$")
            || String.IsNullOrEmpty(layoutPath) || String.IsNullOrEmpty(editor) || String.IsNullOrEmpty(mono))
            throw new InvalidOperationException("Explicit source, SDK, layout and new output required");
        var layoutHash = Hash(layoutPath);
        var layout = JsonUtility.FromJson<Layout>(File.ReadAllText(layoutPath));
        var loadedImages = Enumerable.Range(0, checked((int)_dyld_image_count()))
            .Select(i => new {index = (uint)i, path = Marshal.PtrToStringAnsi(_dyld_get_image_name((uint)i))}).ToArray();
        var image = loadedImages.Single(i => i.path == editor);
        if (loadedImages.Count(i => i.path == mono) != 1) throw new InvalidOperationException("Selected Mono is not already loaded");
        var slide = _dyld_get_image_vmaddr_slide(image.index);
        // RTLD_NOLOAD | RTLD_NOW obtains an existing image handle only. Retain
        // the reference until this isolated process exits; never unload Mono.
        var handle = dlopen(mono, 0x10 | 0x2);
        if (handle == IntPtr.Zero) throw new InvalidOperationException("Existing Mono handle unavailable");
        var getName = Api(handle, "mono_class_get_name");
        var getNamespace = Api(handle, "mono_class_get_namespace");
        var getNesting = Api(handle, "mono_class_get_nesting_type");
        var getImage = Api(handle, "mono_class_get_image");
        var getFilename = Api(handle, "mono_image_get_filename");
        var self = dlsym(new IntPtr(-2), "mach_task_self_");
        if (self == IntPtr.Zero) throw new InvalidOperationException("Self task unavailable");
        uint task = unchecked((uint)Marshal.ReadInt32(self));
        Func<ulong, int, byte[]> read = (address, count) => {
            if (address == 0 || count <= 0 || count > 65536) throw new InvalidOperationException("Invalid self VM read");
            var buffer = new byte[count];
            var pin = GCHandle.Alloc(buffer, GCHandleType.Pinned);
            try {
                ulong actual;
                if (mach_vm_read_overwrite(task, address, (ulong)count, unchecked((ulong)pin.AddrOfPinnedObject().ToInt64()), out actual) != 0
                    || actual != (ulong)count) throw new InvalidOperationException("Self VM range is unreadable");
            } finally {pin.Free();}
            return buffer;
        };
        Func<IntPtr, string> text = pointer => {
            var bytes = new List<byte>();
            for (int i = 0; i < 4096; i++) {
                byte value = read(checked((ulong)pointer.ToInt64() + (ulong)i), 1)[0];
                if (value == 0) return new UTF8Encoding(false, true).GetString(bytes.ToArray());
                bytes.Add(value);
            }
            throw new InvalidOperationException("Unterminated metadata string");
        };
        Func<ulong, Name> identify = address => {
            var current = new IntPtr(checked((long)address));
            read(address, 8);
            var path = Path.GetFullPath(text(getFilename(getImage(current))));
            var contents = Path.GetDirectoryName(Path.GetDirectoryName(editor)) + Path.DirectorySeparatorChar;
            if (!path.StartsWith(contents, StringComparison.Ordinal)) throw new InvalidOperationException("Reverse class image is outside selected SDK");
            var names = new List<string>();
            var seen = new HashSet<IntPtr>();
            string space = "";
            while (current != IntPtr.Zero) {
                if (!seen.Add(current) || seen.Count > 32) throw new InvalidOperationException("Cyclic or excessive nested metadata");
                read(checked((ulong)current.ToInt64()), 8);
                names.Insert(0, text(getName(current)));
                space = text(getNamespace(current));
                current = getNesting(current);
            }
            return new Name {name = (space.Length == 0 ? "" : space + ".") + String.Join("/", names),
                assembly_identity = AssemblyName.GetAssemblyName(path).FullName, image_path = path, image_sha256 = Hash(path)};
        };
        var loaded = AppDomain.CurrentDomain.GetAssemblies();
        var native = WrapperMetadataOracle.UniqueType(loaded, "UnityEditor.UnityType");
        var wrapper = WrapperMetadataOracle.UniqueType(loaded, "UnityEditor.RuntimeClassMetadataUtils");
        var report = new Report {unity = Application.unityVersion, source_commit = commit, layout_sha256 = layoutHash,
            mono_path = mono, mono_sha256 = Hash(mono), records = WrapperPopulationOracle.Collect(native, wrapper)};
        report.reverse = ReadTable(layout, slide, read, identify);
        var nodes = ((System.Collections.IEnumerable)native.GetMethod("GetTypes", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            .Invoke(null, null)).Cast<object>().ToArray();
        var indexField = native.GetField("runtimeTypeIndex", BindingFlags.Instance | BindingFlags.NonPublic);
        var idProperty = native.GetProperty("persistentTypeID", BindingFlags.Instance | BindingFlags.Public);
        if (indexField == null || indexField.FieldType != typeof(uint) || nodes.Length != report.records.Length)
            throw new InvalidOperationException("Native runtime index API differs");
        var indexed = nodes.ToDictionary(n => (uint)indexField.GetValue(n), n => (int)idProperty.GetValue(n, null));
        if (Enumerable.Range(0, nodes.Length).Any(i => !indexed.ContainsKey((uint)i)))
            throw new InvalidOperationException("Native runtime index coverage differs");
        report.forward = ReadForward(layout, slide, Enumerable.Range(0, nodes.Length).Select(i => indexed[(uint)i]).ToArray(), read, identify);
        report.stable_snapshot = true;
        report.assemblies = new[] {native.Assembly, wrapper.Assembly, typeof(UnityEngine.Object).Assembly}.Distinct()
            .Select(a => new WrapperMetadataOracle.AssemblyInput {identity = a.FullName, path = Path.GetFullPath(a.Location), sha256 = Hash(a.Location)}).ToArray();
        if (Hash(layoutPath) != layoutHash) throw new InvalidOperationException("Reverse layout drift");
        using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
        using (var writer = new StreamWriter(stream)) writer.WriteLine(JsonUtility.ToJson(report, true));
        Debug.Log("Reverse cache observation completed: " + report.reverse.Length + " entries");
    }
}
