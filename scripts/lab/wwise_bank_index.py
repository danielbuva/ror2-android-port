"""Index accepted local Wwise banks without copying or publishing game audio.

SoundBanksInfo names events and media, while DIDX identifies the media actually
embedded in each bank. Both are needed before a local Android audio adapter can
make a source-backed playback choice. This is an inventory, not Wwise playback.
"""

import argparse
import json
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from common import WORK, game, now, read, run, sha, write


def chunks(path):
    size = path.stat().st_size
    with path.open("rb") as stream:
        while stream.tell() < size:
            start = stream.tell()
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError(f"Truncated bank chunk header: {path.name}")
            tag, length = struct.unpack("<4sI", header)
            end = start + 8 + length
            if end > size:
                raise ValueError(f"Bank chunk exceeds file: {path.name}")
            yield tag, stream.tell(), length
            stream.seek(end)


def embedded_media(path):
    sections = {tag: (offset, length) for tag, offset, length in chunks(path)}
    if b"BKHD" not in sections:
        raise ValueError(f"Not a Wwise bank: {path.name}")
    if b"DIDX" not in sections:
        return []
    if b"DATA" not in sections:
        raise ValueError(f"DIDX without DATA: {path.name}")
    didx_offset, didx_size = sections[b"DIDX"]
    _, data_size = sections[b"DATA"]
    if didx_size % 12:
        raise ValueError(f"Malformed DIDX: {path.name}")
    result = []
    with path.open("rb") as stream:
        stream.seek(didx_offset)
        for index in range(didx_size // 12):
            media_id, offset, length = struct.unpack("<III", stream.read(12))
            if not length or offset + length > data_size:
                raise ValueError(f"DIDX media exceeds DATA: {path.name}")
            result.append({"id": media_id, "subsong": index + 1, "bytes": length})
    if len({entry["id"] for entry in result}) != len(result):
        raise ValueError(f"Duplicate DIDX media ID: {path.name}")
    return result


def bank_version(path):
    """Read the generator ABI from one accepted Windows bank header."""
    headers = [(offset, size) for tag, offset, size in chunks(path) if tag == b"BKHD"]
    if len(headers) != 1 or headers[0][1] < 4:
        raise ValueError(f"Expected one complete BKHD version: {path.name}")
    with path.open("rb") as stream:
        stream.seek(headers[0][0])
        return struct.unpack("<I", stream.read(4))[0]


def parse_source_banks(root: Path, input_id: str) -> dict:
    """Read the complete source metadata/bank cohort, without lab state or decoding.

    The caller must validate the legitimate inventory; an input-id argument alone
    is not ownership or input verification. No source or project file is written.
    """
    root = Path(root)
    xml = root / "SoundbanksInfo.xml"
    if not xml.is_file():
        raise RuntimeError("Accepted Wwise bank metadata unavailable")
    source = ET.parse(xml).getroot()
    metadata_version = int(source.attrib["SoundBankVersion"])
    banks, events, mismatches = [], [], []
    all_media = {}
    for bank in source.findall("SoundBanks/SoundBank"):
        path_node = bank.find("Path")
        if path_node is None or not path_node.text:
            raise ValueError("Bank has no source path")
        relative = path_node.text.replace("\\", "/")
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Bank path escapes accepted audio root")
        if not path.is_file() or path.suffix.lower() != ".bnk":
            raise ValueError(f"SoundBanksInfo bank missing: {relative}")
        embedded = embedded_media(path)
        version = bank_version(path)
        if version != metadata_version:
            raise ValueError(f"Bank generator version differs from SoundBanksInfo: {relative}")
        embedded_ids = {entry["id"] for entry in embedded}
        declared = []
        for file in bank.findall("Media/File"):
            media_id = int(file.attrib["Id"])
            location = file.attrib["Location"]
            declared.append({"id": media_id, "location": location, "streaming": file.attrib["Streaming"] == "true"})
            all_media.setdefault(media_id, set()).add(relative)
            if (location == "Memory") != (media_id in embedded_ids):
                mismatches.append({"bank": relative, "media": media_id, "location": location, "embedded": media_id in embedded_ids})
        banks.append({"path": relative, "sha256": sha(path), "bytes": path.stat().st_size, "version": version, "embedded": embedded, "declared": declared})
        for event in bank.findall("Events/Event"):
            events.append(
                {
                    "bank": relative,
                    "id": int(event.attrib["Id"]),
                    "name": event.attrib["Name"],
                    "duration_type": event.attrib.get("DurationType"),
                    "media": [int(item.attrib["Id"]) for item in event.findall("MediaRefs/MediaRef")],
                }
            )
    if mismatches:
        raise ValueError(f"Bank metadata/DIDX mismatch: {len(mismatches)}; first {mismatches[0]}")
    unresolved = [event for event in events if any(media not in all_media for media in event["media"])]
    if unresolved:
        raise ValueError(f"Events reference absent media: {len(unresolved)}; first {unresolved[0]['name']}")
    report = {
        "input_id": input_id,
        "metadata_sha256": sha(xml),
        "metadata_schema_version": int(source.attrib["SchemaVersion"]),
        "metadata_bank_version": metadata_version,
        "platform": source.attrib["Platform"],
        "banks": banks,
        "events": events,
        "summary": {
            "banks": len(banks),
            "bank_versions": sorted({bank["version"] for bank in banks}),
            "events": len(events),
            "embedded_media": sum(len(bank["embedded"]) for bank in banks),
            "single_media_events": sum(len(event["media"]) == 1 for event in events),
            "multi_media_events": sum(len(event["media"]) > 1 for event in events),
            "no_media_events": sum(not event["media"] for event in events),
        },
        "decoder_sample": None,
    }
    return report


def decoder_metadata(root: Path, banks: list, scratch: Path, *, executable="vgmstream-cli") -> dict:
    """Explicit metadata-only qualification on a temporary copy, never original audio."""
    candidate = min(((bank, media) for bank in banks for media in bank["embedded"]), key=lambda pair: pair[0]["bytes"], default=None)
    if candidate is None:
        raise ValueError("No embedded audio to verify")
    bank, media = candidate
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="decoder-", dir=scratch) as temp:
        local = Path(temp) / Path(bank["path"]).name
        original = root / bank["path"]
        if sha(original) != bank["sha256"]:
            raise ValueError("decoder source bank changed")
        shutil.copy2(original, local)
        if sha(local) != bank["sha256"]:
            raise ValueError("decoder bank copy differs")
        result = run([str(executable), "-m", "-I", "-s", str(media["subsong"]), local])
        if sha(original) != bank["sha256"] or sha(local) != bank["sha256"]:
            raise ValueError("decoder changed a source or copied bank")
    decoder = json.loads(result.stdout)
    if int(decoder["streamInfo"]["name"]) != media["id"] or decoder["numberOfSamples"] <= 0:
        raise ValueError("Decoder subsong does not match DIDX media identity")
    return decoder


