using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;

static class Program
{
    const string InputSha = "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272";
    const string ObserverType = "OriginalOwnerProbeObserver.Observer";
    const string InitType = "AkSoundEngineInitialization";
    const string BankType = "AkBankManager";
    const string EngineType = "AkSoundEngine";
    const string CallbackType = "AkCallbackManager";
    const string SoundEnginePinvokeType = "AkSoundEnginePINVOKE";

    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "inspect") return Inspect(args[1]);
            if (args.Length == 4 && args[0] == "transform") return Transform(args[1], args[2], args[3]);
            if (args.Length == 4 && args[0] == "verify") return Verify(args[1], args[2], args[3]);
            if (args.Length == 3 && args[0] == "validate-sites") return ValidateSites(args[1], args[2]);
            if (args.Length == 4 && args[0] == "mutate") return Mutate(args[1], args[2], args[3]);
            throw new InvalidOperationException("usage: inspect <dll> | transform <input> <output> <observer.dll> | verify <input> <output> <observer.dll> | validate-sites <mutant.dll> <observer.dll> | mutate <input> <output> <missing-init|duplicate-init|missing-bank|duplicate-bank|missing-engine-term|missing-callback-term|missing/duplicate-postobserver|missing/duplicate-renderobserver|undeclared-body|term-guard-bypass>");
        }
        catch (Exception e) { Console.Error.WriteLine(e.GetType().Name + ": " + e.Message); return 2; }
    }

    static int Inspect(string path)
    {
        using var a = Read(path);
        foreach (var r in a.MainModule.AssemblyReferences) Console.WriteLine("REF " + r.FullName);
        foreach (var t in AllTypes(a.MainModule.Types).Where(t => t.Name.Contains("AkSoundEngineInitialization") || t.Name.Contains("AkBankManager") || t.Name.Contains("AkWwiseInitializationSettings") || t.Name.Contains("AkWindowsSettings") || t.FullName == "AkSoundEngine" || t.FullName == "AkCallbackManager"))
        {
            Console.WriteLine("TYPE " + t.FullName);
            foreach (var m in t.Methods.Where(m => m.HasBody && (t.FullName != "AkSoundEngine" && t.FullName != "AkCallbackManager" || m.Name == "RenderAudio" || m.Name == "PostCallbacks")))
            {
                Console.WriteLine("METHOD " + m.FullName + " max=" + m.Body.MaxStackSize + " locals=" + m.Body.Variables.Count);
                foreach (var i in m.Body.Instructions) Console.WriteLine($"  IL_{i.Offset:x4}: {i.OpCode} {i.Operand}");
            }
        }
        return 0;
    }

    static int Transform(string input, string output, string observerPath)
    {
        Require(Hash(input) == InputSha, "input API hash is not the pinned 2bd original-564-derived fixture input");
        Require(Hash(observerPath) == ExpectedObserverSha, "observer helper does not match its pinned source build; update candidate pins");
        Require(Path.GetFullPath(input) != Path.GetFullPath(output), "transform must write a separate candidate copy");
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!);
        using var a = Read(input);
        using var helper = Read(observerPath);
        var sites = FindSites(a.MainModule);
        Inject(a.MainModule, helper.MainModule, sites);
        a.Write(output);
        VerifyCore(input, output, observerPath);
        Console.WriteLine("transformed and verified " + Hash(output));
        return 0;
    }

    static int Verify(string input, string output, string observerPath)
    {
        Require(Hash(input) == InputSha, "input API hash is not pinned");
        Require(Hash(observerPath) == ExpectedObserverSha, "observer helper hash is not pinned");
        VerifyCore(input, output, observerPath);
        Console.WriteLine("verification passed " + Hash(output));
        return 0;
    }

    // Update only after deliberately freezing a newly compiled observer source.
    const string ExpectedObserverSha = "21c797a5f098a2de9ef5b723558693eb110a30011412bc87f2a2f3ad368279cf";

    static int ValidateSites(string mutantPath, string observerPath)
    {
        using var a = Read(mutantPath);
        using var helper = Read(observerPath);
        _ = FindSites(a.MainModule);
        Console.WriteLine("target callsites unique and complete");
        return 0;
    }

    static int Mutate(string input, string output, string mutation)
    {
        using var a = Read(input);
        var sites = FindSites(a.MainModule);
        MethodDefinition method;
        Instruction target;
        switch (mutation)
        {
            case "term-guard-bypass":
                if (sites.TermTeardownBranches.Length == 0) throw new InvalidOperationException("teardown branch site missing");
                sites.TermTeardownBranches[0].Operand = sites.TermTeardownBodyStart;
                a.Write(output);
                return 0;
            case "undeclared-body":
                method = FindMethod(a.MainModule, InitType, "ResetBanks", Array.Empty<string>());
                var ret = method.Body.Instructions.Last(i => i.OpCode == OpCodes.Ret);
                method.Body.GetILProcessor().InsertBefore(ret, Instruction.Create(OpCodes.Nop));
                a.Write(output);
                return 0;
            case "missing-init": method = sites.InitMethod; target = sites.InitCall; break;
            case "duplicate-init": method = sites.InitMethod; target = sites.InitCall; break;
            case "missing-bank": method = sites.BankMethod; target = sites.BankCall; break;
            case "duplicate-bank": method = sites.BankMethod; target = sites.BankCall; break;
            case "missing-engine-term": method = sites.TermMethod; target = sites.EngineTermCall; break;
            case "missing-callback-term": method = sites.TermMethod; target = sites.CallbackTermCall; break;
            case "missing-postobserver":
                method = sites.PostCallbacksMethod; target = FindObserverCalls(method, "RecordPostCallbacksReturned").Single(); break;
            case "duplicate-postobserver":
                method = sites.PostCallbacksMethod; target = FindObserverCalls(method, "RecordPostCallbacksReturned").Single();
                DuplicateReturnObserver(method, target); a.Write(output); return 0;
            case "missing-renderobserver":
                method = sites.RenderAudioMethod; target = FindObserverCalls(method, "RecordRenderAudioReturned").Single(); break;
            case "duplicate-renderobserver":
                method = sites.RenderAudioMethod; target = FindObserverCalls(method, "RecordRenderAudioReturned").Single();
                DuplicateReturnObserver(method, target); a.Write(output); return 0;
            default: throw new InvalidOperationException("unknown mutation: " + mutation);
        }
        var il = method.Body.GetILProcessor();
        if (mutation.StartsWith("missing-", StringComparison.Ordinal))
        {
            il.Remove(target);
        }
        else
        {
            il.InsertBefore(target, il.Create(target.OpCode, (MethodReference)target.Operand));
        }
        a.Write(output);
        return 0;
    }

    static void DuplicateReturnObserver(MethodDefinition method, Instruction observerCall)
    {
        var mr = (MethodReference)observerCall.Operand;
        var il = method.Body.GetILProcessor();
        var dup = il.Create(OpCodes.Dup);
        var call = il.Create(OpCodes.Call, mr);
        il.InsertBefore(observerCall, dup);
        il.InsertBefore(observerCall, call);
    }

    static void VerifyCore(string input, string output, string observerPath)
    {
        Require(File.Exists(output), "candidate output is missing");
        using var before = Read(input);
        using var after = Read(output);
        var beforeSites = FindSites(before.MainModule);
        var afterSites = FindInstrumentedSites(after.MainModule);
        RequireSameOriginalMemberSurface(before.MainModule, after.MainModule);
        RequireObserverReference(after.MainModule, observerPath);
        foreach (var oldMethod in AllTypes(before.MainModule.Types).SelectMany(t => t.Methods))
        {
            var newMethod = FindMethod(after.MainModule, oldMethod.DeclaringType.FullName, oldMethod.Name, oldMethod.Parameters.Select(p => p.ParameterType.FullName).ToArray());
            Require(Signature(oldMethod) == Signature(newMethod), "existing method identity/attributes changed: " + oldMethod.FullName);
            if (!oldMethod.HasBody) continue;
            Require(newMethod.HasBody, "existing method body removed: " + oldMethod.FullName);
            bool target = IsAllowedTarget(oldMethod, beforeSites);
            string oldFingerprint = BodyFingerprint(oldMethod, stripObserver: false);
            string newFingerprint = BodyFingerprint(newMethod, stripObserver: true);
            if (!target) Require(oldFingerprint == newFingerprint, "undeclared method body changed: " + oldMethod.FullName);
            else Require(oldFingerprint == newFingerprint, "original target body differs after removing only declared observer injections: " + oldMethod.FullName);
            if (target)
                Require(newMethod.Body.MaxStackSize >= oldMethod.Body.MaxStackSize, "target MaxStackSize decreased: " + oldMethod.FullName);
        }
        Require(afterSites.BeforeInitObserverCalls == 1 && afterSites.InitObserverCalls == 1 && afterSites.InitFailureTermObserverCalls == 2 &&
                afterSites.InitializeReturnObserverCalls == 3 && afterSites.BankObserverCalls == 1 &&
                afterSites.PostCallbacksObserverCalls == 1 && afterSites.RenderAudioObserverCalls == 1 &&
                afterSites.BeforeEngineTermObserverCalls == 1 && afterSites.EngineTermObserverCalls == 1 && afterSites.CallbackTermObserverCalls == 1,
                "injected observer call count is not exact");
        Require(afterSites.InitCallCount == 1 && afterSites.InitFailureTermCallCount == 2 && afterSites.BankCallCount == 1 &&
                afterSites.EngineTermCallCount == 1 && afterSites.CallbackTermCallCount == 1 &&
                afterSites.PostCallbacksReturnCount == 1 && afterSites.RenderAudioReturnCount == 1,
                "original native call count changed");
    }

    static bool IsAllowedTarget(MethodDefinition m, Sites s) =>
        m.FullName == s.InitMethod.FullName || m.FullName == s.BankMethod.FullName || m.FullName == s.TermMethod.FullName ||
        m.FullName == s.PostCallbacksMethod.FullName || m.FullName == s.RenderAudioMethod.FullName;

    static Sites FindSites(ModuleDefinition module)
    {
        var init = FindMethod(module, InitType, "InitializeSoundEngine", Array.Empty<string>());
        var bank = FindMethod(module, BankType, "LoadInitBank", new[] { "System.Boolean" });
        var term = FindMethod(module, InitType, "TerminateSoundEngine", new[] { "System.Boolean" });
        var postCallbacks = FindMethod(module, CallbackType, "PostCallbacks", Array.Empty<string>());
        var renderAudio = FindMethod(module, EngineType, "RenderAudio", Array.Empty<string>());
        Require(init.ReturnType.FullName == "System.Boolean", "InitializeSoundEngine return type drift");
        Require(bank.ReturnType.FullName == "System.Void", "LoadInitBank return type drift");
        Require(term.ReturnType.FullName == "System.Void", "TerminateSoundEngine(bool) return type drift");
        Require(postCallbacks.ReturnType.FullName == "System.Int32", "PostCallbacks return type drift");
        Require(renderAudio.ReturnType.FullName == "AKRESULT", "RenderAudio return type drift");
        RequireCallsOnlyOne(init, EngineType, "Init", "AKRESULT AkSoundEngine::Init(AkInitializationSettings)");
        var initFailureTerms = init.Body.Instructions.Where(i => IsCall(i, EngineType, "Term")).ToArray();
        Require(initFailureTerms.Length == 2 && initFailureTerms.All(i => ((MethodReference)i.Operand).FullName == "System.Void AkSoundEngine::Term()"),
            "InitializeSoundEngine failure Term callsite set drift");
        RequireCallsOnlyOne(bank, EngineType, "LoadBank", "AKRESULT AkSoundEngine::LoadBank(System.String,System.UInt32&)");
        RequireCallsOnlyOne(term, EngineType, "Term", "System.Void AkSoundEngine::Term()");
        RequireCallsOnlyOne(term, EngineType, "SetOfflineRendering", "AKRESULT AkSoundEngine::SetOfflineRendering(System.Boolean)");
        RequireCallsOnlyOne(term, CallbackType, "Term", "System.Void AkCallbackManager::Term()");
        RequireCallsOnlyOne(renderAudio, SoundEnginePinvokeType, "CSharp_RenderAudio__SWIG_1", "System.Int32 AkSoundEnginePINVOKE::CSharp_RenderAudio__SWIG_1()");
        var initCall = FindUniqueCall(init, EngineType, "Init");
        var bankCall = FindUniqueCall(bank, EngineType, "LoadBank");
        var engineTerm = FindUniqueCall(term, EngineType, "Term");
        var teardown = FindTermTeardownStart(term);
        var callbackTerm = FindUniqueCall(term, CallbackType, "Term");
        var postCallbacksReturns = postCallbacks.Body.Instructions.Where(i => i.OpCode == OpCodes.Ret).ToArray();
        var renderAudioReturns = renderAudio.Body.Instructions.Where(i => i.OpCode == OpCodes.Ret).ToArray();
        Require(postCallbacksReturns.Length == 1 && renderAudioReturns.Length == 1, "frame-service return-site set drift");
        Require(postCallbacksReturns.All(r => !HasIncomingControlBoundary(postCallbacks, r)) &&
                renderAudioReturns.All(r => !HasIncomingControlBoundary(renderAudio, r)),
                "frame-service return is a branch/EH boundary");
        var outputIdLoad = bankCall.Previous ?? throw new InvalidOperationException("Init bank output ID load missing");
        Require(IsLdloca(outputIdLoad.OpCode), "Init bank output ID is not a single existing local");
        var outputId = outputIdLoad.Operand as VariableDefinition ?? throw new InvalidOperationException("Init bank output ID local operand missing");
        Require(outputId.VariableType.FullName == "System.UInt32", "Init bank output ID local type drift");
        Require(outputIdLoad.Previous?.OpCode == OpCodes.Ldstr && (string)outputIdLoad.Previous.Operand == "Init.bnk", "Init bank name/call sequence drift");
        Require(!HasIncomingControlBoundary(init, initCall.Next) && !HasIncomingControlBoundary(bank, bankCall.Next) &&
                initFailureTerms.All(t => !HasIncomingControlBoundary(init, t.Next)) &&
                !IsInsideExceptionRegion(term, teardown.BodyStart) &&
                !HasIncomingControlBoundary(term, engineTerm) && !HasIncomingControlBoundary(term, engineTerm.Next) &&
                !IsInsideExceptionRegion(term, engineTerm) && !HasIncomingControlBoundary(term, callbackTerm.Next),
                "observer insertion point is a branch or exception-region boundary; refuse ambiguous IL");
        RequireCallsOnlyOne(bank, BankType, "Reset", "System.Void AkBankManager::Reset()");
        var loadWrapper = FindMethod(module, InitType, "LoadInitBank", Array.Empty<string>());
        Require(loadWrapper.Body.Instructions.Any(i => IsCall(i, BankType, "LoadInitBank") && i.Previous?.OpCode == OpCodes.Ldc_I4_1),
                "original initializer no longer calls LoadInitBank(true), preserving Reset semantics");
        var returns = init.Body.Instructions.Where(i => i.OpCode == OpCodes.Ret).ToArray();
        Require(returns.Length == 3, "InitializeSoundEngine return-site count drift");
        Require(returns.All(r => !HasIncomingControlBoundary(init, r)), "InitializeSoundEngine return is a branch/EH boundary");
        return new Sites(init, bank, term, postCallbacks, renderAudio, initCall, initFailureTerms, bankCall, engineTerm, teardown.BodyStart, teardown.Entry, teardown.Branches, callbackTerm, outputId, returns, postCallbacksReturns, renderAudioReturns);
    }

    static Sites FindInstrumentedSites(ModuleDefinition module)
    {
        var sites = FindSitesIgnoringObserverCalls(module);
        var counters = CountObserverCalls(module);
        sites.BeforeInitObserverCalls = counters.beforeInit;
        sites.InitFailureTermObserverCalls = counters.initFailureTerm;
        sites.InitializeReturnObserverCalls = counters.initializeReturn;
        sites.InitObserverCalls = counters.init;
        sites.BankObserverCalls = counters.bank;
        sites.BeforeEngineTermObserverCalls = counters.beforeEngineTerm;
        sites.EngineTermObserverCalls = counters.engineTerm;
        sites.CallbackTermObserverCalls = counters.callbackTerm;
        sites.PostCallbacksObserverCalls = counters.postCallbacks;
        sites.RenderAudioObserverCalls = counters.renderAudio;
        sites.InitCallCount = sites.InitMethod.Body.Instructions.Count(i => IsCall(i, EngineType, "Init"));
        sites.InitFailureTermCallCount = sites.InitMethod.Body.Instructions.Count(i => IsCall(i, EngineType, "Term"));
        sites.BankCallCount = sites.BankMethod.Body.Instructions.Count(i => IsCall(i, EngineType, "LoadBank"));
        sites.EngineTermCallCount = sites.TermMethod.Body.Instructions.Count(i => IsCall(i, EngineType, "Term"));
        sites.CallbackTermCallCount = sites.TermMethod.Body.Instructions.Count(i => IsCall(i, CallbackType, "Term"));
        sites.PostCallbacksReturnCount = sites.PostCallbacksMethod.Body.Instructions.Count(i => i.OpCode == OpCodes.Ret);
        sites.RenderAudioReturnCount = sites.RenderAudioMethod.Body.Instructions.Count(i => i.OpCode == OpCodes.Ret);
        sites.PostCallbacksReturnCount = sites.PostCallbacksMethod.Body.Instructions.Count(i => i.OpCode == OpCodes.Ret);
        sites.RenderAudioReturnCount = sites.RenderAudioMethod.Body.Instructions.Count(i => i.OpCode == OpCodes.Ret);
        return sites;
    }

    static Sites FindSitesIgnoringObserverCalls(ModuleDefinition module)
    {
        // An output must still contain exactly the original callsites; FindSites also
        // checks every source-specific operand and branch boundary.
        return FindSites(module);
    }

    static (int beforeInit, int init, int bank, int initFailureTerm, int initializeReturn, int beforeEngineTerm, int engineTerm, int callbackTerm, int postCallbacks, int renderAudio) CountObserverCalls(ModuleDefinition module)
    {
        var calls = AllTypes(module.Types).SelectMany(t => t.Methods).Where(m => m.HasBody).SelectMany(m => m.Body.Instructions)
            .Where(i => i.OpCode == OpCodes.Call && i.Operand is MethodReference mr && mr.DeclaringType.FullName == ObserverType)
            .Select(i => ((MethodReference)i.Operand).Name).ToArray();
        return (calls.Count(n => n == "RecordBeforeEngineInit"), calls.Count(n => n == "RecordInitResult"), calls.Count(n => n == "RecordInitBankResult"),
            calls.Count(n => n == "RecordInitFailureTermReturned"), calls.Count(n => n == "RecordInitializeMethodReturned"),
            calls.Count(n => n == "RecordBeforeEngineTerm"), calls.Count(n => n == "RecordEngineTermReturned"), calls.Count(n => n == "RecordCallbackManagerTermReturned"),
            calls.Count(n => n == "RecordPostCallbacksReturned"), calls.Count(n => n == "RecordRenderAudioReturned"));
    }

    static void Inject(ModuleDefinition module, ModuleDefinition observerModule, Sites s)
    {
        var observer = observerModule.GetType(ObserverType) ?? throw new InvalidOperationException("observer type missing");
        var beforeInit = Import(module, observer, "RecordBeforeEngineInit");
        var initFailureTermReturned = Import(module, observer, "RecordInitFailureTermReturned");
        var recordInitializeMethodReturned = Import(module, observer, "RecordInitializeMethodReturned", "System.Int32");
        var recordInit = Import(module, observer, "RecordInitResult", "System.Int32");
        var recordBank = Import(module, observer, "RecordInitBankResult", "System.Int32", "System.UInt32");
        var recordBeforeEngineTerm = Import(module, observer, "RecordBeforeEngineTerm");
        var recordEngineTerm = Import(module, observer, "RecordEngineTermReturned");
        var recordCallbackTerm = Import(module, observer, "RecordCallbackManagerTermReturned");
        var recordPostCallbacks = Import(module, observer, "RecordPostCallbacksReturned", "System.Int32");
        var recordRenderAudio = Import(module, observer, "RecordRenderAudioReturned", "System.Int32");

        var initIl = s.InitMethod.Body.GetILProcessor();
        initIl.InsertBefore(s.InitCall, initIl.Create(OpCodes.Call, beforeInit));
        foreach (var failureTerm in s.InitFailureTermCalls)
            initIl.InsertAfter(failureTerm, initIl.Create(OpCodes.Call, initFailureTermReturned));
        foreach (var ret in s.InitializeReturns)
        {
            var duplicate = initIl.Create(OpCodes.Dup);
            var returnObserver = initIl.Create(OpCodes.Call, recordInitializeMethodReturned);
            initIl.InsertBefore(ret, duplicate);
            initIl.InsertBefore(ret, returnObserver);
        }
        var initDup = initIl.Create(OpCodes.Dup);
        var initCall = initIl.Create(OpCodes.Call, recordInit);
        initIl.InsertAfter(s.InitCall, initDup);
        initIl.InsertAfter(initDup, initCall);
        s.InitMethod.Body.MaxStackSize = Math.Max(s.InitMethod.Body.MaxStackSize, 2);

        var bankIl = s.BankMethod.Body.GetILProcessor();
        var bankDup = bankIl.Create(OpCodes.Dup);
        var loadId = bankIl.Create(OpCodes.Ldloc, s.OutputId);
        var bankObserverCall = bankIl.Create(OpCodes.Call, recordBank);
        bankIl.InsertAfter(s.BankCall, bankDup);
        bankIl.InsertAfter(bankDup, loadId);
        bankIl.InsertAfter(loadId, bankObserverCall);
        s.BankMethod.Body.MaxStackSize = Math.Max(s.BankMethod.Body.MaxStackSize, 3);

        var termIl = s.TermMethod.Body.GetILProcessor();
        var preTeardownGuard = termIl.Create(OpCodes.Call, recordBeforeEngineTerm);
        termIl.InsertBefore(s.TermTeardownBodyStart, preTeardownGuard);
        foreach (var branch in s.TermTeardownBranches) branch.Operand = preTeardownGuard;
        termIl.InsertAfter(s.EngineTermCall, termIl.Create(OpCodes.Call, recordEngineTerm));
        termIl.InsertAfter(s.CallbackTermCall, termIl.Create(OpCodes.Call, recordCallbackTerm));
        var postIl = s.PostCallbacksMethod.Body.GetILProcessor();
        postIl.InsertBefore(s.PostCallbacksReturns[0], postIl.Create(OpCodes.Dup));
        postIl.InsertBefore(s.PostCallbacksReturns[0], postIl.Create(OpCodes.Call, recordPostCallbacks));
        var renderIl = s.RenderAudioMethod.Body.GetILProcessor();
        renderIl.InsertBefore(s.RenderAudioReturns[0], renderIl.Create(OpCodes.Dup));
        renderIl.InsertBefore(s.RenderAudioReturns[0], renderIl.Create(OpCodes.Call, recordRenderAudio));
        VerifyInjectionForm(s);
    }

    static void VerifyInjectionForm(Sites s)
    {
        var init = s.InitMethod; var bank = s.BankMethod; var term = s.TermMethod; var post = s.PostCallbacksMethod; var render = s.RenderAudioMethod;
        var initObserver = FindObserverCalls(init, "RecordInitResult").Single();
        Require(initObserver.Previous?.OpCode == OpCodes.Dup && IsCall(initObserver.Previous.Previous, EngineType, "Init"), "Init observer is not immediately after the original Init result");
        var beforeInitObserver = FindObserverCalls(init, "RecordBeforeEngineInit").Single();
        Require(IsCall(beforeInitObserver.Next, EngineType, "Init") &&
                beforeInitObserver.Previous is { OpCode: var previousOp } && (previousOp == OpCodes.Call || previousOp == OpCodes.Callvirt) &&
                beforeInitObserver.Previous.Operand is MethodReference settingsGetter &&
                settingsGetter.FullName == "AkInitializationSettings AkBasePlatformSettings::get_AkInitializationSettings()",
            "Pre-Init observer is not immediately between the original typed settings getter and Init call");
        var failureTerms = FindObserverCalls(init, "RecordInitFailureTermReturned").ToArray();
        Require(failureTerms.Length == 2 && failureTerms.All(t => IsCall(t.Previous, EngineType, "Term")), "Init-failure Term witnesses are not at the original Term return sites");
        var methodReturns = FindObserverCalls(init, "RecordInitializeMethodReturned").ToArray();
        Require(methodReturns.Length == 3 && methodReturns.All(c => c.Previous?.OpCode == OpCodes.Dup && c.Next?.OpCode == OpCodes.Ret),
            "InitializeSoundEngine bool return observers do not preserve all original return values");
        var bankObserver = FindObserverCalls(bank, "RecordInitBankResult").Single();
        Require(bankObserver.Previous?.OpCode == OpCodes.Ldloc && bankObserver.Previous.Previous?.OpCode == OpCodes.Dup &&
                IsCall(bankObserver.Previous.Previous.Previous, EngineType, "LoadBank"), "Init-bank observer does not preserve result/out ID at original call site");
        var beforeEngineTermObserver = FindObserverCalls(term, "RecordBeforeEngineTerm").Single();
        var engineTermObserver = FindObserverCalls(term, "RecordEngineTermReturned").Single();
        var callbackTermObserver = FindObserverCalls(term, "RecordCallbackManagerTermReturned").Single();
        Require(beforeEngineTermObserver.Next == s.TermTeardownBodyStart && beforeEngineTermObserver.Next?.OpCode == OpCodes.Ldc_I4_0 &&
                IsCall(beforeEngineTermObserver.Next.Next, EngineType, "SetOfflineRendering"),
            "pre-Term observer is not the first instruction after both original early-return gates and before teardown");
        Require(s.TermTeardownBranches.All(b => ReferenceEquals(b.Operand, beforeEngineTermObserver)) && s.TermTeardownBranches.Length == 2,
            "both admitted teardown branches must pass through the pre-teardown guard");
        Require(IsCall(engineTermObserver.Previous, EngineType, "Term"), "engine Term witness is not at its original return site");
        Require(IsCall(callbackTermObserver.Previous, CallbackType, "Term"), "callback-manager Term witness is not at its original return site");
        var postObserver = FindObserverCalls(post, "RecordPostCallbacksReturned").Single();
        Require(postObserver.Previous?.OpCode == OpCodes.Dup && postObserver.Next?.OpCode == OpCodes.Ret,
            "PostCallbacks result observer does not preserve its original return value");
        var renderObserver = FindObserverCalls(render, "RecordRenderAudioReturned").Single();
        Require(renderObserver.Previous?.OpCode == OpCodes.Dup && renderObserver.Next?.OpCode == OpCodes.Ret,
            "RenderAudio result observer does not preserve its original return value");
    }

    static IEnumerable<Instruction> FindObserverCalls(MethodDefinition m, string name) => m.Body.Instructions.Where(i =>
        i.OpCode == OpCodes.Call && i.Operand is MethodReference mr && mr.DeclaringType.FullName == ObserverType && mr.Name == name);

    static MethodReference Import(ModuleDefinition module, TypeDefinition type, string methodName, params string[] args)
    {
        var m = type.Methods.SingleOrDefault(x => x.Name == methodName && x.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(args));
        if (m == null) throw new InvalidOperationException("observer method signature missing: " + methodName);
        return module.ImportReference(m);
    }

    static bool HasIncomingControlBoundary(MethodDefinition method, Instruction? next)
    {
        if (next == null) return true;
        foreach (var i in method.Body.Instructions)
        {
            if (ReferenceEquals(i.Operand, next)) return true;
            if (i.Operand is Instruction[] targets && targets.Any(t => ReferenceEquals(t, next))) return true;
        }
        return method.Body.ExceptionHandlers.Any(e => ReferenceEquals(e.TryStart, next) || ReferenceEquals(e.TryEnd, next) ||
            ReferenceEquals(e.HandlerStart, next) || ReferenceEquals(e.HandlerEnd, next) || ReferenceEquals(e.FilterStart, next));
    }

    // The pre-Term observer may deliberately throw to preserve a still-owned
    // native callback. Refuse a callsite inside an existing EH region where the
    // original method could catch that refusal and continue into Term.
    static bool IsInsideExceptionRegion(MethodDefinition method, Instruction target)
    {
        var instructions = method.Body.Instructions;
        int targetIndex = instructions.IndexOf(target);
        if (targetIndex < 0) return true;
        bool Covers(Instruction? start, Instruction? end)
        {
            if (start == null) return false;
            int startIndex = instructions.IndexOf(start);
            int endIndex = end == null ? instructions.Count : instructions.IndexOf(end);
            return startIndex >= 0 && endIndex >= 0 && startIndex <= targetIndex && targetIndex < endIndex;
        }
        foreach (var handler in method.Body.ExceptionHandlers)
        {
            if (Covers(handler.TryStart, handler.TryEnd) || Covers(handler.HandlerStart, handler.HandlerEnd) ||
                (handler.FilterStart != null && Covers(handler.FilterStart, handler.HandlerStart))) return true;
        }
        return false;
    }

    static void RequireCallsOnlyOne(MethodDefinition m, string type, string name, string exact)
    {
        var calls = m.Body.Instructions.Where(i => IsCall(i, type, name)).ToArray();
        Require(calls.Length == 1, $"expected exactly one {type}::{name} call in {m.FullName}; got {calls.Length}");
        Require(((MethodReference)calls[0].Operand).FullName == exact, $"call signature drift: {calls[0].Operand}");
    }

    static (Instruction BodyStart, Instruction Entry, Instruction[] Branches) FindTermTeardownStart(MethodDefinition term)
    {
        var instructions = term.Body.Instructions;
        var offline = FindUniqueCall(term, EngineType, "SetOfflineRendering");
        var bodyStart = offline.Previous;
        Require(bodyStart?.OpCode == OpCodes.Ldc_I4_0, "Term teardown no longer disables offline rendering with literal false");
        var existingGuards = FindObserverCalls(term, "RecordBeforeEngineTerm").ToArray();
        Require(existingGuards.Length <= 1, "duplicate pre-teardown observer guard");
        var entry = existingGuards.Length == 1 ? existingGuards[0] : bodyStart!;
        if (existingGuards.Length == 1)
            Require(existingGuards[0].Next == bodyStart, "pre-teardown guard is not directly before offline-rendering disable");
        var keep = instructions.Where(i => IsCall(i, InitType, "ShouldKeepSoundEngineEnabled")).ToArray();
        Require(keep.Length == 1, "Term early-return gate callsite changed");
        var keepIndex = instructions.IndexOf(keep[0]);
        Require(keepIndex + 4 < instructions.Count, "Term early-return gate instruction count drift");
        Require(instructions[keepIndex + 1].OpCode == OpCodes.Brfalse_S, "ShouldKeep early gate branch opcode drift: " + instructions[keepIndex + 1]);
        Require(ReferenceEquals(instructions[keepIndex + 1].Operand, entry), "ShouldKeep false branch no longer enters teardown");
        Require(instructions[keepIndex + 2].OpCode == OpCodes.Ldarg_1, "forceReset argument load drift");
        Require(instructions[keepIndex + 3].OpCode == OpCodes.Brtrue_S, "forceReset early gate branch opcode drift: " + instructions[keepIndex + 3]);
        Require(ReferenceEquals(instructions[keepIndex + 3].Operand, entry), "forceReset true branch no longer enters teardown");
        Require(instructions[keepIndex + 4].OpCode == OpCodes.Ret, "ShouldKeep early-return ret drift");
        var incoming = instructions.Where(i => (i.Operand is Instruction target && ReferenceEquals(target, entry)) ||
            (i.Operand is Instruction[] targets && targets.Any(t => ReferenceEquals(t, entry)))).ToArray();
        Require(incoming.Length == 2 && incoming.All(i => i.OpCode == OpCodes.Brfalse_S || i.OpCode == OpCodes.Brtrue_S),
            "Term teardown entry has an unexpected branch predecessor");
        Require(bodyStart != null && !IsInsideExceptionRegion(term, bodyStart), "pre-teardown insertion point is inside an exception region or absent");
        // The expected two conditional branches are the only control-flow entry
        // into teardown; redirect both through the refusal gate before any mutation.
        return (bodyStart!, entry, incoming);
    }

    static Instruction FindUniqueCall(MethodDefinition m, string type, string name)
    {
        var found = m.Body.Instructions.Where(i => IsCall(i, type, name)).ToArray();
        Require(found.Length == 1, $"expected one call to {type}::{name}; got {found.Length}");
        return found[0];
    }

    static bool IsCall(Instruction? i, string type, string name) => i != null &&
        (i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt) && i.Operand is MethodReference m &&
        m.DeclaringType.FullName == type && m.Name == name;

    static bool IsLdloca(OpCode op) => op == OpCodes.Ldloca || op == OpCodes.Ldloca_S;

    static MethodDefinition FindMethod(ModuleDefinition module, string typeName, string name, string[] parameterTypes)
    {
        var t = AllTypes(module.Types).SingleOrDefault(x => x.FullName == typeName) ?? throw new InvalidOperationException("type missing: " + typeName);
        return t.Methods.SingleOrDefault(m => m.Name == name && m.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(parameterTypes))
            ?? throw new InvalidOperationException("method missing/ambiguous: " + typeName + "::" + name);
    }

    static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> roots)
    {
        foreach (var t in roots)
        {
            yield return t;
            foreach (var child in AllTypes(t.NestedTypes)) yield return child;
        }
    }

    static string Signature(MethodDefinition m) => m.FullName + "|attr=" + (int)m.Attributes + "|impl=" + (int)m.ImplAttributes +
        "|generic=" + string.Join(",", m.GenericParameters.Select(p => p.Name + ":" + (int)p.Attributes)) +
        "|params=" + string.Join(",", m.Parameters.Select(p => p.Name + ":" + p.ParameterType.FullName + ":" + (int)p.Attributes));

    static void RequireSameOriginalMemberSurface(ModuleDefinition before, ModuleDefinition after)
    {
        var oldTypes = AllTypes(before.Types).ToArray();
        var newTypes = AllTypes(after.Types).ToDictionary(t => t.FullName);
        foreach (var old in oldTypes)
        {
            Require(newTypes.TryGetValue(old.FullName, out var current), "existing type removed: " + old.FullName);
            Require(old.Attributes == current!.Attributes && old.BaseType?.FullName == current.BaseType?.FullName,
                "existing type identity/attributes changed: " + old.FullName);
            var fields = current.Fields.ToDictionary(f => f.Name);
            foreach (var f in old.Fields)
                Require(fields.TryGetValue(f.Name, out var nf) && f.FullName == nf.FullName && f.Attributes == nf.Attributes,
                    "existing field identity changed: " + f.FullName);
            var methods = current.Methods.ToDictionary(Signature);
            foreach (var m in old.Methods)
                Require(methods.ContainsKey(Signature(m)), "existing method identity changed: " + m.FullName);
            var properties = current.Properties.Select(p => p.FullName + "|" + (int)p.Attributes).OrderBy(x => x).ToArray();
            var oldProperties = old.Properties.Select(p => p.FullName + "|" + (int)p.Attributes).OrderBy(x => x).ToArray();
            Require(properties.SequenceEqual(oldProperties), "existing properties changed: " + old.FullName);
            var events = current.Events.Select(e => e.FullName + "|" + (int)e.Attributes).OrderBy(x => x).ToArray();
            var oldEvents = old.Events.Select(e => e.FullName + "|" + (int)e.Attributes).OrderBy(x => x).ToArray();
            Require(events.SequenceEqual(oldEvents), "existing events changed: " + old.FullName);
        }
        Require(newTypes.Count == oldTypes.Length, "API assembly has added/removed type identities");
        var beforeRefs = before.AssemblyReferences.Select(r => r.FullName).OrderBy(x => x).ToArray();
        var afterRefs = after.AssemblyReferences.Select(r => r.FullName).OrderBy(x => x).ToArray();
        var extra = afterRefs.Except(beforeRefs).ToArray();
        Require(extra.Length == 1 && extra[0].StartsWith("OriginalOwnerProbeObserver,", StringComparison.Ordinal), "unexpected assembly-reference change: " + string.Join(" || ", extra));
        Require(beforeRefs.Except(afterRefs).Count() == 0, "existing assembly reference removed");
    }

    static void RequireObserverReference(ModuleDefinition module, string observerPath)
    {
        using var observer = Read(observerPath);
        var expected = observer.Name.FullName;
        Require(module.AssemblyReferences.Any(r => r.FullName == expected), "candidate does not reference exact observer helper identity");
    }

    static string BodyFingerprint(MethodDefinition m, bool stripObserver)
    {
        var instructions = m.Body.Instructions.ToList();
        if (stripObserver) instructions = StripObserverInjection(instructions);
        var index = instructions.Select((ins, i) => (ins, i)).ToDictionary(x => x.ins, x => x.i);
        var lines = new List<string>();
        foreach (var i in instructions)
        {
            string operand = i.Operand switch
            {
                null => "",
                Instruction target => "target:" + index[NormalizeTarget(target)],
                Instruction[] targets => "targets:" + string.Join(",", targets.Select(t => index[NormalizeTarget(t)])),
                VariableDefinition v => "var:" + v.Index + ":" + v.VariableType.FullName,
                ParameterDefinition p => "param:" + p.Index + ":" + p.ParameterType.FullName,
                MethodReference mr => "method:" + mr.FullName,
                FieldReference fr => "field:" + fr.FullName,
                TypeReference tr => "type:" + tr.FullName,
                string s => "string:" + s,
                _ => i.Operand.ToString() ?? ""
            };
            lines.Add(i.OpCode.Code + " " + operand);
        }
        Instruction NormalizeTarget(Instruction target)
        {
            if (stripObserver && target.OpCode == OpCodes.Call && target.Operand is MethodReference mr &&
                mr.DeclaringType.FullName == ObserverType && mr.Name == "RecordBeforeEngineTerm")
                return target.Next ?? throw new InvalidOperationException("pre-teardown observer has no continuation target");
            return target;
        }
        string locals = string.Join(";", m.Body.Variables.Select(v => v.Index + ":" + v.VariableType.FullName));
        string handlers = string.Join(";", m.Body.ExceptionHandlers.Select(e => (int)e.HandlerType + ":" + Boundary(e.TryStart) + ":" + Boundary(e.TryEnd) + ":" + Boundary(e.HandlerStart) + ":" + Boundary(e.HandlerEnd) + ":" + Boundary(e.FilterStart)));
        return string.Join("\n", lines) + "\nLOCALS " + locals + "\nEH " + handlers;
        string Boundary(Instruction? x) => x == null ? "-" : "i" + index[x];
    }

    static List<Instruction> StripObserverInjection(List<Instruction> ins)
    {
        var result = new List<Instruction>();
        foreach (var instruction in ins)
        {
            if (instruction.OpCode == OpCodes.Call && instruction.Operand is MethodReference mr && mr.DeclaringType.FullName == ObserverType)
            {
                switch (mr.Name)
                {
                    case "RecordInitResult":
                        Require(result.Count >= 1 && result[^1].OpCode == OpCodes.Dup, "malformed Init observer injection");
                        result.RemoveAt(result.Count - 1); break;
                    case "RecordBeforeEngineInit": break;
                    case "RecordInitFailureTermReturned": break;
                    case "RecordInitializeMethodReturned":
                        Require(result.Count >= 1 && result[^1].OpCode == OpCodes.Dup, "malformed InitializeSoundEngine return observer injection");
                        result.RemoveAt(result.Count - 1); break;
                    case "RecordInitBankResult":
                        Require(result.Count >= 2 && result[^1].OpCode == OpCodes.Ldloc && result[^2].OpCode == OpCodes.Dup, "malformed Init-bank observer injection");
                        result.RemoveRange(result.Count - 2, 2); break;
                    case "RecordBeforeEngineTerm":
                    case "RecordEngineTermReturned":
                    case "RecordCallbackManagerTermReturned": break;
                    case "RecordPostCallbacksReturned":
                    case "RecordRenderAudioReturned":
                        Require(result.Count >= 1 && result[^1].OpCode == OpCodes.Dup, "malformed frame-service observer injection");
                        result.RemoveAt(result.Count - 1); break;
                    default: throw new InvalidOperationException("unknown inserted observer method: " + mr.Name);
                }
                continue;
            }
            result.Add(instruction);
        }
        return result;
    }

    static AssemblyDefinition Read(string path) => AssemblyDefinition.ReadAssembly(path, new ReaderParameters { InMemory = true, ReadWrite = false });
    static string Hash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
    static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }

    sealed class Sites
    {
        public MethodDefinition InitMethod { get; }
        public MethodDefinition BankMethod { get; }
        public MethodDefinition TermMethod { get; }
        public MethodDefinition PostCallbacksMethod { get; }
        public MethodDefinition RenderAudioMethod { get; }
        public Instruction InitCall { get; }
        public Instruction[] InitFailureTermCalls { get; }
        public Instruction[] InitializeReturns { get; }
        public Instruction[] PostCallbacksReturns { get; }
        public Instruction[] RenderAudioReturns { get; }
        public Instruction BankCall { get; }
        public Instruction EngineTermCall { get; }
        public Instruction TermTeardownBodyStart { get; }
        public Instruction TermTeardownEntry { get; }
        public Instruction[] TermTeardownBranches { get; }
        public Instruction CallbackTermCall { get; }
        public VariableDefinition OutputId { get; }
        public int BeforeInitObserverCalls, InitObserverCalls, InitFailureTermObserverCalls, InitializeReturnObserverCalls, BankObserverCalls, BeforeEngineTermObserverCalls, EngineTermObserverCalls, CallbackTermObserverCalls, PostCallbacksObserverCalls, RenderAudioObserverCalls;
        public int InitCallCount, InitFailureTermCallCount, BankCallCount, EngineTermCallCount, CallbackTermCallCount, PostCallbacksReturnCount, RenderAudioReturnCount;
        public Sites(MethodDefinition init, MethodDefinition bank, MethodDefinition term, MethodDefinition postCallbacks, MethodDefinition renderAudio, Instruction initCall, Instruction[] initFailureTermCalls, Instruction bankCall, Instruction engineTerm, Instruction teardownBodyStart, Instruction teardownEntry, Instruction[] teardownBranches, Instruction callbackTerm, VariableDefinition outputId, Instruction[] initializeReturns, Instruction[] postCallbacksReturns, Instruction[] renderAudioReturns)
        { InitMethod=init; BankMethod=bank; TermMethod=term; PostCallbacksMethod=postCallbacks; RenderAudioMethod=renderAudio; InitCall=initCall; InitFailureTermCalls=initFailureTermCalls; BankCall=bankCall; EngineTermCall=engineTerm; TermTeardownBodyStart=teardownBodyStart; TermTeardownEntry=teardownEntry; TermTeardownBranches=teardownBranches; CallbackTermCall=callbackTerm; OutputId=outputId; InitializeReturns=initializeReturns; PostCallbacksReturns=postCallbacksReturns; RenderAudioReturns=renderAudioReturns; }
    }
}
