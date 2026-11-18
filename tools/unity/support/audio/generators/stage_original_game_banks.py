#!/usr/bin/env python3
"""Generate a hash-bound Android StreamingAssets cohort for the original Wwise loaders.

All source files are read from the configured accepted Steam installation. Outputs,
when requested, must be a new directory below ignored work/. This tool stages bytes
only; it does not copy to the app-private runtime root or establish native loading.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[5]
WORK = ROOT / "work"
ACCEPTED_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"
PREFAB_SHA = "7f074267744a3f7652349572f4aa88f48cd3d43328ba629f686288f08c4be6af"
BANK_INDEX_SHA = "f1d41954cb78c582a6c8a5fbbca58148057a120b01e4bb09cd47f8f107d66326"
OWNER_BANK_INDEX_SHA = "063944216e330019b171e8d654b3f0c53ca33289888a2615100abc9e27fa2b76"
SOUNDBANKS_INFO_SHA = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407"
MEDIA_PLANNER_SHA = "d67c2e222d3315a14ab3f338a3de3fc2eebf4dd3d17288defc84b3a702d44989"
INIT_SHA = "618d1c5d534af10fc4cc30a1bacd193bf6871dab3e63992ebedd92a92576fb90"
INIT_SOURCE_SHA = "3182093b59cf48034b2715b224f3f217b34eaecf104d10940528ea20c4baffc6"
INIT_RECEIPT_SHA = "3b274de411fe2128bffd43de117baf9156e58e75ebcd0f0cb2a5379b1f22260f"
INIT_RECIPE = ROOT / "recipe/wwise-init-android.json"
GLOBAL_SHA = "37756450a0a08a0e3d79ed42926c4de062f67c01dbfef590db1c4af1130485e4"
GLOBAL_SIZE = 95239411
BANK_ROOT = Path("Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows")
OUTPUT_RELATIVE = Path("Audio/GeneratedSoundBanks/Android")
STARTUP_BANK_COUNT = 153


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
    if len(names) != STARTUP_BANK_COUNT or len(set(names)) != STARTUP_BANK_COUNT or any(not n or "/" in n or "\\" in n for n in names):
        raise ValueError("current WwiseGlobal must contain exactly 153 unique safe bank names")
    return names


def packaged_bank_names(startup_names: list[str], index_rows: list[dict]) -> list[str]:
    startup = {name.casefold() for name in startup_names}
    additional = []
    for row in index_rows:
        path = row.get("path")
        if not isinstance(path, str) or Path(path).name != path or Path(path).suffix.lower() != ".bnk":
            raise ValueError("bank index contains an unsafe/non-leaf bank path")
        name = Path(path).stem
        if name.casefold() != "init" and name.casefold() not in startup:
            additional.append(name)
    return startup_names + sorted(additional)


def soundbanks_rows(path: Path) -> list[dict]:
    if sha_file(path) != SOUNDBANKS_INFO_SHA:
        raise ValueError("current accepted SoundbanksInfo pin mismatch")
    root = ET.parse(path).getroot()
    if root.tag != "SoundBanksInfo" or root.attrib.get("Platform") != "Windows":
        raise ValueError("SoundbanksInfo root/platform mismatch")
    rows = []
    for bank in root.findall("SoundBanks/SoundBank"):
        if bank.attrib.get("Language") != "SFX":
            continue
        name = bank.findtext("ShortName")
        if not name:
            raise ValueError("SoundbanksInfo bank has no ShortName")
        media = []
        for item in bank.findall("Media/File"):
            streaming = item.attrib.get("Streaming")
            if streaming not in {"true", "false"}:
                raise ValueError("SoundbanksInfo media has unknown Streaming value")
            media_path = item.findtext("Path")
            media.append(
                {
                    "id": int(item.attrib["Id"]),
                    "streaming": streaming == "true",
                    "location": item.attrib.get("Location"),
                    "path": media_path.replace("\\", "/") if media_path else None,
                }
            )
        rows.append({"short_name": name, "media": media})
    return rows


def external_media_planner():
    helper = Path(__file__).with_name("original_media_plan.py")
    if sha_file(helper) != MEDIA_PLANNER_SHA:
        raise ValueError("pinned external-media planner source mismatch")
    spec = importlib.util.spec_from_file_location("original_media_plan_r2", helper)
    if spec is None or spec.loader is None:
        raise ValueError("external-media planner cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.plan_external_media


def bank_context(prefab_path: Path, bank_index_path: Path, owner_work: Path | None):
    work = WORK.resolve(strict=True) if owner_work is None else owner_work
    if work != work.resolve(strict=True):
        raise ValueError("owner work root must be canonical")
    accepted = json.loads((work / "config/accepted-input.json").read_text())
    inventory = json.loads((work / "inventory/files.json").read_text())
    local = json.loads((work / "config/local.json").read_text())
    game_root = Path(local["game_path"]).expanduser().resolve(strict=True)
    if accepted.get("input_id") != ACCEPTED_ID or inventory.get("input_id") != ACCEPTED_ID or inventory.get("hash_mode") != "full":
        raise ValueError("accepted identity/full inventory mismatch")
    if sha_file(prefab_path) != PREFAB_SHA:
        raise ValueError("WwiseGlobal prefab pin mismatch")
    bank_index_raw = bank_index_path.read_bytes()
    bank_index = json.loads(bank_index_raw)
    expected_index = BANK_INDEX_SHA if owner_work is None else OWNER_BANK_INDEX_SHA
    if sha_bytes(bank_index_raw) != expected_index or bank_index.get("input_id") != ACCEPTED_ID:
        raise ValueError("current accepted bank-index receipt mismatch")
    if owner_work is not None:
        files = [(row["path"], row["sha256"]) for row in inventory["files"]]
        if sha_bytes(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()) != ACCEPTED_ID:
            raise ValueError("owner inventory content does not match accepted identity")
    return game_root, {"accepted": accepted, "inventory": inventory, "bank_index": bank_index}


def load_inputs(
    prefab_path: Path,
    bank_index_path: Path,
    init_path: Path,
    init_receipt_path: Path,
    *,
    owner_work: Path | None = None,
    startup_only: bool = False,
) -> tuple[Path, dict, list[dict], dict]:
    game_root, inputs = bank_context(prefab_path, bank_index_path, owner_work)
    inventory, bank_index = inputs["inventory"], inputs["bank_index"]
    adaptation_bytes = init_receipt_path.read_bytes()
    adaptation = json.loads(adaptation_bytes)
    receipt_sha = INIT_RECEIPT_SHA if owner_work is None else json.loads(INIT_RECIPE.read_text())["owner_receipt_sha256"]
    if (
        sha_bytes(adaptation_bytes) != receipt_sha
        or adaptation.get("input_sha256") != INIT_SOURCE_SHA
        or adaptation.get("output_sha256") != INIT_SHA
        or (owner_work is None and adaptation.get("transform_sha256") != "91c72d254ba9473d93ffb18c4be2233be1781b6072b08571aed7f607e76e9b37")
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
    if not startup_only:
        names = packaged_bank_names(names, index_rows)
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
        inputs,
    )


def load_streamed_media_inputs(
    prefab_path: Path, bank_index_path: Path, soundbanks_info_path: Path, *, owner_work: Path | None = None
) -> tuple[Path, list[dict]]:
    game_root, inputs = bank_context(prefab_path, bank_index_path, owner_work)
    if owner_work is not None and soundbanks_info_path.resolve(strict=True) != game_root / BANK_ROOT / "SoundbanksInfo.xml":
        raise ValueError("owner SoundbanksInfo must come from the admitted originals")
    index_rows = inputs["bank_index"]["banks"]
    names = packaged_bank_names(extract_names(prefab_path.read_text(encoding="utf-8")), index_rows)
    xml_rows = soundbanks_rows(soundbanks_info_path)
    media_plans = external_media_planner()(
        names,
        index_rows,
        xml_rows,
        inputs["inventory"].get("files", []),
        game_root,
        BANK_ROOT.as_posix(),
    )
    return game_root, media_plans


def create_stage(
    output: Path,
    game_root: Path,
    init_path: Path,
    init_receipt_path: Path,
    plans: list[dict],
    media_plans: list[dict],
    inputs: dict,
    *,
    owner_work: Path | None = None,
) -> dict:
    absolute = Path(os.path.abspath(output))
    reject_symlink_components(absolute)
    canonical_work = WORK.resolve(strict=True) if owner_work is None else owner_work
    if not inside(absolute, canonical_work) or absolute == canonical_work or absolute.exists():
        raise ValueError("stage output must be a new directory under ignored work/")
    if inside(absolute, game_root.resolve(strict=True)):
        raise ValueError("stage output cannot be in accepted game installation")
    if owner_work is None and not subprocess_check_ignore(absolute):
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
        (target / "Media").mkdir(exist_ok=False)
        for row in media_plans:
            source = game_root / row["source_relative_path"]
            dest = target / row["relative_path"]
            write_exclusive(source, dest, row["sha256"])
        receipt = {
            "schema": "original-game-wwise-bank-cohort-r2",
            "accepted_input_id": ACCEPTED_ID,
            "accepted_inventory_sha256": sha_file(canonical_work / "inventory/files.json"),
            "current_bank_index_sha256": BANK_INDEX_SHA if owner_work is None else OWNER_BANK_INDEX_SHA,
            "soundbanks_info_sha256": SOUNDBANKS_INFO_SHA,
            "wwise_global_prefab_sha256": PREFAB_SHA,
            "init_adaptation_receipt_sha256": sha_file(init_receipt_path),
            "init_adaptation_candidate_sha256": INIT_SHA,
            "global_accepted_original_sha256": GLOBAL_SHA,
            "requested_banks": STARTUP_BANK_COUNT,
            "outputs": outputs,
            "streamed_media": [
                {
                    key: row[key]
                    for key in (
                        "media_id",
                        "relative_path",
                        "sha256",
                        "size_bytes",
                        "referenced_by",
                    )
                }
                for row in media_plans
            ],
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

    if not path.is_relative_to(WORK.resolve(strict=True)):
        return False
    # Git cannot descend through the shared work symlink in isolated checkouts.
    ignored_path = WORK if WORK.is_symlink() else path
    relative = ignored_path.relative_to(ROOT).as_posix()
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
    parser.add_argument("--soundbanks-info", type=Path, required=True)
    parser.add_argument("--adapted-init", type=Path, required=True)
    parser.add_argument("--init-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan-json", type=Path)
    parser.add_argument("--owner-work", type=Path, help="explicit admitted owner work root and decoder-free index")
    args = parser.parse_args()
    if (args.output_dir is None) == (args.plan_json is None):
        parser.error("choose exactly one of --output-dir or --plan-json")
    game_root, _, plans, inputs = load_inputs(args.prefab, args.bank_index, args.adapted_init, args.init_receipt, owner_work=args.owner_work)
    media_root, media_plans = load_streamed_media_inputs(args.prefab, args.bank_index, args.soundbanks_info, owner_work=args.owner_work)
    if media_root != game_root:
        raise ValueError("bank and media sources resolve to different accepted roots")
    summary = {
        "schema": "original-game-wwise-bank-stage-plan-r2",
        "accepted_input_id": ACCEPTED_ID,
        "soundbanks_info_sha256": SOUNDBANKS_INFO_SHA,
        "requested_bank_count": STARTUP_BANK_COUNT,
        "packaged_bank_count": len(plans) + 1,
        "exact_filename_matches": sum(not p["case_renamed"] for p in plans),
        "case_renamed_filenames": [p["output_filename"] for p in plans if p["case_renamed"]],
        "total_requested_bank_bytes": sum(p["size_bytes"] for p in plans),
        "streamed_media_count": len(media_plans),
        "streamed_media_bytes": sum(p["size_bytes"] for p in media_plans),
        "streamed_media_copy_peak_bytes": sum(p["size_bytes"] for p in media_plans) + max((p["size_bytes"] for p in media_plans), default=0),
        "init_candidate_sha256": INIT_SHA,
        "global_original_sha256": GLOBAL_SHA,
        "banks": plans,
        "streamed_media": media_plans,
    }
    if args.plan_json:
        destination = Path(os.path.abspath(args.plan_json))
        reject_symlink_components(destination)
        work = WORK.resolve(strict=True) if args.owner_work is None else args.owner_work
        if not inside(destination, work) or inside(destination, game_root) or destination.exists():
            raise ValueError("plan output must be a new file under work/")
        if args.owner_work is None and not subprocess_check_ignore(destination):
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
            media_plans,
            inputs,
            owner_work=args.owner_work,
        )
        summary["stage_receipt"] = receipt
    print(json.dumps({k: v for k, v in summary.items() if k != "banks"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
