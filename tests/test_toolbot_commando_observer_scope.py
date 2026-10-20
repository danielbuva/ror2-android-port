"""Exercise the production Commando-body policy and its diagnostic consumers."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def repo_root():
    explicit = os.environ.get("TOOLBOT_SCOPE_SOURCE_ROOT")
    if explicit:
        return Path(explicit).resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/unity/runtime/world/PrimaryFireBoundary.cs").is_file():
            return candidate
    raise AssertionError("Could not locate production source root")


ROOT = repo_root()
PRIVATE = ROOT / "work/host-tests/toolbot-commando-observer-scope"
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def extract_member(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("Unclosed production member: " + declaration)


class ToolbotCommandoObserverScopeTests(unittest.TestCase):
    def test_production_body_policy_and_consumers(self):
        primary = (ROOT / "tools/unity/runtime/world/PrimaryFireBoundary.cs").read_text(encoding="utf-8")
        nova = (ROOT / "tools/unity/runtime/input/NovaInputBoundary.cs").read_text(encoding="utf-8")
        policy = extract_member(primary, "internal static bool IsCommandoPrimaryDiagnosticBody(")
        self.assertIn('BodyCatalog.FindBodyIndex("CommandoBody")', policy)
        self.assertIn("expected != BodyIndex.None", policy)
        self.assertIn("body.bodyIndex == expected", policy)
        self.assertIn("bool commandoPrimaryDiagnostic = spine && IsCommandoPrimaryDiagnosticBody(body);", nova)
        self.assertIn("if (commandoPrimaryDiagnostic)\n                        coordinator.ObserveSpinePrimary(body);", nova)
        self.assertIn("if (commandoPrimaryDiagnostic)\n                    coordinator.Check(coordinator.r.primary.shots > 0", nova)
        self.assertIn("r.nova.commandoPrimaryDiagnostic && r.primary != null", nova)
        self.assertIn("public bool commandoPrimaryDiagnostic;", nova)
        self.assertIn("commandoPrimaryDiagnostic = commandoPrimaryDiagnostic", nova)

        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler is unavailable")
        fixture = (Path(__file__).resolve().parent / "fixtures/toolbot_commando_observer_scope_host.cs").read_text(encoding="utf-8")
        stubs = r"""
using RoR2;
namespace RoR2
{
    public enum BodyIndex { None, Commando, Toolbot, Other }
    public sealed class CharacterBody
    {
        public BodyIndex bodyIndex;
        public bool primaryMissing;
        public static implicit operator bool(CharacterBody body) => !System.Object.ReferenceEquals(body, null);
    }
    public static class BodyCatalog
    {
        public static BodyIndex FindBodyIndex(string name) => name == "CommandoBody" ? BodyIndex.Commando : BodyIndex.None;
    }
}
public sealed class CommandoPrimaryScopeHarness
{
    public int commandoObserverCalls, readinessReads, hudPrimaryReads, genericCoverageTicks;
    __POLICY__
    public void Update(bool playableSpine, RoR2.CharacterBody body)
    {
        genericCoverageTicks++;
        bool commandoPrimaryDiagnostic = playableSpine && IsCommandoPrimaryDiagnosticBody(body);
        if (commandoPrimaryDiagnostic)
        {
            commandoObserverCalls++;
            if (body.primaryMissing) throw new System.InvalidOperationException("strict missing primary");
            readinessReads++;
            hudPrimaryReads++;
        }
    }
}
public static class Program
{
    public static void Main() { ObserverScopeHost.Run(); }
}
""".replace("__POLICY__", policy)
        PRIVATE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="commando-scope-", dir=PRIVATE) as directory:
            scratch = Path(directory).resolve()
            source = scratch / "Scope.cs"
            output = scratch / "Scope.exe"
            pdb = scratch / "Scope.pdb"
            refout = scratch / "Scope.ref.dll"
            source.write_text(stubs + "\n" + fixture, encoding="utf-8")
            for path in (source, output, pdb, refout):
                path.resolve().relative_to(scratch)
            environment = os.environ.copy()
            environment.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
            compiled = subprocess.run(
                [
                    str(mono),
                    str(csc),
                    "-nologo",
                    "-langversion:9",
                    "-target:exe",
                    "-out:" + str(output),
                    "-debug:portable",
                    "-pdb:" + str(pdb),
                    "-refout:" + str(refout),
                    str(source),
                ],
                cwd=scratch,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            self.assertTrue(output.is_file() and pdb.is_file() and refout.is_file())
            ran = subprocess.run([str(mono), str(output)], cwd=scratch, env=environment, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertEqual(ran.stdout.strip(), "PASS: Commando primary observer scope")


if __name__ == "__main__":
    unittest.main()
