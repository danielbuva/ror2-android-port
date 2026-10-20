"""Host contracts for the bounded Toolbot readiness terminal observation."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "recipe" / "runtime-sources.json").is_file():
            return parent
    raise RuntimeError("could not find repository root from test location")


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


def method_body(source: str, signature: str) -> str:
    block = block_after(source, signature)
    opening = block.index("{")
    return block[opening + 1 : -1]


class ToolbotTerminalReadinessCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = find_repo_root(Path(__file__).resolve())
        source = Path(
            os.environ.get(
                "TOOLBOT_READINESS_SOURCE",
                root / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs",
            )
        )
        cls.source = source.read_text(encoding="utf-8")

    def test_production_header_keeps_first_refusal_and_captures_terminal_once(self) -> None:
        compiler = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe")
        mono = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/bin/mono")
        if not compiler.is_file() or not mono.is_file():
            self.skipTest("pinned Unity Mono/Roslyn host compiler is unavailable")

        machine_observation = block_after(
            self.source,
            "public sealed class ToolbotReadinessMachineObservation",
        )
        observation = block_after(self.source, "public sealed class ToolbotReadinessObservation")
        availability = method_body(self.source, "public static string ToolbotObjectAvailability(")
        header = method_body(
            self.source,
            "public static bool BeginToolbotReadinessCaptureHeader(",
        )
        harness = f"""using System;
[Serializable]
{machine_observation}
[Serializable]
{observation}
public static class ProductionCapture
{{
    public static string ToolbotObjectAvailability(bool referenceIsNull, bool unityObjectAlive)
    {{{availability}
    }}
    public static bool BeginToolbotReadinessCaptureHeader(ToolbotReadinessObservation observation,
        int phase, float elapsedSeconds, string outcome, int frameCount, float fixedTime, string clockStatus)
    {{{header}
    }}
}}
public static class Program
{{
    static void Need(bool condition, string message)
    {{ if (!condition) throw new Exception(message); }}
    public static int Main()
    {{
        Need(ProductionCapture.ToolbotObjectAvailability(true, false) == "null",
            "actual null must remain distinguishable");
        Need(ProductionCapture.ToolbotObjectAvailability(false, false) == "destroyed-fake-null",
            "destroyed Unity wrapper must be identified as fake-null");
        Need(ProductionCapture.ToolbotObjectAvailability(false, true) == "available",
            "live Unity wrapper should be available");

        var firstRefusal = new ToolbotReadinessObservation();
        Need(ProductionCapture.BeginToolbotReadinessCaptureHeader(firstRefusal, 3, 0.3597f,
            "phase-3-first-refusal", 120, 0.34f, "available"),
            "first refusal should capture once");
        Need(!ProductionCapture.BeginToolbotReadinessCaptureHeader(firstRefusal, 3, 8.353f,
            "terminal:offhand-secondary-not-native-ready", 600, 8.32f, "available"),
            "terminal capture must not overwrite historical first refusal");
        Need(firstRefusal.captureCount == 1 && firstRefusal.phase == 3 &&
             firstRefusal.outcome == "phase-3-first-refusal" && firstRefusal.elapsedSeconds == 0.3597f,
            "first-refusal snapshot changed after terminal attempt");

        var terminal = new ToolbotReadinessObservation();
        Need(ProductionCapture.BeginToolbotReadinessCaptureHeader(terminal, 3, 8.353f,
            "terminal:offhand-secondary-not-native-ready", 600, 8.32f, "available"),
            "terminal observation should capture once");
        Need(!ProductionCapture.BeginToolbotReadinessCaptureHeader(terminal, 4, 8.4f,
            "duplicate-terminal", 601, 8.34f, "available"),
            "duplicate terminal capture must be refused");
        Need(terminal.captureCount == 1 && terminal.phase == 3 &&
             terminal.outcome == "terminal:offhand-secondary-not-native-ready" &&
             terminal.elapsedSeconds == 8.353f && terminal.frameCount == 600 &&
             terminal.fixedTime == 8.32f && terminal.clockStatus == "available",
            "terminal timestamp/phase/outcome must remain stable");
        return 0;
    }}
}}
"""
        with tempfile.TemporaryDirectory(prefix="toolbot-terminal-readiness-") as temp_dir:
            temp = Path(temp_dir)
            source = temp / "TerminalReadinessExtracted.cs"
            assembly = temp / "TerminalReadinessExtracted.exe"
            source.write_text(harness, encoding="utf-8")
            subprocess.run(
                [str(mono), str(compiler), "-noconfig", f"-out:{assembly}", str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [str(mono), str(assembly)],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_terminal_capture_is_toolbot_only_and_does_not_change_native_gates(self) -> None:
        source = self.source
        self.assertEqual(source.count("new ToolbotReadinessObservation()"), 4)
        initialization = block_after(source, "if (toolbotOffhandMode)")
        self.assertIn("toolbotReadinessAtTerminal = new ToolbotReadinessObservation()", initialization)
        stop = block_after(source, "void StopToolbotOffhand(string outcome)")
        self.assertIn("report.toolbotReadinessAtStop", stop)
        self.assertIn("report.toolbotReadinessAtTerminal", stop)
        self.assertIn('"terminal:" + (outcome ?? "unknown")', stop)
        self.assertIn(
            "if (secondary && secondary.enabled && secondary.skillDef && secondary.CanExecute())",
            source,
        )
        self.assertIn('report.toolbotOffhandPhase == 3 ? "offhand-secondary-not-native-ready"', source)
        capture = block_after(source, "void CaptureToolbotReadinessSnapshot(")
        self.assertLess(
            capture.index("if (observation == null || observation.captured)"),
            capture.index("Time.frameCount"),
        )
        machine = block_after(source, "public sealed class ToolbotReadinessMachineObservation")
        self.assertNotIn("frameCount", machine)
        self.assertNotIn("clockStatus", machine)

    def test_machine_capture_uses_only_public_read_operands_and_marks_pending_type_unavailable(self) -> None:
        capture = block_after(self.source, "ToolbotReadinessMachineObservation CaptureToolbotReadinessMachine(")
        for operand in (
            "machine.enabled",
            "machine.gameObject.activeSelf",
            "machine.gameObject.activeInHierarchy",
            "machine.ShouldStateTransitionOnUpdate",
            "machine.IsPendingMainState()",
            "machine.networkIndex",
            "machine.networker",
            "networker.hasAuthority",
            'pendingTargetTypeStatus = "unavailable-no-public-api"',
        ):
            with self.subTest(operand=operand):
                self.assertIn(operand, capture)
        self.assertNotIn("GetField(", capture)
        self.assertNotIn("BindingFlags", capture)

    def test_terminal_and_first_refusal_slots_remain_distinct_and_default_off(self) -> None:
        source = self.source
        self.assertIn("CaptureToolbotReadinessSnapshot(report.toolbotReadinessAtStop", source)
        self.assertIn("phase-3-secondary-native-readiness-refusal", source)
        self.assertIn("CaptureToolbotReadinessSnapshot(report.toolbotReadinessAtTerminal", source)
        self.assertIn('"terminal:" + (outcome ?? "unknown")', source)
        self.assertIn("toolbotOffhandRequested = toolbotOffhandMode", source)
        self.assertIn("if (toolbotOffhandMode)\n        {\n            report.toolbotReadinessBeforeSpecial", source)


if __name__ == "__main__":
    unittest.main()
