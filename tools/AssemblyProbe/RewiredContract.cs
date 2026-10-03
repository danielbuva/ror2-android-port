using Mono.Cecil;
using System.Security.Cryptography;
using System.Text.Json;

// Metadata only: no assembly loading, IL execution, resources or method bodies.
// Preserve full signatures and scopes: matching a name alone is insufficient.
static class RewiredContract
{
    static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types)
    {
        foreach (var type in types)
        {
            yield return type;
            foreach (var nested in Types(type.NestedTypes)) yield return nested;
        }
    }

    static string Scope(TypeReference type) => type.GetElementType().Scope?.ToString() ?? "";
    static bool Rewired(TypeReference type) => Scope(type).StartsWith("Rewired_");
    static string[] Attributes(ICustomAttributeProvider provider) => provider.CustomAttributes
        .Select(a => a.AttributeType.FullName).OrderBy(a => a).ToArray();
    static object Method(MethodDefinition method) => new
    {
        signature = method.FullName, attributes = method.Attributes.ToString(),
        genericArity = method.GenericParameters.Count,
        parameters = method.Parameters.Select(p => new { p.Name, type = p.ParameterType.FullName, attributes = p.Attributes.ToString() }),
        customAttributes = Attributes(method), overrides = method.Overrides.Select(m => m.FullName),
        pinvoke = method.HasPInvokeInfo ? new { module = method.PInvokeInfo.Module.Name, entry = method.PInvokeInfo.EntryPoint } : null
    };

    public static void Run(string[] args)
    {
        if (args.Length != 2) throw new ArgumentException("--rewired-contract <managed-directory> <output-json>");
        var directory = Path.GetFullPath(args[0]);
        var files = Directory.GetFiles(directory, "*.dll").OrderBy(p => p).ToArray();
        var assemblies = new List<object>();
        foreach (var file in files)
        {
            using var assembly = AssemblyDefinition.ReadAssembly(file);
            var module = assembly.MainModule;
            bool middleware = assembly.Name.Name.StartsWith("Rewired_");
            var types = Types(module.Types).ToArray();
            var members = module.GetMemberReferences().Where(m => Rewired(m.DeclaringType)).ToArray();
            var referencedTypes = module.GetTypeReferences().Where(Rewired).ToArray();
            if (!middleware && members.Length == 0 && referencedTypes.Length == 0) continue;
            assemblies.Add(new
            {
                file = Path.GetFileName(file), identity = assembly.Name.FullName,
                sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))).ToLowerInvariant(),
                middleware, runtime = module.RuntimeVersion, architecture = module.Architecture.ToString(),
                references = module.AssemblyReferences.Select(r => r.FullName),
                versionAttributes = assembly.CustomAttributes.Where(a => a.AttributeType.FullName is
                    "System.Reflection.AssemblyFileVersionAttribute" or "System.Reflection.AssemblyInformationalVersionAttribute")
                    .Select(a => new { type = a.AttributeType.FullName, value = a.ConstructorArguments.FirstOrDefault().Value?.ToString() }),
                consumedMembers = members.Select(m => new { signature = m.FullName, scope = Scope(m.DeclaringType), kind = m.GetType().Name }).Distinct(),
                consumedTypes = referencedTypes.Select(t => new { type = t.FullName, scope = Scope(t) }).Distinct(),
                consumerTypes = middleware ? Array.Empty<object>() : types.Where(t =>
                    (t.BaseType != null && Rewired(t.BaseType)) || t.Interfaces.Any(i => Rewired(i.InterfaceType)))
                    .Select(t => new { type = t.FullName, baseType = t.BaseType?.FullName,
                        interfaces = t.Interfaces.Select(i => i.InterfaceType.FullName),
                        methods = t.Methods.Select(Method) }).Cast<object>().ToArray(),
                definitions = middleware ? types.Select(t => new
                {
                    type = t.FullName, attributes = t.Attributes.ToString(), baseType = t.BaseType?.FullName,
                    interfaces = t.Interfaces.Select(i => i.InterfaceType.FullName), genericArity = t.GenericParameters.Count,
                    packing = t.PackingSize, classSize = t.ClassSize, customAttributes = Attributes(t),
                    fields = t.Fields.Select(f => new
                    {
                        signature = f.FullName, attributes = f.Attributes.ToString(), offset = f.Offset,
                        customAttributes = Attributes(f),
                        // Only enum values; never copy arbitrary middleware constants.
                        enumValue = t.IsEnum && f.HasConstant ? f.Constant : null
                    }),
                    methods = t.Methods.Select(Method),
                    properties = t.Properties.Select(p => new { signature = p.FullName, getter = p.GetMethod?.FullName, setter = p.SetMethod?.FullName }),
                    events = t.Events.Select(e => new { signature = e.FullName, add = e.AddMethod?.FullName, remove = e.RemoveMethod?.FullName })
                }).Cast<object>().ToArray() : Array.Empty<object>()
            });
        }
        var output = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        File.WriteAllText(output, JsonSerializer.Serialize(new
        {
            schema = 1, readOnly = true, scannedAssemblyCount = files.Length,
            scope = "Static referenced signatures, identities and metadata; not runtime, serialized migration or controller acceptance",
            assemblies
        }, new JsonSerializerOptions { WriteIndented = true }) + "\n");
        Console.WriteLine(JsonSerializer.Serialize(new { success = true, scanned = files.Length, relevant = assemblies.Count }));
    }
}
