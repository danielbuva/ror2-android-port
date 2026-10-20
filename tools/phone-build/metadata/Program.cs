using Mono.Cecil;
using System.Security.Cryptography;
using System.Text.Json;

// Metadata only: never loads or executes the inspected assemblies.
if (args.Length != 2) throw new ArgumentException("Expected INPUT.json NEW_OUTPUT.json");
using var input = JsonDocument.Parse(File.ReadAllText(args[0]));
string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> values)
{
    foreach (var type in values)
    {
        yield return type;
        foreach (var child in Types(type.NestedTypes)) yield return child;
    }
}
object Argument(CustomAttributeArgument argument) => new
{
    type = argument.Type.FullName,
    value = argument.Value?.ToString()
};
var assemblies = new List<object>();
var seen = new HashSet<string>(StringComparer.Ordinal);
foreach (var row in input.RootElement.GetProperty("assemblies").EnumerateArray())
{
    string group = row.GetProperty("group").GetString()!;
    string path = Path.GetFullPath(row.GetProperty("path").GetString()!);
    if (!seen.Add(group + "\n" + path)) throw new InvalidOperationException("Duplicate metadata input");
    string before = Hash(path);
    using var resolver = new DefaultAssemblyResolver();
    resolver.AddSearchDirectory(Path.GetDirectoryName(path)!);
    using var assembly = AssemblyDefinition.ReadAssembly(path, new ReaderParameters { AssemblyResolver = resolver, ReadSymbols = false });
    var types = Types(assembly.MainModule.Types).Select(type => new
    {
        name = type.FullName,
        base_type = type.BaseType?.FullName,
        native_attributes = type.CustomAttributes.Where(attribute =>
            attribute.AttributeType.Name == "NativeClassAttribute" || attribute.AttributeType.Name == "NativeTypeAttribute")
            .Select(attribute => new
            {
                name = attribute.AttributeType.FullName,
                arguments = attribute.ConstructorArguments.Select(Argument).ToArray(),
                fields = attribute.Fields.Select(field => new { name = field.Name, argument = Argument(field.Argument) }).ToArray(),
                properties = attribute.Properties.Select(property => new { name = property.Name, argument = Argument(property.Argument) }).ToArray()
            }).ToArray()
    }).ToArray();
    if (Hash(path) != before) throw new InvalidOperationException("SDK metadata input changed during inspection");
    assemblies.Add(new { group, path, sha256 = before, assembly = assembly.Name.Name, types });
}
using var output = new FileStream(args[1], FileMode.CreateNew, FileAccess.Write);
JsonSerializer.Serialize(output, new { schema = 1, executes_inputs = false, assemblies }, new JsonSerializerOptions { WriteIndented = true });
