"""Create the authored Android Init metadata variant from one accepted bank."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import struct

from common import ROOT, WORK, game, read

DEFAULT_RECIPE = ROOT / "recipe/wwise-init-android.json"


class Refusal(ValueError):
    pass


def _repository_root() -> Path:
    return ROOT.resolve()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    cursor = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        cursor /= component
        try:
            mode = cursor.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise Refusal(f"output path contains a symlink: {cursor}")


def validate_output_paths(
    source: Path, destination: Path, receipt_path: Path | None = None, *, repository_root: Path | None = None
) -> tuple[Path, Path | None]:
    """Require new output paths under ignored repository work, before any reads/writes."""
    repository_root = (repository_root or _repository_root()).resolve(strict=True)
    work_root = repository_root / "work"
    if work_root.is_symlink() or not work_root.is_dir():
        raise Refusal("repository work output root is absent or a symlink")
    work_root = work_root.resolve(strict=True)

    source_real = source.resolve(strict=True)
    outputs = [("destination", destination)]
    if receipt_path is not None:
        outputs.append(("receipt", receipt_path))
    resolved: dict[str, Path] = {}
    for name, path in outputs:
        absolute = Path(os.path.abspath(path))
        _reject_symlink_components(absolute)
        canonical = absolute.resolve(strict=False)
        if not _is_within(canonical, work_root):
            raise Refusal(f"{name} must resolve inside repository ignored work")
        if canonical == source_real:
            raise Refusal(f"{name} must not be the source file")
        if canonical.exists() or canonical.is_symlink():
            raise Refusal(f"refusing to overwrite existing {name}")
        parent = canonical.parent
        if not parent.is_dir():
            raise Refusal(f"{name} parent directory must already exist")
        if not _is_within(parent.resolve(strict=True), work_root):
            raise Refusal(f"{name} parent resolves outside repository work")
        relative = canonical.relative_to(repository_root).as_posix()
        ignored = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", relative], cwd=repository_root, check=False).returncode == 0
        if not ignored:
            raise Refusal(f"{name} is not ignored by Git")
        resolved[name] = canonical
    if receipt_path is not None and resolved["destination"] == resolved["receipt"]:
        raise Refusal("destination and receipt must be different paths")
    return resolved["destination"], resolved.get("receipt")


def _write_new_file(path: Path, data: bytes) -> None:
    """Create exclusively so a late path collision cannot replace user data."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def verify_accepted_source(
    source: Path, expected_sha256: str, configured_game: Path, accepted: dict, inventory: dict, contract: "Contract", input_relative_path: str
) -> tuple[str, int, bytes]:
    if len(expected_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha256):
        raise Refusal("expected source SHA-256 must be 64 lowercase hexadecimal characters")
    accepted_id = accepted.get("input_id")
    if not accepted_id or inventory.get("input_id") != accepted_id:
        raise Refusal("full local inventory does not match the accepted game input")
    if inventory.get("hash_mode") != "full":
        raise Refusal("run a full input inspection before selecting a soundbank")
    try:
        configured = (configured_game / input_relative_path).resolve(strict=True)
        selected = source.resolve(strict=True)
    except OSError as exc:
        raise Refusal("configured accepted source bank is unavailable") from exc
    if selected != configured:
        raise Refusal("source must be the recipe's bank in the configured accepted game")
    matching = [row for row in inventory.get("files", []) if row.get("path") == input_relative_path]
    if len(matching) != 1:
        raise Refusal("accepted full inventory must contain exactly one recipe source")
    row = matching[0]
    # Hash and transform this one snapshot. Never reopen the mutable accepted
    # installation path after verifying it.
    data = selected.read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if (
        actual_sha256 != expected_sha256
        or row.get("sha256") != expected_sha256
        or row.get("size") != contract.bank_size_bytes
        or len(data) != contract.bank_size_bytes
    ):
        raise Refusal("source bytes differ from the accepted full inventory/hash/size")
    return actual_sha256, len(data), data


@dataclass(frozen=True)
class Contract:
    format_version: int
    bank_id: int
    bank_size_bytes: int
    plugin_entries: tuple[tuple[int, str], ...]
    device_effects: dict[int, int]
    root_bus_map: dict[int, int]
    controller_bus_map: dict[int, int]
    system_device: int
    remove_plugin: int
    remove_devices: tuple[int, ...]
    expected_tags: tuple[bytes, ...]


