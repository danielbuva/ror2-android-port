"""Validate complete external Wwise media dependencies against accepted input.

Streaming/prefetch media needs its full external file. Embedded-only memory
media stays in its bank; contradictory metadata or changed source bytes refuse.
"""

from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any


HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_ANDROID_LONG = (1 << 63) - 1


def _reject_symlink_components(path: Path) -> None:
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        try:
            if stat.S_ISLNK(cursor.lstat().st_mode):
                raise ValueError("external media source path contains a symlink component")
        except FileNotFoundError:
            pass


def required_copy_free_bytes(pending_sizes: list[int]) -> int:
    """Minimum free space for remaining files plus one atomic temp copy."""
    if any(type(size) is not int or size <= 0 for size in pending_sizes):
        raise ValueError("pending copy sizes must be positive integers")
    total = sum(pending_sizes)
    peak = total + (max(pending_sizes) if pending_sizes else 0)
    if peak > MAX_ANDROID_LONG:
        raise ValueError("copy space requirement overflows Android StatFs long")
    return peak


def _safe_media_path(value: str, media_id: int) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or len(path.parts) != 2
        or path.parts[0] != "Media"
        or path.suffix.lower() != ".wem"
        or path.stem != str(media_id)
    ):
        raise ValueError(f"unsafe or noncanonical Wwise media path for ID {media_id}")
    return path.as_posix()


