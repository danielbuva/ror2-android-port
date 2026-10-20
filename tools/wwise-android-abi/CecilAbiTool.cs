using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

static string Sha(byte[] b) => Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();
static string TypeName(TypeReference t) => t switch {
    ByReferenceType x => TypeName(x.ElementType) + "&",
    PointerType x => TypeName(x.ElementType) + "*",
    ArrayType x when x.Rank == 1 && !x.IsVector => throw new InvalidDataException("Unsupported non-vector rank-one array metadata"),
    ArrayType x => TypeName(x.ElementType) + "[" + new string(',', x.Rank - 1) + "]" +
        (x.Dimensions.Any(d => d.LowerBound is not null || d.UpperBound is not null)
            ? "{" + string.Join(',', x.Dimensions.Select(d => (d.LowerBound?.ToString(CultureInfo.InvariantCulture) ?? "") + ".." + (d.UpperBound?.ToString(CultureInfo.InvariantCulture) ?? ""))) + "}" : ""),
    GenericInstanceType x => TypeName(x.ElementType) + "<" + string.Join(',', x.GenericArguments.Select(TypeName)) + ">",
    GenericParameter x => (x.Type == GenericParameterType.Method ? "!!" : "!") + x.Position,
    OptionalModifierType x => "modopt(" + TypeName(x.ModifierType) + ")" + TypeName(x.ElementType),
    RequiredModifierType x => "modreq(" + TypeName(x.ModifierType) + ")" + TypeName(x.ElementType),
    FunctionPointerType => throw new InvalidDataException("Unsupported function-pointer metadata"),
    _ => t.FullName switch {
        "System.Void"=>"void", "System.Boolean"=>"bool", "System.Byte"=>"byte", "System.SByte"=>"sbyte",
        "System.Int16"=>"short", "System.UInt16"=>"ushort", "System.Int32"=>"int", "System.UInt32"=>"uint",
        "System.Int64"=>"long", "System.UInt64"=>"ulong", "System.Single"=>"float", "System.Double"=>"double",
        "System.String"=>"string", "System.IntPtr"=>"IntPtr", "System.UIntPtr"=>"UIntPtr", _=>t.FullName.Replace('/', '.')
    }
};
static string Direction(ParameterDefinition p) => p.ParameterType is not ByReferenceType ? "value" :
    (p.Attributes & Mono.Cecil.ParameterAttributes.Out) != 0 && (p.Attributes & Mono.Cecil.ParameterAttributes.In) == 0 ? "out" :
    (p.Attributes & Mono.Cecil.ParameterAttributes.In) != 0 && (p.Attributes & Mono.Cecil.ParameterAttributes.Out) == 0 ? "in" : "ref";
static object? StableValue(object? v) => v switch {
    null => null, TypeReference t => TypeName(t), string s => s, bool b => b,
    IFormattable f => f.ToString(null, CultureInfo.InvariantCulture), _ => throw new InvalidDataException("Unknown metadata property type: " + v.GetType().FullName)
};
static object? MarshalContract(MarshalInfo? info) {
    if (info is null) return null;
    var kind = info.GetType().Name;
    var allowed = new HashSet<string>{"MarshalInfo","ArrayMarshalInfo","FixedArrayMarshalInfo","FixedSysStringMarshalInfo","SafeArrayMarshalInfo","CustomMarshalInfo","InterfaceMarshalInfo"};
    if (!allowed.Contains(kind)) throw new InvalidDataException("Unsupported MarshalInfo: " + kind);
    var properties = info.GetType().GetProperties(BindingFlags.Instance|BindingFlags.Public)
        .Where(p=>p.CanRead && p.GetIndexParameters().Length==0).OrderBy(p=>p.Name,StringComparer.Ordinal)
        .ToDictionary(p=>p.Name,p=>StableValue(p.GetValue(info)),StringComparer.Ordinal);
    return new { kind, properties };
}
static object Param(ParameterDefinition p) => new {
    name=p.Name, type=TypeName(p.ParameterType), direction=Direction(p),
    attributes=p.Attributes.ToString(), marshal=MarshalContract(p.MarshalInfo),
    customAttributes=p.CustomAttributes.Select(AttributeContract)
};
static object AttributeContract(CustomAttribute a) => new {
    type=a.AttributeType.FullName, constructor=a.Constructor.FullName,
    raw_blob_base64=Convert.ToBase64String(a.GetBlob())
};
static string CallingConvention(PInvokeAttributes a) => (a & PInvokeAttributes.CallConvMask) switch {
    PInvokeAttributes.CallConvWinapi=>"default",PInvokeAttributes.CallConvCdecl=>"Cdecl",PInvokeAttributes.CallConvStdCall=>"StdCall",
    PInvokeAttributes.CallConvThiscall=>"ThisCall",PInvokeAttributes.CallConvFastcall=>"FastCall",_=>throw new InvalidDataException("Unknown P/Invoke calling convention")};
