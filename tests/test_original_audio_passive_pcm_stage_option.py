from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "canonical" and (parent / "scripts/lab/original_game_audio_stage.py").is_file():
            return parent
        if (parent / "scripts/lab/original_game_audio_stage.py").is_file():
            return parent
    raise RuntimeError("repository root not found")


ROOT = find_repo_root()
SPEC = importlib.util.spec_from_file_location("audio_stage_under_test", ROOT / "scripts/lab/original_game_audio_stage.py")
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class PassivePcmStageOptionTests(unittest.TestCase):
    def verify(self, request: dict, manifest_request: dict | None = None) -> dict:
        if manifest_request is None:
            manifest_request = dict(request)
        with tempfile.TemporaryDirectory(prefix="passive-pcm-stage-option-", dir=ROOT) as temp:
            path = Path(temp) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            return stage.verify_request({"request": manifest_request}, path)

    def base_request(self) -> dict:
        return {
            "schema": "game-audio-original-runtime-request-r3",
            "requested": True,
            "request_id": "0123456789abcdef0123456789abcdef",
            "build_input_contract_sha256": "a" * 64,
            "passive_pcm_capture_requested": True,
            "passive_pcm_capture_music_output_requested": False,
            "passive_pcm_capture_after_authority_skill_requested": False,
        }

    def test_default_off_and_deferred_main_output_options_are_recorded(self) -> None:
        default = self.base_request()
        # A prior request that predates this selector remains false when the
        # field is absent from both serialized request objects.
        default.pop("passive_pcm_capture_after_authority_skill_requested")
        pins = self.verify(default)
        self.assertIs(pins["passive_pcm_capture_after_authority_skill_requested"], False)

        deferred = self.base_request()
        deferred["passive_pcm_capture_after_authority_skill_requested"] = True
        pins = self.verify(deferred)
        self.assertIs(pins["passive_pcm_capture_after_authority_skill_requested"], True)

    def test_stage_refuses_request_mismatch_and_unsupported_selector_modes(self) -> None:
        request = self.base_request()
        request["passive_pcm_capture_after_authority_skill_requested"] = True
        wrong_manifest = {**request, "passive_pcm_capture_after_authority_skill_requested": False}
        with self.assertRaisesRegex(ValueError, "differs from compiled artifact set"):
            self.verify(request, wrong_manifest)

        for music in (True,):
            invalid = {**request, "passive_pcm_capture_music_output_requested": music}
            with self.assertRaisesRegex(ValueError, "requires MainOutput"):
                self.verify(invalid)

        invalid = {**request, "passive_pcm_capture_after_authority_skill_requested": 1}
        with self.assertRaisesRegex(ValueError, "unsupported runtime request schema"):
            self.verify(invalid)


if __name__ == "__main__":
    unittest.main()
