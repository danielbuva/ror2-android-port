using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

static string Sha(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
static string ShaText(string text) => Sha(Encoding.UTF8.GetBytes(text));
const string ReviewedInputSha = "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781";
const string ReviewedPolicySha = "1f28d8b071a9e7dd5fe7ade1bd6b7a693df23dbd4d42f4e58241b43377c06676";
const string ReviewedPlanSha = "3f60b5c66aae12be4b5ccfee704f155e4950d0681effcb09e15388de4fbd8222";
static string Need(JsonElement e, string key) => e.GetProperty(key).GetString() ?? throw new InvalidDataException(key);
static string TypeName(TypeReference t) => t switch {
    ByReferenceType x => TypeName(x.ElementType) + "&", PointerType x => TypeName(x.ElementType) + "*",
    ArrayType x when x.Rank == 1 && !x.IsVector => throw new InvalidDataException("Unsupported non-vector rank-one array metadata"),
    ArrayType x => TypeName(x.ElementType) + "[" + new string(',', x.Rank - 1) + "]" +
        (x.Dimensions.Any(d => d.LowerBound is not null || d.UpperBound is not null)
            ? "{" + string.Join(',', x.Dimensions.Select(d => (d.LowerBound?.ToString(CultureInfo.InvariantCulture) ?? "") + ".." + (d.UpperBound?.ToString(CultureInfo.InvariantCulture) ?? ""))) + "}" : ""),
    GenericInstanceType x => TypeName(x.ElementType) + "<" + string.Join(',', x.GenericArguments.Select(TypeName)) + ">",
    GenericParameter x => (x.Type == GenericParameterType.Method ? "!!" : "!") + x.Position,
    OptionalModifierType x => "modopt(" + TypeName(x.ModifierType) + ")" + TypeName(x.ElementType),
    RequiredModifierType x => "modreq(" + TypeName(x.ModifierType) + ")" + TypeName(x.ElementType),
    FunctionPointerType => throw new InvalidDataException("Unsupported function-pointer metadata"),
    _ => t.FullName switch { "System.Void"=>"void", "System.Boolean"=>"bool", "System.Byte"=>"byte", "System.SByte"=>"sbyte",
        "System.Int16"=>"short", "System.UInt16"=>"ushort", "System.Int32"=>"int", "System.UInt32"=>"uint",
        "System.Int64"=>"long", "System.UInt64"=>"ulong", "System.Single"=>"float", "System.Double"=>"double",
        "System.String"=>"string", "System.IntPtr"=>"IntPtr", "System.UIntPtr"=>"UIntPtr", _=>t.FullName.Replace('/', '.') }
};
// Import rows keep by-reference direction as a separate explicit ABI field;
// CanonType removes only that outer wrapper while preserving nested pointer,
// array-rank/bounds, generic, and modifier shapes.
static string CanonType(TypeReference t) => t is ByReferenceType br ? TypeName(br.ElementType) : TypeName(t);
static string Direction(ParameterDefinition p) {
    if (p.ParameterType is not ByReferenceType) return "value";
    return (p.Attributes & ParameterAttributes.Out) != 0 && (p.Attributes & ParameterAttributes.In) == 0 ? "out" :
        (p.Attributes & ParameterAttributes.In) != 0 && (p.Attributes & ParameterAttributes.Out) == 0 ? "in" : "ref";
}
static string MarshalKind(MarshalInfo? info) => info is null ? "" : info.NativeType == NativeType.Array ? "LPArray" : info.NativeType.ToString();
static string ExpectedMarshal(JsonElement list) => list.GetArrayLength() == 0 ? "" : list[0].GetString()!.Replace("UnmanagedType.", "", StringComparison.Ordinal);
static void Check(bool condition, string message) { if (!condition) throw new InvalidDataException(message); }
static string BodyFingerprint(MethodDefinition m) {
    if (!m.HasBody) return "<no-body>";
    var sb = new StringBuilder();
    sb.Append("max=").Append(m.Body.MaxStackSize).Append(";init=").Append(m.Body.InitLocals).Append(";locals=");
    foreach (var v in m.Body.Variables) sb.Append(v.Index).Append(':').Append(TypeName(v.VariableType)).Append(';');
    sb.Append(";eh=");
    foreach (var h in m.Body.ExceptionHandlers) sb.Append(h.HandlerType).Append(':').Append(h.TryStart?.Offset).Append(':').Append(h.TryEnd?.Offset)
        .Append(':').Append(h.HandlerStart?.Offset).Append(':').Append(h.HandlerEnd?.Offset).Append(':').Append(h.FilterStart?.Offset)
        .Append(':').Append(h.CatchType is null ? "" : TypeName(h.CatchType)).Append(';');
    sb.Append(";il=");
    foreach (var ins in m.Body.Instructions) {
        sb.Append(ins.OpCode.Code).Append('|');
        var o = ins.Operand;
        sb.Append(o switch {
            null => "",
            string s => "str:" + JsonSerializer.Serialize(s),
            Instruction target => "br:" + target.Offset.ToString(CultureInfo.InvariantCulture),
            Instruction[] targets => "brs:" + string.Join(',', targets.Select(x => x.Offset)),
            MethodReference mr => "method:" + mr.FullName,
            FieldReference fr => "field:" + fr.FullName,
            TypeReference tr => "type:" + tr.FullName,
            ParameterDefinition pd => "param:" + pd.Index,
            VariableDefinition vd => "var:" + vd.Index,
            IFormattable f => f.ToString(null, CultureInfo.InvariantCulture) ?? "",
            _ => o.ToString() ?? ""
        }).Append('\n');
    }
    return ShaText(sb.ToString());
}
static string MarshalFingerprint(MarshalInfo? info) {
    if (info is null) return "<none>";
    var kind = info.GetType().Name;
    var allowed = new HashSet<string>{"MarshalInfo","ArrayMarshalInfo","FixedArrayMarshalInfo","FixedSysStringMarshalInfo","SafeArrayMarshalInfo","CustomMarshalInfo","InterfaceMarshalInfo"};
    Check(allowed.Contains(kind), "Unsupported MarshalInfo in structure fingerprint: " + kind);
    static string StableValue(object? value) => value switch {
        null => "null",
        TypeReference type => "type:" + TypeName(type),
        string text => "string:" + JsonSerializer.Serialize(text),
        bool flag => "bool:" + (flag ? "true" : "false"),
        IFormattable formattable => value.GetType().FullName + ":" + (formattable.ToString(null, CultureInfo.InvariantCulture) ?? ""),
        _ => throw new InvalidDataException("Unsupported MarshalInfo property type: " + value.GetType().FullName)
    };
    var values = info.GetType().GetProperties(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public)
        .Where(p => p.CanRead && p.GetIndexParameters().Length == 0).OrderBy(p => p.Name, StringComparer.Ordinal)
        .Select(p => p.Name + "=" + StableValue(p.GetValue(info)));
    return kind + "{" + string.Join(';', values) + "}";
}
static string PInvokeMarshalFingerprint(IEnumerable<MethodDefinition> methods) => string.Join("\n",
    methods.Where(m => m.PInvokeInfo is not null).Select(m => m.FullName + "|return=" + MarshalFingerprint(m.MethodReturnType.MarshalInfo) +
        "|args=" + string.Join(";", m.Parameters.Select(p => MarshalFingerprint(p.MarshalInfo)))));
static string CustomAttributesFingerprint(IEnumerable<CustomAttribute> attrs) => string.Join(";", attrs.Select(a =>
    a.AttributeType.FullName + ":" + a.Constructor.FullName + ":" + Convert.ToBase64String(a.GetBlob())));
static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> types) {
    foreach (var type in types) { yield return type; foreach (var child in AllTypes(type.NestedTypes)) yield return child; }
}
static string CallConv(PInvokeAttributes a) => (a & PInvokeAttributes.CallConvMask) switch {
    PInvokeAttributes.CallConvWinapi => "default", PInvokeAttributes.CallConvCdecl => "Cdecl",
    PInvokeAttributes.CallConvStdCall => "StdCall", PInvokeAttributes.CallConvThiscall => "ThisCall",
    PInvokeAttributes.CallConvFastcall => "FastCall", _ => "unsupported"
};
static string Charset(PInvokeAttributes a) => (a & PInvokeAttributes.CharSetMask) switch {
    0 => "default", PInvokeAttributes.CharSetAnsi => "Ansi",
    PInvokeAttributes.CharSetUnicode => "Unicode", PInvokeAttributes.CharSetAuto => "Auto", _ => "unsupported"
};
static string BestFit(PInvokeAttributes a) => (a & PInvokeAttributes.BestFitMask) switch {
    0 => "default", PInvokeAttributes.BestFitEnabled => "enabled", PInvokeAttributes.BestFitDisabled => "disabled", _ => "unsupported"
};
static string ThrowOnUnmappable(PInvokeAttributes a) => (a & PInvokeAttributes.ThrowOnUnmappableCharMask) switch {
    0 => "default", PInvokeAttributes.ThrowOnUnmappableCharEnabled => "enabled", PInvokeAttributes.ThrowOnUnmappableCharDisabled => "disabled", _ => "unsupported"
};
static string AttributeFingerprint(IEnumerable<CustomAttribute> attributes) => string.Join("\n", attributes.Select(a =>
    a.AttributeType.FullName + "|" + a.Constructor.FullName + "|" + Convert.ToBase64String(a.GetBlob())));
