"""Execute the actual native teardown branches against independent ownership contracts."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


def repo_root():
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/unity/runtime/stage/TeleporterWorldBoundary.cs").is_file():
            return candidate
    raise AssertionError("Could not locate the production runtime owners")


ROOT = repo_root()
TELEPORTER = ROOT / "tools/unity/runtime/stage/TeleporterWorldBoundary.cs"
INTEGRATED = ROOT / "tools/unity/runtime/world/IntegratedWorldBoundary.cs"
SESSION = ROOT / "tools/unity/runtime/session/PortSession.cs"
FIXTURE = Path(__file__).parent / "fixtures/native_commerce_release_order_host.cs"
NATIVE = "if (coordinator.r.nativeFirstStageLifecycleDiagnosticAttempt)"


def braced_block(source, declaration):
    # Preserve offsets while excluding braces inside C# comments and literals.
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
    raise AssertionError("Production block does not close: " + declaration)


def production_host(teleporter_source=None, integrated_source=None):
    teleporter_source = TELEPORTER.read_text() if teleporter_source is None else teleporter_source
    integrated_source = INTEGRATED.read_text() if integrated_source is None else integrated_source
    owner = braced_block(teleporter_source, "sealed class TeleporterWorldSession : IDisposable")
    dispose = braced_block(owner, "public void Dispose()")
    native_dispose = braced_block(dispose, NATIVE)
    # Keep the real support tail, including its order, rather than retyping calls
    # in the host double. Unrelated Unity subscription/resource code is outside
    # this deliberately small extraction seam.
    tail = re.search(
        r"(?m)^[ \t]*ObserveObjectiveSupport\(true\);[ \t]*\n"
        r"[ \t]*CleanupObjectiveEffects\(\);[ \t]*\n"
        r"[ \t]*CleanupObjectiveSupport\(\);",
        dispose,
    )
    if tail is None:
        raise AssertionError("Production objective-support teardown seam changed")
    integrated = braced_block(integrated_source, "public void CleanupIntegratedWorld()")
    native_integrated = braced_block(integrated, NATIVE)
    return (
        FIXTURE.read_text()
        + "\npublic sealed partial class Coordinator {\n"
        + braced_block(SESSION.read_text(), "internal long MarkSourceStageLifecycleRecovery(bool required)")
        + "\n}\n"
        + "\npublic sealed partial class TeleporterWorldSession {\npublic void Dispose() {\n"
        + native_dispose
        + "\n"
        + tail.group()
        + "\n}\n}\n"
        + "public sealed partial class IntegratedWorldSession {\npublic void CleanupIntegratedWorld() {\n"
        + native_integrated
        + "\n}\n}\n"
    )


def compile_and_execute(source, arguments=()):
    editor = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents"))
    mono = editor / "MonoBleedingEdge/bin/mono"
    compiler = editor / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    if not mono.is_file() or not compiler.is_file():
        raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn toolchain is unavailable")
    with tempfile.TemporaryDirectory(prefix="native-commerce-release-order-") as temporary:
        scratch = Path(temporary).resolve()
        production = scratch / "NativeCommerceReleaseOrderHost.cs"
        executable = scratch / "NativeCommerceReleaseOrderHost.exe"
        pdb = scratch / "NativeCommerceReleaseOrderHost.pdb"
        reference = scratch / "NativeCommerceReleaseOrderHost.ref.dll"
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
            raise AssertionError("Compiler did not produce the explicit private outputs")
        return subprocess.run([str(mono), str(executable), *arguments], cwd=scratch, env=environment, capture_output=True, text=True)


class NativeCommerceReleaseOrderTests(unittest.TestCase):
    def test_actual_native_owners_reconcile_before_releasing_support(self):
        executed = compile_and_execute(production_host())
        self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
        self.assertEqual(
            json.loads(executed.stdout),
            {
                "normal_purchase": True,
                "no_purchase": True,
                "unexpected_extra_retained": True,
                "source_retirement_failure_retained": True,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