def load_contract(path: Path = DEFAULT_RECIPE) -> Contract:
    recipe = json.loads(path.read_text())
    expected_tags = tuple(tag.encode("ascii") for tag in recipe["expected_chunk_order"])
    return Contract(
        format_version=int(recipe["format_version"]),
        bank_id=int(recipe["bank_id"]),
        bank_size_bytes=int(recipe["bank_size_bytes"]),
        plugin_entries=tuple((int(row["id"]), row["library_name"]) for row in recipe["plugin_entries"]),
        device_effects={int(key): int(value) for key, value in recipe["audio_device_plugin_ids"].items()},
        root_bus_map={int(key): int(value) for key, value in recipe["top_level_bus_device_ids"].items()},
        controller_bus_map={int(key): int(value) for key, value in recipe["controller_bus_to_system"].items()},
        system_device=int(recipe["system_device_id"]),
        remove_plugin=int(recipe["remove_plugin_id"]),
        remove_devices=tuple(int(value) for value in recipe["remove_audio_device_ids"]),
        expected_tags=expected_tags,
    )


def _u32(data: bytes, at: int) -> int:
    if at < 0 or at + 4 > len(data):
        raise Refusal("truncated uint32 field")
    return struct.unpack_from("<I", data, at)[0]


def _put_u32(data: bytearray, at: int, value: int) -> None:
    if at < 0 or at + 4 > len(data):
        raise Refusal("truncated uint32 write")
    struct.pack_into("<I", data, at, value)


def _chunks(data: bytes, expected_tags: tuple[bytes, ...]) -> list[tuple[bytes, bytes]]:
    result = []
    at = 0
    while at < len(data):
        if at + 8 > len(data):
            raise Refusal("truncated top-level bank chunk header")
        tag = data[at : at + 4]
        size = _u32(data, at + 4)
        end = at + 8 + size
        if end > len(data):
            raise Refusal(f"chunk {tag!r} overruns bank")
        result.append((tag, data[at + 8 : end]))
        at = end
    tags = tuple(tag for tag, _ in result)
    if tags != expected_tags:
        raise Refusal(f"unexpected top-level chunk sequence: {tags!r}")
    if len({tag for tag, _ in result}) != len(result):
        raise Refusal("duplicate top-level bank chunk")
    return result


def _encode_chunk(tag: bytes, payload: bytes) -> bytes:
    if len(tag) != 4 or len(payload) > 0xFFFFFFFF:
        raise Refusal("invalid chunk serialization")
    return tag + struct.pack("<I", len(payload)) + payload


def _parse_plugin_chunk(payload: bytes) -> tuple[list[tuple[int, str, bytes]], bytes]:
    if len(payload) < 4:
        raise Refusal("truncated INIT plugin list")
    count = _u32(payload, 0)
    at = 4
    entries = []
    for _ in range(count):
        if at + 4 > len(payload):
            raise Refusal("truncated INIT plugin ID")
        plugin_id = _u32(payload, at)
        end = payload.find(b"\0", at + 4)
        if end < 0:
            raise Refusal("unterminated INIT plugin library name")
        raw_name = payload[at + 4 : end]
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise Refusal("non-ASCII plugin library name") from exc
        entry_bytes = payload[at : end + 1]
        entries.append((plugin_id, name, entry_bytes))
        at = end + 1
    if at != len(payload):
        raise Refusal("unexpected trailing bytes in INIT plugin list")
    return entries, payload[:4]


def _parse_hirc(payload: bytes) -> list[tuple[int, bytes]]:
    if len(payload) < 4:
        raise Refusal("truncated HIRC payload")
    count = _u32(payload, 0)
    at = 4
    records = []
    for _ in range(count):
        if at + 5 > len(payload):
            raise Refusal("truncated HIRC object header")
        kind = payload[at]
        section_size = _u32(payload, at + 1)
        end = at + 5 + section_size
        if end > len(payload):
            raise Refusal("HIRC object overruns chunk")
        records.append((kind, payload[at:end]))
        at = end
    if at != len(payload):
        raise Refusal("unexpected trailing HIRC bytes")
    return records


def _record_id(kind: int, record: bytes) -> int:
    if len(record) < 9:
        raise Refusal("HIRC record too small to contain ID")
    return _u32(record, 5)


