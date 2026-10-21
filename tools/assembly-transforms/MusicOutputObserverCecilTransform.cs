using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class MusicOutputObserverCecilTransform
{
    private const string ExpectedInputSha = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc";
    private const string ObserverTypeName = "OriginalOwnerProbeObserver.Observer";
    private const string ObserverAssemblyName = "OriginalOwnerProbeObserver";

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 3 && args[0] == "verify-shape")
            {
                using var candidate = AssemblyDefinition.ReadAssembly(args[1]);
                var music = FindType(candidate.MainModule, "RoR2.MusicController");
                VerifyShape(candidate.MainModule, FindMethod(music, "Awake"), FindMethod(music, "OnDestroy"), args[2]);
                Console.WriteLine("Music output observer structural/stack shape passed");
                return 0;
            }
            if (args.Length == 4 && args[0] == "verify-output")
            {
                VerifyPair(args[1], args[2], args[3]);
                Console.WriteLine("Music output observer structure, metadata, methods and exception tables passed");
                return 0;
            }
            if (args.Length < 5 || args[0] != "transform")
                throw new InvalidOperationException("usage: transform <exact-6f96-RoR2.dll> <OriginalOwnerProbeObserver.dll> <explicit-reference-directory> <new-output.dll> | verify-shape <output.dll> <observer-assembly-name> | verify-output <exact-6f96-RoR2.dll> <candidate.dll> <observer-assembly-full-identity>");
            Transform(args[1], args[2], args[3], args[4], args.Skip(5));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 2;
        }
    }

    internal static void Transform(string inputPath, string corePath, string referenceDirectory, string outputPath, IEnumerable<string> extraSearchDirectories)
    {
        Require(Hash(inputPath) == ExpectedInputSha, "music output observer requires the exact 6f96 composed game input");
        Require(!String.Equals(Path.GetFullPath(inputPath), Path.GetFullPath(outputPath), StringComparison.Ordinal),
            "output must be a new file");
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        using var observer = AssemblyDefinition.ReadAssembly(corePath);
        Require(observer.Name.Name == ObserverAssemblyName, "unexpected owner observer assembly identity");
        var observerType = FindType(observer.MainModule, ObserverTypeName);
        var recordAdd = FindMethod(observerType, "RecordMusicAddOutputReturned", "System.Int32", "System.Object", "System.UInt64");
        var recordRemove = FindMethod(observerType, "RecordMusicRemoveOutputReturned", "System.Int32", "System.Object", "System.UInt64");

        using var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(inputPath))!);
        resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(corePath))!);
        Require(Directory.Exists(referenceDirectory), "explicit assembly reference directory is unavailable");
        resolver.AddSearchDirectory(Path.GetFullPath(referenceDirectory));
        foreach (var directory in extraSearchDirectories)
            if (Directory.Exists(directory)) resolver.AddSearchDirectory(Path.GetFullPath(directory));
        using var game = AssemblyDefinition.ReadAssembly(inputPath, new ReaderParameters { AssemblyResolver = resolver });
        var moduleBefore = ModuleFingerprint(game.MainModule);
        var referencesBefore = game.MainModule.AssemblyReferences.Select(r => r.FullName).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var music = FindType(game.MainModule, "RoR2.MusicController");
        var awake = FindMethod(music, "Awake");
        var destroy = FindMethod(music, "OnDestroy");
        Require(awake.ReturnType.FullName == "System.Void" && awake.Parameters.Count == 0 &&
                destroy.ReturnType.FullName == "System.Void" && destroy.Parameters.Count == 0,
            "MusicController lifecycle signatures changed");
        VerifyAddSite(awake, out var addCall, out var addOutputLocal, out var musicOutputIdField);
        VerifyRemoveSite(destroy, out var removeCall, out var removeOutputIdField);
        Require(musicOutputIdField.FullName == removeOutputIdField.FullName,
            "AddOutput success field and RemoveOutput argument differ");

        var observerReferences = game.MainModule.AssemblyReferences.Where(r => r.Name == observer.Name.Name).ToArray();
        Require(observerReferences.Length <= 1, "6f96 input has ambiguous owner observer references");
        var observerAssemblyRef = observerReferences.Length == 1 ? observerReferences[0] : null;
        Require(observerAssemblyRef == null || observerAssemblyRef.FullName == observer.Name.FullName,
            "6f96 input references a different owner observer assembly identity");
        if (observerAssemblyRef == null)
        {
            observerAssemblyRef = new AssemblyNameReference(observer.Name.Name, observer.Name.Version)
            {
                Culture = observer.Name.Culture,
                PublicKeyToken = observer.Name.PublicKeyToken,
                HasPublicKey = observer.Name.HasPublicKey,
                Attributes = observer.Name.Attributes
            };
            game.MainModule.AssemblyReferences.Add(observerAssemblyRef);
        }
        var observerTypeRef = new TypeReference("OriginalOwnerProbeObserver", "Observer",
            game.MainModule, observerAssemblyRef);
        var importedAdd = MakeObserverReference(game.MainModule, observerTypeRef, recordAdd);
        var importedRemove = MakeObserverReference(game.MainModule, observerTypeRef, recordRemove);
        InsertAddObserver(awake, addCall, addOutputLocal, importedAdd);
        InsertRemoveObserver(destroy, removeCall, removeOutputIdField, importedRemove);
        game.Write(outputPath);

        VerifyPair(inputPath, outputPath, observer.Name.FullName);
        Console.WriteLine("MusicController AddOutput/RemoveOutput observer verified; output sha256=" + Hash(outputPath));
    }

    internal static void VerifyPair(string inputPath, string outputPath, string observerAssemblyIdentity)
    {
        Require(Hash(inputPath) == ExpectedInputSha, "full comparison requires the exact 6f96 composed game input");
        using var baseline = AssemblyDefinition.ReadAssembly(inputPath);
        using var result = AssemblyDefinition.ReadAssembly(outputPath);
        var before = AllMethods(baseline.MainModule).ToDictionary(MethodKey, StringComparer.Ordinal);
        var moduleBefore = ModuleFingerprint(baseline.MainModule);
        var referencesBefore = baseline.MainModule.AssemblyReferences.Select(r => r.FullName).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        VerifyOutput(result, before, moduleBefore, referencesBefore, observerAssemblyIdentity);
    }

    internal static void VerifyOutput(AssemblyDefinition result, Dictionary<string, MethodDefinition> before,
        string moduleBefore, string[] referencesBefore, string observerAssemblyIdentity)
    {
        var music = FindType(result.MainModule, "RoR2.MusicController");
        var awake = FindMethod(music, "Awake");
        var destroy = FindMethod(music, "OnDestroy");
        var observerAssemblyName = new AssemblyNameReference(observerAssemblyIdentity.Split(',')[0], new Version(0, 0, 0, 0));
        VerifyShape(result.MainModule, awake, destroy, observerAssemblyName.Name);
        Require(ModuleFingerprint(result.MainModule) == moduleBefore,
            "module/type/member/layout/resource metadata changed outside the allowed observer reference and method-body edits");
        var expectedReferences = referencesBefore.Contains(observerAssemblyIdentity, StringComparer.Ordinal)
            ? referencesBefore
            : referencesBefore.Append(observerAssemblyIdentity).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var actualReferences = result.MainModule.AssemblyReferences.Select(r => r.FullName).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        Require(actualReferences.SequenceEqual(expectedReferences, StringComparer.Ordinal),
            "assembly references changed outside the single exact observer identity addition");
        var after = AllMethods(result.MainModule).ToDictionary(MethodKey, StringComparer.Ordinal);
        Require(before.Count == after.Count, "method inventory changed");
        foreach (var pair in before)
        {
            if (pair.Key == MethodKey(awake))
            {
                var candidate = after[pair.Key];
                Require(MethodFingerprintIgnoringObserver(candidate) == MethodFingerprintIgnoringObserver(pair.Value),
                    "Awake metadata, IL or exception handlers changed outside the return-site observer sequence");
                Require(candidate.Body.MaxStackSize == Math.Max(pair.Value.Body.MaxStackSize, 4),
                    "Awake max stack changed outside the exact observer requirement");
            }
            else if (pair.Key == MethodKey(destroy))
            {
                var candidate = after[pair.Key];
                Require(MethodFingerprintIgnoringObserver(candidate) == MethodFingerprintIgnoringObserver(pair.Value),
                    "OnDestroy metadata, IL or exception handlers changed outside the return-site observer sequence");
                Require(candidate.Body.MaxStackSize == Math.Max(pair.Value.Body.MaxStackSize, 4),
                    "OnDestroy max stack changed outside the exact observer requirement");
            }
            else
                Require(after.TryGetValue(pair.Key, out var actual) && MethodFingerprint(actual) == MethodFingerprint(pair.Value),
                    "unrelated method metadata, IL or exception handlers changed: " + pair.Key);
        }
        Require(result.MainModule.AssemblyReferences.Count(r => r.FullName == observerAssemblyIdentity) == 1,
            "exact owner observer reference count or identity changed");
    }

    private static MethodReference MakeObserverReference(ModuleDefinition module, TypeReference declaringType, MethodDefinition source)
    {
        var method = new MethodReference(source.Name, module.TypeSystem.Void, declaringType) { HasThis = false };
        method.Parameters.Add(new ParameterDefinition(module.TypeSystem.Int32));
        method.Parameters.Add(new ParameterDefinition(module.TypeSystem.Object));
        method.Parameters.Add(new ParameterDefinition(module.TypeSystem.UInt64));
        return method;
    }

    internal static void VerifyShape(ModuleDefinition module, MethodDefinition awake, MethodDefinition destroy, string coreAssemblyName)
    {
        VerifyAddObserver(awake);
        VerifyRemoveObserver(destroy);
        Require(awake.Body.MaxStackSize >= 4 && destroy.Body.MaxStackSize >= 4,
            "instrumented return-site stack maximum is too small");
        Require(module.AssemblyReferences.Count(r => r.Name == coreAssemblyName) == 1,
            "exact owner observer reference must remain unique");
    }

    private static void VerifyAddSite(MethodDefinition method, out Instruction call, out VariableDefinition outputId, out FieldReference outputField)
    {
        var calls = method.Body.Instructions.Where(i => IsCall(i, "AkSoundEngine", "AddOutput",
            "AKRESULT", "AkOutputSettings", "System.UInt64&", "System.UInt64[]", "System.UInt32")).ToArray();
        Require(calls.Length == 1, "expected exactly one original AddOutput overload");
        var addCall = calls[0];
        call = addCall;
        Require(call.Next?.OpCode == OpCodes.Ldc_I4_1 && call.Next.Next?.OpCode == OpCodes.Bne_Un_S,
            "AddOutput result must feed the original AK_Success equality branch");
        var localLoads = method.Body.Instructions.TakeWhile(i => !ReferenceEquals(i, addCall))
            .Where(i => i.OpCode == OpCodes.Ldloc || i.OpCode == OpCodes.Ldloc_S || i.OpCode == OpCodes.Ldloc_0 ||
                i.OpCode == OpCodes.Ldloc_1 || i.OpCode == OpCodes.Ldloc_2 || i.OpCode == OpCodes.Ldloc_3)
            .ToArray();
        var stfld = method.Body.Instructions.Single(i => i.OpCode == OpCodes.Stfld && i.Operand is FieldReference f &&
            f.DeclaringType.FullName == "RoR2.MusicController" && f.Name == "musicListenerId");
        Require(stfld.Previous?.OpCode == OpCodes.Ldloc_2, "AddOutput out device id local changed");
        outputId = method.Body.Variables.Single(v => v.Index == 2 && v.VariableType.FullName == "System.UInt64");
        outputField = (FieldReference)stfld.Operand;
        Require(localLoads.Length > 0, "source AddOutput argument locals are missing");
    }

    private static void VerifyRemoveSite(MethodDefinition method, out Instruction call, out FieldReference outputField)
    {
        var calls = method.Body.Instructions.Where(i => IsCall(i, "AkSoundEngine", "RemoveOutput",
            "AKRESULT", "System.UInt64")).ToArray();
        Require(calls.Length == 1, "expected exactly one original RemoveOutput overload");
        call = calls[0];
        Require(call.Previous?.OpCode == OpCodes.Ldfld && call.Previous.Operand is FieldReference field &&
                field.DeclaringType.FullName == "RoR2.MusicController" && field.Name == "musicListenerId" &&
                call.Previous.Previous?.OpCode == OpCodes.Ldarg_0 && call.Next?.OpCode == OpCodes.Pop,
            "RemoveOutput must retain the original musicListenerId argument and discarded-result shape");
        outputField = (FieldReference)call.Previous.Operand;
    }

    private static void InsertAddObserver(MethodDefinition method, Instruction call, VariableDefinition outputId, MethodReference observer)
    {
        var il = method.Body.GetILProcessor();
        var injected = new[] {
            il.Create(OpCodes.Dup),
            il.Create(OpCodes.Ldarg_0),
            il.Create(OpCodes.Ldloc, outputId),
            il.Create(OpCodes.Call, observer)
        };
        InsertAfter(method, call, injected);
        if (method.Body.MaxStackSize < 4) method.Body.MaxStackSize = 4;
    }

    private static void InsertRemoveObserver(MethodDefinition method, Instruction call, FieldReference outputId, MethodReference observer)
    {
        var il = method.Body.GetILProcessor();
        var injected = new[] {
            il.Create(OpCodes.Dup),
            il.Create(OpCodes.Conv_I4),
            il.Create(OpCodes.Ldarg_0),
            il.Create(OpCodes.Ldarg_0),
            il.Create(OpCodes.Ldfld, outputId),
            il.Create(OpCodes.Call, observer)
        };
        InsertAfter(method, call, injected);
        if (method.Body.MaxStackSize < 4) method.Body.MaxStackSize = 4;
    }

    private static void VerifyAddObserver(MethodDefinition method)
    {
        var call = method.Body.Instructions.Single(i => IsCall(i, "AkSoundEngine", "AddOutput"));
        var seq = new[] { call.Next, call.Next?.Next, call.Next?.Next?.Next, call.Next?.Next?.Next?.Next };
        Require(seq[0]?.OpCode == OpCodes.Dup && seq[1]?.OpCode == OpCodes.Ldarg_0 &&
                seq[2]?.OpCode == OpCodes.Ldloc && ((VariableDefinition)seq[2]!.Operand).Index == 2 &&
                IsObserverCall(seq[3], "RecordMusicAddOutputReturned"),
            "AddOutput observer sequence is not stack-neutral at the original result branch");
        Require(seq[3]!.Next?.OpCode == OpCodes.Ldc_I4_1 && seq[3]!.Next.Next?.OpCode == OpCodes.Bne_Un_S,
            "original AddOutput result branch moved or changed");
        Require(method.Body.Instructions.Count(i => IsCall(i, "AkSoundEngine", "AddOutput")) == 1,
            "AddOutput call count changed");
    }

    private static void VerifyRemoveObserver(MethodDefinition method)
    {
        var call = method.Body.Instructions.Single(i => IsCall(i, "AkSoundEngine", "RemoveOutput"));
        var seq = new[] { call.Next, call.Next?.Next, call.Next?.Next?.Next, call.Next?.Next?.Next?.Next,
            call.Next?.Next?.Next?.Next?.Next, call.Next?.Next?.Next?.Next?.Next?.Next, call.Next?.Next?.Next?.Next?.Next?.Next?.Next };
        Require(seq[0]?.OpCode == OpCodes.Dup && seq[1]?.OpCode == OpCodes.Conv_I4 && seq[2]?.OpCode == OpCodes.Ldarg_0 &&
                seq[3]?.OpCode == OpCodes.Ldarg_0 && seq[4]?.OpCode == OpCodes.Ldfld &&
                ((FieldReference)seq[4]!.Operand).Name == "musicListenerId" &&
                IsObserverCall(seq[5], "RecordMusicRemoveOutputReturned") && seq[6]?.OpCode == OpCodes.Pop,
            "RemoveOutput observer sequence must leave the original discarded result intact");
        Require(method.Body.Instructions.Count(i => IsCall(i, "AkSoundEngine", "RemoveOutput")) == 1,
            "RemoveOutput call count changed");
    }

    private static void InsertAfter(MethodDefinition method, Instruction after, Instruction[] inserted)
    {
        var il = method.Body.GetILProcessor();
        var cursor = after;
        foreach (var instruction in inserted) { il.InsertAfter(cursor, instruction); cursor = instruction; }
    }

    private static IEnumerable<MethodDefinition> AllMethods(ModuleDefinition module) =>
        AllTypes(module.Types).SelectMany(t => t.Methods);
    private static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> types)
    {
        foreach (var type in types) { yield return type; foreach (var nested in AllTypes(type.NestedTypes)) yield return nested; }
    }
    private static string MethodKey(MethodDefinition method) => method.FullName;
    private static string MethodFingerprintIgnoringObserver(MethodDefinition method)
    {
        var removed = new HashSet<Instruction>();
        foreach (var call in method.Body.Instructions.Where(i => IsObserverCall(i, "RecordMusicAddOutputReturned") ||
                     IsObserverCall(i, "RecordMusicRemoveOutputReturned")))
        {
            removed.Add(call);
            int preceding = ((MethodReference)call.Operand).Name == "RecordMusicAddOutputReturned" ? 3 : 5;
            var cursor = call.Previous;
            for (int i = 0; i < preceding; i++)
            {
                Require(cursor != null, "truncated injected observer sequence");
                removed.Add(cursor);
                cursor = cursor.Previous;
            }
        }
        var filtered = method.Body.Instructions.Where(i => !removed.Contains(i)).ToArray();
        string Operand(object? value) => value switch {
            Instruction target => "target:" + Array.IndexOf(filtered, target),
            Instruction[] targets => "targets:" + string.Join(',', targets.Select(t => Array.IndexOf(filtered, t))),
            MethodReference mr => "method:" + mr.FullName,
            FieldReference fr => "field:" + fr.FullName,
            TypeReference tr => "type:" + tr.FullName,
            VariableDefinition v => "var:" + v.Index + ":" + v.VariableType.FullName,
            ParameterDefinition p => "param:" + p.Index + ":" + p.ParameterType.FullName,
            null => "", _ => value.ToString() ?? ""
        };
        return MethodHeaderFingerprint(method) + "\n" + BodyFingerprint(method, filtered, Operand, includeMaxStack: false) +
            "\nEH:" + ExceptionHandlerFingerprint(method, filtered);
    }

    private static string MethodFingerprint(MethodDefinition method)
    {
        if (!method.HasBody) return MethodHeaderFingerprint(method) + "\nno-body";
        var instructions = method.Body.Instructions.ToArray();
        string Operand(object? value) => value switch {
            Instruction target => "target:" + Array.IndexOf(instructions, target),
            Instruction[] targets => "targets:" + string.Join(',', targets.Select(t => Array.IndexOf(instructions, t))),
            MethodReference mr => "method:" + mr.FullName,
            FieldReference fr => "field:" + fr.FullName,
            TypeReference tr => "type:" + tr.FullName,
            VariableDefinition v => "var:" + v.Index + ":" + v.VariableType.FullName,
            ParameterDefinition p => "param:" + p.Index + ":" + p.ParameterType.FullName,
            null => "", _ => value.ToString() ?? ""
        };
        return MethodHeaderFingerprint(method) + "\n" + BodyFingerprint(method, instructions, Operand, includeMaxStack: true) +
            "\nEH:" + ExceptionHandlerFingerprint(method, instructions);
    }

    private static string BodyFingerprint(MethodDefinition method, Instruction[] instructions, Func<object?, string> operand,
        bool includeMaxStack)
    {
        return string.Join("\n", instructions.Select(i => i.OpCode.Name + "|" + operand(i.Operand))) +
            (includeMaxStack ? "\nmaxstack:" + method.Body.MaxStackSize : "") +
            "\ninitlocals:" + method.Body.InitLocals +
            "\nlocals:" + string.Join(";", method.Body.Variables.Select(v => v.Index + ":" + v.VariableType.FullName + ":" + v.IsPinned));
    }

    private static string MethodHeaderFingerprint(MethodDefinition method) => string.Join("|", new[] {
        method.FullName, ((int)method.Attributes).ToString(), ((int)method.ImplAttributes).ToString(),
        ((int)method.CallingConvention).ToString(), method.HasThis.ToString(), method.ExplicitThis.ToString(),
        method.IsPInvokeImpl.ToString(), method.PInvokeInfo?.Module?.Name ?? "", method.PInvokeInfo?.EntryPoint ?? "",
        method.PInvokeInfo == null ? "" : ((int)method.PInvokeInfo.Attributes).ToString(),
        AttributesFingerprint(method.CustomAttributes), AttributesFingerprint(method.MethodReturnType.CustomAttributes),
        string.Join(";", method.Parameters.Select(p => string.Join(":", p.Name, p.ParameterType.FullName,
            (int)p.Attributes, p.HasConstant ? p.Constant?.ToString() ?? "null" : "no-constant",
            p.HasMarshalInfo ? p.MarshalInfo.NativeType.ToString() : "no-marshal", AttributesFingerprint(p.CustomAttributes)))),
        string.Join(";", method.GenericParameters.Select(g => g.Name + ":" + (int)g.Attributes + ":" +
            string.Join(",", g.Constraints.Select(c => c.ConstraintType.FullName).OrderBy(x => x, StringComparer.Ordinal)) + ":" +
            AttributesFingerprint(g.CustomAttributes)))
    });

    private static string AttributesFingerprint(IEnumerable<CustomAttribute> values) =>
        string.Join(";", values.Select(a => a.Constructor.FullName + ":" + Convert.ToHexString(a.GetBlob()))
            .OrderBy(x => x, StringComparer.Ordinal));

    private static string ExceptionHandlerFingerprint(MethodDefinition method, Instruction[] instructions)
    {
        var positions = instructions.Select((instruction, index) => (instruction, index))
            .ToDictionary(x => x.instruction, x => x.index);
        string Boundary(Instruction? instruction) => instruction == null ? "end" :
            positions.TryGetValue(instruction, out int index) ? index.ToString() : "outside-filtered-body";
        return string.Join(";", method.Body.ExceptionHandlers.Select(h => string.Join(":", new[] {
            ((int)h.HandlerType).ToString(), h.CatchType?.FullName ?? "", Boundary(h.TryStart), Boundary(h.TryEnd),
            Boundary(h.HandlerStart), Boundary(h.HandlerEnd), Boundary(h.FilterStart)
        })));
    }

    private static string ModuleFingerprint(ModuleDefinition module)
    {
        var types = AllTypes(module.Types).Select(t => string.Join("\n", new[] {
            "TYPE:" + t.FullName + ":" + (int)t.Attributes + ":" + (t.BaseType?.FullName ?? "") + ":" +
                t.IsBeforeFieldInit + ":" + t.IsSealed + ":" + t.IsAbstract + ":" + t.IsSequentialLayout + ":" +
                t.IsExplicitLayout + ":" + t.ClassSize + ":" + t.PackingSize + ":" + AttributesFingerprint(t.CustomAttributes),
            "INTERFACES:" + string.Join(";", t.Interfaces.Select(i => i.InterfaceType.FullName).OrderBy(x => x, StringComparer.Ordinal)),
            "GENERICS:" + string.Join(";", t.GenericParameters.Select(g => g.Name + ":" + (int)g.Attributes + ":" +
                string.Join(",", g.Constraints.Select(c => c.ConstraintType.FullName).OrderBy(x => x, StringComparer.Ordinal)))),
            "FIELDS:" + string.Join(";", t.Fields.Select(f => string.Join(":", f.Name, f.FieldType.FullName, (int)f.Attributes,
                f.Offset, f.HasConstant ? f.Constant?.ToString() ?? "null" : "no-constant",
                f.HasMarshalInfo ? f.MarshalInfo.NativeType.ToString() : "no-marshal",
                (f.Attributes & FieldAttributes.HasFieldRVA) != 0 ? Convert.ToHexString(f.InitialValue) : "no-rva-data",
                AttributesFingerprint(f.CustomAttributes)))
                .OrderBy(x => x, StringComparer.Ordinal)),
            "PROPERTIES:" + string.Join(";", t.Properties.Select(p => p.FullName + ":" + (int)p.Attributes + ":" +
                (p.GetMethod?.FullName ?? "") + ":" + (p.SetMethod?.FullName ?? "") + ":" + AttributesFingerprint(p.CustomAttributes))
                .OrderBy(x => x, StringComparer.Ordinal)),
            "EVENTS:" + string.Join(";", t.Events.Select(e => e.FullName + ":" + (int)e.Attributes + ":" +
                (e.AddMethod?.FullName ?? "") + ":" + (e.RemoveMethod?.FullName ?? "") + ":" + (e.InvokeMethod?.FullName ?? "") + ":" + AttributesFingerprint(e.CustomAttributes))
                .OrderBy(x => x, StringComparer.Ordinal))
        })).OrderBy(x => x, StringComparer.Ordinal);
        var resources = module.Resources.Select(r => r.Name + ":" + (int)r.ResourceType + ":" + (int)r.Attributes)
            .OrderBy(x => x, StringComparer.Ordinal);
        return string.Join("\n", new[] {
            "ASSEMBLY:" + module.Assembly.Name.FullName + ":" + AttributesFingerprint(module.Assembly.CustomAttributes),
            "MODULE:" + module.Name + ":" + module.Kind + ":" + module.RuntimeVersion + ":" + module.Architecture + ":" +
                (int)module.Attributes + ":" + module.Characteristics,
            "MODULEATTRS:" + AttributesFingerprint(module.CustomAttributes),
            "RESOURCES:" + string.Join(";", resources),
            "TYPES:" + string.Join("\n", types)
        });
    }
    private static TypeDefinition FindType(ModuleDefinition module, string name) =>
        AllTypes(module.Types).Single(t => t.FullName == name);
    private static MethodDefinition FindMethod(TypeDefinition type, string name, params string[] parameters) =>
        type.Methods.Single(m => m.Name == name && m.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(parameters));
    private static bool IsObserverCall(Instruction? instruction, string name) =>
        instruction?.Operand is MethodReference mr && mr.DeclaringType.FullName == ObserverTypeName &&
        mr.Name == name && mr.ReturnType.FullName == "System.Void" && !mr.HasThis &&
        mr.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(new[] { "System.Int32", "System.Object", "System.UInt64" });
    private static bool IsCall(Instruction instruction, string declaring, string name, params string[] signature) =>
        (instruction.OpCode == OpCodes.Call || instruction.OpCode == OpCodes.Callvirt) &&
        instruction.Operand is MethodReference mr && mr.DeclaringType.Name == declaring && mr.Name == name &&
        (signature.Length == 0 || mr.ReturnType.FullName == signature[0] && mr.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(signature.Skip(1)));
    private static string Hash(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }
    private static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
}
