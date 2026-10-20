import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from phone_linker import LITERALS, arguments, sha, strip, stripped_input


class PhoneLinkerTests(unittest.TestCase):
    def test_converter_handoff_binds_outputs_exact_assemblies_and_report_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            project, stage, output = (root / name for name in ("project", "stage", "output"))
            original = project / "Library/Bee/artifacts/Android/ManagedStripped"
            stripped = output / "stripped"
            for path in (original, stripped, stage):
                path.mkdir(parents=True)
            for path in (original, stripped):
                (path / "Fixture.dll").write_bytes(b"fixture assembly")
                (path / "Fixture.pdb").write_bytes(b"fixture symbols")
            reports = [
                {"report": {"modules": [{"name": "Alpha", "kept": True}, {"name": "Beta", "kept": False}]}},
                {"report": {"modules": [{"name": "Beta", "kept": False}, {"name": "Alpha", "kept": True}]}},
            ]
            for path, report in zip((original, stripped), reports):
                (path / "UnityLinkerToEditorData.json").write_text(json.dumps(report))
            (original / "analytics.json").write_text("desktop diagnostic")
            (stage / "tool.dll").write_bytes(b"supplied tool")
            (stage / "input-manifest.json").write_text(json.dumps({"tool.dll": sha(stage / "tool.dll")}))
            fixture = {"project": str(project), "apk": str(root / "fixture.apk"), "sha256": "fixture-apk"}
            (stage / "stage-receipt.json").write_text(json.dumps({"request": fixture | {"capture": str(root / "capture")}}))
            result = {"success": True, "exit_code": 0, "input_manifest_sha256": sha(stage / "input-manifest.json")}

            def save_result():
                result["outputs"] = {p.relative_to(stripped).as_posix(): sha(p) for p in stripped.rglob("*") if p.is_file()}
                (output / "result.json").write_text(json.dumps(result))
                return {"stage": str(stage), "output": str(output), "result_sha256": sha(output / "result.json")}

            request = save_result()
            before = (stripped / "UnityLinkerToEditorData.json").read_bytes()
            self.assertEqual(stripped_input(request, fixture), stripped)
            self.assertEqual((stripped / "UnityLinkerToEditorData.json").read_bytes(), before)
            (stripped / "Fixture.dll").write_bytes(b"changed assembly")
            with self.assertRaisesRegex(ValueError, "output drift"):
                stripped_input(request, fixture)
            request = save_result()
            with self.assertRaisesRegex(ValueError, "closure differs"):
                stripped_input(request, fixture)
            (stripped / "Fixture.dll").write_bytes(b"fixture assembly")
            reports[1]["report"]["modules"][0]["kept"] = True
            (stripped / "UnityLinkerToEditorData.json").write_text(json.dumps(reports[1]))
            request = save_result()
            with self.assertRaisesRegex(ValueError, "report entries differ"):
                stripped_input(request, fixture)
            with self.assertRaisesRegex(ValueError, "another fixture"):
                stripped_input(request, fixture | {"sha256": "other-apk"})

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