static string ConstantFingerprint(bool hasConstant, object? value) => !hasConstant ? "<none>" : value switch {
    byte[] bytes => "bytes:" + Convert.ToBase64String(bytes),
    null => "null",
    IFormattable f => value.GetType().FullName + ":" + (f.ToString(null, CultureInfo.InvariantCulture) ?? ""),
    _ => value.GetType().FullName + ":" + value.ToString()
};
static string ConstraintFingerprint(GenericParameterConstraint c) => c.ConstraintType.FullName + ":attrs=" + CustomAttributesFingerprint(c.CustomAttributes);
static string ParameterFingerprint(ParameterDefinition p) => p.Name + "/" + TypeName(p.ParameterType) + "/" + p.Attributes +
    "/marshal=" + MarshalFingerprint(p.MarshalInfo) + "/constant=" + ConstantFingerprint(p.HasConstant, p.Constant) +
    "/attrs=" + CustomAttributesFingerprint(p.CustomAttributes);
static string ReturnFingerprint(MethodReturnType r) => r.Attributes + "/marshal=" + MarshalFingerprint(r.MarshalInfo) +
    "/constant=" + ConstantFingerprint(r.HasConstant, r.Constant) + "/attrs=" + CustomAttributesFingerprint(r.CustomAttributes);
