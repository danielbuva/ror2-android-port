using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;

// Read-only metadata attribution. Never loads or runs the inspected game assembly.
var resolver = new DefaultAssemblyResolver();
resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(args[0]))!);
using var assembly = AssemblyDefinition.ReadAssembly(args[0], new ReaderParameters { AssemblyResolver = resolver });
IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> ts) {
    foreach (var t in ts) { yield return t; foreach (var n in Types(t.NestedTypes)) yield return n; }
}
string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
string Operand(object? x) => x switch {
    null => "", Instruction i => "offset:" + i.Offset,
    Instruction[] many => string.Join(",", many.Select(i => i.Offset)),
    MemberReference member => member.FullName, ParameterDefinition p => "parameter:" + p.Index,
    VariableDefinition v => "variable:" + v.Index, _ => x.ToString() ?? ""
};
var filter = args.Skip(1).ToHashSet();
var types = Types(assembly.MainModule.Types).ToArray();
var report = new {
    input = Path.GetFullPath(args[0]), sha256 = Hash(File.ReadAllBytes(args[0])),
    name = assembly.Name.FullName, references = assembly.MainModule.AssemblyReferences.Select(r => r.FullName),
    typeCount = types.Length,
    runtimeInitializers = types.SelectMany(t => t.Methods).Where(m => m.CustomAttributes.Any(a => a.AttributeType.Name == "RuntimeInitializeOnLoadMethodAttribute")).Select(m => m.FullName),
    types = types.Where(t => filter.Count == 0 || filter.Contains(t.FullName)).Select(t => new {
        name = t.FullName, baseType = t.BaseType?.FullName, attributes = t.Attributes.ToString(),
        fields = t.Fields.Select(f => new { name = f.Name, type = f.FieldType.FullName, constant = f.HasConstant ? f.Constant : null }),
        methods = t.Methods.Select(m => new {
            name = m.FullName, token = m.MetadataToken.ToInt32(), attributes = m.Attributes.ToString(),
            overrides = m.Overrides.Select(o => o.FullName),
            body = m.HasBody ? m.Body.Instructions.Select(i => i.OpCode.Name + " " + Operand(i.Operand)).ToArray() : Array.Empty<string>()
        }),
        duplicateExplicitOverrides = t.Methods.SelectMany(m => m.Overrides.Select(o => new { target = o.FullName, body = m.FullName })).GroupBy(x => x.target).Where(g => g.Select(x => x.body).Distinct().Count() > 1).Select(g => new { target = g.Key, bodies = g.Select(x => x.body) })
    })
};
Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
