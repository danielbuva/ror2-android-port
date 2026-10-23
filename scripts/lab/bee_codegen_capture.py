"""Version-pinned host verifier for Unity 2021.3.45f2 Bee IL2CPP inputs.

This support module verifies graph metadata for explicit capture requests; it
does not claim an exact argv vector or game-audio acceptance.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import shlex
from pathlib import Path

EDITOR_VERSION = "2021.3.45f2 (88f88f591b2e)"
TRACE_EVENT = "il2cpp.exe"
_PLAYER_DAG = re.compile(r'--dagfile="(Library/Bee/[^"\r\n]+\.dag)".* Player$')
_PLAYER_PROFILE = re.compile(r'--profile="(Library/Bee/[^"\r\n]+\.traceevents)"')
_RSP = re.compile(r'@"(Library/Bee/artifacts/rsp/[^"\r\n]+\.rsp)"')
_ASSEMBLY = re.compile(r'--assembly="([^"]+)"')
_PROFILER = re.compile(r'--profiler-output-file="([^"]+)"')
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TRACE_LIMIT = 64 * 1024 * 1024
_TRACE_EVENT_LIMIT = 2_000_000


class CaptureError(ValueError):
    pass


def editor_version_from_toolchain(pin: dict) -> str:
    """Match Unity's full version string from the repository's pinned fields."""
    if not isinstance(pin, dict):
        raise CaptureError("Unity toolchain pin is malformed")
    version, revision = pin.get("unity_version"), pin.get("unity_revision")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+[a-z][0-9]+", version):
        raise CaptureError("Unity toolchain version is malformed")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{12}", revision):
        raise CaptureError("Unity toolchain revision is malformed")
    return version + " (" + revision + ")"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_file_prefix(path: Path, size: int) -> str:
    if type(size) is not int or size < 0:
        raise CaptureError("Editor.log prefix size is malformed")
    h = hashlib.sha256()
    remaining = size
    with path.open("rb") as stream:
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise CaptureError("Editor.log is shorter than the pre-build offset")
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def require_changed(data: bytes, *, baseline_sha256: str | None, label: str) -> str:
    digest = sha256_bytes(data)
    if baseline_sha256 is not None:
        if not _HEX64.fullmatch(baseline_sha256) or digest == baseline_sha256:
            raise CaptureError(f"{label} is unchanged or has an invalid pre-build hash")
    return digest


def _project_file(project: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or relative.startswith("/"):
        raise CaptureError("Bee path must be normalized project-relative POSIX text")
    pieces = relative.split("/")
    if any(piece in {"", ".", ".."} for piece in pieces):
        raise CaptureError("Bee path is aliased or escapes the project")
    path = project.joinpath(*pieces)
    try:
        resolved = path.resolve(strict=True)
        root = project.resolve(strict=True)
    except OSError as exc:
        raise CaptureError("Bee input path is missing") from exc
    current = path
    while current != project:
        if current.is_symlink():
            raise CaptureError("Bee input path contains a symbolic link")
        current = current.parent
    if root not in resolved.parents or not path.is_file():
        raise CaptureError("Bee input path redirects outside the project or is not a file")
    return path


def _relative_project_path(project: Path, raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise CaptureError("Bee metadata path is malformed")
    path = Path(raw)
    if path.is_absolute():
        try:
            raw = path.resolve(strict=True).relative_to(project.resolve(strict=True)).as_posix()
        except ValueError as exc:
            raise CaptureError("Bee metadata path is outside the project") from exc
    _project_file(project.resolve(strict=True), raw)
    return raw


def player_dag_from_log(log_segment: str) -> str:
    """Compatibility helper returning the DAG from a validated Player invocation."""
    return parse_player_invocation(log_segment)["dag"]


def _validated_player_attempt(lines: list[str], index: int) -> dict:
    line = lines[index]
    dag = _PLAYER_DAG.search(line)
    if not dag:
        raise CaptureError("Bee Player invocation has an unsupported DAG command")
    profile = _PLAYER_PROFILE.search(line)
    if not profile or not re.fullmatch(r"Library/Bee/backend_profiler[0-9]+\.traceevents", profile.group(1)):
        raise CaptureError("Bee Player invocation lacks its backend profile path")
    if index + 2 >= len(lines):
        raise CaptureError("Bee Player invocation lacks working-directory/exit rows")
    working = re.fullmatch(r"WorkingDir: (.+)", lines[index + 1])
    exited = re.fullmatch(r"ExitCode: (-?[0-9]+) Duration: .+", lines[index + 2])
    if not working or not exited:
        raise CaptureError("Bee Player invocation lacks working-directory/exit rows")
    return {
        "dag": dag.group(1),
        "profile": profile.group(1),
        "working_directory": working.group(1),
        "exit_code": int(exited.group(1)),
        "start_index": index,
        "exit_index": index + 2,
    }


def _is_supported_player_build_program(line: str, dag: str, input_path: str) -> bool:
    """Match the observed netcorerun wrapper and its Unity-local BuildProgram."""
    if not line.startswith("Starting: "):
        return False
    try:
        command = shlex.split(line[len("Starting: ") :], posix=True)
    except ValueError:
        return False
    if len(command) != 6:
        return False
    runner = Path(command[0])
    if (
        runner.name != "netcorerun"
        or runner.parent.name != "netcorerun"
        or runner.parent.parent.name != "Tools"
        or runner.parent.parent.parent.name != "Contents"
        or runner.parent.parent.parent.parent.name != "Unity.app"
    ):
        return False
    editor_root = runner.parents[4]
    if editor_root.name != EDITOR_VERSION.split(" ", 1)[0]:
        return False
    android_player = editor_root / "PlaybackEngines" / "AndroidPlayer"
    expected_program = android_player / "AndroidPlayerBuildProgram.exe"
    expected_context = str(android_player / "Bee") + ":" + str(editor_root / "Unity.app" / "Contents" / "Tools" / "BuildPipeline")
    return (
        command[1] == str(expected_program)
        and command[2] == expected_context
        and command[3] == dag + ".json"
        and command[4] == input_path
        and re.fullmatch(r"Library/Bee/buildprogram[0-9]+\.traceevents", command[5]) is not None
    )


def _has_supported_dag_retry(lines: list[str], failed: dict, next_start: int) -> bool:
    """Accept only the observed exit-4 → FileSignature rebuild → Tundra rerun chain."""
    dag = failed["dag"]
    input_path = dag.removesuffix(".dag") + "-inputdata.json"
    expected_rebuild = "Rebuilding DAG because FileSignature timestamp changed: " + input_path
    segment = lines[failed["exit_index"] + 1 : next_start]
    rebuild_rows = [i for i, line in enumerate(segment) if line == expected_rebuild]
    tundra_rows = [
        i
        for i, line in enumerate(segment)
        if re.fullmatch(
            r"\*\*\* Tundra requires additional run \([^)]*\), [0-9]+ items updated, [0-9]+ evaluated",
            line,
        )
    ]
    # Treat every line naming this executable as a candidate, including malformed
    # or decoy commands; none may be silently ignored when counting the witness.
    build_program_rows = [i for i, line in enumerate(segment) if line.startswith("Starting:") and "AndroidPlayerBuildProgram.exe" in line]
    build_rows = [i for i in build_program_rows if _is_supported_player_build_program(segment[i], dag, input_path)]
    if len(rebuild_rows) != 1 or len(tundra_rows) != 1 or len(build_program_rows) != 1 or len(build_rows) != 1:
        return False
    rebuild_index, tundra_index, build_index = (
        rebuild_rows[0],
        tundra_rows[0],
        build_rows[0],
    )
    if not rebuild_index < tundra_index < build_index or build_index + 2 >= len(segment):
        return False
    build_working = re.fullmatch(r"WorkingDir: (.+)", segment[build_index + 1])
    build_exit = re.fullmatch(r"ExitCode: (-?[0-9]+) Duration: .+", segment[build_index + 2])
    return bool(build_working and build_working.group(1) == failed["working_directory"] and build_exit and build_exit.group(1) == "0")


def parse_player_invocation(log_segment: str) -> dict:
    """Bind one successful Player run, allowing one evidenced DAG-invalidation retry."""
    lines = log_segment.splitlines()
    attempts = []
    for index, line in enumerate(lines):
        if "Starting:" not in line or "bee_backend" not in line:
            continue
        # A malformed Player invocation must not disappear while another
        # well-formed invocation satisfies the exactly-one check.
        if not re.search(r"\bPlayer\b", line):
            continue
        attempts.append(_validated_player_attempt(lines, index))
    if len(attempts) == 1:
        attempt = attempts[0]
        if attempt["exit_code"] != 0:
            raise CaptureError("Bee Player invocation lacks a successful scoped exit")
        return {key: attempt[key] for key in ("dag", "profile", "working_directory", "exit_code")}
    if len(attempts) != 2:
        raise CaptureError("request log must contain one successful Player run or one bounded DAG retry")
    failed, succeeded = attempts
    if (
        failed["exit_code"] != 4
        or succeeded["exit_code"] != 0
        or failed["dag"] != succeeded["dag"]
        or failed["working_directory"] != succeeded["working_directory"]
        or not _has_supported_dag_retry(lines, failed, succeeded["start_index"])
    ):
        raise CaptureError("Player attempts do not form the supported scoped DAG-invalidation retry")
    return {key: succeeded[key] for key in ("dag", "profile", "working_directory", "exit_code")}


def validate_build_result(
    log_segment: str,
    *,
    request_id: str,
    report_guid: str,
    source_commit: str,
    input_id: str,
    apk_sha256: str,
    editor_version: str,
) -> dict:
    """Bind the request log's terminal result to the host-verified BuildReport/APK."""
    matches = []
    prefix = "LAB_BUILD_RESULT "
    for line in log_segment.splitlines():
        index = line.find(prefix)
        if index >= 0:
            try:
                matches.append(json.loads(line[index + len(prefix) :]))
            except json.JSONDecodeError as exc:
                raise CaptureError("LAB_BUILD_RESULT is malformed") from exc
    if len(matches) != 1:
        raise CaptureError("request log must contain exactly one terminal build result")
    result = matches[0]
    if (
        result.get("request_id") != request_id
        or result.get("build_report_guid") != report_guid
        or result.get("success") is not True
        or result.get("errors") != 0
    ):
        raise CaptureError("request log result does not match the successful BuildReport")
    if not _HEX64.fullmatch(apk_sha256 or ""):
        raise CaptureError("verified APK hash is malformed")
    if editor_version != EDITOR_VERSION:
        raise CaptureError("Bee graph schema is pinned to another Unity editor version")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit or "") or not _HEX64.fullmatch(input_id or ""):
        raise CaptureError("source or accepted-input identity is malformed")
    return {
        "request_id": request_id,
        "build_report_guid": report_guid,
        "source_commit": source_commit,
        "input_id": input_id,
        "apk_sha256": apk_sha256,
        "editor_version": editor_version,
    }


