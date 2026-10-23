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
from catalog_rebuild import catalog_closure, dependencies, merge_postprocessing_rows
from scene_rebuild import stage_variants, source_scenes
from build_entry_rebuild import build_entries, runtime_sources, validate_bindings
from project_input_rebuild import PROJECT_INPUT_PATHS, project_inputs
from importer_rebuild import IMPORTER_PATHS, importer_identities
from shader_rebuild import shader_pipeline
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


def assembly_payload(work, input_id, temporary, expected):
    """Produce the recipe cohort independently of the working-project oracle."""
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
    transformed = assembly_transforms.generate(managed, temporary, transforms)
    payload = {}
    for row in rows:
        path, name = row["path"], row["source"]
        payload[path] = transformed[name].read_bytes() if name in transformed else originals[name]
        payload[path + ".meta"] = metadata[path]
    return payload


def assemblies(destination, work, input_id, expected, provenance):
    # The R1 comparison gate still checks the whole cohort before placing files.
    with tempfile.TemporaryDirectory(prefix=".assemblies-", dir=destination) as scratch:
        payload = assembly_payload(work, input_id, Path(scratch), expected)
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
    "shader-pipeline": Step(
        ("repo-builder",),
        lambda path: path.startswith("Assets/LabLoadingScene/Resources/"),
        shader_pipeline,
        ("shader_source.generate", "shader_deferred.generate", "shader_materials.generate"),
    ),
    "composition": Step(("export-copy", "recipe-transform", "generator", "inherited-store"), lambda path: not assembly_path(path), composition),
    "project-inputs": Step(("tool-owned", "unknown", "repo-builder"), lambda path: path in PROJECT_INPUT_PATHS, project_inputs),
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
    "build-entries": Step(
        ("repo-builder", "tool-owned"),
        lambda path: not assembly_path(path),
        build_entries,
        (
            "build.generate_runtime_config",
            "body_visual_map.generate via whole_catalog.build_integration",
            "common_assets_map.generate via whole_catalog.build_integration",
            "animation_bindings.repair via whole_catalog.build_integration",
            "whole_catalog.original_stage_contexts",
            "whole_catalog.build_integration",
        ),
    ),
    "runtime-sources": Step(
        ("repo-builder", "tool-owned"),
        lambda path: not assembly_path(path),
        runtime_sources,
        ("whole_catalog.preservation_descriptor via build_integration", "build.py / whole_catalog.build_integration source staging"),
    ),
    "importer-identities": Step(("unity-generated",), lambda path: path in IMPORTER_PATHS, importer_identities),
    # Final gate after R3–R8 supply all runtime/build binding targets (J565).
    "validate-bindings": Step((), lambda path: False, validate_bindings),
}


def selected_paths(owner, provenance):
    return {
        path
        for path, row in provenance.items()
        if owner.owns(path)
        and row["producer"] in owner.producers
        and (not owner.evidence or any(item.get("function") in owner.evidence or item.get("owner") in owner.evidence for item in row.get("evidence", [])))
    }


def provenance_coverage(provenance):
    """Map attribution only, not evidence of a completed replay or runtime readiness."""
    membership = {name: selected_paths(owner, provenance) for name, owner in STEPS.items() if name != "validate-bindings"}
    covered = set().union(*membership.values())
    r9 = read(RECIPE / "rebuild-r9-obligations.json")["files"]
    return dict(
        r9_obligations={path: dict(row, **r9[path]) for path, row in provenance.items() if path in r9},
        counts={name: len(paths) for name, paths in membership.items()},
        uncovered={path: row for path, row in provenance.items() if path not in covered and path not in r9},
    )


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


UNITY_OWNED = frozenset(("Library", "Temp", "Logs", "UserSettings"))


def _catalog_shader_override_rows(destination, project, work, expected, provenance):
    work = Path(work)
    marker_path = Path(destination) / ".rebuild/catalog-shader-overrides.json"
    if marker_path.is_symlink():
        raise RuntimeError("Catalog shader override marker is not a regular file")
    if not marker_path.exists():
        return {}
    input_id = read(work / "config/accepted-input.json")["input_id"]
    from catalog_rebuild import read_shader_override_receipt, shader_override_rows

    receipt = read_shader_override_receipt(destination, input_id, work)
    if receipt is None:
        return {}
    overrides = shader_override_rows(receipt, input_id, expected, provenance, candidate_work=work)
    from composition_io import StageIO

    reconstruction = read(Path(work) / "config/reconstruction.json")
    projects = reconstruction.get("projects")
    if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
        raise RuntimeError("Shader override comparison requires the exact accepted export root")
    export = StageIO(work).resolve(projects[0])
    for path, row in overrides.items():
        if row.get("_meta_only"):
            continue
        source = export / row["source_asset_path"]
        source_meta = export / (row["source_asset_path"] + ".meta")
        target_meta = destination / (path + ".meta")
        if (
            source.is_symlink()
            or source_meta.is_symlink()
            or target_meta.is_symlink()
            or not source.is_file()
            or not source_meta.is_file()
            or not target_meta.is_file()
            or sha(source) != row["original_source_sha256"]
            or sha(source_meta) != row["original_meta_sha256"]
            or sha(target_meta) != row["preserved_meta_sha256"]
        ):
            raise RuntimeError("Catalog shader override did not preserve its exact source or .meta: " + path)
    return overrides


