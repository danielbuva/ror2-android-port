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
import re
import tempfile
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SELECTION = Path("config/original-game-audio/selection.json")
SELECTION_SCHEMA = "original-game-audio-build-selection-r2"
LEGACY_SELECTION_SCHEMA = "original-game-audio-build-selection-r1"
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
    paths.update(
        ROOT / name
        for name in (
            "environment/toolchain.json",
            "recipe/assembly-transforms.json",
            "recipe/wwise-android-abi.json",
            "recipe/runtime-sources.json",
            "recipe/runtime-sources.native-view-camera.json",
            "recipe/project-layout.json",
            "recipe/original-audio-owner-sources.json",
            "tools/unity/runtime/session/PortSession.cs",
            "tools/unity/runtime/session/PortSessionOriginalAudioOwner.cs",
            "tools/unity/runtime/session/OriginalMusicControllerContract.cs",
            "tools/unity/runtime/session/PortSessionOriginalMusicControllerOwner.cs",
        )
    )
    for directory in (
        "tools/unity/support/audio",
        "tools/assembly-transforms",
        "tools/wwise-android-abi",
    ):
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
    if json.loads(receipt.read_text()) != {
        "schema": 1,
        "generation_key": generation_key,
        "inputs": payload,
    }:
        raise ValueError("cached audio generation differs from current source/input identity")


def record_generation(output: Path, generation_key: str, payload: dict) -> None:
    if source_bundle_hashes() != payload["source_bundle"]:
        raise ValueError("audio producer sources changed during generation")
    with (output / "generation.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {"schema": 1, "generation_key": generation_key, "inputs": payload},
            stream,
            sort_keys=True,
            indent=2,
        )
        stream.write("\n")


