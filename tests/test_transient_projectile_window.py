"""Compile and execute the exact production timing policy with scalar host contracts."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
SOURCE = HERE / "tools/unity/runtime/world/SurvivorCombatOutputObserver.cs"
FIXTURE = HERE / "tests/fixtures/TransientProjectileWindowHost.cs"


def extract_class(source: str, declaration: str) -> str:
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
    raise AssertionError("Unclosed production helper: " + declaration)


class TransientProjectileWindowContracts(unittest.TestCase):
    def test_extracted_production_policy(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("Pinned Unity Roslyn/Mono is unavailable")
        policy = extract_class(SOURCE.read_text(encoding="utf-8"), "public sealed class TransientProjectileWindowSchedule")
        fixture = FIXTURE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="host-") as temporary:
            scratch = Path(temporary).resolve()
            source = scratch / "TransientProjectileWindowHost.cs"
            output = scratch / "TransientProjectileWindowHost.exe"
            pdb = scratch / "TransientProjectileWindowHost.pdb"
            refout = scratch / "TransientProjectileWindowHost.ref.dll"
            source.write_text("using System;\n" + policy + "\n" + fixture, encoding="utf-8")
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
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, env=environment, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout.strip(), "PASS: transient projectile window policy contracts")


if __name__ == "__main__":
    unittest.main()
