#!/usr/bin/env python3
"""Callable build-stage adapter for whole-catalog project generation.

The caller invokes ``stage_for_build`` after ordinary migration/runtime source
generation and before its project-input/cache digest. Missing selection means
default-off. A present opt-in selection is explicit and must bind every input
path; this module never guesses a timestamped producer result.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SELECTION = Path("config/original-game-audio/selection.json")
SELECTION_SCHEMA = "original-game-audio-build-selection-r1"
REQUESTED_PATHS = (
    "android_source",
    "android_os_string_source",
    "native_library",
    "abi_native_plugin",
    "stage_receipt",
    "stage_root",
    "prefab",
    "bank_index",
    "adapted_init",
    "init_receipt",
)


def source_bundle_hashes() -> dict[str, str]:
    paths = {
        ROOT / "scripts/lab" / name
        for name in (
            "original_game_audio.py",
            "original_game_audio_build_hook.py",
            "original_game_audio_produce.py",
            "original_game_audio_stage.py",
            "assembly_transforms.py",
            "common.py",
        )
    }
    paths.update(ROOT / name for name in ("environment/toolchain.json", "recipe/assembly-transforms.json", "recipe/wwise-android-abi.json"))
    for directory in ("tools/unity/support/audio", "tools/assembly-transforms", "tools/wwise-android-abi"):
        paths.update(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file() and path.suffix in (".py", ".cs", ".csproj") and not {"obj", "bin", "__pycache__"}.intersection(path.parts)
        )
    return {path.relative_to(ROOT).as_posix(): file_sha(path) for path in sorted(paths)}


def validate_generation_receipt(output: Path, generation_key: str, payload: dict) -> None:
    receipt = output / "generation.json"
    if receipt.is_symlink() or not receipt.is_file():
        raise ValueError("cached audio generation lacks its source/input receipt")
    if json.loads(receipt.read_text()) != {"schema": 1, "generation_key": generation_key, "inputs": payload}:
        raise ValueError("cached audio generation differs from current source/input identity")


def record_generation(output: Path, generation_key: str, payload: dict) -> None:
    if source_bundle_hashes() != payload["source_bundle"]:
        raise ValueError("audio producer sources changed during generation")
    with (output / "generation.json").open("x", encoding="utf-8") as stream:
        json.dump({"schema": 1, "generation_key": generation_key, "inputs": payload}, stream, sort_keys=True, indent=2)
        stream.write("\n")


def requested_tool_identity(dotnet: Path, llvm_nm: Path) -> dict:
    version = subprocess.run([str(dotnet), "--version"], text=True, capture_output=True, check=True, timeout=30).stdout.strip()
    sdk = dotnet.resolve(strict=True).parent / "sdk" / version
    return {
        "dotnet_sha256": file_sha(dotnet),
        "dotnet_sdk_version": version,
        "dotnet_sdk_roslyn_sha256": file_sha(sdk / "Roslyn/bincore/csc.dll"),
        "dotnet_msbuild_sha256": file_sha(sdk / "MSBuild.dll"),
        "llvm_nm_sha256": file_sha(llvm_nm),
    }


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load authored owner: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def work_path(work: Path, value: object, field: str, *, directory: bool = False) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or Path(value).is_absolute() or ".." in Path(value).parts or Path(value).as_posix() != value:
        raise ValueError(f"selection {field} must be a canonical path relative to work/")
    path = work / value
    cursor = work
    for part in Path(value).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"selection {field} cannot traverse a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(work) or (not resolved.is_dir() if directory else not resolved.is_file()):
        raise ValueError(f"selection {field} has the wrong path type or escapes work/")
    return resolved


def read_selection(work: Path, selection_path: Path) -> tuple[dict, dict[str, Path], str]:
    """Resolve the explicit selection or return the safe default-off value."""
    if not selection_path.exists() and not selection_path.is_symlink():
        return {"schema": SELECTION_SCHEMA, "requested": False}, {}, "default-off"
    lexical = selection_path.absolute()
    if not lexical.is_relative_to(work):
        raise ValueError("audio selection must be a regular file under work/")
    cursor = work
    for part in lexical.relative_to(work).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("audio selection cannot traverse a symlink")
    if not selection_path.resolve(strict=True).is_relative_to(work) or not selection_path.is_file():
        raise ValueError("audio selection must be a regular file under work/")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(selection, dict) or selection.get("schema") != SELECTION_SCHEMA or type(selection.get("requested")) is not bool:
        raise ValueError("audio selection schema/request flag is invalid")
    if selection["requested"]:
        paths = selection.get("inputs")
        if not isinstance(paths, dict) or set(paths) != set(REQUESTED_PATHS):
            raise ValueError("requested audio selection must provide the exact explicit input path set")
        if not isinstance(selection.get("request_id"), str) or len(selection["request_id"]) != 32:
            raise ValueError("requested audio selection must bind a compact request identity")
        resolved = {key: work_path(work, value, key, directory=(key == "stage_root")) for key, value in paths.items()}
        return selection, resolved, "requested"
    if set(selection) != {"schema", "requested"}:
        raise ValueError("default-off selection must not contain hidden request inputs")
    return selection, {}, "default-off"


def stage_for_build(project: Path, work: Path, *, selection_path: Path | None = None) -> dict:
    """Compile and stage audio inputs before the enclosing build computes its key."""
    project = project.resolve(strict=True)
    work = work.resolve(strict=True)
    if not project.is_dir() or work != (ROOT / "work").resolve(strict=True):
        raise ValueError("audio build hook requires the current project and canonical ignored work/ root")
    selection_path = selection_path or (work / SELECTION)
    if not selection_path.is_absolute():
        selection_path = work / selection_path
    selection, resolved, variant = read_selection(work, selection_path)

    editor = Path(os.environ.get("UNITY_EDITOR", ""))
    if not editor.is_absolute() or not editor.is_file():
        raise ValueError("pinned UNITY_EDITOR must be configured before the build hook runs")
    producer = load(Path(__file__).with_name("original_game_audio_produce.py"), "audio_build_producer")
    stager = load(Path(__file__).with_name("original_game_audio_stage.py"), "audio_build_stager")
    if not project.parent.resolve(strict=True).is_relative_to(work):
        raise ValueError("project build directory must remain under ignored work/")
    editor_contents = editor.resolve(strict=True).parent.parent
    mono = editor_contents / "MonoBleedingEdge/bin/mono"
    csc = editor_contents / "MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe"
    toolchain = producer.validate_toolchain(project, editor_contents, mono, csc)
    payload = {
        "variant": variant,
        "source_bundle": source_bundle_hashes(),
        "toolchain": toolchain,
        "unity_references": [file_sha(path) for path in producer.unity_reference_options(editor_contents, project)[1]],
        "owner_sources": producer.OWNER_SOURCE_HASHES,
        "project_api_sha256": file_sha(project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll"),
        "project_game_sha256": file_sha(project / "Assets/LabLoadingScene/Plugins/RoR2.dll"),
        "selection_sha256": file_sha(selection_path) if selection_path.is_file() else None,
    }
    if variant == "requested":
        dotnet_text = shutil.which("dotnet")
        if not dotnet_text:
            raise ValueError("dotnet must be available from the pinned build environment")
        dotnet = Path(dotnet_text).resolve(strict=True)
        llvm_nm = (
            editor.resolve(strict=True).parent.parent.parent.parent / "PlaybackEngines/AndroidPlayer/NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm"
        )
        payload["requested_tools"] = requested_tool_identity(dotnet, llvm_nm)
        payload["managed_producer_sha256"] = file_sha(ROOT / "tools/unity/support/audio/managed-producer/produce.py")
        payload["request_id"] = selection["request_id"]
        payload["input_sha256"] = {key: file_sha(path) for key, path in sorted(resolved.items()) if key != "stage_root"}
        payload["receipt_bound_payload"] = json.loads(resolved["stage_receipt"].read_text(encoding="utf-8"))["outputs"]
    generation_key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output_parent = project.parent / "original-game-audio-owner"
    producer.reject_symlink_components(output_parent)
    output_parent.mkdir(exist_ok=True)
    output = output_parent / generation_key
    request_file = output / "generated/request.json" if variant == "requested" else None
    stage_receipt = resolved["stage_receipt"] if variant == "requested" else None
    if output.exists():
        validate_generation_receipt(output, generation_key, payload)
        manifest_path = output / "artifact-manifest.json"
        stager.read_artifacts(manifest_path, request_file, stage_receipt)
        receipt = stager.stage(project, manifest_path, request_file, stage_receipt)
        return {"producer": {"variant": variant, "cached": True, "generation_key": generation_key}, "stage": receipt, "variant": variant}

    if variant == "default-off":
        result = producer.compile_default_off(project, editor_contents, mono, csc, output)
        record_generation(output, generation_key, payload)
        receipt = stager.stage(project, output / "artifact-manifest.json", None, None)
    else:
        managed_producer = ROOT / "tools/unity/support/audio/managed-producer/produce.py"
        if not managed_producer.is_file():
            raise ValueError("authored managed producer is not installed at its stable tools path")
        if not os.access(llvm_nm, os.X_OK):
            raise ValueError("pinned Unity Android NDK llvm-nm is unavailable")
        result = producer.compile_requested(
            project,
            editor_contents,
            mono,
            csc,
            dotnet,
            managed_producer,
            resolved["android_source"],
            resolved["android_os_string_source"],
            resolved["native_library"],
            resolved["abi_native_plugin"],
            llvm_nm,
            None,
            None,
            resolved["stage_receipt"],
            resolved["stage_root"],
            resolved["prefab"],
            resolved["bank_index"],
            resolved["adapted_init"],
            resolved["init_receipt"],
            output,
            selection["request_id"],
        )
        record_generation(output, generation_key, payload)
        receipt = stager.stage(project, output / "artifact-manifest.json", output / "generated/request.json", resolved["stage_receipt"])
    return {"producer": result, "stage": receipt, "variant": variant}


__all__ = ["stage_for_build"]
