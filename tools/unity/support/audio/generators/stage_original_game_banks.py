#!/usr/bin/env python3
"""Generate a hash-bound Android StreamingAssets cohort for the original Wwise loaders.

All source files are read from the configured accepted Steam installation. Outputs,
when requested, must be a new directory below ignored work/. This tool stages bytes
only; it does not copy to the app-private runtime root or establish native loading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[5]
WORK = ROOT / "work"
ACCEPTED_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
PREFAB_SHA = "7f074267744a3f7652349572f4aa88f48cd3d43328ba629f686288f08c4be6af"
BANK_INDEX_SHA = "f1d41954cb78c582a6c8a5fbbca58148057a120b01e4bb09cd47f8f107d66326"
INIT_SHA = "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90"
INIT_SOURCE_SHA = "3182093b59cf48034b2715b224f3f217b34eaecf104d10940528ea20c4baffc6"
INIT_RECEIPT_SHA = "3b274de411fe2128bffd43de117baf9156e58e75ebcd0f0cb2a5379b1f22260f"
GLOBAL_SHA = "37756450a0a08a0e3d79ed42926c4de062f67c01dbfef590db1c4af1130485e4"
GLOBAL_SIZE = 95239411
BANK_ROOT = Path("Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows")
OUTPUT_RELATIVE = Path("Audio/GeneratedSoundBanks/Android")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def reject_symlink_components(path: Path) -> None:
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        try:
            if stat.S_ISLNK(cursor.lstat().st_mode):
                raise ValueError("symlink path component refused")
        except FileNotFoundError:
            pass


def extract_names(prefab: str) -> list[str]:
    docs = re.split(r"(?m)^--- !u!\d+ &[^\n]+\n", prefab)[1:]
    names: list[str] = []
    for doc in docs:
        if "guid: 951ce57ad999ac1f040a4dceb5f8b763" not in doc:
            continue
        match = re.search(r"(?ms)^  soundbankStrings:\n(.*?)(?=^  decodeBank:)", doc)
        if match:
            names.extend(re.findall(r"^  - (.*)$", match.group(1), re.M))
    if len(names) != 153 or len(set(names)) != 153 or any(not n or "/" in n or "\\" in n for n in names):
        raise ValueError("current WwiseGlobal must contain exactly 153 unique safe bank names")
    return names


def load_inputs(prefab_path: Path, bank_index_path: Path, init_path: Path, init_receipt_path: Path) -> tuple[Path, dict, list[dict], dict]:
    accepted = json.loads((WORK / "config/accepted-input.json").read_text())
    inventory = json.loads((WORK / "inventory/files.json").read_text())
    local = json.loads((WORK / "config/local.json").read_text())
    game_root = Path(local["game_path"]).expanduser().resolve(strict=True)
    if accepted.get("input_id") != ACCEPTED_ID or inventory.get("input_id") != ACCEPTED_ID or inventory.get("hash_mode") != "full":
        raise ValueError("accepted identity/full inventory mismatch")
    if sha_file(prefab_path) != PREFAB_SHA:
        raise ValueError("WwiseGlobal prefab pin mismatch")
    bank_index = json.loads(bank_index_path.read_text())
    if sha_file(bank_index_path) != BANK_INDEX_SHA or bank_index.get("input_id") != ACCEPTED_ID:
        raise ValueError("current accepted bank-index receipt mismatch")
    adaptation = json.loads(init_receipt_path.read_text())
    if (
        sha_file(init_receipt_path) != INIT_RECEIPT_SHA
        or adaptation.get("input_sha256") != INIT_SOURCE_SHA
        or adaptation.get("output_sha256") != INIT_SHA
        or adaptation.get("transform_sha256") != "91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37"
    ):
        raise ValueError("explicit Init adaptation receipt mismatch")
    if sha_file(init_path) != INIT_SHA:
        raise ValueError("adapted Init candidate hash mismatch")
    prefab = prefab_path.read_text(encoding="utf-8")
    names = extract_names(prefab)
    inventory_by_path: dict[str, dict] = {}
    for row in inventory.get("files", []):
        inventory_by_path[row.get("path", "")] = row
    index_rows = bank_index.get("banks")
    if not isinstance(index_rows, list):
        raise ValueError("bank index has no bank rows")
    indexed: dict[str, list[dict]] = {}
    for row in index_rows:
        path = row.get("path")
        if not isinstance(path, str) or Path(path).name != path or Path(path).suffix.lower() != ".bnk":
            raise ValueError("bank index contains an unsafe/non-leaf bank path")
        indexed.setdefault(Path(path).stem.casefold(), []).append(row)
    plans = []
    for name in names:
        matches = indexed.get(name.casefold(), [])
        if len(matches) != 1:
            raise ValueError(f"serialized bank does not map uniquely to accepted bank index: {name}")
        row = matches[0]
        relative = (BANK_ROOT / row["path"]).as_posix()
        inventory_row = inventory_by_path.get(relative)
        if inventory_row is None or inventory_row.get("sha256") != row.get("sha256") or inventory_row.get("size") != row.get("bytes"):
            raise ValueError(f"full accepted inventory does not bind bank: {name}")
        source = game_root / relative
        if not source.is_file() or source.is_symlink() or source.stat().st_size != row["bytes"] or sha_file(source) != row["sha256"]:
            raise ValueError(f"configured accepted bank bytes changed: {name}")
        plans.append(
            {
                "requested_name": name,
                "source_relative_path": relative,
                "source_sha256": row["sha256"],
                "size_bytes": row["bytes"],
                "output_filename": name + ".bnk",
                "case_renamed": Path(row["path"]).name != name + ".bnk",
            }
        )
    global_rows = [p for p in plans if p["requested_name"] == "Global"]
    if len(global_rows) != 1 or global_rows[0]["source_sha256"] != GLOBAL_SHA or global_rows[0]["size_bytes"] != GLOBAL_SIZE:
        raise ValueError("Global bank must remain the exact accepted original bytes")
    if len({p["output_filename"].casefold() for p in plans}) != len(plans):
        raise ValueError("Android output filename collision")
    return (
        game_root,
        adaptation,
        plans,
        {"accepted": accepted, "inventory": inventory, "bank_index": bank_index},
    )


def create_stage(
    output: Path,
    game_root: Path,
    init_path: Path,
    init_receipt_path: Path,
    plans: list[dict],
    inputs: dict,
) -> dict:
    absolute = Path(os.path.abspath(output))
    reject_symlink_components(absolute)
    canonical_work = WORK.resolve(strict=True)
    if not inside(absolute, canonical_work) or absolute == canonical_work or absolute.exists():
        raise ValueError("stage output must be a new directory under ignored work/")
    if inside(absolute, game_root.resolve(strict=True)):
        raise ValueError("stage output cannot be in accepted game installation")
    if subprocess_check_ignore(absolute) is False:
        raise ValueError("stage output must be ignored by Git")
    absolute.mkdir(parents=True, exist_ok=False)
    target = absolute / OUTPUT_RELATIVE
    target.mkdir(parents=True, exist_ok=False)
    outputs = []
    try:
        init_dest = target / "Init.bnk"
        write_exclusive(init_path, init_dest, INIT_SHA)
        outputs.append(
            {
                "filename": "Init.bnk",
                "sha256": INIT_SHA,
                "size_bytes": init_dest.stat().st_size,
                "role": "explicit_adapted_init_candidate",
                "scope": "fixture-derived candidate; runtime use still gated",
            }
        )
        for row in plans:
            source = game_root / row["source_relative_path"]
            dest = target / row["output_filename"]
            write_exclusive(source, dest, row["source_sha256"])
            outputs.append(
                {
                    "filename": row["output_filename"],
                    "sha256": row["source_sha256"],
                    "size_bytes": dest.stat().st_size,
                    "requested_name": row["requested_name"],
                    "source_relative_path": row["source_relative_path"],
                    "case_renamed": row["case_renamed"],
                }
            )
        receipt = {
            "schema": "original-game-wwise-bank-cohort-r1",
            "accepted_input_id": ACCEPTED_ID,
            "accepted_inventory_sha256": sha_file(WORK / "inventory/files.json"),
            "current_bank_index_sha256": BANK_INDEX_SHA,
            "wwise_global_prefab_sha256": PREFAB_SHA,
            "init_adaptation_receipt_sha256": sha_file(init_receipt_path),
            "init_adaptation_candidate_sha256": INIT_SHA,
            "global_accepted_original_sha256": GLOBAL_SHA,
            "requested_banks": len(plans),
            "outputs": outputs,
            "output_relative_directory": OUTPUT_RELATIVE.as_posix(),
            "runtime_private_copy_required": True,
            "runtime_copy_complete": False,
            "runtime_bank_ready": False,
        }
        receipt_path = absolute / "stage-receipt.json"
        with receipt_path.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return receipt
    except BaseException:
        # Preserve partial evidence; never replace or silently clean a failed attempt.
        raise


def write_exclusive(source: Path, dest: Path, expected: str) -> None:
    if dest.exists() or dest.is_symlink():
        raise ValueError("refusing to overwrite staged payload")
    before = source.stat()
    h = hashlib.sha256()
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with source.open("rb") as src, os.fdopen(fd, "wb") as out:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            h.update(block)
            out.write(block)
        out.flush()
        os.fsync(out.fileno())
    after = source.stat()
    if h.hexdigest() != expected or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError("source drift during payload snapshot")
    if sha_file(dest) != expected:
        raise ValueError("staged payload hash mismatch")


def subprocess_check_ignore(path: Path) -> bool:
    import subprocess

    relative = path.relative_to(ROOT).as_posix()
    return (
        subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefab", type=Path, required=True)
    parser.add_argument("--bank-index", type=Path, required=True)
    parser.add_argument("--adapted-init", type=Path, required=True)
    parser.add_argument("--init-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan-json", type=Path)
    args = parser.parse_args()
    if (args.output_dir is None) == (args.plan_json is None):
        parser.error("choose exactly one of --output-dir or --plan-json")
    game_root, _, plans, inputs = load_inputs(args.prefab, args.bank_index, args.adapted_init, args.init_receipt)
    summary = {
        "schema": "original-game-wwise-bank-stage-plan-r1",
        "accepted_input_id": ACCEPTED_ID,
        "requested_bank_count": len(plans),
        "exact_filename_matches": sum(not p["case_renamed"] for p in plans),
        "case_renamed_filenames": [p["output_filename"] for p in plans if p["case_renamed"]],
        "total_requested_bank_bytes": sum(p["size_bytes"] for p in plans),
        "init_candidate_sha256": INIT_SHA,
        "global_original_sha256": GLOBAL_SHA,
        "banks": plans,
    }
    if args.plan_json:
        destination = Path(os.path.abspath(args.plan_json))
        reject_symlink_components(destination)
        if not inside(destination, WORK.resolve(strict=True)) or destination.exists() or not subprocess_check_ignore(destination):
            raise ValueError("plan output must be a new ignored file under work/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write("\n")
    else:
        receipt = create_stage(
            args.output_dir,
            game_root,
            args.adapted_init,
            args.init_receipt,
            plans,
            inputs,
        )
        summary["stage_receipt"] = receipt
    print(json.dumps({k: v for k, v in summary.items() if k != "banks"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
