"""R5/R6 host replay, with retained analysis explicitly pinned, never inferred live."""

from pathlib import Path
import re

from catalog_rebuild import CatalogIO, verify_outputs
from common import RECIPE, game, read, sha


class SceneIO(CatalogIO):
    def __init__(self, work, destination, input_id, provenance=None):
        recipe = read(RECIPE / "scene-rebuild-inputs.json")
        if recipe["schema"] != 2 or recipe["input_id"] != input_id:
            raise RuntimeError("Scene rebuild inputs require accepted input")
        if recipe["files"]:
            raise RuntimeError("Scene rebuild reads no retained analysis input (J597)")
        from rebuild import relative_path

        payload = {}
        for name, row in recipe["files"].items():
            relative_path(name)
            relative_path(row["path"])
            source = Path(work) / row["path"]
            if not source.resolve().is_relative_to(Path(work).resolve()) or sha(source) != row["sha256"]:
                raise RuntimeError("Recorded scene input drift: " + name)
            payload[name] = source.read_bytes()
        identities = recipe["script_identities"]
        relative_path(identities["path"])
        payload[identities["path"]] = script_identities(work, identities["assembly"]).encode()
        super().__init__(work, destination, input_id)
        self.provenance = provenance or {}
        self.unity_deferred = []
        self.graphs = None
        for name, content in payload.items():
            # Pin reads in memory as well as retaining them beneath destination.
            self.apply(self.work / name, content)

    def accepted(self, path, digest):
        relative = str(Path(path).relative_to(self.project))
        if self.graphs is not None and relative in self.graphs:
            # Before R9 a stage graph is exactly its export copy; Unity's reserialization is an R9 obligation.
            if digest != self.graphs[relative] or self.sha(path) != digest:
                return False
            if self.provenance.get(relative, {}).get("producer") == "unity-generated":
                self.unity_deferred.append(relative)
            return True
        # The frozen baseline hashes the editor's re-serialized form of unity-generated files;
        # before R9 imports the destination, require the export copy R2 placed instead.
        if super().accepted(path, digest):
            return True
        relative = str(Path(path).relative_to(self.project))
        row = self.provenance.get(relative, {})
        if row.get("producer") != "unity-generated" or row.get("sha256") != digest:
            return False
        sources = {item.get("export_path") for item in row.get("evidence", [])} - {None}
        if len(sources) != 1:
            return False
        export = self.resolve(self.read(self.work / "config/reconstruction.json")["projects"][0])
        if self.read_bytes(path) != (export / sources.pop()).read_bytes():
            return False
        self.unity_deferred.append(relative)
        return True


def script_identities(work, assembly):
    """Regenerate the MapZone script lookup from the installation instead of a retained editor list (J597)."""
    from script_identity import identity_rows

    rows = [row for row in read(RECIPE / "original-assemblies.json")["assemblies"] if row["source"] == assembly]
    if len(rows) != 1:
        raise RuntimeError("Script identities require one R1 importer for " + assembly)
    data = game(work) / "Risk of Rain 2_Data"
    if sha(data / "Managed" / assembly) != rows[0]["sha256"]:
        raise RuntimeError("Script identities require the accepted " + assembly)
    return identity_rows(data, assembly, rows[0]["guid"])


def node_graphs(io, export):
    """Destination stage graphs and their export-copy hashes, replacing the frozen code-build baseline (J597).

    A graph is an exported asset whose script is RoR2.Navigation.NodeGraph; its identity
    comes from the R1 importer GUID and Unity's script file ID rule (`script_identity`).
    """
    from script_identity import script_file_id

    rows = [row for row in read(RECIPE / "original-assemblies.json")["assemblies"] if row["source"] == "RoR2.dll"]
    if len(rows) != 1:
        raise RuntimeError("Stage graphs require the R1 RoR2.dll importer")
    needle = f"m_Script: {{fileID: {script_file_id('RoR2.Navigation', 'NodeGraph')}, guid: {rows[0]['guid']}, type: 3}}".encode()
    graphs = {}
    for source in sorted((export / "Assets").rglob("*.asset")):
        with source.open("rb") as stream:
            if needle not in stream.read(4096):
                continue
        relative = "Assets/WholeGame/" + str(source.relative_to(export / "Assets"))
        if io.is_file(io.project / relative):
            graphs[relative] = sha(source)
    if not graphs:
        raise RuntimeError("No exported stage graph is staged in the destination")
    return graphs


