from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def find_source_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts/lab/original_music_output_observer_build_hook.py").is_file():
            return parent
    raise RuntimeError("observer source root not found")


SOURCE_ROOT = find_source_root()
HOOK_PATH = SOURCE_ROOT / "scripts/lab/original_music_output_observer_build_hook.py"
SPEC = importlib.util.spec_from_file_location("original_music_observer_hook", HOOK_PATH)
assert SPEC is not None and SPEC.loader is not None
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)
RAW = HOOK.RAW_GAME
GAME = HOOK.GAME
API_PATH = HOOK.API
CORE = HOOK.CORE
ACCEPTED_INPUT = HOOK.ACCEPTED_INPUT_ID
ACCEPTED_GAME = HOOK.ACCEPTED_GAME
GUARDED_GAME = HOOK.GUARDED_GAME
CORE_HASH = "a" * 64


class OriginalMusicOutputObserverReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="music-observer-contract-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        for path in (self.project / GAME, self.project / API_PATH, self.project / CORE):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"authored fixture identity")
        self.api_hash = next(iter(HOOK.API_PROFILES))
        self.lineage = {
            "accepted_input_id": ACCEPTED_INPUT,
            "accepted_game_sha256": ACCEPTED_GAME,
            "guarded_game_input_sha256": GUARDED_GAME,
            "composed_game_sha256": RAW,
            "composed_api_sha256": self.api_hash,
        }
        self.audio = {
            "requested": True,
            "runtime_accepted": False,
            "audible": False,
            "accepted_input_id": ACCEPTED_INPUT,
            "lineage": self.lineage,
            "outputs": [
                {"target": GAME.as_posix(), "sha256": RAW},
                {"target": CORE.as_posix(), "sha256": CORE_HASH},
            ],
        }
        self.hashes = {
            (self.project / GAME).resolve(): RAW,
            (self.project / API_PATH).resolve(): self.api_hash,
            (self.project / CORE).resolve(): CORE_HASH,
        }

    def call_generation(self):
        with patch.object(HOOK, "sha", side_effect=lambda path: self.hashes[Path(path).resolve()]):
            return HOOK._generation(self.project, self.audio, "0" * 64)

    def test_exact_unaccepted_audio_pair_and_unique_owned_rows_pass(self) -> None:
        self.assertEqual(self.call_generation(), self.lineage)

    def test_unrequested_or_already_accepted_audio_is_refused(self) -> None:
        for key, value in (("requested", False), ("runtime_accepted", True), ("audible", True)):
            with self.subTest(key=key):
                original = self.audio[key]
                self.audio[key] = value
                with self.assertRaisesRegex(ValueError, "requested but unaccepted"):
                    self.call_generation()
                self.audio[key] = original

    def test_foreign_or_mismatched_lineage_is_refused(self) -> None:
        mutations = (
            ("accepted_input_id", "0" * 64),
            ("accepted_game_sha256", "0" * 64),
            ("guarded_game_input_sha256", "0" * 64),
            ("composed_game_sha256", "0" * 64),
            ("composed_api_sha256", "0" * 64),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                original = self.lineage[key]
                self.lineage[key] = value
                with self.assertRaisesRegex(ValueError, "outside exact 6f96/d540-or-1ced"):
                    self.call_generation()
                self.lineage[key] = original

    def test_duplicate_or_drifted_output_rows_are_refused(self) -> None:
        self.audio["outputs"].append({"target": GAME.as_posix(), "sha256": RAW})
        with self.assertRaisesRegex(ValueError, "exactly the expected raw PointSound game module"):
            self.call_generation()
        self.audio["outputs"] = [row for row in self.audio["outputs"] if row["target"] != GAME.as_posix()]
        self.audio["outputs"] = [
            {"target": GAME.as_posix(), "sha256": RAW},
            {"target": CORE.as_posix(), "sha256": "0" * 64},
        ]
        with self.assertRaisesRegex(ValueError, "observer assembly differs"):
            self.call_generation()

    def test_live_game_or_api_hash_drift_is_refused(self) -> None:
        self.hashes[(self.project / GAME).resolve()] = "0" * 64
        with self.assertRaisesRegex(ValueError, "staged game/API bytes"):
            self.call_generation()


if __name__ == "__main__":
    unittest.main()