static string SecurityFingerprint(MethodDefinition m) {
    Check(m.SecurityDeclarations.Count == 0, "Unsupported method security declarations: " + m.FullName);
    return "<none>";
}
static string ExpectedAttributeFingerprint(JsonElement rows) => string.Join("\n", rows.EnumerateArray().Select(a =>
    Need(a, "type") + "|" + Need(a, "constructor") + "|" + Need(a, "raw_blob_base64")));
static string CanonOption(string value) => value == "default" ? "default" : value;
static void VerifyImport(MethodDefinition m, JsonElement declaration, string label) {
    var p = m.PInvokeInfo ?? throw new InvalidDataException("Expected P/Invoke: " + label);
    Check(p.Module.Name == Need(declaration, "library"), label + ": library mismatch");
    Check(p.EntryPoint == Need(declaration, "entrypoint"), label + ": entrypoint mismatch");
    Check(CallConv(p.Attributes) == CanonOption(Need(declaration, "calling_convention")), label + ": calling convention mismatch");
    Check(Charset(p.Attributes) == CanonOption(Need(declaration, "charset")), label + ": charset mismatch");
    Check(BestFit(p.Attributes) == Need(declaration, "best_fit_mapping"), label + ": BestFitMapping mismatch");
    Check(ThrowOnUnmappable(p.Attributes) == Need(declaration, "throw_on_unmappable_char"), label + ": ThrowOnUnmappableChar mismatch");
    Check((int)p.Attributes == declaration.GetProperty("raw_pinvoke_flags").GetInt32(), label + ": complete P/Invoke flag mismatch");
    Check(((p.Attributes & PInvokeAttributes.NoMangle) != 0 ? "true" : "default") == Need(declaration, "exact_spelling"), label + ": ExactSpelling mismatch");
    Check(((p.Attributes & PInvokeAttributes.SupportsLastError) != 0 ? "true" : "default") == Need(declaration, "set_last_error"), label + ": SetLastError mismatch");
    Check(AttributeFingerprint(m.CustomAttributes) == ExpectedAttributeFingerprint(declaration.GetProperty("method_custom_attributes")), label + ": method custom-attribute payload mismatch");
    Check(CanonType(m.ReturnType) == Need(declaration, "return"), label + ": return type mismatch");
    Check(m.MethodReturnType.Attributes.ToString() == Need(declaration, "return_attributes"), label + ": return parameter flags mismatch");
    Check(AttributeFingerprint(m.MethodReturnType.CustomAttributes) == ExpectedAttributeFingerprint(declaration.GetProperty("return_custom_attributes")), label + ": return custom-attribute payload mismatch");
    Check(MarshalKind(m.MethodReturnType.MarshalInfo) == ExpectedMarshal(declaration.GetProperty("return_marshal")), label + ": return MarshalAs mismatch");
    var expectedArgs = declaration.GetProperty("args");
    Check(m.Parameters.Count == expectedArgs.GetArrayLength(), label + ": parameter count mismatch");
    for (int i = 0; i < m.Parameters.Count; i++) {
        var actual = m.Parameters[i]; var expected = expectedArgs[i];
        Check(CanonType(actual.ParameterType) == Need(expected, "type"), label + $": parameter {i} type mismatch actual={CanonType(actual.ParameterType)} expected={Need(expected, "type")}");
        Check(Direction(actual) == Need(expected, "direction"), label + $": parameter {i} direction mismatch");
        var actualFlags = actual.Attributes.ToString().Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Where(x => x != "None").OrderBy(x => x, StringComparer.Ordinal);
        var expectedFlags = expected.GetProperty("attributes").EnumerateArray().Select(x => x.GetString()!).OrderBy(x => x, StringComparer.Ordinal);
        Check(actualFlags.SequenceEqual(expectedFlags), label + $": parameter {i} metadata flags mismatch");
        Check(AttributeFingerprint(actual.CustomAttributes) == ExpectedAttributeFingerprint(expected.GetProperty("custom_attributes")), label + $": parameter {i} custom-attribute payload mismatch");
        Check(MarshalKind(actual.MarshalInfo) == ExpectedMarshal(expected.GetProperty("marshal")), label + $": parameter {i} MarshalAs mismatch actual={MarshalKind(actual.MarshalInfo)} expected={ExpectedMarshal(expected.GetProperty("marshal"))}");
    }
}
static string MethodFingerprint(MethodDefinition m) => m.FullName + "|" + m.Attributes + "|" + m.ImplAttributes + "|" +
    "generic=" + string.Join(";", m.GenericParameters.Select(g => g.Name + ":" + g.Attributes + ":" + string.Join(',', g.Constraints.Select(ConstraintFingerprint)) + ":attrs=" + CustomAttributesFingerprint(g.CustomAttributes))) +
    "|return=" + (m.PInvokeInfo is null ? ReturnFingerprint(m.MethodReturnType) : m.MethodReturnType.Attributes + "/constant=" + ConstantFingerprint(m.MethodReturnType.HasConstant, m.MethodReturnType.Constant) + "/pinvoke-reviewed-separately") +
    "|args=" + string.Join(";", m.Parameters.Select(p => m.PInvokeInfo is null ? ParameterFingerprint(p) : p.Name + "/" + TypeName(p.ParameterType) + "/" + p.Attributes + "/constant=" + ConstantFingerprint(p.HasConstant, p.Constant) + "/pinvoke-reviewed-separately")) +
    "|overrides=" + string.Join(";", m.Overrides.Select(x => x.FullName)) +
    "|security=" + SecurityFingerprint(m) + "|" + BodyFingerprint(m);
