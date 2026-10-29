"""Produce the qualified mesh cohort from pinned original PC files only."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import resource
import shutil
import time


def module(name):
    spec = importlib.util.spec_from_file_location("_owner_" + name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


_bundle, _mesh = module("unity_bundle"), module("unity_mesh")
Bundle, exact, sha = _bundle.Bundle, _bundle.exact, _bundle.sha
mesh_objects, transform = _mesh.mesh_objects, _mesh.transform


INPUT_ID = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88"


def safe_input(root, relative):
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(part in (".", "..") for part in parts.parts) or "\\" in relative:
        raise ValueError("unsafe source path")
    path = root
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("source symlink refused")
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("source outside original root")
    return path


def produce(profile_path, profile_sha256, pc, output, obj_helper=None):
    started = time.monotonic()
    if sha(profile_path) != profile_sha256:
        raise ValueError("mesh profile drift")
    profile = json.loads(profile_path.read_text())
    if set(profile) - {"obj_import"} != {"input_id", "bundles", "excluded"} or profile["input_id"] != INPUT_ID:
        raise ValueError("unknown mesh input profile")
    native = None
    obj_module = None
    if "obj_import" in profile:
        if obj_helper is None:
            raise ValueError("source OBJ import requires its pinned public helper")
        obj_module = module("obj_mesh")
        native = obj_module.Native(obj_helper, profile["obj_import"])
    elif obj_helper is not None:
        raise ValueError("OBJ helper supplied for an ordinary mesh profile")
    pc = pc.resolve(strict=True)
    parent = output.parent.resolve(strict=True)
    if output.name in ("", ".", "..") or output.exists() or output.is_symlink() or parent.is_relative_to(pc) or pc.is_relative_to(parent / output.name):
        raise ValueError("output must be new and separate from original input")
    expected = sum(target["bytes"] for bundle in profile["bundles"] for member in bundle["members"] for mesh in member["meshes"] for target in mesh["outputs"])
    if shutil.disk_usage(parent).free < expected + 2 * 1024**3:
        raise ValueError("insufficient output space")
    output = parent / output.name
    output.mkdir()
    receipt = {
        "success": False,
        "input_id": INPUT_ID,
        "profile_sha256": profile_sha256,
        "objects": 0,
        "object_bytes": 0,
        "resource_bytes": 0,
        "excluded": profile["excluded"],
    }
    try:
        with (output / "objects.bin").open("xb") as objects, (output / "resources.bin").open("xb") as resources, (output / "index.jsonl").open("x") as index:
            for selected in profile["bundles"]:
                path = safe_input(pc, selected["path"])
                before = path.stat()
                if sha(path) != selected["sha256"]:
                    raise ValueError("original bundle drift")
                bundle = Bundle(path)
                for selected_member in selected["members"]:
                    member = bundle.member(selected_member["name"])
                    catalog = mesh_objects(member)
                    for selected_mesh in selected_member["meshes"]:
                        offset, size, schema = catalog[selected_mesh["path_id"]]
                        member.seek(offset)
                        body = exact(member, size)
                        if hashlib.sha256(body).hexdigest() != selected_mesh["sha256"]:
                            raise ValueError("original mesh drift")
                        vertex = None
                        if "stream" in selected_mesh:
                            source = selected_mesh["stream"]
                            stream = bundle.member(source["member"])
                            stream.seek(source["offset"])
                            vertex = exact(stream, source["bytes"])
                            if hashlib.sha256(vertex).hexdigest() != source["sha256"]:
                                raise ValueError("original vertex stream drift")
                        for target in selected_mesh["outputs"]:
                            if "obj_import" in target["ops"]:
                                if native is None:
                                    raise ValueError("source OBJ operation requires the helper profile")
                                result, external = transform(
                                    body, schema, target["ops"], vertex, lambda data, indices: obj_module.convert(data, indices, native)
                                )
                            else:
                                result, external = transform(body, schema, target["ops"], vertex)
                            digest = hashlib.sha256(result).hexdigest()
                            if len(result) != target["bytes"] or digest != target["sha256"]:
                                raise ValueError("produced mesh differs: " + target["bundle"] + ":" + str(target["path_id"]))
                            row = {
                                "bundle": target["bundle"],
                                "member": target["member"],
                                "path_id": target["path_id"],
                                "offset": objects.tell(),
                                "bytes": len(result),
                                "sha256": digest,
                            }
                            objects.write(result)
                            if external is not None:
                                row["resource"] = {
                                    "offset": resources.tell(),
                                    "bytes": len(external),
                                    "sha256": hashlib.sha256(external).hexdigest(),
                                    "destination": target["ops"]["stream_destination"],
                                }
                                resources.write(external)
                                receipt["resource_bytes"] += len(external)
                            index.write(json.dumps(row, sort_keys=True) + "\n")
                            receipt["objects"] += 1
                            receipt["object_bytes"] += len(result)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or sha(path) != selected["sha256"]:
                    raise ValueError("original bundle changed during production")
                print(json.dumps({"objects": receipt["objects"], "seconds": round(time.monotonic() - started, 3)}), flush=True)
        receipt["outputs"] = {
            name: {"bytes": (output / name).stat().st_size, "sha256": sha(output / name)} for name in ("objects.bin", "resources.bin", "index.jsonl")
        }
        # Re-read persisted object extents independently of the write-time hash.
        with (output / "objects.bin").open("rb") as objects, (output / "resources.bin").open("rb") as resources, (output / "index.jsonl").open() as index:
            for line in index:
                row = json.loads(line)
                for file, section in ((objects, row), (resources, row.get("resource"))):
                    if section is None:
                        continue
                    file.seek(section["offset"])
                    if hashlib.sha256(exact(file, section["bytes"])).hexdigest() != section["sha256"]:
                        raise ValueError("persisted mesh pack drift")
        if native is not None:
            native.finish()
            receipt["obj_import_helper"] = {path.name: pin for path, pin in native.pins.items()}
        receipt["success"] = True
        return receipt
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["seconds"] = time.monotonic() - started
        receipt["peak_rss"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--pc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--obj-helper", type=Path, help="Current pinned public OBJ helper build directory; required only by OBJ profiles")
    args = parser.parse_args()
    produce(args.profile, args.profile_sha256, args.pc, args.output, args.obj_helper)


if __name__ == "__main__":
    main()
