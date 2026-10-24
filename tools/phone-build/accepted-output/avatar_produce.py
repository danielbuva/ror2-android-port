"""Produce accepted Avatar bodies using only owner PC ranges and entry ordering."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import time


def module(name):
    spec = importlib.util.spec_from_file_location("_avatar_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


BUNDLE = module("unity_bundle")
MESH = module("mesh_produce")


def reorder(body, field, order):
    """Reorder complete source hash/string entries; introduce no bone values."""
    start, length = field
    end = start + length
    if start < 0 or start % 4 or length < 4 or end > len(body):
        raise ValueError("Avatar table outside original body")
    (count,) = struct.unpack_from("<I", body, start)
    if count > 100000 or len(order) != count or any(type(index) is not int for index in order) or sorted(order) != list(range(count)):
        raise ValueError("Avatar order must be a complete source permutation")
    cursor = start + 4
    entries = []
    for _ in range(count):
        before = cursor
        if cursor + 8 > end:
            raise ValueError("truncated Avatar entry")
        # Preserve the original hash and UTF-8 string bytes, including padding.
        (size,) = struct.unpack_from("<I", body, cursor + 4)
        cursor = (cursor + 8 + size + 3) // 4 * 4
        if cursor > end:
            raise ValueError("Avatar string exceeds source table")
        entries.append(body[before:cursor])
    if cursor != end:
        raise ValueError("trailing Avatar table bytes")
    return body[: start + 4] + b"".join(entries[index] for index in order) + body[end:]


def produce(profile_path, profile_sha256, pc, output):
    if BUNDLE.sha(profile_path) != profile_sha256:
        raise ValueError("Avatar profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) != {"input_id", "bundles"} or profile["input_id"] != MESH.INPUT_ID:
        raise ValueError("unknown Avatar input")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(output):
        raise ValueError("Avatar output must be new and outside original input")
    expected = sum(
        target["bytes"] for bundle in profile["bundles"] for member in bundle["members"] for avatar in member["avatars"] for target in avatar["outputs"]
    )
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient Avatar output capacity")
    output.mkdir()
    started = time.monotonic()
    receipt = {"success": False, "input_id": MESH.INPUT_ID, "profile_sha256": profile_sha256, "objects": 0, "object_bytes": 0}
    try:
        with (output / "objects.bin").open("xb") as data, (output / "index.jsonl").open("x") as index:
            for selected in profile["bundles"]:
                path = MESH.safe_input(pc, selected["path"])
                before = path.stat()
                if BUNDLE.sha(path) != selected["sha256"]:
                    raise ValueError("original Avatar bundle drift")
                bundle = BUNDLE.Bundle(path)
                for selected_member in selected["members"]:
                    member = bundle.member(selected_member["name"])
                    for avatar in selected_member["avatars"]:
                        member.seek(avatar["offset"])
                        body = BUNDLE.exact(member, avatar["bytes"])
                        if hashlib.sha256(body).hexdigest() != avatar["sha256"]:
                            raise ValueError("original Avatar body drift")
                        for target in avatar["outputs"]:
                            result = reorder(body, avatar["tos_field"], target["order"]) if "order" in target else body
                            digest = hashlib.sha256(result).hexdigest()
                            if digest != target["sha256"] or len(result) != target["bytes"]:
                                raise ValueError("produced Avatar differs from accepted hash")
                            row = {
                                "bundle": target["bundle"],
                                "member": target["member"],
                                "path_id": target["path_id"],
                                "offset": data.tell(),
                                "bytes": len(result),
                                "sha256": digest,
                            }
                            data.write(result)
                            index.write(json.dumps(row, sort_keys=True) + "\n")
                            receipt["objects"] += 1
                            receipt["object_bytes"] += len(result)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or BUNDLE.sha(path) != selected["sha256"]:
                    raise ValueError("original Avatar input changed during production")
        with (output / "objects.bin").open("rb") as data, (output / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                data.seek(row["offset"])
                if hashlib.sha256(BUNDLE.exact(data, row["bytes"])).hexdigest() != row["sha256"]:
                    raise ValueError("persisted Avatar extent drift")
        receipt["outputs"] = {name: {"bytes": (output / name).stat().st_size, "sha256": BUNDLE.sha(output / name)} for name in ("objects.bin", "index.jsonl")}
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output)


if __name__ == "__main__":
    main()
