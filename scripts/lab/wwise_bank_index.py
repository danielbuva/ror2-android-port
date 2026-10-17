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


def index(verify_decoder=False):
    accepted = read(WORK / "config/accepted-input.json")
    generation = read(WORK / "lab-project/.port-input.json")
    if accepted["input_id"] != generation["input_id"]:
        raise RuntimeError("Audio input differs from accepted lab generation")
    root = game() / "Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows"
    xml = root / "SoundbanksInfo.xml"
    if not xml.is_file():
        raise RuntimeError("Accepted Wwise bank metadata unavailable")
    source = ET.parse(xml).getroot()
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
        embedded_ids = {entry["id"] for entry in embedded}
        declared = []
        for file in bank.findall("Media/File"):
            media_id = int(file.attrib["Id"])
            location = file.attrib["Location"]
            declared.append({"id": media_id, "location": location, "streaming": file.attrib["Streaming"] == "true"})
            all_media.setdefault(media_id, set()).add(relative)
            if (location == "Memory") != (media_id in embedded_ids):
                mismatches.append({"bank": relative, "media": media_id, "location": location, "embedded": media_id in embedded_ids})
        banks.append({"path": relative, "sha256": sha(path), "bytes": path.stat().st_size, "embedded": embedded, "declared": declared})
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
    decoder = None
    if verify_decoder:
        candidate = min(((bank, media) for bank in banks for media in bank["embedded"]), key=lambda pair: pair[0]["bytes"], default=None)
        if candidate is None:
            raise ValueError("No embedded audio to verify")
        bank, media = candidate
        scratch = WORK / "experiments/audio-recovery"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="decoder-", dir=scratch) as temp:
            local = Path(temp) / Path(bank["path"]).name
            shutil.copy2(root / bank["path"], local)
            result = run(["vgmstream-cli", "-m", "-I", "-s", str(media["subsong"]), local])
        decoder = json.loads(result.stdout)
        if int(decoder["streamInfo"]["name"]) != media["id"] or decoder["numberOfSamples"] <= 0:
            raise ValueError("Decoder subsong does not match DIDX media identity")
    report = {
        "input_id": accepted["input_id"],
        "metadata_sha256": sha(xml),
        "banks": banks,
        "events": events,
        "summary": {
            "banks": len(banks),
            "events": len(events),
            "embedded_media": sum(len(bank["embedded"]) for bank in banks),
            "single_media_events": sum(len(event["media"]) == 1 for event in events),
            "multi_media_events": sum(len(event["media"]) > 1 for event in events),
            "no_media_events": sum(not event["media"] for event in events),
        },
        "decoder_sample": decoder,
    }
    out = WORK / "experiments/audio-recovery" / now()
    write(out / "bank-index.json", report)
    write(
        WORK / "experiments/audio-recovery/current.json",
        {"index": str((out / "bank-index.json").relative_to(WORK)), "input_id": accepted["input_id"], "summary": report["summary"]},
    )
    return report["summary"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-decoder", action="store_true")
    args = parser.parse_args()
    print(json.dumps(index(args.verify_decoder), sort_keys=True))
