"""Host-only R3/R4 replay over the catalog analysis regenerated in the destination (J725)."""

from pathlib import Path
import re

from common import RECIPE, read, sha
from composition_io import StageIO


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


def verify_outputs(io, expected, provenance):
    for path in sorted(expected):
        target = io.project / path
        row = provenance[path]
        if not io.is_file(target) or io.sha(target) != row["sha256"] or len(io.read_bytes(target)) != row["size"]:
            raise RuntimeError("Rebuilt catalog output differs from provenance: " + path)
    io.flush()


def catalog_closure(destination, work, input_id, expected, provenance):
    from whole_catalog import prepare_integration

    config = destination / ".rebuild/composition/scene-probe-build.json"
    if not config.is_file():
        raise RuntimeError("Catalog closure requires destination composition config from R2")
    attempt = bootstrap_identity(work, input_id)
    io = CatalogIO(work, destination, input_id)
    prepare_integration(io, attempt=attempt)
    verify_outputs(io, expected, provenance)
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
    verify_outputs(io, expected, provenance)
    io.write(destination / ".rebuild/dependencies-complete.json", dict(input_id=input_id))
    io.flush()
