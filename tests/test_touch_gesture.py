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
    def test_inputs_use_validated_external_runtime_and_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "gesture.json"
            path.write_text(json.dumps(request()))
            dex = root / "classes.dex"
            dex.write_bytes(b"authored fixture")
            runtime = "/sdcard/Android/data/" + touch_gesture.PACKAGE + "/files"
            device = Mock()
            device.owned.return_value = dict(apk_sha256="a" * 64)
            device.read_receipt.return_value = dict(persistentDataPath=runtime)
            device.evidence_directory.return_value = root / "evidence"
            pushed = {}

            def command(*args, **kwargs):
                if args[0] == "push":
                    pushed[args[2]] = Path(args[1])
                    return ""
                return '{"success": true}'

            def shell(*args, **kwargs):
                if args[0] == "pidof":
                    return "123"
                if args[0] == "getprop":
                    return "33"
                if args[0] == "dumpsys":
                    return "  Display: mDisplayId=0\n  mCurrentFocus=Window{fixture u0 " + touch_gesture.PACKAGE + "/Activity}"
                if args[0] == "cmd":
                    return "package:" + touch_gesture.PACKAGE + " uid:10001"
                if args[0] == "sha256sum":
                    return touch_gesture.sha(pushed[args[1]]) + "  " + args[1]
                if args[0] == "rm":
                    pushed.pop(args[2])
                    return ""
                raise AssertionError(args)

            device.cmd.side_effect = command
            device.sh.side_effect = shell
            with (
                patch.object(touch_gesture, "Device", return_value=device),
                patch.object(touch_gesture, "compile_tool", return_value=dex),
                patch.object(touch_gesture, "_remote_path_state", return_value="absent"),
                patch.object(touch_gesture, "WORK", root / "work"),
            ):
                self.assertTrue(touch_gesture.run(path, "a" * 64)["success"])
            device.read_receipt.assert_called_once_with("runtime.json")
            transfers = [call.args[2] for call in device.cmd.call_args_list if call.args[0] == "push"]
            self.assertEqual(len(transfers), 2)
            self.assertTrue(all(target.startswith(runtime + "/ror2lab-touch-") for target in transfers))
            self.assertFalse(pushed)

    def test_focus_must_belong_to_the_owned_app_on_display_zero(self):
        def display(index, window):
            return "  Display: mDisplayId=%d (organized)\n  mCurrentFocus=%s\n  mFocusedApp=ignored\n" % (index, window)

        owned = "Window{fixture u0 dev.ror2lab.arm64/com.unity3d.player.UnityPlayerActivity}"
        foreign = "Window{fixture u0 fixture.other/Activity}"
        self.assertTrue(touch_gesture.owned_display_zero_focus(display(4, foreign) + display(0, owned)))
        for text in (display(4, owned), display(4, owned) + display(0, foreign), display(0, "null"), display(0, owned) * 2, ""):
            with self.subTest(text=text):
                self.assertFalse(touch_gesture.owned_display_zero_focus(text))

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
