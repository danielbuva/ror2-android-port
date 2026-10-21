from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


def calls_in(function: ast.FunctionDef) -> list[tuple[int, str]]:
    result = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name:
            result.append((node.lineno, name))
    return sorted(result)


class MusicOutputObserverPipelineTests(unittest.TestCase):
    def test_build_and_restore_order_is_camera_observer_audio(self) -> None:
        source = (CANDIDATE / "scripts/lab/whole_catalog.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_build_integration")
        ordered = calls_in(function)

        def position(call: str, start: int = 0) -> int:
            return next(index for index, (line, name) in enumerate(ordered) if index >= start and name == call)

        destination_camera = position("restore_previous_camera")
        destination_observer = position("restore_previous_music_output_observer", destination_camera + 1)
        destination_audio = position("stage_for_build", destination_observer + 1)
        project_camera = position("restore_previous_camera", destination_audio + 1)
        project_observer = position("restore_previous_music_output_observer", project_camera + 1)
        project_audio = position("stage_for_build", project_observer + 1)
        project_camera_stage = position("stage_after_audio", project_audio + 1)
        self.assertLess(destination_camera, destination_observer)
        self.assertLess(destination_observer, destination_audio)
        self.assertLess(project_camera, project_observer)
        self.assertLess(project_observer, project_audio)
        self.assertLess(project_audio, project_camera_stage)

    def test_observer_profile_and_output_receipts_remain_unaccepted(self) -> None:
        camera = json.loads((CANDIDATE / "recipe/native-view-camera-transform.json").read_text())
        self.assertEqual(camera["profiles"]["default-game-3124"]["output_sha256"], "494ba9acd8ea34bed17ac56edb9a49eafa8cb5afd2f91466b95ca0d71ce3b8cd")
        self.assertEqual(
            camera["profiles"]["post-audio-music-observer-6f96-api-d540"]["output_sha256"], "4bd3b240ce5a9cb620d14ce4041f493ba013b9700d792dc9c99c8666f3af06f0"
        )
        gates = camera["gate_status"]
        for key in (
            "accepted",
            "camera_enabled",
            "current_player_closure_verified",
            "device_tested",
            "full_closure_scan",
            "runtime_dispatch_ready",
            "stage_to_apk_binding",
        ):
            self.assertIs(gates[key], False, key)
        observer = (CANDIDATE / "scripts/lab/original_music_output_observer_build_hook.py").read_text()
        self.assertIn('"accepted": False', observer)
        self.assertIn('"runtime_dispatch_ready": False', observer)


if __name__ == "__main__":
    unittest.main()
