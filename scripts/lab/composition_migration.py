"""Stage an input-reviewed composition rebase without copying a Unity snapshot."""

from common import *
import hashlib
import re
from composition_io import StageIO


def private_path(value, io=None):
    io = io or StageIO()
    path = io.resolve(value).resolve()
    if io.work.resolve() not in path.parents:
        raise RuntimeError("Composition migration paths must remain ignored under work/")
    return path


def assembly_paths(project, generation, io=None):
    io = io or StageIO()
    result = {}
    for name, original in generation["original_assemblies"].items():
        matches = io.glob(project / "Assets", "**/" + name)
        expected = generation.get("transformed_assemblies", {}).get(name, original)
        if len(matches) != 1 or io.sha(matches[0]) != expected:
            raise RuntimeError("Current runtime assembly placement/identity is ambiguous: " + name)
        result[name] = str(matches[0].relative_to(project))
    return result


def restore_script_orders(project, source, io=None):
    """Retain shipped nonzero MonoScript orders on the corresponding runtime DLLs."""
    import UnityPy

    io = io or StageIO()

    generation = io.read(project / ".port-input.json")
    paths = assembly_paths(project, generation, io)
    selected = {}
    unavailable = []
    for obj in UnityPy.load(str(source)).objects:
        if obj.type.name != "MonoScript":
            continue
        row = obj.read_typetree()
        order = row.get("m_ExecutionOrder", 0)
        if not order:
            continue
        assembly = row["m_AssemblyName"]
        name = ".".join(filter(None, [row["m_Namespace"], row["m_ClassName"]]))
        if assembly not in paths:
            unavailable.append(dict(assembly=assembly, type=name, order=order))
            continue
        orders = selected.setdefault(assembly, {})
        if name in orders:
            raise RuntimeError("Duplicate original script execution-order owner")
        orders[name] = order
    plan = []
    for assembly, orders in selected.items():
        meta = Path(str(project / paths[assembly]) + ".meta")
        text = io.read_text(meta)
        match = re.search(r"^  executionOrder:(?: \{\})?\n(?:    .*\n)*", text, re.M)
        if not match:
            raise RuntimeError("Runtime plugin execution-order metadata missing: " + assembly)
        prior = {}
        for line in match[0].splitlines()[1:]:
            name, value = line.strip().rsplit(": ", 1)
            prior[name] = int(value)
        merged = dict(prior, **orders)
        block = "  executionOrder:\n" + "".join("    " + name + ": " + str(value) + "\n" for name, value in sorted(merged.items()))
        plan.append((meta, text[: match.start()] + block + text[match.end() :], dict(assembly=assembly, orders=orders, before_sha256=io.sha(meta))))
    # Validate all owners before writing any importer.
    for meta, text, row in plan:
        io.apply(meta, text, reason="restore original MonoScript execution orders")
        row["after_sha256"] = io.sha(meta)
    return dict(input_id=generation["input_id"], source_sha256=sha(source), restored=[row for _, _, row in plan], unavailable_assemblies=unavailable)