def _rewrite_plugin_chunk(payload: bytes, contract: Contract) -> bytes:
    entries, count_bytes = _parse_plugin_chunk(payload)
    observed = tuple((plugin_id, name) for plugin_id, name, _ in entries)
    if observed != contract.plugin_entries:
        raise Refusal("INIT plugin inventory differs from pinned source contract")
    removed = [entry for entry in entries if entry[0] == contract.remove_plugin]
    if len(removed) != 1 or removed[0][1] != "":
        raise Refusal("expected exactly one empty-name unsupported sink entry")
    kept = [entry for entry in entries if entry[0] != contract.remove_plugin]
    return struct.pack("<I", len(kept)) + b"".join(entry[2] for entry in kept)


def _rewrite_hirc(payload: bytes, contract: Contract) -> bytes:
    records = _parse_hirc(payload)
    device_records: dict[int, int] = {}
    top_bus_records: dict[int, int] = {}
    bus_sharesets: dict[int, int] = {}

    for index, (kind, record) in enumerate(records):
        body = record[5:]
        if kind == 21:  # Wwise 150 CAkAudioDevice, per pinned wwiser parser.
            device_id = _record_id(kind, record)
            if len(body) < 8:
                raise Refusal("truncated CAkAudioDevice record")
            plugin_id = _u32(body, 4)
            if device_id in device_records:
                raise Refusal("duplicate CAkAudioDevice ID")
            device_records[device_id] = plugin_id
        elif kind == 8:  # CAkBus. idDeviceShareset is present on top-level buses.
            bus_id = _record_id(kind, record)
            if bus_id in top_bus_records:
                raise Refusal("duplicate CAkBus ID")
            if len(body) < 8:
                raise Refusal("truncated CAkBus prefix")
            override_bus = _u32(body, 4)
            if override_bus == 0:
                if len(body) < 12:
                    raise Refusal("truncated top-level CAkBus shareset")
                top_bus_records[bus_id] = index
                bus_sharesets[bus_id] = _u32(body, 8)

    if device_records != contract.device_effects:
        raise Refusal("CAkAudioDevice identities/effects differ from pinned source contract")
    if set(contract.root_bus_map) - set(top_bus_records):
        raise Refusal("one or more target Controller Speaker buses are absent or not top-level")
    if len(top_bus_records) != len(bus_sharesets) or set(top_bus_records) != set(contract.root_bus_map):
        raise Refusal("top-level bus inventory differs from pinned source contract")
    if bus_sharesets != contract.root_bus_map:
        raise Refusal("top-level bus-to-device relationships differ from pinned source contract")
    for old_device in contract.remove_devices:
        if sum(1 for value in bus_sharesets.values() if value == old_device) != 1:
            raise Refusal("removed device must have exactly one top-level bus route")

    remove = set(contract.remove_devices)
    new_records = []
    removed_ids = []
    for index, (kind, record) in enumerate(records):
        object_id = _record_id(kind, record)
        if kind == 21 and object_id in remove:
            body = record[5:]
            if _u32(body, 4) != contract.remove_plugin or len(body) != 20 or body[8:] != bytes(12):
                raise Refusal("target Controller CAkAudioDevice has unexpected serialized parameters")
            removed_ids.append(object_id)
            continue
        if kind == 8 and object_id in contract.root_bus_map and object_id in contract.controller_bus_map:
            patched = bytearray(record)
            _put_u32(patched, 5 + 8, contract.system_device)
            record = bytes(patched)
        new_records.append((kind, record))

    if set(removed_ids) != remove or len(removed_ids) != len(remove):
        raise Refusal("not all exact target CAkAudioDevice records were removed")
    # Check the transformed structural graph before serialization.
    remaining_devices = {device_id: plugin_id for device_id, plugin_id in device_records.items() if device_id not in remove}
    if any(plugin_id == contract.remove_plugin for plugin_id in remaining_devices.values()):
        raise Refusal("unsupported plugin still referenced by a remaining audio device")
    output_top_bus = dict(bus_sharesets)
    for bus_id in contract.root_bus_map:
        if bus_id in contract.controller_bus_map:
            output_top_bus[bus_id] = contract.system_device
    if any(output_top_bus[bus_id] != contract.system_device for bus_id in contract.controller_bus_map):
        raise Refusal("target bus did not resolve to System device")
    return struct.pack("<I", len(new_records)) + b"".join(record for _, record in new_records)