def _catalog_postprocessing_bloom_rows(destination, project, work, expected, provenance):
    work = Path(work)
    marker_path = Path(destination) / ".rebuild/postprocessing-bloom.json"
    if marker_path.is_symlink():
        raise RuntimeError("Bloom batch marker is not a regular file")
    if not marker_path.exists():
        return {}
    from catalog_rebuild import postprocessing_bloom_rows, read_postprocessing_bloom_receipt

    input_id = read(work / "config/accepted-input.json")["input_id"]
    receipt = read_postprocessing_bloom_receipt(destination, input_id, work)
    rows = postprocessing_bloom_rows(receipt, input_id, expected, provenance, candidate_work=work)
    if not rows:
        return rows
    from composition_io import StageIO

    reconstruction = read(work / "config/reconstruction.json")
    projects = reconstruction.get("projects")
    if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
        raise RuntimeError("Bloom batch comparison requires the exact accepted export root")
    export = StageIO(work).resolve(projects[0])
    for path, row in rows.items():
        if row.get("_meta_only") or row.get("_generated_only") or row.get("_generated_meta"):
            continue
        source = export / row["source_asset_path"]
        source_meta = export / (row["source_asset_path"] + ".meta")
        resource = export / row["resource_asset_path"]
        resource_meta = export / (row["resource_asset_path"] + ".meta")
        source_target_meta = Path(project) / (path + ".meta")
        resource_target = Path(project) / ("Assets/WholeGame/" + row["resource_asset_path"].removeprefix("Assets/"))
        resource_target_meta = Path(str(resource_target) + ".meta")
        camera_prefab = export / row["source_camera_prefab_path"] if "source_camera_prefab_path" in row else None
        camera_prefab_meta = Path(str(camera_prefab) + ".meta") if camera_prefab is not None else None
        camera_target = Path(project) / ("Assets/WholeGame/" + row["source_camera_prefab_path"].removeprefix("Assets/")) if camera_prefab is not None else None
        camera_target_meta = Path(str(camera_target) + ".meta") if camera_target is not None else None
        if (
            any(
                item is not None and item.is_symlink()
                for item in (
                    source,
                    source_meta,
                    resource,
                    source_target_meta,
                    resource_target,
                    resource_meta,
                    resource_target_meta,
                    camera_prefab,
                    camera_prefab_meta,
                    camera_target,
                    camera_target_meta,
                )
            )
            or not source.is_file()
            or not source_meta.is_file()
            or not resource.is_file()
            or not source_target_meta.is_file()
            or not resource_target.is_file()
            or ("resource_meta_sha256" in row and (not resource_meta.is_file() or not resource_target_meta.is_file()))
            or (
                camera_prefab is not None
                and (not camera_prefab.is_file() or not camera_target.is_file() or not camera_prefab_meta.is_file() or not camera_target_meta.is_file())
            )
            or sha(source) != row["original_source_sha256"]
            or sha(source_meta) != row["original_meta_sha256"]
            or sha(resource) != row["resource_sha256"]
            or sha(source_target_meta) != row["preserved_meta_sha256"]
            or sha(resource_target) != row["resource_sha256"]
            or (
                "resource_meta_sha256" in row
                and (sha(resource_meta) != row["resource_meta_sha256"] or sha(resource_target_meta) != row["resource_meta_sha256"])
            )
            or (
                camera_prefab is not None
                and (
                    sha(camera_prefab) != row["source_camera_prefab_sha256"]
                    or sha(camera_target) != row["source_camera_prefab_sha256"]
                    or sha(camera_prefab_meta) != row["source_camera_prefab_meta_sha256"]
                    or sha(camera_target_meta) != row["source_camera_prefab_meta_sha256"]
                )
            )
        ):
            raise RuntimeError("Bloom batch source/resource identity changed during comparison: " + path)
    return rows