def scene_contract(source_text, staged_text):
    """Measure current reduced-scene contracts; retain the existing callback policy."""
    from serialization_rebase import objects, identity, hierarchy_keys

    header, rows = objects(staged_text)
    _, original = objects(source_text)
    # These are the existing measured MonoScript file IDs, not object file IDs.
    preview = "866789372"
    zone = "-376374237"
    network = "372142912"
    team = "-1895344032"

    def script(block):
        value = identity(block)[2]
        return re.search(r"fileID: (-?\d+)", value)[1] if value else None

    behaviours = {fid: block for fid, block in rows.items() if identity(block)[0] == "114"}
    for fid, block in behaviours.items():
        if fid not in original or identity(block) != identity(original[fid]):
            raise RuntimeError("Current scene callback differs from original identity: " + fid)
        if script(block) not in {preview, zone, network, team}:
            raise RuntimeError("Unreviewed reduced-scene callback: " + fid)
    zone_owners = {identity(block)[1] for block in behaviours.values() if script(block) == zone}
    # The type-based rebase can retain new network identities outside MapZones.
    # The accepted reduced-scene policy retained only zone-owned identities.
    removed = {fid for fid, block in behaviours.items() if script(block) in {network, team} and identity(block)[1] not in zone_owners}
    for fid in removed:
        del rows[fid]
    for fid, block in list(rows.items()):
        if identity(block)[0] == "1":
            rows[fid] = re.sub(r"^  - component: \{fileID: (-?\d+)\}\n", lambda m: "" if m[1] in removed else m[0], block, flags=re.M)
    paths = hierarchy_keys(rows)

    def decode_name(value):
        return json.loads(value) if value.startswith('"') else value[1:-1].replace("''", "'") if value.startswith("'") else value

    def name(owner):
        return decode_name(re.search(r"^  m_Name: (.*)$", rows[owner], re.M)[1])

    previews = [identity(block)[1] for fid, block in behaviours.items() if fid not in removed and script(block) == preview]
    active = sorted(name(owner) for owner in zone_owners if re.search(r"^  m_IsActive: 1$", original[owner], re.M))
    empty = {33: [], 64: [], 137: []}
    for fid, block in rows.items():
        kind, owner, _ = identity(block)
        if int(kind) in empty and re.search(r"^  m_Mesh: \{fileID: 0\}$", block, re.M):
            if not re.search(r"^  m_Mesh: \{fileID: 0\}$", original[fid], re.M):
                raise RuntimeError("Staging lost an original mesh reference: " + fid)
            empty[int(kind)].append("/".join(decode_name(part) for part in paths[owner]))
    counts = dict(
        previewCallbacks=len(previews),
        previewNames=sorted(name(owner) for owner in previews),
        mapZoneCount=len(zone_owners),
        mapZoneActiveNames=active,
        mapZoneNetworkObjects=sum(script(block) == network and fid not in removed for fid, block in behaviours.items()),
        emptyMeshPaths=sorted(empty[33] + empty[137]),
        emptyColliderPaths=sorted(empty[64]),
    )
    return header + "".join(rows.values()), counts, sorted(removed)


def refresh_scene_contracts(project, export, configuration, recipe, io=None):
    io = io or StageIO()
    observations = []
    stages = {row["scene"]: row for row in configuration["integratedStages"] if not row.get("moonMission")}
    for path in [recipe["stageScene"]] + [row["scene"] for row in configuration["integratedStages"] if not row.get("moonMission")]:
        staged = project / path
        source = export / ("Assets/" + path.removeprefix("Assets/WholeGame/"))
        before = io.sha(staged)
        text, counts, removed = scene_contract(source.read_text(), io.read_text(staged))
        if text != io.read_text(staged):
            io.apply(staged, text, source="recipe transform", reason="reduced-scene callback contract")
        if path == recipe["stageScene"]:
            configuration.update(
                stagePreviewCallbacks=counts["previewCallbacks"],
                stagePreviewNames=counts["previewNames"],
                stageMapZoneCount=counts["mapZoneCount"],
                stageMapZoneActiveNames=counts["mapZoneActiveNames"],
            )
        else:
            stages[path].update(counts)
        observations.append(
            dict(scene=path, source_sha256=sha(source), before_sha256=before, after_sha256=io.sha(staged), removed_nonzone_network_components=removed, **counts)
        )
    return observations