def index(verify_decoder=False):
    accepted = read(WORK / "config/accepted-input.json")
    generation = read(WORK / "lab-project/.port-input.json")
    if accepted["input_id"] != generation["input_id"]:
        raise RuntimeError("Audio input differs from accepted lab generation")
    root = game() / "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows"
    report = parse_source_banks(root, accepted["input_id"])
    decoder = decoder_metadata(root, report["banks"], WORK / "experiments/audio-recovery") if verify_decoder else None
    report["decoder_sample"] = decoder
    out = WORK / "experiments/audio-recovery" / now()
    write(out / "bank-index.json", report)
    write(
        WORK / "experiments/audio-recovery/current.json",
        {"index": str((out / "bank-index.json").relative_to(WORK)), "input_id": accepted["input_id"], "summary": report["summary"]},
    )
    return report["summary"]


def owner_index(work: Path, output: Path, verify_decoder=False, *, decoder_executable=None) -> dict:
    """Derive a complete index from a verified owner inventory, without a project."""
    from owner_assemblies import input_state

    work, output = Path(work), Path(output)
    if decoder_executable is not None and not verify_decoder:
        raise ValueError("explicit decoder requires metadata qualification")
    if not work.is_absolute() or work != work.resolve(strict=True):
        raise ValueError("owner work root must be canonical")
    if not output.is_absolute() or ".." in output.parts or output.parent != output.parent.resolve(strict=True):
        raise ValueError("new output must have a canonical parent")
    if not output.is_relative_to(work) or output == work or output.exists() or output.is_symlink():
        raise ValueError("new output must be inside owner work")
    identity, installation, receipts = input_state(work)
    if output.is_relative_to(installation) or installation.is_relative_to(output):
        raise ValueError("owner output overlaps original installation")
    output.mkdir()
    terminal = {"schema": 1, "success": False, "input_id": identity, "project_required": False, "decoder_executed": False}
    try:
        inventory = read(work / "inventory/files.json")
        expected = {row["path"]: row for row in inventory["files"]}
        prefix = "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/"
        root = installation / prefix
        report = parse_source_banks(root, identity)
        if verify_decoder:
            terminal["decoder_executed"] = True
            executable = Path(decoder_executable if decoder_executable is not None else shutil.which("vgmstream-cli") or "").resolve(strict=True)
            if not executable.is_file():
                raise ValueError("decoder executable must be a regular file")
            executable_sha = sha(executable)
            report["decoder_sample"] = decoder_metadata(root, report["banks"], output / "decoder-scratch", executable=executable)
            if sha(executable) != executable_sha:
                raise ValueError("decoder executable changed during metadata qualification")
            terminal["decoder_executable_sha256"] = executable_sha
        selected = {prefix + "SoundbanksInfo.xml": report["metadata_sha256"]}
        selected.update({prefix + row["path"]: row["sha256"] for row in report["banks"]})
        for relative, digest in selected.items():
            if relative not in expected or digest != expected[relative]["sha256"] or sha(installation / relative) != digest:
                raise ValueError("source bank/metadata differs from accepted inventory")
        after_identity, after_installation, after_receipts = input_state(work)
        if (after_identity, after_installation, after_receipts) != (identity, installation, receipts):
            raise ValueError("owner inventory/configuration changed during indexing")
        write(output / "bank-index.json", report)
        terminal.update(
            success=True,
            summary=report["summary"],
            index_sha256=sha(output / "bank-index.json"),
            source_hashes=selected,
            inventory_receipts=receipts,
            parser_sha256=sha(Path(__file__)),
        )
    except Exception as error:
        terminal["error"] = str(error)
        raise
    finally:
        write(output / "result.json", terminal)
    return terminal


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-decoder", action="store_true")
    parser.add_argument("--owner-work", type=Path, help="current source-only mode: verified owner inventory root, no lab project")
    parser.add_argument("--output", type=Path, help="new private output directory inside owner work")
    args = parser.parse_args()
    if args.owner_work is not None or args.output is not None:
        if args.owner_work is None or args.output is None:
            parser.error("owner mode requires --owner-work and --output")
        result = owner_index(args.owner_work, args.output, args.verify_decoder)
        print(json.dumps({"success": result["success"], "summary": result["summary"], "index_sha256": result["index_sha256"]}, sort_keys=True))
    else:
        print(json.dumps(index(args.verify_decoder), sort_keys=True))