def plan_external_media(
    selected_bank_names: list[str],
    bank_index_rows: list[dict[str, Any]],
    soundbanks_info_rows: list[dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    game_root: Path,
    bank_root_relative: str,
) -> list[dict[str, Any]]:
    """Build a unique ID->path plan for all streaming or loose selected media.

    Both metadata sources are checked for every external dependency. Memory
    media that is not streamed must have an embedded bank entry and does not
    require an external WEM. Streaming media with an embedded prefetch still
    requires the complete external WEM.
    """
    game_root = game_root.resolve(strict=True)
    if len(selected_bank_names) != len(set(name.casefold() for name in selected_bank_names)):
        raise ValueError("selected bank names collide case-insensitively")

    index_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in bank_index_rows:
        path = row.get("path")
        if not isinstance(path, str) or Path(path).name != path or Path(path).suffix.lower() != ".bnk":
            raise ValueError("bank index has an unsafe bank path")
        index_by_name.setdefault(Path(path).stem.casefold(), []).append(row)

    xml_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in soundbanks_info_rows:
        name = row.get("short_name")
        if not isinstance(name, str) or not name:
            raise ValueError("SoundbanksInfo bank has no ShortName")
        xml_by_name.setdefault(name.casefold(), []).append(row)

    inventory_by_path: dict[str, list[dict[str, Any]]] = {}
    for row in inventory_rows:
        path = row.get("path")
        if isinstance(path, str):
            inventory_by_path.setdefault(path, []).append(row)

    plan_by_id: dict[int, dict[str, Any]] = {}
    for bank_name in selected_bank_names:
        index_matches = index_by_name.get(bank_name.casefold(), [])
        xml_matches = xml_by_name.get(bank_name.casefold(), [])
        if len(index_matches) != 1 or len(xml_matches) != 1:
            raise ValueError(f"selected bank must map uniquely in both metadata sources: {bank_name}")
        index_row, xml_row = index_matches[0], xml_matches[0]

        declared_rows = index_row.get("declared")
        embedded_rows = index_row.get("embedded")
        media_rows = xml_row.get("media")
        if not all(isinstance(value, list) for value in (declared_rows, embedded_rows, media_rows)):
            raise ValueError(f"selected bank media metadata is malformed: {bank_name}")

        declared: dict[int, dict[str, Any]] = {}
        embedded: dict[int, dict[str, Any]] = {}
        xml_media: dict[int, dict[str, Any]] = {}
        for source, destination, key in (
            (declared_rows, declared, "declared"),
            (embedded_rows, embedded, "embedded"),
            (media_rows, xml_media, "SoundbanksInfo"),
        ):
            for media in source:
                media_id = media.get("id")
                if type(media_id) is not int or media_id < 0 or media_id in destination:
                    raise ValueError(f"duplicate or invalid {key} media ID in {bank_name}")
                destination[media_id] = media

        # Cross-check every bank-index declaration against SoundbanksInfo.
        # The two inputs may contain extra non-streamed records in either view;
        # only external dependencies must have identical streaming/location data.
        external_ids: set[int] = set()
        for media_id, media in declared.items():
            streaming = media.get("streaming")
            location = media.get("location")
            if type(streaming) is not bool or location not in {"Memory", "Loose"}:
                raise ValueError(f"unknown bank media mode for {bank_name}:{media_id}")
            xml = xml_media.get(media_id)
            if xml is not None and (xml.get("streaming") is not streaming or xml.get("location") != location):
                raise ValueError(f"media mode differs between bank index and SoundbanksInfo: {bank_name}:{media_id}")
            if streaming or location == "Loose":
                external_ids.add(media_id)
                if xml is None:
                    raise ValueError(f"external media missing from SoundbanksInfo: {bank_name}:{media_id}")
                if xml.get("streaming") is not streaming or xml.get("location") != location:
                    raise ValueError(f"external media mode differs between metadata sources: {bank_name}:{media_id}")
                xml_path = xml.get("path")
                if not isinstance(xml_path, str) or _safe_media_path(xml_path, media_id) != f"Media/{media_id}.wem":
                    raise ValueError(f"external media path differs from Wwise ID path: {bank_name}:{media_id}")
            elif location == "Memory" and media_id not in embedded:
                raise ValueError(f"non-streamed Memory media is not embedded: {bank_name}:{media_id}")

        # SoundbanksInfo-only external entries also imply a required file. This
        # catches stale/incomplete bank-index rows rather than dropping content.
        for media_id, media in xml_media.items():
            streaming = media.get("streaming")
            location = media.get("location")
            if type(streaming) is not bool or location not in {"Memory", "Loose"}:
                raise ValueError(f"unknown SoundbanksInfo media mode: {bank_name}:{media_id}")
            if streaming or location == "Loose":
                index_media = declared.get(media_id)
                if index_media is None:
                    raise ValueError(f"SoundbanksInfo external media missing from bank index: {bank_name}:{media_id}")
                if index_media.get("streaming") is not streaming or index_media.get("location") != location:
                    raise ValueError(f"media mode differs between bank index and SoundbanksInfo: {bank_name}:{media_id}")
                external_ids.add(media_id)

        for media_id in external_ids:
            xml = xml_media[media_id]
            relative = _safe_media_path(xml["path"], media_id)
            source_relative = f"{bank_root_relative}/{relative}"
            matches = inventory_by_path.get(source_relative, [])
            if len(matches) != 1:
                raise ValueError(f"full inventory must contain one exact external media path: {source_relative}")
            inventory = matches[0]
            size = inventory.get("size")
            digest = inventory.get("sha256")
            if type(size) is not int or size <= 0 or not isinstance(digest, str) or not HASH.fullmatch(digest):
                raise ValueError(f"invalid external media inventory row: {source_relative}")
            source = game_root / source_relative
            _reject_symlink_components(source)
            if source.is_symlink() or not source.is_file() or source.stat().st_size != size:
                raise ValueError(f"external media source is missing, linked or size-drifted: {source_relative}")
            hasher = hashlib.sha256()
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            if hasher.hexdigest() != digest:
                raise ValueError(f"external media source hash differs from full inventory: {source_relative}")
            proposed = {
                "media_id": media_id,
                "relative_path": relative,
                "source_relative_path": source_relative,
                "sha256": digest,
                "size_bytes": size,
                "referenced_by": [],
            }
            prior = plan_by_id.get(media_id)
            if prior is not None and any(
                prior[key] != proposed[key]
                for key in (
                    "relative_path",
                    "source_relative_path",
                    "sha256",
                    "size_bytes",
                )
            ):
                raise ValueError(f"same Wwise media ID resolves to conflicting source bytes: {media_id}")
            if prior is None:
                plan_by_id[media_id] = proposed
            plan_by_id[media_id]["referenced_by"].append(bank_name)

    return [plan_by_id[key] for key in sorted(plan_by_id)]
