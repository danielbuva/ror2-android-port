import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
import touch_gesture


def request():
    return dict(pid="123", width=1920, height=1080, steps=[dict(action="down", id=0, x=100, y=200), dict(action="up", id=0, x=100, y=200)])


class TouchGestureTests(unittest.TestCase):
    def test_multiple_fingers_and_a_final_canceled_hold_are_valid(self):
        value = request()
        value["steps"].insert(1, dict(action="down", id=1, x=900, y=300))
        value["steps"].insert(2, dict(action="wait", ms=500))
        self.assertIs(touch_gesture.validate_request(value), value)

    def test_invalid_pointer_lifetimes_and_coordinates_refuse_before_device_access(self):
        invalid = []
        value = request()
        value["steps"].reverse()
        invalid.append(value)
        value = request()
        value["steps"].insert(1, copy.deepcopy(value["steps"][0]))
        invalid.append(value)
        for axis in (float("nan"), -1, 1920, True):
            value = request()
            value["steps"][0]["x"] = axis
            invalid.append(value)
        value = request()
        value["steps"].append(dict(action="wait", ms=30001))
        invalid.append(value)
        with patch.object(touch_gesture, "Device") as device:
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    touch_gesture.validate_request(value)
            device.assert_not_called()

    def test_absent_apk_binding_refuses_before_reading_request_or_device(self):
        with patch.object(touch_gesture, "Device") as device, self.assertRaises(ValueError):
            touch_gesture.run("missing.json")
        device.assert_not_called()

    def run_refusal(self, sh, message):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gesture.json"
            path.write_text(json.dumps(request()))
            device = Mock()
            device.sh.side_effect = sh
            with (
                patch.object(touch_gesture, "Device", return_value=device),
                patch.object(touch_gesture, "bind_installed_apk") as binding,
                patch.object(touch_gesture, "compile_tool") as compile_tool,
                self.assertRaisesRegex(RuntimeError, message),
            ):
                touch_gesture.run(path, "a" * 64)
            binding.assert_called_once_with(device.owned.return_value, expected_sha256="a" * 64)
            compile_tool.assert_not_called()
            device.cmd.assert_not_called()
            return device

    def test_restarted_process_cannot_replay_a_stale_gesture(self):
        self.run_refusal(lambda *args, **kwargs: "456", "PID differs")

    def test_foreign_focused_window_cannot_receive_or_stage_events(self):
        def shell(*args, **kwargs):
            if args[0] == "pidof":
                return "123"
            if args[0] == "getprop":
                return "33"
            return "mCurrentFocus=Window{fixture u0 fixture.other/Activity}"

        self.run_refusal(shell, "not the focused window")
