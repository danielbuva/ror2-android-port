#!/usr/bin/env python3
"""Emit opt-in C# constants from a request, exact build manifest and stage receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[5]
WORK = (ROOT / "work").resolve()
EXPECTED = {
    "accepted_input_id": "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88",
    "adapted_init_sha256": "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90",
    "game_assembly_sha256": "a5f7d83c7e6872fdd6099fdc299adb7d4fa03cbf465e526d6f5efcc35c2c281d",
    "composed_game_sha256": "594282cfa617ac58eda6965e0a48e6958438f345cbb98bfb7cb49b9130efad1d",
    "raw_api_sha256": "564b74ec232e81af8fa4b65c17537a4d05890d9181281eab0bc28bd441a3a781",
    "adapted_api_sha256": "2bd973178c99bfcb4d20510e2d1eac7efa9dd6d698237f2edfa486171bc2f272",
    "observed_api_sha256": "a2914ace8e2a7338010f8e9a9515911d68489bf0ad467bc7f73f4de293a19fe9",
    "instrumented_api_sha256": "1cedc89f59f44f91deea8b07fcdf289e5fec9448ba87d4d68519d6658bba942b",
    "native_library_sha256": "9075b5a4d3718a209eb244760d2b251a59ef2f5c486a2d2fc0e83b90240cbba3",
    "current_bank_index_sha256": "f1d41954cb78c582a6c8a5fbbca58148057a120b01e4bb09cd47f8f107d66326",
    "wwise_global_prefab_sha256": "7f074267744a3f7652349572f4aa88f48cd3d43328ba629f686288f08c4be6af",
    "init_adaptation_receipt_sha256": "3b274de411fe2128bffd43de117baf9156e58e75ebcd0f0cb2a5379b1f22260f",
    "global_accepted_original_sha256": "37756450a0a08a0e3d79ed42926c4de062f67c01dbfef590db1c4af1130485e4",
}
SOUNDBANKS_INFO_SHA256 = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CONTRACT_SCHEMA = "game-audio-original-build-input-contract-r1"
REQUEST_SCHEMA = "game-audio-original-runtime-request-r3"
CONTRACT_ROLES = {
    "game_assembly_sha256",
    "composed_game_sha256",
    "raw_api_sha256",
    "adapted_api_sha256",
    "observed_api_sha256",
    "instrumented_api_sha256",
    "native_library_sha256",
    "current_bank_index_sha256",
    "wwise_global_prefab_sha256",
    "init_adaptation_receipt_sha256",
    "global_accepted_original_sha256",
    "adapted_init_sha256",
}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_work_file(path: Path, label: str) -> Path:
    lexical = path.absolute()
    try:
        resolved = lexical.resolve(strict=True)
        relative = lexical.relative_to(WORK)
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} must be an existing file under work/") from error
    if not resolved.is_relative_to(WORK) or not resolved.is_file():
        raise ValueError(f"{label} must be a regular file under work/")
    cursor = WORK
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"{label} cannot traverse symlinks")
    return resolved


def validate_input_contract(path: Path) -> str:
    path = checked_work_file(path, "build input contract")
    raw = path.read_bytes()
    contract = json.loads(raw)
    if (
        not isinstance(contract, dict)
        or set(contract) != {"schema", "accepted_input_id", "inputs"}
        or contract.get("schema") != CONTRACT_SCHEMA
        or contract.get("accepted_input_id") != EXPECTED["accepted_input_id"]
        or not isinstance(contract.get("inputs"), list)
    ):
        raise ValueError("build input contract schema or accepted input ID mismatch")
    actual: dict[str, str] = {}
    for row in contract["inputs"]:
        if not isinstance(row, dict) or set(row) != {"role", "path", "sha256"}:
            raise ValueError("build input contract row must contain role, path and sha256")
        role, relative, declared = row["role"], row["path"], row["sha256"]
        if not isinstance(role, str) or not isinstance(declared, str):
            raise ValueError("build input contract role and sha256 must be strings")
        if role not in CONTRACT_ROLES or role in actual:
            raise ValueError("build input contract has an unknown or duplicate role")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("build input contract paths must be work-relative files")
        parts = Path(relative).parts
        if any(part in ("", ".", "..") for part in parts):
            raise ValueError("build input contract path is not canonical")
        candidate = checked_work_file(WORK / relative, "build input contract member")
        actual_sha = sha_file(candidate)
        if not HASH_RE.fullmatch(str(declared)) or declared != actual_sha:
            raise ValueError(f"build input contract member hash mismatch: {role}")
        if EXPECTED.get(role) != actual_sha:
            raise ValueError(f"build input contract accepted pin mismatch: {role}")
        actual[role] = actual_sha
    if set(actual) != CONTRACT_ROLES:
        raise ValueError("build input contract does not contain the exact accepted role set")
    return hashlib.sha256(raw).hexdigest()


def streamed_media_rows(receipt: dict) -> list[dict]:
    validator_path = ROOT / "scripts/lab/original_game_audio_stage.py"
    spec = importlib.util.spec_from_file_location("original_audio_stage_validator", validator_path)
    if spec is None or spec.loader is None:
        raise ValueError("shared streamed-media receipt validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, "validate_streamed_media_rows", None)
    if not callable(validator):
        raise ValueError("shared streamed-media receipt validator unavailable")
    rows = validator(receipt)
    if not isinstance(rows, list) or len(rows) != 120:
        raise ValueError("R2 receipt must validate exactly 120 streamed media rows")
    return rows


def validate(request_path: Path, manifest_path: Path, stage_path: Path) -> dict:
    request_path = checked_work_file(request_path, "opt-in request")
    stage_path = checked_work_file(stage_path, "stage receipt")
    raw = request_path.read_bytes()
    request = json.loads(raw)
    if (
        not isinstance(request, dict)
        or request.get("schema") != REQUEST_SCHEMA
        or request.get("requested") is not True
        or type(request.get("passive_pcm_capture_requested")) is not bool
        or type(request.get("passive_pcm_capture_music_output_requested", False)) is not bool
    ):
        raise ValueError("explicit opted-in runtime request schema/flag required")
    if request.get("passive_pcm_capture_music_output_requested", False) and not request["passive_pcm_capture_requested"]:
        raise ValueError("specific-output capture requires passive PCM capture to be explicitly requested")
    request_id = request.get("request_id")
    try:
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
            raise ValueError("request_id must use compact lowercase N form")
        uuid.UUID(hex=request_id)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("request_id must be a UUID in compact hex form") from error
    if len(request_id) != 32:
        raise ValueError("request_id must use compact N form")
    contract_sha = validate_input_contract(manifest_path)
    if request.get("build_input_contract_sha256") != contract_sha:
        raise ValueError("request does not bind the exact build input contract")
    stage_raw = stage_path.read_bytes()
    stage = json.loads(stage_raw)
    if not isinstance(stage, dict):
        raise ValueError("stage receipt must be a JSON object")
    stage_sha = hashlib.sha256(stage_raw).hexdigest()
    if request.get("stage_receipt_sha256") != stage_sha:
        raise ValueError("request does not bind exact generated stage receipt")
    if request.get("adapted_init_sha256") != EXPECTED["adapted_init_sha256"]:
        raise ValueError("adapted Init hash is not the accepted adaptation")
    for field, value in EXPECTED.items():
        if request.get(field) != value:
            raise ValueError(f"accepted source pin mismatch: {field}")
    if (
        stage.get("schema") != "original-game-wwise-bank-cohort-r2"
        or stage.get("accepted_input_id") != EXPECTED["accepted_input_id"]
        or stage.get("soundbanks_info_sha256") != SOUNDBANKS_INFO_SHA256
        or stage.get("requested_banks") != 153
        or stage.get("runtime_private_copy_required") is not True
        or stage.get("output_relative_directory") != "Audio/GeneratedSoundBanks/Android"
        or stage.get("runtime_copy_complete") is not False
        or stage.get("runtime_bank_ready") is not False
    ):
        raise ValueError("stage receipt is outside the accepted 153-bank runtime contract")
    inventory_path = WORK / "inventory/files.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if (
        inventory.get("input_id") != EXPECTED["accepted_input_id"]
        or inventory.get("hash_mode") != "full"
        or stage.get("accepted_inventory_sha256") != sha_file(inventory_path)
    ):
        raise ValueError("stage receipt does not bind the current full accepted inventory")
    for key in (
        "current_bank_index_sha256",
        "wwise_global_prefab_sha256",
        "init_adaptation_receipt_sha256",
        "init_adaptation_candidate_sha256",
        "global_accepted_original_sha256",
    ):
        expected = EXPECTED["adapted_init_sha256"] if key == "init_adaptation_candidate_sha256" else EXPECTED.get(key)
        if stage.get(key) != expected:
            raise ValueError(f"stage receipt source pin mismatch: {key}")
    outputs = stage.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 154:
        raise ValueError("stage receipt must contain exactly 153 banks and Init")
    names: set[str] = set()
    filenames: set[str] = set()
    found_init = False
    for row in outputs:
        if not isinstance(row, dict):
            raise ValueError("stage receipt row must be an object")
        filename = row.get("filename")
        if not isinstance(filename, str) or not filename or filename in filenames or any(c in filename for c in "/\\:"):
            raise ValueError("unsafe or duplicate stage filename")
        filenames.add(filename)
        if not HASH_RE.fullmatch(str(row.get("sha256", ""))) or not isinstance(row.get("size_bytes"), int) or row["size_bytes"] <= 0:
            raise ValueError("stage output lacks a valid hash/size")
        if filename == "Init.bnk":
            found_init = True
            if row["sha256"] != EXPECTED["adapted_init_sha256"]:
                raise ValueError("staged Init differs from accepted adapted Init")
            continue
        name = row.get("requested_name")
        if not isinstance(name, str) or not name or filename != name + ".bnk" or name in names:
            raise ValueError("unsafe or duplicate serialized bank name")
        names.add(name)
    if not found_init or len(names) != 153:
        raise ValueError("stage receipt must bind the exact 153-name set plus Init")
    media_rows = streamed_media_rows(stage)
    if len(media_rows) != 120:
        raise ValueError("stage receipt must validate exactly 120 streamed media rows")
    if any(not set(row["referenced_by"]).issubset(names) for row in media_rows):
        raise ValueError("streamed media references do not match the exact staged bank names")
    return {
        "request": request,
        "request_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "build_input_contract_sha256": contract_sha,
        "stage_receipt_sha256": stage_sha,
        "streamed_media_count": len(media_rows),
        "soundbanks_info_sha256": SOUNDBANKS_INFO_SHA256,
    }


def emit(request_path: Path, manifest_path: Path, stage_path: Path, output: Path) -> dict:
    if not output.absolute().resolve(strict=False).is_relative_to(WORK):
        raise ValueError("generated source output must remain under ignored work/")
    if output.exists():
        raise ValueError("generated source output must be a new file")
    result = validate(request_path, manifest_path, stage_path)
    request = result["request"]
    fields = {
        "Requested": "true",
        "PassivePcmCaptureRequested": "true" if request["passive_pcm_capture_requested"] else "false",
        "PassivePcmCaptureMusicOutputRequested": "true" if request.get("passive_pcm_capture_music_output_requested", False) else "false",
        "RequestId": request["request_id"].lower(),
        "RequestReceiptSha256": result["request_receipt_sha256"],
        "BuildInputContractSha256": result["build_input_contract_sha256"],
        "StageReceiptSha256": result["stage_receipt_sha256"],
        "AdaptedInitSha256": request["adapted_init_sha256"],
        "GameAssemblySha256": request["game_assembly_sha256"],
        "ComposedGameSha256": request["composed_game_sha256"],
        "RawApiSha256": request["raw_api_sha256"],
        "AdaptedApiSha256": request["adapted_api_sha256"],
        "ObservedApiSha256": request["observed_api_sha256"],
        "InstrumentedApiSha256": request["instrumented_api_sha256"],
        "NativeLibrarySha256": request["native_library_sha256"],
    }
    source = (
        "// Generated by generate_accepted_request_pin.py; opt-in exists only for this exact request.\n"
        "internal static class GameAudioOriginalGeneratedRequestPin\n{\n"
        + "\n".join(
            f"    internal const {'bool' if key in {'Requested', 'PassivePcmCaptureRequested', 'PassivePcmCaptureMusicOutputRequested'} else 'string'} {key} = {value if key in {'Requested', 'PassivePcmCaptureRequested', 'PassivePcmCaptureMusicOutputRequested'} else json.dumps(value)};"
            for key, value in fields.items()
        )
        + "\n}\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    return {
        "output": str(output.relative_to(ROOT)),
        "source_sha256": sha_file(output),
        **{k: v for k, v in result.items() if k != "request"},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("build_manifest", type=Path)
    parser.add_argument("stage_receipt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            emit(args.request, args.build_manifest, args.stage_receipt, args.output),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
