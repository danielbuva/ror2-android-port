"""Current, incremental reconstruction into an isolated project; the oracle is read-only."""

from dataclasses import dataclass
import filecmp
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Callable

import assembly_transforms
from composition_io import composition
from catalog_rebuild import catalog_closure, dependencies
from scene_rebuild import stage_variants, source_scenes
from common import RECIPE, ROOT, WORK, game, read, sha


def relative_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise RuntimeError("Unsafe project path: " + value)
    return path


def assembly_path(path):
    return path.endswith((".dll", ".dll.meta"))


def importer(row):
    if not re.fullmatch("[0-9a-f]{32}", row["guid"]):
        raise RuntimeError("Invalid assembly GUID")
    orders = row["execution_order"]
    if any(not re.fullmatch(r"[\w.]+", name) or type(order) is not int for name, order in orders.items()):
        raise RuntimeError("Invalid assembly execution order")
    execution = "  executionOrder: {}" if not orders else "  executionOrder:\n" + "\n".join(f"    {name}: {order}" for name, order in orders.items())
    if type(row["time_created"]) is not int:
        raise RuntimeError("Invalid assembly importer time")
    return (
        (RECIPE / "templates/original-assembly.meta").read_text().format(guid=row["guid"], time_created=row["time_created"], execution_order=execution).encode()
    )


def assemblies(destination, work, input_id, expected, provenance):
    recipe = read(RECIPE / "original-assemblies.json")
    transforms = assembly_transforms.load_recipe()
    if recipe["schema"] != 1 or recipe["input_id"] != input_id or transforms["input_id"] != input_id:
        raise RuntimeError("Assembly recipes require the accepted input")
    rows = recipe["assemblies"]
    paths = [row["path"] for row in rows]
    names = [row["source"] for row in rows]
    if len(set(paths)) != len(paths) or len(set(names)) != len(names):
        raise RuntimeError("Duplicate assembly recipe membership")
    if {path + suffix for path in paths for suffix in ("", ".meta")} != expected:
        raise RuntimeError("Assembly recipe and provenance membership differ")
    managed = game(work) / "Risk of Rain 2_Data/Managed"
    originals = {}
    metadata = {}
    for row in rows:
        path, name = row["path"], row["source"]
        relative_path(path)
        if not path.endswith(".dll") or Path(path).name != name:
            raise RuntimeError("Invalid Managed assembly source")
        source = managed / name
        if sha(source) != row["sha256"]:
            raise RuntimeError("Original assembly drift: " + name)
        originals[name] = source.read_bytes()
        metadata[path] = importer(row)
    transform_inputs = {name: value for step in transforms["steps"] for name, value in step["inputs"].items()}
    by_name = {row["source"]: row for row in rows}
    if any(name not in by_name or by_name[name]["sha256"] != value for name, value in transform_inputs.items()):
        raise RuntimeError("Assembly transform input membership/hash drift")
    # Prepare and hash-gate the entire cohort before placing any project files.
    with tempfile.TemporaryDirectory(prefix=".assemblies-", dir=destination) as scratch:
        transformed = assembly_transforms.generate(managed, Path(scratch), transforms)
        payload = {}
        for row in rows:
            path, name = row["path"], row["source"]
            payload[path] = transformed[name].read_bytes() if name in transformed else originals[name]
            payload[path + ".meta"] = metadata[path]
        for path, content in payload.items():
            if hashlib.sha256(content).hexdigest() != provenance[path]["sha256"] or len(content) != provenance[path]["size"]:
                raise RuntimeError("Rebuilt assembly/importer differs from provenance: " + path)
        for path, content in payload.items():
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


@dataclass(frozen=True)
class Step:
    producers: tuple[str, ...]
    owns: Callable
    build: Callable
    evidence: tuple[str, ...] = ()


# In dependency order. Map producers are broad categories, so each step also
# selects its subsystem paths; e.g. R1 must not claim all unknown assets.
STEPS = {
    "assemblies": Step(("unknown", "export-copy", "repo-builder", "recipe-transform", "unity-generated"), assembly_path, assemblies),
    "composition": Step(("export-copy", "recipe-transform", "generator", "inherited-store"), lambda path: not assembly_path(path), composition),
    "catalog-closure": Step(("repo-builder",), lambda path: not assembly_path(path), catalog_closure, ("whole_catalog.prepare_integration",)),
    "dependencies": Step(
        ("repo-builder",),
        lambda path: not assembly_path(path),
        dependencies,
        ("integrated_objective.sanitize_optional_content", "whole_catalog.repair_support_source"),
    ),
    "stage-variants": Step(
        ("repo-builder",),
        lambda path: not assembly_path(path),
        stage_variants,
        ("stage_variants.stage → nova_bridge.stage_first_stage_geometry", "composition_migration.refresh_scene_contracts → scene_contract"),
    ),
    "source-scenes": Step(("repo-builder",), lambda path: not assembly_path(path), source_scenes, ("source_scene_candidate.prepare",)),
    # Final gate after R3–R8 supply all runtime/build binding targets (J565).
    "validate-bindings": Step((), lambda path: False, None),
}


