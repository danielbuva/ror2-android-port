import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import phone_wrapper_population_oracle as oracle
import phone_wrapper_reverse as reverse


class ReverseTests(unittest.TestCase):
    def test_readable_vm_includes_zero_fill_without_relaxing_file_reader(self):
        sdk = Path(os.environ.get("ROR2_POPULATION_SDK", "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"))
        if not sdk.is_file():
            self.skipTest("Optional owner SDK absent")
        self.assertEqual(oracle.base.sha(sdk), reverse.registry.BINARY_SHA256)
        image = reverse.registry.MachO(sdk.read_bytes())
        layout = reverse.layout(image)
        self.assertEqual(layout["end_offset"], layout["begin_offset"] + 8)
        self.assertEqual(layout["stride"], 16)
        with self.assertRaisesRegex(ValueError, "not file backed"):
            image.at(layout["manager_slot"], 8)
        self.assertEqual(sum(r["start"] <= layout["manager_slot"] < r["start"] + r["size"] for r in layout["ranges"]), 1)
        self.assertFalse({"forward", "reverse", "records", "managed"} & layout.keys())

    def test_vm_ranges_refuse_overlap_and_ignore_unreadable_segments(self):
        def segment(start, size, protection):
            value = bytearray(72)
            struct.pack_into("<II", value, 0, 0x19, 72)
            struct.pack_into("<QQQQ", value, 24, start, size, 0, size // 2)
            struct.pack_into("<I", value, 60, protection)
            return value

        header = bytearray(32)
        struct.pack_into("<I", header, 16, 2)
        image = SimpleNamespace(data=header + segment(0x1000, 0x1000, 1) + segment(0x1800, 0x1000, 0))
        self.assertEqual(len(reverse.readable_ranges(image)), 1)
        image.data = header + segment(0x1000, 0x1000, 1) + segment(0x1800, 0x1000, 1)
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            reverse.readable_ranges(image)

    def test_stage_identity_binds_lock_and_transitive_reader_sources(self):
        self.assertIn("scripts/lab/build_lock.py", oracle.SOURCES)
        self.assertTrue(set(reverse.SOURCES) <= set(oracle.SOURCES))
        self.assertIn("tools/phone-build/WrapperReverseOracle.cs", oracle.SOURCES)

    def test_actual_reverse_collector_with_independent_memory(self):
        mono_root = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MonoBleedingEdge")
        mono, compiler = mono_root / "bin/mono", mono_root / "lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("Optional exact-editor compiler absent")
        root = Path(__file__).resolve().parents[1]
        sources = ["tools/phone-build/" + name + ".cs" for name in ("WrapperMetadataOracle", "WrapperPopulationOracle", "WrapperReverseOracle")]
        sources.append("tests/fixtures/WrapperReverseOracleHost.cs")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reverse.exe"
            built = subprocess.run(
                [str(mono), str(compiler), "-nologo", "-out:" + str(output), *(str(root / name) for name in sources)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(mono), str(output)], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: reverse snapshot", run.stdout)
