"""Host-only R3/R4 replay over the catalog analysis regenerated in the destination (J725)."""

from pathlib import Path
import hashlib
import json
import re

from common import RECIPE, ROOT, read, sha
from composition_io import StageIO


SHADER_OVERRIDE_ROWS = (
    (
        16022,
        "41e90cbc5ad198a438128b019f8d8553",
        "RoR2/Base/Shaders/HGOutlineHighlight.shader",
        "Assets/RoR2/Base/Shaders/PostProcess/HGOutlineHighlight.shader",
    ),
    (15950, "c14b6abb309b8c246add9e94a6920d7f", "RoR2/Base/Shaders/RampFog.shader", "Assets/RoR2/Base/Shaders/CustomPostProcess/RampFog.shader"),
)
SHADER_OVERRIDE_GENERATORS = {
    16022: (
        "shader_outline.py",
        "recipe/shader-outline-candidate.json",
        "private-outline-highlight-generated-candidate-r1",
        "manifest.json",
        "sources/OutlineHighlightCandidate.shader",
        "generated_shader_path",
        "Hopoo Games/Internal/Outline Highlight",
        -5736718617091362218,
    ),
    15950: (
        "shader_ramp_fog.py",
        "recipe/shader-ramp-fog-candidate.json",
        1,
        "candidate.json",
        "sources/RampFogCandidate.shader",
        "generated_shader",
        "Hidden/PostProcess/RampFog",
        2910825169780710437,
    ),
}


def read_local_shader_override_selector(work, input_id):
    """Read the optional, input-bound local activation switch; absence means off."""
    work = Path(work).absolute()
    path = work / "config/shader-catalog-overrides.json"
    if work.is_symlink() or path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("Local shader override selector path may not contain symlinks")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 4096 or not path.resolve().is_relative_to(work.resolve()):
        raise RuntimeError("Local shader override selector is not a bounded regular file under work/")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Local shader override selector is malformed") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "input_id", "enabled"}
        or data.get("schema") != "whole-catalog-shader-overrides-activation-r1"
        or data.get("input_id") != input_id
        or type(data.get("enabled")) is not bool
    ):
        raise RuntimeError("Local shader override selector has an unknown schema or input")
    return {**data, "sha256": hashlib.sha256(raw).hexdigest()}


