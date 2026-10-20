"""Execute production effect-loan retirement owners against authored lifecycle contracts."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


def repo_root():
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/unity/runtime/stage/IntegratedStageBoundary.cs").is_file():
            return candidate
    raise AssertionError("Could not locate production stage/runtime owners")


ROOT = repo_root()
STAGE = ROOT / "tools/unity/runtime/stage/IntegratedStageBoundary.cs"
CLOCK = ROOT / "tools/unity/runtime/world/RunClockBoundary.cs"
REWARD = ROOT / "tools/unity/runtime/world/EnemyRewardBoundary.cs"
FIXTURE = Path(__file__).parent / "fixtures/native_effect_loan_return_lifecycle_host.cs"


def braced_block(source, declaration):
    lexical = re.compile(r"//[^\n]*|/\*.*?\*/|@\"(?:[^\"]|\"\")*\"|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.S)
    masked = lexical.sub(lambda match: " " * len(match.group()), source)
    start = source.index(declaration)
    opening = masked.index("{", start + len(declaration))
    depth = 0
    for end in range(opening, len(masked)):
        if masked[end] == "{":
            depth += 1
        elif masked[end] == "}":
            depth -= 1
            if depth == 0:
                return source[start : end + 1]
    raise AssertionError("Unclosed production block: " + declaration)


def production_host(stage_source=None, clock_source=None, reward_source=None):
    stage = STAGE.read_text() if stage_source is None else stage_source
    clock = CLOCK.read_text() if clock_source is None else clock_source
    reward = REWARD.read_text() if reward_source is None else reward_source
    methods = [
        braced_block(stage, signature)
        for signature in (
            "sealed class EffectLoanReturnBatch",
            "void CheckEffectLoanPoolOwnership(EffectLoanReturnBatch batch)",
            "EffectLoanReturnBatch BeginIntegratedStageEffectReturns()",
            "void CompleteIntegratedStageEffectReturns(EffectLoanReturnBatch batch)",
            "public void ReturnIntegratedStageEffects()",
            "public IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks()",
        )
    ]
    field = re.search(r"EffectLoanReturnBatch pendingEffectLoanReturns;", stage)
    reward_seam = re.search(
        r"            var asyncRelease = coordinator.ReleaseCompletedRunAsyncAssets\(\);\n"
        r"            while \(asyncRelease.MoveNext\(\)\)\n                yield return asyncRelease.Current;",
        reward,
    )
    transport_seam = re.search(
        r"            var effectReturns = ReturnIntegratedStageEffectsAfterNativeCallbacks\(\);\n"
        r"            while \(effectReturns.MoveNext\(\)\)\n                yield return effectReturns.Current;\n"
        r"            coordinator.ReleaseObjectiveOrbCache\(\);",
        stage,
    )
    if not field or not reward_seam or not transport_seam:
        raise AssertionError("Production retained-owner or coroutine caller seams changed")
    host = FIXTURE.read_text() + "\npublic partial class PortSession {\n"
    host += braced_block(stage, "IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks()") + "\n"
    host += braced_block(stage, "void ReturnIntegratedStageEffects()") + "\n"
    host += braced_block(clock, "IEnumerator ReleaseCompletedRunAsyncAssets()") + "\n"
    host += "public IEnumerator CleanupSeam(){var coordinator=this;\n" + reward_seam[0] + "\ndependentReleases++;}\n"
    host += "public IEnumerator TransportSeam(){var coordinator=this;\n" + transport_seam[0] + "\n}\n"
    host += "public IEnumerator SynchronousSeam(){ReturnIntegratedStageEffects();yield break;}\n"
    host += "public partial class IntegratedStageSession {\n" + field[0] + "\n" + "\n".join(methods) + "\n}\n"
    host += "public partial class RunClockSession {\n" + braced_block(clock, "public IEnumerator ReleaseCompletedRunAsyncAssets()") + "\n}\n}\n"
    return host


def compile_and_execute(source):
    editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
    mono = editor / "MonoBleedingEdge/bin/mono"
    compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    if not mono.is_file() or not compiler.is_file():
        raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn unavailable")
    with tempfile.TemporaryDirectory(prefix="native-effect-loan-return-") as temporary:
        scratch = Path(temporary).resolve()
        production = scratch / "NativeEffectLoanReturnHost.cs"
        executable = scratch / "NativeEffectLoanReturnHost.exe"
        pdb = scratch / "NativeEffectLoanReturnHost.pdb"
        reference = scratch / "NativeEffectLoanReturnHost.ref.dll"
        for path in (production, executable, pdb, reference):
            path.resolve().relative_to(scratch)
        production.write_text(source)
        environment = os.environ.copy()
        environment.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
        compiled = subprocess.run(
            [
                str(mono),
                str(compiler),
                "-nologo",
                "-langversion:9",
                "-target:exe",
                "-out:" + str(executable),
                "-debug:portable",
                "-pdb:" + str(pdb),
                "-refout:" + str(reference),
                str(production),
            ],
            cwd=scratch,
            env=environment,
            capture_output=True,
            text=True,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        if not all(path.is_file() for path in (executable, pdb, reference)):
            raise AssertionError("Explicit private compiler outputs missing")
        return subprocess.run([str(mono), str(executable)], cwd=scratch, env=environment, capture_output=True, text=True)


class NativeEffectLoanReturnLifecycleTests(unittest.TestCase):
    def test_actual_owners_wait_for_native_retirement_and_retain_unknown_owners(self):
        executed = compile_and_execute(production_host())
        self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
        self.assertIn("PASS: immediate/deferred/stuck/foreign/partial/interrupted/frame/transport", executed.stdout)

    def test_synchronous_guard_mutant_fails_the_deferred_native_contract(self):
        source = production_host()
        fence = braced_block(source, "public IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks()")
        mutant = source.replace(
            fence, "public IEnumerator ReturnIntegratedStageEffectsAfterNativeCallbacks() { ReturnIntegratedStageEffects(); yield break; }", 1
        )
        executed = compile_and_execute(mutant)
        self.assertNotEqual(executed.returncode, 0)
        self.assertIn("Owned stage effect loans survived original return callbacks", executed.stdout + executed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
