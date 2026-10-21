from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_wrapper_population as population
import phone_wrapper_population_oracle as oracle


class Image:
    def __init__(self, words):
        self.start = 0x1000
        self.words = {self.start + 4 * i: word for i, word in enumerate(words)}
        self.symbols = {"authored": {self.start}, "end": {self.start + 4 * len(words)}}
        self.symbol_addresses = sorted(next(iter(v)) for v in self.symbols.values())

    def at(self, address, size):
        return b"".join(struct.pack("<I", self.words[pc]) for pc in range(address, address + size, 4))


class PopulationOriginTests(unittest.TestCase):
    def test_literal_and_call_result_are_different_origins(self):
        image = Image([0x52800062, 0x94000010, 0xAA0003E2, 0xD65F03C0])
        reader = population.Origins(image, image.words)
        self.assertEqual(reader.origin(0x1004, 2), ("constant", 3))
        self.assertEqual(reader.origin(0x100C, 2), ("call", 0x1004, 0x1044))

    def test_skipped_definition_zero_register_and_unknown_effect_refuse(self):
        for words, register, message in [
            ([0xB4000040, 0x52800021, 0xD65F03C0], 1, "another path"),
            ([0xAA1F03E2, 0xD65F03C0], 2, "Unqualified"),
            ([0xFFFFFFFF, 0xD65F03C0], 2, "Unknown instruction"),
            ([0x94000010, 0xD65F03C0], 2, "Caller-saved"),
        ]:
            with self.subTest(message=message):
                image = Image(words)
                with self.assertRaisesRegex(ValueError, message):
                    population.Origins(image, image.words).origin(max(image.words), register)

    def test_native_extra_shape_is_decoded_without_a_captured_table(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity")
        if not sdk.is_file():
            self.skipTest("Optional owner SDK absent")
        data = sdk.read_bytes()
        self.assertEqual(population.hashlib.sha256(data).hexdigest(), population.registry.BINARY_SHA256)
        root, extras = population.profile(population.registry.MachO(data))
        self.assertGreater(root, 0)
        self.assertEqual(len({row["native"] for row in extras}), 6)
        self.assertEqual(sorted(row["source"]["kind"] for row in extras), ["assembly", "corlib", "corlib", "corlib", "search", "search"])

    def test_actual_population_collector_with_independent_api(self):
        mono_root = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
        mono, compiler = mono_root / "bin/mono", mono_root / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("Optional exact-editor compiler absent")
        root = Path(__file__).resolve().parents[1]
        sources = [
            "tools/phone-build/WrapperMetadataOracle.cs",
            "tools/phone-build/WrapperPopulationOracle.cs",
            "tests/fixtures/WrapperPopulationOracleHost.cs",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "population.exe"
            built = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-out:" + str(output), *(str(root / name) for name in sources)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(mono), str(output)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: abstract", run.stdout)


class PopulationStagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in oracle.SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// authored source fixture\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "test: fixture"], cwd=self.root, check=True)
        self.editor = self.root / "Contents/MacOS/AuthoredEditor"
        self.editor.parent.mkdir(parents=True)
        self.editor.write_bytes(b"authored non-executable editor substitute")
        self.work = self.root / "work"

    def invoke(self, execute):
        proxy = SimpleNamespace(check_output=subprocess.check_output, run=execute, SubprocessError=subprocess.SubprocessError)
        with patch.object(oracle, "subprocess", proxy), patch.object(oracle.base, "BINARY_SHA256", oracle.base.sha(self.editor)):
            return oracle.run(self.root, self.work, self.editor)

    def test_actual_staging_uses_guarded_namespace_and_retains_editor_failure(self):
        calls = []

        def failed(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=7, stdout=b"authored failure", stderr=b"")

        destination, receipt = self.invoke(failed)
        self.assertEqual(len(calls), 1)
        self.assertTrue(destination.is_relative_to(self.work / "rebuild/phone-wrapper-oracle"))
        self.assertFalse(receipt["success"])
        self.assertEqual(receipt["exit_code"], 7)
        self.assertEqual((destination / "launch.txt").read_bytes(), b"authored failure")
        self.assertTrue((destination / "receipt.json").is_file())

    def test_symlinked_parent_refuses_before_any_child_or_outside_write(self):
        self.work.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.work / "rebuild").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "without links"):
            self.invoke(lambda *args, **kwargs: self.fail("Editor must not start"))
        self.assertEqual(list(outside.iterdir()), [])

    def test_foreign_project_asset_refuses_after_child_exit(self):
        def changed(args, **kwargs):
            project = Path(args[args.index("-projectPath") + 1])
            (project / "Assets/foreign.dll").write_bytes(b"authored foreign control")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

        _, receipt = self.invoke(changed)
        self.assertFalse(receipt["success"])
        self.assertIn("Foreign population oracle asset", receipt["error"])
