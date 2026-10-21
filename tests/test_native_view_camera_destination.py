from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load candidate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DestinationCameraCompatibilityTests(unittest.TestCase):
    def test_external_destination_without_camera_receipt_is_an_inert_restore(self):
        hook = load("r14_camera_hook", CANDIDATE / "scripts/lab/native_view_camera_build_hook.py")
        with tempfile.TemporaryDirectory(dir=CANDIDATE.parent) as temp:
            root = Path(temp)
            project = root / "rebuild/input/lab-project"
            work = root / "selected-work"
            project.mkdir(parents=True)
            work.mkdir()
            self.assertIsNone(hook.restore_previous_camera(project, work))

    def test_camera_owner_has_no_compile_time_marker_dependency(self):
        source = (CANDIDATE / "tools/unity/runtime/input/AndroidNativeSourceCameraRigOwner.cs").read_text()
        # The marker assembly type is opt-in metadata in the current-project
        # transform; destination rebuilds compile with the base RoR2 module.
        self.assertNotIn("AndroidNativeSourceViewOnlyRigMarker guardMarker", source)
        self.assertNotIn("AddComponent<AndroidNativeSourceViewOnlyRigMarker>", source)
        self.assertIn('"RoR2.AndroidNativeSourceViewOnlyRigMarker"', source)
        self.assertIn('markerType.GetField("rig"', source)
        self.assertIn("markerRigField.SetValue(marker, rig)", source)

    def test_destination_build_route_restores_then_keeps_audio_without_camera_transform(self):
        source = (CANDIDATE / "scripts/lab/whole_catalog.py").read_text()
        start = source.index("if destination is not None:", source.index("def _build_integration"))
        end = source.index("    io = StageIO(WORK)", start)
        route = source[start:end]
        self.assertIn("safe_destination(destination, destination_input_id, destination_work)", route)
        self.assertIn("restore_previous_camera(destination_project, destination_work)", route)
        self.assertIn("stage_for_build(destination_project, WORK", route)
        self.assertIn('"staged": False', route)
        self.assertNotIn("stage_after_audio(destination_project", route)


if __name__ == "__main__":
    unittest.main()
