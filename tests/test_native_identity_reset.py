"""Execute the production identity rollback method against authored HLAPI doubles."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
SOURCE = ROOT / "tools/unity/runtime/stage/SourceStageIdentityLifecycle.cs"
FIXTURE = Path(__file__).parent / "fixtures/native_identity_reset_host.cs"


def source_method(source, declaration):
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
    raise AssertionError("Production method does not close: " + declaration)


def production_host():
    source = SOURCE.read_text()
    rollback = source_method(source, "void RollbackOwnedIdentities()")
    if "state.hasRegisteredId && state.identity.netId == state.registeredId" not in rollback:
        raise AssertionError("Rollback must reset the exact captured ID after HLAPI UnSpawn")
    if "state.identity.isServer || state.identity.isClient" not in rollback:
        raise AssertionError("Rollback must refuse residual native identity flags")
    return FIXTURE.read_text() + "\npublic partial class RollbackHarness {\n" + rollback + "\n}\n"


class NativeIdentityResetTests(unittest.TestCase):
    def test_production_rollback_with_host_ordered_hlapi_stub(self):
        mono = EDITOR / "bin/mono"
        csc = EDITOR / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not csc.exists():
            self.skipTest("matching Unity Mono compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="native-identity-reset-") as directory:
            scratch = Path(directory)
            source = scratch / "NativeIdentityResetHost.cs"
            output = scratch / "NativeIdentityResetHost.exe"
            source.write_text(production_host())
            compiled = subprocess.run(
                [str(mono), str(csc), "-nologo", "-langversion:9", "-out:" + str(output), str(source)],
                cwd=scratch,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(mono), str(output)], cwd=scratch, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertEqual(
                json.loads(executed.stdout),
                {
                    "success_reset": True,
                    "repeat_cleanup": True,
                    "foreign_remap_refused": True,
                    "changed_id_refused": True,
                    "ineffective_reset_refused": True,
                    "residual_flags_refused": True,
                    "active_restore_ordered": True,
                    "all_passed": True,
                },
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
