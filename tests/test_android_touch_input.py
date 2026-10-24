"""Run the complete touch producer against the exact editor's managed Unity API."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
MONO = EDITOR / "MonoBleedingEdge/bin/mono"
CSC = EDITOR / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
ENGINE = EDITOR / "Managed/UnityEngine"


class AndroidTouchInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MONO.is_file() or not CSC.is_file():
            raise unittest.SkipTest("pinned Unity Mono/Roslyn unavailable")
        cls.temp = tempfile.TemporaryDirectory(prefix="android-touch-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name) / "touch.exe"
        camera_source = (ROOT / "tools/unity/runtime/input/NovaThirdPersonView.cs").read_text()
        method = camera_source.split("    public void LookTouch(", 1)[1].split("    public Vector3 Movement(", 1)[0]
        camera = Path(cls.temp.name) / "Camera.cs"
        camera.write_text(
            "using UnityEngine;\npublic sealed class AndroidOfflineSettings { public sealed class Values { "
            "public float lookSensitivity=1; public bool invertY; } public static Values current=new Values(); }\n"
            "public sealed class CameraFixture { public sealed class Report { public int touchFrames,lookFrames; } "
            "public Report report=new Report(); public float yaw,pitch; public int poses; void Place(){poses++;} "
            "public void LookTouch(" + method + "}\n"
        )
        result = subprocess.run(
            [
                str(MONO),
                str(CSC),
                "-nologo",
                "-langversion:9",
                "-out:" + str(cls.exe),
                *[
                    "-r:" + str(ENGINE / name)
                    for name in (
                        "UnityEngine.CoreModule.dll",
                        "UnityEngine.IMGUIModule.dll",
                        "UnityEngine.InputLegacyModule.dll",
                        "UnityEngine.TextRenderingModule.dll",
                    )
                ],
                str(ROOT / "tools/unity/runtime/input/AndroidTouchInput.cs"),
                str(ROOT / "tests/fixtures/AndroidTouchInputHost.cs"),
                str(camera),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def case(self, name):
        result = subprocess.run([str(MONO), str(self.exe), name], env=dict(os.environ, MONO_PATH=str(ENGINE)), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ": PASS", result.stdout)

    def test_independent_fingers_move_look_and_hold_an_action(self):
        self.case("multi-pointer")

    def test_all_eight_short_action_taps_reach_exactly_one_fixed_tick(self):
        self.case("short-taps")

    def test_pause_focus_and_orientation_release_and_require_lift(self):
        self.case("suspension")

    def test_canceled_missing_and_unowned_pointers_do_not_stick(self):
        self.case("cancellation")

    def test_camera_drag_is_pixel_based_and_honors_sensitivity_and_invert(self):
        self.case("camera-delta")