static string TypeApiFingerprint(TypeDefinition t) {
    var fields = string.Join(";", t.Fields.Select(f => { var hasRva = (f.Attributes & FieldAttributes.HasFieldRVA) != 0; return f.Name + ":" + TypeName(f.FieldType) + ":" + f.Attributes + ":offset=" + f.Offset + ":marshal=" + MarshalFingerprint(f.MarshalInfo) + ":constant=" + ConstantFingerprint(f.HasConstant, f.Constant) + ":rva=" + hasRva + ":initial=" + (hasRva ? Convert.ToBase64String(f.InitialValue) : "") + ":attrs=" + CustomAttributesFingerprint(f.CustomAttributes); }));
    var methods = string.Join(";", t.Methods.Select(m => m.FullName + ":" + m.Attributes + ":" + m.ImplAttributes + ":ret=" + m.MethodReturnType.Attributes +
        ":retmarshal=" + (m.PInvokeInfo is null ? MarshalFingerprint(m.MethodReturnType.MarshalInfo) : "<pinvoke-reviewed-separately>") + ":attrs=" + CustomAttributesFingerprint(m.CustomAttributes) +
        ":retattrs=" + (m.PInvokeInfo is null ? CustomAttributesFingerprint(m.MethodReturnType.CustomAttributes) : "<pinvoke-reviewed-separately>") + ":args=" + string.Join(',', m.Parameters.Select(p => p.Name + "/" + TypeName(p.ParameterType) + "/" + p.Attributes + "/constant=" + ConstantFingerprint(p.HasConstant, p.Constant) +
            "/marshal=" + (m.PInvokeInfo is null ? MarshalFingerprint(p.MarshalInfo) : "<pinvoke-reviewed-separately>") + "/attrs=" + (m.PInvokeInfo is null ? CustomAttributesFingerprint(p.CustomAttributes) : "<pinvoke-reviewed-separately>")))));
    var properties = string.Join(";", t.Properties.Select(p => p.Name + ":" + TypeName(p.PropertyType) + ":" + p.Attributes + ":" + string.Join(',', p.Parameters.Select(x => TypeName(x.ParameterType))) +
        ":get=" + (p.GetMethod?.FullName ?? "") + ":set=" + (p.SetMethod?.FullName ?? "") + ":other=" + string.Join(',', p.OtherMethods.Select(x => x.FullName)) + ":attrs=" + CustomAttributesFingerprint(p.CustomAttributes)));
    var events = string.Join(";", t.Events.Select(e => e.Name + ":" + TypeName(e.EventType) + ":" + e.Attributes + ":add=" + (e.AddMethod?.FullName ?? "") +
        ":remove=" + (e.RemoveMethod?.FullName ?? "") + ":raise=" + (e.InvokeMethod?.FullName ?? "") + ":other=" + string.Join(',', e.OtherMethods.Select(x => x.FullName)) + ":attrs=" + CustomAttributesFingerprint(e.CustomAttributes)));
    var interfaces = string.Join(";", t.Interfaces.Select(i => i.InterfaceType.FullName + ":attrs=" + CustomAttributesFingerprint(i.CustomAttributes)).OrderBy(x => x, StringComparer.Ordinal));
    // GetBlob preserves constructor enum/array/named-field/named-property data
    // without asking Cecil to resolve types through the desktop GAC.
    var attrs = CustomAttributesFingerprint(t.CustomAttributes);
    var generic = string.Join(";", t.GenericParameters.Select(g => g.Name + ":" + g.Attributes + ":" + string.Join(',', g.Constraints.Select(ConstraintFingerprint)) + ":attrs=" + CustomAttributesFingerprint(g.CustomAttributes)));
    var layout = t.PackingSize + ":" + t.ClassSize;
    var nested = string.Join(";", t.NestedTypes.Select(TypeApiFingerprint));
    return t.FullName + "|" + t.Attributes + "|layout=" + layout + "|generic=" + generic + "|" + (t.BaseType?.FullName ?? "") + "|" + interfaces + "|" + fields + "|" + methods + "|" + properties + "|" + events + "|" + attrs + "|nested=" + nested;
}
static string ResourceFingerprint(AssemblyDefinition a) => string.Join("\n", a.MainModule.Resources.Select(r => r.Name + ":" + r.ResourceType + ":" + (r is EmbeddedResource e ? Sha(ReadResource(e)) : "linked:" + ((LinkedResource)r).File)));
static byte[] ReadResource(EmbeddedResource r) { using var s = r.GetResourceStream(); using var m = new MemoryStream(); s.CopyTo(m); return m.ToArray(); }
static string StructureFingerprint(AssemblyDefinition a) => ShaText(a.Name.FullName + "|" + a.MainModule.Mvid + "|" +
    string.Join("\n", AllTypes(a.MainModule.Types).Select(TypeApiFingerprint)) + "|" +
    string.Join("\n", AllTypes(a.MainModule.Types).SelectMany(t => t.Methods).Select(MethodFingerprint)) + "|" + ResourceFingerprint(a) + "|" +
    string.Join("\n", a.MainModule.AssemblyReferences.Select(r => r.FullName)) + "|" +
    string.Join("\n", a.MainModule.ModuleReferences.Select(r => r.Name)) + "|" + CustomAttributesFingerprint(a.CustomAttributes) + "|" + CustomAttributesFingerprint(a.MainModule.CustomAttributes));