def _catalog_postprocessing_uber_rows(destination, project, work, expected, provenance):
    work = Path(work)
    marker = Path(destination) / ".rebuild/postprocessing-uber.json"
    if marker.is_symlink():
        raise RuntimeError("Uber batch marker is not a regular file")
    if not marker.exists():
        return {}
    from catalog_rebuild import postprocessing_uber_rows, read_postprocessing_uber_receipt

    input_id = read(work / "config/accepted-input.json")["input_id"]
    receipt = read_postprocessing_uber_receipt(destination, input_id, work)
    rows = postprocessing_uber_rows(receipt, input_id, expected, provenance, candidate_work=work)
    if not rows:
        return rows
    from composition_io import StageIO

    reconstruction = read(work / "config/reconstruction.json")
    projects = reconstruction.get("projects")
    if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
        raise RuntimeError("Uber comparison requires the exact accepted export root")
    export = StageIO(work).resolve(projects[0])
    for path, row in rows.items():
        if row.get("_meta_only") or row.get("_generated_only"):
            continue
        source, meta = export / row["source_asset_path"], export / (row["source_asset_path"] + ".meta")
        resource, resource_meta = export / row["resource_asset_path"], export / (row["resource_asset_path"] + ".meta")
        camera, camera_meta = export / row["source_camera_prefab_path"], export / (row["source_camera_prefab_path"] + ".meta")
        target_meta = Path(project) / (path + ".meta")
        resource_target = Path(project) / ("Assets/WholeGame/" + row["resource_asset_path"].removeprefix("Assets/"))
        resource_target_meta = Path(str(resource_target) + ".meta")
        camera_target = Path(project) / ("Assets/WholeGame/" + row["source_camera_prefab_path"].removeprefix("Assets/"))
        camera_target_meta = Path(str(camera_target) + ".meta")
        paths = (
            source,
            meta,
            resource,
            resource_meta,
            camera,
            camera_meta,
            target_meta,
            resource_target,
            resource_target_meta,
            camera_target,
            camera_target_meta,
        )
        if (
            any(p.is_symlink() for p in paths)
            or any(not p.is_file() for p in paths)
            or sha(source) != row["original_source_sha256"]
            or sha(meta) != row["original_meta_sha256"]
            or sha(resource) != row["resource_sha256"]
            or sha(resource_meta) != row["resource_meta_sha256"]
            or sha(camera) != row["source_camera_prefab_sha256"]
            or sha(camera_meta) != row["source_camera_prefab_meta_sha256"]
            or sha(target_meta) != row["original_meta_sha256"]
            or sha(resource_target) != row["resource_sha256"]
            or sha(resource_target_meta) != row["resource_meta_sha256"]
            or sha(camera_target) != row["source_camera_prefab_sha256"]
            or sha(camera_target_meta) != row["source_camera_prefab_meta_sha256"]
        ):
            raise RuntimeError("Uber batch source/resource identity changed during comparison: " + path)
    return rows


