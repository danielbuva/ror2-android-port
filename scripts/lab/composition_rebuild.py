"""R2's composition inputs from public recipes, replacing migration evidence B1, B3–B6 and B8 (J597).

`composition_migration.stage` takes its selection from `migration_inputs` in the real action.
The rebuild path passes the same fields built here, so R2 reads no previous project, no
composition evidence, no live content selection and no old run attempt:

- asset transforms: `recipe/asset-transforms.json` (B3's plan rows were exactly this set);
- additions: the 229 ledger rows in `recipe/inherited-state.json` (B4's addition rows);
- GUID rebase: only the 90 pairs that change inherited store bodies (from B5's 53,683);
- runtime config: the public `recipe/runtime-config.json`, reduced to the stages composition
  stages (B8 retargeted an older copy of the same rows); content: `recipe/content.json`;
- shader selection: `recipe/shader-rebuild-inputs.json`; global textures: `recipe/composition.json`.

Source GUIDs come from the catalog index R2–R4 regenerate on the host (`catalog_analysis`, J725). B6's removed-state proof
is unnecessary because the public config already omits those bindings.
"""

import copy
from pathlib import Path

from common import RECIPE, read


def catalog_input_path(work, destination, name):
    """One file of the destination's regenerated catalog analysis, never the live catalog pointer (J725)."""
    from catalog_analysis import OUTPUTS, ensure

    if name not in OUTPUTS:
        raise RuntimeError("Unknown catalog analysis output: " + name)
    return ensure(work, destination, read(Path(work) / "config/accepted-input.json")["input_id"]) / name


def catalog_input(work, destination, name):
    return read(catalog_input_path(work, destination, name))


def intermediate_config(runtime, stages):
    """The public runtime config as composition sees it: only the stages composition stages.

    Later steps add the remaining stages and R7 writes the full recipe.
    """
    if len(runtime["integratedStages"]) < stages or len(runtime["stageCombatDecks"]) < stages:
        raise RuntimeError("Composition stage selection exceeds the runtime recipe")
    configuration = copy.deepcopy(runtime)
    # Both lists keep composition's rows first, in its order; later steps append theirs.
    configuration["integratedStages"] = configuration["integratedStages"][:stages]
    configuration["stageCombatDecks"] = configuration["stageCombatDecks"][:stages]
    return configuration


def recipe_inputs(io):
    from asset_transforms import load_recipe
    from inherited_state import load_ledger

    accepted = read(io.work / "config/accepted-input.json")["input_id"]
    recipe = read(RECIPE / "composition.json")
    runtime = read(RECIPE / "runtime-config.json")
    if recipe["schema"] != 1 or recipe["input_id"] != accepted:
        raise RuntimeError("Composition recipe requires accepted input")
    index = catalog_input(io.work, io.project, "source-guid-index.json")
    plan = dict(
        conflicts=[],
        rows=[
            # A target may already exist only as its unchanged export copy.
            dict(
                source=asset["source"],
                current_source_sha256=asset["source_sha256"],
                target=asset["output"],
                output_sha=None,
                target_before_sha256=asset["source_sha256"],
            )
            for asset in load_recipe(accepted)["assets"]
        ],
    )
    ledger = load_ledger()
    if ledger["input_id"] != accepted:
        raise RuntimeError("Addition ledger requires accepted input")
    generated = [dict(old=a["path"], guid=a["guid"], target=a["project_path"], kind=Path(a["path"]).suffix) for a in ledger["assets"]]
    shaders = read(RECIPE / "shader-rebuild-inputs.json")
    evidence = io.work / "experiments/input-migration" / runtime["attempt"]
    configuration, content = intermediate_config(runtime, recipe["composition_stages"]), read(RECIPE / "content.json")
    # The binding receipt validate-bindings checks after R8: the public J565 targets, each of
    # which R2's configuration or content selection must name (the old retarget guard listed them).
    targets = read(RECIPE / "rebuild-binding-targets.json")
    named = set()

    def collect(value):
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str) and value.casefold().startswith("assets/"):
            named.add(value)

    collect(configuration)
    collect(content)
    if targets["input_id"] != accepted or not set(targets["targets"]) <= named:
        raise RuntimeError("Composition configuration does not name every J565 binding target")
    io.apply(evidence / "missing-runtime-bindings.json", value=sorted(targets["targets"]), reason="binding targets validated after R8")
    return dict(
        evidence=evidence,
        previous=None,
        plan=plan,
        guids={path: guid for guid, path in index.items()},
        guidmap=dict(recipe["inherited_guid_rebase"]),
        generated=generated,
        configuration=configuration,
        recipe=content,
        shader_sources=[group["selected_source"] for group in shaders["groups"]],
        native_global_textures=recipe["native_global_textures"],
        historical_receipts=False,
        receipt=dict(original_input_removals=[], retargeted_assets=0, removed_state_bindings=[]),
    )