static string CanonicalExistingPath(string path) {
    var full = Path.GetFullPath(path);
    var drive = Path.GetPathRoot(full) ?? throw new InvalidDataException("Path has no root");
    var current = drive;
    foreach (var segment in full[drive.Length..].Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries)) {
        var next = Path.Combine(current, segment);
        FileSystemInfo info = Directory.Exists(next) ? new DirectoryInfo(next) : new FileInfo(next);
        current = info.LinkTarget is null ? next : info.ResolveLinkTarget(true)?.FullName ?? throw new InvalidDataException("Broken symlink in configured game path");
    }
    return Path.GetFullPath(current);
}
static bool IsWithin(string path, string parent) {
    var comparison = OperatingSystem.IsWindows() || OperatingSystem.IsMacOS() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
    var canonicalParent = Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
    var canonicalPath = Path.GetFullPath(path);
    return string.Equals(canonicalPath.TrimEnd(Path.DirectorySeparatorChar), canonicalParent.TrimEnd(Path.DirectorySeparatorChar), comparison) ||
        canonicalPath.StartsWith(canonicalParent, comparison);
}
static void RequireOutputUnderIgnoredWork(string output) {
    var dir = new DirectoryInfo(Path.GetDirectoryName(output)!);
    for (DirectoryInfo? d = dir; d is not null; d = d.Parent) Check((d.Attributes & FileAttributes.ReparsePoint) == 0, "Output path contains a symlink");
    Check(!File.Exists(output) && !Directory.Exists(output) && new FileInfo(output).LinkTarget is null, "Refusing to overwrite or follow output");
    var root = Directory.GetCurrentDirectory();
    var work = Path.GetFullPath(Path.Combine(root, "work")) + Path.DirectorySeparatorChar;
    Check(Path.GetFullPath(output).StartsWith(work, StringComparison.Ordinal), "Output must be beneath repository work/");
    var localConfig = Path.Combine(root, "work", "config", "local.json");
    Check(File.Exists(localConfig) && new FileInfo(localConfig).LinkTarget is null, "Required local config is unavailable");
    using var config = JsonDocument.Parse(File.ReadAllBytes(localConfig));
    var configured = Need(config.RootElement, "game_path");
    if (configured == "~") configured = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    else if (configured.StartsWith("~/", StringComparison.Ordinal)) configured = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), configured[2..]);
    var gameRoot = CanonicalExistingPath(configured);
    Check(!IsWithin(Path.GetFullPath(output), gameRoot), "Output path is inside the configured accepted game installation");
    var gitInfo = new System.Diagnostics.ProcessStartInfo("git") { WorkingDirectory = root, UseShellExecute = false };
    gitInfo.ArgumentList.Add("check-ignore"); gitInfo.ArgumentList.Add("--quiet"); gitInfo.ArgumentList.Add(output);
    using var git = System.Diagnostics.Process.Start(gitInfo);
    git!.WaitForExit(); Check(git.ExitCode == 0, "Output is not ignored by Git");
}