def compare(destination, project, expected, provenance, owns, producers=None, work=None):
    result = {status: [] for status in ("identical", "different", "missing", "extra")}
    work = Path(work or WORK)
    overrides = _catalog_shader_override_rows(destination, project, work, expected, provenance)
    bloom_overrides = _catalog_postprocessing_bloom_rows(destination, project, work, expected, provenance)
    uber_overrides = _catalog_postprocessing_uber_rows(destination, project, work, expected, provenance)
    if set(overrides) & set(bloom_overrides) or set(overrides) & set(uber_overrides):
        raise RuntimeError("Shader batch receipts claim the same path")
    overrides.update(bloom_overrides)
    overrides = merge_postprocessing_rows(overrides, uber_overrides)
    expected = set(expected) | set(overrides)
    export = None
    if overrides:
        from composition_io import StageIO

        reconstruction = read(work / "config/reconstruction.json")
        projects = reconstruction.get("projects")
        if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
            raise RuntimeError("Project comparison requires the exact accepted export root")
        export = StageIO(work).resolve(projects[0])
    # Deep comparison reads actual bytes, never shallow stat/mtime equality.
    for path in sorted(expected):
        target, oracle = destination / path, project / path
        if path in overrides:
            override = overrides[path]
            if override.get("_meta_only"):
                source_oracle = export / (override["source_asset_path"] + ".meta")
                matches = (
                    target.is_file()
                    and not target.is_symlink()
                    and source_oracle.is_file()
                    and not source_oracle.is_symlink()
                    and sha(target) == override["preserved_meta_sha256"]
                    and sha(source_oracle) == override["original_meta_sha256"]
                )
            elif (override.get("_generated_only") or override.get("_generated_meta")) and not override.get("_uber_generated"):
                recipe = read(RECIPE / "shader-postprocessing-bloom-candidate.json")
                from shader_postprocessing_bloom import candidate_root

                candidate_root_path = candidate_root(work, read(work / "config/accepted-input.json")["input_id"], recipe)
                candidate_rel = override["candidate_meta_path"] if override.get("_generated_meta") else override["candidate_path"]
                candidate = candidate_root_path / candidate_rel
                candidate_sha = override["candidate_meta_sha256"] if override.get("_generated_meta") else override["candidate_sha256"]
                matches = (
                    target.is_file() and not target.is_symlink() and candidate.is_file() and sha(target) == candidate_sha and sha(candidate) == candidate_sha
                )
            elif override.get("_bloom_candidate"):
                source_oracle = export / override["source_asset_path"]
                matches = (
                    target.is_file()
                    and not target.is_symlink()
                    and source_oracle.is_file()
                    and not source_oracle.is_symlink()
                    and sha(source_oracle) == override["original_source_sha256"]
                    and sha(target) == override["candidate_shader_sha256"]
                )
            elif override.get("_uber_candidate"):
                recipe = read(RECIPE / "shader-postprocessing-uber-candidate.json")
                from shader_postprocessing_uber import candidate_root

                candidate = candidate_root(work, read(work / "config/accepted-input.json")["input_id"], recipe) / override["candidate_path"]
                matches = (
                    target.is_file()
                    and not target.is_symlink()
                    and candidate.is_file()
                    and sha(target) == override["candidate_shader_sha256"]
                    and sha(candidate) == override["candidate_shader_sha256"]
                )
            elif override.get("_uber_generated"):
                recipe = read(RECIPE / "shader-postprocessing-uber-candidate.json")
                from shader_postprocessing_uber import candidate_root

                candidate = candidate_root(work, read(work / "config/accepted-input.json")["input_id"], recipe) / override["candidate_path"]
                matches = (
                    target.is_file()
                    and not target.is_symlink()
                    and candidate.is_file()
                    and sha(target) == override["candidate_sha256"]
                    and sha(candidate) == override["candidate_sha256"]
                )
            else:
                source_oracle = export / override["source_asset_path"]
                matches = (
                    target.is_file()
                    and not target.is_symlink()
                    and source_oracle.is_file()
                    and not source_oracle.is_symlink()
                    and sha(target) == override["candidate_shader_sha256"]
                    and sha(source_oracle) == override["original_source_sha256"]
                )
            if matches:
                result["identical"].append(path)
            else:
                result["different"].append(path)
        elif not target.is_file() or not oracle.is_file():
            result["missing"].append({"path": path, "destination": not target.is_file(), "project": not oracle.is_file()})
        else:
            # filecmp caches by stat; clear it so repeated comparisons also see
            # changes with preserved size and timestamps.
            filecmp.clear_cache()
            result["identical" if filecmp.cmp(target, oracle, shallow=False) else "different"].append(path)
    for target in sorted(destination.rglob("*")):
        if target.is_file():
            path = target.relative_to(destination).as_posix()
            # R9's editor caches are not project inputs and belong to no step.
            if path == ".port-input.json" or path.startswith(".rebuild/") or path.split("/", 1)[0] in UNITY_OWNED:
                continue
            if path not in overrides and (
                path not in provenance or (owns(path) and path not in expected and (producers is None or provenance[path]["producer"] in producers))
            ):
                result["extra"].append(path)
    result["counts"] = {status: len(result[status]) for status in ("identical", "different", "missing", "extra")}
    result["equal"] = not any(result[status] for status in ("different", "missing", "extra"))
    return result


def rebuild_step(step, dest=None, compare_only=False, work=None):
    work = Path(work or WORK).resolve()
    if step == "unity-build":
        from unity_rebuild import unity_build

        input_id = read(work / "config/accepted-input.json")["input_id"]
        if not re.fullmatch("[0-9a-f]{64}", input_id):
            raise RuntimeError("Invalid accepted input ID")
        destination = safe_destination(dest, input_id, work)
        provenance = read(work / "receipts/provenance-map.json")
        for path in provenance:
            relative_path(path)
        return unity_build(destination, work, input_id, provenance, compare_only)
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
    expected = selected_paths(owner, provenance)
    if step == "validate-bindings":
        return validate_bindings(destination, work, input_id, provenance=provenance)
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
        build_result = owner.build(destination, work, input_id, expected, provenance)
    result = compare(
        destination, work / "lab-project", expected, provenance, (lambda path: path in expected) if owner.evidence else owner.owns, owner.producers, work=work
    )
    if not compare_only and build_result is not None:
        result["replay"] = build_result
        if build_result.get("blocked"):
            result["equal"] = False
    return result


def rebuild_action(step, dest=None, compare_only=False, work=None):
    result = rebuild_step(step, dest, compare_only, work)
    print(json.dumps(result, indent=2))
    if not result["equal"]:
        raise SystemExit(1)
