"""Host shader replay; retained recovery/fallback records are explicit rebuild debt."""

from pathlib import Path

from common import RECIPE, now, read, sha
from composition_io import StageIO


def pinned_inputs(work, recipe, input_id):
    from rebuild import relative_path

    if recipe["schema"] != 1 or recipe["input_id"] != input_id:
        raise RuntimeError("Shader rebuild recipe requires accepted input")
    for path, digest in recipe["files"].items():
        relative_path(path)
        source = work / path
        if not source.resolve().is_relative_to(work.resolve()) or sha(source) != digest:
            raise RuntimeError("Retained shader input drift: " + path)
    # Every generator read of private analysis must have an explicit hash gate.
    for group in recipe["groups"]:
        for key, value in group["selection"].items():
            if isinstance(value, str) and value.startswith("work/"):
                path = value.removeprefix("work/")
                required = [path] if key == "material_inventory" else [path + "/receipt.json", path + "/original-tree-base64.json"]
                if any(p not in recipe["files"] for p in required):
                    raise RuntimeError("Unpinned shader analysis input")
        independent = group["independent"]
        relative_path(independent)
        receipt_path = independent + "/receipt.json"
        if receipt_path not in recipe["files"]:
            raise RuntimeError("Unpinned shader output receipt")
        receipt = read(work / receipt_path)
        if not receipt["success"] or set(receipt["source_sha256_by_file"]) != set(group["outputs"]):
            raise RuntimeError("Shader selected output membership drift")
        from common import digest

        for program in receipt["programs"]:
            if "fallback" in program.get("origin", ""):
                stem = "program-" + digest(program["shader"])[:12] + "-" + str(program["index"])
                path = independent + "/" + stem + "-independent/" + stem + ".hlsl"
                if recipe["files"].get(path) != program["hlsl_sha256"]:
                    raise RuntimeError("Unpinned independent shader intermediate")


def shader_pipeline(destination, work, input_id, expected, provenance):
    import shader_deferred
    import shader_materials
    import shader_source

    from rebuild import relative_path

    io = StageIO(work, destination)
    recipe_path = RECIPE / "shader-rebuild-inputs.json"
    recipe = read(recipe_path)
    pinned_inputs(work, recipe, input_id)
    prefix = "Assets/LabLoadingScene/Resources/"
    membership = []
    for group in recipe["groups"]:
        for filename in group["outputs"]:
            relative_path(filename)
            if Path(filename).name != filename:
                raise RuntimeError("Shader output must be a basename")
            membership.append(prefix + filename)
    if len(membership) != len(set(membership)) or set(membership) != expected:
        raise RuntimeError("Shader recipe and provenance membership differ")
    from composition_io import initialize

    initialize(io, input_id)
    io.preflight()
    scratch = io.output(destination / ".rebuild/shader-pipeline" / now())
    scratch.mkdir(parents=True)
    generators = {"intersection": shader_source.generate, "deferred": shader_deferred.generate, "materials": shader_materials.generate}
    report = dict(
        input_id=input_id, recipe_sha256=sha(recipe_path), placed=[], blocked={}, sources=[], retained_inputs=len(recipe["files"]), recovery_regenerated=False
    )
    report["recovery_blocker"] = "shader_recovery.recover requires pinned native tools and a configured CrossOver bottle; retained records are hash-gated"
    for group in recipe["groups"]:
        name = group["name"]
        output = scratch / name
        kwargs = dict(output=output, work=work, root=work.parent, selection=group["selection"])
        if name != "intersection":
            kwargs["independent"] = work / group["independent"]
        try:
            # Native decompilation runs in destination scratch; isolated mode refuses
            # Wine/bottle writes. No selected final source is ever an input here.
            generators[name](**kwargs)
        except Exception as error:
            for filename in group["outputs"]:
                report["blocked"][prefix + filename] = str(error)
            continue
        emitted = {path.name for path in (output / "sources").iterdir()} if (output / "sources").is_dir() else set()
        if emitted != set(group["outputs"]):
            for filename in group["outputs"]:
                report["blocked"][prefix + filename] = "Generator output membership differs from recorded selection"
            continue
        for filename in group["outputs"]:
            path = prefix + filename
            source = output / "sources" / filename
            row = provenance[path]
            if not source.is_file():
                report["blocked"][path] = "Generator did not emit selected output"
            elif sha(source) != row["sha256"] or source.stat().st_size != row["size"]:
                report["blocked"][path] = "Regenerated bytes differ; retain J558 state until a device-verified replacement"
            else:
                io.apply(destination / path, copy=source)
                report["placed"].append(path)
        report["sources"].append(str((output / "sources").relative_to(destination)))
    report["complete"] = not report["blocked"]
    io.write(destination / ".rebuild/shader-pipeline-result.json", report)
    io.flush()
    return report


def composition_sources(io, selected):
    """Real actions retain historical selections; rebuild consumes freshly generated sources."""
    if not io.rebuilding:
        from composition_migration import private_path

        return [private_path(path, io) for path in selected]
    recipe_path = RECIPE / "shader-rebuild-inputs.json"
    recipe = read(recipe_path)
    report_path = io.project / ".rebuild/shader-pipeline-result.json"
    if not report_path.is_file():
        raise RuntimeError("Run shader-pipeline before composition")
    report = read(report_path)
    accepted = read(io.work / "config/accepted-input.json")["input_id"]
    if not report["complete"] or report["input_id"] != accepted or recipe["input_id"] != accepted or report["recipe_sha256"] != sha(recipe_path):
        raise RuntimeError("Shader replay blocked; inspect shader-pipeline-result.json")
    pinned_inputs(io.work, recipe, accepted)
    if selected != [group["selected_source"] for group in recipe["groups"]]:
        raise RuntimeError("Composition shader selection drift")
    from rebuild import relative_path

    sources = []
    for value in report["sources"]:
        relative_path(value)
        path = io.project / value
        if not path.resolve().is_relative_to((io.project / ".rebuild/shader-pipeline").resolve()):
            raise RuntimeError("Shader source escapes rebuild scratch")
        sources.append(path)
    if len(sources) != len(recipe["groups"]):
        raise RuntimeError("Incomplete shader replay sources")
    for group, source in zip(recipe["groups"], sources):
        retained = read(io.work / group["independent"] / "receipt.json")["source_sha256_by_file"]
        generated = read(source.parent / "receipt.json")
        if not generated["success"] or generated["source_sha256_by_file"] != retained:
            raise RuntimeError("Regenerated shader receipt drift")
        if {p.name for p in source.iterdir()} != set(group["outputs"]) or any(sha(source / name) != retained[name] for name in group["outputs"]):
            raise RuntimeError("Regenerated shader source drift")
    return sources
