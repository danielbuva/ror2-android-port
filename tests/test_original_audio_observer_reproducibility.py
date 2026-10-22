"""Exact compiler contract for the authored standalone music observer."""

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/lab"))
import original_game_audio_produce as producer
import original_music_output_observer_build_hook as music


class ObserverReproducibilityTests(unittest.TestCase):
    def test_producer_reproduces_active_music_profile_across_source_and_output_roots(self):
        unity = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = unity / "MonoBleedingEdge/bin/mono"
        csc = unity / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not csc.is_file():
            self.skipTest("exact pinned Unity Mono/Roslyn is absent")
        source = producer.SOURCE / "core/OriginalOwnerProbeObserver.cs"
        with tempfile.TemporaryDirectory() as temp:
            hashes = []
            for name in ("first source", "second source"):
                root = Path(temp) / name
                (root / "core").mkdir(parents=True)
                shutil.copyfile(source, root / "core" / source.name)
                output = root / "outputs"
                output.mkdir()
                dll = output / "OriginalOwnerProbeObserver.dll"
                with patch.object(producer, "SOURCE", root):
                    producer.compile_observer(mono, csc, dll, output / "observer.log")
                hashes.append(hashlib.sha256(dll.read_bytes()).hexdigest())
            self.assertEqual(hashes, [music.R3_CORE_OBSERVER, music.R3_CORE_OBSERVER])
            self.assertNotEqual(hashes[0], music.R3_CORE_PREDECESSOR_RESTORE_ONLY)


if __name__ == "__main__":
    unittest.main()
