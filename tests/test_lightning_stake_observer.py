"""Exercise extracted production LightningStake observation policy with host doubles."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def repo_root():
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/unity/runtime/world/LightningStakeDiagnosticObserver.cs").is_file():
            return candidate
    raise AssertionError("Could not locate repository root from test path")


ROOT = repo_root()
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")


def extract_block(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise AssertionError("Production declaration does not close: " + declaration)


def production_host():
    source = (ROOT / "tools/unity/runtime/world/LightningStakeDiagnosticObserver.cs").read_text(encoding="utf-8")
    policy = extract_block(source, "public sealed class LightningStakeSamplingPolicy : IDisposable")
    retirement = extract_block(source, "void RetireTrackedAt(int index)")
    fixture = (ROOT / "tests/fixtures/lightning_stake_observer_host.cs").read_text(encoding="utf-8")
    return (
        "using System;\nusing System.Collections.Generic;\n"
        + policy
        + "\n"
        + fixture.replace("__EXTRACTED_RETIREMENT_METHOD__", retirement)
    )


class LightningStakeObserverContracts(unittest.TestCase):
    def test_recycling_caps_first_transition_and_disposal(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory).resolve()
            source = scratch / "LightningStakeObserverHost.cs"
            output = scratch / "LightningStakeObserverHost.exe"
            pdb = scratch / "LightningStakeObserverHost.pdb"
            refout = scratch / "LightningStakeObserverHost.ref.dll"
            source.write_text(production_host(), encoding="utf-8")
            for path in (source, output, pdb, refout):
                try:
                    path.resolve().relative_to(scratch)
                except ValueError:
                    self.fail("host compiler input/output escaped private path: " + str(path.resolve()))

            environment = os.environ.copy()
            environment.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
            compiled = subprocess.run(
                [
                    str(mono), str(csc), "-nologo", "-langversion:9", "-target:exe",
                    "-out:" + str(output), "-debug:portable", "-pdb:" + str(pdb),
                    "-refout:" + str(refout), str(source),
                ],
                cwd=scratch,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            self.assertTrue(output.is_file() and pdb.is_file() and refout.is_file())
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, env=environment,
                                      capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout.strip(), "PASS: rolling observer policy contracts")


if __name__ == "__main__":
    unittest.main()
