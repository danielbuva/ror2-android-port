from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_wrapper_population as population


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
