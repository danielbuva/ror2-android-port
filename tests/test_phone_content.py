import tempfile
import unittest
from pathlib import Path
import json
import subprocess
import sys
import hashlib
from unittest.mock import patch

import UnityPy

from phone_bundle import ASSET, PAYLOAD, make_bundle
from phone_content import run_editor, stage, validate_ambient_capture, validate_linker_capture, validate_oracle


class PhoneContentTests(unittest.TestCase):
    def test_ambient_fixture_compiles_against_exact_editor_api(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = sdk / "MonoBleedingEdge/bin/mono"
        compiler = sdk / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.exists() or not compiler.exists():
            self.skipTest("Exact editor Mono/Roslyn unavailable")
        with tempfile.TemporaryDirectory() as root:
            args = [str(mono), str(compiler), "/nologo", "/target:library", "/out:" + str(Path(root) / "fixture.dll")]
            args += ["/r:" + str(path) for path in sorted((sdk / "Managed/UnityEngine").glob("UnityEngine*.dll"))]
            args += ["/r:" + str(sdk / "Managed/UnityEditor.dll"), str(Path(__file__).resolve().parents[1] / "tools/phone-build/AmbientSkyFixture.cs")]
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_graphical_capture_keeps_editor_alive_and_requires_real_observation_bytes(self):
        def launched(args, *, env, **kwargs):
            report_path = Path(env["ROR2_PHONE_ORACLE_REPORT"])
            ambient = "ROR2_AMBIENT_CAPTURE" in env
            self.assertEqual("-nographics" not in args, ambient)
            self.assertEqual("-quit" not in args, ambient)
            self.assertIn("-batchmode", args)
            if ambient:
                self.assertIn("AmbientSkyFixture.Begin", args)
                report = {"unity": "2021.3.45f2", "gpu": "Metal", "captureCompleted": True}
                receipt = {"faces": [], "sh": {}}
                for index in range(7):
                    data = bytes(108 if index == 6 else 64 * 64 * 16)
                    name = "observation-" + str(index) + ".bin"
                    (report_path.parent / name).write_bytes(data)
                    row = {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
                    if index == 6:
                        receipt["sh"] = row | {"cached": False}
                    else:
                        receipt["faces"].append(row | {"face": index, "width": 64, "height": 64, "format": 89})
                (report_path.parent / "capture-complete.json").write_text(json.dumps(receipt))
                (report_path.parent / "ambient.gputrace").write_bytes(b"authored trace fixture")
            else:
                self.assertIn("ContentFixtureBuilder.Check", args)
                report = {"unity": "2021.3.45f2", "bundleLoaded": True, "textMatched": True, "unloaded": True}
            report_path.write_text(json.dumps(report))
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with (
            tempfile.TemporaryDirectory() as root,
            patch("common.WORK", Path(root)),
            patch.dict("os.environ", {"UNITY_EDITOR": "authored-editor"}),
            patch("build_lock.host_build_lock") as lock,
        ):
            for ambient in (False, True):
                project = Path(root) / "rebuild/phone-content" / str(ambient) / "project"
                receipt = stage(project, ambient=ambient)
                self.assertEqual(receipt["ambient_capture"], ambient)
                self.assertEqual((project / "Assets/Editor/AmbientSkyFixture.cs").exists(), ambient)
                with (
                    patch("phone_content.subprocess.run", side_effect=launched),
                    patch(
                        "phone_content.subprocess.check_output",
                        side_effect=lambda args, **kwargs: str(Path(root) / ".git") if "--git-common-dir" in args else "c" * 40,
                    ),
                    patch("builtins.print"),
                ):
                    run_editor(project, ambient=ambient)
                self.assertTrue(lock.called)
                if ambient:
                    attempt = next(project.parent.glob("editor-ambient-capture-*"))
                    captured = validate_ambient_capture(attempt)
                    captured["sh"]["cached"] = True
                    (attempt / "capture-complete.json").write_text(json.dumps(captured))
                    with self.assertRaisesRegex(RuntimeError, "uncached SH"):
                        validate_ambient_capture(attempt)
                    captured["sh"]["cached"] = False
                    (attempt / "capture-complete.json").write_text(json.dumps(captured))
                    (attempt / captured["faces"][0]["file"]).write_bytes(b"changed")
                    with self.assertRaisesRegex(RuntimeError, "bytes changed"):
                        validate_ambient_capture(attempt)

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
            native = "tools/phone-build/NativeScriptSchemaFixture.cs"
            source = Path(__file__).resolve().parents[1] / native
            self.assertEqual(
                ((project / "Assets/NativeScriptSchemaFixture.cs").read_bytes(), receipt["sources"][native]),
                (source.read_bytes(), hashlib.sha256(source.read_bytes()).hexdigest()),
            )
            with self.assertRaises(FileExistsError):
                stage(project)
