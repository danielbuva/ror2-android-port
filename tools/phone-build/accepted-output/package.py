"""Reproduce or stream a private accepted-output packet from explicit owner inputs.

This consumes an existing pinned private profile and accepted target files. It
does not derive Android output from PC files alone or grant redistribution rights.
Generated manifests/frames contain game-derived information and must stay private.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time


MODES = {"sdk-copy", "private-delta", "private-target-frame"}
RESERVE = 8 * 1024**3


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or str(relative) != name:
        raise ValueError("unsafe packet path")
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("symlink packet path refused")
    return path


def verify(root, row):
    path = safe(root, row["path"])
    if path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
        raise ValueError("selected input/output hash differs")
    return path


def profile(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("private profile pin differs")
    value = json.loads(data)
    if value["schema"] != "private-accepted-output-delta-v1" or value["tool"]["flags"] != ["-3", "--single-thread"]:
        raise ValueError("unsupported private packet profile")
    names = set()
    patches = set()
    for row in value["targets"]:
        safe(Path("."), row["path"])
        if row["mode"] not in MODES or row["path"] in names or type(row["bytes"]) is not int or row["bytes"] < 0:
            raise ValueError("invalid/duplicate packet target")
        names.add(row["path"])
        if row["mode"] != "sdk-copy":
            safe(Path("."), row["patch"])
            if row["patch"] in patches or not row["patch"].startswith("patches/") or row["patch_bytes"] < 1:
                raise ValueError("invalid/duplicate compressed frame")
            patches.add(row["patch"])
    return data, value


def create(manifest, expected, targets, pc, sdk, codec, output):
    manifest, targets, pc, sdk, codec, output = map(Path, (manifest, targets, pc, sdk, codec, output))
    # Output must be a new sibling tree, never inside any input tree.
    for root in (targets, pc, sdk):
        if output.resolve().is_relative_to(root.resolve()) or root.resolve().is_relative_to(output.resolve()):
            raise ValueError("packet output overlaps input tree")
    data, value = profile(manifest, expected)
    if sha(codec) != value["tool"]["sha256"]:
        raise ValueError("encoder executable pin differs")
    output.mkdir(mode=0o700)
    started = time.monotonic()
    result = {"success": False, "public_distribution_qualified": False, "independent_owner_input_producer": False, "targets_verified": 0}
    try:
        (output / "patches").mkdir()
        for row in value["sources"]:
            verify(pc, row)
        for row in value["targets"]:
            if shutil.disk_usage(output).free < RESERVE or time.monotonic() - started > 1800:
                raise RuntimeError("packet reserve/deadline reached")
            target = verify(targets, row)
            if row["mode"] == "sdk-copy":
                source = verify(sdk, row["reference"])
                if sha(source) != row["sha256"]:
                    raise ValueError("SDK copy does not match target")
            else:
                command = [str(codec), "-3", "--single-thread", "-q", "-c"]
                if row["mode"] == "private-delta":
                    command += ["--patch-from", str(verify(pc, row["reference"]))]
                command += ["--", str(target)]
                dest = safe(output, row["patch"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("xb") as frame, (output / "codec-stderr.log").open("wb") as error:
                    subprocess.run(command, stdout=frame, stderr=error, check=True, timeout=600)
                if dest.stat().st_size != row["patch_bytes"] or sha(dest) != row["patch_sha256"]:
                    raise ValueError("reproduced compressed frame differs")
            result["targets_verified"] += 1
        for row in value["sources"]:
            verify(pc, row)
        # Preserve exact bytes: timing/tool provenance belongs to the pinned
        # profile; this reproduction's elapsed time is a separate receipt.
        with (output / "manifest.json").open("xb") as destination:
            destination.write(data)
        result.update(success=True, manifest_sha256=expected, compressed_bytes=sum(r.get("patch_bytes", 0) for r in value["targets"]))
        return result
    finally:
        result["seconds"] = time.monotonic() - started
        with (output / "creation-result.json").open("x") as destination:
            json.dump(result, destination, indent=2)
            destination.write("\n")


def stream(package, expected, sdk, destination):
    package, sdk = map(Path, (package, sdk))
    data, value = profile(package / "manifest.json", expected)
    selected = []
    for row in value["targets"]:
        source_row = row["reference"] if row["mode"] == "sdk-copy" else {"path": row["patch"], "bytes": row["patch_bytes"], "sha256": row["patch_sha256"]}
        selected.append((verify(sdk if row["mode"] == "sdk-copy" else package, source_row), source_row))
    # Verify all required frames before emitting any bytes. Recheck during output
    # as well; a changed stream is refused independently by the receiver.
    destination.write(b"R2DLT01\n" + len(data).to_bytes(4, "big") + data)
    for path, row in selected:
        digest = hashlib.sha256()
        count = 0
        with path.open("rb") as source:
            while chunk := source.read(65536):
                destination.write(chunk)
                digest.update(chunk)
                count += len(chunk)
        if count != row["bytes"] or digest.hexdigest() != row["sha256"]:
            raise ValueError("stream source changed")
    destination.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser("create", help="reproduce a private packet from a pinned profile and owner target files")
    for name in ("manifest", "manifest-sha256", "targets", "pc", "sdk", "codec", "output"):
        build.add_argument("--" + name, required=True)
    emit = actions.add_parser("stream", help="emit the verified private packet and SDK copies to stdout")
    for name in ("package", "manifest-sha256", "sdk"):
        emit.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.action == "create":
        result = create(args.manifest, args.manifest_sha256, args.targets, args.pc, args.sdk, args.codec, args.output)
        print(json.dumps(result), file=sys.stderr)
    else:
        stream(args.package, args.manifest_sha256, args.sdk, sys.stdout.buffer)


if __name__ == "__main__":
    main()
