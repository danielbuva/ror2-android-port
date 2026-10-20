"""Host contracts for the Toolbot offhand readiness observation."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "recipe" / "runtime-sources.json").is_file():
            return parent
    raise RuntimeError("could not find repository root from test location")


def method_body(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unclosed method: {signature}")


def member_after(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed member: {marker}")


def block_after(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed block: {marker}")


class ToolbotReadinessObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = find_repo_root(Path(__file__).resolve())
        owner = root / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
        cls.source = owner.read_text(encoding="utf-8")

    def test_snapshots_are_fixed_and_toolbot_only(self) -> None:
        source = self.source
        self.assertEqual(source.count("new ToolbotReadinessObservation()"), 3)
        self.assertIn(
            "if (toolbotOffhandMode)\n        {\n            report.toolbotReadinessBeforeSpecial",
            source,
        )
        capture = method_body(source, "void CaptureToolbotReadinessSnapshot(")
        self.assertIn("if (observation == null || observation.captured)\n            return;", capture)
        self.assertIn("observation.captured = true;", capture)
        self.assertIn("observation.captureCount = 1;", capture)
        for snapshot in (
            "toolbotReadinessBeforeSpecial",
            "toolbotReadinessAfterOverride",
            "toolbotReadinessAtStop",
        ):
            self.assertIn(f"CaptureToolbotReadinessSnapshot(report.{snapshot}", source)
        self.assertIn("phase-3-secondary-native-readiness-refusal", source)

    def test_snapshot_records_native_operands_and_exception_statuses(self) -> None:
        capture = method_body(self.source, "void CaptureToolbotReadinessSnapshot(")
        for operand in (
            "secondary.enabled",
            "secondary.stock",
            "skillDef.requiredStock",
            "secondary.IsReady()",
            "secondary.CanExecute()",
            "skillDef.IsReady(secondary)",
            "skillDef.CanExecute(secondary)",
            "secondary.CalculateFinalRechargeInterval()",
            "skillDef.activationStateMachineName",
            "secondary.stateMachine",
            '"Weapon", "Weapon"',
            '"Weapon2", "Weapon2"',
        ):
            with self.subTest(operand=operand):
                self.assertIn(operand, capture)
        self.assertIn('"unavailable"', capture)
        self.assertIn("ToolbotObservationException(exception)", capture)
        machine = method_body(
            self.source,
            "ToolbotReadinessMachineObservation CaptureToolbotReadinessMachine(",
        )
        for operand in (
            "GetInstanceID()",
            "machine.customName",
            "machine.state",
            "HasPendingState()",
            "CanInterruptState(interruptPriority)",
        ):
            with self.subTest(operand=operand):
                self.assertIn(operand, machine)
        self.assertIn("observation.availability = ToolbotObservationException(exception);", machine)
        self.assertIn("configuredMachineName = skillDef.activationStateMachineName", capture)
        self.assertIn("secondary ? secondary.stateMachine : null, null", self.source)
        self.assertIn('CaptureNamedToolbotReadinessMachine("Weapon", "Weapon"', capture)
        self.assertIn('CaptureNamedToolbotReadinessMachine("Weapon2", "Weapon2"', capture)

    def test_extracted_production_resolver_handles_null_fake_null_and_empty_name(self) -> None:
        compiler = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")
        mono = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
        if not compiler.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")

        resolver = member_after(
            self.source,
            "static EntityStateMachine ResolveToolbotReadinessMachine(",
        )
        machine_capture = method_body(
            self.source,
            "ToolbotReadinessMachineObservation CaptureToolbotReadinessMachine(",
        )
        self.assertIn('availability = machine ? "available" : "unavailable"', machine_capture)
        wrapper = f"""using System;
namespace UnityEngine {{
    public class Object {{
        public bool destroyed;
        public static implicit operator bool(Object value) => value != null && !value.destroyed;
    }}
}}
public sealed class EntityStateMachine : UnityEngine.Object {{ public string customName; }}
public static class ProductionCaptureHelper {{
    {resolver}
    public static EntityStateMachine Invoke(EntityStateMachine direct, Func<EntityStateMachine> lookup) =>
        ResolveToolbotReadinessMachine(direct, lookup);
}}
public static class Program {{
    static void Require(bool condition, string message) {{
        if (!condition) throw new Exception(message);
    }}
    public static int Main() {{
        var unrelatedEmptyNameMachine = new EntityStateMachine {{ customName = "" }};
        bool lookupCalled = false;
        Func<EntityStateMachine> emptyNameLookup = () => {{
            lookupCalled = true;
            return unrelatedEmptyNameMachine;
        }};
        var unresolved = ProductionCaptureHelper.Invoke(null, null);
        Require(unresolved == null && !lookupCalled,
            "null resolved target must not search for an empty-name machine");
        var fakeNull = new EntityStateMachine {{ destroyed = true, customName = "" }};
        var unresolvedFakeNull = ProductionCaptureHelper.Invoke(fakeNull, null);
        Require(unresolvedFakeNull == null && !lookupCalled,
            "fake-null target must remain unavailable without name lookup");
        var direct = new EntityStateMachine {{ customName = "Weapon2" }};
        var selectedDirect = ProductionCaptureHelper.Invoke(direct, emptyNameLookup);
        Require(Object.ReferenceEquals(direct, selectedDirect) && !lookupCalled,
            "direct resolved target takes precedence");
        var selectedNamed = ProductionCaptureHelper.Invoke(null, emptyNameLookup);
        Require(Object.ReferenceEquals(unrelatedEmptyNameMachine, selectedNamed) && lookupCalled,
            "explicit name lookup callback remains usable");
        return 0;
    }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="toolbot-readiness-", dir=Path(__file__).resolve().parent) as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "ResolverExtracted.cs"
            assembly_path = temp / "ResolverExtracted.exe"
            source_path.write_text(wrapper, encoding="utf-8")
            subprocess.run(
                [str(mono), str(compiler), "-noconfig", f"-out:{assembly_path}", str(source_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [str(mono), str(assembly_path)],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_native_gate_is_frozen_and_capture_helpers_do_not_mutate_gameplay(self) -> None:
        gate = "if (secondary && secondary.enabled && secondary.skillDef && secondary.CanExecute())"
        self.assertIn(gate, self.source)
        capture = method_body(self.source, "void CaptureToolbotReadinessSnapshot(")
        named_machine = method_body(
            self.source,
            "ToolbotReadinessMachineObservation CaptureNamedToolbotReadinessMachine(",
        )
        self.assertIn("FindByCustomName(body.gameObject, customName)", named_machine)
        self.assertNotIn('FindByCustomName(body.gameObject, "")', self.source)
        machine = method_body(
            self.source,
            "ToolbotReadinessMachineObservation CaptureToolbotReadinessMachine(",
        )
        resolver = method_body(
            self.source,
            "static EntityStateMachine ResolveToolbotReadinessMachine(",
        )
        observation = capture + named_machine + machine + resolver
        for forbidden in (
            "SetNextState(",
            "SetSkillOverride(",
            "secondary.stock =",
            "secondary.rechargeStopwatch =",
            "secondary.enabled =",
            "secondary.stateMachine =",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, observation)


if __name__ == "__main__":
    unittest.main()