def shader_override_rows(receipt, input_id, expected, provenance, candidate_work=None):
    """Validate the only two authored shader exceptions to byte-identical replay."""
    if receipt is None:
        return {}
    candidate_work = Path(candidate_work or ROOT / "work")
    selector = read_local_shader_override_selector(candidate_work, input_id)
    if (
        selector is None
        or selector["enabled"] is not True
        or receipt.get("selector_path") != "work/config/shader-catalog-overrides.json"
        or receipt.get("selector_sha256") != selector["sha256"]
    ):
        raise RuntimeError("Shader override receipt does not match the current local selector")
    if (
        receipt.get("schema") != "whole-catalog-shader-override-receipt-r2"
        or receipt.get("input_id") != input_id
        or receipt.get("enabled") is not True
        or receipt.get("unity_compiled") is not False
        or receipt.get("android_accepted") is not False
        or receipt.get("visual_parity_proven") is not False
    ):
        raise RuntimeError("Shader override receipt is not a qualified source-only receipt")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != len(SHADER_OVERRIDE_ROWS):
        raise RuntimeError("Shader override receipt must contain exactly the two qualified roots")
    result = {}
    for row, (location_id, guid, primary_key, source_path) in zip(rows, SHADER_OVERRIDE_ROWS, strict=True):
        target = "Assets/WholeGame/" + source_path.removeprefix("Assets/")
        generator, generator_recipe, schema, manifest_name, shader_name, manifest_path_field, shader_name_value, object_path_id = SHADER_OVERRIDE_GENERATORS[
            location_id
        ]
        if (
            row.get("location_id") != location_id
            or row.get("guid") != guid
            or row.get("type") != "UnityEngine.Shader, UnityEngine.CoreModule, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null"
            or row.get("primary_key") != primary_key
            or row.get("source_asset_path") != source_path
            or row.get("target") != target
            or not isinstance(row.get("candidate_shader_sha256"), str)
            or row.get("generator") != generator
            or row.get("generator_recipe") != generator_recipe
            or row.get("generator_sha256") != sha(ROOT / "scripts/lab" / generator)
            or row.get("generator_recipe_sha256") != sha(ROOT / generator_recipe)
        ):
            raise RuntimeError("Shader override row differs from its exact catalog identity or provenance: " + str(location_id) + " " + repr(row))
        # These two catalog-added shaders are not members of the original
        # provenance map. If a future map does contain one, it must agree with
        # the exact receipt rather than widening this exception.
        source_provenance = provenance.get(target)
        if source_provenance is not None and (
            source_provenance.get("sha256") != row.get("original_source_sha256")
            or source_provenance.get("producer") != "repo-builder"
            or not any(item.get("function") == "whole_catalog.prepare_integration" for item in source_provenance.get("evidence", []))
        ):
            raise RuntimeError("Shader override source provenance conflicts with its receipt: " + target)
        meta_provenance = provenance.get(target + ".meta")
        if meta_provenance is not None and meta_provenance.get("sha256") != row.get("original_meta_sha256"):
            raise RuntimeError("Shader override metadata provenance conflicts with its receipt: " + target + ".meta")
        for field in (
            "original_source_sha256",
            "original_meta_sha256",
            "preserved_meta_sha256",
            "generator_sha256",
            "generator_recipe_sha256",
            "candidate_manifest_sha256",
            "candidate_shader_sha256",
        ):
            if not isinstance(row.get(field), str) or len(row[field]) != 64 or any(char not in "0123456789abcdef" for char in row[field]):
                raise RuntimeError("Shader override receipt has an invalid digest: " + field)
        if type(row.get("preserved_meta_bytes")) is not int or row["preserved_meta_bytes"] < 0:
            raise RuntimeError("Shader override receipt has an invalid preserved metadata size")
        recipe = read(ROOT / generator_recipe)
        stable_output = recipe.get("stable_output")
        if not isinstance(stable_output, str) or "{input_id}" not in stable_output:
            raise RuntimeError("Shader override generator recipe lacks an input-bound output path")
        expected_root = "work/" + stable_output.format(input_id=input_id)
        manifest_rel = row.get("candidate_manifest_path")
        shader_rel = row.get("candidate_shader_path")
        if manifest_rel != expected_root + "/" + manifest_name or shader_rel != expected_root + "/" + shader_name:
            raise RuntimeError("Shader override candidate path differs from its current recipe")
        manifest_path = candidate_work / Path(manifest_rel).relative_to("work")
        shader_path = candidate_work / Path(shader_rel).relative_to("work")
        if (
            any(path.is_symlink() for path in (*manifest_path.parents, manifest_path, *shader_path.parents, shader_path))
            or not manifest_path.is_file()
            or not shader_path.is_file()
            or sha(manifest_path) != row.get("candidate_manifest_sha256")
            or sha(shader_path) != row.get("candidate_shader_sha256")
            or shader_path.stat().st_size != row.get("candidate_shader_bytes")
        ):
            raise RuntimeError("Shader override candidate output changed after staging")
        candidate_manifest = read(manifest_path)
        if (
            candidate_manifest.get("schema") != schema
            or candidate_manifest.get("generator_sha256") != row["generator_sha256"]
            or candidate_manifest.get("recipe_sha256") != row["generator_recipe_sha256"]
            or candidate_manifest.get("source", {}).get("input_id") != input_id
            or candidate_manifest.get(manifest_path_field) != shader_name
            or candidate_manifest.get("generated_shader_sha256") != row["candidate_shader_sha256"]
        ):
            raise RuntimeError("Shader override candidate manifest no longer matches its input")
        if location_id == 16022:
            candidate_identity_matches = (
                candidate_manifest.get("success") is True
                and candidate_manifest.get("object_path_id") == object_path_id
                and candidate_manifest.get("source", {}).get("catalog_key") == guid
                and candidate_manifest.get("source", {}).get("catalog_location") == location_id
                and candidate_manifest.get("source", {}).get("asset_path") == source_path
            )
        else:
            candidate_identity_matches = (
                candidate_manifest.get("kind") == "local-source-bound-ramp-fog-candidate"
                and candidate_manifest.get("source", {}).get("shader_path_id") == object_path_id
                and candidate_manifest.get("source", {}).get("shader_name") == shader_name_value
            )
        if not re.match(rb"\s*Shader\s+" + re.escape(json.dumps(shader_name_value).encode()) + rb"\s*\{", shader_path.read_bytes()):
            raise RuntimeError("Shader override candidate declaration changed")
        if not candidate_identity_matches:
            raise RuntimeError("Shader override candidate identity changed")
        result[target] = row
        result[target + ".meta"] = {**row, "_meta_only": True}
    return result


