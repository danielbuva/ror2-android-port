"""Strict host verifier for the opt-in UnityLinker input-directory capture."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class LinkerCaptureError(ValueError):
    pass


def request_capture_fields(
    enabled: bool,
    source: dict | None,
    input_id: str | None,
    *,
    capture_il2cpp_invocation: bool = False,
) -> dict:
    """Keep the extra build inputs absent by default; bind identity when enabled."""
    if not enabled:
        if capture_il2cpp_invocation:
            raise LinkerCaptureError("IL2CPP invocation capture requires the pre-strip linker capture")
        return {}
    commit = source.get("commit") if isinstance(source, dict) else None
    if not _HEX40.fullmatch(commit or "") or not _HEX64.fullmatch(input_id or ""):
        raise LinkerCaptureError("opted-in request requires committed source and accepted input identities")
    return {
        "capturePlayerLinkerInputs": True,
        "captureIl2CppInvocation": bool(capture_il2cpp_invocation),
        "sourceCommit": commit,
        "inputId": input_id,
    }


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_text(raw: str) -> tuple[str, ...]:
    if not isinstance(raw, str) or not raw or "\\" in raw or raw.startswith("/"):
        raise LinkerCaptureError("capture path is not normalized relative POSIX text")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise LinkerCaptureError("capture path is aliased or escapes its root")
    return tuple(parts)


def _relative(root: Path, raw: str) -> Path:
    parts = _relative_text(raw)
    value = root.joinpath(*parts)
    try:
        resolved = value.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise LinkerCaptureError("capture path is missing or inaccessible") from exc
    current = value
    while current != root:
        if current.is_symlink():
            raise LinkerCaptureError("capture path contains a symbolic link")
        current = current.parent
    if root not in resolved.parents or not value.is_file() and not value.is_dir():
        raise LinkerCaptureError("capture path is missing, redirected, or outside its root")
    return value


def verify_capture(
    capture: dict,
    *,
    work_root: Path,
    request_id: str,
    source_commit: str,
    input_id: str,
) -> tuple[dict, str]:
    if not _TOKEN.fullmatch(request_id or ""):
        raise LinkerCaptureError("build request identity is malformed")
    if not _HEX40.fullmatch(source_commit or "") or not _HEX64.fullmatch(input_id or ""):
        raise LinkerCaptureError("expected source or input identity is malformed")
    if capture.get("schema") != "ror2lab-unitylinker-input-v1":
        raise LinkerCaptureError("unsupported UnityLinker capture schema")
    if (
        capture.get("request_id"),
        capture.get("source_commit"),
        capture.get("input_id"),
    ) != (
        request_id,
        source_commit,
        input_id,
    ):
        raise LinkerCaptureError("UnityLinker capture belongs to another request, source, or input")
    if capture.get("target") != "Android":
        raise LinkerCaptureError("UnityLinker capture target is not Android")

    relative_dir = capture.get("input_directory")
    if not isinstance(relative_dir, str):
        raise LinkerCaptureError("UnityLinker input directory is missing")
    _relative_text(relative_dir)
    work = work_root.resolve(strict=True)
    rows = capture.get("files")
    if not isinstance(rows, list) or not rows:
        raise LinkerCaptureError("UnityLinker input capture is empty")

    normalized_rows = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "role",
            "path",
            "sha256",
            "size",
            "snapshot_path",
        }:
            raise LinkerCaptureError("UnityLinker inventory row has an unexpected shape")
        if row["role"] != "UnityLinkerInput":
            raise LinkerCaptureError("UnityLinker inventory role is unexpected")
        relative = row["path"]
        if not isinstance(relative, str) or not relative or "\\" in relative or relative.startswith("/"):
            raise LinkerCaptureError("UnityLinker DLL path is not normalized relative text")
        parts = relative.split("/")
        if any(part in {"", ".", ".."} for part in parts) or not relative.lower().endswith(".dll"):
            raise LinkerCaptureError("UnityLinker DLL path is aliased or has the wrong type")
        if relative in seen:
            raise LinkerCaptureError("UnityLinker inventory contains duplicate DLL paths")
        seen.add(relative)
        expected_hash = row["sha256"]
        size = row["size"]
        if not isinstance(expected_hash, str) or not _HEX64.fullmatch(expected_hash) or type(size) is not int or size <= 0:
            raise LinkerCaptureError("UnityLinker DLL hash or size is malformed")
        expected_snapshot = f"lab-build/player-linker-inputs/{request_id}/assemblies/{relative}"
        if row["snapshot_path"] != expected_snapshot:
            raise LinkerCaptureError("UnityLinker DLL snapshot path is not request-bound")
        snapshot = _relative(work, row["snapshot_path"])
        if not snapshot.is_file() or snapshot.stat().st_size != size or digest_file(snapshot) != expected_hash:
            raise LinkerCaptureError("request-bound UnityLinker DLL snapshot is missing or changed")
        normalized_rows.append(
            {
                "role": "UnityLinkerInput",
                "path": relative,
                "size": size,
                "sha256": expected_hash,
                "snapshot_path": expected_snapshot,
            }
        )

    normalized_rows.sort(key=lambda item: item["path"])
    normalized = {
        "schema": capture["schema"],
        "request_id": request_id,
        "source_commit": source_commit,
        "input_id": input_id,
        "target": "Android",
        "input_directory": relative_dir,
        "files": normalized_rows,
    }
    return normalized, hashlib.sha256(canonical_json(normalized)).hexdigest()


def bind_successful_apk(
    result: dict,
    capture: dict,
    *,
    work_root: Path,
    request_id: str,
    source_commit: str,
    input_id: str,
) -> dict:
    if result.get("success") is not True or result.get("errors") != 0:
        raise LinkerCaptureError("cannot bind a failed player build")
    if result.get("request_id") != request_id or result.get("input_id") != input_id:
        raise LinkerCaptureError("APK result request or input identity differs")
    if not isinstance(result.get("source"), dict) or result["source"].get("commit") != source_commit:
        raise LinkerCaptureError("APK result source commit differs")
    apk = Path(result.get("apk", ""))
    apk_hash = result.get("apk_sha256")
    if not apk.is_file() or not isinstance(apk_hash, str) or not _HEX64.fullmatch(apk_hash) or digest_file(apk) != apk_hash:
        raise LinkerCaptureError("APK bytes do not match the successful result")
    verified, capture_hash = verify_capture(
        capture,
        work_root=work_root,
        request_id=request_id,
        source_commit=source_commit,
        input_id=input_id,
    )
    sealed = dict(result)
    sealed["player_managed_linker_inputs"] = {
        "capture_sha256": capture_hash,
        "apk_sha256": apk_hash,
        **verified,
    }
    return sealed


def capture_cache_key(base_key: str, request_id: str) -> str:
    """Give each opted-in capture an immutable, non-reusable receipt location."""
    if not isinstance(base_key, str) or not base_key or "/" in base_key or "\\" in base_key:
        raise LinkerCaptureError("base build cache key is malformed")
    if not _TOKEN.fullmatch(request_id or ""):
        raise LinkerCaptureError("build request identity is malformed")
    return f"{base_key}-linker-{request_id}"
