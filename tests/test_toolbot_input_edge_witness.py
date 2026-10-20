import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO_ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "tools/unity/runtime/input/NovaInputBridge.cs").is_file())
DRAFT_ROOT = next((parent for parent in Path(__file__).resolve().parents if (parent / "source/tools/unity/runtime/input/NovaInputBridge.cs").is_file()), None)
SOURCE_ROOT = DRAFT_ROOT / "source" if DRAFT_ROOT else REPO_ROOT
BRIDGE = SOURCE_ROOT / "tools/unity/runtime/input/NovaInputBridge.cs"
OWNER = SOURCE_ROOT / "tools/unity/runtime/input/SurvivorSkillInputCoverage.cs"
UNITY = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))


def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("unbalanced method: " + signature)


class InputEdgeWitness(unittest.TestCase):
    def setUp(self):
        self.bridge = BRIDGE.read_text()
        self.owner = OWNER.read_text()

    def test_fixed_sink_counts_only_the_edges_it_just_pushed(self):
        fixed = method(self.bridge, "void FixedUpdate()")
        for slot, member in enumerate(("skill1", "skill2", "skill3", "skill4")):
            push = fixed.index(f"bank.{member}.PushState(")
            count = fixed.index(f"diagnosticInputEdgeCounts[{slot}] = AdvanceDiagnosticInputEdgeCount", push)
            self.assertGreater(count, push)
            self.assertLess(fixed.index(f"bank.{member}.justPressed", count), fixed.index("fixedTicks++;", count))
        self.assertIn("diagnosticInputEdgeWitnessEnabled", self.bridge)
        self.assertIn("ownedBridge.SetDiagnosticInputEdgeWitness(true)", self.owner)
        self.assertIn("bridge.SetDiagnosticInputEdgeWitness(false)", method(self.owner, "void StopToolbotOffhand(string outcome)"))
        self.assertIn("bridge.SetDiagnosticInputEdgeWitness(false)", method(self.owner, "public void Dispose()"))

    def test_offhand_snapshots_each_request_and_keeps_ordinary_observation_unchanged(self):
        begin = method(self.owner, "bool BeginToolbotPulse(int slot, float elapsed)")
        self.assertLess(begin.index("TryGetDiagnosticInputEdgeCount"), begin.index("isolatedDiagnosticSkillPulse = true"))
        observe = method(self.owner, "bool ObserveInputBankEdge()")
        self.assertIn("bridge.fixedTicks > toolbotPulseStartTick", observe)
        self.assertIn("if (toolbotOffhandMode)", observe)
        self.assertIn("bank.skill4.justPressed", observe)
        self.assertIn("toolbotPulseEdgeBaseline = count", observe)
        self.assertIn('"toolbot-input-edge-counter-reset"', observe)
        self.assertIn('"multiple-toolbot-input-edges-for-pulse"', observe)
        offhand = method(self.owner, "void ApplyToolbotOffhand(float elapsed)")
        self.assertLess(offhand.index("inputNeutralRevision != lastNeutralRevision"), offhand.index("ObserveInputBankEdge()"))
        self.assertIn('StopToolbotOffhand("neutralized-request-cancelled")', offhand)
        self.assertIn("bridge.isolatedDiagnosticSkillPulse = false", method(self.owner, "void StopToolbotOffhand(string outcome)"))
        constructor = method(self.owner, "public SurvivorSkillInputCoverage(")
        self.assertRegex(
            constructor, r"if \(toolbotOffhandMode\)\s*\{\s*CaptureToolbotOffhandIdentity\(\);\s*ownedBridge.SetDiagnosticInputEdgeWitness\(true\)"
        )

    @unittest.skipUnless(
        (UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe").is_file() and (UNITY / "MonoBleedingEdge/bin/mono").is_file(),
        "pinned Unity Mono compiler/runtime unavailable",
    )
    def test_extracted_production_witness_survives_late_sampling_and_refuses_bad_deltas(self):
        bridge_helper = method(self.bridge, "public static long AdvanceDiagnosticInputEdgeCount(")
        enum = re.search(r"public enum DiagnosticInputEdgeStatus\s*\{[^}]+\}", self.owner).group(0)
        classifier = method(self.owner, "public static DiagnosticInputEdgeStatus ClassifyDiagnosticInputEdge(")
        harness = r"""using System;
public static class Program
{
    ENUM
    BRIDGE_HELPER
    OWNER_HELPER
    struct ButtonState
    {
        public bool down, wasDown;
        public bool justPressed => down && !wasDown;
        public void PushState(bool next) { wasDown = down; down = next; }
    }
    static void Need(bool ok, string why) { if (!ok) throw new Exception(why); }
    public static void Main()
    {
        long count = 0;
        bool enabled = true;
        var button = new ButtonState();
        long requestBaseline = count;
        button.PushState(true);
        count = AdvanceDiagnosticInputEdgeCount(count, enabled, button.justPressed);
        Need(count == 1, "real rising edge counted once at the sink");
        for (int fixedTick = 0; fixedTick < 4; fixedTick++)
        {
            button.PushState(true);
            count = AdvanceDiagnosticInputEdgeCount(count, enabled, button.justPressed);
        }
        Need(!button.justPressed, "native justPressed is frame-volatile after repeated PushState");
        Need(ClassifyDiagnosticInputEdge(requestBaseline, count, true) == DiagnosticInputEdgeStatus.Fresh,
             "late observer still sees the one new sink edge");
        requestBaseline = count;
        Need(ClassifyDiagnosticInputEdge(requestBaseline, count, true) == DiagnosticInputEdgeStatus.None,
             "accepted edge is not counted twice");
        Need(ClassifyDiagnosticInputEdge(requestBaseline, count, false) == DiagnosticInputEdgeStatus.None,
             "same-tick observation is not fresh");

        long staleBaseline = count;
        Need(ClassifyDiagnosticInputEdge(staleBaseline, count, true) == DiagnosticInputEdgeStatus.None,
             "pre-request/stale edge is excluded by the request snapshot");
        Need(ClassifyDiagnosticInputEdge(staleBaseline, staleBaseline - 1, true) == DiagnosticInputEdgeStatus.CounterReset,
             "counter reset/drift refuses");
        Need(ClassifyDiagnosticInputEdge(staleBaseline, staleBaseline + 2, true) == DiagnosticInputEdgeStatus.Multiple,
             "ambiguous multiple new edges refuse");
        Need(ClassifyDiagnosticInputEdge(staleBaseline, staleBaseline + 1, true, true) == DiagnosticInputEdgeStatus.Multiple,
             "second fresh edge in a later sample of the same pulse refuses");
        Need(ClassifyDiagnosticInputEdge(-1, 0, true) == DiagnosticInputEdgeStatus.CounterReset,
             "invalid baseline refuses before computing a delta");
        Need(AdvanceDiagnosticInputEdgeCount(count, false, true) == count,
             "disabled witness does not count physical/ordinary traffic");
        button.PushState(false);
        Need(!button.justPressed && AdvanceDiagnosticInputEdgeCount(count, enabled, button.justPressed) == count,
             "neutral release cannot create an edge");
        Need(AdvanceDiagnosticInputEdgeCount(long.MaxValue, enabled, true) == long.MaxValue,
             "counter saturation stays monotonic and fails closed");
        Console.WriteLine("production input-edge witness passed");
    }
}"""
        harness = harness.replace("ENUM", enum).replace("BRIDGE_HELPER", bridge_helper).replace("OWNER_HELPER", classifier)
        with tempfile.TemporaryDirectory(prefix="toolbot-input-edge-") as temp:
            temp = Path(temp)
            source, exe = temp / "Harness.cs", temp / "harness.exe"
            source.write_text(harness)
            runtime = UNITY / "MonoBleedingEdge/bin/mono"
            compiler = UNITY / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
            compiled = subprocess.run(
                [str(runtime), str(compiler), "-nologo", "-out:" + str(exe), str(source)], cwd=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            run = subprocess.run([str(runtime), str(exe)], cwd=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("production input-edge witness passed", run.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