def _parse_action(action: str) -> str:
    if not isinstance(action, str) or "/il2cpp" not in action:
        raise CaptureError("Bee IL2CPP_CodeGen action is absent")
    matches = _RSP.findall(action)
    if len(matches) != 1:
        raise CaptureError("Bee action must reference one project-relative response file")
    return matches[0]


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON number: " + value)


def _trace_events(data: bytes) -> list[dict]:
    """Parse the pinned Bee trace's multiline comma-separated JSON object stream."""
    if len(data) > _TRACE_LIMIT:
        raise CaptureError("Bee conversion trace exceeds the bounded parser limit")
    try:
        text = data.decode("utf-8")
        decoder = json.JSONDecoder(parse_constant=_reject_constant)
        events = []
        offset = 0
        need_event = True
        saw_separator = False
        while offset < len(text):
            while offset < len(text) and text[offset].isspace():
                offset += 1
            if offset == len(text):
                break
            if text[offset] == ",":
                if need_event or saw_separator:
                    raise CaptureError("Bee trace stream has an empty event separator")
                saw_separator = True
                need_event = True
                offset += 1
                continue
            if not need_event:
                raise CaptureError("Bee trace stream is missing an event separator")
            event, offset = decoder.raw_decode(text, offset)
            if not isinstance(event, dict):
                raise CaptureError("Bee trace stream contains a non-object record")
            events.append(event)
            if len(events) > _TRACE_EVENT_LIMIT:
                raise CaptureError("Bee conversion trace exceeds the event limit")
            need_event = False
            saw_separator = False
        # The pinned trace format ends with a comma; leading or repeated commas
        # are malformed, but the single trailing separator is allowed.
        if need_event and not saw_separator:
            raise CaptureError("Bee trace stream ends between records")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CaptureError("Bee conversion trace is not a complete JSON event stream") from exc
    if not events:
        raise CaptureError("Bee conversion trace has no event records")
    return events


