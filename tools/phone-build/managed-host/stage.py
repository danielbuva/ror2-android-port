"""Stage the fixed app-host experiment from public source and owner SDK jars."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
METADATA = ROOT / "recipe/owner-app-host-tools.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise ValueError("Unsafe fixture input path")
    return path


def load_metadata():
    data = json.loads(METADATA.read_text())
    if data.get("schema") != 1 or data.get("kind") != "owner-app-host-tools-v1" or data.get("python_version") != "3.14.8":
        raise ValueError("Unsupported app-host tool profile")
    targets = set()
    for row in data["natives"]:
        relative(row["path"])
        if row["root"] not in ("python", "usr") or not re.fullmatch(r"lib[-A-Za-z0-9_.]+\.so", row["target"]) or row["target"] in targets:
            raise ValueError("Invalid native fixture entry")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid native fixture digest")
        targets.add(row["target"])
    for name, target in data["links"].items():
        relative(name)
        if not name.startswith(("python/lib/python3.14/lib-dynload/", "native-links/")) or target not in targets:
            raise ValueError("Invalid native fixture link")
    for name, expected in data["public_profile_source_hashes"].items():
        relative(name)
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid public fixture source digest")
    return data


def stage(profile_source, sdk, destination, *, root=ROOT):
    profile_source = Path(profile_source).resolve(strict=True)
    sdk = Path(sdk).resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    owned = root.resolve() / "work"
    if destination != destination.resolve() or not destination.is_relative_to(owned) or destination.exists():
        raise ValueError("Fixture destination must be new under this checkout's ignored work/")
    if profile_source == destination or destination in profile_source.parents or sdk == destination or sdk in destination.parents:
        raise ValueError("Fixture destination overlaps its supplied inputs")
    metadata = load_metadata()
    files = {}

    def bind(source, name):
        if source.is_symlink() or not source.is_file():
            raise ValueError("Fixture input must be a regular file")
        files[name] = (source, digest(source))

    for name, expected in metadata["public_profile_source_hashes"].items():
        path = profile_source / name
        if path != path.resolve() or not path.resolve().is_relative_to(profile_source):
            raise ValueError("Public source path contains links")
        bind(path, "repo/" + name)
        if files["repo/" + name][1] != expected:
            raise ValueError("Public transform source drift: " + name)
    for name in ("NativePythonHost.c", "NativeDotnetMuxer.c", "ToolHostActivity.java", "run_profile.py", "build_fixture.py"):
        bind(SOURCE / name, name)
    for name in ("NativeToolHost.c", "Hello.cs", "AndroidManifest.xml"):
        bind(SOURCE.parent / "native-host" / name, name)
    bind(METADATA, "python-native-plan.json")
    for name, path in {
        "android.jar": "platforms/android-30/android.jar",
        "d8.jar": "build-tools/34.0.0/lib/d8.jar",
        "apksigner.jar": "build-tools/34.0.0/lib/apksigner.jar",
    }.items():
        bind(sdk / path, name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    receipt = dict(schema=1, success=False, game_inputs=False, source_hint=metadata["source_head"], files={})
    try:
        for name, (source, expected) in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
            if digest(source) != expected or digest(path) != expected:
                raise RuntimeError("Fixture source/copy drift")
            receipt["files"][name] = expected
        receipt["success"] = True
    except Exception as error:
        receipt["failure"] = str(error)
        raise
    finally:
        (destination / "stage-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-source", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.profile_source, args.sdk, args.dest)
    print(json.dumps(dict(success=result["success"], files=len(result["files"]))))
