"""Index receipt-pinned source-produced records under explicit destination IDs."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("remap_objects", Path(__file__).with_name("object_produce.py"))
O = importlib.util.module_from_spec(spec)
spec.loader.exec_module(O)


def serialized_records(directory, receipt, selected):
    """Select bodies from an independently produced, receipt-pinned player file."""
    directory = directory.resolve(strict=True)
    relative, identity = selected["source"]
    path = O.M.safe_input(directory, relative)
    pin = receipt["files"][relative]
    if path.stat().st_size != pin["bytes"] or O.B.sha(path) != pin["sha256"]:
        raise ValueError("serialized supplier file drift")
    with path.open("rb") as stream:
        stream.size = path.stat().st_size
        metadata = O.W.read_serialized(stream)
        matches = [r for r in metadata["objects"] if r["path_id"] == identity]
        if len(matches) != 1:
            raise ValueError("serialized supplier identity differs")
        original = matches[0]
        class_id = metadata["types"][original["type_id"]]["class_id"]
        if class_id != selected["class_id"] or original["bytes"] != selected["bytes"]:
            raise ValueError("serialized supplier class or size differs")
        stream.seek(metadata["data_offset"] + original["offset"])
        body = O.B.exact(stream, original["bytes"])
    if hashlib.sha256(body).hexdigest() != selected["sha256"]:
        raise ValueError("serialized supplier body differs")
    if path.stat().st_size != pin["bytes"] or O.B.sha(path) != pin["sha256"]:
        raise ValueError("serialized supplier changed during extraction")
    row = {
        "bytes": len(body),
        "sha256": selected["sha256"],
        "class_id": class_id,
        "source_produced": {"profile_sha256": receipt["profile_sha256"], "file": relative, "path_id": identity, "file_sha256": pin["sha256"]},
    }
    return row, body


def produce(profile_path, profile_sha256, packs, output, serialized=()):
    if O.B.sha(profile_path) != profile_sha256:
        raise ValueError("record remap profile drift")
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != O.M.INPUT_ID:
        raise ValueError("record remap input drift")
    providers = {}
    serialized_keys = set()
    for directory, pin in [*packs, *serialized]:
        directory = Path(directory).resolve(strict=True)
        if O.B.sha(directory / "result.json") != pin:
            raise ValueError("record remap supplier receipt drift")
        receipt = json.loads((directory / "result.json").read_text())
        key = receipt["profile_sha256"]
        if not receipt["success"] or receipt["input_id"] != profile["input_id"] or key in providers:
            raise ValueError("invalid record remap supplier")
        providers[key] = directory, pin, receipt
    for directory, _ in serialized:
        serialized_keys.add(json.loads((Path(directory) / "result.json").read_text())["profile_sha256"])
    O.check_record_packs({key: value for key, value in providers.items() if key not in serialized_keys})
    indices = {
        key: [json.loads(line) for line in (directory / "index.jsonl").read_text().splitlines()]
        for key, (directory, _, _) in providers.items()
        if key not in serialized_keys
    }
    rows, bodies, used, identities = [], [], set(), set()
    offset = 0
    for selected in profile["records"]:
        key = selected["source_profile_sha256"]
        source = selected["source"]
        if key in serialized_keys:
            row, body = serialized_records(providers[key][0], providers[key][2], selected)
        else:
            matches = [r for r in indices[key] if [r["bundle"], r["member"], r["path_id"]] == source]
            if len(matches) != 1:
                raise ValueError("record remap source identity differs")
            row = matches[0]
            if row["sha256"] != selected["sha256"] or row["bytes"] != selected["bytes"]:
                raise ValueError("record remap source body differs")
            body = O.record_extent(providers[key][0] / "objects.bin", row)
        destination = selected["destination"]
        identity = tuple(destination)
        if identity in identities:
            raise ValueError("duplicate record remap destination")
        identities.add(identity)
        rows.append(dict(row, bundle=destination[0], member=destination[1], path_id=destination[2], offset=offset))
        bodies.append(body)
        offset += len(body)
        used.add(key)
    if used != providers.keys():
        raise ValueError("unused record remap supplier")
    for directory, pin, _ in providers.values():
        if O.B.sha(directory / "result.json") != pin:
            raise ValueError("record remap supplier changed during extraction")
    output.mkdir()
    with (output / "objects.bin").open("wb") as stream:
        for body in bodies:
            stream.write(body)
    (output / "index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    receipt = {
        "success": True,
        "input_id": profile["input_id"],
        "profile_sha256": profile_sha256,
        "scope": "Index remap only; source bodies and dependency provenance retained",
        "supplier_receipts": {key: pin for key, (_, pin, _) in providers.items()},
        "outputs": {name: {"bytes": (output / name).stat().st_size, "sha256": O.B.sha(output / name)} for name in ("objects.bin", "index.jsonl")},
    }
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--record-pack", nargs=2, action="append", default=[], metavar=("DIRECTORY", "RECEIPT_SHA256"))
    parser.add_argument(
        "--serialized-producer",
        nargs=2,
        action="append",
        default=[],
        metavar=("DIRECTORY", "RECEIPT_SHA256"),
        help="receipt-pinned source-produced serialized files",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.record_pack, args.output, args.serialized_producer)


if __name__ == "__main__":
    main()
