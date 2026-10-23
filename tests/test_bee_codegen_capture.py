from __future__ import annotations

import ast
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(os.environ.get("ROR2LAB_TEST_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts/lab"))
from bee_codegen_capture import (  # noqa: E402
    EDITOR_VERSION,
    CaptureError,
    _trace_events,
    collect_request_capture,
    editor_version_from_toolchain,
    inspect_codegen_node,
    parse_player_invocation,
    validate_build_result,
    verify_fresh_trace,
)
from common import toolchain  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/synthetic-multiline.traceevents"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def trace() -> bytes:
    return b'{"pid":"il2cpp_in_graph","tid":1,"ts":10,"dur":5,"ph":"X","name":"il2cpp.exe"},\n'


def fake_dag(project: Path) -> tuple[dict, list[str]]:
    managed = [
        "Library/Bee/artifacts/Android/ManagedStripped/Assembly-CSharp.dll",
        "Library/Bee/artifacts/Android/ManagedStripped/RoR2.dll",
    ]
    trace_path = (project / "Library/Bee/artifacts/il2cpp_conv_current.traceevents").as_posix()
    rsp_relative = "Library/Bee/artifacts/rsp/123.rsp"
    rsp_path = project / rsp_relative
    rsp_path.parent.mkdir(parents=True, exist_ok=True)
    rsp_path.write_text("--convert-to-cpp " + " ".join(f'--assembly="{path}"' for path in managed) + f' --profiler-output-file="{trace_path}"')
    for i, path in enumerate(managed):
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"managed-{i}".encode())
    trace_target = project / "Library/Bee/artifacts/il2cpp_conv_current.traceevents"
    trace_target.parent.mkdir(parents=True, exist_ok=True)
    trace_target.write_bytes(trace())
    dag = {
        "Nodes": [
            {
                "Annotation": "IL2CPP_CodeGen " + trace_path,
                "Action": f'"/Unity/il2cpp" @"{rsp_relative}"',
                "ProfilerOutput": trace_path,
                "Inputs": [*managed, "/Unity/il2cpp/il2cpp_root"],
                "Outputs": [trace_path],
            }
        ]
    }
    (project / "Library/Bee/Player123.dag").parent.mkdir(parents=True, exist_ok=True)
    (project / "Library/Bee/Player123.dag").write_bytes(b"active raw graph")
    return dag, managed


def fixture_log(project: Path, *, working: str | None = None) -> bytes:
    return (
        'Starting: /Unity/bee_backend --profile="Library/Bee/backend_profiler0.traceevents" '
        '--stdin-canary --dagfile="Library/Bee/Player123.dag" --continue-on-failure Player\n'
        f"WorkingDir: {working or project}\n"
        "ExitCode: 0 Duration: 0s476ms\n"
    ).encode()


def request_receipts(project: Path, log_slice: bytes, trace_bytes: bytes):
    guid = "0123456789abcdef0123456789abcdef"
    pre = {
        "schema": "ror2lab-bee-prebuild-v2",
        "scan_root": "Library/Bee",
        "scan_started_utc": "2026-01-01T00:00:00.0000000Z",
        "scan_completed_utc": "2026-01-01T00:00:00.0000001Z",
        "baseline_file_count": 0,
        "baseline_sha256": digest(b""),
        "editor_version": EDITOR_VERSION,
        "request_id": "req-1",
        "source_commit": "a" * 40,
        "input_id": "b" * 64,
        "build_report_guid": guid,
        "target": "Android",
        "log_byte_offset": 100,
        "editor_log_path": str(project / "Editor.log"),
        "editor_pid": 77,
        "editor_log_prefix_sha256": digest(b"x" * 100),
        "baseline_files": [],
    }
    pre_bytes = json.dumps(pre, sort_keys=True, separators=(",", ":")).encode()
    post = {
        "schema": "ror2lab-bee-postprocess-v2",
        "prebuild_sha256": digest(pre_bytes),
        "request_id": "req-1",
        "source_commit": "a" * 40,
        "input_id": "b" * 64,
        "build_report_guid": guid,
        "target": "Android",
        "build_report_result": "Succeeded",
        "build_report_errors": 0,
        "log_byte_start": 100,
        "log_byte_end": 100 + len(log_slice),
        "log_slice_sha256": digest(log_slice),
        "log_slice_path": "lab-build/player-linker-inputs/req-1.bee-log-slice",
        "build_report_output_path": str(project / "verified.apk"),
    }
    capture_dir = project / "lab-build/player-linker-inputs"
    capture_dir.mkdir(parents=True, exist_ok=True)
    (capture_dir / "req-1.bee-pre.json").write_bytes(pre_bytes)
    (capture_dir / "req-1.bee-post.json").write_text(json.dumps(post))
    (capture_dir / "req-1.bee-log-slice").write_bytes(log_slice)
    (project / "editor").mkdir(parents=True, exist_ok=True)
    (project / "editor/lab-process.json").write_text(json.dumps({"log": str(project / "Editor.log"), "pid": 77}))
    (project / "Editor.log").write_bytes(b"x" * 100 + log_slice)
    apk = project / "verified.apk"
    apk.write_bytes(b"apk bytes")
    result = {
        "request_id": "req-1",
        "success": True,
        "errors": 0,
        "build_report_guid": guid,
        "input_id": "b" * 64,
        "source": {"commit": "a" * 40},
        "apk": str(apk),
        "apk_sha256": digest(apk.read_bytes()),
        "build_report_output_path": str(apk),
    }
    return pre_bytes, post, result


