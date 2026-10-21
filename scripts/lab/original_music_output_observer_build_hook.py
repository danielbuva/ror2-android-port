"""Receipt-bound original music native-return observation after audio staging.

This transformation observes the exact source MusicController calls; it makes
no Wwise calls and does not imply that an accepted output is audible.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "environment/toolchain.json").is_file())
GAME = Path("Assets/LabLoadingScene/Plugins/RoR2.dll")
API = Path("Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll")
CORE = Path("Assets/LabLoadingScene/Plugins/OriginalOwnerProbeObserver.dll")
CORE_TARGET = CORE.as_posix()
STAGE = Path("Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json")
SCHEMA = "original-music-output-observer-stage-r1"
RAW_GAME = "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc"
ACCEPTED_INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
GUARDED_GAME = "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30"
ACCEPTED_GAME = "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d"
LEGACY_OBSERVED_GAME = "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef"
NATIVE_RESULT_OBSERVED_GAME = "a6385e3166d3950944da8a08f145d7e9be602571a6a75b4afb18279801f44311"
R10_API = "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b"
API_PROFILES = {
    "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
}
AUDIO_RECEIPT = Path("Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json")
TRANSFORM_PROJECT = ROOT / "tools/assembly-transforms/MusicOutputObserverCecilTransform.csproj"
TRANSFORM = ROOT / "tools/assembly-transforms/MusicOutputObserverCecilTransform.cs"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(path: Path, *, missing: bool = False) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("symlink path component refused: " + str(cursor))
        if not missing and not cursor.exists():
            raise ValueError("required path component is missing: " + str(cursor))


def _receipt(project: Path) -> tuple[dict, str]:
    path = project / AUDIO_RECEIPT
    _safe(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema") != "original-game-audio-project-stage-r1":
        raise ValueError("exact original-audio stage receipt is required")
    return value, hashlib.sha256(raw).hexdigest()


def _generation(project: Path, audio: dict, receipt_sha: str) -> Path:
    if audio.get("requested") is not True or audio.get("runtime_accepted") is not False or audio.get("audible") is not False:
        raise ValueError("music output observation requires a requested but unaccepted original-audio stage")
    lineage = audio.get("lineage")
    if (
        audio.get("accepted_input_id") != ACCEPTED_INPUT_ID
        or not isinstance(lineage, dict)
        or lineage.get("accepted_input_id") != ACCEPTED_INPUT_ID
        or lineage.get("accepted_game_sha256") != ACCEPTED_GAME
        or lineage.get("guarded_game_input_sha256") != GUARDED_GAME
        or lineage.get("composed_game_sha256") != RAW_GAME
        or lineage.get("composed_api_sha256") not in API_PROFILES
    ):
        raise ValueError("audio stage is outside exact 6f96/d540-or-1ced observer profiles")
    if sha(project / GAME) != RAW_GAME or sha(project / API) != lineage["composed_api_sha256"]:
        raise ValueError("staged game/API bytes differ from the exact original-audio pair")
    rows = audio.get("outputs")
    game_rows = [row for row in rows if isinstance(row, dict) and row.get("target") == GAME.as_posix()] if isinstance(rows, list) else []
    core_rows = [row for row in rows if isinstance(row, dict) and row.get("target") == CORE_TARGET] if isinstance(rows, list) else []
    if len(game_rows) != 1 or game_rows[0].get("sha256") != RAW_GAME:
        raise ValueError("audio stage does not own exactly the expected raw PointSound game module")
    if len(core_rows) != 1 or not (project / CORE).is_file() or sha(project / CORE) != core_rows[0].get("sha256"):
        raise ValueError("observer assembly differs from its exact preceding audio stage row")
    return lineage


def _copy_verified(source: Path, destination: Path, expected: str, replace: str) -> None:
    _safe(source)
    _safe(destination, missing=True)
    current = sha(destination) if destination.is_file() else None
    if current not in (expected, replace):
        raise ValueError("observer target is outside the exact raw/observed game pair")
    with tempfile.NamedTemporaryFile(prefix=".music-observer-", dir=destination.parent, delete=False) as stream:
        temp = Path(stream.name)
        with source.open("rb") as src:
            shutil.copyfileobj(src, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if sha(temp) != expected:
        temp.unlink(missing_ok=True)
        raise ValueError("observer stage copy hash mismatch")
    os.replace(temp, destination)


def stage(project: Path, work: Path, reference_directory: Path, profile: str) -> dict:
    project = project.resolve(strict=True)
    work = work.resolve(strict=True)
    canonical_work = (ROOT / "work").resolve(strict=True)
    if work != canonical_work or not project.is_relative_to(work):
        raise ValueError("observer stage is restricted to the canonical ignored work project")
    _safe(project)
    game = project / GAME
    receipt_path = project / STAGE
    _safe(receipt_path, missing=True)
    if receipt_path.exists():
        raise ValueError("previous music observer stage must be restored before replacement")
    audio, audio_receipt_sha = _receipt(project)
    lineage = _generation(project, audio, audio_receipt_sha)
    expected_profile = "post-audio-r10-1ced-game-6f96"
    if profile != expected_profile:
        raise ValueError("observer transform resolver profile differs from exact audio API")
    expected_output = NATIVE_RESULT_OBSERVED_GAME
    if lineage["composed_api_sha256"] != R10_API:
        raise ValueError("new music observer production result is qualified only for the exact 1ced API")
    camera_pins = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text(encoding="utf-8"))
    script = ROOT / camera_pins["source_paths"]["producer"]
    import importlib.util

    spec = importlib.util.spec_from_file_location("music_observer_camera_producer", script)
    if spec is None or spec.loader is None:
        raise ValueError("exact camera resolver verifier is unavailable")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    editor_contents, _ = producer.pinned_editor(camera_pins)
    reference_directory, _ = producer.exact_resolution_closure(reference_directory, camera_pins, profile, project, editor_contents)
    core = project / CORE
    if not core.is_file() or core.is_symlink():
        raise ValueError("staged observer assembly is absent or unsafe")
    core_hash = sha(core)
    toolchain = json.loads((ROOT / "environment/toolchain.json").read_text(encoding="utf-8"))
    editor = Path(os.environ.get("UNITY_EDITOR", "")).expanduser()
    if not editor.is_absolute() or not editor.is_file():
        raise ValueError("UNITY_EDITOR must identify the pinned Unity editor")
    contents = editor.resolve().parent.parent
    if contents.name != "Contents" or contents.parents[1].name != toolchain["unity_version"]:
        raise ValueError("Unity editor differs from the exact tracked toolchain")
    mono = contents / "MonoBleedingEdge/bin/mono"
    cecil = contents / "MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll"
    dotnet_text = shutil.which("dotnet")
    if (
        not mono.is_file()
        or mono.is_symlink()
        or not cecil.is_file()
        or cecil.is_symlink()
        or not TRANSFORM.is_file()
        or not TRANSFORM_PROJECT.is_file()
        or not dotnet_text
    ):
        raise ValueError("pinned Unity Mono/Cecil, .NET SDK or observer producer source is missing")
    dotnet = Path(dotnet_text).resolve(strict=True)
    cecil_pins = json.loads((ROOT / "recipe/assembly-transforms.json").read_text())
    camera_pins = json.loads((ROOT / "recipe/native-view-camera-transform.json").read_text())
    expected_tool = camera_pins.get("unity_tools_sha256", {})
    if sha(cecil) != cecil_pins["cecil_sha256"] or sha(cecil) != expected_tool.get("cecil"):
        raise ValueError("Unity Cecil differs from the repository transform pin")
    if sha(mono) != expected_tool.get("mono"):
        raise ValueError("Unity Mono differs from the camera cohort's pinned toolchain")
    expected_transform = camera_pins.get("source_sha256", {}).get("music_observer_transform")
    expected_project = camera_pins.get("source_sha256", {}).get("music_observer_transform_project")
    if not expected_transform or sha(TRANSFORM) != expected_transform or not expected_project or sha(TRANSFORM_PROJECT) != expected_project:
        raise ValueError("music output observer transform source/project differs from its exact recipe pin")
    generation_key = hashlib.sha256(
        json.dumps(
            {"audio_receipt": audio_receipt_sha, "input": RAW_GAME, "api": lineage["composed_api_sha256"], "core": core_hash, "transform": sha(TRANSFORM)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    output_root = work / "generated/original-music-output-observer" / generation_key
    _safe(output_root, missing=True)
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot = output_root / "RoR2.preimage.dll"
    output = output_root / "RoR2.music-output-observed.dll"
    if snapshot.exists() or output.exists():
        if not snapshot.is_file() or not output.is_file() or sha(snapshot) != RAW_GAME or sha(output) != expected_output:
            raise ValueError("cached observer generation is incomplete or differs from exact immutable hashes")
        transform_log = "reused exact content-addressed observer output"
    else:
        shutil.copyfile(game, snapshot)
        if sha(snapshot) != RAW_GAME:
            raise ValueError("observer input snapshot failed its exact source hash")
        tool_root = output_root / "transform-tool"
        build = subprocess.run(
            [str(dotnet), "build", str(TRANSFORM_PROJECT), "-p:UseSharedCompilation=false", "-p:CecilPath=" + str(cecil), "-o", str(tool_root)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if build.returncode:
            raise RuntimeError("music observer Cecil compile failed: " + build.stdout)
        tool = tool_root / "MusicOutputObserverCecilTransform.dll"
        extra_references = [
            project / "Assets/LabLoadingScene/Plugins",
            contents / "MonoBleedingEdge/lib/mono/4.7.2-api",
            contents / "MonoBleedingEdge/lib/mono/4.7.2-api/Facades",
            contents / "Managed/UnityEngine",
            contents / "NetStandard/ref/2.1.0",
            contents / "NetStandard/compat/2.1.0/shims/netstandard",
            contents / "NetStandard/compat/2.1.0/shims/netfx",
        ]
        run = subprocess.run(
            [str(dotnet), str(tool), "transform", str(snapshot), str(core), str(reference_directory), str(output), *[str(path) for path in extra_references]],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if run.returncode or not output.is_file() or sha(output) != expected_output:
            raise RuntimeError("exact music observer transform failed: " + run.stdout)
        transform_log = run.stdout
    _copy_verified(output, game, expected_output, RAW_GAME)
    receipt = {
        "schema": SCHEMA,
        "accepted": False,
        "runtime_dispatch_ready": False,
        "audio_stage_receipt_sha256": audio_receipt_sha,
        "audio_stage_input_game_sha256": RAW_GAME,
        "api_sha256": lineage["composed_api_sha256"],
        "core_observer_sha256": core_hash,
        "input_sha256": RAW_GAME,
        "output_sha256": expected_output,
        "generation": generation_key,
        "preimage_snapshot": output_root.relative_to(work).as_posix() + "/RoR2.preimage.dll",
        "limitations": "Original output, intro PostEvent and selected-track SetState returns are bounded observations; no return proves rendering, event completion, output activity or audibility.",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_receipt = receipt_path.with_name("." + receipt_path.name + ".tmp")
    _safe(temporary_receipt, missing=True)
    try:
        temporary_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        os.replace(temporary_receipt, receipt_path)
    except Exception:
        temporary_receipt.unlink(missing_ok=True)
        if game.is_file() and sha(game) == expected_output:
            _copy_verified(snapshot, game, RAW_GAME, expected_output)
        raise
    return {"receipt": receipt, "receipt_sha256": sha(receipt_path), "transform_log": transform_log}


def restore(project: Path, work: Path) -> dict | None:
    # A destination project without an observer receipt has nothing owned by
    # this hook to restore. Keep that common case inert before requiring the
    # canonical ignored-work root; a present receipt still takes the strict
    # lineage and containment path below.
    project = Path(project)
    path = project / STAGE
    _safe(path, missing=True)
    if not path.exists():
        return None
    project = project.resolve(strict=True)
    work = work.resolve(strict=True)
    canonical_work = (ROOT / "work").resolve(strict=True)
    if work != canonical_work or not project.is_relative_to(work):
        raise ValueError("observer restore is restricted to the canonical ignored work project")
    path = project / STAGE
    if (project / "Assets/StreamingAssets/Lab/NativeViewCameraStageReceipt.json").exists():
        raise ValueError("camera stage must be restored before its music-observer predecessor")
    audio, audio_receipt_sha = _receipt(project)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA or receipt.get("audio_stage_receipt_sha256") != audio_receipt_sha:
        raise ValueError("observer receipt is not bound to current audio stage")
    lineage = audio.get("lineage")
    if (
        audio.get("requested") is not True
        or audio.get("accepted_input_id") != ACCEPTED_INPUT_ID
        or not isinstance(lineage, dict)
        or lineage.get("accepted_input_id") != ACCEPTED_INPUT_ID
        or lineage.get("accepted_game_sha256") != ACCEPTED_GAME
        or lineage.get("guarded_game_input_sha256") != GUARDED_GAME
        or lineage.get("composed_game_sha256") != RAW_GAME
        or lineage.get("composed_api_sha256") != receipt.get("api_sha256")
    ):
        raise ValueError("observer receipt is not bound to the exact live audio/API lineage")
    api_hash = receipt.get("api_sha256")
    output_hash = receipt.get("output_sha256")
    allowed_pairs = {
        ("d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23", LEGACY_OBSERVED_GAME),
        (R10_API, LEGACY_OBSERVED_GAME),  # exact historical R22 receipt remains unwindable
        (R10_API, NATIVE_RESULT_OBSERVED_GAME),
    }
    if receipt.get("input_sha256") != RAW_GAME or (api_hash, output_hash) not in allowed_pairs:
        raise ValueError("observer receipt names an unknown exact input/API/output pair")
    game = project / GAME
    if sha(game) != output_hash:
        raise ValueError("game module differs from the exact observer-owned stage")
    snapshot_rel = receipt.get("preimage_snapshot")
    if (
        not isinstance(snapshot_rel, str)
        or not snapshot_rel
        or "\\" in snapshot_rel
        or Path(snapshot_rel).is_absolute()
        or ".." in Path(snapshot_rel).parts
        or Path(snapshot_rel).as_posix() != snapshot_rel
    ):
        raise ValueError("observer preimage path is not a canonical work-relative path")
    snapshot = (work / snapshot_rel).resolve(strict=True)
    if not snapshot.is_relative_to(work) or sha(snapshot) != RAW_GAME:
        raise ValueError("observer preimage snapshot is missing or changed")
    if sha(project / API) != receipt.get("api_sha256") or sha(project / CORE) != receipt.get("core_observer_sha256"):
        raise ValueError("observer restore API/core differs from its receipt-bound audio stage")
    _copy_verified(snapshot, game, RAW_GAME, output_hash)
    path.unlink()
    return {"restored_sha256": RAW_GAME, "audio_stage_receipt_sha256": audio_receipt_sha}
