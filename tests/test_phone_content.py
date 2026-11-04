import tempfile
import unittest
from pathlib import Path
import json
import subprocess
import sys
import hashlib
import copy
from unittest.mock import patch

import UnityPy

from phone_bundle import ASSET, PAYLOAD, make_bundle
from phone_content import native_content_request, run_editor, stage, validate_ambient_capture, validate_linker_capture, validate_native_content, validate_oracle


class PhoneContentTests(unittest.TestCase):
    def test_content_builder_compiles_against_exact_editor_api(self):
        sdk = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents")
        mono = sdk / "MonoBleedingEdge/bin/mono"
        compiler = sdk / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
        if not mono.is_file() or not compiler.is_file():
            self.skipTest("Exact editor Mono/Roslyn unavailable")
        source = Path(__file__).resolve().parents[1] / "tools/phone-build"
        with tempfile.TemporaryDirectory() as root:
            args = [str(mono), str(compiler), "/nologo", "/target:library", "/define:UNITY_EDITOR", "/out:" + str(Path(root) / "fixture.dll")]
            args += ["/r:" + str(path) for path in sorted((sdk / "Managed/UnityEngine").glob("UnityEngine*.dll"))]
            args += ["/r:" + str(sdk / "Managed/UnityEditor.dll")]
            args += [str(source / name) for name in ("ContentFixtureBuilder.cs", "ContentFixture.cs", "NativeScriptSchemaFixture.cs")]
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_content_requires_each_typed_load_and_bound_bundle_destruction(self):
        with tempfile.TemporaryDirectory() as root:
            attempt = Path(root).resolve()
            bundle = attempt / "authored.bundle"
            bundle.write_bytes(b"authored native request control")
            request = {
                "path": str(bundle),
                "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "assets": [{"name": "lighting", "type": "LightingSettings"}, {"name": "occlusion", "type": "OcclusionCullingData"}],
            }
            request_path = attempt / "native-content-request.json"
            request_path.write_text(json.dumps(request))
            report = {
                "unity": "2021.3.45f2",
                "source_commit": "c" * 40,
                "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
                "path": str(bundle),
                "sha256": request["sha256"],
                "count": 2,
                "unloaded": True,
                "assets": [asset | {"loaded_name": "", "loaded_type": "UnityEngine." + asset["type"]} for asset in request["assets"]],
            }
            output = attempt / "native-content-check.json"
            output.write_text(json.dumps(report))
            self.assertEqual(validate_native_content(attempt, "c" * 40)["count"], 2)
            for mutate in (
                lambda r: r.update(sha256="0" * 64),
                lambda r: r.update(request_sha256="0" * 64),
                lambda r: r.update(count=1),
                lambda r: r.update(unloaded=False),
                lambda r: r.update(failure="native deserialize failed"),
                lambda r: r["assets"].pop(),
                lambda r: r["assets"][0].update(loaded_type="UnityEngine.Object"),
                lambda r: r["assets"][1].update(name="wrong-address"),
            ):
                changed = copy.deepcopy(report)
                mutate(changed)
                output.write_text(json.dumps(changed))
                with self.assertRaises(RuntimeError):
                    validate_native_content(attempt, "c" * 40)
            for change in ({"assets": []}, {"assets": [{"name": "shader", "type": "Shader"}]}, {"assets": request["assets"] * 2}, {"path": "relative.bundle"}):
                request_path.write_text(json.dumps(request | change))
                with self.assertRaises(RuntimeError):
                    native_content_request(request_path)
            request_path.write_text(json.dumps(request))
            bundle.write_bytes(b"changed bundle")
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                native_content_request(request_path)

    def test_editor_runner_requires_native_content_report_when_requested(self):
        def launched(args, *, env, **kwargs):
            oracle = Path(env["ROR2_PHONE_ORACLE_REPORT"])
            self.assertEqual(Path(env["ROR2_PHONE_NATIVE_CONTENT_CHECK"]), oracle.parent / "native-content-request.json")
            oracle.write_text(json.dumps({"unity": "2021.3.45f2", "bundleLoaded": True, "textMatched": True, "unloaded": True}))
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with tempfile.TemporaryDirectory() as root:
            bundle = Path(root) / "control.bundle"
            bundle.write_bytes(b"authored control")
            request = Path(root) / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "path": str(bundle),
                        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                        "assets": [{"name": "lighting", "type": "LightingSettings"}],
                    }
                )
            )
            with (
                patch("common.WORK", Path(root)),
                patch.dict("os.environ", {"UNITY_EDITOR": "authored-editor", "ROR2_PHONE_NATIVE_CONTENT_CHECK": str(request)}),
                patch("build_lock.host_build_lock"),
                patch("phone_content.subprocess.run", side_effect=launched),
                patch(
                    "phone_content.subprocess.check_output",
                    side_effect=lambda args, **kwargs: str(Path(root) / ".git") if "--git-common-dir" in args else "c" * 40,
                ),
                patch("builtins.print"),
            ):
                project = Path(root) / "rebuild/phone-content/native/project"
                stage(project)
                with self.assertRaisesRegex(RuntimeError, "Exact-editor fixture failed"):
                    run_editor(project)
            outcome = json.loads(next(project.parent.glob("editor-check-*/receipt.json")).read_text())
            self.assertIn("native-content-check.json", outcome["oracle_error"])
            self.assertIsNone(outcome["native_content"])

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
