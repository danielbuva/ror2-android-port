from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


def find_repo_root() -> Path:
    marker = Path("tools/unity/support/audio/core/GameAudioOriginalOwner.cs")
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    raise RuntimeError("repository root not found from test path")


ROOT = find_repo_root()
AUDIO_CORE = ROOT / "tools/unity/support/audio/core"
FIXTURES = Path(__file__).resolve().parent / "fixtures/original_audio"
UNITY_MONO = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
MONO = UNITY_MONO / "bin/mono"
CSC = UNITY_MONO / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"

CORE_SOURCES = [
    AUDIO_CORE / "GameAudioOriginalOwner.cs",
    AUDIO_CORE / "GameAudioOriginalReadiness.cs",
    AUDIO_CORE / "OriginalOwnerProbeObserver.cs",
]


class OriginalAudioOwnerHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity 2021.3.45f2 Mono/Roslyn compiler unavailable")
        missing = [path for path in CORE_SOURCES if not path.is_file()]
        if missing:
            raise AssertionError("public audio core source missing: " + ", ".join(map(str, missing)))

    def compile_and_run(self, name: str, fixture_names: list[str]) -> str:
        with tempfile.TemporaryDirectory(prefix=f"{name}-") as temp_name:
            temp = Path(temp_name)
            executable = temp / f"{name}.exe"
            fixture_paths = [FIXTURES / fixture for fixture in fixture_names]
            command = [
                str(MONO),
                str(CSC),
                "-nologo",
                "-define:GAME_AUDIO_HOST_TEST",
                "-target:exe",
                "-out:" + str(executable),
                *map(str, CORE_SOURCES),
                *map(str, fixture_paths),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(MONO), str(executable)], capture_output=True, text=True, check=False)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("PASS", executed.stdout)
            return executed.stdout.strip()

    def test_readiness_contract(self) -> None:
        output = self.compile_and_run("readiness", ["GameAudioOriginalReadinessHarness.cs"])
        self.assertIn("default-off", output)
        self.assertIn("Term closure", output)
        self.assertIn("delayed exact control", output)

    def test_owner_one_shot_native_query_and_catalog_release_policy(self) -> None:
        output = self.compile_and_run("owner-one-shot", ["OwnerOneShotHarness.cs"])
        self.assertIn("default-off admission", output)
        self.assertIn("process one-shot reuse", output)
        self.assertIn("readiness closure", output)

    def test_original_observer_callbacks_and_default_off_admission(self) -> None:
        output = self.compile_and_run(
            "owner-observers",
            [
                "PublicAudioOwnerObserverHarness.cs",
            ],
        )
        self.assertIn("both-Term", output)
        self.assertIn("false admission", output)
        self.assertIn("observed original callbacks", output)

    def test_public_runtime_membership_and_request_placeholder(self) -> None:
        runtime_sources = json.loads((ROOT / "recipe/runtime-sources.json").read_text())
        owner_path = "runtime/session/PortSessionOriginalAudioOwner.cs"
        self.assertIn(owner_path, runtime_sources)
        self.assertTrue((ROOT / "tools/unity" / owner_path).is_file())

        generated_pin = (ROOT / "tools/unity/support/audio/bootstrap/GameAudioOriginalGeneratedRequestPin.cs").read_text()
        provider = (ROOT / "tools/unity/support/audio/bootstrap/GameAudioOriginalAcceptedRequestProvider.cs").read_text()
        request_bootstrap = (ROOT / "tools/unity/support/audio/bootstrap/GameAudioOriginalRequestBootstrap.cs").read_text()
        self.assertIn("internal const bool Requested = false;", generated_pin)
        self.assertIn("if (!GameAudioOriginalGeneratedRequestPin.Requested) return null;", provider)
        self.assertIn("GameAudioOriginalAcceptedRequestProvider.Create", request_bootstrap)


if __name__ == "__main__":
    unittest.main()