if (args.Length != 5 || (args[0] is not "--emit-incomplete-candidate" and not "--full-enable"
#if WWISE_TEST_ONLY
    and not "--synthetic-test" and not "--synthetic-corrupt-reopened-array-marshal" and not "--synthetic-corrupt-reopened-return-array-marshal"
#endif
    )) {
    Console.Error.WriteLine("usage: --emit-incomplete-candidate|--full-enable <assembly> <plan.json> <policy.json> <new-output.dll>"); return 2;
}
var mode = args[0]; var input = Path.GetFullPath(args[1]); var planPath = Path.GetFullPath(args[2]); var policyPath = Path.GetFullPath(args[3]); var output = Path.GetFullPath(args[4]);
var planBytes = File.ReadAllBytes(planPath); var policyBytes = File.ReadAllBytes(policyPath);
#if WWISE_TEST_ONLY
var syntheticTest = mode is "--synthetic-test" or "--synthetic-corrupt-reopened-array-marshal" or "--synthetic-corrupt-reopened-return-array-marshal";
#else
const bool syntheticTest = false;
#endif
if (!syntheticTest) {
Check(Sha(planBytes) == ReviewedPlanSha, "Generated plan is not the reviewed deterministic plan");
Check(Sha(policyBytes) == ReviewedPolicySha, "ABI policy differs from the reviewed exact profile");
}
using var planDoc = JsonDocument.Parse(planBytes); using var policyDoc = JsonDocument.Parse(policyBytes); var root = planDoc.RootElement; var policy = policyDoc.RootElement;
Check(root.GetProperty("schema").GetInt32() == 1, "Unsupported plan schema");
Check(root.GetProperty("full_enable_ready").GetBoolean() == false, "This draft cannot mark itself full-enable-ready");
Check(Sha(File.ReadAllBytes(input)) == Need(root, "input_assembly_sha256"), "Input assembly hash mismatch");
if (syntheticTest) Check(Need(policy, "profile") == "synthetic-test", "Test-only writer profile mismatch");
else {
Check(Sha(File.ReadAllBytes(input)) == ReviewedInputSha && Need(root, "input_assembly_sha256") == ReviewedInputSha, "Input differs from accepted retained ABI");
Check(Need(root, "android_source_sha256") == Need(policy, "official_android_declaration_source_sha256"), "Official Android declaration pin mismatch");
Check(Need(root, "native_plugin_sha256") == Need(policy, "android_arm64_release_plugin_sha256"), "Native plugin pin mismatch");
Check(Need(root, "native_export_set_sha256") == Need(policy, "android_arm64_export_set_sha256"), "Native export-set pin mismatch");
}
var unresolved = root.GetProperty("unavailable");
if (!syntheticTest && mode == "--full-enable") {
    Console.Error.WriteLine("Refusing full enable: " + unresolved.GetArrayLength() + " imports unavailable; Android initialization/platform path is unresolved");
    return 3;
}
RequireOutputUnderIgnoredWork(output);
var tempOutput = output + ".tmp-" + Guid.NewGuid().ToString("N") + ".dll";
using var removeTemporaryOutput = new DeletePathOnDispose(tempOutput);
using var assembly = AssemblyDefinition.ReadAssembly(input, new ReaderParameters { InMemory = true, ReadWrite = false });
var allTypes = AllTypes(assembly.MainModule.Types).ToArray();
var methods = allTypes.SelectMany(t => t.Methods).ToArray();
var imports = methods.Where(m => m.PInvokeInfo is not null).ToArray();
var originalName = assembly.Name.FullName; var originalMvid = assembly.MainModule.Mvid;
var identityRows = methods.Select(MethodFingerprint).ToArray();
var apiRows = allTypes.Select(TypeApiFingerprint).ToArray();
var sourceRows = root.GetProperty("imports").EnumerateArray().ToArray();
var unavailableRows = root.GetProperty("unavailable").EnumerateArray().ToArray();
var plannedSourceEntries = sourceRows.Select(x => Need(x, "source_entrypoint"))
    .Concat(unavailableRows.Select(x => Need(x, "entrypoint"))).ToHashSet(StringComparer.Ordinal);
var extraEntries = imports.Select(m => m.PInvokeInfo!.EntryPoint).Where(n => !plannedSourceEntries.Contains(n)).Distinct().ToArray();
var duplicateEntries = imports.GroupBy(m => m.PInvokeInfo!.EntryPoint).Where(g => g.Count() > 1).Select(g => g.Key + " x" + g.Count()).ToArray();
Check(imports.Length == root.GetProperty("counts").GetProperty("source_imports").GetInt32() && extraEntries.Length == 0,
    $"Input P/Invoke set differs from pinned source declarations: count={imports.Length}; extra=[{string.Join(',', extraEntries)}]; duplicate=[{string.Join(',', duplicateEntries)}]");
