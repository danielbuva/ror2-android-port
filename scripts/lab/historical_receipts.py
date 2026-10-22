"""Explicit, hash-pinned selection of retained historical evidence (never acceptance)."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from common import ROOT

NAME = "input-migration-optional-guards"
SCHEMA = "ror2-historical-receipt-v1"


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


def _selection(root, name):
    if name != NAME:
        raise RuntimeError("Unknown historical receipt name: " + name)
    return _path(root, "work/config/historical-receipts/" + name + ".json")


def _read_source(root, selection):
    if not isinstance(selection, dict) or selection.get("schema") != SCHEMA or selection.get("name") != NAME:
        raise RuntimeError("Historical receipt selection schema/name mismatch")
    source = _path(root, selection.get("path"))
    try:
        raw = source.read_bytes()
    except FileNotFoundError as error:
        raise RuntimeError("Selected historical receipt is missing; restore the specific retained evidence, never substitute latest") from error
    if hashlib.sha256(raw).hexdigest() != _hash(selection.get("sha256")):
        raise RuntimeError("Historical receipt SHA-256 mismatch")
    return _guards(json.loads(raw))


def resolve(name, *, root=ROOT, original_sha256):
    """Read the selected bytes once, then check their identity against preserved input."""
    root = Path(root)
    path = _selection(root, name)
    try:
        selection = json.loads(path.read_bytes())
    except FileNotFoundError as error:
        raise RuntimeError("Missing named historical receipt " + name + "; explicitly pin retained evidence with scripts/lab/historical_receipts.py") from error
    data = _read_source(root, selection)
    if data["input_sha256"] != _hash(original_sha256):
        raise RuntimeError("Optional guard receipt does not match preserved original RoR2.dll")
    return data, selection


def pin(name, source, expected_sha256, *, root=ROOT):
    """Register an operator-reviewed hash without copying, rewriting or accepting input."""
    root = Path(root)
    path = _selection(root, name)
    selection = dict(schema=SCHEMA, name=name, path=source, sha256=_hash(expected_sha256))
    _read_source(root, selection)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation deliberately refuses replacement of an existing selection.
    with path.open("x") as stream:
        stream.write(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    return selection


def main():
    parser = argparse.ArgumentParser(description="Historical support only: pin reviewed retained evidence, without accepting game input or changing rollbacks.")
    parser.add_argument("name", choices=[NAME])
    parser.add_argument("source", help="Repository-relative file under ignored work/")
    parser.add_argument("--sha256", required=True, help="Independently reviewed SHA-256 of the retained receipt")
    args = parser.parse_args()
    pin(args.name, args.source, args.sha256)


if __name__ == "__main__":
    main()
