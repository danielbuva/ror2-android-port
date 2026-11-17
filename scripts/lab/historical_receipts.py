"""Explicit, hash-pinned selection of retained historical evidence (never acceptance)."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from common import ROOT

NAME = "input-migration-optional-guards"
SCHEMA = "ror2-historical-receipt-v1"
SCENE_ASSEMBLIES = "scene-runtime-original-assemblies"
AUDIO_IDENTITIES = "scene-runtime-audio-identities"
AUDIO_CLOSURE = "scene-runtime-audio-closure"
TELEPORT_QUERY = "scene-runtime-teleport-query"
NAMES = (NAME, SCENE_ASSEMBLIES, AUDIO_IDENTITIES, AUDIO_CLOSURE, TELEPORT_QUERY)


def _path(root, relative):
    if not isinstance(relative, str):
        raise RuntimeError("Historical receipt path must be work-relative repository text")
    path = Path(relative)
    if path.is_absolute() or not path.parts or path.parts[0] != "work" or ".." in path.parts:
        raise RuntimeError("Historical receipt path must stay under ignored work/")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise RuntimeError("Historical receipt paths must not contain symlinks")
    return target


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("Historical receipt requires a lowercase SHA-256")
    return value


def _guards(data):
    if not isinstance(data, dict):
        raise RuntimeError("Optional guard receipt must be an object")
    _hash(data.get("input_sha256"))
    _hash(data.get("output_sha256"))
    for key in ("assembly_identity_preserved", "type_field_method_contracts_preserved", "module_identity_preserved"):
        if data.get(key) is not True:
            raise RuntimeError("Optional guard receipt lacks preserved contract: " + key)
    methods = data.get("methods")
    if not isinstance(methods, list) or not methods or any(not isinstance(m, str) or not m.strip() for m in methods) or len(set(methods)) != len(methods):
        raise RuntimeError("Optional guard receipt requires distinct nonempty method names")
    return data


def _scene_contract(name, data):
    if not isinstance(data, dict):
        raise RuntimeError("Historical scene receipt must be an object")
    if name == SCENE_ASSEMBLIES:
        assemblies = data.get("original_assemblies")
        if not isinstance(assemblies, dict) or not assemblies:
            raise RuntimeError("Historical scene receipt requires original assemblies")
        for assembly, digest in assemblies.items():
            if not isinstance(assembly, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.dll", assembly):
                raise RuntimeError("Historical assembly name must be a plain DLL filename")
            _hash(digest)
    elif name == AUDIO_IDENTITIES:
        rows = data.get("rows")
        if (
            not isinstance(rows, list)
            or len(rows) != 8
            or any(not isinstance(row, dict) or row.get("resolved") is not True or "error" not in row or row["error"] for row in rows)
        ):
            raise RuntimeError("Audio identity gate failed")
    elif name == AUDIO_CLOSURE:
        files = data.get("files")
        if "unresolved" not in data or data["unresolved"] or not isinstance(files, list) or not files:
            raise RuntimeError("Historical audio closure must be resolved and nonempty")
        for row in files:
            path = row.get("path") if isinstance(row, dict) else None
            if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise RuntimeError("Historical audio closure requires relative asset paths")
            _hash(row.get("sha256"))
    elif name == TELEPORT_QUERY:
        locations = data.get("locations")
        if not isinstance(locations, list) or any(
            not isinstance(row, dict) or not all(key in row for key in ("internalId", "type", "key")) for row in locations
        ):
            raise RuntimeError("Historical teleport query requires location records")
        selected = [
            row
            for row in locations
            if row.get("internalId") == "Assets/RoR2/Base/Common/TeleportOutController/matTPInOut.mat" and row.get("type") == "UnityEngine.Material"
        ]
        if len(selected) != 1 or not isinstance(selected[0].get("key"), str) or not selected[0]["key"]:
            raise RuntimeError("Teleport material catalog identity differs")
    return data


def _selection(root, name):
    if name not in NAMES:
        raise RuntimeError("Unknown historical receipt name: " + name)
    return _path(root, "work/config/historical-receipts/" + name + ".json")


def _read_source(root, name, selection):
    if not isinstance(selection, dict) or selection.get("schema") != SCHEMA or selection.get("name") != name:
        raise RuntimeError("Historical receipt selection schema/name mismatch")
    source = _path(root, selection.get("path"))
    try:
        raw = source.read_bytes()
    except FileNotFoundError as error:
        raise RuntimeError("Selected historical receipt is missing; restore the specific retained evidence, never substitute latest") from error
    if hashlib.sha256(raw).hexdigest() != _hash(selection.get("sha256")):
        raise RuntimeError("Historical receipt SHA-256 mismatch")
    data = json.loads(raw)
    return _guards(data) if name == NAME else _scene_contract(name, data)


def resolve(name, *, root=ROOT, original_sha256=None):
    """Read the selected bytes once, then check their identity against preserved input."""
    root = Path(root)
    path = _selection(root, name)
    try:
        selection = json.loads(path.read_bytes())
    except FileNotFoundError as error:
        raise RuntimeError("Missing named historical receipt " + name + "; explicitly pin retained evidence with scripts/lab/historical_receipts.py") from error
    data = _read_source(root, name, selection)
    if name == NAME and data["input_sha256"] != _hash(original_sha256):
        raise RuntimeError("Optional guard receipt does not match preserved original RoR2.dll")
    return data, selection


def pin(name, source, expected_sha256, *, root=ROOT):
    """Register an operator-reviewed hash without copying, rewriting or accepting input."""
    root = Path(root)
    path = _selection(root, name)
    selection = dict(schema=SCHEMA, name=name, path=source, sha256=_hash(expected_sha256))
    _read_source(root, name, selection)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation deliberately refuses replacement of an existing selection.
    with path.open("x") as stream:
        stream.write(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    return selection


def main():
    parser = argparse.ArgumentParser(description="Historical support only: pin reviewed retained evidence, without accepting game input or changing rollbacks.")
    parser.add_argument("name", choices=NAMES)
    parser.add_argument("source", help="Repository-relative file under ignored work/")
    parser.add_argument("--sha256", required=True, help="Independently reviewed SHA-256 of the retained receipt")
    args = parser.parse_args()
    pin(args.name, args.source, args.sha256)


if __name__ == "__main__":
    main()