def verify_fresh_trace(
    trace_data: bytes,
    *,
    baseline_sha256: str | None,
) -> dict:
    require_changed(trace_data, baseline_sha256=baseline_sha256, label="Bee conversion trace")
    events = _trace_events(trace_data)
    fresh = [
        event
        for event in events
        if event.get("name") == TRACE_EVENT
        and event.get("ph") == "X"
        and event.get("pid") == "il2cpp_in_graph"
        and type(event.get("ts")) in (int, float)
        and type(event.get("dur")) in (int, float)
        and math.isfinite(event["ts"])
        and math.isfinite(event["dur"])
        and event["ts"] >= 0
        and event["dur"] > 0
    ]
    if len(fresh) != 1:
        raise CaptureError("fresh Bee trace must contain exactly one complete IL2CPP conversion event")
    return {
        "sha256": sha256_bytes(trace_data),
        "il2cpp_event_count": len(fresh),
    }


def inspect_codegen_node(dag: dict, *, project_root: Path) -> dict:
    """Extract the exact graph-declared managed input set and response-file path."""
    if not isinstance(dag, dict) or not isinstance(dag.get("Nodes"), list):
        raise CaptureError("Bee Player DAG schema is unsupported")
    nodes = [node for node in dag["Nodes"] if isinstance(node, dict) and str(node.get("Annotation", "")).startswith("IL2CPP_CodeGen ")]
    if len(nodes) != 1:
        raise CaptureError("Bee DAG must contain exactly one IL2CPP_CodeGen node")
    node = nodes[0]
    rsp_path = _parse_action(node.get("Action"))
    outputs = node.get("Outputs")
    if not isinstance(outputs, list):
        raise CaptureError("Bee IL2CPP node outputs are missing")
    trace_paths = {str(path) for path in outputs if "il2cpp_conv_" in str(path) and str(path).endswith(".traceevents")}
    if len(trace_paths) != 1:
        raise CaptureError("Bee IL2CPP node must declare one conversion trace output")
    trace_raw = next(iter(trace_paths))
    trace_relative = _relative_project_path(project_root, trace_raw)
    annotation = node.get("Annotation")
    profiler_output = node.get("ProfilerOutput")
    if annotation != "IL2CPP_CodeGen " + profiler_output or profiler_output != trace_raw:
        raise CaptureError("Bee node annotation, profiler output, and trace output differ")
    inputs = node.get("Inputs")
    if not isinstance(inputs, list):
        raise CaptureError("Bee IL2CPP node inputs are missing")
    managed = sorted({str(path) for path in inputs if "/ManagedStripped/" in str(path) and str(path).endswith(".dll")})
    if not managed:
        raise CaptureError("Bee IL2CPP node has no declared stripped managed DLL inputs")
    resolved = []
    for raw in managed:
        relative = raw
        root = project_root.resolve(strict=True)
        value = Path(raw)
        if value.is_absolute():
            try:
                relative = value.absolute().relative_to(root).as_posix()
            except ValueError as exc:
                raise CaptureError("Bee managed input is outside the project") from exc
        path = _project_file(root, relative)
        resolved.append((relative, path))
    rsp_relative = rsp_path
    rsp_bytes = _project_file(project_root.resolve(strict=True), rsp_relative).read_bytes()
    try:
        rsp_text = rsp_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaptureError("Bee response file is not UTF-8 text") from exc
    rsp_managed = sorted(set(match for match in _ASSEMBLY.findall(rsp_text) if "/ManagedStripped/" in match and match.endswith(".dll")))
    if rsp_managed != managed:
        raise CaptureError("Bee response-file managed assemblies differ from graph-declared inputs")
    profiler_paths = _PROFILER.findall(rsp_text)
    if len(profiler_paths) != 1 or _relative_project_path(project_root, profiler_paths[0]) != trace_relative:
        raise CaptureError("Bee response-file profiler output differs from the declared trace")
    return {
        "node_annotation": node["Annotation"],
        "node_action_metadata": node["Action"],
        "argv_vector_binding": False,
        "response_file": rsp_relative,
        "response_file_sha256": sha256_bytes(rsp_bytes),
        "trace_output": trace_relative,
        "managed_inputs": [{"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)} for relative, path in resolved],
    }


def _baseline_inventory(pre: dict) -> dict[str, dict]:
    if pre.get("schema") != "ror2lab-bee-prebuild-v2" or pre.get("scan_root") != "Library/Bee" or pre.get("editor_version") != EDITOR_VERSION:
        raise CaptureError("C# pre-build Bee inventory is unsupported")
    rows = pre.get("baseline_files")
    if (
        not isinstance(rows, list)
        or type(pre.get("baseline_file_count")) is not int
        or pre["baseline_file_count"] != len(rows)
        or not isinstance(pre.get("scan_started_utc"), str)
        or not isinstance(pre.get("scan_completed_utc"), str)
        or not _HEX64.fullmatch(pre.get("baseline_sha256", ""))
    ):
        raise CaptureError("pre-build Bee inventory rows are absent")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise CaptureError("pre-build Bee inventory row is malformed")
        path, size, digest = row["path"], row["size"], row["sha256"]
        if not isinstance(path, str):
            raise CaptureError("pre-build Bee inventory path is malformed")
        is_dag = path.startswith("Library/Bee/Player") and path.endswith((".dag", ".dag.json"))
        is_trace = path.startswith("Library/Bee/artifacts/il2cpp_conv_") and path.endswith(".traceevents")
        if (
            not isinstance(path, str)
            or not (is_dag or is_trace)
            or path in result
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or not _HEX64.fullmatch(digest)
        ):
            raise CaptureError("pre-build Bee inventory contains an invalid row")
        result[path] = row
    if rows != sorted(rows, key=lambda row: row["path"]):
        raise CaptureError("pre-build Bee inventory is not deterministically sorted")
    canonical = "\n".join(f"{row['path']}\t{row['size']}\t{row['sha256']}" for row in rows).encode("utf-8")
    if sha256_bytes(canonical) != pre["baseline_sha256"]:
        raise CaptureError("pre-build Bee inventory digest differs from its rows")
    return result


def _snapshot_metadata(project: Path, destination: Path, paths: list[str]) -> list[dict]:
    metadata = destination / "metadata"
    metadata.mkdir(parents=True)
    rows = []
    try:
        for relative in paths:
            source = _project_file(project, relative)
            target = metadata / Path(relative).name
            if target.exists():
                raise CaptureError("Bee metadata snapshot names collide")
            before = source.read_bytes()
            target.write_bytes(before)
            copied = target.read_bytes()
            if source.read_bytes() != before or copied != before:
                raise CaptureError("Bee metadata drifted while being snapshotted")
            rows.append(
                {
                    "path": relative,
                    "snapshot_name": target.name,
                    "size": len(copied),
                    "sha256": sha256_bytes(copied),
                }
            )
        return rows
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def collect_request_capture(
    *,
    project_root: Path,
    work_root: Path,
    snapshot_destination: Path,
    final_result: dict,
    request_id: str,
    source_commit: str,
    input_id: str,
    editor_version: str,
) -> dict:
    """Verify C# pre/post receipts and bind exact Bee evidence to the final APK."""
    if editor_version != EDITOR_VERSION:
        raise CaptureError("Bee collector is pinned to another Unity editor version")
    work = work_root.resolve(strict=True)
    capture_dir = work / "lab-build/player-linker-inputs"
    pre_path = capture_dir / (request_id + ".bee-pre.json")
    post_path = capture_dir / (request_id + ".bee-post.json")
    try:
        prebuild_bytes = pre_path.read_bytes()
        pre = json.loads(prebuild_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureError("C# pre-build receipt is malformed") from exc
    except OSError as exc:
        raise CaptureError("request-owned C# pre-build receipt is missing") from exc
    try:
        postprocess = json.loads(post_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError("request-owned C# postprocess receipt is missing or malformed") from exc
    baseline = _baseline_inventory(pre)
    guid = pre.get("build_report_guid")
    identity = (request_id, source_commit, input_id, guid)
    if (
        not isinstance(guid, str)
        or not re.fullmatch(r"[0-9a-fA-F]{32}", guid)
        or (
            pre.get("request_id"),
            pre.get("source_commit"),
            pre.get("input_id"),
            pre.get("build_report_guid"),
        )
        != identity
        or pre.get("target") != "Android"
        or type(pre.get("log_byte_offset")) is not int
        or pre["log_byte_offset"] < 0
    ):
        raise CaptureError("pre-build receipt request/report/log identity is invalid")
    process_path = work / "editor/lab-process.json"
    try:
        process = json.loads(process_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError("active Unity editor process receipt is missing") from exc
    if pre.get("editor_log_path") != process.get("log") or type(pre.get("editor_pid")) is not int or pre.get("editor_pid") != process.get("pid"):
        raise CaptureError("C# pre-build log owner differs from the active editor process")
    try:
        editor_log = Path(pre["editor_log_path"]).resolve(strict=True)
        editor_log.relative_to(work)
    except (OSError, ValueError) as exc:
        raise CaptureError("active Editor.log is missing or outside the work root") from exc
    if sha256_file_prefix(editor_log, pre["log_byte_offset"]) != pre.get("editor_log_prefix_sha256"):
        raise CaptureError("Editor.log bytes before the pre-build offset changed")
    slice_relative = f"lab-build/player-linker-inputs/{request_id}.bee-log-slice"
    if postprocess.get("log_slice_path") != slice_relative:
        raise CaptureError("postprocess log slice is not request-owned")
    slice_path = work / slice_relative
    try:
        log_slice = slice_path.read_bytes()
    except OSError as exc:
        raise CaptureError("request-owned Editor.log slice is missing") from exc
    if (
        postprocess.get("schema") != "ror2lab-bee-postprocess-v2"
        or postprocess.get("prebuild_sha256") != sha256_bytes(prebuild_bytes)
        or postprocess.get("request_id") != request_id
        or postprocess.get("source_commit") != source_commit
        or postprocess.get("input_id") != input_id
        or postprocess.get("build_report_guid") != guid
        or postprocess.get("target") != "Android"
        or postprocess.get("build_report_result") != "Succeeded"
        or postprocess.get("build_report_errors") != 0
    ):
        raise CaptureError("postprocess receipt is not the same successful Android BuildReport")
    start, end = postprocess.get("log_byte_start"), postprocess.get("log_byte_end")
    if type(start) is not int or type(end) is not int or start != pre["log_byte_offset"] or end - start != len(log_slice):
        raise CaptureError("postprocess Editor.log byte range differs from pre-build boundary")
    if postprocess.get("log_slice_sha256") != sha256_bytes(log_slice):
        raise CaptureError("postprocess Editor.log slice hash differs")
    with editor_log.open("rb") as stream:
        stream.seek(start)
        if stream.read(end - start) != log_slice:
            raise CaptureError("request-owned slice differs from actual Editor.log byte range")
    try:
        log_text = log_slice.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaptureError("captured Editor.log slice is not UTF-8") from exc
    invocation = parse_player_invocation(log_text)
    project = project_root.resolve(strict=True)
    try:
        working_directory = Path(invocation["working_directory"]).resolve(strict=True)
    except OSError as exc:
        raise CaptureError("Bee Player WorkingDir does not exist") from exc
    if working_directory != project:
        raise CaptureError("Bee Player WorkingDir differs from the exact Unity project")
    profile_relative = invocation["profile"]
    _project_file(project, profile_relative)
    dag_relative = invocation["dag"]
    _project_file(project, dag_relative)
    dag_json_relative = dag_relative + ".json"
    dag_json_path = _project_file(project, dag_json_relative)
    try:
        dag = json.loads(dag_json_path.read_bytes())
    except json.JSONDecodeError as exc:
        raise CaptureError("active Bee Player DAG JSON is malformed") from exc
    contract = inspect_codegen_node(dag, project_root=project)
    trace_relative = contract["trace_output"]
    trace_bytes = _project_file(project, trace_relative).read_bytes()
    previous_trace = baseline.get(trace_relative)
    trace_result = verify_fresh_trace(
        trace_bytes,
        baseline_sha256=previous_trace["sha256"] if previous_trace else None,
    )
    result = final_result
    if (
        result.get("request_id") != request_id
        or result.get("success") is not True
        or result.get("errors") != 0
        or result.get("build_report_guid") != guid
        or result.get("build_report_output_path") != postprocess.get("build_report_output_path")
        or result.get("input_id") != input_id
        or not isinstance(result.get("source"), dict)
        or result["source"].get("commit") != source_commit
    ):
        raise CaptureError("final host build result differs from pre/post BuildReport identity")
    apk = Path(result.get("apk", ""))
    apk_hash = result.get("apk_sha256")
    if not apk.is_file() or not isinstance(apk_hash, str) or not _HEX64.fullmatch(apk_hash) or sha256_file(apk) != apk_hash:
        raise CaptureError("final APK bytes do not match host build receipt")
    report_apk = Path(postprocess["build_report_output_path"])
    if not report_apk.is_file() or sha256_file(report_apk) != apk_hash:
        raise CaptureError("BuildReport output bytes differ from the final copied APK")
    if snapshot_destination.exists() or snapshot_destination.is_symlink():
        raise CaptureError("request capture snapshot destination already exists")
    try:
        metadata = _snapshot_metadata(
            project,
            snapshot_destination,
            [
                dag_relative,
                dag_json_relative,
                contract["response_file"],
                trace_relative,
            ],
        )
        managed_rows = snapshot_managed_inputs(
            contract,
            project_root=project,
            destination=snapshot_destination / "managed",
        )
    except Exception:
        shutil.rmtree(snapshot_destination, ignore_errors=True)
        raise
    return {
        "schema": "ror2lab-bee-il2cpp-owned-build-v2",
        "request_id": request_id,
        "source_commit": source_commit,
        "input_id": input_id,
        "editor_version": editor_version,
        "build_report_guid": guid,
        "apk_sha256": apk_hash,
        "snapshot_root": snapshot_destination.as_posix(),
        "bee_invocation": invocation,
        "bee_player_dag": dag_relative,
        "bee_codegen_node": contract["node_annotation"],
        "bee_codegen_action_metadata": contract["node_action_metadata"],
        "response_file": contract["response_file"],
        "response_file_sha256": contract["response_file_sha256"],
        "trace_file": trace_relative,
        "trace_sha256": trace_result["sha256"],
        "il2cpp_event_count": trace_result["il2cpp_event_count"],
        "argv_vector_binding": False,
        "metadata_snapshots": metadata,
        "snapshot_scope": "Bee IL2CPP_CodeGen node declared ManagedStripped DLL inputs only",
        "managed_inputs": managed_rows,
    }


def snapshot_managed_inputs(contract: dict, *, project_root: Path, destination: Path) -> list[dict]:
    """Copy only declared ManagedStripped DLLs into a fresh request-owned snapshot."""
    if destination.exists() or destination.is_symlink():
        raise CaptureError("post-strip managed snapshot destination already exists")
    destination.mkdir(parents=True)
    root = project_root.resolve(strict=True)
    rows = []
    try:
        for row in contract["managed_inputs"]:
            source = _project_file(root, row["path"])
            if source.stat().st_size != row["size"] or sha256_file(source) != row["sha256"]:
                raise CaptureError("Bee managed input changed after graph inspection")
            target = destination / Path(row["path"]).name
            if target.exists():
                raise CaptureError("two Bee inputs map to the same managed snapshot name")
            shutil.copyfile(source, target)
            digest = sha256_file(target)
            if target.stat().st_size != row["size"] or digest != row["sha256"]:
                raise CaptureError("managed snapshot bytes differ from Bee's declared input")
            if sha256_file(source) != digest:
                raise CaptureError("Bee managed input drifted while snapshotting")
            rows.append(
                {
                    "path": row["path"],
                    "snapshot_name": target.name,
                    "size": row["size"],
                    "sha256": digest,
                }
            )
        return rows
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
