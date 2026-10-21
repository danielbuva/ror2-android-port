from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
EDITOR_CONTENTS = Path(
    os.environ.get(
        "UNITY_EDITOR_PATH",
        "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents",
    )
).expanduser()
MONO = EDITOR_CONTENTS / "MonoBleedingEdge/bin/mono"
CSC = EDITOR_CONTENTS / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
BCL = EDITOR_CONTENTS / "MonoBleedingEdge/lib/mono/4.7.2-api"
OWNER = ROOT / "tools/unity/runtime/session/PortSessionOriginalMusicControllerOwner.cs"
CONTRACT = ROOT / "tools/unity/runtime/session/OriginalMusicControllerContract.cs"
OBSERVER = ROOT / "tools/unity/support/audio/core/OriginalOwnerProbeObserver.cs"
STUBS = Path(os.environ.get("ORIGINAL_MUSIC_OWNER_STUBS", ROOT / "tests/fixtures/original_music_owner_compile_stubs.cs")).expanduser()


class OriginalMusicOwnerStaticObserverCompileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        missing = [str(path) for path in (MONO, CSC, BCL / "mscorlib.dll", BCL / "System.dll", BCL / "System.Core.dll") if not path.is_file()]
        if missing:
            raise unittest.SkipTest("pinned Unity Mono/Roslyn host tools are unavailable")

    def compile_sources(self, owner_source: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-target:library",
                "-langversion:7.3",
                f"-out:{output}",
                f"-r:{BCL / 'mscorlib.dll'}",
                f"-r:{BCL / 'System.dll'}",
                f"-r:{BCL / 'System.Core.dll'}",
                str(STUBS),
                str(OBSERVER),
                str(CONTRACT),
                str(owner_source),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_tracked_owner_compiles_with_actual_observer_and_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="music-owner-compile-") as temp:
            output = Path(temp) / "OriginalMusicOwner.dll"
            result = self.compile_sources(OWNER, output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.is_file())

    def test_static_class_as_value_regression_is_rejected_by_compiler(self) -> None:
        source = OWNER.read_text(encoding="utf-8")
        signature = "void InstallMusicOutputObserver()"
        method_start = source.index(signature)
        opening_brace = source.index("{", method_start)
        mutant = source[: opening_brace + 1] + "\n        var observer = OriginalOwnerProbeObserver.Observer;\n" + source[opening_brace + 1 :]
        with tempfile.TemporaryDirectory(prefix="music-owner-static-mutant-") as temp:
            mutated_owner = Path(temp) / OWNER.name
            mutated_owner.write_text(mutant, encoding="utf-8")
            output = Path(temp) / "ShouldNotCompile.dll"
            result = self.compile_sources(mutated_owner, output)
            diagnostics = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, diagnostics)
            self.assertRegex(diagnostics, r"(?i)(static type|static class|CS0723)")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
