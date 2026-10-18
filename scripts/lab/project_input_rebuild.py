"""Public settings, historical authored editors, explicit importer and original OBJ replay."""

from pathlib import Path

from common import RECIPE, ROOT, game, read, sha
from composition_io import StageIO


def membership(recipe):
    return (
        set(recipe["settings_templates"])
        | {row["path"] for row in recipe["editors"]}
        | {
            "ProjectSettings/InputManager.asset",
            "Assets/LabLoadingScene/NovaInputBridge.cs.meta",
            "Assets/Recovered/geometry.obj",
        }
    )


PROJECT_INPUT_PATHS = frozenset(membership(read(RECIPE / "project-inputs.json")))


def project_inputs(destination, work, input_id, expected, provenance):
    import UnityPy

    from catalog_rebuild import verify_outputs
    from nova_bridge import insert_axes, nova_axes
    from prepare import export_geometry
    from rebuild import relative_path

    recipe = read(RECIPE / "project-inputs.json")
    if recipe["schema"] != 1 or recipe["input_id"] != input_id or membership(recipe) != expected:
        raise RuntimeError("Project input recipe/provenance membership or accepted input differs")
    io = StageIO(work, destination)
    io.preflight()
    for path in recipe["settings_templates"]:
        relative_path(path)
        if Path(path).parent.as_posix() != "ProjectSettings":
            raise RuntimeError("Unexpected settings template")
        io.apply(destination / path, copy=ROOT / "smoke" / path)
    for row in recipe["editors"]:
        relative_path(row["template"])
        relative_path(row["path"])
        source = RECIPE / row["template"]
        if not source.resolve().is_relative_to(RECIPE.resolve()) or sha(source) != row["sha256"]:
            raise RuntimeError("Historical authored editor template drift")
        io.apply(destination / row["path"], copy=source)
    io.apply(destination / "ProjectSettings/InputManager.asset", insert_axes((ROOT / "smoke/ProjectSettings/InputManager.asset").read_text(), nova_axes()))
    guids = read(RECIPE / "project-layout.json")["runtime_source_guids"]
    guid = guids["runtime/input/NovaInputBridge.cs"]
    import re

    if not re.fullmatch("[0-9a-f]{32}", guid):
        raise RuntimeError("Invalid Nova input script GUID")
    io.apply(destination / "Assets/LabLoadingScene/NovaInputBridge.cs.meta", (RECIPE / "templates/ordered-script.meta").read_text().format(guid=guid))
    geometry = recipe["geometry"]
    relative_path(geometry["bundle"])
    base = game(work)
    bundle = base / geometry["bundle"]
    inventory = read(work / "inventory/files.json")
    if inventory["input_id"] != input_id or read(work / "config/accepted-input.json")["input_id"] != input_id:
        raise RuntimeError("Geometry requires accepted input")
    identities = [row["sha256"] for row in inventory["files"] if row["path"] == geometry["bundle"]]
    if identities != [geometry["bundle_sha256"]] or not bundle.resolve().is_relative_to(base.resolve()) or sha(bundle) != geometry["bundle_sha256"]:
        raise RuntimeError("Geometry source bundle drift")
    objects = [obj for obj in UnityPy.load(str(bundle)).objects if obj.type.name == "Mesh" and obj.path_id == geometry["path_id"]]
    if len(objects) != 1:
        raise RuntimeError("Geometry object identity ambiguous")
    mesh = objects[0].read()
    if mesh.m_Name != geometry["mesh_name"]:
        raise RuntimeError("Geometry mesh name drift")
    target = destination / "Assets/Recovered/geometry.obj"
    io.apply(target, export_geometry(mesh))
    if io.sha(target) != geometry["output_sha256"]:
        raise RuntimeError("Geometry serializer drift")
    # Includes full importer bytes, not merely GUID/order, and every selected template.
    verify_outputs(io, expected, provenance)
    io.write(destination / ".rebuild/project-inputs-complete.json", dict(input_id=input_id))
    io.flush()
