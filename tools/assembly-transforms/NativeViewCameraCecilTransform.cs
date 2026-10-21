using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Strict single-module transform candidate. The accepted profile is either the
// exact default 3124 preimage or exact frozen audio-owner outputs (1034 and PointSound 6f96 with d540 or retained PCM 1ced API). In the
// audio profile this pass runs after the audio producer and emits a separately
// pinned RoR2.dll; the full closure scanner must consume that result afterward.
internal static class NativeViewCameraCecilTransform
{
    static readonly HashSet<string> ExpectedInputs = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        // Exact outputs of the current accepted input migration and the frozen
        // audio R4 candidate. The 6f96 game image has two exact owner profiles
        // (d540 and the retained PCM 1ced API); resolver validation checks the
        // API half of that pair below.
        "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
        "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
        "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
        "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef", // exact observer output from 6f96
    };

    static string Sha256(string path)
    {
        using (var sha = SHA256.Create()) using (var stream = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static TypeDefinition FindType(ModuleDefinition module, string fullName) =>
        module.GetType(fullName) ?? throw new InvalidOperationException("missing exact type " + fullName);

    static MethodDefinition FindOne(IEnumerable<MethodDefinition> methods, Func<MethodDefinition, bool> predicate, string label)
    {
        var found = methods.Where(predicate).ToArray();
        if (found.Length != 1)
            throw new InvalidOperationException(label + " requires one exact match, observed=" + found.Length);
        return found[0];
    }

    static TypeReference ImportType(ModuleDefinition target, TypeReference source, TypeDefinition sourceMarker, TypeDefinition targetMarker)
    {
        if (source.FullName == sourceMarker.FullName) return targetMarker;
        var local = target.GetType(source.FullName);
        return local != null ? (TypeReference)local : target.ImportReference(source);
    }

    static MethodReference ImportMethod(ModuleDefinition target, MethodReference source)
    {
        var localType = target.GetType(source.DeclaringType.FullName);
        if (localType != null)
        {
            var localMethod = localType.Methods.FirstOrDefault(x => x.FullName == source.FullName);
            if (localMethod != null) return localMethod;
            throw new InvalidOperationException("marker method references a missing target-local method: " + source.FullName);
        }
        return target.ImportReference(source);
    }

    static FieldReference ImportField(ModuleDefinition target, FieldReference source)
    {
        var localType = target.GetType(source.DeclaringType.FullName);
        if (localType != null)
        {
            var localField = localType.Fields.FirstOrDefault(x => x.Name == source.Name &&
                x.FieldType.FullName == source.FieldType.FullName);
            if (localField != null) return localField;
            throw new InvalidOperationException("marker method references a missing target-local field: " + source.FullName);
        }
        return target.ImportReference(source);
    }

    static TypeDefinition CopyMarkerType(ModuleDefinition target, TypeDefinition source)
    {
        if (source.FullName != "RoR2.AndroidNativeSourceViewOnlyRigMarker" || source.NestedTypes.Count != 0 ||
            source.Interfaces.Count != 0 || source.HasProperties || source.HasEvents)
            throw new InvalidOperationException("marker helper type shape changed");
        if (target.GetType(source.FullName) != null)
            throw new InvalidOperationException("marker type already exists in target");

        var type = new TypeDefinition(source.Namespace, source.Name, source.Attributes,
            target.ImportReference(source.BaseType));
        target.Types.Add(type);
        var fieldMap = new Dictionary<FieldDefinition, FieldDefinition>();
        foreach (var field in source.Fields)
        {
            var copy = new FieldDefinition(field.Name, field.Attributes, ImportType(target, field.FieldType, source, type));
            type.Fields.Add(copy);
            fieldMap.Add(field, copy);
        }
        var methodMap = new Dictionary<MethodDefinition, MethodDefinition>();
        foreach (var method in source.Methods)
        {
            var copy = new MethodDefinition(method.Name, method.Attributes, ImportType(target, method.ReturnType, source, type))
            {
                CallingConvention = method.CallingConvention,
                HasThis = method.HasThis,
                ExplicitThis = method.ExplicitThis,
                ImplAttributes = method.ImplAttributes,
            };
            foreach (var parameter in method.Parameters)
                copy.Parameters.Add(new ParameterDefinition(parameter.Name, parameter.Attributes,
                    ImportType(target, parameter.ParameterType, source, type)));
            type.Methods.Add(copy);
            methodMap.Add(method, copy);
        }
        foreach (var method in source.Methods)
        {
            if (!method.HasBody)
                continue;
            var copy = methodMap[method];
            copy.Body = new MethodBody(copy) { InitLocals = method.Body.InitLocals, MaxStackSize = method.Body.MaxStackSize };
            var variableMap = new Dictionary<VariableDefinition, VariableDefinition>();
            foreach (var variable in method.Body.Variables)
            {
                var variableCopy = new VariableDefinition(ImportType(target, variable.VariableType, source, type));
                copy.Body.Variables.Add(variableCopy);
                variableMap.Add(variable, variableCopy);
            }
            var instructionMap = new Dictionary<Instruction, Instruction>();
            foreach (var instruction in method.Body.Instructions)
            {
                var instructionCopy = Instruction.Create(OpCodes.Nop);
                instructionCopy.OpCode = instruction.OpCode;
                copy.Body.Instructions.Add(instructionCopy);
                instructionMap.Add(instruction, instructionCopy);
            }
            foreach (var instruction in method.Body.Instructions)
            {
                object operand = instruction.Operand;
                if (operand is Instruction branch) operand = instructionMap[branch];
                else if (operand is Instruction[] branches) operand = branches.Select(x => instructionMap[x]).ToArray();
                else if (operand is VariableDefinition variable) operand = variableMap[variable];
                else if (operand is ParameterDefinition parameter) operand = copy.Parameters[parameter.Index];
                else if (operand is TypeReference typeRef)
                    operand = ImportType(target, typeRef, source, type);
                else if (operand is MethodReference methodRef) operand = ImportMethod(target, methodRef);
                else if (operand is FieldReference fieldRef)
                    operand = fieldRef is FieldDefinition fd && fieldMap.ContainsKey(fd) ? fieldMap[fd] : ImportField(target, fieldRef);
                else if (operand != null && !(operand is string) && !(operand is int) && !(operand is long) &&
                         !(operand is float) && !(operand is double) && !(operand is byte) && !(operand is sbyte) &&
                         !(operand is short) && !(operand is ushort) && !(operand is uint) && !(operand is ulong))
                    throw new InvalidOperationException("unsupported marker operand " + operand.GetType().FullName);
                instructionMap[instruction].Operand = operand;
            }
            // Preserve the source exception regions along with their IL. In
            // particular, TryPumpOriginalEarlyUpdate has a catch whose first
            // instruction consumes the exception object and rethrows it.
            foreach (var handler in method.Body.ExceptionHandlers)
            {
                copy.Body.ExceptionHandlers.Add(new ExceptionHandler(handler.HandlerType)
                {
                    CatchType = handler.CatchType == null
                        ? null
                        : ImportType(target, handler.CatchType, source, type),
                    TryStart = handler.TryStart == null ? null : instructionMap[handler.TryStart],
                    TryEnd = handler.TryEnd == null ? null : instructionMap[handler.TryEnd],
                    HandlerStart = handler.HandlerStart == null ? null : instructionMap[handler.HandlerStart],
                    HandlerEnd = handler.HandlerEnd == null ? null : instructionMap[handler.HandlerEnd],
                    FilterStart = handler.FilterStart == null ? null : instructionMap[handler.FilterStart],
                });
            }
        }
        return type;
    }

    static void AddGuard(ModuleDefinition target, TypeDefinition marker)
    {
        var rig = FindType(target, "RoR2.CameraRigController");
        var method = FindOne(rig.Methods, x => x.Name == "ModifyAimRayIfApplicable" && !x.HasThis &&
            x.ReturnType.FullName == "UnityEngine.Ray" && x.Parameters.Count == 3 &&
            x.Parameters[0].ParameterType.FullName == "UnityEngine.Ray" &&
            x.Parameters[1].ParameterType.FullName == "UnityEngine.GameObject" &&
            x.Parameters[2].ParameterType.FullName == "System.Single&", "ModifyAimRayIfApplicable signature");
        if (!method.HasBody || method.Body.Instructions.Count != 63)
            throw new InvalidOperationException("pinned ModifyAimRayIfApplicable IL length changed");
        var dereferences = method.Body.Instructions.Where(x => x.OpCode == OpCodes.Ldfld &&
            x.Operand is FieldReference field && field.FullName == "RoR2.LocalUser RoR2.CameraRigController::_localUserViewer").ToArray();
        if (dereferences.Length != 1)
            throw new InvalidOperationException("exact local-viewer dereference site changed");
        var dereference = dereferences[0];
        if (dereference.Previous == null || dereference.Previous.OpCode != OpCodes.Ldloc_2 ||
            dereference.Next == null || dereference.Next.OpCode != OpCodes.Callvirt ||
            !(dereference.Next.Operand is MethodReference cached) || cached.Name != "get_cachedBodyObject" ||
            cached.DeclaringType.FullName != "RoR2.LocalUser")
            throw new InvalidOperationException("local-viewer null-unsafe call shape changed");
        var loopIncrement = method.Body.Instructions.Where(x => x.OpCode == OpCodes.Ldloc_1 &&
            x.Next != null && x.Next.OpCode == OpCodes.Ldc_I4_1 && x.Next.Next != null &&
            x.Next.Next.OpCode == OpCodes.Add && x.Next.Next.Next != null && x.Next.Next.Next.OpCode == OpCodes.Stloc_1).ToArray();
        if (loopIncrement.Length != 1)
            throw new InvalidOperationException("expected unique camera-rig loop increment");
        var helper = FindOne(marker.Methods, x => x.Name == "ShouldSkipNullViewerAim" && !x.HasThis &&
            x.ReturnType.FullName == "System.Boolean" && x.Parameters.Count == 2 &&
            x.Parameters[0].ParameterType.FullName == "RoR2.CameraRigController" &&
            x.Parameters[1].ParameterType.FullName == "UnityEngine.GameObject", "marker null-viewer guard signature");

        var guardStart = dereference.Previous;
        if (guardStart == null || guardStart.OpCode != OpCodes.Ldloc_2)
            throw new InvalidOperationException("guard insertion point before null-unsafe receiver changed");
        var il = method.Body.GetILProcessor();
        il.InsertBefore(guardStart, Instruction.Create(OpCodes.Ldloc_2));
        il.InsertBefore(guardStart, Instruction.Create(OpCodes.Ldarg_1));
        il.InsertBefore(guardStart, Instruction.Create(OpCodes.Call, helper));
        il.InsertBefore(guardStart, Instruction.Create(OpCodes.Brtrue, loopIncrement[0]));
        method.Body.MaxStackSize = Math.Max(method.Body.MaxStackSize, 2);
    }

    static void AddSceneCameraConsoleGuard(ModuleDefinition target, TypeDefinition marker)
    {
        var sceneCamera = FindType(target, "RoR2.SceneCamera");
        var configure = FindOne(sceneCamera.Methods, x => x.Name == "ConfigureGraphicsSettings" && x.HasThis &&
            !x.IsStatic && x.ReturnType.FullName == "System.Void" && x.Parameters.Count == 0,
            "SceneCamera.ConfigureGraphicsSettings signature");
        if (!configure.IsPrivate || !configure.HasBody || configure.Body.Instructions.Count < 1)
            throw new InvalidOperationException("SceneCamera ConfigureGraphicsSettings visibility/body changed");
        var originalEntry = configure.Body.Instructions[0];
        if (configure.Body.Instructions.Any(x => x.Operand == originalEntry ||
            x.Operand is Instruction[] targets && targets.Contains(originalEntry)) ||
            configure.Body.ExceptionHandlers.Any(x => x.TryStart == originalEntry || x.HandlerStart == originalEntry || x.FilterStart == originalEntry))
            throw new InvalidOperationException("SceneCamera graphics method has an incoming branch/handler at entry");
        var consoleType = FindType(target, "RoR2.Console");
        var getInstance = FindOne(consoleType.Methods, x => x.Name == "get_instance" && x.IsStatic &&
            x.Parameters.Count == 0 && x.ReturnType.FullName == "RoR2.Console", "Console.instance getter");
        var guard = FindOne(marker.Methods, x => x.Name == "ShouldSkipMissingConsole" && x.IsStatic &&
            x.ReturnType.FullName == "System.Boolean" && x.Parameters.Count == 2 &&
            x.Parameters[0].ParameterType.FullName == "RoR2.SceneCamera" &&
            x.Parameters[1].ParameterType.FullName == "System.Boolean", "owned SceneCamera Console guard");
        var il = configure.Body.GetILProcessor();
        var begin = Instruction.Create(OpCodes.Ldarg_0);
        var getConsole = Instruction.Create(OpCodes.Call, target.ImportReference(getInstance));
        var nullValue = Instruction.Create(OpCodes.Ldnull);
        var notNull = Instruction.Create(OpCodes.Cgt_Un);
        var callGuard = Instruction.Create(OpCodes.Call, guard);
        var continueOriginal = Instruction.Create(OpCodes.Brfalse, originalEntry);
        var returnVoid = Instruction.Create(OpCodes.Ret);
        il.InsertBefore(originalEntry, begin);
        il.InsertBefore(originalEntry, getConsole);
        il.InsertBefore(originalEntry, nullValue);
        il.InsertBefore(originalEntry, notNull);
        il.InsertBefore(originalEntry, callGuard);
        il.InsertBefore(originalEntry, continueOriginal);
        il.InsertBefore(originalEntry, returnVoid);
        configure.Body.MaxStackSize = Math.Max(configure.Body.MaxStackSize, 3);
    }

    static Dictionary<string, string> ReadAssemblyNames(string directory)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var path in Directory.GetFiles(directory, "*.dll"))
        {
            using (var module = ModuleDefinition.ReadModule(path, new ReaderParameters { ReadSymbols = false }))
            {
                var name = module.Assembly.Name.Name;
                if (result.ContainsKey(name))
                    throw new InvalidOperationException("duplicate assembly identity in resolver directory: " + name);
                result.Add(name, path);
            }
        }
        return result;
    }

    static Dictionary<string, string> ValidateResolverSet(string input, string helperAssembly, string baseDirectory, bool audioProfile)
    {
        var rows = ReadAssemblyNames(baseDirectory);
        var expectedInput = audioProfile
            ? Sha256(input)
            : "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30";
        if (audioProfile && expectedInput != "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c" &&
            expectedInput != "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc" &&
            expectedInput != "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef")
            throw new InvalidOperationException("audio-profile input is outside exact owned game preimages");
        var actualApi = rows.ContainsKey("AK.Wwise.Unity.API")
            ? Sha256(Path.Combine(baseDirectory, "AK.Wwise.Unity.API.dll"))
            : "";
        var expectedApi = audioProfile
            ? ((expectedInput == "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc" ||
                expectedInput == "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef")
                ? new HashSet<string>(StringComparer.OrdinalIgnoreCase)
                {
                    "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
                    "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
                }
                : new HashSet<string>(StringComparer.OrdinalIgnoreCase)
                {
                    "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
                })
            : new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c",
            };
        if (Sha256(input) != expectedInput || !rows.ContainsKey("RoR2") ||
            !rows.ContainsKey("AK.Wwise.Unity.API") ||
            Sha256(Path.Combine(baseDirectory, "RoR2.dll")) != expectedInput ||
            !expectedApi.Contains(actualApi))
            throw new InvalidOperationException("resolver source set does not match exact camera game/API profile");

        // This transform accesses only these external identities: game-local
        // CameraRigController/LocalUser definitions, UnityEngine.CoreModule
        // GameObject/Ray/MonoBehaviour definitions, and the BCL exception/type
        // definitions emitted by the marker helper. Other RoR2 references are
        // intentionally outside Cecil's operand-resolution scope; the current
        // player closure scanner remains the separate completeness gate.
        foreach (var required in new[] { "RoR2", "UnityEngine.CoreModule", "mscorlib" })
            if (!rows.ContainsKey(required))
                throw new InvalidOperationException("missing exact transform type dependency: " + required);

        using (var helper = ModuleDefinition.ReadModule(helperAssembly, new ReaderParameters { ReadSymbols = false }))
        {
            var helperReferences = helper.AssemblyReferences.Select(x => x.Name).OrderBy(x => x, StringComparer.Ordinal).ToArray();
            var expected = new[] { "RoR2", "UnityEngine.CoreModule", "mscorlib" }.OrderBy(x => x, StringComparer.Ordinal).ToArray();
            if (!helperReferences.SequenceEqual(expected))
                throw new InvalidOperationException("marker helper external assembly scope changed: " + String.Join(",", helperReferences));
        }
        using (var target = ModuleDefinition.ReadModule(input, new ReaderParameters { ReadSymbols = false }))
        {
            foreach (var required in new[] { "mscorlib", "UnityEngine.CoreModule" })
                if (!target.AssemblyReferences.Any(x => x.Name == required))
                    throw new InvalidOperationException("exact target reference missing for transformed signature: " + required);
        }
        return rows;
    }

    public static void Transform(string input, string output, string helperAssembly, string audioOverlayOrDash, string baseDirectory, string[] extraSearchDirectories)
    {
        if (!File.Exists(input) || File.Exists(output) || Path.GetFullPath(input) == Path.GetFullPath(output))
            throw new InvalidOperationException("input must exist and output must be a new distinct path");
        string actual = Sha256(input);
        if (!ExpectedInputs.Contains(actual))
            throw new InvalidOperationException("RoR2 input is not the exact pinned preimage: " + actual);
        bool audioProfile = actual != "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30";
        if (audioOverlayOrDash != "-")
            throw new InvalidOperationException("camera transform consumes a single exact generated resolver set, never an overlay");
        ValidateResolverSet(input, helperAssembly, baseDirectory, audioProfile);
        var searchDirectories = new List<string> { baseDirectory };
        searchDirectories.AddRange(extraSearchDirectories);
        var resolver = new DefaultAssemblyResolver();
        foreach (var directory in searchDirectories)
            if (Directory.Exists(directory)) resolver.AddSearchDirectory(directory);
        using (var target = ModuleDefinition.ReadModule(input, new ReaderParameters { ReadSymbols = false, AssemblyResolver = resolver }))
        using (var helper = ModuleDefinition.ReadModule(helperAssembly, new ReaderParameters { ReadSymbols = false, AssemblyResolver = resolver }))
        {
            var sourceMarker = FindType(helper, "RoR2.AndroidNativeSourceViewOnlyRigMarker");
            var marker = CopyMarkerType(target, sourceMarker);
            AddGuard(target, marker);
            AddSceneCameraConsoleGuard(target, marker);
            target.Write(output);
        }
    }
    public static int Main(string[] args)
    {
        if (args.Length < 5) return 2;
        Transform(args[0], args[1], args[2], args[3], args[4], args.Skip(5).ToArray());
        return 0;
    }
}
