import tempfile
import unittest
from pathlib import Path
import json
import subprocess
import sys
import hashlib

import UnityPy

from phone_bundle import ASSET, PAYLOAD, make_bundle
from phone_content import stage, validate_linker_capture, validate_oracle


class PhoneContentTests(unittest.TestCase):
    def test_linker_snapshot_requires_same_build_complete_input_set_and_unchanged_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary)
            capture = attempt / "linker-capture"
            inputs = capture / "inputs"
            inputs.mkdir(parents=True)
            rows = []
            for name in ("Assembly-CSharp.dll", "TypesInScenes.xml", "EditorToUnityLinkerData.json"):
                data = ("authored " + name).encode()
                (inputs / name).write_bytes(data)
                rows.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            build = {"unity": "2021.3.45f2", "source_commit": "c" * 40, "build_report_guid": "authored-build"}
            (attempt / "player-build.json").write_text(json.dumps(build))
            receipt = build | {"files": rows}
            (capture / "receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(validate_linker_capture(attempt, "c" * 40)["files"], 3)
            for mutant in (
                receipt | {"build_report_guid": "another-build"},
                receipt | {"source_commit": "d" * 40},
                receipt | {"files": rows[:-1]},
                receipt | {"files": rows + rows[:1]},
            ):
                (capture / "receipt.json").write_text(json.dumps(mutant))
                with self.assertRaises(RuntimeError):
                    validate_linker_capture(attempt, "c" * 40)
            (capture / "receipt.json").write_text(json.dumps(receipt))
            (inputs / "Assembly-CSharp.dll").write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "input drift"):
                validate_linker_capture(attempt, "c" * 40)

    def test_oracle_requires_actual_pinned_version_and_successful_native_contract(self):
        report = {"unity": "2021.3.45f2", "bundleLoaded": True, "textMatched": True, "unloaded": True}
        validate_oracle(report)
        for change in ({"unity": "2021.3.33f1"}, {"unity": None}, {"unloaded": False}, {"failure": "native failure"}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                validate_oracle(report | change)

    def test_authored_schema_bundle_contains_android_text_without_template(self):
        data = make_bundle()
        self.assertEqual(data, make_bundle())
        env = UnityPy.load(data)
        self.assertEqual(len(env.objects), 2)
        text = env.container[ASSET].read()
        self.assertEqual(text.m_Script, PAYLOAD)
        self.assertEqual(text.assets_file.unity_version, "2021.3.45f2")
        self.assertEqual(text.assets_file.target_platform.name, "Android")

    def test_variable_length_utf8_payload_keeps_native_object_alignment(self):
        for payload in ("", "a", "abc", "é漢字\n"):
            with self.subTest(payload=payload):
                text = UnityPy.load(make_bundle(payload)).container[ASSET].read()
                self.assertEqual(text.m_Script, payload)

    def test_standalone_writer_needs_only_standard_library_and_refuses_overwrite(self):
        script = Path(__file__).resolve().parents[1] / "scripts/lab/phone_bundle.py"
        with tempfile.TemporaryDirectory() as root:
            bundle = Path(root) / "fixture.bundle"
            command = [sys.executable, "-I", "-S", str(script), str(bundle)]
            result = subprocess.run(command, text=True, capture_output=True, check=True)
            self.assertEqual(bundle.read_bytes(), make_bundle())
            self.assertEqual(json.loads(result.stdout)["bytes"], len(make_bundle()))
            refusal = subprocess.run(command, capture_output=True)
            self.assertNotEqual(refusal.returncode, 0)
            self.assertEqual(bundle.read_bytes(), make_bundle())

    def test_stage_refuses_to_overwrite_an_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "project"
            receipt = stage(project)
            self.assertFalse(receipt["device_accepted"])
            self.assertFalse(receipt["game_inputs"])
            with self.assertRaises(FileExistsError):
                stage(project)