def stage_missing_sources(io=None):
    """Import current-source dependencies used only by the composed configuration."""
    from whole_catalog import repair_support_source
    from scene_closure import REFERENCE

    io = io or StageIO()
    io.preflight()
    project = io.project
    export = io.resolve(io.read(io.work / "config/reconstruction.json")["projects"][0])
    catalog = io.catalog()
    index = io.read(catalog / "source-guid-index.json")
    guids = {path: guid for guid, path in index.items()}
    selection = (
        dict(input_id=io.read(project / ".port-input.json")["input_id"], evidence="work/rebuild-dependencies")
        if io.rebuilding
        else io.read(io.work / "config/composition-migration.json")
    )
    evidence = private_path(selection["evidence"], io) / ("dependency-stage-" + now())
    io.mkdir(evidence)
    remaps = read(RECIPE / "hud-ui-remaps.json")
    if selection["input_id"] != io.read(project / ".port-input.json")["input_id"] or remaps["input_id"] != selection["input_id"]:
        raise RuntimeError("Composition dependency generation mismatch")
    owners = {}
    for meta in io.glob(project / "Assets", "**/*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", io.read_text(meta, errors="replace"), re.M)
        if match:
            if match[1] in owners:
                raise RuntimeError("Duplicate imported GUID owner")
            owners[match[1]] = str(Path(str(meta)[:-5]).relative_to(project))

    def paths(value):
        if isinstance(value, str):
            return {value} if value.startswith("Assets/") else set()
        if isinstance(value, dict):
            return paths(list(value.values()))
        if isinstance(value, (list, tuple)):
            return set().union(*(paths(item) for item in value)) if value else set()
        return set()

    required = paths(io.read(io.work / "scene-probe-build.json")) | paths(io.read(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"))
    deferred = sorted(path for path in required if path in io.deferred and not io.is_file(project / path))
    required -= set(deferred)
    missing = sorted(path for path in required if not io.is_file(project / path))
    if any(not path.startswith("Assets/WholeGame/") for path in missing):
        raise RuntimeError("Missing authored composition asset; refuse original-source substitution")
    pending = ["Assets/" + path.removeprefix("Assets/WholeGame/") for path in missing]
    mapped = {}
    copied = []
    unresolved = []
    while pending:
        relative = pending.pop()
        if relative in mapped:
            continue
        source = export / relative
        guid = guids.get(relative)
        if not guid or not source.is_file():
            raise RuntimeError("Composed current source missing: " + relative)
        existing = owners.get(guid)
        if existing and (not io.rebuilding or io.is_file(project / existing)):
            mapped[relative] = existing
            continue
        if source.suffix == ".dll":
            raise RuntimeError("Composed dependency needs an unprovided runtime assembly: " + relative)
        target_relative = existing or "Assets/WholeGame/" + relative.removeprefix("Assets/")
        target = project / target_relative
        io.apply(target, copy=source, catalog=True)
        io.apply(Path(str(target) + ".meta"), copy=Path(str(source) + ".meta"), catalog=True)
        mapped[relative] = target_relative
        owners[guid] = target_relative
        with source.open("rb") as stream:
            yaml = stream.read(5) == b"%YAML"
        if yaml:
            original = source.read_text()
            text = original
            for row in remaps["rows"]:
                text = text.replace(row["from"], row["to"])
            if text != original:
                io.apply(target, text)
            for _, dependency, _ in REFERENCE.findall(original):
                if not dependency or dependency.startswith("0000000000000000"):
                    continue
                if dependency in index:
                    pending.append(index[dependency])
                else:
                    unresolved.append(dict(source=relative, guid=dependency))
        copied.append(dict(source=relative, source_sha256=sha(source), target=target_relative, sha256=io.sha(target)))
    if io.rebuilding:
        support = "Assets/Scripts/Assembly-CSharp/AffixBeadProjectileSound.cs"
        if guids.get(support) in owners:
            mapped[support] = owners[guids[support]]
    repair_support_source(export, mapped, project, evidence, io)
    from integrated_objective import sanitize_optional_content

    sanitize_optional_content(project / "Assets/LabLoadingScene", evidence, project / "Assets/WholeGame", io=io)
    if any(not io.is_file(project / path) for path in required):
        raise RuntimeError("Composed paths remain missing after current dependency import")
    receipt = dict(input_id=selection["input_id"], missing_roots=missing, copied=copied, unresolved=unresolved)
    if deferred:
        receipt["deferred_to_later_steps"] = deferred
    io.write(evidence / "receipt.json", receipt)
    print(json.dumps(dict(missing_roots=len(missing), copied=len(copied), unresolved=len(unresolved), evidence=io.label(evidence))))


def prepare_asset_transforms(plan, transforms, export, previous, evidence, project, guids, io=None):
    """Validate all stage rows before writes; recipe rows need no historical asset bytes."""
    from asset_transforms import generate_asset

    io = io or StageIO()
    transformed = {}
    for row in plan["rows"]:
        if sha(export / row["source"]) != row["current_source_sha256"]:
            raise RuntimeError("Serialized rebase provenance drift: " + row["source"])
        if row["target"] not in transforms:
            output = evidence / "preview" / row["target"]
            if sha(output) != row["output_sha"] or sha(previous / row["old"]) != row["previous_adapted_sha256"]:
                raise RuntimeError("Serialized rebase provenance drift: " + row["source"])
        target = project / row["target"]
        if io.is_file(target) and io.sha(target) not in {row["target_before_sha256"], row["output_sha"]}:
            raise RuntimeError("Current project changed after the rebase: " + row["target"])
        if row["target"] in transforms:
            asset = transforms[row["target"]]
            if asset["source"] != row["source"] or asset["source_sha256"] != row["current_source_sha256"]:
                raise RuntimeError("Asset transform disagrees with composition provenance: " + row["target"])
            data, meta_data = generate_asset(export, asset, guids[row["source"]])
            if hashlib.sha256(data).hexdigest() != row["output_sha"]:
                raise RuntimeError("Asset transform differs from composition oracle: " + row["target"])
            meta = Path(str(target) + ".meta")
            if io.is_file(meta) and io.read_bytes(meta) != meta_data:
                raise RuntimeError("Current metadata differs from export importer: " + row["target"])
            if row["target"] in transformed:
                raise RuntimeError("Duplicate transformed composition target")
            transformed[row["target"]] = (data, meta_data)
    if transformed.keys() != transforms.keys():
        raise RuntimeError("Composition plan omits recipe asset transforms")
    return transformed


def normalize_addition(data, guidmap, remaps):
    if not data.startswith(b"%YAML"):
        return data
    text = re.sub(r"(?<=guid: )[a-f0-9]{32}", lambda match: guidmap.get(match[0], match[0]), data.decode())
    for row in remaps["rows"]:
        text = text.replace(row["from"], row["to"])
    return text.encode()


def stage_addition(row, authored, previous, project, guidmap, remaps, io=None, source="generator"):
    io = io or StageIO(work=project.parent)
    target = project / row["target"]
    if row["old"] in authored:
        data, meta_data = authored[row["old"]]
        io.apply(target, data, source=source, reason="addition owner output")
        io.apply(Path(str(target) + ".meta"), meta_data, source=source, reason="addition importer")
    else:
        source = previous / row["old"]
        io.apply(target, normalize_addition(source.read_bytes(), guidmap, remaps), reason="historical addition")
        io.apply(Path(str(target) + ".meta"), copy=Path(str(source) + ".meta"))


def plan_additions(rows, export, accepted, guidmap, remaps, work=None, ledger=None):
    """Plan every addition without reading previous_project or composition evidence.

    GUID translation is still supplied by the migration coordinator; this planner does
    not claim that the full coordinator's configuration/provenance reads are retired.
    """
    from asset_transforms import prepare_decks
    from authored_additions import prepare as authored_pairs
    from shader_additions import prepare as shader_pairs
    from export_additions import prepare as export_pairs
    from unity_package_additions import prepare as package_pairs
    from inherited_state import prepare as inherited_pairs

    prepared = {}
    groups = (
        authored_pairs(rows),
        shader_pairs(rows, work=work, ledger=ledger),
        prepare_decks(rows, export, accepted),
        export_pairs(rows, work=work, ledger=ledger),
        package_pairs(rows, work=work, ledger=ledger),
    )
    for pairs in groups:
        if prepared.keys() & pairs.keys():
            raise RuntimeError("Overlapping generated addition owners")
        prepared.update(pairs)
    inherited = inherited_pairs(rows, work=work, ledger=ledger)
    if prepared.keys() & inherited.keys():
        raise RuntimeError("Overlapping inherited addition owners")
    prepared.update({path: (normalize_addition(data, guidmap, remaps), meta) for path, (data, meta) in inherited.items()})
    if len({row["old"] for row in rows}) != len(rows) or prepared.keys() != {row["old"] for row in rows}:
        raise RuntimeError("Composition additions lack exactly one recipe/store owner")
    return prepared


def stage(io=None):
    io = io or StageIO()
    io.preflight()
    selection = read(io.work / "config/composition-migration.json")
    evidence = private_path(selection["evidence"], io)
    previous = private_path(selection["previous_project"], io)
    export = io.resolve(read(io.work / "config/reconstruction.json")["projects"][0])
    project = io.project
    accepted = read(io.work / "config/accepted-input.json")["input_id"]
    if selection["input_id"] != accepted or io.read(project / ".port-input.json")["input_id"] != accepted:
        raise RuntimeError("Composition rebase belongs to a different accepted input")
    if previous.resolve() == project.resolve():
        raise RuntimeError("Previous composition must remain a separate rollback")
    plan = read(evidence / "semantic-preview-result.json")
    if plan["conflicts"]:
        raise RuntimeError("Unresolved serialized rebase; refuse partial composition staging")
    catalog = io.resolve(read(io.work / "experiments/whole-catalog/latest.json")["path"])
    index = read(catalog / "source-guid-index.json")
    guids = {path: guid for guid, path in index.items()}
    owners = {}
    for meta in io.glob(project / "Assets", "**/*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", io.read_text(meta, errors="replace"), re.M)
        if match:
            if match[1] in owners:
                raise RuntimeError("Duplicate current GUID owner")
            owners[match[1]] = str(Path(str(meta)[:-5]).relative_to(project))
    remaps = read(RECIPE / "hud-ui-remaps.json")
    if remaps["input_id"] != accepted:
        raise RuntimeError("UI bindings belong to a different input")
    analysis = read(evidence / "asset-analysis.json")["rows"]
    path_overrides = selection.get("source_path_overrides", {})
    guidmap = read(evidence / "rebase-analysis.json")["guidmap"]
    removed = selection.get("removed_state_configs", {})
    if removed:
        proof = read(evidence / "removed-state-types.json")
        present = {row["name"] for row in proof["contract"]["types"]}
        if proof["contract"]["sha256"] != sha(game(io.work) / "Risk of Rain 2_Data/Managed/RoR2.dll"):
            raise RuntimeError("Removed state proof belongs to another input")
        for path, type_name in removed.items():
            if proof["paths"].get(path) != type_name or type_name in present:
                raise RuntimeError("State removal lacks exact current TypeDef absence evidence")
    removed_bindings = []
    assetmap = {}
    absent = []
    generated = []
    for row in analysis:
        old_path = row["old"]
        if row.get("old_source"):
            source = path_overrides.get(row["old_source"], row["old_source"])
            guid = guids.get(source)
            if not guid:
                absent.append(old_path)
                continue
            guidmap[row["guid"]] = guid
            assetmap[old_path.casefold()] = owners.get(guid, "Assets/WholeGame/" + source.removeprefix("Assets/"))
        else:
            if not old_path.startswith("Assets/LabLoadingScene/") or any(
                part.startswith(("Retired", "J371Archived", "J379Archived")) for part in Path(old_path).parts
            ):
                continue
            if row["kind"] == ".cs" or "/Editor/" in old_path or row["kind"] == ".xml" or Path(old_path).name == "WholeCatalogBootstrap.json":
                continue
            target = owners.get(row["guid"], old_path)
            assetmap[old_path.casefold()] = target
            generated.append(dict(row, target=target))
    missing_runtime = []

    def retarget(value):
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str) and item in removed:
                    removed_bindings.append(dict(asset=item, type=removed[item]))
                else:
                    result.append(retarget(item))
            return result
        if isinstance(value, dict):
            return {k: retarget(v) for k, v in value.items()}
        if isinstance(value, str) and value.casefold().startswith("assets/"):
            mapped = assetmap.get(value.casefold())
            if mapped is None:
                missing_runtime.append(value)
                return value
            return mapped
        return value

    config_path = previous / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"
    configuration = retarget(read(config_path))
    chest_source = export / "Assets/RoR2/Base/Interactables/Chest1/Chest1.prefab"
    costs = re.findall(r"^  cost: (\d+)$", chest_source.read_text(), re.M)
    if configuration.get("originalMoneyCost"):
        if costs != ["25"]:
            raise RuntimeError("Updated original Chest1 cost requires contract review")
        configuration["moneySourceSha256"] = sha(chest_source)
    recipe = io.read(io.work / "scene-probe-build.json")
    # Removed original inputs are not incompatibility quarantines or fallbacks.
    recipe["prefabAssets"] = [path for path in recipe["prefabAssets"] if path.casefold() in assetmap]
    recipe = retarget(recipe)
    if missing_runtime:
        io.apply(
            evidence / "missing-runtime-bindings.json",
            value=sorted(set(missing_runtime)),
            reason="unresolved runtime bindings from the current configuration/build recipe",
        )
        if not io.rebuilding:
            raise RuntimeError("Composition still references removed or unowned assets; inspect missing-runtime-bindings.json")

    # Historical plan/identity checks remain until their contracts have replacements.
    from asset_transforms import load_recipe

    transforms = {asset["output"]: asset for asset in load_recipe(accepted)["assets"]}
    if {row["target"] for row in plan["rows"]} != transforms.keys():
        raise RuntimeError("Current composition requires recipe coverage; historical preview fallback is disabled")
    transformed = prepare_asset_transforms(plan, transforms, export, previous, evidence, project, guids, io)
    authored = plan_additions(generated, export, accepted, guidmap, remaps, work=io.work)
    staged = []
    for row in generated:
        stage_addition(row, authored, None, project, guidmap, remaps, io)
        staged.append(row["target"])
    for row in plan["rows"]:
        target = project / row["target"]
        if row["target"] in transformed:
            data, meta_data = transformed[row["target"]]
            io.apply(target, data, source="recipe transform", reason="accepted serialized asset transform")
            io.apply(Path(str(target) + ".meta"), meta_data, source="recipe transform", reason="export importer for transformed asset")
            staged.append(row["target"])
            continue
        raise RuntimeError("Composition asset has no current recipe owner")
    # Native source outputs replace the old recovered resources by name. Their
    # current binary/tool receipts remain local; this does not assert PC parity.
    from inherited_state import load_ledger
    from shader_additions import cohort

    reproducible_shaders = {a["path"] for a in cohort(load_ledger())}
    native_names = set()
    from shader_rebuild import composition_sources

    for source in composition_sources(io, selection["shader_sources"]):
        receipt = read(source.parent / "receipt.json")
        if not receipt["success"]:
            raise RuntimeError("Current native binding generation failed")
        for file in source.iterdir():
            if file.is_file():
                if sha(file) != receipt["source_sha256_by_file"][file.name]:
                    raise RuntimeError("Native generated source drift")
                target = project / "Assets/LabLoadingScene/Resources" / file.name
                generated_pair = authored.get(str(target.relative_to(project)))
                if generated_pair is not None and str(target.relative_to(project)) not in reproducible_shaders:
                    generated_pair = None
                if generated_pair is not None:
                    if file.read_bytes() != generated_pair[0]:
                        raise RuntimeError("Native source differs from regenerated shader pair")
                else:
                    io.apply(target, copy=file, source="generator", reason="verified native shader output")
                native_names.add(file.name)
                staged.append(str(target.relative_to(project)))
    for path in io.glob(project / "Assets/LabLoadingScene/Resources", "AndroidNative*.shader"):
        if path.name not in native_names:
            io.apply(path, delete=True, reason="native shader absent from selected outputs")
            io.apply(Path(str(path) + ".meta"), delete=True, missing_ok=True, reason="obsolete native shader importer")
    global_textures = []
    for row in selection.get("native_global_textures", []):
        source = export / row["source"]
        target = project / "Assets/LabLoadingScene/Resources" / row["resource"]
        if source.suffix != ".png" or target.parent != project / "Assets/LabLoadingScene/Resources" or sha(source) != row["sha256"]:
            raise RuntimeError("Current original global texture identity changed")

        def importer(path):
            return re.sub(r"(?m)^(?:guid|timeCreated): .*\n", "", io.read_text(Path(str(path) + ".meta")))

        if importer(source) != importer(target):
            raise RuntimeError("Native global texture importer requires review")
        before = io.sha(target)
        io.apply(target, copy=source, source="export copy", reason="verified native global texture")
        global_textures.append(dict(row, before_sha256=before, after_sha256=io.sha(target)))
    io.apply(
        project / "Assets/LabLoadingScene/AndroidNativeDeferredPresentation.cs",
        copy=ROOT / "tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs",
        catalog=True,
        source="generator",
        reason="authored native presentation runtime",
    )
    configuration["attempt"] = evidence.name
    configuration["pauseBeforeMoon"] = True
    io.apply(
        project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json",
        value=configuration,
        source="config",
        reason="retargeted previous configuration and refreshed scene contracts",
    )
    io.apply(io.work / "scene-probe-build.json", value=recipe, source="config")
    # Reapply the accepted shared unavailable-presentation boundary as part of
    # importing the composed-only current dependencies.
    if not io.rebuilding:
        stage_missing_sources()
    scene_contracts = refresh_scene_contracts(project, export, configuration, recipe, io)
    io.apply(
        project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json",
        value=configuration,
        source="config",
        reason="retargeted previous configuration and refreshed scene contracts",
    )
    io.apply(evidence / "current-scene-contracts.json", value=scene_contracts)
    # A fresh attempt is necessary for existing build/run attribution. It is a
    # small receipt, never another project snapshot or inherited assembly proof.
    generation = io.read(project / ".port-input.json")
    io.apply(
        evidence / "current-original-script-orders.json",
        value=restore_script_orders(project, game(io.work) / "Risk of Rain 2_Data/globalgamemanagers.assets", io),
    )
    old_attempt = io.resolve(io.read(io.work / "experiments/scene-runtime/current.json")["path"])
    mapping = read(old_attempt / "nova-input-mapping.json")
    if sha(io.resolve(mapping["observation"])) != mapping["observation_sha256"]:
        raise RuntimeError("Accepted physical mapping evidence changed")
    mapping["attempt"] = evidence.name
    io.apply(evidence / "nova-input-mapping.json", value=mapping)
    probe = "body-state-spawn-state-auto-nova-spine-bringup"
    io.apply(
        evidence / "attempt.json",
        value=dict(
            attempt=evidence.name,
            input_id=accepted,
            stage=str(project / "Assets/LabLoadingScene"),
            original_assemblies=generation["original_assemblies"],
            transformed_assemblies=generation["transformed_assemblies"],
            assembly_paths=assembly_paths(project, generation, io),
            configuration_sha256=io.sha(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"),
            movement_batch=True,
            playable_spine=True,
            integrated_world=True,
            teleporter_loop=True,
            automated_menu_start=True,
            batch_ids=[probe],
            batch_seconds={probe: 900},
            batch_stop_when_complete=[probe],
            status="Updated composed generation staged; Android acceptance pending",
        ),
    )
    io.apply(io.work / "experiments/scene-runtime/current.json", value=dict(path="work/" + str(evidence.relative_to(io.work))))
    io.apply(
        evidence / "staging-result.json",
        value=dict(
            input_id=accepted,
            staged=len(set(staged)),
            source_adaptations=len(plan["rows"]),
            original_input_removals=absent,
            retargeted_assets=len(assetmap),
            native_sources=len(native_names),
            removed_state_bindings=removed_bindings,
            native_global_textures=global_textures,
            scope="Current ignored composition generation only; no Android or complete gameplay acceptance",
        ),
    )
    print(json.dumps(io.read(evidence / "staging-result.json")))
