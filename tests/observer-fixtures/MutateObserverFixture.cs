using Mono.Cecil;
using Mono.Cecil.Cil;

if (args.Length != 4) throw new Exception("mutator <input> <output> <mode> <reference-directory>");
using var resolver = new DefaultAssemblyResolver();
resolver.AddSearchDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(args[0]))!);
resolver.AddSearchDirectory(args[3]);
using var assembly = AssemblyDefinition.ReadAssembly(args[0], new ReaderParameters { AssemblyResolver = resolver });
var music = assembly.MainModule.GetType("RoR2.MusicController");
var awake = music.Methods.Single(m => m.Name == "Awake");
var destroy = music.Methods.Single(m => m.Name == "OnDestroy");
if (args[2] == "remove-add-dup")
{
    var record = awake.Body.Instructions.Single(i => i.Operand is MethodReference mr && mr.Name == "RecordMusicAddOutputReturned");
    if (record.Previous?.OpCode != OpCodes.Ldloc || record.Previous.Previous?.OpCode != OpCodes.Ldarg_0 ||
        record.Previous.Previous.Previous?.OpCode != OpCodes.Dup) throw new Exception("unexpected add observer shape");
    awake.Body.GetILProcessor().Remove(record.Previous.Previous.Previous);
}
else if (args[2] == "rename-add-observer")
{
    var record = awake.Body.Instructions.Single(i => i.Operand is MethodReference mr && mr.Name == "RecordMusicAddOutputReturned");
    var original = (MethodReference)record.Operand;
    record.Operand = new MethodReference("WrongMusicOutputObserver", original.ReturnType, original.DeclaringType)
    { HasThis = original.HasThis };
    foreach (var parameter in original.Parameters) ((MethodReference)record.Operand).Parameters.Add(new ParameterDefinition(parameter.ParameterType));
}
else if (args[2] == "remove-remove-observer")
{
    var record = destroy.Body.Instructions.Single(i => i.Operand is MethodReference mr && mr.Name == "RecordMusicRemoveOutputReturned");
    destroy.Body.GetILProcessor().Remove(record);
}
else if (args[2] == "change-exception-handler")
{
    var handler = assembly.MainModule.Types.SelectMany(AllTypes)
        .SelectMany(type => type.Methods)
        .Where(method => method.HasBody)
        .SelectMany(method => method.Body.ExceptionHandlers)
        .FirstOrDefault(item => item.TryStart != null && item.TryEnd != null && item.TryStart != item.TryEnd);
    if (handler == null) throw new Exception("fixture has no exception handler to mutate");
    handler.TryEnd = handler.TryStart;
}
else throw new Exception("unknown mutation");
assembly.Write(args[1]);

static IEnumerable<TypeDefinition> AllTypes(TypeDefinition type)
{
    yield return type;
    foreach (var nested in type.NestedTypes)
        foreach (var child in AllTypes(nested)) yield return child;
}
