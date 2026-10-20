import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from phone_linker import LITERALS, arguments, strip


class PhoneLinkerTests(unittest.TestCase):
    def test_mapping_preserves_flags_and_order_and_refuses_foreign_roots_or_output(self):
        project, input_root, capture, android, launcher = map(
            Path, ("/fixture", "/fixture/Temp/Managed", "/attempt/linker-capture", "/sdk/android", "/sdk/deploy/UnityLinker")
        )
        tokens = [
            str(launcher),
            *sorted(LITERALS),
            "--enable-analytics",
            "--search-directory=" + str(input_root),
            "--include-directory=" + str(input_root),
            "--out=Library/Bee/artifacts/Android/ManagedStripped",
            "--profiler-output-file=/fixture/trace",
            "--include-link-xml=" + str(input_root / "TypesInScenes.xml"),
            "--include-link-xml=" + str(android / "Tools/AndroidNativeLink.xml"),
            "--include-link-xml=" + str(capture / "empty-linker.xml"),
            "--editor-data-file=" + str(input_root / "EditorToUnityLinkerData.json"),
            "--engine-modules-asset-file=" + str(android / "modules.asset"),
            "--include-unity-root-assembly=" + str(input_root / "Assembly-CSharp.dll"),
        ]
        plan = arguments(shlex.join(tokens), launcher, project, input_root, capture, android)
        self.assertEqual([x for x in plan if isinstance(x, str)], sorted(LITERALS))
        self.assertNotIn("--enable-analytics", plan)
        self.assertEqual(
            [x["path"] for x in plan if isinstance(x, dict) and x.get("prefix") == "--include-link-xml="],
            ["inputs/TypesInScenes.xml", "sdk/AndroidNativeLink.xml", "empty-linker.xml"],
        )
        for mutant in (
            tokens + ["--unknown"],
            [t.replace("/fixture/Temp/Managed/TypesInScenes.xml", "/foreign/root.xml") for t in tokens],
            [t.replace("--out=Library/Bee/artifacts/Android/ManagedStripped", "--out=../escape") for t in tokens],
            [t.replace("--platform=Android", "--platform=Windows") for t in tokens],
            tokens[:-1],
        ):
            with self.assertRaises(ValueError):
                arguments(shlex.join(mutant), launcher, project, input_root, capture, android)

    def test_staged_drift_refuses_before_tool_and_keeps_first_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            (stage / "input.dll").write_bytes(b"changed")
            (stage / "input-manifest.json").write_text(json.dumps({"input.dll": hashlib.sha256(b"expected").hexdigest()}))
            with patch("phone_linker.subprocess.run") as run:
                self.assertFalse(strip(stage, root / "tools", root / "output"))
                run.assert_not_called()
            self.assertIn("input drift", json.loads((root / "output/result.json").read_text())["failure"])
            with self.assertRaises(FileExistsError):
                strip(stage, root / "tools", root / "output")

    def test_zero_exit_without_fixture_output_does_not_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            (stage / "plan.json").write_text(json.dumps({"arguments": ["--platform=Android"], "game_inputs": False, "desktop_editor_roots": True}))
            (stage / "input-manifest.json").write_text(json.dumps({"plan.json": hashlib.sha256((stage / "plan.json").read_bytes()).hexdigest()}))
            with patch("phone_linker.subprocess.run", return_value=type("Result", (), {"returncode": 0})()):
                self.assertFalse(strip(stage, root / "tools", root / "output"))
            self.assertIn("no fixture assembly", json.loads((root / "output/result.json").read_text())["failure"])
