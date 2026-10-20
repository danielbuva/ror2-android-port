"""Verify the opted-in same-build post-strip snapshot and APK receipt.

Rendered IL2CPP command text is recorded with its actual evidence kind.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_GUID = re.compile(r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$")
_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_PREFIX = "Invoking il2cpp with arguments: "


class CaptureError(ValueError):
    pass


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _snapshot(work: Path, raw: str, expected_hash: str, expected_size: int) -> Path:
    if not isinstance(raw, str) or raw.startswith("/") or "\\" in raw:
        raise CaptureError("snapshot path must be normalized relative POSIX text")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CaptureError("snapshot path is aliased or escapes work root")
    path = work.joinpath(*parts)
    if work.is_symlink():
        raise CaptureError("work root is a symbolic link")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise CaptureError("post-strip snapshot is missing") from exc
    root = work.resolve(strict=True)
    current = path
    while current != work:
        if current.is_symlink():
            raise CaptureError("post-strip snapshot path contains a symbolic link")
        current = current.parent
    if root not in resolved.parents:
        raise CaptureError("post-strip snapshot redirects outside work root")
    if not path.is_file() or path.stat().st_size != expected_size or _digest(path) != expected_hash:
        raise CaptureError("post-strip snapshot bytes differ")
    return path


def verify_poststrip(
    capture: dict,
    *,
    prestrip: dict,
    work_root: Path,
    project_root: Path,
    result: dict,
    request_id: str,
    source_commit: str,
    input_id: str,
) -> dict:
    """Validate a same-report inventory; never attest exact argv[] from log text."""
    if work_root.is_symlink():
        raise CaptureError("work root is a symbolic link")
    if project_root.is_symlink():
        raise CaptureError("project root is a symbolic link")
    if not _TOKEN.fullmatch(request_id or ""):
        raise CaptureError("request identity is malformed")
    if not _HEX40.fullmatch(source_commit or "") or not _HEX64.fullmatch(input_id or ""):
        raise CaptureError("source or accepted-input identity is malformed")
    if capture.get("schema") != "ror2lab-il2cpp-invocation-capture-candidate-v1":
        raise CaptureError("unsupported post-strip capture schema")
    if capture.get("capture_flag") != "captureIl2CppInvocation":
        raise CaptureError("independent IL2CPP capture opt-in is absent")
    if capture.get("evidence_kind") != "UnityLogWriter pre-launch rendered command line; not argv[]":
        raise CaptureError("command-line evidence kind is not explicit")
    if capture.get("request_id") != request_id or capture.get("source_commit") != source_commit or capture.get("input_id") != input_id:
        raise CaptureError("post-strip capture belongs to a different request/source/input")
    guid = capture.get("build_report_guid")
    if not isinstance(guid, str) or not _GUID.fullmatch(guid):
        raise CaptureError("Unity BuildReport GUID is missing or malformed")
    if not isinstance(prestrip, dict):
        raise CaptureError("pre-strip linker receipt is malformed")
    prestrip_identity = (
        prestrip.get("request_id"),
        prestrip.get("source_commit"),
        prestrip.get("input_id"),
        prestrip.get("target"),
    )
    expected_prestrip_identity = (request_id, source_commit, input_id, "Android")
    if prestrip_identity != expected_prestrip_identity:
        raise CaptureError("pre-strip linker capture belongs to another request/source/input/target")
    if prestrip.get("build_report_guid") != guid:
        raise CaptureError("pre-strip linker capture belongs to a different Unity build report")
    if capture.get("target") != "Android":
        raise CaptureError("post-strip capture target is not Android")
    if not isinstance(capture.get("build_report_result"), str) or not capture["build_report_result"]:
        raise CaptureError("Unity BuildReport result state is absent")
    if result.get("success") is not True or result.get("errors") != 0:
        raise CaptureError("cannot bind post-strip inputs to an unsuccessful player build")
    if result.get("request_id") != request_id or result.get("input_id") != input_id:
        raise CaptureError("final build result request/input differs")
    if not isinstance(result.get("source"), dict) or result["source"].get("commit") != source_commit:
        raise CaptureError("final build result source differs")
    if result.get("build_report_guid") != guid:
        raise CaptureError("final build result report GUID differs")
    apk = Path(result.get("apk", ""))
    apk_hash = result.get("apk_sha256")
    if not apk.is_file() or not isinstance(apk_hash, str) or not _HEX64.fullmatch(apk_hash) or _digest(apk) != apk_hash:
        raise CaptureError("APK bytes do not match successful result")
    raw_dir = capture.get("il2cpp_input_directory")
    if not isinstance(raw_dir, str) or not raw_dir or raw_dir.startswith("/") or "\\" in raw_dir:
        raise CaptureError("IL2CPP input directory is not normalized relative text")
    directory_parts = raw_dir.split("/")
    if any(part in {"", ".", ".."} for part in directory_parts):
        raise CaptureError("IL2CPP project-relative directory is aliased or escapes project")
    command = capture.get("il2cpp_command_line_log")
    if not isinstance(command, str) or not command.startswith(_PREFIX) or "\n" in command or "\r" in command:
        raise CaptureError("actual pre-launch command-line log is absent or malformed")
    rendered = command[len(_PREFIX) :]
    directory_tokens = [token for token in rendered.split(" ") if token == "--directory" or token.startswith("--directory=")]
    if len(directory_tokens) != 1 or not directory_tokens[0].startswith("--directory="):
        raise CaptureError("rendered command line must contain one unambiguous --directory argument")
    directory_arg = directory_tokens[0][len("--directory=") :]
    if not directory_arg or any(char in directory_arg for char in "\"'\t\r\n"):
        raise CaptureError("rendered command line must contain one unambiguous --directory argument")
    try:
        if project_root.is_symlink():
            raise CaptureError("project root is a symbolic link")
        project = project_root.resolve(strict=True)
        expected_path = project.joinpath(*directory_parts)
        expected_input = expected_path.resolve(strict=True)
        logged_path = Path(directory_arg)
        if not logged_path.is_absolute():
            raise CaptureError("logged --directory is not an absolute path")
        logged_input = logged_path.resolve(strict=True)
    except OSError as exc:
        raise CaptureError("logged/project IL2CPP input directory is missing") from exc
    current = expected_path
    while current != project:
        if current.is_symlink():
            raise CaptureError("project-relative IL2CPP input path contains a symbolic link")
        current = current.parent
    if logged_input != expected_input or not logged_input.is_dir():
        raise CaptureError("logged --directory does not resolve to the recorded project-relative input")
    rows = capture.get("files")
    if not isinstance(rows, list) or not rows:
        raise CaptureError("post-strip input-file inventory is empty")
    seen: set[str] = set()
    checked = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "snapshot_path", "size", "sha256"}:
            raise CaptureError("post-strip inventory row shape is invalid")
        rel = row["path"]
        if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel:
            raise CaptureError("post-strip input file path is malformed")
        if any(part in {"", ".", ".."} for part in rel.split("/")) or rel in seen:
            raise CaptureError("post-strip input-file path is aliased or duplicated")
        seen.add(rel)
        size, digest = row["size"], row["sha256"]
        if type(size) is not int or size < 0 or not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise CaptureError("post-strip input-file size/hash is malformed")
        expected = f"lab-build/player-linker-inputs/{request_id}/poststrip/{rel}"
        if row["snapshot_path"] != expected:
            raise CaptureError("post-strip input file is not in the request-specific snapshot")
        _snapshot(work_root.resolve(strict=True), expected, digest, size)
        checked.append({"path": rel, "snapshot_path": expected, "size": size, "sha256": digest})
    return {
        "build_report_guid": guid,
        "il2cpp_input_directory": raw_dir,
        "files": sorted(checked, key=lambda row: row["path"]),
        "apk_sha256": apk_hash,
        "il2cpp_command_line_log": command,
        "il2cpp_argv_vector_binding": False,
        "il2cpp_snapshot_to_apk_build_binding": True,
        "stage_to_apk_binding": False,
    }