static string Charset(PInvokeAttributes a) => (a & PInvokeAttributes.CharSetMask) switch {
    0=>"default",PInvokeAttributes.CharSetAnsi=>"Ansi",PInvokeAttributes.CharSetUnicode=>"Unicode",PInvokeAttributes.CharSetAuto=>"Auto",_=>throw new InvalidDataException("Unknown P/Invoke charset")};
static string BestFit(PInvokeAttributes a) => (a & PInvokeAttributes.BestFitMask) switch {
    0=>"default",PInvokeAttributes.BestFitEnabled=>"enabled",PInvokeAttributes.BestFitDisabled=>"disabled",_=>throw new InvalidDataException("Unknown BestFitMapping flags")};
static string ThrowOnUnmappable(PInvokeAttributes a) => (a & PInvokeAttributes.ThrowOnUnmappableCharMask) switch {
    0=>"default",PInvokeAttributes.ThrowOnUnmappableCharEnabled=>"enabled",PInvokeAttributes.ThrowOnUnmappableCharDisabled=>"disabled",_=>throw new InvalidDataException("Unknown ThrowOnUnmappableChar flags")};
static object Import(MethodDefinition m) {
    var p=m.PInvokeInfo ?? throw new InvalidDataException("Expected P/Invoke method");
    if (m.HasGenericParameters || m.HasBody || m.IsStatic == false) throw new InvalidDataException("Unsupported P/Invoke method shape: "+m.FullName);
    return new {
        method=m.FullName, entrypoint=p.EntryPoint, library=p.Module.Name, calling_convention=CallingConvention(p.Attributes), charset=Charset(p.Attributes),
        best_fit_mapping=BestFit(p.Attributes), throw_on_unmappable_char=ThrowOnUnmappable(p.Attributes), raw_pinvoke_flags=(int)p.Attributes,
        method_custom_attributes=m.CustomAttributes.Select(AttributeContract),
        exact_spelling=(p.Attributes&PInvokeAttributes.NoMangle)!=0,
        set_last_error=(p.Attributes&PInvokeAttributes.SupportsLastError)!=0,
        return_type=TypeName(m.ReturnType), return_marshal=MarshalContract(m.MethodReturnType.MarshalInfo),
        return_attributes=m.MethodReturnType.Attributes.ToString(), return_custom_attributes=m.MethodReturnType.CustomAttributes.Select(AttributeContract),
        parameters=m.Parameters.Select(Param)
    };
}

if (args.Length != 2 || args[0] != "--inspect-pinvoke") {
    Console.Error.WriteLine("usage: --inspect-pinvoke <managed-assembly.dll>"); return 2;
}
var input=Path.GetFullPath(args[1]);
using var assembly=AssemblyDefinition.ReadAssembly(input,new ReaderParameters{InMemory=true,ReadWrite=false});
var imports=AllTypes(assembly.MainModule.Types).SelectMany(t=>t.Methods).Where(m=>m.PInvokeInfo is not null).Select(Import).ToArray();
Console.WriteLine(JsonSerializer.Serialize(new {schema=1,assembly=assembly.Name.FullName,mvid=assembly.MainModule.Mvid,sha256=Sha(File.ReadAllBytes(input)),imports},new JsonSerializerOptions{WriteIndented=true}));
return 0;

static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> types) {
    foreach(var t in types){yield return t;foreach(var n in AllTypes(t.NestedTypes))yield return n;}
}
