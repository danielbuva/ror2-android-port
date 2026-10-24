"""Current isolated owner assembly prefix; no project oracle, editor or device."""

from functools import partial
import hashlib
import json
from pathlib import Path
import shutil

import assembly_transforms
import rebuild
from common import ROOT, WORK, RECIPE, digest, game, read, run, sha, write


def input_state(work):
    """Verify the reviewed inventory and current source stats without changing it."""
    accepted = read(work / "config/accepted-input.json")
    inventory = read(work / "inventory/files.json")
    identity = inventory["input_id"]
    files = inventory["files"]
    if accepted["input_id"] != identity or digest([(row["path"], row["sha256"]) for row in files]) != identity:
        raise RuntimeError("Owner assembly input is not the reviewed inventory")
    installation = game(work)
    current = {path.relative_to(installation).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns) for path in installation.rglob("*") if path.is_file()}
    expected = {row["path"]: (row["size"], row["mtime_ns"]) for row in files}
    if len(expected) != len(files) or current != expected:
        raise RuntimeError("Owner assembly input changed; inspect and review it before generation")
    receipts = {name: sha(work / name) for name in ("config/local.json", "config/accepted-input.json", "inventory/files.json")}
    return identity, installation, receipts


def public_contract(identity):
    """Use published input/output hashes and authored importer parameters."""
    original = read(RECIPE / "original-assemblies.json")
    transforms = assembly_transforms.load_recipe()
    if original["schema"] != 1 or original["input_id"] != identity or transforms["input_id"] != identity:
        raise RuntimeError("Owner assembly recipes require the reviewed input")
    outputs = {name: value for step in transforms["steps"] for name, value in step["outputs"].items()}
    expected, names = {}, set()
    for row in original["assemblies"]:
        path, name = row["path"], row["source"]
        rebuild.relative_path(path)
        if not path.endswith(".dll") or Path(path).name != name or path in expected or name in names:
            raise RuntimeError("Invalid or duplicate owner assembly recipe membership")
        names.add(name)
        expected[path] = outputs.get(name, row["sha256"])
        expected[path + ".meta"] = hashlib.sha256(rebuild.importer(row)).hexdigest()
    if not expected or not set(outputs).issubset(names):
        raise RuntimeError("Missing owner assembly recipe membership")
    return expected, transforms


def source_state(transforms):
    names = {
        "dev",
        "scripts/env.sh",
        "scripts/lab/main.py",
        "scripts/lab/actions.py",
        "scripts/lab/owner_assemblies.py",
        "scripts/lab/rebuild.py",
        "scripts/lab/assembly_transforms.py",
        "scripts/lab/common.py",
        "recipe/original-assemblies.json",
        "recipe/assembly-transforms.json",
        "recipe/templates/original-assembly.meta",
        "environment/toolchain.json",
        "scripts/lab/public_transform_tools.py",
        "recipe/owner-public-tools.json",
        "tools/owner-build/PublicProviderWitness.cs",
        "tools/owner-build/licenses/Roslyn-LICENSE.txt",
        *transforms["tool_sources"],
    }
    return {
        "commit": run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.decode().strip(),
        "uncommitted": bool(run(["git", "status", "--porcelain", "--", *sorted(names)], cwd=ROOT).stdout.strip()),
        "files": {name: sha(ROOT / name) for name in sorted(names)},
    }


def stage(destination, work=None, *, assembly_profile="sdk", tool_archives=None, tool_launcher=None, tool_host=None):
    """Keep an exclusive attempt and its first failure; never update lab pointers."""
    if destination is None:
        raise RuntimeError("Owner assembly prefix requires an explicit new --dest")
    options = (tool_archives, tool_launcher, tool_host)
    if (
        assembly_profile not in {"sdk", "public-dotnet8"}
        or (assembly_profile == "sdk" and any(options))
        or (assembly_profile == "public-dotnet8" and not all(options))
    ):
        raise RuntimeError("Public profile requires explicit tool archives, launcher and qualified host; SDK profile accepts none")
    work = Path(work or WORK).expanduser().resolve()
    identity, installation, inputs = input_state(work)
    destination = rebuild.safe_destination(destination, identity, work)
    if destination.exists():
        raise RuntimeError("Owner assembly prefix destination already exists")
    if destination.is_relative_to(installation) or installation.is_relative_to(destination):
        raise RuntimeError("Owner assembly prefix overlaps the legitimate installation")
    expected, transforms = public_contract(identity)
    source = source_state(transforms)
    if shutil.disk_usage(ROOT).free < 10 * 1024**3:
        raise RuntimeError("Less than 10 GiB host headroom")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    receipt_path = destination / "receipt.json"
    receipt = {
        "schema": 1,
        "kind": "owner-assembly-prefix",
        "success": False,
        "phase": "preparing",
        "input_id": identity,
        "input_receipts_sha256": inputs,
        "source": source,
        "transform_profile": assembly_profile,
        "cecil_sha256": transforms["cecil_sha256"] if assembly_profile == "sdk" else None,
        "full_project_qualified": False,
        "phone_build_qualified": False,
        "runtime_qualified": False,
    }
    write(receipt_path, receipt)
    try:
        attempt = destination / "attempt"
        attempt.mkdir()
        if assembly_profile == "public-dotnet8":
            import public_transform_tools

            producer = partial(public_transform_tools.generate, archives=tool_archives, launcher=tool_launcher, host=tool_host)
            payload = rebuild.assembly_payload(work, identity, attempt, set(expected), transform_producer=producer)
            receipt["public_tools_receipt_sha256"] = sha(attempt / "public-tools-receipt.json")
        else:
            payload = rebuild.assembly_payload(work, identity, attempt, set(expected))
        if set(payload) != set(expected) or any(hashlib.sha256(data).hexdigest() != expected[path] for path, data in payload.items()):
            raise RuntimeError("Owner assembly cohort differs from the public output contract")
        if input_state(work) != (identity, installation, inputs) or source_state(transforms) != source:
            raise RuntimeError("Owner assembly inputs or source changed during generation")
        project = destination / "project"
        project.mkdir()
        manifest = []
        for path, data in sorted(payload.items()):
            target = project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            if sha(target) != expected[path]:
                raise RuntimeError("Owner assembly output readback mismatch")
            manifest.append({"path": path, "bytes": len(data), "sha256": expected[path]})
        write(destination / "manifest.json", manifest)
        receipt.update(phase="complete", success=True, output_files=len(manifest), manifest_sha256=sha(destination / "manifest.json"))
        write(receipt_path, receipt)
    except BaseException as error:
        receipt.update(phase="failed", success=False, error_type=type(error).__name__, error=str(error))
        try:
            write(receipt_path, receipt)
        except Exception as receipt_error:
            raise RuntimeError(str(error) + "; failed to record prefix failure: " + str(receipt_error)) from error
        raise
    return receipt


def stage_action(dest=None, work=None, **profile):
    print(json.dumps(stage(dest, work, **profile), indent=2))