def read_shader_override_receipt(project, input_id, work):
    """Load a persisted marker only when its input, selector, and receipt join."""
    project = Path(project)
    work = Path(work)
    marker_path = project / ".rebuild/catalog-shader-overrides.json"
    if marker_path.is_symlink():
        raise RuntimeError("Catalog shader override marker is not a regular file")
    if not marker_path.exists():
        return None
    if any(path.is_symlink() for path in (marker_path, *marker_path.parents)) or not marker_path.is_file():
        raise RuntimeError("Catalog shader override marker is not a regular file")
    marker = read(marker_path)
    if (
        set(marker) != {"schema", "input_id", "receipt_path", "receipt_sha256", "selector_path", "selector_sha256"}
        or marker.get("schema") != "whole-catalog-shader-override-marker-r2"
        or marker.get("input_id") != input_id
    ):
        raise RuntimeError("Catalog shader override marker belongs to a different input or schema")
    relative = Path(marker.get("receipt_path", ""))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(marker.get("receipt_path", "")):
        raise RuntimeError("Catalog shader override receipt path is unsafe")
    receipt_path = project / relative
    if (
        not receipt_path.resolve().is_relative_to(project.resolve())
        or any(path.is_symlink() for path in (receipt_path, *receipt_path.parents))
        or not receipt_path.is_file()
        or sha(receipt_path) != marker.get("receipt_sha256")
    ):
        raise RuntimeError("Catalog shader override receipt is missing or changed")
    selector = read_local_shader_override_selector(work, input_id)
    receipt = read(receipt_path)
    if (
        selector is None
        or selector["enabled"] is not True
        or marker.get("selector_path") != "work/config/shader-catalog-overrides.json"
        or marker.get("selector_sha256") != selector["sha256"]
        or receipt.get("selector_path") != marker["selector_path"]
        or receipt.get("selector_sha256") != marker["selector_sha256"]
    ):
        raise RuntimeError("Catalog shader override marker does not match the current local selector")
    return receipt


def bootstrap_identity(work, input_id):
    """The historical generation identity, recorded publicly in the build-entry recipe (J597)."""
    recipe = read(RECIPE / "build-entry-inputs.json")
    if recipe["schema"] != 2 or recipe["input_id"] != input_id:
        raise RuntimeError("Bootstrap identity requires accepted input")
    attempt = recipe.get("bootstrap_attempt", "")
    if not re.fullmatch(r"integration-[A-Za-z0-9._-]+", attempt):
        raise RuntimeError("Invalid bootstrap identity")
    return attempt


class CatalogIO(StageIO):
    def __init__(self, work, destination, input_id):
        super().__init__(work, destination)
        from catalog_analysis import ensure

        if read(self.work / "config/accepted-input.json")["input_id"] != input_id:
            raise RuntimeError("Catalog rebuild inputs require accepted input")
        # Audit, native inventory and reconcile run once per destination from the installation.
        self.analysis = ensure(self.work, self.project, input_id)

    def runtime_guid(self, name):
        import re
        from pathlib import PurePosixPath

        guids = read(RECIPE / "project-layout.json")["runtime_source_guids"]
        values = [guid for path, guid in guids.items() if PurePosixPath(path).name == name]
        if len(values) != 1 or not re.fullmatch("[0-9a-f]{32}", values[0] or ""):
            raise RuntimeError("Missing authored script identity: " + name)
        return values[0]

    def label(self, path):
        path = Path(path)
        return "destination/" + str(path.relative_to(self.project)) if path.is_relative_to(self.project) else super().label(path)

    def catalog(self):
        return self.analysis


