from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL_PROJECT = ROOT / "tools/assembly-transforms/MusicOutputObserverCecilTransform.csproj"
FIXTURE_PROJECT = HERE / "observer-fixtures/MusicNativeResultFixture.csproj"
OWNER = ROOT / "tools/unity/runtime/session/PortSessionOriginalMusicControllerOwner.cs"
CONTRACT = ROOT / "tools/unity/runtime/session/OriginalMusicControllerContract.cs"
OBSERVER = ROOT / "tools/unity/support/audio/core/OriginalOwnerProbeObserver.cs"
OWNER_STUBS = HERE / "fixtures/original_music_owner_compile_stubs.cs"
OWNER_HARNESS = HERE / "fixtures/original_music_native_result_harness.cs"
CECL_SHA256 = "8b33668cd03b78b7bcaa96eac82488d88c7c89416f82037ecbe2b781ab9642f8"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dotnet_path() -> Path | None:
    configured = os.environ.get("DOTNET")
    if configured:
        return Path(configured).expanduser().resolve()
    found = shutil.which("dotnet")
    if found:
        return Path(found).resolve()
    local = Path.home() / ".local/share/dotnet/dotnet"
    return local if local.is_file() else None


def cecil_path() -> Path | None:
    configured = os.environ.get("MUSIC_OBSERVER_CECIL")
    editor = os.environ.get("UNITY_EDITOR_PATH")
    if configured:
        candidate = Path(configured).expanduser().resolve()
    elif editor:
        contents = Path(editor).expanduser().resolve().parent.parent
        candidate = contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    else:
        candidate = Path(
            "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
        )
    return candidate if candidate.is_file() else None


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise AssertionError(f"exit {result.returncode}: {' '.join(args)}\n{result.stdout}")
    return result


class NativeResultObserverTransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dotnet = dotnet_path()
        cls.cecil = cecil_path()
        if cls.dotnet is None or not cls.dotnet.is_file():
            raise unittest.SkipTest("dotnet is unavailable for optional Cecil host tests")
        if cls.cecil is None:
            raise unittest.SkipTest("pinned Unity Mono.Cecil is unavailable")
        if digest(cls.cecil) != CECL_SHA256:
            raise AssertionError("Mono.Cecil does not match pinned Unity 0.11.1 bytes")
        cls.temp = tempfile.TemporaryDirectory(prefix="music-native-result-transform-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.out = Path(cls.temp.name)
        cls.tool = cls.out / "tool"
        cls.fixture = cls.out / "fixture"
        run([str(cls.dotnet), "build", str(TOOL_PROJECT), f"-p:CecilPath={cls.cecil}", "-c", "Release", "-o", str(cls.tool)])
        run([str(cls.dotnet), "build", str(FIXTURE_PROJECT), "-c", "Release", "-o", str(cls.fixture)])

    def build_mutant(self, name: str) -> Path:
        output = self.out / f"fixture-{name}"
        run([str(self.dotnet), "build", str(FIXTURE_PROJECT), "-c", "Release", f"-p:FixtureMutant={name}", "-o", str(output)])
        return output / "MusicNativeResultFixture.dll"

    def transform(self, input_dll: Path, output_dll: Path) -> subprocess.CompletedProcess[str]:
        return run(
            [
                str(self.dotnet),
                str(self.tool / "MusicOutputObserverCecilTransform.dll"),
                "transform-fixture",
                str(input_dll),
                str(self.fixture / "OriginalOwnerProbeObserver.dll"),
                str(input_dll.parent),
                str(output_dll),
            ],
            check=False,
        )

    def test_synthetic_transform_and_runtime_preserve_calls_results_sources_and_throw_paths(self) -> None:
        source = self.fixture / "MusicNativeResultFixture.dll"
        transformed = self.out / "MusicNativeResultFixture.observed.dll"
        result = self.transform(source, transformed)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("observer verified", result.stdout)
        self.assertTrue(transformed.is_file())

        runtime = self.out / "run"
        runtime.mkdir()
        shutil.copy2(transformed, runtime / "MusicNativeResultFixture.dll")
        for name in ("MusicNativeResultFixture.runtimeconfig.json", "MusicNativeResultFixture.deps.json", "OriginalOwnerProbeObserver.dll"):
            shutil.copy2(self.fixture / name, runtime / name)
        executed = run([str(self.dotnet), str(runtime / "MusicNativeResultFixture.dll")], check=False)
        self.assertEqual(executed.returncode, 0, executed.stdout)
        self.assertIn("preserved original calls, uint/int values, sources and safe callback behavior", executed.stdout)

    def test_missing_duplicate_and_changed_native_sites_refuse_before_output_write(self) -> None:
        cases = {
            "MissingStop": "expected exactly one original AkSoundEngine.SetState",
            "DuplicatePostEvent": "expected exactly one original StartIntroMusic PostEvent",
            "ChangedPostEvent": "expected exactly one original StartIntroMusic PostEvent",
        }
        for mutant, message in cases.items():
            with self.subTest(mutant=mutant):
                source = self.build_mutant(mutant)
                output = self.out / f"refused-{mutant}.dll"
                result = self.transform(source, output)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stdout)
                self.assertFalse(output.exists())

    def test_normal_transform_still_refuses_nonpinned_input_before_writing(self) -> None:
        source = self.fixture / "MusicNativeResultFixture.dll"
        output = self.out / "refused-nonpinned.dll"
        result = run(
            [
                str(self.dotnet),
                str(self.tool / "MusicOutputObserverCecilTransform.dll"),
                "transform",
                str(source),
                str(self.fixture / "OriginalOwnerProbeObserver.dll"),
                str(self.fixture),
                str(output),
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("exact R3 PointSound composed game input", result.stdout)
        self.assertFalse(output.exists())

    def test_copied_runtime_owner_compiles_and_joins_exact_identity_then_detaches(self) -> None:
        editor_contents = Path(os.environ.get("UNITY_EDITOR_PATH", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")).expanduser()
        mono = editor_contents / "MonoBleedingEdge/bin/mono"
        csc = editor_contents / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        bcl = editor_contents / "MonoBleedingEdge/lib/mono/4.7.2-api"
        if not all(path.is_file() for path in (mono, csc, bcl / "mscorlib.dll", bcl / "System.dll", bcl / "System.Core.dll")):
            self.skipTest("pinned Unity Mono/Roslyn host tools are unavailable")
        executable = self.out / "NativeResultOwnerHarness.exe"
        compiled = run(
            [
                str(mono),
                str(csc),
                "-nologo",
                "-target:exe",
                "-langversion:7.3",
                f"-out:{executable}",
                f"-r:{bcl / 'mscorlib.dll'}",
                f"-r:{bcl / 'System.dll'}",
                f"-r:{bcl / 'System.Core.dll'}",
                str(OWNER_STUBS),
                str(OBSERVER),
                str(CONTRACT),
                str(OWNER),
                str(OWNER_HARNESS),
            ],
            check=False,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stdout)
        executed = subprocess.run([str(mono), str(executable)], cwd=self.out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(executed.returncode, 0, executed.stdout)
        self.assertIn("owner identity, scalar result, unknown context and teardown", executed.stdout)


if __name__ == "__main__":
    unittest.main()
