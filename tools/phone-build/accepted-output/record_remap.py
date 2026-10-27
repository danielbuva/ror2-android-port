"""Index receipt-pinned source-produced records under explicit destination IDs."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("remap_objects", Path(__file__).with_name("object_produce.py"))
O = importlib.util.module_from_spec(spec)
spec.loader.exec_module(O)


def produce(profile_path, profile_sha256, packs, output):
    if O.B.sha(profile_path) != profile_sha256:
        raise ValueError("record remap profile drift")
    profile = json.loads(profile_path.read_text())
    if profile["input_id"] != O.M.INPUT_ID:
        raise ValueError("record remap input drift")
    providers = {}
    for directory, pin in packs:
        directory = Path(directory).resolve(strict=True)
        if O.B.sha(directory / "result.json") != pin:
            raise ValueError("record remap supplier receipt drift")
        receipt = json.loads((directory / "result.json").read_text())
        key = receipt["profile_sha256"]
        if not receipt["success"] or receipt["input_id"] != profile["input_id"] or key in providers:
            raise ValueError("invalid record remap supplier")
        providers[key] = directory, pin, receipt
    O.check_record_packs(providers)
    indices = {key: [json.loads(line) for line in (directory / "index.jsonl").read_text().splitlines()] for key, (directory, _, _) in providers.items()}
    rows, bodies, used, identities = [], [], set(), set()
    offset = 0
    for selected in profile["records"]:
        key = selected["source_profile_sha256"]
        source = selected["source"]
        matches = [r for r in indices[key] if [r["bundle"], r["member"], r["path_id"]] == source]
        if len(matches) != 1:
            raise ValueError("record remap source identity differs")
        row = matches[0]
        if row["sha256"] != selected["sha256"] or row["bytes"] != selected["bytes"]:
            raise ValueError("record remap source body differs")
        destination = selected["destination"]
        identity = tuple(destination)
        if identity in identities:
            raise ValueError("duplicate record remap destination")
        identities.add(identity)
        body = O.record_extent(providers[key][0] / "objects.bin", row)
        rows.append(dict(row, bundle=destination[0], member=destination[1], path_id=destination[2], offset=offset))
        bodies.append(body)
        offset += len(body)
        used.add(key)
    if used != providers.keys():
        raise ValueError("unused record remap supplier")
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
    parser.add_argument("--record-pack", nargs=2, action="append", required=True, metavar=("DIRECTORY", "RECEIPT_SHA256"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.record_pack, args.output)


if __name__ == "__main__":
    main()
