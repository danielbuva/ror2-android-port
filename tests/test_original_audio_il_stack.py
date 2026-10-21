from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest
import uuid


def find_repo_root() -> Path:
    marker = Path("tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()
PRODUCTION_SOURCE = ROOT / "tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs"
UNITY_CONTENTS = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
UNITY_CORE = UNITY_CONTENTS / "Managed/UnityEngine/UnityEngine.CoreModule.dll"
MONO_DIR = UNITY_CONTENTS / "MonoBleedingEdge"
MONO = MONO_DIR / "bin/mono"
CSC = MONO_DIR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = MONO_DIR / "lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
OUTPUT_ROOT = ROOT / "work/coordination/original-game-audio-basepath-repair/r3/portable-test"


SYNTHETIC_FIXTURE_SOURCE = r"""
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using Mono.Cecil;
using Mono.Cecil.Cil;
using CecilMethodBody = Mono.Cecil.Cil.MethodBody;
using CecilTypeAttributes = Mono.Cecil.TypeAttributes;
using CecilMethodAttributes = Mono.Cecil.MethodAttributes;

internal static class StackContractFixture
{
    private static MethodInfo verifier;

    private static int Main(string[] args)
    {
        var transform = Assembly.LoadFrom(args[0]);
        var type = transform.GetType("OriginalGameCecilTransform", true);
        verifier = type.GetMethod("VerifyStackHeights", BindingFlags.Static | BindingFlags.NonPublic);
        if (verifier == null) throw new InvalidOperationException("actual transform stack verifier is missing");

        ExpectPass("empty void return", Body((m, _) => m.Append(Instruction.Create(OpCodes.Ret))));
        ExpectFail("call underflow", "stack underflow", Body((m, method) =>
        {
            var owner = method.DeclaringType;
            var call = new MethodReference("NeedsArgument", method.Module.TypeSystem.Void, owner) { HasThis = false };
            call.Parameters.Add(new ParameterDefinition(method.Module.TypeSystem.Int32));
            m.Append(Instruction.Create(OpCodes.Call, call));
            m.Append(Instruction.Create(OpCodes.Ret));
        }));
        ExpectFail("leftover on void return", "return leaves extra", Body((m, _) =>
        {
            m.Append(Instruction.Create(OpCodes.Ldc_I4_1));
            m.Append(Instruction.Create(OpCodes.Ret));
        }));
        ExpectPass("leave.s clears evaluation stack", Body((m, _) =>
        {
            var target = Instruction.Create(OpCodes.Ret);
            m.Append(Instruction.Create(OpCodes.Ldc_I4_1));
            m.Append(Instruction.Create(OpCodes.Leave_S, target));
            m.Append(target);
        }));
        ExpectPass("cpblk consumes three operands", Body((m, _) =>
        {
            m.Append(Instruction.Create(OpCodes.Ldc_I4_1));
            m.Append(Instruction.Create(OpCodes.Ldc_I4_2));
            m.Append(Instruction.Create(OpCodes.Ldc_I4_3));
            m.Append(Instruction.Create(OpCodes.Cpblk));
            m.Append(Instruction.Create(OpCodes.Ret));
        }));
        ExpectFail("branch stack-height join mismatch", "inconsistent stack height", Body((m, _) =>
        {
            var target = Instruction.Create(OpCodes.Ret);
            m.Append(Instruction.Create(OpCodes.Ldc_I4_0));
            m.Append(Instruction.Create(OpCodes.Brfalse_S, target));
            m.Append(Instruction.Create(OpCodes.Ldc_I4_1));
            m.Append(target);
        }));
        Console.WriteLine("six synthetic stack-contract cases passed");
        if (args.Length == 3) AndroidProbeCases(transform, args[1], args[2]);
        else if (args.Length != 1) throw new InvalidOperationException("fixture expects transform and optional CoreModule/output directory");
        return 0;
    }

    private static void AndroidProbeCases(Assembly transform, string unityCorePath, string outputDirectory)
    {
        if (String.IsNullOrEmpty(unityCorePath) || !File.Exists(unityCorePath))
            throw new InvalidOperationException("pinned Unity CoreModule path is required");
        var type = transform.GetType("OriginalGameCecilTransform", true);
        var insert = type.GetMethod("InsertAndroidJarProbe", BindingFlags.Static | BindingFlags.NonPublic);
        var verify = type.GetMethod("VerifyAndroidJarProbe", BindingFlags.Static | BindingFlags.NonPublic);
        if (insert == null || verify == null)
            throw new InvalidOperationException("actual production Android probe injector/verifier is missing");
        Directory.CreateDirectory(outputDirectory);
        var validPath = Path.Combine(outputDirectory, "android-probe-valid.dll");
        WriteAndroidProbeFixture(transform, insert, verify, unityCorePath, validPath, null);
        foreach (var mutation in new[] { "android-false", "branch-invert", "remove-probe" })
            WriteAndroidProbeFixture(transform, insert, verify, unityCorePath,
                Path.Combine(outputDirectory, mutation + ".dll"), mutation);
    }

    private static void WriteAndroidProbeFixture(Assembly transform, MethodInfo insert, MethodInfo verify,
        string unityCorePath, string outputPath, string mutation)
    {
        using (var module = ModuleDefinition.CreateModule("AndroidProbeFixture", ModuleKind.Dll))
        {
            var type = new TypeDefinition("", "AkBasePathGetter", CecilTypeAttributes.Public | CecilTypeAttributes.Class,
                module.TypeSystem.Object);
            module.Types.Add(type);
            var getBase = new MethodDefinition("GetPlatformBasePath", CecilMethodAttributes.Public | CecilMethodAttributes.Static,
                module.TypeSystem.String);
            var setBase = new MethodDefinition("set_SoundBankBasePath", CecilMethodAttributes.Public | CecilMethodAttributes.Static,
                module.TypeSystem.Void);
            setBase.Parameters.Add(new ParameterDefinition(module.TypeSystem.String));
            var evaluate = new MethodDefinition("EvaluateGamePaths", CecilMethodAttributes.Public | CecilMethodAttributes.Static,
                module.TypeSystem.Void);
            type.Methods.Add(getBase);
            type.Methods.Add(setBase);
            type.Methods.Add(evaluate);
            getBase.Body.Instructions.Add(Instruction.Create(OpCodes.Ldstr, "jar:file:///fixture/base.apk!/assets"));
            getBase.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));
            setBase.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));

            var exists = typeof(File).GetMethod("Exists", new[] { typeof(string) });
            if (exists == null) throw new InvalidOperationException("host File.Exists(string) is unavailable");
            var il = evaluate.Body.GetILProcessor();
            evaluate.Body.Variables.Add(new VariableDefinition(module.TypeSystem.Boolean));
            evaluate.Body.InitLocals = true;
            il.Append(il.Create(OpCodes.Call, getBase));
            il.Append(il.Create(OpCodes.Dup));
            il.Append(il.Create(OpCodes.Call, module.ImportReference(exists)));
            il.Append(il.Create(OpCodes.Stloc_0));
            il.Append(il.Create(OpCodes.Call, setBase));
            il.Append(il.Create(OpCodes.Ret));
            evaluate.Body.MaxStackSize = 2;

            insert.Invoke(null, new object[] { module, evaluate, unityCorePath });
            if (mutation == null)
            {
                verify.Invoke(null, new object[] { module, evaluate, unityCorePath });
                AssertExactAndroidMetadata(module, evaluate, unityCorePath);
            }
            else
            {
                var file = evaluate.Body.Instructions.Single(i => i.Operand is MethodReference call &&
                    call.DeclaringType.FullName == "System.IO.File" && call.Name == "Exists");
                var nonAndroid = file.Previous;
                var branch = evaluate.Body.Instructions.Single(i => i.OpCode == OpCodes.Bne_Un &&
                    i.Operand is Instruction target && Object.ReferenceEquals(target, nonAndroid));
                if (mutation == "android-false")
                {
                    var literal = branch.Next.Next.Next;
                    if (literal.OpCode != OpCodes.Ldc_I4_1) throw new InvalidOperationException("Android true arm changed");
                    literal.OpCode = OpCodes.Ldc_I4_0;
                    literal.Operand = null;
                }
                else if (mutation == "branch-invert") branch.OpCode = OpCodes.Beq;
                else if (mutation == "remove-probe") evaluate.Body.GetILProcessor().Remove(file);
                else throw new InvalidOperationException("unknown mutation " + mutation);
            }
            module.Write(outputPath);
        }
    }

    private static void AssertExactAndroidMetadata(ModuleDefinition module, MethodDefinition method, string unityCorePath)
    {
        var applicationCall = method.Body.Instructions.Single(i => i.Operand is MethodReference call &&
            call.DeclaringType.FullName == "UnityEngine.Application" && call.Name == "get_platform");
        var getter = (MethodReference)applicationCall.Operand;
        if (getter.HasThis || getter.Parameters.Count != 0 || getter.ReturnType.FullName != "UnityEngine.RuntimePlatform" ||
            !getter.ReturnType.IsValueType || getter.ReturnType.Scope.Name != "UnityEngine.CoreModule")
            throw new InvalidOperationException("injected call is not the exact CoreModule enum-returning platform getter");
        using (var core = AssemblyDefinition.ReadAssembly(unityCorePath))
        {
            var platform = core.MainModule.Types.Single(t => t.FullName == "UnityEngine.RuntimePlatform");
            var android = platform.Fields.Single(f => f.Name == "Android" && f.HasConstant);
            var branch = method.Body.Instructions.Single(i => i.OpCode == OpCodes.Bne_Un);
            if (!platform.IsEnum || !platform.IsValueType || Convert.ToInt32(android.Constant) != Convert.ToInt32(branch.Previous.Operand))
                throw new InvalidOperationException("branch literal does not match the pinned RuntimePlatform.Android enum value");
        }
        var file = method.Body.Instructions.Single(i => i.Operand is MethodReference call &&
            call.DeclaringType.FullName == "System.IO.File" && call.Name == "Exists");
        if (!Object.ReferenceEquals(file.Previous, branchTarget(method)) ||
            method.Body.Instructions.Count(i => i.Operand is MethodReference call &&
                call.DeclaringType.FullName == "AkBasePathGetter" && call.Name == "GetPlatformBasePath") != 1 ||
            method.Body.Instructions.Count(i => i.Operand is MethodReference call &&
                call.DeclaringType.FullName == "AkBasePathGetter" && call.Name == "set_SoundBankBasePath") != 1)
            throw new InvalidOperationException("non-Android File.Exists arm or unchanged base-path calculation missing");
        Console.WriteLine("PASS exact Android enum metadata and preserved non-Android File.Exists/base-path calls");
    }

    private static Instruction branchTarget(MethodDefinition method)
    {
        return (Instruction)method.Body.Instructions.Single(i => i.OpCode == OpCodes.Bne_Un).Operand;
    }

    private static CecilMethodBody Body(Action<ILProcessor, MethodDefinition> emit)
    {
        var module = ModuleDefinition.CreateModule("StackContractFixture", ModuleKind.Dll);
        var type = new TypeDefinition("Fixture", "Container", CecilTypeAttributes.Public | CecilTypeAttributes.Class,
            module.TypeSystem.Object);
        module.Types.Add(type);
        var method = new MethodDefinition("Synthetic", CecilMethodAttributes.Public | CecilMethodAttributes.Static,
            module.TypeSystem.Void);
        type.Methods.Add(method);
        emit(method.Body.GetILProcessor(), method);
        return method.Body;
    }

    private static void ExpectPass(string name, CecilMethodBody body)
    {
        Invoke(name, body, null);
    }

    private static void ExpectFail(string name, string expected, CecilMethodBody body)
    {
        Invoke(name, body, expected);
    }

    private static void Invoke(string name, CecilMethodBody body, string expectedFailure)
    {
        try
        {
            verifier.Invoke(null, new object[] { body.Method });
            if (expectedFailure != null) throw new InvalidOperationException(name + " unexpectedly passed");
        }
        catch (TargetInvocationException error)
        {
            var inner = error.InnerException;
            if (expectedFailure == null || inner == null || !inner.Message.Contains(expectedFailure))
                throw new InvalidOperationException(name + " had unexpected verifier result", inner);
        }
        Console.WriteLine("PASS " + name);
    }
}
"""


class OriginalAudioStackValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all(path.is_file() for path in (MONO, CSC, CECIL, UNITY_CORE)):
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn/Cecil/CoreModule unavailable")
        cls.source = PRODUCTION_SOURCE
        if not cls.source.is_file():
            raise AssertionError("composed Cecil transform source unavailable")
        text = cls.source.read_text(encoding="utf-8")
        if "VerifyStackHeights" not in text:
            raise AssertionError("stack verifier is missing from the production transform source")

        cls.work = OUTPUT_ROOT / ("pytest-" + uuid.uuid4().hex)
        cls.work.mkdir(parents=True, exist_ok=False)
        cls.transform = cls.work / "ComposedGameCecilTransform.exe"
        cls.fixture_source = cls.work / "StackContractFixture.cs"
        cls.fixture_source.write_text(SYNTHETIC_FIXTURE_SOURCE, encoding="utf-8")
        cls.fixture = cls.work / "StackContractFixture.exe"

        for label, output, source in (
            ("transform", cls.transform, cls.source),
            ("fixture", cls.fixture, cls.fixture_source),
        ):
            result = subprocess.run(
                [
                    str(MONO),
                    str(CSC),
                    "-nologo",
                    "-deterministic+",
                    "-target:exe",
                    "-r:" + str(CECIL),
                    "-out:" + str(output),
                    str(source),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            (cls.work / (label + ".compile.log")).write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                raise AssertionError(label + " compile failed: " + result.stdout + result.stderr)

    def test_actual_transform_stack_verifier_contracts(self) -> None:
        env = dict(os.environ)
        env["MONO_PATH"] = str(CECIL.parent)
        result = subprocess.run(
            [str(MONO), str(self.fixture), str(self.transform)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("six synthetic stack-contract cases passed", result.stdout)

    def test_actual_android_probe_injector_verifier_and_mutants(self) -> None:
        output = self.work / "android-probe"
        output.mkdir()
        env = dict(os.environ)
        env["MONO_PATH"] = str(CECIL.parent)
        fixture = subprocess.run(
            [str(MONO), str(self.fixture), str(self.transform), str(UNITY_CORE), str(output)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(fixture.returncode, 0, fixture.stdout + fixture.stderr)
        self.assertIn("PASS exact Android enum metadata", fixture.stdout)

        valid = subprocess.run(
            [str(MONO), str(self.transform), "validate-android-probe", str(output / "android-probe-valid.dll"), str(UNITY_CORE)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
        for mutation in ("android-false", "branch-invert", "remove-probe"):
            rejected = subprocess.run(
                [str(MONO), str(self.transform), "validate-android-probe", str(output / (mutation + ".dll")), str(UNITY_CORE)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(rejected.returncode, 2, mutation + ": " + rejected.stdout + rejected.stderr)


if __name__ == "__main__":
    unittest.main()