def rewrite_bank(data: bytes, contract: Contract) -> bytes:
    chunks = _chunks(data, contract.expected_tags)
    by_tag = dict(chunks)
    header = by_tag[b"BKHD"]
    if len(header) != 48 or _u32(header, 0) != contract.format_version or _u32(header, 4) != contract.bank_id:
        raise Refusal("unexpected format-150 bank header")
    rewritten = []
    for tag, payload in chunks:
        if tag == b"INIT":
            payload = _rewrite_plugin_chunk(payload, contract)
        elif tag == b"HIRC":
            payload = _rewrite_hirc(payload, contract)
        rewritten.append(_encode_chunk(tag, payload))
    result = b"".join(rewritten)
    # Reparse the entire output and verify counts/relationships against the same
    # structural constraints, with the adapted inventory expected explicitly.
    verify = _chunks(result, contract.expected_tags)
    output = dict(verify)
    out_plugins, _ = _parse_plugin_chunk(output[b"INIT"])
    if any(entry[0] == contract.remove_plugin for entry in out_plugins):
        raise Refusal("unsupported plugin entry remains in output")
    out_records = _parse_hirc(output[b"HIRC"])
    if any(kind == 21 and _u32(record, 9) == contract.remove_plugin for kind, record in out_records):
        raise Refusal("unsupported plugin remains in output HIRC")
    output_devices = {}
    output_buses = {}
    for kind, record in out_records:
        body = record[5:]
        if kind == 21:
            output_devices[_record_id(kind, record)] = _u32(body, 4)
        elif kind == 8 and _u32(body, 4) == 0:
            output_buses[_record_id(kind, record)] = _u32(body, 8)
    expected_devices = {device: plugin for device, plugin in contract.device_effects.items() if device not in contract.remove_devices}
    expected_buses = dict(contract.root_bus_map)
    for bus_id in contract.controller_bus_map:
        expected_buses[bus_id] = contract.system_device
    if output_devices != expected_devices or output_buses != expected_buses:
        raise Refusal("output device/bus relationship check failed")
    for tag in (b"BKHD", b"STMG", b"ENVS", b"PLAT"):
        if output[tag] != by_tag[tag]:
            raise Refusal(f"unexpected change to preserved {tag.decode('ascii')} chunk")
    return result


def transform_file(
    source: Path,
    destination: Path,
    receipt_path: Path,
    expected_sha256: str,
    contract: Contract,
    configured_game: Path,
    accepted: dict,
    inventory: dict,
    input_relative_path: str,
) -> dict:
    destination, receipt_path = validate_output_paths(source, destination, receipt_path)
    digest, input_size, data = verify_accepted_source(source, expected_sha256, configured_game, accepted, inventory, contract, input_relative_path)
    output = rewrite_bank(data, contract)
    output_sha = hashlib.sha256(output).hexdigest()
    receipt = {
        "candidate": "fixture-only Controller Speaker omission plus System bus routing",
        "transform_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": digest,
        "input_relative_path": input_relative_path,
        "input_size_bytes": input_size,
        "output_sha256": output_sha,
        "output_size_bytes": len(output),
        "format_version": contract.format_version,
        "bank_id": contract.bank_id,
        "removed_plugin_id": contract.remove_plugin,
        "removed_audio_device_ids": list(contract.remove_devices),
        "retained_bus_ids": sorted(contract.root_bus_map),
        "rewritten_controller_bus_ids": sorted(contract.controller_bus_map),
        "retargeted_device_shareset": contract.system_device,
        "untouched_chunks": ["BKHD", "STMG", "ENVS", "PLAT"],
        "scope": "standalone native fixture metadata candidate only; not approved for retained managed game runtime; original bank and Global bank unchanged; no controller sink fidelity, event routing, PCM, or runtime-load claim",
    }
    _write_new_file(destination, output)
    if receipt_path is not None:
        try:
            _write_new_file(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
        except Exception:
            destination.unlink()
            raise
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        recipe = json.loads(DEFAULT_RECIPE.read_text())
        contract = load_contract()
        game_root = game()
        accepted = read(WORK / "config/accepted-input.json")
        inventory = read(WORK / "inventory/files.json")
        receipt = transform_file(
            args.source,
            args.destination,
            args.receipt,
            args.expected_sha256,
            contract,
            game_root,
            accepted,
            inventory,
            recipe["input_relative_path"],
        )
    except (OSError, Refusal) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
