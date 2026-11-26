#!/usr/bin/env python3
"""Emit the original-game stage pin from explicit, receipt-bound inputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[5]
WORK = (ROOT / "work").resolve()
STAGER = Path(__file__).resolve().parent / "stage_original_game_banks.py"
STAGER_SHA256 = "11e730f34f019566186c3d8f1c3461752a87f5416ce3b0f0be6d5da001850fe6"
INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
PREFAB_SHA256 = "7f074267744a3f7652349572f4aa88f48cd3d43328ba629f686288f08c4be6af"
BANK_INDEX_SHA256 = "f1d41954cb78c582a6c8a5fbbca58148057a120b01e4bb09cd47f8f107d66326"
OWNER_BANK_INDEX_SHA256 = "063944216e330019b171e8d654b3f0c53ca33289888a2615100abc9e27fa2b76"
INIT_SHA256 = "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90"
INIT_RECEIPT_SHA256 = "3b274de411fe2128bffd43de117baf9156e58e75ebcd0f0cb2a5379b1f22260f"
GLOBAL_SHA256 = "37756450a0a08a0e3d79ed42926c4de062f67c01dbfef590db1c4af1130485e4"
SOUNDBANKS_INFO_SHA256 = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407"
STREAMED_MEDIA_COUNT = 120
HASH = re.compile(r"^[0-9a-f]{64}$")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_work_file(path: Path, label: str, work: Path) -> Path:
    lexical = path.absolute()
    resolved = lexical.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(work):
        raise ValueError(f"{label} must be a regular file under work/")
    try:
        relative = lexical.relative_to(work)
    except ValueError as error:
        raise ValueError(f"{label} must be a work-relative path") from error
    cursor = work
    for part in relative.parts:
        cursor /= part
        if stat.S_ISLNK(cursor.lstat().st_mode):
            raise ValueError(f"{label} cannot traverse symlinks")
    return resolved


def streamed_media_rows(
    receipt: dict,
    *,
    accepted_inventory_sha256: str | None = None,
    bank_index_sha256: str | None = None,
    init_receipt_sha256: str | None = None,
) -> list[dict]:
    validator_path = ROOT / "scripts/lab/original_game_audio_stage.py"
    spec = importlib.util.spec_from_file_location("original_audio_stage_validator", validator_path)
    if spec is None or spec.loader is None:
        raise ValueError("shared streamed-media receipt validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = getattr(module, "validate_streamed_media_rows", None)
    if not callable(validator):
        raise ValueError("shared streamed-media receipt validator unavailable")
    rows = validator(receipt, accepted_inventory_sha256=accepted_inventory_sha256, bank_index_sha256=bank_index_sha256, init_receipt_sha256=init_receipt_sha256)
    if not isinstance(rows, list) or len(rows) != STREAMED_MEDIA_COUNT:
        raise ValueError("R2 receipt must validate exactly 120 streamed media rows")
    return rows


def checked_staged_file(path: Path, label: str, work: Path) -> Path:
    lexical = path.absolute()
    try:
        relative = lexical.relative_to(work)
    except ValueError as error:
        raise ValueError(f"{label} must remain under work/") from error
    cursor = work
    for part in relative.parts:
        cursor /= part
        try:
            if stat.S_ISLNK(cursor.lstat().st_mode):
                raise ValueError(f"{label} cannot traverse symlinks")
        except FileNotFoundError as error:
            raise ValueError(f"{label} is missing") from error
    info = lexical.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular file")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_relative_to(work):
        raise ValueError(f"{label} must resolve under work/")
    return resolved


def source_plan(
    prefab: Path, bank_index: Path, adapted_init: Path, init_receipt: Path, *, owner_work: Path | None = None, startup_only: bool
) -> tuple[list[dict], list[str]]:
    if sha_file(STAGER) != STAGER_SHA256:
        raise ValueError("pinned explicit-input stage producer changed")
    spec = importlib.util.spec_from_file_location("root_bank_stage", STAGER)
    if spec is None or spec.loader is None:
        raise ValueError("explicit-input bank stage producer unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index_sha = BANK_INDEX_SHA256 if owner_work is None else OWNER_BANK_INDEX_SHA256
    if sha_file(prefab) != PREFAB_SHA256 or sha_file(bank_index) != index_sha:
        raise ValueError("current accepted prefab/bank index pins differ")
    _, _, plan, _ = module.load_inputs(prefab, bank_index, adapted_init, init_receipt, owner_work=owner_work, startup_only=startup_only)
    return plan, module.extract_names(prefab.read_text(encoding="utf-8"))


def generate(
    receipt_path: Path,
    stage_root: Path,
    output: Path,
    prefab: Path,
    bank_index: Path,
    adapted_init: Path,
    init_receipt: Path,
    *,
    owner_work: Path | None = None,
) -> dict:
    work = WORK if owner_work is None else owner_work
    if work != work.resolve(strict=True):
        raise ValueError("owner work root must be canonical")
    receipt_path = checked_work_file(receipt_path, "stage receipt", work)
    prefab = checked_work_file(prefab, "WwiseGlobal prefab", work)
    bank_index = checked_work_file(bank_index, "accepted bank index", work)
    adapted_init = checked_work_file(adapted_init, "adapted Init candidate", work)
    init_receipt = checked_work_file(init_receipt, "Init adaptation receipt", work)
    stage_root = stage_root.absolute()
    if not stage_root.resolve(strict=True).is_relative_to(work):
        raise ValueError("stage root must be under work/")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "original-game-wwise-bank-cohort-r2"
        or receipt.get("accepted_input_id") != INPUT_ID
        or receipt.get("soundbanks_info_sha256") != SOUNDBANKS_INFO_SHA256
        or receipt.get("requested_banks") != 153
        or receipt.get("runtime_private_copy_required") is not True
        or receipt.get("runtime_copy_complete") is not False
        or receipt.get("runtime_bank_ready") is not False
        or receipt.get("output_relative_directory") != "Audio/GeneratedSoundBanks/Android"
    ):
        raise ValueError("stage receipt does not match current default-unaccepted contract")
    inventory_sha = sha_file(work / "inventory/files.json")
    if receipt.get("accepted_inventory_sha256") != inventory_sha:
        raise ValueError("stage receipt does not bind current full accepted inventory")
    outputs = receipt.get("outputs")
    if not isinstance(outputs, list) or len(outputs) < 154:
        raise ValueError("stage receipt must contain at least 153 startup banks plus Init")
    plan, names = source_plan(prefab, bank_index, adapted_init, init_receipt, owner_work=owner_work, startup_only=len(outputs) == 154)
    init_receipt_sha = INIT_RECEIPT_SHA256 if owner_work is None else sha_file(init_receipt)
    index_sha = BANK_INDEX_SHA256 if owner_work is None else OWNER_BANK_INDEX_SHA256
    for key, expected in {
        "current_bank_index_sha256": index_sha,
        "wwise_global_prefab_sha256": PREFAB_SHA256,
        "init_adaptation_receipt_sha256": init_receipt_sha,
        "init_adaptation_candidate_sha256": INIT_SHA256,
        "global_accepted_original_sha256": GLOBAL_SHA256,
    }.items():
        if receipt.get(key) != expected:
            raise ValueError(f"stage receipt source pin mismatch: {key}")
    if owner_work is None:
        media_rows = streamed_media_rows(receipt)
    else:
        media_rows = streamed_media_rows(receipt, accepted_inventory_sha256=inventory_sha, bank_index_sha256=index_sha, init_receipt_sha256=init_receipt_sha)
    expected = {row["output_filename"]: row for row in plan}
    expected["Init.bnk"] = {"source_sha256": INIT_SHA256, "size_bytes": adapted_init.stat().st_size}
    seen: set[str] = set()
    for row in outputs:
        if not isinstance(row, dict):
            raise ValueError("invalid stage output row")
        name = row.get("filename")
        if name not in expected or name in seen:
            raise ValueError("unexpected or duplicate staged filename")
        seen.add(name)
        expected_row = expected[name]
        if row.get("sha256") != expected_row["source_sha256"] or row.get("size_bytes") != expected_row["size_bytes"]:
            raise ValueError(f"stage receipt output differs from accepted source row: {name}")
        if name != "Init.bnk":
            requested = row.get("requested_name")
            if requested != expected_row["requested_name"] or name != requested + ".bnk":
                raise ValueError(f"stage filename/name mapping differs: {name}")
        output_path = stage_root / receipt["output_relative_directory"] / name
        output_path = checked_staged_file(output_path, f"staged output {name}", work)
        if output_path.stat().st_size != row["size_bytes"] or sha_file(output_path) != row["sha256"]:
            raise ValueError(f"staged output bytes do not match receipt: {name}")
    if seen != set(expected):
        raise ValueError("stage receipt does not bind the exact current cohort")
    media_dir = stage_root / receipt["output_relative_directory"]
    for row in media_rows:
        media_path = checked_staged_file(media_dir / row["relative_path"], f"staged media {row['media_id']}", work)
        if media_path.stat().st_size != row["size_bytes"] or sha_file(media_path) != row["sha256"]:
            raise ValueError(f"staged streamed media bytes do not match receipt: {row['media_id']}")
    absolute = output.absolute()
    if not absolute.resolve(strict=False).is_relative_to(work) or absolute.exists():
        raise ValueError("generated source must be a new file under work/")
    values = ",\n        ".join(json.dumps(name, ensure_ascii=True) for name in sorted(names))
    source = (
        "// Generated by generate_runtime_stage_pin.py from explicit current input and receipt paths.\n"
        "internal static class GameAudioOriginalGeneratedStagePin\n{\n"
        f'    internal const string ReceiptSha256 = "{sha_file(receipt_path)}";\n'
        f'    internal const string AcceptedInputId = "{INPUT_ID}";\n'
        "    internal static readonly string[] BankNames = new string[]\n    {\n        " + values + "\n    };\n}\n"
    )
    absolute.parent.mkdir(parents=True, exist_ok=True)
    with absolute.open("x", encoding="utf-8") as stream:
        stream.write(source)
    return {
        "receipt_sha256": sha_file(receipt_path),
        "source_sha256": sha_file(absolute),
        "output": str(Path("work") / absolute.relative_to(work)),
        "bank_count": len(names),
        "streamed_media_count": len(media_rows),
        "soundbanks_info_sha256": SOUNDBANKS_INFO_SHA256,
        "init_sha256": INIT_SHA256,
        "global_sha256": GLOBAL_SHA256,
        "runtime_copy_complete": False,
        "runtime_bank_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefab", type=Path, required=True)
    parser.add_argument("--bank-index", type=Path, required=True)
    parser.add_argument("--adapted-init", type=Path, required=True)
    parser.add_argument("--init-receipt", type=Path, required=True)
    parser.add_argument("--owner-work", type=Path, help="explicit admitted owner work root and decoder-free index")
    args = parser.parse_args()
    print(
        json.dumps(
            generate(
                args.receipt, args.stage_root, args.output, args.prefab, args.bank_index, args.adapted_init, args.init_receipt, owner_work=args.owner_work
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