def require_step(destination, name, input_id):
    marker = destination / (".rebuild/" + name + "-complete.json")
    if not marker.is_file() or read(marker).get("input_id") != input_id:
        raise RuntimeError("Run " + name + " before this rebuild step")
    if not (destination / ".rebuild/composition/scene-probe-build.json").is_file():
        raise RuntimeError("Scene rebuild requires destination composition config from R2")


def finish(io, name, input_id, expected, provenance):
    verify_outputs(io, expected, provenance)
    io.write(io.project / (".rebuild/" + name + "-complete.json"), dict(input_id=input_id))
    io.flush()


def stage_variants(destination, work, input_id, expected, provenance):
    from stage_variants import stage

    require_step(destination, "dependencies", input_id)
    io = SceneIO(work, destination, input_id, provenance)
    io.preflight()
    stage(io)
    finish(io, "stage-variants", input_id, expected, provenance)


def source_scenes(destination, work, input_id, expected, provenance):
    from source_scene_candidate import SCENES, prepare

    require_step(destination, "stage-variants", input_id)
    io = CatalogIO(work, destination, input_id)
    io.preflight()
    # Wwise is already transformed and placed by R1. The real action's separate
    # stage_unavailable_audio call is deliberately absent from this coordinator.
    prepare(tuple(SCENES), io)
    finish(io, "source-scenes", input_id, expected, provenance)