def safe_destination(destination, input_id, work):
    root = ROOT.resolve()
    rebuild_root = root / "work/rebuild"
    if rebuild_root.resolve() != rebuild_root:
        raise RuntimeError("work/rebuild must not redirect outside this clone")
    dest = Path(destination).expanduser().absolute() if destination is not None else rebuild_root / input_id / "lab-project"
    resolved = dest.resolve()
    protected = (work / "lab-project").resolve()
    if not resolved.is_relative_to(rebuild_root) or resolved == rebuild_root or resolved == protected or protected.is_relative_to(resolved):
        raise RuntimeError("Destination must be an isolated project under work/rebuild")
    if dest != resolved:
        raise RuntimeError("Destination must not contain symlinks or parent traversal")
    if resolved.exists():
        if not resolved.is_dir():
            raise RuntimeError("Destination is not a directory")
        for path in resolved.rglob("*"):
            if path.is_symlink() or (not path.is_dir() and not path.is_file()):
                raise RuntimeError("Destination contains a symlink or special file")
            if path.is_file() and path.stat().st_nlink != 1:
                raise RuntimeError("Destination contains a hard-linked file")
    return resolved


def compare(destination, project, expected, provenance, owns, producers=None):
    result = {status: [] for status in ("identical", "different", "missing", "extra")}
    # Deep comparison reads actual bytes, never shallow stat/mtime equality.
    for path in sorted(expected):
        target, oracle = destination / path, project / path
        if not target.is_file() or not oracle.is_file():
            result["missing"].append({"path": path, "destination": not target.is_file(), "project": not oracle.is_file()})
        else:
            # filecmp caches by stat; clear it so repeated comparisons also see
            # changes with preserved size and timestamps.
            filecmp.clear_cache()
            result["identical" if filecmp.cmp(target, oracle, shallow=False) else "different"].append(path)
    for target in sorted(destination.rglob("*")):
        if target.is_file():
            path = target.relative_to(destination).as_posix()
            if path == ".port-input.json" or path.startswith(".rebuild/"):
                continue
            if path not in provenance or (owns(path) and path not in expected and (producers is None or provenance[path]["producer"] in producers)):
                result["extra"].append(path)
    result["counts"] = {status: len(result[status]) for status in ("identical", "different", "missing", "extra")}
    result["equal"] = not any(result[status] for status in ("different", "missing", "extra"))
    return result


def rebuild_step(step, dest=None, compare_only=False, work=None):
    work = Path(work or WORK).resolve()
    if step not in STEPS:
        raise RuntimeError("Unknown rebuild step: " + step)
    if STEPS[step].build is None:
        raise RuntimeError("validate-bindings is not runnable yet: requires all later builders R3–R8")
    input_id = read(work / "config/accepted-input.json")["input_id"]
    if not re.fullmatch("[0-9a-f]{64}", input_id):
        raise RuntimeError("Invalid accepted input ID")
    destination = safe_destination(dest, input_id, work)
    provenance = read(work / "receipts/provenance-map.json")
    owner = STEPS[step]
    for path in provenance:
        relative_path(path)
    expected = {
        path
        for path, row in provenance.items()
        if owner.owns(path)
        and row["producer"] in owner.producers
        and (not owner.evidence or any(item.get("function") in owner.evidence for item in row.get("evidence", [])))
    }
    if not expected:
        raise RuntimeError("No provenance paths for step: " + step)
    if compare_only:
        if not destination.is_dir():
            raise RuntimeError("Compare-only requires an existing destination")
    else:
        installation = game(work)
        if destination.is_relative_to(installation) or installation.is_relative_to(destination):
            raise RuntimeError("Destination overlaps the installation")
        destination.mkdir(parents=True, exist_ok=True)
        owner.build(destination, work, input_id, expected, provenance)
    return compare(destination, work / "lab-project", expected, provenance, (lambda path: path in expected) if owner.evidence else owner.owns, owner.producers)


def rebuild_action(step, dest=None, compare_only=False, work=None):
    result = rebuild_step(step, dest, compare_only, work)
    print(json.dumps(result, indent=2))
    if not result["equal"]:
        raise SystemExit(1)
