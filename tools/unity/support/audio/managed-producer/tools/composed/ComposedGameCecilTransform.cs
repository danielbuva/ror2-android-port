using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class OriginalGameCecilTransform
{
    private const string ApiObserverInputSha = "a2914ace8e2a7338010f8e9a9515911d68489bf0ad467bc7f73f4de293a19fe9";
    private const string AcceptedRoR2Sha = "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30";
    private const string OwnerType = "GameAudioOriginalOwner";

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length == 5 && args[0] == "api") return TransformApi(args[1], args[2], args[3], args[4]);
            if (args.Length == 4 && args[0] == "game") return TransformGame(args[1], args[2], args[3], null);
            if (args.Length == 5 && args[0] == "game") return TransformGame(args[1], args[2], args[3], args[4]);
            if (args.Length == 2 && args[0] == "validate-bank-il") return ValidateBankMethod(args[1]);
            if (args.Length == 5 && args[0] == "point-sound") return TransformPointSound(args[1], args[2], args[3], args[4]);
            if (args.Length == 2 && args[0] == "validate-point-sound") return ValidatePointSound(args[1]);
            if (args.Length == 3 && args[0] == "validate-android-probe") return ValidateAndroidProbe(args[1], args[2]);
            throw new InvalidOperationException("usage: api <7ec-api> <core.dll> <output.dll> <UnityEngine.CoreModule.dll> | game <current-guarded-RoR2.dll> <core.dll> <output.dll> | point-sound <1034-game.dll> <core.dll> <output.dll> <managed-reference-directory>");
        }
        catch (Exception error) { Console.Error.WriteLine(error.GetType().Name + ": " + error.Message); return 2; }
    }

    private static int TransformPointSound(string input, string observerPath, string output, string referenceDirectory)
    {
        const string expectedInput = "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c";
        Require(Hash(input) == expectedInput, "point-sound diagnostic requires exact composed game 1034 input");
        using (var observer = AssemblyDefinition.ReadAssembly(observerPath))
        using (var resolver = Resolver(input, observerPath, referenceDirectory))
        using (var game = AssemblyDefinition.ReadAssembly(input, new ReaderParameters { AssemblyResolver = resolver }))
        {
            var before = AllMethods(game.MainModule).ToDictionary(m => m.FullName, Fingerprint);
            var type = FindType(game.MainModule, "RoR2.Audio.PointSoundManager");
            var request = FindMethod(type, "RequestEmitter");
            var emit = FindMethod(type, "EmitSoundLocal", "RoR2.Audio.AkEventIdArg", "UnityEngine.Vector3");
            int requestShortBranchCount = ShortBranchCount(request);
            int emitShortBranchCount = ShortBranchCount(emit);
            var observerType = FindType(observer.MainModule, "PointSoundDiagnosticObserver");
            var mark = game.MainModule.ImportReference(FindMethod(observerType, "Mark", "System.Int32"));

            var begin = game.MainModule.ImportReference(FindMethod(observerType, "Begin", "System.UInt32"));
            var beginSequence = new[] {
                emit.Body.GetILProcessor().Create(OpCodes.Ldarg_0),
                emit.Body.GetILProcessor().Create(OpCodes.Ldfld, FindField(game.MainModule, "RoR2.Audio.AkEventIdArg", "id")),
                emit.Body.GetILProcessor().Create(OpCodes.Call, begin)
            };
            InsertBeforeWithoutRetarget(emit, emit.Body.Instructions[0], beginSequence);
            var requestCall = emit.Body.Instructions.Single(i => IsCall(i, "RoR2.Audio.PointSoundManager", "RequestEmitter"));
            MarkBefore(emit, requestCall, mark, 2); // emitter acquisition entered
            MarkAfter(emit, requestCall, mark, 3); // returned reference is now on the stack
            var emitterStore = requestCall.Next.Next.Next;
            Require(emitterStore != null && emitterStore.OpCode == OpCodes.Stloc_0, "emitter local store shape changed");
            var objectTruth = request.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Object", "op_Implicit"));
            var enabledGetter = game.MainModule.ImportReference(FindMethod(observerType, "get_Enabled"));
            var aliveObserver = game.MainModule.ImportReference(FindMethod(observerType, "RecordEmitterAlive", "System.Boolean"));
            var il = emit.Body.GetILProcessor();
            var skipEmitterCheck = il.Create(OpCodes.Nop);
            il.InsertAfter(emitterStore, il.Create(OpCodes.Call, enabledGetter));
            il.InsertAfter(emitterStore.Next, il.Create(OpCodes.Brfalse, skipEmitterCheck));
            il.InsertAfter(emitterStore.Next.Next, il.Create(OpCodes.Ldloc_0));
            il.InsertAfter(emitterStore.Next.Next.Next, il.Create(OpCodes.Call, game.MainModule.ImportReference((MethodReference)objectTruth.Operand)));
            il.InsertAfter(emitterStore.Next.Next.Next.Next, il.Create(OpCodes.Call, aliveObserver));
            il.InsertAfter(emitterStore.Next.Next.Next.Next.Next, skipEmitterCheck);
            var getTransform = emit.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Component", "get_transform"));
            MarkBefore(emit, getTransform, mark, 4);
            var setPosition = emit.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Transform", "set_position"));
            MarkAfter(emit, setPosition, mark, 5);
            var setAkPosition = emit.Body.Instructions.Single(i => IsCall(i, "AkGameObj", "SetPosition"));
            MarkAfter(emit, setAkPosition, mark, 6);
            var postEvents = emit.Body.Instructions.Where(i => IsCall(i, "AkSoundEngine", "PostEvent")).ToArray();
            Require(postEvents.Length == 2, "expected original timeout/callback PostEvent alternatives");
            foreach (var post in postEvents) { MarkBefore(emit, post, mark, 7); MarkAfter(emit, post, mark, 8); }
            var enqueue = emit.Body.Instructions.Single(i => IsCall(i,
                "System.Collections.Generic.Queue`1<RoR2.Audio.PointSoundManager/TimeoutInfo>", "Enqueue"));
            MarkBefore(emit, enqueue, mark, 9);
            MarkAfter(emit, enqueue, mark, 10);

            // Mark the selected source-owned acquisition path immediately before
            // its first operation; this distinguishes a thrown pool/prefab/fallback
            // operation as well as successful returns.
            MarkBefore(request, request.Body.Instructions.Single(i => IsCall(i,
                "System.Collections.Generic.Stack`1<AkGameObj>", "Pop")), mark, 20);
            MarkBefore(request, request.Body.Instructions.Single(i => IsCall(i,
                "UnityEngine.Object", "Instantiate")), mark, 21);
            MarkBefore(request, request.Body.Instructions.Single(i => IsCall(i,
                "RoR2.Audio.PointSoundManager", "LoadEmitterPrefab")), mark, 22);

            game.Write(output);
            using (var result = AssemblyDefinition.ReadAssembly(output, new ReaderParameters { AssemblyResolver = resolver }))
            {
                var resultType = FindType(result.MainModule, "RoR2.Audio.PointSoundManager");
                var resultRequest = FindMethod(resultType, "RequestEmitter");
                var resultEmit = FindMethod(resultType, "EmitSoundLocal", "RoR2.Audio.AkEventIdArg", "UnityEngine.Vector3");
                VerifyStackHeights(resultRequest);
                VerifyStackHeights(resultEmit);
                Require(resultEmit.Body.Instructions.Count(i => IsObserverCall(i, "Mark")) == 11,
                    "unexpected EmitSoundLocal marker count");
                Require(resultEmit.Body.Instructions.Count(i => IsObserverCall(i, "Begin")) == 1 &&
                    resultEmit.Body.Instructions.Count(i => IsObserverCall(i, "RecordEmitterAlive")) == 1,
                    "event identity or Unity fake-null observation hook missing");
                Require(resultRequest.Body.Instructions.Count(i => IsObserverCall(i, "Mark")) == 3,
                    "unexpected RequestEmitter branch marker count");
                Require(ShortBranchCount(resultRequest) == requestShortBranchCount &&
                    ShortBranchCount(resultEmit) == emitShortBranchCount,
                    "existing short-branch shape changed; refuse diagnostic output");
                var after = AllMethods(result.MainModule).ToDictionary(m => m.FullName, Fingerprint);
                foreach (var pair in before)
                    if (pair.Key != emit.FullName && pair.Key != request.FullName)
                        Require(after[pair.Key] == pair.Value, "unexpected method changed by diagnostic: " + pair.Key);
                Require(result.MainModule.AssemblyReferences.Any(r => r.Name == observer.Name.Name),
                    "transformed game lacks point-sound diagnostic owner reference");
            }
            Console.WriteLine("point-sound diagnostic boundaries verified; original PostEvent callsites retained; output " + Hash(output));
        }
        return 0;
    }

    private static int ValidatePointSound(string path)
    {
        using (var game = AssemblyDefinition.ReadAssembly(path))
        {
            var type = FindType(game.MainModule, "RoR2.Audio.PointSoundManager");
            var request = FindMethod(type, "RequestEmitter");
            var emit = FindMethod(type, "EmitSoundLocal", "RoR2.Audio.AkEventIdArg", "UnityEngine.Vector3");
            VerifyStackHeights(request);
            VerifyStackHeights(emit);
            Require(emit.Body.Instructions.Count(i => IsObserverCall(i, "Mark")) == 11,
                "instrumented EmitSoundLocal boundary set is incomplete");
            Require(emit.Body.Instructions.Count(i => IsObserverCall(i, "Begin")) == 1 &&
                emit.Body.Instructions.Count(i => IsObserverCall(i, "RecordEmitterAlive")) == 1,
                "instrumented request/event/alive check is incomplete");
            Require(request.Body.Instructions.Count(i => IsObserverCall(i, "Mark")) == 3,
                "instrumented RequestEmitter branch set is incomplete");
            Require(emit.Body.Instructions.Count(i => IsCall(i, "AkSoundEngine", "PostEvent")) == 2,
                "original callback/timeout PostEvent alternatives changed");
            Require(emit.Body.Instructions.Count(i => IsCall(i, "RoR2.Audio.PointSoundManager", "RequestEmitter")) == 1,
                "original emitter request call changed");
            RequireNoIncomingControlEdge(emit, emit.Body.Instructions.Single(i => IsCall(i, "RoR2.Audio.PointSoundManager", "RequestEmitter")));
            RequireNoIncomingControlEdge(request, request.Body.Instructions.Single(i => IsCall(i,
                "System.Collections.Generic.Stack`1<AkGameObj>", "Pop")));
            RequireNoIncomingControlEdge(request, request.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Object", "Instantiate")));
            RequireNoIncomingControlEdge(request, request.Body.Instructions.Single(i => IsCall(i,
                "RoR2.Audio.PointSoundManager", "LoadEmitterPrefab")));
            RequireNoIncomingControlEdge(emit, emit.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Component", "get_transform")));
            RequireNoIncomingControlEdge(emit, emit.Body.Instructions.Single(i => IsCall(i, "UnityEngine.Transform", "set_position")));
            RequireNoIncomingControlEdge(emit, emit.Body.Instructions.Single(i => IsCall(i, "AkGameObj", "SetPosition")));
            foreach (var post in emit.Body.Instructions.Where(i => IsCall(i, "AkSoundEngine", "PostEvent")))
                RequireNoIncomingControlEdge(emit, post);
            RequireNoIncomingControlEdge(emit, emit.Body.Instructions.Single(i => IsCall(i,
                "System.Collections.Generic.Queue`1<RoR2.Audio.PointSoundManager/TimeoutInfo>", "Enqueue")));
        }
        Console.WriteLine("point-sound diagnostic validation passed: " + Hash(path));
        return 0;
    }

    private static void MarkBefore(MethodDefinition method, Instruction before, MethodReference observer, int stage)
    {
        var il = method.Body.GetILProcessor();
        InsertBeforeAndRetarget(method, before, new[] {
            il.Create(OpCodes.Ldc_I4, stage),
            il.Create(OpCodes.Call, observer)
        });
    }

    // Existing branches and exception-region entries must land on the first
    // diagnostic instruction, or a source path can bypass its stage marker.
    private static void InsertBeforeAndRetarget(MethodDefinition method, Instruction before, Instruction[] inserted)
    {
        Require(inserted != null && inserted.Length > 0, "empty instrumentation sequence");
        var il = method.Body.GetILProcessor();
        foreach (var instruction in inserted) il.InsertBefore(before, instruction);
        var first = inserted[0];
        foreach (var instruction in method.Body.Instructions)
        {
            if (ReferenceEquals(instruction, first) || inserted.Contains(instruction)) continue;
            if (ReferenceEquals(instruction.Operand, before)) instruction.Operand = first;
            else if (instruction.Operand is Instruction[] targets)
                for (int i = 0; i < targets.Length; i++) if (ReferenceEquals(targets[i], before)) targets[i] = first;
        }
        foreach (var handler in method.Body.ExceptionHandlers)
        {
            if (ReferenceEquals(handler.TryStart, before)) handler.TryStart = first;
            if (ReferenceEquals(handler.HandlerStart, before)) handler.HandlerStart = first;
            if (ReferenceEquals(handler.FilterStart, before)) handler.FilterStart = first;
        }
    }

    private static void MarkAfter(MethodDefinition method, Instruction after, MethodReference observer, int stage)
    {
        var next = after.Next ?? throw new InvalidOperationException("cannot mark after terminal instruction");
        var il = method.Body.GetILProcessor();
        InsertBeforeWithoutRetarget(method, next, new[] {
            il.Create(OpCodes.Ldc_I4, stage),
            il.Create(OpCodes.Call, observer)
        });
    }

    private static void InsertBeforeWithoutRetarget(MethodDefinition method, Instruction before, Instruction[] inserted)
    {
        Require(inserted != null && inserted.Length > 0, "empty instrumentation sequence");
        var il = method.Body.GetILProcessor();
        foreach (var instruction in inserted) il.InsertBefore(before, instruction);
    }

    private static bool IsObserverCall(Instruction instruction, string name) =>
        instruction.Operand is MethodReference method && method.DeclaringType.FullName == "PointSoundDiagnosticObserver" && method.Name == name;
    private static void RequireNoIncomingControlEdge(MethodDefinition method, Instruction target)
    {
        foreach (var instruction in method.Body.Instructions)
        {
            if (ReferenceEquals(instruction.Operand, target) ||
                instruction.Operand is Instruction[] targets && targets.Any(x => ReferenceEquals(x, target)))
                throw new InvalidOperationException("control-flow edge bypasses point-sound marker before " + target);
        }
        foreach (var handler in method.Body.ExceptionHandlers)
            if (ReferenceEquals(handler.TryStart, target) || ReferenceEquals(handler.HandlerStart, target) ||
                ReferenceEquals(handler.FilterStart, target))
                throw new InvalidOperationException("exception-region entry bypasses point-sound marker before " + target);
    }
    private static int ShortBranchCount(MethodDefinition method) => method.Body.Instructions.Count(i =>
        i.OpCode.OperandType == OperandType.ShortInlineBrTarget);

    private static int TransformApi(string input, string ownerPath, string output, string unityCorePath)
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
            var originalEntry = load.Body.Instructions[0];
            var requestName = loadIl.Create(OpCodes.Ldarg_0);
            var requestCall = loadIl.Create(OpCodes.Call, requestRef);
            loadIl.InsertBefore(originalEntry, requestName);
            loadIl.InsertBefore(originalEntry, requestCall);
            var tryGetValue = load.Body.Instructions.Single(i => IsCall(i,
                "System.Collections.Generic.Dictionary`2<System.String,AkBankManager/BankHandle>", "TryGetValue"));
            var existingBranch = tryGetValue.Next;
            Require(existingBranch != null && existingBranch.OpCode == OpCodes.Brfalse_S,
                "TryGetValue no longer has the pinned false/new-handle branch");
            var newHandleStart = (Instruction)existingBranch.Operand;
            Require(newHandleStart.Next != null && newHandleStart.Next.OpCode == OpCodes.Ldarg_1 &&
                newHandleStart.Next.Next != null && newHandleStart.Next.Next.OpCode == OpCodes.Newobj,
                "TryGetValue false edge no longer starts the new-handle path");
            var incRef = load.Body.Instructions.Single(i => IsCall(i, "AkBankManager/BankHandle", "IncRef"));
            var existingHandleObserverStart = incRef.Next;
            Require(existingHandleObserverStart != null && existingHandleObserverStart.OpCode == OpCodes.Ldarg_1 &&
                existingHandleObserverStart.Next != null && existingHandleObserverStart.Next.OpCode == OpCodes.Brfalse_S,
                "TryGetValue true edge no longer reaches the existing-handle callback guard after IncRef");
            // The true edge falls through IncRef and reaches this stack-empty
            // point. The false edge still branches to newHandleStart and must
            // never report AK_BankAlreadyLoaded.
            InsertBankResult(load, existingHandleObserverStart, resultRef, false, true, fromExistingLocals: false);

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

            // Android Application.streamingAssetsPath is a jar:file URI. The
            // accepted Wwise File.Exists diagnostic therefore cannot establish
            // whether Init.bnk is present. Keep the exact original filesystem
            // probe off Android; on Android use the upstream Wwise policy and
            // leave SoundBankBasePath and every native path untouched.
            var basePathGetter = FindType(api.MainModule, "AkBasePathGetter");
            var evaluatePaths = FindMethod(basePathGetter, "EvaluateGamePaths");
            InsertAndroidJarProbe(api.MainModule, evaluatePaths, unityCorePath);
            api.Write(output);
            VerifyApi(output, ownerPath, apiBefore, new[] { load.FullName, callback.FullName,
                initialized.FullName, FindMethod(engine, "SetRTPCValueByPlayingID", "System.String", "System.Single", "System.UInt32").FullName,
                FindMethod(engine, "StopPlayingID", "System.UInt32").FullName, evaluatePaths.FullName }, unityCorePath);
            Console.WriteLine("bank request and result observers injected into exact existing-handle/new-callback paths: " + Hash(output));
        }
        return 0;
    }

    private static int ValidateAndroidProbe(string path, string unityCorePath)
    {
        using (var assembly = AssemblyDefinition.ReadAssembly(path))
        {
            var method = FindMethod(FindType(assembly.MainModule, "AkBasePathGetter"), "EvaluateGamePaths");
            VerifyAndroidJarProbe(assembly.MainModule, method, unityCorePath);
            VerifyStackHeights(method);
        }
        Console.WriteLine("Android-only Init probe contract and stack/control-flow verified");
        return 0;
    }

    private static void InsertAndroidJarProbe(ModuleDefinition module, MethodDefinition method, string unityCorePath)
    {
        var fileSites = method.Body.Instructions.Where(i => IsCall(i, "System.IO.File", "Exists") &&
            i.Operand is MethodReference called && called.Parameters.Count == 1 &&
            called.Parameters[0].ParameterType.FullName == "System.String" && called.ReturnType.FullName == "System.Boolean").ToArray();
        Require(fileSites.Length == 1, "accepted EvaluateGamePaths must contain exactly one File.Exists(string) probe");
        var fileProbe = fileSites[0];
        Require(!method.Body.Instructions.Any(i => i.Operand is Instruction target && ReferenceEquals(target, fileProbe) ||
            i.Operand is Instruction[] targets && targets.Any(target => ReferenceEquals(target, fileProbe))) &&
            !method.Body.ExceptionHandlers.Any(h => ReferenceEquals(h.TryStart, fileProbe) || ReferenceEquals(h.TryEnd, fileProbe) ||
                ReferenceEquals(h.HandlerStart, fileProbe) || ReferenceEquals(h.HandlerEnd, fileProbe) || ReferenceEquals(h.FilterStart, fileProbe)),
            "File.Exists probe is a branch/EH entry; refusing to splice the platform guard");
        MethodReference getter;
        int androidValue;
        using (var core = AssemblyDefinition.ReadAssembly(unityCorePath))
        {
            Require(core.Name.Name == "UnityEngine.CoreModule", "Unity platform API must come from the pinned CoreModule");
            var application = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.Application");
            var platform = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.RuntimePlatform");
            var platformGetter = application.Methods.Single(m => m.Name == "get_platform" &&
                m.IsStatic && m.Parameters.Count == 0 && m.ReturnType.FullName == platform.FullName);
            Require(platform.IsEnum && platform.IsValueType && platformGetter.ReturnType.IsValueType,
                "RuntimePlatform must retain its exact enum/value-type metadata");
            getter = module.ImportReference(platformGetter);
            var android = platform.Fields.Single(f => f.Name == "Android" && f.IsStatic && f.IsLiteral && f.HasConstant);
            androidValue = Convert.ToInt32(android.Constant);
        }
        var il = method.Body.GetILProcessor();
        var nonAndroid = il.Create(OpCodes.Pop);
        var join = il.Create(OpCodes.Nop);
        var sequence = new[]
        {
            il.Create(OpCodes.Dup),
            il.Create(OpCodes.Call, getter),
            il.Create(OpCodes.Ldc_I4, androidValue),
            il.Create(OpCodes.Bne_Un, nonAndroid),
            il.Create(OpCodes.Pop),
            il.Create(OpCodes.Pop),
            il.Create(OpCodes.Ldc_I4_1),
            il.Create(OpCodes.Br, join),
            nonAndroid,
        };
        foreach (var instruction in sequence) il.InsertBefore(fileProbe, instruction);
        il.InsertAfter(fileProbe, join);
        method.Body.MaxStackSize = Math.Max(method.Body.MaxStackSize, 3);
        VerifyAndroidJarProbe(module, method, unityCorePath);
        VerifyStackHeights(method);
    }

    private static int ResolveAndroidPlatformValue(string unityCorePath, string expectedAssembly)
    {
        using (var core = AssemblyDefinition.ReadAssembly(unityCorePath))
        {
            Require(core.Name.Name == expectedAssembly, "Unity CoreModule differs from Application.platform's assembly scope");
            var platform = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.RuntimePlatform");
            var android = platform.Fields.Single(f => f.Name == "Android" && f.IsStatic && f.IsLiteral && f.HasConstant);
            return Convert.ToInt32(android.Constant);
        }
    }

    private static void VerifyAndroidJarProbe(ModuleDefinition module, MethodDefinition method, string unityCorePath)
    {
        var instructions = method.Body.Instructions;
        using (var core = AssemblyDefinition.ReadAssembly(unityCorePath))
        {
            var platform = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.RuntimePlatform");
            var application = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.Application");
            var exactGetter = application.Methods.Single(m => m.Name == "get_platform" && m.IsStatic &&
                m.Parameters.Count == 0 && m.ReturnType.FullName == platform.FullName);
            Require(platform.IsEnum && platform.IsValueType && exactGetter.ReturnType.IsValueType,
                "pinned Unity CoreModule must define the exact RuntimePlatform enum getter");
        }
        var fileProbe = instructions.Single(i => IsCall(i, "System.IO.File", "Exists") &&
            i.Operand is MethodReference called && called.Parameters.Count == 1 && called.Parameters[0].ParameterType.FullName == "System.String");
        var platformCalls = instructions.Where(i => IsCall(i, "UnityEngine.Application", "get_platform")).ToArray();
        Require(platformCalls.Length == 1 && platformCalls[0].OpCode == OpCodes.Call &&
            platformCalls[0].Operand is MethodReference platformGetter && platformGetter.Parameters.Count == 0 &&
            platformGetter.ReturnType.FullName == "UnityEngine.RuntimePlatform" && platformGetter.ReturnType.IsValueType &&
            platformGetter.ReturnType.Scope.Name == "UnityEngine.CoreModule" &&
            platformGetter.DeclaringType.FullName == "UnityEngine.Application" &&
            platformGetter.DeclaringType.Scope.Name == "UnityEngine.CoreModule",
            "Android probe must use the exact enum-returning CoreModule Application.platform getter once");
        var nonAndroid = fileProbe.Previous;
        Require(nonAndroid != null && nonAndroid.OpCode == OpCodes.Pop &&
            instructions.Count(i => i.OpCode == OpCodes.Bne_Un && i.Operand is Instruction target && ReferenceEquals(target, nonAndroid)) == 1,
            "non-Android arm must retain the original filesystem probe");
        var branch = instructions.Single(i => i.OpCode == OpCodes.Bne_Un && i.Operand is Instruction target && ReferenceEquals(target, nonAndroid));
        var androidValue = ResolveAndroidPlatformValue(unityCorePath, platformCalls[0].Operand is MethodReference getter ? getter.DeclaringType.Scope.Name : "");
        Require(branch.Previous?.OpCode == OpCodes.Ldc_I4 && Convert.ToInt32(branch.Previous.Operand) == androidValue &&
            branch.Previous.Previous != null && ReferenceEquals(branch.Previous.Previous, platformCalls[0]),
            "branch comparison must use pinned RuntimePlatform.Android metadata");
        Require(nonAndroid.Next == fileProbe && fileProbe.Next?.OpCode == OpCodes.Nop,
            "non-Android arm must call the original File.Exists then join");
        var androidArm = branch.Next;
        Require(androidArm != null && androidArm.OpCode == OpCodes.Pop && androidArm.Next?.OpCode == OpCodes.Pop &&
            androidArm.Next.Next?.OpCode == OpCodes.Ldc_I4_1 && androidArm.Next.Next.Next?.OpCode == OpCodes.Br &&
            androidArm.Next.Next.Next.Operand is Instruction targetJoin && ReferenceEquals(targetJoin, fileProbe.Next),
            "Android arm must discard jar URI and provide true only to the existing warning predicate");
        Require(instructions.Count(i => IsCall(i, "AkBasePathGetter", "GetPlatformBasePath")) == 1 &&
            instructions.Count(i => IsCall(i, "AkBasePathGetter", "set_SoundBankBasePath")) == 1,
            "platform branch must preserve the original bank path calculation and single base-path assignment");
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
        System.Collections.Generic.Dictionary<string, string> before, string[] changedMethods, string unityCorePath)
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
            var evaluatePaths = FindMethod(FindType(api.MainModule, "AkBasePathGetter"), "EvaluateGamePaths");
            VerifyAndroidJarProbe(api.MainModule, evaluatePaths, unityCorePath);
            VerifyStackHeights(evaluatePaths);
            VerifyStackHeights(load);
            VerifyLoadBankAsyncInstrumentation(load);
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

    private static int ValidateBankMethod(string path)
    {
        using (var assembly = AssemblyDefinition.ReadAssembly(path))
        {
            var method = FindMethod(FindType(assembly.MainModule, "AkBankManager"), "LoadBankAsync",
                "System.String", "AkCallbackManager/BankCallback");
            VerifyStackHeights(method);
            VerifyLoadBankAsyncInstrumentation(method);
        }
        Console.WriteLine("LoadBankAsync instrumentation and stack heights valid");
        return 0;
    }

    private static void VerifyLoadBankAsyncInstrumentation(MethodDefinition load)
    {
        var ins = load.Body.Instructions;
        Require(ins.Count >= 4 && ins[0].OpCode == OpCodes.Ldarg_0 &&
            IsOwnerCall(ins[1], "ObserveBankRequest") && ins[2].OpCode == OpCodes.Ldnull,
            "request observer must consume the bank name before the original first instruction");
        var tryGetValue = ins.Single(i => IsCall(i,
            "System.Collections.Generic.Dictionary`2<System.String,AkBankManager/BankHandle>", "TryGetValue"));
        var branch = tryGetValue.Next;
        Require(branch != null && branch.OpCode == OpCodes.Brfalse_S,
            "TryGetValue no longer has its false/new-handle branch");
        var resultCalls = ins.Where(i => IsOwnerCall(i, "ObserveBankResult")).ToArray();
        Require(resultCalls.Length == 1, "existing-handle result observer count is not one");
        var result = resultCalls[0];
        var resultStart = result.Previous?.Previous?.Previous?.Previous?.Previous?.Previous;
        Require(!ReferenceEquals(branch.Operand, resultStart),
            "TryGetValue false/new-handle edge must not enter the already-loaded observer");
        var newHandleStart = (Instruction)branch.Operand;
        Require(newHandleStart.Next != null && newHandleStart.Next.OpCode == OpCodes.Ldarg_1 &&
            newHandleStart.Next.Next != null && newHandleStart.Next.Next.OpCode == OpCodes.Newobj,
            "TryGetValue false edge must still create a new async handle");
        Require(result.Previous != null && result.Previous.OpCode == OpCodes.Ldc_I4_1 &&
            result.Previous.Previous?.OpCode == OpCodes.Ldc_I4_0 &&
            result.Previous.Previous.Previous?.OpCode == OpCodes.Ldc_I4_S &&
            Convert.ToInt32(result.Previous.Previous.Previous.Operand) == 69,
            "existing-handle observer argument sequence changed");
        Require(resultStart != null && resultStart.OpCode == OpCodes.Ldarg_0 &&
            result.Next != null && result.Next.OpCode == OpCodes.Ldarg_1 &&
            result.Next.Next != null && result.Next.Next.OpCode == OpCodes.Brfalse_S,
            "existing-handle observer must run after IncRef and before optional callback handling");
        var incRef = resultStart.Previous;
        Require(incRef != null && IsCall(incRef, "AkBankManager/BankHandle", "IncRef"),
            "existing-handle result observer is not on the TryGetValue true/found path");
        Require(!ReferenceEquals(branch.Operand, resultStart),
            "TryGetValue false/new-handle edge must not enter the already-loaded observer");
        Require(!ins.Any(i => i.Operand is Instruction target && ReferenceEquals(target, resultStart)) &&
            !ins.Any(i => i.Operand is Instruction[] targets && targets.Any(target => ReferenceEquals(target, resultStart))) &&
            !load.Body.ExceptionHandlers.Any(handler => ReferenceEquals(handler.TryStart, resultStart) ||
                ReferenceEquals(handler.TryEnd, resultStart) || ReferenceEquals(handler.HandlerStart, resultStart) ||
                ReferenceEquals(handler.HandlerEnd, resultStart) || ReferenceEquals(handler.FilterStart, resultStart)),
            "existing-handle observer point must remain a plain fallthrough within the original exception region");
        Require(ins.Count(i => IsOwnerCall(i, "ObserveBankRequest")) == 1,
            "bank request observer count is not one");
    }

    private static void VerifyStackHeights(MethodDefinition method)
    {
        var instructions = method.Body.Instructions;
        var heights = new System.Collections.Generic.Dictionary<Instruction, int>();
        var pending = new System.Collections.Generic.Queue<Instruction>();
        void Seed(Instruction instruction, int height)
        {
            if (!heights.TryGetValue(instruction, out var prior))
            {
                heights.Add(instruction, height);
                pending.Enqueue(instruction);
            }
            else Require(prior == height, "inconsistent stack height at IL_" + instruction.Offset.ToString("x4"));
        }
        Seed(instructions[0], 0);
        foreach (var handler in method.Body.ExceptionHandlers)
        {
            if (handler.HandlerStart != null)
                Seed(handler.HandlerStart, handler.HandlerType == ExceptionHandlerType.Catch ||
                    handler.HandlerType == ExceptionHandlerType.Filter ? 1 : 0);
            if (handler.FilterStart != null) Seed(handler.FilterStart, 1);
        }
        while (pending.Count != 0)
        {
            var instruction = pending.Dequeue();
            var before = heights[instruction];
            var (pop, push) = StackEffect(instruction, method);
            Require(before >= pop, "stack underflow at IL_" + instruction.Offset.ToString("x4") + " " + instruction.OpCode);
            var after = instruction.OpCode.Code == Code.Leave || instruction.OpCode.Code == Code.Leave_S
                ? 0
                : before - pop + push;
            if (instruction.OpCode.Code == Code.Ret)
                Require(after == 0, "return leaves extra stack entries at IL_" + instruction.Offset.ToString("x4"));
            if (instruction.Operand is Instruction target) Seed(target, after);
            else if (instruction.Operand is Instruction[] targets)
                foreach (var item in targets) Seed(item, after);
            if (instruction.OpCode.FlowControl != FlowControl.Branch &&
                instruction.OpCode.FlowControl != FlowControl.Return &&
                instruction.OpCode.FlowControl != FlowControl.Throw && instruction.Next != null)
                Seed(instruction.Next, after);
        }
    }

    private static (int pop, int push) StackEffect(Instruction instruction, MethodDefinition containingMethod)
    {
        var op = instruction.OpCode;
        if (op == OpCodes.Leave || op == OpCodes.Leave_S) return (0, 0);
        if (op == OpCodes.Call || op == OpCodes.Callvirt || op == OpCodes.Newobj)
        {
            var called = (MethodReference)instruction.Operand;
            var pop = called.Parameters.Count + (op == OpCodes.Newobj || !called.HasThis ? 0 : 1);
            var push = op == OpCodes.Newobj || called.ReturnType.MetadataType != MetadataType.Void ? 1 : 0;
            return (pop, push);
        }
        if (op == OpCodes.Ret) return (containingMethod.ReturnType.MetadataType == MetadataType.Void ? 0 : 1, 0);
        var popCount = FixedStackCount(op.StackBehaviourPop, instruction);
        var pushCount = FixedStackCount(op.StackBehaviourPush, instruction);
        Require(popCount >= 0 && pushCount >= 0, "unsupported variable stack behavior at IL_" + instruction.Offset.ToString("x4"));
        return (popCount, pushCount);
    }

    private static int FixedStackCount(StackBehaviour behavior, Instruction instruction)
    {
        switch (behavior)
        {
            case StackBehaviour.Pop0: case StackBehaviour.Push0: return 0;
            case StackBehaviour.Pop1: case StackBehaviour.Popi: case StackBehaviour.Popref:
            case StackBehaviour.Push1: case StackBehaviour.Pushi: case StackBehaviour.Pushi8:
            case StackBehaviour.Pushr4: case StackBehaviour.Pushr8: case StackBehaviour.Pushref: return 1;
            case StackBehaviour.Pop1_pop1: case StackBehaviour.Popi_pop1: case StackBehaviour.Popi_popi:
            case StackBehaviour.Popi_popi8: case StackBehaviour.Popi_popr4:
            case StackBehaviour.Popi_popr8: case StackBehaviour.Popref_pop1: case StackBehaviour.Popref_popi:
            case StackBehaviour.Push1_push1: return 2;
            case StackBehaviour.Popi_popi_popi: case StackBehaviour.Popref_popi_popi:
            case StackBehaviour.Popref_popi_popref: return 3;
            case StackBehaviour.Varpop: case StackBehaviour.Varpush: return -1;
            default: throw new InvalidOperationException("unhandled stack behavior " + behavior + " at " + instruction);
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
