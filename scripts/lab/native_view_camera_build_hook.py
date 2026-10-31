"""Stage the exact native-view camera marker after the original-audio owner.

This helper is deliberately limited to the canonical ignored whole-catalog
project and the two reviewed RoR2 module profiles.  It is a producer/stager,
not a runtime enable switch: the camera owner remains inert until its authored
caller supplies an explicit request and the original source-body contract.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from pathlib import PurePosixPath

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "environment/toolchain.json").is_file() and (parent / "recipe").is_dir())
CAMERA_SOURCE_ROOT = ROOT
CAMERA_PINS = ROOT / "recipe/native-view-camera-transform.json"
CAMERA_STAGE_RELATIVE = Path("Assets/StreamingAssets/Lab/NativeViewCameraStageReceipt.json")
AUDIO_STAGE_RELATIVE = Path("Assets/StreamingAssets/Lab/OriginalGameAudioStageReceipt.json")
GAME_RELATIVE = Path("Assets/LabLoadingScene/Plugins/RoR2.dll")
API_RELATIVE = Path("Assets/LabLoadingScene/Plugins/AK.Wwise.Unity.API.dll")
AUDIO_RESOLVER_TARGETS = {
    "api": API_RELATIVE,
    "core": Path("Assets/LabLoadingScene/Plugins/GameAudioOriginalCore.dll"),
    "observer": Path("Assets/LabLoadingScene/Plugins/OriginalOwnerProbeObserver.dll"),
}
STAGE_SCHEMA = "native-view-camera-project-stage-r1"
AUDIO_SCHEMA = "original-game-audio-project-stage-r1"
HASHES = {
    "accepted_input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "r4_manifest_sha256": "a5a8794dc84a7247d31768b3d54d1ef509c509a3642eb693e47dcf53f361deef",
    "stage_receipt_sha256": "db1969babb2db2f4201ebdb6c971b084c5ab9336fff5623187555dfcc7b18978",
    "ordinary_api": "107295e478a58ef295a83228111f375c536861bc9081f482d638c59899bf495c",
    "ordinary_game": "3124a2ed9cf458acee78b1beaf969590b184be452e2b3aa5a8852df82ff95d30",
    "composed_api": "d540a22693ca7a149cdb2344ce5f61936c2c998a9d82f0bdf66b5492edb18e23",
    "pcm_composed_api": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
    "previous_composed_api_restore_only": "793f22866c85bbcf104f20f5c1f619062eaad9f5414a217b602fe758c71e01b9",
    "composed_game": "1034a747e31a3b79554b9cb06f941c7acabaa9e0ee82c2a00abc4b24f9327c1c",
    "point_sound_composed_game": "6f96ed83bf6358b9aecc4cdf866d424caf04af9abd34ad368c8db271d27c15cc",
    "music_observed_game": "27340ed60dbfe77f66fa394d028b597d3e4613ee8ea405416c061766fb226eef",
    "native_result_observed_game": "a6385e3166d3950944da8a08f145d7e9be602571a6a75b4afb18279801f44311",
    "lightning_r3_point_sound_composed_game": "594282cfa617ac58eda6965e0a48e6958438f345cbb98bfb7cb49b9130efad1d",
    "lightning_r3_native_result_observed_game": "619af38a62b19fdfcd6ef1408548aecedbda3e0830be7982cc4f96cd6b000523",
    "lightning_r3_native_result_camera_output": "15a92aa6f513e2271ce7240c33a205b0376fff37200089987f0cb54944c3382c",
    "music_camera_output": "4bd3b240ce5a9cb620d14ce4041f493ba013b9700d792dc9c99c8666f3af06f0",
    "native_result_camera_output": "64628a52d443786d7920fc8d6b65215f32886cb3489bf5439c3efaed17e43ccf",
    "camera_default": "494ba9acd8ea34bed17ac56edb9a49eafa8cb5afd2f91466b95ca0d71ce3b8cd",
    "camera_default_previous_restore_only": "236fab2c616b1a017971c316437ec1a9fa9f6b3999563263d4a8ab689a1e59b6",
    "camera_after_audio": "83513fd59e81d84d093a1f9fb6d5eaaafb6382165f060dbd1b96b14990164aeb",
    "camera_after_audio_previous_restore_only": "e16e01bc6545bb6d8248c9196be890b99cf60df721d1b894b8d9871a880c7f91",
    "camera_after_point_sound": "0da94add5e860c6f3dd05f4e69d3019208e9d58294874eb373619d1756b8876d",
    "camera_after_r10_1ced": "0da94add5e860c6f3dd05f4e69d3019208e9d58294874eb373619d1756b8876d",
    # Restore-only predecessor emitted by the exact older R12 camera receipt.
    # It is never selected by select_profile or stage_after_audio.
    "camera_predecessor_f6bc_restore_only": "f6bc1a860e8abe2c82a397a83e55ec2050136e91763ade302ed0e181b320083c",
    "camera_after_point_sound_previous_restore_only": "41b66d072085f70b6929dcd2a566fffff3f26b9c886d8781624e52ae8ab7e92f",
    # R18 delegate-bind outputs retained only to unwind receipts created before
    # the marker-refresh transform. These are never emitted by current staging.
    "camera_default_delegate_previous_restore_only": "d5fc522e83cb6f6f6845b2a8b7e5de28011031fe2f3b54c0716c52db9679c65c",
    "camera_after_audio_delegate_previous_restore_only": "e4aeeb5acb7b81922a0a6603d01c1d407c57e9b00852b5e15ef70838e1961e5b",
    "camera_after_point_sound_delegate_previous_restore_only": "2ae5d92a652d69c7e6fd471448af203d52be3ef9350743a91fc84a5bd2bc1384",
    "camera_music_observer_delegate_previous_restore_only": "a2054dcfc5d14d2fdfba0fd0e61851e4a153b842be6bb6f1c0e1df8ef634762e",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_symlinks(path: Path, *, allow_missing: bool = False) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"symlink component refused: {cursor}")
        if not allow_missing and not cursor.exists():
            raise ValueError(f"required path component is missing: {cursor}")


def _canonical_project(project: Path, work: Path) -> tuple[Path, Path]:
    project = project.resolve(strict=True)
    work = work.resolve(strict=True)
    expected_work = (ROOT / "work").resolve(strict=True)
    if work != expected_work or project == work or not project.is_relative_to(work):
        raise ValueError("camera build hook requires a project below the canonical ignored work/ root")
    if not project.is_dir():
        raise ValueError("camera build project is not a directory")
    _reject_symlinks(project)
    return project, work


def _audio_receipt(project: Path) -> tuple[dict, str]:
    path = project / AUDIO_STAGE_RELATIVE
    _reject_symlinks(path)
    raw = path.read_bytes()
    receipt = json.loads(raw)
    if not isinstance(receipt, dict) or receipt.get("schema") != AUDIO_SCHEMA:
        raise ValueError("camera stage requires the exact current audio-stage receipt")
    return receipt, hashlib.sha256(raw).hexdigest()


def _verify_tracked_sources(pins: dict) -> None:
    for role, expected in pins.get("source_sha256", {}).items():
        relative = pins.get("source_paths", {}).get(role)
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError(f"camera producer pins omit a safe tracked source role: {role}")
        path = CAMERA_SOURCE_ROOT / relative
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise ValueError(f"reviewed camera source drift: {relative}")


def _audio_resolver_sources(project: Path, generation: Path, manifest: dict, audio: dict) -> list[dict]:
    """Bind the post-audio resolver overlay to the exact current stage rows."""
    manifest_outputs = manifest.get("outputs")
    stage_outputs = audio.get("outputs")
    if not isinstance(manifest_outputs, list) or not isinstance(stage_outputs, list):
        raise ValueError("audio artifact and stage receipts must expose output rows")
    work_root = (ROOT / "work").resolve(strict=True)
    resolved_rows = []
    for role, target in AUDIO_RESOLVER_TARGETS.items():
        manifest_rows = [row for row in manifest_outputs if isinstance(row, dict) and row.get("role") == role]
        stage_rows = [row for row in stage_outputs if isinstance(row, dict) and row.get("target") == target.as_posix()]
        if len(manifest_rows) != 1 or len(stage_rows) != 1:
            raise ValueError("post-audio resolver role is missing or duplicated: " + role)
        row = manifest_rows[0]
        source_value = row.get("source")
        if not isinstance(source_value, str):
            raise ValueError("audio resolver artifact source is malformed: " + role)
        source_relative = PurePosixPath(source_value)
        if (
            source_relative.is_absolute()
            or not source_relative.parts
            or ".." in source_relative.parts
            or "\\" in source_value
            or source_relative.as_posix() != source_value
        ):
            raise ValueError("audio resolver artifact source path is unsafe: " + role)
        source = (work_root / Path(*source_relative.parts)).resolve(strict=True)
        if not source.is_relative_to(work_root) or not source.is_relative_to(generation.resolve(strict=True)) or source.is_symlink() or not source.is_file():
            raise ValueError("audio resolver artifact source escapes its exact work generation: " + role)
        expected = row.get("sha256")
        if not isinstance(expected, str) or sha256(source) != expected:
            raise ValueError("audio resolver artifact source hash differs: " + role)
        if stage_rows[0].get("sha256") != expected:
            raise ValueError("audio stage row differs from resolver artifact: " + role)
        staged = project / target
        _reject_symlinks(staged)
        if not staged.is_file() or sha256(staged) != expected:
            raise ValueError("staged audio resolver target differs from artifact: " + role)
        if role == "api" and expected not in {HASHES["composed_api"], HASHES["pcm_composed_api"]}:
            raise ValueError("post-audio resolver API is outside the exact d540/1ced profiles")
        resolved_rows.append(
            {
                "role": role,
                "filename": target.name,
                "target": target.as_posix(),
                "source": source_relative.as_posix(),
                "sha256": expected,
            }
        )
    return resolved_rows


def _resolver_module():
    path = CAMERA_SOURCE_ROOT / "scripts/lab/native_view_camera_resolver.py"
    if not path.is_file() or path.is_symlink():
        raise ValueError("camera resolver producer is missing")
    spec = importlib.util.spec_from_file_location("native_view_camera_resolver", path)
    if spec is None or spec.loader is None:
        raise ValueError("camera resolver producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ensure_resolver_set(
    resolver_root: Path, resolver_set: dict, project: Path, input_path: Path, api_hash: str, profile: str, pins: dict, editor_contents: Path
) -> Path:
    module = _resolver_module()
    profile_pins = pins["profiles"].get(profile) or pins.get("music_observer_resolver_profiles", {}).get(profile)
    if not isinstance(profile_pins, dict) or profile_pins.get("input_sha256") != sha256(input_path):
        raise ValueError("resolver-only profile does not match its exact source input")
    rows = module.source_rows(project, editor_contents, profile_pins["input_sha256"], api_hash)
    inventory_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    destination = resolver_root / (resolver_set["profile"] + "-" + inventory_hash[:16])
    if not (destination / "resolver-set.json").is_file():
        module.materialize(
            profile,
            project,
            input_path,
            editor_contents,
            destination,
            profile_pins["input_sha256"],
            api_hash,
        )
    else:
        receipt = json.loads((destination / "resolver-set.json").read_text(encoding="utf-8"))
        if receipt.get("source_inventory_sha256") != inventory_hash:
            raise ValueError("cached resolver source inventory differs from current project/editor inputs")
    return destination / "assemblies"


def _verify_stage_manifest_rows(stage: dict, manifest: dict, project: Path) -> None:
    stage_rows = stage.get("outputs")
    manifest_rows = manifest.get("outputs")
    if not isinstance(stage_rows, list) or not isinstance(manifest_rows, list) or not stage_rows:
        raise ValueError("audio stage and artifact manifest must contain complete output inventories")

    def normalized(rows: list, target_key: str) -> list[tuple[str, str]]:
        result = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("audio output inventory contains a malformed row")
            target, digest = row.get(target_key), row.get("sha256")
            path = PurePosixPath(target) if isinstance(target, str) else None
            if (
                path is None
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in target
                or path.as_posix() != target
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)
            ):
                raise ValueError("audio output inventory contains an unsafe target or hash")
            result.append((target, digest))
        if len(set(result)) != len(result) or len({target for target, _ in result}) != len(result):
            raise ValueError("audio output inventory has duplicate targets or rows")
        return sorted(result)

    stage_set = normalized(stage_rows, "target")
    if stage_set != normalized(manifest_rows, "target"):
        raise ValueError("audio staged target/hash set differs from its exact artifact manifest")
    for relative, expected in stage_set:
        path = project / Path(*PurePosixPath(relative).parts)
        _reject_symlinks(path)
        if not path.is_file() or sha256(path) != expected:
            if (
                relative == GAME_RELATIVE.as_posix()
                and expected in {HASHES["point_sound_composed_game"], HASHES["lightning_r3_point_sound_composed_game"]}
                and sha256(path)
                in {
                    HASHES["music_observed_game"],
                    HASHES["native_result_observed_game"],
                    HASHES["lightning_r3_native_result_observed_game"],
                    HASHES["lightning_r3_native_result_camera_output"],
                }
            ):
                audio, receipt_sha = _audio_receipt(project)
                _music_observer_receipt(project, receipt_sha, audio)
                continue
            raise ValueError("audio staged file differs from the exact stage/manifest row: " + relative)


def _select_point_sound_profile(audio: dict, game_hash: str, api_hash: str) -> tuple[str, str]:
    """Select a receipt-bound exact PointSound lineage, independent of PCM state."""
    if game_hash == HASHES["lightning_r3_point_sound_composed_game"]:
        if api_hash != HASHES["pcm_composed_api"]:
            raise ValueError("R3 PointSound continuation requires the exact 1ced API")
        lineage = audio.get("lineage")
        output_rows = audio.get("outputs")
        game_rows = (
            [row for row in output_rows if isinstance(row, dict) and row.get("target") == GAME_RELATIVE.as_posix()] if isinstance(output_rows, list) else []
        )
        if (
            audio.get("requested") is not True
            or audio.get("stage_receipt_sha256") != HASHES["stage_receipt_sha256"]
            or not isinstance(lineage, dict)
            or lineage.get("composed_game_sha256") != game_hash
            or lineage.get("composed_api_sha256") != api_hash
            or len(game_rows) != 1
            or game_rows[0].get("sha256") != game_hash
        ):
            raise ValueError("R3 PointSound camera profile requires its exact accepted source lineage")
        return "post-audio-r10-1ced-game-lightning-r3", HASHES["lightning_r3_native_result_observed_game"]
    if game_hash != HASHES["point_sound_composed_game"]:
        raise ValueError("PointSound camera profile requires an exact accepted composed game image")
    if api_hash == HASHES["composed_api"]:
        profile = "post-audio-point-sound-6f96-api-d540"
        output_hash = HASHES["camera_after_point_sound"]
        if audio.get("passive_pcm_capture_requested") is True:
            raise ValueError("d540 profile cannot claim the later passive-PCM request")
    elif api_hash == HASHES["pcm_composed_api"]:
        profile = "post-audio-r10-1ced-game-6f96"
        output_hash = HASHES["camera_after_r10_1ced"]
        if type(audio.get("passive_pcm_capture_requested")) is not bool:
            raise ValueError("1ced profile requires an explicit boolean PCM request state")
    else:
        raise ValueError("PointSound camera API is outside the exact d540/1ced profiles")
    lineage = audio.get("lineage")
    if (
        audio.get("requested") is not True
        or audio.get("stage_receipt_sha256") != HASHES["stage_receipt_sha256"]
        or not isinstance(lineage, dict)
        or lineage.get("composed_game_sha256") != game_hash
        or lineage.get("composed_api_sha256") != api_hash
    ):
        raise ValueError("PointSound camera profile requires its exact accepted audio receipt")
    output_rows = audio.get("outputs")
    game_rows = [row for row in output_rows if row.get("target") == GAME_RELATIVE.as_posix()] if isinstance(output_rows, list) else []
    if len(game_rows) != 1 or game_rows[0].get("sha256") != game_hash:
        raise ValueError("PointSound audio receipt must own exactly the selected game module")
    return profile, output_hash


def _music_observer_receipt(project: Path, audio_receipt_sha: str, audio: dict) -> dict:
    path = project / "Assets/StreamingAssets/Lab/OriginalMusicOutputObserverStageReceipt.json"
    _reject_symlinks(path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    lineage = audio.get("lineage")
    api_hash = receipt.get("api_sha256") if isinstance(receipt, dict) else None
    output_hash = receipt.get("output_sha256") if isinstance(receipt, dict) else None
    allowed_game_states = {
        (HASHES["composed_api"], HASHES["music_observed_game"]): {
            HASHES["music_observed_game"],
            HASHES["music_camera_output"],
            HASHES["camera_music_observer_delegate_previous_restore_only"],
        },
        (HASHES["pcm_composed_api"], HASHES["music_observed_game"]): {
            HASHES["music_observed_game"],
            HASHES["music_camera_output"],
            HASHES["camera_music_observer_delegate_previous_restore_only"],
        },
        (HASHES["pcm_composed_api"], HASHES["native_result_observed_game"]): {
            HASHES["native_result_observed_game"],
            HASHES["native_result_camera_output"],
        },
        (HASHES["pcm_composed_api"], HASHES["lightning_r3_native_result_observed_game"]): {
            HASHES["lightning_r3_native_result_observed_game"],
            HASHES["lightning_r3_native_result_camera_output"],
        },
    }
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "original-music-output-observer-stage-r1"
        or receipt.get("accepted") is not False
        or receipt.get("runtime_dispatch_ready") is not False
        or receipt.get("audio_stage_receipt_sha256") != audio_receipt_sha
        or receipt.get("input_sha256")
        != (
            HASHES["lightning_r3_point_sound_composed_game"]
            if output_hash in {HASHES["lightning_r3_native_result_observed_game"], HASHES["lightning_r3_native_result_camera_output"]}
            else HASHES["point_sound_composed_game"]
        )
        or (api_hash, output_hash) not in allowed_game_states
        or not isinstance(lineage, dict)
        or lineage.get("composed_game_sha256") != receipt.get("input_sha256")
        or api_hash != lineage.get("composed_api_sha256")
    ):
        raise ValueError("music observer receipt is not bound to the exact preceding PointSound audio/API/output tuple")
    if (
        output_hash in {HASHES["lightning_r3_native_result_observed_game"], HASHES["lightning_r3_native_result_camera_output"]}
        and receipt.get("profile") != "post-audio-r10-1ced-game-lightning-r3"
    ):
        raise ValueError("R3 observer receipt omits its exact source profile identity")
    if sha256(project / GAME_RELATIVE) not in allowed_game_states[(api_hash, output_hash)]:
        raise ValueError("project game module differs from the exact observer/API camera lineage")
    snapshot_rel = receipt.get("preimage_snapshot")
    if not isinstance(snapshot_rel, str) or "\\" in snapshot_rel or Path(snapshot_rel).is_absolute() or ".." in Path(snapshot_rel).parts:
        raise ValueError("music observer preimage path is malformed")
    snapshot = (ROOT / "work" / snapshot_rel).resolve(strict=True)
    work = (ROOT / "work").resolve(strict=True)
    if not snapshot.is_relative_to(work) or sha256(snapshot) != receipt.get("input_sha256"):
        raise ValueError("music observer preimage snapshot differs from its exact audio-stage input")
    return receipt


def select_profile(
    project: Path,
    audio_build_result: dict | None = None,
    *,
    resolver_root: Path | None = None,
    allow_music_observer_input: bool = False,
) -> dict:
    """Select only the exact default-off, R4, PointSound, or R10 game/API profiles."""
    pins = json.loads(CAMERA_PINS.read_text(encoding="utf-8"))
    audio, receipt_sha = _audio_receipt(project)
    if not isinstance(audio_build_result, dict):
        raise ValueError("camera stage must consume the immediate audio build-hook result")
    producer_result = audio_build_result.get("producer")
    stage_result = audio_build_result.get("stage")
    generation_key = producer_result.get("generation_key") if isinstance(producer_result, dict) else None
    if not isinstance(producer_result, dict) or not isinstance(stage_result, dict):
        raise ValueError("audio build-hook result lacks an exact stage receipt")
    if not isinstance(generation_key, str):
        manifest_path = producer_result.get("manifest_path")
        if isinstance(manifest_path, str):
            candidate_path = Path(manifest_path)
            if candidate_path.name != "artifact-manifest.json" or not candidate_path.is_file():
                raise ValueError("audio producer manifest path is malformed")
            generation_key = candidate_path.parent.name
        else:
            # Noncached default-off production does not return its generation
            # key. Resolve by exact manifest hash in the deterministic keyed
            # cache, never by timestamp or directory order.
            owner_root = project.parent / "original-game-audio-owner"
            _reject_symlinks(owner_root)
            matches = []
            for candidate in owner_root.iterdir():
                if candidate.is_symlink() or not candidate.is_dir() or len(candidate.name) != 64 or any(ch not in "0123456789abcdef" for ch in candidate.name):
                    continue
                candidate_manifest = candidate / "artifact-manifest.json"
                if candidate_manifest.is_file() and not candidate_manifest.is_symlink() and sha256(candidate_manifest) == audio.get("artifact_manifest_sha256"):
                    matches.append(candidate.name)
            if len(matches) != 1:
                raise ValueError("audio stage manifest does not resolve to one deterministic generation cache")
            generation_key = matches[0]
    if len(generation_key) != 64 or any(ch not in "0123456789abcdef" for ch in generation_key):
        raise ValueError("audio build-hook result generation identity is malformed")
    generation = project.parent / "original-game-audio-owner" / generation_key
    if not generation.is_dir():
        raise ValueError("audio build result generation output is missing")
    generation_receipt = generation / "generation.json"
    artifact_manifest = generation / "artifact-manifest.json"
    supplied_manifest = producer_result.get("manifest_path")
    if isinstance(supplied_manifest, str) and Path(supplied_manifest).resolve(strict=True) != artifact_manifest.resolve(strict=True):
        raise ValueError("audio producer returned a manifest outside its exact keyed generation")
    _reject_symlinks(generation_receipt)
    _reject_symlinks(artifact_manifest)
    generated = json.loads(generation_receipt.read_text(encoding="utf-8"))
    manifest = json.loads(artifact_manifest.read_text(encoding="utf-8"))
    _verify_stage_manifest_rows(audio, manifest, project)
    if (
        generated.get("schema") != 1
        or generated.get("generation_key") != generation_key
        or generated.get("inputs", {}).get("variant") != producer_result.get("variant")
        or producer_result.get("variant") != ("requested" if audio.get("requested") is True else "default-off")
        or hashlib.sha256(artifact_manifest.read_bytes()).hexdigest() != audio.get("artifact_manifest_sha256")
        or manifest.get("owner_ancestor_manifest_sha256") != HASHES["r4_manifest_sha256"]
        or manifest.get("accepted_input_id") != HASHES["accepted_input_id"]
        or manifest.get("lineage") != audio.get("lineage")
        or manifest.get("request", {}).get("requested") is not audio.get("requested")
        or stage_result != audio
        or audio.get("runtime_accepted") is not False
        or audio.get("audible") is not False
    ):
        raise ValueError("audio build result is not bound to its exact R4 generation and staged receipt")
    game = project / GAME_RELATIVE
    api = project / API_RELATIVE
    _reject_symlinks(game)
    _reject_symlinks(api)
    game_hash, api_hash = sha256(game), sha256(api)
    if audio.get("accepted_input_id") != HASHES["accepted_input_id"]:
        raise ValueError("audio stage receipt is not bound to the accepted local game input")
    lineage = audio.get("lineage")
    if not isinstance(lineage, dict) or lineage.get("accepted_input_id") != HASHES["accepted_input_id"]:
        raise ValueError("audio stage receipt omits the exact R4 source lineage")
    if game_hash == HASHES["ordinary_game"] and api_hash == HASHES["ordinary_api"]:
        if audio.get("requested") is not False:
            raise ValueError("ordinary 3124 camera profile requires default-off audio receipt")
        if lineage.get("guarded_game_input_sha256") != HASHES["ordinary_game"]:
            raise ValueError("ordinary camera profile has an unrelated guarded game preimage")
        output_hash = HASHES["camera_default"]
        profile = "default-game-3124"
    elif game_hash == HASHES["composed_game"] and api_hash == HASHES["composed_api"]:
        expected_game = HASHES["composed_game"]
        if (
            audio.get("requested") is not True
            or audio.get("stage_receipt_sha256") != HASHES["stage_receipt_sha256"]
            or not isinstance(lineage, dict)
            or lineage.get("composed_game_sha256") != expected_game
            or lineage.get("composed_api_sha256") != HASHES["composed_api"]
        ):
            raise ValueError("composed camera profile requires the accepted audio receipt for its exact 1034/d540 pair")
        output_rows = audio.get("outputs")
        game_rows = [row for row in output_rows if row.get("target") == GAME_RELATIVE.as_posix()] if isinstance(output_rows, list) else []
        if len(game_rows) != 1 or game_rows[0].get("sha256") != expected_game:
            raise ValueError("composed audio receipt does not own exactly the selected game module")
        output_hash = HASHES["camera_after_audio"]
        profile = "post-audio-r4-1034-api-d540"
        resolver_rows = _audio_resolver_sources(project, generation, manifest, audio)
    elif game_hash == HASHES["point_sound_composed_game"] and api_hash in {HASHES["composed_api"], HASHES["pcm_composed_api"]}:
        profile, output_hash = _select_point_sound_profile(audio, game_hash, api_hash)
        resolver_rows = _audio_resolver_sources(project, generation, manifest, audio)
    elif game_hash == HASHES["lightning_r3_point_sound_composed_game"] and api_hash == HASHES["pcm_composed_api"]:
        if not allow_music_observer_input:
            raise ValueError("Lightning R3 point-sound input is music-observer-only and has no measured camera output")
        profile, output_hash = _select_point_sound_profile(audio, game_hash, api_hash)
        output_hash = None
        resolver_rows = _audio_resolver_sources(project, generation, manifest, audio)
    elif game_hash == HASHES["music_observed_game"] and api_hash in {HASHES["composed_api"], HASHES["pcm_composed_api"]}:
        _music_observer_receipt(project, receipt_sha, audio)
        raise ValueError("legacy 27340 music-observer camera pair is restore-only")
    elif game_hash == HASHES["native_result_observed_game"] and api_hash == HASHES["pcm_composed_api"]:
        _music_observer_receipt(project, receipt_sha, audio)
        profile = "post-audio-native-music-results-r23-1ced"
        output_hash = HASHES["native_result_camera_output"]
        resolver_rows = _audio_resolver_sources(project, generation, manifest, audio)
    elif game_hash == HASHES["lightning_r3_native_result_observed_game"] and api_hash == HASHES["pcm_composed_api"]:
        _music_observer_receipt(project, receipt_sha, audio)
        profile = "post-audio-native-music-results-lightning-r3-1ced"
        output_hash = HASHES["lightning_r3_native_result_camera_output"]
        resolver_rows = _audio_resolver_sources(project, generation, manifest, audio)
    else:
        raise ValueError("project API/RoR2 pair is not one of the exact reviewed camera profiles")
    music_observer_source = profile in pins.get("music_observer_resolver_profiles", {})
    resolver_set = (pins["music_observer_resolver_profiles"] if music_observer_source else pins["resolver_profiles"])[profile]
    resolver_base = resolver_root or ROOT / "work/generated/native-view-camera/resolver-sets"
    producer = _producer_module()
    editor_contents, _ = producer.pinned_editor(pins)
    resolver_directory = _ensure_resolver_set(resolver_base, resolver_set, project, game, api_hash, profile, pins, editor_contents)
    _, resolver_receipt = producer.exact_resolution_closure(resolver_directory, pins, profile, project, editor_contents)
    resolver_inventory_sha256 = hashlib.sha256(json.dumps(resolver_receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {
        "profile": profile,
        "resolver_set_profile": resolver_set["profile"],
        "resolver_set_directory": resolver_directory.relative_to(ROOT / "work").as_posix(),
        "resolver_inventory_sha256": resolver_inventory_sha256,
        "resolver_identity_count": resolver_receipt["count"],
        "input_sha256": game_hash,
        "output_sha256": output_hash,
        "audio_stage_receipt_sha256": receipt_sha,
        "audio_requested": audio["requested"],
        "api_sha256": api_hash,
        "audio_artifact_manifest_sha256": audio.get("artifact_manifest_sha256"),
        "audio_artifact_manifest_path": artifact_manifest.resolve(strict=True).relative_to((ROOT / "work").resolve(strict=True)).as_posix(),
        "audio_stage_receipt_path": (project / AUDIO_STAGE_RELATIVE).resolve(strict=True).relative_to((ROOT / "work").resolve(strict=True)).as_posix(),
        "resolver_rows": resolver_rows if profile != "default-game-3124" else [],
        "resolver_effective_assembly_identity_count": resolver_receipt["count"],
    }
    if music_observer_source:
        result["music_observer_source_only"] = True
    return result


def restore_previous_camera(project: Path, work: Path) -> dict | None:
    """Restore an existing camera-owned image before an audio stage.

    Destination rebuilds can have no camera receipt at all, in which case this
    is an inert no-op. A present receipt still must satisfy the canonical work
    boundary and all exact lineage/hash checks before any write.
    """
    project = Path(project)
    receipt_path = project / CAMERA_STAGE_RELATIVE
    _reject_symlinks(receipt_path, allow_missing=True)
    if not receipt_path.exists():
        return None
    project, work = _canonical_project(project, work)
    receipt_path = project / CAMERA_STAGE_RELATIVE
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    if not isinstance(receipt, dict) or receipt.get("schema") != STAGE_SCHEMA:
        raise ValueError("existing camera-stage receipt has an unknown schema")
    audio, audio_sha = _audio_receipt(project)
    if receipt.get("audio_stage_receipt_sha256") != audio_sha:
        raise ValueError("camera receipt is not bound to the current preceding audio receipt")
    if receipt.get("audio_requested") is not audio.get("requested"):
        raise ValueError("camera receipt audio mode differs from the current audio receipt")
    expected_input = receipt.get("input_sha256")
    camera_profiles = {
        (HASHES["ordinary_game"], HASHES["ordinary_api"]): ("default-game-3124", HASHES["camera_default"]),
        (HASHES["composed_game"], HASHES["composed_api"]): ("post-audio-r4-1034-api-d540", HASHES["camera_after_audio"]),
        # Retain this exact legacy pair only so an existing R10 camera stage
        # can be unwound before audio replaces it. New camera selections still
        # require the current d540 profile above.
        (HASHES["composed_game"], HASHES["previous_composed_api_restore_only"]): (
            "post-audio-r4-1034",
            HASHES["camera_after_audio"],
        ),
        (HASHES["point_sound_composed_game"], HASHES["composed_api"]): ("post-audio-point-sound-6f96-api-d540", HASHES["camera_after_point_sound"]),
        (HASHES["point_sound_composed_game"], HASHES["pcm_composed_api"]): ("post-audio-r10-1ced-game-6f96", HASHES["camera_after_r10_1ced"]),
        (HASHES["music_observed_game"], HASHES["composed_api"]): ("post-audio-music-observer-6f96-api-d540", HASHES["music_camera_output"]),
        (HASHES["music_observed_game"], HASHES["pcm_composed_api"]): ("post-audio-music-observer-r10-1ced", HASHES["music_camera_output"]),
        (HASHES["native_result_observed_game"], HASHES["pcm_composed_api"]): (
            "post-audio-native-music-results-r23-1ced",
            HASHES["native_result_camera_output"],
        ),
        (HASHES["lightning_r3_native_result_observed_game"], HASHES["pcm_composed_api"]): (
            "post-audio-native-music-results-lightning-r3-1ced",
            HASHES["lightning_r3_native_result_camera_output"],
        ),
    }
    profile_entry = camera_profiles.get((expected_input, receipt.get("api_sha256")))
    if profile_entry is None:
        raise ValueError("camera receipt preimage is outside the exact owned camera profiles")
    expected_profile, expected_output = profile_entry
    expected_api = receipt.get("api_sha256")
    if receipt.get("input_sha256") != expected_input:
        raise ValueError("camera receipt does not name its exact owned preimage")
    predecessor_output = HASHES["camera_predecessor_f6bc_restore_only"]
    predecessor_profile = expected_input == HASHES["point_sound_composed_game"] and (
        (expected_api == HASHES["pcm_composed_api"] and expected_profile == "post-audio-r10-1ced-game-6f96")
        or (expected_api == HASHES["composed_api"] and expected_profile == "post-audio-point-sound-6f96-api-d540")
    )
    exact_prior_default = (
        expected_input == HASHES["ordinary_game"]
        and expected_api == HASHES["ordinary_api"]
        and expected_profile == "default-game-3124"
        and receipt.get("output_sha256")
        in {
            HASHES["camera_default_previous_restore_only"],
            "e237af4fea2b04dfecb54593e39d98862078a66de4a08272b75531303fe4b33d",
        }
    )
    exact_prior_1034 = (
        expected_input == HASHES["composed_game"]
        and expected_api in {HASHES["composed_api"], HASHES["previous_composed_api_restore_only"]}
        and expected_profile in {"post-audio-r4-1034-api-d540", "post-audio-r4-1034"}
        and receipt.get("output_sha256")
        in {
            HASHES["camera_after_audio_previous_restore_only"],
            "aa7ca07c363d6d2d144cc6d378264302846036661daa631b8a3a52dc9ed15ffc",
        }
    )
    exact_r14_broken_point_sound = (
        expected_input == HASHES["point_sound_composed_game"]
        and expected_api in {HASHES["composed_api"], HASHES["pcm_composed_api"]}
        and expected_profile in {"post-audio-point-sound-6f96-api-d540", "post-audio-r10-1ced-game-6f96"}
        and receipt.get("output_sha256") == HASHES["camera_after_point_sound_previous_restore_only"]
    )
    # Exact pre-delegate-bind images are restore-only. Bind the accepted old
    # output to the complete input/API/profile tuple, independently of the
    # current output hash which Root may advance after the new transform.
    prior_delegate_outputs = {
        (HASHES["ordinary_game"], HASHES["ordinary_api"], "default-game-3124"): {HASHES["camera_default_delegate_previous_restore_only"]},
        (HASHES["composed_game"], HASHES["composed_api"], "post-audio-r4-1034-api-d540"): {HASHES["camera_after_audio_delegate_previous_restore_only"]},
        (HASHES["point_sound_composed_game"], HASHES["composed_api"], "post-audio-point-sound-6f96-api-d540"): {
            HASHES["camera_after_point_sound_delegate_previous_restore_only"]
        },
        (HASHES["point_sound_composed_game"], HASHES["pcm_composed_api"], "post-audio-r10-1ced-game-6f96"): {
            HASHES["camera_after_point_sound_delegate_previous_restore_only"]
        },
        (HASHES["music_observed_game"], HASHES["composed_api"], "post-audio-music-observer-6f96-api-d540"): {
            HASHES["camera_music_observer_delegate_previous_restore_only"]
        },
        (HASHES["music_observed_game"], HASHES["pcm_composed_api"], "post-audio-music-observer-r10-1ced"): {
            HASHES["camera_music_observer_delegate_previous_restore_only"]
        },
    }
    exact_pre_delegate_output = receipt.get("output_sha256") in prior_delegate_outputs.get((expected_input, expected_api, expected_profile), set())
    is_restore_only_predecessor = (
        (predecessor_profile and receipt.get("output_sha256") == predecessor_output)
        or exact_prior_default
        or exact_prior_1034
        or exact_r14_broken_point_sound
        or exact_pre_delegate_output
    )
    if receipt.get("output_sha256") != expected_output and not is_restore_only_predecessor:
        raise ValueError("camera receipt output is outside the exact current or restore-only profile")
    if receipt.get("accepted") is not False or receipt.get("runtime_requested") is not False or receipt.get("runtime_dispatch_ready") is not False:
        raise ValueError("camera receipt claims runtime acceptance outside the current contract")
    game = project / GAME_RELATIVE
    api = project / API_RELATIVE
    _reject_symlinks(game)
    _reject_symlinks(api)
    if expected_input == HASHES["ordinary_game"]:
        expected_apis = {HASHES["ordinary_api"]}
    else:
        # R10's 793 artifact is accepted here solely to unwind its exact
        # already-staged e16 output before the current audio stager replaces it.
        # New R11 profile selection and transformation accept only current d540.
        expected_apis = {expected_api, HASHES["previous_composed_api_restore_only"]} if expected_input == HASHES["composed_game"] else {expected_api}
        if receipt.get("api_sha256") == HASHES["previous_composed_api_restore_only"]:
            if expected_input != HASHES["composed_game"] or audio.get("lineage", {}).get("composed_api_sha256") != HASHES["previous_composed_api_restore_only"]:
                raise ValueError("predecessor camera receipt is not bound to exact 793 audio lineage")
        elif expected_input in {HASHES["music_observed_game"], HASHES["native_result_observed_game"], HASHES["lightning_r3_native_result_observed_game"]}:
            _music_observer_receipt(project, audio_sha, audio)
            if audio.get("lineage", {}).get("composed_api_sha256") != expected_api or audio.get("lineage", {}).get("composed_game_sha256") != (
                HASHES["lightning_r3_point_sound_composed_game"]
                if expected_input == HASHES["lightning_r3_native_result_observed_game"]
                else HASHES["point_sound_composed_game"]
            ):
                raise ValueError("music-camera receipt is not bound to its exact PointSound audio lineage")
        elif audio.get("lineage", {}).get("composed_api_sha256") != expected_api or audio.get("lineage", {}).get("composed_game_sha256") != expected_input:
            raise ValueError("current camera receipt is not bound to exact d540 audio lineage")
    if receipt.get("api_sha256") not in expected_apis or sha256(api) != receipt.get("api_sha256"):
        raise ValueError("camera receipt API pair differs from its exact owned profile")
    if receipt.get("profile") != expected_profile and not (
        expected_input == HASHES["composed_game"]
        and receipt.get("profile") == "post-audio-r4-1034"
        and receipt.get("api_sha256") == HASHES["previous_composed_api_restore_only"]
    ):
        raise ValueError("camera receipt profile does not match its exact audio-owned preimage")
    if sha256(game) != receipt["output_sha256"]:
        raise ValueError("project RoR2.dll differs from the receipt-owned camera output")
    snapshot_rel = receipt.get("preimage_snapshot")
    if (
        not isinstance(snapshot_rel, str)
        or not snapshot_rel
        or "\\" in snapshot_rel
        or PurePosixPath(snapshot_rel).is_absolute()
        or ".." in PurePosixPath(snapshot_rel).parts
        or PurePosixPath(snapshot_rel).as_posix() != snapshot_rel
    ):
        raise ValueError("camera preimage snapshot path is not canonical relative work/ state")
    snapshot = work / snapshot_rel
    if not snapshot.is_file() or snapshot.is_symlink() or not snapshot.resolve(strict=True).is_relative_to(work):
        raise ValueError("camera preimage snapshot is missing or escapes work/")
    if sha256(snapshot) != expected_input:
        raise ValueError("camera preimage snapshot differs from the audio-owned source hash")
    _atomic_copy(snapshot, game, expected_input, replace_hash=receipt["output_sha256"])
    receipt_sha = hashlib.sha256(receipt_raw).hexdigest()
    receipt_path.unlink()
    return {"restored_sha256": expected_input, "camera_receipt_sha256": receipt_sha}


def _copy_file_clone(source: Path, target: Path) -> None:
    spec = importlib.util.spec_from_file_location("camera_artifact_copy", Path(__file__).with_name("common.py"))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.copy_file_clone(source, target)


def _atomic_copy(source: Path, target: Path, expected_hash: str, *, replace_hash: str | None = None) -> None:
    _reject_symlinks(source)
    _reject_symlinks(target, allow_missing=True)
    current = sha256(target) if target.is_file() else None
    if current not in (None, replace_hash, expected_hash):
        raise ValueError("staging target changed outside the owned preimage/output pair")
    with tempfile.NamedTemporaryFile(prefix=".native-view-camera-", dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
    _copy_file_clone(source, temporary)
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    if sha256(temporary) != expected_hash:
        temporary.unlink(missing_ok=True)
        raise ValueError("atomic camera copy hash verification failed")
    os.replace(temporary, target)


def _producer_module():
    path = CAMERA_SOURCE_ROOT / "scripts/lab/native_view_camera_transform.py"
    if not path.is_file():
        raise ValueError("camera transform producer is missing")
    spec = importlib.util.spec_from_file_location("r9_native_view_camera_transform", path)
    if spec is None or spec.loader is None:
        raise ValueError("camera transform producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_after_audio(project: Path, work: Path, audio_build_result: dict) -> dict:
    """Observe source output returns, then stage the camera guard after audio."""
    project, work = _canonical_project(project, work)
    initial = select_profile(project, audio_build_result, allow_music_observer_input=True)
    if initial.get("music_observer_source_only") or initial["profile"] == "post-audio-r10-1ced-game-6f96":
        from original_music_output_observer_build_hook import stage as stage_music_output_observer

        resolver_dir = ROOT / "work" / PurePosixPath(initial["resolver_set_directory"])
        stage_music_output_observer(project, work, resolver_dir, initial["profile"])
    selection = select_profile(project, audio_build_result)
    pins = json.loads(CAMERA_PINS.read_text(encoding="utf-8"))
    _verify_tracked_sources(pins)
    producer = _producer_module()
    resolution_dir = ROOT / "work" / PurePosixPath(selection["resolver_set_directory"])
    resolution_dir, resolver_receipt = producer.exact_resolution_closure(resolution_dir, pins, selection["profile"], project, producer.pinned_editor(pins)[0])
    producer.pinned_editor(pins)
    if not isinstance(selection.get("output_sha256"), str) or len(selection["output_sha256"]) != 64:
        raise ValueError("camera profile output hash is an unmeasured placeholder; staging is disabled")
    input_path = project / pins["profiles"][selection["profile"]]["input_relative_path"]
    if sha256(input_path) != selection["input_sha256"]:
        raise ValueError("profile source file does not match the staged audio-owned DLL")
    if sha256(project / GAME_RELATIVE) != selection["input_sha256"]:
        raise ValueError("project RoR2.dll changed after profile selection")
    generation = hashlib.sha256(
        json.dumps(
            {
                "profile": selection["profile"],
                "input": selection["input_sha256"],
                "audio_receipt": selection["audio_stage_receipt_sha256"],
                "resolver_inventory": selection["resolver_inventory_sha256"],
                "pins": hashlib.sha256(CAMERA_PINS.read_bytes()).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    output_root = project.parent / "native-view-camera" / generation
    output_root_existed = output_root.exists()
    if not output_root_existed:
        output_root.mkdir(parents=True)
    snapshot = output_root / "RoR2.preimage.dll"
    transformed = output_root / "RoR2.native-view-camera.dll"
    producer_receipt = transformed.with_name(transformed.name + ".producer-receipt.json")
    _reject_symlinks(output_root, allow_missing=True)
    if not output_root_existed:
        _copy_file_clone(input_path, snapshot)
        if sha256(snapshot) != selection["input_sha256"]:
            raise ValueError("immutable camera input snapshot failed hash verification")
        producer.transform(selection["profile"], input_path, resolution_dir, transformed, project)
    else:
        if not snapshot.is_file() or sha256(snapshot) != selection["input_sha256"]:
            raise ValueError("cached camera generation has no matching immutable input snapshot")
        if not transformed.is_file() or sha256(transformed) != selection["output_sha256"]:
            raise ValueError("cached camera generation output is missing or changed")
        if not producer_receipt.is_file():
            raise ValueError("cached camera generation lacks its producer receipt")
        cache_receipt = json.loads(producer_receipt.read_text(encoding="utf-8"))
        if (
            cache_receipt.get("profile") != selection["profile"]
            or cache_receipt.get("input_sha256") != selection["input_sha256"]
            or cache_receipt.get("output_sha256") != selection["output_sha256"]
            or cache_receipt.get("resolver_inventory_sha256") != selection["resolver_inventory_sha256"]
            or cache_receipt.get("resolver_dll_count") != selection["resolver_identity_count"]
            or cache_receipt.get("resolver_source_contract")
            != "current project plugin DLLs plus pinned Unity engine modules/Mono mscorlib; not a player linker closure"
            or cache_receipt.get("transformer_sha256") != pins["source_sha256"]["transformer"]
            or cache_receipt.get("verifier_sha256") != pins["source_sha256"]["verifier"]
            or cache_receipt.get("unity_tools_sha256") != pins["unity_tools_sha256"]
            or cache_receipt.get("resolver_effective_assembly_identity_count") != selection["resolver_identity_count"]
        ):
            raise ValueError("cached camera producer receipt differs from the exact profile")
    if sha256(project / GAME_RELATIVE) != selection["input_sha256"]:
        raise ValueError("project RoR2.dll changed before camera output staging")
    receipt_path = project / CAMERA_STAGE_RELATIVE
    _reject_symlinks(receipt_path, allow_missing=True)
    if receipt_path.exists():
        raise ValueError("camera receipt must be restored and cleared before the audio stage")
    _atomic_copy(transformed, project / GAME_RELATIVE, selection["output_sha256"], replace_hash=selection["input_sha256"])
    stage_receipt = {
        "schema": STAGE_SCHEMA,
        "profile": selection["profile"],
        "input_sha256": selection["input_sha256"],
        "output_sha256": selection["output_sha256"],
        "audio_stage_receipt_sha256": selection["audio_stage_receipt_sha256"],
        "audio_requested": selection["audio_requested"],
        "api_sha256": selection["api_sha256"],
        "resolver_inventory_sha256": selection["resolver_inventory_sha256"],
        "resolver_effective_assembly_identity_count": selection["resolver_identity_count"],
        "preimage_snapshot": snapshot.relative_to(work).as_posix(),
        "producer_receipt_sha256": sha256(producer_receipt),
        "runtime_requested": False,
        "runtime_dispatch_ready": False,
        "accepted": False,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(prefix=".native-view-camera-receipt-", dir=receipt_path.parent, delete=False, mode="w", encoding="utf-8") as stream:
            temporary = Path(stream.name)
            json.dump(stage_receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, receipt_path)
    except Exception:
        _atomic_copy(snapshot, project / GAME_RELATIVE, selection["input_sha256"], replace_hash=selection["output_sha256"])
        raise
    if sha256(project / GAME_RELATIVE) != selection["output_sha256"]:
        raise ValueError("staged camera output differs after atomic replacement")
    return stage_receipt


__all__ = ["restore_previous_camera", "select_profile", "stage_after_audio"]