Check(duplicateEntries.Length == 0, "Input P/Invoke entrypoints are ambiguous: " + string.Join(',', duplicateEntries));
var originalByEntryPoint = imports.ToDictionary(m => m.PInvokeInfo!.EntryPoint, StringComparer.Ordinal);
Check(sourceRows.Length == root.GetProperty("counts").GetProperty("mapped_imports").GetInt32(), "Mapped import count mismatch");
var seen = new HashSet<MethodDefinition>();
var mappedIdentity = new Dictionary<string, (JsonElement Row, string SourceEntryPoint)>();
var targetIdentity = new Dictionary<string, (MethodDefinition Method, JsonElement Row)>();
foreach (var row in sourceRows) {
    var sourceName = Need(row, "source_entrypoint");
    Check(originalByEntryPoint.TryGetValue(sourceName, out var method), "Source entrypoint is absent in assembly: " + sourceName);
    Check(seen.Add(method!), "Plan references one method more than once");
    mappedIdentity.Add(method!.FullName, (row, sourceName));
    VerifyImport(method, row.GetProperty("game"), sourceName + " original");
    var changes = row.GetProperty("parameter_lpstr_indices").EnumerateArray().Select(x => x.GetInt32()).ToHashSet();
    foreach (var index in changes) {
        Check(index >= 0 && index < method.Parameters.Count, "Invalid LPStr parameter index: " + sourceName);
        Check(MarshalKind(method.Parameters[index].MarshalInfo) == "LPWStr", "Expected source LPWStr: " + sourceName);
        method.Parameters[index].MarshalInfo = new MarshalInfo(NativeType.LPStr);
    }
    method.PInvokeInfo.EntryPoint = Need(row, "target_entrypoint");
    targetIdentity.Add(method.FullName, (method, row));
}
foreach (var row in unavailableRows) {
    var sourceName = Need(row, "entrypoint");
    Check(originalByEntryPoint.TryGetValue(sourceName, out var method), "Unavailable source entrypoint is absent in assembly: " + sourceName);
    VerifyImport(method!, row.GetProperty("game"), sourceName + " unavailable original");
}
foreach (var item in targetIdentity.Values) {
    VerifyImport(item.Method, item.Row.GetProperty("android"), Need(item.Row, "target_entrypoint") + " Android contract");
}
var rewriteRows = root.GetProperty("managed_call_rewrites").EnumerateArray().ToArray();
var policyRewrites = policy.GetProperty("managed_call_rewrites").EnumerateArray().ToArray();
Check(rewriteRows.Length == 1 && policyRewrites.Length == 1, "Exactly one reviewed managed call rewrite is required");
var rewrite = rewriteRows[0];
var reviewedRewrite = policyRewrites[0];
foreach (var field in new[] { "assembly", "type", "method", "return_type", "expected_target", "replacement_target", "android_source", "reason" })
    Check(Need(rewrite, field) == Need(reviewedRewrite, field), "Managed call rewrite differs from policy: " + field);
Check((syntheticTest ? Need(rewrite, "assembly") == "ShapeFixture" : Need(rewrite, "assembly") == "AK.Wwise.Unity.API") &&
      Need(rewrite, "type") == "AkSoundEngine" &&
      Need(rewrite, "method") == "StringFromIntPtrOSString", "Unexpected managed rewrite target");
Check(Need(rewrite, "return_type") == "System.String" &&
      rewrite.GetProperty("parameter_types").EnumerateArray().Select(x => x.GetString()).SequenceEqual(new[] { "System.IntPtr" }) &&
      reviewedRewrite.GetProperty("parameter_types").EnumerateArray().Select(x => x.GetString()).SequenceEqual(new[] { "System.IntPtr" }),
      "Managed call rewrite signature differs from policy");
Check(rewrite.GetProperty("expected_instruction_count").GetInt32() == 3 &&
      reviewedRewrite.GetProperty("expected_instruction_count").GetInt32() == 3, "Managed rewrite instruction count differs from policy");
Check(Need(rewrite, "expected_target") == "System.String AkSoundEngine::StringFromIntPtrWString(System.IntPtr)" &&
      Need(rewrite, "replacement_target") == "System.String AkSoundEngine::StringFromIntPtrString(System.IntPtr)",
      "Managed rewrite call operands differ from reviewed Android OS-string contract");
Check(Need(root, "android_os_string_source_sha256") == Need(policy, "official_android_os_string_source_sha256"),
      "Official Android OS-string source pin mismatch");
Check(assembly.Name.Name == Need(rewrite, "assembly"), "Managed rewrite assembly identity mismatch");
var rewriteType = allTypes.Single(t => t.FullName == Need(rewrite, "type"));
var namedRewriteMethods = rewriteType.Methods.Where(m => m.Name == Need(rewrite, "method")).ToArray();
Check(namedRewriteMethods.Length == 1, "Managed rewrite method has unexpected overloads");
var rewriteMethod = namedRewriteMethods[0];
Check(rewriteMethod.IsStatic && rewriteMethod.ReturnType.FullName == Need(rewrite, "return_type") &&
      rewriteMethod.Parameters.Count == 1 && rewriteMethod.Parameters[0].ParameterType.FullName == "System.IntPtr",
      "Managed rewrite method signature differs from policy");
var expectedCall = Need(rewrite, "expected_target");
var replacementCall = Need(rewrite, "replacement_target");
Check(rewriteMethod.Body.Instructions.Count == rewrite.GetProperty("expected_instruction_count").GetInt32() &&
      rewriteMethod.Body.Instructions[0].OpCode == OpCodes.Ldarg_0 &&
      rewriteMethod.Body.Instructions[1].OpCode == OpCodes.Call &&
      rewriteMethod.Body.Instructions[1].Operand is MethodReference originalCall && originalCall.FullName == expectedCall &&
      rewriteMethod.Body.Instructions[2].OpCode == OpCodes.Ret,
      "Managed OS-string method signature/body/call operand differs from reviewed source contract");
