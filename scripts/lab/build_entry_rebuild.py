"""Host-only R7/R8 replay; no editor import, build, or live-project fallback."""

from pathlib import Path

from catalog_rebuild import CatalogIO
from common import RECIPE, game, read, sha
from scene_rebuild import finish, require_step


class BuildEntryIO(CatalogIO):
    def __init__(self, work, destination, input_id):
        from rebuild import relative_path

        recipe = read(RECIPE / "build-entry-inputs.json")
        required = {"CharacterBody.cs", "HealthComponent.cs", "GlobalEventManager.cs", "contracts.json", "bootstrap-identity.json"}
        if recipe["schema"] != 1 or recipe["input_id"] != input_id or set(recipe["files"]) != required:
            raise RuntimeError("Build-entry pinned inputs require accepted input and complete membership")
        payload = {}
        for name, row in recipe["files"].items():
            relative_path(row["path"])
            source = Path(work) / row["path"]
            if not source.resolve().is_relative_to(Path(work).resolve()) or sha(source) != row["sha256"]:
                raise RuntimeError("Recorded build-entry input drift: " + name)
            payload[name] = source.read_bytes()
        super().__init__(work, destination, input_id)
        self.inputs = self.project / ".rebuild/build-entry-inputs"
        for name, data in payload.items():
            self.apply(self.inputs / name, data)

    def manifest(self):
        from rebuild import relative_path

        pointer = self.read(self.catalog() / "integration-latest.json")["path"]
        if not pointer.startswith("destination/"):
            raise RuntimeError("Build entries require regenerated R3 manifest")
        relative = pointer.removeprefix("destination/")
        relative_path(relative)
        path = self.project / relative / "manifest.json"
        if not path.is_relative_to(self.catalog()):
            raise RuntimeError("Manifest escapes regenerated catalog inputs")
        manifest = self.read(path)
        if manifest["input_id"] != self.read(self.work / "config/accepted-input.json")["input_id"]:
            raise RuntimeError("Build-entry manifest input mismatch")
        return manifest


def build_entries(destination, work, input_id, expected, provenance):
    from build import generate_content_recipe, generate_runtime_config
    from whole_catalog import generate_build_bootstrap, generate_build_maps

    require_step(destination, "source-scenes", input_id)
    io = BuildEntryIO(work, destination, input_id)
    io.preflight()
    manifest = io.manifest()
    contract = io.read(io.catalog() / "original-catalog-contract.json")
    if contract["input_sha256"] != sha(game(work) / "Risk of Rain 2_Data/Managed/RoR2.dll"):
        raise RuntimeError("Original visual references require accepted assembly")
    generate_runtime_config(destination, io=io)
    generate_content_recipe(io=io)
    export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0])
    for path in sorted(expected):
        if path.endswith(".anim"):
            # Reconstruct from the accepted export, including clips absent from R2/R3.
            source = export / path.replace("Assets/WholeGame/", "Assets/", 1)
            if not path.startswith("Assets/WholeGame/") or not source.resolve().is_relative_to(export.resolve()):
                raise RuntimeError("Animation source escapes accepted export")
            io.apply(destination / path, copy=source)
    generate_build_maps(io, manifest, contract, io.inputs / "CharacterBody.cs")
    # Only the historical attempt identity comes from this pinned record. Locations,
    # keys, pool identities and closure are regenerated in the destination by R3.
    identity = io.read(io.inputs / "bootstrap-identity.json")
    if identity["input_id"] != input_id:
        raise RuntimeError("Bootstrap identity input mismatch")
    generate_build_bootstrap(io, dict(manifest, attempt=identity["attempt"]), io.read(io.catalog() / "reconciled-closure.json"))
    finish(io, "build-entries", input_id, expected, provenance)


def runtime_sources(destination, work, input_id, expected, provenance):
    from build import runtime_sources as selection, stage_android_assets
    from whole_catalog import stage_build_sources

    require_step(destination, "build-entries", input_id)
    io = BuildEntryIO(work, destination, input_id)
    io.preflight()
    stage_build_sources(io, selection(), io.manifest(), io.read(io.inputs / "contracts.json"))
    stage_android_assets(destination, io=io)
    finish(io, "runtime-sources", input_id, expected, provenance)


def validate_bindings(destination, work, input_id, expected=None, provenance=None):
    """Fail closed on missing receipts/targets; Unity graph reserialization belongs to R9."""
    from rebuild import relative_path

    require_step(destination, "runtime-sources", input_id)
    composition = destination / ".rebuild/composition"
    missing_records = list(composition.rglob("missing-runtime-bindings.json"))
    dependency_records = list(composition.rglob("dependency-stage-*/receipt.json"))
    if len(missing_records) != 1 or len(dependency_records) != 1:
        raise RuntimeError("Binding validation requires unique regenerated R2 and R4 binding receipts")
    dependencies = read(dependency_records[0])
    if dependencies["input_id"] != input_id:
        raise RuntimeError("Binding receipt input mismatch")
    bindings = read(missing_records[0])
    deferred = dependencies.get("deferred_to_later_steps")
    if not isinstance(bindings, list) or not bindings or not isinstance(deferred, list):
        raise RuntimeError("Invalid or empty binding receipt")
    recipe = read(RECIPE / "rebuild-binding-targets.json")
    if recipe["schema"] != 1 or recipe["input_id"] != input_id or not recipe["targets"]:
        raise RuntimeError("J565 binding membership requires accepted input")
    if not set(recipe["targets"]) <= set(bindings):
        raise RuntimeError("Regenerated R2 receipt omits J565 bindings")
    required = set(recipe["targets"]) | set(bindings) | set(deferred)
    for path in required:
        relative_path(path)
        if path not in provenance:
            raise RuntimeError("Binding target has no provenance: " + path)
    missing = sorted(path for path in required if not (destination / path).is_file())
    graph_receipt = destination / ".rebuild/stage-variants/result.json"
    if not graph_receipt.is_file() or read(graph_receipt).get("input_id") != input_id:
        raise RuntimeError("Binding validation requires R5 graph receipt")
    graphs = read(graph_receipt).get("unity_import_deferred", [])
    for path in graphs:
        relative_path(path)
        if provenance.get(path, {}).get("producer") != "unity-generated" or not (destination / path).is_file():
            raise RuntimeError("Invalid R9 graph obligation: " + path)
    return dict(equal=not missing, checked=len(required), r2_bindings=len(bindings), r4_deferred=len(deferred), missing=missing, unity_import_deferred=graphs)