def verify_outputs(io, expected, provenance, shader_overrides=None, input_id=None):
    overrides = shader_override_rows(shader_overrides, input_id, expected, provenance, candidate_work=io.work)
    expected = set(expected) | set(overrides)
    export = None
    if overrides:
        reconstruction = io.read(io.work / "config/reconstruction.json")
        projects = reconstruction.get("projects")
        if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], str):
            raise RuntimeError("Shader override verification requires the exact accepted export root")
        export = io.resolve(projects[0])
    for path in sorted(expected):
        target = io.project / path
        row = provenance.get(path, {})
        data = io.read_bytes(target) if io.is_file(target) else None
        if path in overrides:
            override = overrides[path]
            meta = io.project / (path + ".meta")
            if override.get("_meta_only"):
                if data is None or io.sha(target) != override["preserved_meta_sha256"] or len(data) != override["preserved_meta_bytes"]:
                    raise RuntimeError("Qualified shader override metadata differs from its exact receipt: " + path)
            else:
                source = export / override["source_asset_path"]
                source_meta = export / (override["source_asset_path"] + ".meta")
                if (
                    source.is_symlink()
                    or source_meta.is_symlink()
                    or not source.is_file()
                    or not source_meta.is_file()
                    or io.sha(source) != override["original_source_sha256"]
                    or io.sha(source_meta) != override["original_meta_sha256"]
                    or data is None
                    or io.sha(target) != override["candidate_shader_sha256"]
                    or len(data) != override["candidate_shader_bytes"]
                    or not io.is_file(meta)
                    or io.sha(meta) != override["preserved_meta_sha256"]
                ):
                    raise RuntimeError("Qualified shader override does not match its exact builder receipt: " + path)
        elif data is None or io.sha(target) != row["sha256"] or len(data) != row["size"]:
            raise RuntimeError("Rebuilt catalog output differs from provenance: " + path)
    io.flush()


def catalog_closure(destination, work, input_id, expected, provenance):
    from whole_catalog import prepare_integration

    config = destination / ".rebuild/composition/scene-probe-build.json"
    if not config.is_file():
        raise RuntimeError("Catalog closure requires destination composition config from R2")
    attempt = bootstrap_identity(work, input_id)
    io = CatalogIO(work, destination, input_id)
    override_receipt = prepare_integration(io, attempt=attempt)
    verify_outputs(io, expected, provenance, shader_overrides=override_receipt, input_id=input_id)
    io.write(destination / ".rebuild/catalog-closure-complete.json", dict(input_id=input_id))
    io.flush()


def dependencies(destination, work, input_id, expected, provenance):
    from composition_migration import stage_missing_sources

    marker = destination / ".rebuild/catalog-closure-complete.json"
    if not marker.is_file() or read(marker)["input_id"] != input_id:
        raise RuntimeError("Run catalog-closure after composition before dependencies")
    from rebuild import STEPS

    io = CatalogIO(work, destination, input_id)
    # Required build entries that R5–R8 builders own cannot exist yet; validate-bindings checks them.
    built = {function for name in ("catalog-closure", "dependencies") for function in STEPS[name].evidence}
    io.deferred = frozenset(
        path
        for path, row in provenance.items()
        if row.get("producer") == "repo-builder" and row.get("evidence") and not any(item.get("function") in built for item in row["evidence"])
    )
    config = io.output(io.work / "scene-probe-build.json")
    if not config.is_file():
        raise RuntimeError("Dependencies require destination composition config from R2")
    stage_missing_sources(io)
    override_receipt = read_shader_override_receipt(destination, input_id, work)
    verify_outputs(io, expected, provenance, shader_overrides=override_receipt, input_id=input_id)
    io.write(destination / ".rebuild/dependencies-complete.json", dict(input_id=input_id))
    io.flush()