var helper = rewriteType.Methods.Single(m => m.FullName == replacementCall);
Check(helper.IsStatic && helper.ReturnType.FullName == "System.String" && helper.Parameters.Count == 1 &&
      helper.Parameters[0].ParameterType.FullName == "System.IntPtr", "Replacement helper signature mismatch");
rewriteMethod.Body.Instructions[1].Operand = helper;
var expectedMethodRows = methods.Select(MethodFingerprint).ToArray();
var expectedStructure = StructureFingerprint(assembly);
Check(assembly.Name.FullName == originalName && assembly.MainModule.Mvid == originalMvid, "Assembly/type identity changed");
Check(methods.Length == identityRows.Length && methods.Select((m, i) => m == rewriteMethod || expectedMethodRows[i] == identityRows[i]).All(x => x),
      "Managed rewrite changed an unrelated method body or metadata");
assembly.Write(tempOutput);
Check(File.Exists(tempOutput), "Candidate temporary output was not written");
using var result = AssemblyDefinition.ReadAssembly(tempOutput, new ReaderParameters { InMemory = true, ReadWrite = false });
var outMethods = AllTypes(result.MainModule.Types).SelectMany(t => t.Methods).ToArray();
var outImports = outMethods.Where(m => m.PInvokeInfo is not null).ToArray();
#if WWISE_TEST_ONLY
if (mode == "--synthetic-corrupt-reopened-array-marshal") {
    var arrayParameter = outImports.SelectMany(m => m.Parameters)
        .First(p => p.MarshalInfo is ArrayMarshalInfo);
    var marshal = (ArrayMarshalInfo)arrayParameter.MarshalInfo!;
    marshal.Size += 1; // Keep NativeType.Array while simulating a lost/changed size contract.
}
if (mode == "--synthetic-corrupt-reopened-return-array-marshal") {
    var arrayReturn = outImports.Select(m => m.MethodReturnType)
        .First(r => r.MarshalInfo is ArrayMarshalInfo);
    var marshal = (ArrayMarshalInfo)arrayReturn.MarshalInfo!;
    marshal.Size += 1;
}
#endif
Check(outImports.Length == imports.Length, "Output P/Invoke count changed");
Check(result.Name.FullName == originalName && result.MainModule.Mvid == originalMvid, "Written assembly/type identity changed");
Check(StructureFingerprint(result) == expectedStructure, "Assembly contract differs from the one declared managed-call rewrite");
Check(AllTypes(result.MainModule.Types).Select(TypeApiFingerprint).SequenceEqual(apiRows), "Written assembly public/serialized type API changed");
Check(PInvokeMarshalFingerprint(outMethods) == PInvokeMarshalFingerprint(methods),
    "Written P/Invoke MarshalInfo metadata changed");
var outFingerprints = outMethods.Select(MethodFingerprint).ToArray();
if (!outFingerprints.SequenceEqual(expectedMethodRows)) {
    var diffs = expectedMethodRows.Zip(outFingerprints).Select((pair, index) => (pair, index)).Where(x => x.pair.First != x.pair.Second).Take(3)
        .Select(x => $"#{x.index} before={x.pair.First} after={x.pair.Second}");
    throw new InvalidDataException("Written assembly differs from declared ABI and managed-call rewrites: " + string.Join(" || ", diffs));
}
var persistedRewrite = outMethods.Single(m => m.FullName == rewriteMethod.FullName);
Check(persistedRewrite.FullName == rewriteMethod.FullName && persistedRewrite.Attributes == rewriteMethod.Attributes &&
      persistedRewrite.Body.Instructions.Count == 3 && persistedRewrite.Body.Instructions[1].Operand is MethodReference persistedCall &&
      persistedCall.FullName == replacementCall, "Declared managed-call rewrite did not persist with method identity intact");
foreach (var pair in mappedIdentity) {
    var found = outMethods.Where(m => m.FullName == pair.Key).ToArray();
    Check(found.Length == 1 && found[0].PInvokeInfo is not null, "Output method identity changed: " + pair.Key);
    VerifyImport(found[0], pair.Value.Row.GetProperty("android"), Need(pair.Value.Row, "target_entrypoint") + " persisted Android contract");
}
foreach (var row in unavailableRows) {
    var sourceName = Need(row, "entrypoint");
    var found = outImports.Where(m => m.PInvokeInfo!.EntryPoint == sourceName).ToArray();
    Check(found.Length == 1, "Unavailable entrypoint changed: " + sourceName);
    VerifyImport(found[0], row.GetProperty("game"), sourceName + " remains unavailable");
}
File.Move(tempOutput, output, false);
Console.WriteLine(JsonSerializer.Serialize(new { status = "draft_incomplete_android_candidate", input_sha256 = Need(root, "input_assembly_sha256"), output_sha256 = Sha(File.ReadAllBytes(output)), mapped = sourceRows.Length, unavailable = unresolved.GetArrayLength(), managed_call_rewrites = rewriteRows.Length, full_enable_ready = false }));
return 0;

sealed class DeletePathOnDispose(string path) : IDisposable {
    public void Dispose() { try { File.Delete(path); } catch { } }
}
