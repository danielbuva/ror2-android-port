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
STAGER_SHA256 = "38298a82431e8b58a05298e64b6f93f3fdf24c3d7ce2bbfaba1e011b3e5bf5e2"
INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
PREFAB_SHA256 = "7f074267744a3f7652349572f4aa88f48cd3d43328ba629f686288f08c4be6af"
BANK_INDEX_SHA256 = "f1d41954cb78c582a6c8a5fbbca58148057a120b01e4bb09cd47f8f107d66326"
INIT_SHA256 = "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90"
INIT_RECEIPT_SHA256 = "3b274de411fe2128bffd43de117baf9156e58e75ebcd0f0cb2a5379b1f22260f"
GLOBAL_SHA256 = "37756450a0a08a0e3d79ed42926c4de062f67c01dbfef590db1c4af1130485e4"
HASH = re.compile(r"^[0-9a-f]{64}$")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_work_file(path: Path, label: str) -> Path:
    lexical = path.absolute()
    resolved = lexical.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(WORK):
        raise ValueError(f"{label} must be a regular file under work/")
    try:
        relative = lexical.relative_to(WORK)
    except ValueError as error:
        raise ValueError(f"{label} must be a work-relative path") from error
    cursor = WORK
    for part in relative.parts:
        cursor /= part
        if stat.S_ISLNK(cursor.lstat().st_mode):
            raise ValueError(f"{label} cannot traverse symlinks")
    return resolved


def source_plan(prefab: Path, bank_index: Path, adapted_init: Path, init_receipt: Path) -> list[dict]:
    if sha_file(STAGER) != STAGER_SHA256:
        raise ValueError("pinned explicit-input stage producer changed")
    spec = importlib.util.spec_from_file_location("root_bank_stage", STAGER)
    if spec is None or spec.loader is None:
        raise ValueError("explicit-input bank stage producer unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sha_file(prefab) != PREFAB_SHA256 or sha_file(bank_index) != BANK_INDEX_SHA256:
        raise ValueError("current accepted prefab/bank index pins differ")
    if sha_file(adapted_init) != INIT_SHA256 or sha_file(init_receipt) != INIT_RECEIPT_SHA256:
        raise ValueError("explicit adapted Init candidate/receipt pins differ")
    _, _, plan, _ = module.load_inputs(prefab, bank_index, adapted_init, init_receipt)
    return plan


def generate(receipt_path: Path, stage_root: Path, output: Path, prefab: Path, bank_index: Path, adapted_init: Path, init_receipt: Path) -> dict:
    receipt_path = checked_work_file(receipt_path, "stage receipt")
    prefab = checked_work_file(prefab, "WwiseGlobal prefab")
    bank_index = checked_work_file(bank_index, "accepted bank index")
    adapted_init = checked_work_file(adapted_init, "adapted Init candidate")
    init_receipt = checked_work_file(init_receipt, "Init adaptation receipt")
    stage_root = stage_root.absolute()
    if not stage_root.resolve(strict=True).is_relative_to(WORK):
        raise ValueError("stage root must be under work/")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "original-game-wwise-bank-cohort-r1"
        or receipt.get("accepted_input_id") != INPUT_ID
        or receipt.get("requested_banks") != 153
        or receipt.get("runtime_private_copy_required") is not True
        or receipt.get("runtime_copy_complete") is not False
        or receipt.get("runtime_bank_ready") is not False
        or receipt.get("output_relative_directory") != "Audio/GeneratedSoundBanks/Android"
    ):
        raise ValueError("stage receipt does not match current default-unaccepted contract")
    if receipt.get("accepted_inventory_sha256") != sha_file(WORK / "inventory/files.json"):
        raise ValueError("stage receipt does not bind current full accepted inventory")
    for key, expected in {
        "current_bank_index_sha256": BANK_INDEX_SHA256,
        "wwise_global_prefab_sha256": PREFAB_SHA256,
        "init_adaptation_receipt_sha256": INIT_RECEIPT_SHA256,
        "init_adaptation_candidate_sha256": INIT_SHA256,
        "global_accepted_original_sha256": GLOBAL_SHA256,
    }.items():
        if receipt.get(key) != expected:
            raise ValueError(f"stage receipt source pin mismatch: {key}")
    plan = source_plan(prefab, bank_index, adapted_init, init_receipt)
    expected = {row["output_filename"]: row for row in plan}
    expected["Init.bnk"] = {"source_sha256": INIT_SHA256, "size_bytes": adapted_init.stat().st_size}
    outputs = receipt.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 154:
        raise ValueError("stage receipt must contain 153 banks plus Init")
    names: list[str] = []
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
            names.append(requested)
        output_path = stage_root / receipt["output_relative_directory"] / name
        if not output_path.is_file() or output_path.is_symlink() or output_path.stat().st_size != row["size_bytes"] or sha_file(output_path) != row["sha256"]:
            raise ValueError(f"staged output bytes do not match receipt: {name}")
    if seen != set(expected) or len(names) != 153 or len(set(names)) != 153:
        raise ValueError("stage receipt does not bind the exact current cohort")
    absolute = output.absolute()
    if not absolute.resolve(strict=False).is_relative_to(WORK) or absolute.exists():
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
        "output": str(absolute.relative_to(ROOT)),
        "bank_count": len(names),
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
    args = parser.parse_args()
    print(json.dumps(generate(args.receipt, args.stage_root, args.output, args.prefab, args.bank_index, args.adapted_init, args.init_receipt), sort_keys=True))


if __name__ == "__main__":
    main()
