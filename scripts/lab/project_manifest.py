"""Local-only, read-only project input receipts for composition equivalence."""

from pathlib import Path, PurePosixPath
from common import ROOT, WORK, read, sha

AREAS = ("Assets", "Packages", "ProjectSettings")


def _external_inputs():
    # Mirror build.build_cache_key's external selection. Extracting it would change
    # build.py's self-hash and invalidate existing cache keys; a host test guards drift.
    external = {}
    recipe = WORK / "scene-probe-build.json"
    if recipe.exists():
        external["bundle_recipe"] = sha(recipe)
    whole = WORK / "whole-catalog-build.json"
    if whole.exists():
        manifest = Path(read(whole)["manifest"])
        if not manifest.is_absolute():
            manifest = ROOT / manifest
        if not manifest.is_file():
            raise RuntimeError("Whole-catalog build manifest is missing")
        external["whole_catalog_manifest"] = sha(manifest)
    return external


def _local_path(project, path):
    if not path.is_relative_to(project) or ".." in path.relative_to(project).parts or not path.resolve().is_relative_to(project):
        raise RuntimeError("Project manifest path is outside project")
    # Refuse directory links too: traversal must neither escape nor omit a tree.
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent.is_relative_to(project)):
        raise RuntimeError("Project manifest refuses symbolic links")


def _files(project, folder):
    _local_path(project, folder)
    for path in sorted(folder.iterdir()):
        _local_path(project, path)
        if path.is_dir():
            yield from _files(project, path)
        elif path.is_file():
            yield path
        else:
            raise RuntimeError("Project manifest requires regular files")


def capture(project, extra=None):
    """Hash all three input trees plus build externals; extra lists project-local files.

    Paths in files are relative to the Unity project, independent of its location.
    No file contents, timestamps or absolute paths are stored. Missing input trees
    are empty; unreadable files, escaping paths and symbolic links fail closed.
    """
    project = Path(project).resolve(strict=True)
    if not project.is_dir():
        raise RuntimeError("Project manifest requires a project directory")
    paths = set()
    for name in extra or ():
        path = project / Path(name)
        _local_path(project, path)
        if not path.is_file():
            raise RuntimeError("Project manifest extra input must be a file")
        paths.add(path)
    for area in AREAS:
        folder = project / area
        _local_path(project, folder)
        if folder.exists():
            paths.update(_files(project, folder))
    files = {path.relative_to(project).as_posix(): {"sha256": sha(path), "size": path.stat().st_size} for path in sorted(paths)}
    return {"version": 1, "files": files, "external": _external_inputs()}


def _validate(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"version", "files", "external"} or manifest["version"] != 1:
        raise RuntimeError("Invalid project manifest schema")
    for kind in ("files", "external"):
        if not isinstance(manifest[kind], dict):
            raise RuntimeError("Invalid project manifest inputs")
        for path, value in manifest[kind].items():
            if (
                not isinstance(path, str)
                or not path
                or PurePosixPath(path).is_absolute()
                or ".." in PurePosixPath(path).parts
                or PurePosixPath(path).as_posix() != path
            ):
                raise RuntimeError("Invalid project manifest path")
            if kind == "files":
                if not isinstance(value, dict) or set(value) != {"sha256", "size"} or type(value["size"]) is not int or value["size"] < 0:
                    raise RuntimeError("Invalid project manifest file record")
                value = value["sha256"]
            if not isinstance(value, str) or len(value) != 64 or set(value) - set("0123456789abcdef"):
                raise RuntimeError("Invalid project manifest hash")


def compare(a, b):
    """Return sorted added/removed/changed paths by area, equality and a short summary."""
    _validate(a)
    _validate(b)
    areas = {}
    counts = dict(added=0, removed=0, changed=0)
    for kind in ("files", "external"):
        before, after = a[kind], b[kind]
        changes = {
            "added": after.keys() - before.keys(),
            "removed": before.keys() - after.keys(),
            "changed": {path for path in before.keys() & after.keys() if before[path] != after[path]},
        }
        for change, paths in changes.items():
            counts[change] += len(paths)
            for path in sorted(paths):
                area = path.split("/")[0] if kind == "files" else "external"
                group = areas.setdefault(area, dict(added=[], removed=[], changed=[]))
                group[change].append(path if kind == "files" else "external/" + path)
    equal = not any(counts.values())
    summary = "Project manifests match." if equal else "Project manifests differ: " + ", ".join(f"{count} {change}" for change, count in counts.items()) + "."
    return {"equal": equal, "areas": dict(sorted(areas.items())), "summary": summary}