class BeeCodegenCaptureTests(unittest.TestCase):
    def test_synthetic_multiline_trace_parses_nested_records_and_one_conversion_event(self):
        contents = FIXTURE.read_bytes()
        self.assertLess(len(contents), 2_000)
        self.assertEqual(len(_trace_events(contents)), 2)
        self.assertEqual(
            verify_fresh_trace(contents, baseline_sha256=digest(b"old trace"))["il2cpp_event_count"],
            1,
        )

    def test_trace_parser_refuses_truncated_nonfinite_or_invalid_conversion(self):
        contents = FIXTURE.read_bytes()
        with self.assertRaises(CaptureError):
            _trace_events(contents[:-20])
        with self.assertRaises(CaptureError):
            _trace_events(b'{"name":"x","ts":NaN},')
        for malformed in (
            b',{"name":"x"},',
            b'{"name":"x"},,{"name":"y"},',
            b'{"name":"x"} {"name":"y"},',
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(CaptureError):
                    _trace_events(malformed)
        self.assertEqual(_trace_events(b'{"name":"x"},'), [{"name": "x"}])
        with self.assertRaises(CaptureError):
            verify_fresh_trace(
                b'{"pid":"il2cpp_in_graph","ph":"X","name":"il2cpp.exe","ts":1,"dur":-1}',
                baseline_sha256=None,
            )
        with self.assertRaises(CaptureError):
            verify_fresh_trace(trace(), baseline_sha256=digest(trace()))

    def test_active_graph_requires_exact_profiler_output_across_node_and_rsp(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            dag, _ = fake_dag(project)
            contract = inspect_codegen_node(dag, project_root=project)
            self.assertEqual(
                contract["trace_output"],
                "Library/Bee/artifacts/il2cpp_conv_current.traceevents",
            )
            dag["Nodes"][0]["ProfilerOutput"] = "/tmp/wrong.traceevents"
            with self.assertRaises(CaptureError):
                inspect_codegen_node(dag, project_root=project)

    def test_request_capture_binds_successful_report_and_snapshots_only_declared_dlls(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            dag, managed = fake_dag(project)
            dag_path = project / "Library/Bee/Player123.dag.json"
            dag_path.write_text(json.dumps(dag))
            trace_bytes = FIXTURE.read_bytes()
            (project / "Library/Bee/artifacts/il2cpp_conv_current.traceevents").write_bytes(trace_bytes)
            profile = project / "Library/Bee/backend_profiler0.traceevents"
            profile.write_bytes(b"bee profile")
            log_slice = fixture_log(project)
            pre, post, result = request_receipts(project, log_slice, trace_bytes)
            destination = project / "receipt"
            receipt = collect_request_capture(
                project_root=project,
                work_root=project,
                snapshot_destination=destination,
                final_result=result,
                request_id="req-1",
                source_commit="a" * 40,
                input_id="b" * 64,
                editor_version=EDITOR_VERSION,
            )
            self.assertEqual(receipt["build_report_guid"], "0123456789abcdef0123456789abcdef")
            self.assertFalse(receipt["argv_vector_binding"])
            self.assertEqual([row["path"] for row in receipt["managed_inputs"]], managed)
            self.assertEqual(len(receipt["metadata_snapshots"]), 4)
            self.assertTrue(all((destination / "managed" / row["snapshot_name"]).is_file() for row in receipt["managed_inputs"]))
            self.assertFalse(any("il2cppOutput" in row["path"] for row in receipt["managed_inputs"]))

    def test_request_capture_refuses_stale_trace_wrong_report_or_wrong_working_dir(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            dag, _ = fake_dag(project)
            (project / "Library/Bee/Player123.dag.json").write_text(json.dumps(dag))
            trace_path = project / "Library/Bee/artifacts/il2cpp_conv_current.traceevents"
            trace_path.write_bytes(trace())
            (project / "Library/Bee/backend_profiler0.traceevents").write_bytes(b"profile")
            log_slice = fixture_log(project)
            pre, post, result = request_receipts(project, log_slice, trace())
            pre_value = json.loads(pre)
            pre_value["baseline_files"] = [
                {
                    "path": "Library/Bee/artifacts/il2cpp_conv_current.traceevents",
                    "size": trace_path.stat().st_size,
                    "sha256": digest(trace()),
                }
            ]
            pre_value["baseline_file_count"] = len(pre_value["baseline_files"])
            canonical = "\n".join(f"{row['path']}\t{row['size']}\t{row['sha256']}" for row in pre_value["baseline_files"]).encode()
            pre_value["baseline_sha256"] = digest(canonical)
            pre = json.dumps(pre_value, sort_keys=True, separators=(",", ":")).encode()
            post["prebuild_sha256"] = digest(pre)
            capture_dir = project / "lab-build/player-linker-inputs"
            (capture_dir / "req-1.bee-pre.json").write_bytes(pre)
            post_path = capture_dir / "req-1.bee-post.json"
            with self.assertRaises(CaptureError):
                collect_request_capture(
                    project_root=project,
                    work_root=project,
                    snapshot_destination=project / "stale",
                    final_result=result,
                    request_id="req-1",
                    source_commit="a" * 40,
                    input_id="b" * 64,
                    editor_version=EDITOR_VERSION,
                )
            post["build_report_guid"] = "fedcba9876543210fedcba9876543210"
            post_path.write_text(json.dumps(post))
            with self.assertRaises(CaptureError):
                collect_request_capture(
                    project_root=project,
                    work_root=project,
                    snapshot_destination=project / "wrong-report",
                    final_result=result,
                    request_id="req-1",
                    source_commit="a" * 40,
                    input_id="b" * 64,
                    editor_version=EDITOR_VERSION,
                )
            post["build_report_guid"] = "0123456789abcdef0123456789abcdef"
            wrong_log = fixture_log(project, working="/wrong/project")
            (capture_dir / "req-1.bee-log-slice").write_bytes(wrong_log)
            (project / "Editor.log").write_bytes(b"x" * 100 + wrong_log)
            post["log_byte_end"] = 100 + len(wrong_log)
            post["log_slice_sha256"] = digest(wrong_log)
            post_path.write_text(json.dumps(post))
            with self.assertRaises(CaptureError):
                collect_request_capture(
                    project_root=project,
                    work_root=project,
                    snapshot_destination=project / "wrong-working-dir",
                    final_result=result,
                    request_id="req-1",
                    source_commit="a" * 40,
                    input_id="b" * 64,
                    editor_version=EDITOR_VERSION,
                )

    def test_prebuild_baseline_digest_must_bind_exact_inventory_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            dag, _ = fake_dag(project)
            (project / "Library/Bee/Player123.dag.json").write_text(json.dumps(dag))
            trace_path = project / "Library/Bee/artifacts/il2cpp_conv_current.traceevents"
            trace_path.write_bytes(trace())
            (project / "Library/Bee/backend_profiler0.traceevents").write_bytes(b"profile")
            log_slice = fixture_log(project)
            pre, post, result = request_receipts(project, log_slice, trace())
            pre_value = json.loads(pre)
            pre_value["baseline_files"] = [
                {
                    "path": "Library/Bee/artifacts/il2cpp_conv_current.traceevents",
                    "size": trace_path.stat().st_size,
                    "sha256": digest(trace()),
                }
            ]
            pre_value["baseline_file_count"] = 1
            encoded = json.dumps(pre_value, sort_keys=True, separators=(",", ":")).encode()
            post["prebuild_sha256"] = digest(encoded)
            capture_dir = project / "lab-build/player-linker-inputs"
            (capture_dir / "req-1.bee-pre.json").write_bytes(encoded)
            post_path = capture_dir / "req-1.bee-post.json"
            post_path.write_text(json.dumps(post))
            with self.assertRaisesRegex(CaptureError, "inventory digest"):
                collect_request_capture(
                    project_root=project,
                    work_root=project,
                    snapshot_destination=project / "tampered-baseline",
                    final_result=result,
                    request_id="req-1",
                    source_commit="a" * 40,
                    input_id="b" * 64,
                    editor_version=EDITOR_VERSION,
                )

    def test_player_invocation_rejects_unparsed_player_line_even_with_valid_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            valid = fixture_log(project).decode()
            malformed = (
                'Starting: /Unity/bee_backend --profile="Library/Bee/backend_profiler0.traceevents" '
                '--dagfile="foreign/Player.dag" --continue-on-failure Player\n'
                f"WorkingDir: {project}\nExitCode: 0 Duration: 0s1ms\n"
            )
            with self.assertRaises(CaptureError):
                parse_player_invocation(valid + malformed)

    def test_build_bridge_uses_full_revision_qualified_pinned_toolchain_version(self):
        pin = toolchain()
        expected = f"{pin['unity_version']} ({pin['unity_revision']})"
        self.assertEqual(editor_version_from_toolchain(pin), expected)
        self.assertEqual(expected, EDITOR_VERSION)
        build_tree = ast.parse((ROOT / "scripts/lab/build.py").read_text())
        bridge_calls = [
            node
            for node in ast.walk(build_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "collect_request_capture"
        ]
        self.assertEqual(len(bridge_calls), 1)
        version_arg = next(keyword.value for keyword in bridge_calls[0].keywords if keyword.arg == "editor_version")
        self.assertIsInstance(version_arg, ast.Call)
        self.assertEqual(version_arg.func.id, "editor_version_from_toolchain")
        self.assertIsInstance(version_arg.args[0], ast.Call)
        self.assertEqual(version_arg.args[0].func.id, "toolchain")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            log = (
                fixture_log(project).decode()
                + 'LAB_BUILD_RESULT {"request_id":"req-1","build_report_guid":"0123456789abcdef0123456789abcdef","success":true,"errors":0}\n'
            )
            args = dict(
                request_id="req-1",
                report_guid="0123456789abcdef0123456789abcdef",
                source_commit="a" * 40,
                input_id="b" * 64,
                apk_sha256="c" * 64,
            )
            self.assertEqual(
                validate_build_result(log, editor_version=editor_version_from_toolchain(pin), **args)["editor_version"],
                EDITOR_VERSION,
            )
            with self.assertRaises(CaptureError):
                validate_build_result(log, editor_version=pin["unity_version"], **args)

    def test_player_invocation_requires_single_success_and_log_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            text = fixture_log(project).decode()
            self.assertEqual(parse_player_invocation(text)["exit_code"], 0)
            with self.assertRaises(CaptureError):
                parse_player_invocation(text + text)
            with self.assertRaises(CaptureError):
                parse_player_invocation(text.replace("ExitCode: 0", "ExitCode: 1"))
            with self.assertRaises(CaptureError):
                parse_player_invocation(text.replace("--profile=", "--no-profile="))

    def test_player_invocation_accepts_only_the_evidenced_single_dag_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            root = str(project / "Unity Project With Spaces")
            dag = "Library/Bee/Player123.dag"
            first = (
                'Starting: /Unity/bee_backend --profile="Library/Bee/backend_profiler0.traceevents" '
                f'--stdin-canary --dagfile="{dag}" --continue-on-failure Player\n'
                f"WorkingDir: {root}\nExitCode: 4 Duration: 0s1ms\n"
            )
            editor_root = "/Applications/Unity Hub/Editor/2021.3.45f2"
            runner = f"{editor_root}/Unity.app/Contents/Tools/netcorerun/netcorerun"
            program = f"{editor_root}/PlaybackEngines/AndroidPlayer/AndroidPlayerBuildProgram.exe"
            context = f"{editor_root}/PlaybackEngines/AndroidPlayer/Bee:{editor_root}/Unity.app/Contents/Tools/BuildPipeline"
            program_start = (
                f'Starting: "{runner}" "{program}" "{context}" '
                f'"{dag}.json" "{dag.removesuffix(".dag")}-inputdata.json" '
                '"Library/Bee/buildprogram0.traceevents"\n'
            )
            rebuild = (
                f"Rebuilding DAG because FileSignature timestamp changed: {dag.removesuffix('.dag')}-inputdata.json\n"
                "*** Tundra requires additional run (0.03 seconds), 0 items updated, 0 evaluated\n"
                + program_start
                + f"WorkingDir: {root}\nExitCode: 0 Duration: 0s1ms\n"
            )
            final = (
                'Starting: /Unity/bee_backend --profile="Library/Bee/backend_profiler1.traceevents" '
                f'--stdin-canary --dagfile="{dag}" --continue-on-failure --dagfilejson="{dag}.json" Player\n'
                f"WorkingDir: {root}\nExitCode: 0 Duration: 1s\n"
            )
            parsed = parse_player_invocation(first + rebuild + final)
            direct_root = "/Applications/Unity/Hub/Editor/2021.3.45f2"
            direct_rebuild = rebuild.replace(editor_root, direct_root)
            direct_runner = f"{direct_root}/Unity.app/Contents/Tools/netcorerun/netcorerun"
            direct_program = f"{direct_root}/PlaybackEngines/AndroidPlayer/AndroidPlayerBuildProgram.exe"
            direct_rebuild = direct_rebuild.replace(f'"{direct_runner}"', direct_runner)
            direct_rebuild = direct_rebuild.replace(f'"{direct_program}"', direct_program)
            self.assertEqual(parse_player_invocation(first + direct_rebuild + final), parsed)
            unquoted_program = rebuild.replace(f'"{program}"', program)
            with self.assertRaises(CaptureError):
                parse_player_invocation(first + unquoted_program + final)
            self.assertEqual(
                parsed,
                {
                    "dag": dag,
                    "profile": "Library/Bee/backend_profiler1.traceevents",
                    "working_directory": root,
                    "exit_code": 0,
                },
            )

            refused = (
                (first + final, "missing retry witness"),
                (
                    first + rebuild.replace("Tundra requires additional run", "Tundra skipped rerun") + final,
                    "missing Tundra witness",
                ),
                (
                    first + rebuild.replace("Player123.dag.json", "Other.dag.json") + final,
                    "mismatched BuildProgram DAG",
                ),
                (
                    first + rebuild.replace(f"WorkingDir: {root}", "WorkingDir: /other", 1) + final,
                    "mismatched retry cwd",
                ),
                (
                    first + rebuild + final.replace(dag, "Library/Bee/Other.dag"),
                    "mismatched final DAG",
                ),
                (
                    first + rebuild + final.replace(f"WorkingDir: {root}", "WorkingDir: /other"),
                    "mismatched final cwd",
                ),
                (
                    first.replace("ExitCode: 4", "ExitCode: 2") + rebuild + final,
                    "unsupported failed exit",
                ),
                (first + rebuild + final + final, "two successful Player attempts"),
                (
                    first + rebuild.replace("ExitCode: 0 Duration: 0s1ms", "ExitCode: 1 Duration: 0s1ms") + final,
                    "failed BuildProgram retry",
                ),
                (
                    first
                    + rebuild.replace(
                        program,
                        program.replace(
                            "AndroidPlayerBuildProgram.exe",
                            "NotAndroidPlayerBuildProgram.exe",
                        ),
                    )
                    + final,
                    "prefixed executable decoy",
                ),
                (
                    first
                    + rebuild.replace(
                        program,
                        program.replace(
                            "AndroidPlayerBuildProgram.exe",
                            "AndroidPlayerBuildProgram.exe.wrapper",
                        ),
                    )
                    + final,
                    "suffixed executable decoy",
                ),
                (
                    first + rebuild.replace(program, "/Other/Unity/AndroidPlayerBuildProgram.exe") + final,
                    "program from different Unity root",
                ),
                (
                    first + rebuild.replace(runner, "/usr/bin/env") + final,
                    "foreign wrapper executable",
                ),
                (
                    first + rebuild.replace("/AndroidPlayer/Bee:", "/AndroidPlayer/Other:") + final,
                    "mismatched Unity context",
                ),
                (
                    first + rebuild + rebuild.replace("Player123.dag.json", "Other.dag.json") + final,
                    "additional unmatched build-program start",
                ),
            )
            for candidate, reason in refused:
                with self.subTest(reason=reason), self.assertRaises(CaptureError):
                    parse_player_invocation(candidate)


if __name__ == "__main__":
    unittest.main()
