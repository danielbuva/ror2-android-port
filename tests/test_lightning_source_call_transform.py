from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs").is_file() and (
            parent / "tools/unity/runtime/world/LightningStakeSourceCallObserver.cs"
        ).is_file():
            return parent
    raise AssertionError("repository root not found")


ROOT = repo_root()
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/lightning-source-call"
TOOLCHAIN = ROOT / "environment/toolchain.json"
UNITY_VERSION = "2021.3.45f2"
if TOOLCHAIN.is_file():
    import json

    UNITY_VERSION = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))["unity_version"]
UNITY = Path("/Applications/Unity/Hub/Editor") / UNITY_VERSION / "Unity.app/Contents/MonoBleedingEdge"
MONO = UNITY / "bin/mono"
CSC = UNITY / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
CECIL = UNITY / "lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
TRANSFORM = ROOT / "tools/unity/support/audio/managed-producer/tools/composed/ComposedGameCecilTransform.cs"
BRIDGE = ROOT / "tools/unity/support/audio/managed-producer/source/owner-api/OriginalOwnerProbeObserver.cs"
OWNER = ROOT / "tools/unity/runtime/world/LightningStakeSourceCallObserver.cs"
FIXTURE = FIXTURE_ROOT / "LightningSourceCallFixture.cs"
OWNER_STUBS = FIXTURE_ROOT / "LightningStakeOwnerHostStubs.cs"
OWNER_CONTRACTS = FIXTURE_ROOT / "LightningStakeOwnerHostContracts.cs"


@unittest.skipUnless(
    MONO.is_file() and CSC.is_file() and CECIL.is_file(),
    "standard Unity Mono/Roslyn/Cecil host tooling is unavailable",
)
class LightningSourceCallTransformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="lightning-source-call-")
        self.out = Path(self.temp.name)
        self.bridge = self.out / "OriginalOwnerProbeObserver.dll"
        self.fixture = self.out / "LightningFixture.exe"
        self.tool = self.out / "ComposedTransformHostTest.exe"
        self.owner_test = self.out / "LightningStakeOwnerHostContracts.exe"
        self.target = self.out / "LightningFixture.transformed.exe"
        self.compile(
            [
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-target:library",
                f"-out:{self.bridge}",
                str(BRIDGE),
            ]
        )
        self.compile(
            [
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-target:exe",
                "-debug",
                "-optimize-",
                f"-r:{self.bridge}",
                f"-out:{self.fixture}",
                str(FIXTURE),
            ]
        )
        self.compile(
            [
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-define:LIGHTNING_STAKE_HOST_TEST",
                f"-r:{CECIL}",
                f"-out:{self.tool}",
                str(TRANSFORM),
            ]
        )
        self.compile(
            [
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-target:exe",
                f"-r:{self.bridge}",
                f"-out:{self.owner_test}",
                str(OWNER),
                str(OWNER_STUBS),
                str(OWNER_CONTRACTS),
            ]
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def compile(self, command: list[str]) -> None:
        result = subprocess.run([str(MONO), *command], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def transform(self, mode: str, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(MONO),
                str(self.tool),
                "lightning-fixture",
                str(self.fixture),
                str(self.bridge),
                str(output),
                mode,
            ],
            text=True,
            capture_output=True,
        )

    def test_default_off_and_observer_paths_keep_exact_single_original_call(self) -> None:
        result = self.transform("normal", self.target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        execution = subprocess.run([str(MONO), str(self.target)], text=True, capture_output=True)
        self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
        self.assertIn("PASS default-off, exact pre-call operand capture", execution.stdout)
        self.assertIn("original call preservation, and contained observer throw", execution.stdout)

    def test_existing_incoming_branch_is_redirected_through_observer_guard(self) -> None:
        target = self.out / "LightningFixture.bypass.exe"
        result = self.transform("bypass", target)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        execution = subprocess.run([str(MONO), str(target)], text=True, capture_output=True)
        self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
        self.assertIn("PASS", execution.stdout)

    def test_changed_or_duplicated_source_site_and_eh_boundary_refuse_before_write(self) -> None:
        for mode in ("changed-string", "duplicate", "eh-boundary"):
            with self.subTest(mode=mode):
                target = self.out / f"{mode}.exe"
                result = self.transform(mode, target)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(target.exists())

    def test_actual_runtime_owner_captures_bounded_values_and_tears_down_exactly(self) -> None:
        result = subprocess.run([str(MONO), str(self.owner_test)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS actual observer source captures scalar context", result.stdout)


if __name__ == "__main__":
    unittest.main()
