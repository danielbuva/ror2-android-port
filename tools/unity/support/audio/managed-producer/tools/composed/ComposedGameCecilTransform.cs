using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class OriginalGameCecilTransform
{
    private const string ApiObserverInputSha = "7ec842ee2244590f9227c44280ebbb4a0debf9b83ad1958c045d68dec47e0af9";
    private const string AcceptedRoR2Sha = "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30";
    private const string OwnerType = "GameAudioOriginalOwner";

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 4 && args[0] == "api") return TransformApi(args[1], args[2], args[3]);
            if (args.Length == 4 && args[0] == "game") return TransformGame(args[1], args[2], args[3], null);
            if (args.Length == 5 && args[0] == "game") return TransformGame(args[1], args[2], args[3], args[4]);
            throw new InvalidOperationException("usage: api <7ec-api> <core.dll> <output.dll> | game <current-guarded-RoR2.dll> <core.dll> <output.dll>");
        }
        catch (Exception error) { Console.Error.WriteLine(error.GetType().Name + ": " + error.Message); return 2; }
    }

    private static int TransformApi(string input, string ownerPath, string output)
    {
        Require(Hash(input) == ApiObserverInputSha, "API must be the exact R4 instrumented candidate based on accepted raw 564");
        using (var owner = AssemblyDefinition.ReadAssembly(ownerPath))
        using (var api = AssemblyDefinition.ReadAssembly(input))
        {
            var apiBefore = AllMethods(api.MainModule).ToDictionary(m => m.FullName, Fingerprint);
            var bankManager = FindType(api.MainModule, "AkBankManager");
            var load = FindMethod(bankManager, "LoadBankAsync", "System.String", "AkCallbackManager/BankCallback");
            var asyncType = FindType(api.MainModule, "AkBankManager/AsyncBankHandle");
            var callback = FindMethod(asyncType, "GlobalBankCallback", "System.UInt32", "System.IntPtr", "AKRESULT", "System.Object");
            Require(load.IsStatic && callback.IsStatic, "bank callback sites changed static shape");
            var hook = FindType(owner.MainModule, OwnerType);
            var requestObserver = FindMethod(hook, "ObserveBankRequest", "System.String");
            var resultObserver = FindMethod(hook, "ObserveBankResult", "System.String", "System.Int32", "System.Int32", "System.Int32", "System.UInt32", "System.Boolean");
            var requestRef = api.MainModule.ImportReference(requestObserver);
            var resultRef = api.MainModule.ImportReference(resultObserver);

            Require(load.Body.Instructions.Count(i => IsCall(i, "System.Collections.Generic.Dictionary`2<System.String,AkBankManager/BankHandle>", "TryGetValue")) == 1,
                "unique original managed-handle branch changed");
            Require(load.Body.Instructions.Count(i => IsCall(i, "AkCallbackManager/BankCallback", "Invoke")) == 1,
                "already-loaded callback callsite changed");
            Require(callback.Body.Instructions.Count(i => IsCall(i, "AkCallbackManager/BankCallback", "Invoke")) == 1,
                "new-bank callback forwarding site changed");

            var loadIl = load.Body.GetILProcessor();
            var requestName = loadIl.Create(OpCodes.Ldarg_0);
            var requestCall = loadIl.Create(OpCodes.Call, requestRef);
            loadIl.InsertBefore(load.Body.Instructions[0], requestName);
            loadIl.InsertBefore(load.Body.Instructions[0], requestCall);
            var existingBranch = load.Body.Instructions.Single(i => i.OpCode == OpCodes.Brfalse_S && i.Operand is Instruction target &&
                target.OpCode == OpCodes.Ldarg_0 && target.Next != null && target.Next.OpCode == OpCodes.Ldarg_1);
            var existingStart = (Instruction)existingBranch.Operand;
            // The branch target starts with original name/delegate setup while the
            // lock is held. Insert at its first stack-empty instruction.
            InsertBankResult(load, existingStart, resultRef, false, true, fromExistingLocals: false);

            var callbackFirst = callback.Body.Instructions[0];
            var callbackCast = callbackFirst.Next;
            Require(callbackFirst.OpCode == OpCodes.Ldarg_3 && callbackCast != null && callbackCast.OpCode == OpCodes.Castclass &&
                callbackCast.Operand is TypeReference castType && castType.FullName == asyncType.FullName,
                "GlobalBankCallback cookie cast shape changed");
            var callbackObserverStart = callbackCast.Next.Next;
            InsertBankResult(callback, callbackObserverStart, resultRef, false, false, fromExistingLocals: true);

            // Preserve the current WwiseUnavailable default while restoring a
            // truthful query only after the opt-in bootstrap has successfully
            // loaded the exact native library. Readiness is intentionally not
            // consulted here: an initialized engine whose later bank/monitor
            // gate fails still needs the original owner's real query/Term path.
            var engine = FindType(api.MainModule, "AkSoundEngine");
            var initialized = FindMethod(engine, "IsInitialized");
            Require(initialized.IsStatic && initialized.ReturnType.FullName == "System.Boolean" &&
                initialized.Body.Instructions.Count == 2 &&
                IsCall(initialized.Body.Instructions[0], "AkSoundEnginePINVOKE", "CSharp_IsInitialized") &&
                initialized.Body.Instructions[1].OpCode == OpCodes.Ret,
                "accepted adapted IsInitialized native wrapper changed");
            var nativeAvailable = api.MainModule.ImportReference(FindMethod(
                FindType(owner.MainModule, OwnerType), "get_NativeApiCallsAvailable"));
            var initIl = initialized.Body.GetILProcessor();
            var nativeCall = initialized.Body.Instructions[0];
            var nativeGate = initIl.Create(OpCodes.Call, nativeAvailable);
            var nativeBranch = initIl.Create(OpCodes.Brtrue, nativeCall);
            initIl.InsertBefore(nativeCall, nativeGate);
            initIl.InsertBefore(nativeCall, nativeBranch);
            initIl.InsertBefore(nativeCall, initIl.Create(OpCodes.Ldc_I4_0));
            initIl.InsertBefore(nativeCall, initIl.Create(OpCodes.Ret));

            // Retain the authored unavailable semantics for playback-ID RTPC
            // and stop methods: before/after a live engine they return the
            // documented not-initialized result or do nothing, while a live
            // native engine receives the exact original call and result.
            GuardUnavailableNativeMethod(api.MainModule,
                FindMethod(engine, "SetRTPCValueByPlayingID", "System.String", "System.Single", "System.UInt32"),
                initialized, 102);
            GuardUnavailableNativeMethod(api.MainModule,
                FindMethod(engine, "StopPlayingID", "System.UInt32"), initialized, null);
            api.Write(output);
            VerifyApi(output, ownerPath, apiBefore, new[] { load.FullName, callback.FullName,
                initialized.FullName, FindMethod(engine, "SetRTPCValueByPlayingID", "System.String", "System.Single", "System.UInt32").FullName,
                FindMethod(engine, "StopPlayingID", "System.UInt32").FullName });
            Console.WriteLine("bank request and result observers injected into exact existing-handle/new-callback paths: " + Hash(output));
        }
        return 0;
    }

    private static void GuardUnavailableNativeMethod(ModuleDefinition module, MethodDefinition method,
        MethodDefinition initialized, int? unavailableResult)
    {
        Require(method.IsStatic && method.HasBody && method.Body.Instructions.Count ==
            (unavailableResult.HasValue ? 5 : 3), "unavailable Wwise method body changed: " + method.FullName);
        if (unavailableResult.HasValue)
            Require(method.Body.Instructions[0].OpCode == OpCodes.Ldarg_0 &&
                method.Body.Instructions[1].OpCode == OpCodes.Ldarg_1 &&
                method.Body.Instructions[2].OpCode == OpCodes.Ldarg_2 &&
                IsCall(method.Body.Instructions[3], "AkSoundEnginePINVOKE", "CSharp_SetRTPCValueByPlayingID__SWIG_7") &&
                method.Body.Instructions[4].OpCode == OpCodes.Ret,
                "unavailable Wwise RTPC argument/native-call shape changed: " + method.FullName);
        else
            Require(method.Body.Instructions[0].OpCode == OpCodes.Ldarg_0 &&
                IsCall(method.Body.Instructions[1], "AkSoundEnginePINVOKE", "CSharp_StopPlayingID__SWIG_2") &&
                method.Body.Instructions[2].OpCode == OpCodes.Ret,
                "unavailable Wwise stop argument/native-call shape changed: " + method.FullName);
        var il = method.Body.GetILProcessor();
        var nativeStart = method.Body.Instructions[0];
        var query = module.ImportReference(initialized);
        var available = il.Create(OpCodes.Call, query);
        var branch = il.Create(OpCodes.Brtrue, nativeStart);
        il.InsertBefore(nativeStart, available);
        il.InsertBefore(nativeStart, branch);
        if (unavailableResult.HasValue)
        {
            il.InsertBefore(nativeStart, il.Create(OpCodes.Ldc_I4, unavailableResult.Value));
            il.InsertBefore(nativeStart, il.Create(OpCodes.Ret));
        }
        else il.InsertBefore(nativeStart, il.Create(OpCodes.Ret));
    }

    private static void InsertBankResult(MethodDefinition method, Instruction before, MethodReference observer,
        bool unused, bool alreadyLoaded, bool fromExistingLocals)
    {
        var il = method.Body.GetILProcessor();
        var seq = new System.Collections.Generic.List<Instruction>();
        if (fromExistingLocals)
        {
            // GlobalBankCallback: cookie cast was stored in V0; native callback
            // arguments are (bankId, memory, result, cookie).
            seq.Add(il.Create(OpCodes.Ldloc_0));
            seq.Add(il.Create(OpCodes.Ldfld, FindField(method.Module, "AkBankManager/BankHandle", "bankName")));
            seq.Add(il.Create(OpCodes.Ldarg_2));
            seq.Add(il.Create(OpCodes.Ldc_I4_1)); // AK_Success (pinned IL enum value)
            seq.Add(il.Create(OpCodes.Ldc_I4_S, (sbyte)69)); // AK_BankAlreadyLoaded (pinned IL enum value)
            seq.Add(il.Create(OpCodes.Ldarg_0));
            seq.Add(il.Create(OpCodes.Ldc_I4_0));
        }
        else
        {
            // LoadBankAsync existing-handle branch: method args preserve exact
            // requested name. This is the only branch that calls the game callback
            // synchronously with ID 0 and AK_BankAlreadyLoaded.
            seq.Add(il.Create(OpCodes.Ldarg_0));
            seq.Add(il.Create(OpCodes.Ldc_I4_S, (sbyte)69));
            seq.Add(il.Create(OpCodes.Ldc_I4_1));
            seq.Add(il.Create(OpCodes.Ldc_I4_S, (sbyte)69));
            seq.Add(il.Create(OpCodes.Ldc_I4_0));
            seq.Add(il.Create(OpCodes.Ldc_I4_1));
        }
        seq.Add(il.Create(OpCodes.Call, observer));
        foreach (var instruction in seq) il.InsertBefore(before, instruction);
    }

    private static void VerifyApi(string output, string ownerPath,
        System.Collections.Generic.Dictionary<string, string> before, string[] changedMethods)
    {
        using (var owner = AssemblyDefinition.ReadAssembly(ownerPath))
        using (var resolver = Resolver(output, ownerPath))
        using (var api = AssemblyDefinition.ReadAssembly(output, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var bank = FindType(api.MainModule, "AkBankManager");
            var load = FindMethod(bank, "LoadBankAsync", "System.String", "AkCallbackManager/BankCallback");
            var asyncType = FindType(api.MainModule, "AkBankManager/AsyncBankHandle");
            var callback = FindMethod(asyncType, "GlobalBankCallback", "System.UInt32", "System.IntPtr", "AKRESULT", "System.Object");
            var engine = FindType(api.MainModule, "AkSoundEngine");
            var initialized = FindMethod(engine, "IsInitialized");
            var rtpc = FindMethod(engine, "SetRTPCValueByPlayingID", "System.String", "System.Single", "System.UInt32");
            var stopPlaying = FindMethod(engine, "StopPlayingID", "System.UInt32");
            Require(load.Body.Instructions.Count(i => IsOwnerCall(i, "ObserveBankRequest")) == 1, "bank request hook count is not one");
            Require(load.Body.Instructions.Count(i => IsOwnerCall(i, "ObserveBankResult")) == 1, "existing-handle result hook count is not one");
            Require(callback.Body.Instructions.Count(i => IsOwnerCall(i, "ObserveBankResult")) == 1, "new-bank result hook count is not one");
            Require(initialized.Body.Instructions.Count(i => IsOwnerCall(i, "get_NativeApiCallsAvailable")) == 1 &&
                initialized.Body.Instructions.Any(i => i.OpCode == OpCodes.Brtrue && i.Operand is Instruction target &&
                    IsCall(target, "AkSoundEnginePINVOKE", "CSharp_IsInitialized")),
                "IsInitialized must be false before native-loader proof and query the exact import afterward");
            Require(rtpc.Body.Instructions.Count(i => IsCall(i, "AkSoundEngine", "IsInitialized")) == 1 &&
                rtpc.Body.Instructions.Any(i => i.OpCode == OpCodes.Ldc_I4 && Convert.ToInt32(i.Operand) == 102),
                "RTPC-by-playing-ID unavailable result guard missing");
            Require(stopPlaying.Body.Instructions.Count(i => IsCall(i, "AkSoundEngine", "IsInitialized")) == 1 &&
                stopPlaying.Body.Instructions.Any(i => i.OpCode == OpCodes.Brtrue),
                "stop-by-playing-ID no-op guard missing");
            var after = AllMethods(api.MainModule).ToDictionary(m => m.FullName, Fingerprint);
            Require(before.Count == after.Count && before.Keys.All(after.ContainsKey),
                "Wwise API transform changed method identities");
            foreach (var pair in before)
            {
                if (changedMethods.Contains(pair.Key))
                    Require(pair.Value != after[pair.Key], "declared Wwise API transform did not change expected body: " + pair.Key);
                else
                    Require(pair.Value == after[pair.Key], "unexpected Wwise API body change: " + pair.Key);
            }
            Require(api.MainModule.AssemblyReferences.Any(r => r.Name == owner.Name.Name), "API output lacks observer owner reference");
        }
    }

    private static int TransformGame(string input, string ownerPath, string output, string referenceDirectory)
    {
        Require(Hash(input) == AcceptedRoR2Sha, "game input is not the exact current optional-presentation-guarded RoR2.dll");
        using (var core = AssemblyDefinition.ReadAssembly(ownerPath))
        using (var resolver = Resolver(input, ownerPath, referenceDirectory))
        using (var game = AssemblyDefinition.ReadAssembly(input, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var coreType = FindType(core.MainModule, OwnerType);
            var noAudioRef = game.MainModule.ImportReference(FindMethod(coreType, "get_NoAudio"));
            var skipManagerRef = game.MainModule.ImportReference(FindMethod(coreType, "ShouldSkipOriginalManagerInit"));
            var manager = FindType(game.MainModule, "RoR2.WwiseIntegrationManager");
            var noAudioGetter = FindMethod(manager, "get_noAudio");
            Require(noAudioGetter.ReturnType.FullName == "System.Boolean" && noAudioGetter.Body.Instructions.Count == 2 &&
                noAudioGetter.Body.Instructions[0].OpCode == OpCodes.Ldc_I4_1 && noAudioGetter.Body.Instructions[1].OpCode == OpCodes.Ret,
                "current optional-presentation default-off getter contract changed");
            var init = FindMethod(manager, "Init");
            var gateCalls = init.Body.Instructions.Where(i => IsCall(i, "RoR2.WwiseIntegrationManager", "get_noAudio")).ToArray();
            Require(gateCalls.Length == 1 && gateCalls[0].OpCode == OpCodes.Call &&
                gateCalls[0].Operand is MethodReference gate && gate.Parameters.Count == 0 && skipManagerRef.Parameters.Count == 0 &&
                skipManagerRef.ReturnType.FullName == "System.Boolean",
                "original manager skip gate callsite/signature changed");
            Require(init.Body.Instructions.Count(i => i.OpCode == OpCodes.Ldstr && Equals(i.Operand, "Prefabs/WwiseGlobal")) == 1 &&
                init.Body.Instructions.Count(i => i.OpCode == OpCodes.Ldstr && Equals(i.Operand, "Prefabs/AudioManager")) == 1 &&
                init.Body.Instructions.Count(i => IsCall(i, "RoR2.LegacyResourcesAPI", "LoadAsyncCallback")) == 2,
                "original independent WwiseGlobal/AudioManager resource requests changed");
            var before = AllMethods(game.MainModule).ToDictionary(m => m.FullName, Fingerprint);
            noAudioGetter.Body.Instructions.Clear();
            noAudioGetter.Body.GetILProcessor().Append(Instruction.Create(OpCodes.Call, noAudioRef));
            noAudioGetter.Body.GetILProcessor().Append(Instruction.Create(OpCodes.Ret));
            gateCalls[0].Operand = skipManagerRef;
            game.Write(output);
            VerifyGame(output, ownerPath, before, referenceDirectory);
            Console.WriteLine("guarded game owner/noAudio and correctly-polarized original manager admission hooks injected: " + Hash(output));
        }
        return 0;
    }

    private static void VerifyGame(string output, string corePath, System.Collections.Generic.Dictionary<string, string> before, string referenceDirectory)
    {
        using (var core = AssemblyDefinition.ReadAssembly(corePath))
        using (var resolver = Resolver(output, corePath, referenceDirectory))
        using (var game = AssemblyDefinition.ReadAssembly(output, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var manager = FindType(game.MainModule, "RoR2.WwiseIntegrationManager");
            var getter = FindMethod(manager, "get_noAudio");
            var init = FindMethod(manager, "Init");
            Require(getter.Body.Instructions.Count == 2 && IsOwnerCall(getter.Body.Instructions[0], "get_NoAudio") &&
                getter.Body.Instructions[0].OpCode == OpCodes.Call && getter.Body.Instructions[1].OpCode == OpCodes.Ret,
                "noAudio getter must delegate to the Core readiness gate");
            var skip = init.Body.Instructions.Single(i => IsOwnerCall(i, "ShouldSkipOriginalManagerInit"));
            Require(skip.OpCode == OpCodes.Call && skip.Operand is MethodReference skipMethod &&
                skipMethod.Parameters.Count == 0 && skipMethod.ReturnType.FullName == "System.Boolean" &&
                skip.Next.OpCode == OpCodes.Brtrue_S,
                "manager's original brtrue must skip only when Core says not selected");
            Require(init.Body.Instructions.Count(i => i.OpCode == OpCodes.Ldstr && Equals(i.Operand, "Prefabs/WwiseGlobal")) == 1 &&
                init.Body.Instructions.Count(i => i.OpCode == OpCodes.Ldstr && Equals(i.Operand, "Prefabs/AudioManager")) == 1 &&
                init.Body.Instructions.Count(i => IsCall(i, "RoR2.LegacyResourcesAPI", "LoadAsyncCallback")) == 2,
                "original manager resource requests must remain in place");
            var after = AllMethods(game.MainModule).ToDictionary(m => m.FullName, Fingerprint);
            Require(before.Count == after.Count && before.Keys.All(after.ContainsKey), "game transform changed method identities");
            foreach (var pair in before)
                if (pair.Key != getter.FullName && pair.Key != init.FullName)
                    Require(pair.Value == after[pair.Key], "unexpected non-audio method-body change: " + pair.Key);
            Require(game.MainModule.AssemblyReferences.Any(r => r.Name == core.Name.Name), "transformed game lacks Core reference");
        }
    }

    private static System.Collections.Generic.IEnumerable<MethodDefinition> AllMethods(ModuleDefinition module) =>
        module.Types.SelectMany(All).SelectMany(t => t.Methods);
    private static string Fingerprint(MethodDefinition method)
    {
        if (!method.HasBody) return "no-body";
        var instructions = method.Body.Instructions;
        string Operand(object value)
        {
            if (value is Instruction target) return "instruction:" + instructions.IndexOf(target);
            if (value is Instruction[] targets) return string.Join(",", targets.Select(x => instructions.IndexOf(x)));
            if (value is MemberReference member) return member.FullName;
            if (value is VariableDefinition variable) return "variable:" + variable.Index;
            if (value is ParameterDefinition parameter) return "parameter:" + parameter.Index;
            return value == null ? "" : value.ToString();
        }
        return string.Join("\n", instructions.Select(i => i.OpCode.Name + " " + Operand(i.Operand)));
    }

    private static bool IsOwnerCall(Instruction i, string name) => i.Operand is MethodReference mr && mr.DeclaringType.FullName == OwnerType && mr.Name == name;
    private static bool IsCall(Instruction i, string type, string method) => i.Operand is MethodReference mr && mr.DeclaringType.FullName == type && mr.Name == method;
    private static TypeDefinition FindType(ModuleDefinition module, string name) => module.Types.SelectMany(All).Single(t => t.FullName == name);
    private static System.Collections.Generic.IEnumerable<TypeDefinition> All(TypeDefinition t)
    { yield return t; foreach (var n in t.NestedTypes) foreach (var x in All(n)) yield return x; }
    private static MethodDefinition FindMethod(TypeDefinition type, string name, params string[] parameters) => type.Methods.Single(m => m.Name == name && m.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(parameters));
    private static FieldReference FindField(ModuleDefinition module, string type, string name) => FindType(module, type).Fields.Single(f => f.Name == name);
    private static string Hash(string path) { using (var stream = File.OpenRead(path)) using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant(); }
    private static DefaultAssemblyResolver Resolver(string input, string owner, string extraDirectory = null)
    {
        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(input)));
        resolver.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(owner)));
        if (!String.IsNullOrEmpty(extraDirectory))
        {
            string full = Path.GetFullPath(extraDirectory);
            if (!Directory.Exists(full)) throw new DirectoryNotFoundException("assembly resolver directory does not exist");
            resolver.AddSearchDirectory(full);
        }
        string unityRefs = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/Managed/UnityEngine";
        if (Directory.Exists(unityRefs)) resolver.AddSearchDirectory(unityRefs);
        string unityManaged = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/Managed";
        if (Directory.Exists(unityManaged)) resolver.AddSearchDirectory(unityManaged);
        return resolver;
    }
    private static void Require(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
}
