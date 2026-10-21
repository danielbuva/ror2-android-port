using System;
using System.Linq;
using System.Reflection;
using Mono.Cecil;
using Mono.Cecil.Cil;
using CecilMethodAttributes = Mono.Cecil.MethodAttributes;
using CecilTypeAttributes = Mono.Cecil.TypeAttributes;

internal static class OwnerApiPreTermInjectionHarness
{
    private const CecilTypeAttributes PublicClass = CecilTypeAttributes.Public | CecilTypeAttributes.Class;
    private const CecilMethodAttributes PublicStatic = CecilMethodAttributes.Public | CecilMethodAttributes.Static;

    private static TypeDefinition AddType(ModuleDefinition module, string name, TypeReference baseType = null)
    {
        var type = new TypeDefinition("", name, PublicClass, baseType ?? module.TypeSystem.Object);
        module.Types.Add(type);
        return type;
    }

    private static MethodDefinition AddMethod(TypeDefinition type, string name, TypeReference result, params TypeReference[] args)
    {
        var method = new MethodDefinition(name, PublicStatic, result);
        foreach (var arg in args) method.Parameters.Add(new ParameterDefinition(arg));
        type.Methods.Add(method);
        return method;
    }

    private static ModuleDefinition MakeApi()
    {
        var module = ModuleDefinition.CreateModule("AuthoredOriginalOwnerApiFixture", ModuleKind.Dll);
        var enumType = AddType(module, "AKRESULT", module.ImportReference(typeof(Enum)));
        var initSettings = AddType(module, "AkInitializationSettings");
        var baseSettings = AddType(module, "AkBasePlatformSettings");
        var baseSettingsGetter = AddMethod(baseSettings, "get_AkInitializationSettings", initSettings);
        var engine = AddType(module, "AkSoundEngine");
        var engineInit = AddMethod(engine, "Init", enumType, initSettings);
        var engineTerm = AddMethod(engine, "Term", module.TypeSystem.Void);
        var setOffline = AddMethod(engine, "SetOfflineRendering", enumType, module.TypeSystem.Boolean);
        var loadBank = AddMethod(engine, "LoadBank", enumType, module.TypeSystem.String,
            new ByReferenceType(module.TypeSystem.UInt32));
        var pinvoke = AddType(module, "AkSoundEnginePINVOKE");
        var renderNative = AddMethod(pinvoke, "CSharp_RenderAudio__SWIG_1", module.TypeSystem.Int32);
        var callback = AddType(module, "AkCallbackManager");
        var callbackTerm = AddMethod(callback, "Term", module.TypeSystem.Void);
        var bankManager = AddType(module, "AkBankManager");
        var bank = AddMethod(bankManager, "LoadInitBank", module.TypeSystem.Void, module.TypeSystem.Boolean);
        var reset = AddMethod(bankManager, "Reset", module.TypeSystem.Void);
        var initOwner = AddType(module, "AkSoundEngineInitialization");
        var keepEngine = AddMethod(initOwner, "ShouldKeepSoundEngineEnabled", module.TypeSystem.Boolean);
        var initialize = AddMethod(initOwner, "InitializeSoundEngine", module.TypeSystem.Boolean);
        var initIl = initialize.Body.GetILProcessor();
        initIl.Append(initIl.Create(OpCodes.Call, baseSettingsGetter));
        initIl.Append(initIl.Create(OpCodes.Call, engineInit));
        initIl.Append(initIl.Create(OpCodes.Pop));
        initIl.Append(initIl.Create(OpCodes.Call, engineTerm));
        initIl.Append(initIl.Create(OpCodes.Call, engineTerm));
        initIl.Append(initIl.Create(OpCodes.Ldc_I4_1));
        initIl.Append(initIl.Create(OpCodes.Ret));
        initIl.Append(initIl.Create(OpCodes.Ldc_I4_0));
        initIl.Append(initIl.Create(OpCodes.Ret));
        initIl.Append(initIl.Create(OpCodes.Ldc_I4_0));
        initIl.Append(initIl.Create(OpCodes.Ret));
        var wrapper = AddMethod(initOwner, "LoadInitBank", module.TypeSystem.Void);
        wrapper.Body.Instructions.Add(Instruction.Create(OpCodes.Ldc_I4_1));
        wrapper.Body.Instructions.Add(Instruction.Create(OpCodes.Call, bank));
        wrapper.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));
        var term = AddMethod(initOwner, "TerminateSoundEngine", module.TypeSystem.Void, module.TypeSystem.Boolean);
        var termIl = term.Body.GetILProcessor();
        var teardown = Instruction.Create(OpCodes.Ldc_I4_0);
        termIl.Append(termIl.Create(OpCodes.Call, keepEngine));
        var keepBranch = termIl.Create(OpCodes.Brfalse_S, teardown);
        termIl.Append(keepBranch);
        termIl.Append(termIl.Create(OpCodes.Ldarg_1));
        var forceBranch = termIl.Create(OpCodes.Brtrue_S, teardown);
        termIl.Append(forceBranch);
        termIl.Append(termIl.Create(OpCodes.Ret));
        termIl.Append(teardown);
        termIl.Append(termIl.Create(OpCodes.Call, setOffline));
        termIl.Append(termIl.Create(OpCodes.Pop));
        termIl.Append(termIl.Create(OpCodes.Call, engineTerm));
        termIl.Append(termIl.Create(OpCodes.Call, callbackTerm));
        termIl.Append(termIl.Create(OpCodes.Ret));
        var outputId = new VariableDefinition(module.TypeSystem.UInt32);
        bank.Body.Variables.Add(outputId);
        bank.Body.InitLocals = true;
        var bankIl = bank.Body.GetILProcessor();
        bankIl.Append(bankIl.Create(OpCodes.Call, reset));
        bankIl.Append(bankIl.Create(OpCodes.Ldstr, "Init.bnk"));
        bankIl.Append(bankIl.Create(OpCodes.Ldloca, outputId));
        bankIl.Append(bankIl.Create(OpCodes.Call, loadBank));
        bankIl.Append(bankIl.Create(OpCodes.Pop));
        bankIl.Append(bankIl.Create(OpCodes.Ret));
        var post = AddMethod(callback, "PostCallbacks", module.TypeSystem.Int32);
        post.Body.Instructions.Add(Instruction.Create(OpCodes.Ldc_I4_0));
        post.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));
        var render = AddMethod(engine, "RenderAudio", enumType);
        render.Body.Instructions.Add(Instruction.Create(OpCodes.Call, renderNative));
        render.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));
        return module;
    }

    private static ModuleDefinition MakeObserver()
    {
        var module = ModuleDefinition.CreateModule("OriginalOwnerProbeObserver", ModuleKind.Dll);
        var type = new TypeDefinition("OriginalOwnerProbeObserver", "Observer", PublicClass, module.TypeSystem.Object);
        module.Types.Add(type);
        AddMethod(type, "RecordBeforeEngineInit", module.TypeSystem.Void);
        AddMethod(type, "RecordInitFailureTermReturned", module.TypeSystem.Void);
        AddMethod(type, "RecordInitializeMethodReturned", module.TypeSystem.Int32, module.TypeSystem.Int32);
        AddMethod(type, "RecordInitResult", module.TypeSystem.Void, module.TypeSystem.Int32);
        AddMethod(type, "RecordInitBankResult", module.TypeSystem.Void, module.TypeSystem.Int32, module.TypeSystem.UInt32);
        AddMethod(type, "RecordBeforeEngineTerm", module.TypeSystem.Void);
        AddMethod(type, "RecordEngineTermReturned", module.TypeSystem.Void);
        AddMethod(type, "RecordCallbackManagerTermReturned", module.TypeSystem.Void);
        AddMethod(type, "RecordPostCallbacksReturned", module.TypeSystem.Void, module.TypeSystem.Int32);
        AddMethod(type, "RecordRenderAudioReturned", module.TypeSystem.Void, module.TypeSystem.Int32);
        return module;
    }

    private static int Main(string[] args)
    {
        var transformAssembly = Assembly.LoadFrom(args[0]);
        var transformType = transformAssembly.GetType("Program", true);
        const BindingFlags flags = BindingFlags.NonPublic | BindingFlags.Static;
        var findSites = transformType.GetMethod("FindSites", flags);
        var inject = transformType.GetMethod("Inject", flags);
        var verifyInjection = transformType.GetMethod("VerifyInjectionForm", flags);
        if (findSites == null || inject == null || verifyInjection == null)
            throw new InvalidOperationException("pinned owner transform helpers missing");
        using var api = MakeApi();
        using var observer = MakeObserver();
        var sites = findSites.Invoke(null, new object[] { api });
        inject.Invoke(null, new[] { api, observer, sites });
        verifyInjection.Invoke(null, new[] { sites });
        var term = api.Types.Single(t => t.Name == "AkSoundEngineInitialization")
            .Methods.Single(m => m.Name == "TerminateSoundEngine");
        var guard = term.Body.Instructions.Single(i => i.Operand is MethodReference called && called.Name == "RecordBeforeEngineTerm");
        var branches = (Instruction[])sites.GetType().GetProperty("TermTeardownBranches").GetValue(sites);
        if (branches.Length != 2 || branches.Any(branch => !Object.ReferenceEquals(branch.Operand, guard)))
            throw new InvalidOperationException("both admitted Term branches must pass through the production pre-Term guard");
        var earlyReturn = term.Body.Instructions.First(i => i.OpCode == OpCodes.Ret);
        if (term.Body.Instructions.IndexOf(earlyReturn) >= term.Body.Instructions.IndexOf(guard))
            throw new InvalidOperationException("the original keep-engine early return must remain before the guard");
        branches[0].Operand = (Instruction)sites.GetType().GetProperty("TermTeardownBodyStart").GetValue(sites);
        try
        {
            verifyInjection.Invoke(null, new[] { sites });
            throw new InvalidOperationException("Term-guard bypass mutant unexpectedly passed production verification");
        }
        catch (TargetInvocationException error) when (error.InnerException is InvalidOperationException)
        {
            if (!error.InnerException.Message.Contains("both admitted teardown branches")) throw;
        }
        Console.WriteLine("PASS actual owner API transform injection, two Term gates, preserved early return, and bypass mutant refusal");
        return 0;
    }
}
