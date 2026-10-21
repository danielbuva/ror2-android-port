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
MONO_DIR = UNITY_CONTENTS / "MonoBleedingEdge"
MONO = MONO_DIR / "bin/mono"
CSC = MONO_DIR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = MONO_DIR / "lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
OUTPUT_ROOT = ROOT / "work/coordination/original-audio-async-bank-il-fix/r2/portable-test"


SYNTHETIC_FIXTURE_SOURCE = r"""
using System;
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
        return 0;
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
        if not all(path.is_file() for path in (MONO, CSC, CECIL)):
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn/Cecil unavailable")
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


if __name__ == "__main__":
    unittest.main()
