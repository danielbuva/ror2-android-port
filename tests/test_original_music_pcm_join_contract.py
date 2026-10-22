from __future__ import annotations

import hashlib
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
NETSTANDARD = EDITOR_CONTENTS / "MonoBleedingEdge/lib/mono/4.7.1-api/Facades/netstandard.dll"
UNITY_CORE = EDITOR_CONTENTS / "Managed/UnityEngine/UnityEngine.CoreModule.dll"
API = ROOT / "work/lab-project/Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"
API_SHA256 = "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b"
HELPER = ROOT / "tools/unity/runtime/session/MusicPcmJoinObserver.cs"
ADAPTER = ROOT / "tools/unity/runtime/session/AkMusicPcmJoinQueryAdapter.cs"
CORE_CAPTURE_CONTRACT = ROOT / "tools/unity/support/audio/core/GameAudioOriginalPassivePcmContract.cs"
FIXTURES = ROOT / "tests/fixtures"


class OriginalMusicPcmJoinContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn host tools are unavailable")

    def compile(self, output: Path, references: list[Path], sources: list[Path]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-target:exe" if output.suffix == ".exe" else "-target:library",
                "-langversion:7.3",
                f"-out:{output}",
                *[f"-r:{reference}" for reference in references],
                *map(str, sources),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clock_and_capture_contract_with_synthetic_queries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="music-pcm-contract-") as temp:
            output = Path(temp) / "join.exe"
            build = self.compile(
                output,
                [],
                [
                    HELPER,
                    ADAPTER,
                    FIXTURES / "music_pcm_join_native_stubs.cs",
                    FIXTURES / "music_pcm_join_harness.cs",
                ],
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(MONO), str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS bounded cadence", run.stdout)

    def test_adapter_compiles_against_accepted_api_when_available(self) -> None:
        if not API.is_file() or not UNITY_CORE.is_file() or not NETSTANDARD.is_file():
            self.skipTest("accepted Wwise API or pinned Unity references are unavailable")
        self.assertEqual(hashlib.sha256(API.read_bytes()).hexdigest(), API_SHA256)
        with tempfile.TemporaryDirectory(prefix="music-pcm-exact-api-") as temp:
            output = Path(temp) / "MusicPcmJoinAdapter.dll"
            build = self.compile(
                output,
                [API, UNITY_CORE, NETSTANDARD],
                [
                    CORE_CAPTURE_CONTRACT,
                    FIXTURES / "music_pcm_join_exact_api_owner_stub.cs",
                    HELPER,
                    ADAPTER,
                ],
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