def requested_tool_identity(dotnet: Path, llvm_nm: Path) -> dict:
    version = subprocess.run(
        [str(dotnet), "--version"],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout.strip()
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
    if (
        not isinstance(selection, dict)
        or selection.get("schema") not in {LEGACY_SELECTION_SCHEMA, SELECTION_SCHEMA}
        or type(selection.get("requested")) is not bool
    ):
        raise ValueError("audio selection schema/request flag is invalid")
    if selection["requested"]:
        # R1 is the actual pre-diagnostic selection schema in existing local
        # state. R2 is the diagnostic-aware schema. Both preserve original
        # audio admission; only R2 may name the diagnostic flag, and omission
        # in either legacy shape maps to false. Unknown fields remain a hard
        # refusal so the diagnostic is never inferred or enabled.
        selection_keys = {"schema", "requested", "request_id", "inputs"}
        if selection["schema"] == SELECTION_SCHEMA and "passive_pcm_capture_requested" in selection:
            selection_keys.add("passive_pcm_capture_requested")
        if set(selection) != selection_keys:
            raise ValueError("requested audio selection has unexpected fields")
        passive_pcm_requested = selection.get("passive_pcm_capture_requested", False)
        if type(passive_pcm_requested) is not bool:
            raise ValueError("passive PCM diagnostic selection must be a boolean")
        selection["passive_pcm_capture_requested"] = passive_pcm_requested
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


SOUND_EMITTER_ASSET = "Assets/RoR2/Base/Utility/SoundEmitter.prefab"
SOUND_EMITTER_GUID = "e0447f0f885c66f4bb55ba311b31d463"
SOUND_EMITTER_ACCEPTED_INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
SOUND_EMITTER_ACCEPTED_SOURCE_SHA256 = "9eeef75a0a96fb748820b26775720ae14e6d2718f86d6477530d46c69fb4ab1e"
SOUND_EMITTER_WWISE_PATH = "Assets/RoR2/Base/Core/Audio/WwiseGlobal.prefab"
AK_GAME_OBJECT_SCRIPT_FILE_ID = "-130519023"
AK_GAME_OBJECT_SCRIPT_GUID = "2b6c926553287666f24ffd5af5ba21cb"


def _asset_guid(meta: Path) -> str:
    match = re.search(r"^guid: ([a-f0-9]{32})", meta.read_text(encoding="utf-8", errors="replace"), re.M)
    if not match:
        raise ValueError("accepted SoundEmitter metadata has no unique asset GUID")
    return match[1]


def _sound_emitter_stripped_text(source_text: str) -> str:
    """Derive the default-off sanitizer output from one exact source component."""
    component_script = "m_Script: {fileID: " + AK_GAME_OBJECT_SCRIPT_FILE_ID + ", guid: " + AK_GAME_OBJECT_SCRIPT_GUID + ", type: 3}"
    blocks = re.split(r"(?=^--- !u!)", source_text, flags=re.M)
    matches = []
    for block in blocks:
        match = re.match(r"--- !u!114 &(-?\d+)", block)
        if match and component_script in block:
            matches.append((match[1], block))
    if len(matches) != 1:
        raise ValueError("accepted SoundEmitter must contain exactly one source AkGameObj")
    component_id, component_block = matches[0]
    owner = re.search(r"^  m_GameObject: \{fileID: (-?\d+)\}", component_block, re.M)
    if not owner:
        raise ValueError("source AkGameObj has no owning GameObject")
    owner_blocks = [block for block in blocks if re.match(r"--- !u!1 &" + re.escape(owner[1]) + r"\n", block)]
    component_ref = "  - component: {fileID: " + component_id + "}\n"
    if len(owner_blocks) != 1 or owner_blocks[0].count(component_ref) != 1:
        raise ValueError("source AkGameObj is not uniquely listed on its owning GameObject")
    stripped = source_text.replace(component_block, "", 1)
    stripped, count = re.subn(r"^" + re.escape(component_ref), "", stripped, count=1, flags=re.M)
    if count != 1:
        raise ValueError("source AkGameObj reference is not uniquely removable")
    return stripped


def _safe_project_file(path: Path, project: Path) -> None:
    resolved_project = project.resolve(strict=True)
    if not path.absolute().is_relative_to(resolved_project):
        raise ValueError("SoundEmitter target escapes the selected project")
    cursor = resolved_project
    for part in path.absolute().relative_to(resolved_project).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("SoundEmitter target refuses symlink components")
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("SoundEmitter target must be an owned regular project file")


def synchronize_sound_emitter(project: Path, work: Path, *, requested: bool, resolved: dict[str, Path] | None = None) -> dict:
    """Select the exact accepted SoundEmitter prefab form before the build key."""
    project = project.resolve(strict=True)
    work = work.resolve(strict=True)
    if not project.is_relative_to(work):
        raise ValueError("SoundEmitter output project must remain under ignored work/")
    accepted = json.loads((work / "config/accepted-input.json").read_text(encoding="utf-8"))
    reconstruction = json.loads((work / "config/reconstruction.json").read_text(encoding="utf-8"))
    project_input = json.loads((project / ".port-input.json").read_text(encoding="utf-8"))
    input_id = accepted.get("input_id")
    if input_id != SOUND_EMITTER_ACCEPTED_INPUT_ID or reconstruction.get("input_id") != input_id or project_input.get("input_id") != input_id:
        raise ValueError("SoundEmitter accepted input does not match the selected project")
    projects = reconstruction.get("projects")
    if reconstruction.get("success") is not True or not isinstance(projects, list) or len(projects) != 1:
        raise ValueError("SoundEmitter requires one successful accepted export project")
    export_value = projects[0]
    if not isinstance(export_value, str) or not export_value.startswith("work/"):
        raise ValueError("accepted export path must be relative to work/")
    export = work_path(work, export_value.removeprefix("work/"), "accepted export", directory=True)
    source_relative = export.relative_to(work) / SOUND_EMITTER_ASSET
    source = work_path(work, source_relative.as_posix(), "SoundEmitter source")
    source_meta = work_path(work, source_relative.as_posix() + ".meta", "SoundEmitter source metadata")
    target = project / "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab"
    target_meta = Path(str(target) + ".meta")
    _safe_project_file(target, project)
    _safe_project_file(target_meta, project)
    if _asset_guid(source_meta) != SOUND_EMITTER_GUID or _asset_guid(target_meta) != SOUND_EMITTER_GUID:
        raise ValueError("SoundEmitter source/project asset GUID relationship changed")
    if requested:
        selected_prefab = None if resolved is None else resolved.get("prefab")
        if selected_prefab is None or Path(selected_prefab).resolve() != (export / SOUND_EMITTER_WWISE_PATH).resolve():
            raise ValueError("requested audio prefab is not the accepted WwiseGlobal source")
    audio_meta = project / "Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.MonoBehaviour.dll.meta"
    _safe_project_file(audio_meta, project)
    if _asset_guid(audio_meta) != AK_GAME_OBJECT_SCRIPT_GUID:
        raise ValueError("AkGameObj source script GUID changed")

    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOUND_EMITTER_ACCEPTED_SOURCE_SHA256:
        raise ValueError("accepted SoundEmitter source bytes differ from the pinned import receipt")
    source_text = source_bytes.decode("utf-8")
    stripped_text = _sound_emitter_stripped_text(source_text)
    prior_bytes = target.read_bytes()
    prior_text = prior_bytes.decode("utf-8")
    if prior_text not in {source_text, stripped_text}:
        raise ValueError("staged SoundEmitter differs beyond the exact source AkGameObj removal")
    desired_bytes = source_bytes if requested else stripped_text.encode("utf-8")
    if prior_bytes != desired_bytes:
        mode = target.stat().st_mode & 0o777
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".sound-emitter-", dir=target.parent, delete=False) as stream:
                temp_name = Path(stream.name)
                stream.write(desired_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, mode)
            os.replace(temp_name, target)
        finally:
            if temp_name is not None:
                temp_name.unlink(missing_ok=True)
    return {
        "requested": requested,
        "path": "Assets/WholeGame/RoR2/Base/Utility/SoundEmitter.prefab",
        "asset_guid": SOUND_EMITTER_GUID,
        "component_script_guid": AK_GAME_OBJECT_SCRIPT_GUID,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "before_sha256": hashlib.sha256(prior_bytes).hexdigest(),
        "after_sha256": file_sha(target),
        "component_restored": requested,
    }


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
    producer = load(
        Path(__file__).with_name("original_game_audio_produce.py"),
        "audio_build_producer",
    )
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
        payload["passive_pcm_capture_requested"] = selection["passive_pcm_capture_requested"]
        payload["input_sha256"] = {key: file_sha(path) for key, path in sorted(resolved.items()) if key != "stage_root"}
        payload["receipt_bound_payload"] = json.loads(resolved["stage_receipt"].read_text(encoding="utf-8"))["outputs"]
    sound_emitter = synchronize_sound_emitter(project, work, requested=variant == "requested", resolved=resolved)
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
        return {
            "producer": {
                "variant": variant,
                "cached": True,
                "generation_key": generation_key,
            },
            "stage": receipt,
            "variant": variant,
            "sound_emitter": sound_emitter,
        }

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
            selection["passive_pcm_capture_requested"],
        )
        record_generation(output, generation_key, payload)
        receipt = stager.stage(
            project,
            output / "artifact-manifest.json",
            output / "generated/request.json",
            resolved["stage_receipt"],
        )
    return {"producer": result, "stage": receipt, "variant": variant, "sound_emitter": sound_emitter}


__all__ = ["stage_for_build"]