def replay_variants(io):
    from composition_migration import scene_contract
    from nova_bridge import stage_first_stage_geometry
    from stage_variants import VARIANTS, SOURCE_SHA256, scene_root, include_runtime_graph_roots
    from whole_catalog import original_stage_contexts

    project = io.project
    input_id = io.read(io.work / "config/accepted-input.json")["input_id"]
    if io.read(project / ".port-input.json")["input_id"] != input_id:
        raise RuntimeError("Stage project belongs to a different accepted game input")
    export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0])
    config_path = project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
    recipe_path = io.work / "scene-probe-build.json"
    config, recipe = io.read(config_path), io.read(recipe_path)
    accepted = io.graphs = node_graphs(io, export)
    accepted_lower = {path.casefold(): digest for path, digest in accepted.items()}
    if len(accepted_lower) != len(accepted):
        raise RuntimeError("Ambiguous stage graph paths")
    out = project / ".rebuild/stage-variants"
    stages = {row["name"]: row for row in config["integratedStages"]}
    decks = {row["name"]: row for row in config["stageCombatDecks"]}
    if len(stages) != len(config["integratedStages"]) or len(decks) != len(config["stageCombatDecks"]):
        raise RuntimeError("Duplicate existing stage contract")
    pending = []
    for name, digest in VARIANTS.items():
        relative = "Assets/WholeGame/RoR2/" + scene_root(name) + "/Scenes/" + name + "/" + name + ".unity"
        target = project / relative
        # R2 may already carry final config rows, but not their later scene bodies.
        # Pending is determined from destination bytes, never the oracle's config.
        if name in stages and io.is_file(target) and io.sha(target) == digest:
            continue
        pending.append(name)
        source = export / relative.replace("Assets/WholeGame/", "Assets/", 1)
        if name in SOURCE_SHA256 and sha(source) != SOURCE_SHA256[name]:
            raise RuntimeError("Original stage source changed: " + name)
        spec = stage_first_stage_geometry(
            project / "Assets/LabLoadingScene",
            out,
            original_name=True,
            scene_name=name,
            map_zones=True,
            presentation=True,
            billboards=True,
            scene_root=scene_root(name),
            io=io,
        )
        generated = project / "Assets/LabLoadingScene/StageGeometry" / (name + ".unity")
        if io.sha(generated) != digest:
            raise RuntimeError("Recovered scene variant differs from measured projection: " + name)
        text, counts, removed = scene_contract(source.read_text(), io.read_text(generated))
        if text != io.read_text(generated) or removed:
            raise RuntimeError("Recovered scene has an unexpected callback or network owner: " + name)
        for key in ("previewCallbacks", "mapZoneCount", "mapZoneNetworkObjects"):
            if spec[key] != counts[key]:
                raise RuntimeError("Scene contract report differs: " + name + "/" + key)
        for key in ("previewNames", "mapZoneActiveNames", "emptyMeshPaths", "emptyColliderPaths"):
            if sorted(spec[key]) != sorted(counts[key]):
                raise RuntimeError("Scene contract report differs: " + name + "/" + key)
            spec[key] = sorted(counts[key])
        for key in ("groundGraph", "airGraph"):
            # Resolve case through the export's graph membership, not a filesystem guess.
            paths = [path for path in accepted if path.casefold() == spec[key].casefold()]
            if len(paths) != 1 or not io.accepted(project / paths[0], accepted_lower[spec[key].casefold()]):
                raise RuntimeError("Accepted variant graph changed: " + name + "/" + key)
            spec[key] = paths[0].lower()
        spec["scene"] = relative.lower()
        io.apply(target, text)
        # Generated projection is scratch, not another project-owned scene.
        io.pending.pop(generated)
        if name in stages:
            stages[name].update(spec)
        else:
            config["integratedStages"].append(spec)
            stages[name] = spec
        if name not in decks:
            row = dict(name=name, asset="", cards=0, categories=0, excluded=0)
            config["stageCombatDecks"].append(row)
            decks[name] = row
        if relative not in recipe["nextStageScenes"]:
            recipe["nextStageScenes"].append(relative)
    # The map assigns these final J431 repairs to this step, even though their
    # original seven scene projections are composition products.
    for name in ("skymeadow", "shipgraveyard"):
        relative = "Assets/WholeGame/RoR2/Base/Scenes/" + name + "/" + name + ".unity"
        text, counts, _ = scene_contract((export / relative.replace("Assets/WholeGame/", "Assets/", 1)).read_text(), io.read_text(project / relative))
        io.apply(project / relative, text)
        stages[name].update(counts)
    for row in config["integratedStages"]:
        if row["name"] in VARIANTS:
            row["previewNames"] = sorted(row["previewNames"])
    added = include_runtime_graph_roots(config, recipe, project, accepted, io=io)
    # R3's regenerated manifest supplies pool identities; never follow live latest.
    pointer = io.read(io.catalog() / "integration-latest.json")["path"]
    from rebuild import relative_path

    if not pointer.startswith("destination/"):
        raise RuntimeError("Stage variants require regenerated R3 manifest")
    relative = pointer.removeprefix("destination/")
    relative_path(relative)
    manifest = project / relative / "manifest.json"
    if not manifest.is_relative_to(io.catalog()):
        raise RuntimeError("Stage manifest escapes regenerated catalog inputs")
    pool_keys = {}
    for row in io.read(manifest)["locations"]:
        if row["type"].startswith("RoR2.DccsPool,"):
            guid = re.search(r"^guid: ([a-f0-9]{32})$", io.read_text(project / (row["path"] + ".meta")), re.M)[1]
            if guid in pool_keys and pool_keys[guid] != row["primaryKey"]:
                raise RuntimeError("Ambiguous original stage pool identity")
            pool_keys[guid] = row["primaryKey"]
    # R5 precedes SourceScenes and its receipt. Emit population policy only; R7
    # regenerates strict receipt-bound identity metadata after R6 completes.
    contexts = original_stage_contexts(export, list(decks), input_id, pool_keys, include_source_identity=False)
    io.write(project / "Assets/LabLoadingScene/Resources/WholeStageContexts.json", contexts)
    io.write(config_path, config)
    io.write(recipe_path, recipe)
    result = dict(input_id=input_id, stages=pending, runtime_graph_roots_added=added)
    if getattr(io, "unity_deferred", None):
        result["unity_import_deferred"] = sorted(set(io.unity_deferred))
    io.write(out / "result.json", result)
    return result
