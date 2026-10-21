from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from _music_observer_test_support import cecil, digest, dotnet, required_directory, required_file


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / ".git").exists():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_root()
RAW_HASH = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"
OUTPUT_HASH = "a6385e3166d3950944da8a08f145d7e9be602571a6a75b4afb18279801f44311"
API_HASHES = {
    "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
}
TRANSFORM_PROJECT = ROOT / "tools/assembly-transforms/MusicOutputObserverCecilTransform.csproj"
MUTATOR_PROJECT = ROOT / "tests/observer-fixtures/MutateObserverFixture.csproj"
SAFE_FIXTURE_PROJECT = ROOT / "tests/observer-fixtures/ObserverSafeCallbackFixture.csproj"
CORE_PROJECT = ROOT / "tests/observer-fixtures/OriginalOwnerProbeObserver.Fixture.csproj"


def run(args: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode != 0:
        raise AssertionError(f"exit {result.returncode}: {' '.join(args)}\n{result.stdout}")
    return result


class MusicOutputObserverHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game = required_file("MUSIC_OBSERVER_GAME_DLL", RAW_HASH)
        cls.references = required_directory("MUSIC_OBSERVER_REFERENCES")
        api = cls.references / "AK.Wwise.Unity.API.dll"
        if not api.is_file() or digest(api) not in API_HASHES:
            raise unittest.SkipTest("MUSIC_OBSERVER_REFERENCES lacks a pinned d540/1ced audio API")
        cls.dotnet = dotnet()
        cls.cecil = cecil()
        cls.temp = tempfile.TemporaryDirectory(prefix="music-output-observer-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.out = Path(cls.temp.name)
        cls.tool_out = cls.out / "transform-tool"
        cls.core_out = cls.out / "observer"
        cls.mutator_out = cls.out / "mutator"
        cls.safe_out = cls.out / "callback-fixture"
        cls.output = cls.out / "RoR2.output-observed.dll"
        run([str(cls.dotnet), "build", str(TRANSFORM_PROJECT), f"-p:CecilPath={cls.cecil}", "-o", str(cls.tool_out)])
        run([str(cls.dotnet), "build", str(CORE_PROJECT), "-o", str(cls.core_out)])
        run(
            [
                str(cls.dotnet),
                str(cls.tool_out / "MusicOutputObserverCecilTransform.dll"),
                "transform",
                str(cls.game),
                str(cls.core_out / "OriginalOwnerProbeObserver.dll"),
                str(cls.references),
                str(cls.output),
            ]
        )
        run([str(cls.dotnet), "build", str(MUTATOR_PROJECT), f"-p:CecilPath={cls.cecil}", "-o", str(cls.mutator_out)])
        run(
            [
                str(cls.dotnet),
                "build",
                str(SAFE_FIXTURE_PROJECT),
                f"-p:CoreObserverPath={cls.core_out / 'OriginalOwnerProbeObserver.dll'}",
                "-o",
                str(cls.safe_out),
            ]
        )

    def verify_shape(self, path: Path) -> subprocess.CompletedProcess[str]:
        return run(
            [
                str(self.dotnet),
                str(self.tool_out / "MusicOutputObserverCecilTransform.dll"),
                "verify-output",
                str(self.game),
                str(path),
                "OriginalOwnerProbeObserver, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
            ],
            check=False,
        )

    def mutate(self, mode: str) -> Path:
        output = self.out / f"{mode}.dll"
        run([str(self.dotnet), str(self.mutator_out / "MutateObserverFixture.dll"), str(self.output), str(output), mode, str(self.references)])
        return output

    def test_exact_real_6f96_transform_and_scoped_output_hash(self) -> None:
        self.assertEqual(digest(self.game), RAW_HASH)
        self.assertEqual(digest(self.output), OUTPUT_HASH)
        result = self.verify_shape(self.output)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("structure, metadata, methods and exception tables passed", result.stdout)

    def test_malformed_stack_or_observer_sites_are_rejected(self) -> None:
        cases = ["remove-add-dup", "rename-add-observer", "remove-remove-observer", "change-exception-handler"]
        for mode in cases:
            with self.subTest(mode=mode):
                result = self.verify_shape(self.mutate(mode))
                self.assertNotEqual(result.returncode, 0)
                if mode == "change-exception-handler":
                    self.assertIn("exception handlers changed", result.stdout)

    def test_wrong_preimage_is_refused_without_creating_output(self) -> None:
        bad = self.out / "wrong-preimage.dll"
        changed = bytearray(self.game.read_bytes())
        changed[len(changed) // 2] ^= 1
        bad.write_bytes(changed)
        output = self.out / "refused-preimage-output.dll"
        result = run(
            [
                str(self.dotnet),
                str(self.tool_out / "MusicOutputObserverCecilTransform.dll"),
                "transform",
                str(bad),
                str(self.core_out / "OriginalOwnerProbeObserver.dll"),
                str(self.references),
                str(output),
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact 6f96 composed game input", result.stdout)
        self.assertFalse(output.exists())


class MusicObserverCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dotnet = dotnet()
        cls.temp = tempfile.TemporaryDirectory(prefix="music-observer-callback-")
        cls.addClassCleanup(cls.temp.cleanup)
        out = Path(cls.temp.name)
        core_out = out / "observer"
        safe_out = out / "callback-fixture"
        run([str(cls.dotnet), "build", str(CORE_PROJECT), "-o", str(core_out)])
        run(
            [
                str(cls.dotnet),
                "build",
                str(SAFE_FIXTURE_PROJECT),
                f"-p:CoreObserverPath={core_out / 'OriginalOwnerProbeObserver.dll'}",
                "-o",
                str(safe_out),
            ]
        )
        cls.fixture = safe_out / "ObserverSafeCallbackFixture.dll"

    def test_callback_preserves_scalar_identity_and_contains_observer_failure(self) -> None:
        result = run([str(self.dotnet), str(self.fixture)])
        self.assertIn("forward exact scalar arguments", result.stdout)


if __name__ == "__main__":
    unittest.main()
